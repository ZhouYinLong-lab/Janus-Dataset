"""Create a zero-request content triage from saved sentence_v3 records.

This is a review queue, not an expert gold set and not an acceptance bypass.
It applies the seven already documented source-checked cases, then makes only
conservative lexical routing suggestions for the remaining saved records.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


KNOWN_DECISIONS = {
    'b8ee41417e77b3798313a0287e90b7cb60e1841088ef166374fc45cf249d9656': ('exclude_non_target', 'C01'),
    'bb656d3aa45569cf606cabb881680a9134f6d4645ab843935a0bc6367483c593': ('quarantine_mixed_endpoint', 'C02'),
    '91ae9c10fcce087ad787b1c32b8d81ee762360fe6da4b4d9c27198fc1d9b250d': ('quarantine_direction_error', 'C03'),
    'c2c6cc02ff20515edf7a8bdc6af30d9b2735a0ca3e8dcfb24f499aed56fb431b': ('exclude_method_rule', 'C04'),
    'd43d3ae20fc05ffba007d1af78ac7978081fe96c9deeee31a1daf4336411338c': ('quarantine_mixed_endpoint', 'C05'),
    '871c6b8b3fedd1451a2ec46552f80e2869f7f978eafd26695fda7303d8c15a27': ('quarantine_numeric_claim', 'C06'),
    '968e771d4d3abd35300300581d192da2d3c520e54bcc29588336c7c9d7bea13e': ('quarantine_mixed_endpoint', 'C07'),
}

METHOD_RE = re.compile(r'\b(sample size|euthan|body weight|near death|clinically available|calculation was not performed)\b', re.I)
NEGATIVE_RE = re.compile(r'\b(no|not|did not|does not|failed to|failure|without|insensitive|ineffective|attenuat|resistance|could not|no longer|less competitive)\b', re.I)
POSITIVE_RE = re.compile(r'\b(decreased|down[- ]?regulat|induced|accelerat|strongly|enhanc|increased|resulted in|exhibits|blocked|rescued|intensified|binds?)\b', re.I)


def _route(record):
    key = record['record_key']
    if key in KNOWN_DECISIONS:
        destination, case_id = KNOWN_DECISIONS[key]
        return destination, 'source_checked_' + case_id, False
    values = record.get('values', {})
    text = ' '.join(str(values.get(k) or '') for k in ('endpoint', 'observation', 'scope_condition'))
    if METHOD_RE.search(text):
        return 'exclude_method_or_protocol', 'method_or_protocol_language', True
    if record.get('record_status') in {'semantic_pending', 'quarantine'}:
        return 'pending_existing_status', 'existing_semantic_guard', True
    negative = bool(NEGATIVE_RE.search(text))
    positive = bool(POSITIVE_RE.search(text))
    outcome = record.get('outcome_type')
    if negative and not positive and outcome in {'not_observed', 'not_significant', 'not_improved', 'conditional_loss'}:
        return 'candidate_boundary_negative', 'explicit_negative_language', True
    if positive or outcome == 'reduced':
        return 'candidate_positive_or_mixed', 'direction_or_scope_review', True
    return 'pending_manual_review', 'no_conservative_route', True


def triage(records_path, known_cases_path, out_path):
    records = json.loads(Path(records_path).read_text(encoding='utf-8'))
    known = json.loads(Path(known_cases_path).read_text(encoding='utf-8'))
    known_ids = {case['case_id'] for case in known.get('cases', [])}
    rows = []
    for record in records:
        destination, reason, manual = _route(record)
        case_id = KNOWN_DECISIONS.get(record['record_key'], (None, None))[1]
        if case_id and case_id not in known_ids:
            raise ValueError('Known case id missing from reviewed cases: ' + case_id)
        rows.append({'record_key': record['record_key'], 'paper_id': record.get('paper_id'),
                     'record_status': record.get('record_status'), 'outcome_type': record.get('outcome_type'),
                     'destination': destination, 'reason': reason, 'known_case_id': case_id,
                     'requires_manual_review': manual})
    summary = {'scope': 'offline triage of saved responses; not expert gold and not acceptance',
               'records': len(rows), 'known_cases_applied': sum(bool(r['known_case_id']) for r in rows),
               'destinations': dict(Counter(r['destination'] for r in rows)),
               'manual_review_records': sum(r['requires_manual_review'] for r in rows),
               'generation_requests': 0, 'source_records': str(Path(records_path).resolve())}
    out = Path(out_path)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'triage.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('--known-cases', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(triage(args.records, args.known_cases, args.out), ensure_ascii=False, indent=2))
