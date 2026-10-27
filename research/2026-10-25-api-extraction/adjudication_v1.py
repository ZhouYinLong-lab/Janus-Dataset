"""Build and validate record- and experiment-level v1 adjudication queues."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import blind_review_completion_v1 as blind
import release_v1


ALLOWED_DUPLICATE_DECISIONS = {"same_experiment", "distinct_experiments", "possible_duplicate"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def merge_reviews(primary: dict[str, dict], extra: dict[str, dict]) -> dict[str, dict]:
    overlap = set(primary) & set(extra)
    if overlap:
        raise ValueError(f"Duplicate review identities: {sorted(overlap)[:3]}")
    return {**primary, **extra}


def _verdict(row: dict | None) -> str | None:
    return release_v1.normalize_verdict(row or {})


def adjudication_reasons(a: dict, b: dict) -> list[str]:
    reasons = []
    a_verdict, b_verdict = _verdict(a), _verdict(b)
    if not a_verdict or not b_verdict:
        return ["missing_independent_review"]
    if a_verdict != b_verdict:
        reasons.append("verdict_disagreement")
    elif a_verdict == "pending_review":
        reasons.append("joint_pending")
    for field, label in (("scope_class", "scope_disagreement"),
                         ("evidence_origin", "origin_disagreement"),
                         ("citation_direct_support", "citation_support_disagreement"),
                         ("required_fields_supported", "required_fields_disagreement")):
        if field in a and field in b and a.get(field) != b.get(field):
            reasons.append(label)
    if b.get("corrections"):
        reasons.append("reviewer_b_correction_proposed")
    if a.get("review_role") == "reviewer_a_extra" and a.get("corrections"):
        reasons.append("reviewer_a_correction_proposed")
    return sorted(set(reasons))


def _context(row: dict, workspace: Path) -> list[dict]:
    document = read(workspace / "documents" / f"{row['paper_id']}.json")
    units = document.get("units") or []
    positions = {unit["unit_id"]: index for index, unit in enumerate(units)}
    indexes = set()
    for span in row.get("evidence_spans") or []:
        if span.get("unit_id") in positions:
            index = positions[span["unit_id"]]
            indexes.update(range(max(0, index - 1), min(len(units), index + 2)))
    return [units[index] for index in sorted(indexes)]


def build_queues(release: Path, run: Path, workspace: Path,
                 review_a_extra: Path, review_b: Path, output: Path) -> dict:
    records = release_v1.load_baseline(run)
    # The release candidate is authoritative for the 35 append-only recovered records.
    records = blind.load_release_records(release)
    by_id = {blind.record_id(row): row for row in records}
    review_a_all = merge_reviews(release_v1.load_review_a(run),
                                 release_v1.load_jsonl_dir(review_a_extra))
    reviews_b_all = release_v1.load_jsonl_dir(review_b)
    review_a = {rid: row for rid, row in review_a_all.items() if rid in by_id}
    reviews_b = {rid: row for rid, row in reviews_b_all.items() if rid in by_id}
    if set(review_a) != set(by_id) or set(reviews_b) != set(by_id):
        raise ValueError(
            f"Review coverage incomplete: A={len(review_a)}, B={len(reviews_b)}, records={len(records)}")

    queue = []
    for rid, row in by_id.items():
        reasons = adjudication_reasons(review_a[rid], reviews_b[rid])
        if not reasons:
            continue
        item = {
            "evidence_id": rid,
            "paper_id": row["paper_id"],
            "source_sha256": row.get("source_sha256"),
            "queue_reasons": reasons,
            "record": {key: row.get(key) for key in
                       ("facts", "observation", "conditions", "evidence_spans")},
            "reviewer_a": review_a[rid],
            "reviewer_b": reviews_b[rid],
            "context_units": _context(row, workspace),
        }
        item["queue_sha256"] = blind.sha256_json(item)
        queue.append(item)
    queue.sort(key=lambda row: (row["paper_id"], row["evidence_id"]))

    duplicate_queue = read(release / "possible_duplicates.json")
    output.mkdir(parents=True, exist_ok=True)
    (output / "record_adjudication_queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "duplicate_adjudication_queue.json").write_text(
        json.dumps(duplicate_queue, ensure_ascii=False, indent=2), encoding="utf-8")
    adjudication_shards = blind.partition_by_paper(queue, 3)
    for index, shard in enumerate(adjudication_shards, 1):
        (output / f"record_adjudication_shard_{index}.json").write_text(
            json.dumps(shard, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for item in queue:
        for reason in item["queue_reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    manifest = {
        "schema_version": 1,
        "records": len(records),
        "record_adjudications_required": len(queue),
        "duplicate_adjudications_required": len(duplicate_queue),
        "record_adjudication_shard_sizes": [len(shard) for shard in adjudication_shards],
        "reason_counts": counts,
        "record_queue_sha256": hashlib.sha256(
            (output / "record_adjudication_queue.json").read_bytes()).hexdigest(),
        "duplicate_queue_sha256": hashlib.sha256(
            (output / "duplicate_adjudication_queue.json").read_bytes()).hexdigest(),
        "external_generation_api_requests": 0,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate_adjudications(rows: list[dict], queue: list[dict]) -> dict:
    expected = {row["evidence_id"]: row for row in queue}
    actual = {row.get("evidence_id"): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise ValueError("Adjudication IDs do not exactly match the queue")
    for rid, row in actual.items():
        if row.get("verdict") not in blind.ALLOWED_VERDICTS:
            raise ValueError(f"Invalid adjudication verdict: {rid}")
        if row.get("scope_class") not in blind.ALLOWED_SCOPES:
            raise ValueError(f"Invalid adjudication scope: {rid}")
        if row.get("evidence_origin") not in blind.ALLOWED_ORIGINS:
            raise ValueError(f"Invalid adjudication origin: {rid}")
        if row.get("source_sha256") != expected[rid]["source_sha256"]:
            raise ValueError(f"Adjudication source mismatch: {rid}")
        if not row.get("reason") or row.get("expert_gold") is not False:
            raise ValueError(f"Adjudication provenance incomplete: {rid}")
    return {"records": len(rows)}


def validate_duplicate_adjudications(rows: list[dict], queue: list[dict]) -> dict:
    expected = {row["group_id"]: row for row in queue}
    actual = {row.get("group_id"): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise ValueError("Duplicate adjudication groups do not exactly match the queue")
    for gid, row in actual.items():
        if row.get("decision") not in ALLOWED_DUPLICATE_DECISIONS:
            raise ValueError(f"Invalid duplicate decision: {gid}")
        if set(row.get("evidence_ids") or []) != set(expected[gid]["evidence_ids"]):
            raise ValueError(f"Duplicate evidence set changed: {gid}")
        if not row.get("reason"):
            raise ValueError(f"Duplicate decision lacks reason: {gid}")
        if row["decision"] == "same_experiment" and not row.get("canonical_experiment_id"):
            raise ValueError(f"Merged group lacks canonical experiment ID: {gid}")
    return {"groups": len(rows)}


def finalize_recommendations(recommendation_paths: list[Path], queue_path: Path,
                             output: Path) -> dict:
    queue = read(queue_path)
    expected = {row["evidence_id"]: row for row in queue}
    recommendations = []
    for path in recommendation_paths:
        recommendations.extend(
            json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip())
    actual = {row.get("evidence_id"): row for row in recommendations}
    if len(actual) != len(recommendations) or set(actual) != set(expected):
        raise ValueError("Recommendation IDs do not exactly match the adjudication queue")
    rows = []
    for rid in sorted(expected):
        recommendation, task = actual[rid], expected[rid]
        if recommendation.get("source_sha256") != task["source_sha256"]:
            raise ValueError(f"Recommendation source mismatch: {rid}")
        if recommendation.get("queue_sha256") != task["queue_sha256"]:
            raise ValueError(f"Recommendation queue hash mismatch: {rid}")
        if recommendation.get("verdict") not in blind.ALLOWED_VERDICTS:
            raise ValueError(f"Invalid recommendation verdict: {rid}")
        if recommendation.get("scope_class") not in blind.ALLOWED_SCOPES:
            raise ValueError(f"Invalid recommendation scope: {rid}")
        if recommendation.get("evidence_origin") not in blind.ALLOWED_ORIGINS:
            raise ValueError(f"Invalid recommendation origin: {rid}")
        if (recommendation["verdict"] == "reliable"
                and not (recommendation.get("citation_direct_support")
                         and recommendation.get("required_fields_supported"))):
            raise ValueError(f"Unsupported recommendation cannot be reliable: {rid}")
        row = {
            "adjudication_id": "ADJ_" + hashlib.sha256(
                f"v1:{rid}:{task['queue_sha256']}".encode()).hexdigest()[:20],
            "evidence_id": rid,
            "paper_id": task["paper_id"],
            "verdict": recommendation["verdict"],
            "scope_class": recommendation["scope_class"],
            "evidence_origin": recommendation["evidence_origin"],
            "citation_direct_support": recommendation["citation_direct_support"],
            "required_fields_supported": recommendation["required_fields_supported"],
            "accepted_corrections": recommendation.get("accepted_corrections") or {},
            "evidence_unit_ids": recommendation.get("evidence_unit_ids") or [],
            "reason": recommendation["reason"],
            "source_sha256": recommendation["source_sha256"],
            "queue_sha256": task["queue_sha256"],
            "queue_reasons": task["queue_reasons"],
            "reviewer_a_verdict": _verdict(task["reviewer_a"]),
            "reviewer_b_verdict": _verdict(task["reviewer_b"]),
            "recommendation_worker_id": recommendation["recommendation_worker_id"],
            "adjudicator_id": "codex-main-v1",
            "adjudication_basis": "source_reviewed_recommendation_accepted_by_main",
            "adjudicated_utc": time.time(),
            "generation_method": "Codex main-agent adjudication",
            "external_generation_api_requests": 0,
            "expert_gold": False,
        }
        rows.append(row)
    validate_adjudications(rows, queue)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                              for row in rows), encoding="utf-8")
    return {
        "records": len(rows),
        "verdict_counts": dict(Counter(row["verdict"] for row in rows)),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "external_generation_api_requests": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--review-a-extra", required=True, type=Path)
    parser.add_argument("--review-b", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_queues(args.release, args.run, args.workspace,
                                  args.review_a_extra, args.review_b, args.output),
                     ensure_ascii=False, indent=2))
