import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import repair_shadow_batch  # noqa: E402


class RepairShadowBatchTests(unittest.TestCase):
    def test_problem_jobs_are_detected_without_mutating_source(self):
        source = ROOT / "local" / "shadow_batch_20261103" / "workspace"
        before = (source / "manifest.json").read_bytes()
        jobs, audit = repair_shadow_batch._problem_jobs(source)
        self.assertTrue(jobs)
        self.assertGreater(audit["structural_audit_rows"], 0)
        self.assertEqual(before, (source / "manifest.json").read_bytes())

    def test_repair_clone_has_new_prompt_hash_and_empty_runtime_state(self):
        source = ROOT / "local" / "shadow_batch_20261103" / "workspace"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "repair"
            report = repair_shadow_batch.build(source, out)
            self.assertTrue(report["cross_workspace_reuse"])
            self.assertFalse((out / "candidate_state.json").exists())
            self.assertFalse((out / "responses").exists())
            self.assertTrue((out / "manifest.json").is_file())
            self.assertIn("REPAIR CONTRACT RULES", (out / "facts_v3.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
