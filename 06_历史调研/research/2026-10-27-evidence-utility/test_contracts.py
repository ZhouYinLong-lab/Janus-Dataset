import copy
from pathlib import Path
import tempfile
import unittest

from common import assign_splits, read, sha, verify, write
from prepare import prepare


def fixture(root, n=12):
    """Invented experiments only; never a scientific benchmark."""
    root = Path(root)
    release, ws = root / 'release', root / 'ws'
    records, papers, supplements = [], [], []
    for i in range(n):
        pid = 'SYNTHETIC_' + str(i)
        text = f'Synthetic compound X{i} did not reduce synthetic protein Y{i} at 1 uM for 4 h.'
        positive = f'Synthetic compound P{i} reduced synthetic protein Y{i} at 1 uM for 4 h.'
        background = f'Synthetic instrument I{i} was calibrated using synthetic standard Z{i}.'
        source = root / (pid + '.txt')
        source.write_text('\n'.join([text, positive, background]), encoding='utf-8')
        source_sha = sha(source)
        units = [{'unit_id': pid + ':' + str(j), 'kind': 'body_paragraph', 'text': t}
                 for j, t in enumerate([text, positive, background])]
        doc = {'paper_id': pid, 'source_path': str(source), 'source_sha256': source_sha, 'units': units}
        write(ws / 'documents' / (pid + '.json'), doc)
        papers.append({'paper_id': pid, 'doi': '10.0000/synthetic' + str(i)})
        rec = {'paper_id': pid, 'doi': papers[-1]['doi'], 'source_sha256': source_sha,
               'record_key': 'record' + str(i), 'original_quote': text,
               'values': {'subject': 'X' + str(i), 'target': 'Y' + str(i), 'endpoint': 'protein',
                          'observation': 'did not reduce', 'scope_condition': '1 uM, 4 h'},
               'outcome_type': 'not_observed', 'content_decision': 'reliable',
               'review_kind': 'synthetic_test_only', 'ready_for_training': True,
               'field_evidence': [{'unit_id': pid + ':0', 'quote': text, 'char_start': 0, 'char_end': len(text)}],
               'sources': [{'task_id': 'synthetic-task-' + str(i), 'response_sha256': 'f' * 64}]}
        records.append(rec)
        for j, kind in [(1, 'positive'), (2, 'background')]:
            supplements.append({'evidence_id': kind + str(i), 'paper_id': pid, 'doi': papers[-1]['doi'],
                                'source_sha256': source_sha, 'kind': kind, 'text': units[j]['text'],
                                'quote': units[j]['text'], 'unit_id': units[j]['unit_id'],
                                'char_start': 0, 'char_end': len(units[j]['text']),
                                'review_status': 'reliable', 'review_kind': 'synthetic_test_only',
                                'training_allowed': True})
    write(ws / 'manifest.json', {'papers': papers})
    write(release / 'acceptance_report.json', {'acceptance_passed': True, 'blockers': []})
    write(release / 'reliable_evidence.json', records)
    write(root / 'supplements.json', supplements)
    return release, ws, root / 'supplements.json'


class Contracts(unittest.TestCase):
    def test_admission_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, ws, sup = fixture(root)
            stats = prepare(release, [ws], root / 'bundle', sup)
            self.assertEqual(stats['admitted'], 36)
            self.assertEqual(stats['generation_requests'], 0)
            self.assertTrue(stats['training_material_ready'])
            verify(root / 'bundle')
            rows = read(root / 'bundle/evidence.json')
            sources = {}
            for r in rows:
                sources.setdefault(r['source_sha256'], set()).add(r['split'])
            self.assertTrue(all(len(v) == 1 for v in sources.values()))
            rows[0]['content_decision'] = 'excluded'
            write(root / 'bundle/evidence.json', rows)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                verify(root / 'bundle')

    def test_reject_offsets_and_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, ws, _ = fixture(root, 1)
            rows = read(release / 'reliable_evidence.json')
            rows[0]['field_evidence'][0]['char_start'] = 1
            write(release / 'reliable_evidence.json', rows)
            with self.assertRaisesRegex(ValueError, 'offset'):
                prepare(release, [ws], root / 'out')
            write(release / 'acceptance_report.json', {'acceptance_passed': False})
            with self.assertRaisesRegex(ValueError, 'acceptance'):
                prepare(release, [ws], root / 'out')

    def test_pending_never_becomes_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, ws, _ = fixture(root, 2)
            rows = read(release / 'reliable_evidence.json')
            rows[0]['content_decision'] = 'pending'
            write(release / 'reliable_evidence.json', rows)
            result = prepare(release, [ws], root / 'out')
            self.assertEqual(result['admitted'], 1)
            self.assertEqual(result['held'], 1)
            self.assertFalse(result['training_material_ready'])

    def test_aliases_and_duplicates_cannot_cross_splits(self):
        rows = [{'paper_id': 'p' + str(i), 'doi': '10.1/' + str(i),
                 'source_sha256': str(i), 'evidence_id': str(i), 'text': 'different ' + str(i)}
                for i in range(8)]
        rows[1]['doi'] = 'https://doi.org/10.1/0'
        rows[2]['source_sha256'] = rows[1]['source_sha256']
        rows[3]['experiment_id'] = rows[2]['experiment_id'] = 'same-experiment'
        rows[4]['text'] = rows[3]['text']
        original = copy.deepcopy(rows)
        self.assertEqual(assign_splits(rows), 4)
        self.assertEqual(len({r['split'] for r in rows[:5]}), 1)
        assign_splits(original)
        self.assertEqual(rows, original)

    def test_explicit_holdout_plan_and_source_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, ws, sup = fixture(root)
            write(root / 'splits.json', {'10.0000/synthetic0': 'test'})
            prepare(release, [ws], root / 'bundle', sup, split_plan=root / 'splits.json')
            self.assertTrue(all(r['split'] == 'test' for r in read(root / 'bundle/evidence.json')
                                if r['doi'] == '10.0000/synthetic0'))
            (root / 'SYNTHETIC_0.txt').write_text('Changed content', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                verify(root / 'bundle')


if __name__ == '__main__':
    unittest.main()
