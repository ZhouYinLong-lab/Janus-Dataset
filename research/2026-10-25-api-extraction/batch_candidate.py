"""Candidate-scoped enrichment runner; body discovery and shared budget stay unchanged."""
import argparse
import csv
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import batch_contract
import batch_export
import batch_plan
import batch_run
from api import check_config
from corpus import normal, read, save, sha
from candidate_context import build_candidate_contexts
from contract import FIELDS

STATUS_VALUES = {'supported', 'not_found_in_supplied_context', 'ambiguous_in_supplied_context'}


def candidate_request_for(workspace, job, stage, config, candidates=None, discovery_hash=None):
    if stage == 'discovery':
        return batch_plan.request_for(workspace, job, stage, config, candidates, discovery_hash)
    contexts, context_units = build_candidate_contexts(job, candidates or [])
    user = {
        'paper_id': job['paper_id'], 'doi': job.get('doi'), 'title': job.get('title'),
        'candidates': candidates or [], 'candidate_contexts': contexts,
        'context_units': context_units, 'discovery_result_sha256': discovery_hash,
    }
    prompt = ((Path(workspace) / 'enrichment.md').read_text(encoding='utf-8') + '\n\n'
              + (Path(workspace) / 'record_schema.txt').read_text(encoding='utf-8'))
    payload = {'model': config['model'], 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)},
    ], 'stream': read(Path(workspace) / 'manifest.json').get('transport') == 'sse',
       config['output_token_parameter']: config['max_output_tokens']}
    if payload['stream']:
        payload['stream_options'] = {'include_usage': True}
    if config['response_format'] == 'json_object':
        payload['response_format'] = {'type': 'json_object'}
    return payload


def candidate_enrichment(payload, job, candidates):
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise ValueError('Invalid candidate enrichment response')
    status_by_candidate = {}
    clean_items = []
    status_errors = []
    for item in payload['items']:
        if not isinstance(item, dict):
            clean_items.append(item)
            continue
        clean_items.append({k: item[k] for k in ('candidate_id', 'record') if k in item})
        cid = item.get('candidate_id')
        statuses = item.get('field_search_status')
        if not isinstance(cid, str) or not isinstance(statuses, dict) or set(statuses) != set(FIELDS):
            status_errors.append({'candidate_id': cid, 'error': 'missing_or_invalid_field_search_status'})
            continue
        if any(value not in STATUS_VALUES for value in statuses.values()):
            status_errors.append({'candidate_id': cid, 'error': 'unknown_field_search_status_value'})
            continue
        record = item.get('record')
        fields = record.get('fields', {}) if isinstance(record, dict) else {}
        mismatched = [field for field in FIELDS if
                      (fields.get(field) is not None) != (statuses[field] == 'supported')]
        if mismatched:
            status_errors.append({'candidate_id': cid, 'error': 'status_value_conflict',
                                  'fields': mismatched})
            continue
        status_by_candidate[cid] = statuses

    candidate_contexts, shared_units = build_candidate_contexts(job, candidates)
    for candidate in candidates:
        if not any(u['unit_id'] == candidate['unit_id'] for u in job['primary_units']):
            raise ValueError('Candidate anchor is absent from the frozen primary job')
    anchor_ids = {candidate['unit_id'] for candidate in candidates}
    validation_job = dict(job, primary_units=job['primary_units'],
                          context_units=[u for u in shared_units if u['unit_id'] not in anchor_ids])

    cleaned = dict(payload)
    cleaned['items'] = clean_items
    base = batch_contract.enrichment(cleaned, validation_job, candidates)
    allowed = {x['candidate_id']: set(x['allowed_evidence_unit_ids']) for x in candidate_contexts}
    candidates_by_id = {candidate['candidate_id']: candidate for candidate in candidates}
    accepted, rejected = [], list(base['rejected'])
    for item in base['accepted']:
        cid = item['candidate_id']
        record = item['record']
        wrong_scope = sorted({e['unit_id'] for e in record['evidence']
                              if e['unit_id'] not in allowed.get(cid, set())})
        candidate_quote = normal(candidates_by_id[cid]['quote'])
        anchor_quotes_outside = [e for e in record['evidence']
                                 if e['unit_id'] == candidates_by_id[cid]['unit_id']
                                 and normal(e['quote']) not in candidate_quote]
        if wrong_scope or anchor_quotes_outside:
            rejected.append({'candidate_id': cid, 'record': record,
                             'errors': (['evidence_from_another_candidate_context'] if wrong_scope else [])
                                       + (['anchor_evidence_outside_candidate_quote']
                                          if anchor_quotes_outside else []),
                             'unit_ids': wrong_scope})
            continue
        statuses = status_by_candidate.get(cid)
        if statuses is None:
            status_errors.append({'candidate_id': cid, 'error': 'field_search_status_not_usable'})
            statuses = {field: ('supported' if record['fields'].get(field) is not None
                                else 'ambiguous_in_supplied_context') for field in FIELDS}
        record['field_search_status'] = statuses
        candidate_issues = [issue for issue in status_errors if issue.get('candidate_id') == cid]
        if candidate_issues:
            record['field_search_status_issues'] = candidate_issues
        accepted.append(item)
    for issue in status_errors:
        cid = issue.get('candidate_id')
        if cid in status_by_candidate:
            continue
        # Keep core extraction status separate from whether the requested audit
        # wrapper was usable; it must not silently look like a valid field audit.
        issue['record_retained_if_core_valid'] = cid in {x['candidate_id'] for x in accepted}
    base['accepted'] = accepted
    base['rejected'] = rejected
    base['field_status_issues'] = status_errors
    return base


def prepare(workspace, papers=None, manifest_path=None, limit=5):
    workspace = Path(workspace)
    manifest = batch_plan.prepare(workspace, papers, manifest_path, limit)
    prompt_path = workspace / 'enrichment.md'
    prompt_path.write_bytes((HERE / 'enrichment_candidate.md').read_bytes())
    manifest['file_hashes']['enrichment.md'] = sha(prompt_path)
    manifest['candidate_context_version'] = 1
    for filename in ('batch_candidate.py', 'candidate_context.py'):
        manifest['code_hashes'][filename] = sha(HERE / filename)
    save(workspace / 'manifest.json', manifest)
    batch_plan.verify(workspace)
    return manifest


def export_context_audit(workspace):
    workspace = Path(workspace)
    summary = batch_export.export(workspace)
    records_path = workspace / 'exports' / 'records.json'
    records = read(records_path)
    columns = ['record_key', 'paper_id', 'doi', 'candidate_id', *FIELDS]
    with (workspace / 'exports' / 'field_search_status.csv').open(
            'w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in records:
            statuses = record.get('field_search_status', {})
            candidate_ids = sorted({p.get('candidate_id') for p in record.get('provenance', [])
                                    if p.get('candidate_id')}) or ['']
            for candidate_id in candidate_ids:
                writer.writerow({'record_key': record.get('record_key'),
                    'paper_id': record.get('paper_id'), 'doi': record.get('doi'),
                    'candidate_id': candidate_id,
                    **{field: statuses.get(field, '') for field in FIELDS}})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--papers', nargs='+')
    p.add_argument('--manifest', type=Path)
    p.add_argument('--limit', type=int, default=5)
    p = sub.add_parser('run')
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--ledger', required=True, type=Path)
    p.add_argument('--env-file', type=Path)
    p.add_argument('--live', action='store_true')
    p.add_argument('--retry-known', action='store_true')
    p.add_argument('--max-new-requests', type=int)
    for name in ('status', 'export'):
        sub.add_parser(name).add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.workspace, args.papers, args.manifest, args.limit)
        print(json.dumps({'papers': len(result['papers']), 'discovery_jobs': len(result['job_ids']),
                          'api_requests_sent': 0, 'candidate_context_version': 1}, ensure_ascii=False))
        return
    workspace = args.workspace
    manifest = batch_plan.verify(workspace)
    if manifest.get('candidate_context_version') != 1:
        parser.error('Workspace was not prepared with batch_candidate.py prepare')
    if args.command in {'status', 'export'}:
        print(json.dumps(export_context_audit(workspace), ensure_ascii=False, indent=2))
        return
    config = read(args.config)
    check_config(config)
    batch_run.request_for = candidate_request_for
    batch_run.enrichment = candidate_enrichment
    result = batch_run.run(workspace, config, args.ledger, live=args.live,
                           env_file=args.env_file, retry_known=args.retry_known,
                           max_new_requests=args.max_new_requests)
    export_context_audit(workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
