"""One audited recovery after a successful no-generation route diagnosis."""
import time

from corpus import read, save, sha
from batch_budget import ledger_lock


def resume_network_after_diagnosis(ledger_path, diagnostic_path, config):
    diagnostic = read(diagnostic_path)
    if (diagnostic.get('status') != 'reachable' or diagnostic.get('generation_requests') != 0
            or diagnostic.get('configured_model_listed') is not True
            or diagnostic.get('base_url') != config['base_url']
            or diagnostic.get('model') != config['model']
            or diagnostic.get('route') != 'direct'):
        raise ValueError('A matching successful direct-route model-list diagnosis is required')
    digest = sha(diagnostic_path)
    with ledger_lock(ledger_path):
        ledger = read(ledger_path)
        if ledger.get('global_stop') != 'two_consecutive_network_failures':
            raise ValueError('Only the diagnosed consecutive-network-failure stop may be recovered')
        if any(e.get('diagnostic_sha256') == digest for e in ledger.get('operator_events', [])):
            raise ValueError('This diagnosis has already been used; no repeated automatic recovery')
        event = {'action': 'resume_after_transport_diagnosis', 'time': time.time(),
                 'previous_stop': ledger['global_stop'], 'diagnostic_sha256': digest,
                 'requests_reserved_at_action': len(ledger['attempts']), 'new_route': 'direct',
                 'reason': 'User authorized unattended continuation; model-list reachable directly; '
                           'future independent tasks only; all unknown paid requests retained'}
        ledger.setdefault('operator_events', []).append(event)
        ledger.pop('global_stop')
        save(ledger_path, ledger)
    return event
