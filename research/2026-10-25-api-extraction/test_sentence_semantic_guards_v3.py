"""Result-strength and condition-revision regressions using source sentences."""
import unittest

from facts_v3 import FIELDS
from sentence_v3 import index_document
import sentence_workflow as workflow


def fact(text, observation, outcome, subject='Compound A', endpoint='protein degradation'):
    sentences = index_document({'paper_id': 'P', 'source_sha256': 'synthetic-source',
        'units': [{'unit_id': 'U', 'kind': 'body_paragraph', 'section': 'Results', 'text': text}]})
    sid = sentences[0]['sentence_id']
    candidate = {'candidate_id': 'C', 'sentence_ids': [sid], 'anchor_sentence_ids': [sid]}
    job = {'paper_id': 'P', 'doi': None, 'source_sha256': 'synthetic-source',
           'sentences': sentences, 'active_stage': 'facts',
           'frozen_context': {'candidate': candidate, 'sentences': sentences}}
    values = dict.fromkeys(FIELDS)
    values.update(subject=subject, endpoint=endpoint, observation=observation)
    payload = {'status': 'observations', 'reason': None, 'observations': [{
        'values': values, 'outcome_type': outcome,
        'evidence': {f: [sid] if values[f] else [] for f in FIELDS}}]}
    return workflow.validate_response(payload, job, [candidate])['accepted'][0]['record'], job


class SemanticGuardTests(unittest.TestCase):
    def test_no_improvement_variants_cannot_become_no_effect(self):
        for text in ('Compound A failed to enhance degradation.',
                     'Compound A showed no improvement in degradation.',
                     'Compound A did not significantly increase degradation.'):
            with self.subTest(text=text):
                row, _ = fact(text, 'no degradation', 'not_observed')
                self.assertEqual(row['record_status'], 'quarantine')

    def test_qualitative_absence_is_not_numeric_zero(self):
        for text in ('No metastases were observed.', 'Expression was completely abrogated.'):
            with self.subTest(text=text):
                row, _ = fact(text, text, 'reported_zero')
                self.assertEqual(row['record_status'], 'semantic_pending')

    def test_zero_dose_or_time_cannot_support_zero_readout(self):
        row, _ = fact('Compound A was tested at 0 nM for 0 hours; no degradation was observed.',
                      '0% degradation', 'reported_zero')
        self.assertEqual(row['record_status'], 'semantic_pending')

    def test_explicit_zero_still_requires_object_and_readout_review(self):
        row, _ = fact('Compound A caused 0% degradation.', '0% degradation', 'reported_zero')
        self.assertEqual(row['record_status'], 'semantic_pending')

    def test_nonzero_decimal_cannot_supply_numeric_zero(self):
        for number in ('0.5', '10.0', '100'):
            with self.subTest(number=number):
                row, _ = fact(f'Compound A caused {number}% degradation.', '0% degradation', 'reported_zero')
                self.assertEqual(row['record_status'], 'semantic_pending')

    def test_zero_in_another_readout_cannot_supply_degradation_zero(self):
        row, _ = fact('Compound A caused 0% inhibition but 50% degradation.',
                      '0% degradation', 'reported_zero')
        self.assertEqual(row['record_status'], 'semantic_pending')

    def test_zero_ranges_units_and_other_objects_stay_pending(self):
        for text in ('Compound A degradation was 0-50%.',
                     'Compound A degradation was 0 to 50%.',
                     'Compound A degradation was 0,5%.',
                     'Compound A degradation was 0 nM.',
                     'Protein B showed 0% degradation but protein A showed 50%.'):
            with self.subTest(text=text):
                row, _ = fact(text, '0% degradation', 'reported_zero')
                self.assertEqual(row['record_status'], 'semantic_pending')

    def revise(self, subject, endpoint):
        row, job = fact('Compound A did not degrade protein T.', 'did not degrade protein T',
                        'not_observed', subject=subject, endpoint=None)
        group = dict(job['frozen_context'], records=[row], requested_record_ids=[row['record_key']])
        values = dict.fromkeys(workflow.CONDITION_FIELDS)
        values['endpoint_resolution'] = endpoint
        payload = {'items': [{'record_id': row['record_key'], 'values': values,
                    'evidence': {f: [job['sentences'][0]['sentence_id']] if values[f] else []
                                 for f in workflow.CONDITION_FIELDS}}]}
        return workflow.validate_conditions(payload, dict(job, frozen_context=group))['accepted'][0]['record']

    def test_endpoint_resolution_does_not_clear_unknown_subject(self):
        self.assertEqual(self.revise('unknown', 'protein degradation')['record_status'], 'semantic_pending')

    def test_unknown_or_generic_resolution_cannot_become_usable(self):
        for endpoint in ('unknown', 'activity', 'potency', 'EC50'):
            with self.subTest(endpoint=endpoint):
                row = self.revise('Compound A', endpoint)
                self.assertEqual(row['record_status'], 'semantic_pending')
                self.assertTrue(row['endpoint_verification_required'])

    def test_resolved_core_can_become_usable(self):
        self.assertEqual(self.revise('Compound A', 'protein degradation')['record_status'], 'core_usable')


if __name__ == '__main__':
    unittest.main()
