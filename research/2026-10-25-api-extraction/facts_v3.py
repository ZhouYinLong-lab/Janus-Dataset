"""Offline minimal fact contract. Source preparation belongs to the caller."""

from copy import deepcopy
import hashlib
import json
import re


FIELDS = ('subject', 'target', 'endpoint', 'observation', 'comparator', 'scope_condition')
OUTCOME_TYPES = ('not_observed', 'not_significant', 'reduced', 'not_improved',
                 'conditional_loss', 'reported_zero', 'uncertain')
STATUSES = ('observations', 'uncertain', 'not_experimental_negative')
SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    'type': 'object', 'additionalProperties': False,
    'required': ['status', 'reason', 'observations'],
    'properties': {
        'status': {'type': 'string', 'enum': list(STATUSES)},
        'reason': {'type': ['string', 'null']},
        'observations': {
            'type': 'array',
            'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['values', 'outcome_type', 'evidence'],
                'properties': {
                    'values': {
                        'type': 'object', 'additionalProperties': False,
                        'required': list(FIELDS),
                        'properties': {f: {'type': ['string', 'null']} for f in FIELDS},
                    },
                    'outcome_type': {'type': 'string', 'enum': list(OUTCOME_TYPES)},
                    'evidence': {
                        'type': 'object', 'additionalProperties': False,
                        'required': list(FIELDS),
                        'properties': {
                            f: {'type': 'array', 'uniqueItems': True,
                                'items': {'type': 'string', 'minLength': 1}}
                            for f in FIELDS
                        },
                    },
                },
            },
        },
    },
    'allOf': [{
        'if': {'properties': {'status': {'const': 'observations'}}},
        'then': {'properties': {'observations': {'minItems': 1}}},
        'else': {'properties': {'reason': {'type': 'string', 'pattern': r'\S'},
                                'observations': {'maxItems': 0}}},
    }],
}

# Entirely synthetic FORMAT example, not a project observation or a gold label.
# S1: "Synthetic analogues A and B did not improve target Z degradation
#      relative to synthetic reference R; this does not establish inactivity."
EXAMPLE = {
    'status': 'observations', 'reason': None,
    'observations': [{
        'values': {
            'subject': 'Synthetic analogues A and B', 'target': 'target Z',
            'endpoint': 'target Z degradation',
            'observation': 'did not improve degradation relative to reference R',
            'comparator': 'synthetic reference R', 'scope_condition': None,
        },
        'outcome_type': 'not_improved',
        'evidence': {f: ([] if f == 'scope_condition' else ['S1']) for f in FIELDS},
    }],
}

_UNCERTAIN = re.compile(
    r'\b(?:uncertain|unknown|unspecified|unresolved|undetermined|unclear|ambiguous|'
    r'not\s+(?:known|specified|determined))\b|未知|不确定|不明确|未明确|待定|[?？]', re.I)
_MISSING = r'(?:missing|omitted|absent|unavailable|not\s+(?:provided|supplied|included|available)|缺失|缺少|未提供|省略)'
_ANCHOR = r'(?:\banchor(?:\s+sentences?)?\b|锚点|锚句)'
_FIGURE = r'(?:\bfig(?:ure)?s?\.?\s*(?:S?\d+)?\b|补充图|图\s*S?\d+)'
_OPTIONAL = r'(?:\bdose\b|\bconcentration\b|\btreatment\s+time\b|剂量|浓度|处理时间)'
_CORE_GAP = re.compile(r'\b(?:subject|endpoint|observation|assay\s+identity)\b|实验对象|终点|观察结果', re.I)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def _sentence(row, key=None):
    if not isinstance(row, dict):
        raise ValueError('Sentence must be an object with source text and location')
    sid = row.get('sentence_id', key)
    quote = row.get('text', row.get('quote'))
    if (not _text(sid) or (key is not None and sid != key)
            or not _text(row.get('unit_id')) or not _text(quote)):
        raise ValueError('Invalid sentence_id, unit_id or sentence text')
    if 'text' in row and 'quote' in row and row['text'] != row['quote']:
        raise ValueError('Conflicting sentence text and quote')
    start, end = row.get('char_start'), row.get('char_end')
    if (type(start) is not int or type(end) is not int or start < 0
            or end - start != len(quote)):
        raise ValueError('Sentence offsets must delimit its exact text within the unit')
    return {'sentence_id': sid, 'unit_id': row['unit_id'], 'quote': quote,
            'char_start': start, 'char_end': end}


def _sentence_map(rows):
    if isinstance(rows, dict):
        pairs = rows.items()
    elif isinstance(rows, list):
        pairs = ((None, row) for row in rows)
    else:
        raise ValueError('job.sentences must be a sentence list or ID-to-sentence mapping')
    result = {}
    for key, row in pairs:
        sentence = _sentence(row, key)
        sid = sentence['sentence_id']
        if sid in result:
            raise ValueError('Duplicate sentence ID: ' + sid)
        result[sid] = sentence
    return result


def _context(job, candidates):
    """Validate trusted caller data separately from the model response."""
    if (not isinstance(job, dict) or not _text(job.get('paper_id'))
            or not _text(job.get('source_sha256'))
            or not (job.get('doi') is None or _text(job['doi']))):
        raise ValueError('job requires paper_id, source_sha256 and optional DOI')
    if (not isinstance(candidates, (list, tuple)) or len(candidates) != 1
            or not isinstance(candidates[0], dict)
            or not _text(candidates[0].get('candidate_id'))):
        raise ValueError('Exactly one candidate is required')
    candidate = candidates[0]
    frozen = job.get('frozen_context')
    if (not isinstance(frozen, dict) or frozen.get('candidate') != candidate
            or not isinstance(frozen.get('sentences'), list)):
        raise ValueError('frozen_context requires the same candidate and a sentence list')
    registry = _sentence_map(job.get('sentences'))
    supplied = {}
    for row in frozen['sentences']:
        if isinstance(row, str):
            sid = row
            if sid not in registry:
                raise ValueError('Frozen sentence ID absent from source mapping: ' + sid)
            sentence = registry[sid]
        else:
            sentence = _sentence(row)
            sid = sentence['sentence_id']
            if registry.get(sid) != sentence:
                raise ValueError('Frozen sentence differs from source mapping: ' + sid)
        if sid in supplied:
            raise ValueError('Duplicate frozen sentence ID: ' + sid)
        supplied[sid] = sentence
    anchors = candidate.get('anchor_sentence_ids')
    if (not isinstance(anchors, list) or not anchors
            or any(not _text(sid) for sid in anchors) or len(set(anchors)) != len(anchors)):
        raise ValueError('candidate requires distinct anchor_sentence_ids')
    return candidate, supplied, anchors


def _mentions_gap(reason, noun):
    # Deliberately limited phrase detection; it does not classify assays or biology.
    return bool(re.search(rf'{_MISSING}.{{0,80}}{noun}|{noun}.{{0,80}}{_MISSING}', reason, re.I))


def _abstention_errors(reason, anchors, supplied):
    errors = []
    if _mentions_gap(reason, _ANCHOR) and all(sid in supplied for sid in anchors):
        errors.append('anchor_already_provided')
    if not _CORE_GAP.search(reason):
        if _mentions_gap(reason, _FIGURE):
            errors.append('missing_figure_alone')
        if _mentions_gap(reason, _OPTIONAL):
            errors.append('missing_optional_condition_alone')
    return errors


def _observation_errors(row, supplied, anchors):
    if not _keys(row, ('values', 'outcome_type', 'evidence')):
        return ['invalid_observation_schema']
    if not _keys(row['values'], FIELDS) or not _keys(row['evidence'], FIELDS):
        return ['invalid_field_mapping']
    if not isinstance(row['outcome_type'], str) or row['outcome_type'] not in OUTCOME_TYPES:
        return ['invalid_outcome_type']
    errors = []
    for field in FIELDS:
        value, ids = row['values'][field], row['evidence'][field]
        if value is not None and not isinstance(value, str):
            errors.append('invalid_value_type:' + field)
            continue
        if not isinstance(ids, list) or any(not _text(sid) for sid in ids):
            errors.append('invalid_evidence_ids:' + field)
            continue
        if len(set(ids)) != len(ids):
            errors.append('duplicate_evidence_id:' + field)
        if any(sid not in supplied for sid in ids):
            errors.append('unknown_sentence_id:' + field)
        if _text(value) and not ids:
            errors.append('missing_field_evidence:' + field)
        if not _text(value) and ids:
            errors.append('evidence_for_empty_field:' + field)
    if any(sid not in supplied for sid in anchors):
        errors.append('missing_candidate_anchor')
    observation_ids = row['evidence']['observation']
    if (_text(row['values']['observation']) and isinstance(observation_ids, list)
            and not any(sid in anchors for sid in observation_ids)):
        errors.append('observation_not_linked_to_candidate_anchor')
    return errors


def _record(row, job, candidate, supplied, anchors):
    values = deepcopy(row['values'])
    field_evidence = [dict(field=field, **supplied[sid])
                      for field in FIELDS for sid in row['evidence'][field]]
    core_fields = ('subject', 'endpoint', 'observation')
    clear = (row['outcome_type'] != 'uncertain'
             and all(_text(values[f]) and not _UNCERTAIN.search(values[f]) for f in core_fields)
             and values['endpoint'].strip().casefold() not in {'activity', 'potency', 'ec50'})
    identity = {'source_sha256': job['source_sha256'], 'paper_id': job['paper_id'],
                'candidate_id': candidate['candidate_id'], 'values': values,
                'outcome_type': row['outcome_type']}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':')).encode('utf-8')).hexdigest()
    return {
        'values': values, 'outcome_type': row['outcome_type'],
        'field_evidence': field_evidence, 'source_sha256': job['source_sha256'],
        'paper_id': job['paper_id'], 'doi': job.get('doi'),
        'candidate_id': candidate['candidate_id'], 'record_key': digest,
        'anchor_sentence_ids': list(anchors),
        'original_quote': '\n'.join(supplied[sid]['quote'] for sid in anchors),
        'record_status': 'core_usable' if clear else 'semantic_pending',
        'expert_gold': False, 'semantic_review': 'pending', 'ready_for_training': False,
    }


def validate_facts(payload, job, candidates):
    """Return accepted/rejected observations and candidate accounting, without I/O.

    Invalid caller material raises ValueError. Malformed model output is returned
    in rejected/unresolved. An accounted candidate can still be unresolved.
    """
    candidate, supplied, anchors = _context(job, candidates)
    cid = candidate['candidate_id']
    missing = [sid for sid in anchors if sid not in supplied]
    result = {'accepted': [], 'rejected': [], 'unresolved': [],
              'coverage_notes': ['anchor_missing:' + ','.join(missing)
                                 if missing else 'anchor_present'],
              'accounting_complete': False}
    errors = []
    if not _keys(payload, ('status', 'reason', 'observations')):
        errors.append('invalid_payload_schema')
    else:
        status, reason, observations = payload['status'], payload['reason'], payload['observations']
        if not isinstance(status, str) or status not in STATUSES:
            errors.append('invalid_status')
        if reason is not None and not isinstance(reason, str):
            errors.append('invalid_reason_type')
        if not isinstance(observations, list):
            errors.append('invalid_observations_array')
        elif status == 'observations' and not observations:
            errors.append('observations_status_requires_rows')
        elif status != 'observations' and observations:
            errors.append('abstention_must_have_no_observations')
        if status != 'observations' and not _text(reason):
            errors.append('abstention_requires_reason')
    if errors:
        result['rejected'].append({'candidate_id': cid, 'errors': errors})
        result['unresolved'].append({'candidate_id': cid, 'reason': 'invalid_payload',
                                     'reported_reason': (payload.get('reason')
                                                         if isinstance(payload, dict) else None)})
        return result

    result['accounting_complete'] = True
    if status != 'observations':
        issues = _abstention_errors(reason, anchors, supplied)
        if status == 'uncertain' or issues or missing:
            entry = {'candidate_id': cid, 'status': status, 'reason': reason, 'errors': []}
            if issues:
                entry['errors'] = ['invalid_abstention_reason']
                result['coverage_notes'].extend('invalid_abstention_reason:' + issue for issue in issues)
            result['unresolved'].append(entry)
        else:
            result['rejected'].append({'candidate_id': cid, 'status': status,
                                       'reason': reason, 'errors': []})
        return result

    for index, row in enumerate(observations):
        errors = _observation_errors(row, supplied, anchors)
        if errors:
            result['rejected'].append({'candidate_id': cid, 'observation_index': index,
                                       'errors': errors})
        else:
            result['accepted'].append({'candidate_id': cid,
                                      'record': _record(row, job, candidate, supplied, anchors)})
    if not result['accepted']:
        result['unresolved'].append({'candidate_id': cid, 'reason': 'no_valid_observations',
                                     'reported_reason': reason})
    return result
