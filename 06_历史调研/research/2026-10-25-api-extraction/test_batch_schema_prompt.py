import tempfile
from pathlib import Path
import unittest

from batch_plan import prepare
from corpus import save


class PromptContractTests(unittest.TestCase):
    def test_quote_and_type_limits_are_visible_to_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'paper.xml'
            source.write_text('<article><body><p>HF did not reduce protein abundance.</p>'
                              '</body></article>', encoding='utf-8')
            manifest = root / 'input.json'
            save(manifest, [{'paper_id': 'P1', 'path': str(source)}])
            out = root / 'workspace'
            prepare(out, custom=manifest)
            schema = (out / 'record_schema.txt').read_text(encoding='utf-8')
            self.assertIn('at least 8 characters', schema)
            self.assertIn('at most 3000 characters', schema)
            self.assertIn('containing clause or sentence', schema)
            self.assertIn('no_activity is NOT an allowed negative_type', schema)


if __name__ == '__main__':
    unittest.main()
