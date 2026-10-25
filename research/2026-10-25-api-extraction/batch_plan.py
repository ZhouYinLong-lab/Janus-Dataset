"""Generic frozen two-stage paper queue. Preparation is offline and key-free."""
import json
from pathlib import Path
import re

from api import check_config, reserve_tokens
from contract import DOMAINS, FIELDS, NEGATIVES
from corpus import HERE, PARSER_VERSION, existing_papers, parse_source, read, save, sha
from prepare import build_jobs

CODE = ('batch.py', 'batch_plan.py', 'batch_contract.py', 'batch_budget.py',
        'batch_run.py', 'batch_export.py', 'api.py', 'credentials.py',
        'corpus.py', 'prepare.py', 'contract.py', 'two_stage_core.py', 'runner.py', 'export.py',
        'stream_http.py', 'batch_upgrade.py')
BATCH_SIZE = 8


def prepare(workspace, papers=None, custom=None, limit=5):
    workspace = Path(workspace)
    if workspace.exists():
        raise ValueError('Workspace exists: resume it, do not prepare again')
    if type(limit) is not int or limit < 1:
        raise ValueError('Positive paper limit required')
    if custom:
        selected = read(custom)
        if not isinstance(selected, list) or any(not isinstance(x, dict) for x in selected):
            raise ValueError('Manifest must be an array of paper metadata')
    else:
        _, meta = existing_papers()
        if papers and set(papers) - set(meta):
            raise ValueError('Unknown paper IDs')
        selected = [meta[p] for p in papers] if papers else [m for m in meta.values()
            if 'molecular_glue_degradation' in m['legacy_scope_groups']
            and 'include' in m['legacy_metadata_decisions']]
    if papers and custom:
        selected = [m for m in selected if m.get('paper_id') in papers]
        if set(papers) - {m.get('paper_id') for m in selected}:
            raise ValueError('Selected papers missing from custom manifest')
    selected = selected[:limit] if papers else sorted(selected, key=lambda m: str(m.get('paper_id')))[:limit]
    ids = [m.get('paper_id') for m in selected]
    if not ids or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', p) for p in ids):
        raise ValueError('Safe unique paper IDs required')
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate paper IDs')
    workspace.mkdir(parents=True)
    manifest = {'version': 1, 'pipeline': 'two_stage_batch_v1', 'transport': 'sse', 'parser_version': PARSER_VERSION,
                'batch_size': BATCH_SIZE, 'papers': [], 'job_ids': [], 'file_hashes': {},
                'code_hashes': {n: sha(HERE / n) for n in CODE},
                'input_manifest_sha256': sha(custom) if custom else None,
                'selection': 'Explicit local queue; historical scope metadata is not expert confirmation',
                'coverage': 'All parsed narrative body units; no figure pixels or separate supplements',
                'expert_gold': False}
    for m in selected:
        entry = {k: m.get(k) for k in ['paper_id', 'doi', 'title', 'url', 'source_license']}
        entry.update(source_path=None, source_sha256=None, job_ids=[], status='input_gap')
        try:
            if not isinstance(m.get('path'), str) or not m['path'].strip():
                raise ValueError('Missing source path')
            entry['source_path'] = str(Path(m['path']).resolve())
            source = Path(entry['source_path'])
            if not source.is_file():
                raise ValueError('Source is not a file')
            entry['source_sha256'] = sha(source)
            document = parse_source(source, m['paper_id'])
            jobs = build_jobs(document, m)
            doc_path = f'documents/{m["paper_id"]}.json'
            save(workspace / doc_path, document)
            manifest['file_hashes'][doc_path] = sha(workspace / doc_path)
            for job in jobs:
                name = f'jobs/{job["job_id"]}.json'
                save(workspace / name, job)
                manifest['file_hashes'][name] = sha(workspace / name)
                entry['job_ids'].append(job['job_id']); manifest['job_ids'].append(job['job_id'])
            entry.update(status='prepared' if jobs else 'input_gap',
                         body_units=sum(u['kind'] == 'body_paragraph' for u in document['units']))
            if not jobs:
                entry['input_error'] = 'no_structured_body'
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            entry['input_error'] = 'source_unreadable_or_invalid'
        except Exception:
            # XML parsing errors are input failures; do not expose source contents.
            entry['input_error'] = 'source_parse_failed'
        manifest['papers'].append(entry)
    for name in ['discovery.md', 'enrichment.md']:
        (workspace / name).write_bytes((HERE / name).read_bytes())
        manifest['file_hashes'][name] = sha(workspace / name)
    record = {'domain': 'uncertain', 'negative_type': 'uncertain',
              'experimental_setting': 'mixed_or_unclear', 'directness': 'unclear',
              'fields': dict.fromkeys(FIELDS), 'evidence': [], 'qualifiers': []}
    schema = ('Each item.record has exactly this shape:\n' + json.dumps(record)
              + '\nAllowed domain: ' + ', '.join(sorted(DOMAINS))
              + '\nAllowed negative_type: ' + ', '.join(sorted(NEGATIVES))
              + '\nAllowed experimental_setting: unperturbed, special_condition, mixed_or_unclear.'
              + '\nAllowed directness: explicit, author_inferred, unclear.'
              + '\nEach evidence entry has exactly field, unit_id, quote. field must be one of fields keys.'
              + '\nEvery quote must be copied exactly from its cited unit, at least 8 characters after whitespace normalization and at most 3000 characters. For short identifiers such as HF or WDR18, quote the containing clause or sentence, not only the identifier. Never use ellipses to replace source words.'
              + '\nUse molecular_glue only when supported; keep PROTACs and engineered tags separate.'
              + '\nNo significant effect is not zero. Missing residual protein can indicate successful degradation.'
              + '\nKeep unknowns null; use context only for supported interpretation. Do not guess image or SI values.'
              + '\nDiscovery category no_activity is NOT an allowed negative_type. For an undetected non-degradation response use response_not_detected, or uncertain if its endpoint is unclear. Keep the actual endpoint.')
    (workspace / 'record_schema.txt').write_text(schema, encoding='utf-8')
    manifest['file_hashes']['record_schema.txt'] = sha(workspace / 'record_schema.txt')
    save(workspace / 'manifest.json', manifest)
    return manifest


def verify(workspace):
    workspace = Path(workspace); m = read(workspace / 'manifest.json')
    if m.get('pipeline') != 'two_stage_batch_v1':
        raise ValueError('Not a generic batch workspace')
    for name, digest in m['file_hashes'].items():
        if sha(workspace / name) != digest:
            raise ValueError('Frozen input changed: ' + name)
    for name, digest in m['code_hashes'].items():
        if sha(HERE / name) != digest:
            raise ValueError('Processing code changed; frozen workspace will not silently mix versions')
    for p in m['papers']:
        if p.get('source_sha256') and sha(p['source_path']) != p['source_sha256']:
            raise ValueError('Source file changed: ' + p['paper_id'])
    return m


def request_for(workspace, job, stage, config, candidates=None, discovery_hash=None):
    workspace = Path(workspace)
    user = {k: job.get(k) for k in ['paper_id', 'doi', 'title', 'primary_units']}
    if stage == 'discovery':
        prompt = (workspace / 'discovery.md').read_text(encoding='utf-8')
    elif stage == 'enrichment':
        prompt = ((workspace / 'enrichment.md').read_text(encoding='utf-8') + '\n\n'
                  + (workspace / 'record_schema.txt').read_text(encoding='utf-8'))
        user.update(context_units=job['context_units'], candidates=candidates,
                    discovery_result_sha256=discovery_hash,
                    context_omitted_units=job.get('context_omitted_units', 0))
    else:
        raise ValueError('Unknown batch stage')
    payload = {'model': config['model'], 'messages': [{'role': 'system', 'content': prompt},
               {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}],
               'stream': read(workspace / 'manifest.json').get('transport') == 'sse',
               config['output_token_parameter']: config['max_output_tokens']}
    if payload['stream']:
        payload['stream_options'] = {'include_usage': True}
    if config['response_format'] == 'json_object':
        payload['response_format'] = {'type': 'json_object'}
    return payload


def estimate(workspace, config):
    check_config(config); workspace = Path(workspace); m = verify(workspace)
    discovery_tokens = 0; minimum_enrich = 0
    for jid in m['job_ids']:
        job = read(workspace / f'jobs/{jid}.json')
        discovery_tokens += reserve_tokens(request_for(workspace, job, 'discovery', config), config)
        minimum_enrich += reserve_tokens(request_for(workspace, job, 'enrichment', config, [], 'estimated'), config)
    return {'api_requests_sent': 0, 'credentials_read': False, 'papers': len(m['papers']),
            'input_gap_papers': [p['paper_id'] for p in m['papers'] if not p['job_ids']],
            'discovery_requests': len(m['job_ids']),
            'enrichment_requests_if_one_batch_each': len(m['job_ids']),
            'enrichment_max_if_100_candidates_each': 13 * len(m['job_ids']),
            'discovery_reserved_token_estimate': discovery_tokens,
            'enrichment_estimate_excluding_discovered_candidates_one_batch_each': minimum_enrich,
            'notice': 'Enrichment skipped for empty discovery; batches of eight candidates may require more than one request. Shared ledger is the hard operational cap; estimates are not currency limits.'}
