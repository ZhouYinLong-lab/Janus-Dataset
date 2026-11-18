"""Read-only inspection of public research inputs, not a modeling experiment.

Caches a bounded public Parquet file, checks its schema and provenance fields,
and records DOI endpoint responses. Never imports downloaded project code.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import importlib.util
import json
import time
import requests

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'sources'
MAX_BYTES = 8 * 1024 * 1024

def probe(item):
    key, url = item
    row = {'id': key, 'url': url}
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Janus-source-audit/1.0'})
        row.update(http_status=response.status_code, resolved_url=response.url,
                   content_type=response.headers.get('content-type', ''), bytes=len(response.content))
        if response.status_code == 200 and 'json' in row['content_type']:
            data = response.json()
            attributes = data.get('data', {}).get('attributes', {})
            row['registered_doi'] = attributes.get('doi')
            row['registered_titles'] = attributes.get('titles')
    except Exception as error:
        row['error'] = str(error)
    return row

def inspect_parquet(name, url):
    row = {'name': name, 'url': url, 'limit_bytes': MAX_BYTES}
    path = SOURCE / name
    try:
        if path.exists():
            raw = path.read_bytes()
            row['state'] = 'cached'
        else:
            started = time.monotonic()
            with requests.get(url, timeout=20, stream=True) as response:
                response.raise_for_status()
                pieces, size = [], 0
                for piece in response.iter_content(65536):
                    size += len(piece)
                    if size > MAX_BYTES or time.monotonic() - started > 45:
                        raise ValueError('Bounded retrieval stopped: size or elapsed-time cap')
                    pieces.append(piece)
                raw = b''.join(pieces)
            if not raw.startswith(b'PAR1') or not raw.endswith(b'PAR1'):
                raise ValueError('Not a standard Parquet container; possible Git LFS pointer or error page')
            path.write_bytes(raw)
            row['state'] = 'downloaded'
        row.update(bytes=len(raw), sha256=sha256(raw).hexdigest())
        if importlib.util.find_spec('pyarrow') is None:
            row['inspection'] = 'Valid Parquet magic; schema not inspected because pyarrow is unavailable'
            return row
        import pyarrow.parquet as pq
        table = pq.read_table(path)
        row.update(rows=table.num_rows, columns=table.column_names)
        for key in ('censoring_class', 'standard_relation', 'assay_type', 'target_key'):
            if key in table.column_names:
                row[key + '_counts'] = table[key].to_pandas().value_counts(dropna=False).to_dict()
        row['provenance_fields'] = [key for key in table.column_names
            if any(term in key.lower() for term in ('assay', 'document', 'source', 'year', 'activity_id'))]
        row['caution'] = 'Available columns and row counts are not validation of experimental labels or paper results.'
    except Exception as error:
        row['error'] = str(error)
    return row

def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    endpoints = [
        ('software_doi', 'https://doi.org/10.5281/zenodo.21417709'),
        ('software_datacite', 'https://api.datacite.org/dois/10.5281/zenodo.21417709'),
        ('software_zenodo_record', 'https://zenodo.org/api/records/21417709'),
        ('claimed_manuscript_doi', 'https://doi.org/10.26434/chemrxiv.15006239/v1'),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        endpoint_results = list(pool.map(probe, endpoints))
    parquet_results = [inspect_parquet(name, url) for name, url in [
        ('CensorADMET_hERG_IC50_B.parquet', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/data/endpoints/hERG_IC50_B.parquet'),
        ('CensorADMET_measurements.parquet', 'https://raw.githubusercontent.com/eva-mitropoulou/censorADMET/main/data/measurement_records.parquet'),
    ]]
    report = {'checked_utc': datetime.now(timezone.utc).isoformat(),
        'doi_probes': endpoint_results, 'data_files': parquet_results,
        'training_or_model_inference_run': False, 'downloaded_code_executed': False,
        'paper_findings_independently_reproduced': False}
    (ROOT / 'public_artifact_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

if __name__ == '__main__':
    main()
