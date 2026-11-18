"""Frozen development cases and contracts; no network or credential access."""
from pathlib import Path

from contract import validate
from corpus import HERE, LEGACY, normal, parse_source, read, save, sha

ACTIVE = ('p0090', 'p0100', 'p0105', 'p0115')
EMPTY = ('p0050', 'p0070')
CONTEXT = ('p0040', 'p0045', 'p0055', 'p0060', 'p0080', 'p0085', 'tbl1', 'tbl2')
CATEGORIES = {'no_activity', 'no_degradation', 'conditional_loss',
              'relative_weakening', 'target_not_detected', 'uncertain'}
SOURCE_HASH = '1732d8026fa40417375c40f7ab6a58cca1756e46713bc784434d7710255c4873'


def prepare(out):
    out = Path(out)
    if out.exists():
        raise ValueError('Use a fresh experiment workspace; never overwrite existing attempts')
    source = LEGACY / 'sources/B022_PMC13487472.xml'
    if sha(source) != SOURCE_HASH:
        raise ValueError('Development source identity changed')
    doc = parse_source(source, 'B022')
    by_locator = {u['locator']: u for u in doc['units']}
    common = {'paper_id': 'B022', 'doi': '10.1182/blood.2025031127',
              'source_sha256': SOURCE_HASH}
    active = [by_locator[x] for x in ACTIVE]
    context = [by_locator[x] for x in CONTEXT]
    jobs = {
        'active': dict(common, job_id='two_stage_active', primary_units=active,
                       context_units=context),
        'empty': dict(common, job_id='two_stage_empty',
                      primary_units=[by_locator[x] for x in EMPTY],
                      context_units=context + active),
    }
    # Reference stays local and is NEVER included in request construction.
    reference = {
        'development_only': True, 'expert_gold': False,
        'checkpoints': [
            {'id': 'compound4', 'locator': 'p0105', 'compound': '4'},
            {'id': 'compound5', 'locator': 'p0105', 'compound': '5'},
            {'id': 'compound6', 'locator': 'p0105', 'compound': '6'},
            {'id': 'compound15', 'locator': 'p0115', 'compound': '15'},
            {'id': 'conditional_compound1', 'locator': 'p0090', 'compound': '1',
             'condition': 'lenalidomide'},
        ],
        'risk_control': 'p0100 reduced but measurable activity is not complete inactivity',
        'scoring': 'Assistant source audit, not automatic biological accuracy. Count named-object coverage separately from record and experiment counts.',
    }
    out.mkdir(parents=True)
    for name, job in jobs.items():
        save(out / f'{name}.json', job)
    save(out / 'reference.json', reference)
    for source_name, target in [('prompt.md', 'one_step.md'),
                                ('discovery.md', 'discovery.md'),
                                ('enrichment.md', 'enrichment.md')]:
        (out / target).write_bytes((HERE / source_name).read_bytes())
    names = ['active.json', 'empty.json', 'reference.json', 'one_step.md',
             'discovery.md', 'enrichment.md']
    manifest = {
        'version': 1, 'design': 'known-case single-paper development comparison',
        'source_path': str(source), 'source_sha256': SOURCE_HASH,
        'input_hashes': {n: sha(out / n) for n in names},
        'max_new_generation_requests': 6,
        'planned_calls': ['baseline_active', 'discovery_active', 'discovery_empty',
                          'enrich_active', 'baseline_empty'],
        'retry_policy': 'No automatic retries; at most one explicit HTTP429/500 retry. Unknown outcomes block all sending.',
        'comparison': 'Same model and active result paragraphs; two-stage discovery sees primary only, enrichment sees the same context as baseline. Empty-primary context intentionally contains negatives.',
        'limits': ['Known cases used for development, not blind evaluation or full-paper recall.',
                   'Two-stage uses more calls and tokens; no matched-compute causal claim.',
                   'No new-paper generalisation, expert gold, table novelty, RAG or training test.'],
    }
    save(out / 'manifest.json', manifest)
    return manifest


def check_frozen(out):
    out = Path(out)
    manifest = read(out / 'manifest.json')
    if sha(manifest['source_path']) != manifest['source_sha256']:
        raise ValueError('Source changed after freezing')
    for name, expected in manifest['input_hashes'].items():
        if sha(out / name) != expected:
            raise ValueError('Frozen experiment input changed: ' + name)
    return manifest


def validate_discovery(payload, job):
    if not isinstance(payload, dict) or set(payload) != {
            'paper_id', 'candidates', 'coverage_notes', 'no_candidate_reason'}:
        raise ValueError('Invalid discovery wrapper')
    if payload['paper_id'] != job['paper_id']:
        raise ValueError('Wrong discovery paper')
    candidates = payload['candidates']
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError('Invalid candidate list')
    if not isinstance(payload['coverage_notes'], list) or any(
            not isinstance(n, str) for n in payload['coverage_notes']):
        raise ValueError('Invalid discovery notes')
    if not candidates and not isinstance(payload['no_candidate_reason'], str):
        raise ValueError('Empty discovery needs a reason')
    units = {u['unit_id']: u for u in job['primary_units']}
    accepted, rejected, seen = [], [], set()
    for c in candidates:
        errors = []
        if not isinstance(c, dict) or set(c) != {
                'candidate_id', 'unit_id', 'quote', 'compound_mentions',
                'condition_mentions', 'category', 'notes'}:
            rejected.append({'candidate': c, 'errors': ['invalid_candidate_schema']})
            continue
        cid = c['candidate_id']
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError('Invalid or duplicate candidate_id')
        seen.add(cid)
        uid, quote = c['unit_id'], c['quote']
        if not isinstance(uid, str) or uid not in units:
            errors.append('result_not_in_primary')
        if not isinstance(quote, str) or len(normal(quote)) < 8 or len(quote) > 3000:
            errors.append('invalid_quote')
        elif uid in units and normal(quote) not in normal(units[uid]['text']):
            errors.append('quote_not_in_cited_unit')
        if c['category'] not in CATEGORIES:
            errors.append('invalid_category')
        for field in ['compound_mentions', 'condition_mentions', 'notes']:
            values = c[field]
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                errors.append('invalid_' + field)
            elif field != 'notes' and isinstance(quote, str):
                if any(normal(v) not in normal(quote) for v in values):
                    errors.append('mention_not_in_quote:' + field)
        (rejected if errors else accepted).append(
            {'candidate': c, 'errors': errors} if errors else c)
    return {'accepted': accepted, 'rejected': rejected,
            'coverage_notes': payload['coverage_notes'],
            'no_candidate_reason': payload['no_candidate_reason'],
            'semantic_review': 'pending', 'ready_for_training': False}


def validate_enrichment(payload, job, candidates):
    if not isinstance(payload, dict) or set(payload) != {
            'paper_id', 'items', 'unresolved', 'coverage_notes'}:
        raise ValueError('Invalid enrichment wrapper')
    if payload['paper_id'] != job['paper_id']:
        raise ValueError('Wrong enrichment paper')
    if not isinstance(payload['coverage_notes'], list) or any(
            not isinstance(n, str) for n in payload['coverage_notes']):
        raise ValueError('Invalid enrichment notes')
    if not isinstance(payload['items'], list) or not isinstance(payload['unresolved'], list):
        raise ValueError('Invalid enrichment arrays')
    expected = {c['candidate_id']: c for c in candidates}
    seen, accepted, rejected = set(), [], []
    for item in payload['items'] + payload['unresolved']:
        if not isinstance(item, dict):
            raise ValueError('Invalid enrichment item')
        cid = item.get('candidate_id')
        if not isinstance(cid, str) or cid not in expected or cid in seen:
            raise ValueError('Unknown, duplicate or unlinked candidate')
        seen.add(cid)
    if seen != set(expected):
        raise ValueError('Missing discovery candidates in enrichment accounting')
    for item in payload['unresolved']:
        if set(item) != {'candidate_id', 'reason'} or not isinstance(item['reason'], str) or not item['reason'].strip():
            raise ValueError('Invalid unresolved item')
    for item in payload['items']:
        if set(item) != {'candidate_id', 'record'}:
            raise ValueError('Invalid linked record')
        cid, record = item['candidate_id'], item['record']
        result = validate({'schema_version': 1, 'paper_id': job['paper_id'],
                           'records': [record], 'coverage_notes': [],
                           'no_negative_reason': None}, job)
        anchor = expected[cid]
        linked = isinstance(record, dict) and isinstance(record.get('evidence'), list) and any(
            isinstance(e, dict) and e.get('field') == 'result_text'
            and e.get('unit_id') == anchor['unit_id']
            and isinstance(e.get('quote'), str)
            and normal(e['quote']) == normal(anchor['quote'])
            for e in record['evidence'])
        if not linked:
            rejected.append(dict(item, errors=['missing_original_discovery_anchor']))
        elif result['rejected']:
            rejected.append(dict(item, errors=result['rejected'][0]['errors']))
        else:
            accepted.append({'candidate_id': cid, 'record': result['accepted'][0]})
    return {'accepted': accepted, 'rejected': rejected,
            'unresolved': payload['unresolved'], 'coverage_notes': payload['coverage_notes'],
            'semantic_review': 'pending', 'ready_for_training': False}
