"""Offline recovery of uniquely locatable citation IDs; preserve raw model output."""
from copy import deepcopy
from pathlib import Path
import argparse
import json

from api import parse_completion
from batch_contract import enrichment
from batch_plan import verify
from batch_run import load_result
from corpus import normal, read, save, sha
from runner import fingerprint


def align(record, units):
    fixed = deepcopy(record); changes = []
    by_id = {u['unit_id']: u for u in units}
    if not isinstance(fixed, dict) or not isinstance(fixed.get('evidence'), list):
        return fixed, changes
    for e in fixed['evidence']:
        if not isinstance(e, dict) or not isinstance(e.get('quote'), str):
            continue
        quote = normal(e['quote']); old = e.get('unit_id')
        if len(quote) < 8:
            continue
        if isinstance(old, str) and old in by_id and quote in normal(by_id[old]['text']):
            continue
        matches = [u['unit_id'] for u in units if quote in normal(u['text'])]
        if len(matches) == 1:
            e['unit_id'] = matches[0]
            changes.append({'field': e.get('field'), 'old_unit_id': old, 'new_unit_id': matches[0]})
    return fixed, changes


def canonical(record):
    return fingerprint({k: record[k] for k in ['paper_id', 'domain', 'negative_type',
        'experimental_setting', 'directness', 'fields', 'qualifiers']})


def recover(workspace):
    workspace = Path(workspace); manifest = verify(workspace)
    state = read(workspace / 'batch_state.json')
    records = {canonical(r): r for r in read(workspace / 'exports/records.json')}
    baseline = len(records); modifications = []; newly_recovered = []
    for key, entry in state['tasks'].items():
        if entry['stage'] != 'enrichment' or not entry.get('response_sha256'):
            continue
        if sha(workspace / entry['response_path']) != entry['response_sha256']:
            raise ValueError('Stored response changed')
        original = parse_completion(read(workspace / entry['response_path']))
        if not isinstance(original, dict) or not isinstance(original.get('items'), list):
            continue
        payload = deepcopy(original); changes_by_id = {}
        job = read(workspace / f'jobs/{entry["job_id"]}.json')
        for item in payload['items']:
            if not isinstance(item, dict) or 'record' not in item:
                continue
            fixed, changes = align(item['record'], job['primary_units'] + job['context_units'])
            item['record'] = fixed
            if changes: changes_by_id[item.get('candidate_id')] = changes
        if not changes_by_id:
            continue
        discovery = load_result(workspace, state['tasks'][entry['job_id'] + ':discovery'])
        offset = entry['group'] * manifest['batch_size']
        candidates = discovery['accepted'][offset:offset + manifest['batch_size']]
        checked = enrichment(payload, job, candidates)
        modifications.append({'task_id': key, 'response_sha256': entry['response_sha256'],
                              'changes': changes_by_id, 'rejected_after_repair': checked['rejected']})
        for item in checked['accepted']:
            if item['candidate_id'] not in changes_by_id:
                continue
            r = item['record']; digest = canonical(r)
            if digest not in records:
                r.update(citation_id_repairs=changes_by_id[item['candidate_id']],
                         repair_basis='Unique exact quote match within supplied units; no field values changed',
                         original_response_sha256=entry['response_sha256'])
                records[digest] = r; newly_recovered.append(r)
    out = workspace / 'citation_recovery'
    save(out / 'combined_records.json', list(records.values()))
    save(out / 'recovered_only.json', newly_recovered)
    save(out / 'repair_log.json', modifications)
    summary = {'baseline_records': baseline, 'new_records_from_unique_id_repair': len(newly_recovered),
               'combined_records': len(records), 'modified_response_tasks': len(modifications),
               'api_requests_sent': 0, 'original_outputs_unchanged': True,
               'semantic_review': 'pending; unique quote location is not evidence of field meaning',
               'limits': 'No missing field evidence invented, no text or values changed, ambiguous matches remain quarantined'}
    save(out / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(recover(args.workspace), ensure_ascii=False, indent=2))
