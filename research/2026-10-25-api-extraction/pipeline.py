"""CLI: prepare offline, inspect status, explicitly run API, export local results."""
import argparse
from pathlib import Path
from corpus import read
from export import export
from estimate import estimate
from prepare import prepare
from runner import run,status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    prep=commands.add_parser('prepare',help='Offline; no credentials or API calls')
    prep.add_argument('--out',type=Path,required=True)
    prep.add_argument('--papers',nargs='+')
    prep.add_argument('--limit',type=int,default=3)
    prep.add_argument('--manifest',type=Path)
    for name in ['status','run','export','estimate']:
        cmd=commands.add_parser(name)
        cmd.add_argument('--workspace',type=Path,required=True)
        if name in {'run','estimate'}:
            cmd.add_argument('--config',type=Path,required=True)
        if name=='run':
            cmd.add_argument('--live',action='store_true',help='Explicit authorization to send charged provider requests')
            cmd.add_argument('--retry-failed',action='store_true',help='Explicitly retry known failures; counts against lifetime workspace budget')
    args=parser.parse_args()
    try:
        if args.command=='prepare':
            if args.limit<1:raise ValueError('--limit must be positive')
            p=prepare(args.out,args.papers,args.limit,args.manifest)
            result={'papers':len(p['papers']),'jobs':p['jobs'],'api_requests_sent':0}
        elif args.command=='status':result=status(args.workspace)
        elif args.command=='export':result=export(args.workspace)
        elif args.command=='estimate':result=estimate(args.workspace,read(args.config))
        else:result=run(args.workspace,read(args.config),args.live,args.retry_failed)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,f'{type(exc).__name__}: {exc}\n')
    import json
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.command=='run' and any(result['job_status'].get(k,0) for k in ['failed','needs_attention','in_flight']):
        parser.exit(3,'Some requests need inspection; results retained, no automatic retry.\n')


if __name__=='__main__':main()
