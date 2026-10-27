"""Synthetic offline contract tests; these fixtures are not scientific gold."""

from copy import deepcopy
import unittest

from facts_v3 import EXAMPLE, FIELDS, OUTCOME_TYPES, SCHEMA, validate_facts


def fixture():
    quote = ('Synthetic analogues A and B did not improve target Z degradation '
             'relative to synthetic reference R; this does not establish inactivity.')
    sentence = {'sentence_id': 'S1', 'unit_id': 'SYNTHETIC:U1', 'text': quote,
                'char_start': 12, 'char_end': 12 + len(quote)}
    candidate = {'candidate_id': 'SYNTHETIC:C1', 'anchor_sentence_ids': ['S1']}
    job = {'paper_id': 'SYNTHETIC_FORMAT_ONLY', 'doi': None,
           'source_sha256': 'synthetic-source-not-a-real-paper',
           'sentences': [sentence],
           'frozen_context': {'sentences': [deepcopy(sentence)],
                              'candidate': deepcopy(candidate)}}
    return deepcopy(EXAMPLE), job, [candidate]


def abstention(reason, status='uncertain'):
    return {'status': status, 'reason': reason, 'observations': []}


class FactsV3Tests(unittest.TestCase):
    def test_filled_example_and_exact_record_contract(self):
        payload, job, candidates = fixture()
        result = validate_facts(payload, job, candidates)
        self.assertEqual(set(result), {'accepted', 'rejected', 'unresolved',
                                       'coverage_notes', 'accounting_complete'})
        self.assertTrue(result['accounting_complete'])
        self.assertFalse(result['rejected'])
        self.assertFalse(result['unresolved'])
        self.assertEqual(set(result['accepted'][0]), {'candidate_id', 'record'})
        record = result['accepted'][0]['record']
        self.assertEqual(set(record), {
            'values', 'outcome_type', 'field_evidence', 'source_sha256', 'paper_id', 'doi',
            'candidate_id', 'record_key', 'anchor_sentence_ids', 'original_quote',
            'record_status', 'expert_gold', 'semantic_review', 'ready_for_training'})
        self.assertEqual(record['record_status'], 'core_usable')
        self.assertEqual(record['values'], payload['observations'][0]['values'])
        self.assertEqual(record['outcome_type'], 'not_improved')
        self.assertFalse(record['expert_gold'])
        self.assertFalse(record['ready_for_training'])
        self.assertEqual(record['semantic_review'], 'pending')

    def test_schema_is_plain_json_serializable_and_matches_fields(self):
        import json
        self.assertEqual(json.loads(json.dumps(SCHEMA)), SCHEMA)
        item = SCHEMA['properties']['observations']['items']['properties']
        self.assertEqual(item['values']['required'], list(FIELDS))
        self.assertEqual(item['outcome_type']['enum'], list(OUTCOME_TYPES))
        self.assertFalse(item['values']['additionalProperties'])

    def test_dict_array_and_other_non_string_values_are_rejected(self):
        for field in FIELDS:
            for value in ({'value': 'invented'}, ['invented'], 0, False):
                with self.subTest(field=field, value=value):
                    payload, job, candidates = fixture()
                    payload['observations'][0]['values'][field] = value
                    result = validate_facts(payload, job, candidates)
                    self.assertFalse(result['accepted'])
                    self.assertIn('invalid_value_type:' + field, result['rejected'][0]['errors'])

    def test_null_and_empty_strings_are_legal_and_preserved(self):
        for value in (None, '', '  '):
            with self.subTest(value=value):
                payload, job, candidates = fixture()
                row = payload['observations'][0]
                row['values']['target'] = value
                row['evidence']['target'] = []
                record = validate_facts(payload, job, candidates)['accepted'][0]['record']
                self.assertEqual(record['values']['target'], value)
                self.assertEqual(record['record_status'], 'core_usable')

    def test_empty_core_fields_are_retained_as_semantic_pending(self):
        for field in ('subject', 'endpoint', 'observation'):
            for value in (None, '', ' '):
                with self.subTest(field=field, value=value):
                    payload, job, candidates = fixture()
                    payload['observations'][0]['values'][field] = value
                    payload['observations'][0]['evidence'][field] = []
                    result = validate_facts(payload, job, candidates)
                    self.assertEqual(result['accepted'][0]['record']['record_status'], 'semantic_pending')

    def test_each_nonempty_field_requires_ids(self):
        for field in FIELDS:
            with self.subTest(field=field):
                payload, job, candidates = fixture()
                row = payload['observations'][0]
                row['values'][field] = 'synthetic value'
                row['evidence'][field] = []
                result = validate_facts(payload, job, candidates)
                self.assertIn('missing_field_evidence:' + field, result['rejected'][0]['errors'])

    def test_empty_field_cannot_have_evidence(self):
        payload, job, candidates = fixture()
        payload['observations'][0]['evidence']['scope_condition'] = ['S1']
        result = validate_facts(payload, job, candidates)
        self.assertIn('evidence_for_empty_field:scope_condition', result['rejected'][0]['errors'])

    def test_nonexistent_sentence_id_is_rejected(self):
        payload, job, candidates = fixture()
        payload['observations'][0]['evidence']['subject'] = ['S999']
        result = validate_facts(payload, job, candidates)
        self.assertIn('unknown_sentence_id:subject', result['rejected'][0]['errors'])

    def test_source_sentence_not_frozen_cannot_be_cited(self):
        payload, job, candidates = fixture()
        job['sentences'].append(dict(job['sentences'][0], sentence_id='S2'))
        payload['observations'][0]['evidence']['subject'] = ['S2']
        result = validate_facts(payload, job, candidates)
        self.assertIn('unknown_sentence_id:subject', result['rejected'][0]['errors'])

    def test_evidence_is_ids_only_and_ids_must_be_unique(self):
        for ids in ('S1', None, [{'sentence_id': 'S1'}], [1], [''], ['S1', 'S1']):
            with self.subTest(ids=ids):
                payload, job, candidates = fixture()
                payload['observations'][0]['evidence']['subject'] = ids
                self.assertFalse(validate_facts(payload, job, candidates)['accepted'])

    def test_quotes_and_unicode_offsets_are_copied_from_trusted_sentence(self):
        payload, job, candidates = fixture()
        sentence = job['sentences'][0]
        sentence.update(text='合成示例：甲和乙的反应未提高。', char_start=7)
        sentence['char_end'] = 7 + len(sentence['text'])
        job['frozen_context']['sentences'] = [deepcopy(sentence)]
        record = validate_facts(payload, job, candidates)['accepted'][0]['record']
        self.assertEqual(record['original_quote'], sentence['text'])
        for evidence in record['field_evidence']:
            self.assertEqual(set(evidence), {'field', 'sentence_id', 'unit_id', 'quote', 'char_start', 'char_end'})
            self.assertEqual(evidence['quote'], sentence['text'])
            self.assertEqual(evidence['char_start'], 7)
            self.assertEqual(evidence['char_end'], sentence['char_end'])
        self.assertEqual(record['source_sha256'], job['source_sha256'])
        self.assertEqual(record['paper_id'], job['paper_id'])

    def test_source_sentence_mapping_and_frozen_id_list(self):
        payload, job, candidates = fixture()
        sentence = job['sentences'][0]
        sentence.pop('sentence_id')
        sentence['quote'] = sentence.pop('text')
        job['sentences'] = {'S1': sentence}
        job['frozen_context']['sentences'] = ['S1']
        self.assertEqual(len(validate_facts(payload, job, candidates)['accepted']), 1)

    def test_context_supports_optional_field_but_cannot_replace_anchor_observation(self):
        payload, job, candidates = fixture()
        support = {'sentence_id': 'S2', 'unit_id': 'SYNTHETIC:METHODS',
                   'text': 'Synthetic treatment lasted 6 hours.', 'char_start': 0,
                   'char_end': len('Synthetic treatment lasted 6 hours.')}
        job['sentences'].append(support)
        job['frozen_context']['sentences'].append(deepcopy(support))
        row = payload['observations'][0]
        row['values']['scope_condition'] = '6 hours'
        row['evidence']['scope_condition'] = ['S2']
        record = validate_facts(payload, job, candidates)['accepted'][0]['record']
        self.assertEqual(record['record_status'], 'core_usable')
        self.assertEqual(record['anchor_sentence_ids'], ['S1'])
        self.assertEqual(record['original_quote'], job['sentences'][0]['text'])
        self.assertEqual(record['field_evidence'][-1]['unit_id'], 'SYNTHETIC:METHODS')
        row['evidence']['observation'] = ['S2']
        result = validate_facts(payload, job, candidates)
        self.assertFalse(result['accepted'])
        self.assertIn('observation_not_linked_to_candidate_anchor', result['rejected'][0]['errors'])

    def test_multiple_anchors_preserve_original_order_and_multisentence_evidence(self):
        payload, job, candidates = fixture()
        support = dict(job['sentences'][0], sentence_id='S2')
        job['sentences'].append(support)
        job['frozen_context']['sentences'].append(deepcopy(support))
        candidates[0]['anchor_sentence_ids'] = ['S2', 'S1']
        job['frozen_context']['candidate'] = deepcopy(candidates[0])
        payload['observations'][0]['evidence']['observation'] = ['S1', 'S2']
        record = validate_facts(payload, job, candidates)['accepted'][0]['record']
        self.assertEqual(record['anchor_sentence_ids'], ['S2', 'S1'])
        self.assertEqual(record['original_quote'], support['text'] + '\n' + job['sentences'][0]['text'])
        self.assertEqual([e['sentence_id'] for e in record['field_evidence'] if e['field'] == 'observation'], ['S1', 'S2'])

    def test_same_sentence_two_endpoints_remain_two_records(self):
        payload, job, candidates = fixture()
        sentence = job['sentences'][0]
        sentence['text'] = ('SYNTHETIC: A and B did not improve Z degradation; '
                            'their binding response was reduced relative to R.')
        sentence['char_end'] = sentence['char_start'] + len(sentence['text'])
        job['frozen_context']['sentences'] = [deepcopy(sentence)]
        row = deepcopy(payload['observations'][0])
        row['values'].update(endpoint='binding response', observation='reduced binding response relative to R')
        row['outcome_type'] = 'reduced'
        payload['observations'].append(row)
        result = validate_facts(payload, job, candidates)
        self.assertEqual(len(result['accepted']), 2)
        a, b = [item['record'] for item in result['accepted']]
        self.assertNotEqual(a['record_key'], b['record_key'])
        self.assertEqual(a['original_quote'], b['original_quote'])

    def test_same_endpoint_different_outcome_strength_is_not_merged(self):
        payload, job, candidates = fixture()
        payload['observations'].append(deepcopy(payload['observations'][0]))
        payload['observations'][1]['outcome_type'] = 'not_significant'
        records = [x['record'] for x in validate_facts(payload, job, candidates)['accepted']]
        self.assertEqual(len(records), 2)
        self.assertNotEqual(records[0]['record_key'], records[1]['record_key'])

    def test_group_subject_is_not_expanded(self):
        payload, job, candidates = fixture()
        result = validate_facts(payload, job, candidates)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['accepted'][0]['record']['values']['subject'], 'Synthetic analogues A and B')

    def test_hash_is_stable_and_covers_each_value_and_outcome(self):
        payload, job, candidates = fixture()
        key = validate_facts(payload, job, candidates)['accepted'][0]['record']['record_key']
        self.assertEqual(len(key), 64)
        reordered = deepcopy(payload)
        reordered['observations'][0]['values'] = dict(reversed(list(reordered['observations'][0]['values'].items())))
        self.assertEqual(validate_facts(reordered, job, candidates)['accepted'][0]['record']['record_key'], key)
        for field in FIELDS:
            with self.subTest(field=field):
                other = deepcopy(payload)
                other['observations'][0]['values'][field] = 'different synthetic value'
                other['observations'][0]['evidence'][field] = ['S1']
                self.assertNotEqual(validate_facts(other, job, candidates)['accepted'][0]['record']['record_key'], key)

    def test_missing_figure_alone_is_invalid_abstention_and_retains_reason(self):
        _, job, candidates = fixture()
        for reason in ('Missing supplemental Figure S2.', 'Figure S2 is unavailable.', '缺少补充图，无法提取。'):
            for status in ('uncertain', 'not_experimental_negative'):
                with self.subTest(reason=reason, status=status):
                    result = validate_facts(abstention(reason, status), job, candidates)
                    self.assertFalse(result['accepted'])
                    self.assertFalse(result['rejected'])
                    self.assertTrue(result['accounting_complete'])
                    self.assertEqual(result['unresolved'][0]['reason'], reason)
                    self.assertIn('invalid_abstention_reason', result['unresolved'][0]['errors'])
                    self.assertIn('invalid_abstention_reason:missing_figure_alone', result['coverage_notes'])

    def test_fake_missing_or_omitted_anchor_is_detected_from_frozen_material(self):
        _, job, candidates = fixture()
        for reason in ('Missing anchor sentence.', 'The anchor was omitted.', '未提供锚点。'):
            with self.subTest(reason=reason):
                result = validate_facts(abstention(reason), job, candidates)
                self.assertEqual(result['unresolved'][0]['reason'], reason)
                self.assertIn('invalid_abstention_reason:anchor_already_provided', result['coverage_notes'])

    def test_actually_missing_anchor_is_not_marked_fake(self):
        _, job, candidates = fixture()
        job['frozen_context']['sentences'] = []
        result = validate_facts(abstention('Missing anchor sentence.'), job, candidates)
        self.assertEqual(result['unresolved'][0]['errors'], [])
        self.assertIn('anchor_missing:S1', result['coverage_notes'])

    def test_missing_anchor_prevents_records(self):
        payload, job, candidates = fixture()
        job['frozen_context']['sentences'] = []
        result = validate_facts(payload, job, candidates)
        self.assertFalse(result['accepted'])
        self.assertIn('missing_candidate_anchor', result['rejected'][0]['errors'])

    def test_missing_optional_conditions_preserve_core(self):
        payload, job, candidates = fixture()
        self.assertIsNone(payload['observations'][0]['values']['scope_condition'])
        self.assertEqual(validate_facts(payload, job, candidates)['accepted'][0]['record']['record_status'], 'core_usable')
        result = validate_facts(abstention('Dose is missing.'), job, candidates)
        self.assertIn('invalid_abstention_reason:missing_optional_condition_alone', result['coverage_notes'])

    def test_legal_uncertain_status_retains_reason_without_inventing_record(self):
        _, job, candidates = fixture()
        reason = 'The subject of the reported result is ambiguous.'
        result = validate_facts(abstention(reason), job, candidates)
        self.assertEqual(result['unresolved'][0]['reason'], reason)
        self.assertFalse(result['unresolved'][0]['errors'])
        self.assertFalse(result['accepted'])
        self.assertTrue(result['accounting_complete'])

    def test_unknown_endpoint_and_uncertain_outcome_are_semantic_pending(self):
        for endpoint, outcome in (('unknown endpoint', 'not_observed'),
                                  ('uncertain activity', 'not_observed'),
                                  ('未知终点', 'not_observed'),
                                  ('target Z degradation', 'uncertain')):
            with self.subTest(endpoint=endpoint, outcome=outcome):
                payload, job, candidates = fixture()
                payload['observations'][0]['values']['endpoint'] = endpoint
                payload['observations'][0]['outcome_type'] = outcome
                record = validate_facts(payload, job, candidates)['accepted'][0]['record']
                self.assertEqual(record['record_status'], 'semantic_pending')
                self.assertEqual(record['values']['endpoint'], endpoint)

    def test_free_endpoint_names_are_preserved_and_generic_words_do_not_infer_assays(self):
        for endpoint, status in (('activity', 'semantic_pending'), ('potency', 'semantic_pending'),
                                 ('EC50', 'semantic_pending'), ('antiproliferative EC50', 'core_usable'),
                                 ('custom experimentally named response', 'core_usable')):
            with self.subTest(endpoint=endpoint):
                payload, job, candidates = fixture()
                payload['observations'][0]['values']['endpoint'] = endpoint
                record = validate_facts(payload, job, candidates)['accepted'][0]['record']
                self.assertEqual(record['values']['endpoint'], endpoint)
                self.assertEqual(record['record_status'], status)

    def test_genuine_not_experimental_negative_is_accounted_rejection(self):
        _, job, candidates = fixture()
        reason = 'The synthetic text describes an untested prediction.'
        result = validate_facts(abstention(reason, 'not_experimental_negative'), job, candidates)
        self.assertFalse(result['accepted'])
        self.assertFalse(result['unresolved'])
        self.assertEqual(result['rejected'][0]['reason'], reason)
        self.assertTrue(result['accounting_complete'])

    def test_bad_row_does_not_discard_other_observation(self):
        payload, job, candidates = fixture()
        payload['observations'].extend([None, {'values': []}])
        result = validate_facts(payload, job, candidates)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual([row['observation_index'] for row in result['rejected']], [1, 2])
        self.assertTrue(result['accounting_complete'])

    def test_model_cannot_supply_provenance_or_context_flags(self):
        for field in ('paper_id', 'candidate_id', 'anchor_sentence_ids', 'context_complete', 'original_quote'):
            with self.subTest(field=field):
                payload, job, candidates = fixture()
                payload['observations'][0][field] = 'forged'
                self.assertFalse(validate_facts(payload, job, candidates)['accepted'])

    def test_invalid_envelopes_are_incomplete_and_preserve_candidate(self):
        invalid = [None, [], {}, dict(EXAMPLE, paper_id='forged'),
                   dict(EXAMPLE, status=[]), dict(EXAMPLE, observations={}),
                   dict(EXAMPLE, observations=[]), abstention(None), abstention(' '),
                   dict(EXAMPLE, status='uncertain', reason='uncertain')]
        for payload in invalid:
            with self.subTest(payload=payload):
                _, job, candidates = fixture()
                result = validate_facts(payload, job, candidates)
                self.assertFalse(result['accounting_complete'])
                self.assertFalse(result['accepted'])
                self.assertEqual(result['unresolved'][0]['candidate_id'], candidates[0]['candidate_id'])

    def test_invalid_caller_material_raises_value_error(self):
        for mutate in (
            lambda j, c: c.append(deepcopy(c[0])),
            lambda j, c: j['frozen_context']['candidate'].update(candidate_id='other'),
            lambda j, c: j['frozen_context']['sentences'][0].update(text='tampered'),
            lambda j, c: j['sentences'][0].update(char_start=True),
            lambda j, c: j['frozen_context'].update(sentences=['S999']),
            lambda j, c: c[0].update(anchor_sentence_ids=[]),
        ):
            payload, job, candidates = fixture()
            mutate(job, candidates)
            with self.assertRaises(ValueError):
                validate_facts(payload, job, candidates)

    def test_inputs_and_returned_values_do_not_alias(self):
        payload, job, candidates = fixture()
        before = deepcopy((payload, job, candidates))
        result = validate_facts(payload, job, candidates)
        self.assertEqual((payload, job, candidates), before)
        result['accepted'][0]['record']['values']['subject'] = 'changed locally'
        result['accepted'][0]['record']['anchor_sentence_ids'].append('S999')
        self.assertEqual((payload, job, candidates), before)


if __name__ == '__main__':
    unittest.main()
