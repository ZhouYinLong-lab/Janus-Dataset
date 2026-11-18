"""Check review CSV shape, provenance files, hashes and old-matrix crosswalk.

This checks document integrity, not scientific correctness or exhaustive coverage.
"""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import csv
import json
import re

ROOT = Path(__file__).resolve().parent

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        grid = list(csv.reader(f))
    if not grid:
        raise ValueError(f'Empty CSV {path}')
    bad = [(i+1,len(r)) for i,r in enumerate(grid) if len(r) != len(grid[0])]
    if bad:
        raise ValueError(f'CSV column mismatch {path}: {bad}')
    return [dict(zip(grid[0], r)) for r in grid[1:]]

def key_url(url):
    found = re.search(r'10\.\d{4,9}/[^\s?#]+', url, re.I)
    return found.group(0).rstrip('/').casefold() if found else url.rstrip('/').casefold()

def main():
    matrix = read_csv(ROOT / '证据总表.csv')
    old = read_csv(ROOT.parent / 'literature_matrix.csv')
    assert len({r['id'] for r in matrix}) == len(matrix)
    assert all(r['source_url'].startswith('https://') for r in matrix)
    missing = [r['id'] for r in matrix if r['local_source'] and not (ROOT/r['local_source']).is_file()]
    if missing:
        raise ValueError(f'Missing cited local sources {missing}')
    crosswalk = []
    for row in matrix:
        exact = [x['id'] for x in old if key_url(x['source_url']) == key_url(row['source_url'])]
        crosswalk.append(dict(review_id=row['id'], title=row['title'],
            old_matrix_ids=';'.join(exact),
            relation='already_in_matrix_same_url_or_doi' if exact else 'not_matched_by_url_or_doi_not_global_novelty',
            source_url=row['source_url']))
    with (ROOT/'与已有文献矩阵的对应.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(crosswalk[0]))
        writer.writeheader()
        writer.writerows(crosswalk)
    inventory=read_csv(ROOT/'source_inventory.csv')
    for row in inventory:
        path=ROOT/row['path']
        assert path.is_file()
        assert sha256(path.read_bytes()).hexdigest() == row['sha256'], row['path']
    manifest=json.loads((ROOT/'bridge/source_manifest.json').read_text(encoding='utf-8'))
    for row in manifest['sources']:
        if row['status']=='ok':
            path=ROOT/'bridge/sources'/row['name']
            assert sha256(path.read_bytes()).hexdigest()==row['sha256']
    summary={
        'review_date_client_timezone':'2026-10-18 Asia/Shanghai',
        'review_entries':len(matrix),
        'old_matrix_entries':len(old),
        'same_url_or_doi_in_old_matrix':sum(bool(r['old_matrix_ids']) for r in crosswalk),
        'not_same_url_or_doi_in_old_matrix':sum(not bool(r['old_matrix_ids']) for r in crosswalk),
        'crosswalk_warning':'Unmatched URLs are not proof of newly discovered papers or research novelty.',
        'read_depth_counts':dict(Counter(r['read_depth'] for r in matrix)),
        'local_source_files':len(inventory),
        'unique_source_bytes_total':sum(int(r['bytes']) for r in inventory),
        'entries_without_retained_primary_fulltext':[r['id'] for r in matrix if not r['local_source'] or r['local_source'].endswith('_metadata.json')],
        'access_challenge_files_not_evidence':[r['path'] for r in inventory if 'access_challenge' in r['validation']],
        'all_csv_shapes_valid':True,
        'all_referenced_local_sources_exist':True,
        'all_inventory_hashes_match':True,
        'all_successful_download_hashes_match':True,
        'scientific_claims_independently_reproduced':False,
        'experiments_run_this_round':False,
    }
    (ROOT/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
