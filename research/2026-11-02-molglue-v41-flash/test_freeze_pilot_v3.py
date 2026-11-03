import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import freeze_pilot_v3


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "local" / "sentence_pilot_scope_v2"
V2 = ROOT / "local" / "pilot_adjudicated_v2_final_20261103"


class FreezePilotV3Tests(unittest.TestCase):
    def build(self, tmp):
        return freeze_pilot_v3.build(type("Args", (), {"workspace": WORKSPACE, "v2": V2, "out": Path(tmp)})())

    def test_blind_packet_hides_current_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            packet = json.loads((Path(tmp) / "blind_review_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(len(packet), 4)
            self.assertTrue(all("decision" not in row and "model_eligible" not in row for row in packet))

    def test_v3_freeze_counts_and_review_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            quality = self.build(tmp)
            self.assertEqual(quality["status"], "frozen_candidate")
            self.assertEqual(quality["independent_reviews"], 4)
            self.assertEqual(quality["independent_review_supported"], 4)
            self.assertEqual(quality["pending_records"], 0)
            self.assertEqual(quality["external_generation_requests"], 0)

    def test_exclusion_sample_is_model_ineligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            rows = json.loads((Path(tmp) / "excluded_sample_review.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row["model_eligible"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()
