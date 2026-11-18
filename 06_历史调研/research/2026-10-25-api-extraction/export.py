"""Export grounded candidates separately from quarantine, risks and incomplete coverage."""
from collections import Counter
import csv
import json
from pathlib import Path

from corpus import read,save
from runner import verify_workspace


def safe_cell(value):
    if isinstance(value,(list,dict)):value=json.dumps(value,ensure_ascii=False)
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value


def export(workspace):
    workspace=Path(workspace)
    manifest=verify_workspace(workspace)
    state=read(workspace/'state.json') if (workspace/'state.json').exists() else {'jobs':{}}
    unique={};quarantine=[];paper_status=[]
    for jid in manifest['job_ids']:
        entry=state['jobs'].get(jid,{})
        if entry.get('status') not in {'complete','complete_with_quarantine'}:continue
        from corpus import sha
        if sha(workspace/entry['result_path'])!=entry['result_sha256']:raise ValueError('Result integrity mismatch')
        result=read(workspace/entry['result_path'])
        quarantine.extend(dict(r,job_id=jid) for r in result['rejected'])
        for record in result['accepted']:
            if record['record_key'] not in unique:
                unique[record['record_key']]=dict(record,provenance=[{'job_id':jid,'evidence':record['evidence']}])
            else:unique[record['record_key']]['provenance'].append({'job_id':jid,'evidence':record['evidence']})
    records=list(unique.values())
    for p in manifest['papers']:
        jobs=[j for j in manifest['job_ids'] if read(workspace/'jobs'/f'{j}.json')['paper_id']==p['paper_id']]
        completed=sum(state['jobs'].get(j,{}).get('status') in {'complete','complete_with_quarantine'} for j in jobs)
        rejected=sum(state['jobs'].get(j,{}).get('rejected',0) for j in jobs)
        paper_status.append({'paper_id':p['paper_id'],'jobs':len(jobs),'completed':completed,'quarantined':rejected,
            'status':'input_gap' if not jobs else 'partial' if completed<len(jobs)
                     else 'processed_with_quarantine' if rejected else 'processed_not_semantically_reviewed'})
    out=workspace/'exports'
    save(out/'records.json',records)
    save(out/'primary_candidates.json',[r for r in records if r['primary_candidate']])
    save(out/'other_or_risk_records.json',[r for r in records if not r['primary_candidate']])
    save(out/'quarantine.json',quarantine)
    columns=['record_key','paper_id','doi','domain','negative_type','experimental_setting',
             'compound','target','construct','assay','cell_line','treatment_time','tested_concentration',
             'perturbation','endpoint','result_text','qualifiers','evidence','semantic_review','ready_for_training']
    out.mkdir(parents=True,exist_ok=True)
    with (out/'records.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for r in records:
            writer.writerow({k:safe_cell(v) for k,v in dict(r,**r['fields']).items() if k in columns})
    summary={'unique_records':len(records),'primary_candidates':sum(r['primary_candidate'] for r in records),
             'quarantined_records':len(quarantine),'domain_counts':dict(Counter(r['domain'] for r in records)),
             'papers':paper_status,'expert_gold':False,'training_ready_records':0,
             'interpretation':'Body quote-grounded model candidates; not verified biological negatives, table-unique facts or downstream gains'}
    save(out/'summary.json',summary)
    return summary
