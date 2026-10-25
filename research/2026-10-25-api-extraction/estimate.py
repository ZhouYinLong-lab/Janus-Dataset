"""Inspect request volume and conservative token reservations without a key or network."""
from pathlib import Path
from api import make_request,reserve_tokens
from corpus import read
from runner import verify_workspace


def estimate(workspace,config):
    workspace=Path(workspace)
    manifest=verify_workspace(workspace)
    prompt=(workspace/'prompt.md').read_text(encoding='utf-8')
    state=read(workspace/'state.json') if (workspace/'state.json').exists() else {'jobs':{},'attempts':[]}
    rows=[]
    for jid in manifest['job_ids']:
        job=read(workspace/'jobs'/f'{jid}.json')
        request=make_request(job,prompt,config)
        rows.append({'job_id':jid,'paper_id':job['paper_id'],
                     'estimated_reserved_tokens':reserve_tokens(request,config),
                     'status':state['jobs'].get(jid,{}).get('status','pending')})
    pending=[r for r in rows if r['status']=='pending']
    return {'api_requests_sent':0,'credentials_read':False,'papers':len(manifest['papers']),
            'jobs':len(rows),'pending_jobs':len(pending),'configured_lifetime_request_cap':config['max_requests'],
            'configured_lifetime_reserved_token_cap':config['max_reserved_tokens'],
            'total_estimated_reservation_all_jobs':sum(r['estimated_reserved_tokens'] for r in rows),
            'largest_job_estimate':max((r['estimated_reserved_tokens'] for r in rows),default=0),
            'previous_request_reservations':len(state['attempts']),
            'jobs_detail':rows,
            'notice':'Reservation = UTF8 input bytes+2048 overhead+requested output tokens. This is a conservative planning estimate, not exact tokens or a guaranteed billing cap. Configure provider-side currency limits.'}
