"""Offline regressions for endpoint scope, intervention direction and isolation."""
from copy import deepcopy
import unittest

from batch_contract import discovery, enrichment
from contract import FIELDS


MIXED_QUOTE = (
    'Compound X bound BRD4 in NanoBRET assays after 1 h at 1 μM, but did not '
    'induce BRD4 degradation after 24 h at 10 μM.'
)
UNCHANGED_QUOTE = (
    'RMND5B knockout had no effect on Compound X-induced BRD4 degradation.'
)
# Exact short clause from B149, source unit B149:76d321307b744131.
B149_INSENSITIVITY_QUOTE = 'the insensitivity of BRD4 degradation to RMND5B knockout'


def observation(quote=MIXED_QUOTE, negative_type='no_degradation', **values):
    fields = dict.fromkeys(FIELDS)
    fields.update(compound='Compound X', target='BRD4', endpoint='BRD4 degradation',
                  result_text='Compound X did not induce BRD4 degradation.')
    fields.update(values)
    job = {'paper_id': 'P', 'job_id': 'J', 'source_sha256': 'synthetic',
           'primary_units': [{'unit_id': 'P1', 'text': quote}], 'context_units': []}
    candidate = {'candidate_id': 'C1', 'unit_id': 'P1', 'quote': quote,
                 'compound_mentions': [], 'condition_mentions': [],
                 'category': 'uncertain', 'notes': []}
    record = {'domain': 'molecular_glue', 'negative_type': negative_type,
              'experimental_setting': 'special_condition' if fields['perturbation'] else 'unperturbed',
              'directness': 'explicit', 'fields': fields, 'qualifiers': [],
              'evidence': [{'field': f, 'unit_id': 'P1', 'quote': quote}
                           for f, value in fields.items() if value is not None]}
    payload = {'paper_id': 'P', 'items': [{'candidate_id': 'C1', 'record': record}],
               'unresolved': [], 'coverage_notes': []}
    return job, [candidate], payload


class ObservationScopeTests(unittest.TestCase):
    def check_observation(self, case, error=None):
        job, candidates, payload = case
        before = deepcopy(case)
        result = enrichment(payload, job, candidates)
        self.assertEqual(case, before, 'Validation must not mutate the source or input records')
        self.assertEqual(result['unresolved'], [])
        self.assertEqual(result['missing_candidate_ids'], [])
        self.assertTrue(result['accounting_complete'])
        self.assertEqual(result['semantic_review'], 'pending')
        self.assertFalse(result['ready_for_training'])
        if error:
            self.assertEqual(result['accepted'], [])
            self.assertEqual(len(result['rejected']), 1)
            self.assertEqual(result['rejected'][0]['errors'],
                             [error] if isinstance(error, str) else error)
        else:
            self.assertEqual(result['rejected'], [])
            self.assertEqual(len(result['accepted']), 1)
            record = result['accepted'][0]['record']
            self.assertEqual(record['semantic_review'], 'pending')
            self.assertFalse(record['ready_for_training'])
            self.assertIn({'field': 'result_text', 'unit_id': 'P1',
                           'quote': candidates[0]['quote']}, record['evidence'])
        return result

    def test_single_degradation_keeps_full_multi_endpoint_anchor(self):
        case = observation(treatment_time='24 h', tested_concentration='10 μM',
                           result_text=MIXED_QUOTE)
        case[2]['items'][0]['record']['qualifiers'] = [
            'Positive binding is context; its 1 h and 1 μM conditions are not shared.'
        ]
        self.check_observation(case)

    def test_single_binding_can_mention_positive_degradation_in_result(self):
        quote = ('Compound X showed no detectable BRD4 binding in NanoBRET assays '
                 'after 1 h at 1 μM, but induced BRD4 degradation after 24 h at 10 μM.')
        case = observation(quote, 'response_not_detected', endpoint='BRD4 binding',
                           assay='NanoBRET', treatment_time='1 h',
                           tested_concentration='1 μM', result_text=quote)
        case[2]['items'][0]['record']['qualifiers'] = [
            'Degradation is positive context; its 24 h and 10 μM conditions are not shared.'
        ]
        self.check_observation(case)

    def test_mixed_endpoint_or_assay_with_shared_conditions_is_quarantined(self):
        for selected in [dict(endpoint='BRD4 binding and degradation'),
                         dict(endpoint='ternary complex formation and BRD4 degradation'),
                         dict(endpoint='BRD4 degradation', assay='NanoBRET'),
                         dict(endpoint='BRD4 binding', assay='degradation assay'),
                         dict(endpoint=None, assay='binding and degradation assays')]:
            for condition in [dict(treatment_time='24 h'), dict(tested_concentration='10 μM'),
                              dict(perturbation='MG132'), dict(cell_line='HEK293')]:
                with self.subTest(selected=selected, condition=condition):
                    quote = MIXED_QUOTE + ' HEK293 cells were also treated with MG132.'
                    self.check_observation(observation(quote, **selected, **condition),
                                           'mixed_observation_endpoints_share_conditions')

    def test_mixed_endpoint_without_conditions_still_awaits_semantic_review(self):
        self.check_observation(observation(endpoint='BRD4 binding and degradation'))

    def test_single_endpoint_with_and_without_conditions(self):
        for conditions in [{}, dict(treatment_time='24 h', tested_concentration='10 μM')]:
            with self.subTest(conditions=conditions):
                self.check_observation(observation(**conditions))

    def test_ineffective_intervention_is_not_degradation_loss(self):
        for quote, perturbation in [
            (UNCHANGED_QUOTE, 'RMND5B'),
            ('RMND5B KO did not affect Compound X-induced BRD4 degradation.', 'RMND5B'),
            ('Knockout of RMND5B had no effect on BRD4 degradation by Compound X.', 'RMND5B'),
            ('RMND5B knock-out did not block Compound X-induced BRD4 degradation.', None),
            ('RMND5B knockout failed to inhibit Compound X-induced BRD4 degradation.', 'RMND5B'),
            ('RMND5B knockout did not affect the degradation of BRD4 by Compound X.', 'RMND5B'),
            ('MG132 did not block Compound X-induced BRD4 degradation.', 'MG132'),
        ]:
            for label in ['no_degradation', 'conditional_loss', 'no_significant_degradation']:
                with self.subTest(quote=quote, label=label):
                    self.check_observation(observation(quote, label, perturbation=perturbation),
                                           'ineffective_intervention_is_not_degradation_loss')

    def test_no_endpoint_does_not_hide_known_direction_inversion(self):
        self.check_observation(observation(UNCHANGED_QUOTE, endpoint=None, assay='Western blot'),
                               'ineffective_intervention_is_not_degradation_loss')

    def test_b149_original_insensitivity_clause_is_not_degradation_loss(self):
        for label in ['no_degradation', 'conditional_loss']:
            for perturbation in [None, 'RMND5B', 'RMND5B knockout']:
                with self.subTest(label=label, perturbation=perturbation):
                    self.check_observation(observation(
                        B149_INSENSITIVITY_QUOTE, label, compound=None, endpoint='degradation',
                        perturbation=perturbation, result_text=B149_INSENSITIVITY_QUOTE),
                        'ineffective_intervention_is_not_degradation_loss')

    def test_b149_noun_phrase_does_not_reject_another_target(self):
        quote = (B149_INSENSITIVITY_QUOTE + ' was observed, but Compound X did not '
                 'induce BRD2 degradation after RMND5B knockout.')
        self.check_observation(observation(quote, target='BRD2', endpoint='BRD2 degradation',
                                           perturbation='RMND5B knockout'))

    def test_b149_noun_phrase_does_not_reject_another_intervention(self):
        for perturbation, label, continuation in [
            ('MG132', 'conditional_loss', 'MG132 blocked Compound X-induced BRD4 degradation.'),
            ('RMND5A knockout', 'no_degradation',
             'Compound X did not induce BRD4 degradation after RMND5A knockout.'),
        ]:
            with self.subTest(perturbation=perturbation):
                quote = B149_INSENSITIVITY_QUOTE + ' was observed. ' + continuation
                self.check_observation(observation(quote, label, perturbation=perturbation))

    def test_insensitivity_of_binding_does_not_supply_degradation_direction(self):
        quote = ('The insensitivity of BRD4 binding to RMND5B knockout was observed. '
                 'Compound X did not induce BRD4 degradation.')
        self.check_observation(observation(quote, perturbation='RMND5B knockout'))

    def test_b149_mechanism_control_can_remain_uncertain(self):
        self.check_observation(observation(
            B149_INSENSITIVITY_QUOTE, 'uncertain', compound=None, perturbation='RMND5B knockout',
            result_text='BRD4 degradation was unaffected by RMND5B knockout.'))

    def test_ineffective_intervention_can_remain_uncertain_mechanism_control(self):
        result = self.check_observation(observation(
            UNCHANGED_QUOTE, 'uncertain', perturbation='RMND5B',
            result_text='RMND5B knockout did not affect Compound X-induced BRD4 degradation.'))
        self.assertFalse(result['accepted'][0]['record']['primary_candidate'])

    def test_ineffective_intervention_can_be_unresolved(self):
        job, candidates, payload = observation(UNCHANGED_QUOTE)
        payload['items'] = []
        payload['unresolved'] = [{'candidate_id': 'C1',
                                  'reason': 'Mechanism control: knockout did not affect degradation.'}]
        result = enrichment(payload, job, candidates)
        self.assertEqual(result['unresolved'], payload['unresolved'])
        self.assertEqual(result['rejected'], [])
        self.assertTrue(result['accounting_complete'])

    def test_intervention_that_blocks_degradation_is_conditional_loss(self):
        for intervention in ['MG132', 'RMND5B knockout']:
            with self.subTest(intervention=intervention):
                quote = f'{intervention} blocked Compound X-induced BRD4 degradation.'
                result = self.check_observation(observation(
                    quote, 'conditional_loss', perturbation=intervention,
                    result_text=quote))
                record = result['accepted'][0]['record']
                self.assertEqual(record['experimental_setting'], 'special_condition')
                self.assertEqual(record['fields']['perturbation'], intervention)

    def test_ko_mention_alone_is_not_rejected(self):
        quote = 'Compound X did not induce BRD4 degradation in RMND5B KO cells.'
        self.check_observation(observation(quote, perturbation='RMND5B KO'))

    def test_no_effect_on_binding_is_not_no_effect_on_degradation(self):
        quote = ('RMND5B knockout had no effect on BRD4 binding, but Compound X '
                 'did not induce BRD4 degradation.')
        self.check_observation(observation(quote, perturbation='RMND5B'))

    def test_no_effect_for_another_target_does_not_reject_selected_target(self):
        quote = ('RMND5B knockout had no effect on BRD2 degradation, but Compound X '
                 'did not induce BRD4 degradation.')
        self.check_observation(observation(quote, perturbation='RMND5B'))

    def test_no_effect_for_another_intervention_does_not_reject_actual_block(self):
        quote = (UNCHANGED_QUOTE + ' MG132 blocked Compound X-induced BRD4 degradation.')
        self.check_observation(observation(quote, 'conditional_loss', perturbation='MG132'))

    def test_unrecognised_intervention_wording_remains_pending(self):
        quote = 'Compound X-induced BRD4 degradation was insensitive to loss of RMND5B.'
        self.check_observation(observation(quote, perturbation='RMND5B'))

    def test_relative_weakening_is_not_zero_and_qualitative_results_are_not_zero(self):
        quote = 'Compound X induced weak but measurable BRD4 degradation.'
        self.check_observation(observation(quote, 'relative_weakening', result_text=quote))
        for quote in [quote, 'Compound X was inactive in the BRD4 degradation assay.',
                      'Compound X did not significantly induce BRD4 degradation.']:
            with self.subTest(quote=quote):
                self.check_observation(observation(quote, 'reported_zero'),
                                       'qualitative_result_is_not_measured_zero')

    def test_explicit_measured_zero_still_passes(self):
        quote = 'Compound X produced measured BRD4 degradation of Dmax = 0%.'
        self.check_observation(observation(quote, 'reported_zero', result_text=quote))

    def test_rejected_rows_do_not_affect_valid_neighbour_or_unresolved(self):
        cases = [observation(), observation(endpoint='binding and degradation', treatment_time='24 h'),
                 observation(B149_INSENSITIVITY_QUOTE, compound=None,
                             endpoint='degradation', perturbation='RMND5B knockout')]
        job, candidates, payload = deepcopy(cases[0])
        for index, (other_job, other_candidates, other_payload) in enumerate(cases[1:], 2):
            uid, cid = f'P{index}', f'C{index}'
            job['primary_units'].append(dict(other_job['primary_units'][0], unit_id=uid))
            candidates.append(dict(other_candidates[0], candidate_id=cid, unit_id=uid))
            item = deepcopy(other_payload['items'][0]); item['candidate_id'] = cid
            for evidence in item['record']['evidence']:
                evidence['unit_id'] = uid
            payload['items'].append(item)
        candidates.append(dict(candidates[0], candidate_id='C4'))
        payload['unresolved'] = [{'candidate_id': 'C4', 'reason': 'Core endpoint unclear.'}]
        result = enrichment(payload, job, candidates)
        self.assertEqual([item['candidate_id'] for item in result['accepted']], ['C1'])
        self.assertEqual([item['candidate_id'] for item in result['rejected']], ['C2', 'C3'])
        self.assertEqual(result['unresolved'], payload['unresolved'])
        self.assertTrue(result['accounting_complete'])
        self.assertEqual(result['missing_candidate_ids'], [])

    def test_short_field_values_need_full_quotes_and_anchor_stays_exact(self):
        quote = 'HF did not induce BRD4 degradation.'
        job, candidates, payload = observation(quote, compound='HF')
        self.check_observation((job, candidates, payload))
        payload['items'][0]['record']['evidence'][0]['quote'] = 'HF'
        self.check_observation((job, candidates, payload),
                               ['invalid_quote', 'ungrounded_field:compound'])
        payload['items'][0]['record']['evidence'][0]['quote'] = quote
        payload['items'][0]['record']['evidence'][-1]['quote'] = 'did not induce BRD4 degradation'
        self.check_observation((job, candidates, payload), 'missing_original_discovery_anchor')

    def test_discovery_preserves_full_multi_endpoint_anchor(self):
        job, candidates, _ = observation()
        payload = {'paper_id': 'P', 'candidates': candidates, 'coverage_notes': [],
                   'no_candidate_reason': None}
        result = discovery(payload, job)
        self.assertEqual(result['accepted'], candidates)
        self.assertEqual(result['rejected'], [])
        candidates[0]['quote'] = 'BRD4'
        self.assertIn('invalid_quote', discovery(payload, job)['rejected'][0]['errors'])


if __name__ == '__main__':
    unittest.main()
