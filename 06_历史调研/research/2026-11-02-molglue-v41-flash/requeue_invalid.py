"""Requeue saved contract failures after an offline contract repair.

This never requeues needs_attention/unknown attempts and preserves every old
artifact in the task's historical_failure list.
"""
import argparse
import json
from pathlib import Path


RESET_FIELDS = ('request_path', 'request_sha256', 'response_path', 'response_sha256',
                'result_path', 'result_sha256', 'accepted', 'rejected', 'unresolved',
                'usage', 'returned_model', 'exception_type', 'failure_kind', 'global_stop')


def requeue(workspace, include_logical_reservations=False):
    workspace = Path(workspace).resolve()
    state_path = workspace / 'candidate_state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    selected = []
    for task_id, entry in state.get('tasks', {}).items():
        is_invalid = entry.get('status') == 'invalid_response'
        is_logical_reservation = (
            include_logical_reservations
            and entry.get('status') == 'needs_attention'
            and entry.get('failure_kind') == 'logical_task_already_reserved'
        )
        if not (is_invalid or is_logical_reservation):
            continue
        historical = {key: entry.get(key) for key in (
            'status', 'failure_kind', 'attempt_id', 'historical_attempt_id',
            'request_path', 'request_sha256', 'response_path', 'response_sha256',
            'result_path', 'result_sha256') if entry.get(key) is not None}
        entry.setdefault('historical_failures', []).append(historical)
        entry['status'] = 'pending'
        entry['requeue_reason'] = (
            'offline_contract_repair; unknown attempts excluded'
            if is_invalid else
            'logical reservation repair; provider unknown attempts excluded'
        )
        for key in RESET_FIELDS:
            entry.pop(key, None)
        selected.append(task_id)
    if selected:
        state['retry_revision'] = int(state.get('retry_revision', 0)) + 1
        state['stop_reason'] = None
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'workspace': str(workspace), 'requeued_invalid_tasks': selected,
            'count': len(selected), 'unknown_tasks_requeued': 0,
            'retry_revision': state.get('retry_revision', 0)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--include-logical-reservations', action='store_true',
                        help='Requeue local logical_task_already_reserved entries only; never provider unknowns')
    args = parser.parse_args()
    print(json.dumps(requeue(args.workspace, args.include_logical_reservations),
                     ensure_ascii=False, indent=2))
