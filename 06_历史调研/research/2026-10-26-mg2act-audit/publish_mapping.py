"""Keep identity/source facts reproducible while raw database and papers stay local."""
import csv
import hashlib
import json
from pathlib import Path

from label_audit import ROOT, save_csv, save_json

FIELDS = [
    'benchmark_split', 'benchmark_id', 'benchmark_row_number', 'benchmark_revision',
    'benchmark_csv_sha256', 'benchmark_structure', 'benchmark_target_uniprot', 'benchmark_e3_uniprot',
    'evidence_uid', 'version', 'original_id', 'paper_id', 'doi', 'compound', 'target',
    'smiles', 'target_uniprot', 'e3_uniprot', 'target_tag_annotation',
    'mapping_status', 'provenance_scope', 'source_doi', 'source_url', 'source_locator',
    'compound_original_name', 'source_names', 'source_structure', 'source_sha256',
    'source_row_sha256', 'mapping_basis',
]


def main():
    local = ROOT / 'local/source_mapping'
    sources = [local / 'benchmark_provenance.csv', local / 'local_identity_provenance.csv']
    rows, inputs = [], []
    for path in sources:
        payload = path.read_bytes()
        with path.open(encoding='utf-8-sig', newline='') as f:
            content = list(csv.DictReader(f))
        rows.extend({k: r.get(k, '') for k in FIELDS} for r in content)
        inputs.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(payload).hexdigest(), 'rows': len(content)})
    save_csv('source_associations.csv', rows, FIELDS)
    metadata = json.loads((local / 'mapping_summary.json').read_text(encoding='utf-8'))
    save_json('mapping_manifest.json', {'inputs': inputs, 'source_mapping_summary': metadata,
        'published_rows': len(rows), 'published_sha256': hashlib.sha256((ROOT / 'source_associations.csv').read_bytes()).hexdigest(),
        'scope': 'Database-source associations and separately resolved local identities; benchmark original assay provenance remains unknown.',
        'excluded': 'Raw assay descriptions, paper full text, original database export and protein sequences.'})
    print(json.dumps({'published_mapping_rows': len(rows), 'inputs': inputs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
