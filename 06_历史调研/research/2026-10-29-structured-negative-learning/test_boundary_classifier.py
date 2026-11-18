import importlib.util
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("boundary_classifier.py")
SPEC = importlib.util.spec_from_file_location("boundary_classifier", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class BoundaryClassifierTests(unittest.TestCase):
    def test_metric_reports_negative_false_positive_rate(self):
        result = MODULE.classification_metrics(
            np.asarray([0, 0, 1, 1]),
            np.asarray([0.2, 0.7, 0.6, 0.9]),
        )
        self.assertEqual(result["negative_false_positive_rate"], 0.5)
        self.assertEqual(result["accuracy"], 0.75)

    def test_training_row_keeps_doi_and_entity(self):
        row = {
            "mapping_id": "m1", "doi": "d1", "canonical_smiles": "CC",
            "target_normalized": "brd4", "e3": "DCAF16",
        }
        result = MODULE.as_training_row(row, 0, "recovered_negative")
        self.assertEqual(result["doi"], "d1")
        self.assertEqual(result["e3_normalized"], "dcaf16")
        self.assertEqual(MODULE.entity_key(result), ("CC", "brd4", "dcaf16"))

    def test_sampling_is_without_replacement(self):
        rows = [{"record_id": str(index)} for index in range(10)]
        sample = MODULE.sample_rows(rows, 5, np.random.default_rng(7))
        self.assertEqual(len({row["record_id"] for row in sample}), 5)


if __name__ == "__main__":
    unittest.main()
