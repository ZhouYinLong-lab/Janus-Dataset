"""Build a source-linked offline content-review queue from sentence exports.

The queue never upgrades a record. It only identifies why a row needs human or
source-first review and preserves the exact quote and provenance fields needed
for an auditable decision.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


OUT_OF_SCOPE = re.compile(
    r"mRNA|cytotox|viability|sensitivity|binding|affinity|prolifer|"
    r"phosphoryl|solubility|toxicity|tumou?r|cell growth|interaction|TR-FRET",
    re.I,
)


def reasons(row: dict, incomplete_candidates: set[str]) -> list[str]:
    values = row.get("values", {})
    result = []
    endpoint = values.get("endpoint") or ""
    if OUT_OF_SCOPE.search(endpoint):
        result.append("out_of_scope_endpoint")
    if not values.get("target"):
        result.append("target_missing")
    if row.get("record_status") == "semantic_pending":
        result.append("semantic_pending")
    if row.get("candidate_id") in incomplete_candidates:
        result.append("context_incomplete")
    if not result:
        result.append("source_first_review")
    return result


def build(records_path: Path, context_path: Path, out_json: Path, out_csv: Path) -> dict:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    context = json.loads(context_path.read_text(encoding="utf-8"))
    incomplete = {r.get("candidate_id") for r in context if r.get("context_complete") is False}
    queue = []
    for row in records:
        values = row.get("values", {})
        review_reasons = reasons(row, incomplete)
        queue.append({
            "record_key": row.get("record_key"),
            "candidate_id": row.get("candidate_id"),
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "source_sha256": row.get("source_sha256"),
            "endpoint": values.get("endpoint"),
            "subject": values.get("subject"),
            "target": values.get("target"),
            "observation": values.get("observation"),
            "outcome_type": row.get("outcome_type"),
            "original_quote": row.get("original_quote"),
            "anchor_sentence_ids": row.get("anchor_sentence_ids", []),
            "review_reasons": review_reasons,
            "review_status": "pending_source_review",
            "model_eligible": False,
        })
    summary = {
        "records": len(queue),
        "by_reason": dict(Counter(reason for row in queue for reason in row["review_reasons"])),
        "context_incomplete_candidates": sorted(incomplete),
        "status": "review_queue_only; no records upgraded",
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"summary": summary, "records": queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = list(queue[0]) if queue else ["record_key"]
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in queue:
            flat = dict(row)
            flat["review_reasons"] = ";".join(flat["review_reasons"])
            flat["anchor_sentence_ids"] = ";".join(flat["anchor_sentence_ids"])
            writer.writerow(flat)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.records, args.context, args.out_json, args.out_csv), ensure_ascii=False, indent=2))
