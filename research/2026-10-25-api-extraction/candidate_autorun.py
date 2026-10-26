"""Unattended pilot, source acquisition and gated full extraction. No budget reset."""
import argparse
import json
from pathlib import Path
import shutil
import time

from corpus import HERE, read, save, sha
from candidate_runtime import RunLock, run
from candidate_workspace import prepare, check
from candidate_export import export, snapshot
from candidate_acceptance import assess, require_acceptance
from runner import fingerprint


def autorun(settings_path, run_dir, diagnosis_path=None):
    folder = Path(run_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    s = read(settings_path)
    config = read(s['config'])
    state = {'started': time.time(), 'stage': 'starting', 'status': 'running',
             'run_dir': str(folder), 'errors': [], 'generation_budget_reset': False}

    def checkpoint(stage, **extra):
        state.update(stage=stage, updated=time.time(), **extra)
        save(folder/'state.json', state)
        save(HERE/'local/active_autorun.json', state)
        print(json.dumps({'stage': stage, 'status': state['status'], **extra}, ensure_ascii=False), flush=True)

    with RunLock(folder/'autorun.lock'):
        try:
            checkpoint('pilot_preparation')
            inventory_dir = Path(s['inventory'])
            if not (inventory_dir/'papers.json').exists():
                from molglue_sources import inventory
                inventory(s['database'], inventory_dir)
            pilot = Path(s['pilot_workspace'])
            if not pilot.exists():
                prepare(pilot, manifest_path=inventory_dir/'papers.json', phase='pilot')
            reference = pilot/'acceptance_reference.json'
            if not reference.exists():
                source_reference = HERE/'local/pilot_reference_draft.json'
                if not source_reference.is_file():
                    raise ValueError('Frozen pre-run reference is missing')
                shutil.copyfile(source_reference, reference)
            ledger = read(s['ledger'])
            remaining = max(0, ledger['max_requests']-len(ledger['attempts']))
            checkpoint('pilot_preflight', remaining_authorized_requests=remaining,
                       preflight=check(pilot, config, s['ledger']))
            if diagnosis_path and ledger.get('global_stop') == 'two_consecutive_network_failures':
                from candidate_recovery import resume_network_after_diagnosis
                try:
                    recovery = resume_network_after_diagnosis(s['ledger'], diagnosis_path, config)
                    save(folder/'network_recovery.json', recovery)
                except ValueError:
                    state['errors'].append({'stage': 'network_recovery',
                                            'error_type': 'diagnosis_not_eligible_stop_retained'})
            checkpoint('pilot_extraction')
            from batch_candidate import candidate_request_for, candidate_enrichment
            try:
                run(pilot, config, s['ledger'], candidate_request_for, candidate_enrichment,
                    live=True, env_file=s['env_file'], max_new_requests=remaining,
                    resume_operator_pause=True, phase='pilot', on_progress=export,
                    network_route='direct')
            except Exception as error:
                state['errors'].append({'stage': 'pilot_extraction', 'error_type': type(error).__name__})
            summary, records, audit, _ = snapshot(pilot)
            save(folder/'pilot_summary.json', summary)
            review_path = folder/'content_review.json'
            if not review_path.exists():
                save(review_path, {'reference_sha256': sha(reference),
                    'output_fingerprint': fingerprint({'records': records, 'audit': audit}),
                    'reviewer_kind': 'not_reviewed',
                    'records': [{'record_key': r['record_key'], 'decision': 'uncertain',
                                 'reason': 'Content review pending'} for r in records],
                    'missed_references': None, 'critical_errors_unresolved': None,
                    'quote_location_pass': None, 'known_regressions_pass': None,
                    'engineering_checks_pass': read(HERE/'candidate_engineering_validation.json').get('passed', False)})
            acceptance = assess(pilot, review_path, s['acceptance'])
            checkpoint('source_acquisition', pilot_records=summary['unique_records'],
                       acceptance_passed=acceptance['passed'])
            from molglue_sources import fetch_sources
            fetched = fetch_sources(inventory_dir)
            save(folder/'source_summary.json', fetched)
            checkpoint('full_preparation', available_sources=fetched['with_local_source'])
            workspace = Path(s['workspace'])
            if not workspace.exists():
                prepare(workspace, manifest_path=inventory_dir/'papers.json', phase='full')
            export(workspace)
            try:
                require_acceptance(s['acceptance'], workspace, config)
            except (OSError, ValueError) as error:
                checkpoint('awaiting_acceptance', status='blocked',
                           blockers=acceptance['blockers'], full_extraction_started=False)
            else:
                checkpoint('full_extraction', full_extraction_started=True)
                run(workspace, config, s['ledger'], candidate_request_for, candidate_enrichment,
                    live=True, env_file=s['env_file'], phase='full', resume_operator_pause=True,
                    on_progress=export, network_route='direct')
                checkpoint('finished', status='finished', full_summary=export(workspace))
        except BaseException as error:
            checkpoint('interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                       status='failed', error_type=type(error).__name__)
            raise
        finally:
            ledger = read(s['ledger'])
            state['shared_requests'] = len(ledger['attempts'])
            state['max_requests'] = ledger['max_requests']
            state['global_stop'] = ledger.get('global_stop')
            state['finished'] = time.time()
            save(folder/'state.json', state)
            save(HERE/'local/active_autorun.json', state)
            (folder/'运行汇总.md').write_text('\n'.join([
                '# 无人值守提取进度', '', f'阶段：{state["stage"]}；状态：{state["status"]}。', '',
                f'共享生成调用：{state["shared_requests"]}/{state["max_requests"]}。', '',
                f'全局停止原因：{state["global_stop"] or "无"}。', '',
                f'验收阻碍：{state.get("blockers", [])}。', '',
                '详细状态在 state.json；原文、请求、响应与未知任务保留在对应工作区。', '']), encoding='utf-8')
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--diagnosis', type=Path)
    args = parser.parse_args()
    autorun(args.settings, args.run_dir, args.diagnosis)
