from pathlib import Path
import tempfile
import unittest
from batch_budget import create, reserve, finish
from budget_control import control
from corpus import read


class ControlTests(unittest.TestCase):
    def test_pause_resume_does_not_reset_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'; create(path, 20, 10000, 'Fixture')
            a = reserve(path, folder, 'task', {'model': 'fixture'}, 100)
            control(path, 'pause', 'Quality check after current request')
            finish(path, a['attempt_id'], 'complete')
            control(path, 'resume', 'Quality check finished')
            d = read(path)
            self.assertEqual(len(d['attempts']), 1)
            self.assertEqual(d['max_requests'], 20)
            self.assertEqual(len(d['operator_events']), 2)

    def test_cannot_resume_real_provider_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'budget.json'; create(path, 20, 10000, 'Fixture')
            a = reserve(path, folder, 'task', {'model': 'fixture'}, 100)
            finish(path, a['attempt_id'], 'http_failure', http_status=401, global_stop='authentication')
            with self.assertRaises(ValueError): control(path, 'resume', 'Not a provider diagnosis')
