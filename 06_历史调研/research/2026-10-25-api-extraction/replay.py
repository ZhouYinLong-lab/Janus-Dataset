"""Exercise the pipeline with legacy evidence fixtures. NOT a model extraction evaluation."""
import argparse
from collections import Counter
import json
from pathlib import Path

from api import make_request,reserve_tokens
from contract import FIELDS
from corpus import HERE,LEGACY,locate_quote,read,save
from export import export
from prepare import prepare
from runner import run,status

CASES={'B013_004':('conditional_loss','special_condition','author_inferred'),
       'B022_010':('no_degradation','unperturbed','explicit'),
       'B043_004':('conditional_loss','special_condition','explicit'),
       'B046_010':('response_not_detected','unperturbed','explicit')}
OLD_FIELDS={'assay':'assay','cell_line':'cell_line','treatment_time':'treatment_time',
            'tested_concentration_range':'tested_concentration'}


def fixture_for(old,job):
    units=job['primary_units']+job['context_units']
    primary_ids={u['unit_id'] for u in job['primary_units']}
    results=[]
    for e in old['result_evidence']:
        hits=locate_quote(units,e['quote'])
        if not hits:return None
        chosen=next((h for h in hits if h['unit_id'] in primary_ids),hits[0])
        results.append({'field':'result_text','unit_id':chosen['unit_id'],'quote':e['quote']})
    if not any(e['unit_id'] in primary_ids for e in results):return None
    fields={f:None for f in FIELDS}
    fields.update(compound=old['compound'],target=old['target'],endpoint=old['endpoint'],
                  result_text='; '.join(e['quote'] for e in old['result_evidence']))
    evidence=list(results)
    unit=next(u for u in units if u['unit_id']==results[0]['unit_id'])
    # Full original result paragraph supplies the contextual entity names in this fixture.
    for f in ['compound','target','endpoint']:
        evidence.append({'field':f,'unit_id':unit['unit_id'],'quote':unit['text'][:3000]})
    for e in old.get('condition_evidence',[]):
        old_field=e.get('field');field=OLD_FIELDS.get(old_field)
        if not field or not old.get(old_field):continue
        hits=locate_quote(units,e['quote'])
        if hits:
            fields[field]=old[old_field]
            evidence.append({'field':field,'unit_id':hits[0]['unit_id'],'quote':e['quote']})
    kind,setting,directness=CASES[old['record_id']]
    return {'domain':'molecular_glue','negative_type':kind,'experimental_setting':setting,
            'directness':directness,'fields':fields,'evidence':evidence,
            'qualifiers':old.get('uncertainties',[])+['Offline legacy fixture, not a fresh model response; semantic review pending.']}


class ReplayClient:
    def __init__(self,workspace):
        self.workspace=workspace
        self.jobs=[read(p) for p in (workspace/'jobs').glob('*.json')]
        self.old=[r for r in read(LEGACY/'continuation_2026-10-24/final_records.json')['records']
                  if r['record_id'] in CASES]
        self.matched=set()

    def complete(self,request):
        evidence=json.loads(request['messages'][1]['content'])
        job=next(j for j in self.jobs if j['paper_id']==evidence['paper_id']
                 and j['primary_chunk_index']==evidence['primary_chunk_index'])
        records=[]
        for old in self.old:
            if old['paper_id']!=job['paper_id']:continue
            record=fixture_for(old,job)
            if record is not None:
                records.append(record);self.matched.add(old['record_id'])
        result={'schema_version':1,'paper_id':job['paper_id'],'records':records,
                'coverage_notes':['Replay only supplies four predetermined legacy cases; it does not search for other negatives.'],
                'no_negative_reason':None if records else 'No assigned replay fixture in these units; NOT evidence of absence.'}
        return {'model':'offline-replay-no-inference','choices':[{'finish_reason':'stop',
                'message':{'content':json.dumps(result,ensure_ascii=False)}}]}


def replay(workspace):
    prepare(workspace,papers=['B013','B022','B043','B046'],limit=4)
    cfg=read(HERE/'config.example.json')
    cfg.update(base_url='https://offline-replay.invalid/v1',model='offline-replay-no-inference',
               max_requests=1000,max_reserved_tokens=100_000_000)
    client=ReplayClient(workspace)
    run(workspace,cfg,live=True,client=client)
    result=export(workspace)
    checks={'mode':'offline_legacy_replay_not_model_inference','paid_api_requests':0,
            'expected_legacy_cases':sorted(CASES),'matched_legacy_cases':sorted(client.matched),
            'matched_all_cases':client.matched==set(CASES),
            'jobs_processed':status(workspace)['completion_status'],
            'export_summary':result,
            'interpretation':'Tests preparation, response parsing, grounding, resume/export with existing cases; does not measure new extraction precision or recall.'}
    save(workspace/'replay_summary.json',checks)
    if not checks['matched_all_cases'] or result['quarantined_records']:
        raise ValueError('Replay did not preserve all fixed cases without mechanical errors')
    return checks


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=replay(a.out)
    print(json.dumps(r,ensure_ascii=False,indent=2))
