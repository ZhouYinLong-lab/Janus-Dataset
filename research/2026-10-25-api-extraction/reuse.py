"""Audit legacy negative candidates by verifiable source origin, without relabelling."""
import argparse
from collections import Counter
import csv
from pathlib import Path

from corpus import LEGACY, existing_papers, locate_quote, parse_source, save, sha


def inventory(legacy=LEGACY):
    records,papers=existing_papers(legacy)
    negatives=[r for r in records if r['negative_evidence_status']=='model_supported_scoped_negative_claim']
    parsed={}
    rows=[]
    for record in negatives:
        pid=record['paper_id']
        if pid not in parsed:
            parsed[pid]=parse_source(papers[pid]['path'],pid)
        units=parsed[pid]['units']
        result_quotes=record.get('result_evidence',[])
        matches=[locate_quote(units,x.get('quote','')) for x in result_quotes]
        kinds={m['kind'] for group in matches for m in group}
        body='body_paragraph' in kinds
        outside=bool(kinds-{'body_paragraph'})
        unresolved=not matches or any(not m for m in matches)
        origin=('unresolved' if unresolved else 'body_and_other' if body and outside
                else 'body_quote_matched' if body else 'table_or_caption_only')
        rows.append({'record_id':record['record_id'],'paper_id':pid,'doi':record.get('doi'),
                     'scope_group':record['scope_group'],'metadata_decision':record['metadata_decision'],
                     'claim_type':record['claim_type'],'origin':origin,
                     'source_match_kinds':sorted(kinds),'result_quote_matches':matches,
                     'source_sha256':parsed[pid]['source_sha256'],
                     'semantic_status':'existing_model_assisted_support_not_expert_gold',
                     'reuse':'source-linked candidate; domain and biological interpretation still require review'})
    strict=[r for r in rows if r['scope_group']=='molecular_glue_degradation' and r['metadata_decision']=='include']
    summary={'legacy_observations':len(records),'negative_candidates':len(rows),
             'papers':len(parsed),'origin_counts':dict(Counter(r['origin'] for r in rows)),
             'scope_counts':dict(Counter(r['scope_group'] for r in rows)),
             'glue_include_candidates':len(strict),'glue_include_papers':len({r['paper_id'] for r in strict}),
             'glue_include_origin_counts':dict(Counter(r['origin'] for r in strict)),
             'source_snapshot_sha256':sha(Path(legacy)/'continuation_2026-10-24/final_records.json'),
             'source_sha256':{p:d['source_sha256'] for p,d in parsed.items()},
             'expert_gold':False,
             'interpretation':'Body match establishes where a supplied quotation occurs; not narrative uniqueness, complete coverage, semantic correctness or database novelty.'}
    return rows,summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy',type=Path,default=LEGACY)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('Choose a new output directory; preserve old inventory')
    rows,summary=inventory(args.legacy)
    save(args.out/'summary.json',summary)
    save(args.out/'records.json',rows)
    columns=['record_id','paper_id','doi','scope_group','metadata_decision','claim_type','origin']
    with (args.out/'records.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    print({k:v for k,v in summary.items() if k not in {'source_sha256'}})


if __name__=='__main__':main()
