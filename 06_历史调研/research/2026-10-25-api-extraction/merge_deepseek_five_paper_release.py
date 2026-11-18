"""Merge bounded DeepSeek B296 output into the non-destructive five-paper release."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from build_five_paper_release import _context_coverage, _reference_links


B296_RELIABLE = {1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18}
B296_PENDING = {7, 8}
B296_EXCLUDED = {5}
B296_REASONS = {
    'reliable': 'B296正文报告已实施实验中的明确作用边界、失效或条件性结果，引用可定位。',
    'pending': '定性零值或不确定归属需要进一步正文核对，暂不进入可靠集。',
    'excluded': '该条是阳性招募/作用结果，不是本项目要保留的失败或边界阴性。',
}


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


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _b296_records(path):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    if len(rows) != 18:
        raise ValueError('Expected 18 bounded B296 records')
    output = []
    for index, row in enumerate(rows, 1):
        if index in B296_RELIABLE:
            decision = 'reliable'
        elif index in B296_PENDING:
            decision = 'pending'
        elif index in B296_EXCLUDED:
            decision = 'excluded'
        else:
            raise ValueError('B296 decision map is incomplete at index ' + str(index))
        value = dict(row, content_decision=decision, content_reason=B296_REASONS[decision],
                     reviewed_case_id=None, review_kind='assistant_offline_source_review',
                     expert_gold=False, ready_for_training=decision == 'reliable',
                     provider_model='deepseek-flash')
        output.append(value)
    return output


def _b296_coverage(workspace, records):
    workspace = Path(workspace)
    manifest = json.loads((workspace / 'manifest.json').read_text(encoding='utf-8'))
    state = json.loads((workspace / 'candidate_state.json').read_text(encoding='utf-8'))
    jobs = next((p.get('job_ids', []) for p in manifest['papers'] if p['paper_id'] == 'B296'), [])
    task_rows = [(tid, e) for tid, e in state['tasks'].items()
                 if e.get('job_id') in jobs]
    complete = sum(e.get('status') == 'complete' for _, e in task_rows)
    discoveries = sum(e.get('stage') == 'discovery' and e.get('status') == 'complete'
                      for _, e in task_rows)
    facts = sum(e.get('stage') == 'facts' and e.get('status') == 'complete'
                for _, e in task_rows)
    seen_jobs = {e.get('job_id') for _, e in task_rows}
    unfinished = [
        {'task_id': tid, 'stage': entry.get('stage'), 'status': entry.get('status'),
         'failure_kind': entry.get('failure_kind')}
        for tid, entry in task_rows if entry.get('status') != 'complete'
    ]
    unfinished.extend(
        {'task_id': f'{job}:discovery', 'stage': 'discovery', 'status': 'not_started',
         'failure_kind': 'request_limit_reached'}
        for job in jobs if job not in seen_jobs
    )
    paper = next(p for p in manifest['papers'] if p['paper_id'] == 'B296')
    source_path = Path(paper['source_path'])
    source_exists = source_path.is_file()
    source_hash_ok = source_exists and _sha(source_path) == paper.get('source_sha256')
    paper_records = [r for r in records if r.get('paper_id') == 'B296']
    return {'paper_id': 'B296', 'doi': '10.1038/s41586-020-2374-x',
            'source_path': paper['source_path'],
            'jobs': len(jobs), 'discovery_complete': discoveries, 'facts_complete': facts,
            'tasks_seen': len(task_rows), 'tasks_complete': complete,
            'unfinished_tasks': unfinished, 'source_exists': source_exists,
            'source_hash_ok': source_hash_ok, 'source_sha256': paper.get('source_sha256'),
            'raw_records': len(paper_records),
            'reliable_records': sum(r['content_decision'] == 'reliable' for r in paper_records),
            'pending_records': sum(r['content_decision'] == 'pending' for r in paper_records),
            'excluded_records': sum(r['content_decision'] == 'excluded' for r in paper_records),
            'status': 'unfinished' if discoveries < len(jobs) else 'processed_with_content_review'}


def merge(old_release, deepseek_workspace, old_workspace, deepseek_records, reference, out):
    old = Path(old_release)
    records = json.loads((old / 'all_reviewed_records.json').read_text(encoding='utf-8'))
    records.extend(_b296_records(deepseek_records))
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
    old_papers = json.loads((old / 'paper_coverage.json').read_text(encoding='utf-8'))
    papers = [p for p in old_papers if p['paper_id'] != 'B296']
    papers.append(_b296_coverage(deepseek_workspace, records))
    refs = _reference_links(reference, records)
    context = json.loads((old / 'context_coverage.json').read_text(encoding='utf-8'))
    context.extend(_context_coverage(Path(deepseek_workspace)))
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    datasets = {
        'reliable_evidence': [r for r in evidence if r['content_decision'] == 'reliable'],
        'pending_review': [r for r in evidence if r['content_decision'] == 'pending'],
        'excluded_records': [r for r in evidence if r['content_decision'] == 'excluded'],
        'paper_coverage': papers, 'context_coverage': context,
        'failures': [
            {'paper_id': p['paper_id'], 'status': p['status'],
             'unfinished_tasks': p.get('unfinished_tasks', [])}
            for p in papers if p['status'] == 'unfinished'
        ],
    }
    for name, rows in datasets.items():
        (out / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        _csv(out / (name + '.csv'), rows)
    (out / 'all_reviewed_records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'reference_coverage.json').write_text(json.dumps(refs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    core = [r for r in refs if r['core_case']]
    recovered = [r for r in core if r['decision'] == 'recovered']
    counts = Counter(r['content_decision'] for r in records)
    summary = {'scope': 'five-paper release after bounded DeepSeek B296 continuation; assistant review, not expert gold',
               'generation_requests_in_deepseek_run': 25, 'raw_records': len(records),
               'unique_evidence_records': len(evidence), 'decision_counts': dict(counts),
               'papers': papers, 'context_coverage_rows': len(context),
               'reference_counts': dict(Counter(r['decision'] for r in refs)),
               'core_reference_count': len(core), 'core_recovered': len(recovered),
               'core_recall': len(recovered) / len(core) if core else None,
               'support_rate': counts['reliable'] / len(records) if records else None,
               'pending_records': counts['pending'], 'acceptance_passed': False,
               'blockers': ['five_paper_processing_incomplete', 'content_review_pending',
                            'core_reference_recall_below_0.8'],
               'old_workspace_unchanged': True,
               'old_workspace': str(Path(old_workspace).resolve()),
               'deepseek_workspace': str(Path(deepseek_workspace).resolve())}
    (out / 'acceptance_report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-release', required=True, type=Path)
    parser.add_argument('--deepseek-workspace', required=True, type=Path)
    parser.add_argument('--old-workspace', required=True, type=Path)
    parser.add_argument('--deepseek-records', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(merge(args.old_release, args.deepseek_workspace, args.old_workspace,
                            args.deepseek_records, args.reference, args.out), ensure_ascii=False, indent=2))
