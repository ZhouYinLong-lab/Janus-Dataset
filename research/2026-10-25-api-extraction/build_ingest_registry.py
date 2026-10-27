"""Build a non-destructive, hash-checked registry for the full MolGlueDB inventory."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path, rows):
    columns = sorted({key for row in rows for key in row})
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def build(papers_path, workspace_path, out_path, baseline_report=None,
          baseline_inventory=None, baseline_workspace_manifest=None):
    papers_path = Path(papers_path).resolve()
    workspace_path = Path(workspace_path).resolve()
    out_path = Path(out_path).resolve()
    papers = json.loads(papers_path.read_text(encoding='utf-8'))
    manifest = json.loads((workspace_path / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(papers, list) or not isinstance(manifest.get('papers'), list):
        raise ValueError('Inventory and workspace manifest must contain paper arrays')

    manifest_by_id = {row['paper_id']: row for row in manifest['papers']}
    if len(manifest_by_id) != len(manifest['papers']):
        raise ValueError('Duplicate paper_id in workspace manifest')
    rows = []
    for paper in papers:
        pid = paper['paper_id']
        if pid not in manifest_by_id:
            raise ValueError('Paper missing from workspace manifest: ' + pid)
        source_path = paper.get('path') or paper.get('source_path')
        exists = bool(source_path) and Path(source_path).is_file()
        actual_sha = _sha(source_path) if exists else None
        expected_sha = paper.get('source_sha256')
        hash_ok = bool(exists and expected_sha and actual_sha == expected_sha)
        manifest_paper = manifest_by_id[pid]
        jobs = list(manifest_paper.get('job_ids', []))
        fulltext_status = 'local_fulltext' if hash_ok else 'fulltext_missing'
        extraction_status = 'ready_for_extraction' if jobs else 'input_gap'
        rows.append({
            'paper_id': pid,
            'source_id': paper.get('source_id'),
            'doi': paper.get('doi'),
            'title': paper.get('title'),
            'url': paper.get('url'),
            'availability': paper.get('availability'),
            'source_path': source_path,
            'source_sha256': expected_sha,
            'source_sha256_actual': actual_sha,
            'source_hash_ok': hash_ok,
            'source_kind': paper.get('source_kind'),
            'source_format': paper.get('source_format'),
            'publication_kind': paper.get('publication_kind'),
            'source_coverage': (paper.get('sources') or [{}])[0].get('coverage'),
            'fetch_attempts': paper.get('fetch_attempts', []),
            'fulltext_status': fulltext_status,
            'extraction_status': extraction_status,
            'workspace_status': manifest_paper.get('status'),
            'sentence_job_count': len(jobs),
            'sentence_job_ids': jobs,
        })

    dois = [row.get('doi', '').strip().lower() for row in rows if row.get('doi')]
    source_ids = [row.get('source_id') for row in rows if row.get('source_id')]
    baseline = None
    if baseline_report:
        baseline = json.loads(Path(baseline_report).read_text(encoding='utf-8'))
    old_inventory_unchanged = True
    old_workspace_unchanged = True
    if baseline:
        old_inventory_unchanged = (
            _sha(Path(baseline_inventory)) == baseline['inventory_sha256']
            if baseline_inventory else True)
        old_workspace_unchanged = (
            _sha(Path(baseline_workspace_manifest)) == baseline['workspace_manifest_sha256']
            if baseline_workspace_manifest else True)
    report = {
        'schema_version': 1,
        'inventory_sha256': _sha(papers_path),
        'workspace_manifest_sha256': _sha(workspace_path / 'manifest.json'),
        'paper_count': len(rows),
        'paper_id_duplicates': len(rows) - len({row['paper_id'] for row in rows}),
        'doi_duplicates': len(dois) - len(set(dois)),
        'source_id_duplicates': len(source_ids) - len(set(source_ids)),
        'fulltext_status_counts': dict(Counter(row['fulltext_status'] for row in rows)),
        'extraction_status_counts': dict(Counter(row['extraction_status'] for row in rows)),
        'source_hash_mismatches': sum(not row['source_hash_ok']
                                      for row in rows if row['fulltext_status'] == 'local_fulltext'),
        'sentence_job_count': sum(row['sentence_job_count'] for row in rows),
        'api_requests_sent': 0,
        'old_inventory_unchanged': old_inventory_unchanged,
        'old_workspace_unchanged': old_workspace_unchanged,
    }
    if report['paper_count'] != 193 or report['paper_id_duplicates'] or report['doi_duplicates'] \
            or report['source_id_duplicates'] or report['source_hash_mismatches']:
        raise ValueError('Inventory acceptance failed: ' + json.dumps(report, ensure_ascii=False))
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / 'ingest_registry.json').write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    _write_csv(out_path / 'ingest_registry.csv', rows)
    (out_path / 'ingest_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--papers', required=True, type=Path)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--baseline-report', type=Path)
    parser.add_argument('--baseline-inventory', type=Path)
    parser.add_argument('--baseline-workspace-manifest', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.papers, args.workspace, args.out, args.baseline_report,
                           args.baseline_inventory, args.baseline_workspace_manifest),
                     ensure_ascii=False, indent=2))
