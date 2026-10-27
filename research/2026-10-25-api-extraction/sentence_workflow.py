"""One-candidate facts, selective context and deterministic evidence restoration."""
from copy import deepcopy
from pathlib import Path
import re

from corpus import read, normal
from linked_context import LinkedContext

TEXT_CAP = 8000
CONDITION_FIELDS = ('cell_line', 'treatment_time', 'tested_concentration', 'assay',
                    'perturbation', 'endpoint_resolution')
TOKEN_CAPS = {'discovery': 2048, 'facts': 4096, 'conditions': 2048}
CONDITION_EXAMPLE = {'items': [{'record_id': 'synthetic-record',
    'values': dict.fromkeys(CONDITION_FIELDS),
    'evidence': {field: [] for field in CONDITION_FIELDS}}]}
CONDITION_EXAMPLE['items'][0]['values']['endpoint_resolution'] = 'cell proliferation'
CONDITION_EXAMPLE['items'][0]['evidence']['endpoint_resolution'] = ['synthetic-method-sentence']
CONDITION_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['items'],
    'properties': {'items': {'type': 'array', 'items': {'type': 'object',
        'additionalProperties': False, 'required': ['record_id', 'values', 'evidence'],
        'properties': {'record_id': {'type': 'string'},
            'values': {'type': 'object', 'additionalProperties': False,
                'required': list(CONDITION_FIELDS),
                'properties': {f: {'type': ['string', 'null']} for f in CONDITION_FIELDS}},
            'evidence': {'type': 'object', 'additionalProperties': False,
                'required': list(CONDITION_FIELDS),
                'properties': {f: {'type': 'array', 'uniqueItems': True,
                    'items': {'type': 'string'}} for f in CONDITION_FIELDS}}}}}}}


def _document(job):
    return read(job['document_path'])


def _sentences(job):
    return read(job['sentence_index_path'])


def _select(sentences, required_ids, ordered_units, cap=TEXT_CAP):
    by_id = {s['sentence_id']: s for s in sentences}
    if set(required_ids) - by_id.keys():
        raise ValueError('Candidate evidence is absent from frozen sentence index')
    selected = {sid: by_id[sid] for sid in required_ids}
    used = sum(len(s['text']) for s in selected.values())
    if used > cap:
        raise ValueError('Required evidence exceeds facts/context text cap')
    omitted = []
    for uid in dict.fromkeys(ordered_units):
        pieces = [s for s in sentences if s['unit_id'] == uid and s['sentence_id'] not in selected]
        size = sum(len(s['text']) for s in pieces)
        if used + size <= cap:
            selected.update((s['sentence_id'], s) for s in pieces)
            used += size
        elif pieces:
            omitted.append(uid)
    return [s for s in sentences if s['sentence_id'] in selected], omitted


def plan_facts(job, candidates):
    doc = _document(job)
    body = [u for u in doc['units'] if u['kind'] == 'body_paragraph']
    positions = {u['unit_id']: i for i, u in enumerate(body)}
    sentences = _sentences(job)
    by_sentence = {s['sentence_id']: s for s in sentences}
    groups = []
    for candidate in candidates:
        candidate = deepcopy(candidate)
        candidate['anchor_sentence_ids'] = list(candidate['sentence_ids'])
        source_ids = list(dict.fromkeys(by_sentence[sid]['unit_id'] for sid in candidate['sentence_ids']))
        order = list(source_ids)
        for uid in source_ids:
            pos = positions[uid]
            for neighbour in (pos-1, pos+1):
                if 0 <= neighbour < len(body) and body[neighbour].get('section') == body[pos].get('section'):
                    order.append(body[neighbour]['unit_id'])
        supplied, omitted = _select(sentences, candidate['sentence_ids'], order)
        groups.append({'candidates': [deepcopy(candidate)], 'candidate': deepcopy(candidate),
                       'sentences': supplied, 'context_units': [], 'candidate_contexts': [],
                       'omitted_unit_ids': omitted, 'stage': 'facts'})
    return groups


def _context_sentences(document, units):
    from sentence_v3 import index_document
    indexed = []
    for unit in units:
        # Use the same offset-preserving segmenter for contextual text; the
        # original kind is restored and cannot become primary discovery text.
        surrogate = dict(document, units=[dict(unit, kind='body_paragraph')])
        for sentence in index_document(surrogate):
            sentence['kind'] = unit['kind']
            indexed.append(sentence)
    return indexed


def _requires_definition(record, supplied):
    ids = {e['sentence_id'] for e in record.get('field_evidence', [])
           if e['field'] in {'observation', 'endpoint'}}
    text = ' '.join(s['text'] for s in supplied if s['sentence_id'] in ids)
    # This asks for assay-definition evidence; it never maps EC50 to a fixed
    # endpoint or treats a table value as a new narrative negative.
    return bool(re.search(r'\b(?:activit(?:y|ies)|potency)\b', text, re.I) and
                re.search(r'\bfold\b|倍|\b[EDI]C\s*50\b', text, re.I))


def plan_conditions(job, fact_result, candidate):
    records = [item['record'] for item in fact_result['accepted']]
    needed = {}
    for record in records:
        endpoint = record['values'].get('endpoint')
        if record.get('endpoint_verification_required') or not endpoint or normal(endpoint) in {
                'uncertain', 'unknown', 'activity', 'potency', 'ec50', '待定'}:
            needed[record['record_key']] = 'endpoint_resolution'
        elif record['outcome_type'] == 'conditional_loss' and not record['values'].get('scope_condition'):
            needed[record['record_key']] = 'claim_conditions'
    if not needed:
        return None
    doc = _document(job)
    units = {u['unit_id']: u for u in doc['units']}
    original = _sentences(job)
    by_id = {s['sentence_id']: s for s in original}
    anchors = [units[uid] for uid in dict.fromkeys(by_id[s]['unit_id'] for s in candidate['sentence_ids'])]
    linked = LinkedContext(doc)
    references = linked.references(anchors)
    targets = [uid for r in references for uid in r.get('target_unit_ids', []) if uid in units]
    terms = set(re.findall(r'[a-z0-9-]{3,}', ' '.join(
        str(r['values'].get(k) or '') for r in records for k in ('subject', 'target')).lower()))
    methods = []
    for u in doc['units']:
        if u['unit_id'] in linked.method_units or re.search(r'method|experimental|assay', u.get('section', ''), re.I):
            score = len(terms & set(re.findall(r'[a-z0-9-]{3,}', u['text'].lower())))
            if score:
                methods.append((-score, u['unit_id']))
    support_ids = list(dict.fromkeys(targets + [uid for _, uid in sorted(methods)[:2]]))
    if not support_ids:
        return None
    extra = _context_sentences(doc, [units[uid] for uid in support_ids if units[uid]['kind'] != 'body_paragraph'])
    all_sentences = list({s['sentence_id']: s for s in original + extra}.values())
    required = list(dict.fromkeys(candidate['sentence_ids'] + [e['sentence_id'] for r in records
                               for e in r.get('field_evidence', [])]))
    supplied, omitted = _select(all_sentences, required, support_ids)
    original_context = {s['sentence_id'] for s in job.get('frozen_context', {}).get('sentences', [])}
    if not any(s['sentence_id'] not in original_context for s in supplied):
        return None
    return {'candidates': [deepcopy(candidate)], 'candidate': deepcopy(candidate),
            'records': deepcopy(records), 'requested_record_ids': list(needed), 'needs': needed,
            'sentences': supplied, 'context_units': [], 'candidate_contexts': [],
            'omitted_unit_ids': omitted, 'references': references, 'stage': 'conditions'}


def request_for(workspace, job, stage, config, candidates=None, discovery_hash=None):
    import json
    w = Path(workspace)
    if stage == 'discovery':
        prompt = (w/'discovery_v3.md').read_text(encoding='utf-8')
        user = {'paragraphs': job['paragraphs'], 'sentences': job['sentences']}
    else:
        frozen = job['frozen_context']
        prompt = (w/('facts_v3.md' if stage == 'facts' else 'conditions_v3.md')).read_text(encoding='utf-8')
        user = {'anchor_sentence_ids': frozen['candidate']['sentence_ids'],
                'sentences': frozen['sentences']}
        if stage == 'conditions':
            user.update(records=[{'record_id': r['record_key'], 'values': r['values'],
                         'outcome_type': r['outcome_type']} for r in frozen['records']
                         if r['record_key'] in frozen['requested_record_ids']], needs=frozen['needs'])
    request = {'model': config['model'], 'messages': [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}], 'stream': True,
               config['output_token_parameter']: min(config['max_output_tokens'], TOKEN_CAPS[stage])}
    if config['response_format'] == 'json_object':
        request['response_format'] = {'type': 'json_object'}
    request['stream_options'] = {'include_usage': True}
    return request


def validate_response(payload, job, candidates):
    if job['active_stage'] == 'facts':
        from facts_v3 import validate_facts
        # The facts context can include neighbours outside its discovery block.
        # Its frozen registry, not the smaller discovery registry, is authoritative.
        effective = dict(job, sentences=job['frozen_context']['sentences'])
        result = validate_facts(payload, effective, candidates)
        for item in result['accepted']:
            r = item['record']
            if _requires_definition(r, job['frozen_context']['sentences']):
                r['endpoint_verification_required'] = True
                r['record_status'] = 'semantic_pending'
            observation_text = ' '.join(e['quote'] for e in r['field_evidence']
                                        if e['field'] == 'observation')
            flags = []
            if (re.search(r'\b(?:did|does|do) not (?:improve|enhance|increase)\b', observation_text, re.I)
                    and r['outcome_type'] in {'not_observed', 'reported_zero'}):
                flags.append('not_improved_must_not_become_inactive')
            if (re.search(r'\b(?:not significant|no significant|not significantly)\b', observation_text, re.I)
                    and r['outcome_type'] == 'reported_zero'):
                flags.append('not_significant_must_not_become_zero')
            if flags:
                r['record_status'] = 'quarantine'
                r['semantic_flags'] = flags
        return result
    return validate_conditions(payload, job)


def validate_conditions(payload, job):
    group = job['frozen_context']
    originals = {r['record_key']: r for r in group['records']}
    expected = set(group['requested_record_ids'])
    sentences = {s['sentence_id']: s for s in group['sentences']}
    if not isinstance(payload, dict) or set(payload) != {'items'} or not isinstance(payload['items'], list):
        raise ValueError('Invalid condition response')
    counts = {}
    for row in payload['items']:
        if isinstance(row, dict) and isinstance(row.get('record_id'), str):
            counts[row['record_id']] = counts.get(row['record_id'], 0)+1
    accepted, rejected, unresolved = [], [], []
    for row in payload['items']:
        rid = row.get('record_id') if isinstance(row, dict) else None
        errors = []
        if (not isinstance(rid, str) or rid not in expected or counts.get(rid) != 1 or
                set(row) != {'record_id', 'values', 'evidence'}):
            rejected.append({'item': row, 'errors': ['invalid_or_duplicate_record_id']});continue
        values, evidence = row['values'], row['evidence']
        if (not isinstance(values, dict) or set(values) != set(CONDITION_FIELDS) or
                not isinstance(evidence, dict) or set(evidence) != set(CONDITION_FIELDS)):
            rejected.append({'record_id': rid, 'errors': ['invalid_condition_fields']});continue
        citations = []
        for field in CONDITION_FIELDS:
            value, ids = values[field], evidence[field]
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append('invalid_value:' + field)
            if (not isinstance(ids, list) or any(not isinstance(sid, str) or sid not in sentences for sid in ids)
                    or (isinstance(ids, list) and len(ids) != len(set(ids)))
                    or (value is not None and not ids) or (value is None and ids)):
                errors.append('invalid_evidence:' + field);continue
            for sid in ids:
                s = sentences[sid]
                citations.append({'field': field, 'quote': s['text'], **{k: s[k] for k in
                    ('sentence_id', 'unit_id', 'char_start', 'char_end')}})
        if errors:
            rejected.append({'record_id': rid, 'errors': errors});continue
        record = deepcopy(originals[rid])
        record['core_original'] = deepcopy(originals[rid])
        record['context_revision'] = {'values': values, 'evidence': citations}
        record['conditions'] = {k: v for k, v in values.items() if k != 'endpoint_resolution'}
        record['condition_evidence'] = citations
        old_endpoint, new_endpoint = record['values'].get('endpoint'), values['endpoint_resolution']
        if new_endpoint and old_endpoint and normal(old_endpoint) not in {'uncertain','unknown','activity','potency','ec50','待定'} and normal(old_endpoint) != normal(new_endpoint):
            record['record_status'] = 'quarantine'
            record['condition_conflicts'] = ['endpoint_resolution_differs_from_core_requires_review']
        elif new_endpoint:
            record['values']['endpoint'] = new_endpoint
            record['field_evidence'] = [e for e in record['field_evidence'] if e['field'] != 'endpoint'] + [
                dict(e, field='endpoint') for e in citations if e['field'] == 'endpoint_resolution']
            record['endpoint_verification_required'] = False
            if (record['record_status'] != 'quarantine' and not record.get('semantic_flags') and
                    all(record['values'].get(k) for k in ('subject','endpoint','observation')) and record['outcome_type'] != 'uncertain'):
                record['record_status'] = 'core_usable'
        accepted.append({'candidate_id': record['candidate_id'], 'record': record})
    represented = set(counts) & expected
    unresolved.extend({'record_id': rid, 'reason': 'missing_response'} for rid in sorted(expected-represented))
    return {'accepted': accepted, 'rejected': rejected, 'unresolved': unresolved,
            'accounting_complete': not unresolved and not rejected, 'coverage_notes': []}
