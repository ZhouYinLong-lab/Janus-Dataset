"""Source-anchor coverage against non-expert reference; not semantic recall."""
import argparse
from collections import Counter
from pathlib import Path
import json

from corpus import normal, read, save, sha


def compare(workspace, reference_paths, out):
    workspace = Path(workspace); state = read(workspace / 'batch_state.json')
    references = [p for f in reference_paths for p in read(f)['papers']]
    discovered = []; scanned = set(); rows = []; per_paper = []
    for tid, e in state['tasks'].items():
        if e['stage'] != 'discovery' or e['status'] != 'complete': continue
        job = read(workspace / f'jobs/{e["job_id"]}.json')
        scanned.update(u.get('parent_unit_id', u['unit_id']) for u in job['primary_units'])
        if sha(workspace / e['result_path']) != e['result_sha256']: raise ValueError('Discovery changed')
        discovered.extend(read(workspace / e['result_path'])['accepted'])
    for p in references:
        file = workspace / f'documents/{p["paper_id"]}.json'
        if not file.exists(): continue
        doc = read(file); units = {u['unit_id']: u for u in doc['units'] if u['kind'] == 'body_paragraph'}
        paper_rows = []
        for c in p['candidates']:
            uid, quote = c['unit_id'], c['quote']
            valid = uid in units and normal(quote) in normal(units[uid]['text'])
            same_unit = [d for d in discovered if d['unit_id'].split(':chars:')[0] == uid]
            contained = any(normal(quote) in normal(d['quote']) or normal(d['quote']) in normal(quote) for d in same_unit)
            row = {'reference_id': c['candidate_id'], 'paper_id': p['paper_id'], 'unit_id': uid,
                   'tier': c.get('tier', c.get('layer', 'not_tiered')), 'reference_quote_valid': valid,
                   'unit_was_scanned': uid in scanned, 'unit_has_discovered_statement': bool(same_unit),
                   'quote_containment_match': contained,
                   'reference_quote': quote, 'candidate_ids_in_unit': [d['candidate_id'] for d in same_unit]}
            rows.append(row); paper_rows.append(row)
        per_paper.append({'paper_id': p['paper_id'], 'body_units': len(units),
            'body_units_scanned': sum(u in scanned for u in units), 'reference_candidates': len(paper_rows),
            'valid_reference_quotes': sum(r['reference_quote_valid'] for r in paper_rows),
            'reference_locations': len({r['unit_id'] for r in paper_rows}),
            'reference_locations_with_any_discovery': len({r['unit_id'] for r in paper_rows if r['unit_has_discovered_statement']}),
            'quote_containment_matches': sum(r['quote_containment_match'] and r['reference_quote_valid'] for r in paper_rows),
            'tiers': dict(Counter(r['tier'] for r in paper_rows))})
    summary = {'papers': per_paper, 'reference_candidates': len(rows),
               'reference_invalid_quotes': sum(not r['reference_quote_valid'] for r in rows),
               'reference_sha256': {str(p): sha(p) for p in reference_paths},
               'expert_gold': False, 'semantic_precision_or_recall': 'not_estimated',
               'interpretation': 'Paragraph overlap and literal quote containment only. Multiple endpoints per paragraph and scope-boundary references prevent treating these counts as semantic recall or independent experiments.'}
    save(Path(out) / 'reference_rows.json', rows); save(Path(out) / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True); p.add_argument('--references', nargs='+', required=True)
    p.add_argument('--out', required=True); a = p.parse_args()
    print(json.dumps(compare(a.workspace, a.references, a.out), ensure_ascii=False, indent=2))
