"""Release gates bind completed pilot work and reviewed references to a runtime."""
from pathlib import Path
import time

from corpus import normal, read, save, sha
from runner import fingerprint
from candidate_workspace import PILOT_PAPERS, verify


def binding(workspace, config):
    m = verify(workspace)
    return {'code_hashes': m['code_hashes'],
            'prompt_hashes': {k: m['file_hashes'][k] for k in
                              ('discovery.md', 'enrichment.md', 'record_schema.txt')},
            'model_config': {k: v for k, v in config.items()
                             if k not in {'max_requests', 'max_reserved_tokens'}}}


def assess(workspace, review_path, out_path):
    from candidate_export import snapshot
    workspace = Path(workspace)
    m = verify(workspace)
    review = read(review_path)
    summary, records, audits, failures = snapshot(workspace)
    state_path = workspace / 'candidate_state.json'
    state = read(state_path) if state_path.exists() else {}
    reference_path = workspace / 'acceptance_reference.json'
    blockers = []
    if m.get('phase') != 'pilot':
        blockers.append('workspace_is_not_fixed_pilot')
    if {p['paper_id'] for p in m['papers']} != set(PILOT_PAPERS):
        blockers.append('five_fixed_papers_not_present')
    if not summary['all_sources_processed'] or failures:
        blockers.append('five_paper_end_to_end_processing_incomplete')
    if not reference_path.exists():
        blockers.append('pre_run_reference_missing')
    else:
        reference = read(reference_path)
        if review.get('reference_sha256') != sha(reference_path):
            blockers.append('review_reference_mismatch')
        if not reference.get('full_body_reference_complete'):
            blockers.append('reference_body_coverage_incomplete')
        by_paper = {p.get('paper_id'): p for p in reference.get('papers', [])}
        for paper in m['papers']:
            pid = paper['paper_id']
            doc_path = workspace/'documents'/f'{pid}.json'
            if not doc_path.is_file() or pid not in by_paper:
                blockers.append('reference_paper_missing:' + pid)
                continue
            doc = read(doc_path)
            body = {u['unit_id']: u for u in doc['units'] if u['kind'] == 'body_paragraph'}
            ref = by_paper[pid]
            rows = ref.get('units_reviewed', [])
            reviewed_ids = [row.get('unit_id') for row in rows]
            if (len(reviewed_ids) != len(set(reviewed_ids)) or set(reviewed_ids) != set(body)
                    or ref.get('source_sha256') != doc['source_sha256']
                    or any(row.get('decision') not in {'has_negative', 'no_eligible_negative', 'uncertain'}
                           for row in rows)):
                blockers.append('reference_units_incomplete_or_invalid:' + pid)
            if any(neg.get('unit_id') not in body or not normal(neg.get('quote', ''))
                   or normal(neg.get('quote', '')) not in normal(body[neg['unit_id']]['text'])
                   for neg in ref.get('negatives', [])):
                blockers.append('reference_quote_not_grounded:' + pid)
        if reference.get('expert_gold'):
            blockers.append('reference_requires_documented_expert_provenance')
        if not state.get('reference_sha256') or state['reference_sha256'] != sha(reference_path):
            blockers.append('reference_not_frozen_before_generation')
    result_hash = fingerprint({'records': records, 'audit': audits})
    if review.get('output_fingerprint') != result_hash:
        blockers.append('review_does_not_cover_current_outputs')
    reviewed_records = review.get('records', [])
    if ({row.get('record_key') for row in reviewed_records} != {r['record_key'] for r in records}
            or len(reviewed_records) != len(records)
            or any(row.get('decision') not in {'supported', 'quarantine', 'uncertain'}
                   for row in reviewed_records)):
        blockers.append('record_level_review_incomplete')
    if not isinstance(review.get('missed_references'), list):
        blockers.append('reference_recall_not_reviewed')
    if review.get('critical_errors_unresolved') != 0:
        blockers.append('critical_content_errors_unresolved_or_not_reviewed')
    if review.get('quote_location_pass') is not True:
        blockers.append('quote_locations_not_verified')
    if review.get('known_regressions_pass') is not True:
        blockers.append('known_error_cases_not_verified')
    if not review.get('engineering_checks_pass'):
        blockers.append('engineering_checks_not_verified')
    if not state.get('config'):
        blockers.append('pilot_model_configuration_missing')
    report = {'passed': not blockers, 'blockers': blockers, 'created': time.time(),
              'pilot_workspace': str(workspace.resolve()), 'pilot_manifest_sha256': sha(workspace/'manifest.json'),
              'output_fingerprint': result_hash, 'review_sha256': sha(review_path),
              'review_path': str(Path(review_path).resolve()),
              'binding': binding(workspace, state['config']) if state.get('config') else None,
              'reviewer_kind': review.get('reviewer_kind', 'assistant'), 'expert_gold': False,
              'summary': summary, 'precision': review.get('precision'), 'recall': review.get('recall')}
    save(out_path, report)
    return report


def require_acceptance(path, workspace, config):
    if not path or not Path(path).is_file():
        raise ValueError('Full extraction locked: fixed five-paper acceptance is missing')
    report = read(path)
    if not report.get('passed') or report.get('binding') != binding(workspace, config):
        raise ValueError('Full extraction locked: acceptance is incomplete or runtime/model changed')
    pilot = Path(report['pilot_workspace'])
    if sha(pilot/'manifest.json') != report['pilot_manifest_sha256']:
        raise ValueError('Full extraction locked: acceptance pilot inputs changed')
    if not report.get('review_path') or sha(report['review_path']) != report['review_sha256']:
        raise ValueError('Full extraction locked: acceptance review changed')
    from candidate_runtime import _check_state
    _check_state(pilot, read(pilot/'candidate_state.json'))
    from candidate_export import snapshot
    _, records, audit, _ = snapshot(pilot)
    if fingerprint({'records': records, 'audit': audit}) != report['output_fingerprint']:
        raise ValueError('Full extraction locked: reviewed pilot outputs changed')
    return report
