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


def assess(workspace: Path, ledger_path: Path, out: Path, resolutions: Path | None = None):
    workspace = Path(workspace).resolve()
    summary, records, audits, failures = snapshot(workspace)
    ledger = _ledger_report(Path(ledger_path).resolve())
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
    if pending_context:
        blockers.append("pending_context")
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
    if support.get("support_rate") is None or support.get("support_rate") < 0.90:
        blockers.append("citation_support_below_threshold")
    report = {
        "schema_version": 1,
        "status": "batch_ready_for_next" if not blockers else "batch_blocked",
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
        "citation": {k: support.get(k) for k in ("records", "supported", "support_rate")},
        "scope": {"model_eligible": sum(row.get("model_eligible") is True
                                        for row in (support.get("rows") or []))},
        "blockers": blockers,
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
