import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from server.app import app, initialize_persistence, reset_store, recover_interrupted_batches, process_batch, store
from server.import_sqlite import SQLiteImportError
from server.persistence import storage_options, build_store, PersistenceConfigurationError
from server.supabase_store import SupabaseConfigurationError, SupabaseUnavailableError, SupabaseConflictError


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tcc-persistence-")
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {"TCC_DATA_DIR": self.directory.name, "TCC_STORAGE_BACKEND": "auto", "SUPABASE_PROJECT_REF": "", "SUPABASE_ACCESS_TOKEN": "", "TCC_IMPORT_SQLITE": "auto"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(reset_store)
        self.addCleanup(setattr, app.state, "persistence_error", None)
        reset_store()
        app.state.persistence_error = None

    def remote(self):
        return SimpleNamespace(
            source_name="supabase", check_ready=Mock(), dictionary_edits=Mock(return_value=[]),
            all=Mock(return_value=[]), create=Mock(), add_dictionary_edit=Mock(),
        )

    def test_without_credentials_auto_is_local(self):
        backend, directory, project = storage_options()
        self.assertEqual(backend, "sqlite")
        self.assertEqual(project, "dcfcxrvjkvppulhhxvoq")
        self.assertIsInstance(directory, Path)

    def test_existing_token_activates_linked_project(self):
        with patch.dict(os.environ, {"SUPABASE_ACCESS_TOKEN": "example-test-value"}):
            self.assertEqual(storage_options()[0], "supabase")

    def test_explicit_local_works_with_token_present(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"TCC_DATA_DIR": folder, "TCC_STORAGE_BACKEND": "sqlite", "SUPABASE_ACCESS_TOKEN": "example-test-value"}):
            self.assertEqual(build_store(storage_options()).source_name, "sqlite")

    def test_explicit_cloud_never_falls_back_without_token(self):
        with patch.dict(os.environ, {"TCC_STORAGE_BACKEND": "supabase"}):
            with self.assertRaises(SupabaseConfigurationError):
                build_store(storage_options())

    def test_invalid_backend_is_explicit_error(self):
        with patch.dict(os.environ, {"TCC_STORAGE_BACKEND": "unknown"}):
            with self.assertRaises(PersistenceConfigurationError):
                storage_options()

    def test_remote_start_does_not_cancel_other_workers(self):
        class Remote:
            source_name = "supabase"
            def all(self):
                raise AssertionError("A local startup must not inspect and cancel shared workers")
        with patch("server.app.store", return_value=Remote()):
            recover_interrupted_batches()

    def test_api_errors_are_useful_and_bounded(self):
        for error, status in [(SupabaseUnavailableError("Supabase temporariamente indisponível."), 503), (SupabaseConflictError("O lote mudou; tente novamente."), 409)]:
            with patch("server.app.store", side_effect=error), TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/batches")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["detail"], str(error))

    def test_startup_failure_keeps_health_endpoint_available(self):
        with patch("server.app._raw_store", side_effect=SupabaseConfigurationError("Verifique a credencial Supabase.")), TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/health")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "Verifique a credencial Supabase.")
        app.state.persistence_error = None

    def test_health_retry_recovers_after_transient_startup_failure(self):
        remote = self.remote()
        remote.check_ready.side_effect = [SupabaseUnavailableError("Conexão temporariamente indisponível."), None]
        with patch("server.app._raw_store", return_value=remote), TestClient(app) as client:
            self.assertIsNotNone(app.state.persistence_error)
            response = client.get("/api/health")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIsNone(app.state.persistence_error)
            self.assertEqual(client.get("/api/batches").json(), [])
            self.assertEqual(remote.check_ready.call_count, 2)

    def test_import_failure_blocks_reads_writes_and_background_store_access(self):
        remote = self.remote()
        Path(self.directory.name, "platform.sqlite3").touch()
        with patch("server.app._raw_store", return_value=remote), \
                patch("server.import_sqlite.import_sqlite_snapshot", side_effect=SQLiteImportError("Conflito na importação; origem preservada.")), \
                TestClient(app) as client:
            for method, path, body in (
                ("GET", "/api/batches", None),
                ("POST", "/api/demo", None),
                ("POST", "/api/dictionary", {"competency_id": "python", "alias": "python3"}),
            ):
                response = client.request(method, path, json=body)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.json()["detail"], "Conflito na importação; origem preservada.")
            with self.assertRaises(SupabaseUnavailableError):
                store()
            remote.all.assert_not_called()
            remote.create.assert_not_called()
            remote.add_dictionary_edit.assert_not_called()
            self.assertNotEqual(client.get("/").status_code, 503)

    def test_import_retry_unlocks_data_only_after_import_completes(self):
        remote = self.remote()
        Path(self.directory.name, "platform.sqlite3").touch()
        with patch("server.app._raw_store", return_value=remote), \
                patch("server.import_sqlite.import_sqlite_snapshot", side_effect=[SQLiteImportError("Importação interrompida."), {"counts": {"batches": 2}}]) as importer, \
                TestClient(app) as client:
            self.assertIsNotNone(app.state.persistence_error)
            response = client.get("/api/batches")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), [])
            self.assertIsNone(app.state.persistence_error)
            self.assertEqual(importer.call_count, 2)
            self.assertEqual(app.state.sqlite_import, {"counts": {"batches": 2}})

    def test_parallel_health_and_batches_share_one_retry_and_import(self):
        remote = self.remote()
        remote.check_ready.side_effect = [SupabaseUnavailableError("Conexão temporária."), None]
        Path(self.directory.name, "platform.sqlite3").touch()
        importing = threading.Event()
        queued_retry = threading.Event()
        release_import = threading.Event()
        retries = []

        def import_snapshot(*args, **kwargs):
            importing.set()
            if not release_import.wait(5):
                raise AssertionError("Concurrent request did not reach the retry guard")
            return {"counts": {"batches": 2}}

        def initialize(application, expected_generation=None):
            if expected_generation is not None:
                retries.append(expected_generation)
                if len(retries) == 2:
                    queued_retry.set()
            return initialize_persistence(application, expected_generation)

        with patch("server.app._raw_store", return_value=remote), \
                patch("server.import_sqlite.import_sqlite_snapshot", side_effect=import_snapshot) as importer, \
                patch("server.app.initialize_persistence", side_effect=initialize), TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=2) as workers:
                health = workers.submit(client.get, "/api/health")
                try:
                    self.assertTrue(importing.wait(5))
                    batches = workers.submit(client.get, "/api/batches")
                    self.assertTrue(queued_retry.wait(5))
                    remote.all.assert_not_called()
                finally:
                    release_import.set()
                self.assertEqual(health.result(timeout=10).status_code, 200)
                self.assertEqual(batches.result(timeout=10).status_code, 200)
            self.assertEqual(remote.check_ready.call_count, 2)
            self.assertEqual(importer.call_count, 1)
            self.assertEqual(retries[0], retries[1])

    def test_background_storage_failure_does_not_escape_response(self):
        with patch("server.app.store", side_effect=SupabaseUnavailableError("Supabase temporariamente indisponível.")), self.assertLogs("tcc", level="WARNING"):
            process_batch(1)
