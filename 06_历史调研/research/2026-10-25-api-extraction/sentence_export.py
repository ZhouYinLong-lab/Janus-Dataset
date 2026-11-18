"""Read-only v3 snapshots and lossless per-observation JSON/CSV exports."""
from collections import Counter
from copy import deepcopy
import csv
import json
import os
from pathlib import Path
import uuid

from corpus import read, save, sha
from export import safe_cell
from facts_v3 import FIELDS
from sentence_workspace import PIPELINE, verify


def _artifact(workspace, name, digest):
    path = (workspace / name).resolve()
    if not path.is_relative_to(workspace.resolve()) or not digest or sha(path) != digest:
        raise ValueError('Saved sentence artifact changed: ' + str(name))
    return read(path)


def _result(workspace, entry):
    for kind in ('request', 'response'):
        if entry.get(kind + '_sha256'):
            _artifact(workspace, entry[kind + '_path'], entry[kind + '_sha256'])
    return _artifact(workspace, entry['result_path'], entry['result_sha256'])


def _notes(audits, paper_id, jid, stage, result, tid=None):
    for kind, destination in (('rejected', 'quarantine'), ('unresolved', 'unresolved')):
        for item in result.get(kind, []):
            audits.append({'paper_id': paper_id, 'job_id': jid, 'task_id': tid,
                           'stage': stage, 'destination': destination, 'details': deepcopy(item),
                           **{key: deepcopy(item[key]) for key in
                              ('candidate_id', 'record_id', 'paragraph_id', 'errors', 'reason', 'reasons')
                              if isinstance(item, dict) and key in item}})
    if result.get('coverage_notes') or not result.get('accounting_complete', False):
        audits.append({'paper_id': paper_id, 'job_id': jid, 'task_id': tid, 'stage': stage,
                       'destination': 'response_accounting',
                       'accounting_complete': result.get('accounting_complete', False),
                       'coverage_notes': deepcopy(result.get('coverage_notes', []))})


def _provenance(paper, jid, tid, entry, index):
    return {'paper_id': paper['paper_id'], 'doi': paper.get('doi'),
            'source_sha256': paper.get('source_sha256'), 'source_path': paper.get('source_path'),
            'job_id': jid, 'task_id': tid, 'stage': entry['stage'], 'record_index': index,
            **{key: entry.get(key) for key in
               ('request_path', 'request_sha256', 'response_path', 'response_sha256',
                'result_path', 'result_sha256', 'discovery_result_sha256', 'facts_result_sha256')}}


def _needs_conditions(record):
    endpoint = (record['values'].get('endpoint') or '').strip().casefold()
    return bool(record.get('endpoint_verification_required') or
                endpoint in {'', 'uncertain', 'unknown', 'activity', 'potency', 'ec50', '待定'} or
                (record['outcome_type'] == 'conditional_loss' and not record['values'].get('scope_condition')))


def _merge_evidence_records(records):
    """Build the unique evidence layer without deleting raw observations.

    The raw ``records`` export remains lossless.  The evidence layer groups
    repeated record keys and keeps every provenance occurrence so downstream
    review and RAG do not count repeated mentions as independent evidence.
    """
    merged = {}
    occurrences = {}
    for index, record in enumerate(records):
        key = record.get('record_key')
        if not key:
            continue
        occurrences.setdefault(key, []).append(index)
        if key not in merged:
            merged[key] = deepcopy(record)
            merged[key]['raw_record_indexes'] = [index]
            merged[key]['raw_observation_count'] = 1
            merged[key]['source_occurrences'] = deepcopy(record.get('sources', []))
            continue
        target = merged[key]
        target['raw_record_indexes'].append(index)
        target['raw_observation_count'] += 1
        for source in record.get('sources', []):
            if source not in target['source_occurrences']:
                target['source_occurrences'].append(deepcopy(source))
    for key, record in merged.items():
        record['duplicate_observation'] = len(occurrences[key]) > 1
        record['source_occurrence_count'] = len(record['source_occurrences'])
    return list(merged.values())


def _input_gap_classification(paper):
    """Separate absent full text from local parsing/chunking failures."""
    source = paper.get('source_path')
    if not source or not Path(source).is_file():
        return 'fulltext_missing', 'source_not_available'
    expected = paper.get('source_sha256')
    if expected and sha(Path(source)) != expected:
        return 'parse_or_chunk_failure', 'source_hash_mismatch'
    return 'parse_or_chunk_failure', paper.get('input_error') or 'no_scannable_jobs'


def snapshot(workspace):
    """Return (summary, records, audit, failures); never merge observations or write files."""
    workspace = Path(workspace).resolve()
    manifest = verify(workspace)
    state_path = workspace / 'candidate_state.json'
    state = read(state_path) if state_path.exists() else {'tasks': {}, 'attempts': []}
    if state.get('pipeline', PIPELINE) != PIPELINE:
        raise ValueError('Sentence state pipeline mismatch')
    tasks = state['tasks']
    records, audits, paper_rows = [], [], []
    unresolved_paragraphs = 0
    for paper in manifest['papers']:
        pid = paper['paper_id']
        gaps = paper.get('sentence_gaps', [])
        for gap in gaps:
            audits.append({'paper_id': pid, 'stage': 'discovery', 'destination': 'unscanned',
                           'details': deepcopy(gap), **{key: deepcopy(gap[key]) for key in
                           ('sentence_id', 'unit_id', 'char_start', 'char_end', 'status', 'reason') if key in gap}})
        if not paper['job_ids']:
            gap_type, gap_reason = _input_gap_classification(paper)
            audits.append({'paper_id': pid, 'stage': 'prepare', 'destination': 'input_gap',
                           'gap_type': gap_type, 'reason': gap_reason})
        job_statuses = []
        for jid in paper['job_ids']:
            job = read(workspace / f'jobs/{jid}.json')
            discovery_tid = jid + ':discovery'
            discovery = tasks.get(discovery_tid, {})
            if discovery.get('status') != 'complete':
                for paragraph in job['paragraphs']:
                    audits.append({'paper_id': pid, 'job_id': jid, 'task_id': discovery_tid,
                                   'stage': 'discovery', 'destination': 'paragraph_coverage',
                                   'paragraph_id': paragraph['paragraph_id'],
                                   'sentence_ids': paragraph['sentence_ids'],
                                   'status': 'unscanned', 'task_status': discovery.get('status', 'pending'),
                                   'reasons': [discovery.get('failure_kind', 'discovery_not_complete')],
                                   'candidate_ids': []})
                    unresolved_paragraphs += 1
                job_statuses.append('pending' if not discovery else 'discovery_failed')
                continue
            d = _result(workspace, discovery)
            _notes(audits, pid, jid, 'discovery', d, discovery_tid)
            coverage = {row['paragraph_id']: row for row in d.get('coverage', [])}
            issues = bool(d.get('rejected') or d.get('unresolved') or not d.get('accounting_complete'))
            for paragraph in job['paragraphs']:
                row = deepcopy(coverage.get(paragraph['paragraph_id'], {
                    'paragraph_id': paragraph['paragraph_id'], 'status': 'unresolved',
                    'candidate_ids': [], 'reasons': ['missing_paragraph_coverage']}))
                audits.append({'paper_id': pid, 'job_id': jid, 'task_id': discovery_tid,
                               'stage': 'discovery', 'destination': 'paragraph_coverage',
                               'sentence_ids': paragraph['sentence_ids'], **row})
                unresolved_paragraphs += row['status'] not in {'has_candidates', 'none_found'}
            groups = []
            descriptor = state.get('groups', {}).get(jid)
            if descriptor:
                grouped = _artifact(workspace, descriptor['path'], descriptor['sha256'])
                if (grouped['discovery_result_sha256'] != discovery['result_sha256'] or
                        descriptor['discovery_result_sha256'] != discovery['result_sha256']):
                    raise ValueError('Facts grouping discovery dependency changed')
                groups = grouped['groups']
            indices = {}
            for index, group in enumerate(groups):
                for candidate in group['candidates']:
                    indices.setdefault(candidate['candidate_id'], []).append(index)
            complete = True
            for candidate in d.get('accepted', []):
                cid = candidate['candidate_id']
                status_row = {'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                              'destination': 'candidate_status', 'stage': 'facts',
                              'sentence_ids': deepcopy(candidate['sentence_ids']),
                              'facts_status': 'pending_grouping', 'conditions_status': 'not_planned',
                              'record_count': 0, 'record_statuses': []}
                assigned = indices.get(cid, [])
                if len(assigned) != 1:
                    if len(assigned) > 1:
                        status_row['facts_status'] = 'ambiguous_grouping'
                    complete = False
                    audits.append(status_row)
                    continue
                index = assigned[0]
                facts_tid = jid + f':facts:{index:03d}'
                facts = tasks.get(facts_tid, {})
                status_row.update(task_id=facts_tid, facts_status=facts.get('status', 'pending'))
                if facts.get('status') != 'complete':
                    complete = False
                    audits.append(status_row)
                    continue
                if facts.get('discovery_result_sha256') != discovery['result_sha256']:
                    raise ValueError('Facts discovery dependency changed')
                fact_result = _result(workspace, facts)
                _notes(audits, pid, jid, 'facts', fact_result, facts_tid)
                status_row['facts_accounting_complete'] = fact_result.get('accounting_complete', False)
                status_row['facts_disposition'] = ('unresolved' if fact_result.get('unresolved')
                    else 'observations' if fact_result.get('accepted') else 'rejected' if fact_result.get('rejected')
                    else 'empty_response')
                issues |= bool(fact_result.get('rejected') or fact_result.get('unresolved') or
                               not fact_result.get('accounting_complete'))
                needed_ids = [item['record']['record_key'] for item in fact_result.get('accepted', [])
                              if _needs_conditions(item['record'])]
                condition_tid = jid + f':conditions:{index:03d}'
                condition_entry = tasks.get(condition_tid, {})
                condition_descriptor = state.get('condition_groups', {}).get(condition_tid)
                condition_result, plan = None, None
                if condition_descriptor:
                    frozen = _artifact(workspace, condition_descriptor['path'], condition_descriptor['sha256'])
                    if (frozen['facts_result_sha256'] != facts['result_sha256'] or
                            condition_descriptor['facts_result_sha256'] != facts['result_sha256']):
                        raise ValueError('Conditions facts dependency changed')
                    plan = frozen['group']
                    if plan is None:
                        plan_reason = frozen.get('reason', 'not_needed')
                        context_gap = plan_reason != 'not_needed'
                        status_row['conditions_status'] = 'context_gap' if context_gap else 'not_needed'
                        status_row['conditions_reason'] = plan_reason
                        if context_gap:
                            issues = True
                            audits.append({'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                                           'stage': 'conditions', 'destination': 'optional_conditions_gap',
                                           'status': 'context_gap', 'record_ids': needed_ids,
                                           'reason': status_row['conditions_reason']})
                        audits.append({'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                                       'stage': 'conditions', 'destination': 'context_coverage',
                                       'context_complete': not context_gap,
                                       'selected_unit_ids': [], 'omitted_unit_ids': [],
                                       'omission_reason': status_row.get('conditions_reason'),
                                       'references': []})
                    else:
                        status_row['conditions_status'] = condition_entry.get('status', 'pending')
                        for context in plan.get('candidate_contexts', []):
                            if context.get('candidate_id') != cid:
                                continue
                            audits.append({'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                                           'stage': 'conditions', 'destination': 'context_coverage',
                                           'context_complete': context.get('context_complete', False),
                                           'anchor_unit_id': context.get('anchor_unit_id'),
                                           'selected_unit_ids': deepcopy(context.get('context_unit_ids', [])),
                                           'allowed_evidence_unit_ids': deepcopy(context.get('allowed_evidence_unit_ids', [])),
                                           'omitted_unit_ids': deepcopy(context.get('omitted_context_unit_ids', [])),
                                           'omission_reason': context.get('omission_reason'),
                                           'references': deepcopy(context.get('references', []))})
                    if plan is not None:
                        if condition_entry.get('status') == 'complete':
                            if condition_entry.get('facts_result_sha256') != facts['result_sha256']:
                                raise ValueError('Conditions result dependency changed')
                            condition_result = _result(workspace, condition_entry)
                            _notes(audits, pid, jid, 'conditions', condition_result, condition_tid)
                            condition_issues = bool(condition_result.get('rejected') or condition_result.get('unresolved') or
                                                    not condition_result.get('accounting_complete'))
                            status_row['conditions_accounting_complete'] = condition_result.get('accounting_complete', False)
                            if condition_issues:
                                status_row['conditions_status'] = 'complete_with_issues'
                            issues |= condition_issues
                        else:
                            issues = True
                            if condition_entry.get('status', 'pending') == 'pending':
                                complete = False
                            audits.append({'paper_id': pid, 'job_id': jid, 'task_id': condition_tid,
                                           'candidate_id': cid, 'stage': 'conditions',
                                           'destination': 'optional_conditions_gap',
                                           'status': condition_entry.get('status', 'pending'),
                                           'reason': condition_entry.get('failure_kind', 'conditions_not_complete')})
                else:
                    complete = False
                    audits.append({'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                                   'stage': 'conditions', 'destination': 'optional_conditions_gap',
                                   'status': 'not_planned', 'reason': 'conditions_plan_not_frozen',
                                   'stop_reason': state.get('stop_reason'),
                                   'exception_type': state.get('exception_type'), 'record_ids': needed_ids})
                    audits.append({'paper_id': pid, 'job_id': jid, 'candidate_id': cid,
                                   'stage': 'conditions', 'destination': 'context_coverage',
                                   'context_complete': False, 'selected_unit_ids': [],
                                   'omitted_unit_ids': [], 'omission_reason': 'conditions_plan_not_frozen',
                                   'references': []})
                revisions = {}
                for revised_index, item in enumerate((condition_result or {}).get('accepted', [])):
                    revised = item['record']
                    key = revised.get('core_original', revised)['record_key']
                    if key in revisions:
                        raise ValueError('Duplicate conditions revision for a fact')
                    revisions[key] = (revised_index, revised)
                for fact_index, item in enumerate(fact_result.get('accepted', [])):
                    base = item['record']
                    if item['candidate_id'] != cid or base['candidate_id'] != cid:
                        raise ValueError('Fact belongs to another candidate')
                    record = deepcopy(base)
                    sources = deepcopy(record.get('sources', []))
                    sources.append(_provenance(paper, jid, facts_tid, facts, fact_index))
                    revision = revisions.get(base['record_key'])
                    if revision is not None:
                        revised_index, revised = revision
                        record.update(deepcopy(revised))
                        record.setdefault('core_original', deepcopy(base))
                        sources.append(_provenance(paper, jid, condition_tid, condition_entry, revised_index))
                    record['sources'] = sources
                    records.append(record)
                    issues |= record['record_status'] != 'core_usable'
                    status_row['record_count'] += 1
                    status_row['record_statuses'].append(record['record_status'])
                    audits.append({'paper_id': pid, 'job_id': jid, 'task_id': facts_tid,
                                   'candidate_id': cid, 'stage': 'facts',
                                   'destination': record['record_status'], 'record_key': record['record_key'],
                                   'fact_index': fact_index, 'sources': deepcopy(sources)})
                audits.append(status_row)
            job_statuses.append('partial' if not complete else 'processed_with_issues' if issues
                                else 'processed_pending_review' if d.get('accepted')
                                else 'processed_no_candidates_found')
        processed = sum(status.startswith('processed') for status in job_statuses)
        gap_type, gap_reason = _input_gap_classification(paper) if not paper['job_ids'] else (None, None)
        paper_rows.append({'paper_id': pid, 'doi': paper.get('doi'), 'url': paper.get('url'),
                           'source_sha256': paper.get('source_sha256'),
                           'jobs': len(job_statuses), 'jobs_processed': processed,
                           'sentence_count': paper.get('sentence_count', 0), 'unscanned_sentences': len(gaps),
                           'status': 'input_gap' if not job_statuses else 'partial' if processed < len(job_statuses)
                           else 'processed_with_issues' if gaps or 'processed_with_issues' in job_statuses
                           else 'processed_pending_review', 'input_error': paper.get('input_error'),
                           'input_gap_type': gap_type, 'input_gap_reason': gap_reason,
                           'coverage': paper.get('parsed_coverage')})
    failures = [dict(deepcopy(entry), task_id=tid) for tid, entry in tasks.items()
                if entry.get('status') != 'complete']
    statuses = Counter(r['record_status'] for r in records)
    unscanned = sum(p['unscanned_sentences'] for p in paper_rows)
    semantic_pending = statuses['semantic_pending'] + statuses['quarantine']
    unresolved_candidates = sum(a['destination'] == 'unresolved' and a.get('stage') == 'facts' for a in audits)
    condition_gaps = sum(a['destination'] == 'optional_conditions_gap' for a in audits)
    evidence_records = _merge_evidence_records(records)
    buckets = {'成功': [], '失败': [], '缺少全文': [], '未完成': []}
    for row in paper_rows:
        if row['status'] == 'input_gap':
            bucket = '缺少全文' if row.get('input_gap_type') == 'fulltext_missing' else '失败'
            buckets[bucket].append(row['paper_id'])
        elif row['status'] == 'partial':
            buckets['未完成'].append(row['paper_id'])
        elif row['status'] == 'processed_with_issues':
            buckets['失败'].append(row['paper_id'])
        else:
            buckets['成功'].append(row['paper_id'])
    summary = {'pipeline': PIPELINE, 'protocol': 'sentence_v3', 'records': len(records),
               'paper_buckets': buckets,
               'unique_records': len({r['record_key'] for r in records}),
               'evidence_records': len(evidence_records),
               'duplicate_record_keys': sum(r.get('raw_observation_count', 1) > 1
                                            for r in evidence_records),
               'record_status': dict(statuses), 'core_usable_records': statuses['core_usable'],
               'semantic_pending_records': statuses['semantic_pending'], 'quarantine_records': statuses['quarantine'],
               'papers': paper_rows, 'paper_status': dict(Counter(p['status'] for p in paper_rows)),
               'candidate_destinations': dict(Counter(a['destination'] for a in audits)),
               'unscanned_sentences': unscanned, 'unresolved_paragraphs': unresolved_paragraphs,
               'optional_conditions_gaps': condition_gaps,
               'context_coverage_rows': sum(a['destination'] == 'context_coverage' for a in audits),
               'context_omissions': sum(bool(a.get('omitted_unit_ids')) for a in audits
                                        if a['destination'] == 'context_coverage'),
               'input_gap_classification': {p['paper_id']: p.get('input_gap_type')
                                            for p in paper_rows if p.get('input_gap_type')},
               'failed_tasks': len(failures), 'workspace_requests': len(state.get('attempts', [])),
               'reused_tasks': sum(bool(e.get('reused_from')) for e in tasks.values()),
               'task_status': dict(Counter(e['status'] for e in tasks.values())),
               'stop_reason': state.get('stop_reason'), 'expert_gold': False, 'training_ready_records': 0,
               'content_review_status': 'pending', 'release_status': 'requires_sentence_acceptance',
               'all_sources_processed': bool(paper_rows) and not unscanned and not unresolved_paragraphs and
                   not semantic_pending and not unresolved_candidates and not condition_gaps and
                   all(p['status'].startswith('processed') for p in paper_rows),
               'all_readable_sources_processed': bool(manifest['job_ids']) and not unscanned and
                   not unresolved_paragraphs and not semantic_pending and not unresolved_candidates and not condition_gaps and
                   all(p['status'].startswith('processed') for p in paper_rows if p['jobs'])}
    if state.get('budget_path'):
        import batch_budget
        summary['shared_budget'] = batch_budget.status(state['budget_path'])
    return summary, records, audits, failures


def _csv(path, rows):
    rows = list(rows)
    columns = list(dict.fromkeys(key for row in rows for key in row)) or ['status']
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows({key: safe_cell(row.get(key)) for key in columns} for row in rows)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def export(workspace):
    import batch_budget
    workspace = Path(workspace).resolve()
    with batch_budget.ledger_lock(workspace / 'export'):
        summary, records, audits, failures = snapshot(workspace)
        out = workspace / 'exports'
        datasets = {'records': records, 'candidate_audit': audits, 'failures': failures,
                    'paper_coverage': summary['papers'],
                    'evidence_records': _merge_evidence_records(records),
                    'paragraph_coverage': [a for a in audits if a['destination'] == 'paragraph_coverage'],
                    'candidate_status': [a for a in audits if a['destination'] == 'candidate_status'],
                    'coverage_gaps': [a for a in audits if a['destination'] in {'input_gap', 'unscanned'}],
                    'context_coverage': [a for a in audits if a['destination'] == 'context_coverage']}
        for name, rows in datasets.items():
            save(out / (name + '.json'), rows)
            csv_rows = rows
            if name == 'records':
                csv_rows = [dict(r, **{field: r['values'].get(field) for field in FIELDS},
                                 **{'condition_' + field: value for field, value in r.get('conditions', {}).items()})
                            for r in records]
            _csv(out / (name + '.csv'), csv_rows)
        save(out / 'summary.json', summary)
        _summary_markdown(out / 'summary.md', summary, audits)
        return summary


def _summary_markdown(path, summary, audits):
    budget = summary.get('shared_budget')
    candidate_status = Counter(a['facts_status'] for a in audits if a['destination'] == 'candidate_status')
    condition_status = Counter(a['conditions_status'] for a in audits if a['destination'] == 'candidate_status')
    lines = ['# 句段提取进度（sentence_v3）', '',
             f'来源：{len(summary["papers"])}；观察记录：{summary["records"]}；'
             f'不同 record_key：{summary["unique_records"]}；唯一证据记录：{summary.get("evidence_records", summary["unique_records"])}。'
             '原始观察逐条保留，重复提及在证据层合并。', '',
             '成功 / 失败 / 缺少全文 / 未完成：']
    buckets = summary.get('paper_buckets', {})
    for label in ('成功', '失败', '缺少全文', '未完成'):
        papers = buckets.get(label, [])
        lines.append(f'- {label}（{len(papers)}）：' + ('、'.join(papers) if papers else '无'))
    lines += ['',
             f'覆盖状态：{summary["paper_status"]}；未扫描句段：{summary["unscanned_sentences"]}；'
             f'未解决正文段落：{summary["unresolved_paragraphs"]}。', '',
             f'全部来源处理完整：{summary["all_sources_processed"]}；'
             f'条件补充缺口：{summary["optional_conditions_gaps"]}。', '',
             f'上下文审计行：{summary.get("context_coverage_rows", 0)}；'
             f'存在裁剪的候选：{summary.get("context_omissions", 0)}。', '',
             f'候选事实阶段状态：{dict(candidate_status)}；条件阶段状态：{dict(condition_status)}。', '',
             f'候选去向：{summary["candidate_destinations"]}。', '',
             f'记录状态：{summary["record_status"]}；核心可用：{summary["core_usable_records"]}；'
             f'语义待定：{summary["semantic_pending_records"]}；隔离：{summary["quarantine_records"]}。', '',
             f'任务状态：{summary["task_status"]}；失败或未完成任务：{summary["failed_tasks"]}。', '',
             f'停止原因：{summary["stop_reason"] or "未报告停止原因（尚未运行或已到队列末尾）"}。', '',
             f'本工作区请求：{summary["workspace_requests"]}；复用任务：{summary["reused_tasks"]}。', '']
    if budget:
        lines += [f'共享预算：{budget["requests_reserved"]}/{budget["max_requests"]} 次；'
                  f'保守 token 预留：{budget["reserved_token_estimate"]}；'
                  f'已上报 token：{budget["reported_total_tokens"]}；'
                  f'未上报用量请求：{budget["attempts_without_usage"]}。未知用量保留未知。', '']
    else:
        lines += ['预算：工作区尚无绑定账本；本导出未发起生成请求。', '']
    lines += ['内容复核：待复核；expert_gold=false；ready_for_training=false。', '',
              '验收放行：本导出未放行，须由 sentence_acceptance 独立验收。', '',
              '条件补充失败时原 fact 保留；semantic_pending 和 quarantine 均保留原状态及语义标记。', '',
              '逐篇范围见 paper_coverage.csv；逐段范围见 paragraph_coverage.csv；'
              '候选与条件缺口见 candidate_audit.json；权威完整观察见 records.json。', '']
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text('\n'.join(lines), encoding='utf-8')
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
