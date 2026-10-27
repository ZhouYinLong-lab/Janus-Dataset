"""Offline content gate for molgluedb_sentence_v3 (no transport or credentials).

Workspace contract: manifest.json has pipeline, phase, papers, code_hashes and
file_hashes, as in candidate_workspace. Freeze discovery_v3.md, facts_v3.md,
conditions_v3.md, documents/<paper_id>.json and every other prepared input.
Original XMLs and runtime/*.py must still match their manifest hashes. The
runtime must persist candidate_state.json.reference_sha256 BEFORE any generation;
this gate verifies that frozen value, and never creates or repairs it.

Review schema (all decisions are assistant assessments, not expert gold)::

    {
      "schema_version": 3, "pipeline": "molgluedb_sentence_v3",
      "reviewer_kind": "assistant", "expert_gold": false,
      "binding": binding(workspace, state["config"]),
      "reference_sha256": "<SHA256 of acceptance_reference.json>",
      "output_fingerprint": output_fingerprint(summary, records, audits, failures),
      "records": [
        {"record_key": "<actual output key>", "decision": "supported",
         "reason": "Checked the object, endpoint, observation and conditions",
         "severe_error": false}
      ],
      "references": [
        {"reference_id": "<core reference ID>", "decision": "recovered",
         "reason": "The complete claim and its scope are preserved",
         "record_keys": ["<supported actual output key>"]}
      ],
      "known_regressions_pass": true, "engineering_checks_pass": true
    }

Record decisions: supported/quarantine/uncertain. severe_error is REQUIRED and
must be an explicit JSON boolean on every record. Reference decisions:
recovered/missed/uncertain; every core reference needs one row, and missed and
uncertain rows have empty record_keys. Top-level precision/recall are ignored.
All records, including quarantine/uncertain, enter the precision denominator.
Only complete recovered references enter the recall numerator. Empty output is
never a pass. One record_key can recover at most one core reference: preserve
group-level references instead of duplicating a group into artificial cases.
This is a CONSERVATIVE gate: repeated mentions of one fact in different sentences
may share a real record, but that record is counted for only one reference here.
A reference describing multiple endpoints needs multiple actual record_keys;
the reviewer checks complete endpoint coverage in the reference row's reason.

The gate verifies actual keys, source hashes, exact sentence offsets and full
reference-quote coverage by the linked record's primary anchors, with an
observation citation overlapping that reference. This rejects invented IDs,
cross-paper/other-passage matches and repeated-key recall inflation. Semantic
support and full recovery still require the row-level reviewer judgement; text
overlap alone does not establish biological equivalence.

sentence_export.snapshot(workspace) is imported lazily and must return
(summary, records, audits, failures). summary requires all_sources_processed and
five paper rows with paper_id, jobs, jobs_processed and processed* status.
Missing v3 modules, state, reference, outputs or review produce blocked reports.
require_acceptance re-evaluates the pilot read-only and compares the full report,
then checks runtime/prompt/config binding against the requested workspace.

CLI: binding --workspace W --config C; assess --workspace W --review R --out O;
require --acceptance O --workspace W --config C. Exit 0 = success, 2 = blocked.
No CLI command sends a request, reads an environment/key file or changes budget.
"""

from collections import Counter
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

PIPELINE = 'molgluedb_sentence_v3'
HERE = Path(__file__).resolve().parent
PILOT_PAPERS = {
    'B296': '10.1038/s41586-020-2374-x',
    'MG_5cf5ae284fe057161ed1f3e2': '10.1002/advs.202104344',
    'MG_51cc8beb041f311c9f9c6a7c': '10.1002/advs.202412985',
    'MG_7483136d16dced0733a36f6e': '10.1002/advs.202413676',
    'MG_1601b48e6bb99dc76c546cfc': '10.1002/ctm2.881',
}
PROMPTS = ('discovery_v3.md', 'facts_v3.md', 'conditions_v3.md')
REQUIRED_RUNTIME = {'sentence_acceptance.py', 'sentence_v3.py', 'facts_v3.py',
                    'sentence_workflow.py', 'sentence_export.py', 'sentence_workspace.py',
                    'candidate_runtime.py', 'batch_candidate.py'}
PROTOCOL_FILES = set(PROMPTS) | {'discovery_schema.json', 'discovery_example.json',
    'facts_schema.json', 'facts_example.json', 'conditions_schema.json',
    'conditions_example.json', 'sentence_protocol.json'}
THRESHOLDS = {'support_rate': .9, 'complete_recall': .8, 'minimum_core_references': 20,
              'maximum_severe_errors': 0}
FIELDS = ('subject', 'target', 'endpoint', 'observation', 'comparator', 'scope_condition')
CONDITION_FIELDS = {'cell_line', 'treatment_time', 'tested_concentration', 'assay',
                    'perturbation', 'endpoint_resolution'}
OUTCOMES = {'not_observed', 'not_significant', 'reduced', 'not_improved',
            'conditional_loss', 'reported_zero', 'uncertain'}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'duplicate_json_key:' + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('nonfinite_json_number:' + value)

    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=invalid_constant)


def _inside(workspace, name):
    _need(_text(name) and not Path(name).is_absolute(), 'invalid_workspace_path')
    path = (workspace / name).resolve()
    _need(path != workspace and workspace in path.parents, 'path_outside_workspace:' + name)
    return path


def _unique(rows, key, label):
    _need(isinstance(rows, list), label + '_must_be_array')
    result = {}
    for row in rows:
        _need(isinstance(row, dict) and _text(row.get(key)), label + '_invalid_row')
        value = row[key]
        _need(value not in result, label + '_duplicate:' + value)
        result[value] = row
    return result


def _verify(workspace):
    """Independently verify v3 inputs, without importing a sending runtime."""
    w = Path(workspace).resolve()
    m = _read(w / 'manifest.json')
    _need(isinstance(m, dict) and m.get('pipeline') == PIPELINE, 'not_sentence_v3_workspace')
    files, code = m.get('file_hashes'), m.get('code_hashes')
    _need(isinstance(files, dict) and files, 'frozen_inputs_missing')
    _need(isinstance(code, dict) and REQUIRED_RUNTIME <= code.keys(), 'runtime_hashes_incomplete')
    pending, dependencies = list(REQUIRED_RUNTIME), set()
    while pending:
        name = pending.pop()
        if name in dependencies:
            continue
        dependencies.add(name)
        tree = ast.parse((HERE / name).read_text(encoding='utf-8-sig'), filename=name)
        for node in ast.walk(tree):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                dependency = module.split('.')[0] + '.py'
                if (HERE / dependency).is_file() and dependency not in dependencies:
                    pending.append(dependency)
    _need(dependencies <= code.keys(), 'transitive_runtime_hashes_incomplete')
    _need(set(PROMPTS) <= files.keys(), 'prompt_hashes_incomplete')
    runtime = w / 'runtime'
    actual_code = {p.relative_to(runtime).as_posix() for p in runtime.rglob('*.py')}
    _need(actual_code == set(code), 'runtime_inventory_mismatch')
    for name, digest in code.items():
        path = _inside(runtime.resolve(), name)
        original = _inside(HERE.resolve(), name)
        _need(_hash(path) == digest == _hash(original), 'runtime_changed:' + name)
    for name, digest in files.items():
        _need(_hash(_inside(w, name)) == digest, 'frozen_input_changed:' + name)
    papers = _unique(m.get('papers'), 'paper_id', 'manifest_papers')
    for pid, p in papers.items():
        _need('/' not in pid and '\\' not in pid and pid not in {'.', '..'}, 'invalid_paper_id')
        name = 'documents/' + pid + '.json'
        if m.get('phase') != 'pilot' and not p.get('source_sha256'):
            continue  # Full inventories may include unavailable sources.
        _need(name in files, 'document_not_frozen:' + pid)
        source = p.get('source_path', p.get('path'))
        _need(_text(source), 'original_source_missing:' + pid)
        if m.get('phase') == 'pilot':
            _need(Path(source).suffix.lower() == '.xml', 'xml_source_missing:' + pid)
        _need(_hash(source) == p.get('source_sha256'), 'original_source_changed:' + pid)
        doc = _read(_inside(w, name))
        _need(doc.get('paper_id') == pid and doc.get('source_sha256') == p['source_sha256'],
              'document_source_mismatch:' + pid)
        _need(Path(doc.get('source_path', '')).resolve() == Path(source).resolve(),
              'document_source_path_mismatch:' + pid)
        _unique(doc.get('units'), 'unit_id', 'document_units:' + pid)
    _need(papers, 'manifest_has_no_papers')
    return m


def binding(workspace, config):
    """Return verified runtime/prompt/config identity, including this gate's code.

    Budget caps are included in config. A changed cap/config needs new acceptance.
    Input and output bindings belong to the assessed pilot, not the full corpus.
    """
    _need(isinstance(config, dict) and config, 'model_configuration_missing')
    m = _verify(workspace)
    # Round-trip to avoid exposing mutable references to caller-owned config.
    result = {'pipeline': PIPELINE, 'code_hashes': m['code_hashes'],
              'prompt_hashes': {name: m['file_hashes'][name] for name in PROMPTS},
              'protocol_hashes': {name: digest for name, digest in m['file_hashes'].items()
                                  if name in PROTOCOL_FILES},
              'execution_contract': {k: m.get(k) for k in ('protocol', 'version', 'transport',
                  'sentence_version', 'batch_size', 'primary_cap', 'max_paragraphs')},
              'model_config': config}
    return json.loads(json.dumps(result, allow_nan=False))


def output_fingerprint(summary, records, audits, failures):
    """Bind outputs and coverage, excluding the independently changing ledger.

    shared_budget is diagnostic, not a pilot output: full extraction can consume
    the same ledger after acceptance without changing the reviewed pilot.
    """
    stable_summary = {k: v for k, v in summary.items() if k != 'shared_budget'}
    return _fingerprint({'summary': stable_summary, 'records': records, 'audits': audits,
                         'failures': failures})


def _snapshot(workspace):
    from sentence_export import snapshot
    return snapshot(workspace)


def _reference(reference, manifest, workspace, index):
    _need(isinstance(reference, dict) and reference.get('expert_gold') is False
          and reference.get('reviewer_kind') == 'assistant', 'reference_provenance_invalid')
    _need(reference.get('full_body_reference_complete') is True, 'reference_body_coverage_incomplete')
    by_paper = _unique(reference.get('papers'), 'paper_id', 'reference_papers')
    _need(set(by_paper) == set(PILOT_PAPERS), 'reference_five_fixed_papers_missing')
    _need(isinstance(index, dict) and index.get('protocol') == 'sentence_v3'
          and index.get('reviewer_kind') == 'assistant' and index.get('expert_gold') is False,
          'public_reference_index_invalid')
    _need(index.get('reference_sha256') == _hash(workspace / 'acceptance_reference.json'),
          'public_reference_hash_mismatch')
    public = _unique(index.get('papers'), 'paper_id', 'public_reference_papers')
    _need(set(public) == set(PILOT_PAPERS), 'public_reference_five_papers_missing')
    docs, core, signatures, all_ids = {}, {}, set(), set()
    for p in manifest['papers']:
        pid = p['paper_id']
        doc = _read(workspace / 'documents' / (pid + '.json'))
        docs[pid] = doc
        units = _unique(doc['units'], 'unit_id', 'document_units')
        body = {uid: u for uid, u in units.items() if u.get('kind') == 'body_paragraph'}
        _need(body, 'reference_body_empty:' + pid)
        ref = by_paper[pid]
        idx = public[pid]
        _need(idx.get('doi') == PILOT_PAPERS[pid]
              and idx.get('source_sha256') == doc['source_sha256']
              and idx.get('document_sha256') == _hash(workspace / 'documents' / (pid + '.json')),
              'public_document_binding_mismatch:' + pid)
        _need(ref.get('source_sha256') == doc['source_sha256'], 'reference_source_mismatch:' + pid)
        reviewed = _unique(ref.get('units_reviewed'), 'unit_id', 'reference_units')
        _need(set(reviewed) == set(body), 'reference_units_incomplete:' + pid)
        for row in reviewed.values():
            _need(row.get('decision') in ('has_negative', 'no_eligible_negative', 'uncertain')
                  and _text(row.get('reason')), 'reference_unit_decision_invalid:' + pid)
        negatives = _unique(ref.get('negatives'), 'id', 'reference_negatives')
        expected = _unique(idx.get('references'), 'id', 'public_reference_ids')
        _need({rid: (n.get('unit_id'), n.get('core_case')) for rid, n in negatives.items()}
              == {rid: (n.get('unit_id'), n.get('core_case')) for rid, n in expected.items()},
              'public_reference_ids_mismatch:' + pid)
        _need(idx.get('body_units_reviewed') == len(body)
              and idx.get('negative_reference_count') == len(negatives)
              and idx.get('core_reference_count') == sum(n.get('core_case') is True for n in negatives.values()),
              'public_reference_counts_mismatch:' + pid)
        for rid, neg in negatives.items():
            uid, quote = neg.get('unit_id'), neg.get('quote')
            _need(rid not in all_ids, 'reference_id_duplicate:' + rid)
            all_ids.add(rid)
            _need(isinstance(uid, str) and uid in body and _text(quote)
                  and quote in body[uid]['text'], 'reference_quote_not_grounded:' + rid)
            _need(type(neg.get('core_case')) is bool, 'reference_core_flag_invalid:' + rid)
            _need(reviewed[uid]['decision'] == 'has_negative', 'reference_unit_conflict:' + rid)
            signature = _fingerprint([pid, uid, quote, [neg.get(f) for f in FIELDS], neg.get('outcome_type')])
            _need(signature not in signatures, 'duplicate_reference_claim:' + rid)
            signatures.add(signature)
            if neg['core_case']:
                core[rid] = dict(neg, paper_id=pid)
    _need(index.get('core_reference_count') == len(core)
          and index.get('body_units_reviewed') == sum(len(p['units_reviewed']) for p in by_paper.values()),
          'public_reference_total_mismatch')
    return docs, core


def _sentence_registry(doc):
    from sentence_v3 import index_document
    # Contextual captions/tables use the same indexer with the kind restored.
    registry = {}
    for unit in doc['units']:
        surrogate = dict(doc, units=[dict(unit, kind='body_paragraph')])
        for sentence in index_document(surrogate):
            registry[sentence['sentence_id']] = dict(sentence, kind=unit['kind'])
    return registry


def _citation(row, registry, allowed_fields):
    _need(isinstance(row, dict), 'citation_not_object')
    sid = row.get('sentence_id')
    _need(isinstance(sid, str) and sid in registry, 'citation_sentence_unknown')
    source = registry[sid]
    _need(row.get('field') in allowed_fields, 'citation_field_invalid')
    quote = row.get('quote', row.get('text'))
    _need(_text(quote) and quote == source['text'], 'citation_text_changed')
    if 'text' in row and 'quote' in row:
        _need(row['text'] == row['quote'], 'citation_text_conflict')
    _need(row.get('unit_id') == source['unit_id'], 'citation_unit_changed')
    _need(type(row.get('char_start')) is int and type(row.get('char_end')) is int
          and row['char_start'] == source['char_start']
          and row['char_end'] == source['char_end'], 'citation_offsets_changed')
    return source


def _ground_record(record, docs):
    pid = record.get('paper_id')
    _need(isinstance(pid, str) and pid in docs, 'record_paper_unknown')
    doc = docs[pid]
    _need(record.get('source_sha256') == doc['source_sha256'], 'record_source_mismatch')
    _need(record.get('doi') == PILOT_PAPERS[pid], 'record_doi_mismatch')
    registry = _sentence_registry(doc)
    values = record.get('values')
    _need(isinstance(values, dict) and set(values) == set(FIELDS), 'record_values_invalid')
    _need(all(v is None or _text(v) for v in values.values()), 'record_value_type_invalid')
    _need(record.get('outcome_type') in OUTCOMES, 'record_outcome_invalid')
    _need(_text(record.get('candidate_id')), 'record_candidate_missing')
    original = record.get('core_original', record)
    _need(isinstance(original, dict), 'record_original_invalid')
    if original is not record:
        _need(all(original.get(k) == record.get(k) for k in
                  ('record_key', 'paper_id', 'source_sha256', 'candidate_id', 'outcome_type',
                   'anchor_sentence_ids', 'original_quote')), 'record_original_identity_changed')
        _need(isinstance(original.get('values'), dict)
              and all(original['values'].get(k) == values[k] for k in FIELDS if k != 'endpoint'),
              'record_core_fields_changed')
        revision = record.get('context_revision')
        _need(isinstance(revision, dict) and isinstance(revision.get('values'), dict),
              'record_revision_missing')
        new_endpoint = revision['values'].get('endpoint_resolution')
        if values['endpoint'] != original['values'].get('endpoint'):
            _need(_text(new_endpoint) and new_endpoint == values['endpoint'], 'endpoint_revision_unbound')
        _need(revision.get('evidence') == record.get('condition_evidence'), 'revision_evidence_unbound')
    identity = {k: original.get(k) for k in
                ('source_sha256', 'paper_id', 'candidate_id', 'values', 'outcome_type')}
    _need(record.get('record_key') == _fingerprint(identity), 'record_key_not_content_bound')
    evidence = record.get('field_evidence')
    conditions = record.get('condition_evidence', [])
    _need(isinstance(evidence, list) and evidence and isinstance(conditions, list), 'record_evidence_missing')
    for row in evidence:
        _citation(row, registry, set(FIELDS))
    for row in conditions:
        _citation(row, registry, CONDITION_FIELDS)
    for field, value in values.items():
        candidates = [r for r in evidence if r['field'] == field]
        if field == 'endpoint':
            candidates += [r for r in conditions if r['field'] == 'endpoint_resolution']
        _need(value is None or candidates, 'field_evidence_missing:' + field)
    anchors = record.get('anchor_sentence_ids')
    _need(isinstance(anchors, list) and anchors
          and all(isinstance(s, str) and s in registry for s in anchors)
          and len(anchors) == len(set(anchors)), 'record_anchors_invalid')
    primary = [registry[s] for s in anchors]
    _need(all(s['kind'] == 'body_paragraph' for s in primary), 'record_anchor_not_body')
    order = {sid: i for i, sid in enumerate(registry)}
    _need([order[s] for s in anchors] == sorted(order[s] for s in anchors), 'record_anchors_reversed')
    _need(record.get('original_quote') == '\n'.join(s['text'] for s in primary), 'original_quote_changed')
    observations = [registry[r['sentence_id']] for r in evidence if r['field'] == 'observation']
    _need(any(r['sentence_id'] in anchors for r in evidence if r['field'] == 'observation'),
          'observation_not_anchored')
    return primary, observations


def _covers(neg, record, location, doc):
    if neg['paper_id'] != record['paper_id']:
        return False
    primary, observations = location
    unit = next(u for u in doc['units'] if u['unit_id'] == neg['unit_id'])
    quote, start = neg['quote'], 0
    while True:
        start = unit['text'].find(quote, start)
        if start < 0:
            return False
        stop, cursor = start + len(quote), start
        for s in primary:
            if s['unit_id'] != neg['unit_id']:
                continue
            # Unindexed whitespace is allowed; source words cannot be skipped.
            if s['char_start'] > cursor and unit['text'][cursor:min(s['char_start'], stop)].strip():
                break
            if s['char_start'] <= cursor or not unit['text'][cursor:s['char_start']].strip():
                cursor = max(cursor, s['char_end'])
        overlap = any(s['unit_id'] == neg['unit_id'] and s['char_start'] < stop
                      and s['char_end'] > start for s in observations)
        if cursor >= stop and overlap:
            return True
        start += 1


def _evaluate(workspace, review_path):
    w, review_path = Path(workspace).resolve(), Path(review_path).resolve()
    blockers = []
    report = {'schema_version': 3, 'pipeline': PIPELINE, 'passed': False, 'blockers': blockers,
              'pilot_workspace': str(w), 'review_path': str(review_path), 'reviewer_kind': 'assistant',
              'expert_gold': False, 'thresholds': dict(THRESHOLDS), 'binding': None,
              'metrics': {'records': 0, 'supported': 0, 'support_rate': None,
                          'core_references': 0, 'recovered': 0, 'complete_recall': None,
                          'severe_errors': 0}, 'summary': None}

    def attempt(label, action):
        try:
            return action()
        except (OSError, ValueError, TypeError, KeyError, ImportError, AttributeError, SyntaxError) as error:
            blockers.append(label + ':' + str(error))
            return None

    m = attempt('workspace_invalid', lambda: _verify(w))
    state = attempt('state_unavailable', lambda: _read(w / 'candidate_state.json'))
    review = attempt('review_unavailable', lambda: _read(review_path))
    reference = attempt('reference_unavailable', lambda: _read(w / 'acceptance_reference.json'))
    index_path = HERE / 'sentence_v3_reference_index.json'
    index = attempt('reference_index_unavailable', lambda: _read(index_path))
    for name, path in [('pilot_manifest_sha256', w / 'manifest.json'),
                       ('state_sha256', w / 'candidate_state.json'),
                       ('reference_sha256', w / 'acceptance_reference.json'),
                       ('reference_index_sha256', index_path),
                       ('review_sha256', review_path)]:
        report[name] = attempt(name, lambda path=path: _hash(path))
    state = state if isinstance(state, dict) else {}
    review = review if isinstance(review, dict) else {}
    if m is not None:
        if m.get('phase') != 'pilot':
            blockers.append('workspace_is_not_fixed_pilot')
        papers = {p['paper_id']: p.get('doi') for p in m['papers']}
        if papers != PILOT_PAPERS:
            blockers.append('five_fixed_papers_not_present')
        report['input_fingerprint'] = _fingerprint({'manifest': report['pilot_manifest_sha256'],
                                                   'files': m['file_hashes'],
                                                   'sources': {p['paper_id']: p['source_sha256'] for p in m['papers']}})
        report['binding'] = attempt('binding_invalid', lambda: binding(w, state.get('config')))
    if state.get('pipeline') != PIPELINE:
        blockers.append('state_pipeline_invalid')
    if (not report['reference_sha256'] or state.get('reference_sha256') != report['reference_sha256']):
        blockers.append('reference_not_frozen_before_generation')
    if review.get('schema_version') != 3 or review.get('pipeline') != PIPELINE:
        blockers.append('review_schema_invalid')
    if review.get('reviewer_kind') != 'assistant' or review.get('expert_gold') is not False:
        blockers.append('review_provenance_invalid')
    if not report['binding'] or review.get('binding') != report['binding']:
        blockers.append('review_runtime_binding_mismatch')
    if not report['reference_sha256'] or review.get('reference_sha256') != report['reference_sha256']:
        blockers.append('review_reference_mismatch')
    for field in ('known_regressions_pass', 'engineering_checks_pass'):
        if review.get(field) is not True:
            blockers.append(field + '_not_verified')
    if 'critical_errors_unresolved' in review:
        if type(review['critical_errors_unresolved']) is not int or review['critical_errors_unresolved'] != 0:
            blockers.append('critical_errors_unresolved_or_invalid')
    checked_reference = None
    if m is not None and reference is not None and {p['paper_id'] for p in m['papers']} == set(PILOT_PAPERS):
        checked_reference = attempt('reference_invalid', lambda: _reference(reference, m, w, index))
    docs, core = checked_reference if checked_reference is not None else ({}, {})
    metrics = report['metrics']
    metrics['core_references'] = len(core)
    if len(core) < THRESHOLDS['minimum_core_references']:
        blockers.append('fewer_than_20_core_references')
    snapshot = attempt('snapshot_unavailable', lambda: _snapshot(w))
    if not isinstance(snapshot, tuple) or len(snapshot) != 4:
        blockers.append('snapshot_contract_invalid')
        snapshot = ({}, [], [], [])
    summary, records, audits, failures = snapshot
    if not isinstance(summary, dict) or not all(isinstance(x, list) for x in (records, audits, failures)):
        blockers.append('snapshot_types_invalid')
        summary, records, audits, failures = {}, [], [], []
    report['summary'] = summary
    report['output_fingerprint'] = attempt('output_invalid', lambda: output_fingerprint(summary, records, audits, failures))
    if review.get('output_fingerprint') != report['output_fingerprint'] or not report['output_fingerprint']:
        blockers.append('review_does_not_cover_current_outputs')
    if summary.get('all_sources_processed') is not True or failures:
        blockers.append('five_paper_end_to_end_processing_incomplete')
    if summary.get('pipeline') != PIPELINE:
        blockers.append('snapshot_pipeline_invalid')
    if summary.get('unscanned_sentences', 0) != 0 or summary.get('unresolved_paragraphs', 0) != 0:
        blockers.append('sentence_or_paragraph_coverage_gaps')

    def coverage():
        rows = _unique(summary.get('papers'), 'paper_id', 'summary_papers')
        _need(set(rows) == set(PILOT_PAPERS), 'summary_five_fixed_papers_missing')
        for row in rows.values():
            _need(type(row.get('jobs')) is int and row['jobs'] > 0
                  and type(row.get('jobs_processed')) is int
                  and row['jobs_processed'] == row['jobs']
                  and isinstance(row.get('status'), str) and row['status'].startswith('processed'),
                  'paper_processing_incomplete:' + row['paper_id'])
            _need(row.get('unscanned_sentences', 0) == 0, 'paper_unscanned_sentences:' + row['paper_id'])
    attempt('source_coverage_invalid', coverage)
    actual = attempt('records_invalid', lambda: _unique(records, 'record_key', 'output_records')) or {}
    rows = attempt('record_review_invalid', lambda: _unique(review.get('records'), 'record_key', 'review_records')) or {}
    metrics['records'] = len(records)
    if set(actual) != set(rows) or len(rows) != len(records):
        blockers.append('record_level_review_incomplete')
    locations, supported = {}, set()
    for key, record in actual.items():
        location = attempt('quote_not_grounded:' + key, lambda record=record: _ground_record(record, docs))
        if location is not None:
            locations[key] = location
    for key, row in rows.items():
        decision = row.get('decision')
        severe = row.get('severe_error')
        if type(severe) is not bool:
            blockers.append('severe_error_flag_invalid:' + key)
        elif severe:
            metrics['severe_errors'] += 1
        if decision not in ('supported', 'quarantine', 'uncertain') or not _text(row.get('reason')):
            blockers.append('record_decision_invalid:' + key)
            continue
        if decision == 'supported' and key in actual and key in locations and severe is False:
            record = actual[key]
            if (all(_text(record['values'].get(f)) for f in ('subject', 'endpoint', 'observation'))
                    and record['outcome_type'] != 'uncertain'
                    and record.get('record_status') != 'quarantine'):
                supported.add(key)
            else:
                blockers.append('supported_record_unresolved:' + key)
    if metrics['severe_errors']:
        blockers.append('severe_content_errors_present')
    metrics['supported'] = len(supported)
    if records:
        metrics['support_rate'] = len(supported) / len(records)
    if not records or len(supported) * 10 < len(records) * 9:
        blockers.append('support_rate_below_0.9_or_empty_output')
    reviewed_refs = attempt('reference_review_invalid', lambda: _unique(
        review.get('references'), 'reference_id', 'review_references')) or {}
    if set(reviewed_refs) != set(core):
        blockers.append('core_reference_review_incomplete')
    counts = Counter(key for row in reviewed_refs.values()
                     if isinstance(row.get('record_keys'), list)
                     for key in row['record_keys'] if isinstance(key, str))
    for rid, row in reviewed_refs.items():
        decision, keys = row.get('decision'), row.get('record_keys')
        if (decision not in ('recovered', 'missed', 'uncertain') or not _text(row.get('reason'))
                or not isinstance(keys, list) or not all(_text(k) for k in keys)
                or len(keys) != len(set(keys))):
            blockers.append('reference_decision_invalid:' + rid)
            continue
        if decision != 'recovered':
            if keys:
                blockers.append('unrecovered_reference_has_record_keys:' + rid)
            continue
        if not keys or rid not in core:
            blockers.append('recovered_reference_has_no_actual_match:' + rid)
            continue
        valid = True
        for key in keys:
            if (key not in supported or counts[key] != 1
                    or not _covers(core[rid], actual[key], locations[key], docs[core[rid]['paper_id']])):
                blockers.append('reference_record_match_invalid:' + rid + ':' + key)
                valid = False
        if valid:
            metrics['recovered'] += 1
    if core:
        metrics['complete_recall'] = metrics['recovered'] / len(core)
    if not core or metrics['recovered'] * 5 < len(core) * 4:
        blockers.append('complete_recall_below_0.8_or_no_core_references')
    report['passed'] = not blockers
    if report['passed']:
        report['summary'] = {k: v for k, v in summary.items() if k != 'shared_budget'}
    return report


def assess(workspace, review_path, out_path):
    """Write a passed/blocked report; missing material is a blocker, not a pass."""
    w, target = Path(workspace).resolve(), Path(out_path).resolve()
    review_path = Path(review_path).resolve()
    # Assessment must not overwrite any evidence it is assessing.
    protected = {review_path, w / 'manifest.json', w / 'candidate_state.json', w / 'acceptance_reference.json'}
    protected.add((HERE / 'sentence_v3_reference_index.json').resolve())
    manifest_path = w / 'manifest.json'
    if manifest_path.exists():
        try:
            m = _read(manifest_path)
        except (OSError, ValueError):
            m = {}  # _evaluate reports the malformed manifest as a blocker.
        if isinstance(m, dict):
            protected.update((w / n).resolve() for n in m.get('file_hashes', {}))
            protected.update((w / 'runtime' / n).resolve() for n in m.get('code_hashes', {}))
            protected.update((HERE / n).resolve() for n in m.get('code_hashes', {}))
            protected.update(Path(p.get('source_path', p.get('path', ''))).resolve() for p in m.get('papers', []))
    _need(target not in protected, 'assessment_output_would_overwrite_inputs')
    if target.is_relative_to(w):
        _need(not any(part in {'documents', 'runtime', 'jobs', 'requests', 'responses', 'results',
                               'groups', 'condition_groups', 'sentence_indexes', 'coverage_gaps'}
                      for part in target.relative_to(w).parts[:-1]), 'assessment_output_would_overwrite_inputs')
    report = _evaluate(w, review_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report


def require_acceptance(path, workspace, config):
    """Recompute the complete pilot assessment and bind the requested runtime."""
    try:
        _need(path and Path(path).is_file(), 'acceptance_missing')
        report = _read(path)
        _need(isinstance(report, dict) and report.get('passed') is True, 'acceptance_not_passed')
        current = _evaluate(report['pilot_workspace'], report['review_path'])
        _need(current['passed'] is True and current == report, 'acceptance_changed_or_no_longer_valid')
        _need(report['binding'] == binding(workspace, config), 'runtime_prompt_or_config_changed')
        return report
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        raise ValueError('Full extraction locked: ' + str(error)) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('binding', 'assess', 'require'):
        sub = commands.add_parser(command)
        sub.add_argument('--workspace', required=True, type=Path)
        if command == 'assess':
            sub.add_argument('--review', required=True, type=Path)
            sub.add_argument('--out', required=True, type=Path)
        else:
            sub.add_argument('--config', required=True, type=Path)
        if command == 'require':
            sub.add_argument('--acceptance', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'assess':
            result = assess(args.workspace, args.review, args.out)
        elif args.command == 'binding':
            result = binding(args.workspace, _read(args.config))
        else:
            result = require_acceptance(args.acceptance, args.workspace, _read(args.config))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('passed') is False else 0
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        print(json.dumps({'passed': False, 'blockers': [str(error)]}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
