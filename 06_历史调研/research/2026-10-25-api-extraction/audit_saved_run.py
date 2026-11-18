"""Offline audit statistics with explicit human/assistant adjudication inputs."""
import argparse
from collections import Counter
from pathlib import Path

from corpus import normal, read, save, sha


def audit(workspace, annotation_paths, out):
    w, out = Path(workspace), Path(out)
    state, manifest = read(w/'candidate_state.json'), read(w/'manifest.json')
    reference = read(w/'acceptance_reference.json')
    decisions = {}
    for path in annotation_paths:
        for paper in read(path)['papers']:
            for item in paper['candidates']:
                key = (item['job_id'], item['candidate_id'])
                if key in decisions:
                    raise ValueError('Duplicate adjudication')
                decisions[key] = dict(item, paper_id=paper['paper_id'])
    all_candidates, scanned, job_counts = [], {}, Counter()
    for entry in state['tasks'].values():
        if entry['stage'] != 'discovery' or entry['status'] != 'complete':
            continue
        jid = entry['job_id']
        job = read(w/'jobs'/f'{jid}.json')
        pid = job['paper_id']
        job_counts[pid] += 1
        scanned.setdefault(pid, []).extend(job['primary_units'])
        for destination in ('accepted', 'rejected'):
            for value in read(w/entry['result_path'])[destination]:
                candidate = value.get('candidate', value)
                key = (jid, candidate.get('candidate_id'))
                if key not in decisions:
                    raise ValueError('Candidate missing content adjudication: ' + str(key))
                annotation = decisions.pop(key)
                if annotation['decision'] not in {'supported', 'partial', 'incorrect', 'uncertain'}:
                    raise ValueError('Invalid audit decision')
                all_candidates.append(dict(annotation, raw_discovery_destination=destination,
                    unit_id=candidate.get('unit_id'), mechanical_errors=value.get('errors', [])))
    if decisions:
        raise ValueError('Annotations contain candidates absent from outputs')
    rows, source_summary = [], []
    core_ids = {case['id'] for case in reference.get('cases', []) if case.get('core_case')}
    for p in reference['papers']:
        pid = p['paper_id']
        doc = read(w/'documents'/f'{pid}.json')
        body = {u['unit_id']: u for u in doc['units'] if u['kind'] == 'body_paragraph'}
        units = scanned.get(pid, [])
        full_units = {u['unit_id'] for u in units if not u.get('parent_unit_id')}
        slices = {}
        for u in units:
            if u.get('parent_unit_id'):
                slices.setdefault(u['parent_unit_id'], []).append((u['char_start'], u['char_end']))
        for uid, spans in slices.items():
            end = 0
            for start, stop in sorted(spans):
                if start > end:
                    break
                end = max(end, stop)
            if uid in body and end >= len(body[uid]['text']):
                full_units.add(uid)
        matches, partials = set(), set()
        for candidate in all_candidates:
            if candidate['paper_id'] == pid:
                if candidate['decision'] == 'supported':
                    matches.update(candidate.get('matched_reference_ids', []))
                elif candidate['decision'] == 'partial':
                    partials.update(candidate.get('matched_reference_ids', []))
                partials.update(candidate.get('partial_reference_ids', []))
        for ref in p['negatives']:
            covered = ref['unit_id'] in full_units or any(
                normal(ref['quote']) in normal(u['text']) for u in units)
            status = ('unprocessed' if not covered else 'matched' if ref['id'] in matches else
                      'partial' if ref['id'] in partials else 'missed')
            rows.append({'paper_id': pid, 'reference_id': ref['id'], 'unit_id': ref['unit_id'],
                         'core_case': ref['id'] in core_ids, 'status': status})
        selected = [r for r in rows if r['paper_id'] == pid]
        source_summary.append({'paper_id': pid, 'body_units_total': len(body),
            'fully_scanned_body_units': len(full_units), 'completed_discovery_jobs': job_counts[pid],
            'reference_status': dict(Counter(r['status'] for r in selected))})
    counts = Counter(c['decision'] for c in all_candidates)
    coverage = Counter(r['status'] for r in rows)
    core = Counter(r['status'] for r in rows if r['core_case'])
    def recall(c):
        denominator = sum(c[k] for k in ('matched', 'partial', 'missed'))
        return c['matched']/denominator if denominator else None
    summary = {'reviewer_kind': 'assistant_offline_source_review', 'expert_gold': False,
        'reference_sha256': sha(w/'acceptance_reference.json'),
        'input_manifest_sha256': sha(w/'manifest.json'), 'candidate_count': len(all_candidates),
        'candidate_decisions': dict(counts), 'reference_coverage': dict(coverage),
        'core_reference_coverage': dict(core), 'strict_discovery_precision': counts['supported']/len(all_candidates)
            if all_candidates else None, 'strict_scanned_reference_recall': recall(coverage),
        'strict_scanned_core_reference_recall': recall(core),
        'sources': source_summary,
        'scope': 'Returned discovery candidates and references visible in successful discovery requests; '
                 'unprocessed text is excluded from recall, partial matches excluded from strict numerator'}
    save(out/'discovery_content_audit.json', all_candidates)
    save(out/'reference_coverage.json', rows)
    save(out/'content_audit_summary.json', summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--annotations', required=True, nargs='+', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    print(audit(a.workspace, a.annotations, a.out))
