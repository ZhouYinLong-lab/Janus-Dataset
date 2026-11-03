import json
import tempfile
import unittest
from pathlib import Path

from offline_gate import validate_batch_gate, validate_gate


def _report(**changes):
    value = {
        "gate_schema_version": 1,
        "status": "shadow_ready_for_full_readable",
        "allow_full_extraction": True,
        "source_hashes_stable": True,
        "raw_workspace_untouched": True,
        "blockers": [],
        "paragraphs": {"unresolved": 0},
        "citation": {"support_rate": 1.0},
        "failures": [],
    }
    value.update(changes)
    return value


class OfflineGateTests(unittest.TestCase):
    def test_accepts_valid_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(json.dumps(_report()), encoding="utf-8")
            self.assertEqual(validate_gate(path)["status"], "shadow_ready_for_full_readable")

    def test_rejects_blocked_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(json.dumps(_report(status="shadow_blocked")), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_gate(path)

    def test_rejects_unresolved_paragraphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gate.json"
            path.write_text(json.dumps(_report(paragraphs={"unresolved": 1})), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_gate(path)

    def test_accepts_ready_batch_gate(self):
        report = {
            "schema_version": 1, "status": "batch_ready_for_next", "allow_next_batch": True,
            "hard_blockers": [], "source_hashes_stable": True, "failures": [],
            "citation_support_rate": 0.95, "tasks": {"complete": 10},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertTrue(validate_batch_gate(path)["allow_next_batch"])

    def test_rejects_isolated_batch_with_hard_blocker(self):
        report = {
            "schema_version": 1, "status": "batch_ready_for_next", "allow_next_batch": True,
            "hard_blockers": ["source_hash_changes"], "source_hashes_stable": False,
            "failures": [], "citation_support_rate": 1.0, "tasks": {"complete": 10},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_batch_gate(path)


if __name__ == "__main__":
    unittest.main()
