"""One explicit spending ledger shared by extraction and downstream workspaces."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

from corpus import read, save


def request_hash(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@contextmanager
def ledger_lock(path):
    lock_path = Path(str(path) + '.lock')
    with lock_path.open('x', encoding='utf-8') as stream:
        stream.write(str(os.getpid()))
    try:
        yield
    finally:
        lock_path.unlink()


def create(path, max_requests, max_reserved_tokens, authorization):
    path = Path(path)
    for name, value in [('max_requests', max_requests), ('max_reserved_tokens', max_reserved_tokens)]:
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError(f'{name} must be a positive integer or null')
    if not isinstance(authorization, str) or not authorization.strip():
        raise ValueError('Record the explicit authorization before creating a budget')
    path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_lock(path):
        if path.exists():
            raise ValueError('Budget already exists; never reset spent requests')
        save(path, {'version': 1, 'max_requests': max_requests,
                    'max_reserved_tokens': max_reserved_tokens,
                    'authorization': authorization, 'created': time.time(), 'attempts': []})
    return read(path)


def reserve(path, workspace, task, request, tokens, retry=False, provider_identity=''):
    if type(tokens) is not int or tokens < 1:
        raise ValueError('Invalid token reservation')
    with ledger_lock(path):
        ledger = read(path)
        if ledger.get('global_stop'):
            raise ValueError('Global provider stop requires diagnosis: ' + ledger['global_stop'])
        parsed = urlsplit(provider_identity)
        provider = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
        digest = request_hash({'provider': provider, 'request': request})
        previous = [a for a in ledger['attempts'] if a['request_sha256'] == digest]
        if previous and (not retry or len(previous) != 1 or previous[-1]['status'] != 'http_failure'
                         or previous[-1].get('http_status') not in {429, 500}):
            raise ValueError('Duplicate/unknown paid request blocked by shared ledger')
        if retry and not previous:
            raise ValueError('No eligible previous request for retry')
        request_cap_hit = (ledger['max_requests'] is not None
                           and len(ledger['attempts']) >= ledger['max_requests'])
        token_cap_hit = (ledger['max_reserved_tokens'] is not None
                         and sum(a['reserved_tokens'] for a in ledger['attempts']) + tokens
                         > ledger['max_reserved_tokens'])
        if request_cap_hit or token_cap_hit:
            raise ValueError('Shared request/token budget exhausted')
        attempt = {'attempt_id': uuid.uuid4().hex, 'workspace': str(Path(workspace).resolve()),
                   'task': task, 'request_sha256': digest, 'reserved_tokens': tokens,
                   'content_sha256': request_hash(request), 'provider_identity': provider,
                   'requested_model': request['model'], 'status': 'in_flight',
                   'explicit_retry': retry, 'started': time.time()}
        ledger['attempts'].append(attempt)
        save(path, ledger)  # before any provider call; orphan reservations stay consumed
        return attempt.copy()


def finish(path, attempt_id, status, **details):
    allowed = {'complete', 'http_failure', 'needs_attention', 'invalid_response', 'local_processing_error'}
    if status not in allowed:
        raise ValueError('Invalid ledger final status')
    if set(details) - {'http_status', 'failure_kind', 'usage', 'returned_model', 'global_stop'}:
        raise ValueError('Unsupported diagnostic fields')
    with ledger_lock(path):
        ledger = read(path)
        attempt = next(a for a in ledger['attempts'] if a['attempt_id'] == attempt_id)
        if attempt['status'] != 'in_flight':
            raise ValueError('Attempt already final; never overwrite its history')
        global_stop = details.pop('global_stop', None)
        attempt.update(status=status, finished=time.time(), **details)
        # Across workspaces too: two consecutive transport failures stop further sends.
        recent = ledger['attempts'][-2:]
        if len(recent) == 2 and all(a.get('failure_kind') == 'network_outcome_unknown' for a in recent):
            global_stop = 'two_consecutive_network_failures'
        if global_stop:
            ledger['global_stop'] = global_stop
        save(path, ledger)


def status(path):
    ledger = read(path)
    usage = [a.get('usage') for a in ledger['attempts']]
    return {'max_requests': ledger['max_requests'], 'requests_reserved': len(ledger['attempts']),
            'reserved_token_estimate': sum(a['reserved_tokens'] for a in ledger['attempts']),
            'reported_total_tokens': sum(u.get('total_tokens', 0) for u in usage if isinstance(u, dict)),
            'attempts_without_usage': sum(not isinstance(u, dict) for u in usage),
            'global_stop': ledger.get('global_stop'),
            'billing': 'Reported usage is not a verified bill; missing usage is unknown, not zero.'}
