"""Connection repair never retries unknown requests or changes system proxies."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from corpus import read, save
from candidate_runtime import RunLock
import sentence_network as network


class NetworkRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='janus network ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_path = self.root / 'launch.json'
        self.config = {'base_url': 'https://api.example.test/v1', 'model': 'm',
                       'timeout_seconds': 120, 'api_key_env': 'TEST_KEY'}
        self.settings = {'pilot_workspace': str(self.root / 'pilot'),
                         'config': str(self.root / 'config.json'), 'env_file': str(self.root / '.env')}
        save(self.settings['config'], self.config)
        self.ledger = self.root / 'ledger.json'
        self.attempts = [{'attempt_id': 'unknown-kept', 'status': 'needs_attention'}]
        save(self.ledger, {'attempts': self.attempts, 'max_requests': 800,
                          'global_stop': 'two_consecutive_network_failures'})
        self.state = Path(self.settings['pilot_workspace']) / 'candidate_state.json'
        save(self.state, {'config': self.config, 'network_route': 'environment',
                          'budget_path': str(self.ledger), 'tasks': {'old': {'status': 'needs_attention'}}})
        self.state_before = self.state.read_bytes()
        self.direct = dict(self.config, route='direct', generation_requests=0,
                           configured_model_listed=True, status='reachable', elapsed_seconds=.5)
        self.probes = [dict(self.direct, route='environment', status='failed'), self.direct]

    def diagnose(self, probes=None):
        with patch('sentence_workspace.verify'), \
                patch('credentials.load_key', return_value='synthetic-key'), \
                patch.object(network, '_probe', side_effect=probes or self.probes):
            return network.repair(self.settings_path, self.settings, self.ledger)

    def test_repair_preserves_unknown_attempts_state_config_and_parent_env(self):
        original_env = dict(os.environ)
        result = self.diagnose()
        ledger = read(self.ledger)
        self.assertEqual(ledger['attempts'], self.attempts)
        self.assertEqual(ledger['max_requests'], 800)
        self.assertNotIn('global_stop', ledger)
        self.assertEqual(self.state.read_bytes(), self.state_before)
        self.assertEqual(read(self.settings['config']), self.config)
        self.assertEqual(dict(os.environ), original_env)
        self.assertEqual(result['generation_requests'], 0)
        self.assertEqual(result['unknown_requests_retried'], 0)
        self.assertTrue((Path(result['diagnosis_dir']) / 'recovery.json').is_file())

    def test_proxy_bypass_is_only_added_to_child_environment(self):
        self.diagnose()
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://127.0.0.1:7890',
                                    'NO_PROXY': 'localhost', 'no_proxy': 'old.test'}):
            before = dict(os.environ)
            env = network.child_environment(self.settings_path, self.config)
            self.assertEqual(os.environ, before)
            self.assertEqual(env['HTTPS_PROXY'], before['HTTPS_PROXY'])
            # Windows environment names are case-insensitive; POSIX can retain both.
            expected = {x for k in ('NO_PROXY', 'no_proxy') for x in before.get(k, '').split(',') if x}
            self.assertEqual(set(env['NO_PROXY'].split(',')), expected | {'api.example.test'})
            self.assertEqual(env['NO_PROXY'], env['no_proxy'])

    def test_direct_diagnosis_failure_preserves_stop_and_does_not_install_route(self):
        probes = [self.probes[0], dict(self.direct, status='failed')]
        with self.assertRaisesRegex(ValueError, 'Direct API diagnosis failed'):
            self.diagnose(probes)
        self.assertEqual(read(self.ledger)['global_stop'], 'two_consecutive_network_failures')
        self.assertFalse(network.route_file(self.settings_path).exists())

    def test_model_missing_preserves_stop(self):
        probes = [self.probes[0], dict(self.direct, configured_model_listed=False)]
        with self.assertRaises(ValueError):
            self.diagnose(probes)
        self.assertEqual(read(self.ledger)['attempts'], self.attempts)

    def test_changed_api_requires_new_diagnosis(self):
        self.diagnose()
        with self.assertRaisesRegex(ValueError, 'does not match'):
            network.child_environment(self.settings_path, dict(self.config, model='other'))

    def test_unrelated_stop_is_not_cleared(self):
        ledger = read(self.ledger)
        ledger['global_stop'] = 'authentication_failed'
        save(self.ledger, ledger)
        with self.assertRaisesRegex(ValueError, 'cannot clear'):
            self.diagnose()
        self.assertEqual(read(self.ledger)['global_stop'], 'authentication_failed')

    def test_active_run_blocks_repair_before_key_loading_or_network(self):
        with RunLock(str(self.ledger) + '.candidate_run.lock'), \
                patch('credentials.load_key') as key:
            with self.assertRaisesRegex(RuntimeError, 'holds the lock'):
                network.repair(self.settings_path, self.settings, self.ledger)
        key.assert_not_called()

    def test_without_saved_route_environment_stays_default(self):
        self.assertIsNone(network.child_environment(self.settings_path, self.config))


if __name__ == '__main__':
    unittest.main()
