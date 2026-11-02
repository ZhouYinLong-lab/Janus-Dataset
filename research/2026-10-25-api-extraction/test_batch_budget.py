from pathlib import Path
import tempfile
import unittest

from batch_budget import create, finish, reserve, status


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.path = self.root / 'budget.json'
        create(self.path, 3, 1000, 'Synthetic test; no real API authorization')
        self.req = {'model': 'fixture', 'messages': [{'role': 'user', 'content': 'fixture'}]}

    def reserve(self, req=None, retry=False):
        return reserve(self.path, self.root, 'task', req or self.req, 100, retry)

    def test_budget_cannot_reset(self):
        with self.assertRaises(ValueError): create(self.path, 999, 999999, 'replace')

    def test_duplicate_after_crash_blocked_across_workspaces(self):
        self.reserve()
        with self.assertRaises(ValueError): reserve(self.path, self.root / 'other', 'other', self.req, 100)
        self.assertEqual(status(self.path)['requests_reserved'], 1)

    def test_unknown_does_not_block_different_task(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'needs_attention', failure_kind='network_outcome_unknown')
        self.reserve({'model': 'fixture', 'messages': ['different']})
        with self.assertRaises(ValueError): self.reserve(retry=True)

    def test_cumulative_request_cap(self):
        for i in range(3): self.reserve({'model': 'fixture', 'number': i})
        with self.assertRaises(ValueError): self.reserve({'model': 'fixture', 'number': 4})

    def test_token_cap(self):
        with self.assertRaises(ValueError): reserve(self.path, self.root, 'x', self.req, 1001)
        self.assertEqual(status(self.path)['requests_reserved'], 0)

    def test_explicit_known_failure_retry_once(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'http_failure', http_status=500)
        a = self.reserve(retry=True); finish(self.path, a['attempt_id'], 'http_failure', http_status=500)
        with self.assertRaises(ValueError): self.reserve(retry=True)
        self.assertEqual(status(self.path)['requests_reserved'], 2)

    def test_completed_request_never_resent(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'complete', usage={'total_tokens': 8})
        with self.assertRaises(ValueError): self.reserve(retry=True)
        self.assertEqual(status(self.path)['reported_total_tokens'], 8)

    def test_double_network_failure_global_stop(self):
        for i in range(2):
            a = self.reserve({'model': 'fixture', 'number': i})
            finish(self.path, a['attempt_id'], 'needs_attention', failure_kind='network_outcome_unknown')
        with self.assertRaises(ValueError): self.reserve({'model': 'fixture', 'number': 2})
        self.assertEqual(status(self.path)['global_stop'], 'two_consecutive_network_failures')

    def test_global_auth_stop(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'http_failure', http_status=401, global_stop='authentication')
        with self.assertRaises(ValueError): self.reserve({'model': 'fixture', 'number': 2})

    def test_final_history_immutable(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'needs_attention')
        with self.assertRaises(ValueError): finish(self.path, a['attempt_id'], 'complete')

    def test_missing_usage_not_claimed_zero(self):
        a = self.reserve(); finish(self.path, a['attempt_id'], 'needs_attention')
        self.assertEqual(status(self.path)['attempts_without_usage'], 1)

    def test_provider_identity_distinguishes_different_endpoints(self):
        reserve(self.path, self.root, 'one', self.req, 100, provider_identity='https://one.invalid/v1')
        reserve(self.path, self.root, 'two', self.req, 100, provider_identity='https://two.invalid/v1')
        self.assertEqual(status(self.path)['requests_reserved'], 2)
        with self.assertRaises(ValueError):
            reserve(self.path, self.root, 'same', self.req, 100, provider_identity='https://ONE.invalid/v1/')

    def test_unbounded_continuation_ledger_allows_reservations(self):
        path = self.root / 'unbounded.json'
        create(path, None, None, 'Explicit continuation authorization')
        for index in range(3):
            attempt = reserve(path, self.root, f'task-{index}',
                              {'model': 'fixture', 'number': index}, 100)
            finish(path, attempt['attempt_id'], 'complete', usage={'total_tokens': 1})
        self.assertIsNone(status(path)['max_requests'])
        self.assertEqual(status(path)['requests_reserved'], 3)
