import unittest

from server.areas import CANONICAL_AREAS, canonical_area, infer_area
from server.demo import demo_data
from server.engine import analyze
from server.uploads import deduplicate_jobs


class AreaTests(unittest.TestCase):
    def test_aliases_and_explicit_unknown_labels(self):
        for alias, expected in (("Backend", "Programação"), ("Inteligência artificial", "Dados"),
                                ("DevOps", "Infraestrutura"), ("Segurança", "Infraestrutura"),
                                ("Análise de sistemas", "Análise"), ("Help desk", "Suporte")):
            self.assertEqual(canonical_area(alias), expected)
        self.assertEqual(canonical_area("Marketing", "Desenvolvedor Java"), "Outra")

    def test_title_precedes_incidental_description_skills(self):
        self.assertEqual(canonical_area("", "Desenvolvedor Java", "Banco de dados e redes TCP/IP"), "Programação")
        self.assertEqual(canonical_area("", "Analista de suporte", "Banco de dados e cloud"), "Suporte")
        self.assertEqual(canonical_area("", "Especialista", "Administrar infraestrutura e redes"), "Infraestrutura")
        self.assertEqual(infer_area("Analista de dados e indicadores"), "Dados")

    def test_import_and_demo_share_the_same_categories(self):
        jobs, _ = deduplicate_jobs([{"title": "Desenvolvedor", "description": "Python e SQL", "area": "Front-end"}])
        self.assertEqual(jobs[0]["area"], "Programação")
        demo = demo_data()
        self.assertTrue(all(job["area"] in CANONICAL_AREAS for job in demo["jobs"]))
        self.assertEqual(len(demo["jobs"]), 30)
        self.assertEqual(len(demo["disciplines"]), 12)

    def test_area_denominators_partition_all_jobs(self):
        demo = demo_data()
        result = analyze(demo["disciplines"], demo["jobs"], demo["config"])
        self.assertEqual(sum(area["jobs"] for area in result["area_indicators"]), len(demo["jobs"]))
        self.assertEqual(sum(area["demand_count"] for area in result["area_indicators"]), result["indicators"]["total_demand"])


if __name__ == "__main__":
    unittest.main()
