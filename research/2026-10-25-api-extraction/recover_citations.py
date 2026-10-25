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


def bind_anchor(record, anchor, primary_units):
    """Bind server-owned provenance only when the model's result is literal source text."""
    fixed = deepcopy(record)
    if (not isinstance(fixed, dict) or not isinstance(fixed.get('evidence'), list)
            or not isinstance(fixed.get('fields'), dict) or not isinstance(anchor, dict)):
        return fixed, []
    quote, uid = anchor.get('quote'), anchor.get('unit_id')
    value = fixed['fields'].get('result_text')
    primary = {u['unit_id']: u['text'] for u in primary_units}
    if (not isinstance(quote, str) or not isinstance(value, str) or uid not in primary
            or not 8 <= len(normal(quote)) or len(quote) > 3000
            or len(normal(value)) < 8 or normal(value) not in normal(quote)
            or normal(quote) not in normal(primary[uid])):
        return fixed, []
    if any(isinstance(e, dict) and e.get('field') == 'result_text'
           and e.get('unit_id') == uid and isinstance(e.get('quote'), str)
           and normal(e['quote']) == normal(quote) for e in fixed['evidence']):
        return fixed, []
    fixed['evidence'].append({'field': 'result_text', 'unit_id': uid, 'quote': quote})
    return fixed, [{'field': 'result_text', 'old_unit_id': None, 'new_unit_id': uid,
                    'rule': 'verified_candidate_anchor_for_literal_result_text'}]


def canonical(record):
    return fingerprint({k: record[k] for k in ['paper_id', 'domain', 'negative_type',
        'experimental_setting', 'directness', 'fields', 'qualifiers']})


def recover(workspace, bind_known_result_anchor=False):
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
        discovery = load_result(workspace, state['tasks'][entry['job_id'] + ':discovery'])
        offset = entry['group'] * manifest['batch_size']
        candidates = discovery['accepted'][offset:offset + manifest['batch_size']]
        anchors = {c['candidate_id']: c for c in candidates}
        for item in payload['items']:
            if not isinstance(item, dict) or 'record' not in item:
                continue
            fixed, changes = align(item['record'], job['primary_units'] + job['context_units'])
            if bind_known_result_anchor:
                fixed, anchor_changes = bind_anchor(fixed, anchors.get(item.get('candidate_id')),
                                                    job['primary_units'])
                changes += anchor_changes
            item['record'] = fixed
            if changes: changes_by_id[item.get('candidate_id')] = changes
        if not changes_by_id:
            continue
        checked = enrichment(payload, job, candidates)
        modifications.append({'task_id': key, 'response_sha256': entry['response_sha256'],
                              'changes': changes_by_id, 'rejected_after_repair': checked['rejected']})
        for item in checked['accepted']:
            if item['candidate_id'] not in changes_by_id:
                continue
            r = item['record']; digest = canonical(r)
            if digest not in records:
                r.update(citation_id_repairs=changes_by_id[item['candidate_id']],
                         repair_basis='Exact supplied quote identity and optional verified candidate anchor; no field values changed',
                         original_response_sha256=entry['response_sha256'])
                records[digest] = r; newly_recovered.append(r)
    out = workspace / 'citation_recovery'
    save(out / 'combined_records.json', list(records.values()))
    save(out / 'recovered_only.json', newly_recovered)
    save(out / 'repair_log.json', modifications)
    summary = {'baseline_records': baseline, 'new_records_from_provenance_repair': len(newly_recovered),
               'new_records_from_unique_id_repair': sum(any(c.get('rule') != 'verified_candidate_anchor_for_literal_result_text'
                   for c in r['citation_id_repairs']) for r in newly_recovered),
               'new_records_with_candidate_anchor_binding': sum(any(c.get('rule') == 'verified_candidate_anchor_for_literal_result_text'
                   for c in r['citation_id_repairs']) for r in newly_recovered),
               'candidate_anchor_binding_enabled': bind_known_result_anchor,
               'combined_records': len(records), 'modified_response_tasks': len(modifications),
               'api_requests_sent': 0, 'original_outputs_unchanged': True,
               'semantic_review': 'pending; unique quote location is not evidence of field meaning',
               'limits': 'No scientific text or values changed. Optional result_text anchor binding requires literal result text inside the verified primary-source candidate. Other missing field evidence is never filled; ambiguous matches remain quarantined.'}
    save(out / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--bind-known-result-anchor', action='store_true')
    args = parser.parse_args()
    print(json.dumps(recover(args.workspace, args.bind_known_result_anchor), ensure_ascii=False, indent=2))
