"""Revalidate saved sentence responses offline into a separate audit directory."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path

from api import parse_completion
from candidate_runtime import _checked, _check_state
from corpus import read, save, sha
from sentence_workflow import validate_response

HERE = Path(__file__).resolve().parent


def revalidate(workspace, out):
    workspace, out = Path(workspace).resolve(), Path(out).resolve()
    if out.is_relative_to(workspace) or out.exists():
        raise ValueError('Use a new audit directory outside the frozen workspace')
    manifest = read(workspace / 'manifest.json')
    if manifest.get('pipeline') != 'molgluedb_sentence_v3':
        raise ValueError('A frozen sentence_v3 workspace is required')
    # Verify the original frozen runtime, rather than comparing it with the new
    # validators. No prepared file, original result, state or ledger is changed.
    for name, digest in manifest['file_hashes'].items():
        _checked(workspace, name, digest)
    for name, digest in manifest['code_hashes'].items():
        _checked(workspace, 'runtime/' + name, digest)
    for paper in manifest['papers']:
        if paper.get('source_sha256') and sha(paper['source_path']) != paper['source_sha256']:
            raise ValueError('Original source changed: ' + paper['paper_id'])
    state_path = workspace / 'candidate_state.json'
    before = sha(state_path)
    state = read(state_path)
    _check_state(workspace, state)
    results, bases, revisions = {}, {}, {}
    for tid, entry in state['tasks'].items():
        if entry['stage'] != 'facts' or entry['status'] != 'complete':
            continue
        jid = entry['job_id']
        descriptor = state['groups'][jid]
        groups = read(_checked(workspace, descriptor['path'], descriptor['sha256']))['groups']
        context = deepcopy(groups[entry['group']])
        job = read(workspace / 'jobs' / (jid + '.json'))
        job.update(active_stage='facts', frozen_context=context)
        response = read(_checked(workspace, entry['response_path'], entry['response_sha256']))
        result = validate_response(parse_completion(response), job, context['candidates'])
        results[tid] = result
        bases[tid] = [deepcopy(item['record']) for item in result['accepted']]
    for tid, entry in state['tasks'].items():
        if entry['stage'] != 'conditions' or entry['status'] != 'complete':
            continue
        fact_tid = entry['job_id'] + f':facts:{entry["group"]:03d}'
        if fact_tid not in bases:
            raise ValueError('A completed conditions response has no valid facts input')
        descriptor = state['condition_groups'][tid]
        context = deepcopy(read(_checked(workspace, descriptor['path'], descriptor['sha256']))['group'])
        context['records'] = deepcopy(bases[fact_tid])
        job = read(workspace / 'jobs' / (entry['job_id'] + '.json'))
        job.update(active_stage='conditions', frozen_context=context)
        response = read(_checked(workspace, entry['response_path'], entry['response_sha256']))
        result = validate_response(parse_completion(response), job, context['candidates'])
        results[tid] = result
        for item in result['accepted']:
            record = item['record']
            revisions[(fact_tid, record['record_key'])] = record
    records = []
    for tid, rows in bases.items():
        for base in rows:
            record = deepcopy(revisions.get((tid, base['record_key']), base))
            record['offline_revalidation'] = {'workspace': str(workspace), 'facts_task': tid,
                'response_sha256': state['tasks'][tid]['response_sha256']}
            records.append(record)
    previous = read(workspace / 'exports/records.json')
    old = {r['record_key']: r for r in previous}
    changes = [{'record_key': r['record_key'], 'paper_id': r['paper_id'],
                'old_status': old.get(r['record_key'], {}).get('record_status'),
                'new_status': r['record_status'], 'semantic_flags': r.get('semantic_flags', [])}
               for r in records if old.get(r['record_key'], {}).get('record_status') != r['record_status']]
    summary = {'scope': 'Offline mechanical revalidation of saved responses; not content acceptance',
        'source_manifest_sha256': sha(workspace / 'manifest.json'), 'source_state_sha256': before,
        'validator_hashes': {name: sha(HERE / name) for name in ('facts_v3.py', 'sentence_workflow.py')},
        'records_before': len(previous), 'records_after': len(records),
        'status_before': dict(Counter(r['record_status'] for r in previous)),
        'status_after': dict(Counter(r['record_status'] for r in records)),
        'changed_status_records': len(changes), 'response_tasks_revalidated': len(results),
        'generation_requests': 0, 'expert_gold': False, 'content_acceptance_complete': False}
    if sha(state_path) != before:
        raise ValueError('Source run changed while being revalidated; retry after it stops')
    save(out / 'records.json', records)
    save(out / 'changes.json', changes)
    save(out / 'response_revalidations.json', results)
    save(out / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(revalidate(args.workspace, args.out), ensure_ascii=False, indent=2))
