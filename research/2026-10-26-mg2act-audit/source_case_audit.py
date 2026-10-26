"""Compare selected, source-reviewed assay values without changing benchmark labels."""
import csv
import json
from pathlib import Path

from label_audit import ROOT, load_rows, save_csv


def potency_bin(nm):
    if nm in (1, 10, 100, 1000, 10000):
        return None  # author interval-boundary convention is not fully specified
    for cutoff, score in ((1, 1), (10, .8), (100, .6), (1000, .4), (10000, .2)):
        if nm < cutoff:
            return score
    return 0


def main():
    rows = {r['id']: r for r in load_rows()}
    inputs = json.loads((ROOT / 'source_readout_checks.json').read_text(encoding='utf-8'))
    mapping_file = ROOT / 'source_associations.csv'
    if not mapping_file.exists():
        mapping_file = ROOT / 'local/source_mapping/benchmark_provenance.csv'
    with mapping_file.open(encoding='utf-8-sig') as f:
        mappings = list(csv.DictReader(f))
    output = []
    for case in inputs['cases']:
        r = rows[case['benchmark_id']]
        links = [m for m in mappings if m['benchmark_id'] == r['id'] and
                 m['source_doi'] == case['source_doi'] and
                 m['compound_original_name'] == case['compound_original_name']]
        if not links:
            raise ValueError(f"Missing verified identity/source association for {r['id']}")
        dc, dm = case['original_DC50_nM'], case['original_Dmax_percent']
        score_dc = potency_bin(dc) if dc is not None else None
        penalty = (0 if dm > 80 else .33 if dm > 60 else .67 if dm > 40 else 1) if dm is not None and dm not in (40,60,80) else None
        source_score = score_dc * (1-.5*penalty) if score_dc is not None and penalty is not None else None
        item = {'benchmark_id': r['id'], 'split': r['split'], 'benchmark_name': r['Name'],
                'source_doi': case['source_doi'], 'source_locator': case['source_locator'],
                'source_DC50_nM': dc, 'source_Dmax_percent': dm,
                'potency_from_source_table': score_dc, 'released_sDC': r['sDC'],
                'released_Dmax_Sc': r['Dmax_Sc'], 'released_score': r['Score'],
                'hypothetical_score_using_source_table_values': source_score,
                'same_benchmark_assay_confirmed': False, 'finding': case['finding'],
                'source_url': case['source_url']}
        output.append(item)
    save_csv('source_readout_checks.csv', output)
    print(json.dumps({'cases': len(output), 'benchmark_labels_changed': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
