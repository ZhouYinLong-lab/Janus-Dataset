import unittest

from fixed_choice_eval import make_options, score_report


class FixedChoiceTests(unittest.TestCase):
    def test_options_have_one_correct_and_distractors(self):
        q = {"reference_answer": "subject=A；target=B；endpoint=C；observation=no change"}
        options = make_options(q, [], 0)
        self.assertEqual(len(options), 4)
        self.assertEqual(sum(o["category"] == "correct" for o in options), 1)
        self.assertEqual({o["category"] for o in options}, {"correct", "overclaim", "wrong_endpoint", "insufficient"})

    def test_report_keeps_single_seed_and_baselines(self):
        labels = [{"question_id": "q1", "correct_option": 0, "evaluation_group": "g"},
                  {"question_id": "q2", "correct_option": 1, "evaluation_group": "g"}]
        records = [{"question_id": "q1", "question": "A", "evidence": [],
                    "options": [{"category": "correct", "text": "A"}, {"category": "overclaim", "text": "Z"}]},
                   {"question_id": "q2", "question": "B", "evidence": [],
                    "options": [{"category": "overclaim", "text": "Z"}, {"category": "correct", "text": "B"}]}]
        preds = [{"model": "base", "question_id": "q1", "predicted_option": 0,
                  "predicted_category": "correct", "correct": True},
                 {"model": "base", "question_id": "q2", "predicted_option": 0,
                  "predicted_category": "overclaim", "correct": False}]
        report = score_report(preds, labels, records)
        self.assertTrue(report["single_seed"])
        self.assertIn("majority_accuracy", report["baselines"])
        self.assertIn("keyword_accuracy", report["baselines"])


if __name__ == "__main__":
    unittest.main()
