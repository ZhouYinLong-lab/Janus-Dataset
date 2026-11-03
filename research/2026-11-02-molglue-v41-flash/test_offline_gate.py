import json
import tempfile
import unittest
from pathlib import Path

from offline_gate import validate_gate


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


if __name__ == "__main__":
    unittest.main()
