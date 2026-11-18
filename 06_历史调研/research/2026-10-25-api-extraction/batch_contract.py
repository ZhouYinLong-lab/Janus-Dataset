"""Isolate malformed individual candidates without discarding valid neighbours."""
from collections import Counter
import re

from two_stage_core import validate_discovery, validate_enrichment


def _intervention_leaves_degradation_unchanged(quote, perturbation=None, target=None):
    """Recognise explicit no-effect clauses and the known insensitivity noun phrase."""
    subject = (r'\b(?:[\w-]+\s+)?(?:knock[ -]?(?:out|down)|KO|deletion|depletion)'
               r'(?:\s+of\s+[\w-]+)?')
    if perturbation:
        subject = rf'(?:{subject}|(?<!\w){re.escape(perturbation)}(?!\w))'
    no_effect = (
        r'(?:(?:had|has|have|showed)\s+no\s+(?:(?:significant|detectable)\s+)?'
        r'(?:effects?|impact)\s+on|(?:did|does|do)\s+not\s+'
        r'(?:affect|alter|influence|impair|inhibit|block|prevent|reduce)|'
        r'failed\s+to\s+(?:affect|alter|influence|inhibit|block|prevent))'
    )
    # Only a short degradation noun phrase may follow the no-effect predicate.
    # Binding or a separate clause must not supply a degradation interpretation.
    endpoint = (r'(?P<endpoint>(?:(?!(?:binding|ternary|NanoBRET|and|but|whereas|not)\b)'
                r'[\w-]+\s+){0,4}degradation(?:\s+of\s+[\w-]+)?)\b')
    patterns = (
        rf'(?P<subject>{subject})\s+{no_effect}\s+{endpoint}',
        # B149: "the insensitivity of BRD4 degradation to RMND5B knockout".
        # Capture only this endpoint and intervention, not a later paralog or control.
        rf'\bthe\s+insensitivity\s+of\s+{endpoint}\s+to\s+(?P<subject>{subject})',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, quote, re.I):
            if perturbation and not re.search(
                    rf'(?<!\w){re.escape(perturbation)}(?!\w)', match['subject'], re.I):
                continue
            if not target or re.search(rf'(?<!\w){re.escape(target)}(?!\w)',
                                       match['endpoint'], re.I):
                return True
    return False


def _observation_scope_errors(record, anchor):
    """Quarantine explicit known shapes; all other semantics still need review."""
    fields = record['fields']
    errors = []
    # Inspect the selected fields only. A full result anchor can legitimately
    # mention another endpoint, including a positive binding/degradation result.
    selected = ' '.join(fields.get(f) or '' for f in ('endpoint', 'assay'))
    if (re.search(r'\b(?:binding|ternary|NanoBRET)\b', selected, re.I)
            and re.search(r'\bdegrad(?:ation|e|es|ed|ing)\b', selected, re.I)
            and any(fields.get(f) for f in
                    ('treatment_time', 'tested_concentration', 'cell_line', 'perturbation'))):
        errors.append('mixed_observation_endpoints_share_conditions')
    if (record['negative_type'] in {'no_degradation', 'no_significant_degradation',
                                    'no_abundance_change', 'conditional_loss'}
            and (not fields.get('endpoint') or re.search(r'degrad', fields['endpoint'], re.I))
            and _intervention_leaves_degradation_unchanged(
                anchor['quote'], fields.get('perturbation'), fields.get('target'))):
        errors.append('ineffective_intervention_is_not_degradation_loss')
    return errors


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
            for accepted_item in r['accepted']:
                record = accepted_item['record']
                errors = _observation_scope_errors(record, expected[cid])
                result_quotes = ' '.join(e['quote'] for e in record['evidence'] if e['field'] == 'result_text')
                endpoint = (record['fields'].get('endpoint') or '').casefold()
                if record['negative_type'] == 'reported_zero' and not re.search(
                        r'(?:\bzero\b|(?<![\d.])0(?:\.0+)?\s*%|\b(?:Dmax|activity|response|degradation)\s*[=:]\s*0(?:\.0+)?(?![\d.]))',
                        result_quotes, re.I):
                    errors.append('qualitative_result_is_not_measured_zero')
                if record['negative_type'] == 'target_not_detected' and any(
                        x in endpoint for x in ['labeling', 'labelling', 'binding', 'ubiquitination']):
                    errors.append('assay_response_is_not_baseline_target_absence')
                endpoint_quotes = ' '.join(e['quote'] for e in record['evidence'] if e['field'] == 'endpoint')
                if ('degrad' in endpoint and endpoint_quotes and not re.search(
                        r'degrad|protein|abundance|\blevels?\b|deplet', endpoint_quotes, re.I)):
                    errors.append('degradation_endpoint_not_explicit_in_endpoint_evidence')
                if errors:
                    rejected.append({'candidate_id': accepted_item['candidate_id'],
                                     'record': record, 'errors': errors})
                else:
                    accepted.append(accepted_item)
            rejected.extend(r['rejected'])
            unresolved.extend(r['unresolved'])
        except (ValueError, TypeError, KeyError):
            rejected.append({'item': item, 'errors': ['invalid_enrichment_contract']})
    missing = sorted(set(expected) - accounted)
    unresolved.extend({'candidate_id': cid, 'reason': 'missing_or_ambiguous_response_entry'} for cid in missing)
    return {'accepted': accepted, 'rejected': rejected, 'unresolved': unresolved,
            'missing_candidate_ids': missing, 'accounting_complete': not missing,
            'coverage_notes': payload['coverage_notes'],
            'semantic_review': 'pending', 'ready_for_training': False}
