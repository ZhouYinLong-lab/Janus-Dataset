"""Diagnose a stopped pilot and scope proxy bypass to its API child process."""
from copy import deepcopy
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from corpus import read, save


def route_file(settings_path):
    path = Path(settings_path)
    return path.with_name(path.stem + '.network.json')


def child_environment(settings_path, config):
    """Never change the caller environment, frozen route identity or API config."""
    path = route_file(settings_path)
    if not path.exists():
        return None
    route = read(path)
    if (route.get('route') != 'direct' or route.get('base_url') != config['base_url']
            or route.get('model') != config['model']):
        raise ValueError('Saved network route does not match the configured API; diagnose again')
    host = urlsplit(config['base_url']).hostname
    if not host:
        raise ValueError('API hostname is missing')
    env = dict(os.environ)
    exclusions = [x.strip() for x in
                  (env.get('no_proxy', '') + ',' + env.get('NO_PROXY', '')).split(',') if x.strip()]
    exclusions = list(dict.fromkeys(exclusions + [host]))
    env['no_proxy'] = env['NO_PROXY'] = ','.join(exclusions)
    return env


def _probe(config, key, route):
    from candidate_transport import DiagnosticStreamingClient
    bounded = dict(config, timeout_seconds=min(config['timeout_seconds'], 12))
    client = DiagnosticStreamingClient(bounded, key, route)
    start = time.monotonic()
    result = {'base_url': config['base_url'], 'model': config['model'], 'route': route,
              'generation_requests': 0, 'checked_at': time.time()}
    try:
        ids = client.models()
        result.update(status='reachable', configured_model_listed=config['model'] in ids)
    except Exception as error:
        result.update(status='failed', failure_kind=getattr(error, 'kind', type(error).__name__),
                      http_status=getattr(error, 'http_status', None))
    result.update(elapsed_seconds=round(time.monotonic() - start, 3),
                  transport=deepcopy(client.opener.diagnostic))
    return result


def repair(settings_path, settings, ledger_path):
    """Only model-list GETs; no generation, retries, config edits or task resets."""
    from candidate_runtime import RunLock
    from candidate_recovery import resume_network_after_diagnosis
    from credentials import load_key
    from sentence_workspace import verify
    workspace = Path(settings['pilot_workspace']).resolve()
    config = read(settings['config'])
    diagnosis_dir = Path(settings_path).parent / ('network_diagnosis_' + str(time.time_ns()))
    with RunLock(str(Path(ledger_path).resolve()) + '.candidate_run.lock'), \
            RunLock(workspace / '.candidate_run.lock'):
        verify(workspace)
        state = read(workspace / 'candidate_state.json')
        if state.get('config') != config or Path(state['budget_path']).resolve() != Path(ledger_path).resolve():
            raise ValueError('Pilot config or budget does not match; preserve the existing run')
        # Other route identities need their own explicit migration; this repair
        # preserves this pilot's environment identity by using per-host NO_PROXY.
        if state.get('network_route') != 'environment':
            raise ValueError('This repair requires the existing environment route identity')
        ledger = read(ledger_path)
        stop = ledger.get('global_stop')
        if stop not in {None, 'two_consecutive_network_failures'}:
            raise ValueError('Network repair cannot clear this stop: ' + str(stop))
        key = load_key(config['api_key_env'], settings['env_file'])
        # Sequential, bounded, non-generating GETs. Save only fixed diagnostics.
        probes = [_probe(config, key, r) for r in ('environment', 'direct')]
        for result in probes:
            save(diagnosis_dir / (result['route'] + '.json'), result)
        direct = probes[1]
        if direct['status'] != 'reachable' or direct.get('configured_model_listed') is not True:
            raise ValueError('Direct API diagnosis failed; the existing stop is retained')
        if stop:
            event = resume_network_after_diagnosis(ledger_path, diagnosis_dir / 'direct.json', config)
            save(diagnosis_dir / 'recovery.json', event)
        # No proxy is removed: only this API host bypasses it in child processes.
        save(route_file(settings_path), {'route': 'direct', 'base_url': config['base_url'],
              'model': config['model'], 'created': time.time(), 'diagnosis_dir': str(diagnosis_dir.resolve()),
              'scope': 'api_host_in_launcher_child_process_only'})
    return {'probes': probes, 'diagnosis_dir': str(diagnosis_dir.resolve()),
            'generation_requests': 0, 'unknown_requests_retried': 0}
