import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import prepare_shadow_batch  # noqa: E402


SOURCE = ROOT / "local" / "sentence_full" / "manifest.json"


class PrepareShadowBatchTests(unittest.TestCase):
    def test_selection_is_repeatable_and_excludes_fixed_pilot(self):
        first = prepare_shadow_batch.select(SOURCE, 10, 20261103)
        second = prepare_shadow_batch.select(SOURCE, 10, 20261103)
        ids_first = [row["paper_id"] for row in first]
        ids_second = [row["paper_id"] for row in second]
        self.assertEqual(ids_first, ids_second)
        self.assertEqual(len(ids_first), 10)
        self.assertEqual(len(set(ids_first)), 10)
        self.assertTrue(set(ids_first).isdisjoint(prepare_shadow_batch.PILOT_IDS))
        self.assertTrue(all(Path(row["source_path"]).suffix.lower() == ".xml" for row in first))

    def test_build_writes_independent_workspace_ledger_and_zero_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shadow"
            config = ROOT / "deepseek_v41_flash_unbounded_repair.config.json"
            report = prepare_shadow_batch.build(type("Args", (), {
                "source_manifest": SOURCE,
                "out_root": out,
                "config_source": config,
                "count": 2,
                "seed": 20261103,
            })())
            self.assertEqual(report["generation_requests_sent"], 0)
            self.assertTrue((out / "workspace" / "manifest.json").is_file())
            ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["attempts"], [])
            self.assertIsNone(ledger["max_requests"])
            self.assertIsNone(ledger["max_reserved_tokens"])
            manifest = json.loads((out / "workspace" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["papers"]), 2)
            self.assertGreater(len(manifest["job_ids"]), 0)


if __name__ == "__main__":
    unittest.main()
