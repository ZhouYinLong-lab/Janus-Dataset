"""Validate the offline shadow gate used to release readable full batches."""

from __future__ import annotations

import json
from pathlib import Path


REQUIRED_STATUS = "shadow_ready_for_full_readable"


def validate_gate(path: Path) -> dict:
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"offline_gate_missing:{path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised by CLI failures
        raise ValueError(f"offline_gate_invalid_json:{type(exc).__name__}") from exc
    if not isinstance(report, dict):
        raise ValueError("offline_gate_not_object")
    if report.get("gate_schema_version") != 1:
        raise ValueError("offline_gate_schema_version_missing")
    if report.get("status") != REQUIRED_STATUS:
        raise ValueError(f"offline_gate_status:{report.get('status')!r}")
    if report.get("allow_full_extraction") is not True:
        raise ValueError("offline_gate_not_allowed")
    if report.get("source_hashes_stable") is not True:
        raise ValueError("offline_gate_source_hashes_unstable")
    if report.get("raw_workspace_untouched") is not True:
        raise ValueError("offline_gate_raw_workspace_changed")
    if report.get("blockers"):
        raise ValueError("offline_gate_blockers_present")
    paragraphs = report.get("paragraphs") or {}
    if paragraphs.get("unresolved") != 0:
        raise ValueError("offline_gate_unresolved_paragraphs")
    citation = report.get("citation") or {}
    if not isinstance(citation.get("support_rate"), (int, float)) or citation["support_rate"] < 0.90:
        raise ValueError("offline_gate_citation_support_below_threshold")
    failures = report.get("failures") or []
    if failures:
        raise ValueError("offline_gate_failures_present")
    return report


def validate_batch_gate(path: Path) -> dict:
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"batch_gate_missing:{path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"batch_gate_invalid_json:{type(exc).__name__}") from exc
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("batch_gate_schema_version_missing")
    if report.get("status") != "batch_ready_for_next" or report.get("allow_next_batch") is not True:
        raise ValueError(f"batch_gate_status:{report.get('status')!r}")
    if report.get("hard_blockers"):
        raise ValueError("batch_gate_hard_blockers_present")
    if report.get("source_hashes_stable") is not True:
        raise ValueError("batch_gate_source_hashes_unstable")
    if report.get("failures"):
        raise ValueError("batch_gate_failures_present")
    support = report.get("citation_support_rate")
    if not isinstance(support, (int, float)) or support < 0.90:
        raise ValueError("batch_gate_citation_support_below_threshold")
    tasks = report.get("tasks") or {}
    if any(tasks.get(status) for status in ("in_flight", "needs_attention", "invalid_response")):
        raise ValueError("batch_gate_nonterminal_tasks")
    return report

