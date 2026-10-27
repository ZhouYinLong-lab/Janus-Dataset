"""Offline sentence indexing, bounded discovery jobs and response accounting.

Offsets are half-open Python string offsets into the original body unit. Only
whitespace may fall outside indexed spans. No source files or services are read.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re


SPLIT_VERSION = 'sentence_v3.1'
_ABBREVIATION = re.compile(
    r'\b(?:e\.g\.|i\.e\.|et\s+al\.|figs?\.|eqs?\.|refs?\.|'
    r'drs?\.|prof\.|vs\.|cf\.|approx\.|no\.|nos\.|vol\.|pp?\.|'
    r'suppl\.|supp\.|a\.u\.|s\.d\.|s\.e\.m\.)', re.I)
_INITIAL = re.compile(r'\b[A-Z]\.(?=\s+[A-Z])')
_END = re.compile(r'[.!?。！？]+[\)\]\}"\'”’]*')


def _id(prefix, *parts):
    encoded = json.dumps(parts, ensure_ascii=False, separators=(',', ':'))
    return prefix + hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _bounds(text):
    """Split only at plausible sentence endings; retain ambiguous long prose."""
    protected = {i for pattern in (_ABBREVIATION, _INITIAL)
                 for match in pattern.finditer(text)
                 for i in range(match.start(), match.end()) if text[i] == '.'}
    start = 0
    for match in _END.finditer(text):
        stop = match.end()
        punctuation = text[match.start()]
        if match.start() in protected:
            continue
        # A period inside a decimal, mutation, isoform, URL or abbreviation is
        # not a boundary. Chinese terminators need no intervening whitespace.
        if punctuation not in '。！？' and stop < len(text):
            if not text[stop].isspace():
                continue
            following = text[stop:].lstrip()
            if punctuation == '.' and following:
                first = following[0]
                if not (first.isupper() or first.isdigit() or
                        first in '\"\'“‘(' or '\u3400' <= first <= '\u9fff'):
                    continue
        left = start
        while left < stop and text[left].isspace():
            left += 1
        if left < stop:
            yield left, stop
        start = stop
    left, right = start, len(text)
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        yield left, right


def index_document(document):
    """Return stable sentence spans for all and only body_paragraph units.

    Identity uses source_sha256, original unit_id, start/end and SPLIT_VERSION;
    metadata and job size therefore have no effect on sentence identities.
    """
    if not isinstance(document.get('source_sha256'), str) or not document['source_sha256']:
        raise ValueError('source_sha256 is required')
    sentences, seen = [], set()
    for unit in document['units']:
        uid = unit['unit_id']
        if not isinstance(uid, str) or not uid or uid in seen:
            raise ValueError('Source unit IDs must be nonempty and unique')
        seen.add(uid)
        if unit['kind'] != 'body_paragraph':
            continue
        if not isinstance(unit['text'], str):
            raise ValueError('Body text must be a string')
        for start, end in _bounds(unit['text']):
            sentences.append({
                'sentence_id': _id('S:', document['source_sha256'], uid,
                                   start, end, SPLIT_VERSION),
                'unit_id': uid, 'char_start': start, 'char_end': end,
                'text': unit['text'][start:end], 'kind': 'body_paragraph',
                'locator': deepcopy(unit.get('locator', '')),
                'section': deepcopy(unit.get('section', ''))})
    return sentences


def build_sentence_jobs(document, metadata, primary_cap=4000, max_paragraphs=3):
    """Build jobs with <= primary_cap source characters / max_paragraphs units.

    Long paragraphs split at indexed sentence boundaries. An indivisible
    sentence over the cap is returned in gaps with status=unscanned. Whitespace
    outside fragments remains verifiable through original-unit offsets.
    """
    if (type(primary_cap) is not int or primary_cap < 1 or
            type(max_paragraphs) is not int or max_paragraphs < 1):
        raise ValueError('Caps must be positive integers')
    sentences = index_document(document)
    by_unit = {}
    for sentence in sentences:
        by_unit.setdefault(sentence['unit_id'], []).append(sentence)
    positions = {s['sentence_id']: i for i, s in enumerate(sentences)}
    unit_positions = {u['unit_id']: i for i, u in enumerate(document['units'])}
    pieces, gaps = [], []
    for unit in document['units']:
        indexed = by_unit.get(unit['unit_id'], [])
        if not indexed:
            continue

        def add_piece(group, whole=False):
            if not group:
                return
            start = 0 if whole else group[0]['char_start']
            end = len(unit['text']) if whole else group[-1]['char_end']
            piece = deepcopy(unit)
            piece.update(parent_unit_id=unit['unit_id'], char_start=start,
                         char_end=end, text=unit['text'][start:end])
            if not whole:
                piece['unit_id'] = _id('F:', document['source_sha256'],
                                       unit['unit_id'], start, end, SPLIT_VERSION)
            pieces.append((piece, group))

        if len(unit['text']) <= primary_cap:
            add_piece(indexed, whole=True)
            continue
        group = []
        for sentence in indexed:
            if len(sentence['text']) > primary_cap:
                add_piece(group)
                group = []
                gaps.append(dict(deepcopy(sentence), reason='sentence_exceeds_primary_cap',
                                 status='unscanned', primary_cap=primary_cap))
            else:
                if group and sentence['char_end'] - group[0]['char_start'] > primary_cap:
                    add_piece(group)
                    group = []
                group.append(sentence)
        add_piece(group)

    jobs, current, used = [], [], 0

    def flush():
        if not current:
            return
        primary = [deepcopy(piece) for piece, _ in current]
        selected = [deepcopy(s) for _, group in current for s in group]
        paper_id = document['paper_id']
        jobs.append({
            'job_id': _id('J_', paper_id, document['source_sha256'], SPLIT_VERSION,
                          [p['unit_id'] for p in primary]),
            'paper_id': paper_id, 'doi': metadata.get('doi', ''),
            'title': metadata.get('title', ''), 'source_path': document['source_path'],
            'source_sha256': document['source_sha256'],
            'source_parser_version': document.get('source_parser_version',
                                                   document.get('parser_version')),
            'protocol': 'sentence_v3', 'sentence_version': SPLIT_VERSION,
            'primary_units': primary, 'sentences': selected,
            'paragraphs': [{'paragraph_id': p['unit_id'],
                            'sentence_ids': [s['sentence_id'] for s in group]}
                           for p, group in current],
            # Absolute positions preserve gaps and non-body barriers even when
            # the skipped material is not included in this bounded job.
            'sentence_positions': {s['sentence_id']: positions[s['sentence_id']]
                                   for s in selected},
            'source_unit_positions': {p['parent_unit_id']: unit_positions[p['parent_unit_id']]
                                      for p in primary}})

    for piece, group in pieces:
        # Keep fragments of one parent in separate jobs: otherwise a large
        # omitted whitespace interval could be silently joined in a quote.
        same_parent = any(p['parent_unit_id'] == piece['parent_unit_id'] for p, _ in current)
        if current and (used + len(piece['text']) > primary_cap or
                        len(current) >= max_paragraphs or same_parent):
            flush()
            current, used = [], 0
        current.append((piece, group))
        used += len(piece['text'])
    flush()
    return {'jobs': jobs, 'gaps': gaps, 'sentences': sentences}


def _candidate(sentence_ids, job, sentence_map, owners, primary):
    """Recover exact per-unit slices; two newlines separate paragraph quotes."""
    selected = [sentence_map[sid] for sid in sentence_ids]
    positions = [job['sentence_positions'][sid] for sid in sentence_ids]
    if any(b != a + 1 for a, b in zip(positions, positions[1:])):
        return None, 'non_contiguous_span'
    parts = []
    for sentence in selected:
        pid = owners[sentence['sentence_id']]
        piece = primary[pid]
        start, end = sentence['char_start'], sentence['char_end']
        offset = piece['char_start']
        if (sentence['unit_id'] != piece['parent_unit_id'] or
                not offset <= start < end <= piece['char_end'] or
                piece['text'][start - offset:end - offset] != sentence['text']):
            return None, 'invalid_source_offsets'
        if parts and parts[-1]['unit_id'] == sentence['unit_id']:
            previous_end = parts[-1]['char_end']
            if start < previous_end or piece['text'][previous_end-offset:start-offset].strip():
                return None, 'non_contiguous_source'
            parts[-1]['char_end'] = end
            parts[-1]['text'] = piece['text'][parts[-1]['char_start']-offset:end-offset]
        else:
            if parts:
                before = job['source_unit_positions'][parts[-1]['unit_id']]
                after = job['source_unit_positions'][sentence['unit_id']]
                if after != before + 1:
                    return None, 'non_contiguous_source_units'
                if not parts[-1]['locator'] or not piece.get('locator'):
                    return None, 'unlocatable_cross_paragraph_span'
            parts.append({'unit_id': sentence['unit_id'], 'primary_unit_id': pid,
                          'char_start': start, 'char_end': end,
                          'locator': deepcopy(piece.get('locator', '')),
                          'text': piece['text'][start-offset:end-offset]})
    return {
        'candidate_id': _id('C:', job['source_sha256'], SPLIT_VERSION, sentence_ids),
        'quote': '\n\n'.join(part['text'] for part in parts),
        'sentence_ids': list(sentence_ids),
        'unit_id': owners[sentence_ids[0]],
        'source_unit_ids': [part['unit_id'] for part in parts],
        'quote_parts': parts}, None


def validate_discovery(payload, job):
    """Quarantine invalid entries/spans while preserving valid neighbours.

    coverage is one row per primary fragment. accounting_complete means each
    row has an explicit, structurally valid disposition; an explicit uncertain
    disposition is accounted for and is also retained in unresolved. Missing,
    duplicate or contradictory responses never become none_found.

    Candidate unit_id names its first primary fragment; source_unit_ids names
    original body units. quote_parts provides exact original offsets and text.
    Duplicate rows leave that paragraph unresolved, with valid candidates from
    the first row retained. Overlapping spans are quarantined after the first
    valid span so one sentence is not expanded into multiple observations.
    Valid evidence survives coverage conflicts for subsequent review.
    """
    primary = {u['unit_id']: u for u in job['primary_units']}
    sentence_map = {s['sentence_id']: s for s in job['sentences']}
    owners = {sid: p['paragraph_id'] for p in job['paragraphs'] for sid in p['sentence_ids']}
    result = {'accepted': [], 'rejected': [], 'unresolved': [],
              'coverage': [], 'accounting_complete': False, 'coverage_notes': []}
    errors = {pid: [] for pid in primary}
    rows = {}
    explicit = {}
    seen_spans, seen_sentence_ids = set(), set()
    touched = {pid: [] for pid in primary}
    schema_ok = isinstance(payload, dict) and set(payload) == {'paragraphs'}
    entries = payload.get('paragraphs') if isinstance(payload, dict) else None
    if not schema_ok or not isinstance(entries, list):
        result['coverage_notes'].append('invalid_payload_schema')
        schema_ok = False
    if not isinstance(entries, list):
        entries = []
    counts = Counter(e.get('paragraph_id') for e in entries
                     if isinstance(e, dict) and isinstance(e.get('paragraph_id'), str)
                     and e['paragraph_id'] in primary)

    def reject(reason, entry, pid=None, span_index=None):
        record = {'reason': reason, 'entry': deepcopy(entry)}
        if pid is not None:
            record['paragraph_id'] = pid
        if span_index is not None:
            record['span_index'] = span_index
        result['rejected'].append(record)
        if pid in errors:
            errors[pid].append(reason)

    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('paragraph_id'), str):
            reject('invalid_paragraph_id', entry)
            continue
        pid = entry['paragraph_id']
        if pid not in primary:
            reject('unknown_paragraph_id', entry, pid)
            continue
        if pid in rows:
            reject('duplicate_paragraph_id', entry, pid)
            continue
        rows[pid] = entry
        if counts[pid] > 1:
            errors[pid].append('duplicate_paragraph_id')
        status, spans = entry.get('status'), entry.get('spans')
        if (set(entry) != {'paragraph_id', 'status', 'spans'} or
                status not in ('has_candidates', 'none_found', 'uncertain') or
                not isinstance(spans, list)):
            reject('invalid_paragraph_schema', entry, pid)
            continue
        explicit[pid] = status
        if status == 'none_found' and spans:
            reject('none_found_with_spans', entry, pid)
            continue
        for index, span in enumerate(spans):
            if not isinstance(span, dict) or set(span) != {'sentence_ids'}:
                reject('invalid_span_schema', span, pid, index)
                continue
            ids = span['sentence_ids']
            if (not isinstance(ids, list) or not ids or
                    any(not isinstance(sid, str) or not sid for sid in ids)):
                reject('invalid_sentence_ids', span, pid, index)
                continue
            if len(ids) != len(set(ids)):
                reject('duplicate_sentence_id', span, pid, index)
                continue
            if any(sid not in sentence_map or sid not in owners for sid in ids):
                reject('unknown_sentence_id', span, pid, index)
                continue
            if tuple(ids) in seen_spans:
                reject('duplicate_span', span, pid, index)
                continue
            if seen_sentence_ids.intersection(ids):
                reject('overlapping_span', span, pid, index)
                continue
            if owners[ids[0]] != pid:
                reject('span_anchor_mismatch', span, pid, index)
                continue
            candidate, reason = _candidate(ids, job, sentence_map, owners, primary)
            if reason:
                reject(reason, span, pid, index)
                continue
            seen_spans.add(tuple(ids))
            seen_sentence_ids.update(ids)
            if status == 'uncertain':
                result['unresolved'].append(dict(candidate, paragraph_id=pid, reason='uncertain_span'))
            else:
                result['accepted'].append(candidate)
                for sid in ids:
                    linked_pid = owners[sid]
                    if candidate['candidate_id'] not in touched[linked_pid]:
                        touched[linked_pid].append(candidate['candidate_id'])

    for pid in primary:
        status = explicit.get(pid)
        if pid not in rows:
            errors[pid].append('missing_paragraph_response')
        if status == 'has_candidates' and not touched[pid]:
            errors[pid].append('has_candidates_without_valid_span')
        if status in ('none_found', 'uncertain') and touched[pid]:
            errors[pid].append('cross_paragraph_status_conflict')
        reasons = list(dict.fromkeys(errors[pid]))
        resolved_status = 'unresolved' if reasons or status is None else status
        coverage = {'paragraph_id': pid, 'status': resolved_status,
                    'candidate_ids': touched[pid], 'reasons': reasons}
        result['coverage'].append(coverage)
        if resolved_status in ('uncertain', 'unresolved'):
            result['unresolved'].append({'paragraph_id': pid, 'status': resolved_status,
                                         'reasons': reasons or ['explicit_uncertain']})
    result['accounting_complete'] = (schema_ok and not result['rejected'] and
                                     all(c['status'] != 'unresolved' for c in result['coverage']))
    if not schema_ok:
        # Keep locally valid candidates but report that the envelope itself
        # cannot certify coverage, even if every row happened to be present.
        result['coverage_notes'].append('coverage_envelope_not_validated')
    return result
