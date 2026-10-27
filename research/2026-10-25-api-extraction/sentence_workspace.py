"""Prepare and verify isolated sentence_v3 workspaces without credentials or I/O to APIs."""
import ast
from pathlib import Path
import re
import shutil
import time

from api import check_config, reserve_tokens
from corpus import HERE, read, save, sha
import facts_v3
import sentence_v3
import sentence_workflow
from source_formats import parse_document


PIPELINE = 'molgluedb_sentence_v3'
PROTOCOL = 'sentence_v3'
PILOT_MANIFEST = HERE / 'local/sentence_v3_evaluation/papers.json'
PILOT_PAPERS = ('MG_5cf5ae284fe057161ed1f3e2', 'MG_51cc8beb041f311c9f9c6a7c',
                'MG_7483136d16dced0733a36f6e', 'MG_1601b48e6bb99dc76c546cfc', 'B296')
PILOT_DOIS = ('10.1002/advs.202104344', '10.1002/advs.202412985',
              '10.1002/advs.202413676', '10.1002/ctm2.881', '10.1038/s41586-020-2374-x')
PROMPTS = ('discovery_v3.md', 'facts_v3.md', 'conditions_v3.md')
PRIMARY_CAP = 4000
MAX_PARAGRAPHS = 3


def runtime_files():
    """Freeze entry points and their transitive local Python imports, including lazy imports."""
    pending = ['batch_candidate.py', 'candidate_runtime.py', 'sentence_workspace.py',
               'sentence_export.py', 'sentence_v3.py', 'facts_v3.py', 'sentence_workflow.py',
               'sentence_acceptance.py']
    found = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = HERE / name
        if not path.is_file():
            raise ValueError('Required sentence runtime module missing: ' + name)
        found.add(name)
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                dependency = module.split('.')[0] + '.py'
                if (HERE / dependency).is_file() and dependency not in found:
                    pending.append(dependency)
    return sorted(found)


def _selected(manifest_path, papers, limit, phase):
    source = read(manifest_path)
    if not isinstance(source, list) or any(not isinstance(p, dict) for p in source):
        raise ValueError('Paper manifest must be an array of metadata objects')
    if phase not in {'pilot', 'full'}:
        raise ValueError('phase must be pilot or full')
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError('Positive limit required')
    requested = set(papers or (PILOT_PAPERS if phase == 'pilot' else ()))
    selected = [p for p in source if not requested or
                p.get('paper_id') in requested or p.get('legacy_paper_id') in requested]
    matched = {p.get('paper_id') for p in selected} | {p.get('legacy_paper_id') for p in selected}
    if requested - matched:
        raise ValueError('Required pilot/selected papers missing from source inventory')
    rank = {pid: index for index, pid in enumerate(PILOT_PAPERS)}
    selected.sort(key=(lambda p: rank.get(p.get('paper_id'), len(rank))) if phase == 'pilot'
                  else (lambda p: str(p.get('paper_id'))))
    if limit is not None:
        selected = selected[:limit]
    ids = [p.get('paper_id') for p in selected]
    if (not ids or any(not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', pid)
                       for pid in ids) or len(set(ids)) != len(ids)):
        raise ValueError('Safe unique paper IDs required')
    if phase == 'pilot':
        expected = dict(zip(PILOT_PAPERS, PILOT_DOIS))
        if set(ids) != set(expected) or any(p.get('doi') != expected[p['paper_id']] for p in selected):
            raise ValueError('sentence_v3 pilot requires B296 and the four fixed new XML papers')
    return selected


def prepare(workspace, papers=None, manifest_path=None, limit=None, phase='full'):
    workspace = Path(workspace).resolve()
    if workspace.exists():
        raise ValueError('Workspace exists; prepare sentence_v3 in a new workspace')
    if manifest_path is None:
        if phase != 'pilot':
            raise ValueError('An explicit papers.json manifest is required for full preparation')
        manifest_path = PILOT_MANIFEST
    manifest_path = Path(manifest_path).resolve()
    selected = _selected(manifest_path, papers, limit, phase)
    code = runtime_files()
    artifacts = {
        'facts_schema.json': facts_v3.SCHEMA, 'facts_example.json': facts_v3.EXAMPLE,
        'conditions_schema.json': sentence_workflow.CONDITION_SCHEMA,
        'conditions_example.json': sentence_workflow.CONDITION_EXAMPLE,
        'sentence_protocol.json': {
            'protocol': PROTOCOL, 'pipeline': PIPELINE, 'sentence_version': sentence_v3.SPLIT_VERSION,
            'discovery': {'prompt': 'discovery_v3.md', 'primary_cap': PRIMARY_CAP,
                          'max_paragraphs': MAX_PARAGRAPHS,
                          'response': 'paragraphs: [{paragraph_id, status, spans: [{sentence_ids}]}]',
                          'statuses': ['has_candidates', 'none_found', 'uncertain']},
            'stages': ['discovery', 'facts', 'conditions'],
            'conditions': 'Selective and optional; failure preserves core facts',
            'examples': 'Synthetic format examples; not project evidence or expert gold',
        },
    }
    # Resolve dependencies before creating anything; missing cooperating modules
    # must not leave a workspace that looks ready to run.
    for name in PROMPTS:
        if not (HERE / name).is_file():
            raise ValueError('Required sentence prompt missing: ' + name)
    m = {'pipeline': PIPELINE, 'protocol': PROTOCOL, 'version': 3,
         'candidate_context_version': 3, 'sentence_version': sentence_v3.SPLIT_VERSION,
         'transport': 'sse', 'phase': phase, 'created': time.time(), 'batch_size': 1,
         'primary_cap': PRIMARY_CAP, 'max_paragraphs': MAX_PARAGRAPHS,
         'papers': [], 'job_ids': [], 'file_hashes': {},
         'code_hashes': {name: sha(HERE / name) for name in code},
         'input_manifest_sha256': sha(manifest_path), 'expert_gold': False,
         'coverage': 'Indexed narrative body; explicit unscanned spans; no pixels or private references'}
    workspace.mkdir(parents=True)
    runtime = workspace / 'runtime'
    runtime.mkdir()
    for name in code:
        shutil.copyfile(HERE / name, runtime / name)
    for name in PROMPTS:
        shutil.copyfile(HERE / name, workspace / name)
        m['file_hashes'][name] = sha(workspace / name)
    for name, value in artifacts.items():
        save(workspace / name, value)
        m['file_hashes'][name] = sha(workspace / name)
    reference_path = manifest_path.parent / 'acceptance_reference.json'
    if phase == 'pilot' and reference_path.is_file():
        shutil.copyfile(reference_path, workspace / 'acceptance_reference.json')
        m['reference_sha256'] = sha(workspace / 'acceptance_reference.json')
        m['file_hashes']['acceptance_reference.json'] = m['reference_sha256']
    public_fields = ('paper_id', 'legacy_paper_id', 'doi', 'title', 'url', 'availability',
                     'publication_kind', 'source_kind', 'source_license', 'sources')
    for metadata in selected:
        row = {key: metadata[key] for key in public_fields if key in metadata}
        row.update(job_ids=[], status='input_gap', sentence_gaps=[])
        try:
            if not metadata.get('path'):
                raise ValueError('source_not_available')
            source = Path(metadata['path'])
            if not source.is_absolute():
                source = manifest_path.parent / source
            if phase == 'pilot' and source.suffix.lower() != '.xml':
                raise ValueError('fixed_sentence_pilot_requires_XML')
            doc = parse_document(source, row['paper_id'])
            row.update(source_path=doc['source_path'], source_sha256=doc['source_sha256'],
                       parsed_coverage=doc['coverage'], format=source.suffix.lower())
            if metadata.get('source_sha256') and metadata['source_sha256'] != doc['source_sha256']:
                raise ValueError('source_manifest_hash_mismatch')
            if doc['status'] not in {'readable', 'readable_partial'}:
                raise ValueError(doc['status'])
            if source.suffix.lower() in {'.html', '.htm', '.pdf'}:
                review = metadata.get('format_review', {})
                if (review.get('source_sha256') != doc['source_sha256'] or
                        review.get('parser_sha256') != sha(HERE / 'source_formats.py') or
                        review.get('body_order_checked') is not True or
                        review.get('body_boundaries_checked') is not True):
                    raise ValueError('format_requires_acceptance_before_automatic_enqueue')
                row['format_review'] = review
            planned = sentence_v3.build_sentence_jobs(doc, metadata, primary_cap=PRIMARY_CAP,
                                                       max_paragraphs=MAX_PARAGRAPHS)
            doc_name = f'documents/{row["paper_id"]}.json'
            index_name = f'sentence_indexes/{row["paper_id"]}.json'
            gaps_name = f'coverage_gaps/{row["paper_id"]}.json'
            for name, value in ((doc_name, doc), (index_name, planned['sentences']),
                                (gaps_name, planned['gaps'])):
                save(workspace / name, value)
                m['file_hashes'][name] = sha(workspace / name)
            row.update(document_path=str(workspace / doc_name),
                       document_sha256=m['file_hashes'][doc_name],
                       sentence_index_path=str(workspace / index_name),
                       sentence_index_sha256=m['file_hashes'][index_name],
                       sentence_count=len(planned['sentences']),
                       sentence_gaps=planned['gaps'], coverage_gaps_path=gaps_name)
            for job in planned['jobs']:
                if not re.fullmatch(r'[A-Za-z0-9_-]+', job['job_id']):
                    raise ValueError('Sentence job_id must be safe for Windows file names')
                job.update(document_path=row['document_path'], document_sha256=row['document_sha256'],
                           sentence_index_path=row['sentence_index_path'],
                           sentence_index_sha256=row['sentence_index_sha256'])
                name = f'jobs/{job["job_id"]}.json'
                save(workspace / name, job)
                m['file_hashes'][name] = sha(workspace / name)
                row['job_ids'].append(job['job_id'])
                m['job_ids'].append(job['job_id'])
            row['status'] = 'prepared' if row['job_ids'] else 'input_gap'
            if not row['job_ids']:
                row['input_error'] = 'no_scannable_body_sentences'
        except (OSError, ValueError, TypeError, KeyError) as error:
            row['input_error'] = (str(error) if isinstance(error, ValueError) else type(error).__name__)[:160]
        m['papers'].append(row)
    save(workspace / 'manifest.json', m)
    verify(workspace)
    return m


def _frozen_path(workspace, value):
    path = Path(value)
    path = (path if path.is_absolute() else workspace / path).resolve()
    try:
        name = path.relative_to(workspace.resolve()).as_posix()
    except ValueError:
        raise ValueError('Frozen path escapes workspace') from None
    return path, name


def verify(workspace):
    workspace = Path(workspace).resolve()
    m = read(workspace / 'manifest.json')
    if m.get('pipeline') != PIPELINE or m.get('protocol') != PROTOCOL:
        raise ValueError('This entry requires a sentence_v3 workspace')
    for name, digest in m['file_hashes'].items():
        path, _ = _frozen_path(workspace, name)
        if sha(path) != digest:
            raise ValueError('Frozen input changed: ' + name)
    for name, digest in m['code_hashes'].items():
        if Path(name).name != name or sha(HERE / name) != digest or sha(workspace / 'runtime' / name) != digest:
            raise ValueError('Runtime changed; use the matching frozen version: ' + name)
    listed_jobs = [jid for paper in m['papers'] for jid in paper['job_ids']]
    if listed_jobs != m['job_ids'] or len(set(listed_jobs)) != len(listed_jobs):
        raise ValueError('Sentence job inventory changed')
    for paper in m['papers']:
        if paper.get('source_sha256') and sha(paper['source_path']) != paper['source_sha256']:
            raise ValueError('Original source changed: ' + paper['paper_id'])
        for jid in paper['job_ids']:
            if not re.fullmatch(r'[A-Za-z0-9_-]+', jid):
                raise ValueError('Unsafe sentence job ID')
            job_name = f'jobs/{jid}.json'
            if job_name not in m['file_hashes']:
                raise ValueError('Job is not frozen: ' + jid)
            job = read(workspace / job_name)
            if (job['paper_id'] != paper['paper_id'] or job['source_sha256'] != paper['source_sha256']
                    or job['job_id'] != jid or job.get('protocol') != PROTOCOL):
                raise ValueError('Job source identity changed: ' + jid)
            for field in ('document', 'sentence_index'):
                _, name = _frozen_path(workspace, job[field + '_path'])
                if (name not in m['file_hashes'] or
                        job[field + '_sha256'] != m['file_hashes'][name] or
                        job[field + '_path'] != paper[field + '_path']):
                    raise ValueError('Job full-document/index binding changed: ' + jid)
    return m


def check(workspace, config, ledger_path):
    import batch_budget
    check_config(config)
    workspace = Path(workspace)
    m = verify(workspace)
    total = sum(reserve_tokens(sentence_workflow.request_for(workspace,
                read(workspace / f'jobs/{jid}.json'), 'discovery', config), config)
                for jid in m['job_ids'])
    return {'pipeline': PIPELINE, 'protocol': PROTOCOL, 'papers': len(m['papers']),
            'readable_papers': sum(bool(p['job_ids']) for p in m['papers']),
            'input_gap_papers': [p['paper_id'] for p in m['papers'] if not p['job_ids']],
            'unscanned_sentences': sum(len(p['sentence_gaps']) for p in m['papers']),
            'discovery_requests': len(m['job_ids']), 'discovery_token_reservation': total,
            'facts_requests': 'One per discovered candidate; unknown until discovery',
            'conditions_requests': 'Selective optional supplement; unknown until facts',
            'primary_cap': PRIMARY_CAP, 'max_paragraphs': MAX_PARAGRAPHS,
            'budget': batch_budget.status(ledger_path), 'generation_requests_sent': 0,
            'estimate_is_billing_amount': False}
