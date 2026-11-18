"""Freeze source-first assistant references; never call a model or copy to prompts."""
import argparse
from copy import deepcopy
from pathlib import Path
from corpus import read, save, sha

DOIS = ('10.1002/advs.202104344', '10.1002/advs.202412985',
        '10.1002/advs.202413676', '10.1002/ctm2.881', '10.1038/s41586-020-2374-x')


def freeze(root, legacy, public_index=None):
    root = Path(root)
    inventory = read(root/'papers.json')
    if len(inventory) != 5 or {p['doi'].lower() for p in inventory} != set(DOIS):
        raise ValueError('Fixed five-paper inventory required')
    references = []
    artifacts = {}
    for name in ('reference_A.json', 'reference_B.json'):
        path = root/name
        data = read(path)
        if data.get('expert_gold') is not False or data.get('full_body_reference_complete') is not True:
            raise ValueError('Assistant whole-body reference required: ' + name)
        references.extend(deepcopy(data['papers']))
        artifacts[name] = sha(path)
    old = read(legacy)
    b296 = deepcopy(next(p for p in old['papers'] if p['paper_id'] == 'B296'))
    b296['reference_origin'] = 'Reused pre-existing assistant full-body reference; prior development exposure'
    references.append(b296)
    artifacts['legacy_reference'] = sha(legacy)
    by_id = {p['paper_id']: p for p in references}
    if len(by_id) != 5 or set(by_id) != {p['paper_id'] for p in inventory}:
        raise ValueError('Exactly the fixed papers must have references')
    index = []
    for metadata in inventory:
        pid = metadata['paper_id']
        doc = read(root/f'{pid}.json')
        ref = by_id[pid]
        body = {u['unit_id']: u for u in doc['units'] if u['kind'] == 'body_paragraph'}
        reviewed = [r['unit_id'] for r in ref['units_reviewed']]
        if (len(reviewed) != len(set(reviewed)) or set(reviewed) != set(body)
                or ref['source_sha256'] != doc['source_sha256']
                or any(r['decision'] not in {'has_negative','no_eligible_negative','uncertain'}
                       for r in ref['units_reviewed'])):
            raise ValueError('Invalid paragraph coverage/hash: ' + pid)
        negative_ids = [n['id'] for n in ref['negatives']]
        if len(set(negative_ids)) != len(negative_ids):
            raise ValueError('Duplicate reference IDs: ' + pid)
        for negative in ref['negatives']:
            if negative['unit_id'] not in body or not negative['quote'] or negative['quote'] not in body[negative['unit_id']]['text']:
                raise ValueError('Reference must be a literal source substring: ' + negative['id'])
        index.append({'paper_id': pid, 'doi': metadata['doi'], 'source_sha256': doc['source_sha256'],
            'document_sha256': sha(root/f'{pid}.json'), 'body_units_reviewed': len(reviewed),
            'negative_reference_count': len(ref['negatives']),
            'core_reference_count': sum(n.get('core_case') is True for n in ref['negatives']),
            'uncertain_count': len(ref.get('uncertain', [])),
            'references': [{'id': n['id'], 'unit_id': n['unit_id'],
                'core_case': n.get('core_case') is True} for n in ref['negatives']]})
    frozen = {'protocol': 'sentence_v3', 'reviewer_kind': 'assistant', 'expert_gold': False,
        'full_body_reference_complete': True, 'use_in_api_prompts': False,
        'reference_status': 'frozen_before_sentence_v3_generation',
        'independence': 'Source-first assistant reference; B296 reuses documented development-exposed review, not blind expert gold.',
        'papers': [by_id[p['paper_id']] for p in inventory], 'source_artifact_hashes': artifacts}
    target = root/'acceptance_reference.json'
    if target.exists() and read(target) != frozen:
        raise ValueError('Frozen reference exists; changes require a separately versioned reference')
    save(target, frozen)
    result = {'protocol': 'sentence_v3', 'expert_gold': False, 'reviewer_kind': 'assistant',
        'reference_sha256': sha(target), 'private_reference_path': 'local/sentence_v3_evaluation/acceptance_reference.json',
        'inventory_sha256': sha(root/'papers.json'), 'papers': index,
        'core_reference_count': sum(p['core_reference_count'] for p in index),
        'body_units_reviewed': sum(p['body_units_reviewed'] for p in index),
        'real_generation_completed': False, 'release_status': 'blocked_budget_200_of_200',
        'scope': 'Narrative body only; includes explicit group/boundary and rescue controls. Uncertain entries excluded from scored core.',
        'independence': frozen['independence']}
    if public_index:
        save(public_index, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--legacy', required=True, type=Path)
    parser.add_argument('--public-index', type=Path)
    args = parser.parse_args()
    result = freeze(args.root, args.legacy, args.public_index)
    print({k: result[k] for k in ('core_reference_count', 'body_units_reviewed', 'release_status')})
