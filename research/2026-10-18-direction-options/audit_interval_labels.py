"""Inspect a released aggregate table; no model fitting or inference.

Classification is illustrative, not a clinically meaningful safety decision.
Each aggregate row is a release-level assertion, not independently validated
measurement evidence. Preserve an unresolved class if the bound is insufficient.
"""
from pathlib import Path
import hashlib
import json
import math

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'sources/CensorADMET_hERG_IC50_B.parquet'


def classify(row, threshold_p):
    relation = row['relation_p']
    if relation == '=':
        return 'supported_inhibitory' if row['value_p'] >= threshold_p else 'supported_not_inhibitory_at_threshold'
    if relation == '<' and row['upper_bound_p'] <= threshold_p:
        return 'supported_not_inhibitory_at_threshold'
    if relation == '>' and row['lower_bound_p'] >= threshold_p:
        return 'supported_inhibitory'
    return 'insufficient_bound'


def main():
    rows = pq.read_table(DATA).to_pylist()
    result = {
        'source': str(DATA.relative_to(ROOT)),
        'sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(),
        'rows': len(rows),
        'unit_definition': 'pIC50=-log10(IC50 in mol/L); inhibitory if IC50 <= the illustrative threshold',
        'scope': 'hERG IC50 assay_type B aggregate; not raw replicate records, clinical safety, or a literature-extraction experiment',
        'training_run': False,
        'model_inference_run': False,
        'classification_assumption': 'Trust release relations =, <, > and bound orientation as supplied; do not replace a bound by an exact value.',
        'multi_assay_rows': sum(r['n_assays'] > 1 for r in rows),
        'multi_document_rows': sum(r['n_documents'] > 1 for r in rows),
        'quality_flag_counts': {},
        'thresholds': [],
    }
    for row in rows:
        q = row['quality_flag']
        result['quality_flag_counts'][q] = result['quality_flag_counts'].get(q, 0) + 1
    for threshold_um in (1.0, 10.0):
        p = -math.log10(threshold_um * 1e-6)
        counts = {}
        bound_counts = {}
        for row in rows:
            label = classify(row, p)
            counts[label] = counts.get(label, 0) + 1
            if row['relation_p'] != '=':
                bound_counts[label] = bound_counts.get(label, 0) + 1
        assert sum(counts.values()) == len(rows)
        assert sum(bound_counts.values()) == sum(r['relation_p'] != '=' for r in rows)
        result['thresholds'].append({'threshold_um': threshold_um, 'threshold_p': p, 'all_rows': counts, 'censored_rows_only': bound_counts})
    (ROOT / 'interval_label_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
