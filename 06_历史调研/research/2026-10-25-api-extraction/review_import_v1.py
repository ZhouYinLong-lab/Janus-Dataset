"""Validate and consolidate completion reviews without rewriting prior shards."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import blind_review_completion_v1 as blind


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing review result: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8")


def import_reviews(packets: Path, results: Path, existing_review_b: Path,
                   output: Path) -> dict:
    all_b, all_a = [], []
    completion_b_ids, completion_a_ids = set(), set()
    b_worker, a_worker = {}, {}
    result_hashes = {}
    for index in range(1, 4):
        packet_path = packets / f"reviewer_{index}_packet.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
        worker_id = packet["worker_id"]
        worker_results = results / f"reviewer_{index}"
        b_path, a_path = worker_results / "review_b.jsonl", worker_results / "review_a_extra.jsonl"
        b_rows, a_rows = read_jsonl(b_path), read_jsonl(a_path)
        blind.validate_review_rows(b_rows, packet["review_b_tasks"], worker_id, "reviewer_b")
        blind.validate_review_rows(a_rows, packet["review_a_extra_tasks"], worker_id, "reviewer_a_extra")
        for row in b_rows:
            rid = blind.record_id(row)
            if rid in completion_b_ids:
                raise ValueError(f"Duplicate completion Reviewer B result: {rid}")
            completion_b_ids.add(rid); b_worker[rid] = worker_id
        for row in a_rows:
            rid = blind.record_id(row)
            if rid in completion_a_ids:
                raise ValueError(f"Duplicate completion Reviewer A result: {rid}")
            completion_a_ids.add(rid); a_worker[rid] = worker_id
        all_b.extend(b_rows); all_a.extend(a_rows)
        result_hashes[b_path.as_posix()] = sha256_file(b_path)
        result_hashes[a_path.as_posix()] = sha256_file(a_path)

    if len(all_b) != 178 or len(all_a) != 35:
        raise ValueError(f"Unexpected completion totals: B={len(all_b)}, A={len(all_a)}")
    for rid in completion_a_ids:
        if rid not in b_worker or a_worker[rid] == b_worker[rid]:
            raise ValueError(f"Recovered record lacks independent A/B workers: {rid}")

    combined_b = output / "review_b"
    combined_a = output / "review_a_extra"
    combined_b.mkdir(parents=True, exist_ok=True)
    combined_a.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    for source in sorted(existing_review_b.glob("*.jsonl")):
        rows = read_jsonl(source)
        for row in rows:
            rid = blind.record_id(row)
            if rid in existing_ids or rid in completion_b_ids:
                raise ValueError(f"Duplicate existing/completion Reviewer B result: {rid}")
            existing_ids.add(rid)
        shutil.copyfile(source, combined_b / f"existing_{source.name}")
    if len(existing_ids) != 286:
        raise ValueError(f"Expected 286 prior Reviewer B results, found {len(existing_ids)}")
    for index in range(1, 4):
        rows = [row for row in all_b if row["worker_id"].endswith(str(index))]
        write_jsonl(combined_b / f"completion_{index}.jsonl", rows)
        a_rows = [row for row in all_a if row["worker_id"].endswith(str(index))]
        write_jsonl(combined_a / f"completion_{index}.jsonl", a_rows)

    manifest = {
        "schema_version": 1,
        "existing_reviewer_b": len(existing_ids),
        "completion_reviewer_b": len(all_b),
        "total_reviewer_b": len(existing_ids) + len(all_b),
        "completion_reviewer_a_extra": len(all_a),
        "independent_recovered_ab": len(completion_a_ids),
        "result_hashes": result_hashes,
        "external_generation_api_requests": 0,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packets", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--existing-review-b", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(import_reviews(args.packets, args.results, args.existing_review_b,
                                    args.output), ensure_ascii=False, indent=2))
