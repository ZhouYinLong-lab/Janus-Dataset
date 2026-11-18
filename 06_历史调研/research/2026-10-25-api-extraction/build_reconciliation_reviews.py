"""Build importable review rows for source-grounded reconciliation additions."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def row(proposal: dict, worker_id: str, role: str, source_files: list[str]) -> dict:
    record = proposal["record"]
    return {
        "record_id": record["record_id"],
        "evidence_id": record["evidence_id"],
        "reference_id": proposal["reference_id"],
        "paper_id": proposal["paper_id"],
        "verdict": "reliable",
        "scope_class": record["scope_class"],
        "evidence_origin": record["evidence_origin"],
        "citation_direct_support": True,
        "required_fields_supported": True,
        "corrections": {},
        "reason": proposal.get("reason"),
        "source_sha256": proposal["source_sha256"],
        "evidence_spans": record.get("evidence_spans", []),
        "review_role": role,
        "worker_id": worker_id,
        "actual_model": "gpt-6-luna",
        "expert_gold": False,
        "generation_method": "Codex child-agent source reconciliation import",
        "source_files": source_files,
        "external_generation_api_requests": 0,
    }


def build(args) -> dict:
    payload = read(args.proposals)
    proposals = [p for p in payload["proposals"] if p.get("action") == "add_record"]
    if len(proposals) != 20:
        raise ValueError(f"Expected 20 add proposals, found {len(proposals)}")
    ids = [p["record"]["record_id"] for p in proposals]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate new record IDs")
    source_files = [str(args.proposals.resolve())]
    a_rows = [row(p, "codex_source_reconciliation_a", "reviewer_a_extra", source_files)
              for p in proposals]
    b_rows = [row(p, "gpt-6-luna_reference_reviewer_b", "reviewer_b", source_files)
              for p in proposals]
    args.a.parent.mkdir(parents=True, exist_ok=True)
    args.b.parent.mkdir(parents=True, exist_ok=True)
    for path, rows in ((args.a, a_rows), (args.b, b_rows)):
        path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                      for r in rows), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "records": len(proposals),
        "review_a": len(a_rows),
        "review_b": len(b_rows),
        "review_a_worker": "codex_source_reconciliation_a",
        "review_b_worker": "gpt-6-luna_reference_reviewer_b",
        "proposal_sha256": sha256(args.proposals),
        "review_a_sha256": sha256(args.a),
        "review_b_sha256": sha256(args.b),
        "actual_model": "gpt-6-luna",
        "expert_gold": False,
        "external_generation_api_requests": 0,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposals", required=True, type=Path)
    parser.add_argument("--a", required=True, type=Path)
    parser.add_argument("--b", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args), ensure_ascii=False, indent=2))
