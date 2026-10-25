"""One entry point: generic two-stage extraction, resume, inspect and export."""
import argparse
import json
from pathlib import Path

import batch_budget
from batch_export import export
from batch_plan import estimate, prepare, verify
from batch_run import run
from corpus import read, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('budget', help='Create explicit shared generation budget; never overwrite')
    p.add_argument('--ledger', required=True, type=Path)
    p.add_argument('--max-requests', required=True, type=int)
    p.add_argument('--max-reserved-tokens', required=True, type=int)
    p.add_argument('--authorization', required=True)
    p = sub.add_parser('upgrade', help='Explicit audited code/transport upgrade without resetting tasks')
    p.add_argument('--workspace', required=True, type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--reason', required=True)
    for name in ['prepare', 'estimate', 'run', 'start', 'status', 'export']:
        p = sub.add_parser(name)
        p.add_argument('--workspace', required=True, type=Path)
        if name in {'prepare', 'start'}:
            p.add_argument('--papers', nargs='+'); p.add_argument('--manifest', type=Path)
            p.add_argument('--limit', type=int, default=5)
        if name in {'estimate', 'run', 'start'}:
            p.add_argument('--config', required=True, type=Path)
        if name in {'run', 'start'}:
            p.add_argument('--ledger', required=True, type=Path)
            p.add_argument('--env-file', type=Path); p.add_argument('--live', action='store_true')
            p.add_argument('--retry-known', action='store_true')
            p.add_argument('--max-new-requests', type=int)
    args = parser.parse_args()
    try:
        if args.command == 'budget':
            batch_budget.create(args.ledger, args.max_requests, args.max_reserved_tokens, args.authorization)
            result = batch_budget.status(args.ledger)
        elif args.command == 'upgrade':
            from batch_upgrade import upgrade
            result = upgrade(args.workspace, read(args.config), args.reason)
        elif args.command == 'prepare':
            m = prepare(args.workspace, args.papers, args.manifest, args.limit)
            result = {'papers': len(m['papers']), 'discovery_jobs': len(m['job_ids']), 'api_requests_sent': 0}
        elif args.command == 'estimate':
            result = estimate(args.workspace, read(args.config))
        elif args.command in {'status', 'export'}:
            result = export(args.workspace)
        else:
            if args.command == 'start' and not args.workspace.exists():
                prepare(args.workspace, args.papers, args.manifest, args.limit)
            elif args.command == 'start' and (args.papers or args.manifest):
                manifest = verify(args.workspace)
                if args.papers and args.papers[:args.limit] != [p['paper_id'] for p in manifest['papers']]:
                    raise ValueError('Resume paper selection differs from frozen workspace')
                if args.manifest and sha(args.manifest) != manifest['input_manifest_sha256']:
                    raise ValueError('Resume input manifest differs from frozen workspace')
            result = run(args.workspace, read(args.config), args.ledger, args.live, args.env_file,
                         retry_known=args.retry_known, max_new_requests=args.max_new_requests)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Provider errors are already sanitized and retained in task/ledger files.
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command in {'run', 'start'} and (result['stop_reason'] or result['failed_tasks']
            or not result['jobs'] or any(p['status'] == 'input_gap' for p in result['papers'])):
        raise SystemExit(3)


if __name__ == '__main__':
    main()
