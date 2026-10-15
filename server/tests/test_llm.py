"""Offline contracts for optional LLM methods. Every HTTP uses MockTransport."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from server.llm import LLMClient, llm_status


KEY = "unit-test-secret-never-return"
JOB = {"id": "j1", "description": "Desenvolver modelos com Python e SQL."}
DISCIPLINE = {"id": "d1", "page": 42, "syllabus": "Programação em Python. Algoritmos e funções.",
              "objectives": "Resolver problemas com algoritmos.", "bibliography": "Livro: Kubernetes avançado."}
VALID_JUDGMENT = {"verdict": "covers", "reason": "Python é explicitamente ensinado.",
                  "job_excerpt": "Python e SQL", "ppc_excerpt": "Programação em Python."}


def envelope(payload):
    return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}


class LLMTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict("os.environ", {"TCC_LLM_API_KEY": KEY, "OPENAI_API_KEY": "",
                                              "TCC_LLM_BASE_URL": "https://api.openai.com/v1",
                                              "TCC_LLM_MODEL": "gpt-4o-mini"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def client(self, handler, **kwargs):
        return LLMClient(self.folder.name, transport=httpx.MockTransport(handler), **kwargs)

    def test_missing_credentials_disable_network_and_persistence(self):
        with patch.dict("os.environ", {"TCC_LLM_API_KEY": "", "OPENAI_API_KEY": ""}):
            client = self.client(lambda request: self.fail("Network must not be called"))
            result = client.judge_pair(JOB, DISCIPLINE, "Python")
            self.assertFalse(client.enabled)
            self.assertEqual(result["status"], "disabled")
            self.assertEqual(client.stats()["calls"], 0)
            self.assertEqual(client.stats()["executed_methods"], [])
            self.assertEqual(list(Path(self.folder.name).iterdir()), [])
            self.assertIn("configure", llm_status()["message"])

    def test_existing_openai_key_is_reused_without_returning_it(self):
        with patch.dict("os.environ", {"TCC_LLM_API_KEY": "", "OPENAI_API_KEY": KEY}):
            status = llm_status()
            self.assertTrue(status["enabled"])
            self.assertNotIn(KEY, json.dumps(status))
            self.assertNotIn("base_url", status)

    def test_insecure_remote_and_embedded_credentials_rejected(self):
        for base in ("http://provider.invalid/v1", "https://user:secret@provider.invalid/v1", "https://provider.invalid/v1?key=value"):
            with self.subTest(base=base), patch.dict("os.environ", {"TCC_LLM_BASE_URL": base}):
                client = self.client(lambda request: self.fail("Invalid URL must not be contacted"))
                self.assertFalse(client.enabled)
                self.assertEqual(client.extract_competencies("Python")["status"], "disabled")

    def test_verified_judgment_has_strict_contract_and_excludes_bibliography(self):
        def handler(request):
            self.assertEqual(request.url, "https://api.openai.com/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer " + KEY)
            body = json.loads(request.content)
            self.assertEqual(body["temperature"], 0)
            self.assertTrue(body["response_format"]["json_schema"]["strict"])
            self.assertNotIn("Kubernetes", request.content.decode())
            return httpx.Response(200, json=envelope(VALID_JUDGMENT))
        client = self.client(handler)
        result = client.judge_pair(JOB, DISCIPLINE, {"name": "Python"})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"], "covers")
        self.assertTrue(result["verified"])
        self.assertEqual(result["page"], 42)
        self.assertEqual(client.stats()["executed_methods"], ["A2"])
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn(KEY.encode(), (Path(self.folder.name) / "llm_cache.sqlite3").read_bytes())

    def test_hallucinated_and_bibliography_quotes_are_discarded(self):
        for quote in ("Texto que nunca existiu.", "Livro: Kubernetes avançado.", "Python... algoritmos"):
            with self.subTest(quote=quote):
                raw = {**VALID_JUDGMENT, "ppc_excerpt": quote}
                client = self.client(lambda request: httpx.Response(200, json=envelope(raw)))
                result = client.judge_pair(JOB, DISCIPLINE, "Python")
                self.assertEqual(result["status"], "discarded")
                self.assertNotIn("verdict", result)
                self.assertEqual(client.stats()["discarded"], 1)

    def test_ppc_bibliography_heading_is_excluded_even_inside_syllabus(self):
        discipline = {"syllabus": "Introdução a Python.\nBibliografia básica:\nLivro Kubernetes.", "objectives": ""}
        def handler(request):
            self.assertNotIn("Kubernetes", request.content.decode())
            return httpx.Response(200, json=envelope({**VALID_JUDGMENT, "ppc_excerpt": "Livro Kubernetes."}))
        self.assertEqual(self.client(handler).judge_pair(JOB, discipline, "Python")["status"], "discarded")

    def test_extraction_discards_unsupported_quotes_and_out_of_scope_names(self):
        raw = {"competencies": [{"name": "Python", "excerpt": "Python e SQL"},
                                {"name": "Docker", "excerpt": "Python e SQL"},
                                {"name": "SQL", "excerpt": "Consulta inventada"}]}
        client = self.client(lambda request: httpx.Response(200, json=envelope(raw)))
        result = client.extract_competencies(JOB["description"], competency_names=["Python", "SQL"])
        self.assertEqual(result["competencies"], [{"name": "Python", "excerpt": "Python e SQL"}])
        self.assertEqual(len(result["discarded"]), 2)
        self.assertEqual(client.stats()["discarded"], 2)

    def test_extraction_excludes_bibliography_and_allows_empty_results(self):
        def handler(request):
            self.assertNotIn("Kubernetes", request.content.decode())
            return httpx.Response(200, json=envelope({"competencies": []}))
        result = self.client(handler).extract_competencies("Python.\nBibliografia:\nKubernetes.", source="ppc")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["competencies"], [])

    def test_cache_survives_new_client_and_works_after_budget_exhaustion(self):
        client = self.client(lambda request: httpx.Response(200, json=envelope(VALID_JUDGMENT)), max_calls=1)
        first = client.judge_pair(JOB, DISCIPLINE, "Python")
        second = client.judge_pair(JOB, DISCIPLINE, "Python")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(second["calls"], 0)
        self.assertEqual(client.stats()["calls"], 1)
        reloaded = self.client(lambda request: self.fail("Cache must avoid HTTP"), max_calls=0)
        self.assertTrue(reloaded.judge_pair(JOB, DISCIPLINE, "Python")["cached"])
        self.assertEqual(reloaded.stats()["cache_hits"], 1)

    def test_input_and_model_changes_do_not_reuse_old_cache(self):
        self.client(lambda request: httpx.Response(200, json=envelope(VALID_JUDGMENT))).judge_pair(JOB, DISCIPLINE, "Python")
        with patch.dict("os.environ", {"TCC_LLM_MODEL": "another-model"}):
            client = self.client(lambda request: httpx.Response(200, json=envelope(VALID_JUDGMENT)))
            self.assertFalse(client.judge_pair(JOB, DISCIPLINE, "Python")["cached"])
            self.assertFalse(client.judge_pair({**JOB, "description": JOB["description"] + " Docker."}, DISCIPLINE, "Python")["cached"])
            self.assertEqual(client.stats()["calls"], 2)

    @patch("server.llm.time.sleep")
    def test_retries_respect_global_call_budget(self, sleep):
        client = self.client(lambda request: httpx.Response(429, text="rate limited"), max_calls=2)
        result = client.judge_pair(JOB, DISCIPLINE, "Python")
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["calls"], 2)
        self.assertEqual(client.stats()["calls"], 2)
        self.assertEqual(client.stats()["failed"], 2)
        self.assertEqual(client.stats()["executed_methods"], [])

    @patch("server.llm.time.sleep")
    def test_timeout_retries_are_bounded(self, sleep):
        def handler(request):
            raise httpx.ReadTimeout("test timeout", request=request)
        client = self.client(handler)
        result = client.judge_pair(JOB, DISCIPLINE, "Python")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(client.stats()["calls"], 3)
        self.assertEqual(sleep.call_count, 2)

    def test_auth_errors_are_not_retried_or_reflected(self):
        client = self.client(lambda request: httpx.Response(401, text="secret echoed: " + KEY))
        result = client.judge_pair(JOB, DISCIPLINE, "Python")
        self.assertEqual(client.stats()["calls"], 1)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn(KEY, json.dumps(result))

    def test_strict_json_rejects_fences_duplicate_keys_nonfinite_and_wrong_types(self):
        invalid = ["```json\n{}\n```", '{"competencies":[],"competencies":[]}',
                   '{"competencies":NaN}', '{"competencies":"Python"}',
                   '{"competencies":[{"name":"Python","excerpt":"Python","extra":true}]}']
        for content in invalid:
            with self.subTest(content=content):
                client = self.client(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}))
                result = client.extract_competencies("Python")
                self.assertEqual(result["status"], "failed")
                self.assertEqual(client.stats()["failed"], 1)

    def test_provider_cannot_return_the_api_key_in_valid_schema(self):
        client = self.client(lambda request: httpx.Response(200, json=envelope({**VALID_JUDGMENT, "reason": KEY})))
        result = client.judge_pair(JOB, DISCIPLINE, "Python")
        self.assertEqual(result["status"], "failed")
        self.assertNotIn(KEY, json.dumps(result))

    def test_empty_and_oversized_sources_do_not_consume_calls(self):
        client = self.client(lambda request: self.fail("Invalid source must not be sent"))
        self.assertEqual(client.extract_competencies("")["status"], "failed")
        self.assertEqual(client.extract_competencies("x" * 60001)["status"], "failed")
        self.assertEqual(client.stats()["calls"], 0)


if __name__ == "__main__":
    unittest.main()
