"""Read-only progress and locked, provenance-preserving exports for v2 jobs."""
from collections import Counter
import csv
from pathlib import Path

from corpus import read, save, sha
from export import safe_cell
from runner import fingerprint
from candidate_workspace import verify


def result(workspace, entry):
    path = Path(workspace) / entry['result_path']
    if sha(path) != entry['result_sha256']:
        raise ValueError('Stored result changed')
    return read(path)


def snapshot(workspace):
    workspace = Path(workspace)
    m = verify(workspace)
    state = read(workspace / 'candidate_state.json') if (workspace / 'candidate_state.json').exists() else {'tasks': {}, 'attempts': []}
    tasks = state['tasks']
    records, audits, failures, paper_rows = {}, [], [], []
    for paper in m['papers']:
        paper_jobs = []
        for jid in paper['job_ids']:
            discovery_entry = tasks.get(jid + ':discovery', {})
            if discovery_entry.get('status') != 'complete':
                paper_jobs.append('pending' if not discovery_entry else 'discovery_failed')
                continue
            d = result(workspace, discovery_entry)
            for rejected in d['rejected']:
                audits.append({'paper_id': paper['paper_id'], 'job_id': jid, 'stage': 'discovery',
                               'destination': 'quarantine', **rejected})
            if not d['accepted']:
                paper_jobs.append('processed_with_issues' if d['rejected'] else 'processed_no_candidates_found')
                continue
            group_path = workspace / 'groups' / (jid + '.json')
            groups = read(group_path)['groups'] if group_path.exists() else []
            if not groups:
                for candidate in d['accepted']:
                    audits.append({'paper_id': paper['paper_id'], 'job_id': jid,
                                   'candidate_id': candidate['candidate_id'], 'destination': 'pending_grouping'})
                paper_jobs.append('partial')
                continue
            job_complete, job_issues = True, bool(d['rejected'])
            for group_index, group in enumerate(groups):
                tid = jid + f':enrichment:{group_index:03d}'
                entry = tasks.get(tid, {})
                if entry.get('status') != 'complete':
                    job_complete = False
                    for candidate in group['candidates']:
                        audits.append({'paper_id': paper['paper_id'], 'job_id': jid,
                            'task_id': tid, 'candidate_id': candidate['candidate_id'],
                            'destination': entry.get('status', 'pending'), 'stage': 'enrichment'})
                    continue
                r = result(workspace, entry)
                contexts = {c['candidate_id']: c for c in group['candidate_contexts']}
                job_issues |= bool(r['rejected'] or r['unresolved'])
                for destination, items in [('quarantine', r['rejected']), ('unresolved', r['unresolved'])]:
                    for item in items:
                        audits.append({'paper_id': paper['paper_id'], 'job_id': jid,
                            'task_id': tid, 'stage': 'enrichment', 'destination': destination,
                            **item})
                for item in r['accepted']:
                    record, cid = item['record'], item['candidate_id']
                    key = fingerprint({k: record[k] for k in ('paper_id', 'domain', 'negative_type',
                        'experimental_setting', 'directness', 'fields', 'qualifiers')})
                    provenance = {'job_id': jid, 'task_id': tid, 'candidate_id': cid,
                        'source_sha256': record['source_sha256'], 'evidence': record['evidence'],
                        'field_search_status': record.get('field_search_status', {}),
                        'field_search_status_issues': record.get('field_search_status_issues', []),
                        'context_audit': contexts.get(cid),
                        'discovery_result_sha256': entry.get('discovery_result_sha256')}
                    if key not in records:
                        records[key] = dict(record, provenance=[], semantic_review='pending',
                                            ready_for_training=False, expert_gold=False)
                        # Status belongs to a provenance item, never to all merged sources.
                        records[key].pop('field_search_status', None)
                        records[key].pop('field_search_status_issues', None)
                    records[key]['provenance'].append(provenance)
                    audits.append({'paper_id': paper['paper_id'], 'job_id': jid, 'task_id': tid,
                        'candidate_id': cid, 'destination': 'mechanically_valid',
                        'record_key': records[key]['record_key'], **provenance})
            paper_jobs.append('partial' if not job_complete else
                              'processed_with_issues' if job_issues else 'processed_pending_review')
        complete = sum(s.startswith('processed') for s in paper_jobs)
        paper_rows.append({'paper_id': paper['paper_id'], 'doi': paper.get('doi'),
            'url': paper.get('url'), 'source_kind': paper.get('publication_kind',
                                                        'paper' if paper.get('doi') else 'corporate_material'),
            'source_sha256': paper.get('source_sha256'), 'availability': paper.get('availability'),
            'jobs': len(paper_jobs), 'jobs_processed': complete,
            'status': 'input_gap' if not paper_jobs else 'partial' if complete < len(paper_jobs)
                else 'processed_with_issues' if 'processed_with_issues' in paper_jobs
                else 'processed_pending_review',
            'input_error': paper.get('input_error'), 'coverage': paper.get('parsed_coverage')})
    failures = [dict(task_id=tid, **entry) for tid, entry in tasks.items() if entry['status'] != 'complete']
    summary = {'pipeline': m['pipeline'], 'unique_records': len(records), 'papers': paper_rows,
        'paper_status': dict(Counter(row['status'] for row in paper_rows)),
        'candidate_destinations': dict(Counter(row['destination'] for row in audits)),
        'failed_tasks': len(failures), 'workspace_requests': len(state['attempts']),
        'reused_tasks': sum(bool(e.get('reused_from')) for e in tasks.values()),
        'task_status': dict(Counter(e['status'] for e in tasks.values())),
        'stop_reason': state.get('stop_reason'), 'expert_gold': False, 'training_ready_records': 0,
        'all_sources_processed': bool(paper_rows) and all(
            row['status'].startswith('processed') for row in paper_rows),
        'all_readable_sources_processed': bool(m['job_ids']) and all(
            row['status'].startswith('processed') for row in paper_rows if row['jobs'])}
    if state.get('budget_path'):
        import batch_budget
        summary['shared_budget'] = batch_budget.status(state['budget_path'])
    return summary, list(records.values()), audits, failures


def _csv(path, rows, columns):
    # Unique temporary file avoids partially visible CSV exports.
    import os, uuid
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: safe_cell(row.get(k)) for k in columns} for row in rows)
    os.replace(temp, path)


def export(workspace):
    workspace = Path(workspace)
    import batch_budget
    with batch_budget.ledger_lock(workspace / 'export'):
        summary, records, audits, failures = snapshot(workspace)
        out = workspace / 'exports'
        for name, rows in [('records', records), ('candidate_audit', audits),
                           ('failures', failures), ('paper_coverage', summary['papers'])]:
            save(out / (name + '.json'), rows)
        from contract import FIELDS
        _csv(out / 'records.csv', [dict(r, **r['fields']) for r in records],
             ['record_key', 'paper_id', 'doi', 'domain', 'negative_type', *FIELDS,
              'evidence', 'provenance', 'semantic_review', 'ready_for_training'])
        _csv(out / 'candidate_audit.csv', audits, ['paper_id', 'job_id', 'task_id',
             'candidate_id', 'destination', 'record_key', 'source_sha256',
             'field_search_status', 'field_search_status_issues', 'context_audit',
             'evidence', 'errors', 'reason'])
        _csv(out / 'paper_coverage.csv', summary['papers'], ['paper_id', 'doi', 'url',
             'source_kind', 'availability', 'jobs', 'jobs_processed', 'status', 'input_error', 'coverage'])
        _csv(out / 'failures.csv', failures, ['task_id', 'status', 'failure_kind', 'attempt_id'])
        save(out / 'summary.json', summary)
        lines = ['# MolGlueDB 提取进度', '',
                 f'来源数：{len(summary["papers"])}；记录数：{len(records)}。', '',
                 f'来源状态：{summary["paper_status"]}。', '',
                 f'候选去向：{summary["candidate_destinations"]}。', '',
                 f'停止原因：{summary["stop_reason"] or "尚未运行或已到达队列末尾"}。', '',
                 f'本工作区新请求：{summary["workspace_requests"]}；复用任务：{summary["reused_tasks"]}。', '',
                 '自动记录均待内容复核；没有发现候选不代表文献没有阴性结果。', '',
                 '逐篇范围见 paper_coverage.csv；逐候选依据见 candidate_audit.csv。', '']
        if summary.get('shared_budget'):
            b = summary['shared_budget']
            lines.extend([f'共享生成预算：{b["requests_reserved"]}/{b["max_requests"]}次；'
                f'保守token预留：{b["reserved_token_estimate"]}；已上报用量：{b["reported_total_tokens"]}。', '',
                f'用量未上报的请求：{b["attempts_without_usage"]}次；未知不计为零，费用以服务账单为准。', ''])
        import os
        tmp = out / 'summary.md.tmp'
        tmp.write_text('\n'.join(lines), encoding='utf-8')
        os.replace(tmp, out / 'summary.md')
        return summary
