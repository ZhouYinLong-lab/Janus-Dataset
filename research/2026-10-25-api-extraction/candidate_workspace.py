"""Prepare immutable MolGlueDB jobs; preparation never reads credentials."""
import json
from pathlib import Path
import shutil
import time

from api import check_config, reserve_tokens
from batch_plan import CODE, request_for
from contract import DOMAINS, FIELDS, NEGATIVES
from corpus import HERE, read, save, sha
from prepare import build_jobs
from source_formats import parse_document

PIPELINE = 'molgluedb_candidates_v2'
PILOT_PAPERS = ('B212', 'B207', 'B235', 'B203', 'B296')
RUNTIME_FILES = (*CODE, 'batch_candidate.py', 'candidate_context.py',
                 'candidate_workspace.py', 'candidate_runtime.py', 'candidate_export.py',
                 'candidate_acceptance.py', 'source_formats.py', 'molglue_sources.py')


def prepare(workspace, papers=None, manifest_path=None, limit=None, phase='full'):
    workspace = Path(workspace).resolve()
    if workspace.exists():
        raise ValueError('Workspace exists; resume it instead of replacing inputs')
    if not manifest_path:
        raise ValueError('An explicit MolGlueDB papers.json manifest is required')
    source = read(manifest_path)
    if not isinstance(source, list):
        raise ValueError('Paper manifest must be an array')
    requested = set(papers or (PILOT_PAPERS if phase == 'pilot' else ()))
    selected = [p for p in source if not requested or
                p.get('paper_id') in requested or p.get('legacy_paper_id') in requested]
    if requested - {p.get('paper_id') for p in selected} - {p.get('legacy_paper_id') for p in selected}:
        raise ValueError('Required pilot/selected papers missing from source inventory')
    selected = sorted(selected, key=lambda p: p['paper_id'])
    if limit is not None:
        if type(limit) is not int or limit < 1:
            raise ValueError('Positive limit required')
        selected = selected[:limit]
    ids = [p['paper_id'] for p in selected]
    import re
    if not ids or len(set(ids)) != len(ids) or any(
            not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', pid) for pid in ids):
        raise ValueError('Safe unique paper IDs required')
    workspace.mkdir(parents=True)
    m = {'pipeline': PIPELINE, 'version': 2, 'candidate_context_version': 2,
         'transport': 'sse', 'phase': phase, 'created': time.time(), 'batch_size': 8,
         'papers': [], 'job_ids': [], 'file_hashes': {},
         'code_hashes': {name: sha(HERE / name) for name in RUNTIME_FILES},
         'input_manifest_sha256': sha(manifest_path), 'expert_gold': False,
         'coverage': 'All readable narrative body; captions/tables contextual; no pixels'}
    runtime = workspace / 'runtime'
    runtime.mkdir()
    for name in RUNTIME_FILES:
        shutil.copyfile(HERE / name, runtime / name)
    for name in ('discovery.md', 'enrichment_candidate.md'):
        dest = 'enrichment.md' if name.startswith('enrichment') else name
        shutil.copyfile(HERE / name, workspace / dest)
        m['file_hashes'][dest] = sha(workspace / dest)
    record = {'domain': 'uncertain', 'negative_type': 'uncertain',
              'experimental_setting': 'mixed_or_unclear', 'directness': 'unclear',
              'fields': dict.fromkeys(FIELDS), 'evidence': [], 'qualifiers': []}
    schema = ('Each record has exactly this shape:\n' + json.dumps(record)
              + '\nAllowed domain: ' + ', '.join(sorted(DOMAINS))
              + '\nAllowed negative_type: ' + ', '.join(sorted(NEGATIVES))
              + '\nexperimental_setting: unperturbed, special_condition, mixed_or_unclear.'
              + '\ndirectness: explicit, author_inferred, unclear.'
              + '\nEvery non-null field needs evidence with exactly field, unit_id, quote.'
              + '\nQuotes must be exact source text, 8 to 3000 characters after normalization.'
              + '\nKeep unknown fields null. No significant effect is not measured zero.'
              + '\nDo not mix observation endpoints or infer unprovided image/SI values.')
    (workspace / 'record_schema.txt').write_text(schema, encoding='utf-8')
    m['file_hashes']['record_schema.txt'] = sha(workspace / 'record_schema.txt')
    for metadata in selected:
        row = dict(metadata, job_ids=[], status='input_gap')
        path = metadata.get('path')
        try:
            if not path:
                raise ValueError('source_not_available')
            doc = parse_document(path, row['paper_id'])
            row.update(source_path=doc['source_path'], source_sha256=doc['source_sha256'],
                       parsed_coverage=doc['coverage'], format=Path(path).suffix.lower())
            if doc['status'] not in {'readable', 'readable_partial'}:
                raise ValueError(doc['status'])
            # Newly supported layouts stay quarantined until format acceptance
            # is bound to this parser revision; XML retains the established path.
            if Path(path).suffix.lower() in {'.html', '.htm', '.pdf'}:
                review = metadata.get('format_review', {})
                if (review.get('source_sha256') != doc['source_sha256'] or
                        review.get('parser_sha256') != sha(HERE/'source_formats.py') or
                        review.get('body_order_checked') is not True or
                        review.get('body_boundaries_checked') is not True):
                    raise ValueError('format_requires_acceptance_before_automatic_enqueue')
                row['format_review'] = review
            name = f'documents/{row["paper_id"]}.json'
            save(workspace / name, doc)
            m['file_hashes'][name] = sha(workspace / name)
            for job in build_jobs(doc, metadata):
                job['document_path'] = str(workspace / name)
                target = f'jobs/{job["job_id"]}.json'
                save(workspace / target, job)
                m['file_hashes'][target] = sha(workspace / target)
                row['job_ids'].append(job['job_id'])
                m['job_ids'].append(job['job_id'])
            row['status'] = 'prepared' if row['job_ids'] else 'input_gap'
        except (OSError, ValueError, TypeError, KeyError) as error:
            row['input_error'] = (str(error) if isinstance(error, ValueError) else type(error).__name__)[:160]
        m['papers'].append(row)
    save(workspace / 'manifest.json', m)
    verify(workspace)
    return m


def verify(workspace):
    workspace = Path(workspace)
    m = read(workspace / 'manifest.json')
    if m.get('pipeline') != PIPELINE:
        raise ValueError('This entry requires a v2 MolGlueDB workspace')
    for name, digest in m['file_hashes'].items():
        if sha(workspace / name) != digest:
            raise ValueError('Frozen input changed: ' + name)
    for name, digest in m['code_hashes'].items():
        if sha(HERE / name) != digest or sha(workspace / 'runtime' / name) != digest:
            raise ValueError('Runtime changed; use the matching frozen version: ' + name)
    for paper in m['papers']:
        if paper.get('source_sha256') and sha(paper['source_path']) != paper['source_sha256']:
            raise ValueError('Original source changed: ' + paper['paper_id'])
    return m


def check(workspace, config, ledger_path):
    import batch_budget
    check_config(config)
    m = verify(workspace)
    total = sum(reserve_tokens(request_for(workspace,
                    read(Path(workspace) / f'jobs/{jid}.json'), 'discovery', config), config)
                for jid in m['job_ids'])
    return {'pipeline': PIPELINE, 'papers': len(m['papers']),
            'readable_papers': sum(bool(p['job_ids']) for p in m['papers']),
            'input_gap_papers': [p['paper_id'] for p in m['papers'] if not p['job_ids']],
            'discovery_requests': len(m['job_ids']), 'discovery_token_reservation': total,
            'enrichment_requests': 'Unknown until discovery; at most 100 one-candidate groups per job',
            'budget': batch_budget.status(ledger_path), 'generation_requests_sent': 0,
            'estimate_is_billing_amount': False}
