import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import finalize_pilot_v2


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "local" / "sentence_pilot_scope_v2"
V1 = ROOT / "local" / "pilot_adjudicated_v1_final_20261103"


class FinalizePilotV2Tests(unittest.TestCase):
    def build(self, tmp):
        return finalize_pilot_v2.build(type("Args", (), {"workspace": WORKSPACE, "v1": V1, "out": Path(tmp)})())

    def test_all_source_rows_adjudicated_and_pending_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(tmp)
            self.assertEqual(report["counts"], {"reliable": 4, "pending_review": 0, "excluded": 73})
            self.assertTrue(report["all_77_adjudicated"])
            self.assertEqual(report["source_hash_changes"], 0)
            self.assertEqual(report["external_generation_requests"], 0)

    def test_drf_and_rosco_have_separate_experiment_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            rows = json.loads((Path(tmp) / "reliable_evidence.json").read_text(encoding="utf-8"))
            row = next(r for r in rows if r["record_key"].startswith("611a556fef25cdb4"))
            self.assertEqual(row["experiment_components"], ["DRF053", "roscovitine"])
            self.assertEqual(len(row["experiment_ids"]), 2)
            self.assertNotEqual(*row["experiment_ids"])

    def test_model_boundary_and_release_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.build(tmp)
            rows = json.loads((Path(tmp) / "source_adjudications.json").read_text(encoding="utf-8"))
            self.assertTrue(all(r["model_eligible"] == (r["decision"] == "reliable") for r in rows))
            self.assertEqual(report["status"], "candidate_blocked_quality_gate")
            self.assertIn("scientific_semantic_gate_requires_independent_content_check", report["blockers"])


if __name__ == "__main__":
    unittest.main()
