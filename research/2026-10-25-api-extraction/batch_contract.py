"""Isolate malformed individual candidates without discarding valid neighbours."""
from collections import Counter

from two_stage_core import validate_discovery, validate_enrichment


def discovery(payload, job):
    if not isinstance(payload, dict) or not isinstance(payload.get('candidates'), list):
        raise ValueError('Invalid discovery envelope')
    # Validate top-level shape even when all rows are malformed.
    validate_discovery(dict(payload, candidates=[], no_candidate_reason='Envelope check'), job)
    if len(payload['candidates']) > 100:
        raise ValueError('Too many candidate rows')
    counts = Counter(c.get('candidate_id') for c in payload['candidates']
                     if isinstance(c, dict) and isinstance(c.get('candidate_id'), str))
    accepted, rejected = [], []
    for c in payload['candidates']:
        cid = c.get('candidate_id') if isinstance(c, dict) else None
        if not isinstance(cid, str) or not cid.strip() or counts[cid] != 1:
            rejected.append({'candidate': c, 'errors': ['invalid_or_duplicate_candidate_id']})
            continue
        try:
            r = validate_discovery(dict(payload, candidates=[c]), job)
            accepted.extend(r['accepted']); rejected.extend(r['rejected'])
        except (ValueError, TypeError, KeyError):
            rejected.append({'candidate': c, 'errors': ['invalid_candidate_contract']})
    if not payload['candidates']:
        validate_discovery(payload, job)
    return {'accepted': accepted, 'rejected': rejected,
            'coverage_notes': payload['coverage_notes'],
            'no_candidate_reason': payload.get('no_candidate_reason'),
            'semantic_review': 'pending', 'ready_for_training': False}


def enrichment(payload, job, candidates):
    if not isinstance(payload, dict) or set(payload) != {'paper_id', 'items', 'unresolved', 'coverage_notes'}:
        raise ValueError('Invalid enrichment envelope')
    if (payload['paper_id'] != job['paper_id'] or not isinstance(payload['items'], list)
            or not isinstance(payload['unresolved'], list)
            or not isinstance(payload['coverage_notes'], list)
            or any(not isinstance(x, str) for x in payload['coverage_notes'])
            or len(payload['items']) + len(payload['unresolved']) > 200):
        raise ValueError('Invalid enrichment arrays or paper')
    expected = {c['candidate_id']: c for c in candidates}
    rows = [(kind, item) for kind in ['items', 'unresolved'] for item in payload[kind]]
    counts = Counter(item.get('candidate_id') for _, item in rows
                     if isinstance(item, dict) and isinstance(item.get('candidate_id'), str))
    accepted, rejected, unresolved, accounted = [], [], [], set()
    for kind, item in rows:
        cid = item.get('candidate_id') if isinstance(item, dict) else None
        if not isinstance(cid, str) or cid not in expected or counts[cid] != 1:
            rejected.append({'item': item, 'errors': ['invalid_duplicate_or_unlinked_candidate']})
            continue
        accounted.add(cid)
        one = dict(payload, items=[item] if kind == 'items' else [],
                   unresolved=[item] if kind == 'unresolved' else [])
        try:
            r = validate_enrichment(one, job, [expected[cid]])
            accepted.extend(r['accepted']); rejected.extend(r['rejected'])
            unresolved.extend(r['unresolved'])
        except (ValueError, TypeError, KeyError):
            rejected.append({'item': item, 'errors': ['invalid_enrichment_contract']})
    missing = sorted(set(expected) - accounted)
    unresolved.extend({'candidate_id': cid, 'reason': 'missing_or_ambiguous_response_entry'} for cid in missing)
    return {'accepted': accepted, 'rejected': rejected, 'unresolved': unresolved,
            'missing_candidate_ids': missing, 'accounting_complete': not missing,
            'coverage_notes': payload['coverage_notes'],
            'semantic_review': 'pending', 'ready_for_training': False}
