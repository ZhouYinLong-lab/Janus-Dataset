"""Offline, exhaustive body-unit jobs with bounded contextual support."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from corpus import HERE, LEGACY, existing_papers, parse_source, read, save, sha


def split_units(units,cap=7000,overlap=300):
    result=[]
    for unit in units:
        if len(unit['text'])<=cap:result.append(unit);continue
        for start in range(0,len(unit['text']),cap-overlap):
            end=min(start+cap,len(unit['text']))
            result.append(dict(unit,unit_id=unit['unit_id']+f':chars:{start}:{end}',
                               parent_unit_id=unit['unit_id'],char_start=start,char_end=end,
                               text=unit['text'][start:end]))
            if end==len(unit['text']):break
    return result


def build_jobs(document,metadata,primary_cap=10000,context_cap=18000):
    body=split_units([u for u in document['units'] if u['kind']=='body_paragraph'])
    if not body:return []
    chunks=[];current=[];size=0
    for unit in body:
        if current and size+len(unit['text'])>primary_cap:
            chunks.append(current);current=[];size=0
        current.append(unit);size+=len(unit['text'])
    if current:chunks.append(current)
    all_units=split_units(document['units'])
    jobs=[]
    for n,primary in enumerate(chunks):
        pids={u.get('parent_unit_id',u['unit_id']) for u in primary}
        primary_words=set(re.findall(r'[a-z0-9]{3,}', ' '.join(u['text'] for u in primary).lower()))
        options=[u for u in all_units if u.get('parent_unit_id',u['unit_id']) not in pids]
        def score(u):
            words=set(re.findall(r'[a-z0-9]{3,}',u['text'].lower()))
            return (-len(words&primary_words),u['unit_id'])
        options.sort(key=score)
        context=[];used=0
        for unit in options:
            if used+len(unit['text'])<=context_cap:
                context.append(unit);used+=len(unit['text'])
        canonical={'schema_version':1,'paper_id':document['paper_id'],'source_sha256':document['source_sha256'],
                   'source_path':document['source_path'],'doi':metadata.get('doi'),'title':metadata.get('title'),
                   'source_url':metadata.get('url'),'scope_basis':metadata.get('scope_basis'),
                   'scope_hypothesis':'molecular_glue_pending_source_confirmation',
                   'primary_units':primary,'context_units':context,
                   'context_omitted_units':len(options)-len(context),
                   'primary_chunk_index':n,'paper_primary_chunks':len(chunks)}
        fingerprint=hashlib.sha256(json.dumps(canonical,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        jobs.append(dict(canonical,job_id=document['paper_id']+'_'+fingerprint[:20]))
    return jobs


def prepare(out,papers=None,limit=3,custom=None):
    out=Path(out)
    if out.exists():raise ValueError('Workspace already exists; use run to resume, not prepare')
    _,metadata=existing_papers() if custom is None else ([],{m['paper_id']:m for m in read(custom)})
    if papers:
        missing=set(papers)-set(metadata)
        if missing:raise ValueError('Unknown local papers: '+','.join(sorted(missing)))
        chosen=[metadata[p] for p in papers]
    else:
        chosen=[m for m in metadata.values() if custom is not None or
                ('molecular_glue_degradation' in m['legacy_scope_groups']
                 and 'include' in m['legacy_metadata_decisions'])]
        chosen=sorted(chosen,key=lambda m:m['paper_id'])
    chosen=chosen[:limit]
    if not chosen:raise ValueError('No selected papers')
    if len({m['paper_id'] for m in chosen})!=len(chosen):raise ValueError('Duplicate paper identity')
    prompt=(HERE/'prompt.md').read_text(encoding='utf-8')
    plan={'schema_version':1,'source_prompt_sha256':sha(HERE/'prompt.md'),'papers':[], 'job_ids':[],
          'job_sha256':{},
          'coverage':'All parsed body units, including negative-free units; captions/methods contextual, no pixels or independent SI',
          'source_selection':'legacy scope flags or explicit user manifest; metadata is not expert domain confirmation',
          'source_manifest':[],'api_requests_sent':0,'expert_gold':False}
    parsed=[]
    # Parse every source before creating a workspace, so a bad source is explicit.
    for m in chosen:
        document=parse_source(m['path'],m['paper_id'])
        jobs=build_jobs(document,m)
        parsed.append((m,document,jobs))
    out.mkdir(parents=True)
    (out/'prompt.md').write_text(prompt,encoding='utf-8')
    plan['prompt_sha256']=sha(out/'prompt.md')
    for m,d,jobs in parsed:
        save(out/'documents'/f'{m["paper_id"]}.json',d)
        for job in jobs:
            save(out/'jobs'/f'{job["job_id"]}.json',job)
            plan['job_ids'].append(job['job_id'])
            plan['job_sha256'][job['job_id']]=sha(out/'jobs'/f'{job["job_id"]}.json')
        plan['papers'].append({'paper_id':m['paper_id'],'doi':m.get('doi'),'title':m.get('title'),
                               'source_sha256':d['source_sha256'],'source_path':d['source_path'],
                               'source_license':m.get('source_license'),'jobs':len(jobs),
                               'status':'prepared' if jobs else 'input_gap_no_structured_body',
                               'body_units':sum(u['kind']=='body_paragraph' for u in d['units'])})
        plan['source_manifest'].append({'paper_id':m['paper_id'],'source_sha256':d['source_sha256']})
    plan['jobs']=len(plan['job_ids'])
    save(out/'manifest.json',plan)
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--papers',nargs='+')
    p.add_argument('--limit',type=int,default=3)
    p.add_argument('--manifest',type=Path,help='Optional local JSON list of paper_id,path,doi,title,url,source_license')
    a=p.parse_args()
    if a.limit<1:p.error('--limit must be positive')
    result=prepare(a.out,a.papers,a.limit,a.manifest)
    print({'papers':len(result['papers']),'jobs':result['jobs'],'api_requests_sent':0})
