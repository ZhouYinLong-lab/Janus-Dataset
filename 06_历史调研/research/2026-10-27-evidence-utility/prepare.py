"""Adapt reviewed sentence_v3 releases without generating labels or training."""
import argparse
from collections import Counter
from pathlib import Path

from common import (assign_splits, check_locator, digest, fresh, norm, read, seal,
                    sha, source_check, write)


def prepare(release, workspaces, out, supplements=None, seed=20261027, split_plan=None):
    release = Path(release)
    report = release / 'acceptance_report.json'
    evidence = release / 'reliable_evidence.json'
    audit = read(report)
    if audit.get('acceptance_passed') is not True or audit.get('blockers'):
        raise ValueError('Release content acceptance has not passed')
    inputs = [report, evidence]
    docs, raw = {}, []
    for ws in workspaces:
        ws = Path(ws)
        manifest = read(ws / 'manifest.json')
        inputs.append(ws / 'manifest.json')
        for paper in manifest['papers']:
            path = ws / 'documents' / (paper['paper_id'] + '.json')
            if not path.is_file():
                continue
            doc = read(path)
            units = source_check(doc)
            key = (paper['paper_id'], doc['source_sha256'])
            if key in docs:
                if docs[key][0]['units'] != doc['units']:
                    raise ValueError('Conflicting parsed documents')
                continue
            docs[key] = (doc, units)
            inputs.extend([path, Path(doc['source_path'])])
            for u in doc['units']:
                if u['kind'] not in {'body_paragraph', 'table', 'figure_caption'}:
                    continue
                # Entire units, never gold-locator selection or silent text cropping.
                raw.append({'evidence_id': 'raw:' + digest([key, u['unit_id']]),
                            'kind': 'raw', 'paper_id': paper['paper_id'], 'doi': paper.get('doi'),
                            'source_sha256': doc['source_sha256'], 'text': u['text'],
                            'unit_id': u['unit_id'], 'section': u.get('section'),
                            'locator': u.get('locator'), 'training_allowed': False})
    rows, held, duplicate_map = [], [], {}
    for r in read(evidence):
        reason = None
        if r.get('content_decision') != 'reliable':
            reason = 'not_content_reviewed_reliable'
        elif not r.get('review_kind'):
            reason = 'review_provenance_missing'
        elif (r.get('paper_id'), r.get('source_sha256')) not in docs:
            reason = 'matching_frozen_document_missing'
        elif not r.get('field_evidence') or not r.get('original_quote'):
            reason = 'source_locators_missing'
        if reason:
            held.append({'record_key': r.get('record_key'), 'reason': reason})
            continue
        _, units = docs[(r['paper_id'], r['source_sha256'])]
        for e in r['field_evidence']:
            check_locator(e, units)
        # original_quote newline-joins one anchor sentence per candidate span;
        # every segment must still be a literal substring of the frozen text.
        segments = [s for s in (r['original_quote'] or '').split('\n') if s.strip()]
        if not segments or not all(any(s in u['text'] for u in units.values()) for s in segments):
            raise ValueError('Original quote is not in the frozen source')
        # Two provenance classes are accepted and never conflated: API responses
        # carry response_sha256; subagent-written rows declare provenance_kind and
        # a worker/generation method. Missing both is still held out.
        sources = r.get('sources') or []
        if not sources or any(not s.get('task_id') for s in sources):
            held.append({'record_key': r.get('record_key'), 'reason': 'response_provenance_missing'})
            continue
        api_provenance = all(s.get('response_sha256') for s in sources)
        subagent_provenance = (r.get('provenance_kind') == 'subagent' and
                               all(s.get('worker_id') or s.get('generation_method') for s in sources))
        if not (api_provenance or subagent_provenance):
            held.append({'record_key': r.get('record_key'), 'reason': 'response_provenance_missing'})
            continue
        # Explicit curator decision governs admission; stale mechanical flags are preserved below.
        row = dict(r, evidence_id='recovered:' + r['record_key'], kind='negative',
                   text=render_record(r), training_allowed=r.get('ready_for_training') is True,
                   original_record=r)
        key = digest([r['source_sha256'], norm(r['original_quote']), r.get('values'), r.get('outcome_type')])
        if key in duplicate_map:
            previous = duplicate_map[key]
            previous.setdefault('duplicate_records', []).append(r)
            previous['training_allowed'] &= row['training_allowed']
        else:
            duplicate_map[key] = row
            rows.append(row)
    if supplements:
        inputs.append(Path(supplements))
        for row in read(supplements):
            if row.get('kind') not in {'positive', 'background', 'structured'}:
                raise ValueError('Supplement kind must be positive/background/structured')
            if row.get('review_status') != 'reliable' or not row.get('review_kind'):
                raise ValueError('Supplements need explicit content review')
            key = (row.get('paper_id'), row.get('source_sha256'))
            if key not in docs or not row.get('text') or not row.get('evidence_id'):
                raise ValueError('Supplement identity/source missing')
            check_locator(row, docs[key][1])
            for locator in row.get('field_evidence', []):
                check_locator(locator, docs[key][1])
            rows.append(dict(row, original_quote=row['quote']))
    if not rows:
        raise ValueError('No reviewed evidence admitted')
    ids = [r['evidence_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate evidence IDs')
    groups = assign_splits(rows, seed)
    if split_plan:
        from common import doi
        inputs.append(Path(split_plan))
        plan = {doi(k): v for k, v in read(split_plan).items()}
        if any(v not in {'train', 'val', 'test'} for v in plan.values()):
            raise ValueError('Split plan values must be train/val/test')
        overrides = {}
        for r in rows:
            requested = plan.get(doi(r.get('doi')))
            if requested:
                if r['group_id'] in overrides and overrides[r['group_id']] != requested:
                    raise ValueError('Conflicting split assignments within one connected source group')
                overrides[r['group_id']] = requested
        for r in rows:
            r['split'] = overrides.get(r['group_id'], r['split'])
    # Raw records use the split of their source, even when there are paper aliases.
    splits = {r['source_sha256']: (r['split'], r['group_id']) for r in rows}
    for r in raw:
        r['split'], r['group_id'] = splits.get(r['source_sha256'], ('retrieval_only', None))
    out = fresh(out)
    write(out / 'evidence.json', rows)
    write(out / 'raw.json', raw)
    write(out / 'admission_issues.json', held)
    summary = {'admitted': len(rows), 'held': len(held), 'independent_source_groups': groups,
               'kind_counts': dict(Counter(r['kind'] for r in rows)),
               'split_counts': dict(Counter(r['split'] for r in rows)),
               'seed': seed, 'generation_requests': 0, 'expert_gold': False,
               'training_material_ready': groups >= 10 and all(any(
                   r['split'] == s and r['kind'] == k and r.get('training_allowed') for r in rows)
                   for s in ('train', 'val') for k in ('positive', 'negative', 'background')),
               'notes': 'Evidence/positive/background summaries are training material, not evaluation gold.'}
    write(out / 'summary.json', summary)
    seal(out, inputs, {'artifact': 'evidence_bundle', 'version': 1})
    return summary


def render_record(r):
    import json
    return json.dumps({'values': r.get('values'), 'outcome_type': r.get('outcome_type'),
                       'conditions': r.get('conditions'), 'original_quote': r['original_quote']},
                      ensure_ascii=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release', required=True, type=Path)
    p.add_argument('--workspaces', nargs='+', required=True, type=Path)
    p.add_argument('--supplements', type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--seed', type=int, default=20261027)
    p.add_argument('--split-plan', type=Path)
    print(prepare(**vars(p.parse_args())))
