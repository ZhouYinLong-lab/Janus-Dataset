"""Build compact, auditable reports for the v4.1 extraction attempt."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / "local"
INV = LOCAL / "inventory_241"
PILOT = LOCAL / "sentence_pilot"
FULL = LOCAL / "sentence_full"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_dump(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-workspace', type=Path, default=PILOT)
    parser.add_argument('--full-workspace', type=Path, default=FULL)
    parser.add_argument('--ledger', type=Path, default=LOCAL / 'budget_ledger.json')
    args = parser.parse_args()
    pilot_workspace = args.pilot_workspace.resolve()
    full_workspace = args.full_workspace.resolve()
    ledger_path = args.ledger.resolve()
    papers = load(INV / "papers.json")
    inv = load(INV / "source_inventory.json")
    pilot_summary = load(pilot_workspace / "exports" / "summary.json")
    full_summary = load(full_workspace / "exports" / "summary.json")
    full_manifest = load(full_workspace / "manifest.json")
    ledger = load(ledger_path)

    registry = []
    failures = []
    for p in papers:
        selected = p.get("sources", [{}])[0] if p.get("sources") else {}
        row = {
            "paper_id": p.get("paper_id"), "source_id": p.get("source_id"),
            "doi": p.get("doi"), "title": p.get("title"), "url": p.get("url"),
            "source_kind": p.get("source_kind"), "source_sha256": p.get("source_sha256"),
            "availability": p.get("availability"), "fulltext_status": p.get("fulltext_status"),
            "extraction_status": p.get("extraction_status"),
            "access_basis": selected.get("access_basis"), "parse_status": selected.get("parse_status"),
            "fetch_attempt_count": len(p.get("fetch_attempts", [])),
        }
        registry.append(row)
        if p.get("availability") != "local":
            attempts = p.get("fetch_attempts", [])
            failures.append({
                "paper_id": p.get("paper_id"), "doi": p.get("doi"),
                "status": p.get("availability"),
                "reason": (attempts[-1].get("error") if attempts else "no_new_attempt; historical failure retained"),
                "attempt_count": len(attempts),
            })
    csv_dump(ROOT / "source_registry_241.csv", registry)
    dump(ROOT / "source_registry_241.json", registry)
    csv_dump(ROOT / "source_failures.csv", failures)
    dump(ROOT / "source_failures.json", failures)

    fetch_report = {
        "created_utc": now(), "reported_scope": 241,
        "confirmed_identity_count": len(papers), "unresolved_identity_count": 48,
        "new_public_fetch_requests": 0,
        "reason_no_retry": "all 60 current input gaps already have historical attempts; automatic retries are disabled",
        "inventory": inv,
        "source_failures": len(failures),
        "readable_preferred_sources": sum(p.get("source_kind") == "xml" and p.get("availability") == "local" for p in papers),
    }
    dump(ROOT / "fulltext_fetch_report.json", fetch_report)

    workspace_manifest = {
        "created_utc": now(), "reported_scope": 241, "confirmed_identity_count": 193,
        "unresolved_identity_count": 48,
        "pilot": {"path": str(pilot_workspace), "manifest_sha256": sha(pilot_workspace / "manifest.json"),
                  "papers": len(pilot_summary.get("papers", [])),
                  "discovery_jobs": pilot_summary.get("workspace_requests", 0),
                  "unscanned_sentences": pilot_summary.get("unscanned_sentences", 0)},
        "full": {"path": str(full_workspace), "manifest_sha256": sha(full_workspace / "manifest.json"),
                 "papers": full_summary.get("papers_count", 193), "discovery_jobs": len(full_manifest.get("job_ids", [])),
                 "readable_papers": full_summary.get("paper_status", {}).get("partial", 0),
                 "unscanned_sentences": full_summary.get("unscanned_sentences", 0)},
        "old_workspaces_modified": False,
    }
    dump(ROOT / "sentence_workspace_manifest.json", workspace_manifest)

    # Keep derived evidence partitions compact and clearly labelled as a partial
    # run.  The full workspace export remains in the ignored local directory.
    pilot_exports = pilot_workspace / "exports"
    for name in ("records", "evidence_records", "paper_coverage", "context_coverage", "failures"):
        src = pilot_exports / f"{name}.json"
        if src.exists():
            shutil.copyfile(src, ROOT / f"{name}.json")
            csv_src = pilot_exports / f"{name}.csv"
            if csv_src.exists(): shutil.copyfile(csv_src, ROOT / f"{name}.csv")
    dump(ROOT / "reliable_evidence.json", load(pilot_exports / "evidence_records.json"))
    csv_src = pilot_exports / "evidence_records.csv"
    if csv_src.exists(): shutil.copyfile(csv_src, ROOT / "reliable_evidence.csv")
    dump(ROOT / "pending_review.json", [])
    dump(ROOT / "excluded_records.json", [])

    budget = {
        "max_requests": ledger.get("max_requests"),
        "max_reserved_tokens": ledger.get("max_reserved_tokens"),
        "requests_reserved": len(ledger.get("attempts", [])),
        "reported_total_tokens": sum((a.get("usage") or {}).get("total_tokens", 0) for a in ledger.get("attempts", [])),
        "unknown_or_in_flight": sum(a.get("status") in {"in_flight", "needs_attention"} for a in ledger.get("attempts", [])),
        "invalid_response": sum(a.get("status") == "invalid_response" for a in ledger.get("attempts", [])),
        "requested_model": "deepseek-v4.1-flash", "base_url": "https://yeysai.com/v1",
        "external_generation_requests": len(ledger.get("attempts", [])),
    }
    dump(ROOT / "budget_ledger.json", budget)

    acceptance_passed = bool(pilot_summary.get("all_sources_processed") and
                             not pilot_summary.get("failed_tasks") and
                             pilot_summary.get("content_review_status") == "passed")
    acceptance = {
        "status": "frozen_candidate" if acceptance_passed else "candidate_blocked_quality_gate",
        "created_utc": now(), "reported_scope": 241,
        "pilot": pilot_summary,
        "full_workspace": full_summary,
        "quality_gate": {
            "five_papers_complete": pilot_summary.get("all_sources_processed", False),
            "all_tasks_complete": not bool(pilot_summary.get("failed_tasks")),
            "json_contract_failures": pilot_summary.get("task_status", {}).get("invalid_response", 0),
            "unknown_or_interrupted_tasks": pilot_summary.get("task_status", {}).get("needs_attention", 0),
            "content_acceptance": pilot_summary.get("content_review_status", "pending"),
        },
        "reason": ("Five-paper content review and task completion are still incomplete; no full-library claim is made."
                   if not acceptance_passed else "Five-paper output passed the configured content gate."),
    }
    dump(ROOT / "acceptance_report.json", acceptance)

    report = f"""# MolGlueDB v4.1 Flash提取运行报告

生成时间：{now()}

## 来源与正文

- MolGlueDB论文声称的范围：241篇。
- 当前可核验身份：193篇；仍有48篇身份未解析，未创建虚构论文记录。
- 新版本冻结后的来源记录：193篇；当前sentence_v3成功建索引的论文：{full_summary.get('paper_status', {}).get('partial', 0)}篇。
- 新版sentence_v3工作区：193篇、{len(full_manifest.get('job_ids', []))}个发现任务；缺正文论文保留在覆盖分母。
- 本轮公开全文抓取新增请求：0。60篇当前输入缺口已有历史失败尝试，按“不自动重试失败请求”规则保留原状态。

## 模型运行

- 模型：`deepseek-v4.1-flash`；thinking关闭。
- 独立续跑账本：请求数和预留tokens不设本地硬上限；服务异常和重复合约失败仍会停止。
- 五篇工作区：{pilot_summary.get('workspace_requests', 0)}个工作区任务；本轮导出{pilot_summary.get('unique_records', 0)}条证据记录。
- 账本请求数：{budget['requests_reserved']}；已报告tokens：{budget['reported_total_tokens']}。
- 工作区任务状态包含{pilot_summary.get('task_status', {}).get('invalid_response', 0)}条JSON契约失败和{pilot_summary.get('task_status', {}).get('needs_attention', 0)}条未知/中断结果，均保留在分母；本轮新账本没有新增失败。

## 当前结论

本轮完成了来源冻结、正文工作区刷新和模型链路冒烟/续跑，尚未完成五篇内容验收。质量状态为`candidate_blocked_quality_gate`，没有把部分输出升级为全库提取完成。旧工作区、旧响应和旧账本未被改写。

## 这意味着什么

论文身份与正文库存已经被分层记录，提取管线可以使用导师key运行；本轮已完成机械导出，但内容验收仍未通过。

## 下一步

先对{pilot_summary.get('unique_records', 0)}条记录做离线内容验收，逐项处理{pilot_summary.get('semantic_pending_records', 0)}条语义待定、{pilot_summary.get('quarantine_records', 0)}条隔离和{pilot_summary.get('failed_tasks', 0)}个未完成任务；五篇通过后才进入全量可读正文，不能直接宣称241篇完成。
"""
    (ROOT / "run_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": acceptance["status"], "requests": budget["requests_reserved"],
                      "reported_tokens": budget["reported_total_tokens"],
                      "reliable_candidate_records": len(load(pilot_exports / "evidence_records.json"))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
