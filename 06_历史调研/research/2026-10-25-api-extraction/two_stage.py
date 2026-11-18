"""Bounded, explicit-call development comparison. No automatic paid retries."""
import argparse
import json
from pathlib import Path
import time

from api import HTTPClient, RequestFailure, check_config, parse_completion, reserve_tokens
from contract import validate
from corpus import HERE, read, save, sha
from credentials import load_key
from runner import fingerprint, lock
from two_stage_core import check_frozen, prepare, validate_discovery, validate_enrichment

CALLS = ('baseline_active', 'discovery_active', 'discovery_empty',
         'enrich_active', 'baseline_empty')
CODE = ('two_stage.py', 'two_stage_core.py', 'api.py', 'contract.py',
        'corpus.py', 'credentials.py', 'runner.py')


def prepare_experiment(out, config):
    check_config(config)
    manifest = prepare(out)
    # Separate experiment budget, explicitly authorised for this six-call comparison.
    config = dict(config, max_requests=6, max_reserved_tokens=500000)
    save(Path(out) / 'config.json', config)
    manifest['input_hashes']['config.json'] = sha(Path(out) / 'config.json')
    save(Path(out) / 'manifest.json', manifest)
    return {'planned_calls': list(CALLS), 'request_ceiling': 6,
            'model': config['model'], 'source_sha256': manifest['source_sha256']}


def stored_result(workspace, state, name):
    item = state['calls'].get(name)
    if not item or item['status'] != 'complete':
        raise ValueError('Required completed result unavailable: ' + name)
    path = workspace / item['result_path']
    if sha(path) != item['result_sha256']:
        raise ValueError('Saved result changed: ' + name)
    return read(path)


def request_for(workspace, name, config, candidates=None):
    active = not name.endswith('_empty')
    job = read(workspace / ('active.json' if active else 'empty.json'))
    user = {k: job[k] for k in ('paper_id', 'doi', 'primary_units')}
    if name.startswith('discovery'):
        system = (workspace / 'discovery.md').read_text(encoding='utf-8')
    elif name.startswith('enrich'):
        system = ((workspace / 'enrichment.md').read_text(encoding='utf-8')
                  + '\n\nATTACHED EXTRACTION CONTRACT:\n'
                  + (workspace / 'one_step.md').read_text(encoding='utf-8'))
        user.update(context_units=job['context_units'], candidates=candidates)
    else:
        system = (workspace / 'one_step.md').read_text(encoding='utf-8')
        user['context_units'] = job['context_units']
    request = {'model': config['model'], 'messages': [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)}],
        'stream': False, config['output_token_parameter']: config['max_output_tokens']}
    if config['response_format'] == 'json_object':
        request['response_format'] = {'type': 'json_object'}
    return request, job


def run_call(workspace, name, live=False, retry=False, env_file=None, client=None):
    if not live:
        raise ValueError('Explicit --live required; no request sent')
    if name not in CALLS:
        raise ValueError('Unknown experiment call')
    workspace = Path(workspace)
    check_frozen(workspace)
    config = read(workspace / 'config.json')
    check_config(config)
    if config['max_requests'] > 6:
        raise ValueError('Hard experiment ceiling is six generation requests')
    identity = fingerprint({'manifest': sha(workspace / 'manifest.json'),
                            'code': {n: sha(HERE / n) for n in CODE}})
    with lock(workspace):
        state_path = workspace / 'state.json'
        state = read(state_path) if state_path.exists() else {
            'identity': identity, 'config': config, 'attempts': [], 'calls': {}}
        if state['identity'] != identity:
            raise ValueError('Experiment code or inputs changed; no resume')
        if any(a['status'] in {'in_flight', 'needs_attention'} for a in state['attempts']):
            raise ValueError('Unresolved request outcome; all new sending blocked')
        old = state['calls'].get(name)
        if old:
            if old['status'] == 'complete':
                stored_result(workspace, state, name)
                return summary(state)
            if old['status'] == 'skipped_no_candidates':
                return summary(state)
            past = [a for a in state['attempts'] if a['call'] == name]
            if (not retry or old['status'] != 'http_failure' or len(past) != 1
                    or past[-1].get('http_status') not in {429, 500}
                    or any(a.get('explicit_retry') for a in state['attempts'])):
                raise ValueError('Only one explicit HTTP429/500 retry is permitted')
        elif retry:
            raise ValueError('Cannot retry a call not yet attempted')
        candidates = None
        if name == 'enrich_active':
            discovered = stored_result(workspace, state, 'discovery_active')
            candidates = discovered['accepted']
            if not candidates:
                state['calls'][name] = {'status': 'skipped_no_candidates'}
                save(state_path, state)
                return summary(state)
        request, job = request_for(workspace, name, config, candidates)
        reservation = reserve_tokens(request, config)
        if (len(state['attempts']) >= min(config['max_requests'], 6)
                or sum(a['reserved_tokens'] for a in state['attempts']) + reservation
                > config['max_reserved_tokens']):
            raise ValueError('Experiment request/token reservation budget exhausted')
        key = ''
        if client is None:
            key = load_key(config['api_key_env'], env_file)
            client = HTTPClient(config, key)
        index = len(state['attempts']) + 1
        request_path = Path('requests') / f'{index:02d}_{name}.json'
        save(workspace / request_path, request)
        attempt = {'index': index, 'call': name, 'explicit_retry': retry,
                   'reserved_tokens': reservation, 'status': 'in_flight',
                   'started': time.time(), 'requested_model': config['model'],
                   'request_path': str(request_path),
                   'request_sha256': sha(workspace / request_path)}
        state['attempts'].append(attempt)
        state['calls'][name] = {'status': 'in_flight'}
        save(state_path, state)  # reserve before the paid request
        response_saved = False
        try:
            envelope = client.complete(request)
            if key:
                envelope = json.loads(json.dumps(envelope, ensure_ascii=False).replace(key, '[REDACTED]'))
            response_path = Path('responses') / f'{index:02d}_{name}.json'
            save(workspace / response_path, envelope)
            response_saved = True
            attempt.update(response_path=str(response_path),
                           response_sha256=sha(workspace / response_path))
            if isinstance(envelope, dict):
                attempt.update(usage=envelope.get('usage'), returned_model=envelope.get('model'))
            payload = parse_completion(envelope)
            if name.startswith('discovery'):
                result = validate_discovery(payload, job)
            elif name.startswith('enrich'):
                result = validate_enrichment(payload, job, candidates)
            else:
                result = validate(payload, job)
            result_path = Path('results') / f'{name}.json'
            save(workspace / result_path, result)
            state['calls'][name] = {'status': 'complete', 'result_path': str(result_path),
                                    'result_sha256': sha(workspace / result_path)}
            attempt['status'] = 'complete'
        except RequestFailure as exc:
            attempt.update(status='needs_attention' if exc.ambiguous else 'http_failure',
                           failure_kind=exc.kind, http_status=exc.http_status)
            state['calls'][name] = {'status': attempt['status']}
        except Exception:
            # Never include provider bodies, exception strings, or credentials in logs.
            attempt['status'] = 'invalid_response' if response_saved else 'needs_attention'
            state['calls'][name] = {'status': attempt['status']}
        attempt['finished'] = time.time()
        save(state_path, state)
        return summary(state)


def summary(state):
    return {'requests_reserved': len(state['attempts']),
            'calls': {k: v['status'] for k, v in state['calls'].items()},
            'reported_tokens': sum(a.get('usage', {}).get('total_tokens', 0)
                                   for a in state['attempts'] if isinstance(a.get('usage'), dict))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--workspace', required=True); p.add_argument('--config', required=True)
    p = sub.add_parser('run')
    p.add_argument('--workspace', required=True); p.add_argument('--call', choices=CALLS, required=True)
    p.add_argument('--live', action='store_true'); p.add_argument('--retry', action='store_true')
    p.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare_experiment(args.workspace, read(args.config))
    else:
        result = run_call(args.workspace, args.call, args.live, args.retry, args.env_file)
    print(json.dumps(result, ensure_ascii=False))
    if args.command == 'run' and result['calls'].get(args.call) not in {'complete', 'skipped_no_candidates'}:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
