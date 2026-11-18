"""Check retained-source identity, CSV structure, and local report links.

This checks artifact integrity, not extraction accuracy or scientific claims.
"""
from pathlib import Path
from hashlib import sha256
from urllib.parse import unquote
import csv
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'source_manifest.json').read_text(encoding='utf-8'))
    inventory = []
    failures = []
    for entry in manifest['sources']:
        p = ROOT / 'sources' / entry['name']
        if entry.get('status') != 'ok' or not p.exists():
            failures.append({'source': entry['name'], 'reason': 'missing or failed retrieval'})
            continue
        data = p.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != entry['sha256']:
            failures.append({'source': entry['name'], 'reason': 'hash mismatch'})
        title, doi = '', ''
        if p.suffix == '.xml':
            root = ET.fromstring(data)
            assert root.tag == 'article', p
            n = root.find('.//article-title')
            title = ''.join(n.itertext()) if n is not None else ''
            doi = ';'.join(n.text or '' for n in root.findall('.//article-id')
                           if n.get('pub-id-type') == 'doi')
        inventory.append({'file': 'sources/' + p.name, 'bytes': len(data),
                          'sha256': digest, 'title': title, 'doi': doi, 'url': entry['url']})

    csv_counts = {}
    for p in list(ROOT.glob('*.csv')) + list((ROOT / 'branches').rglob('*.csv')):
        if p.name == 'source_inventory.csv':
            continue
        with p.open(encoding='utf-8-sig', newline='') as f:
            records = list(csv.reader(f))
        assert records and all(len(r) == len(records[0]) for r in records), p
        csv_counts[str(p.relative_to(ROOT)).replace('\\', '/')] = len(records) - 1

    reference_counts = {}
    for name in ('TPD_GT_Glues.csv', 'TPD_GT_PROTAC.csv'):
        with (ROOT / 'sources' / name).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            records = list(reader)
        assert len(reader.fieldnames) == 19
        reference_counts[name] = {'rows': len(records),
                                  'unique_dois': len({r['DOI'] for r in records if r['DOI']})}

    for p in list(ROOT.glob('*.md')) + list((ROOT / 'branches').rglob('*.md')):
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
            if target.startswith(('http:', 'https:', '#', 'mailto:')):
                continue
            local = unquote(target.split('#')[0].strip('<>'))
            if local and not (p.parent / local).exists():
                failures.append({'document': str(p.relative_to(ROOT)), 'missing_link': target})

    with (ROOT / 'source_inventory.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['file', 'bytes', 'sha256', 'title', 'doi', 'url'])
        writer.writeheader()
        writer.writerows(inventory)
    result = {'scope': 'artifact integrity only; not scientific validation',
              'source_files': len(inventory), 'source_bytes': sum(r['bytes'] for r in inventory),
              'xml_articles': sum(bool(r['title']) for r in inventory),
              'csv_rows': csv_counts, 'expert_tables': reference_counts, 'failures': failures}
    (ROOT / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not failures


if __name__ == '__main__':
    main()
