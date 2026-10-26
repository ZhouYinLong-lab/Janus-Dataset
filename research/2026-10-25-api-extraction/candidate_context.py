"""Offline candidate context selection; exhaustive body discovery stays unchanged."""
from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
import re

from corpus import parse_source, sha
from linked_context import LinkedContext

JOB_CONTEXT_CAP = 18_000
MAX_METHOD_UNITS = 2
MAX_NEARBY_BODY_UNITS = 2
CONTEXT_ROLES = ('explicitly_referenced_figure_or_table',
                 'adjacent_body_paragraph', 'lexically_linked_method')
_METHOD_SECTION = re.compile(
    r'\b(methods?|experimental|procedures?|protocols?|assays?|cell culture)\b', re.I)


def _document(path, paper_id, source_sha256, document_path=None):
    """Prefer frozen parsed units and verify the actual source on every call."""
    if sha(path) != source_sha256:
        raise ValueError('Source changed after the extraction job was prepared')
    if document_path:
        document = json.loads(Path(document_path).read_text(encoding='utf-8-sig'))
    else:
        try:
            from source_formats import parse_document
        except ModuleNotFoundError as error:
            if error.name != 'source_formats':
                raise
            parse_document = parse_source
        document = parse_document(path, paper_id)
    if document['source_sha256'] != source_sha256 or sha(path) != source_sha256:
        raise ValueError('Source changed after the extraction job was prepared')
    if document['paper_id'] != paper_id:
        raise ValueError('Parsed document does not belong to this paper')
    # LinkedContext must reread the same verified source, even if the frozen
    # document was relocated. Do not mutate the frozen parsed object.
    return dict(document, source_path=str(Path(path).resolve()))


def _parent_id(unit):
    return unit.get('parent_unit_id', unit['unit_id'])


def _tokens(value):
    return set(re.findall(r'[a-z0-9]{2,}', value.casefold()))


def _explicit_pieces(unit, units):
    """Use existing, verifiable target slices; never infer panels."""
    pieces = []
    for other in units.values():
        if other['unit_id'] == unit['unit_id'] or _parent_id(other) != unit['unit_id']:
            continue
        start, end = other.get('char_start'), other.get('char_end')
        if (type(start) is int and type(end) is int and
                0 <= start < end <= len(unit['text']) and
                other['text'] == unit['text'][start:end] and
                other.get('kind') == unit['kind']):
            pieces.append(other)
    if not pieces:
        return [unit], False
    pieces.sort(key=lambda u: (u['char_start'], u['char_end'], u['unit_id']))
    covered = 0
    gap = False
    for piece in pieces:
        gap |= piece['char_start'] > covered
        covered = max(covered, piece['char_end'])
    incomplete = gap or covered < len(unit['text'])
    if incomplete and len(unit['text']) <= JOB_CONTEXT_CAP:
        # The original is available and fits by itself. Prefer its complete
        # text over a partial set of old slices; crowded groups can split.
        return [unit], False
    return pieces, incomplete


def _requirements(job, candidates):
    document = _document(job['source_path'], job['paper_id'], job['source_sha256'],
                         job.get('document_path'))
    source_units = {u['unit_id']: u for u in document['units']}
    job_primary = {u['unit_id']: u for u in job['primary_units']}
    # Normalized HTML/PDF units need not have XML locators. They still support
    # conservative section-based prose/method selection, without invented refs.
    normalized = (document.get('source_format') in {'html', 'pdf'} or
                  Path(document['source_path']).suffix.lower() in {'.html', '.htm', '.pdf'})
    linked = (LinkedContext(document)
              if not normalized and all(u.get('locator') for u in document['units']) else None)
    has_references = linked is not None and linked.xml_status in {'jats', 'bioc_text_labels'}

    def section(unit):
        if linked is not None and linked.xml_status == 'jats':
            return linked._section(unit)
        return unit.get('section', '')

    body = [u for u in document['units'] if u['kind'] == 'body_paragraph']
    body_positions = {u['unit_id']: i for i, u in enumerate(body)}
    methods = {u['unit_id'] for u in body if _METHOD_SECTION.search(u.get('section', ''))}
    if linked is not None:
        methods.update(linked.method_units)
    all_units = dict(source_units)
    for unit in job.get('context_units', []):
        # Frozen fragments supplement the original source; they never replace it.
        all_units.setdefault(unit['unit_id'], unit)
    requirements = []
    seen = set()
    for candidate in candidates:
        cid, uid = candidate['candidate_id'], candidate['unit_id']
        if cid in seen:
            raise ValueError(f'Duplicate candidate_id: {cid}')
        seen.add(cid)
        scanned = job_primary.get(uid)
        if scanned is None or scanned.get('kind') != 'body_paragraph':
            raise ValueError(f'Candidate {cid} does not point to a scanned body unit')
        parent = _parent_id(scanned)
        source_anchor = source_units.get(parent, source_units.get(uid))
        if source_anchor is None or source_anchor['kind'] != 'body_paragraph':
            raise ValueError(f'Candidate {cid} has no source body paragraph')
        # Keep the complete frozen primary unit, including when it is a slice.
        # Each candidate retains its own result quote in the candidates payload.
        anchor = deepcopy(scanned)
        refs = (linked.references([source_anchor])
                if has_references and parent in source_units else [])
        roles = OrderedDict()
        incomplete_fragments = []
        ref_pieces = {}
        for ref in refs:
            for target in ref.get('target_unit_ids', []):
                unit = source_units.get(target)
                if not unit or unit['kind'] not in {'table', 'figure_caption'}:
                    continue
                pieces, incomplete = _explicit_pieces(unit, all_units)
                ref_pieces[target] = [u['unit_id'] for u in pieces]
                if incomplete:
                    incomplete_fragments.append(target)
                for piece in pieces:
                    roles[piece['unit_id']] = CONTEXT_ROLES[0]

        pos = body_positions.get(source_anchor['unit_id'])
        if pos is not None and section(source_anchor):
            nearby = []
            for index in (pos - 1, pos + 1):
                if not 0 <= index < len(body):
                    continue
                other = body[index]
                if section(other) == section(source_anchor):
                    nearby.append(other['unit_id'])
            for other_id in nearby[:MAX_NEARBY_BODY_UNITS]:
                roles.setdefault(other_id, CONTEXT_ROLES[1])

        query = ' '.join([candidate.get('quote', ''),
                          ' '.join(candidate.get('compound_mentions', [])),
                          ' '.join(candidate.get('condition_mentions', []))])
        query_tokens = _tokens(query)
        ranked = []
        for method_id in methods:
            unit = source_units.get(method_id)
            if not unit or unit['kind'] != 'body_paragraph' or method_id == parent:
                continue
            overlap = len(query_tokens & _tokens(unit['text']))
            if overlap:
                ranked.append((-overlap, method_id))
        for _, method_id in sorted(ranked)[:MAX_METHOD_UNITS]:
            roles.setdefault(method_id, CONTEXT_ROLES[2])
        requirements.append({'candidate_id': cid, 'anchor': anchor, 'roles': roles,
                             'references': refs, 'ref_pieces': ref_pieces,
                             'incomplete_fragments': incomplete_fragments})
    return requirements, all_units


def _select_contexts(requirements, all_units):
    shared = OrderedDict()
    used = 0

    def supply(unit):
        nonlocal used
        if unit['unit_id'] not in shared and used + len(unit['text']) <= JOB_CONTEXT_CAP:
            shared[unit['unit_id']] = deepcopy(unit)
            used += len(unit['text'])

    for requirement in requirements:
        supply(requirement['anchor'])
    # Allocate each priority round-robin. The same supplied unit costs once,
    # including when it is another candidate's anchor or shared nearby prose.
    for role in CONTEXT_ROLES:
        queues = [[uid for uid, value in r['roles'].items() if value == role]
                  for r in requirements]
        for index in range(max(map(len, queues), default=0)):
            for queue in queues:
                if index < len(queue):
                    supply(all_units[queue[index]])

    maps = []
    for requirement in requirements:
        anchor_id = requirement['anchor']['unit_id']
        roles = requirement['roles']
        supplied = [uid for uid in roles if uid in shared and uid != anchor_id]
        omitted = [uid for uid in roles if uid not in shared]
        reasons = []
        if anchor_id not in shared:
            omitted.insert(0, anchor_id)
            reasons.append('anchor_exceeds_group_context_cap')
        if any(uid not in shared for uid in roles):
            reasons.append('context_cap')
        if requirement['incomplete_fragments']:
            omitted.extend(requirement['incomplete_fragments'])
            reasons.append('incomplete_explicit_unit_fragments')
        refs = deepcopy(requirement['references'])
        for ref in refs:
            targets = ref.get('target_unit_ids', [])
            pieces = [uid for target in targets
                      for uid in requirement['ref_pieces'].get(target, [])]
            ref['selected_unit_ids'] = [uid for uid in pieces if uid in shared]
            ref['omitted_unit_ids'] = [uid for uid in pieces if uid not in shared]
            ref['omitted_unit_ids'].extend(
                uid for uid in targets if uid in requirement['incomplete_fragments'])
            if not targets or not pieces:
                ref['status'] = 'unresolved'
                reasons.append('unresolved_explicit_reference')
            elif ref['omitted_unit_ids']:
                ref['status'] = ('partial_context_cap' if ref['selected_unit_ids']
                                 else 'omitted_context_cap')
            else:
                ref['status'] = 'selected'
        maps.append({
            'candidate_id': requirement['candidate_id'],
            'anchor_unit_id': anchor_id,
            'context_unit_ids': supplied,
            'allowed_evidence_unit_ids': ([anchor_id] if anchor_id in shared else []) + supplied,
            'context_roles': {uid: roles[uid] for uid in supplied},
            'references': refs,
            'omitted_context_unit_ids': list(dict.fromkeys(omitted)),
            'context_chars': sum(len(shared[uid]['text']) for uid in supplied),
            'context_complete': not reasons,
            'omission_reason': ';'.join(dict.fromkeys(reasons)) or None,
        })
    return maps, list(shared.values())


def build_candidate_contexts(job, candidates):
    """Preserve the v1 (candidate maps, deduplicated units) return interface.

    Full frozen primary anchors and selected support together have an 18k text
    cap. Maps report supply gaps, not absence of information in the full paper.
    Candidate objects and job units are unchanged. Use plan_candidate_groups to
    split a crowded group before constructing requests.
    """
    requirements, units = _requirements(job, candidates)
    return _select_contexts(requirements, units)


def plan_candidate_groups(job, candidates, max_candidates=8):
    """Return offline groups with candidates, candidate_contexts, context_units.

    Split at max_candidates first, then recursively bisect any group with a
    supply gap. A singleton keeps explicit omission metadata. This function
    performs no generation and does not schedule or send requests.
    """
    if type(max_candidates) is not int or max_candidates < 1:
        raise ValueError('max_candidates must be a positive integer')
    candidates = list(candidates)
    if not candidates:
        return []
    requirements, units = _requirements(job, candidates)

    def plan(start, end):
        maps, selected = _select_contexts(requirements[start:end], units)
        if end - start > 1 and any(not entry['context_complete'] for entry in maps):
            middle = (start + end) // 2
            return plan(start, middle) + plan(middle, end)
        return [{'candidates': deepcopy(candidates[start:end]),
                 'candidate_contexts': maps, 'context_units': selected}]

    groups = []
    for start in range(0, len(candidates), max_candidates):
        groups.extend(plan(start, min(start + max_candidates, len(candidates))))
    return groups
