"""Explicit opt-in inference, persistent attempts, bounded spend and safe resume."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import time

from api import HTTPClient,RequestFailure,check_config,make_request,parse_completion,reserve_tokens
from contract import validate
from corpus import HERE,read,save,sha
from credentials import load_key


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def verify_workspace(workspace):
    workspace=Path(workspace)
    manifest=read(workspace/'manifest.json')
    if sha(workspace/'prompt.md')!=manifest['prompt_sha256']:raise ValueError('Frozen prompt changed')
    if len(manifest['job_ids'])!=len(set(manifest['job_ids'])):raise ValueError('Duplicate job identity')
    for jid in manifest['job_ids']:
        if not jid or Path(jid).name!=jid or '/' in jid or '\\' in jid:raise ValueError('Invalid job filename')
        path=workspace/'jobs'/f'{jid}.json'
        if sha(path)!=manifest['job_sha256'][jid]:raise ValueError('Frozen job changed: '+jid)
    for paper in manifest['papers']:
        if sha(paper['source_path'])!=paper['source_sha256']:raise ValueError('Source changed: '+paper['paper_id'])
    return manifest


@contextmanager
def lock(workspace):
    path=Path(workspace)/'.run.lock'
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps({'pid':os.getpid(),'created':time.time()}))
    try:yield
    finally:path.unlink()


def status(workspace):
    workspace=Path(workspace)
    manifest=verify_workspace(workspace)
    state=read(workspace/'state.json') if (workspace/'state.json').exists() else {'attempts':[],'jobs':{}}
    counts={}
    for jid in manifest['job_ids']:
        key=state['jobs'].get(jid,{}).get('status','pending')
        counts[key]=counts.get(key,0)+1
    return {'jobs':len(manifest['job_ids']),'job_status':counts,'requests_reserved':len(state['attempts']),
            'stop_reason':state.get('stop_reason'),
            'completion_status':('no_jobs' if not manifest['job_ids'] else 'processed'
                if sum(counts.get(k,0) for k in ['complete','complete_with_quarantine'])==len(manifest['job_ids'])
                else 'incomplete'),
            'reserved_token_estimate':sum(a['reserved_tokens'] for a in state['attempts']),
            'reported_usage':[a.get('usage') for a in state['attempts']],
            'source_input_gaps':[p['paper_id'] for p in manifest['papers'] if not p['jobs']],
            'billing_notice':'Reserved units are estimates, not a guaranteed currency cap; provider account caps control billing.'}


def run(workspace,config,live=False,retry_failed=False,client=None,env_file=None,job_ids=None):
    if not live:raise ValueError('No request sent: use --live explicitly after checking plan and provider')
    check_config(config)
    workspace=Path(workspace)
    manifest=verify_workspace(workspace)
    if job_ids is not None and (not job_ids or len(job_ids)!=len(set(job_ids)) or
                                set(job_ids)-set(manifest['job_ids'])):
        raise ValueError('Selected job IDs must be unique known jobs')
    prompt=(workspace/'prompt.md').read_text(encoding='utf-8')
    identity=fingerprint({'request_config':{k:v for k,v in config.items() if k not in {'max_requests','max_reserved_tokens'}},
        'manifest_sha256':sha(workspace/'manifest.json'),
        'code_sha256':{name:sha(HERE/name) for name in ['api.py','runner.py','contract.py','corpus.py','credentials.py']}})
    with lock(workspace):
        path=workspace/'state.json'
        state=read(path) if path.exists() else {'identity':identity,
            'request_config':{k:v for k,v in config.items() if k not in {'max_requests','max_reserved_tokens'}},
            'attempts':[],'jobs':{}}
        if state['identity']!=identity:raise ValueError('Model/config/code changed; use a new prepared workspace')
        if any(a['status']=='in_flight' for a in state['attempts']):
            raise ValueError('Interrupted in-flight request may have been billed. Inspect state; no automatic resend')
        if client is None:
            key=load_key(config['api_key_env'],env_file)
            client=HTTPClient(config,key)
        else:key=''  # Dependency injection is for local tests only, never a CLI transport choice.
        for jid in manifest['job_ids']:
            if job_ids is not None and jid not in job_ids:continue
            old=state['jobs'].get(jid,{})
            if old.get('status') in {'complete','complete_with_quarantine'}:
                if sha(workspace/old['result_path'])!=old['result_sha256']:
                    raise ValueError('Stored result changed; inspect before resume')
                continue
            if old and (old.get('status')=='needs_attention' or not retry_failed):continue
            job=read(workspace/'jobs'/f'{jid}.json')
            request=make_request(job,prompt,config)
            reserved=reserve_tokens(request,config)
            if (len(state['attempts'])>=config['max_requests'] or
                sum(a['reserved_tokens'] for a in state['attempts'])+reserved>config['max_reserved_tokens']):
                state['stop_reason']='budget_limit';save(path,state);break
            attempt={'job_id':jid,'attempt':len(state['attempts'])+1,'reserved_tokens':reserved,
                     'requested_model':config['model'],
                     'budget_caps_at_send':{k:config[k] for k in ['max_requests','max_reserved_tokens']},
                     'status':'in_flight','started':time.time()}
            state['attempts'].append(attempt)
            state['jobs'][jid]={'status':'in_flight'}
            # Persist reservation BEFORE sending; crashes must never silently reissue a paid call.
            save(path,state)
            try:
                envelope=client.complete(request)
                if key:
                    envelope=json.loads(json.dumps(envelope,ensure_ascii=False).replace(key,'[REDACTED]'))
                response_path=Path('responses')/f'{attempt["attempt"]:06d}_{jid}.json'
                save(workspace/response_path,envelope)
                if isinstance(envelope,dict):
                    usage=envelope.get('usage')
                    attempt['usage']=usage if isinstance(usage,dict) else None
                    attempt['returned_model']=envelope.get('model')
                payload=parse_completion(envelope)
                checked=validate(payload,job)
                result_path=Path('results')/f'{jid}.json'
                save(workspace/result_path,{'job_id':jid,'request_identity':identity,
                    'response_path':response_path.as_posix(),'response_sha256':sha(workspace/response_path),
                    'source_sha256':job['source_sha256'],**checked})
                job_status='complete_with_quarantine' if checked['rejected'] else 'complete'
                state['jobs'][jid]={'status':job_status,'result_path':result_path.as_posix(),
                    'result_sha256':sha(workspace/result_path),'accepted':len(checked['accepted']),
                    'rejected':len(checked['rejected'])}
                attempt['status']=job_status
                state.pop('stop_reason',None)
            except RequestFailure as exc:
                attempt.update(status='needs_attention' if exc.ambiguous else 'failed',
                               error=exc.kind,http_status=exc.http_status)
                state['jobs'][jid]={'status':attempt['status'],'error':exc.kind,'http_status':exc.http_status}
                state['stop_reason']='request_failure_no_auto_retry'
            except (ValueError,KeyError,TypeError) as exc:
                # Do not expose a provider's content or credentials via exception messages.
                attempt.update(status='failed',error='response_or_contract_invalid',exception_type=type(exc).__name__)
                state['jobs'][jid]={'status':'failed','error':'response_or_contract_invalid'}
                state['stop_reason']='invalid_response_no_auto_retry'
            attempt['finished']=time.time()
            save(path,state)
            print(json.dumps({'job_id':jid,'status':attempt['status'],
                              'requests_reserved':len(state['attempts'])}),flush=True)
            if attempt['status'] in {'failed','needs_attention'}:break
    return status(workspace)
