"""Single offline preparation entrypoint. Live APIs and training remain separate commands."""
import argparse
import importlib.util
from pathlib import Path

from common import fresh, read, write


def settings(path):
    path = Path(path).resolve()
    cfg = read(path)

    def resolve(value):
        return (path.parent / value).resolve() if value else None

    for key in ('release', 'questions', 'supplements', 'split_plan', 'api_config', 'train_config', 'out'):
        cfg[key] = resolve(cfg.get(key))
    cfg['workspaces'] = [resolve(p) for p in cfg['workspaces']]
    if cfg.get('mg2act'):
        cfg['mg2act'] = {k: resolve(v) for k, v in cfg['mg2act'].items()}
    return cfg


def check(settings_path):
    cfg = settings(settings_path)
    paths = {k: cfg[k] for k in ('release', 'questions', 'api_config', 'train_config')}
    for i, ws in enumerate(cfg['workspaces']):
        paths['workspace_' + str(i)] = ws / 'manifest.json'
    if cfg['supplements']:
        paths['supplements'] = cfg['supplements']
    if cfg['split_plan']:
        paths['split_plan'] = cfg['split_plan']
    if cfg.get('mg2act'):
        paths.update({'mg2act_' + k: v for k, v in cfg['mg2act'].items()})
    missing = {k: str(p) for k, p in paths.items() if p is None or not p.exists()}
    if cfg['release'] and cfg['release'].is_dir():
        for name in ('acceptance_report.json', 'reliable_evidence.json'):
            if not (cfg['release'] / name).is_file():
                missing['release_' + name] = str(cfg['release'] / name)
    return {'preparation_ready': not missing, 'missing_inputs': missing,
            'optional_training_supplements_supplied': bool(cfg['supplements']),
            'training_packages': {n: importlib.util.find_spec(n) is not None
                                  for n in ('torch', 'transformers', 'peft')},
            'generation_requests': 0, 'training_executed': False}


def prepare_all(settings_path):
    status = check(settings_path)
    if not status['preparation_ready']:
        return status
    from prepare import prepare
    from rag import prepare_rag
    from train import prepare_training
    from benchmark import prepare_benchmark
    cfg = settings(settings_path)
    out = fresh(cfg['out'])
    result = {'generation_requests': 0, 'training_executed': False, 'stages': {}}
    try:
        result['stages']['bundle'] = prepare(cfg['release'], cfg['workspaces'], out / 'bundle', cfg['supplements'],
                                              split_plan=cfg['split_plan'])
        result['stages']['rag'] = prepare_rag(out / 'bundle', cfg['questions'], cfg['api_config'], out / 'rag')
        if cfg.get('mg2act'):
            result['stages']['benchmark'] = prepare_benchmark(**cfg['mg2act'], config=cfg['api_config'],
                                                             out=out / 'mg2act', bundle=out / 'bundle')
        result['stages']['training'] = prepare_training(out / 'bundle', cfg['questions'], cfg['train_config'],
                                                        out / 'training', out / 'mg2act' if cfg.get('mg2act') else None)
        result['status'] = 'prepared'
    except Exception as exc:
        result.update(status='preparation_failed', failure_kind=type(exc).__name__, failure=str(exc))
        write(out / 'workflow_state.json', result)
        raise
    write(out / 'workflow_state.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('check', 'prepare'))
    p.add_argument('--settings', type=Path, default=Path(__file__).parent / 'workflow.example.json')
    args = p.parse_args()
    import json
    print(json.dumps(check(args.settings) if args.command == 'check' else prepare_all(args.settings), ensure_ascii=False, indent=2))
