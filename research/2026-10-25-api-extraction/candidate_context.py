"""Build candidate-scoped, source-linked context without changing body discovery."""
from collections import OrderedDict
from functools import lru_cache
import re

from corpus import parse_source
from linked_context import LinkedContext

JOB_CONTEXT_CAP = 18_000
MAX_METHOD_UNITS = 2
MAX_NEARBY_BODY_UNITS = 2


@lru_cache(maxsize=32)
def _document(path, paper_id, source_sha256):
    document = parse_source(path, paper_id)
    if document['source_sha256'] != source_sha256:
        raise ValueError('Source changed after the extraction job was prepared')
    return document


def _parent_id(unit):
    return unit.get('parent_unit_id', unit['unit_id'])


def _tokens(value):
    return set(re.findall(r'[a-z0-9]{2,}', value.casefold()))


def build_candidate_contexts(job, candidates):
    """Return compact per-candidate anchors/context plus a deduplicated unit map.

    Body discovery remains exhaustive and unchanged. Enrichment sees each original
    candidate quote, only uniquely linked table/figure units, nearby body context,
    and a small number of lexically relevant method paragraphs.
    """
    document = _document(job['source_path'], job['paper_id'], job['source_sha256'])
    source_units = {u['unit_id']: u for u in document['units']}
    job_primary = {u['unit_id']: u for u in job['primary_units']}
    linked = LinkedContext(document)
    body = [u for u in document['units'] if u['kind'] == 'body_paragraph']
    body_positions = {u['unit_id']: i for i, u in enumerate(body)}
    all_by_id = {u['unit_id']: u for u in document['units']}
    shared_units = OrderedDict()
    candidate_maps = []

    for candidate in candidates:
        candidate_id = candidate['candidate_id']
        unit_id = candidate['unit_id']
        scanned = job_primary.get(unit_id)
        if scanned is None:
            raise ValueError(f'Candidate {candidate_id} does not point to a scanned body unit')
        parent = _parent_id(scanned)
        source_anchor = source_units.get(parent)
        if source_anchor is None or source_anchor['kind'] != 'body_paragraph':
            raise ValueError(f'Candidate {candidate_id} has no source body paragraph')

        anchor = dict(scanned, text=candidate['quote'])
        # Resolve references against the full source paragraph, not just the quote.
        refs = linked.references([source_anchor])
        explicit_ids = sorted({uid for ref in refs for uid in ref.get('target_unit_ids', [])})
        explicit_ids = [uid for uid in explicit_ids if uid in all_by_id]

        context_ids = []
        context_roles = {}
        for uid in explicit_ids:
            context_roles[uid] = 'explicitly_referenced_figure_or_table'
            context_ids.append(uid)

        # Retain immediate prose around the result only within its source section.
        pos = body_positions.get(parent)
        if pos is not None:
            section = linked._section(source_anchor)
            nearby = []
            for i in range(max(0, pos - 1), min(len(body), pos + 2)):
                other = body[i]
                if other['unit_id'] == parent or linked._section(other) != section:
                    continue
                nearby.append((abs(i - pos), other['unit_id']))
            for _, uid in sorted(nearby)[:MAX_NEARBY_BODY_UNITS]:
                if uid not in context_roles:
                    context_roles[uid] = 'adjacent_body_paragraph'
                    context_ids.append(uid)

        # Methods elsewhere in the article are candidates only when their text
        # shares specific terms with this result. This avoids sending every method.
        query = ' '.join([candidate.get('quote', ''),
                          ' '.join(candidate.get('compound_mentions', [])),
                          ' '.join(candidate.get('condition_mentions', []))])
        query_tokens = _tokens(query)
        method_ranked = []
        for uid in linked.method_units:
            unit = all_by_id.get(uid)
            if not unit or unit['kind'] != 'body_paragraph' or uid == parent:
                continue
            overlap = len(query_tokens & _tokens(unit['text']))
            if overlap:
                method_ranked.append((-overlap, uid))
        for _, uid in sorted(method_ranked)[:MAX_METHOD_UNITS]:
            if uid not in context_roles:
                context_roles[uid] = 'lexically_linked_method'
                context_ids.append(uid)

        candidate_maps.append({
            'candidate_id': candidate_id,
            'anchor_unit_id': anchor['unit_id'],
            'context_unit_ids': [],
            'allowed_evidence_unit_ids': [anchor['unit_id']],
            'context_roles': {},
            'references': refs,
            'omitted_context_unit_ids': [],
            'context_chars': 0,
            '_context_priority': context_roles,
            '_context_order': context_ids,
        })
        shared_units.setdefault(anchor['unit_id'], anchor)

    # Keep the original per-job context budget while distributing it across
    # candidates. Explicitly referenced tables/figures win, then nearby prose,
    # then lexically linked methods. Round-robin prevents the first candidate
    # from consuming the whole budget when several candidates share a job.
    used = 0
    selected_context_ids = set()
    anchor_ids = {candidate['anchor_unit_id'] for candidate in candidate_maps}
    for role in ('explicitly_referenced_figure_or_table',
                 'adjacent_body_paragraph', 'lexically_linked_method'):
        positions = [0] * len(candidate_maps)
        while True:
            progressed = False
            for index, candidate_map in enumerate(candidate_maps):
                ordered = [uid for uid in candidate_map['_context_order']
                           if candidate_map['_context_priority'][uid] == role]
                if positions[index] >= len(ordered):
                    continue
                uid = ordered[positions[index]]
                positions[index] += 1
                progressed = True
                if uid in anchor_ids:
                    candidate_map['omitted_context_unit_ids'].append(uid)
                    continue
                size = len(all_by_id[uid]['text'])
                additional_size = 0 if uid in selected_context_ids else size
                if used + additional_size <= JOB_CONTEXT_CAP:
                    used += additional_size
                    selected_context_ids.add(uid)
                    candidate_map['context_unit_ids'].append(uid)
                    candidate_map['allowed_evidence_unit_ids'].append(uid)
                    candidate_map['context_roles'][uid] = role
                    candidate_map['context_chars'] += size
                    shared_units.setdefault(uid, all_by_id[uid])
                else:
                    candidate_map['omitted_context_unit_ids'].append(uid)
            if not progressed:
                break
    for candidate_map in candidate_maps:
        candidate_map.pop('_context_priority')
        candidate_map.pop('_context_order')

    return candidate_maps, list(shared_units.values())
