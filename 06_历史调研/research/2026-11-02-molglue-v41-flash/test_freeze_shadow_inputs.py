import json
import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from freeze_shadow_inputs import freeze  # noqa: E402


class FreezeShadowInputsTests(unittest.TestCase):
    def test_filters_by_workspace_and_preserves_repair_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ws = root / "original"
            repair = root / "repair"
            ws.mkdir()
            repair.mkdir()
            (ws / "manifest.json").write_text("{}", encoding="utf-8")
            ledger = root / "ledger.json"
            ledger.write_text(json.dumps({"attempts": [
                {"workspace": str(ws), "status": "complete", "attempt_id": "a"},
                {"workspace": str(repair), "status": "complete", "attempt_id": "b"},
            ]}), encoding="utf-8")
            report = freeze(ledger, ws, root / "frozen.json", root / "report.json")
            frozen = json.loads((root / "frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(report["frozen_attempts"], 1)
            self.assertEqual(report["excluded_repair_attempts"], 1)
            self.assertEqual([a["attempt_id"] for a in frozen["attempts"]], ["a"])

    def test_inflight_original_is_not_frozen(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ws = root / "original"
            ws.mkdir()
            (ws / "manifest.json").write_text("{}", encoding="utf-8")
            ledger = root / "ledger.json"
            ledger.write_text(json.dumps({"attempts": [
                {"workspace": str(ws), "status": "in_flight", "attempt_id": "a"},
            ]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                freeze(ledger, ws, root / "frozen.json", root / "report.json")


if __name__ == "__main__":
    unittest.main()
