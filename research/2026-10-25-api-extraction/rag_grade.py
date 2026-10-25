"""Aggregate source-assisted, arm-masked QA judgments; no generation calls."""
import argparse
from collections import Counter
from pathlib import Path

from corpus import read, save


def aggregate(workspace, grading_files):
    workspace = Path(workspace)
    answers = read(workspace / 'answers.json')
    blind = {a['blind_id']: a for a in read(workspace / 'blind_answers.json')}
    judged = {}
    for path in grading_files:
        for item in read(path)['items']:
            bid = item['blind_id']
            if bid not in blind or bid in judged:
                raise ValueError('Unknown or duplicate judgment ID')
            marks = item['rubric_met']
            if (not isinstance(marks, list) or len(marks) != len(blind[bid]['rubric'])
                    or any(type(v) is not bool for v in marks)
                    or type(item['overclaim']) is not bool or not item['reason'].strip()):
                raise ValueError('Invalid rubric judgment')
            judged[bid] = item
    rows = []
    for answer in answers:
        bid = answer['blind_id']
        if bid not in judged:
            continue
        q = blind[bid]; item = judged[bid]
        rows.append({'question_id': q['question_id'], 'split': q['split'],
                     'arm': answer['arm'], 'blind_id': bid,
                     'score': sum(item['rubric_met']), 'maximum': len(q['rubric']),
                     'overclaim': item['overclaim'], 'reason': item['reason']})
    arms = sorted({a['arm'] for a in answers})
    paired = {q for q, n in Counter(r['question_id'] for r in rows).items() if n == len(arms)}
    summary = []
    for split in sorted({r['split'] for r in rows}):
        for arm in arms:
            group = [r for r in rows if r['split'] == split and r['arm'] == arm
                     and r['question_id'] in paired]
            summary.append({'split': split, 'arm': arm, 'paired_questions': len(group),
                            'rubric_points': sum(r['score'] for r in group),
                            'possible_points': sum(r['maximum'] for r in group),
                            'overclaim_answers': sum(r['overclaim'] for r in group)})
    result = {'expert_gold': False, 'generation_requests': 0,
              'judged_answers': len(rows), 'planned_answers': len(answers),
              'unjudged_or_missing_answers': len(answers) - len(rows),
              'paired_question_count': len(paired), 'groups': summary,
              'limitations': 'One nonexpert model-assisted judgment per answer; arm labels masked, '
                            'answer style may reveal retrieval. Purposive known papers, no causal '
                            'negative-evidence ablation and no statistical significance claim.'}
    save(workspace / 'graded_rows.json', rows)
    save(workspace / 'graded_summary.json', result)
    return result


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--grades', nargs='+', required=True)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.workspace, args.grades), ensure_ascii=False, indent=2))
