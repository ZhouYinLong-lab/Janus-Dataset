from copy import deepcopy
import unittest

from two_stage_core import validate_discovery, validate_enrichment
from contract import FIELDS


def fixture():
    quote = 'Compound X did not degrade protein T after cotreatment with Z.'
    job = {'paper_id': 'P', 'job_id': 'J', 'source_sha256': 'fixture',
           'primary_units': [{'unit_id': 'P1', 'text': quote}],
           'context_units': [{'unit_id': 'P2', 'text': quote}]}
    c = {'candidate_id': 'C1', 'unit_id': 'P1', 'quote': quote,
         'compound_mentions': ['Compound X'], 'condition_mentions': ['Z'],
         'category': 'conditional_loss', 'notes': []}
    payload = {'paper_id': 'P', 'candidates': [c], 'coverage_notes': [],
               'no_candidate_reason': None}
    fields = dict.fromkeys(FIELDS)
    fields.update(compound='Compound X', target='protein T', perturbation='Z',
                  result_text='No degradation after cotreatment')
    record = {'domain': 'molecular_glue', 'negative_type': 'conditional_loss',
              'experimental_setting': 'special_condition', 'directness': 'explicit',
              'fields': fields, 'qualifiers': [], 'evidence': [
                  {'field': f, 'unit_id': 'P1', 'quote': quote}
                  for f in ['compound', 'target', 'perturbation', 'result_text']]}
    enrichment = {'paper_id': 'P', 'items': [{'candidate_id': 'C1', 'record': record}],
                  'unresolved': [], 'coverage_notes': []}
    return job, payload, enrichment


class TwoStageContractTests(unittest.TestCase):
    def test_discovery_valid(self):
        j, p, _ = fixture()
        self.assertEqual(len(validate_discovery(p, j)['accepted']), 1)

    def test_context_not_primary(self):
        j, p, _ = fixture(); p['candidates'][0]['unit_id'] = 'P2'
        self.assertEqual(len(validate_discovery(p, j)['rejected']), 1)

    def test_mention_must_be_in_quote(self):
        j, p, _ = fixture(); p['candidates'][0]['compound_mentions'] = ['invented']
        self.assertEqual(len(validate_discovery(p, j)['rejected']), 1)

    def test_false_quote(self):
        j, p, _ = fixture(); p['candidates'][0]['quote'] = 'This result was never reported.'
        self.assertEqual(len(validate_discovery(p, j)['accepted']), 0)

    def test_duplicate_candidate_rejected(self):
        j, p, _ = fixture(); p['candidates'] *= 2
        with self.assertRaises(ValueError): validate_discovery(p, j)

    def test_empty_is_valid_but_needs_reason(self):
        j, p, _ = fixture(); p['candidates'] = []
        with self.assertRaises(ValueError): validate_discovery(p, j)
        p['no_candidate_reason'] = 'Methods only.'
        self.assertEqual(validate_discovery(p, j)['accepted'], [])

    def test_linked_enrichment(self):
        j, p, e = fixture()
        r = validate_enrichment(e, j, p['candidates'])
        self.assertEqual(len(r['accepted']), 1)
        self.assertFalse(r['accepted'][0]['record']['ready_for_training'])

    def test_new_candidate_forbidden(self):
        j, p, e = fixture(); e['items'][0]['candidate_id'] = 'NEW'
        with self.assertRaises(ValueError): validate_enrichment(e, j, p['candidates'])

    def test_missing_candidate_forbidden(self):
        j, p, e = fixture(); e['items'] = []
        with self.assertRaises(ValueError): validate_enrichment(e, j, p['candidates'])

    def test_changed_anchor_quarantined(self):
        j, p, e = fixture()
        e['items'][0]['record']['evidence'][-1]['quote'] = 'did not degrade protein T'
        self.assertEqual(len(validate_enrichment(e, j, p['candidates'])['rejected']), 1)

    def test_missing_field_evidence_quarantined(self):
        j, p, e = fixture(); e['items'][0]['record']['fields']['assay'] = 'invented assay'
        self.assertEqual(len(validate_enrichment(e, j, p['candidates'])['rejected']), 1)

    def test_explicit_unresolved_allowed(self):
        j, p, e = fixture(); e['items'] = []
        e['unresolved'] = [{'candidate_id': 'C1', 'reason': 'Not an experimental result.'}]
        self.assertEqual(len(validate_enrichment(e, j, p['candidates'])['unresolved']), 1)
