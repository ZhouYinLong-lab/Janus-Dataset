"""Trace exact/uniquely identifiable citations; never rewrite a generated answer."""
from collections import Counter
import csv
from pathlib import Path
import pilot

HERE=Path(__file__).resolve().parent


def main():
    out=HERE/'local/trial_01'; m=pilot.verify(out); state=pilot.read(out/'state.json')
    rows=[]
    for tid in m['tasks']:
        entry=state['tasks'].get(tid,{})
        if entry.get('status')!='complete': continue
        task=pilot.read(out/f'tasks/{tid}.json')
        all_ids={x for ids in task['evidence_ids'].values() for x in ids}
        for answer in entry['answers']:
            own=task['evidence_ids'][answer['question_id']]
            for citation in answer['citations']:
                candidates=[]
                if citation in own: status='exact'; candidates=[citation]
                else:
                    candidates=[i for i in own if i.startswith(citation+':')]
                    if len(candidates)==1: status='unique_missing_window_suffix_same_question'
                    else:
                        candidates=[i for i in all_ids if i==citation or i.startswith(citation+':')]
                        status='only_other_question_same_batch' if len(candidates)==1 else 'unresolved'
                rows.append(dict(question_id=answer['question_id'],arm=task['arm'],original_citation=citation,
                                 status=status,candidate_id=';'.join(candidates)))
    with (HERE/'引用核查.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'citation_counts':dict(Counter(r['status'] for r in rows)),
             'nonexact_questions':sorted({r['question_id'] for r in rows if r['status']!='exact'}),
             'other_question_references':sorted({r['question_id'] for r in rows if r['status']=='only_other_question_same_batch'}),
             'responses_modified':False,
             'scope':'Identity tracing only. Does not establish that every factual assertion is supported.'}
    pilot.save(HERE/'citation_summary.json',summary)
    print(summary)


if __name__=='__main__':main()
