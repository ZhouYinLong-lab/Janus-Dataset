"""Reproduce the paper's 73-row fine-test membership as flags, not a new split."""
from collections import defaultdict
import json

from label_audit import ROOT, save_csv, save_json
from overlap_audit import load_benchmark


def main():
    rows, _ = load_benchmark(ROOT / 'local/upstream/MG_data', ROOT / 'source_manifest.json')
    known = defaultdict(set)
    for r in rows:
        if r['split'] in ('train', 'val'):
            known[r['canonical_isomeric_smiles']].add(float(r['Score']))
    flags = []
    for r in rows:
        if r['split'] != 'test':
            continue
        scores = known[r['canonical_isomeric_smiles']]
        same_score = float(r['Score']) in scores
        # SI S6: retain molecules showing activity variance in train/validation.
        excluded = len(scores) == 1 and same_score
        flags.append({'benchmark_uid': r['benchmark_uid'], 'id': r['benchmark_id'],
                      'target': r['target_name'], 'Score': r['Score'],
                      'molecule_seen_trainval': bool(scores),
                      'distinct_trainval_scores': sorted(scores),
                      'same_molecule_score_seen_trainval': same_score,
                      'excluded_by_published_constant_activity_rule': excluded,
                      'included_in_reproduced_fine_test': not excluded})
    save_csv('benchmark_test_flags.csv', flags)
    summary = {'test_rows': len(flags), 'molecule_seen_trainval': sum(r['molecule_seen_trainval'] for r in flags),
               'same_molecule_score_seen_trainval': sum(r['same_molecule_score_seen_trainval'] for r in flags),
               'constant_activity_rows_excluded': sum(r['excluded_by_published_constant_activity_rule'] for r in flags),
               'fine_test_reproduced': sum(r['included_in_reproduced_fine_test'] for r in flags),
               'paper_fine_test_rows': 73,
               'rule_source': 'MG2Act Supplementary Information S6 Table6: exclude identical-activity molecules across train/validation, retain molecules showing activity variance.',
               'interpretation': 'These flags reproduce author protocol; they do not establish independent paper/assay provenance.'}
    save_json('test_protocol_summary.json', summary)
    if summary['fine_test_reproduced'] != summary['paper_fine_test_rows']:
        raise ValueError('Published fine-test membership count not reproduced')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
