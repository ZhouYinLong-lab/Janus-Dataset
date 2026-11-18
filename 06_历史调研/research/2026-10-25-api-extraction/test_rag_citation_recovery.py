import json
import unittest

from rag_citation_recovery import repair


class CitationAliasTests(unittest.TestCase):
    def envelope(self, citations):
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(
            {'answer': 'Answer unchanged', 'uncertainty': '', 'citations': citations})}}]}

    def test_unique_supplied_alias(self):
        p, changes = repair(self.envelope(['raw:B1:abc']),
                            {'evidence_ids': ['raw:B1:abc:0:900']})
        self.assertEqual(p['answer'], 'Answer unchanged')
        self.assertEqual(p['citations'], ['raw:B1:abc:0:900'])
        self.assertEqual(len(changes), 1)

    def test_multiple_windows_refused(self):
        with self.assertRaises(ValueError):
            repair(self.envelope(['raw:B1:abc']),
                   {'evidence_ids': ['raw:B1:abc:0:1800', 'raw:B1:abc:1500:2100']})

    def test_invented_source_refused(self):
        with self.assertRaises(ValueError):
            repair(self.envelope(['raw:B1:other']), {'evidence_ids': ['raw:B1:abc:0:900']})

    def test_literal_empty_only_without_evidence(self):
        payload, _ = repair(self.envelope(['[]']), {'evidence_ids': []})
        self.assertEqual(payload['citations'], [])
        with self.assertRaises(ValueError):
            repair(self.envelope(['[]']), {'evidence_ids': ['raw:B1:abc:0:900']})

    def test_card_prefix_only_with_complete_identity(self):
        payload, _ = repair(self.envelope(['B1:abc']), {'evidence_ids': ['card:B1:abc']})
        self.assertEqual(payload['citations'], ['card:B1:abc'])
        with self.assertRaises(ValueError):
            repair(self.envelope(['B1']), {'evidence_ids': ['card:B1:abc']})


if __name__ == '__main__':
    unittest.main()
