import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import shadow_acceptance  # noqa: E402


class ShadowAcceptanceTests(unittest.TestCase):
    def test_docking_only_text_is_flagged(self):
        row = {"values": {"subject": "UOM", "target": "DDB1 pocket",
                           "endpoint": "occupancy of binding site",
                           "observation": "does not occupy the pocket"}}
        self.assertEqual(shadow_acceptance._scope_flags(row), ["binding"])

    def test_degradation_text_is_not_scope_flagged(self):
        row = {"values": {"subject": "compound A", "target": "CDK12",
                           "endpoint": "protein degradation",
                           "observation": "did not induce degradation"}}
        self.assertEqual(shadow_acceptance._scope_flags(row), [])

    def test_real_shadow_batch_is_blocked_before_review(self):
        workspace = ROOT / "local" / "shadow_batch_20261103" / "workspace"
        ledger = ROOT / "local" / "shadow_batch_20261103" / "ledger.json"
        with tempfile.TemporaryDirectory() as tmp:
            report = shadow_acceptance.build(workspace, ledger, Path(tmp) / "shadow_acceptance_report.json")
            self.assertEqual(report["status"], "shadow_blocked")
            self.assertFalse(report["allow_full_extraction"])
            self.assertIn("independent_citation_review_pending", report["blockers"])


if __name__ == "__main__":
    unittest.main()
