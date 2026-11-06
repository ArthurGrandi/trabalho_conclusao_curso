"""Real PostgreSQL integration tests for the private Supabase migration.

Opt in with TCC_TEST_POSTGRES_CONTAINER=<dedicated local PostgreSQL container>.
The fixture creates and removes its own database; it never connects to Supabase.
No database driver or new application dependency is required.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid


MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def payload(value):
    return literal(json.dumps(value, ensure_ascii=False)) + "::jsonb"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@unittest.skipUnless(os.getenv("TCC_TEST_POSTGRES_CONTAINER"), "Requires the explicitly selected local PostgreSQL test container")
class SupabasePostgresTests(unittest.TestCase):
    @classmethod
    def psql(cls, sql, database=None, check=True):
        # Parent provisions this local daemon/container. Do not inherit a remote
        # Docker context or Docker TLS selectors into this integration fixture.
        environment = dict(os.environ)
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            environment.pop(key, None)
        command = ["docker", "--host=unix:///var/run/docker.sock", "exec", "-i", cls.container,
                   "psql", "-X", "-q", "-U", "postgres", "-d", database or cls.database,
                   "-v", "ON_ERROR_STOP=1", "-A", "-t"]
        result = subprocess.run(command, input=sql, text=True, capture_output=True, env=environment, timeout=45)
        if check and result.returncode:
            raise AssertionError("Local PostgreSQL operation failed: " + result.stderr)
        return result

    @classmethod
    def setUpClass(cls):
        cls.container = os.environ["TCC_TEST_POSTGRES_CONTAINER"]
        cls.database = "tcc_migration_test_" + str(os.getpid())
        cls.psql("""DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN BYPASSRLS; END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='alinhamento_test_reader') THEN CREATE ROLE alinhamento_test_reader NOLOGIN; END IF;
        END $$;""", database="postgres")
        cls.psql('CREATE DATABASE "' + cls.database + '";', database="postgres")
        try:
            files = sorted(MIGRATIONS.glob("*.sql"))
            if not files:
                raise AssertionError("No Supabase migration was found")
            for migration in files:
                cls.psql(migration.read_text())
        except Exception:
            cls.psql('DROP DATABASE "' + cls.database + '" WITH (FORCE);', database="postgres")
            raise

    @classmethod
    def tearDownClass(cls):
        cls.psql('DROP DATABASE "' + cls.database + '" WITH (FORCE);', database="postgres")

    def setUp(self):
        self.psql("TRUNCATE alinhamento.sqlite_imports, alinhamento.batches, alinhamento.dictionary_edits RESTART IDENTITY CASCADE;")

    def rows(self, sql):
        result = self.psql("SELECT coalesce(jsonb_agg(to_jsonb(q)), '[]'::jsonb) FROM (" + sql.rstrip("; ") + ") q;")
        return json.loads(result.stdout)

    def create(self, body, request=None):
        request = request or uuid.uuid4()
        return self.rows("SELECT * FROM alinhamento.create_batch(" + literal(request) + "::uuid," + payload(body) + ")")[0]

    def import_batch(self, source_id, body, source="local:test-source", request=None, digest=None):
        return self.rows("SELECT * FROM alinhamento.import_batch(" + ",".join((literal(source), str(source_id), literal(digest or fingerprint(body)), literal(request or uuid.uuid4()) + "::uuid", payload(body))) + ")")[0]

    def test_private_rls_invoker_views_and_functions(self):
        tables = self.rows("SELECT c.relname,c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='alinhamento' AND c.relkind='r'")
        self.assertEqual({row["relname"] for row in tables}, {"batches", "dictionary_edits", "sqlite_imports"})
        self.assertTrue(all(row["relrowsecurity"] for row in tables))
        self.assertEqual(self.rows("SELECT count(*) AS n FROM pg_policies WHERE schemaname='alinhamento'")[0]["n"], 0)
        views = self.rows("SELECT c.relname,c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='alinhamento' AND c.relkind='v'")
        self.assertEqual({row["relname"] for row in views}, {"disciplines", "jobs", "associations", "annotations", "evidence", "validation"})
        self.assertTrue(all("security_invoker=true" in row["reloptions"] for row in views))
        self.assertEqual(self.rows("SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='alinhamento' AND p.prosecdef")[0]["n"], 0)
        for role in ("anon", "authenticated"):
            self.assertFalse(self.rows("SELECT has_schema_privilege(" + literal(role) + ",'alinhamento','USAGE') AS allowed")[0]["allowed"])
            self.assertFalse(self.rows("SELECT has_table_privilege(" + literal(role) + ",'alinhamento.batches','SELECT') AS allowed")[0]["allowed"])
            self.assertFalse(self.rows("SELECT has_function_privilege(" + literal(role) + ",'alinhamento.create_batch(uuid,jsonb)','EXECUTE') AS allowed")[0]["allowed"])
            denied = self.psql("SET ROLE " + role + "; SELECT * FROM alinhamento.batches;", check=False)
            self.assertNotEqual(denied.returncode, 0)
        self.create({"disciplines": [{"id": "d1"}]})
        self.psql("GRANT USAGE ON SCHEMA alinhamento TO alinhamento_test_reader; GRANT SELECT ON alinhamento.disciplines, alinhamento.batches TO alinhamento_test_reader;")
        # Invoker view respects the caller's RLS restrictions on its base table.
        self.assertEqual(self.psql("SET ROLE alinhamento_test_reader; SELECT count(*) FROM alinhamento.disciplines;").stdout.strip(), "0")

    def test_create_is_idempotent_after_updates_and_does_not_overwrite(self):
        request = uuid.uuid4()
        original = {"status": "review", "unexpected": {"keep": [1, None, "ação"]}}
        first = self.create(original, request)
        self.assertEqual(first["id"], first["body"]["id"])
        self.assertEqual(first["body"]["unexpected"], original["unexpected"])
        changed = {**first["body"], "status": "completed", "new_field": True}
        self.psql("UPDATE alinhamento.batches SET body=" + payload(changed) + ",revision=revision+1 WHERE id=" + str(first["id"]) + ";")
        retry = self.create(original, request)
        self.assertEqual(retry["id"], first["id"])
        self.assertEqual(retry["revision"], 1)
        self.assertEqual(retry["body"], changed)
        conflict = self.psql("SELECT * FROM alinhamento.create_batch(" + literal(request) + "::uuid,'{\"different\":true}'::jsonb);", check=False)
        self.assertNotEqual(conflict.returncode, 0)
        self.assertEqual(self.rows("SELECT count(*) AS n FROM alinhamento.batches")[0]["n"], 1)

    def test_compare_and_swap_rejects_stale_revision(self):
        row = self.create({"status": "review"})
        sql = "WITH changed AS (UPDATE alinhamento.batches SET body=jsonb_set(body,'{status}','\"completed\"'),revision=revision+1 WHERE id=" + str(row["id"]) + " AND revision=0 RETURNING body,revision) SELECT coalesce(jsonb_agg(to_jsonb(changed)), '[]'::jsonb) FROM changed;"
        self.assertEqual(json.loads(self.psql(sql).stdout)[0]["revision"], 1)
        self.assertEqual(json.loads(self.psql(sql).stdout), [])

    def test_dictionary_preserves_competency_id_and_request_idempotence(self):
        edit = {"id": "python", "synonym": "SerpenteLang", "custom": {"note": "literal"}}
        request = uuid.uuid4()
        sql = "SELECT * FROM alinhamento.create_dictionary_edit(" + literal(request) + "::uuid," + payload(edit) + ")"
        first, retry = self.rows(sql)[0], self.rows(sql)[0]
        self.assertEqual(first, retry)
        self.assertIsInstance(first["id"], int)
        self.assertEqual(first["body"], edit)
        conflict = self.psql("SELECT * FROM alinhamento.create_dictionary_edit(" + literal(request) + "::uuid,'{\"id\":\"java\"}'::jsonb);", check=False)
        self.assertNotEqual(conflict.returncode, 0)

    def test_import_preserves_free_ids_and_advances_identity(self):
        original = {"id": 100, "created_at": "2026-01-01T00:00:00Z", "unknown": {"legacy": True}}
        imported = self.import_batch(100, original)
        self.assertTrue(imported["imported"])
        self.assertEqual(imported["id"], 100)
        self.assertEqual(imported["body"], original)
        self.assertGreater(self.create({"status": "review"})["id"], 100)
        # A lower unused legacy identity remains available without rewinding.
        self.assertEqual(self.import_batch(5, {"id": 5})["id"], 5)
        self.assertGreater(self.create({"status": "review"})["id"], 100)

    def test_import_collision_maps_without_overwriting_and_preserves_seed(self):
        existing = self.create({"status": "existing"})
        original = {"id": existing["id"], "status": "legacy", "sample": {"frozen": True}}
        imported = self.import_batch(existing["id"], original)
        self.assertNotEqual(imported["id"], existing["id"])
        self.assertEqual(imported["body"]["sample_seed"], existing["id"])
        self.assertEqual(imported["body"]["id"], imported["id"])
        self.assertEqual(self.rows("SELECT body FROM alinhamento.batches WHERE id=" + str(existing["id"]))[0]["body"], existing["body"])
        mapping = self.rows("SELECT source_id,remote_id,original_body FROM alinhamento.sqlite_imports")[0]
        self.assertEqual(mapping["original_body"], original)
        self.assertEqual(mapping["remote_id"], imported["id"])
        seeded = {"id": existing["id"], "sample_seed": "explicit-seed"}
        other = self.import_batch(existing["id"], seeded, source="another-source")
        self.assertEqual(other["body"]["sample_seed"], "explicit-seed")

    def test_import_retry_returns_current_remote_body_and_conflicts_are_atomic(self):
        original = {"id": 8, "status": "review"}
        first = self.import_batch(8, original)
        self.psql("UPDATE alinhamento.batches SET body=jsonb_set(body,'{status}','\"completed\"'),revision=revision+1 WHERE id=8;")
        retry = self.import_batch(8, original)
        self.assertFalse(retry["imported"])
        self.assertEqual(retry["id"], first["id"])
        self.assertEqual(retry["body"]["status"], "completed")
        for changed, digest in (({"id": 8, "status": "modified"}, "f" * 64), ({"id": 8, "status": "tampered"}, fingerprint(original))):
            sql = "SELECT * FROM alinhamento.import_batch('local:test-source',8," + literal(digest) + "," + literal(uuid.uuid4()) + "::uuid," + payload(changed) + ");"
            self.assertNotEqual(self.psql(sql, check=False).returncode, 0)
        self.assertEqual(self.rows("SELECT count(*) AS n FROM alinhamento.batches")[0]["n"], 1)
        self.assertEqual(self.rows("SELECT count(*) AS n FROM alinhamento.sqlite_imports")[0]["n"], 1)

    def test_import_dictionary_collision_preserves_raw_domain_id(self):
        self.rows("SELECT * FROM alinhamento.create_dictionary_edit(" + literal(uuid.uuid4()) + "::uuid,'{\"id\":\"java\"}'::jsonb)")
        edit = {"id": "python", "context": ["dados"], "extra": 12}
        sql = "SELECT * FROM alinhamento.import_dictionary_edit('legacy',1," + literal(fingerprint(edit)) + "," + literal(uuid.uuid4()) + "::uuid," + payload(edit) + ")"
        first, retry = self.rows(sql)[0], self.rows(sql)[0]
        self.assertNotEqual(first["id"], 1)
        self.assertEqual(first["body"], edit)
        self.assertFalse(retry["imported"])
        self.assertEqual(first["id"], retry["id"])

    def test_audit_views_preserve_unknown_fields_and_guard_old_shapes(self):
        evidence = {"source": "ppc", "source_id": "d1", "text": "Python", "page": 3, "section": "syllabus", "unknown": "kept"}
        llm_evidence = {"source": "job", "source_id": "j1", "competency_id": "python", "name": "Python", "text": "Python", "method": "M3", "verified": True}
        label = {"document_id": "j1", "competency_id": "python", "label": True, "research_note": "kept"}
        body = {"disciplines": [{"id": "d1", "name": "Algoritmos", "arbitrary": [1, 2]}],
                "jobs": [{"id": "j1", "title": "Python", "external_field": {"a": 1}}],
                "results": {"competencies": [{"id": "python", "evidence": [evidence]}],
                            "associations": [{"id": "a1:j1:d1:python", "method": "A1", "evidence": [evidence], "custom": True}],
                            "llm": {"competencies": [llm_evidence]}},
                "annotations": {"primary": {"filename": "labels.xlsx", "labels": {"extraction": [label]}}},
                "validation": {"status": "annotated", "extension": {"nested": True}}}
        self.create(body)
        self.assertEqual(self.rows("SELECT raw FROM alinhamento.disciplines")[0]["raw"], body["disciplines"][0])
        self.assertEqual(self.rows("SELECT raw FROM alinhamento.jobs")[0]["raw"], body["jobs"][0])
        self.assertEqual(self.rows("SELECT raw FROM alinhamento.associations")[0]["raw"], body["results"]["associations"][0])
        self.assertEqual(self.rows("SELECT raw FROM alinhamento.annotations")[0]["raw"], label)
        self.assertEqual(self.rows("SELECT raw FROM alinhamento.validation")[0]["raw"], body["validation"])
        evidence_rows = self.rows("SELECT owner_type,raw FROM alinhamento.evidence")
        self.assertCountEqual([row["raw"] for row in evidence_rows], [evidence, evidence, llm_evidence])
        self.assertIn("llm_competency", [row["owner_type"] for row in evidence_rows])
        self.create({"disciplines": "old-shape", "jobs": None, "results": {"associations": {}}, "annotations": []})
        self.assertEqual(self.rows("SELECT count(*) AS n FROM alinhamento.disciplines")[0]["n"], 1)

    def test_concurrent_create_and_import_are_idempotent(self):
        request = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=4) as pool:
            created = list(pool.map(lambda _: self.create({"status": "same"}, request), range(4)))
        self.assertEqual(len({row["id"] for row in created}), 1)
        import_request = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=4) as pool:
            imported = list(pool.map(lambda _: self.import_batch(50, {"id": 50}, request=import_request), range(4)))
        self.assertEqual(len({row["id"] for row in imported}), 1)
        self.assertEqual(sum(row["imported"] for row in imported), 1)


if __name__ == "__main__":
    unittest.main()
