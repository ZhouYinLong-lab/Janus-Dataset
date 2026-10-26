"""Freeze public MolGlueDB and LLM-TPD-Extraction comparator rows."""
import csv
import hashlib
import json
from pathlib import Path
import re
import urllib.request

HERE = Path(__file__).resolve().parent
REV = '80606e50cf8cb66ab6268178ef29e23735ffb368'
FILES = ['README.md', 'data/molecular_glues/baseline/baseline-molgluedb-70.csv',
         'data/molecular_glues/baseline/baseline-molgluedb-processed.csv',
         'data/molecular_glues/llm/glue_data_llm.csv']


def main():
    dest = HERE / 'local/baselines'; dest.mkdir(parents=True, exist_ok=True)
    sources = []
    tables = {}
    for name in FILES:
        url = f'https://raw.githubusercontent.com/yaochenr/LLM-TPD-Extraction/{REV}/{name}'
        path = dest / Path(name).name
        if not path.exists():
            with urllib.request.urlopen(url, timeout=45) as response:
                path.write_bytes(response.read())
        payload = path.read_bytes()
        sources.append({'path': str(path.relative_to(HERE)), 'url': url, 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)})
        if name.endswith('.csv'):
            with path.open(encoding='utf-8-sig', newline='') as f: tables[path.name] = list(csv.DictReader(f))
    dbpath = HERE.parent / '2026-10-26-mg2act-audit/local/source_mapping/MolGlueDB_full.csv'
    db = list(csv.DictReader(dbpath.open(encoding='utf-8-sig', newline='')))
    sources.append({'path': str(dbpath), 'url': 'https://www.molgluedb.com/api/export_bj_data', 'sha256': hashlib.sha256(dbpath.read_bytes()).hexdigest(), 'bytes': dbpath.stat().st_size})
    papers = json.loads((HERE / 'paper_manifest.json').read_text(encoding='utf-8'))
    by_paper = {}
    coverage = []
    for paper in papers:
        doi = paper['doi'].lower()
        def matches(row):
            return any(doi == re.sub(r'^https?://(?:dx\.)?doi.org/', '', str(v).strip().lower()) for v in row.values())
        selected = [r for r in db if doi in r['SourceAddress_Website'].lower()]
        generic = [r for r in tables['glue_data_llm.csv'] if matches(r)]
        original = [r for r in tables['baseline-molgluedb-70.csv'] if matches(r)]
        processed = [r for r in tables['baseline-molgluedb-processed.csv'] if matches(r)]
        by_paper[paper['paper_id']] = {'doi': doi, 'molgluedb_records': selected,
            'generic_records': generic, 'published_baseline_records': original, 'processed_baseline_records': processed,
            'generic_coverage_status': 'published_output_present' if generic else
                'processed_baseline_present_no_output' if processed else 'no_processed_baseline_or_output_cohort_unconfirmed'}
        coverage.append({'paper_id': paper['paper_id'], 'doi': doi, 'molgluedb_rows': len(selected),
                         'generic_rows': len(generic), 'published_baseline_rows': len(original),
                         'processed_baseline_rows': len(processed),
                         'generic_coverage_status': by_paper[paper['paper_id']]['generic_coverage_status']})
    (dest / 'paper_rows.json').write_text(json.dumps(by_paper, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    summary = {'date': '2026-10-26', 'generic_repository_revision': REV, 'sources': sources,
               'paper_coverage': coverage, 'generic_columns': list(tables['glue_data_llm.csv'][0]),
               'gold_annotations_read': False,
               'limits': 'Absence from published outputs does not establish omission by an extractor if processed-cohort membership is unconfirmed.'}
    (HERE / 'baseline_manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(coverage, ensure_ascii=False))


if __name__ == '__main__': main()
