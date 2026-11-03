import json
import tempfile
import unittest
from pathlib import Path

from batch_quality_gate import _ledger_report, _record_partition


class BatchQualityGateTests(unittest.TestCase):
    def test_duplicate_request_hashes_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps({"attempts": [
                {"status": "complete", "request_sha256": "a", "reserved_tokens": 2,
                 "usage": {"total_tokens": 1}},
                {"status": "complete", "request_sha256": "a", "reserved_tokens": 3,
                 "usage": {"total_tokens": 2}},
            ]}), encoding="utf-8")
            result = _ledger_report(path)
            self.assertEqual(result["duplicate_request_hashes"], 1)
            self.assertEqual(result["reported_tokens"], 3)

    def test_isolated_pending_does_not_become_reliable(self):
        records = [
            {"record_key": "a", "record_status": "core_usable", "ready_for_training": False},
            {"record_key": "b", "record_status": "semantic_pending", "ready_for_training": False},
            {"record_key": "c", "record_status": "quarantine", "ready_for_training": False},
        ]
        routed = [
            {"record_key": "a", "route": "candidate_review"},
            {"record_key": "b", "route": "candidate_review"},
            {"record_key": "c", "route": "mechanism_or_control"},
        ]
        support = [{"record_key": key, "direct_support": True} for key in ("a", "b")]
        result = _record_partition(records, routed, support, [{"terminal_status": "pending_context"}])
        self.assertEqual(result["reliable_records"], 1)
        self.assertEqual(result["excluded_records"], 1)
        self.assertEqual(result["isolated_pending"], 2)
        self.assertEqual(result["model_eligible_records"], 0)



if __name__ == "__main__":
    unittest.main()
