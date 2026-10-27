"""Build leakage-safe blind-review packets for the v1 completion pass."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ALLOWED_VERDICTS = {"reliable", "pending_review", "excluded"}
ALLOWED_SCOPES = {
    "molecular_glue_degradation_negative", "mechanism_or_control",
    "other_endpoint", "out_of_scope",
}
ALLOWED_ORIGINS = {"primary_report", "secondary_report", "unclear"}
LEAKED_KEYS = {
    "final_status", "final_status_basis", "provisional_status", "model_eligibility",
    "citation_exact", "split", "database_overlap", "mg2act_source_splits",
    "mg2act_train_blocked", "scope_class", "scope_basis", "evidence_origin",
    "evidence_origin_basis", "reviewer_a_status", "reviewer_b_status",
    "adjudication_status",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def record_id(row: dict) -> str:
    return row.get("evidence_id") or row.get("record_id") or row.get("candidate_id")


def load_release_records(release: Path) -> list[dict]:
    rows = []
    for name in ("reliable_evidence", "pending_review", "excluded_records"):
        rows.extend(read(release / f"{name}.json"))
    ids = [record_id(row) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Release records contain duplicate evidence IDs")
    return rows


def load_jsonl_ids(folder: Path) -> set[str]:
    result = set()
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            rid = record_id(json.loads(line))
            if not rid or rid in result:
                raise ValueError(f"Duplicate or missing review ID: {rid}")
            result.add(rid)
    return result


def partition_by_paper(rows: list[dict], parts: int = 3) -> list[list[dict]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["paper_id"]].append(row)
    bins = [[] for _ in range(parts)]
    sizes = [0] * parts
    for paper_id, paper_rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        target = min(range(parts), key=lambda index: (sizes[index], index))
        bins[target].extend(sorted(paper_rows, key=record_id))
        sizes[target] += len(paper_rows)
    return bins


def _clean_record(row: dict) -> dict:
    cleaned = {key: value for key, value in row.items() if key not in LEAKED_KEYS}
    leaked = LEAKED_KEYS & set(cleaned)
    if leaked:
        raise ValueError(f"Blind packet leaks review fields: {sorted(leaked)}")
    return cleaned


def build_task(row: dict, document: dict, role: str) -> dict:
    units = document.get("units") or []
    by_id = {unit["unit_id"]: index for index, unit in enumerate(units)}
    unit_ids = []
    spans = row.get("evidence_spans") or (row.get("observation") or {}).get("evidence_detail") or []
    for span in spans:
        if span.get("unit_id") in by_id:
            unit_ids.append(span["unit_id"])
    discovery = row.get("discovery") or {}
    if discovery.get("unit_id") in by_id:
        unit_ids.append(discovery["unit_id"])
    indexes = set()
    for unit_id in unit_ids:
        index = by_id[unit_id]
        indexes.update(range(max(0, index - 1), min(len(units), index + 2)))
    context = [units[index] for index in sorted(indexes)]
    task = {
        "evidence_id": record_id(row),
        "paper_id": row["paper_id"],
        "review_role": role,
        "source_sha256": row.get("source_sha256"),
        "record": _clean_record(row),
        "context_units": context,
    }
    task["task_sha256"] = sha256_json(task)
    return task


def build_packets(release: Path, workspace: Path, inventory_path: Path,
                  review_b: Path, output: Path) -> dict:
    records = load_release_records(release)
    if len(records) != 464:
        raise ValueError(f"Expected 464 current records, found {len(records)}")
    decisions = {row["evidence_id"]: row for row in read(release / "review_decisions.json")}
    existing_b = load_jsonl_ids(review_b)
    missing_b = [row for row in records if record_id(row) not in existing_b]
    if len(existing_b) != 286 or len(missing_b) != 178:
        raise ValueError(f"Unexpected blind-review boundary: {len(existing_b)} existing, {len(missing_b)} missing")
    missing_a = [row for row in records
                 if not decisions[record_id(row)].get("reviewer_a_status")]
    if len(missing_a) != 35:
        raise ValueError(f"Expected 35 recovered records without Reviewer A, found {len(missing_a)}")

    inventory = {row["paper_id"]: row for row in read(inventory_path)}
    documents = {}
    for paper_id in {row["paper_id"] for row in missing_b}:
        document = read(workspace / "documents" / f"{paper_id}.json")
        expected = inventory[paper_id].get("source_sha256")
        if document.get("source_sha256") != expected:
            raise ValueError(f"Document/inventory hash mismatch for {paper_id}")
        documents[paper_id] = document
    for row in missing_b:
        expected = inventory[row["paper_id"]].get("source_sha256")
        if row.get("source_sha256") != expected:
            raise ValueError(f"Record/inventory hash mismatch for {record_id(row)}")

    b_shards = partition_by_paper(missing_b, 3)
    if sorted(len(shard) for shard in b_shards) != [59, 59, 60]:
        raise ValueError(f"Unexpected B shard sizes: {[len(shard) for shard in b_shards]}")
    b_owner = {record_id(row): index for index, shard in enumerate(b_shards) for row in shard}
    a_shards = [[] for _ in range(3)]
    for row in sorted(missing_a, key=record_id):
        a_shards[(b_owner[record_id(row)] + 1) % 3].append(row)

    output.mkdir(parents=True, exist_ok=True)
    packet_hashes = {}
    for index in range(3):
        worker_id = f"codex-v1-completion-reviewer-{index + 1}"
        packet = {
            "schema_version": 1,
            "worker_id": worker_id,
            "blindness": "packet_excludes_reviewer_a_and_current_partition_decisions",
            "instructions": {
                "allowed_verdicts": sorted(ALLOWED_VERDICTS),
                "allowed_scope_classes": sorted(ALLOWED_SCOPES),
                "allowed_evidence_origins": sorted(ALLOWED_ORIGINS),
                "preserve_result_strength": True,
                "untested_or_inferred_is_not_negative": True,
                "expert_gold": False,
                "external_generation_api_requests": 0,
            },
            "review_b_tasks": [build_task(row, documents[row["paper_id"]], "reviewer_b")
                               for row in b_shards[index]],
            "review_a_extra_tasks": [build_task(row, documents[row["paper_id"]], "reviewer_a_extra")
                                     for row in a_shards[index]],
        }
        packet["packet_sha256"] = sha256_json(packet)
        path = output / f"reviewer_{index + 1}_packet.json"
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        packet_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "schema_version": 1,
        "records": len(records),
        "existing_reviewer_b": len(existing_b),
        "missing_reviewer_b": len(missing_b),
        "missing_reviewer_a_extra": len(missing_a),
        "reviewer_b_shard_sizes": [len(shard) for shard in b_shards],
        "reviewer_a_extra_shard_sizes": [len(shard) for shard in a_shards],
        "packet_hashes": packet_hashes,
        "paper_assignment": {
            str(index + 1): sorted({row["paper_id"] for row in shard})
            for index, shard in enumerate(b_shards)
        },
        "external_generation_api_requests": 0,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate_review_rows(rows: list[dict], tasks: list[dict], worker_id: str,
                         role: str) -> dict:
    expected = {task["evidence_id"]: task for task in tasks}
    actual = {record_id(row): row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        raise ValueError("Review output IDs do not exactly match the assigned tasks")
    for rid, row in actual.items():
        if row.get("worker_id") != worker_id or row.get("review_role") != role:
            raise ValueError(f"Worker or role mismatch for {rid}")
        if row.get("verdict") not in ALLOWED_VERDICTS:
            raise ValueError(f"Invalid verdict for {rid}")
        if row.get("scope_class") not in ALLOWED_SCOPES:
            raise ValueError(f"Invalid scope for {rid}")
        if row.get("evidence_origin") not in ALLOWED_ORIGINS:
            raise ValueError(f"Invalid origin for {rid}")
        if not isinstance(row.get("citation_direct_support"), bool):
            raise ValueError(f"Missing citation judgement for {rid}")
        if not isinstance(row.get("required_fields_supported"), bool):
            raise ValueError(f"Missing field judgement for {rid}")
        if row.get("source_sha256") != expected[rid].get("source_sha256"):
            raise ValueError(f"Source hash mismatch for {rid}")
        if not row.get("reason") or row.get("external_generation_api_requests") != 0:
            raise ValueError(f"Incomplete provenance for {rid}")
    return {"records": len(rows), "verdicts": dict(Counter(row["verdict"] for row in rows))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--review-b", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_packets(args.release, args.workspace, args.inventory,
                                   args.review_b, args.output), ensure_ascii=False, indent=2))
