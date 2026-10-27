"""Aggregate Codex subagent evidence into the existing sentence_v3 release shape.

The exporter only reads frozen workspace/inventory files and worker/reviewer
artifacts.  It never calls a model, changes candidate_state, or upgrades a
model-assisted result to expert gold.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import re
import time


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _rows(path):
    value = read(path)
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("records"), list):
        return value["records"]
    return []


def _record_id(row):
    return row.get("record_id") or row.get("evidence_id") or row.get("candidate_id")


def _quote(row):
    spans = row.get("evidence_spans") or []
    if spans:
        return spans[0].get("quote", "")
    detail = (row.get("observation") or {}).get("evidence_detail") or []
    if detail:
        return detail[0].get("quote", "")
    return ""


def _values(row):
    if isinstance(row.get("observation"), dict):
        return (row["observation"].get("values") or {})
    facts = row.get("facts") or {}
    observations = facts.get("observations") or []
    return (observations[0].get("values") or {}) if observations else {}


def _status(row, reviews):
    rid = _record_id(row)
    review = reviews.get(rid, {})
    status = review.get("review_status") or review.get("status")
    if status in {"reliable", "reliable_candidate", "reliable_evidence"}:
        return "reliable"
    if status in {"excluded", "exclude", "excluded_record"}:
        return "excluded"
    status = row.get("status") or row.get("review_status") or row.get("result_type")
    if status in {"reliable", "reliable_candidate", "reliable_evidence"}:
        return "reliable"
    if status in {"excluded", "exclude", "excluded_record"}:
        return "excluded"
    return "pending_review"


def _review_map(run):
    result = {}
    review_dir = Path(run) / "review"
    for path in sorted(review_dir.glob("*_review.json")):
        value = read(path)
        rows = value if isinstance(value, list) else value.get("records", [])
        for row in rows:
            rid = _record_id(row)
            if rid:
                result[rid] = row
    return result


def _worker_records(worker):
    records = sorted((worker / "records").glob("*.json"))
    if records:
        return [read(p) for p in records]
    raw = worker / "raw_records.json"
    return _rows(raw) if raw.is_file() else []


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False)
                             if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def export(run_dir, inventory_path, workspace_manifest_path):
    run = Path(run_dir).resolve()
    inventory = read(inventory_path)
    manifest = read(workspace_manifest_path)
    reviews = _review_map(run)
    raw_records, worker_summaries = [], []
    for worker in sorted((run / "workers").iterdir()):
        if not worker.is_dir():
            continue
        summary_path = worker / "worker_summary.json"
        if not summary_path.is_file():
            state_path = worker / "worker_state.json"
            summary_path = state_path
        if summary_path.is_file():
            summary = read(summary_path)
            if "summary" in summary:
                summary = summary["summary"]
            worker_summaries.append(summary)
        raw_records.extend(_worker_records(worker))

    reliable, pending, excluded = [], [], []
    seen = {}
    for row in raw_records:
        rid = _record_id(row)
        if not rid:
            continue
        values = _values(row)
        dedupe = digest({"paper_id": row.get("paper_id"), "quote": _quote(row),
                         "subject": values.get("subject"), "target": values.get("target"),
                         "endpoint": values.get("endpoint"),
                         "observation": values.get("observation")})
        normalized = dict(row)
        normalized["evidence_id"] = normalized.get("evidence_id") or rid
        normalized["dedupe_key"] = dedupe
        normalized["review"] = reviews.get(rid, {})
        normalized["final_status"] = _status(row, reviews)
        if dedupe in seen:
            # Keep one evidence row and preserve the raw duplicate linkage.
            seen[dedupe].setdefault("duplicate_record_ids", []).append(rid)
            continue
        seen[dedupe] = normalized
        {"reliable": reliable, "pending_review": pending,
         "excluded": excluded}[normalized["final_status"]].append(normalized)

    out = run / "exports"
    out.mkdir(parents=True, exist_ok=True)
    datasets = {"reliable_evidence": reliable, "pending_review": pending,
                "excluded_records": excluded}
    for name, rows in datasets.items():
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_csv(out / f"{name}.csv", rows)

    summaries = {s.get("paper_id"): s for s in worker_summaries if s.get("paper_id")}
    manifest_papers = {p.get("paper_id"): p for p in manifest.get("papers", [])}
    paper_rows, context_rows, failures = [], [], []
    records_by_paper = defaultdict(list)
    for row in raw_records:
        records_by_paper[row.get("paper_id")].append(row)
    for paper in inventory:
        pid = paper.get("paper_id")
        mp = manifest_papers.get(pid, {})
        summary = summaries.get(pid, {})
        source_kind = mp.get("source_kind") or paper.get("source_kind")
        if not paper.get("path"):
            status = "fulltext_missing"
        elif pid in summaries and summary.get("failed_tasks", 0) == 0 and summary.get("unfinished_tasks", 0) == 0:
            status = "completed_with_candidates" if summary.get("candidate_count", 0) else "completed_no_candidates"
        elif source_kind == "html":
            status = "html_pending_format"
        elif paper.get("path"):
            status = "ready_unprocessed"
        else:
            status = "input_gap"
        paper_rows.append({"paper_id": pid, "doi": paper.get("doi"), "title": paper.get("title"),
                           "status": status, "source_kind": source_kind,
                           "source_sha256": paper.get("source_sha256") or mp.get("source_sha256"),
                           "task_count": summary.get("task_count", len(mp.get("job_ids", []))),
                           "completed_tasks": summary.get("completed_tasks", 0),
                           "candidate_count": summary.get("candidate_count", 0),
                           "reliable_count": summary.get("reliable_evidence_count", summary.get("reliable_count", 0)),
                           "pending_count": summary.get("pending_review_count", 0),
                           "failed_tasks": summary.get("failed_tasks", 0)})
        if pid in summaries:
            context_rows.append({"paper_id": pid, "source_sha256": summary.get("source_sha256"),
                                 "task_count": summary.get("task_count", 0),
                                 "completed_tasks": summary.get("completed_tasks", 0),
                                 "failed_tasks": summary.get("failed_tasks", 0),
                                 "candidate_count": summary.get("candidate_count", 0),
                                 "reliable_count": summary.get("reliable_evidence_count", summary.get("reliable_count", 0)),
                                 "pending_count": summary.get("pending_review_count", 0),
                                 "api_requests": summary.get("api_requests", 0),
                                 "usage": summary.get("usage"),
                                 "review_status": "model_assisted_not_expert_gold"})
            if summary.get("failed_tasks", 0) or summary.get("unfinished_tasks", 0):
                failures.append({"paper_id": pid, "reason": "worker_incomplete", "summary": summary})

    for name, rows in (("paper_coverage", paper_rows), ("context_coverage", context_rows),
                       ("failures", failures)):
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_csv(out / f"{name}.csv", rows)
    report = {"run_id": "codex_luna_run_20261027", "generation_method": "Codex subagent",
              "model_label": "Luna High; worker metadata authoritative when available",
              "external_generation_api_used": False, "api_requests_sent": 0,
              "paper_count": len(inventory), "worker_papers": len(summaries),
              "records_raw": len(raw_records), "records_deduplicated": len(reliable) + len(pending) + len(excluded),
              "reliable_count": len(reliable), "pending_review_count": len(pending),
              "excluded_count": len(excluded), "failure_count": len(failures),
              "paper_status_counts": dict(Counter(row["status"] for row in paper_rows)),
              "source_inventory_sha256": hashlib.sha256(Path(inventory_path).read_bytes()).hexdigest(),
              "workspace_manifest_sha256": hashlib.sha256(Path(workspace_manifest_path).read_bytes()).hexdigest(),
              "expert_gold": False, "content_review_status": "model_assisted_not_expert_gold",
              "generated_utc": time.time()}
    (out / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "run_report.md").write_text("# Codex Luna 离线提取报告\n\n" +
        "- 外部生成 API：0 次\n" + f"- 工作论文：{len(summaries)}\n" +
        f"- 原始候选：{len(raw_records)}；去重后：{report['records_deduplicated']}\n" +
        f"- 可靠：{len(reliable)}；待确认：{len(pending)}；排除：{len(excluded)}\n" +
        "- 结果为模型辅助提取与复核，不是专家金标。\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--workspace-manifest", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.run, args.inventory, args.workspace_manifest), ensure_ascii=False, indent=2))
