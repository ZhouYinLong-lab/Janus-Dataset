import tempfile
from pathlib import Path
import unittest

from corpus import save
from rag_grade import aggregate


class GradeTests(unittest.TestCase):
    def fixture(self, root):
        save(root / 'answers.json', [{'blind_id': 'a', 'arm': 'raw'},
                                     {'blind_id': 'b', 'arm': 'cards'}])
        save(root / 'blind_answers.json', [
            {'blind_id': bid, 'question_id': 'Q1', 'split': 'evaluation', 'rubric': ['x', 'y']}
            for bid in ['a', 'b']])
        path = root / 'grades.json'
        save(path, {'items': [{'blind_id': bid, 'rubric_met': [True, False],
                              'overclaim': False, 'reason': 'source supports one point'}
                             for bid in ['a', 'b']]})
        return path

    def test_paired_and_no_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = self.fixture(root)
            result = aggregate(root, [path])
            self.assertEqual(result['paired_question_count'], 1)
            self.assertEqual(result['generation_requests'], 0)
            self.assertEqual(result['groups'][0]['rubric_points'], 1)

    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = self.fixture(root)
            with self.assertRaises(ValueError):
                aggregate(root, [path, path])

    def test_unpaired_not_imputed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = self.fixture(root)
            save(path, {'items': [{'blind_id': 'a', 'rubric_met': [True, True],
                                   'overclaim': False, 'reason': 'supported'}]})
            result = aggregate(root, [path])
            self.assertEqual(result['paired_question_count'], 0)
            self.assertEqual(result['unjudged_or_missing_answers'], 1)
            self.assertTrue(all(g['possible_points'] == 0 for g in result['groups']))


if __name__ == '__main__':
    unittest.main()
