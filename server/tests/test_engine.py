"""Scientific invariants: evidence, scope, denominators and ambiguous terms."""
import copy
import unittest
from unittest.mock import patch

from server.dictionary import DICTIONARY, build_dictionary
from server.engine import analyze, find_matches


def entry(name):
    return next(item for item in DICTIONARY if item["name"] == name)


def discipline(identifier="d1", syllabus="", objectives="", bibliography=""):
    return {"id": identifier, "name": "Componente", "period": 1, "hours": 60,
            "page": 7, "syllabus": syllabus, "objectives": objectives, "bibliography": bibliography}


def job(identifier="j1", text="", area="Desenvolvimento"):
    return {"id": identifier, "title": "Oportunidade", "company": "Exemplo",
            "city": "Itajaí", "area": area, "date": "2026-01-01", "url": "", "description": text, "source": "csv"}


class MatchingTests(unittest.TestCase):
    def test_language_boundaries_and_punctuation(self):
        self.assertFalse(find_matches("JavaScript e MySQL", entry("Java")))
        self.assertFalse(find_matches("JavaScript e MySQL", entry("SQL")))
        self.assertFalse(find_matches("Linguagem C++ e C#", entry("C")))
        self.assertTrue(find_matches("Linguagem C++ e C#", entry("C++")))
        self.assertTrue(find_matches("Linguagem C++ e C#", entry("C#")))
        self.assertTrue(find_matches("Aplicações .NET e ASP.NET", entry(".NET")))

    def test_ambiguous_aliases_require_local_context(self):
        self.assertFalse(find_matches("Produto de 500 ML. Sala R. Go home.", entry("Machine Learning")))
        self.assertFalse(find_matches("Salário R$ 5.000 para análise de dados", entry("R")))
        self.assertFalse(find_matches("Registro R, nível C", entry("R")))
        self.assertTrue(find_matches("Análise de dados em R", entry("R")))
        self.assertTrue(find_matches("Treino de modelos ML com Python", entry("Machine Learning")))
        self.assertTrue(find_matches("RStudio", entry("R")))
        self.assertFalse(find_matches("Código interno AI aprovado.", entry("Inteligência Artificial")))
        self.assertTrue(find_matches("Modelos de IA generativa", entry("Inteligência Artificial")))

    def test_negation_and_contrast(self):
        for text in ("Não é necessário Java.", "Sem experiência em Java.", "Java não é obrigatório.", "Não exigimos conhecimento em Java."):
            self.assertFalse(find_matches(text, entry("Java")), text)
        self.assertTrue(find_matches("Não é necessário Java, mas Python é obrigatório.", entry("Python")))
        self.assertTrue(find_matches("Não apenas Java: Python também.", entry("Java")))

    def test_evidence_is_original_substring(self):
        text = "Objetivos: estudar ANÁLISE DE DADOS e desenvolver aplicações."
        match = find_matches(text, entry("Análise de dados"))[0]
        self.assertIn(match["text"], text)
        self.assertEqual(text[match["start"]:match["end"]], match["matched"])


class IndicatorTests(unittest.TestCase):
    def config(self, **changes):
        return {"source": "csv", "methods": ["M2", "A1"], "threshold": 30, **changes}

    def test_bibliography_cannot_inflate_coverage(self):
        result = analyze([discipline(bibliography="Python, React e Docker")], [job(text="Python, React e Docker")], self.config())
        self.assertEqual(result["indicators"]["i2"], 0)
        self.assertEqual(result["indicators"]["i4"], 0)
        self.assertEqual(result["associations"], [])
        self.assertTrue(all(item["status"] == "gap" for item in result["competencies"]))
        embedded = analyze([discipline(syllabus="Conteúdo introdutório.\nBibliografia complementar:\nPython e React")], [job(text="Python e React")], self.config())
        self.assertEqual(embedded["indicators"]["i2"], 0)

    def test_concept_candidate_is_outside_literal_coverage(self):
        result = analyze([discipline(syllabus="Desenvolvimento web com interfaces acessíveis.")], [job(text="React")], self.config())
        react = next(item for item in result["competencies"] if item["name"] == "React")
        self.assertEqual(react["status"], "partial")
        self.assertEqual(react["discipline_ids"], [])
        self.assertEqual(react["concept_discipline_ids"], ["d1"])
        self.assertEqual(result["indicators"]["i2"], 0)
        self.assertEqual(result["indicators"]["i4"], 100)
        self.assertEqual(result["associations"][0]["verdict"], "partial")

    def test_demand_weighting_and_per_job_deduplication(self):
        result = analyze([discipline(syllabus="Python")], [job("j1", "Python Python Python. React"), job("j2", "Python")], self.config())
        self.assertAlmostEqual(result["indicators"]["i2"], 66.67)
        python = next(item for item in result["competencies"] if item["name"] == "Python")
        self.assertEqual(python["count"], 2)
        self.assertEqual(python["percent"], 100)
        self.assertEqual(result["indicators"]["total_demand"], 3)
        self.assertEqual(result["indicators"]["priority_gap_count"], 1)

    def test_jaccard_and_ppc_without_demand(self):
        result = analyze([discipline(syllabus="Python e Java.")], [job("j1", "Python e React"), job("j2", "Python")], self.config())
        matrix = result["cooccurrence"]
        self.assertEqual(matrix["matrix"][0][0], 1)
        self.assertEqual(matrix["matrix"][0][1], .5)
        self.assertEqual(matrix["matrix"][1][0], .5)
        self.assertIn("Java", [item["name"] for item in result["ppc_without_demand"]])

    def test_empty_input_and_unavailable_methods_are_honest(self):
        with patch("server.engine.llm_status", return_value={"enabled": False, "message": "Sem credenciais"}):
            result = analyze([], [], self.config(methods=["M3", "A2"]))
        self.assertEqual(result["indicators"]["i2"], 0)
        self.assertEqual(result["summary"]["llm_calls"], 0)
        self.assertFalse(result["method_status"]["M3"]["executed"])
        self.assertFalse(result["method_status"]["A2"]["executed"])
        self.assertNotIn("M3", result["predicted_by_method"])

    def test_inputs_immutable_and_fingerprint_stable(self):
        disciplines, jobs, config = [discipline(syllabus="Python")], [job(text="Python")], self.config()
        before = copy.deepcopy((disciplines, jobs, config))
        first = analyze(disciplines, jobs, config)
        second = analyze(disciplines, jobs, config)
        self.assertEqual(before, (disciplines, jobs, config))
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        for association in first["associations"]:
            self.assertIn(association["job_excerpt"], jobs[0]["description"])
            self.assertIn(association["ppc_excerpt"], disciplines[0]["syllabus"])

    def test_m1_and_m2_predictions_and_curation_are_separate(self):
        result = analyze([], [job(text="Python e Terraform")], self.config(methods=["M1", "M2", "A1"]))
        self.assertEqual(len(result["predicted_by_method"]["M1"]["job"]), 1)
        self.assertEqual(len(result["predicted_by_method"]["M2"]["job"]), 2)
        overrides = {"python": {"synonym": "SerpenteLang"}}
        self.assertTrue(find_matches("SerpenteLang", next(item for item in build_dictionary(overrides) if item["id"] == "python")))
        self.assertFalse(find_matches("SerpenteLang", entry("Python")))

    def test_real_method_contract_keeps_model_output_separate(self):
        class Model:
            def __init__(self, **kwargs):
                pass

            def extract_competencies(self, text, **kwargs):
                return {"status": "completed", "competencies": [{"name": "Python", "excerpt": "Python"}]}

            def judge_pair(self, *args):
                return {"status": "completed", "verdict": "does_not_cover", "reason": "Conteúdo insuficiente para esta vaga.", "job_excerpt": "Python", "ppc_excerpt": "Python"}

            def stats(self):
                return {"calls": 3, "failed": 0, "cache_hits": 0, "discarded": 0, "executed_methods": ["M3", "A2"]}

        with patch("server.engine.llm_status", return_value={"enabled": True, "message": "Configurado"}), patch("server.engine.LLMClient", Model):
            result = analyze([discipline(syllabus="Python")], [job(text="Python")], self.config(tags="Python", methods=["M2", "A1", "M3", "A2"]))
        self.assertEqual(result["indicators"]["i2"], 100)  # Lexical quantity is independent of semantic verdict.
        self.assertEqual(result["summary"]["llm_calls"], 3)
        self.assertEqual(result["predicted_by_method"]["M3"]["evaluated_documents"], {"job": ["j1"], "ppc": ["d1"]})
        self.assertEqual(result["predicted_by_method"]["A2"][0]["related"], False)
        self.assertEqual([item["verdict"] for item in result["associations"]], ["covers", "none"])

    def test_failed_model_documents_are_not_negative_predictions(self):
        class Model:
            def __init__(self, **kwargs):
                pass

            def extract_competencies(self, text, **kwargs):
                return {"status": "budget_exhausted"}

            def stats(self):
                return {"calls": 0, "failed": 0, "cache_hits": 0, "discarded": 0, "executed_methods": []}

        with patch("server.engine.llm_status", return_value={"enabled": True, "message": "Configurado"}), patch("server.engine.LLMClient", Model):
            result = analyze([discipline(syllabus="Python")], [job(text="Python")], self.config(methods=["M2", "M3"]))
        self.assertNotIn("M3", result["predicted_by_method"])
        self.assertTrue(result["llm"]["partial"])
        self.assertEqual(result["llm"]["pending_documents"], 2)


if __name__ == "__main__":
    unittest.main()
