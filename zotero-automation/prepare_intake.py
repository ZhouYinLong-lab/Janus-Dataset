"""Resolve a public reading manifest and stage evidence; never write Zotero DB."""
import csv, hashlib, html, json, re, shutil, time, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
import fitz

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / 'zotero-automation'
OUT = ROOT / 'research/reading_route'
SEEDS = AUTO / 'inputs/incoming/2026-09-06-janus-seeds.json'
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest'

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def get(url, **kwargs):
    prepared=requests.Request('GET',url,params=kwargs.get('params')).prepare().url
    with tempfile.TemporaryDirectory(prefix='janus-fetch-') as tmp:
        dest=Path(tmp)/'response'
        fetched=subprocess.run(['pwsh','-NoProfile','-File',str(AUTO/'fetch.ps1'),'-Url',prepared,'-Destination',str(dest)],capture_output=True,timeout=45)
        if fetched.returncode==0 and dest.exists():
            response=requests.Response(); response.status_code=200; response._content=dest.read_bytes()
            return response
    raise requests.RequestException('Public source could not be fetched: '+prepared)

def process(seed):
    entry = dict(seed)
    cache = OUT / 'metadata' / (seed['order'] + '.json')
    try:
        if cache.exists(): hit = json.loads(cache.read_text(encoding='utf-8'))
        else:
            query = 'DOI:' + seed['doi'] if seed.get('doi') else 'TITLE:"' + seed['title'] + '"'
            hits = get(EPMC+'/search', params={'query':query,'format':'json','resultType':'core'}).json()['resultList']['result']
            if not hits: raise ValueError('No verified metadata match')
            hit = hits[0]
            if seed.get('doi') and hit.get('doi','').lower() != seed['doi'].lower(): raise ValueError('DOI mismatch')
            if seed.get('title') and re.sub(r'\W','',seed['title']).lower() != re.sub(r'\W','',hit['title']).lower(): raise ValueError('Title mismatch')
            save(cache, hit)
        entry.update(title=hit['title'].rstrip('.'), DOI=hit['doi'], year=hit['pubYear'],
            itemType='journalArticle', publicationTitle=hit['journalInfo']['journal']['title'],
            volume=hit['journalInfo'].get('volume',''), issue=hit['journalInfo'].get('issue',''),
            pages=hit.get('pageInfo',''), url='https://doi.org/'+hit['doi'],
            creators=[{'firstName':a.get('firstName',''),'lastName':a.get('lastName',a.get('fullName','')),'creatorType':'author'} for a in hit['authorList']['author']],
            abstractNote=re.sub('<[^>]+>','',hit.get('abstractText','')), pmcid=hit.get('pmcid',''),
            collection_path='Janus｜小分子生物活性阴性证据/'+seed['group'], review_required=False,
            evidence=['Europe PMC verified DOI metadata','publisher abstract'], license=hit.get('license','not verified'))
        pdf = AUTO / 'staging' / (seed['order']+'.pdf')
        pdf.parent.mkdir(parents=True,exist_ok=True)
        candidates = [u['url'] for u in hit.get('fullTextUrlList',{}).get('fullTextUrl',[]) if u.get('documentStyle')=='pdf' and u.get('availabilityCode') in ('OA','F')]
        # Existing, source-verified local PDFs are reusable without another download.
        for matrix in (ROOT/'research/value_assessment').glob('*/evidence.csv'):
            for row in csv.DictReader(matrix.open(encoding='utf-8-sig')):
                if hit['doi'].lower() in row['doi_or_url'].lower() and row.get('local_copy'):
                    source = (matrix.parent / row['local_copy']).resolve()
                    if source.exists() and not pdf.exists(): shutil.copy2(source,pdf)
        if not pdf.exists():
            for url in candidates:
                try:
                    body=get(url).content
                    if not body.startswith(b'%PDF'): continue
                    with fitz.open(stream=body,filetype='pdf') as check: assert len(check)>0
                    pdf.write_bytes(body)
                    entry['pdf_url']=url
                    break
                except Exception: continue
        # Save available OA XML as a separately traceable source for supplementary links.
        if hit.get('isOpenAccess')=='Y' and hit.get('pmcid'):
            xml=OUT/'fulltext'/f"{seed['order']}.xml"
            if not xml.exists():
                try:
                    data=get(EPMC+'/'+hit['pmcid']+'/fullTextXML').content
                    if b'<article' in data: xml.parent.mkdir(parents=True,exist_ok=True); xml.write_bytes(data)
                except Exception: pass
        locators=[]
        if pdf.exists():
            with fitz.open(pdf) as doc:
                for term in seed['terms']:
                    found=[]
                    for n,page in enumerate(doc):
                        if page.search_for(term): found.append(n+1)
                    if found: locators.append({'term':term,'pdf_pages':found[:8]})
            entry['staged_pdf']='staging/'+pdf.name
            entry['pdf_sha256']=hashlib.sha256(pdf.read_bytes()).hexdigest()
            entry['evidence'].append('local PDF keyword locations; not exhaustive full-text review')
        entry['locators']=locators
        print(seed['order'],entry['title'], 'PDF='+str(pdf.exists()),flush=True)
    except Exception as exc:
        entry.update(review_required=True,error=type(exc).__name__+': '+str(exc))
        print(seed['order'],'NEEDS_REVIEW',entry['error'],flush=True)
    return entry

if __name__=='__main__':
    seeds=json.loads(SEEDS.read_text(encoding='utf-8'))
    entries=list(ThreadPoolExecutor(3).map(process,seeds))
    save(AUTO/'inputs/incoming/2026-09-06-janus.json',entries)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'literature-matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['order','group','alias','title','year','DOI','reason','focus','question','caution','review_required']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(entries)
    print('MANIFEST',len(entries),'NEEDS_REVIEW',sum(e['review_required'] for e in entries),flush=True)
