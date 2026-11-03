import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adjudicate_pilot


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "local" / "sentence_pilot_scope_v2"


class AdjudicatePilotTests(unittest.TestCase):
    def test_partition_closes_and_keeps_model_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = adjudicate_pilot.build(
                type("Args", (), {"workspace": WORKSPACE, "out": Path(tmp)})()
            )
            counts = report["counts"]
            self.assertEqual(sum(counts.values()), 77)
            self.assertEqual(report["source_failures"], [])
            eligible = [
                row for row in json.loads((Path(tmp) / "reliable.json").read_text(encoding="utf-8"))
                if row["model_eligible"]
            ]
            self.assertEqual(len(eligible), 2)
            self.assertTrue(all(row["scope_class"] == "molecular_glue_degradation_negative" for row in eligible))
            self.assertTrue(all(row["evidence_origin"] == "primary_report" for row in eligible))

    def test_b296_caption_condition_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            adjudicate_pilot.build(
                type("Args", (), {"workspace": WORKSPACE, "out": Path(tmp)})()
            )
            rows = json.loads((Path(tmp) / "reliable.json").read_text(encoding="utf-8"))
            flav = next(row for row in rows if row["record_key"].startswith("519c41fdb66ac1"))
            self.assertIn("HEK293T Cas9", flav["condition"])
            self.assertIn("1 μM", flav["condition"])
            self.assertIn("2 h", flav["condition"])
            self.assertIn("n=3", flav["condition"])

    def test_source_adjudication_is_append_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            adjudicate_pilot.build(
                type("Args", (), {"workspace": WORKSPACE, "out": Path(tmp)})()
            )
            rows = json.loads((Path(tmp) / "source_adjudications.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 77)
            self.assertTrue(all(row["before_record_sha256"] for row in rows))
            self.assertTrue(all(row["source_hash_status"] == "source_hash_match" for row in rows))
            self.assertFalse(any(row["decision"] == "reliable" and row["evidence_origin"] == "secondary_report" for row in rows))


if __name__ == "__main__":
    unittest.main()
