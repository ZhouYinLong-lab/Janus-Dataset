import unittest

from fixed_choice_eval import make_options, score_report, validate_authored_options


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

    def test_hard_options_keep_labels_separate_and_balanced(self):
        questions, authored, evidence = [], [], {}
        for i in range(57):
            qid = f"q{i}"
            questions.append({"question_id": qid, "question": f"question {i}",
                              "reference_answer": f"reference answer {i}",
                              "evaluation_group": "g", "source_dois": ["10/x"]})
            evidence[qid] = [{"evidence_id": f"e{i}", "text": f"evidence {i}"}]
            correct = i % 4
            categories = ["overclaim", "wrong_endpoint", "insufficient"]
            options = []
            for j in range(4):
                category = "correct" if j == correct else categories.pop(0)
                options.append({"category": category,
                                "text": f"supported experimental statement {i} variant {j}",
                                "changed_field": None if category == "correct" else category})
            authored.append({"question_id": qid, "options": options, "correct_option": correct,
                             "evidence_ids_used": [f"e{i}"]})
        records, labels, issues, positions = validate_authored_options(authored, questions, evidence)
        self.assertEqual(len(records), 57)
        self.assertEqual(len(labels), 57)
        self.assertEqual(issues, [])
        self.assertEqual(sorted(positions.values()), [14, 14, 14, 15])
        self.assertNotIn("correct_option", records[0])

    def test_hard_options_reject_reference_copy_and_bad_evidence(self):
        questions = [{"question_id": "q", "question": "Q", "reference_answer": "exact answer"}]
        authored = [{"question_id": "q", "correct_option": 0, "evidence_ids_used": ["wrong"],
                     "options": [{"category": "correct", "text": "exact answer"},
                                 {"category": "overclaim", "text": "near answer", "changed_field": "direction"},
                                 {"category": "wrong_endpoint", "text": "near target", "changed_field": "target"},
                                 {"category": "insufficient", "text": "near support", "changed_field": "support"}]}]
        _, _, issues, _ = validate_authored_options(authored, questions, {"q": [{"evidence_id": "e"}]})
        self.assertIn("reference_copy", {x["code"] for x in issues})
        self.assertIn("evidence_identity", {x["code"] for x in issues})


if __name__ == "__main__":
    unittest.main()
