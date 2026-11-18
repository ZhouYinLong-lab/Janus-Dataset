"""Create a mechanical second-round view and validate cached primary sources.

This validates file structure, not scientific correctness or model performance.
"""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import csv
import json

ROOT = Path(__file__).resolve().parent
with (ROOT.parent / '证据总表.csv').open(encoding='utf-8-sig', newline='') as handle:
    matrix = list(csv.DictReader(handle))
rows = [row for row in matrix if int(row['id'][1:]) >= 34]
assert len(rows) == 17
assert len({row['id'] for row in rows}) == 17
for row in rows:
    assert None not in row, row
    assert (ROOT.parent / row['local_source']).is_file(), row['id']
with (ROOT / '补充证据表.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(matrix[0]))
    writer.writeheader()
    writer.writerows(rows)
manifest = json.loads((ROOT / 'source_manifest.json').read_text(encoding='utf-8'))
for item in manifest['sources']:
    if item['status'] == 'ok':
        path = ROOT / 'sources' / item['name']
        assert sha256(path.read_bytes()).hexdigest() == item['sha256'], item['name']
summary = {
    'second_round_entries': len(rows),
    'source_files': len(list((ROOT / 'sources').iterdir())),
    'retained_fulltext_files': sum(path.suffix in ('.xml', '.pdf') for path in (ROOT / 'sources').iterdir()),
    'abstract_metadata_only': [row['id'] for row in rows if row['local_source'].endswith('.json')],
    'read_depth_counts': dict(Counter(row['read_depth'] for row in rows)),
    'failed_downloads': [item['name'] for item in manifest['sources'] if item['status'] != 'ok'],
    'page_images_actually_viewed': ['Caceres2020_p34.png', 'AssayFrames2017_p7.png'],
    'all_referenced_sources_exist': True,
    'all_successful_download_hashes_match': True,
    'model_experiments_run': False,
    'scientific_results_independently_reproduced': False,
}
(ROOT / 'verification.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
