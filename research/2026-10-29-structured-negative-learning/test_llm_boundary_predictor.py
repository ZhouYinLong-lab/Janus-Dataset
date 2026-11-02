import json
import tempfile
import unittest
from pathlib import Path

from llm_boundary_predictor import api_payload, build_user_prompt, parse_predictions, score_predictions


class LLMBoundaryPredictorTests(unittest.TestCase):
    def test_prompt_hides_test_labels_and_identity(self):
        tests = [{"task_id": "T1", "molecule_smiles": "CC", "target": "x", "e3_ligase": "crbn"}]
        demos = [{
            "molecule_smiles": "CCC", "target": "y", "e3_ligase": "crbn",
            "observed_degradation": 0,
        }]
        prompt = build_user_prompt("recovered_negative_fewshot", demos, tests)
        self.assertNotIn('"label"', prompt)
        self.assertNotIn('"doi"', prompt)
        self.assertNotIn('"source"', prompt)
        self.assertIn("observed_degradation", prompt)

    def test_parser_requires_exact_complete_task_set(self):
        content = json.dumps({"predictions": [
            {"task_id": "T1", "prediction": 0, "confidence": 0.8, "rationale": "boundary"},
            {"task_id": "T2", "prediction": 1, "confidence": 0.7, "rationale": "compatible"},
        ]})
        parsed = parse_predictions(content, ["T1", "T2"])
        self.assertEqual(len(parsed), 2)
        with self.assertRaises(ValueError):
            parse_predictions(content, ["T1", "T2", "T3"])

    def test_v4_pro_request_explicitly_disables_thinking(self):
        payload = api_payload("deepseek-v4-pro", "predict")
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_scoring_keeps_all_three_arms_and_seeds(self):
        labels = {}
        predictions = []
        for seed in (20261029, 20261030, 20261031):
            for index, label in enumerate((0, 1)):
                current_id = f"{seed}_{index}"
                labels[current_id] = {"seed": seed, "label": label}
                for arm in (
                    "zero_shot", "structured_negative_fewshot", "recovered_negative_fewshot"
                ):
                    predictions.append({
                        "task_id": current_id,
                        "seed": seed,
                        "arm": arm,
                        "prediction": label,
                        "confidence": 0.8,
                    })
        scored = score_predictions(predictions, labels)
        self.assertEqual(len(scored["runs"]), 9)
        self.assertEqual(len(scored["summary"]), 3)
        self.assertTrue(all(row["accuracy_mean"] == 1.0 for row in scored["summary"]))


if __name__ == "__main__":
    unittest.main()
