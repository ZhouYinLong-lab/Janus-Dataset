"""The unattended driver continues free source work without forging acceptance."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate_autorun
from corpus import read, save


class AutorunTests(unittest.TestCase):
    def test_incomplete_acceptance_does_not_start_full_paid_run(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            pilot = root/'pilot'; full = root/'full'; inv = root/'inventory'
            pilot.mkdir();full.mkdir()
            save(inv/'papers.json', [])
            save(pilot/'acceptance_reference.json', {'expert_gold': False})
            save(root/'ledger.json', {'max_requests': 200, 'attempts': [{}]*185})
            save(root/'config.json', {'model': 'fake'})
            settings = {'config': str(root/'config.json'), 'ledger': str(root/'ledger.json'),
                        'inventory': str(inv), 'pilot_workspace': str(pilot), 'workspace': str(full),
                        'env_file': str(root/'unused.env'), 'acceptance': str(root/'acceptance.json')}
            save(root/'settings.json', settings)
            save(root/'candidate_engineering_validation.json', {'passed': True})
            stack.enter_context(patch('candidate_autorun.HERE', root))
            stack.enter_context(patch('candidate_autorun.check', return_value={}))
            run = stack.enter_context(patch('candidate_autorun.run'))
            stack.enter_context(patch('candidate_autorun.snapshot', return_value=(
                {'unique_records': 0}, [], [], [])))
            stack.enter_context(patch('candidate_autorun.export', return_value={}))
            stack.enter_context(patch('candidate_autorun.assess', return_value={
                'passed': False, 'blockers': ['content_review_pending']}))
            fetch = stack.enter_context(patch('molglue_sources.fetch_sources', return_value={
                'with_local_source': 25}))
            stack.enter_context(patch('candidate_autorun.require_acceptance', side_effect=ValueError('blocked')))
            result = candidate_autorun.autorun(root/'settings.json', root/'run')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.kwargs['max_new_requests'], 15)
            self.assertEqual(run.call_args.kwargs['network_route'], 'direct')
            fetch.assert_called_once_with(inv)
            self.assertFalse(result['full_extraction_started'])
            self.assertEqual(result['status'], 'blocked')
            self.assertIsNone(read(root/'run/content_review.json')['critical_errors_unresolved'])
            self.assertEqual(len(read(root/'ledger.json')['attempts']), 185)


if __name__ == '__main__':
    unittest.main()
