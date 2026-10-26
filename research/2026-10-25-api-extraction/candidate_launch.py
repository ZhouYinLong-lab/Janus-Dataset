"""Three desktop actions backed by the same versioned command-line entry."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DEFAULTS = {'database': str(HERE.parent / '2026-10-26-mg2act-audit/local/source_mapping/MolGlueDB_full.csv'),
            'inventory': str(HERE / 'local/molgluedb_inventory'),
            'workspace': str(HERE / 'local/molgluedb_full_v2'),
            'pilot_workspace': str(HERE / 'local/molgluedb_pilot_v2'),
            'config': str(HERE / 'batch.config.example.json'),
            'ledger': str(HERE / 'local/round_01_budget.json'),
            'env_file': str(HERE / '.env'),
            'acceptance': str(HERE / 'local/molgluedb_acceptance.json')}


def command(*args):
    subprocess.run([sys.executable, str(HERE/'batch_candidate.py'), *map(str, args)],
                   cwd=HERE.parents[1], check=True)


def action(name, settings_path=None):
    from corpus import read, save
    path = Path(settings_path) if settings_path else HERE/'local/molglue_launch.json'
    if path.exists():
        settings = read(path)
        if set(settings) != set(DEFAULTS):
            raise ValueError('Launch settings keys do not match the documented defaults')
    elif name == 'prepare':
        save(path, DEFAULTS)
        settings = DEFAULTS
    else:
        raise ValueError('Run 准备与检查.cmd first')
    s = settings
    if name == 'prepare':
        inv = Path(s['inventory'])
        if not (inv/'papers.json').exists():
            command('sources', '--database', s['database'], '--out', inv)
        command('fetch', '--inventory', inv)
        if Path(s['workspace']).exists():
            from corpus import sha
            manifest = read(Path(s['workspace'])/'manifest.json')
            digest = sha(inv/'papers.json')
            if manifest.get('input_manifest_sha256') != digest:
                old = Path(s['workspace'])
                s['workspace'] = str(old.parent/('molgluedb_full_v2_'+digest[:12]))
                save(path, s)
        if not Path(s['workspace']).exists():
            command('prepare', '--workspace', s['workspace'], '--manifest', inv/'papers.json')
        command('check', '--workspace', s['workspace'], '--config', s['config'], '--ledger', s['ledger'])
        print('准备结束。全库启动仍需固定五篇验收通过；设置保存在：' + str(path))
    elif name == 'run':
        command('run', '--workspace', s['workspace'], '--config', s['config'],
                '--ledger', s['ledger'], '--env-file', s['env_file'], '--phase', 'full',
                '--acceptance', s['acceptance'], '--resume-operator-pause', '--live')
    else:
        if not Path(s['workspace']).exists():
            inventory_summary = Path(s['inventory'])/'source_inventory.json'
            if inventory_summary.exists():
                print(json.dumps(read(inventory_summary), ensure_ascii=False, indent=2))
                print('全文准备尚未结束，提取工作区未创建。')
                return
            raise ValueError('Run 准备与检查.cmd first')
        command('status', '--workspace', s['workspace'])
        report = Path(s['workspace'])/'exports/summary.md'
        if report.exists() and os.name == 'nt':
            os.startfile(report)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'run', 'status'])
    p.add_argument('--settings', type=Path)
    a = p.parse_args()
    try:
        action(a.action, a.settings)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(1)
