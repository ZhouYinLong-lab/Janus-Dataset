"""Offline regressions for context planning and known semantic failures."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from corpus import save
from facts_v3 import FIELDS
from sentence_v3 import index_document, build_sentence_jobs, validate_discovery
import sentence_workflow as workflow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = {'paper_id': 'P', 'source_sha256': 'source-hash',
            'source_path': str(self.root/'source.xml'), 'units': [
                {'unit_id': 'U1', 'text': 'Analogues A and B were tested against protein Z.',
                 'kind': 'body_paragraph', 'section': 'Results', 'locator': 'p1'},
                {'unit_id': 'U2', 'text': 'These compounds did not improve degradation relative to R.',
                 'kind': 'body_paragraph', 'section': 'Results', 'locator': 'p2'}]}
        save(self.root/'document.json', self.doc)
        self.sentences = index_document(self.doc)
        save(self.root/'sentences.json', self.sentences)
        self.job = build_sentence_jobs(self.doc, {'doi': 'test'})['jobs'][0]
        self.job.update(document_path=str(self.root/'document.json'),
                        sentence_index_path=str(self.root/'sentences.json'))
        payload = {'paragraphs': [{'paragraph_id': p['paragraph_id'],
            'status': 'has_candidates' if i == 1 else 'none_found',
            'spans': [{'sentence_ids': p['sentence_ids']}] if i == 1 else []}
            for i, p in enumerate(self.job['paragraphs'])]}
        self.candidate = validate_discovery(payload, self.job)['accepted'][0]
        self.group = workflow.plan_facts(self.job, [self.candidate])[0]
        self.candidate = self.group['candidate']
        self.effective = dict(self.job, active_stage='facts', frozen_context=self.group)
        self.payload = {'status': 'observations', 'reason': None, 'observations': [{
            'values': {'subject': 'Analogues A and B', 'target': 'protein Z',
                'endpoint': 'protein degradation', 'observation': 'did not improve',
                'comparator': 'R', 'scope_condition': None},
            'outcome_type': 'not_improved',
            'evidence': {f: [] if f == 'scope_condition' else [
                self.sentences[0 if f in {'subject', 'target'} else 1]['sentence_id']]
                for f in FIELDS}}]}

    def result(self, payload=None):
        return workflow.validate_response(payload or self.payload, self.effective, [self.candidate])

    def test_name_in_previous_sentence_and_group_preserved(self):
        result = self.result()
        record = result['accepted'][0]['record']
        self.assertEqual(record['values']['subject'], 'Analogues A and B')
        self.assertEqual(record['record_status'], 'core_usable')
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual([s['unit_id'] for s in self.group['sentences']], ['U1', 'U2'])

    def test_wrong_not_improved_strength_is_quarantined(self):
        bad = deepcopy(self.payload)
        bad['observations'][0]['outcome_type'] = 'not_observed'
        self.assertEqual(self.result(bad)['accepted'][0]['record']['record_status'], 'quarantine')

    def test_missing_optional_figure_cannot_cancel_core(self):
        result = self.result({'status': 'uncertain', 'reason': 'Missing figure S4', 'observations': []})
        self.assertIn('invalid_abstention_reason', result['unresolved'][0]['errors'])

    def test_falsely_missing_provided_anchor_is_flagged(self):
        result = self.result({'status': 'uncertain', 'reason': 'Anchor sentence is missing', 'observations': []})
        self.assertIn('invalid_abstention_reason', result['unresolved'][0]['errors'])

    def test_quote_object_not_converted_into_value(self):
        bad = deepcopy(self.payload)
        bad['observations'][0]['values']['subject'] = {'quote': 'Analogues A and B'}
        self.assertFalse(self.result(bad)['accepted'])

    def test_one_candidate_multiple_observations(self):
        payload = deepcopy(self.payload)
        extra = deepcopy(payload['observations'][0])
        extra['values']['endpoint'] = 'separate assay'
        payload['observations'].append(extra)
        rows = self.result(payload)['accepted']
        self.assertEqual(len({r['record']['record_key'] for r in rows}), 2)

    def test_optional_missing_conditions_do_not_trigger_call(self):
        result = self.result()
        self.assertIsNone(workflow.plan_conditions(self.effective, result, self.candidate))

    def test_ambiguous_activity_requests_verification_not_degradation_label(self):
        record = self.result()['accepted'][0]['record']
        sid = self.sentences[1]['sentence_id']
        supplied = [dict(self.sentences[1], text='LL-K12-4 showed a 100-fold lower activity (EC50).')]
        record['field_evidence'] = [{'field': 'observation', 'sentence_id': sid}]
        self.assertTrue(workflow._requires_definition(record, supplied))

    def condition_case(self):
        record = self.result()['accepted'][0]['record']
        self.condition_group = dict(self.group, records=[record],
            requested_record_ids=[record['record_key']])
        payload = deepcopy(workflow.CONDITION_EXAMPLE)
        row = payload['items'][0]
        row['record_id'] = record['record_key']
        row['values']['endpoint_resolution'] = 'cell proliferation'
        row['evidence']['endpoint_resolution'] = [self.sentences[0]['sentence_id']]
        return payload, dict(self.effective, active_stage='conditions', frozen_context=self.condition_group)

    def test_conflicting_context_preserves_core_and_quarantines(self):
        payload, job = self.condition_case()
        row = workflow.validate_conditions(payload, job)['accepted'][0]['record']
        self.assertEqual(row['record_status'], 'quarantine')
        self.assertEqual(row['values']['endpoint'], 'protein degradation')
        self.assertEqual(row['context_revision']['values']['endpoint_resolution'], 'cell proliferation')
        self.assertEqual(row['core_original']['values']['endpoint'], 'protein degradation')

    def test_missing_condition_response_not_empty_success(self):
        _, job = self.condition_case()
        result = workflow.validate_conditions({'items': []}, job)
        self.assertFalse(result['accounting_complete'])
        self.assertEqual(result['unresolved'][0]['reason'], 'missing_response')

    def test_condition_requires_grounded_string(self):
        payload, job = self.condition_case()
        payload['items'][0]['values']['cell_line'] = {'quote': 'HeLa'}
        self.assertTrue(workflow.validate_conditions(payload, job)['rejected'])

    def test_no_condition_citation_to_hidden_material(self):
        payload, job = self.condition_case()
        payload['items'][0]['evidence']['endpoint_resolution'] = ['not-supplied']
        self.assertTrue(workflow.validate_conditions(payload, job)['rejected'])

    def test_context_without_definition_keeps_pending(self):
        payload, job = self.condition_case()
        job['frozen_context']['records'][0]['record_status'] = 'semantic_pending'
        for f in workflow.CONDITION_FIELDS:
            payload['items'][0]['values'][f] = None
            payload['items'][0]['evidence'][f] = []
        row = workflow.validate_conditions(payload, job)['accepted'][0]['record']
        self.assertEqual(row['record_status'], 'semantic_pending')
        self.assertFalse(row['ready_for_training'])

    def test_endpoint_resolution_has_its_own_core_evidence(self):
        payload, job = self.condition_case()
        job['frozen_context']['records'][0]['values']['endpoint'] = None
        job['frozen_context']['records'][0]['record_status'] = 'semantic_pending'
        row = workflow.validate_conditions(payload, job)['accepted'][0]['record']
        endpoint = [e for e in row['field_evidence'] if e['field'] == 'endpoint']
        self.assertEqual(row['record_status'], 'core_usable')
        self.assertEqual(endpoint[0]['quote'], self.sentences[0]['text'])

    def test_context_cannot_clear_existing_semantic_quarantine(self):
        payload, job = self.condition_case()
        record = job['frozen_context']['records'][0]
        record['values']['endpoint'] = None
        record['record_status'] = 'quarantine'
        record['semantic_flags'] = ['not_improved_must_not_become_inactive']
        row = workflow.validate_conditions(payload, job)['accepted'][0]['record']
        self.assertEqual(row['record_status'], 'quarantine')

    def test_request_token_caps_and_candidate_id_kept_by_program(self):
        for name in ('discovery_v3.md', 'facts_v3.md', 'conditions_v3.md'):
            (self.root/name).write_text('Return JSON.', encoding='utf-8')
        config = {'model': 'offline', 'output_token_parameter': 'max_tokens',
                  'max_output_tokens': 3000, 'response_format': 'json_object'}
        for stage, cap in [('discovery', 2048), ('facts', 3000)]:
            request = workflow.request_for(self.root, self.effective, stage, config)
            self.assertEqual(request['max_tokens'], cap)
        self.assertNotIn('candidate_id', workflow.request_for(self.root, self.effective, 'facts', config)['messages'][1]['content'])


if __name__ == '__main__':
    unittest.main()
