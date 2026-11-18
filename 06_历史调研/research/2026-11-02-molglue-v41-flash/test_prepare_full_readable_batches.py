import json
import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare_full_readable_batches import load_readable  # noqa: E402


class PrepareFullReadableBatchTests(unittest.TestCase):
    def test_selects_only_local_xml(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "papers.json"
            path.write_text(json.dumps([
                {"paper_id": "B1", "availability": "local", "source_kind": "xml", "path": "a"},
                {"paper_id": "B2", "availability": "local", "source_kind": "html", "path": "b"},
                {"paper_id": "B3", "availability": "input_gap", "source_kind": "xml", "path": "c"},
            ]), encoding="utf-8")
            self.assertEqual([p["paper_id"] for p in load_readable(path)], ["B1"])


if __name__ == "__main__":
    unittest.main()
