import json
from pathlib import Path
import tempfile
import unittest

from api import RequestFailure
from corpus import HERE, read, save, sha
from test_runner import config
from test_two_stage import fixture
from two_stage import CALLS, request_for, run_call


class FakeClient:
    def __init__(self, fail=None):
        self.calls = 0; self.fail = fail
    def complete(self, request):
        self.calls += 1
        if self.fail: raise self.fail
        _, payload, _ = fixture()
        return {'model': 'fixture-only', 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(payload)}}], 'usage': {'total_tokens': 10}}


class TwoStageRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        j, _, _ = fixture()
        save(self.work / 'active.json', dict(j, doi='fixture'))
        save(self.work / 'empty.json', dict(j, doi='fixture'))
        save(self.work / 'config.json', config())
        for n, origin in [('one_step.md', 'prompt.md'), ('discovery.md', 'discovery.md'),
                          ('enrichment.md', 'enrichment.md')]:
            (self.work / n).write_bytes((HERE / origin).read_bytes())
        (self.work / 'source.xml').write_text('fixture', encoding='utf-8')
        save(self.work / 'reference.json', {'secret_answer_marker': 'NEVER_SEND_EXPECTED_ANSWER'})
        self.freeze()

    def freeze(self):
        save(self.work / 'manifest.json', {
            'source_path': str(self.work / 'source.xml'),
            'source_sha256': sha(self.work / 'source.xml'),
            'input_hashes': {p.name: sha(p) for p in self.work.iterdir()
                             if p.name in {'active.json', 'empty.json', 'config.json',
                                           'one_step.md', 'discovery.md', 'enrichment.md', 'reference.json'}}})

    def test_no_live_no_send(self):
        c = FakeClient()
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_active', client=c)
        self.assertEqual(c.calls, 0)

    def test_cached_no_resend(self):
        c = FakeClient()
        run_call(self.work, 'discovery_active', True, client=c)
        run_call(self.work, 'discovery_active', True, client=c)
        self.assertEqual(c.calls, 1)

    def test_reference_not_in_requests(self):
        for name in CALLS:
            request, _ = request_for(self.work, name, config(), [])
            self.assertNotIn('NEVER_SEND_EXPECTED_ANSWER', json.dumps(request))

    def test_discovery_sees_no_context(self):
        r, _ = request_for(self.work, 'discovery_active', config())
        self.assertNotIn('context_units', json.loads(r['messages'][1]['content']))

    def test_dependency_required_before_paid_enrichment(self):
        c = FakeClient()
        with self.assertRaises(ValueError): run_call(self.work, 'enrich_active', True, client=c)
        self.assertEqual(c.calls, 0)

    def test_token_reservation_stops_before_send(self):
        cfg = config(); cfg['max_reserved_tokens'] = 1
        save(self.work / 'config.json', cfg); self.freeze()
        c = FakeClient()
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_active', True, client=c)
        self.assertEqual(c.calls, 0)

    def test_unknown_outcome_blocks_other_calls(self):
        c = FakeClient(RequestFailure('timeout', ambiguous=True))
        run_call(self.work, 'discovery_active', True, client=c)
        with self.assertRaises(ValueError): run_call(self.work, 'baseline_empty', True, client=c)
        self.assertEqual(c.calls, 1)

    def test_known_failure_no_implicit_retry(self):
        c = FakeClient(RequestFailure('http_error', 500))
        run_call(self.work, 'discovery_active', True, client=c)
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_active', True, client=c)
        c.fail = None
        run_call(self.work, 'discovery_active', True, retry=True, client=c)
        self.assertEqual(c.calls, 2)

    def test_hard_six_request_cap(self):
        cfg = config(); cfg['max_requests'] = 7
        save(self.work / 'config.json', cfg); self.freeze()
        c = FakeClient()
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_active', True, client=c)
        self.assertEqual(c.calls, 0)

    def test_changed_frozen_input_blocks(self):
        (self.work / 'discovery.md').write_text('changed', encoding='utf-8')
        c = FakeClient()
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_active', True, client=c)
        self.assertEqual(c.calls, 0)

    def test_changed_saved_discovery_blocks_enrichment(self):
        c = FakeClient(); run_call(self.work, 'discovery_active', True, client=c)
        save(self.work / 'results/discovery_active.json', {'accepted': []})
        with self.assertRaises(ValueError): run_call(self.work, 'enrich_active', True, client=c)
        self.assertEqual(c.calls, 1)

    def test_request_persisted_before_send(self):
        outer = self
        class InspectClient(FakeClient):
            def complete(self, request):
                state = read(outer.work / 'state.json')
                outer.assertEqual(state['attempts'][0]['status'], 'in_flight')
                outer.assertTrue((outer.work / state['attempts'][0]['request_path']).exists())
                return super().complete(request)
        run_call(self.work, 'discovery_active', True, client=InspectClient())

    def test_full_workflow_with_synthetic_responses(self):
        cfg = config(); cfg['max_requests'] = 6
        save(self.work / 'config.json', cfg); self.freeze()
        _, discovered, enriched = fixture()
        baseline = {'schema_version': 1, 'paper_id': 'P',
                    'records': [enriched['items'][0]['record']],
                    'coverage_notes': [], 'no_negative_reason': None}
        empty_discovery = {'paper_id': 'P', 'candidates': [], 'coverage_notes': [],
                           'no_candidate_reason': 'No result in the selected methods.'}
        empty_baseline = dict(baseline, records=[], no_negative_reason='Methods only.')
        replies = [baseline, discovered, empty_discovery, enriched, empty_baseline]
        class WorkflowClient:
            calls = 0
            def complete(self, request):
                payload = replies[self.calls]; self.calls += 1
                return {'model': 'fixture-only', 'choices': [{'finish_reason': 'stop',
                        'message': {'content': json.dumps(payload)}}],
                        'usage': {'total_tokens': 10}}
        c = WorkflowClient()
        for name in CALLS:
            result = run_call(self.work, name, True, client=c)
        self.assertEqual(c.calls, 5)
        self.assertEqual(set(result['calls'].values()), {'complete'})
        self.assertEqual(result['reported_tokens'], 50)
        e = read(self.work / 'results/enrich_active.json')
        self.assertEqual(len(e['accepted']), 1)
        self.assertEqual(e['accepted'][0]['record']['fields']['perturbation'], 'Z')
        self.assertFalse(e['accepted'][0]['record']['ready_for_training'])

    def test_no_discoveries_skips_paid_enrichment(self):
        class EmptyClient:
            calls = 0
            def complete(self, request):
                self.calls += 1
                payload = {'paper_id': 'P', 'candidates': [], 'coverage_notes': [],
                           'no_candidate_reason': 'No negatives found.'}
                return {'choices': [{'finish_reason': 'stop',
                        'message': {'content': json.dumps(payload)}}]}
        c = EmptyClient()
        run_call(self.work, 'discovery_active', True, client=c)
        s = run_call(self.work, 'enrich_active', True, client=c)
        self.assertEqual(c.calls, 1)
        self.assertEqual(s['calls']['enrich_active'], 'skipped_no_candidates')

    def test_workspace_cumulative_limit(self):
        cfg = config(); cfg['max_requests'] = 1
        save(self.work / 'config.json', cfg); self.freeze()
        c = FakeClient()
        run_call(self.work, 'discovery_active', True, client=c)
        with self.assertRaises(ValueError): run_call(self.work, 'discovery_empty', True, client=c)
        self.assertEqual(c.calls, 1)
