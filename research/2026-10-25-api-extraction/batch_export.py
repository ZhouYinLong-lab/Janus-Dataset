"""Export every candidate destination, coverage gap and interpretation variant."""
from collections import Counter
import csv
from pathlib import Path

import batch_budget as budget
from batch_plan import verify
from batch_run import load_result
from corpus import read, save
from export import safe_cell
from runner import fingerprint


def export(workspace):
    workspace = Path(workspace); m = verify(workspace)
    path = workspace / 'batch_state.json'
    state = read(path) if path.exists() else {'tasks': {}, 'attempts': []}
    records, quarantine, unresolved, discoveries, jobs = {}, [], [], [], []
    for jid in m['job_ids']:
        job = read(workspace / f'jobs/{jid}.json')
        dentry = state['tasks'].get(jid + ':discovery', {})
        row = {'job_id': jid, 'paper_id': job['paper_id'],
               'primary_units': [u['unit_id'] for u in job['primary_units']],
               'discovery_status': dentry.get('status', 'pending'), 'candidates': None,
               'enrichment_groups_expected': None, 'enrichment_groups_complete': 0,
               'discovery_rejected': 0, 'enrichment_rejected': 0, 'unresolved': 0,
               'status': 'pending'}
        if dentry.get('status') != 'complete':
            row['status'] = 'pending' if not dentry else 'discovery_failed'
            jobs.append(row); continue
        result = load_result(workspace, dentry)
        cs = result['accepted']; size = m['batch_size']
        discoveries.extend(dict(c, job_id=jid, paper_id=job['paper_id']) for c in cs)
        quarantine.extend(dict(r, stage='discovery', job_id=jid) for r in result['rejected'])
        row.update(candidates=len(cs), discovery_rejected=len(result['rejected']),
                   enrichment_groups_expected=(len(cs) + size - 1) // size,
                   no_candidate_reason=result.get('no_candidate_reason'))
        for offset in range(0, len(cs), size):
            group = offset // size
            entry = state['tasks'].get(jid + f':enrichment:{group:03d}', {})
            if entry.get('status') != 'complete':
                unresolved.extend({'job_id': jid, 'candidate_id': c['candidate_id'],
                    'reason': 'enrichment_' + entry.get('status', 'pending')}
                    for c in cs[offset:offset + size])
                row['unresolved'] += len(cs[offset:offset + size]); continue
            r = load_result(workspace, entry)
            row['enrichment_groups_complete'] += 1
            row['enrichment_rejected'] += len(r['rejected'])
            row['unresolved'] += len(r['unresolved'])
            quarantine.extend(dict(v, stage='enrichment', job_id=jid, group=group) for v in r['rejected'])
            unresolved.extend(dict(v, job_id=jid, group=group) for v in r['unresolved'])
            for item in r['accepted']:
                record = item['record']
                # Only exact canonical records merge; all qualifiers/directness variants survive.
                digest = fingerprint({k: record[k] for k in ['paper_id', 'domain', 'negative_type',
                    'experimental_setting', 'directness', 'fields', 'qualifiers']})
                provenance = {'job_id': jid, 'candidate_id': item['candidate_id'],
                              'discovery_result_sha256': entry['discovery_result_sha256'],
                              'evidence': record['evidence']}
                if digest not in records:
                    records[digest] = dict(record, record_key=job['paper_id'] + ':' + digest[:20],
                                           provenance=[provenance])
                else:
                    records[digest]['provenance'].append(provenance)
        if row['enrichment_groups_complete'] < row['enrichment_groups_expected']:
            row['status'] = 'enrichment_incomplete'
        elif row['discovery_rejected'] or row['enrichment_rejected'] or row['unresolved']:
            row['status'] = 'processed_with_issues'
        elif not cs:
            row['status'] = 'processed_no_candidates_found'
        else:
            row['status'] = 'processed_not_semantically_reviewed'
        jobs.append(row)
    paper_rows = []
    for p in m['papers']:
        js = [j for j in jobs if j['paper_id'] == p['paper_id']]
        finished = sum(j['status'].startswith('processed_') for j in js)
        paper_rows.append({'paper_id': p['paper_id'], 'doi': p.get('doi'),
            'source_sha256': p.get('source_sha256'), 'jobs': len(js),
            'jobs_processed': finished, 'input_error': p.get('input_error'),
            'status': 'input_gap' if not js else 'partial' if finished < len(js)
                else 'processed_with_issues' if any(j['status'] == 'processed_with_issues' for j in js)
                else 'processed_not_semantically_reviewed'})
    out = workspace / 'exports'; values = list(records.values())
    for name, data in [('records', values), ('discovery_candidates', discoveries),
                       ('quarantine', quarantine), ('unresolved', unresolved), ('job_coverage', jobs),
                       ('primary_candidates', [r for r in values if r['primary_candidate']]),
                       ('other_or_risk_records', [r for r in values if not r['primary_candidate']])]:
        save(out / (name + '.json'), data)
    columns = ['record_key', 'paper_id', 'doi', 'domain', 'negative_type', 'experimental_setting',
               'compound', 'target', 'construct', 'assay', 'cell_line', 'treatment_time',
               'tested_concentration', 'perturbation', 'endpoint', 'result_text', 'qualifiers',
               'evidence', 'provenance', 'semantic_review', 'ready_for_training']
    with (out / 'records.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore'); writer.writeheader()
        for r in values:
            writer.writerow({k: safe_cell(v) for k, v in dict(r, **r['fields']).items() if k in columns})
    failures = [dict(task_id=k, **v) for k, v in state['tasks'].items() if v['status'] != 'complete']
    save(out / 'failures.json', failures)
    summary = {'pipeline': m['pipeline'], 'unique_records': len(values),
               'primary_candidates': sum(r['primary_candidate'] for r in values),
               'discovered_candidates': len(discoveries), 'quarantined_entries': len(quarantine),
               'unresolved_candidates': len(unresolved), 'failed_tasks': len(failures),
               'jobs': len(jobs), 'job_status': dict(Counter(j['status'] for j in jobs)),
               'papers': paper_rows, 'workspace_requests': len(state['attempts']),
               'shared_budget': budget.status(state['budget_path']) if state.get('budget_path') else None,
               'stop_reason': state.get('stop_reason'), 'training_ready_records': 0,
               'expert_gold': False, 'semantic_review': 'not performed by mechanical validation',
               'deduplication': 'Exact canonical records only; experiment identity and paraphrase equivalence not established'}
    save(out / 'summary.json', summary)
    return summary
