from pathlib import Path
import tempfile
import unittest

from common import HERE, read, verify, write
from test_contracts import fixture
from workflow import check, prepare_all


class WorkflowTests(unittest.TestCase):
    def test_missing_data_is_reported_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            cfg = read(HERE / 'workflow.example.json')
            cfg['mg2act'] = None
            write(path, cfg)
            result = prepare_all(path)
            self.assertFalse(result['preparation_ready'])
            self.assertEqual(result['generation_requests'], 0)
            self.assertFalse((Path(tmp) / 'local/utility_run_01').exists())

    def test_offline_prepare_end_to_end_without_training_or_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, ws, sup = fixture(root)
            qs = [{'question_id': 'synthetic_q', 'question': 'Does synthetic X0 reduce synthetic Y0?',
                   'protocol': 'evidence_lookup', 'split': 'test', 'source_dois': ['10.0000/synthetic0'],
                   'rubric': [{'id': 'scope', 'text': 'Preserve tested condition'}],
                   'evaluation_group': 'synthetic0', 'gold_status': 'assistant_reviewed'}]
            write(root / 'questions.json', qs)
            write(root / 'split_plan.json', {'10.0000/synthetic0': 'test'})
            cfg = {'release': str(release), 'workspaces': [str(ws)], 'supplements': str(sup),
                   'split_plan': str(root / 'split_plan.json'), 'questions': str(root / 'questions.json'),
                   'api_config': str(HERE / 'api.example.json'), 'train_config': str(HERE / 'train.example.json'),
                   'out': str(root / 'utility'), 'mg2act': None}
            write(root / 'settings.json', cfg)
            self.assertTrue(check(root / 'settings.json')['preparation_ready'])
            result = prepare_all(root / 'settings.json')
            self.assertEqual(result['status'], 'prepared')
            self.assertEqual(result['generation_requests'], 0)
            self.assertFalse(result['training_executed'])
            self.assertTrue(result['stages']['training']['ready'])
            for artifact in ('bundle', 'rag', 'training'):
                verify(root / 'utility' / artifact)
            with self.assertRaises(FileExistsError):
                prepare_all(root / 'settings.json')


if __name__ == '__main__':
    unittest.main()
