"""Offline v3 orchestration tests with real plans and injected response contracts."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from api import RequestFailure
import batch_budget as budget
import candidate_runtime as runtime
from corpus import parse_source, read, save, sha
import sentence_v3
import sentence_workflow as workflow


def config():
    return {'base_url': 'https://offline.invalid/v1', 'model': 'synthetic-only',
            'api_key_env': 'NO_TEST_KEY', 'timeout_seconds': 2,
            'max_output_tokens': 500, 'output_token_parameter': 'max_tokens',
            'response_format': 'json_object', 'max_requests': 100,
            'max_reserved_tokens': 5_000_000}


class Client:
    def __init__(self, fail_stage=None, failure=None, empty=False):
        self.calls = []
        self.fail_stage = fail_stage
        self.failure = failure
        self.empty = empty

    def complete(self, request):
        stage = request['messages'][0]['content'].split()[-1]
        user = json.loads(request['messages'][1]['content'])
        self.calls.append((stage, deepcopy(user)))
        if stage == self.fail_stage:
            raise self.failure
        if stage == 'discovery':
            payload = {'paragraphs': [
                {'paragraph_id': p['paragraph_id'],
                 'status': 'none_found' if self.empty else 'has_candidates',
                 'spans': [] if self.empty else [{'sentence_ids': p['sentence_ids']}]}
                for p in user['paragraphs']]}
        else:
            payload = {'stage': stage}
        return {'model': 'synthetic-only', 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(payload)}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}


class ContractClient(Client):
    """Synthetic envelopes accepted by the actual facts/conditions validators."""
    def complete(self, request):
        from facts_v3 import FIELDS
        envelope = super().complete(request)
        stage, user = self.calls[-1]
        if stage == 'discovery':
            return envelope
        if stage == 'facts':
            sid = user['anchor_sentence_ids'][0]
            text = next(s['text'] for s in user['sentences'] if s['sentence_id'] == sid)
            observations = []
            rows = [('degradation', 'conditional_loss', 'did not degrade target T'),
                    ('binding', 'reduced', 'showed weaker binding')] if 'weaker binding' in text else [
                        ('degradation', 'not_improved', 'did not improve target T degradation')]
            for endpoint, outcome, observation in rows:
                values = dict.fromkeys(FIELDS)
                values.update(subject='Compounds A and B' if len(rows) == 2 else 'Compound C',
                              target='target T', endpoint=endpoint, observation=observation)
                observations.append({'values': values, 'outcome_type': outcome,
                                     'evidence': {f: [sid] if values[f] else [] for f in FIELDS}})
            payload = {'status': 'observations', 'reason': None, 'observations': observations}
        else:
            support = next(s['sentence_id'] for s in user['sentences'] if s['kind'] == 'figure_caption')
            payload = {'items': []}
            for record in user['records']:
                values = dict.fromkeys(workflow.CONDITION_FIELDS)
                values.update(treatment_time='24 h', tested_concentration='1 nM')
                payload['items'].append({'record_id': record['record_id'], 'values': values,
                                         'evidence': {f: [support] if values[f] else [] for f in values}})
        envelope['choices'][0]['message']['content'] = json.dumps(payload)
        return envelope


class SentenceRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='sentence_runtime_')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'workspace'
        self.ledger = self.root / 'budget.json'
        self.cfg = config()
        self.validated = []
        self.built = []
        budget.create(self.ledger, 100, 8_000_000, 'Synthetic offline fixtures')
        self.source = self.root / 'source.xml'
        self.source.write_text(
            '<article><body><sec><title>Results</title>'
            '<p id="a">Compounds A and B did not degrade target T and showed weaker binding '
            'under Z (<xref ref-type="fig" rid="f1">Fig. 1</xref>).</p>'
            '<p id="b">Compound C did not improve target T degradation '
            '(<xref ref-type="fig" rid="f1">Fig. 1</xref>).</p></sec>'
            '<fig id="f1"><label>Figure 1</label><caption><p>Target T was measured '
            'after 24 h at 1 nM in cells with Z.</p></caption></fig></body></article>',
            encoding='utf-8')
        self.prepare(self.workspace)
        self.client = Client()
        self.key = patch('credentials.load_key', side_effect=AssertionError('No credentials')).start()
        self.transport = patch('candidate_transport.DiagnosticStreamingClient',
                               side_effect=AssertionError('No network')).start()
        self.addCleanup(patch.stopall)

    def prepare(self, workspace):
        doc = parse_source(self.source, 'P')
        indexed = sentence_v3.build_sentence_jobs(doc, {'doi': '10.synthetic/offline', 'title': 'Fixture'})
        manifest = {'pipeline': 'molgluedb_sentence_v3', 'protocol': 'sentence_v3', 'papers': [
            {'paper_id': 'P', 'source_path': str(self.source), 'source_sha256': sha(self.source)}],
            'job_ids': [], 'file_hashes': {}, 'code_hashes': {}}
        document_path = workspace / 'documents/P.json'
        index_path = workspace / 'documents/P_sentences.json'
        save(document_path, doc)
        save(index_path, indexed['sentences'])
        for path in (document_path, index_path):
            manifest['file_hashes'][path.relative_to(workspace).as_posix()] = sha(path)
        for job in indexed['jobs']:
            job.update(document_path=str(document_path), document_sha256=sha(document_path),
                       sentence_index_path=str(index_path), sentence_index_sha256=sha(index_path))
            name = f'jobs/{job["job_id"]}.json'
            save(workspace / name, job)
            manifest['job_ids'].append(job['job_id'])
            manifest['file_hashes'][name] = sha(workspace / name)
        manifest['papers'][0].update(job_ids=list(manifest['job_ids']),
                                     document_path=str(document_path), sentence_index_path=str(index_path))
        for stage in ('discovery', 'facts', 'conditions'):
            name = stage + '_v3.md'
            (workspace / name).write_text('Synthetic offline ' + stage, encoding='utf-8')
            manifest['file_hashes'][name] = sha(workspace / name)
        save(workspace / 'manifest.json', manifest)
        self.jid = manifest['job_ids'][0]
        return manifest

    def builder(self, workspace, job, stage, cfg, candidates=None, discovery_hash=None):
        self.assertEqual(job['active_stage'], stage)
        if stage in {'facts', 'conditions'}:
            state = read(Path(workspace) / 'candidate_state.json')
            self.assertEqual(discovery_hash, state['tasks'][self.jid + ':discovery']['result_sha256'])
            self.assertEqual(len(candidates), 1)
            self.assertEqual(job['frozen_context']['candidates'], candidates)
        self.built.append((stage, deepcopy(job), deepcopy(candidates)))
        return workflow.request_for(workspace, job, stage, cfg, candidates, discovery_hash)

    def validator(self, payload, job, candidates):
        stage = job['active_stage']
        self.assertEqual(stage, payload['stage'])
        self.assertIn(stage, ('facts', 'conditions'))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates, job['frozen_context']['candidates'])
        self.validated.append((stage, deepcopy(job), deepcopy(candidates)))
        if stage == 'facts':
            # Multiple observations from one discovery candidate must share
            # one facts request and at most one subsequent conditions request.
            records = [{'candidate_id': candidates[0]['candidate_id'],
                        'record_key': f'{candidates[0]["candidate_id"]}_{n}',
                        'values': {'subject': 'Compounds A and B', 'target': 'target T',
                                   'endpoint': endpoint, 'scope_condition': None},
                        'outcome_type': 'conditional_loss', 'field_evidence': []}
                       for n, endpoint in enumerate(('degradation', 'binding'))]
        else:
            self.assertTrue(job['facts_result_sha256'])
            records = job['frozen_context']['records']
        return {'accepted': [{'candidate_id': candidates[0]['candidate_id'], 'record': r} for r in records],
                'rejected': [], 'unresolved': [], 'accounting_complete': True}

    def execute(self, workspace=None, client=None, use_client=True, validator=None, **kwargs):
        with redirect_stdout(io.StringIO()):
            return runtime.run(workspace or self.workspace, self.cfg, self.ledger,
                               self.builder, validator or self.validator,
                               client=(client or self.client) if use_client else None,
                               **dict({'live': True}, **kwargs))

    def task(self, state, stage, group=0):
        return state['tasks'][runtime._task_key(self.jid, stage, group)]

    def test_real_plans_dispatch_and_multiple_observations_use_one_conditions_request(self):
        with (patch.object(sentence_v3, 'validate_discovery', wraps=sentence_v3.validate_discovery) as discover,
                patch.object(workflow, 'plan_facts', wraps=workflow.plan_facts) as facts,
                patch.object(workflow, 'plan_conditions', wraps=workflow.plan_conditions) as conditions):
            state = self.execute()
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(facts.call_count, 1)
        self.assertEqual(conditions.call_count, 2)
        self.assertEqual([stage for stage, _ in self.client.calls],
                         ['discovery', 'facts', 'conditions', 'facts', 'conditions'])
        self.assertEqual([stage for stage, _, _ in self.validated],
                         ['facts', 'conditions', 'facts', 'conditions'])
        self.assertEqual(len(state['tasks']), 5)
        self.assertEqual(state['version'], 3)
        for n in range(2):
            facts_entry, condition_entry = self.task(state, 'facts', n), self.task(state, 'conditions', n)
            self.assertEqual(facts_entry['accepted'], 2)
            self.assertEqual(condition_entry['accepted'], 2)
            self.assertEqual(condition_entry['facts_result_sha256'], facts_entry['result_sha256'])
            descriptor = state['condition_groups'][runtime._task_key(self.jid, 'conditions', n)]
            plan = read(self.workspace / descriptor['path'])
            self.assertEqual(plan['facts_result_sha256'], facts_entry['result_sha256'])
            self.assertEqual(len(plan['group']['requested_record_ids']), 2)
            planner_job, fact_result, candidate = conditions.call_args_list[n].args
            self.assertEqual(planner_job['frozen_context']['candidates'], [candidate])
            self.assertEqual(len(fact_result['accepted']), 2)
        self.key.assert_not_called()
        self.transport.assert_not_called()

    def test_real_workflow_builder_and_validators_preserve_records_across_stages(self):
        client = ContractClient()
        state = self.execute(client=client, validator=workflow.validate_response)
        self.assertTrue(all(e['status'] == 'complete' for e in state['tasks'].values()))
        self.assertEqual([s for s, _ in client.calls], ['discovery', 'facts', 'conditions', 'facts'])
        self.assertEqual(self.task(state, 'facts')['accepted'], 2)
        self.assertEqual(self.task(state, 'conditions')['accepted'], 1)
        self.assertEqual(self.task(state, 'facts', 1)['accepted'], 1)
        condition = read(self.workspace / self.task(state, 'conditions')['result_path'])
        revised = condition['accepted'][0]['record']
        self.assertEqual(revised['conditions']['treatment_time'], '24 h')
        self.assertEqual(revised['conditions']['tested_concentration'], '1 nM')
        self.assertEqual(revised['core_original']['record_key'], revised['record_key'])
        skipped = state['condition_groups'][runtime._task_key(self.jid, 'conditions', 1)]
        self.assertEqual(skipped['reason'], 'not_needed')
        count = len(client.calls)
        self.execute(client=client, validator=workflow.validate_response, live=False)
        self.assertEqual(len(client.calls), count)

    def test_resume_uses_frozen_plans_and_does_not_call_planners_or_clients(self):
        first = self.execute()
        count = len(self.client.calls)
        with (patch.object(workflow, 'plan_facts', side_effect=AssertionError('Facts replanned')),
                patch.object(workflow, 'plan_conditions', side_effect=AssertionError('Conditions replanned'))):
            second = self.execute(live=False)
        self.assertEqual(len(self.client.calls), count)
        self.assertEqual(first['groups'], second['groups'])
        self.assertEqual(first['condition_groups'], second['condition_groups'])
        self.assertEqual(len(read(self.ledger)['attempts']), 5)

    def test_optional_none_condition_plan_is_persisted_and_not_replanned(self):
        with patch.object(workflow, 'plan_conditions', return_value=None) as planner:
            first = self.execute()
        self.assertEqual(planner.call_count, 2)
        self.assertEqual([s for s, _ in self.client.calls], ['discovery', 'facts', 'facts'])
        for descriptor in first['condition_groups'].values():
            frozen = read(self.workspace / descriptor['path'])
            self.assertIsNone(frozen['group'])
            self.assertEqual(frozen['reason'], 'required_context_unavailable_or_already_supplied')
            self.assertEqual(descriptor['reason'], frozen['reason'])
        with patch.object(workflow, 'plan_conditions', side_effect=AssertionError('None replanned')):
            self.execute()
        self.assertEqual(len(self.client.calls), 3)

    def test_none_condition_reason_preserves_all_core_records_without_extra_requests(self):
        for kind in ('endpoint', 'semantic_pending', 'conditional_missing_scope',
                     'conditional_supplied_scope', 'usable', 'no_accepted_records'):
            with self.subTest(kind=kind):
                workspace = self.root / ('none_reason_' + kind)
                self.prepare(workspace)
                self.cfg['model'] = 'reason-' + kind

                def validator(payload, job, candidates):
                    result = self.validator(payload, job, candidates)
                    for item in result['accepted']:
                        item['record'].update(outcome_type='reduced', record_status='core_usable')
                    last = result['accepted'][-1]['record']
                    if kind == 'endpoint':
                        last['endpoint_verification_required'] = True
                    elif kind == 'semantic_pending':
                        last['record_status'] = 'semantic_pending'
                    elif kind.startswith('conditional_'):
                        last['outcome_type'] = 'conditional_loss'
                        last['values']['scope_condition'] = ('under Z' if kind == 'conditional_supplied_scope' else None)
                    elif kind == 'no_accepted_records':
                        result['accepted'] = []
                    return result

                before = len(self.client.calls)
                with patch.object(workflow, 'plan_conditions', return_value=None):
                    state = self.execute(workspace=workspace, validator=validator)
                expected = ('required_context_unavailable_or_already_supplied' if kind in
                            {'endpoint', 'semantic_pending', 'conditional_missing_scope'} else 'not_needed')
                self.assertEqual(len(self.client.calls) - before, 3)
                self.assertFalse(any(e['stage'] == 'conditions' for e in state['tasks'].values()))
                for n in range(2):
                    descriptor = state['condition_groups'][runtime._task_key(self.jid, 'conditions', n)]
                    frozen = read(workspace / descriptor['path'])
                    self.assertEqual(frozen['reason'], expected)
                    self.assertEqual(descriptor['reason'], expected)
                    fact_entry = self.task(state, 'facts', n)
                    self.assertEqual(frozen['facts_result_sha256'], fact_entry['result_sha256'])
                    fact_result = read(workspace / fact_entry['result_path'])
                    self.assertEqual(len(fact_result['accepted']), 0 if kind == 'no_accepted_records' else 2)
                with patch.object(workflow, 'plan_conditions', side_effect=AssertionError('Replanned')):
                    resumed = self.execute(workspace=workspace, validator=validator, live=False)
                self.assertEqual(state['condition_groups'], resumed['condition_groups'])
                self.assertEqual(len(self.client.calls) - before, 3)

    def test_conditions_http_failure_is_not_retried_per_observation_or_resume(self):
        self.client = Client('conditions', RequestFailure('http_error', 429))
        state = self.execute()
        self.assertEqual(self.task(state, 'conditions')['status'], 'http_failure')
        self.assertEqual(sum(s == 'conditions' for s, _ in self.client.calls), 2)
        self.execute()
        self.assertEqual(len(self.client.calls), 5)

    def test_unknown_conditions_blocks_same_source_and_never_resends(self):
        self.client = Client('conditions', RequestFailure('network_outcome_unknown', ambiguous=True))
        state = self.execute()
        self.assertEqual(self.task(state, 'conditions')['status'], 'needs_attention')
        self.assertEqual(self.task(state, 'facts', 1)['status'], 'blocked_unknown_scope')
        count = len(self.client.calls)
        self.execute()
        self.assertEqual(len(self.client.calls), count)
        sibling = self.root / 'changed_prompt'
        self.prepare(sibling)
        manifest = read(sibling / 'manifest.json')
        prompt = sibling / 'discovery_v3.md'
        prompt.write_text('Different instructions discovery', encoding='utf-8')
        manifest['file_hashes']['discovery_v3.md'] = sha(prompt)
        save(sibling / 'manifest.json', manifest)
        blocked = self.execute(workspace=sibling)
        self.assertEqual(self.task(blocked, 'discovery')['status'], 'blocked_unknown_scope')
        self.assertEqual(len(self.client.calls), count)

    def test_unknown_facts_does_not_schedule_conditions(self):
        self.client = Client('facts', RequestFailure('network_outcome_unknown', ambiguous=True))
        state = self.execute()
        self.assertEqual(self.task(state, 'facts')['status'], 'needs_attention')
        self.assertNotIn(runtime._task_key(self.jid, 'conditions'), state['tasks'])
        self.assertEqual([s for s, _ in self.client.calls], ['discovery', 'facts'])

    def test_recovery_uses_correct_context_and_stage_without_new_sends(self):
        for stage in ('facts', 'conditions'):
            with self.subTest(stage=stage):
                workspace = self.root / ('recover_' + stage)
                self.prepare(workspace)
                self.cfg['model'] = 'synthetic-' + stage
                client = Client()
                original = runtime.save

                def crash(path, value):
                    original(path, value)
                    if Path(path).parent.name == 'responses' and client.calls[-1][0] == stage:
                        raise KeyboardInterrupt()

                with patch.object(runtime, 'save', side_effect=crash), self.assertRaises(KeyboardInterrupt):
                    self.execute(workspace, client)
                previous_count = len(client.calls)
                self.validated.clear()
                state = self.execute(workspace, client, live=False)
                entry = self.task(state, stage)
                self.assertEqual(entry['status'], 'complete')
                self.assertEqual(entry['recovery'], 'predeclared_response_file')
                self.assertEqual(len(client.calls), previous_count)
                recovered = [j for s, j, _ in self.validated if s == stage]
                self.assertEqual(len(recovered), 1)
                self.assertEqual(recovered[0]['active_stage'], stage)
                self.assertEqual(recovered[0]['frozen_context']['stage'], stage)
                if stage == 'conditions':
                    self.assertEqual(recovered[0]['facts_result_sha256'], self.task(state, 'facts')['result_sha256'])

    def test_crash_without_saved_facts_response_remains_unknown(self):
        self.client = Client('facts', KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.execute()
        self.execute(live=False)
        self.assertEqual([s for s, _ in self.client.calls], ['discovery', 'facts'])
        ledger = read(self.ledger)
        self.assertEqual(ledger['attempts'][-1]['status'], 'needs_attention')

    def test_invalid_saved_facts_can_be_validated_offline_without_resending(self):
        def broken(payload, job, candidates):
            if job['active_stage'] == 'facts':
                raise ValueError('Synthetic validation failure')
            return self.validator(payload, job, candidates)

        state = self.execute(validator=broken)
        self.assertEqual(self.task(state, 'facts')['status'], 'invalid_response')
        count = len(self.client.calls)
        state = self.execute(live=False)
        self.assertEqual(self.task(state, 'facts')['status'], 'complete')
        self.assertEqual(len(self.client.calls), count)
        self.assertFalse(any(s == 'conditions' for s, _ in self.client.calls))

    def test_saved_plan_and_facts_hash_tamper_stop_before_send(self):
        state = self.execute(max_new_requests=3)
        for target in (self.workspace / state['groups'][self.jid]['path'],
                       self.workspace / next(iter(state['condition_groups'].values()))['path'],
                       self.workspace / self.task(state, 'facts')['result_path']):
            with self.subTest(target=target.name):
                original = target.read_bytes()
                target.write_text('{}', encoding='utf-8')
                count = len(self.client.calls)
                with self.assertRaises(runtime.IntegrityError):
                    self.execute()
                self.assertEqual(len(self.client.calls), count)
                target.write_bytes(original)

    def test_conditions_entry_dependency_tamper_is_detected(self):
        state = self.execute(max_new_requests=3)
        self.task(state, 'conditions')['facts_result_sha256'] = 'changed'
        save(self.workspace / 'candidate_state.json', state)
        with self.assertRaisesRegex(runtime.IntegrityError, 'facts dependency changed'):
            self.execute()

    def test_state_cannot_bypass_v3_dependencies_by_changing_pipeline_label(self):
        state = self.execute(max_new_requests=3)
        state['pipeline'] = 'molgluedb_candidates_v2'
        save(self.workspace / 'candidate_state.json', state)
        with self.assertRaises(runtime.IntegrityError):
            self.execute()
        self.assertEqual(len(self.client.calls), 3)

    def test_invalid_fact_plan_cannot_merge_candidates_or_omit_sentences(self):
        self.execute(max_new_requests=1)
        frozen_path = self.workspace / 'candidate_state.json'
        original_state = read(frozen_path)
        group_path = self.workspace / original_state['groups'][self.jid]['path']
        group_path.unlink()
        original_state['groups'] = {}
        for kind in ('merge', 'missing_sentences'):
            save(frozen_path, original_state)
            original_planner = workflow.plan_facts

            def bad(job, candidates):
                groups = original_planner(job, candidates)
                if kind == 'merge':
                    groups[0]['candidates'] += groups.pop()['candidates']
                else:
                    groups[0].pop('sentences')
                return groups

            with self.subTest(kind=kind), patch.object(workflow, 'plan_facts', side_effect=bad):
                with self.assertRaises(ValueError):
                    self.execute()
        self.assertEqual(len(self.client.calls), 1)

    def test_success_reuses_all_stages_across_workspace_without_new_reservations(self):
        first = self.execute()
        sibling = self.root / 'reuse'
        self.prepare(sibling)
        second = self.execute(workspace=sibling, live=False)
        self.assertEqual(len(self.client.calls), 5)
        self.assertEqual(len(read(self.ledger)['attempts']), 5)
        self.assertEqual(second['attempts'], [])
        self.assertTrue(all(e.get('reused_from') for e in second['tasks'].values()))
        self.assertEqual([e['result_sha256'] for e in first['tasks'].values()],
                         [e['result_sha256'] for e in second['tasks'].values()])

    def test_different_unrelated_paper_indexes_reference_and_inventory_do_not_change_task_identity(self):
        def add_unrelated(workspace, label):
            manifest = read(workspace / 'manifest.json')
            for name in ('sentence_indexes/unrelated.json', 'coverage_gaps/unrelated.json',
                         'inventory.json', 'acceptance_reference.json'):
                save(workspace / name, {'unrelated_paper': label})
                manifest['file_hashes'][name] = sha(workspace / name)
            manifest['papers'].append({'paper_id': label, 'job_ids': []})
            save(workspace / 'manifest.json', manifest)

        add_unrelated(self.workspace, 'pilot-only-paper')
        first = self.execute()
        sibling = self.root / 'different_inventory'
        self.prepare(sibling)
        add_unrelated(sibling, 'full-only-paper')
        second = self.execute(workspace=sibling, live=False, phase='full', use_client=False)
        self.assertEqual(len(self.client.calls), 5)
        self.assertEqual(len(read(self.ledger)['attempts']), 5)
        self.assertEqual(second['attempts'], [])
        self.assertTrue(all(e.get('reused_from') for e in second['tasks'].values()))
        self.assertEqual([e['logical_id'] for e in first['tasks'].values()],
                         [e['logical_id'] for e in second['tasks'].values()])
        self.key.assert_not_called()

    def test_protocol_artifact_changes_do_change_v3_task_identity(self):
        manifest = read(self.workspace / 'manifest.json')
        job = read(self.workspace / f'jobs/{self.jid}.json')
        request = workflow.request_for(self.workspace, job, 'discovery', self.cfg)
        for name in ('discovery_v3.md', 'facts_v3.md', 'conditions_v3.md',
                     'facts_schema.json', 'facts_example.json', 'conditions_schema.json',
                     'conditions_example.json', 'sentence_protocol.json'):
            with self.subTest(name=name):
                before = deepcopy(manifest)
                before['file_hashes'][name] = 'original hash'
                after = deepcopy(before)
                after['file_hashes'][name] = 'changed hash'
                self.assertNotEqual(runtime._logical(job, 'discovery', None, request, self.cfg, before),
                                    runtime._logical(job, 'discovery', None, request, self.cfg, after))

    def test_exhausted_budget_still_allows_verified_offline_success_reuse(self):
        self.execute()
        ledger = read(self.ledger)
        ledger['max_requests'] = len(ledger['attempts'])
        save(self.ledger, ledger)
        sibling = self.root / 'reuse_at_limit'
        self.prepare(sibling)
        state = self.execute(workspace=sibling, use_client=False, live=False)
        self.assertEqual(state['attempts'], [])
        self.assertEqual(len(state['tasks']), 5)
        self.assertTrue(all(e.get('reused_from') for e in state['tasks'].values()))
        self.key.assert_not_called()

    def test_changed_facts_result_dependency_prevents_reusing_conditions(self):
        self.execute()
        sibling = self.root / 'changed_facts'
        self.prepare(sibling)

        def changed(payload, job, candidates):
            result = self.validator(payload, job, candidates)
            if job['active_stage'] == 'facts':
                result['validation_marker'] = 'changed local facts validation'
            return result

        # Revalidate the same saved facts response locally, then verify that a
        # byte-identical conditions request with a different facts-result hash
        # cannot reuse the previous conditions outcome.
        original = runtime._reuse

        def revalidate(workspace, entry, record):
            original(workspace, entry, record)
            if entry['stage'] == 'facts':
                job = read(Path(workspace) / f'jobs/{self.jid}.json')
                frozen = runtime._groups(workspace, read(Path(workspace) / 'candidate_state.json'), job)[entry['group']]
                job['frozen_context'] = frozen
                runtime._validate(workspace, entry, job, frozen['candidates'], changed)

        with patch.object(runtime, '_reuse', side_effect=revalidate):
            state = self.execute(workspace=sibling, live=False)
        self.assertEqual(state['stop_reason'], 'live_required')
        self.assertNotIn(runtime._task_key(self.jid, 'conditions'), state['tasks'])
        self.assertEqual(len(self.client.calls), 5)

    def test_v3_never_calls_legacy_response_reuse(self):
        with patch.object(runtime, '_legacy_discovery', side_effect=AssertionError('v2 reuse')):
            self.execute()

    def test_global_request_and_token_budgets_block_before_credentials(self):
        for limit in ('requests', 'tokens'):
            with self.subTest(limit=limit):
                ledger = read(self.ledger)
                ledger['max_requests'] = 100
                ledger['max_reserved_tokens'] = 8_000_000
                if limit == 'requests':
                    # Simulate one completed downstream request on this shared
                    # ledger. Its exhausted reservation must survive v3 startup.
                    downstream = self.root / 'downstream'
                    downstream.mkdir(exist_ok=True)
                    attempt = budget.reserve(self.ledger, downstream, 'other',
                                             {'model': 'fixture', 'messages': [limit]}, 1)
                    budget.finish(self.ledger, attempt['attempt_id'], 'complete')
                    ledger = read(self.ledger)
                    ledger['max_requests'] = len(ledger['attempts'])
                else:
                    ledger['max_reserved_tokens'] = 1
                save(self.ledger, ledger)
                state = self.execute(use_client=False)
                self.assertIn('exhausted', state['stop_reason'])
                self.key.assert_not_called()
                self.transport.assert_not_called()
                self.assertFalse(self.client.calls)

    def test_zero_invocation_and_offline_limits_do_not_read_keys(self):
        for kwargs in ({'max_new_requests': 0}, {'live': False}):
            state = self.execute(use_client=False, **kwargs)
            self.assertIn(state['stop_reason'], ('invocation_request_limit', 'live_required'))
        self.key.assert_not_called()
        self.assertFalse(read(self.ledger)['attempts'])

    def test_manifest_input_code_and_source_hashes_are_enforced(self):
        manifest_path = self.workspace / 'manifest.json'
        manifest = read(manifest_path)
        frozen_runtime = self.workspace / 'runtime/candidate_runtime.py'
        frozen_runtime.parent.mkdir()
        source_runtime = Path(runtime.__file__)
        frozen_runtime.write_bytes(source_runtime.read_bytes())
        manifest['code_hashes']['candidate_runtime.py'] = sha(source_runtime)
        save(manifest_path, manifest)
        self.execute(max_new_requests=0)
        targets = [self.workspace / 'documents/P_sentences.json', frozen_runtime, self.source]
        for target in targets:
            with self.subTest(target=target.name):
                original = target.read_bytes()
                target.write_text('tampered', encoding='utf-8')
                with self.assertRaises(runtime.IntegrityError):
                    self.execute()
                target.write_bytes(original)
        self.assertFalse(self.client.calls)

    def test_legacy_unknown_scope_and_unmapped_full_run_remain_blocked(self):
        legacy = self.root / 'legacy'
        job = read(self.workspace / f'jobs/{self.jid}.json')
        save(legacy / f'jobs/{self.jid}.json', job)
        attempt = budget.reserve(self.ledger, legacy, self.jid + ':facts:000',
                                 {'model': 'old', 'messages': []}, 1)
        budget.finish(self.ledger, attempt['attempt_id'], 'needs_attention')
        # No state: the fallback task parser must understand facts suffixes.
        state = self.execute()
        self.assertEqual(self.task(state, 'discovery')['status'], 'blocked_unknown_scope')
        (legacy / f'jobs/{self.jid}.json').unlink()
        state = self.execute(phase='full')
        self.assertEqual(state['stop_reason'], 'blocked_unknown_mapping')
        self.assertFalse(self.client.calls)

    def test_empty_discovery_finishes_without_facts_or_conditions(self):
        self.client = Client(empty=True)
        state = self.execute()
        self.assertEqual(len(state['tasks']), 1)
        self.assertEqual(self.task(state, 'discovery')['accepted'], 0)
        self.assertEqual([s for s, _ in self.client.calls], ['discovery'])


if __name__ == '__main__':
    unittest.main()
