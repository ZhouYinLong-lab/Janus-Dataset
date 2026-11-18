"""Summarize explicit assistant judgments without editing generated responses."""
import csv
import json
from pathlib import Path
import pilot

HERE=Path(__file__).resolve().parent


def main():
    out=HERE/'local/trial_01'; pilot.export(out)
    answers=pilot.read(out/'answers.json'); grades=pilot.read(HERE/'manual_judgments.json')
    questions={q['id']:q for p in pilot.read(HERE/'reviewed_cases.json') for q in p['questions']}
    lookup={(g['question_id'],g['arm']):g for g in grades}
    assert len(lookup)==len(grades), 'Duplicate judgments'
    rows=[]
    for a in answers:
        if not a['response']: continue
        g=lookup.pop((a['question_id'],a['arm']))
        assert len(g['points'])==2 and all(type(x) is int and x in (0,1) for x in g['points'])
        assert type(g['overclaim']) is bool and g['reason'].strip()
        q=questions[a['question_id']]
        rows.append(dict(question_id=a['question_id'],paper_id=a['paper_id'],arm=a['arm'],kind=q['kind'],
                         point1=g['points'][0],point2=g['points'][1],score=sum(g['points']),
                         overclaim=g['overclaim'],fully_correct=sum(g['points'])==2 and not g['overclaim'],
                         citation_ids_valid=a['status']=='complete',reason=g['reason']))
    assert not lookup, 'Unmatched judgments'
    subsets={'all':set(questions),'generic_processed':{q for q in questions if q[1:4] in ('204','209','236')},
             'generic_cohort_unconfirmed':{q for q in questions if q[1:4] in ('251','280')},
             'audited_missing_content':{'Q209A','Q209D','Q236A','Q236D'},
             'core_degradation_missing_content':{'Q209A','Q236A'}}
    summary={}
    for label,qids in subsets.items():
        paired={qid for qid in qids if all(any(r['question_id']==qid and r['arm']==a for r in rows) for a in pilot.ARMS)}
        summary[label]={'paired_questions':len(paired),'arms':{}}
        for arm in pilot.ARMS:
            selected=[r for r in rows if r['question_id'] in paired and r['arm']==arm]
            summary[label]['arms'][arm]={'score':sum(r['score'] for r in selected),'max_score':2*len(paired),
                'fully_correct':sum(r['fully_correct'] for r in selected),'overclaim':sum(r['overclaim'] for r in selected),
                'valid_citation_ids':sum(r['citation_ids_valid'] for r in selected)}
    with (HERE/'逐题评分.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    ledger=pilot.read(pilot.CORE/'local/round_01_budget.json')
    attempts=[a for a in ledger['attempts'] if a['workspace']==str(out.resolve())]
    result={'graded':True,'subsets':summary,'trial_attempts':len(attempts),
            'all_available_by_arm':{arm:{'answers':sum(r['arm']==arm for r in rows),
                'score':sum(r['score'] for r in rows if r['arm']==arm),
                'overclaim':sum(r['overclaim'] for r in rows if r['arm']==arm),
                'valid_citation_ids':sum(r['citation_ids_valid'] for r in rows if r['arm']==arm)} for arm in pilot.ARMS},
            'reported_trial_tokens':sum(a.get('usage',{}).get('total_tokens',0) for a in attempts if isinstance(a.get('usage'),dict)),
            'trial_attempts_without_usage':sum(not isinstance(a.get('usage'),dict) for a in attempts),
            'trial_reserved_tokens':sum(a['reserved_tokens'] for a in attempts),
            'budget_after':pilot.budget.status(pilot.CORE/'local/round_01_budget.json'),
            'response_hashes':{a['task']:pilot.sha(out/f'responses/{a["task"]}.json') for a in attempts if (out/f'responses/{a["task"]}.json').exists()},
            'grading':'Non-blind assistant review of fixed development rubrics; no expert gold or uncertainty significance claim.'}
    pilot.save(HERE/'results_summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='response_hashes'},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
