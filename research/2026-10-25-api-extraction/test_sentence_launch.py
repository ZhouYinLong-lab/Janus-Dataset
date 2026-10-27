"""Offline checks for desktop launches against an already running pilot."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from corpus import read, save
import sentence_launch as launch


class SentenceLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='janus launch ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = {key: str(self.root / key) for key in launch.DEFAULTS}
        self.settings_path = self.root / 'settings.json'
        save(self.settings_path, self.settings)
        self.ledger = self.root / 'round_02_budget.json'
        save(self.ledger, {'attempts': [{'status': 'complete'}]})
        self.before = self.ledger.read_bytes()

    def bind(self, workspace='pilot_workspace', ledger=None):
        path = Path(self.settings[workspace]) / 'candidate_state.json'
        save(path, {'pipeline': 'molgluedb_sentence_v3',
                    'budget_path': str(ledger or self.ledger)})
        return path

    def test_resume_prefers_actual_binding_without_rewriting_settings_or_ledger(self):
        state = self.bind()
        state_before = state.read_bytes()
        with patch.object(launch, 'command') as command, redirect_stdout(StringIO()):
            launch.action('run', self.settings_path)
        args = command.call_args.args
        self.assertEqual(args[args.index('--ledger') + 1], str(self.ledger))
        self.assertEqual(args[args.index('--phase') + 1], 'pilot')
        self.assertEqual(read(self.settings_path), self.settings)
        self.assertEqual(self.ledger.read_bytes(), self.before)
        self.assertEqual(state.read_bytes(), state_before)

    def test_first_run_keeps_configured_ledger(self):
        self.assertEqual(launch._bound_ledger(self.settings), self.settings['ledger'])

    def test_full_run_carries_pilot_binding_and_keeps_acceptance_check(self):
        self.bind()
        save(self.settings['acceptance'], {'passed': True})
        save(self.settings['config'], {})
        with patch.object(launch, 'command') as command, \
                patch('sentence_acceptance.require_acceptance') as require, \
                redirect_stdout(StringIO()):
            launch.action('run', self.settings_path)
        require.assert_called_once()
        args = command.call_args.args
        self.assertEqual(args[args.index('--phase') + 1], 'full')
        self.assertEqual(args[args.index('--ledger') + 1], str(self.ledger))
        self.assertIn('--acceptance', args)

    def test_conflicting_bindings_stop_before_subprocess(self):
        self.bind()
        other = self.root / 'another.json'
        save(other, {'attempts': []})
        self.bind('workspace', other)
        with patch.object(launch, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'different ledgers'):
                launch.action('run', self.settings_path)
        command.assert_not_called()

    def test_missing_bound_ledger_does_not_fall_back_to_old_budget(self):
        self.bind(ledger=self.root / 'missing.json')
        with patch.object(launch, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'ledger is missing'):
                launch.action('run', self.settings_path)
        command.assert_not_called()

    def test_malformed_state_is_not_ignored(self):
        path = self.bind()
        save(path, {'pipeline': 'other', 'budget_path': str(self.ledger)})
        with self.assertRaisesRegex(ValueError, 'Invalid sentence'):
            launch._bound_ledger(self.settings)

    def test_status_uses_fresh_snapshot_without_subprocess_or_old_autorun(self):
        self.bind()
        save(Path(self.settings['pilot_workspace']) / 'exports/summary.json',
             {'paper_buckets': {'成功': ['STALE']}})
        summary = {'paper_buckets': {'成功': [], '失败': ['CURRENT'],
                    '缺少全文': [], '未完成': []},
                   'papers': [{'jobs_processed': 2, 'jobs': 3}], 'records': 7,
                   'stop_reason': 'two_consecutive_network_failures',
                   'shared_budget': {'requests_reserved': 161, 'max_requests': 800,
                                     'attempts_without_usage': 3}}
        output = StringIO()
        with patch.object(launch, 'command') as command, \
                patch('sentence_export.snapshot', return_value=(summary, [], [], [])) as snapshot, \
                redirect_stdout(output):
            launch.action('status', self.settings_path)
        command.assert_not_called()
        snapshot.assert_called_once_with(self.settings['pilot_workspace'])
        self.assertIn('CURRENT', output.getvalue())
        self.assertNotIn('STALE', output.getvalue())
        self.assertIn('161/800', output.getvalue())
        self.assertIn('2/3', output.getvalue())


if __name__ == '__main__':
    unittest.main()
