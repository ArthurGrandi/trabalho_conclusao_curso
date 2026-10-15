import unittest

from server.reporting import make_sample, validation_result


def annotated_batch():
    return {
        "results": {"fingerprint": "stable", "predicted_by_method": {
            "M1": {"job": [{"document_id": "j1", "competency_id": "c1"}, {"document_id": "j2", "competency_id": "c1"}], "ppc": [{"document_id": "d1", "competency_id": "c1"}]},
            "M2": {"job": [{"document_id": "j1", "competency_id": "c1"}, {"document_id": "j2", "competency_id": "c1"}], "ppc": [{"document_id": "d1", "competency_id": "c1"}]},
            "M3": {"job": [{"document_id": "j1", "competency_id": "c1"}], "ppc": [{"document_id": "d1", "competency_id": "c1"}], "evaluated_documents": {"job": ["j1"], "ppc": ["d1"]}},
            "A1": [{"job_id": "j1", "discipline_id": "d1", "related": True}, {"job_id": "j2", "discipline_id": "d2", "related": True}],
            "A2": [{"job_id": "j1", "discipline_id": "d1", "related": True}, {"job_id": "j1", "discipline_id": "d2", "related": False}],
        }},
        "annotations": {"primary": {"filename": "human.xlsx", "labels": {
            "extraction": [{"source": "jobs", "document_id": "j1", "competency_id": "c1", "label": True},
                           {"source": "jobs", "document_id": "j1", "competency_id": "c2", "label": False},
                           {"source": "jobs", "document_id": "j2", "competency_id": "c1", "label": False},
                           {"source": "ppc", "document_id": "d1", "competency_id": "c1", "label": True},
                           {"source": "ppc", "document_id": "d2", "competency_id": "c1", "label": True}],
            "associations": [{"job_id": "j1", "discipline_id": "d1", "label": True},
                             {"job_id": "j1", "discipline_id": "d2", "label": False},
                             {"job_id": "j2", "discipline_id": "d2", "label": False}],
        }}},
    }


class CommonSupportTests(unittest.TestCase):
    def test_partial_m3_restricts_every_method_to_same_documents_per_source(self):
        result = validation_result(annotated_batch())
        for source, expected_items in (("jobs", 2), ("ppc", 1)):
            rows = [row for row in result["extraction"] if row["source"] == source]
            self.assertEqual({row["method"] for row in rows}, {"M1", "M2", "M3"})
            self.assertEqual({row["items"] for row in rows}, {expected_items})
            self.assertEqual({row["documents"] for row in rows}, {1})
            self.assertTrue(all(row["fp"] == 0 and row["fn"] == 0 for row in rows))
            self.assertTrue(all("mesmo suporte" in row["scope_note"] for row in rows))
        self.assertFalse(any(row.get("document_id") in ("j2", "d2") for row in result["errors"]))

    def test_a2_limits_both_methods_to_effectively_judged_candidate_pairs(self):
        result = validation_result(annotated_batch())
        self.assertEqual({row["method"] for row in result["association"]}, {"A1", "A2"})
        self.assertEqual({row["items"] for row in result["association"]}, {2})
        self.assertTrue(all(row["fp"] == 0 and row["fn"] == 0 for row in result["association"]))
        self.assertEqual(result["supports"]["association"]["excluded_items"], 1)
        self.assertTrue(result["supports"]["association"]["candidate_only"])
        self.assertTrue(all("não representa todos" in row["scope_note"] for row in result["association"]))
        batch = annotated_batch()
        del batch["results"]["predicted_by_method"]["A2"]
        baseline = validation_result(batch)["association"][0]
        self.assertEqual(baseline["items"], 3)
        self.assertEqual(baseline["fp"], 1)

    def test_no_completed_m3_source_is_not_compared_or_counted_as_negative(self):
        batch = annotated_batch()
        batch["results"]["predicted_by_method"]["M3"]["evaluated_documents"]["ppc"] = []
        result = validation_result(batch)
        ppc = [row for row in result["extraction"] if row["source"] == "ppc"]
        self.assertEqual({row["method"] for row in ppc}, {"M1", "M2"})
        self.assertEqual({row["items"] for row in ppc}, {2})

    def test_blind_extraction_sample_contains_title_and_description(self):
        batch = {"id": 1, "jobs": [{"id": "j1", "title": "Desenvolvedor Python", "description": "Criar serviços de integração", "area": "Programação"}],
                 "disciplines": [{"id": "d1", "name": "Programação", "syllabus": "Algoritmos", "objectives": "Programar", "bibliography": "Não entra no texto"}]}
        sample = make_sample(batch, [{"id": "python", "name": "Python"}])
        row = next(row for row in sample["extraction"] if row["source"] == "jobs")
        self.assertEqual(row["text"], "Desenvolvedor Python\nCriar serviços de integração")
        self.assertEqual(row["present"], "")
        self.assertNotIn("prediction", row)
        self.assertTrue(all("Não entra" not in row["text"] for row in sample["extraction"]))


if __name__ == "__main__":
    unittest.main()
