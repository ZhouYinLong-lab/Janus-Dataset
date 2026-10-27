"""Offline synthetic acceptance examples; no generation, keys or real success claims.

Run: python -B -m unittest test_sentence_acceptance_v3 -v
The fixture demonstrates the complete review schema, including explicit severity
on EVERY record and actual record_keys on EACH recovered core reference.
"""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import sentence_acceptance as gate
from sentence_v3 import index_document

SOURCE_ROOT = Path(__file__).resolve().parent


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sentence-acceptance-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = self.root / 'code'
        self.code.mkdir()
        for name in gate.REQUIRED_RUNTIME:
            original = SOURCE_ROOT / name
            if original.is_file():
                shutil.copyfile(original, self.code / name)
            else:
                (self.code / name).write_text('# Synthetic offline fixture\n', encoding='utf-8')
        self.addCleanup(patch.stopall)
        patch.object(gate, 'HERE', self.code).start()
        self.workspace = self.root / 'pilot'
        self.workspace.mkdir()
        runtime = self.workspace / 'runtime'
        shutil.copytree(self.code, runtime)
        self.config = {'model': 'synthetic-offline', 'max_requests': 200, 'max_reserved_tokens': 8000000}
        self.manifest = {'pipeline': gate.PIPELINE, 'protocol': 'sentence_v3', 'phase': 'pilot',
                         'version': 3, 'papers': [], 'file_hashes': {},
                         'code_hashes': {p.name: gate._hash(p) for p in self.code.glob('*.py')}}
        for name in gate.PROMPTS:
            path = self.workspace / name
            path.write_text('Synthetic prompt ' + name, encoding='utf-8')
            self.manifest['file_hashes'][name] = gate._hash(path)
        self.reference = {'expert_gold': False, 'reviewer_kind': 'assistant',
                          'full_body_reference_complete': True, 'papers': []}
        self.documents, records, public = {}, [], []
        for paper_number, (pid, doi) in enumerate(gate.PILOT_PAPERS.items()):
            units = [{'unit_id': pid + ':p' + str(i), 'kind': 'body_paragraph',
                      'locator': 'body/p[' + str(i) + ']', 'section': 'Results',
                      'text': 'Synthetic agent %d_%d did not reduce target Z protein.' % (paper_number, i)}
                     for i in range(4)]
            source = self.root / (pid + '.xml')
            source.write_text('<article><body>' + ''.join('<p>' + u['text'] + '</p>' for u in units)
                              + '</body></article>', encoding='utf-8')
            digest = gate._hash(source)
            doc = {'paper_id': pid, 'source_sha256': digest, 'source_path': str(source), 'units': units}
            self.documents[pid] = doc
            doc_name = 'documents/' + pid + '.json'
            save(self.workspace / doc_name, doc)
            self.manifest['file_hashes'][doc_name] = gate._hash(self.workspace / doc_name)
            self.manifest['papers'].append({'paper_id': pid, 'doi': doi, 'source_sha256': digest,
                                            'source_path': str(source)})
            ref = {'paper_id': pid, 'source_sha256': digest, 'units_reviewed': [], 'negatives': []}
            for i, (unit, sentence) in enumerate(zip(units, index_document(doc))):
                values = {'subject': 'Synthetic agent %d_%d' % (paper_number, i), 'target': 'Z',
                          'endpoint': 'Z protein decrease', 'observation': 'did not reduce target Z protein',
                          'comparator': None, 'scope_condition': None}
                record = {'paper_id': pid, 'doi': doi, 'source_sha256': digest,
                          'candidate_id': 'C:' + pid + ':' + str(i), 'values': values,
                          'outcome_type': 'not_observed', 'anchor_sentence_ids': [sentence['sentence_id']],
                          'original_quote': sentence['text'], 'record_status': 'core_usable',
                          'field_evidence': [dict(field=f, sentence_id=sentence['sentence_id'],
                              unit_id=unit['unit_id'], quote=sentence['text'],
                              char_start=sentence['char_start'], char_end=sentence['char_end'])
                              for f in gate.FIELDS if values[f] is not None]}
                record['record_key'] = gate._fingerprint({k: record[k] for k in
                    ('source_sha256', 'paper_id', 'candidate_id', 'values', 'outcome_type')})
                records.append(record)
                ref['units_reviewed'].append({'unit_id': unit['unit_id'], 'decision': 'has_negative',
                                               'reason': 'Synthetic completed experiment, no reduction.'})
                ref['negatives'].append(dict(id=pid + '-N' + str(i), unit_id=unit['unit_id'],
                                              quote=unit['text'], core_case=True, **values))
            self.reference['papers'].append(ref)
            public.append({'paper_id': pid, 'doi': doi, 'source_sha256': digest,
                           'document_sha256': gate._hash(self.workspace / doc_name),
                           'body_units_reviewed': 4, 'negative_reference_count': 4,
                           'core_reference_count': 4,
                           'references': [{k: n[k] for k in ('id', 'unit_id', 'core_case')} for n in ref['negatives']]})
        self.index = {'protocol': 'sentence_v3', 'reviewer_kind': 'assistant', 'expert_gold': False,
                      'papers': public, 'core_reference_count': 20, 'body_units_reviewed': 20}
        self.write_reference()
        self.write_manifest()
        self.state = {'pipeline': gate.PIPELINE, 'reference_sha256': gate._hash(self.workspace / 'acceptance_reference.json'),
                      'config': self.config, 'tasks': {}, 'attempts': []}
        save(self.workspace / 'candidate_state.json', self.state)
        summary = {'pipeline': gate.PIPELINE, 'protocol': 'sentence_v3', 'all_sources_processed': True,
                   'unscanned_sentences': 0, 'unresolved_paragraphs': 0,
                   'records': 20, 'unique_records': 20,
                   'papers': [{'paper_id': pid, 'doi': doi, 'source_sha256': self.documents[pid]['source_sha256'],
                               'jobs': 1, 'jobs_processed': 1, 'unscanned_sentences': 0,
                               'status': 'processed_pending_review'} for pid, doi in gate.PILOT_PAPERS.items()]}
        self.snapshot = (summary, records, [], [])
        patch.object(gate, '_snapshot', side_effect=lambda _: deepcopy(self.snapshot)).start()
        self.review = {
            'schema_version': 3, 'pipeline': gate.PIPELINE, 'expert_gold': False, 'reviewer_kind': 'assistant',
            'binding': gate.binding(self.workspace, self.config),
            'reference_sha256': self.state['reference_sha256'],
            'output_fingerprint': gate.output_fingerprint(*self.snapshot),
            'records': [{'record_key': r['record_key'], 'decision': 'supported',
                         'reason': 'Checked subject, endpoint, observation and scope against exact source.',
                         'severe_error': False} for r in records],
            'references': [{'reference_id': n['id'], 'decision': 'recovered',
                            'reason': 'The linked record preserves the complete synthetic claim.',
                            'record_keys': [r['record_key']]}
                           for n, r in zip([n for p in self.reference['papers'] for n in p['negatives']], records)],
            'known_regressions_pass': True, 'engineering_checks_pass': True,
            'critical_errors_unresolved': 0,
        }
        self.review_path = self.root / 'review.json'
        self.report_path = self.root / 'acceptance.json'

    def write_manifest(self):
        save(self.workspace / 'manifest.json', self.manifest)

    def write_reference(self):
        save(self.workspace / 'acceptance_reference.json', self.reference)
        self.index['reference_sha256'] = gate._hash(self.workspace / 'acceptance_reference.json')
        save(self.code / 'sentence_v3_reference_index.json', self.index)

    def assess(self, refresh_output=False):
        if refresh_output:
            self.review['output_fingerprint'] = gate.output_fingerprint(*self.snapshot)
        save(self.review_path, self.review)
        return gate.assess(self.workspace, self.review_path, self.report_path)

    def blocked(self, result, fragment):
        self.assertFalse(result['passed'])
        self.assertTrue(any(fragment in x for x in result['blockers']), result['blockers'])

    def test_complete_synthetic_example_passes_and_require_is_read_only(self):
        report = self.assess()
        self.assertTrue(report['passed'], report['blockers'])
        self.assertEqual(report['metrics'], {'records': 20, 'supported': 20, 'support_rate': 1.0,
                         'core_references': 20, 'recovered': 20, 'complete_recall': 1.0, 'severe_errors': 0})
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(gate.require_acceptance(self.report_path, self.workspace, self.config), report)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_exact_thresholds_pass_without_trusting_top_level_numbers(self):
        for i, row in enumerate(self.review['records'][:2]):
            row['decision'] = ('quarantine', 'uncertain')[i]
        for row in self.review['references'][:4]:
            row.update(decision='missed', record_keys=[])
        self.review.update(precision=0, recall=0)
        report = self.assess()
        self.assertTrue(report['passed'], report['blockers'])
        self.assertEqual(report['metrics']['support_rate'], .9)
        self.assertEqual(report['metrics']['complete_recall'], .8)

    def test_below_precision_and_recall_fail_even_with_self_reported_one(self):
        self.review.update(precision=1, recall=1)
        for row in self.review['records'][:3]:
            row['decision'] = 'quarantine'
        for row in self.review['references'][:5]:
            row.update(decision='uncertain', record_keys=[])
        result = self.assess()
        self.blocked(result, 'support_rate_below')
        self.blocked(result, 'complete_recall_below')

    def test_empty_output_has_no_zero_denominator_pass(self):
        self.snapshot[1].clear()
        self.review['records'] = []
        for row in self.review['references']:
            row.update(decision='missed', record_keys=[])
        result = self.assess(refresh_output=True)
        self.blocked(result, 'empty_output')
        self.assertIsNone(result['metrics']['support_rate'])

    def test_every_record_needs_explicit_boolean_severity_and_reason(self):
        for severity in (None, 0, 'false', [], {}):
            with self.subTest(severity=severity):
                self.review['records'][0]['severe_error'] = severity
                self.blocked(self.assess(), 'severe_error_flag_invalid')
        self.review['records'][0].pop('severe_error')
        self.blocked(self.assess(), 'severe_error_flag_invalid')
        self.review['records'][0]['severe_error'] = False
        self.review['records'][0]['reason'] = '  '
        self.blocked(self.assess(), 'record_decision_invalid')

    def test_one_severe_error_blocks_even_above_rate_thresholds(self):
        self.review['records'][0].update(decision='quarantine', severe_error=True)
        self.review['references'][0].update(decision='missed', record_keys=[])
        result = self.assess()
        self.blocked(result, 'severe_content_errors_present')
        self.assertEqual(result['metrics']['severe_errors'], 1)

    def test_missing_duplicate_unknown_record_reviews_rejected(self):
        original = deepcopy(self.review['records'])
        variants = [original[:-1], original + [original[0]],
                    original[:-1] + [dict(original[-1], record_key='invented')], None]
        for rows in variants:
            with self.subTest(rows_type=type(rows)):
                self.review['records'] = rows
                self.blocked(self.assess(), 'record_')

    def test_missing_duplicate_unknown_core_reference_reviews_rejected(self):
        original = deepcopy(self.review['references'])
        for rows in (original[:-1], original + [original[0]], original[:-1] + [dict(original[-1], reference_id='invented')]):
            self.review['references'] = rows
            self.blocked(self.assess(), 'reference_')

    def test_invented_cross_paper_other_passage_and_quarantine_links_rejected(self):
        original = self.review['references'][0]['record_keys']
        for key in ('invented', self.snapshot[1][4]['record_key'], self.snapshot[1][1]['record_key']):
            with self.subTest(key=key):
                self.review['references'][0]['record_keys'] = [key]
                self.blocked(self.assess(), 'reference_record_match_invalid')
        self.review['references'][0]['record_keys'] = original
        self.review['records'][0]['decision'] = 'quarantine'
        self.blocked(self.assess(), 'reference_record_match_invalid')

    def test_conservative_one_key_one_reference_is_explicit(self):
        self.review['references'][1]['record_keys'] = self.review['references'][0]['record_keys']
        result = self.assess()
        self.blocked(result, 'reference_record_match_invalid')
        self.assertEqual(result['metrics']['recovered'], 18)
        self.assertIn('CONSERVATIVE', gate.__doc__)

    def test_unrecovered_rows_cannot_smuggle_keys(self):
        self.review['references'][0]['decision'] = 'missed'
        self.blocked(self.assess(), 'unrecovered_reference_has_record_keys')

    def test_all_exported_record_quotes_checked_including_quarantine(self):
        self.review['records'][0]['decision'] = 'quarantine'
        self.review['references'][0].update(decision='missed', record_keys=[])
        self.snapshot[1][0]['field_evidence'][0]['quote'] = 'fabricated'
        self.blocked(self.assess(refresh_output=True), 'citation_text')

    def test_offsets_sentence_ids_and_original_quote_are_checked(self):
        record = self.snapshot[1][0]
        original = deepcopy(record)
        mutators = [lambda r: r['field_evidence'][0].update(char_start=True),
                    lambda r: r['field_evidence'][0].update(sentence_id='invented'),
                    lambda r: r.update(original_quote='invented'),
                    lambda r: r.update(source_sha256='0' * 64),
                    lambda r: r.update(record_key='invented')]
        for mutate in mutators:
            record.clear(); record.update(deepcopy(original)); mutate(record)
            self.blocked(self.assess(refresh_output=True), 'quote_not_grounded')

    def test_partial_anchor_does_not_recover_full_reference_quote(self):
        # The reference requires the entire original source sentence, not a
        # citation to some other sentence in the same paragraph.
        n = self.reference['papers'][0]['negatives'][0]
        n['quote'] = self.documents[n['id'].split('-N')[0]]['units'][0]['text'] + ' More context.'
        self.write_reference()
        self.state['reference_sha256'] = self.index['reference_sha256']
        save(self.workspace / 'candidate_state.json', self.state)
        self.review['reference_sha256'] = self.index['reference_sha256']
        self.blocked(self.assess(), 'reference_quote_not_grounded')

    def test_reference_coverage_and_public_index_cannot_be_shaved(self):
        self.reference['papers'][0]['units_reviewed'].pop()
        self.write_reference()
        self.blocked(self.assess(), 'reference_units_incomplete')

    def test_reference_core_flag_and_quote_changes_fail_public_binding(self):
        self.reference['papers'][0]['negatives'][0]['core_case'] = False
        self.write_reference()
        self.blocked(self.assess(), 'public_reference_ids_mismatch')

    def test_minimum_twenty_core_references(self):
        self.reference['papers'][0]['negatives'][0]['core_case'] = False
        self.index['papers'][0]['references'][0]['core_case'] = False
        self.index['papers'][0]['core_reference_count'] = 3
        self.index['core_reference_count'] = 19
        self.write_reference()
        self.state['reference_sha256'] = self.index['reference_sha256']
        save(self.workspace / 'candidate_state.json', self.state)
        self.review['reference_sha256'] = self.index['reference_sha256']
        self.review['references'].pop(0)
        self.blocked(self.assess(), 'fewer_than_20')

    def test_frozen_state_must_have_original_reference_hash(self):
        self.state.pop('reference_sha256')
        save(self.workspace / 'candidate_state.json', self.state)
        self.blocked(self.assess(), 'reference_not_frozen_before_generation')

    def test_state_filename_is_candidate_state(self):
        (self.workspace / 'candidate_state.json').rename(self.workspace / 'sentence_state.json')
        self.blocked(self.assess(), 'state_unavailable')

    def test_all_five_sources_and_no_gaps_are_required(self):
        summary = self.snapshot[0]
        summary['all_sources_processed'] = False
        self.blocked(self.assess(refresh_output=True), 'end_to_end')
        summary['all_sources_processed'] = True
        summary['papers'][0]['jobs_processed'] = 0
        self.blocked(self.assess(refresh_output=True), 'paper_processing_incomplete')
        summary['papers'][0]['jobs_processed'] = 1
        summary['unresolved_paragraphs'] = 1
        self.blocked(self.assess(refresh_output=True), 'coverage_gaps')

    def test_false_or_nonboolean_regression_engineering_and_provenance_fail(self):
        for field in ('known_regressions_pass', 'engineering_checks_pass'):
            for value in (False, 1, 'true', None):
                self.review[field] = value
                self.blocked(self.assess(), field)
            self.review[field] = True
        self.review['reviewer_kind'] = 'expert'
        self.blocked(self.assess(), 'review_provenance_invalid')
        self.review['reviewer_kind'] = 'assistant'
        self.review['expert_gold'] = True
        self.blocked(self.assess(), 'review_provenance_invalid')

    def test_v2_and_different_fixed_doi_cannot_pass(self):
        self.manifest['pipeline'] = 'molgluedb_candidates_v2'
        self.write_manifest()
        self.blocked(self.assess(), 'not_sentence_v3_workspace')
        self.manifest['pipeline'] = gate.PIPELINE
        self.manifest['papers'][0]['doi'] = '10.invalid/other'
        self.write_manifest()
        self.blocked(self.assess(), 'five_fixed_papers_not_present')

    def test_snapshot_unavailable_reports_blocker_without_generation(self):
        with patch.object(gate, '_snapshot', side_effect=ImportError('sentence_export missing')):
            self.blocked(self.assess(), 'snapshot_unavailable')

    def test_budget_exhaustion_is_reported_without_claiming_real_acceptance(self):
        self.snapshot[0].update(all_sources_processed=False, stop_reason='budget_exhausted',
            shared_budget={'requests_reserved': 200, 'max_requests': 200})
        self.blocked(self.assess(refresh_output=True), 'end_to_end')
        self.assertEqual(gate._read(self.report_path)['summary']['shared_budget']['requests_reserved'], 200)

    def test_require_detects_report_review_output_audit_state_reference_index_tampering(self):
        self.assertTrue(self.assess()['passed'])
        initial_report = self.report_path.read_bytes()
        saved_review = self.review_path.read_bytes()
        mutations = [('report', lambda: save(self.report_path, dict(gate._read(self.report_path), metrics={}))),
                     ('review', lambda: save(self.review_path, dict(self.review, note='changed'))),
                     ('records', lambda: self.snapshot[1][0].update(note='changed')),
                     ('audits', lambda: self.snapshot[2].append({'destination': 'changed'})),
                     ('failures', lambda: self.snapshot[3].append({'task_id': 'unknown'})),
                     ('summary', lambda: self.snapshot[0].update(stop_reason='changed')),
                     ('state', lambda: save(self.workspace / 'candidate_state.json', dict(self.state, changed=True))),
                     ('reference', lambda: save(self.workspace / 'acceptance_reference.json', dict(self.reference, changed=True))),
                     ('index', lambda: save(self.code / 'sentence_v3_reference_index.json', dict(self.index, changed=True)))]
        baseline = deepcopy(self.snapshot)
        for name, mutate in mutations:
            with self.subTest(name=name):
                self.report_path.write_bytes(initial_report); self.review_path.write_bytes(saved_review)
                self.snapshot = deepcopy(baseline)
                save(self.workspace / 'candidate_state.json', self.state)
                self.write_reference()
                mutate()
                with self.assertRaisesRegex(ValueError, 'Full extraction locked'):
                    gate.require_acceptance(self.report_path, self.workspace, self.config)

    def test_require_rejects_config_prompt_runtime_and_original_source_changes(self):
        self.assertTrue(self.assess()['passed'])
        with self.assertRaises(ValueError):
            gate.require_acceptance(self.report_path, self.workspace, dict(self.config, model='other'))
        paths = [self.workspace / gate.PROMPTS[0], self.workspace / 'runtime/sentence_v3.py',
                 Path(self.manifest['papers'][0]['source_path'])]
        for path in paths:
            before = path.read_bytes()
            path.write_bytes(before + b' changed')
            with self.assertRaises(ValueError):
                gate.require_acceptance(self.report_path, self.workspace, self.config)
            path.write_bytes(before)

    def test_binding_is_portable_to_full_inputs_without_pilot_only_hashes(self):
        self.assertTrue(self.assess()['passed'])
        full = self.root / 'full'
        shutil.copytree(self.workspace, full)
        m = deepcopy(self.manifest)
        m.update(phase='full', papers=[{'paper_id': 'unavailable_full_source', 'doi': '10.test/full'}])
        # Full corpus has different inputs and no pilot reference or documents.
        m['file_hashes'] = {k: v for k, v in m['file_hashes'].items() if k in gate.PROMPTS}
        save(full / 'manifest.json', m)
        self.assertEqual(gate.binding(full, self.config), self.review['binding'])
        self.assertTrue(gate.require_acceptance(self.report_path, full, self.config)['passed'])

    def test_assess_cannot_overwrite_evidence(self):
        save(self.review_path, self.review)
        for path in (self.review_path, self.workspace / 'candidate_state.json',
                     self.workspace / 'documents' / (next(iter(gate.PILOT_PAPERS)) + '.json')):
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                gate.assess(self.workspace, self.review_path, path)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_workspace_generates_blocked_report(self):
        result = gate.assess(self.root / 'missing', self.root / 'missing-review.json', self.report_path)
        self.blocked(result, 'workspace_invalid')
        self.assertTrue(self.report_path.is_file())

    def test_cli_binding_assess_require_and_blocked_exit_codes(self):
        config_path = self.root / 'config.json'
        save(config_path, self.config)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(['binding', '--workspace', str(self.workspace), '--config', str(config_path)]), 0)
            self.assess()
            self.assertEqual(gate.main(['assess', '--workspace', str(self.workspace), '--review', str(self.review_path),
                                       '--out', str(self.report_path)]), 0)
            self.assertEqual(gate.main(['require', '--workspace', str(self.workspace), '--config', str(config_path),
                                       '--acceptance', str(self.report_path)]), 0)
            self.assertEqual(gate.main(['require', '--workspace', str(self.workspace), '--config', str(config_path),
                                       '--acceptance', str(self.root / 'absent.json')]), 2)

    def test_duplicate_json_keys_and_nonfinite_numbers_fail_closed(self):
        self.assess()
        for text in ('{"records": [], "records": []}', '{"precision": NaN}'):
            self.review_path.write_text(text, encoding='utf-8')
            self.blocked(gate.assess(self.workspace, self.review_path, self.report_path), 'review_unavailable')

    def test_actual_sentence_export_snapshot_schema_and_provenance(self):
        """Saved synthetic artifacts, real snapshot; no runtime or client is run."""
        from sentence_export import snapshot
        self.manifest['job_ids'] = []
        self.state.update(groups={}, condition_groups={})

        def artifact(name, value):
            save(self.workspace / name, value)
            return {'path': name, 'sha256': gate._hash(self.workspace / name)}

        def task(jid, stage, group, result):
            tid = jid + ':' + stage + (':' + format(group, '03d') if stage != 'discovery' else '')
            entry = {'job_id': jid, 'stage': stage, 'group': group, 'status': 'complete'}
            for kind, value in (('request', {'synthetic_saved_request': True}),
                                ('response', {'synthetic_saved_response': True}), ('result', result)):
                descriptor = artifact(kind + 's/' + tid.replace(':', '_') + '.json', value)
                entry[kind + '_path'] = descriptor['path']
                entry[kind + '_sha256'] = descriptor['sha256']
            self.state['tasks'][tid] = entry
            return tid, entry

        for number, p in enumerate(self.manifest['papers']):
            pid, jid = p['paper_id'], 'SYNTHETIC_JOB_' + str(number)
            self.manifest['job_ids'].append(jid)
            doc = self.documents[pid]
            index_name = 'sentence_indexes/' + pid + '.json'
            save(self.workspace / index_name, index_document(doc))
            self.manifest['file_hashes'][index_name] = gate._hash(self.workspace / index_name)
            p.update(job_ids=[jid], document_path=str(self.workspace / ('documents/' + pid + '.json')),
                     sentence_index_path=str(self.workspace / index_name))
            sentences = index_document(doc)
            candidates = [{'candidate_id': r['candidate_id'], 'sentence_ids': r['anchor_sentence_ids']}
                          for r in self.snapshot[1] if r['paper_id'] == pid]
            job = {'job_id': jid, 'paper_id': pid, 'source_sha256': doc['source_sha256'], 'protocol': 'sentence_v3',
                   'document_path': p['document_path'], 'document_sha256': gate._hash(p['document_path']),
                   'sentence_index_path': p['sentence_index_path'], 'sentence_index_sha256': gate._hash(p['sentence_index_path']),
                   'paragraphs': [{'paragraph_id': s['unit_id'], 'sentence_ids': [s['sentence_id']]} for s in sentences]}
            job_name = 'jobs/' + jid + '.json'
            save(self.workspace / job_name, job)
            self.manifest['file_hashes'][job_name] = gate._hash(self.workspace / job_name)
            discovery = {'accepted': candidates, 'rejected': [], 'unresolved': [], 'accounting_complete': True,
                         'coverage': [{'paragraph_id': s['unit_id'], 'status': 'has_candidates',
                                       'candidate_ids': [c['candidate_id']]} for s, c in zip(sentences, candidates)]}
            _, discovered = task(jid, 'discovery', 0, discovery)
            groups = [{'candidates': [c]} for c in candidates]
            descriptor = artifact('groups/' + jid + '.json', {'groups': groups,
                                  'discovery_result_sha256': discovered['result_sha256']})
            descriptor['discovery_result_sha256'] = discovered['result_sha256']
            self.state['groups'][jid] = descriptor
            for i, (candidate, record) in enumerate(zip(candidates, [r for r in self.snapshot[1] if r['paper_id'] == pid])):
                result = {'accepted': [{'candidate_id': candidate['candidate_id'], 'record': record}],
                          'rejected': [], 'unresolved': [], 'accounting_complete': True}
                _, facts = task(jid, 'facts', i, result)
                facts['discovery_result_sha256'] = discovered['result_sha256']
                plan = artifact('condition_groups/' + jid + '_' + str(i) + '.json', {
                    'group': None, 'facts_result_sha256': facts['result_sha256']})
                plan['facts_result_sha256'] = facts['result_sha256']
                self.state['condition_groups'][jid + ':conditions:' + format(i, '03d')] = plan
        self.write_manifest()
        save(self.workspace / 'candidate_state.json', self.state)
        actual = snapshot(self.workspace)
        self.assertTrue(actual[0]['all_sources_processed'])
        self.assertEqual(len(actual[1]), 20)
        self.assertTrue(all(r['sources'][0]['result_sha256'] for r in actual[1]))
        self.review['binding'] = gate.binding(self.workspace, self.config)
        self.review['output_fingerprint'] = gate.output_fingerprint(*actual)
        with patch.object(gate, '_snapshot', side_effect=snapshot):
            report = self.assess()
            self.assertTrue(report['passed'], report['blockers'])
            self.assertTrue(gate.require_acceptance(self.report_path, self.workspace, self.config)['passed'])

    def test_real_condition_revision_preserves_key_and_exact_context_quotes(self):
        from sentence_workflow import validate_conditions, CONDITION_FIELDS
        record = self.snapshot[1][0]
        doc = self.documents[record['paper_id']]
        sentences = index_document(doc)
        values = dict.fromkeys(CONDITION_FIELDS)
        values.update(treatment_time='synthetic unspecified time', endpoint_resolution='Z protein decrease')
        row = {'record_id': record['record_key'], 'values': values,
               'evidence': {f: [sentences[1]['sentence_id']] if values[f] else [] for f in CONDITION_FIELDS}}
        job = {'frozen_context': {'records': [record], 'requested_record_ids': [record['record_key']],
                                 'sentences': sentences}}
        result = validate_conditions({'items': [row]}, job)
        self.assertEqual(len(result['accepted']), 1)
        self.snapshot[1][0] = result['accepted'][0]['record']
        report = self.assess(refresh_output=True)
        self.assertTrue(report['passed'], report['blockers'])
        revised = self.snapshot[1][0]
        self.assertEqual(revised['record_key'], record['record_key'])
        self.assertIn('core_original', revised)
        revised['condition_evidence'][0]['text'] = 'fabricated condition quote'
        self.blocked(self.assess(refresh_output=True), 'citation_text_conflict')

    def test_missing_or_duplicate_output_keys_and_blank_core_fields_cannot_pass(self):
        self.snapshot[1].append(deepcopy(self.snapshot[1][0]))
        self.blocked(self.assess(refresh_output=True), 'output_records_duplicate')
        self.snapshot[1].pop()
        self.snapshot[1][0]['values']['subject'] = None
        self.blocked(self.assess(refresh_output=True), 'record_key_not_content_bound')

    def test_shared_ledger_progress_does_not_invalidate_unchanged_pilot(self):
        self.snapshot[0]['shared_budget'] = {'requests_reserved': 180, 'max_requests': 200}
        report = self.assess(refresh_output=True)
        self.assertTrue(report['passed'], report['blockers'])
        self.snapshot[0]['shared_budget']['requests_reserved'] = 200
        self.assertTrue(gate.require_acceptance(self.report_path, self.workspace, self.config)['passed'])

    def test_malformed_manifest_is_a_reported_blocker(self):
        (self.workspace / 'manifest.json').write_text('not JSON', encoding='utf-8')
        self.blocked(self.assess(), 'workspace_invalid')


if __name__ == '__main__':
    unittest.main()
