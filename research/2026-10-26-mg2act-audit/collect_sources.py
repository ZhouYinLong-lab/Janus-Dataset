"""Freeze public MG2Act inputs without any model or credential access."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
REV = 'd3f9d1da48be93d67cfc2be074c0cf0c6bdbb065'
FILES = ['README.md', 'LICENSE', 'MG2Act/dataset.py', 'MG2Act/evaluate.py',
         'MG2Act/train.py', 'MG_data/train.csv', 'MG_data/val.csv', 'MG_data/test.csv']
PAPERS = {
    'article.pdf': 'https://www.biorxiv.org/content/10.64898/2026.08.08.739980v1.full.pdf',
    'supplement.pdf': 'https://www.biorxiv.org/content/biorxiv/early/2026/08/13/2026.08.08.739980/DC1/embed/media-1.pdf?download=true',
}


def main():
    manifest_path = ROOT / 'source_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    expected = {x['path']: x['sha256'] for x in previous.get('files', [])}
    manifest = {'repository': 'https://github.com/Zzy522/MG2Act', 'revision': REV,
                'retrieved_on': '2026-10-26', 'files': []}
    for name in FILES:
        url = f'https://raw.githubusercontent.com/Zzy522/MG2Act/{REV}/{name}'
        target = ROOT / 'local' / 'upstream' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            payload = target.read_bytes()
            if name in expected and hashlib.sha256(payload).hexdigest() != expected[name]:
                raise ValueError(f'Frozen source changed: {name}')
        else:
            request = urllib.request.Request(url, headers={'User-Agent': 'Janus-research-audit/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            target.write_bytes(payload)
        manifest['files'].append({'path': name, 'url': url, 'bytes': len(payload),
                                  'sha256': hashlib.sha256(payload).hexdigest()})
    manifest['paper_sources'] = []
    for name, url in PAPERS.items():
        target = ROOT / 'local' / 'paper' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read()
            if not payload.startswith(b'%PDF'):
                raise ValueError(f'Not a PDF: {url}')
            target.write_bytes(payload)
        payload = target.read_bytes()
        old = next((x for x in previous.get('paper_sources', []) if x['path'] == name), None)
        digest = hashlib.sha256(payload).hexdigest()
        if old and old['sha256'] != digest:
            raise ValueError(f'Frozen paper changed: {name}')
        manifest['paper_sources'].append({'path': name, 'url': url, 'bytes': len(payload), 'sha256': digest})
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'revision': REV, 'files': len(FILES)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
