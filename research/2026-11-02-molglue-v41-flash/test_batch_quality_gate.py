import json
import tempfile
import unittest
from pathlib import Path

from batch_quality_gate import _ledger_report


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



if __name__ == "__main__":
    unittest.main()
