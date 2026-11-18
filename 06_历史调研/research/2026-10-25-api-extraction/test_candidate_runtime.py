"""Offline behavior tests: temporary ledgers, synthetic sources, injected client."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import psutil

from api import RequestFailure
import batch_budget as budget
from batch_candidate import candidate_enrichment, candidate_request_for
from batch_contract import discovery
import candidate_runtime as runtime
from contract import FIELDS
from corpus import HERE, parse_source, read, save, sha
from prepare import build_jobs


def config():
    return {'base_url': 'https://example.invalid/v1', 'model': 'fixture-only',
            'api_key_env': 'JANUS_OFFLINE_ONLY', 'timeout_seconds': 3,
            'max_output_tokens': 500, 'output_token_parameter': 'max_tokens',
            'response_format': 'json_object', 'max_requests': 100,
            'max_reserved_tokens': 5_000_000}


class Client:
    def __init__(self, failure=None, empty=False, candidates=1):
        self.calls = []
        self.failure = failure
        self.empty = empty
        self.candidates = candidates

    def complete(self, request):
        self.calls.append(deepcopy(request))
        if self.failure:
            raise self.failure
        user = json.loads(request['messages'][1]['content'])
        if 'candidates' not in user:
            unit = user['primary_units'][0]
            cs = [{'candidate_id': f'C{i}', 'unit_id': unit['unit_id'],
                   'quote': unit['text'], 'compound_mentions': ['Compound X'],
                   'condition_mentions': ['Z'], 'category': 'conditional_loss', 'notes': []}
                  for i in range(self.candidates)] if not self.empty else []
            payload = {'paper_id': user['paper_id'], 'candidates': cs,
                       'no_candidate_reason': None if cs else 'No reported negatives.',
                       'coverage_notes': []}
        else:
            items = []
            for c in user['candidates']:
                fields = dict.fromkeys(FIELDS)
                fields.update(compound='Compound X', target='protein T', perturbation='Z',
                              result_text='No degradation with Z')
                record = {'domain': 'molecular_glue', 'negative_type': 'conditional_loss',
                          'experimental_setting': 'special_condition', 'directness': 'explicit',
                          'fields': fields, 'qualifiers': [], 'evidence': [
                              {'field': f, 'unit_id': c['unit_id'], 'quote': c['quote']}
                              for f in ('compound', 'target', 'perturbation', 'result_text')]}
                items.append({'candidate_id': c['candidate_id'], 'record': record,
                              'field_search_status': {k: 'supported' if v is not None
                                                      else 'not_found_in_supplied_context'
                                                      for k, v in fields.items()}})
            payload = {'paper_id': user['paper_id'], 'items': items,
                       'unresolved': [], 'coverage_notes': []}
        return {'model': 'fixture-only', 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(payload)}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'workspace'
        self.ledger = self.root / 'budget.json'
        self.cfg = config()
        budget.create(self.ledger, 100, 8_000_000, 'Offline test fixtures only')
        # Any accidental credential or network path is a hard test failure.
        self.addCleanup(patch.stopall)
        self.key_loader = patch('credentials.load_key', side_effect=AssertionError('No real key')).start()
        patch('stream_http.StreamingClient', side_effect=AssertionError('No network client')).start()
        self.prepare()

    def prepare(self, workspace=None, paper_ids=('P1',), negative=True):
        workspace = workspace or self.workspace
        manifest = {'pipeline': 'molgluedb_candidates_v2', 'batch_size': 8,
                    'transport': 'sse', 'papers': [], 'job_ids': [],
                    'file_hashes': {}, 'code_hashes': {}}
        for pid in paper_ids:
            source = self.root / (pid + '.xml')
            if not source.exists():
                quote = ('Compound X did not degrade protein T after cotreatment with Z.'
                         if negative else 'Cells were maintained in RPMI medium.')
                source.write_text('<article><body><sec><title>Results</title>'
                                  '<p id="p1">' + quote + '</p></sec></body></article>', encoding='utf-8')
            doc = parse_source(source, pid)
            doc_path = f'documents/{pid}.json'
            save(workspace / doc_path, doc)
            manifest['file_hashes'][doc_path] = sha(workspace / doc_path)
            jobs = build_jobs(doc, {'title': 'Fixture'})
            for job in jobs:
                job['document_path'] = str(workspace / doc_path)
                name = f'jobs/{job["job_id"]}.json'
                save(workspace / name, job)
                manifest['file_hashes'][name] = sha(workspace / name)
                manifest['job_ids'].append(job['job_id'])
            manifest['papers'].append({'paper_id': pid, 'source_path': str(source),
                                        'source_sha256': sha(source),
                                        'job_ids': [j['job_id'] for j in jobs]})
        for name in ('discovery.md', 'enrichment.md', 'record_schema.txt'):
            (workspace / name).write_text('Synthetic prompt ' + name, encoding='utf-8')
            manifest['file_hashes'][name] = sha(workspace / name)
        save(workspace / 'manifest.json', manifest)
        return manifest

    def execute(self, client=None, workspace=None, **kwargs):
        return runtime.run(workspace or self.workspace, self.cfg, self.ledger,
                           candidate_request_for, candidate_enrichment,
                           client=client if client is not None else Client(),
                           **dict({'live': True}, **kwargs))

    def entries(self, state):
        return list(state['tasks'].values())

    def test_complete_and_resume_use_real_contract_without_credentials(self):
        client = Client()
        state = self.execute(client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual([e['status'] for e in self.entries(state)], ['complete', 'complete'])
        self.assertEqual(self.entries(state)[1]['accepted'], 1)
        self.assertIsNone(state['stop_reason'])
        self.assertEqual(state['budget_path'], str(self.ledger.resolve()))
        self.assertEqual(len(state['attempts']), 2)
        self.assertEqual(self.execute(client), state)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(read(self.ledger)['attempts']), 2)
        self.key_loader.assert_not_called()

    def test_frozen_group_shape_and_identical_builder_validator_material(self):
        seen = []
        def builder(workspace, job, stage, cfg, candidates=None, discovery_hash=None):
            if stage == 'enrichment':
                seen.append(deepcopy(job['frozen_context']))
            return candidate_request_for(workspace, job, stage, cfg, candidates, discovery_hash)
        def validator(payload, job, candidates):
            seen.append(deepcopy(job['frozen_context']))
            self.assertEqual(job['frozen_context']['candidates'], candidates)
            return candidate_enrichment(payload, job, candidates)
        state = runtime.run(self.workspace, self.cfg, self.ledger, builder, validator,
                            live=True, client=Client())
        self.assertEqual(seen[0], seen[1])
        discovery_entry, enriched = self.entries(state)
        self.assertEqual(enriched['group'], 0)
        self.assertTrue(next(k for k in state['tasks'] if ':enrichment:' in k).endswith(':000'))
        jid = discovery_entry['job_id']
        frozen = read(self.workspace / f'groups/{jid}.json')
        self.assertEqual(set(frozen), {'discovery_result_sha256', 'groups'})
        self.assertEqual(frozen['groups'], [seen[0]])
        self.assertEqual(frozen['discovery_result_sha256'], discovery_entry['result_sha256'])

    def test_resume_after_invocation_limit_never_rediscovers(self):
        client = Client()
        first = self.execute(client, max_new_requests=1)
        self.assertEqual(first['stop_reason'], 'invocation_request_limit')
        second = self.execute(client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(second['tasks']), 2)

    def test_offline_and_zero_limit_do_not_read_keys_or_send(self):
        client = Client()
        self.assertEqual(self.execute(client, live=False)['stop_reason'], 'live_required')
        self.assertEqual(self.execute(client, max_new_requests=0)['stop_reason'], 'invocation_request_limit')
        self.assertEqual(client.calls, [])

    def test_empty_discovery_does_not_enrich(self):
        client = Client(empty=True)
        state = self.execute(client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(state['tasks']), 1)

    def test_multiple_groups_have_zero_based_names(self):
        state = self.execute(Client(candidates=9))
        keys = list(state['tasks'])
        self.assertTrue(keys[1].endswith(':enrichment:000'))
        self.assertTrue(keys[2].endswith(':enrichment:001'))
        self.assertEqual([e['accepted'] for e in self.entries(state)], [9, 8, 1])

    def test_unknown_and_http500_never_retry_even_changed_model_workspace(self):
        for error in (RequestFailure('network_outcome_unknown', ambiguous=True),
                      RequestFailure('http_error', 500)):
            with self.subTest(error=error.kind):
                # A new isolated source for each scenario.
                workspace = self.root / error.kind
                manifest = self.prepare(workspace, (error.kind,))
                source = self.root / (error.kind + '.xml')
                source.write_text(source.read_text().replace(
                    '<article>', '<article id="' + error.kind + '">'), encoding='utf-8')
                manifest = self.prepare(workspace, (error.kind,))
                client = Client(error)
                state = self.execute(client, workspace)
                self.assertEqual(self.entries(state)[0]['status'], 'needs_attention')
                self.execute(client, workspace)
                self.assertEqual(len(client.calls), 1)
                sibling = self.root / (error.kind + '_sibling')
                self.prepare(sibling, (error.kind,))
                self.cfg['model'] += '_different'
                blocked_client = Client()
                state = self.execute(blocked_client, sibling)
                self.assertEqual(self.entries(state)[0]['status'], 'blocked_unknown_scope')
                self.assertEqual(blocked_client.calls, [])
                self.assertTrue(manifest['job_ids'])

    def test_http429_is_not_automatically_retried(self):
        client = Client(RequestFailure('http_error', 429))
        self.assertEqual(self.entries(self.execute(client))[0]['status'], 'http_failure')
        self.execute(client)
        self.assertEqual(len(client.calls), 1)

    def test_auth_stop_survives_next_run_and_resume_flag(self):
        client = Client(RequestFailure('http_error', 401))
        self.execute(client)
        self.execute(client, resume_operator_pause=True)
        self.assertEqual(read(self.ledger)['global_stop'], 'provider_http_401')
        self.assertEqual(len(client.calls), 1)

    def test_operator_pause_requires_explicit_audited_resume(self):
        ledger = read(self.ledger)
        ledger['global_stop'] = 'operator_pause'
        save(self.ledger, ledger)
        client = Client()
        self.assertEqual(self.execute(client)['stop_reason'], 'operator_pause')
        self.assertEqual(client.calls, [])
        state = self.execute(client, resume_operator_pause=True)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(state['audit'][0]['event'], 'resume_operator_pause')
        self.assertEqual(read(self.ledger)['max_requests'], 100)
        self.assertEqual(read(self.ledger)['operator_events'][0]['action'], 'resume')

    def test_response_saved_before_validator_and_invalid_can_recover_offline(self):
        def broken_validator(payload, job, candidates):
            state = read(self.workspace / 'candidate_state.json')
            enriched = self.entries(state)[1]
            self.assertTrue((self.workspace / enriched['response_path']).is_file())
            raise ValueError('Synthetic schema mismatch')
        client = Client()
        state = runtime.run(self.workspace, self.cfg, self.ledger, candidate_request_for,
                            broken_validator, live=True, client=client)
        self.assertEqual(self.entries(state)[1]['status'], 'invalid_response')
        state = self.execute(client, live=False)
        self.assertEqual(self.entries(state)[1]['status'], 'complete')
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(read(self.ledger)['attempts']), 2)
        # Original terminal accounting is retained, never overwritten.
        self.assertEqual(read(self.ledger)['attempts'][1]['status'], 'invalid_response')

    def test_crash_after_response_write_recovers_without_network(self):
        original = runtime.save
        def crash(path, value):
            original(path, value)
            if Path(path).parent.name == 'responses':
                raise KeyboardInterrupt()
        client = Client(empty=True)
        with patch.object(runtime, 'save', side_effect=crash), self.assertRaises(KeyboardInterrupt):
            self.execute(client)
        state = read(self.workspace / 'candidate_state.json')
        self.assertEqual(state['stop_reason'], 'interrupted')
        self.assertEqual(self.entries(state)[0]['status'], 'needs_attention')
        state = self.execute(client, live=False)
        self.assertEqual(self.entries(state)[0]['status'], 'complete')
        self.assertEqual(len(client.calls), 1)

    def test_crash_before_response_marks_unknown_and_finishes_budget(self):
        client = Client(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.execute(client)
        state = read(self.workspace / 'candidate_state.json')
        self.assertEqual(state['stop_reason'], 'interrupted')
        self.assertEqual(read(self.ledger)['attempts'][0]['status'], 'needs_attention')
        self.execute(client)
        self.assertEqual(len(client.calls), 1)

    def test_finish_failure_persists_state_then_recovers_finish_offline(self):
        original = budget.finish
        def fail(*args, **kwargs):
            raise OSError('Synthetic ledger failure')
        client = Client(empty=True)
        with patch.object(budget, 'finish', side_effect=fail), self.assertRaises(OSError):
            self.execute(client)
        self.assertEqual(read(self.ledger)['attempts'][0]['status'], 'in_flight')
        self.assertEqual(self.entries(read(self.workspace / 'candidate_state.json'))[0]['status'], 'complete')
        self.execute(client, live=False)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(read(self.ledger)['attempts'][0]['status'], 'complete')
        self.assertTrue(callable(original))

    def test_success_cross_workspace_reuses_envelope_and_results(self):
        client = Client()
        first = self.execute(client)
        sibling = self.root / 'sibling'
        self.prepare(sibling)
        second = self.execute(client, sibling, live=False)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(second['attempts']), 0)
        self.assertEqual(len(read(self.ledger)['attempts']), 2)
        self.assertTrue(all(e.get('reused_from') for e in self.entries(second)))
        self.assertEqual([e['result_sha256'] for e in self.entries(first)],
                         [e['result_sha256'] for e in self.entries(second)])

    def test_cross_workspace_reuse_checks_origin_artifact_hashes(self):
        state = self.execute()
        entry = self.entries(state)[0]
        save(self.workspace / entry['response_path'], {'tampered': True})
        sibling = self.root / 'sibling'
        self.prepare(sibling)
        with self.assertRaises(runtime.IntegrityError):
            self.execute(workspace=sibling)

    def test_each_frozen_artifact_tamper_raises_without_sending(self):
        for kind in ('request', 'response', 'result', 'groups'):
            with self.subTest(kind=kind):
                workspace = self.root / kind
                self.prepare(workspace, (kind,))
                state = self.execute(workspace=workspace, max_new_requests=1)
                entry = self.entries(state)[0]
                if kind == 'groups':
                    target = workspace / state['groups'][entry['job_id']]['path']
                else:
                    target = workspace / entry[kind + '_path']
                before = target.read_bytes()
                target.write_text('{}', encoding='utf-8')
                client = Client()
                with self.assertRaises(runtime.IntegrityError):
                    self.execute(client, workspace)
                self.assertEqual(client.calls, [])
                target.write_bytes(before)

    def test_dependency_tamper_raises(self):
        state = self.execute()
        self.entries(state)[1]['discovery_result_sha256'] = 'changed'
        save(self.workspace / 'candidate_state.json', state)
        with self.assertRaises(runtime.IntegrityError):
            self.execute()

    def test_manifest_verifier_is_used_before_sends(self):
        manifest = read(self.workspace / 'manifest.json')
        prompt = self.workspace / 'discovery.md'
        prompt.write_text('Changed prompt', encoding='utf-8')
        client = Client()
        with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
            self.execute(client)
        self.assertEqual(client.calls, [])
        self.assertTrue(manifest['file_hashes'])

    def test_changed_config_rejects_resume(self):
        self.execute(max_new_requests=1)
        self.cfg['model'] = 'other-fixture'
        with self.assertRaises(runtime.IntegrityError):
            self.execute()

    def test_state_stores_config_and_initial_reference_hash(self):
        reference = self.workspace / 'acceptance_reference.json'
        save(reference, {'expert_gold': False, 'fixtures': []})
        state = self.execute(max_new_requests=0)
        self.assertEqual(state['config'], self.cfg)
        self.assertEqual(state['reference_sha256'], sha(reference))
        self.execute(max_new_requests=0)
        save(reference, {'fixtures': ['changed']})
        with self.assertRaisesRegex(runtime.IntegrityError, 'reference changed'):
            self.execute()

    def test_reference_cannot_be_added_after_first_run_or_removed(self):
        self.execute(max_new_requests=0)
        reference = self.workspace / 'acceptance_reference.json'
        save(reference, {'late': True})
        with self.assertRaises(runtime.IntegrityError):
            self.execute()
        other = self.root / 'reference_removed'
        self.prepare(other)
        save(other / 'acceptance_reference.json', {'first': True})
        self.execute(workspace=other, max_new_requests=0)
        (other / 'acceptance_reference.json').unlink()
        with self.assertRaises(runtime.IntegrityError):
            self.execute(workspace=other)

    def completed_legacy(self, provider=None, stage='discovery'):
        origin = self.root / 'legacy_complete'
        manifest = self.prepare(origin)
        jid = manifest['job_ids'][0]
        job = read(origin / f'jobs/{jid}.json')
        request = candidate_request_for(origin, job, 'discovery', self.cfg)
        envelope = Client().complete(request)
        result = discovery(json.loads(envelope['choices'][0]['message']['content']), job)
        attempt = budget.reserve(self.ledger, origin, jid + ':' + stage, request, 500,
                                 provider_identity=provider or self.cfg['base_url'])
        budget.finish(self.ledger, attempt['attempt_id'], 'complete', usage=envelope['usage'])
        entry = {'job_id': jid, 'stage': stage, 'status': 'complete',
                 'group': 0, 'attempt_id': attempt['attempt_id']}
        for kind, value in (('request', request), ('response', envelope), ('result', result)):
            name = f'{kind}s/old.json'
            save(origin / name, value)
            entry[kind + '_path'] = name
            entry[kind + '_sha256'] = sha(origin / name)
        save(origin / 'batch_state.json', {'tasks': {jid + ':' + stage: entry}})
        return origin, entry

    def test_exact_legacy_discovery_reused_and_revalidated_without_reservation(self):
        origin, old = self.completed_legacy()
        # The stored legacy result is checked, while the saved envelope is
        # revalidated against the new job rather than trusting the old result.
        save(origin / old['result_path'], {'accepted': [], 'rejected': []})
        old['result_sha256'] = sha(origin / old['result_path'])
        save(origin / 'batch_state.json', {'tasks': {old['job_id'] + ':discovery': old}})
        old_files = {p: p.read_bytes() for p in origin.rglob('*') if p.is_file()}
        ledger_before = self.ledger.read_bytes()
        client = Client()
        with patch.object(runtime, 'discovery', wraps=discovery) as revalidate:
            state = self.execute(client, max_new_requests=0)
        entry = self.entries(state)[0]
        self.assertEqual(entry['status'], 'complete')
        self.assertEqual(entry['accepted'], 1)
        self.assertEqual(entry['reused_from']['kind'], 'legacy_exact_discovery')
        self.assertEqual(entry['response_sha256'], old['response_sha256'])
        self.assertNotEqual(entry['result_sha256'], old['result_sha256'])
        self.assertEqual(state['attempts'], [])
        self.assertEqual(client.calls, [])
        self.assertEqual(revalidate.call_count, 1)
        self.assertEqual(self.ledger.read_bytes(), ledger_before)
        self.assertEqual({p: p.read_bytes() for p in old_files}, old_files)
        self.execute(client)
        self.assertEqual(len(client.calls), 1)  # Only new enrichment sends.

    def test_legacy_reuse_requires_same_provider(self):
        self.completed_legacy(provider='https://other.invalid/v1')
        client = Client()
        state = self.execute(client, max_new_requests=1)
        self.assertEqual(len(client.calls), 1)
        self.assertNotIn('reused_from', self.entries(state)[0])

    def test_legacy_reuse_requires_exact_request_content(self):
        self.completed_legacy()
        prompt = self.workspace / 'discovery.md'
        prompt.write_text('New prompt with changed instructions', encoding='utf-8')
        manifest = read(self.workspace / 'manifest.json')
        manifest['file_hashes']['discovery.md'] = sha(prompt)
        save(self.workspace / 'manifest.json', manifest)
        client = Client()
        state = self.execute(client, max_new_requests=1)
        self.assertEqual(len(client.calls), 1)
        self.assertNotIn('reused_from', self.entries(state)[0])

    def test_legacy_enrichment_never_reused_as_discovery(self):
        self.completed_legacy(stage='enrichment')
        client = Client()
        state = self.execute(client)
        self.assertEqual(client.calls, [])  # Exact paid hash remains blocked by old ledger.
        self.assertIn('Duplicate/unknown', state['stop_reason'])
        self.assertEqual(state['tasks'], {})

    def test_legacy_completed_files_must_pass_all_hash_checks(self):
        origin, old = self.completed_legacy()
        before = (origin / old['response_path']).read_bytes()
        (origin / old['response_path']).write_text('{}', encoding='utf-8')
        client = Client()
        with self.assertRaises(runtime.IntegrityError):
            self.execute(client)
        self.assertEqual(client.calls, [])
        (origin / old['response_path']).write_bytes(before)

    def test_source_scope_maps_same_xml_under_a_new_paper_label(self):
        self.legacy_unknown()
        sibling = self.root / 'renamed_paper'
        self.prepare(sibling, ('new_label',))
        # Same source bytes produce different corpus unit IDs, so the stable
        # source locator must link these scopes.
        client = Client()
        state = self.execute(client, sibling)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.entries(state)[0]['status'], 'blocked_unknown_scope')

    def legacy_unknown(self, mapped=True, http500=False):
        workspace = self.root / 'legacy'
        if mapped:
            manifest = self.prepare(workspace)
            jid = manifest['job_ids'][0]
            job = read(workspace / f'jobs/{jid}.json')
        else:
            workspace.mkdir()
            jid, job = 'missing_job', None
        request = {'model': 'legacy-fixture', 'messages': [{'role': 'user', 'content': 'legacy'}]}
        attempt = budget.reserve(self.ledger, workspace, jid + ':discovery', request, 500)
        budget.finish(self.ledger, attempt['attempt_id'], 'http_failure' if http500 else 'needs_attention',
                      http_status=500 if http500 else None)
        save(workspace / 'batch_state.json', {'tasks': {jid + ':discovery': {
            'job_id': jid, 'stage': 'discovery', 'status': 'needs_attention',
            'attempt_id': attempt['attempt_id']}}})
        return attempt, job

    def test_legacy_unknown_scope_blocks_current_source_across_versions(self):
        self.legacy_unknown()
        client = Client()
        state = self.execute(client)
        self.assertEqual(self.entries(state)[0]['status'], 'blocked_unknown_scope')
        self.assertEqual(client.calls, [])

    def test_legacy_http500_is_unknown_despite_old_http_failure_label(self):
        self.legacy_unknown(http500=True)
        client = Client()
        self.assertEqual(self.entries(self.execute(client))[0]['status'], 'blocked_unknown_scope')
        self.assertEqual(client.calls, [])

    def test_legacy_unknown_does_not_block_unrelated_known_source(self):
        self.legacy_unknown()
        other = self.root / 'other'
        self.prepare(other, ('P2',))
        # Use different source bytes; source hash, not paper label, defines scope.
        source = self.root / 'P2.xml'
        source.write_text(source.read_text().replace('<article>', '<article id="different">'), encoding='utf-8')
        self.prepare(other, ('P2',))
        client = Client()
        self.execute(client, other)
        self.assertEqual(len(client.calls), 2)

    def test_unmapped_legacy_unknown_blocks_full_but_known_pilot_can_continue(self):
        attempt, _ = self.legacy_unknown(mapped=False)
        client = Client()
        state = self.execute(client, phase='full')
        self.assertEqual(state['stop_reason'], 'blocked_unknown_mapping')
        self.assertEqual(state['blocked_unknown_mapping'][0]['attempt_id'], attempt['attempt_id'])
        self.assertEqual(client.calls, [])
        state = self.execute(client, phase='pilot')
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(state['blocked_unknown_mapping'])

    def test_overlap_blocks_rechunking_but_not_nonoverlapping_char_ranges(self):
        scope = {'source_sha256': 'same', 'units': [{'unit_id': 'p1', 'start': 10, 'end': 20}]}
        self.assertTrue(runtime._overlaps(scope, {'source_sha256': 'same', 'units': [
            {'unit_id': 'p1', 'start': 0, 'end': None}]}))
        self.assertFalse(runtime._overlaps(scope, {'source_sha256': 'same', 'units': [
            {'unit_id': 'p1', 'start': 20, 'end': 30}]}))

    def test_global_and_workspace_locks_reject_active_run(self):
        client = Client()
        with runtime.RunLock(str(self.ledger) + '.candidate_run.lock'):
            with self.assertRaises(RuntimeError):
                self.execute(client)
        with runtime.RunLock(self.workspace / '.candidate_run.lock'):
            with self.assertRaises(RuntimeError):
                self.execute(client)
        self.assertEqual(client.calls, [])

    def test_live_pid_metadata_not_removed_and_dead_owner_recovery_audited(self):
        path = self.workspace / 'test.lock'
        owner = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
        save(path, owner)
        with self.assertRaises(RuntimeError):
            with runtime.RunLock(path):
                pass
        self.assertEqual(read(path), owner)
        # Same PID with a different creation time models a recycled PID.
        save(path, dict(owner, create_time=owner['create_time'] - 100))
        with runtime.RunLock(path):
            self.assertEqual(read(path)['pid'], os.getpid())
        self.assertFalse(path.exists())
        audit = Path(str(path) + '.audit.jsonl').read_text(encoding='utf-8')
        self.assertIn('recovered_dead_process_lock', audit)

    def test_unverifiable_lock_is_preserved(self):
        path = self.workspace / 'bad.lock'
        save(path, {'pid': os.getpid()})
        with self.assertRaises(runtime.IntegrityError):
            with runtime.RunLock(path):
                pass
        self.assertTrue(path.exists())

    def test_progress_called_each_paper_and_finally(self):
        self.prepare(paper_ids=('P1', 'P2'))
        calls = []
        self.execute(on_progress=lambda workspace: calls.append(workspace))
        self.assertEqual(calls, [self.workspace] * 3)

    def test_callback_and_integrity_errors_propagate_with_final_state(self):
        calls = []
        def callback(workspace):
            calls.append(workspace)
            raise RuntimeError('Synthetic export failure')
        with self.assertRaisesRegex(RuntimeError, 'Synthetic export failure'):
            self.execute(on_progress=callback)
        self.assertEqual(len(calls), 2)
        self.assertEqual(read(self.workspace / 'candidate_state.json')['stop_reason'], 'runtime_error')

    def test_shared_caps_not_reset_and_no_orphan_send(self):
        ledger = read(self.ledger)
        ledger['max_requests'] = 1
        save(self.ledger, ledger)
        client = Client()
        state = self.execute(client)
        self.assertEqual(len(client.calls), 1)
        self.assertIn('exhausted', state['stop_reason'])
        self.execute(client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(read(self.ledger)['max_requests'], 1)


if __name__ == '__main__':
    unittest.main()
