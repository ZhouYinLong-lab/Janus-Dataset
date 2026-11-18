"""Check old invalid values stay invalid; this does not replay an LLM extraction."""
import argparse
from collections import Counter
from pathlib import Path
from corpus import read, save, sha
from facts_v3 import FIELDS, validate_facts
from sentence_v3 import index_document


def replay(workspace, out):
    workspace = Path(workspace)
    state = read(workspace/'candidate_state.json')
    rows = []
    for task in state['tasks'].values():
        if task.get('stage') != 'enrichment' or not task.get('result_path'):
            continue
        result_path = workspace/task['result_path']
        result = read(result_path)
        job = read(workspace/'jobs'/f'{task["job_id"]}.json')
        doc = read(job['document_path'])
        sentences = index_document(doc)
        by_unit = {s['unit_id']: s for s in sentences}
        for item in result.get('rejected', []):
            old = item.get('record', {})
            fields = old.get('fields', {})
            mapping = {'subject': 'compound', 'target': 'target', 'endpoint': 'endpoint',
                       'observation': 'result_text'}
            invalid = [new for new, prev in mapping.items()
                       if fields.get(prev) is not None and not isinstance(fields[prev], str)]
            if not invalid:
                continue
            uid = next((e.get('unit_id') for e in old.get('evidence', [])
                        if e.get('unit_id') in by_unit), None)
            # A malformed response can have no top-level evidence at all. This
            # replay tests value types only, using a trusted source sentence;
            # it does not claim that this rebound sentence supports the values.
            uid = uid or next((u['unit_id'] for u in job['primary_units']
                              if u['unit_id'] in by_unit), None)
            if not uid:
                raise ValueError('No source sentence available for scalar-only replay')
            sentence = by_unit[uid]
            candidate = {'candidate_id': 'offline-type-replay',
                         'anchor_sentence_ids': [sentence['sentence_id']]}
            effective = dict(job, sentences=sentences, frozen_context={
                'candidate': candidate, 'sentences': [sentence]})
            values = {f: fields.get(mapping[f]) if f in mapping else None for f in FIELDS}
            payload = {'status': 'observations', 'reason': None, 'observations': [{
                'values': values, 'outcome_type': 'uncertain',
                'evidence': {f: [sentence['sentence_id']] if values[f] is not None else [] for f in FIELDS}}]}
            checked = validate_facts(payload, effective, [candidate])
            errors = [e for r in checked['rejected'] for e in r['errors']]
            passed = not checked['accepted'] and all('invalid_value_type:' + f in errors for f in invalid)
            rows.append({'job_id': task['job_id'], 'candidate_id': item.get('candidate_id'),
                'source_result_sha256': sha(result_path), 'invalid_fields': invalid,
                'actual_value_types': {f: type(values[f]).__name__ for f in invalid},
                'still_rejected_without_coercion': passed, 'errors': errors})
    if len(rows) != 4 or not all(r['still_rejected_without_coercion'] for r in rows):
        raise ValueError('Expected four old invalid records, all rejected without conversion')
    report = {'replay_kind': 'offline_scalar_contract_only', 'api_requests_sent': 0,
        'recovered_extractions': 0, 'old_invalid_records': len(rows), 'passed': True,
        'source_workspace_manifest_sha256': sha(workspace/'manifest.json'), 'rows': rows,
        'limitation': 'Original object/list values are kept intact and rejected. Evidence IDs are rebound only to exercise the scalar contract; this is not a content-supported extraction or a model improvement measurement.'}
    save(out, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print({k: v for k, v in replay(args.workspace, args.out).items()
           if k in {'passed', 'api_requests_sent', 'old_invalid_records', 'recovered_extractions'}})
