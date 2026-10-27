"""Blinded source-based QA judging and paired utility reports, including failures."""
import argparse
from collections import defaultdict
from pathlib import Path
import random

from common import digest, doi, fresh, read, seal, sha, verify, write


def complete_denominator(trial):
    tasks = {t['task_id']: t for t in read(Path(trial) / 'tasks.json')}
    received = {}
    for a in read(Path(trial) / 'exports/answers.json'):
        if a['task_id'] not in tasks or a['task_id'] in received:
            raise ValueError('Unexpected/duplicate answer task')
        expected = tasks[a['task_id']]
        if any(a[k] != expected[k] for k in ('question_id', 'arm')):
            raise ValueError('Answer identity differs from frozen task')
        received[a['task_id']] = a
    return [received.get(tid, {k: t[k] for k in ('task_id', 'question_id', 'arm')} |
                        {'status': 'missing', 'result': None, 'response_sha256': None})
            for tid, t in tasks.items()]


def make_packet(trial, out, seed=71):
    verify(trial)
    trial = Path(trial)
    questions = {q['question_id']: q for q in read(trial / 'questions.json')}
    tasks = {t['task_id']: t for t in read(trial / 'tasks.json')}
    answers = complete_denominator(trial)
    shuffled = [a for a in answers if a['status'] == 'complete']
    random.Random(seed).shuffle(shuffled)
    packet, key = [], []
    for i, a in enumerate(shuffled):
        q, task = questions[a['question_id']], tasks[a['task_id']]
        judge_id = 'blind_' + str(i + 1).zfill(5)
        packet.append({'judge_id': judge_id, 'question': q['question'], 'rubric': q['rubric'],
                       'reference_answer': q.get('reference_answer'),
                       'reference_evidence': q.get('reference_evidence', []),
                       'supplied_request': task['messages'][-1]['content'], 'answer': a['result'],
                       'judgment': {'criteria': {c['id']: None for c in q['rubric']},
                                    'overclaim': None, 'citation_supported': None,
                                    'judge': '', 'reason': ''}})
        key.append({'judge_id': judge_id, 'task_id': a['task_id'], 'question_id': a['question_id'],
                    'arm': a['arm'], 'answer_sha256': digest(a), 'response_sha256': a['response_sha256']})
    out = fresh(out)
    write(out / 'blinded_packet.json', packet)
    write(out / 'private_key.json', key)
    seal(out, [trial / 'manifest.json', trial / 'exports/answers.json'],
         {'artifact': 'blinded_qa_packet', 'complete_answers': len(packet), 'seed': seed})
    return {'answers_to_judge': len(packet), 'judge_instructions': 'Edit a copy, keep private_key away from judges.'}


def score(trial, packet, judgments, out, bootstrap=2000):
    verify(trial)
    verify(packet)
    trial, packet = Path(trial), Path(packet)
    questions = {q['question_id']: q for q in read(trial / 'questions.json')}
    keys = {r['judge_id']: r for r in read(packet / 'private_key.json')}
    answers = complete_denominator(trial)
    by_task = {a['task_id']: a for a in answers}
    judgments = Path(judgments)
    judged, seen = {}, set()
    for r in read(judgments):
        jid = r['judge_id']
        if jid not in keys or jid in seen:
            raise ValueError('Unexpected/duplicate judgment')
        seen.add(jid)
        key = keys[jid]
        if digest(by_task[key['task_id']]) != key['answer_sha256']:
            raise ValueError('Answers changed since judging packet')
        j, q = r['judgment'], questions[key['question_id']]
        if (set(j['criteria']) != {c['id'] for c in q['rubric']} or
                any(type(v) is not bool for v in j['criteria'].values()) or
                type(j['overclaim']) is not bool or type(j['citation_supported']) is not bool or
                not j.get('judge') or not j.get('reason')):
            raise ValueError('Unfinished judgment/criteria/judge/reason')
        judged[key['task_id']] = j
    groups, doi_owners = {}, {}
    for qid, q in questions.items():
        group = q.get('evaluation_group')
        if not group:
            raise ValueError('Every question needs an explicit evaluation_group')
        groups[qid] = group
        for d in q['source_dois']:
            d = doi(d)
            if d in doi_owners and doi_owners[d] != group:
                raise ValueError('Shared source DOI split across evaluation groups')
            doi_owners[d] = group
    rows = []
    arms = sorted({a['arm'] for a in answers})
    for a in answers:
        q, j = questions[a['question_id']], judged.get(a['task_id'])
        value = sum(j['criteria'].values()) / len(q['rubric']) if j else 0.
        rows.append(dict(a, score=value, judged=j is not None,
                         overclaim=j['overclaim'] if j else None,
                         citation_supported=j['citation_supported'] if j else None,
                         evaluation_group=groups[a['question_id']],
                         split=q['split'], protocol=q['protocol'], gold_status=q['gold_status']))
    reports = {}
    # Test/development and lookup/new-combination are never pooled.
    for split, protocol in sorted({(r['split'], r['protocol']) for r in rows}):
        subset = [r for r in rows if (r['split'], r['protocol']) == (split, protocol)]
        scores = {(r['question_id'], r['arm']): r for r in subset}
        report = {}
        for arm in arms:
            rs = [r for r in subset if r['arm'] == arm]
            js = [r for r in rs if r['judged']]
            report[arm] = {'expected': len(rs), 'complete': sum(r['status'] == 'complete' for r in rs),
                           'judged': len(js), 'missing_or_unjudged': len(rs) - len(js),
                           'score_all_expected': sum(r['score'] for r in rs) / len(rs) if rs else None,
                           'overclaim_rate_judged': sum(r['overclaim'] for r in js) / len(js) if js else None,
                           'citation_support_rate_judged': sum(r['citation_supported'] for r in js) / len(js) if js else None}
        comparisons = {}
        pairs = [('recovered', left) for left in ('structured', 'raw', 'background_ablation')]
        pairs += [('balanced_negative', left) for left in ('base', 'positive_only', 'domain_control')]
        for right, left in pairs:
            deltas = defaultdict(list)
            for qid in {r['question_id'] for r in subset}:
                a, b = scores.get((qid, left)), scores.get((qid, right))
                if a and b and a['judged'] and b['judged']:
                    deltas[groups[qid]].append(b['score'] - a['score'])
            means = [sum(v) / len(v) for v in deltas.values()]
            ci = None
            if len(means) >= 2 and bootstrap > 0:
                rng = random.Random(71)
                samples = sorted(sum(rng.choices(means, k=len(means))) / len(means) for _ in range(bootstrap))
                ci = [samples[int(.025 * (bootstrap - 1))], samples[int(.975 * (bootstrap - 1))]]
            comparisons[right + '_minus_' + left] = {'paired_questions': sum(map(len, deltas.values())), 'source_groups': len(means),
                                  'macro_source_delta': sum(means) / len(means) if means else None,
                                  'bootstrap_95pct_ci': ci}
        reports[split + ':' + protocol] = {'arms': report, 'comparisons': comparisons}
    out = fresh(out)
    write(out / 'per_question.json', rows)
    result = {'strata': reports, 'metric': 'Rubric fraction; missing/unjudged contributes zero in all-expected denominator.',
              'causal_negative_increment': 'Requires length-matched background ablation and independent reviewed test; inspect retrieval_audit.json.',
              'automatic_content_judging': False}
    write(out / 'report.json', result)
    seal(out, [trial / 'manifest.json', trial / 'exports/answers.json',
               packet / 'manifest.json', judgments])
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('packet')
    a.add_argument('--trial', type=Path, required=True)
    a.add_argument('--out', type=Path, required=True)
    a = sub.add_parser('score')
    for name in ('trial', 'packet', 'judgments', 'out'):
        a.add_argument('--' + name, type=Path, required=True)
    args = vars(p.parse_args())
    command = args.pop('command')
    print(make_packet(**args) if command == 'packet' else score(**args))
