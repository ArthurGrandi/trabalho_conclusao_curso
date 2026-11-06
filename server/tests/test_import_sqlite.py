import copy
import hashlib
import io
import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from server.import_sqlite import SQLiteImportError, import_sqlite_snapshot, main


class FakeRemote:
    """Model the schema's import receipt and collision contract, not its SQL."""

    def __init__(self):
        self.batches = {}
        self.dictionary_edits = {}
        self.receipts = {}
        self.calls = []
        self.before_write = None

    def query(self, sql, parameters, *, read_only=True):
        assert read_only is False
        assert parameters[4] not in sql
        assert "'" not in sql
        self.calls.append((sql, list(parameters)))
        if self.before_write:
            self.before_write()
        table = "dictionary_edits" if "import_dictionary_edit" in sql else "batches"
        documents = getattr(self, table)
        source_key, source_id, fingerprint, request_id, serialized = parameters
        self.assert_fingerprint(serialized, fingerprint)
        key = (source_key, table, source_id)
        if key in self.receipts:
            old_fingerprint, remote_id = self.receipts[key]
            if old_fingerprint != fingerprint:
                raise RuntimeError("changed source conflict")
            return [{"id": remote_id, "imported": False}]
        remote_id = source_id if source_id not in documents else max(documents, default=0) + 1
        body = json.loads(serialized)
        if table == "batches":
            body["id"] = remote_id
            if remote_id != source_id:
                body.setdefault("sample_seed", source_id)
        documents[remote_id] = body
        self.receipts[key] = (fingerprint, remote_id)
        return [{"id": remote_id, "imported": True}]

    @staticmethod
    def assert_fingerprint(serialized, expected):
        assert hashlib.sha256(serialized.encode("utf-8")).hexdigest() == expected


class SQLiteImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tcc-sqlite-import-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "platform.sqlite3"
        self.data = self.root / "ignored-local-data"
        self.remote = FakeRemote()
        self.settings = patch("server.import_sqlite.data_directory", return_value=self.data)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.batches = [
            {"id": 1, "created_at": "2026-10-15T13:00:00.123456+00:00", "annotations": {"a": 1}, "sample": {"fixed": True}, "title": "Confidencial: O'Reilly"},
            {"id": 2, "created_at": "2026-10-15T13:01:00+00:00", "annotations": {"b": 0}},
        ]
        self.edits = [{"id": "python", "alias": "python3", "created_at": "2026-10-15T12:00:00+00:00"}]
        with sqlite3.connect(self.source) as database:
            database.execute("CREATE TABLE batches (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            database.execute("CREATE TABLE dictionary_edits (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            for batch in self.batches:
                database.execute("INSERT INTO batches VALUES (?, ?)", (batch["id"], json.dumps(batch)))
            database.execute("INSERT INTO dictionary_edits VALUES (1, ?)", (json.dumps(self.edits[0]),))

    def read_rows(self, source, table="batches"):
        with sqlite3.connect(source) as database:
            return [json.loads(row[0]) for row in database.execute(f"SELECT body FROM {table} ORDER BY id")]

    def test_default_dry_run_has_no_remote_or_filesystem_writes(self):
        before = self.source.read_bytes()
        files = set(self.root.iterdir())
        report = import_sqlite_snapshot(self.source, self.remote)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["counts"], {"batches": 2, "dictionary_edits": 1})
        self.assertEqual(self.remote.calls, [])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), files)
        self.assertFalse(self.data.exists())
        self.assertNotIn("O'Reilly", json.dumps(report))

    def test_apply_backs_up_before_remote_write_and_retains_original_documents(self):
        def check_backup():
            backups = list((self.data / "backups").glob("*.sqlite3"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(self.read_rows(backups[0]), self.batches)

        self.remote.before_write = check_backup
        before = self.source.read_bytes()
        report = import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(report["imported"], {"batches": 2, "dictionary_edits": 1})
        self.assertEqual(report["id_mapping"]["batches"], {"1": 1, "2": 2})
        self.assertEqual(self.remote.batches, {body["id"]: body for body in self.batches})
        self.assertEqual(self.remote.dictionary_edits[1], self.edits[0])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(Path(report["backup"]).is_file())
        self.assertTrue(list((self.data / "import-state").glob("*.json")))

    def test_rerun_and_standalone_copy_reuse_receipts_without_overwriting_remote_edits(self):
        original = import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.remote.batches[1]["annotations"] = {"remote-review": 1}
        rerun = import_sqlite_snapshot(self.source, self.remote, apply=True)
        copied = self.root / "copied.sqlite3"
        shutil.copyfile(self.source, copied)
        copied_report = import_sqlite_snapshot(copied, self.remote, apply=True)
        self.assertEqual(original["source_key"], copied_report["source_key"])
        self.assertEqual(rerun["imported"], {"batches": 0, "dictionary_edits": 0})
        self.assertEqual(copied_report["skipped"], {"batches": 2, "dictionary_edits": 1})
        self.assertEqual(self.remote.batches[1]["annotations"], {"remote-review": 1})
        self.assertEqual(len(self.remote.batches), 2)
        # Stable UUIDs also make ambiguous HTTP retries safe.
        self.assertEqual(self.remote.calls[0][1][3], self.remote.calls[3][1][3])

    def test_collision_keeps_existing_remote_data_and_maps_sample_seed(self):
        existing = {"id": 1, "title": "Already remote"}
        self.remote.batches[1] = copy.deepcopy(existing)
        report = import_sqlite_snapshot(self.source, self.remote, apply=True)
        mapped = report["id_mapping"]["batches"]
        self.assertNotEqual(mapped["1"], 1)
        self.assertEqual(self.remote.batches[1], existing)
        imported = self.remote.batches[mapped["1"]]
        self.assertEqual(imported["sample_seed"], 1)
        self.assertEqual(imported["sample"], self.batches[0]["sample"])
        self.assertEqual(imported["annotations"], self.batches[0]["annotations"])
        self.assertEqual(imported["created_at"], self.batches[0]["created_at"])
        rerun = import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(rerun["id_mapping"], report["id_mapping"])

    def test_changed_source_is_rejected_without_replacing_imported_document(self):
        import_sqlite_snapshot(self.source, self.remote, apply=True)
        saved_remote = copy.deepcopy(self.remote.batches)
        changed = {**self.batches[0], "annotations": {"changed-locally": 1}}
        with sqlite3.connect(self.source) as database:
            database.execute("UPDATE batches SET body = ? WHERE id = 1", (json.dumps(changed),))
        with self.assertRaisesRegex(SQLiteImportError, "registro 1"):
            import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(self.remote.batches, saved_remote)
        self.assertEqual(self.read_rows(self.source)[0], changed)

    def test_snapshot_and_backup_are_stable_when_source_changes_during_import(self):
        def change_source_once():
            self.remote.before_write = None
            changed = {**self.batches[1], "annotations": {"later": 1}}
            with sqlite3.connect(self.source) as database:
                database.execute("UPDATE batches SET body = ? WHERE id = 2", (json.dumps(changed),))

        self.remote.before_write = change_source_once
        report = import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(self.remote.batches[2], self.batches[1])
        self.assertEqual(self.read_rows(report["backup"]), self.batches)
        self.assertNotEqual(self.read_rows(self.source), self.batches)

    def test_committed_wal_rows_are_included_in_consistent_backup(self):
        connection = sqlite3.connect(self.source)
        self.addCleanup(connection.close)
        connection.execute("PRAGMA journal_mode=WAL")
        third = {"id": 3, "created_at": "2026-10-15T14:00:00+00:00"}
        connection.execute("INSERT INTO batches VALUES (3, ?)", (json.dumps(third),))
        connection.commit()
        report = import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(report["counts"]["batches"], 3)
        self.assertEqual(self.remote.batches[3], third)
        self.assertEqual(self.read_rows(report["backup"])[2], third)

    def test_backup_failure_prevents_any_remote_write(self):
        with patch("server.import_sqlite._backup", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(SQLiteImportError, "não foi iniciada"):
                import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(self.remote.calls, [])
        self.assertEqual(self.read_rows(self.source), self.batches)

    def test_invalid_json_or_schema_fails_before_backups_and_remote_writes(self):
        with sqlite3.connect(self.source) as database:
            database.execute("UPDATE batches SET body = ? WHERE id = 2", ("not valid JSON: PRIVATE",))
        with self.assertRaises(SQLiteImportError) as failure:
            import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertNotIn("PRIVATE", str(failure.exception))
        self.assertFalse(self.data.exists())
        self.assertEqual(self.remote.calls, [])

    def test_corrupt_or_missing_database_does_not_create_an_empty_source(self):
        missing = self.root / "missing.sqlite3"
        with self.assertRaises(SQLiteImportError):
            import_sqlite_snapshot(missing)
        self.assertFalse(missing.exists())
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a SQLite database")
        with self.assertRaises(SQLiteImportError):
            import_sqlite_snapshot(corrupt, self.remote, apply=True)
        self.assertEqual(corrupt.read_bytes(), b"not a SQLite database")
        self.assertEqual(self.remote.calls, [])
        self.assertFalse(self.data.exists())

    def test_cli_defaults_to_dry_run_and_prints_counts_without_document_content(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["--source", str(self.source)])
        self.assertEqual(result, 0)
        report = json.loads(output.getvalue())
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["counts"]["batches"], 2)
        self.assertNotIn("Confidencial", output.getvalue())
        self.assertFalse(self.data.exists())

    def test_cli_apply_uses_checked_in_project_configuration_and_closes_client(self):
        constructor = Mock(return_value=self.remote)
        self.remote.close = Mock()
        module = SimpleNamespace(SupabaseStore=constructor, SupabaseStoreError=RuntimeError)
        with patch.dict("sys.modules", {"server.supabase_store": module}), \
                patch("server.persistence.storage_options", return_value=("supabase", self.data, "a" * 20)), \
                redirect_stdout(io.StringIO()):
            result = main(["--source", str(self.source), "--apply"])
        self.assertEqual(result, 0)
        constructor.assert_called_once_with(directory=self.data, project_ref="a" * 20)
        self.remote.close.assert_called_once()
        self.assertEqual(len(self.remote.batches), 2)

    def test_corrupt_import_manifest_prevents_new_backups_or_remote_writes(self):
        import_sqlite_snapshot(self.source, self.remote, apply=True)
        manifest = next((self.data / "import-state").glob("*.json"))
        manifest.write_text("{invalid manifest}")
        calls = len(self.remote.calls)
        backups = list((self.data / "backups").glob("*.sqlite3"))
        with self.assertRaisesRegex(SQLiteImportError, "manifesto"):
            import_sqlite_snapshot(self.source, self.remote, apply=True)
        self.assertEqual(len(self.remote.calls), calls)
        self.assertEqual(list((self.data / "backups").glob("*.sqlite3")), backups)
        self.assertTrue(self.source.is_file())
