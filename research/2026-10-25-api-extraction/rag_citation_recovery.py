"""Separate QA analysis copy: recover unambiguous citation formatting only."""
import argparse
import json
from pathlib import Path

from api import parse_completion
from corpus import read, save
from rag_trial import export


def repair(envelope, task):
    payload = parse_completion(envelope)
    if (not isinstance(payload, dict) or set(payload) != {'answer', 'citations', 'uncertainty'}
            or not isinstance(payload['answer'], str) or not payload['answer'].strip()
            or not isinstance(payload['uncertainty'], str) or not isinstance(payload['citations'], list)
            or any(not isinstance(c, str) for c in payload['citations'])):
        raise ValueError('Not a citation-only format failure')
    changes = []
    citations = []
    if payload['citations'] == ['[]'] and not task['evidence_ids']:
        return dict(payload, citations=[]), [{'from': ['[]'], 'to': [], 'rule': 'empty_evidence_literal_empty_array'}]
    for cite in payload['citations']:
        if cite in task['evidence_ids']:
            citations.append(cite)
            continue
        matches = [eid for eid in task['evidence_ids']
                   if eid.startswith('raw:') and eid.rsplit(':', 2)[0] == cite]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous supplied chunk identity')
        citations.append(matches[0]); changes.append({'from': cite, 'to': matches[0]})
    return dict(payload, citations=citations), changes


def recover(workspace, out):
    workspace, out = Path(workspace), Path(out)
    if out.exists():
        raise ValueError('Use a new analysis directory; preserve prior outputs')
    export(workspace)  # verifies frozen inputs, code and stored response hashes
    state = read(workspace / 'state.json')
    answers = read(workspace / 'answers.json')
    questions = {q['id']: q for q in read(workspace / 'questions.json')['questions']}
    blind = []; repaired_count = 0
    for a in answers:
        a['original_status'] = a['status']; a['citation_repairs'] = []
        if a['status'] == 'invalid_response':
            task = read(workspace / f'tasks/{a["task_id"]}.json')
            entry = state['tasks'][a['task_id']]
            try:
                payload, changes = repair(read(workspace / entry['response_path']), task)
            except (ValueError, KeyError, TypeError):
                continue
            if not changes:
                continue
            a.update(status='complete', answer=payload, citation_repairs=changes)
            repaired_count += 1
        if a['status'] == 'complete':
            q = questions[a['question_id']]
            blind.append({'blind_id': a['blind_id'], 'question_id': q['id'],
                          'question': q['question'], 'rubric': q['rubric'], 'split': q['split'],
                          'answer': a['answer']['answer'], 'uncertainty': a['answer']['uncertainty']})
    save(out / 'answers.json', answers)
    save(out / 'blind_answers.json', sorted(blind, key=lambda a: a['blind_id']))
    save(out / 'grading_reference.json', read(workspace / 'grading_reference.json'))
    summary = {'strict_complete': sum(a['original_status'] == 'complete' for a in answers),
               'citation_alias_recovered': repaired_count, 'analysis_complete': len(blind),
               'planned': len(answers), 'generation_requests': 0, 'originals_unchanged': True,
               'scope': 'Unique supplied raw unit alias to chunk, or literal ["[]"] to [] when no '
                        'evidence was supplied; no new citations, answer '
                        'rewriting or semantic validation. Strict and recovered counts reported separately.'}
    save(out / 'recovery_summary.json', summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True); p.add_argument('--out', required=True)
    args = p.parse_args()
    print(json.dumps(recover(args.workspace, args.out), ensure_ascii=False, indent=2))
