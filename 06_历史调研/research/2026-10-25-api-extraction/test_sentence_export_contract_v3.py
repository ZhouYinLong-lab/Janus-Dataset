"""Offline checks for the sentence export evidence/coverage contract."""
from pathlib import Path
import tempfile
import unittest

import sentence_acceptance
import sentence_export


class SentenceExportContractTests(unittest.TestCase):
    def test_duplicate_raw_mentions_merge_only_in_evidence_layer(self):
        rows = [
            {'record_key': 'k', 'paper_id': 'p', 'values': {'endpoint': 'x'},
             'sources': [{'task_id': 'a'}]},
            {'record_key': 'k', 'paper_id': 'p', 'values': {'endpoint': 'x'},
             'sources': [{'task_id': 'b'}]},
        ]
        evidence = sentence_export._merge_evidence_records(rows)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]['raw_observation_count'], 2)
        self.assertEqual(evidence[0]['source_occurrence_count'], 2)
        merged, conflicts = sentence_acceptance._coalesce_records(rows)
        self.assertEqual(set(merged), {'k'})
        self.assertEqual(conflicts, [])

    def test_same_key_conflicting_content_is_not_silently_merged(self):
        rows = [
            {'record_key': 'k', 'paper_id': 'p', 'values': {'endpoint': 'x'}, 'sources': []},
            {'record_key': 'k', 'paper_id': 'p', 'values': {'endpoint': 'y'}, 'sources': []},
        ]
        _, conflicts = sentence_acceptance._coalesce_records(rows)
        self.assertEqual(conflicts, ['k'])

    def test_input_gap_distinguishes_absent_source_from_parse_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source.xml'
            source.write_text('<article/>', encoding='utf-8')
            kind, _ = sentence_export._input_gap_classification({'source_path': str(source),
                                                                   'input_error': 'no_scannable_body_sentences'})
            self.assertEqual(kind, 'parse_or_chunk_failure')
        kind, reason = sentence_export._input_gap_classification({'source_path': '',
                                                                   'input_error': 'not_downloaded'})
        self.assertEqual((kind, reason), ('fulltext_missing', 'source_not_available'))


if __name__ == '__main__':
    unittest.main()
