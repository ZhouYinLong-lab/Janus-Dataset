from copy import deepcopy
import unittest
from recover_citations import align, bind_anchor


class CitationRecoveryTests(unittest.TestCase):
    def test_unique_quote_relinks_id_without_changing_values(self):
        r = {'fields': {'compound': 'X'}, 'evidence': [
            {'field': 'compound', 'unit_id': 'WRONG', 'quote': 'Compound X did not degrade T.'}]}
        original = deepcopy(r)
        fixed, changes = align(r, [{'unit_id': 'P1', 'text': 'Compound X did not degrade T.'}])
        self.assertEqual(fixed['fields'], original['fields'])
        self.assertEqual(fixed['evidence'][0]['unit_id'], 'P1')
        self.assertEqual(r, original)
        self.assertEqual(len(changes), 1)

    def test_ambiguous_quote_not_relinked(self):
        r = {'evidence': [{'field': 'result_text', 'unit_id': 'WRONG', 'quote': 'No effect was detected.'}]}
        fixed, changes = align(r, [{'unit_id': uid, 'text': 'No effect was detected.'} for uid in ['P1', 'P2']])
        self.assertEqual(changes, [])
        self.assertEqual(fixed, r)

    def test_missing_field_evidence_not_invented(self):
        r = {'fields': {'compound': 'X'}, 'evidence': []}
        self.assertEqual(align(r, [{'unit_id': 'P1', 'text': 'Compound X did not degrade T.'}]), (r, []))

    def test_literal_result_can_bind_verified_discovery_anchor(self):
        quote = 'Compound X did not degrade protein T under the tested conditions.'
        r = {'fields': {'result_text': 'did not degrade protein T'}, 'evidence': []}
        before = deepcopy(r)
        fixed, changes = bind_anchor(r, {'unit_id': 'P1', 'quote': quote},
                                     [{'unit_id': 'P1', 'text': quote}])
        self.assertEqual(r, before)
        self.assertEqual(fixed['fields'], r['fields'])
        self.assertEqual(fixed['evidence'], [{'field': 'result_text', 'unit_id': 'P1', 'quote': quote}])
        self.assertEqual(len(changes), 1)
        self.assertEqual(bind_anchor(fixed, {'unit_id': 'P1', 'quote': quote},
                                     [{'unit_id': 'P1', 'text': quote}]), (fixed, []))

    def test_no_anchor_for_paraphrase_wrong_source_or_other_missing_fields(self):
        quote = 'Compound X did not degrade protein T.'
        anchor = {'unit_id': 'P1', 'quote': quote}
        primary = [{'unit_id': 'P1', 'text': quote}]
        for r in [{'fields': {'result_text': 'Compound X completely eliminated protein T.'}, 'evidence': []},
                  {'fields': {'compound': 'X'}, 'evidence': []},
                  {'fields': {'result_text': 'T'}, 'evidence': []}]:
            self.assertEqual(bind_anchor(r, anchor, primary), (r, []))
        r = {'fields': {'result_text': quote}, 'evidence': []}
        self.assertEqual(bind_anchor(r, anchor, []), (r, []))
        self.assertEqual(bind_anchor(r, anchor, [{'unit_id': 'P1', 'text': 'An unrelated experiment.'}]), (r, []))
        self.assertEqual(bind_anchor(r, None, primary), (r, []))
