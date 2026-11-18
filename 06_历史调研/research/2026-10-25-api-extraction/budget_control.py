"""Audited pause at the next request boundary; never reset caps or attempts."""
import argparse
import json
import time
from batch_budget import ledger_lock
from corpus import read, save


def control(path, action, reason):
    if action not in {'pause', 'resume'} or not reason.strip():
        raise ValueError('Explicit action and reason required')
    with ledger_lock(path):
        ledger = read(path); current = ledger.get('global_stop')
        if action == 'pause':
            if current: raise ValueError('An existing provider/operator stop must not be overwritten')
            ledger['global_stop'] = 'operator_pause'
        else:
            if current != 'operator_pause':
                raise ValueError('This command cannot clear a provider error or absent stop')
            ledger.pop('global_stop')
        ledger.setdefault('operator_events', []).append({'action': action, 'reason': reason,
            'time': time.time(), 'requests_reserved_at_action': len(ledger['attempts'])})
        save(path, ledger)
    return {'action': action, 'requests_reserved': len(ledger['attempts']),
            'max_requests': ledger['max_requests'], 'generation_requests_sent': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['pause', 'resume']); p.add_argument('--ledger', required=True)
    p.add_argument('--reason', required=True); a = p.parse_args()
    print(json.dumps(control(a.ledger, a.action, a.reason)))
