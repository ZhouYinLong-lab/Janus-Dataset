"""Record narrow, source-first checks for unambiguous pilot candidates.

The output is an append-only review artifact.  It does not mutate extraction
records or publish a row as model-eligible; a later release step must import
and adjudicate it explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


TARGETS = {
    "611a556fef25cdb472d020bfc15a8772d8b89a98faeabb2a313075c2abae129d": {
        "source_sentence": "As neither DRF053 nor roscovitine induced degradation of the cycKeGFP reporter in cells (Fig. 3e)",
        "conditions": "HEK293T Cas9 cells; 1 μM compound; 2 h; n=3; CycKeGFP flow analysis (Extended Data Fig. 7e)",
        "subjects": ["DRF053", "roscovitine"],
        "endpoint": "cellular cycK degradation reporter",
    },
    "519c41fdb66ac1cbcd1080882762f242463f3ca441a0b6db008ce4ba9ef48351": {
        "source_sentence": "flavopiridol ... failed to degrade cycK in cells (Fig. 3e)",
        "conditions": "HEK293T Cas9 cells; 1 μM compound; 2 h; n=3; CycKeGFP flow analysis (Extended Data Fig. 7e)",
        "subjects": ["Flavopiridol"],
        "endpoint": "cellular cycK degradation",
    },
}


def stable_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def build(records_path: Path, document_path: Path, out_path: Path) -> dict:
    records = json.loads(records_path.read_text(encoding="utf-8"))
    document = json.loads(document_path.read_text(encoding="utf-8"))
    units = document.get("units", [])
    caption = next((u for u in units if "Flow analysis of CycKeGFP degradation" in (u.get("text") or "") and "1 μM compound" in (u.get("text") or "")), None)
    if caption is None:
        raise ValueError("required CycKeGFP figure caption not found")
    doc_sha = document.get("source_sha256")
    by_key = {r.get("record_key"): r for r in records}
    decisions = []
    for record_key, spec in TARGETS.items():
        row = by_key.get(record_key)
        if row is None:
            raise ValueError(f"missing candidate {record_key}")
        values = row.get("values", {})
        quote = row.get("original_quote") or ""
        if spec["source_sentence"].split("...")[0] not in quote and spec["source_sentence"] not in quote:
            raise ValueError(f"quote mismatch for {record_key}")
        before_hash = stable_hash(row)
        decisions.append({
            "revision_id": f"offline-source-{record_key[:12]}",
            "record_key": record_key,
            "paper_id": row.get("paper_id"),
            "doi": row.get("doi"),
            "source_sha256": row.get("source_sha256"),
            "decision": "pending_release_adjudication",
            "proposed_scope_class": "molecular_glue_degradation_negative",
            "proposed_evidence_origin": "primary_report",
            "direct_primary_support": True,
            "model_eligible": False,
            "subject": spec["subjects"],
            "target": values.get("target"),
            "endpoint": spec["endpoint"],
            "outcome_type": "not_observed",
            "conditions_recovered_from_caption": spec["conditions"],
            "source_sentence_fragment": spec["source_sentence"],
            "figure_unit_id": caption.get("unit_id"),
            "figure_caption_sha256": stable_hash(caption.get("text")),
            "reviewer_kind": "offline_source_review",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reason": "正文直接报告已做的细胞降解实验阴性；图注给出对象、浓度、时间、细胞和重复数。保留为候选，待正式发布裁定。",
            "before_record_sha256": before_hash,
            "after_review_sha256": stable_hash({"record_key": record_key, "decision": "pending_release_adjudication", "conditions": spec["conditions"]}),
            "document_source_sha256": doc_sha,
        })
    result = {
        "status": "offline_source_review_only",
        "scientific_status": "candidate_rows_not_published",
        "records": decisions,
        "source_document": str(document_path),
        "source_sha256": doc_sha,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": result["status"], "records": len(decisions), "model_eligible": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.records, args.document, args.out), ensure_ascii=False, indent=2))
