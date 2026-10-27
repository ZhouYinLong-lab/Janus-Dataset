"""Synthetic offline workspace/CLI/runtime/export integration; no real provider calls."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import batch_budget
import batch_candidate
import candidate_export
import candidate_runtime
import candidate_workspace
from api import RequestFailure
from corpus import HERE, read, save, sha
import facts_v3
import sentence_export
import sentence_v3
import sentence_workflow
import sentence_workspace


TEXT = ('Synthetic analogues A and B did not improve target Z degradation in synthetic cells; '
        'their activity was reduced relative to synthetic reference R.')
METHOD = ('The activity assay for synthetic analogues A and B measured target Z binding '
          'after 6 h using synthetic cells.')


class LocalResponses:
    """In-memory responses only. The runtime is never given a network client."""
    def __init__(self, condition_failure=False, abstain=False, semantic_conflict=False,
                 missing_endpoint=True, condition_http_failure=False, duplicate=False):
        self.stages = []
        self.condition_failure = condition_failure
        self.abstain = abstain
        self.semantic_conflict = semantic_conflict
        self.missing_endpoint = missing_endpoint
        self.condition_http_failure = condition_http_failure
        self.duplicate = duplicate

    def complete(self, request):
        user = json.loads(request['messages'][1]['content'])
        if 'paragraphs' in user:
            self.stages.append('discovery')
            by_id = {s['sentence_id']: s for s in user['sentences']}
            rows = []
            for p in user['paragraphs']:
                anchors = [sid for sid in p['sentence_ids'] if 'did not improve' in by_id[sid]['text']]
                rows.append({'paragraph_id': p['paragraph_id'],
                             'status': 'has_candidates' if anchors else 'none_found',
                             'spans': [{'sentence_ids': anchors}] if anchors else []})
            payload = {'paragraphs': rows}
        elif 'records' in user:
            self.stages.append('conditions')
            if self.condition_http_failure:
                raise RequestFailure('synthetic_http_error', http_status=429)
            if self.condition_failure:
                payload = {'items': [{'record_id': r['record_id'], 'values': {}, 'evidence': {}}
                                     for r in user['records']]}
            else:
                sid = next(s['sentence_id'] for s in user['sentences'] if '6 h' in s['text'])
                payload = {'items': []}
                for record in user['records']:
                    values = dict.fromkeys(sentence_workflow.CONDITION_FIELDS)
                    values['treatment_time'] = '6 h'
                    values['endpoint_resolution'] = 'target Z binding response'
                    evidence = {f: ([sid] if f in {'treatment_time', 'endpoint_resolution'} else [])
                                for f in sentence_workflow.CONDITION_FIELDS}
                    payload['items'].append({'record_id': record['record_id'],
                                             'values': values, 'evidence': evidence})
        else:
            self.stages.append('facts')
            if self.abstain:
                payload = {'status': 'uncertain', 'reason': 'Missing supplemental Figure S2.',
                           'observations': []}
            else:
                sid = user['anchor_sentence_ids'][0]
                values = {'subject': 'Synthetic analogues A and B', 'target': 'target Z',
                          'endpoint': 'target Z degradation',
                          'observation': 'did not improve degradation relative to synthetic reference R',
                          'comparator': 'synthetic reference R', 'scope_condition': 'in synthetic cells'}
                row = {'values': values, 'outcome_type': 'not_improved',
                       'evidence': {f: [sid] for f in facts_v3.FIELDS}}
                other = deepcopy(row)
                other['values'].update(endpoint=None if self.missing_endpoint else 'target Z binding response',
                                       observation='activity reduced relative to synthetic reference R',
                                       scope_condition=None)
                other['evidence']['scope_condition'] = []
                other['evidence']['endpoint'] = [] if self.missing_endpoint else [sid]
                other['outcome_type'] = 'reduced'
                if self.semantic_conflict:
                    row['outcome_type'] = 'not_observed'
                if self.duplicate:
                    other = deepcopy(row)
                payload = {'status': 'observations', 'reason': None, 'observations': [row, other]}
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(payload)}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                'model': 'synthetic-local-test'}


class SentenceIntegrationV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='janus-sentence-integration-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.xml'
        self.source.write_text('<article><body><sec><title>Results</title><p>' + TEXT +
                               '</p><p>Synthetic control measurements were reported.</p></sec>'
                               '<sec><title>Methods</title><p>' + METHOD +
                               '</p></sec></body></article>', encoding='utf-8')
        self.inventory = self.root / 'papers.json'
        save(self.inventory, [{'paper_id': 'SYNTHETIC', 'doi': '10.synthetic/format-only',
                               'path': str(self.source), 'private_reference': 'NEVER_MODEL_INPUT'}])
        self.workspace = self.root / 'work'
        self.config = {'base_url': 'http://localhost', 'model': 'synthetic-local-test',
                       'api_key_env': 'UNUSED_SYNTHETIC_KEY', 'timeout_seconds': 1,
                       'max_output_tokens': 8192, 'output_token_parameter': 'max_tokens',
                       'response_format': 'json_object', 'max_requests': 10,
                       'max_reserved_tokens': 1_000_000}
        self.ledger = self.root / 'synthetic-budget.json'
        batch_budget.create(self.ledger, 10, 1_000_000, 'Isolated synthetic fixture only; no API')

    def prepare(self, workspace=None, **kwargs):
        return candidate_workspace.prepare(workspace or self.workspace, manifest_path=self.inventory,
                                           protocol='sentence_v3', **kwargs)

    def run_local(self, provider, **kwargs):
        with patch('credentials.load_key', side_effect=AssertionError('No key access permitted')):
            with redirect_stdout(io.StringIO()):
                return candidate_runtime.run(self.workspace, self.config, self.ledger,
                    sentence_workflow.request_for, sentence_workflow.validate_response,
                    live=True, client=provider, phase='pilot', on_progress=sentence_export.export, **kwargs)

    def cli(self, *args):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['batch_candidate.py', *map(str, args)]), redirect_stdout(output):
            batch_candidate.main()
        return json.loads(output.getvalue())

    def test_prepare_freezes_dependencies_prompts_schema_examples_and_full_index(self):
        m = self.prepare()
        self.assertEqual(m['pipeline'], 'molgluedb_sentence_v3')
        self.assertEqual((m['primary_cap'], m['max_paragraphs']), (4000, 3))
        self.assertTrue({'sentence_v3.py', 'facts_v3.py', 'sentence_workflow.py',
                         'candidate_runtime.py', 'candidate_transport.py', 'stream_http.py',
                         'sentence_export.py', 'sentence_workspace.py', 'sentence_acceptance.py'} <= m['code_hashes'].keys())
        for name, digest in m['code_hashes'].items():
            self.assertEqual(sha(self.workspace / 'runtime' / name), digest)
        for name in (*sentence_workspace.PROMPTS, 'sentence_protocol.json', 'discovery_schema.json',
                     'discovery_example.json', 'facts_schema.json', 'facts_example.json',
                     'conditions_schema.json', 'conditions_example.json'):
            self.assertEqual(sha(self.workspace / name), m['file_hashes'][name])
        self.assertEqual(read(self.workspace / 'discovery_schema.json'), sentence_v3.DISCOVERY_SCHEMA)
        self.assertEqual(read(self.workspace / 'discovery_example.json'), sentence_v3.DISCOVERY_EXAMPLE)
        self.assertEqual(read(self.workspace / 'facts_schema.json'), facts_v3.SCHEMA)
        self.assertEqual(read(self.workspace / 'facts_example.json'), facts_v3.EXAMPLE)
        self.assertEqual(read(self.workspace / 'conditions_schema.json'), sentence_workflow.CONDITION_SCHEMA)
        self.assertEqual(read(self.workspace / 'conditions_example.json'), sentence_workflow.CONDITION_EXAMPLE)
        for jid in m['job_ids']:
            self.assertNotIn(':', jid)
            job = read(self.workspace / f'jobs/{jid}.json')
            self.assertEqual(sha(job['sentence_index_path']), job['sentence_index_sha256'])
            self.assertEqual(sha(job['document_path']), job['document_sha256'])
            self.assertEqual(read(job['sentence_index_path']), sentence_v3.index_document(read(job['document_path'])))
            self.assertLessEqual(sum(len(p['text']) for p in job['primary_units']), 4000)
            self.assertLessEqual(len(job['paragraphs']), 3)
        self.assertNotIn('NEVER_MODEL_INPUT', (self.workspace / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(candidate_workspace.verify(self.workspace), m)

    def test_default_protocol_stays_v2_and_existing_workspace_is_not_overwritten(self):
        m = candidate_workspace.prepare(self.workspace, manifest_path=self.inventory)
        self.assertEqual(m['pipeline'], 'molgluedb_candidates_v2')
        before = sha(self.workspace / 'manifest.json')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(sha(self.workspace / 'manifest.json'), before)
        self.assertEqual(candidate_workspace.verify(self.workspace), m)
        self.assertEqual(candidate_export.snapshot(self.workspace)[0]['pipeline'], m['pipeline'])

    def test_verify_rejects_changed_full_index_prompt_runtime_and_original_source(self):
        m = self.prepare()
        targets = [self.workspace / 'facts_v3.md', self.workspace / 'runtime/sentence_workflow.py',
                   Path(m['papers'][0]['sentence_index_path']), self.source]
        for target in targets:
            with self.subTest(path=target):
                original = target.read_bytes()
                target.write_bytes(original + b' ')
                try:
                    with self.assertRaises(ValueError):
                        candidate_workspace.verify(self.workspace)
                finally:
                    target.write_bytes(original)

    def test_fixed_pilot_uses_five_ids_and_dois_and_freezes_optional_reference(self):
        papers = [{'paper_id': pid, 'doi': doi, 'path': str(self.source)}
                  for pid, doi in zip(sentence_workspace.PILOT_PAPERS, sentence_workspace.PILOT_DOIS)]
        save(self.inventory, papers)
        reference = {'expert_gold': False, 'private_marker': 'PRIVATE_REFERENCE_ONLY'}
        save(self.root / 'acceptance_reference.json', reference)
        m = self.prepare(phase='pilot')
        self.assertEqual([p['paper_id'] for p in m['papers']], list(sentence_workspace.PILOT_PAPERS))
        self.assertEqual(m['reference_sha256'], sha(self.workspace / 'acceptance_reference.json'))
        self.assertEqual(m['file_hashes']['acceptance_reference.json'], m['reference_sha256'])
        for jid in m['job_ids']:
            job = read(self.workspace / f'jobs/{jid}.json')
            request = sentence_workflow.request_for(self.workspace, job, 'discovery', self.config)
            self.assertNotIn('PRIVATE_REFERENCE_ONLY', json.dumps(request))
            self.assertNotIn('NEVER_MODEL_INPUT', json.dumps(request))
        with self.assertRaises(ValueError):
            self.prepare(self.root / 'incomplete-pilot', phase='pilot', limit=4)

    def test_pilot_fixture_can_omit_reference_and_full_requires_manifest(self):
        save(self.inventory, [{'paper_id': pid, 'doi': doi, 'path': str(self.source)}
                              for pid, doi in zip(sentence_workspace.PILOT_PAPERS, sentence_workspace.PILOT_DOIS)])
        m = self.prepare(phase='pilot')
        self.assertNotIn('acceptance_reference.json', m['file_hashes'])
        with self.assertRaises(ValueError):
            sentence_workspace.prepare(self.root / 'missing-inventory')

    def test_check_is_key_free_and_does_not_change_fixture_ledger(self):
        m = self.prepare()
        before = self.ledger.read_bytes()
        with patch('credentials.load_key', side_effect=AssertionError('No keys')):
            report = candidate_workspace.check(self.workspace, self.config, self.ledger)
        self.assertEqual(report['pipeline'], m['pipeline'])
        self.assertEqual(report['discovery_requests'], len(m['job_ids']))
        self.assertEqual(report['generation_requests_sent'], 0)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_runtime_to_export_keeps_two_observations_and_optional_conditions(self):
        self.prepare()
        provider = LocalResponses()
        state = self.run_local(provider)
        self.assertEqual(provider.stages, ['discovery', 'facts', 'conditions'])
        self.assertFalse(state.get('stop_reason'))
        summary, records, audits, failures = sentence_export.snapshot(self.workspace)
        self.assertEqual(len(records), 2)
        self.assertEqual(len({r['record_key'] for r in records}), 2)
        self.assertFalse(failures)
        self.assertTrue(summary['all_sources_processed'])
        for record in records:
            self.assertEqual(record['values']['subject'], 'Synthetic analogues A and B')
            if record['outcome_type'] == 'reduced':
                self.assertEqual(record['conditions']['treatment_time'], '6 h')
                self.assertIn('core_original', record)
                self.assertEqual([s['stage'] for s in record['sources']], ['facts', 'conditions'])
            else:
                self.assertEqual([s['stage'] for s in record['sources']], ['facts'])
            self.assertFalse(record['expert_gold'])
            self.assertFalse(record['ready_for_training'])
        self.assertTrue(any(a['destination'] == 'paragraph_coverage' for a in audits))
        before_calls = len(provider.stages)
        self.run_local(provider)
        self.assertEqual(len(provider.stages), before_calls)
        exported = batch_candidate.export_context_audit(self.workspace)
        self.assertEqual(exported['records'], 2)
        self.assertEqual(read(self.workspace / 'exports/records.json'), records)
        with (self.workspace / 'exports/records.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['subject'], 'Synthetic analogues A and B')
        self.assertEqual(rows[1]['condition_treatment_time'], '6 h')
        markdown = (self.workspace / 'exports/summary.md').read_text(encoding='utf-8')
        for phrase in ('覆盖状态', '候选去向', '记录状态', '共享预算', '停止原因', '待复核', '未放行'):
            self.assertIn(phrase, markdown)

    def test_invalid_optional_conditions_do_not_remove_core_facts(self):
        self.prepare()
        self.run_local(LocalResponses(condition_failure=True))
        summary, records, audits, _ = sentence_export.snapshot(self.workspace)
        self.assertEqual(len(records), 2)
        self.assertEqual([r['record_status'] for r in records], ['core_usable', 'semantic_pending'])
        self.assertTrue(all([s['stage'] for s in r['sources']] == ['facts'] for r in records))
        self.assertTrue(any(a['stage'] == 'conditions' and a['destination'] == 'quarantine' for a in audits))
        self.assertEqual(summary['paper_status'], {'processed_with_issues': 1})
        self.assertFalse(summary['all_sources_processed'])

    def test_uncertain_and_invalid_abstention_stay_in_candidate_audit(self):
        self.prepare()
        self.run_local(LocalResponses(abstain=True))
        _, records, audits, _ = sentence_export.snapshot(self.workspace)
        self.assertFalse(records)
        unresolved = [a for a in audits if a['stage'] == 'facts' and a['destination'] == 'unresolved']
        self.assertEqual(unresolved[0]['reason'], 'Missing supplemental Figure S2.')
        self.assertIn('invalid_abstention_reason', unresolved[0]['errors'])
        self.assertTrue(any(a['destination'] == 'candidate_status' and a['record_count'] == 0 for a in audits))

    def test_semantic_quarantine_and_flags_survive_json_csv_and_conditions(self):
        self.prepare()
        self.run_local(LocalResponses(semantic_conflict=True))
        summary, records, audits, _ = sentence_export.snapshot(self.workspace)
        quarantined = next(r for r in records if r['outcome_type'] == 'not_observed')
        self.assertEqual(quarantined['record_status'], 'quarantine')
        self.assertIn('not_improved_must_not_become_inactive', quarantined['semantic_flags'])
        self.assertTrue(quarantined['sources'])
        self.assertFalse(summary['all_sources_processed'])
        self.assertEqual(read(self.workspace / 'exports/records.json'), records)
        with (self.workspace / 'exports/records.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['record_status'], 'quarantine')
        self.assertEqual(json.loads(rows[0]['semantic_flags']), quarantined['semantic_flags'])
        self.assertTrue(all('stage' in a for a in audits))

    def test_missing_support_is_context_gap_and_never_not_needed(self):
        self.source.write_text('<article><body><sec><title>Results</title><p>' + TEXT +
                               '</p></sec></body></article>', encoding='utf-8')
        self.prepare()
        provider = LocalResponses()
        self.run_local(provider)
        summary, records, audits, _ = sentence_export.snapshot(self.workspace)
        self.assertEqual(provider.stages, ['discovery', 'facts'])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]['record_status'], 'semantic_pending')
        status = next(a for a in audits if a['destination'] == 'candidate_status')
        self.assertEqual(status['conditions_status'], 'context_gap')
        self.assertEqual(status['conditions_reason'], 'required_context_unavailable_or_already_supplied')
        self.assertTrue(any(a['destination'] == 'optional_conditions_gap' for a in audits))
        self.assertFalse(summary['all_sources_processed'])

    def test_genuine_not_needed_has_reason_and_does_not_issue_supplement(self):
        explicit = TEXT.replace('their activity', 'their target Z binding response')
        self.source.write_text('<article><body><p>' + explicit + '</p></body></article>', encoding='utf-8')
        self.prepare()
        provider = LocalResponses(missing_endpoint=False)
        self.run_local(provider)
        summary, _, audits, _ = sentence_export.snapshot(self.workspace)
        self.assertEqual(provider.stages, ['discovery', 'facts'])
        status = next(a for a in audits if a['destination'] == 'candidate_status')
        self.assertEqual(status['conditions_status'], 'not_needed')
        self.assertEqual(status['conditions_reason'], 'not_needed')
        self.assertTrue(summary['all_sources_processed'])

    def test_optional_http_failure_preserves_core_and_is_not_retried(self):
        self.prepare()
        provider = LocalResponses(condition_http_failure=True)
        self.run_local(provider)
        summary, records, audits, failures = sentence_export.snapshot(self.workspace)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['record_status'], 'core_usable')
        self.assertEqual(records[1]['record_status'], 'semantic_pending')
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['stage'], 'conditions')
        self.assertTrue(any(a['destination'] == 'optional_conditions_gap' for a in audits))
        self.assertFalse(summary['all_sources_processed'])
        self.run_local(provider)
        self.assertEqual(provider.stages.count('conditions'), 1)

    def test_even_same_key_observations_remain_separate_rows(self):
        self.prepare()
        self.run_local(LocalResponses(duplicate=True))
        summary, records, _, _ = sentence_export.snapshot(self.workspace)
        self.assertEqual(summary['records'], 2)
        self.assertEqual(summary['unique_records'], 1)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['record_key'], records[1]['record_key'])
        self.assertNotEqual(records[0]['sources'][0]['record_index'], records[1]['sources'][0]['record_index'])
        self.assertEqual(len(read(self.workspace / 'exports/records.json')), 2)

    def test_changed_authoritative_result_stops_export(self):
        self.prepare()
        state = self.run_local(LocalResponses())
        facts = next(e for e in state['tasks'].values() if e['stage'] == 'facts')
        path = self.workspace / facts['result_path']
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            sentence_export.snapshot(self.workspace)

    def test_unscanned_sentence_and_missing_source_are_visible_without_runtime(self):
        long_source = self.root / 'long.xml'
        long_source.write_text('<article><body><p>' + 'x' * 4001 + '</p></body></article>', encoding='utf-8')
        save(self.inventory, [{'paper_id': 'LONG', 'path': str(long_source)},
                              {'paper_id': 'MISSING', 'path': str(self.root / 'missing.xml')}])
        self.prepare()
        summary, records, audits, _ = sentence_export.snapshot(self.workspace)
        self.assertFalse(records)
        self.assertFalse(summary['all_sources_processed'])
        self.assertEqual(summary['unscanned_sentences'], 1)
        self.assertTrue(any(a['destination'] == 'unscanned' for a in audits))
        self.assertTrue(any(a['destination'] == 'input_gap' and a['paper_id'] == 'MISSING' for a in audits))

    def test_pending_discovery_has_explicit_paragraph_coverage_and_snapshot_is_read_only(self):
        m = self.prepare()
        before = {p: (sha(p), p.stat().st_mtime_ns) for p in self.workspace.rglob('*') if p.is_file()}
        summary, _, audits, _ = sentence_export.snapshot(self.workspace)
        after = {p: (sha(p), p.stat().st_mtime_ns) for p in self.workspace.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        paragraphs = sum(len(read(self.workspace / f'jobs/{jid}.json')['paragraphs']) for jid in m['job_ids'])
        self.assertEqual(summary['unresolved_paragraphs'], paragraphs)
        self.assertEqual(len([a for a in audits if a['destination'] == 'paragraph_coverage']), paragraphs)

    def test_cli_prepare_check_status_export_and_run_dispatch(self):
        prepared = self.cli('prepare', '--workspace', self.workspace, '--manifest', self.inventory,
                            '--protocol', 'sentence_v3')
        self.assertEqual(prepared['candidate_context_version'], 3)
        config = self.root / 'config.json'
        save(config, self.config)
        checked = self.cli('check', '--workspace', self.workspace, '--config', config, '--ledger', self.ledger)
        self.assertEqual(checked['pipeline'], sentence_workspace.PIPELINE)
        self.assertEqual(self.cli('status', '--workspace', self.workspace)['pipeline'], sentence_workspace.PIPELINE)
        self.assertEqual(self.cli('export', '--workspace', self.workspace)['pipeline'], sentence_workspace.PIPELINE)
        with patch('candidate_runtime.run') as run:
            self.cli('run', '--workspace', self.workspace, '--config', config, '--ledger', self.ledger,
                     '--phase', 'pilot', '--max-new-requests', 0)
        self.assertIs(run.call_args.args[3], sentence_workflow.request_for)
        self.assertIs(run.call_args.args[4], sentence_workflow.validate_response)
        self.assertFalse(run.call_args.kwargs['live'])

    def test_cli_acceptance_and_full_run_use_sentence_gate(self):
        self.prepare()
        review, out, config = self.root / 'review.json', self.root / 'assessment.json', self.root / 'config.json'
        save(review, {})
        save(config, self.config)
        with patch('sentence_acceptance.assess', return_value={'passed': False}) as assess:
            self.assertFalse(self.cli('acceptance', '--workspace', self.workspace, '--review', review,
                                      '--out', out)['passed'])
        assess.assert_called_once_with(self.workspace, review, out)
        with patch('sentence_acceptance.require_acceptance', side_effect=ValueError('blocked')) as gate:
            with patch('candidate_runtime.run') as run:
                with self.assertRaisesRegex(ValueError, 'blocked'):
                    self.cli('run', '--workspace', self.workspace, '--config', config,
                             '--ledger', self.ledger, '--acceptance', out)
                run.assert_not_called()
        gate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
