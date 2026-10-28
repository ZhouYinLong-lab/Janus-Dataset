import tempfile
from pathlib import Path
import unittest

from common import write
from mg2act_local_eval import cluster_delta, report_results, score_text


class MG2ActLocalTests(unittest.TestCase):
    def test_fixed_score_text_is_deterministic(self):
        self.assertEqual(score_text(0.2), '{"score":0.2}')

    def test_cluster_delta_keeps_pairs(self):
        a = [{"question_id": "q1", "target": "A", "Score": .2, "prediction": .1},
             {"question_id": "q2", "target": "B", "Score": .8, "prediction": .6}]
        b = [{"question_id": "q1", "target": "A", "Score": .2, "prediction": .4},
             {"question_id": "q2", "target": "B", "Score": .8, "prediction": .8}]
        result = cluster_delta(a, b, draws=100)
        self.assertEqual(result["paired"], 2)
        self.assertEqual(result["clusters"], 2)

    def test_report_keeps_missing_predictions_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "labels.json", [{"question_id": "q", "id": "1", "Score": .4,
                                           "target": "T", "source_dois": [], "fine_test": True}])
            write(root / "baselines.json", {"train_mean": .5, "train_median": .4,
                                             "target_train_mean": {"T": .3}})
            # The report contract requires every declared arm; absent arms remain missing.
            predictions = [{"question_id": "q", "output_arm": "base_structured",
                            "status": "failed", "reason": "x"}]
            report = report_results(root, predictions)
            self.assertEqual(report["models"]["base_structured"]["full_test"]["expected"], 1)
            self.assertEqual(report["models"]["base_structured"]["full_test"]["missing_or_invalid"], 1)
            self.assertEqual(report["baselines"]["target_train_mean"]["full_test"]["complete"], 1)


if __name__ == "__main__":
    unittest.main()
