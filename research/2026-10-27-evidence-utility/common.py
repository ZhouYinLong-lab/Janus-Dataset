"""Offline contracts and immutable artifacts shared by utility experiments."""
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
CORE = HERE.parent / '2026-10-25-api-extraction'


def read(path):
    path = Path(path)
    if path.suffix == '.jsonl':
        return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def doi(value):
    return re.sub(r'^https?://(?:dx\.)?doi.org/', '', str(value or '').strip().lower())


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def fresh(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def seal(folder, inputs=(), metadata=None):
    folder = Path(folder)
    m = {'version': 1, 'metadata': metadata or {},
         'inputs': {str(Path(p).resolve()): sha(p) for p in inputs},
         'code': {str(p.resolve()): sha(p) for p in sorted(HERE.glob('*.py'))},
         'files': {str(p.relative_to(folder)).replace('\\', '/'): sha(p)
                   for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'manifest.json'}}
    write(folder / 'manifest.json', m)
    return m


def verify(folder):
    folder = Path(folder)
    m = read(folder / 'manifest.json')
    for category in ('inputs', 'code', 'files'):
        for name, expected in m[category].items():
            path = folder / name if category == 'files' else Path(name)
            if not path.is_file() or sha(path) != expected:
                raise ValueError('Frozen hash mismatch: ' + str(path))
    return m


def source_check(doc):
    if not doc.get('source_path') or sha(doc['source_path']) != doc['source_sha256']:
        raise ValueError('Source missing/changed: ' + doc['paper_id'])
    return {u['unit_id']: u for u in doc['units']}


def check_locator(e, units):
    unit = units.get(e.get('unit_id'))
    start, end, quote = e.get('char_start'), e.get('char_end'), e.get('quote')
    if (unit is None or type(start) is not int or type(end) is not int or
            not isinstance(quote, str) or not quote or not 0 <= start < end <= len(unit['text']) or
            unit['text'][start:end] != quote):
        raise ValueError('Quote/offset mismatch: ' + str(e.get('unit_id')))


def assign_splits(rows, seed=20261027):
    """Union DOI, source bytes, paper aliases, experiment IDs and exact text duplicates."""
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owners = {}
    for i, r in enumerate(rows):
        keys = [('paper', r['paper_id']), ('source', r['source_sha256']),
                ('quote', digest(norm(r.get('original_quote') or r['text'])))]
        if r.get('doi'):
            keys.append(('doi', doi(r['doi'])))
        if r.get('experiment_id'):
            keys.append(('experiment', r['experiment_id']))
        for key in keys:
            if key in owners:
                parent[root(i)] = root(owners[key])
            else:
                owners[key] = i
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(root(i), []).append(r)
    ordered = sorted(groups.values(), key=lambda g: digest([seed, sorted(r['evidence_id'] for r in g)]))
    # Whole connected groups: at least one validation/test group when >=3 exist.
    held = max(1, round(len(ordered) * .15)) if len(ordered) >= 3 else 0
    for i, group in enumerate(ordered):
        split = 'test' if i < held else 'val' if i < 2 * held else 'train'
        group_id = digest(sorted(r['evidence_id'] for r in group))
        for r in group:
            r.update(split=split, group_id=group_id)
    return len(ordered)
