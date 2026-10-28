import csv
import tempfile
from pathlib import Path
import unittest

from common import write
from expert_audit import blind_rag, ensure_blinded, import_reviews, outcome_bucket, select_evidence


class ExpertAuditTests(unittest.TestCase):
    def test_outcome_bucket_keeps_rare_boundaries(self):
        self.assertEqual(outcome_bucket({"outcome_type": "not_observed"}), "not_observed")
        self.assertEqual(outcome_bucket({"outcome_type": "not_significant"}), "rare_boundary")

    def test_blind_packet_rejects_private_keys(self):
        ensure_blinded([{"audit_id": "a", "options": ["x"]}])
        with self.assertRaisesRegex(ValueError, "leaks"):
            ensure_blinded([{"audit_id": "a", "correct_option": 0}])

    def test_available_rag_sample_requires_answer_and_frozen_evidence(self):
        row = {"question_id": "q", "question": "?", "arms": {
            "recovered": {"answer": None, "evidence_ids": ["e"], "citations": [], "task_id": "t"}}}
        with self.assertRaisesRegex(ValueError, "answer is missing"):
            blind_rag(row, "recovered_gain", {})
        row["arms"]["recovered"]["answer"] = "answer"
        with self.assertRaisesRegex(ValueError, "absent from frozen inputs"):
            blind_rag(row, "recovered_gain", {})

    def test_evidence_sample_uses_exact_split_and_outcome_targets(self):
        outcomes = {"not_observed": 12, "relative_weakening": 6,
                    "conditional_loss": 5, "reduced": 3, "not_significant": 4}
        splits = {
            "not_observed": (6, 3, 3), "relative_weakening": (5, 1, 0),
            "conditional_loss": (3, 1, 1), "reduced": (2, 0, 1),
            "not_significant": (4, 0, 0),
        }
        rows = []
        for outcome, total in outcomes.items():
            allocation = splits[outcome]
            for split, count in zip(("train", "val", "test"), allocation):
                for index in range(count):
                    rows.append({"evidence_id": f"{outcome}:{split}:{index}", "kind": "negative",
                                 "content_decision": "reliable", "outcome_type": outcome,
                                 "split": split, "doi": f"10.test/{outcome}/{split}/{index}",
                                 "values": {"endpoint": "protein degradation", "scope_condition": "x"},
                                 "conditions": {"items": [{"values": {"assay": "WB"}}]}})
        # The frozen contract expects 148 records; add unselected train records.
        for index in range(118):
            rows.append({"evidence_id": f"extra:{index}", "kind": "negative",
                         "content_decision": "reliable", "outcome_type": "not_observed",
                         "split": "train", "doi": f"10.test/extra/{index}",
                         "values": {"endpoint": "protein degradation", "scope_condition": "x"},
                         "conditions": {"items": [{"values": {"assay": "WB"}}]}})
        chosen = select_evidence(rows)
        self.assertEqual(__import__("collections").Counter(x["split"] for x in chosen),
                         {"train": 20, "val": 5, "test": 5})

    def test_duplicate_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write(package / "expert_packet.json", [{"audit_id": "a", "item_type": "evidence"}])
            write(package / "manifest.json", {"version": 1, "metadata": {}, "inputs": {}, "code": {},
                                               "files": {"expert_packet.json": __import__("common").sha(package / "expert_packet.json")}})
            response = root / "responses.csv"
            with response.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["audit_id", "reviewer_id", "decision"])
                writer.writeheader()
                writer.writerow({"audit_id": "a", "reviewer_id": "r", "decision": "accept"})
                writer.writerow({"audit_id": "a", "reviewer_id": "r", "decision": "accept"})
            result = import_reviews(package, [response], root / "out")
            self.assertEqual(result["unique_reviews"], 1)

    def test_import_rejects_invalid_response_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write(package / "expert_packet.json", [{"audit_id": "a", "item_type": "evidence"}])
            write(package / "manifest.json", {"version": 1, "metadata": {}, "inputs": {}, "code": {},
                                               "files": {"expert_packet.json": __import__("common").sha(package / "expert_packet.json")}})
            response = root / "responses.csv"
            with response.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["audit_id", "reviewer_id", "decision"])
                writer.writeheader()
                writer.writerow({"audit_id": "a", "reviewer_id": "r", "decision": "maybe"})
            with self.assertRaisesRegex(ValueError, "Invalid expert decision"):
                import_reviews(package, [response], root / "out")


if __name__ == "__main__":
    unittest.main()
