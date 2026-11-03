"""Offline acceptance report for one readable-XML extraction batch."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402
from sentence_export import snapshot  # noqa: E402


def _ledger_report(path: Path):
    ledger = read(path)
    attempts = ledger.get("attempts", [])
    statuses = Counter(row.get("status") for row in attempts)
    request_hashes = [row.get("request_sha256") for row in attempts if row.get("request_sha256")]
    duplicates = len(request_hashes) - len(set(request_hashes))
    return {
        "attempts": len(attempts),
        "status_counts": dict(statuses),
        "reserved_tokens": sum(row.get("reserved_tokens", 0) or 0 for row in attempts),
        "reported_tokens": sum((row.get("usage") or {}).get("total_tokens", 0) or 0 for row in attempts),
        "duplicate_request_hashes": duplicates,
    }


def _record_partition(records, routed, support_rows, pending_context):
    by_key = {row.get("record_key"): row for row in records}
    route_by_key = {row.get("record_key"): row.get("route") for row in routed}
    directly_supported = {row.get("record_key") for row in support_rows
                          if row.get("direct_support") is True}
    semantic_pending = {key for key, row in by_key.items()
                        if row.get("record_status") == "semantic_pending"}
    quarantined = {key for key, row in by_key.items()
                   if row.get("record_status") == "quarantine"}
    scope_pending = {key for key, route in route_by_key.items()
                     if route == "pending_scope_review"}
    excluded = {key for key, route in route_by_key.items()
                if route in {"other_endpoint", "mechanism_or_control"}} | quarantined
    reliable = {key for key, route in route_by_key.items()
                if route == "candidate_review" and key in directly_supported
                and key not in semantic_pending and key not in quarantined}
    isolated = semantic_pending | scope_pending
    return {
        "reliable_records": len(reliable),
        "excluded_records": len(excluded),
        "isolated_pending": len(isolated) + len(pending_context),
        "model_eligible_records": sum(by_key[key].get("ready_for_training") is True
                                      for key in reliable),
    }


def _source_hash_report(workspace: Path):
    manifest = read(workspace / "manifest.json")
    rows = []
    for paper in manifest.get("papers", []):
        source_path = Path(paper.get("source_path") or "")
        expected = paper.get("source_sha256")
        exists = source_path.is_file()
        actual = sha(source_path) if exists else None
        rows.append({
            "paper_id": paper.get("paper_id"),
            "source_path": str(source_path),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "matches": bool(exists and expected and actual == expected),
        })
    return {"sources": len(rows), "stable": bool(rows) and all(row["matches"] for row in rows),
            "mismatches": [row for row in rows if not row["matches"]]}


def assess(workspace: Path, ledger_path: Path, out: Path, resolutions: Path | None = None):
    workspace = Path(workspace).resolve()
    summary, records, audits, failures = snapshot(workspace)
    ledger = _ledger_report(Path(ledger_path).resolve())
    source_hashes = _source_hash_report(workspace)
    paragraph_rows = [row for row in audits if row.get("destination") == "paragraph_coverage"]
    resolution_rows = {}
    if resolutions and Path(resolutions).is_file():
        resolution_rows = {row.get("paragraph_id"): row for row in
                           (read(Path(resolutions)).get("rows") or [])
                           if row.get("kind") == "paragraph"}
    unresolved_paragraphs = [row for row in paragraph_rows
                             if row.get("status") not in {"has_candidates", "none_found"}
                             and row.get("paragraph_id") not in resolution_rows]
    unscanned = [row for row in audits if row.get("destination") == "unscanned"]
    context_resolution_rows = {}
    if resolutions and Path(resolutions).is_file():
        context_resolution_rows = {(row.get("paper_id"), row.get("candidate_id")): row for row in
                                   (read(Path(resolutions)).get("rows") or [])
                                   if row.get("kind") == "context"}
    context_gaps = [row for row in audits if row.get("destination") in
                    {"optional_conditions_gap", "context_coverage"}
                    and row.get("context_complete") is False
                    and (row.get("paper_id"), row.get("candidate_id")) not in context_resolution_rows]
    pending_context = [row for row in context_resolution_rows.values()
                       if row.get("terminal_status") == "pending_context"]
    task_counts = Counter(row.get("status") for row in
                          (read(workspace / "candidate_state.json").get("tasks", {}) or {}).values())
    support = None
    routed = []
    try:
        from offline_shadow_closeout import scope_partition, citation_audit
        audit_dir = Path(out).resolve().parent / (Path(out).stem + "_audit")
        routed = scope_partition(workspace, audit_dir)
        support = citation_audit(workspace, audit_dir, routed)
    except Exception as exc:
        support = {"records": 0, "supported": 0, "support_rate": None,
                   "error": f"{type(exc).__name__}:{exc}"}
    blockers = []
    if unscanned:
        blockers.append("unscanned_sentences")
    if unresolved_paragraphs:
        blockers.append("unresolved_paragraphs")
    if context_gaps:
        blockers.append("context_gaps")
    if failures:
        blockers.append("task_failures")
    if task_counts.get("in_flight"):
        blockers.append("in_flight_tasks")
    if task_counts.get("needs_attention"):
        blockers.append("unknown_tasks")
    if task_counts.get("invalid_response"):
        blockers.append("invalid_responses")
    if ledger["duplicate_request_hashes"]:
        blockers.append("duplicate_request_hashes")
    if not source_hashes["stable"]:
        blockers.append("source_hash_changes")
    if support.get("support_rate") is None or support.get("support_rate") < 0.90:
        blockers.append("citation_support_below_threshold")
    scope_counts = Counter(row.get("route") for row in routed)
    partition = _record_partition(records, routed, support.get("rows") or [], pending_context)
    hard_blockers = list(blockers)
    report = {
        "schema_version": 1,
        "status": "batch_ready_for_next" if not hard_blockers else "batch_blocked",
        "workspace": str(workspace),
        "workspace_manifest_sha256": sha(workspace / "manifest.json"),
        "summary": summary,
        "papers": len(summary.get("papers", [])),
        "records": len(records),
        "tasks": dict(task_counts),
        "paragraphs": {"total": len(paragraph_rows), "unscanned": len(unscanned),
                       "unresolved": len(unresolved_paragraphs)},
        "context_gaps": len(context_gaps),
        "pending_context": len(pending_context),
        "failures": failures,
        "ledger": ledger,
        "source_hashes": source_hashes,
        "source_hashes_stable": source_hashes["stable"],
        "citation": {k: support.get(k) for k in ("records", "supported", "support_rate")},
        "citation_support_rate": support.get("support_rate"),
        "scope": {"counts": dict(scope_counts),
                  "model_eligible": partition["model_eligible_records"]},
        "candidate_review_records": scope_counts.get("candidate_review", 0),
        "mechanically_supported_records": support.get("supported", 0),
        "reliable_records": partition["reliable_records"],
        "excluded_records": partition["excluded_records"],
        "isolated_pending": partition["isolated_pending"],
        "reliability_basis": "direct anchors plus scope and semantic-status checks; model-assisted, not expert gold",
        "hard_blockers": hard_blockers,
        "blockers": hard_blockers,
        "allow_next_batch": not hard_blockers,
        "model_assisted_review": "not expert gold",
    }
    save(Path(out), report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--resolutions", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(assess(args.workspace, args.ledger, args.out, args.resolutions), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
