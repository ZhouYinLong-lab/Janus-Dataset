"""Create a disjoint offline routing partition for source-first review.

This is a routing artifact, not a scientific adjudication.  It never upgrades
records and never edits the raw extraction.  The three routes are deliberately
disjoint so their counts close to the number of candidate records.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def route(row: dict) -> tuple[str, str]:
    reasons = set(row.get("review_reasons", []))
    if "out_of_scope_endpoint" in reasons:
        return "excluded_scope", "终点不属于蛋白降解主证据范围；保留原记录但不进入主证据集"
    if reasons & {
        "context_incomplete",
        "secondary_or_interpretive_wording",
        "target_missing",
        "semantic_pending",
    }:
        return "pending_context_or_source", "需要回看原文、拆分混合终点或确认引用性质；不升级为可靠"
    return "source_first_review", "字段可定位但仍需逐条回看原文后才能裁定"


def build(queue_path: Path, out_path: Path) -> dict:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    routed = []
    for row in records:
        item = dict(row)
        item["review_route"], item["route_reason"] = route(row)
        # The route is explicitly non-final.  Keep model isolation even for
        # rows whose endpoint is clearly out of scope.
        item["decision"] = None
        item["model_eligible"] = False
        routed.append(item)
    counts = dict(Counter(row["review_route"] for row in routed))
    result = {
        "status": "offline_review_routing_only",
        "scientific_status": "not_content_adjudication",
        "records": len(routed),
        "counts": counts,
        "routes": {
            "excluded_scope": "明确范围外，仍需保留原始记录和来源锚点",
            "pending_context_or_source": "上下文、二手转述或字段冲突待原文裁定",
            "source_first_review": "可定位但尚未完成科学内容裁定",
        },
        "records_by_route": {
            route_name: [r for r in routed if r["review_route"] == route_name]
            for route_name in counts
        },
        "source_queue": str(queue_path),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "records": len(routed), "counts": counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.queue, args.out), ensure_ascii=False, indent=2))
