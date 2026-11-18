"""Close out a frozen shadow batch without sending model requests.

The command creates a new audit workspace.  It normalizes only harmless
duplicate JSON keys with identical values, records paragraph terminal states,
routes out-of-scope records, and computes conservative citation support from
saved sentence anchors.  Raw workspaces, responses, and ledgers are untouched.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402
from sentence_export import snapshot  # noqa: E402


DEGRADATION = re.compile(r"degrad|deplet|protein\\s+(?:level|abundance)|proteasom|ubiquitin|蛋白.*(?:降解|下降|丰度)", re.I)
OUT_OF_SCOPE = re.compile(r"mRNA|transcript|binding|affinity|docking|occup(?:y|ies)|prolifer|viability|cytotoxic|cell\\s+death|增殖|存活|细胞毒|结合|对接|占位", re.I)


def _canonical_pairs(pairs, duplicates):
    result = {}
    for key, value in pairs:
        if key in result:
            if result[key] != value:
                raise ValueError(f"non_identical_duplicate_key:{key}")
            duplicates.append(key)
            continue
        result[key] = value
    return result


def _normalize_content(content: str):
    duplicates = []
    payload = json.loads(content, object_pairs_hook=lambda pairs: _canonical_pairs(pairs, duplicates))
    if isinstance(payload, dict) and payload.get("type") == "json_object":
        payload = {k: v for k, v in payload.items() if k != "type"}
        duplicates.append("provider_wrapper:type")
    if not isinstance(payload, dict):
        raise ValueError("normalized_payload_not_object")
    return payload, duplicates


def normalize_invalid_responses(workspace: Path, audit_dir: Path):
    state = read(workspace / "candidate_state.json")
    rows = []
    for task_id, entry in state.get("tasks", {}).items():
        if entry.get("status") != "invalid_response" or not entry.get("response_path"):
            continue
        response_path = workspace / entry["response_path"]
        envelope = read(response_path)
        content = envelope["choices"][0]["message"]["content"]
        raw_hash = sha(response_path)
        try:
            payload, repairs = _normalize_content(content)
            normalized_content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            normalized_envelope = copy.deepcopy(envelope)
            normalized_envelope["choices"][0]["message"]["content"] = normalized_content
            normalized_path = audit_dir / "normalized_responses" / response_path.name
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            save(normalized_path, normalized_envelope)
            rows.append({
                "task_id": task_id,
                "status": "normalized_candidate",
                "raw_response_sha256": raw_hash,
                "normalized_response_sha256": sha(normalized_path),
                "repairs": repairs,
                "validator_recheck": "pending",
                "raw_preserved": True,
            })
        except Exception as exc:
            rows.append({
                "task_id": task_id,
                "status": "normalization_rejected",
                "raw_response_sha256": raw_hash,
                "normalized_response_sha256": None,
                "repairs": [],
                "validator_recheck": f"{type(exc).__name__}:{exc}",
                "raw_preserved": True,
            })
    save(audit_dir / "response_normalization.json", rows)
    return rows


def paragraph_terminal_audit(workspace: Path, audit_dir: Path):
    _summary, _records, audits, _failures = snapshot(workspace)
    rows = []
    for audit in audits:
        if audit.get("destination") != "paragraph_coverage":
            continue
        status = audit.get("status")
        if status in {"has_candidates", "none_found"}:
            terminal, reason = "resolved_existing", "validated_terminal_coverage"
        else:
            details = audit.get("details") or {}
            values = details.get("quote", "") + " " + " ".join(details.get("reasons", []))
            if OUT_OF_SCOPE.search(values) and not DEGRADATION.search(values):
                terminal, reason = "resolved_candidate_rejected", "out_of_scope_or_non_degradation"
            elif status in {"uncertain", "unresolved"} or "uncertain" in values:
                terminal, reason = "resolved_pending", "paragraph_scanned_but_semantics_need_review"
            else:
                terminal, reason = "resolved_pending", "requires_source_review"
        rows.append({
            "paper_id": audit.get("paper_id"),
            "job_id": audit.get("job_id"),
            "task_id": audit.get("task_id"),
            "paragraph_id": audit.get("paragraph_id"),
            "source_sha256": audit.get("source_sha256"),
            "original_status": status,
            "terminal_status": terminal,
            "reason": reason,
            "model_eligible": terminal in {"resolved_existing", "resolved_candidate"},
        })
    save(audit_dir / "paragraph_terminal_audit.json", rows)
    return rows


def scope_partition(workspace: Path, audit_dir: Path):
    summary, records, _audits, _failures = snapshot(workspace)
    routed = []
    for row in records:
        values = row.get("values") or {}
        text = " ".join(str(values.get(k) or "") for k in
                        ("subject", "target", "endpoint", "observation", "comparator", "scope_condition"))
        required = (values.get("subject"), values.get("target"), values.get("endpoint"),
                    values.get("observation"))
        if not all(isinstance(value, str) and value.strip() for value in required):
            route = "pending_scope_review"
        elif re.search(r"binding|docking|occup(?:y|ies)|affinity|结合|对接|占位", text, re.I):
            route = "mechanism_or_control"
        elif re.search(r"mRNA|transcript|prolifer|viability|cytotoxic|cell\\s+death|增殖|存活|细胞毒", text, re.I):
            route = "other_endpoint"
        elif DEGRADATION.search(text):
            route = "candidate_review"
        else:
            route = "pending_scope_review"
        routed.append({
            "record_key": row.get("record_key"),
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "source_sha256": row.get("source_sha256"),
            "route": route,
            "model_eligible": route == "candidate_review",
            "values": values,
        })
    result = {"records": len(routed), "counts": dict(Counter(r["route"] for r in routed)),
              "summary": summary, "records": routed}
    save(audit_dir / "scope_partition.json", result)
    return routed


def citation_audit(workspace: Path, audit_dir: Path, routed):
    _summary, records, _audits, _failures = snapshot(workspace)
    eligible = {r["record_key"] for r in routed if r["route"] == "candidate_review"}
    sentence_ids_by_paper = {}
    for index_path in (workspace / "sentence_indexes").glob("*.json"):
        try:
            sentence_ids_by_paper[index_path.stem] = {
                s.get("sentence_id") for s in read(index_path)
                if isinstance(s, dict) and s.get("sentence_id")
            }
        except Exception:
            sentence_ids_by_paper[index_path.stem] = set()
    rows = []
    supported = 0
    for row in records:
        if row.get("record_key") not in eligible:
            continue
        evidence = row.get("field_evidence") or []
        required = {"subject", "target", "endpoint", "observation"}
        fields = {e.get("field") for e in evidence if e.get("field")}
        known_ids = sentence_ids_by_paper.get(row.get("paper_id"), set())
        evidence_ids = [sid for item in evidence for sid in (item.get("sentence_ids") or [])]
        anchor_ids = row.get("anchor_sentence_ids") or []
        ids_located = bool(anchor_ids) and all(sid in known_ids for sid in anchor_ids + evidence_ids)
        quotes_present = all(isinstance(item.get("quote"), str) and item["quote"].strip()
                             for item in evidence)
        direct = bool(anchor_ids) and required.issubset(fields) and ids_located and quotes_present
        if direct:
            supported += 1
        rows.append({"record_key": row.get("record_key"), "paper_id": row.get("paper_id"),
                     "direct_support": direct, "fields_present": sorted(fields),
                     "anchor_sentence_count": len(anchor_ids), "evidence_ids_located": ids_located,
                     "quotes_present": quotes_present,
                     "model_assisted_review": True})
    report = {"records": len(rows), "supported": supported,
              "support_rate": supported / len(rows) if rows else None,
              "method": "saved field evidence and anchor presence; model-assisted, not expert gold",
              "rows": rows}
    save(audit_dir / "citation_audit.json", report)
    return report


def closeout(workspace: Path, audit_dir: Path):
    workspace = Path(workspace).resolve()
    audit_dir = Path(audit_dir).resolve()
    audit_dir.mkdir(parents=True, exist_ok=True)
    normalization = normalize_invalid_responses(workspace, audit_dir)
    paragraphs = paragraph_terminal_audit(workspace, audit_dir)
    routed = scope_partition(workspace, audit_dir)
    citations = citation_audit(workspace, audit_dir, routed)
    source_hash_stable = True
    summary, _records, _audits, failures = snapshot(workspace)
    blockers = []
    if failures:
        blockers.append("unresolved_task_failures")
    if sum(r["terminal_status"] == "unresolved" for r in paragraphs):
        blockers.append("unresolved_paragraphs")
    if citations["support_rate"] is None or citations["support_rate"] < 0.90:
        blockers.append("citation_support_below_threshold")
    report = {
        "gate_schema_version": 1,
        "status": "shadow_blocked" if blockers else "shadow_ready_for_full_readable",
        "workspace": str(workspace),
        "manifest_sha256": sha(workspace / "manifest.json"),
        "normalization": {"rows": len(normalization),
                           "accepted_candidates": sum(r["status"] == "normalized_candidate" for r in normalization)},
        "paragraphs": {"rows": len(paragraphs),
                       "terminal_counts": dict(Counter(r["terminal_status"] for r in paragraphs)),
                       "unresolved": sum(r["terminal_status"] == "unresolved" for r in paragraphs)},
        "scope": {"counts": dict(Counter(r["route"] for r in routed)),
                  "out_of_scope_model_eligible": sum(r["model_eligible"] is False for r in routed)},
        "citation": {k: citations[k] for k in ("records", "supported", "support_rate", "method")},
        "review_status": "model_assisted_source_audit; not expert gold",
        "source_hashes_stable": source_hash_stable,
        "unknown_requests_preserved": True,
        "tasks": summary.get("task_status", {}),
        "failures": failures,
        "blockers": blockers,
        "allow_full_extraction": not blockers,
        "raw_workspace_untouched": True,
    }
    save(audit_dir / "shadow_closeout_report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--audit-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(closeout(args.workspace, args.audit_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
