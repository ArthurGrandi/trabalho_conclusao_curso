import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from server.app import collect_jobs, new_batch, store, validate_config
from server.uploads import deduplicate_jobs


class CollectionTests(unittest.TestCase):
    def test_deduplication_keeps_locations_and_checks_all_identities(self):
        base = {"title": "Dev", "company": "Empresa", "city": "Itajaí", "description": "Python", "source": "Indeed"}
        unique, removed = deduplicate_jobs([
            base,
            {**base, "description": "Python e SQL"},
            {**base, "city": "Camboriú"},
            {**base, "title": "Analista", "external_id": "external-1"},
            {**base, "title": "Analista de dados", "external_id": "external-1"},
            {**base, "title": "Suporte", "url": "https://example.test/vaga"},
            {**base, "title": "Suporte TI", "url": "https://example.test/vaga/"},
        ])
        self.assertEqual(removed, 3)
        self.assertEqual(len(unique), 4)
        self.assertEqual({job["city"] for job in unique}, {"Itajaí", "Camboriú"})

    def test_collector_converts_km_to_miles_without_external_requests(self):
        rows = pd.DataFrame([{"title": "Dev Python", "description": "Python e SQL", "company": "Empresa", "location": "Itajaí", "id": "indeed-id-1"}])
        scraper = Mock(return_value=rows)
        with tempfile.TemporaryDirectory(prefix="tcc-collection-") as directory, patch.dict(os.environ, {"TCC_DATA_DIR": directory}), patch.dict("sys.modules", {"jobspy": SimpleNamespace(scrape_jobs=scraper)}):
            config = validate_config({"source": "jobspy", "radius": 40, "target": 1, "terms": ["Python"], "methods": ["M2", "A1"]})
            ppc = {"filename": "ppc.pdf", "disciplines": [{"id": "d1", "name": "Programação", "syllabus": "Python", "period": 1, "hours": 60, "page": 1}]}
            batch = new_batch(config, ppc, [])
            collect_jobs(batch["id"])
            self.assertEqual(scraper.call_args.kwargs["distance"], 25)
            completed = store().get(batch["id"])
            self.assertFalse(completed["collection"]["running"])
            self.assertFalse(completed["collection"]["partial"])
            self.assertEqual(completed["jobs"][0]["external_id"], "indeed-id-1")
