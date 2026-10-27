import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import codex_export


class CodexExportTests(unittest.TestCase):
    def test_deduplicates_records_and_keeps_missing_papers_in_coverage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            (run / "workers" / "P1" / "records").mkdir(parents=True)
            (run / "review").mkdir()
            row = {"record_id": "R1", "paper_id": "P1", "doi": "10.1/p1",
                   "source_sha256": "source", "status": "pending_review",
                   "evidence_spans": [{"quote": "same"}],
                   "facts": {"observations": [{"values": {"subject": "A", "target": "T",
                                                                  "endpoint": "degradation", "observation": "none"}}]}}
            (run / "workers" / "P1" / "records" / "r1.json").write_text(json.dumps(row), encoding="utf-8")
            duplicate = dict(row, record_id="R2")
            (run / "workers" / "P1" / "records" / "r2.json").write_text(json.dumps(duplicate), encoding="utf-8")
            (run / "workers" / "P1" / "worker_summary.json").write_text(json.dumps({
                "paper_id": "P1", "source_sha256": "source", "task_count": 1,
                "completed_tasks": 1, "failed_tasks": 0, "unfinished_tasks": 0,
                "candidate_count": 2, "reliable_count": 0, "pending_review_count": 2,
                "api_requests": 0}), encoding="utf-8")
            inventory = root / "papers.json"
            inventory.write_text(json.dumps([{"paper_id": "P1", "doi": "10.1/p1", "path": "x"},
                                             {"paper_id": "P2", "doi": "10.1/p2", "path": None}]), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"papers": [{"paper_id": "P1", "source_kind": "xml"}]}), encoding="utf-8")
            report = codex_export.export(run, inventory, manifest)
            self.assertEqual(report["records_raw"], 2)
            self.assertEqual(report["records_deduplicated"], 1)
            self.assertEqual(report["paper_status_counts"]["fulltext_missing"], 1)
            self.assertTrue((run / "exports" / "reliable_evidence.json").is_file())

    def test_reads_partitioned_worker_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / "run"
            worker = run / "workers" / "P1"; worker.mkdir(parents=True)
            (run / "review").mkdir()
            row = {"record_id": "R1", "paper_id": "P1", "source_sha256": "s",
                   "status": "pending_review", "evidence_spans": [{"quote": "q"}],
                   "facts": {"observations": [{"values": {"subject": "A", "target": "T",
                                                                  "endpoint": "e", "observation": "o"}}]}}
            (worker / "pending_review.json").write_text(json.dumps([row]), encoding="utf-8")
            (worker / "worker_summary.json").write_text(json.dumps({"paper_id": "P1", "source_sha256": "s",
                "task_count": 1, "completed_tasks": 1, "failed_tasks": 0, "unfinished_tasks": 0,
                "candidate_count": 1, "pending_review_count": 1, "api_requests": 0}), encoding="utf-8")
            inv = root / "papers.json"; inv.write_text(json.dumps([{"paper_id": "P1", "path": "x"}]), encoding="utf-8")
            man = root / "manifest.json"; man.write_text(json.dumps({"papers": [{"paper_id": "P1", "source_kind": "xml"}]}), encoding="utf-8")
            report = codex_export.export(run, inv, man)
            self.assertEqual(report["records_raw"], 1)
            self.assertEqual(report["pending_review_count"], 1)


if __name__ == "__main__":
    unittest.main()
