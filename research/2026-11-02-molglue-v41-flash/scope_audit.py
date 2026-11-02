"""Offline scope audit for sentence_v3 evidence records.

This is a conservative routing report, not a scientific gold label. It keeps the
raw exported records intact and flags endpoints that cannot enter the primary
molecular-glue protein-degradation queue without further review.
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
DEGRADATION = re.compile(
    r"degrad|deplet|protein\s+(?:level|abundance|expression|reduction|decrease)",
    re.I,
)
MECHANISM = re.compile(r"ubiquitin|recruit|proteasome|polyubiquit", re.I)


def classify(endpoint: str) -> str:
    endpoint = endpoint or ""
    if OUT_OF_SCOPE.search(endpoint):
        return "out_of_scope_endpoint"
    if DEGRADATION.search(endpoint):
        return "degradation_or_protein_boundary"
    if MECHANISM.search(endpoint):
        return "degradation_mechanism_review"
    return "manual_scope_review"


def run(records_path: Path, out_json: Path, out_csv: Path) -> dict:
    rows = json.loads(records_path.read_text(encoding="utf-8"))
    audited = []
    for row in rows:
        values = row.get("values", {})
        scope = classify(values.get("endpoint"))
        audited.append({
            "record_key": row.get("record_key"),
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "endpoint": values.get("endpoint"),
            "outcome_type": row.get("outcome_type"),
            "scope_route": scope,
            "model_eligible_without_review": False,
            "reason": "Endpoint routing only; direct source review still required",
        })
    summary = {
        "records": len(audited),
        "by_scope_route": dict(Counter(r["scope_route"] for r in audited)),
        "by_paper": {
            paper: dict(Counter(r["scope_route"] for r in audited if r["paper_id"] == paper))
            for paper in sorted({r["paper_id"] for r in audited})
        },
        "source_records": str(records_path.resolve()),
        "scientific_status": "routing_audit_not_content_acceptance",
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"summary": summary, "records": audited}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(audited[0]) if audited else ["record_key"])
        writer.writeheader()
        writer.writerows(audited)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.records, args.out_json, args.out_csv), ensure_ascii=False, indent=2))
