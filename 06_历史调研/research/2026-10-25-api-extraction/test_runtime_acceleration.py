"""Cross-version raw-response revalidation and bounded integrity work."""
from copy import deepcopy
from unittest.mock import patch

from api import RequestFailure
from corpus import read, save, sha
import candidate_runtime as runtime
import sentence_workflow as workflow
import test_sentence_runtime_v3 as fixtures
from test_sentence_runtime_v3 import ContractClient


class AccelerationTests(fixtures.SentenceRuntimeTests):
    def upgraded(self, sibling, validator=None, client=None):
        original = runtime._logical
        with patch.object(runtime, '_logical', side_effect=lambda *a, **kw: 'new-' + original(*a, **kw)):
            return self.execute(workspace=sibling, client=client or ContractClient(),
                                validator=validator or workflow.validate_response, live=False)

    def test_upgrade_revalidates_all_stages_without_new_paid_requests(self):
        old = self.execute(client=ContractClient(), validator=workflow.validate_response)
        paid = self.ledger.read_bytes()
        before = (self.workspace / 'candidate_state.json').read_bytes()
        sibling = self.root / 'upgraded'
        self.prepare(sibling)
        calls = []
        def revised(payload, job, candidates):
            calls.append(job['active_stage'])
            result = workflow.validate_response(payload, job, candidates)
            result['revalidated_by_new_runtime'] = True
            return result
        client = ContractClient()
        result = self.upgraded(sibling, validator=revised, client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.ledger.read_bytes(), paid)
        self.assertEqual((self.workspace / 'candidate_state.json').read_bytes(), before)
        self.assertEqual(len(result['tasks']), len(old['tasks']))
        self.assertEqual(calls, ['facts', 'conditions', 'facts'])
        for entry in result['tasks'].values():
            self.assertEqual(entry['status'], 'complete')
            self.assertEqual(entry['reused_from']['kind'], 'exact_response_revalidated')
            if entry['stage'] != 'discovery':
                self.assertTrue(read(sibling / entry['result_path'])['revalidated_by_new_runtime'])

    def test_upgrade_rejects_tampered_old_response(self):
        old = self.execute(client=ContractClient(), validator=workflow.validate_response)
        response = self.workspace / self.task(old, 'discovery')['response_path']
        response.write_text('{}', encoding='utf-8')
        sibling = self.root / 'upgraded'
        self.prepare(sibling)
        with self.assertRaises(runtime.IntegrityError):
            self.upgraded(sibling)

    def test_unknown_response_cannot_be_revalidated_or_resent(self):
        failed = ContractClient(fail_stage='discovery',
                                failure=RequestFailure('network_outcome_unknown', ambiguous=True))
        self.execute(client=failed, validator=workflow.validate_response)
        count = len(read(self.ledger)['attempts'])
        sibling = self.root / 'upgraded'
        self.prepare(sibling)
        client = ContractClient()
        state = self.upgraded(sibling, client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(len(read(self.ledger)['attempts']), count)
        self.assertTrue(all(e['status'] == 'blocked_unknown_scope' for e in state['tasks'].values()))

    def test_changed_model_does_not_reuse_old_response(self):
        self.execute(client=ContractClient(), validator=workflow.validate_response)
        sibling = self.root / 'upgraded'
        self.prepare(sibling)
        self.cfg['model'] = 'different-request-model'
        client = ContractClient()
        state = self.upgraded(sibling, client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(state['stop_reason'], 'live_required')
        self.assertFalse(any(e.get('reused_from') for e in state['tasks'].values()))

    def test_known_403_remains_failed_without_repaying_same_request(self):
        client = ContractClient(fail_stage='discovery',
                                failure=RequestFailure('http_error', 403, ambiguous=False))
        self.execute(client=client, validator=workflow.validate_response)
        paid = self.ledger.read_bytes()
        sibling = self.root / 'upgraded'
        self.prepare(sibling)
        state = self.upgraded(sibling)
        entry = self.task(state, 'discovery')
        self.assertEqual(entry['status'], 'http_failure')
        self.assertEqual(entry['http_status'], 403)
        self.assertEqual(entry['reused_from']['kind'], 'known_http_failure_preserved')
        self.assertEqual(self.ledger.read_bytes(), paid)

    def test_refresh_checks_each_source_workspace_once_and_still_detects_tampering(self):
        state = self.execute(client=ContractClient(), validator=workflow.validate_response)
        index = read(str(self.ledger) + '.candidate_index.json')
        with patch.object(runtime, '_check_state', wraps=runtime._check_state) as check:
            runtime._refresh_index(index, self.ledger)
        self.assertEqual(check.call_count, 1)
        path = self.workspace / self.task(state, 'facts')['result_path']
        path.write_text('{}', encoding='utf-8')
        with self.assertRaises(runtime.IntegrityError):
            runtime._refresh_index(index, self.ledger)

    def test_resume_does_not_rewrite_unchanged_completed_state(self):
        self.execute(client=ContractClient(), validator=workflow.validate_response)
        state = read(self.workspace / 'candidate_state.json')
        with patch.object(runtime, 'save', wraps=save) as writes:
            runtime._recover(self.workspace, state, self.ledger, workflow.validate_response)
        writes.assert_not_called()
