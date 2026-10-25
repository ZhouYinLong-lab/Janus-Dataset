from copy import deepcopy
import unittest
from recover_citations import align


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
