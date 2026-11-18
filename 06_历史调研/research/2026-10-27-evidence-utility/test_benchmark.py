import csv
import json
from pathlib import Path
import tempfile
import unittest

from benchmark import FEATURES, import_predictions, prepare_benchmark, regression_metrics, score_benchmark
from common import HERE, read, write


def save_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture(root):
    for s, ids in [('train', [101, 102]), ('val', [201]), ('test', [301, 302])]:
        rows = []
        for i in ids:
            row = {k: 'synthetic-' + k + '-' + str(i) for k in FEATURES}
            row.update(id=str(i), Score=0.2 if i % 2 else 0.8, activity='SECRET_LABEL')
            rows.append(row)
        save_csv(root / 'data' / (s + '.csv'), rows)
    save_csv(root / 'flags.csv', [
        {'benchmark_uid': 'test:1:301', 'id': '301', 'Score': '0.2', 'included_in_reproduced_fine_test': 'True'},
        {'benchmark_uid': 'test:2:302', 'id': '302', 'Score': '0.8', 'included_in_reproduced_fine_test': 'False'}])
    save_csv(root / 'associations.csv', [
        {'benchmark_split': 'test', 'benchmark_id': '301', 'source_doi': '10.0000/synthetic301'},
        {'benchmark_split': 'test', 'benchmark_id': '302', 'source_doi': '10.0000/synthetic302'}])
    prepare_benchmark(root / 'data', root / 'flags.csv', root / 'associations.csv',
                      HERE / 'api.example.json', root / 'benchmark', official=False)
    return root / 'benchmark'


class BenchmarkTests(unittest.TestCase):
    def test_labels_not_in_request_and_fine_test_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bench = fixture(root)
            tasks = read(bench / 'tasks.json')
            self.assertNotIn('SECRET_LABEL', json.dumps(tasks))
            self.assertTrue(all('"Score"' not in t['messages'][1]['content'] for t in tasks))
            summary = read(bench / 'benchmark_summary.json')
            self.assertEqual((summary['test'], summary['fine_test']), (2, 1))
            self.assertEqual(summary['generation_requests'], 0)

    def test_score_all_denominators_and_fine_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bench = fixture(root)
            ps = [{'question_id': 'test:1:301', 'arm': 'recovered', 'status': 'complete', 'result': {'score': .3}},
                  {'question_id': 'test:2:302', 'arm': 'recovered', 'status': 'pending', 'result': None},
                  {'question_id': 'test:1:301', 'arm': 'structured', 'status': 'complete', 'result': {'score': .4}}]
            write(root / 'pred.json', ps)
            result = score_benchmark(bench, root / 'pred.json', root / 'score')
            full = result['arms']['recovered']['full_test']
            self.assertEqual((full['expected'], full['complete'], full['missing_or_invalid']), (2, 1, 1))
            self.assertAlmostEqual(full['mae_complete'], .1)
            self.assertAlmostEqual(full['mae_all_expected_missing_penalty_1'], .55)
            self.assertAlmostEqual(result['paired_changes_negative_is_better']['recovered_minus_structured']['delta_mae'], -.1)
            ps.append(ps[0])
            write(root / 'bad.json', ps)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                score_benchmark(bench, root / 'bad.json', root / 'badscore')

    def test_external_predictions_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bench = fixture(root)
            save_csv(root / 'pred.csv', [{'id': '301', 'prediction': '.25'}])
            result = import_predictions(bench, root / 'pred.csv', 'MG2Act', root / 'import')
            self.assertEqual((result['predictions'], result['expected']), (1, 2))
            save_csv(root / 'nan.csv', [{'id': '301', 'prediction': 'nan'}])
            with self.assertRaisesRegex(ValueError, 'Non-finite'):
                import_predictions(bench, root / 'nan.csv', 'MG2Act', root / 'badimport')

    def test_official_counts_and_flag_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            with self.assertRaisesRegex(ValueError, 'input hash'):
                prepare_benchmark(root / 'data', root / 'flags.csv', root / 'associations.csv',
                                  HERE / 'api.example.json', root / 'official')
            flags = read(root / 'benchmark/labels.json')
            self.assertEqual(flags[0]['question_id'], 'test:1:301')
            save_csv(root / 'badflags.csv', [
                {'benchmark_uid': 'test:1:301', 'id': '301', 'Score': '.9', 'included_in_reproduced_fine_test': 'True'},
                {'benchmark_uid': 'test:2:302', 'id': '302', 'Score': '.8', 'included_in_reproduced_fine_test': 'False'}])
            with self.assertRaisesRegex(ValueError, 'label mismatch'):
                prepare_benchmark(root / 'data', root / 'badflags.csv', root / 'associations.csv',
                                  HERE / 'api.example.json', root / 'bad', official=False)

    def test_r2_and_macro_target(self):
        result = regression_metrics([{'prediction': .2, 'Score': .2, 'target': 'A'},
                                     {'prediction': .8, 'Score': .8, 'target': 'B'}])
        self.assertEqual(result['r2_complete'], 1.)
        self.assertEqual(result['macro_target_mae_complete'], 0.)


if __name__ == '__main__':
    unittest.main()
