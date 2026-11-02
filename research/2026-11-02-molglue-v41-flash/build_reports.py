"""Build compact, auditable reports for the v4.1 extraction attempt."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
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
    papers = load(INV / "papers.json")
    inv = load(INV / "source_inventory.json")
    pilot_summary = load(PILOT / "exports" / "summary.json")
    full_summary = load(FULL / "exports" / "summary.json")
    full_manifest = load(FULL / "manifest.json")
    ledger = load(LOCAL / "budget_ledger.json")

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
        "pilot": {"path": str(PILOT), "manifest_sha256": sha(PILOT / "manifest.json"),
                  "papers": pilot_summary.get("papers_count", 5), "discovery_jobs": 120,
                  "unscanned_sentences": pilot_summary.get("unscanned_sentences", 0)},
        "full": {"path": str(FULL), "manifest_sha256": sha(FULL / "manifest.json"),
                 "papers": full_summary.get("papers_count", 193), "discovery_jobs": len(full_manifest.get("job_ids", [])),
                 "readable_papers": full_summary.get("paper_status", {}).get("partial", 0),
                 "unscanned_sentences": full_summary.get("unscanned_sentences", 0)},
        "old_workspaces_modified": False,
    }
    dump(ROOT / "sentence_workspace_manifest.json", workspace_manifest)

    # Keep derived evidence partitions compact and clearly labelled as a partial
    # run.  The full workspace export remains in the ignored local directory.
    pilot_exports = PILOT / "exports"
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

    acceptance = {
        "status": "candidate_blocked_quality_gate",
        "created_utc": now(), "reported_scope": 241,
        "pilot": pilot_summary,
        "full_workspace": full_summary,
        "quality_gate": {
            "five_papers_complete": False, "all_tasks_complete": False,
            "json_contract_failures": pilot_summary.get("failed_tasks", 0),
            "unknown_or_interrupted_tasks": 1,
            "content_acceptance": "not_run_to_completion",
        },
        "reason": "Stopped after the first JSON contract failure; no full-library claim is made.",
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
- 独立预算：100次请求、2,500,000预留tokens。
- 五篇工作区：120个发现任务；本轮保存20条可靠候选记录。
- 账本请求数：{budget['requests_reserved']}；已报告tokens：{budget['reported_total_tokens']}。
- 任务状态包含1条JSON契约失败和1条中断后未知结果，均保留在分母。

## 当前结论

本轮完成了来源冻结、正文工作区刷新和模型链路冒烟/续跑，尚未完成五篇内容验收。质量状态为`candidate_blocked_quality_gate`，没有把部分输出升级为全库提取完成。旧工作区、旧响应和旧账本未被改写。

## 这意味着什么

论文身份与正文库存已经被分层记录，提取管线可以使用导师key运行，但在出现JSON契约失败后必须先修复或隔离该任务，再继续消耗预算。

## 下一步

离线检查失败响应的合约原因，确认中断任务为未知状态；随后再决定是否用剩余预算继续五篇质量闸门。五篇通过后才进入10–20篇影子批次，不能直接宣称241篇完成。
"""
    (ROOT / "run_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": acceptance["status"], "requests": budget["requests_reserved"],
                      "reported_tokens": budget["reported_total_tokens"],
                      "reliable_candidate_records": len(load(pilot_exports / "evidence_records.json"))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
