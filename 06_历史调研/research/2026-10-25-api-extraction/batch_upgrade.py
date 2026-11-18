"""Explicit audited software/transport upgrade; never clears paid task history."""
from pathlib import Path
import time

from api import check_config
from batch_plan import CODE
from corpus import HERE, read, save, sha
from runner import fingerprint, lock


def upgrade(workspace, config, reason, refresh_prompts=False):
    check_config(config); workspace = Path(workspace)
    if not reason or not reason.strip():
        raise ValueError('Explicit upgrade reason required')
    with lock(workspace):
        manifest = read(workspace / 'manifest.json')
        if manifest.get('pipeline') != 'two_stage_batch_v1':
            raise ValueError('Upgrade accepts only generic batch workspaces, never old B022 trials')
        for name, digest in manifest['file_hashes'].items():
            if sha(workspace / name) != digest:
                raise ValueError('Frozen input changed; upgrade will not hide it')
        for p in manifest['papers']:
            if p.get('source_sha256') and sha(p['source_path']) != p['source_sha256']:
                raise ValueError('Original source changed')
        state_path = workspace / 'batch_state.json'
        state = read(state_path) if state_path.exists() else None
        if refresh_prompts and state and state['attempts']:
            raise ValueError('Prompt refresh is allowed only before any generation in this workspace')
        config_hash = fingerprint({k: v for k, v in config.items()
                                   if k not in {'max_requests', 'max_reserved_tokens'}})
        old_manifest_hash = sha(workspace / 'manifest.json')
        if state:
            expected = fingerprint({'manifest': old_manifest_hash,
                'request_config': {k: v for k, v in config.items()
                                   if k not in {'max_requests', 'max_reserved_tokens'}},
                'budget_path': state['budget_path']})
            if expected != state['identity']:
                raise ValueError('Supplied config does not match the historical workspace')
            if any(t['status'] == 'in_flight' for t in state['tasks'].values()):
                raise ValueError('Finish or reconcile in-flight requests before upgrading')
        history = manifest.get('upgrade_history', [])
        number = len(history) + 1
        save(workspace / f'upgrades/{number:03d}_manifest_before.json', manifest)
        if state:
            save(workspace / f'upgrades/{number:03d}_state_before.json', state)
        event = {'reason': reason, 'time': time.time(), 'old_manifest_sha256': old_manifest_hash,
                 'old_state_identity': state['identity'] if state else None,
                 'request_config_hash': config_hash, 'budget_path': state['budget_path'] if state else None}
        if refresh_prompts:
            for name in ['discovery.md', 'enrichment.md']:
                (workspace / f'upgrades/{number:03d}_{name}_before').write_bytes((workspace / name).read_bytes())
                (workspace / name).write_bytes((HERE / name).read_bytes())
                manifest['file_hashes'][name] = sha(workspace / name)
            event['prompts_refreshed_before_first_generation'] = True
        manifest.update(transport='sse', code_hashes={n: sha(HERE / n) for n in CODE},
                        upgrade_history=history + [event])
        save(workspace / 'manifest.json', manifest)
        if state:
            state.setdefault('identity_history', []).append(event)
            state['identity'] = fingerprint({'manifest': sha(workspace / 'manifest.json'),
                'request_config': {k: v for k, v in config.items()
                                   if k not in {'max_requests', 'max_reserved_tokens'}},
                'budget_path': state['budget_path']})
            save(state_path, state)
    return {'transport': 'sse', 'paid_tasks_preserved': len(state['tasks']) if state else 0,
            'generation_requests_sent': 0, 'reason': reason}
