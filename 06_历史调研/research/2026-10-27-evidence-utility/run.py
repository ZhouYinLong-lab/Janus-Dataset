"""Budgeted, resumable API execution of frozen RAG/benchmark tasks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

from common import CORE, digest, finite, read, sha, verify, write
sys.path.insert(0, str(CORE))
from api import check_config, parse_completion, RequestFailure, reserve_tokens
import batch_budget as budget
from credentials import load_key
from runner import lock
from stream_http import StreamingClient


def request_for(task, cfg):
    request = {'model': cfg['model'], 'messages': task['messages'], 'temperature': 0,
               'stream': True, 'stream_options': {'include_usage': True},
               cfg['output_token_parameter']: cfg['max_output_tokens']}
    for name in ('thinking',):
        if name in cfg:
            request[name] = cfg[name]
    if cfg['response_format'] == 'json_object':
        request['response_format'] = {'type': 'json_object'}
    return request


def validate(envelope, task, allowed_models):
    if envelope.get('model') not in allowed_models:
        raise ValueError('Unexpected returned model')
    result = parse_completion(envelope)
    if not isinstance(result, dict):
        raise ValueError('Answer must be an object')
    expected = {'answer', 'citations', 'uncertainty'} if task['schema'] == 'qa' else {'score', 'citations', 'uncertainty'}
    if (set(result) != expected or not isinstance(result['uncertainty'], str) or
            not isinstance(result['citations'], list) or any(not isinstance(x, str) or
            x not in task['evidence_ids'] for x in result['citations'])):
        raise ValueError('Answer schema/citation contract failed')
    if task['schema'] == 'qa':
        if not isinstance(result['answer'], str) or not result['answer'].strip():
            raise ValueError('Empty answer')
    elif not finite(result['score']) or not 0 <= result['score'] <= 1:
        raise ValueError('Score must be a finite number in [0,1]')
    return result


def find_reusable(ledger, request, cfg, task, allowed_models):
    """Reuse exact successful requests across arms/workspaces, verifying the saved receipt."""
    parsed = urlsplit(cfg['base_url'])
    provider = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    content_hash = budget.request_hash(request)
    for a in read(ledger)['attempts']:
        if (a['status'] != 'complete' or a.get('content_sha256') != content_hash or
                a.get('provider_identity') != provider):
            continue
        source = Path(a['workspace'])
        if not (source / 'state.json').is_file():
            continue
        entry = read(source / 'state.json').get('tasks', {}).get(a['task'])
        if not entry or entry.get('status') != 'complete' or not entry.get('response_sha256'):
            continue
        saved = source / entry['response_path']
        original_request = source / 'requests' / (a['task'] + '.json')
        if (not saved.is_file() or sha(saved) != entry['response_sha256'] or
                not original_request.is_file() or budget.request_hash(read(original_request)) != content_hash):
            raise ValueError('Reusable response/request hash mismatch')
        envelope = read(saved)
        result = validate(envelope, task, allowed_models)
        return envelope, result, {'workspace': str(source), 'task_id': a['task'], 'attempt_id': a['attempt_id']}
    return None


def export(out):
    out = Path(out)
    verify(out)
    state = read(out / 'state.json') if (out / 'state.json').exists() else {'tasks': {}}
    answers = []
    for t in read(out / 'tasks.json'):
        entry = state['tasks'].get(t['task_id'], {'status': 'pending'})
        if entry.get('response_sha256') and sha(out / entry['response_path']) != entry['response_sha256']:
            raise ValueError('Saved response changed')
        result = (validate(read(out / entry['response_path']), t, state['allowed_models'])
                  if entry['status'] == 'complete' else None)
        answers.append({k: t[k] for k in ('task_id', 'question_id', 'arm')} |
                       {'status': entry['status'], 'result': result,
                        'failure_kind': entry.get('failure_kind'),
                        'response_sha256': entry.get('response_sha256')})
    summary = {'tasks': len(answers), 'status_counts': dict(Counter(x['status'] for x in answers)),
               'stop_reason': state.get('stop_reason'), 'ledger': state.get('ledger'),
               'cache_reused_tasks': sum(bool(e.get('reused_from')) for e in state['tasks'].values())}
    if state.get('ledger') and Path(state['ledger']).is_file():
        attempts = [a for a in read(state['ledger'])['attempts'] if a['workspace'] == str(out.resolve())]
        usage = [a.get('usage') for a in attempts]
        summary['usage'] = {'requests_reserved': len(attempts),
                            'reserved_token_estimate': sum(a['reserved_tokens'] for a in attempts),
                            'reported_input_tokens': sum(u.get('prompt_tokens', 0) for u in usage if isinstance(u, dict)),
                            'reported_output_tokens': sum(u.get('completion_tokens', 0) for u in usage if isinstance(u, dict)),
                            'reported_total_tokens': sum(u.get('total_tokens', 0) for u in usage if isinstance(u, dict)),
                            'requests_without_usage': sum(not isinstance(u, dict) for u in usage)}
    write(out / 'exports/answers.json', answers)
    write(out / 'exports/summary.json', summary)
    return summary


def run(out, ledger, env_file=None, live=False, client=None, allowed_models=None, max_new_requests=None):
    if not live:
        return export(out)
    out, ledger = Path(out), Path(ledger).resolve()
    verify(out)
    cfg = read(out / 'config.json')
    check_config(cfg)
    allowed_models = allowed_models or [cfg['model']]
    if max_new_requests is not None and max_new_requests < 1:
        raise ValueError('max_new_requests must be positive')
    actual, key, new_calls = client, '', 0
    identity = digest([sha(out / 'manifest.json'), str(ledger), allowed_models])
    with lock(out):
        path = out / 'state.json'
        state = read(path) if path.exists() else {'identity': identity, 'ledger': str(ledger),
                                                  'allowed_models': allowed_models, 'tasks': {}}
        if state['identity'] != identity:
            raise ValueError('Ledger/model policy/run identity changed')
        state.pop('stop_reason', None)
        for task in read(out / 'tasks.json'):
            tid = task['task_id']
            old = state['tasks'].get(tid)
            if old:
                if old['status'] == 'in_flight':
                    details = {}
                    if (out / old['response_path']).is_file():
                        if old.get('response_sha256') and sha(out / old['response_path']) != old['response_sha256']:
                            raise ValueError('Saved response changed')
                        envelope = read(out / old['response_path'])
                        old['response_sha256'] = sha(out / old['response_path'])
                        details = {'usage': envelope.get('usage'), 'returned_model': envelope.get('model')}
                        try:
                            old.update(status='complete', result=validate(envelope, task, allowed_models))
                        except (ValueError, TypeError, KeyError):
                            old.update(status='invalid_response', failure_kind='saved_response_contract')
                    else:
                        old.update(status='needs_attention', failure_kind='network_outcome_unknown')
                        details = {'failure_kind': 'network_outcome_unknown'}
                    attempt = next(a for a in read(ledger)['attempts'] if a['attempt_id'] == old['attempt_id'])
                    if attempt['status'] == 'in_flight':
                        budget.finish(ledger, old['attempt_id'], old['status'], **details)
                    write(path, state)
                if old['status'] != 'complete':
                    state['stop_reason'] = old.get('failure_kind', old['status'])
                    break
                if sha(out / old['response_path']) != old['response_sha256']:
                    raise ValueError('Saved response changed')
                continue
            if max_new_requests is not None and new_calls >= max_new_requests:
                state['stop_reason'] = 'per_invocation_limit'
                break
            req = request_for(task, cfg)
            reusable = find_reusable(ledger, req, cfg, task, allowed_models)
            if reusable:
                envelope, result, origin = reusable
                response_path = 'responses/' + tid + '.json'
                write(out / response_path, envelope)
                write(out / ('requests/' + tid + '.json'), req)
                state['tasks'][tid] = {'status': 'complete', 'attempt_id': origin['attempt_id'],
                                      'response_path': response_path, 'response_sha256': sha(out / response_path),
                                      'result': result, 'reused_from': origin}
                write(path, state)
                continue
            prior = [a for a in read(ledger)['attempts'] if a['workspace'] == str(out.resolve())]
            if (len(prior) >= cfg['max_requests'] or sum(a['reserved_tokens'] for a in prior) +
                    reserve_tokens(req, cfg) > cfg['max_reserved_tokens']):
                state['stop_reason'] = 'workspace_budget'
                break
            if actual is None:
                key = load_key(cfg['api_key_env'], env_file)
                actual = StreamingClient(cfg, key)
            try:
                a = budget.reserve(ledger, out, tid, req, reserve_tokens(req, cfg), provider_identity=cfg['base_url'])
            except ValueError:
                state['stop_reason'] = 'ledger_stop_budget_or_duplicate'
                break
            entry = {'status': 'in_flight', 'attempt_id': a['attempt_id'], 'response_path': 'responses/' + tid + '.json'}
            state['tasks'][tid] = entry
            write(out / ('requests/' + tid + '.json'), req)
            write(path, state)
            details = {}
            try:
                envelope = actual.complete(req)
                if key:
                    envelope = json.loads(json.dumps(envelope, ensure_ascii=False).replace(key, '[REDACTED]'))
                write(out / entry['response_path'], envelope)
                entry['response_sha256'] = sha(out / entry['response_path'])
                write(path, state)  # raw receipt before validation; recover without resend after interruption
                details = {'usage': envelope.get('usage'), 'returned_model': envelope.get('model')}
                entry.update(status='complete', result=validate(envelope, task, allowed_models))
            except RequestFailure as exc:
                entry.update(status='needs_attention' if exc.ambiguous else 'http_failure',
                             failure_kind=exc.kind)
                details = {'failure_kind': exc.kind, 'http_status': exc.http_status}
                if exc.http_status in {401, 402, 403, 429}:
                    details['global_stop'] = 'provider_http_' + str(exc.http_status)
            except (ValueError, KeyError, TypeError, OSError):
                entry.update(status='invalid_response' if entry.get('response_sha256') else 'needs_attention',
                             failure_kind='response_contract_or_local_error')
            if isinstance(actual, StreamingClient) and actual.wire_events:
                events = json.dumps(actual.wire_events, ensure_ascii=False)
                if key:
                    events = events.replace(key, '[REDACTED]')
                write(out / ('events/' + tid + '.json'), json.loads(events))
            budget.finish(ledger, a['attempt_id'], entry['status'], **details)
            new_calls += 1
            write(path, state)
            if entry['status'] != 'complete':
                state['stop_reason'] = entry['failure_kind']
                break
        write(path, state)
    return export(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init-budget')
    init.add_argument('--ledger', required=True, type=Path)
    init.add_argument('--max-requests', required=True, type=int)
    init.add_argument('--max-reserved-tokens', required=True, type=int)
    init.add_argument('--authorization', required=True)
    r = sub.add_parser('run')
    r.add_argument('--out', required=True, type=Path)
    r.add_argument('--ledger', required=True, type=Path)
    r.add_argument('--env-file', type=Path)
    r.add_argument('--live', action='store_true')
    r.add_argument('--max-new-requests', type=int)
    r.add_argument('--allowed-models', nargs='+')
    args = vars(p.parse_args())
    command = args.pop('command')
    print(budget.create(args['ledger'], args['max_requests'], args['max_reserved_tokens'], args['authorization'])
          if command == 'init-budget' else run(**args))
