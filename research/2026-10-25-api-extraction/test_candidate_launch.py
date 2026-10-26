"""Launcher actions issue argument arrays and never hide acceptance checks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import candidate_launch
from corpus import read, save, sha


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='janus launch ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = {k: str(self.root/k) for k in candidate_launch.DEFAULTS}
        self.path = self.root/'settings.json'
        save(self.path, self.settings)
        self.inventory = Path(self.settings['inventory'])
        save(self.inventory/'papers.json', [{'paper_id': 'P'}])
        save(self.inventory/'source_inventory.json', {'source_count': 1})

    def test_status_while_fetching_reads_inventory_without_commands(self):
        with patch('candidate_launch.command') as command, patch('builtins.print'):
            candidate_launch.action('status', self.path)
        command.assert_not_called()

    def test_run_passes_full_acceptance_and_explicit_live(self):
        save(self.settings['acceptance'], {'passed': True})
        save(self.settings['config'], {})
        with patch('candidate_launch.command') as command, patch('candidate_acceptance.require_acceptance'):
            candidate_launch.action('run', self.path)
        args = command.call_args.args
        self.assertIn('--live', args)
        self.assertIn('--acceptance', args)
        self.assertEqual(args[args.index('--phase')+1], 'full')
        self.assertIn('--resume-operator-pause', args)

    def test_missing_acceptance_stops_before_any_child_process(self):
        with patch('candidate_launch.command') as command:
            with self.assertRaises(ValueError):
                candidate_launch.action('run', self.path)
        command.assert_not_called()

    def test_changed_inventory_creates_new_workspace_without_overwriting_old(self):
        old = Path(self.settings['workspace'])
        save(old/'manifest.json', {'input_manifest_sha256': 'previous'})
        calls = []
        def command(*args):
            calls.append(args)
            if args[0] == 'prepare':
                target = Path(args[args.index('--workspace')+1])
                save(target/'manifest.json', {'input_manifest_sha256': sha(self.inventory/'papers.json')})
        with patch('candidate_launch.command', side_effect=command), patch('builtins.print'):
            candidate_launch.action('prepare', self.path)
        new = Path(read(self.path)['workspace'])
        self.assertNotEqual(old, new)
        self.assertEqual(read(old/'manifest.json')['input_manifest_sha256'], 'previous')
        self.assertEqual([call[0] for call in calls], ['fetch', 'prepare', 'check'])
        self.assertFalse(any('--live' in call for call in calls))

    def test_subprocess_uses_argument_array_and_python(self):
        with patch('candidate_launch.subprocess.run') as run:
            candidate_launch.command('check', '--workspace', self.root/'with spaces')
        args = run.call_args.args[0]
        self.assertIsInstance(args, list)
        self.assertEqual(args[-1], str(self.root/'with spaces'))
        self.assertTrue(run.call_args.kwargs['check'])


if __name__ == '__main__':
    unittest.main()
