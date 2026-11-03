import tempfile
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from revalidate_normalized_shadow import run  # noqa: E402


class RevalidateNormalizedShadowTests(unittest.TestCase):
    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "out"
            p.mkdir()
            with self.assertRaises(ValueError):
                run(Path(td) / "missing", p, Path(td) / "config", Path(td) / "ledger")


if __name__ == "__main__":
    unittest.main()
