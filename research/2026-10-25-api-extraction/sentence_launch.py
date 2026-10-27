"""Three desktop actions for the sentence_v3 pipeline (same versioned CLI entry).

prepare builds the five-paper pilot and the full MolGlueDB workspace, fetches
public full text and checks the budget without sending generation requests.
run drives the pilot first, then the full extraction only after the frozen
five-paper acceptance passes. status prints the four paper buckets (成功 / 失败
/ 缺少全文 / 未完成) and opens the generated summary. Full extraction is locked
until the acceptance file exists and the shared budget permits new requests.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DEFAULTS = {
    'database': str(HERE.parent / '2026-10-26-mg2act-audit/local/source_mapping/MolGlueDB_full.csv'),
    'inventory': str(HERE / 'local/molgluedb_inventory'),
    'pilot_manifest': str(HERE / 'local/sentence_v3_evaluation/papers.json'),
    'pilot_workspace': str(HERE / 'local/sentence_v3_ws_pilot'),
    'workspace': str(HERE / 'local/sentence_v3_ws_full'),
    'config': str(HERE / 'config.local.json'),
    'ledger': str(HERE / 'local/round_01_budget.json'),
    'env_file': str(HERE / '.env'),
    'acceptance': str(HERE / 'local/sentence_v3_acceptance.json'),
}
BUCKET_LABELS = ('成功', '失败', '缺少全文', '未完成')


def command(*args):
    subprocess.run([sys.executable, str(HERE / 'batch_candidate.py'), *map(str, args)],
                   cwd=HERE.parents[1], check=True)


def _status_summary(ws):
    """Print the four paper buckets for one workspace, read-only."""
    from corpus import read
    summary = read(Path(ws) / 'exports/summary.json')
    buckets = summary.get('paper_buckets', {})
    print(f'  {Path(ws).name}:')
    for label in BUCKET_LABELS:
        papers = buckets.get(label, [])
        print(f'    - {label}（{len(papers)}）：' + ('、'.join(papers) if papers else '无'))


def action(name, settings_path=None):
    from corpus import read, save
    path = Path(settings_path) if settings_path else HERE / 'local/sentence_launch.json'
    if path.exists():
        settings = read(path)
        if set(settings) != set(DEFAULTS):
            raise ValueError('Launch settings keys do not match the documented defaults')
    elif name == 'prepare':
        save(path, DEFAULTS)
        settings = DEFAULTS
    else:
        raise ValueError('Run 句段-准备与检查.cmd first')
    s = settings
    if name == 'prepare':
        inv = Path(s['inventory'])
        if not (inv / 'papers.json').exists():
            command('sources', '--database', s['database'], '--out', inv)
        command('fetch', '--inventory', inv)
        for ws, manifest, phase in ((s['pilot_workspace'], s['pilot_manifest'], 'pilot'),
                                    (s['workspace'], inv / 'papers.json', 'full')):
            if not Path(ws).exists():
                command('prepare', '--workspace', ws, '--protocol', 'sentence_v3',
                        '--manifest', manifest, '--phase', phase)
        command('check', '--workspace', s['pilot_workspace'], '--config', s['config'],
                '--ledger', s['ledger'])
        print('准备结束。全库启动仍需固定五篇验收通过；设置保存在：' + str(path))
    elif name == 'run':
        if not Path(s['acceptance']).is_file():
            command('run', '--workspace', s['pilot_workspace'], '--config', s['config'],
                    '--ledger', s['ledger'], '--env-file', s['env_file'], '--phase', 'pilot',
                    '--resume-operator-pause', '--live')
            print('五篇试跑已启动或续跑。完成后用 sentence_acceptance 逐条复核并生成验收文件，'
                  '再重新双击本脚本以启动全库。')
            return
        from sentence_acceptance import require_acceptance
        require_acceptance(s['acceptance'], s['workspace'], read(s['config']))
        command('run', '--workspace', s['workspace'], '--config', s['config'],
                '--ledger', s['ledger'], '--env-file', s['env_file'], '--phase', 'full',
                '--acceptance', s['acceptance'], '--resume-operator-pause', '--live')
    else:
        active = HERE / 'local/active_autorun.json'
        if active.is_file():
            progress = read(active)
            print(json.dumps({k: progress.get(k) for k in ('stage', 'status', 'run_dir', 'updated')},
                             ensure_ascii=False, indent=2))
        present = [ws for ws in (s['pilot_workspace'], s['workspace']) if Path(ws).exists()]
        if not present:
            raise ValueError('Run 句段-准备与检查.cmd first')
        report = None
        for ws in present:
            command('status', '--workspace', ws)
            summary = Path(ws) / 'exports/summary.md'
            if summary.exists():
                report = summary
                _status_summary(ws)
        if report is not None and os.name == 'nt':
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
