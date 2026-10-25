import unittest
from batch_contract import enrichment
from test_two_stage import fixture


class SemanticGuardTests(unittest.TestCase):
    def test_qualitative_inactivity_not_zero(self):
        job, discovery, e = fixture()
        e['items'][0]['record']['negative_type'] = 'reported_zero'
        r = enrichment(e, job, discovery['candidates'])
        self.assertEqual(len(r['accepted']), 0)
        self.assertIn('qualitative_result_is_not_measured_zero', r['rejected'][0]['errors'])

    def test_labeling_not_baseline_absence(self):
        job, discovery, e = fixture(); record = e['items'][0]['record']
        record['negative_type'] = 'target_not_detected'; record['fields']['endpoint'] = 'ABPP labeling'
        record['evidence'].append(dict(record['evidence'][0], field='endpoint'))
        r = enrichment(e, job, discovery['candidates'])
        self.assertIn('assay_response_is_not_baseline_target_absence', r['rejected'][0]['errors'])

    def test_generic_activity_not_degradation_endpoint(self):
        job, discovery, e = fixture()
        quote = 'Compound X showed decreased activity after cotreatment with Z.'
        job['primary_units'][0]['text'] = quote; discovery['candidates'][0]['quote'] = quote
        record = e['items'][0]['record']; record['fields']['endpoint'] = 'degradation potency'
        for item in record['evidence']: item['quote'] = quote
        record['evidence'].append(dict(record['evidence'][0], field='endpoint'))
        r = enrichment(e, job, discovery['candidates'])
        self.assertIn('degradation_endpoint_not_explicit_in_endpoint_evidence', r['rejected'][0]['errors'])
