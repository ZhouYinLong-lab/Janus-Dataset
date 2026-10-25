"""Serial discover/enrich scheduler with per-task failures and a shared ledger."""
import json
from pathlib import Path
import time

from api import HTTPClient, RequestFailure, check_config, parse_completion, reserve_tokens
import batch_budget as budget
from batch_contract import discovery, enrichment
from batch_plan import request_for, verify
from corpus import read, save, sha
from credentials import load_key
from runner import fingerprint, lock
from stream_http import StreamingClient


class DiagnosticOpener:
    """Capture exception TYPES/errno, never URLs, bodies or exception messages."""
    def __init__(self, delegate):
        self.delegate = delegate; self.last_error = None

    def open(self, *args, **kwargs):
        self.last_error = None
        try:
            return self.delegate.open(*args, **kwargs)
        except Exception as exc:
            reason = getattr(exc, 'reason', None)
            number = getattr(reason, 'errno', None)
            self.last_error = {'exception_type': type(exc).__name__,
                               'reason_type': type(reason).__name__,
                               'errno': number if type(number) is int else None}
            raise


def initial_state(workspace, config, budget_path):
    return {'identity': fingerprint({'manifest': sha(workspace / 'manifest.json'),
             'request_config': {k: v for k, v in config.items()
                                if k not in {'max_requests', 'max_reserved_tokens'}},
             'budget_path': str(Path(budget_path).resolve())}),
            'budget_path': str(Path(budget_path).resolve()), 'tasks': {}, 'attempts': []}


def load_result(workspace, entry):
    path = workspace / entry['result_path']
    if sha(path) != entry['result_sha256']:
        raise ValueError('Stored stage result changed')
    return read(path)


def check_state(workspace, state):
    # Validate dependency/result integrity before any new request can be sent.
    for entry in state['tasks'].values():
        if entry['status'] == 'complete':
            load_result(workspace, entry)
        if entry.get('response_sha256') and sha(workspace / entry['response_path']) != entry['response_sha256']:
            raise ValueError('Stored response changed')
        if entry.get('request_sha256') and sha(workspace / entry['request_path']) != entry['request_sha256']:
            raise ValueError('Stored request changed')


def candidates_for(workspace, state, jid):
    entry = state['tasks'].get(jid + ':discovery')
    if not entry or entry['status'] != 'complete':
        return None, None
    return load_result(workspace, entry)['accepted'], entry['result_sha256']


def validate_saved(workspace, entry, job, candidates):
    if sha(workspace / entry['response_path']) != entry['response_sha256']:
        raise ValueError('Stored response integrity failed')
    payload = parse_completion(read(workspace / entry['response_path']))
    result = discovery(payload, job) if entry['stage'] == 'discovery' else enrichment(payload, job, candidates)
    path = f'results/{entry["job_id"]}_{entry["stage"]}_{entry.get("group", 0):03d}.json'
    save(workspace / path, result)
    entry.update(status='complete', result_path=path, result_sha256=sha(workspace / path),
                 accepted=len(result['accepted']), rejected=len(result['rejected']),
                 unresolved=len(result.get('unresolved', [])))
    entry.pop('failure_kind', None)
    return result


def recover_saved(workspace, state, ledger_path):
    """Recover already-saved responses offline; unknown server outcomes stay blocked."""
    for key, entry in state['tasks'].items():
        if entry['status'] not in {'in_flight', 'invalid_response', 'local_processing_error'}:
            continue
        ledger = read(ledger_path)
        a = next(a for a in ledger['attempts'] if a['attempt_id'] == entry['attempt_id'])
        declared_path = entry.get('response_path')
        if declared_path and not entry.get('response_sha256') and (workspace / declared_path).is_file():
            # This unique path was persisted BEFORE sending, not guessed by a glob.
            entry['response_sha256'] = sha(workspace / declared_path)
            entry['recovery'] = 'found_predeclared_response_file'
        if entry.get('response_sha256'):
            job = read(workspace / f'jobs/{entry["job_id"]}.json')
            cs, digest = candidates_for(workspace, state, entry['job_id'])
            if entry['stage'] == 'enrichment':
                if digest != entry['discovery_result_sha256']:
                    raise ValueError('Enrichment dependency changed')
                size = read(workspace / 'manifest.json')['batch_size']
                cs = cs[entry['group'] * size:(entry['group'] + 1) * size]
            try:
                envelope = read(workspace / entry['response_path'])
                u = envelope.get('usage') if isinstance(envelope, dict) else None
                if isinstance(u, dict):
                    entry['usage'] = {k: v for k, v in u.items()
                        if k in {'prompt_tokens', 'completion_tokens', 'total_tokens'} and type(v) is int and v >= 0}
                validate_saved(workspace, entry, job, cs)
            except (ValueError, TypeError, KeyError):
                entry.update(status='invalid_response', failure_kind='saved_response_contract_invalid')
            except OSError:
                entry.update(status='local_processing_error', failure_kind='local_file_processing_failed')
        elif a['status'] in {'http_failure', 'invalid_response', 'local_processing_error'}:
            entry.update(status=a['status'], failure_kind=a.get('failure_kind'),
                         http_status=a.get('http_status'))
        else:
            entry.update(status='needs_attention', failure_kind='interrupted_request_outcome_unknown')
        if a['status'] == 'in_flight':
            budget.finish(ledger_path, a['attempt_id'], entry['status'],
                          failure_kind=entry.get('failure_kind'), usage=entry.get('usage'))
        save(workspace / 'batch_state.json', state)


def run(workspace, config, ledger_path, live=False, env_file=None, client=None,
        retry_known=False, max_new_requests=None):
    if not live:
        raise ValueError('Explicit --live required; no generation sent')
    check_config(config); workspace = Path(workspace); manifest = verify(workspace)
    ledger_path = Path(ledger_path)
    if max_new_requests is not None and (type(max_new_requests) is not int or max_new_requests < 1):
        raise ValueError('Positive invocation request limit required')
    read(ledger_path)  # explicit pre-existing authorized ledger required
    with lock(workspace):
        path = workspace / 'batch_state.json'
        expected = initial_state(workspace, config, ledger_path)
        state = read(path) if path.exists() else expected
        if state['identity'] != expected['identity']:
            raise ValueError('Model/config/budget identity changed; cannot silently resume')
        check_state(workspace, state)
        recover_saved(workspace, state, ledger_path)
        before = len(state['attempts'])
        state.pop('stop_reason', None)
        key = ''
        if client is not None:
            actual_client = client
        else:
            actual_client = None  # load credentials only when a task really needs sending

        def process(jid, stage, group=0, candidates=None, dependency=None):
            nonlocal key, actual_client
            tid = jid + ':' + stage + (f':{group:03d}' if stage == 'enrichment' else '')
            old = state['tasks'].get(tid)
            if old:
                if old['status'] == 'complete':
                    load_result(workspace, old)
                    return True
                eligible_retry = (retry_known and old['status'] == 'http_failure'
                                  and old.get('http_status') in {429, 500})
                if not eligible_retry:
                    return True  # this task/dependency stays failed; independent tasks proceed
            if max_new_requests is not None and len(state['attempts']) - before >= max_new_requests:
                state['stop_reason'] = 'invocation_request_limit'
                return False
            if budget.status(ledger_path)['global_stop']:
                state['stop_reason'] = 'global_provider_stop'
                return False
            work_attempts = [a for a in read(ledger_path)['attempts']
                             if a['workspace'] == str(workspace.resolve())]
            if len(work_attempts) >= config['max_requests']:
                state['stop_reason'] = 'workspace_request_budget'
                return False
            job = read(workspace / f'jobs/{jid}.json')
            request = request_for(workspace, job, stage, config, candidates, dependency)
            if (sum(a['reserved_tokens'] for a in work_attempts) + reserve_tokens(request, config)
                    > config['max_reserved_tokens']):
                state['stop_reason'] = 'workspace_token_reservation_budget'
                return False
            if actual_client is None:
                key = load_key(config['api_key_env'], env_file)
                actual_client = StreamingClient(config, key)
                actual_client.opener = DiagnosticOpener(actual_client.opener)
            try:
                a = budget.reserve(ledger_path, workspace, tid, request,
                                   reserve_tokens(request, config), retry=bool(old),
                                   provider_identity=config['base_url'])
            except ValueError as exc:
                # Local fixed messages from the ledger only, not provider error strings.
                if 'Duplicate/unknown' in str(exc):
                    state['tasks'][tid] = {'job_id': jid, 'stage': stage, 'group': group,
                                           'status': 'needs_attention',
                                           'failure_kind': 'matching_request_already_reserved'}
                    save(path, state)
                    return True
                state['stop_reason'] = str(exc)
                return False
            number = len(state['attempts']) + 1
            request_path = f'requests/{number:05d}_{jid}_{stage}_{group:03d}.json'
            response_path = f'responses/{number:05d}_{jid}_{stage}_{group:03d}.json'
            if (workspace / response_path).exists():
                raise ValueError('Unique response path already exists; inspect before sending')
            save(workspace / request_path, request)
            entry = {'job_id': jid, 'stage': stage, 'group': group, 'status': 'in_flight',
                     'attempt_id': a['attempt_id'], 'request_path': request_path,
                     'response_path': response_path,
                     'request_sha256': sha(workspace / request_path),
                     'discovery_result_sha256': dependency, 'started': time.time()}
            state['tasks'][tid] = entry
            state['attempts'].append(a['attempt_id'])
            save(path, state)
            details = {}
            try:
                envelope = actual_client.complete(request)
                if key:
                    envelope = json.loads(json.dumps(envelope, ensure_ascii=False).replace(key, '[REDACTED]'))
                save(workspace / response_path, envelope)
                entry.update(response_path=response_path, response_sha256=sha(workspace / response_path))
                if isinstance(envelope, dict):
                    u = envelope.get('usage')
                    usage = {k: v for k, v in u.items() if k in {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                             and type(v) is int and v >= 0} if isinstance(u, dict) else None
                    details = {'usage': usage, 'returned_model': envelope.get('model')}
                    entry.update(details)
                save(path, state)  # response can be revalidated offline after a crash
                validate_saved(workspace, entry, job, candidates)
            except RequestFailure as exc:
                entry.update(status='needs_attention' if exc.ambiguous else 'http_failure',
                             failure_kind=exc.kind, http_status=exc.http_status)
                details.update(failure_kind=exc.kind, http_status=exc.http_status)
                if exc.http_status in {401, 402, 403}:
                    details['global_stop'] = f'provider_http_{exc.http_status}'
                opener = getattr(actual_client, 'opener', None)
                if isinstance(opener, DiagnosticOpener):
                    entry['transport_diagnostic'] = opener.last_error
            except Exception as exc:
                status = ('local_processing_error' if isinstance(exc, OSError) and entry.get('response_sha256')
                          else 'invalid_response' if entry.get('response_sha256') else 'needs_attention')
                entry.update(status=status,
                             failure_kind='response_or_local_processing_failed', exception_type=type(exc).__name__)
                details.update(failure_kind=entry['failure_kind'])
            entry['finished'] = time.time()
            if isinstance(actual_client, StreamingClient) and actual_client.wire_events:
                wire = json.dumps(actual_client.wire_events, ensure_ascii=False)
                if key: wire = wire.replace(key, '[REDACTED]')
                wire_path = response_path + '.events.json'
                save(workspace / wire_path, json.loads(wire))
                entry.update(stream_events_path=wire_path, stream_events_sha256=sha(workspace / wire_path))
            budget.finish(ledger_path, a['attempt_id'], entry['status'], **details)
            save(path, state)
            print(json.dumps({'paper_id': job['paper_id'], 'stage': stage, 'group': group,
                              'status': entry['status'], 'accepted': entry.get('accepted'),
                              'rejected': entry.get('rejected'),
                              'global_requests': budget.status(ledger_path)['requests_reserved']}), flush=True)
            return not bool(budget.status(ledger_path)['global_stop'])

        keep_running = True
        for jid in manifest['job_ids']:
            if not process(jid, 'discovery'):
                break
            candidates, digest = candidates_for(workspace, state, jid)
            if candidates is None:
                continue
            size = manifest['batch_size']
            for offset in range(0, len(candidates), size):
                if not process(jid, 'enrichment', offset // size,
                               candidates[offset:offset + size], digest):
                    keep_running = False; break
            if not keep_running:
                break
        save(path, state)
    from batch_export import export
    return export(workspace)
