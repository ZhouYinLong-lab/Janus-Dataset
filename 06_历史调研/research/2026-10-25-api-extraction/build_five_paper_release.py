"""Build a non-destructive five-paper release candidate from saved responses.

The release is intentionally conservative: it does not resend unknown tasks,
does not rewrite the frozen workspace, and never turns an incomplete paper into
a passed acceptance report.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import re


RELIABLE_INDEXES = {3, 4, 7, 8, 10, 12, 13, 14, 21, 25, 26, 27, 29, 30, 36,
                    38, 40, 41, 42, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
                    57, 58, 59, 60, 62, 69, 70, 71, 75, 79, 89}
PENDING_INDEXES = {6, 39, 61, 64, 66, 72, 74, 76, 81, 82, 83, 84, 85, 87}
KNOWN_CASES = {
    'b8ee41417e77b3798313a0287e90b7cb60e1841088ef166374fc45cf249d9656': ('excluded', 'C01'),
    'bb656d3aa45569cf606cabb881680a9134f6d4645ab843935a0bc6367483c593': ('pending', 'C02'),
    '91ae9c10fcce087ad787b1c32b8d81ee762360fe6da4b4d9c27198fc1d9b250d': ('pending', 'C03'),
    'c2c6cc02ff20515edf7a8bdc6af30d9b2735a0ca3e8dcfb24f499aed56fb431b': ('excluded', 'C04'),
    'd43d3ae20fc05ffba007d1af78ac7978081fe96c9deeee31a1daf4336411338c': ('pending', 'C05'),
    '871c6b8b3fedd1451a2ec46552f80e2869f7f978eafd26695fda7303d8c15a27': ('pending', 'C06'),
    '968e771d4d3abd35300300581d192da2d3c520e54bcc29588336c7c9d7bea13e': ('pending', 'C07'),
}
REASONS = {
    'reliable': '正文记录了已实施实验中的明确阴性、条件性失效或作用边界，且对象、终点和方向可由引用核对。',
    'pending': '存在混合终点、对象/方向不确定、定性零值或正文范围不足，暂不进入可靠集。',
    'excluded': '阳性结果、一般性质、方法条款、讨论性陈述或非目标终点，不属于本项目可靠阴性。',
}


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def _csv(path, rows):
    rows = list(rows)
    columns = sorted({key for row in rows for key in row}) or ['status']
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def _record_decision(index, record):
    if record['record_key'] in KNOWN_CASES:
        decision, case_id = KNOWN_CASES[record['record_key']]
        return decision, REASONS[decision], case_id
    if index in RELIABLE_INDEXES:
        return 'reliable', REASONS['reliable'], None
    if index in PENDING_INDEXES:
        return 'pending', REASONS['pending'], None
    return 'excluded', REASONS['excluded'], None


def _load_records(records_path, original_path):
    records = json.loads(Path(records_path).read_text(encoding='utf-8'))
    originals = {r['record_key']: r for r in json.loads(Path(original_path).read_text(encoding='utf-8'))}
    if len(records) != 89 or len(originals) < len(records):
        raise ValueError('Expected 89 revalidated records with matching original provenance')
    output = []
    for index, record in enumerate(records, 1):
        merged = dict(record)
        merged['sources'] = originals[record['record_key']].get('sources', [])
        decision, reason, case_id = _record_decision(index, record)
        merged.update(content_decision=decision, content_reason=reason,
                      reviewed_case_id=case_id, review_kind='assistant_offline_source_review',
                      expert_gold=False, ready_for_training=decision == 'reliable')
        output.append(merged)
    return output


def _paper_coverage(workspace, records):
    workspace = Path(workspace)
    manifest = json.loads((workspace / 'manifest.json').read_text(encoding='utf-8'))
    state = json.loads((workspace / 'candidate_state.json').read_text(encoding='utf-8'))
    rows = []
    for paper in manifest['papers']:
        pid = paper['paper_id']
        jobs = paper.get('job_ids', [])
        task_rows = [(tid, entry) for tid, entry in state.get('tasks', {}).items()
                     if entry.get('job_id') in jobs]
        complete = sum(entry.get('status') == 'complete' for _, entry in task_rows)
        unknown = [{'task_id': tid, 'stage': entry.get('stage'), 'status': entry.get('status'),
                    'failure_kind': entry.get('failure_kind')}
                   for tid, entry in task_rows if entry.get('status') != 'complete']
        paper_records = [r for r in records if r.get('paper_id') == pid]
        source_exists = bool(paper.get('source_path')) and Path(paper['source_path']).is_file()
        source_hash_ok = source_exists and (not paper.get('source_sha256') or
                                             _sha(paper['source_path']) == paper['source_sha256'])
        if not source_exists:
            status = 'fulltext_missing'
        elif not jobs or len(task_rows) < len(jobs) or unknown:
            status = 'unfinished'
        else:
            status = 'processed_with_content_review'
        rows.append({'paper_id': pid, 'doi': paper.get('doi'), 'source_path': paper.get('source_path'),
                     'source_sha256': paper.get('source_sha256'), 'source_exists': source_exists,
                     'source_hash_ok': source_hash_ok, 'jobs': len(jobs),
                     'tasks_seen': len(task_rows), 'tasks_complete': complete,
                     'unfinished_tasks': (unknown if unknown else ([{'task_id': None,
                         'stage': 'discovery', 'status': 'not_started',
                         'failure_kind': 'no_tasks_recorded'}] if jobs and not task_rows else [])),
                     'raw_records': len(paper_records),
                     'reliable_records': sum(r['content_decision'] == 'reliable' for r in paper_records),
                     'pending_records': sum(r['content_decision'] == 'pending' for r in paper_records),
                     'excluded_records': sum(r['content_decision'] == 'excluded' for r in paper_records),
                     'status': status})
    return rows


def _reference_links(reference_path, records):
    reference = json.loads(Path(reference_path).read_text(encoding='utf-8'))
    rows = []
    for paper in reference.get('papers', []):
        paper_records = [r for r in records if r.get('paper_id') == paper['paper_id']]
        for ref in paper.get('negatives', []):
            ref_units = {ref.get('unit_id'), *ref.get('source_support_unit_ids', [])}
            ref_quote = _norm(ref.get('quote'))
            matches = []
            for record in paper_records:
                record_units = {x.get('unit_id') for x in record.get('field_evidence', [])}
                quote = _norm(record.get('original_quote'))
                if ref_units & record_units or (ref_quote and (ref_quote in quote or quote in ref_quote)):
                    matches.append(record)
            reliable = [r for r in matches if r['content_decision'] == 'reliable']
            decision = 'recovered' if reliable else 'missed' if matches else 'unprocessed'
            rows.append({'reference_id': ref['id'], 'paper_id': paper['paper_id'],
                         'unit_id': ref.get('unit_id'), 'core_case': bool(ref.get('core_case')),
                         'decision': decision, 'record_keys': [r['record_key'] for r in reliable],
                         'matched_record_keys': [r['record_key'] for r in matches],
                         'reason': '唯一证据层中存在可核对可靠记录。' if decision == 'recovered'
                                   else '已有输出但未被判为可靠。' if decision == 'missed'
                                   else '该正文参考在已保存任务中没有可核对输出。'})
    return rows


def _context_coverage(workspace):
    workspace = Path(workspace)
    state = json.loads((workspace / 'candidate_state.json').read_text(encoding='utf-8'))
    rows = []
    for descriptor in state.get('groups', {}).values():
        path = workspace / descriptor['path']
        if not path.is_file():
            continue
        frozen = json.loads(path.read_text(encoding='utf-8'))
        for group in frozen.get('groups', []):
            contexts = {x.get('candidate_id'): x for x in group.get('candidate_contexts', [])}
            for candidate in group.get('candidates', []):
                cid = candidate.get('candidate_id')
                context = contexts.get(cid, {})
                unit_id = candidate.get('unit_id')
                paper_id = str(unit_id).split(':', 1)[0] if unit_id else None
                omitted = list(dict.fromkeys(
                    context.get('omitted_context_unit_ids', []) + group.get('omitted_unit_ids', [])))
                rows.append({'candidate_id': cid, 'paper_id': paper_id,
                             'unit_id': unit_id,
                             'anchor_unit_id': context.get('anchor_unit_id', unit_id),
                             'selected_unit_ids': context.get('context_unit_ids', []),
                             'allowed_evidence_unit_ids': context.get('allowed_evidence_unit_ids', []),
                             'omitted_unit_ids': omitted,
                             'context_complete': not omitted and context.get('context_complete', True),
                             'omission_reason': context.get('omission_reason'),
                             'references': context.get('references', [])})
    return rows


def build(workspace, records_path, original_path, reference_path, out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = _load_records(records_path, original_path)
    evidence = {}
    for record in records:
        key = record['record_key']
        if key not in evidence:
            evidence[key] = dict(record, raw_observation_count=0, source_occurrences=[])
        evidence[key]['raw_observation_count'] += 1
        for source in record.get('sources', []):
            if source not in evidence[key]['source_occurrences']:
                evidence[key]['source_occurrences'].append(source)
    evidence = list(evidence.values())
    paper_rows = _paper_coverage(workspace, records)
    context_rows = _context_coverage(workspace)
    reference_rows = _reference_links(reference_path, records)
    datasets = {
        'reliable_evidence': [r for r in evidence if r['content_decision'] == 'reliable'],
        'pending_review': [r for r in evidence if r['content_decision'] == 'pending'],
        'excluded_records': [r for r in evidence if r['content_decision'] == 'excluded'],
        'paper_coverage': paper_rows,
        'context_coverage': context_rows,
        'failures': [x for p in paper_rows for x in p['unfinished_tasks']],
    }
    for name, rows in datasets.items():
        (out / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        _csv(out / (name + '.csv'), rows)
    (out / 'all_reviewed_records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'reference_coverage.json').write_text(json.dumps(reference_rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    core = [r for r in reference_rows if r['core_case']]
    recovered = [r for r in core if r['decision'] == 'recovered']
    summary = {
        'scope': 'five-paper offline release candidate; assistant review, not expert gold',
        'generation_requests': 0, 'raw_records': len(records), 'unique_evidence_records': len(evidence),
        'decision_counts': dict(Counter(r['content_decision'] for r in records)),
        'papers': paper_rows, 'reference_counts': dict(Counter(r['decision'] for r in reference_rows)),
        'context_coverage_rows': len(context_rows),
        'context_omission_rows': sum(bool(r['omitted_unit_ids']) for r in context_rows),
        'core_reference_count': len(core), 'core_recovered': len(recovered),
        'core_recall': len(recovered) / len(core) if core else None,
        'support_rate': sum(r['content_decision'] == 'reliable' for r in records) / len(records),
        'severe_errors': sum(r['content_decision'] == 'pending' for r in records),
        'acceptance_passed': bool(core) and len(recovered) / len(core) >= .8 and
            all(p['status'] == 'processed_with_content_review' for p in paper_rows) and
            all(r['content_decision'] != 'pending' for r in records),
        'blockers': [],
        'source_records': str(Path(records_path).resolve()),
    }
    if any(p['status'] != 'processed_with_content_review' for p in paper_rows):
        summary['blockers'].append('five_paper_processing_incomplete')
    if summary['support_rate'] < .9:
        summary['blockers'].append('content_support_rate_below_0.9')
    if summary['severe_errors']:
        summary['blockers'].append('pending_or_severe_content_items')
    if summary['core_recall'] is None or summary['core_recall'] < .8:
        summary['blockers'].append('core_reference_recall_below_0.8')
    (out / 'reference_coverage.json').write_text(json.dumps(reference_rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'acceptance_report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('--original-records', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.workspace, args.records, args.original_records, args.reference, args.out),
                     ensure_ascii=False, indent=2))
