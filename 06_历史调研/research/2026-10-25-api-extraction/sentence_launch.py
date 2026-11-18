"""Three desktop actions for the sentence_v3 pipeline (same versioned CLI entry).

prepare builds the five-paper pilot and the full MolGlueDB workspace, fetches
public full text and checks the budget without sending generation requests.
run drives the pilot first, then the full extraction only after the frozen
five-paper acceptance passes. status prints the four paper buckets (成功 / 失败
/ 缺少全文 / 未完成) and opens the generated summary. Full extraction is locked
until content acceptance passes and the shared budget permits new requests.
"""
import argparse
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


def command(*args, env=None):
    subprocess.run([sys.executable, str(HERE / 'batch_candidate.py'), *map(str, args)],
                   cwd=HERE.parents[1], check=True, env=env)


def _bound_ledger(settings):
    """Reuse the run's ledger even when desktop settings predate that run."""
    from corpus import read
    bindings = set()
    for key in ('pilot_workspace', 'workspace'):
        state_path = Path(settings[key]) / 'candidate_state.json'
        if not state_path.is_file():
            continue
        state = read(state_path)
        if state.get('pipeline') != 'molgluedb_sentence_v3' or not state.get('budget_path'):
            raise ValueError('Invalid sentence workspace budget binding: ' + str(state_path))
        path = Path(state['budget_path'])
        if not path.is_absolute():
            raise ValueError('Workspace budget binding must be absolute: ' + str(state_path))
        bindings.add(path.resolve())
    if len(bindings) > 1:
        raise ValueError('Pilot and full workspaces bind different ledgers; preserve both runs')
    ledger = next(iter(bindings), Path(settings['ledger']).resolve())
    if bindings and not ledger.is_file():
        raise ValueError('Bound budget ledger is missing: ' + str(ledger))
    if ledger != Path(settings['ledger']).resolve():
        print('使用工作区已绑定的账本：' + str(ledger))
    return str(ledger)


def _status_summary(ws):
    """Read current artifacts, rather than a possibly stale exported summary."""
    from sentence_export import snapshot
    summary = snapshot(ws)[0]
    buckets = summary.get('paper_buckets', {})
    print(f'  {Path(ws).name}:')
    for label in BUCKET_LABELS:
        papers = buckets.get(label, [])
        print(f'    - {label}（{len(papers)}）：' + ('、'.join(papers) if papers else '无'))
    completed = sum(p['jobs_processed'] for p in summary['papers'])
    total = sum(p['jobs'] for p in summary['papers'])
    print(f'    完成分块：{completed}/{total}；观察记录：{summary["records"]}；内容复核：待验收')
    print('    停止原因：' + str(summary.get('stop_reason') or '无'))
    budget = summary.get('shared_budget')
    if budget:
        print(f'    共享调用：{budget["requests_reserved"]}/{budget["max_requests"]}；'
              f'未知用量：{budget["attempts_without_usage"]}')


def action(name, settings_path=None, max_new_requests=None):
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
    ledger = _bound_ledger(s) if name in {'prepare', 'run', 'repair'} else None
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
                '--ledger', ledger)
        print('准备结束。全库启动仍需固定五篇验收通过；设置保存在：' + str(path))
    elif name == 'run':
        from sentence_network import child_environment
        env = child_environment(path, read(s['config']))
        limit_args = [] if max_new_requests is None else ['--max-new-requests', max_new_requests]
        if env is not None:
            print('API连接使用已验证的直连；系统代理设置保持原样。')
        acceptance_path = Path(s['acceptance'])
        acceptance = read(acceptance_path) if acceptance_path.is_file() else {}
        if not isinstance(acceptance, dict):
            raise ValueError('Acceptance report must be an object')
        if acceptance.get('passed') is not True:
            if acceptance_path.is_file():
                print('验收尚未通过，继续五篇试跑；全库保持锁定。')
            command('run', '--workspace', s['pilot_workspace'], '--config', s['config'],
                    '--ledger', ledger, '--env-file', s['env_file'], '--phase', 'pilot',
                    '--resume-operator-pause', '--live', *limit_args, env=env)
            print('五篇试跑已启动或续跑。完成后用 sentence_acceptance 逐条复核并生成验收文件，'
                  '再重新双击本脚本以启动全库。')
            return
        from sentence_acceptance import require_acceptance
        require_acceptance(s['acceptance'], s['workspace'], read(s['config']))
        command('run', '--workspace', s['workspace'], '--config', s['config'],
                '--ledger', ledger, '--env-file', s['env_file'], '--phase', 'full',
                '--acceptance', s['acceptance'], '--resume-operator-pause', '--live', *limit_args, env=env)
    elif name == 'repair':
        from sentence_network import repair
        result = repair(path, s, ledger)
        for probe in result['probes']:
            print(f'连接诊断 {probe["route"]}：{probe["status"]}；{probe["elapsed_seconds"]}秒')
        print('诊断已保存：' + result['diagnosis_dir'])
        print('连接已准备好。再次启动将续跑独立任务；未知请求不重发。')
    else:
        present = [ws for ws in (s['pilot_workspace'], s['workspace']) if Path(ws).exists()]
        if not present:
            raise ValueError('Run 句段-准备与检查.cmd first')
        report = None
        for ws in present:
            _status_summary(ws)
            summary = Path(ws) / 'exports/summary.md'
            if summary.exists():
                report = summary
        if report is not None and os.name == 'nt':
            print('打开最近一次自动导出的汇总；实时进度以上方读取结果为准。')
            os.startfile(report)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'run', 'status', 'repair'])
    p.add_argument('--settings', type=Path)
    p.add_argument('--max-new-requests', type=int)
    a = p.parse_args()
    try:
        action(a.action, a.settings, a.max_new_requests)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(1)
