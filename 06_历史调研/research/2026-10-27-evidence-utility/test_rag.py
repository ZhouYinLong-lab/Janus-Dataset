import copy
import json
from pathlib import Path
import tempfile
import unittest

from common import CORE, HERE, read, write
from evaluate import complete_denominator, make_packet, score
from prepare import prepare
from rag import prepare_rag, retrieve
from run import budget, export, RequestFailure, run, validate
from test_contracts import fixture


def trial_fixture(root, arms=('no_retrieval', 'recovered')):
    release, ws, sup = fixture(root)
    prepare(release, [ws], root / 'bundle', sup)
    question = {'question_id': 'q1', 'question': 'Did synthetic compound X0 reduce protein Y0?',
                'protocol': 'evidence_lookup', 'split': 'test', 'source_dois': ['10.0000/synthetic0'],
                'rubric': [{'id': 'scope', 'text': 'Retains 1 uM and 4 h.'}],
                'reference_answer': 'GOLD_SECRET_DO_NOT_SEND', 'gold_status': 'assistant_reviewed',
                'evaluation_group': 'source0'}
    write(root / 'questions.json', [question])
    prepare_rag(root / 'bundle', root / 'questions.json', HERE / 'api.example.json', root / 'trial', arms=arms)
    return root / 'trial'


class FakeClient:
    def __init__(self, failure=None):
        self.calls, self.failure = 0, failure

    def complete(self, req):
        self.calls += 1
        if self.failure:
            raise self.failure
        return {'model': 'deepseek-flash', 'usage': {'total_tokens': 10},
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
                    'answer': 'No reduction at 1 uM, 4 h.', 'citations': [], 'uncertainty': ''})}}]}


class RagTests(unittest.TestCase):
    def test_retrieval_no_crop_and_gold_not_sent(self):
        self.assertEqual(retrieve('protein', [{'evidence_id': 'x', 'text': 'protein' * 100}], 10), [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            tasks = read(trial / 'tasks.json')
            self.assertNotIn('GOLD_SECRET', json.dumps(tasks))
            self.assertEqual(tasks[0]['evidence_ids'], [])

    def test_new_combination_excludes_test_and_source_doi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial_fixture(root)
            qs = read(root / 'questions.json')
            qs[0]['protocol'] = 'new_combination'
            qs[0]['source_dois'] = [r['doi'] for r in read(root / 'bundle/evidence.json')]
            write(root / 'questions2.json', qs)
            prepare_rag(root / 'bundle', root / 'questions2.json', HERE / 'api.example.json', root / 'novel')
            self.assertTrue(all(not t['evidence_ids'] for t in read(root / 'novel/tasks.json')))

    def test_resume_and_ledger_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            ledger = root / 'ledger.json'
            budget.create(ledger, 10, 100000, 'synthetic test')
            client = FakeClient()
            run(trial, ledger, live=True, client=client, max_new_requests=1)
            self.assertEqual(client.calls, 1)
            result = run(trial, ledger, live=True, client=client)
            run(trial, ledger, live=True, client=client)
            self.assertEqual(client.calls, 2)
            self.assertEqual(result['status_counts'], {'complete': 2})
            self.assertEqual(len(read(ledger)['attempts']), 2)
            state = read(trial / 'state.json')
            tid = next(iter(state['tasks']))
            state['tasks'][tid]['status'] = 'in_flight'
            write(trial / 'state.json', state)
            run(trial, ledger, live=True, client=client)
            self.assertEqual(client.calls, 2)

    def test_unknown_and_429_stop_and_no_auto_retry(self):
        for failure in (RequestFailure('network_outcome_unknown', ambiguous=True),
                        RequestFailure('http_error', http_status=429)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                trial = trial_fixture(root)
                ledger = root / 'ledger.json'
                budget.create(ledger, 10, 100000, 'synthetic')
                client = FakeClient(failure)
                run(trial, ledger, live=True, client=client)
                run(trial, ledger, live=True, client=client)
                self.assertEqual(client.calls, 1)
                self.assertEqual(len(read(ledger)['attempts']), 1)
                if failure.http_status == 429:
                    self.assertEqual(read(ledger)['global_stop'], 'provider_http_429')

    def test_budget_failure_denominator_and_blinded_judging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            ledger = root / 'ledger.json'
            budget.create(ledger, 1, 100000, 'synthetic')
            run(trial, ledger, live=True, client=FakeClient())
            make_packet(trial, root / 'packet')
            js = read(root / 'packet/blinded_packet.json')
            self.assertNotIn('arm', js[0])
            js[0]['judgment'] = {'criteria': {'scope': True}, 'overclaim': False,
                                 'citation_supported': True, 'judge': 'synthetic', 'reason': 'test'}
            write(root / 'judgments.json', js)
            result = score(trial, root / 'packet', root / 'judgments.json', root / 'scores')
            arms = result['strata']['test:evidence_lookup']['arms']
            self.assertEqual(arms['recovered']['missing_or_unjudged'], 1)
            self.assertEqual(arms['recovered']['score_all_expected'], 0)

    def test_citations_and_returned_model_contract(self):
        envelope = FakeClient().complete({})
        task = {'schema': 'qa', 'evidence_ids': []}
        with self.assertRaisesRegex(ValueError, 'model'):
            validate(envelope, task, ['other'])
        obj = json.loads(envelope['choices'][0]['message']['content'])
        obj['citations'] = ['invented']
        envelope['choices'][0]['message']['content'] = json.dumps(obj)
        with self.assertRaisesRegex(ValueError, 'citation'):
            validate(envelope, task, ['deepseek-flash'])

    def test_missing_answer_cannot_shrink_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            write(trial / 'exports/answers.json', [])
            result = complete_denominator(trial)
            self.assertEqual(len(result), 2)
            self.assertTrue(all(r['status'] == 'missing' for r in result))

    def test_orphan_request_stops_without_resend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            ledger = root / 'ledger.json'
            budget.create(ledger, 10, 100000, 'synthetic')
            client = FakeClient()
            run(trial, ledger, live=True, client=client, max_new_requests=1)
            state = read(trial / 'state.json')
            tid = next(iter(state['tasks']))
            entry = state['tasks'][tid]
            entry['status'] = 'in_flight'
            (trial / entry['response_path']).unlink()
            entry.pop('response_sha256')
            write(trial / 'state.json', state)
            result = run(trial, ledger, live=True, client=client)
            self.assertEqual(client.calls, 1)
            self.assertEqual(result['stop_reason'], 'network_outcome_unknown')

    def test_identical_arms_reuse_success_without_paying_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root, arms=('no_retrieval', 'structured'))
            ledger = root / 'ledger.json'
            budget.create(ledger, 10, 100000, 'synthetic')
            client = FakeClient()
            result = run(trial, ledger, live=True, client=client)
            self.assertEqual(client.calls, 1)
            self.assertEqual(result['status_counts'], {'complete': 2})
            self.assertEqual(result['cache_reused_tasks'], 1)
            self.assertEqual(result['usage']['requests_reserved'], 1)


if __name__ == '__main__':
    unittest.main()
