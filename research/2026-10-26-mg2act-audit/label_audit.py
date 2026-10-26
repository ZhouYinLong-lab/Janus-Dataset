"""Recalculate released MG2Act codes; keep raw-assay validation distinct."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPER = 'https://www.biorxiv.org/content/10.64898/2026.08.08.739980v1.full.pdf'
SUPPLEMENT = 'https://www.biorxiv.org/content/biorxiv/early/2026/08/13/2026.08.08.739980/DC1/embed/media-1.pdf?download=true'


def sample_recalculation(rows):
    """Deterministic examples; do not manufacture unavailable raw measurements."""
    samples = []
    # The CSV exposes codes, not the original concentration. This distinction remains explicit.
    for r in sorted((r for r in rows if not r['Dmax_Sc']), key=lambda r: int(r['id']))[:2]:
        samples.append({'category': 'missing_Dmax_in_release', 'origin': 'released_benchmark',
                        'id': r['id'], 'target': r['PrimaryTarget'], 'split': r['split'],
                        'DC50_nM': '', 'Dmax_percent': '', 'potency_score': r['sDC'],
                        'penalty': '', 'reported_score': r['Score'],
                        'recalculated_score': float(r['sDC']),
                        'status': 'codes_match_raw_potency_assignment_unverifiable',
                        'source': f"MG_data/{r['split']}.csv row for id={r['id']}",
                        'note': 'Dmax missing; source DC50 or its curator-equivalent is not released.'})
    # Literal measurements read from SI Table 7, sorted by compound identifier within category.
    # These are prospective experimental examples, NOT the released train/val/test records.
    raw = [
        ('both_measured', 'YFC-208', 'CK1alpha', '51.56', 65.96, .501),
        ('both_measured', 'YFC-208', 'IKZF1', '33.64', 70.27, .501),
        ('inequality', 'YFC-102', 'CK1alpha', '>10000', 31.11, 0),
        ('inequality', 'YFC-106', 'CK1alpha', '>10000', 46.6, 0),
    ]
    for category, name, target, dc50, dmax, score in raw:
        potency = 0 if dc50.startswith('>') else .6  # all chosen finite values lie strictly inside 10-100 nM
        penalty = 1 if dmax < 40 else .67 if dmax < 60 else .33 if dmax < 80 else 0
        value = potency * (1 - .5 * penalty)
        samples.append({'category': category, 'origin': 'prospective_SI_Table7', 'id': name,
                        'target': target, 'split': 'not_in_released_splits', 'DC50_nM': dc50,
                        'Dmax_percent': dmax, 'potency_score': potency, 'penalty': penalty,
                        'reported_score': score, 'recalculated_score': value,
                        'status': 'matches_published_precision' if abs(value - score) < .0005 else 'mismatch',
                        'source': SUPPLEMENT + ' [S8 Table7]',
                        'note': 'Published rounded penalties .33/.67; means retained; uncertainty available in SI.'})
    save_csv('sample_recalculation.csv', samples)
    categories = [
        {'category': 'DC50_and_Dmax', 'selected': 2, 'availability': 'SI_Table7_raw_values', 'reason': 'Two finite-valued YFC-208 target records.'},
        {'category': 'DC50_only', 'selected': 2, 'availability': 'codes_only_raw_DC50_unresolved', 'reason': 'Earliest benchmark IDs with missing Dmax code; raw DC50 not released.'},
        {'category': 'Dmax_only', 'selected': 0, 'availability': 'not_identifiable', 'reason': 'No released flag differentiates measured vs curator-inferred potency.'},
        {'category': 'inequality', 'selected': 2, 'availability': 'SI_Table7_raw_values', 'reason': 'First two compound IDs with >10000 nM values.'},
        {'category': 'explicit_inactive', 'selected': 0, 'availability': 'not_identifiable', 'reason': 'Activity code 0 is not evidence that the original experiment was explicitly inactive.'},
        {'category': 'qualitative_only', 'selected': 0, 'availability': 'not_identifiable', 'reason': 'No qualitative-source provenance or equivalent-value inference rule is released.'},
    ]
    save_csv('sample_categories.csv', categories)
    return samples


def field_definitions():
    definitions = [
        ('activity', '0-5 ordinal potency code; sDC=activity/5 in all released rows', 'observed_release_relation', PAPER+' [p6,p23 for potency bins; column name mapping not documented]'),
        ('Dmax_Sc', 'Codes 1->0; 2->1/3; 3->2/3; 4->1 penalty; blank when unavailable', 'observed_release_relation', SUPPLEMENT+' [S6 Table5 for missingness; CSV code dictionary not documented]'),
        ('sDC', 'Normalized potency score, dimensionless 0 to 1, observed as activity/5', 'paper_rule_with_empirical_column_mapping', PAPER+' [p6,p23]'),
        ('pD', 'Dmax penalty observed as (Dmax_Sc-1)/3; missing code gives -1/3 placeholder', 'observed_release_relation', PAPER+' [p6,p23; published rounded penalties .33/.67]'),
        ('I', 'Observed availability indicator: 1 if Dmax_Sc exists, else 0', 'observed_release_relation', SUPPLEMENT+' [S6 Table5; column symbol not defined in paper]'),
        ('Score', 'Dimensionless composite potency/efficacy score; released calculation sDC*(1-0.5*pD*I)', 'paper_formula_with_empirical_column_mapping', SUPPLEMENT+' [S5 Table4; S8 Table7; S18 Table9]'),
    ]
    save_csv('field_definitions.csv', [{'field': f, 'definition': d, 'evidence_status': s, 'source': u} for f,d,s,u in definitions])


def save_json(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_csv(name, rows, columns=None):
    columns = columns or list(rows[0])
    with (ROOT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def load_rows():
    manifest = json.loads((ROOT / 'source_manifest.json').read_text(encoding='utf-8'))
    expected = {x['path']: x['sha256'] for x in manifest['files']}
    rows = []
    for split in ('train', 'val', 'test'):
        name = f'MG_data/{split}.csv'
        path = ROOT / 'local/upstream' / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]:
            raise ValueError(f'Frozen input hash mismatch: {name}')
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows.extend(dict(r, split=split, source_row=i) for i, r in enumerate(csv.DictReader(f), 2))
    return rows


def main():
    rows = load_rows()
    checks = []
    for r in rows:
        potency, penalty, available, actual = (float(r[k]) for k in ('sDC', 'pD', 'I', 'Score'))
        recalculated = potency * (1 - .5 * penalty * available)
        # These code-name relations are observed in the release, not a raw-assay curation rule.
        relations_ok = abs(potency - float(r['activity']) / 5) < 1e-8
        relations_ok &= available == int(bool(r['Dmax_Sc']))
        relations_ok &= abs(penalty - ((float(r['Dmax_Sc']) - 1) / 3 if r['Dmax_Sc'] else -1/3)) < 1e-8
        checks.append({k: r[k] for k in ('split', 'id', 'Name', 'PrimaryTarget', 'activity', 'Dmax_Sc', 'sDC', 'pD', 'I', 'Score')}
                      | {'source_row': r['source_row'], 'recalculated_from_codes': recalculated,
                         'absolute_difference': abs(actual - recalculated),
                         'encoded_formula_matches_at_1e-8': abs(actual - recalculated) < 1e-8,
                         'observed_code_relations_match': bool(relations_ok),
                         'raw_assay_validation': 'not_established_by_released_csv'})
    save_csv('label_recalculation.csv', checks)
    summary = {
        'input_rows': len(rows), 'split_counts': dict(Counter(r['split'] for r in rows)),
        'targets': len({r['PrimaryTarget'] for r in rows}),
        'score_zero_rows': sum(float(r['Score']) == 0 for r in rows),
        'score_zero_by_split': {s: sum(r['split'] == s and float(r['Score']) == 0 for r in rows) for s in ('train', 'val', 'test')},
        'dmax_code_present': sum(bool(r['Dmax_Sc']) for r in rows),
        'dmax_code_missing': sum(not r['Dmax_Sc'] for r in rows),
        'encoded_formula_mismatches': sum(not r['encoded_formula_matches_at_1e-8'] for r in checks),
        'observed_code_relation_mismatches': sum(not r['observed_code_relations_match'] for r in checks),
        'max_absolute_difference': max(r['absolute_difference'] for r in checks),
        'distributions': {k: dict(Counter(r[k] for r in rows)) for k in ('activity', 'Dmax_Sc', 'sDC', 'pD', 'I', 'Score')},
        'published_rule': 'ScoreDC50 * (1 - 0.5 * PenaltyDmax); omit Dmax penalty when Dmax unavailable',
        'observed_release_formula': 'sDC * (1 - 0.5 * pD * I)',
        'raw_assay_columns_present': False,
        'raw_assay_provenance_columns_present': False,
        'source_locations': {'potency_and_penalty_bins': 'article.pdf pp6,23; supplement.pdf S8,S18',
                             'alpha': 'supplement.pdf S5 Table4',
                             'dmax_missing': 'supplement.pdf S6 Table5'},
        'uncertainties': [
            'activity/Dmax_Sc/sDC/pD/I CSV names have no explicit published data dictionary; their algebraic relations are verified empirically.',
            'Methods p23 says curators inferred equivalent DC50 values if unreported; row-specific inference criteria and input evidence are not provided in the release.',
            'Published bin endpoints overlap at exact threshold values; do not select a boundary convention without original source or code.',
            'Paper uses rounded penalties .33/.67; released codes use thirds; keep this distinction for raw-to-score reproduction.',
            'No general mapping from non-significant, undetected, or qualitative no-degradation prose to Score is specified.',
            'Score zero is a potency-score category, not an assertion of zero measured degradation.'
        ]}
    save_json('label_summary.json', summary)
    field_definitions()
    sample_recalculation(rows)
    print(json.dumps({k: summary[k] for k in ('input_rows', 'split_counts', 'score_zero_rows', 'dmax_code_missing', 'encoded_formula_mismatches', 'max_absolute_difference')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
