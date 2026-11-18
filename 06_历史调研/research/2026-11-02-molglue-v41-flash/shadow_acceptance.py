"""Offline acceptance report for a completed shadow sentence_v3 batch.

This report is conservative: mechanical records are never promoted to
scientific gold, and scope flags block full-corpus release until reviewed.
No network calls or workspace mutations are performed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parent / "2026-10-25-api-extraction"
if str(EXTRACTION) not in sys.path:
    sys.path.insert(0, str(EXTRACTION))

from corpus import read, save, sha  # noqa: E402
from sentence_export import snapshot  # noqa: E402
from sentence_workspace import verify  # noqa: E402


DEGRADATION_TERMS = re.compile(
    r"degrad|deplet|protein\s+level|protein\s+abundance|proteasom|ubiquitin|"
    r"蛋白.*降解|蛋白.*下降|蛋白.*丰度|泛素", re.I)
SCOPE_ONLY_TERMS = {
    "docking": re.compile(r"dock|molecular\s+model|分子对接", re.I),
    "binding": re.compile(r"binding\s+(?:site|pocket|affinity)|occup(?:y|ies)|fit|亲和|结合位点|占据", re.I),
    "mrna": re.compile(r"\bmRNA\b|transcript|转录本", re.I),
    "growth_or_viability": re.compile(r"prolifer|viability|cytotoxic|cell\s+death|抗增殖|细胞毒|存活率", re.I),
}


def _scope_flags(record):
    values = record.get("values") or {}
    text = " ".join(str(values.get(k) or "") for k in
                    ("subject", "target", "endpoint", "observation", "comparator", "scope_condition"))
    if DEGRADATION_TERMS.search(text):
        return []
    return [name for name, pattern in SCOPE_ONLY_TERMS.items() if pattern.search(text)]


def _ledger_metrics(ledger):
    attempts = ledger.get("attempts", [])
    statuses = Counter(a.get("status") for a in attempts)
    request_hashes = [a.get("request_sha256") for a in attempts if a.get("request_sha256")]
    duplicates = len(request_hashes) - len(set(request_hashes))
    return {
        "requests": len(attempts),
        "statuses": dict(statuses),
        "reserved_tokens": sum(a.get("reserved_tokens", 0) for a in attempts),
        "reported_total_tokens": sum((a.get("usage") or {}).get("total_tokens", 0)
                                      for a in attempts if isinstance(a.get("usage"), dict)),
        "attempts_without_usage": sum(not isinstance(a.get("usage"), dict) for a in attempts),
        "duplicate_request_hashes": duplicates,
        "global_stop": ledger.get("global_stop"),
    }


def build(workspace, ledger_path, out):
    workspace = Path(workspace).resolve()
    ledger_path = Path(ledger_path).resolve()
    out = Path(out).resolve()
    source_hashes_stable = True
    source_hash_error = None
    try:
        manifest = verify(workspace)
    except Exception as exc:  # report the gate failure instead of hiding it
        manifest = read(workspace / "manifest.json")
        source_hashes_stable = False
        source_hash_error = f"{type(exc).__name__}: {exc}"
    summary, records, audits, failures = snapshot(workspace)
    ledger = read(ledger_path)
    ledger_metrics = _ledger_metrics(ledger)
    task_statuses = Counter()
    state_path = workspace / "candidate_state.json"
    state = read(state_path) if state_path.is_file() else {"tasks": {}}
    for entry in state.get("tasks", {}).values():
        task_statuses[entry.get("status", "missing")] += 1

    scope_violations = []
    for record in records:
        flags = _scope_flags(record)
        if flags:
            scope_violations.append({
                "paper_id": record.get("paper_id"),
                "record_key": record.get("record_key"),
                "record_status": record.get("record_status"),
                "flags": flags,
                "values": record.get("values"),
            })

    nonterminal = {k: v for k, v in task_statuses.items() if k != "complete"}
    blockers = []
    if nonterminal:
        blockers.append("nonterminal_tasks")
    if summary.get("unresolved_paragraphs", 0):
        blockers.append("unresolved_paragraphs")
    if not source_hashes_stable:
        blockers.append("source_hash_changed_or_workspace_invalid")
    if ledger_metrics["duplicate_request_hashes"]:
        blockers.append("duplicate_paid_request_hashes")
    if ledger_metrics["global_stop"]:
        blockers.append("ledger_global_stop")
    if scope_violations:
        blockers.append("scope_violations_require_review")
    # A scientific citation rate is not inferred from mechanical validation.
    citation_support_rate = None
    blockers.append("independent_citation_review_pending")

    report = {
        "status": "shadow_blocked" if blockers else "shadow_ready_for_full_readable",
        "workspace": str(workspace),
        "manifest_sha256": sha(workspace / "manifest.json"),
        "papers": summary.get("papers", len(manifest.get("papers", []))),
        "records": summary.get("records", len(records)),
        "record_status": summary.get("record_status", {}),
        "tasks": dict(task_statuses),
        "nonterminal_tasks": nonterminal,
        "unscanned_sentences": summary.get("unscanned_sentences", 0),
        "unresolved_paragraphs": summary.get("unresolved_paragraphs", 0),
        "optional_conditions_gaps": summary.get("optional_conditions_gaps", 0),
        "source_hashes_stable": source_hashes_stable,
        "source_hash_error": source_hash_error,
        "scope_violations": scope_violations,
        "scope_violation_count": len(scope_violations),
        "citation_support_rate": citation_support_rate,
        "independent_review_complete": False,
        "ledger": ledger_metrics,
        "failures": failures,
        "blockers": blockers,
        "allow_full_extraction": not blockers,
        "expert_gold": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    save(out, report)
    md = out.with_suffix(".md")
    lines = ["# 影子批次离线验收报告", "", f"状态：`{report['status']}`", "",
             f"论文：{report['papers']}；记录：{report['records']}；请求：{ledger_metrics['requests']}。", "",
             f"任务状态：{dict(task_statuses)}", "",
             f"范围问题：{len(scope_violations)}；未解决段落：{report['unresolved_paragraphs']}；",
             f"来源哈希稳定：{source_hashes_stable}。", "",
             "阻塞项：" + ("、".join(blockers) if blockers else "无"), "",
             "独立内容复核未完成，机械通过不等同于科学确认。"]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.workspace, args.ledger, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
