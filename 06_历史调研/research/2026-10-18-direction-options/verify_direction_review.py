"""Document/source integrity checks, not scientific or model validation."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote
import csv
import importlib.util
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        grid = list(csv.reader(stream))
    assert grid, f'Empty CSV: {path}'
    assert all(len(row) == len(grid[0]) for row in grid[1:]), f'CSV shape: {path}'
    return [dict(zip(grid[0], row)) for row in grid[1:]]


def main():
    checks = {}
    for name, expected in [
        ('主线证据表.csv', 10),
        ('方向比较表.csv', 6),
        ('branches/extraction/evidence.csv', 7),
        ('branches/targeted-value/evidence.csv', 6),
    ]:
        rows = csv_rows(ROOT / name)
        assert len(rows) == expected, (name, len(rows))
        assert len({r['id'] for r in rows}) == expected, f'Duplicate IDs: {name}'
        checks[name] = len(rows)
    for row in csv_rows(ROOT / '主线证据表.csv'):
        assert (ROOT / row['local_source']).is_file(), row['local_source']

    spec = importlib.util.spec_from_file_location('direction_sources', ROOT / 'collect_sources.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source_urls = {name: url for name, url in module.collector.TARGETS}
    artifact = json.loads((ROOT / 'public_artifact_audit.json').read_text(encoding='utf-8'))
    source_urls.update({r['name']: r['url'] for r in artifact['data_files']})
    inventory = []
    for path in sorted(ROOT.rglob('sources/*')):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        fmt = 'not_checked'
        if path.suffix.lower() == '.pdf':
            assert raw.startswith(b'%PDF-'), f'False PDF: {path}'
            fmt = 'PDF_header_ok'
        elif path.suffix.lower() == '.xml':
            ET.fromstring(raw)
            fmt = 'XML_parse_ok'
        elif path.suffix.lower() == '.json':
            json.loads(raw)
            fmt = 'JSON_parse_ok'
        elif path.suffix.lower() == '.parquet':
            assert raw.startswith(b'PAR1') and raw.endswith(b'PAR1'), path
            fmt = 'Parquet_header_footer_ok'
        inventory.append({
            'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw),
            'sha256': sha256(raw).hexdigest(), 'format_check': fmt,
            'url': source_urls.get(path.name, '') if path.parent == ROOT / 'sources' else '',
        })
    with (ROOT / 'source_inventory.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['path', 'bytes', 'sha256', 'format_check', 'url'])
        writer.writeheader()
        writer.writerows(inventory)

    broken_links = []
    for path in ROOT.rglob('*.md'):
        if 'sources' in path.relative_to(ROOT).parts:
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8-sig')):
            target = unquote(target.strip().strip('<>')).split('#')[0]
            if not target or re.match(r'^(https?://|mailto:)', target):
                continue
            local = Path(target) if re.match(r'^[A-Za-z]:[\\/]', target) else path.parent / target
            if not local.exists():
                broken_links.append({'document': path.relative_to(ROOT).as_posix(), 'target': target})

    labels = json.loads((ROOT / 'interval_label_audit.json').read_text(encoding='utf-8'))
    data = ROOT / labels['source']
    assert sha256(data.read_bytes()).hexdigest() == labels['sha256']
    assert labels['rows'] == 11370
    assert not labels['training_run'] and not labels['model_inference_run']
    for threshold in labels['thresholds']:
        assert sum(threshold['all_rows'].values()) == labels['rows']
        assert sum(threshold['censored_rows_only'].values()) == 3453
    assert not artifact['training_or_model_inference_run']
    assert not artifact['downloaded_code_executed']

    original = ROOT.parent / '2026-10-18-literature-judgment/followup/研究路线评估报告_修改前留档.md'
    original_text = original.read_text(encoding='utf-8')
    assert '<!-- ORIGINAL_START -->' in original_text and '<!-- ORIGINAL_END -->' in original_text
    report = {
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'checks': checks, 'evidence_entries_including_reused_and_software': 23,
        'source_file_count': len(inventory), 'source_bytes': sum(r['bytes'] for r in inventory),
        'format_checks': dict(Counter(r['format_check'] for r in inventory)),
        'broken_local_markdown_links': broken_links,
        'original_report_sha256_observed': sha256(original.read_bytes()).hexdigest(),
        'scope': 'Document integrity and static resource checks, not independent scientific replication, expert labeling, completeness, or model performance.',
        'passed': not broken_links,
    }
    (ROOT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert not broken_links, 'Broken Markdown links; see verification.json'


if __name__ == '__main__':
    main()
