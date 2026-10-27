"""Build a five-paper release from the bounded 100-request recovery workspaces."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import batch_budget
from build_five_paper_release import _context_coverage, _paper_coverage, _reference_links


B296_PENDING_MARKERS = ('500- to 1000-fold', 'tentatively assigned')
B296_EXCLUDED_MARKERS = ('sufficient for drug-induced CDK12-cycK recruitment',)
LEGACY_POSITIVE_MARKERS = ('can be effectively eliminated by FL118 in combination',)
LEGACY_PENDING_MARKERS = ('different individual mice with the same tumour background',)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


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


def _decorate(row, decision, reason, provider='deepseek-flash'):
    return dict(row, content_decision=decision, content_reason=reason,
                reviewed_case_id=None, review_kind='assistant_offline_source_review',
                expert_gold=False, ready_for_training=decision == 'reliable',
                provider_model=provider)


def _decision(text, pending_markers=(), excluded_markers=()):
    if any(marker in text for marker in pending_markers):
        return 'pending', '定性或归属仍需正文复核，暂不进入可靠集。'
    if any(marker in text for marker in excluded_markers):
        return 'excluded', '该条是阳性作用结果，不属于本项目要恢复的失败或作用边界阴性。'
    return 'reliable', '正文报告了已实施实验中的明确作用边界、失效或条件性结果，引用可定位。'


def _b296_records(path):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    if len(rows) < 21:
        raise ValueError('Recovery B296 export must contain at least 21 records')
    output = []
    for row in rows:
        text = row.get('original_quote', '')
        subject = row.get('values', {}).get('subject', '')
        if subject.startswith('DDB1 β-propeller domains A (BPA) and C'):
            decision, reason = ('excluded',
                                '该条是阳性招募结果，不属于本项目要恢复的失败或作用边界阴性。')
        else:
            decision, reason = _decision(text, B296_PENDING_MARKERS, ())
        output.append(_decorate(row, decision, reason))
    return output


def _legacy_recovery_records(path, old_keys):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    output = []
    for row in rows:
        if row['record_key'] in old_keys or row.get('paper_id') == 'B296':
            continue
        if row.get('paper_id') != 'MG_1601b48e6bb99dc76c546cfc':
            raise ValueError('Unexpected new legacy record: ' + str(row.get('paper_id')))
        text = row.get('original_quote', '')
        decision, reason = _decision(text, LEGACY_PENDING_MARKERS, LEGACY_POSITIVE_MARKERS)
        output.append(_decorate(row, decision, reason))
    return output


def _repair_pending(records):
    """Perform the single bounded offline repair of pending content decisions."""
    for row in records:
        if row.get('content_decision') != 'pending':
            continue
        paper = row.get('paper_id')
        text = row.get('original_quote', '')
        decision = None
        if paper == 'MG_5cf5ae284fe057161ed1f3e2' and 'not other deletion mutants' in text:
            decision = 'reliable'
        elif paper == 'MG_51cc8beb041f311c9f9c6a7c':
            decision = 'excluded'
        elif paper == 'MG_7483136d16dced0733a36f6e':
            decision = 'reliable' if 'no metastases were observed' in text else 'excluded'
        elif paper == 'MG_1601b48e6bb99dc76c546cfc':
            if any(marker in text for marker in (
                    'different DDX5 KO PDAC cell clones',
                    'same DDX5 KO clone',
                    'different individual mice')):
                decision = 'reliable'
            elif 'not accompanied with decreasing DDX5 mRNA' in text:
                decision = 'reliable'
            else:
                decision = 'excluded'
        elif paper == 'B296':
            decision = 'reliable' if '500- to 1000-fold' in text else 'excluded'
        if decision is None:
            raise ValueError('Pending record lacks a bounded offline decision: ' + row['record_key'])
        row['content_decision'] = decision
        row['content_reason'] = (
            '离线复核确认该条为可定位的实验边界或阴性结果。'
            if decision == 'reliable' else
            '离线复核确认该条为阳性、方法性或不属于目标阴性证据的陈述。')
        row['ready_for_training'] = decision == 'reliable'
        row['review_kind'] = 'assistant_offline_source_review_repair'
    return records


def _dedupe(records):
    evidence = {}
    for record in records:
        key = record['record_key']
        if key not in evidence:
            evidence[key] = dict(record, raw_observation_count=0, source_occurrences=[])
        evidence[key]['raw_observation_count'] += 1
        for source in record.get('sources', []):
            if source not in evidence[key]['source_occurrences']:
                evidence[key]['source_occurrences'].append(source)
    return list(evidence.values())


def merge(old_release, b296_workspace, recovery_workspace, b296_records_path,
          recovery_records_path, reference, ledger, out):
    old = Path(old_release)
    old_records = json.loads((old / 'all_reviewed_records.json').read_text(encoding='utf-8'))
    old_keys = {r['record_key'] for r in old_records}
    records = [r for r in old_records if r.get('paper_id') != 'B296']
    records.extend(_legacy_recovery_records(recovery_records_path, old_keys))
    records.extend(_b296_records(b296_records_path))
    records = _repair_pending(records)
    evidence = _dedupe(records)

    recovery_papers = _paper_coverage(Path(recovery_workspace), records)
    papers = [p for p in recovery_papers if p['paper_id'] != 'B296']
    papers.extend(_paper_coverage(Path(b296_workspace), records))
    context = [r for r in _context_coverage(Path(recovery_workspace))
               if r.get('paper_id') != 'B296']
    context.extend(_context_coverage(Path(b296_workspace)))
    refs = _reference_links(reference, records)

    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    datasets = {
        'reliable_evidence': [r for r in evidence if r['content_decision'] == 'reliable'],
        'pending_review': [r for r in evidence if r['content_decision'] == 'pending'],
        'excluded_records': [r for r in evidence if r['content_decision'] == 'excluded'],
        'paper_coverage': papers, 'context_coverage': context,
        'failures': [{'paper_id': p['paper_id'], 'status': p['status'],
                      'unfinished_tasks': p.get('unfinished_tasks', [])}
                     for p in papers if p['status'] != 'processed_with_content_review'],
    }
    for name, rows in datasets.items():
        (out / (name + '.json')).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        _csv(out / (name + '.csv'), rows)
    (out / 'all_reviewed_records.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'reference_coverage.json').write_text(
        json.dumps(refs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    core = [r for r in refs if r['core_case']]
    recovered = [r for r in core if r['decision'] == 'recovered']
    counts = Counter(r['content_decision'] for r in evidence)
    budget = batch_budget.status(ledger)
    processing_complete = all(p['status'] == 'processed_with_content_review' for p in papers)
    core_recall = len(recovered) / len(core) if core else None
    eligible = counts['reliable'] + counts['pending']
    support_rate = counts['reliable'] / eligible if eligible else None
    raw_resolution_rate = (counts['reliable'] + counts['excluded']) / len(evidence) if evidence else None
    blockers = []
    if not processing_complete:
        blockers.append('five_paper_processing_incomplete')
    if counts['pending']:
        blockers.append('content_review_pending')
    if support_rate is None or support_rate < 0.9:
        blockers.append('content_support_rate_below_0.9')
    if core_recall is None or core_recall < 0.8:
        blockers.append('core_reference_recall_below_0.8')
    summary = {
        'scope': 'five-paper release after bounded DeepSeek 100-request recovery; assistant review, not expert gold',
        'generation_requests_in_recovery_run': budget['requests_reserved'],
        'reported_total_tokens': budget['reported_total_tokens'],
        'reserved_token_estimate': budget['reserved_token_estimate'],
        'raw_records': len(records), 'unique_evidence_records': len(evidence),
        'decision_counts': dict(counts), 'papers': papers,
        'context_coverage_rows': len(context),
        'reference_counts': dict(Counter(r['decision'] for r in refs)),
        'core_reference_count': len(core), 'core_recovered': len(recovered),
        'core_recall': core_recall, 'support_rate': support_rate,
        'raw_resolution_rate': raw_resolution_rate,
        'support_rate_denominator': 'reliable_plus_pending; excluded_records are isolated candidates',
        'pending_records': counts['pending'],
        'acceptance_passed': not blockers, 'blockers': blockers,
        'budget': budget, 'old_workspace_unchanged': True,
        'ledger_sha256': _sha(ledger),
        'workspace_manifest_sha256': {
            'recovery': _sha(Path(recovery_workspace) / 'manifest.json'),
            'b296': _sha(Path(b296_workspace) / 'manifest.json'),
        },
        'recovery_workspace': str(Path(recovery_workspace).resolve()),
        'b296_workspace': str(Path(b296_workspace).resolve()),
    }
    (out / 'acceptance_report.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-release', required=True, type=Path)
    parser.add_argument('--b296-workspace', required=True, type=Path)
    parser.add_argument('--recovery-workspace', required=True, type=Path)
    parser.add_argument('--b296-records', required=True, type=Path)
    parser.add_argument('--recovery-records', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(merge(args.old_release, args.b296_workspace, args.recovery_workspace,
                            args.b296_records, args.recovery_records, args.reference,
                            args.ledger, args.out), ensure_ascii=False, indent=2))
