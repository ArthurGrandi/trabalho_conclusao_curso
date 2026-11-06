from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import threading
import unittest
from email.utils import formatdate
from unittest.mock import patch

import httpx

from server.supabase_store import (
    SupabaseConfigurationError,
    SupabaseConflictError,
    SupabaseMigrationError,
    SupabaseStore,
    SupabaseUnavailableError,
)

PROJECT = "dcfcxrvjkvppulhhxvoq"
TOKEN = "only-a-fake-token-never-persist-this"


class FakeClock:
    def __init__(self):
        self.value = 1000.0
        self.wall = 1_800_000_000.0
        self.sleeps = []
        self.lock = threading.Lock()

    def monotonic(self):
        with self.lock:
            return self.value

    def wall_time(self):
        with self.lock:
            return self.wall

    def sleep(self, seconds):
        with self.lock:
            self.sleeps.append(seconds)
            self.value += seconds
            self.wall += seconds


class FakeDatabase:
    """A tiny transactional mock; HTTP and SQL parameter boundaries stay real."""
    def __init__(self):
        self.batches = {}
        self.edits = {}
        self.batch_requests = {}
        self.edit_requests = {}
        self.requests = []
        self.lock = threading.RLock()
        self.lose_create_reply = False
        self.lose_edit_reply = False
        self.lose_update_reply = False

    def handle(self, request):
        payload = json.loads(request.content)
        sql, params = payload["query"], payload["parameters"]
        with self.lock:
            self.requests.append((request, payload))
            if "to_regclass" in sql:
                return httpx.Response(201, json=[{key: True for key in ("batches_ready", "dictionary_ready", "create_batch_ready", "create_dictionary_ready")}])
            if "count(*)" in sql:
                return httpx.Response(201, json=[{"batches": len(self.batches), "dictionary_edits": len(self.edits)}])
            if "create_batch(" in sql:
                request_id, raw_body = params
                if request_id not in self.batch_requests:
                    identity = len(self.batches) + 1
                    self.batch_requests[request_id] = identity
                    self.batches[identity] = {"id": identity, "body": {**json.loads(raw_body), "id": identity}, "revision": 0}
                    if self.lose_create_reply:
                        self.lose_create_reply = False
                        raise httpx.ReadTimeout("Response lost after commit", request=request)
                return httpx.Response(201, json=[deepcopy(self.batches[self.batch_requests[request_id]])])
            if "create_dictionary_edit(" in sql:
                request_id, raw_body = params
                if request_id not in self.edit_requests:
                    identity = len(self.edits) + 1
                    self.edit_requests[request_id] = identity
                    self.edits[identity] = {"id": identity, "body": json.loads(raw_body)}
                    if self.lose_edit_reply:
                        self.lose_edit_reply = False
                        raise httpx.ReadTimeout("Response lost after commit", request=request)
                return httpx.Response(201, json=[deepcopy(self.edits[self.edit_requests[request_id]])])
            if sql.startswith("SELECT body FROM alinhamento.dictionary_edits"):
                return httpx.Response(201, json=[{"body": deepcopy(row["body"])} for _, row in sorted(self.edits.items())])
            if sql.startswith("SELECT id, body, revision FROM alinhamento.batches"):
                rows = ([deepcopy(self.batches[params[0]])] if params[0] in self.batches else []) if params else [deepcopy(row) for _, row in sorted(self.batches.items(), reverse=True)]
                return httpx.Response(201, json=rows)
            if sql.startswith("UPDATE alinhamento.batches"):
                raw_body, identity, expected_revision = params
                row = self.batches.get(identity)
                if row is None or row["revision"] != expected_revision:
                    return httpx.Response(201, json=[])
                row["body"] = json.loads(raw_body)
                row["revision"] += 1
                if self.lose_update_reply:
                    self.lose_update_reply = False
                    raise httpx.ReadTimeout("Response lost after commit", request=request)
                return httpx.Response(201, json=[deepcopy(row)])
            raise AssertionError(f"Unexpected fixed SQL: {sql}")


class SupabaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()
        self.clients = []
        self.clock = FakeClock()
        self.gates = patch.dict("server.supabase_store._REQUEST_GATES", {}, clear=True)
        self.gates.start()

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.gates.stop()

    def store(self, handler=None, **kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler or self.db.handle))
        self.clients.append(client)
        kwargs.setdefault("request_interval", 0)
        kwargs.setdefault("sleep", self.clock.sleep)
        kwargs.setdefault("clock", self.clock.monotonic)
        kwargs.setdefault("wall_clock", self.clock.wall_time)
        return SupabaseStore(project_ref=PROJECT, access_token=TOKEN, client=client, **kwargs)

    def test_configuration_is_required_without_local_fallback_or_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SupabaseConfigurationError):
                SupabaseStore()
            with self.assertRaises(SupabaseConfigurationError):
                SupabaseStore(project_ref=PROJECT)
        for value in ("https://evil.example", "x" * 19, "a" * 20 + "/evil", "A" * 20):
            with self.assertRaises(SupabaseConfigurationError):
                SupabaseStore(project_ref=value, access_token=TOKEN)
        self.assertEqual(self.db.requests, [])

    def test_create_uses_bound_json_and_header_only_credentials(self):
        store = self.store()
        body = {"name": "O'Reilly'); DROP TABLE batches; --", "nested": {"unicode": "Programação", "text": "line1\nline2\\path"}}
        created = store.create(body)
        self.assertEqual(created, {**body, "id": 1})
        self.assertNotIn("id", body)
        request, sent = self.db.requests[0]
        self.assertEqual(str(request.url), f"https://api.supabase.com/v1/projects/{PROJECT}/database/query")
        self.assertEqual(request.headers["Authorization"], f"Bearer {TOKEN}")
        self.assertNotIn(TOKEN, request.content.decode())
        self.assertNotIn("O'Reilly", sent["query"])
        self.assertEqual(json.loads(sent["parameters"][1]), body)
        self.assertFalse(sent["read_only"])
        self.assertNotIn(TOKEN, repr(store))
        self.assertNotIn(TOKEN, json.dumps(store.health_description()))

    def test_create_and_dictionary_retries_are_idempotent_after_lost_commit_response(self):
        store = self.store()
        self.db.lose_create_reply = self.db.lose_edit_reply = True
        self.assertEqual(store.create({"status": "review"})["id"], 1)
        edit = {"id": "python", "synonym": "Py", "context": ["dados"]}
        self.assertEqual(store.add_dictionary_edit(edit), edit)
        self.assertEqual(len(self.db.batches), 1)
        self.assertEqual(len(self.db.edits), 1)
        for marker in ("create_batch(", "create_dictionary_edit("):
            calls = [sent for _, sent in self.db.requests if marker in sent["query"]]
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["parameters"][0], calls[1]["parameters"][0])
        self.assertEqual(store.dictionary_edits(), [edit])

    def test_cache_returns_deep_copies_expires_and_invalidates_writes(self):
        store = self.store(cache_ttl=99)
        self.assertLessEqual(store._cache_ttl, .5)
        clock = [10.0]
        with patch("server.supabase_store.time.monotonic", side_effect=lambda: clock[0]):
            store.create({"nested": {"values": [1]}})
            before = len(self.db.requests)
            cached = store.get(1)
            cached["nested"]["values"].append(999)
            self.assertEqual(store.get(1)["nested"]["values"], [1])
            self.assertEqual(len(self.db.requests), before)
            clock[0] += .51
            self.assertEqual(store.get(1)["nested"]["values"], [1])
            self.assertEqual(len(self.db.requests), before + 1)
            store.update(1, lambda body: body["nested"]["values"].append(2))
            self.assertEqual(store.get(1)["nested"]["values"], [1, 2])
        self.assertIsNone(store.get(900))
        self.assertIsNone(store.update(900, lambda body: None))

    def test_two_store_instances_use_cas_and_preserve_concurrent_changes(self):
        first, second = self.store(cache_ttl=0), self.store(cache_ttl=0)
        first.create({"counter": 0, "events": []})
        barrier = threading.Barrier(2)
        calls = {}
        lock = threading.Lock()
        def write(store, name):
            def change(body):
                with lock:
                    calls[name] = calls.get(name, 0) + 1
                    attempt = calls[name]
                if attempt == 1:
                    barrier.wait(timeout=3)
                body["counter"] += 1
                body["events"].append(name)
            return store.update(1, change)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write, first, "first"), pool.submit(write, second, "second")]
            for future in futures:
                future.result(timeout=5)
        result = first.get(1)
        self.assertEqual(result["counter"], 2)
        self.assertEqual(set(result["events"]), {"first", "second"})
        self.assertEqual(sum(calls.values()), 3)
        self.assertEqual(self.db.batches[1]["revision"], 2)

    def test_lost_update_response_does_not_apply_callback_twice(self):
        store = self.store()
        store.create({"events": []})
        self.db.lose_update_reply = True
        calls = []
        def change(body):
            calls.append(True)
            body["events"].append("saved-once")
        self.assertEqual(store.update(1, change)["events"], ["saved-once"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.db.batches[1]["revision"], 1)

    def test_persistent_cas_conflicts_are_bounded_and_do_not_overwrite(self):
        def handler(request):
            payload = json.loads(request.content)
            if payload["query"].startswith("UPDATE alinhamento.batches"):
                return httpx.Response(201, json=[])
            return self.db.handle(request)
        store = self.store(handler)
        store.create({"counter": 0})
        calls = []
        def change(body):
            calls.append(True)
            body["counter"] += 1
        with self.assertRaises(SupabaseConflictError):
            store.update(1, change)
        self.assertEqual(len(calls), 5)
        self.assertEqual(self.db.batches[1]["body"]["counter"], 0)

    def test_auth_and_upstream_error_contents_never_leak(self):
        for status in (401, 403, 400, 500):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={"message": f"secret {TOKEN}; raw sql and private curriculum"})
            store = self.store(handler)
            with self.assertRaises((SupabaseConfigurationError, SupabaseUnavailableError)) as error:
                store.get(1)
            self.assertNotIn(TOKEN, str(error.exception))
            self.assertNotIn("private curriculum", str(error.exception))
            self.assertEqual(len(calls), 3 if status == 500 else 1)

    def test_missing_schema_or_functions_has_actionable_safe_migration_error(self):
        for code in ("42P01", "42883", "3F000", "42703"):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(500, json={"code": code, "message": f"secret {TOKEN}"})
            with self.assertRaises(SupabaseMigrationError) as error:
                self.store(handler).get(1)
            self.assertIn("migração", str(error.exception))
            self.assertNotIn(TOKEN, str(error.exception))
            self.assertEqual(len(calls), 1)

    def test_redirects_are_not_followed_and_retry_budget_is_bounded(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(302, headers={"Location": "https://evil.example/steal"})
        with self.assertRaises(SupabaseUnavailableError):
            self.store(handler).get(1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].url.host, "api.supabase.com")
        calls.clear()
        def limited(request):
            calls.append(request)
            return httpx.Response(429)
        with self.assertRaises(SupabaseUnavailableError):
            self.store(limited).get(1)
        self.assertEqual(len(calls), 3)

    def test_readiness_reports_only_safe_backend_details_and_counts(self):
        store = self.store()
        store.create({"private": "not public health data"})
        health = store.check_ready()
        self.assertTrue(health["ready"])
        self.assertEqual(health["backend"], "supabase")
        self.assertEqual(health["counts"], {"batches": 1, "dictionary_edits": 0})
        self.assertNotIn(TOKEN, json.dumps(health))
        self.assertNotIn("not public", json.dumps(health))
        reads = [sent for _, sent in self.db.requests if "create_batch" not in sent["query"] or "to_regclass" in sent["query"]]
        self.assertTrue(all(sent["read_only"] for sent in reads))
        def missing(request):
            return httpx.Response(201, json=[{"batches_ready": False}])
        with self.assertRaises(SupabaseMigrationError):
            self.store(missing).check_ready()

    def test_invalid_identifiers_and_nonfinite_json_fail_before_request(self):
        store = self.store()
        for identity in (True, 0, -1, "1;select 1"):
            with self.assertRaises(Exception):
                store.get(identity)
        with self.assertRaises(Exception):
            store.create({"bad": float("nan")})
        self.assertEqual(self.db.requests, [])

    def test_default_pacing_spaces_all_query_attempts_including_writes_and_retries(self):
        starts = []
        def handler(request):
            starts.append(self.clock.monotonic())
            return self.db.handle(request)
        store = self.store(handler, request_interval=.65, cache_ttl=0)
        self.db.lose_create_reply = True
        store.create({"counter": 0})
        store.get(1)
        store.update(1, lambda body: body.update(counter=1))
        self.assertEqual(len(starts), 5)
        self.assertTrue(all(later - earlier >= .649999 for earlier, later in zip(starts, starts[1:])))
        self.assertTrue(all(0 <= wait <= 60 for wait in self.clock.sleeps))

    def test_rate_gate_is_shared_across_store_instances(self):
        starts = []
        def handler(request):
            starts.append(self.clock.monotonic())
            return self.db.handle(request)
        first = self.store(handler, request_interval=.65)
        second = self.store(handler, request_interval=.65)
        first.get(100)
        second.get(200)
        first.get(300)
        self.assertEqual(len(starts), 3)
        self.assertTrue(all(later - earlier >= .649999 for earlier, later in zip(starts, starts[1:])))

    def test_429_honors_reset_window_without_repeating_write_with_new_request_id(self):
        starts, payloads = [], []
        def handler(request):
            starts.append(self.clock.monotonic())
            payloads.append(json.loads(request.content))
            if len(starts) == 1:
                return httpx.Response(429, headers={"X-RateLimit-Reset": "60", "X-RateLimit-Remaining": "0"})
            return self.db.handle(request)
        store = self.store(handler, request_interval=.65)
        created = store.create({"counter": 0})
        self.assertEqual(created["id"], 1)
        self.assertEqual(starts[1] - starts[0], 60)
        self.assertEqual(payloads[0]["parameters"], payloads[1]["parameters"])
        self.assertEqual(len(self.db.batches), 1)

    def test_retry_after_supports_seconds_http_dates_and_absolute_reset(self):
        store = self.store()
        self.assertEqual(store._header_delay("3"), 3)
        self.assertEqual(store._header_delay(formatdate(self.clock.wall_time() + 8, usegmt=True)), 8)
        self.assertEqual(store._header_delay(str(self.clock.wall_time() + 5), reset=True), 5)
        self.assertEqual(store._header_delay(str((self.clock.wall_time() + 6) * 1000), reset=True), 6)
        self.assertEqual(store._header_delay("9999999"), 60)
        self.assertIsNone(store._header_delay("invalid"))
        self.assertIsNone(store._header_delay("nan"))
        self.assertIsNone(store._header_delay("-2"))
        response = httpx.Response(429, headers={"Retry-After": "4", "X-RateLimit-Reset": "7"})
        self.assertEqual(store._rate_limit_delay(response), 7)

    def test_http_date_retry_after_is_respected_and_waits_are_bounded(self):
        starts = []
        retry_at = formatdate(self.clock.wall_time() + 9, usegmt=True)
        def handler(request):
            starts.append(self.clock.monotonic())
            if len(starts) == 1:
                return httpx.Response(429, headers={"Retry-After": retry_at})
            return httpx.Response(201, json=[])
        self.store(handler, request_interval=.65).get(1)
        self.assertEqual(starts[1] - starts[0], 9)
        self.assertTrue(all(wait <= 60 for wait in self.clock.sleeps))

    def test_exhausted_success_cools_down_the_next_instance_and_terminal_429_is_bounded(self):
        starts = []
        def handler(request):
            starts.append(self.clock.monotonic())
            if len(starts) == 1:
                return httpx.Response(201, json=[], headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "12"})
            return httpx.Response(201, json=[])
        first = self.store(handler, request_interval=.65)
        second = self.store(handler, request_interval=.65)
        first.get(1)
        second.get(2)
        self.assertEqual(starts[1] - starts[0], 12)
        attempts = []
        def limited(request):
            attempts.append(self.clock.monotonic())
            return httpx.Response(429, headers={"Retry-After": "9999"})
        with self.assertRaises(SupabaseUnavailableError):
            self.store(limited, request_interval=.65).get(1)
        self.assertEqual(len(attempts), 3)
        for earlier, later in zip(attempts, attempts[1:]):
            self.assertAlmostEqual(later - earlier, 60)
        self.assertTrue(all(wait <= 60 for wait in self.clock.sleeps))


if __name__ == "__main__":
    unittest.main()
