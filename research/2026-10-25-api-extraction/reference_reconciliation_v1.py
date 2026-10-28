"""Convert source-grounded core-reference reconciliation into append-only records."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import curation_overlay


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stable_id(prefix: str, value) -> str:
    return prefix + hashlib.sha256(curation_overlay.canonical_bytes(value)).hexdigest()[:20]


def proposals(path: Path) -> list[dict]:
    payload = read(path)
    rows = (payload.get("proposals") or payload.get("recommendations")
            or payload.get("items") or [])
    if not rows:
        raise ValueError(f"No reconciliation proposals in {path}")
    return rows


def _document_unit(workspace: Path, paper_id: str, unit_id: str) -> dict:
    document = read(workspace / "documents" / f"{paper_id}.json")
    return next(unit for unit in document["units"] if unit["unit_id"] == unit_id)


def _normalize_span(span: dict, workspace: Path, paper_id: str, evidence_id: str) -> dict:
    span = copy.deepcopy(span)
    unit = _document_unit(workspace, paper_id, span["unit_id"])
    quote = span["quote"]
    start, end = span["char_start"], span["char_end"]
    if unit["text"][start:end] != quote:
        raise ValueError(f"Quote/offset mismatch: {paper_id} {span['unit_id']}")
    span.setdefault("sentence_ids", [])
    span.setdefault("kind", unit.get("kind"))
    span.setdefault("locator", unit.get("locator"))
    span["mention_id"] = stable_id(
        "M_", [evidence_id, span["unit_id"], start, end, quote])
    return span


def normalize_record(item: dict, inventory: dict[str, dict], workspace: Path,
                     worker_id: str) -> dict:
    embedded = item.get("record") or {}
    paper_id = item.get("paper_id") or embedded.get("paper_id")
    reference_id = item["reference_id"]
    if not paper_id:
        raise ValueError(f"Missing paper identity: {reference_id}")
    inventory_row = inventory[paper_id]
    expected_source = inventory_row.get("source_sha256")
    supplied_source = item.get("source_sha256", embedded.get("source_sha256", expected_source))
    if supplied_source != expected_source:
        raise ValueError(f"Source hash mismatch: {reference_id}")
    if item.get("record"):
        record = copy.deepcopy(item["record"])
    else:
        spans = item.get("evidence_spans") or item.get("support") or []
        identity = [paper_id, reference_id, expected_source]
        evidence_id = (item.get("proposed_evidence_id")
                       or stable_id("E_RECON_", f"v1|{paper_id}|{reference_id}|{expected_source}"))
        record = {
            "evidence_id": evidence_id,
            "record_id": evidence_id,
            "experiment_id": stable_id("X_", identity),
            "paper_id": paper_id,
            "doi": inventory_row.get("doi"),
            "source_sha256": expected_source,
            "scope_class": item["scope_class"],
            "evidence_origin": item["evidence_origin"],
            "facts": {
                "status": "observations", "reason": None,
                "observations": [{
                    "outcome_type": "not_observed",
                    "values": copy.deepcopy(item["values"]),
                    "evidence": {},
                }],
            },
            "conditions": {"items": [{
                "record_id": evidence_id,
                "values": copy.deepcopy(item.get("conditions") or {}),
                "evidence": {},
            }]},
            "evidence_spans": copy.deepcopy(spans),
            "final_status": "pending_review",
            "model_eligibility": {
                "training": False, "rag": False,
                "reason": "requires_independent_reference_reconciliation_reviews",
            },
            "generation_method": "Codex child-agent source reconciliation",
            "model": None,
            "worker_id": worker_id,
            "expert_gold": False,
        }
    evidence_id = curation_overlay.record_id(record)
    if record.get("paper_id") != paper_id or record.get("source_sha256") != expected_source:
        raise ValueError(f"Record identity mismatch: {reference_id}")
    record["reference_reconciliation_id"] = reference_id
    record["evidence_spans"] = [
        _normalize_span(span, workspace, paper_id, evidence_id)
        for span in record.get("evidence_spans") or []
    ]
    if not record["evidence_spans"]:
        raise ValueError(f"Missing evidence spans: {reference_id}")
    return record


def _current_records(run: Path, ledger: Path, inventory: dict[str, dict]) -> dict[str, dict]:
    rows = []
    for name in ("reliable_evidence.json", "pending_review.json", "excluded_records.json"):
        rows.extend(read(run / "exports" / name))
    source_hashes = {pid: row.get("source_sha256") for pid, row in inventory.items()}
    current, _ = curation_overlay.apply_ledger(
        rows, curation_overlay.read_jsonl(ledger), source_hashes)
    return {curation_overlay.record_id(row): row for row in current}


def _patched_container(record: dict, changes: dict, conditions: dict) -> dict:
    facts = copy.deepcopy(record.get("facts") or {})
    observations = facts.setdefault("observations", [])
    if not observations:
        observations.append({"values": {}, "evidence": {}})
    values = observations[0].setdefault("values", {})
    for path, value in changes.items():
        prefix = "facts.observations[0].values."
        if not path.startswith(prefix):
            raise ValueError(f"Unsupported reconciled patch path: {path}")
        values[path[len(prefix):]] = copy.deepcopy(value)
    patched = {"facts": facts}
    if conditions:
        condition_container = copy.deepcopy(record.get("conditions") or {"items": []})
        if not condition_container.get("items"):
            condition_container["items"] = [{
                "record_id": curation_overlay.record_id(record), "values": {}, "evidence": {}}]
        condition_container["items"][0].setdefault("values", {}).update(copy.deepcopy(conditions))
        patched["conditions"] = condition_container
    return patched


def build(proposal_paths: list[Path], inventory_path: Path, workspace: Path,
          run: Path | None = None, ledger: Path | None = None) -> list[dict]:
    inventory_rows = read(inventory_path)
    inventory = {row["paper_id"]: row for row in inventory_rows}
    current = _current_records(run, ledger, inventory) if run and ledger else {}
    entries, seen_references, seen_records = [], set(), set()
    for path in proposal_paths:
        payload = read(path)
        worker_id = payload.get("worker_id") or "unknown-reconciliation-worker"
        for item in proposals(path):
            reference_id = item["reference_id"]
            if reference_id in seen_references:
                raise ValueError(f"Duplicate reference proposal: {reference_id}")
            seen_references.add(reference_id)
            action = item.get("action") or item.get("proposal") or item.get("decision")
            if action == "retain_failed_reference_mapping":
                continue
            if action == "patch_existing_record":
                rid = item["evidence_id"]
                if rid not in current:
                    raise ValueError(f"Unknown patch target: {rid}")
                record = current[rid]
                changes = _patched_container(
                    record, item.get("changes") or {}, item.get("conditions") or {})
                entry = {
                    "revision_id": f"REV-REF-{reference_id}-FIELDS-v1",
                    "operation": "patch_record", "record_id": rid,
                    "paper_id": record["paper_id"],
                    "source_sha256": record["source_sha256"],
                    "before_sha256": curation_overlay.sha256_json(record),
                    "changes": changes,
                    "reason": item.get("reason") or "Source-grounded reference field recovery.",
                    "reference_id": reference_id, "curator": "codex-main-v1",
                    "expert_gold": False,
                }
                entries.append(entry)
                patched, _ = curation_overlay.apply_ledger(
                    [record], [entry], {record["paper_id"]: record["source_sha256"]})
                current[rid] = patched[0]
                continue
            record = normalize_record(item, inventory, workspace, worker_id)
            rid = curation_overlay.record_id(record)
            if rid in seen_records:
                raise ValueError(f"Duplicate reconciled record ID: {rid}")
            seen_records.add(rid)
            entries.append({
                "revision_id": f"REV-REF-{reference_id}-RECOVERY-v1",
                "operation": "add_record",
                "record_id": rid,
                "paper_id": record["paper_id"],
                "source_sha256": record["source_sha256"],
                "record": record,
                "reason": item.get("reason") or "Source-grounded core-reference recovery.",
                "reference_id": reference_id,
                "curator": "codex-main-v1",
                "expert_gold": False,
            })
    return entries


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8")


def merge_ledger(base_path: Path, entries: list[dict]) -> list[dict]:
    """Return an append-only ledger while making repeated reconciliation idempotent."""
    base = curation_overlay.read_jsonl(base_path)
    merged = list(base)
    by_revision = {row.get("revision_id"): row for row in base if row.get("revision_id")}
    for entry in entries:
        revision_id = entry.get("revision_id")
        if not revision_id:
            raise ValueError("Reconciliation entry lacks revision_id")
        previous = by_revision.get(revision_id)
        if previous is not None:
            if curation_overlay.canonical_bytes(previous) != curation_overlay.canonical_bytes(entry):
                raise ValueError(f"Revision collision with different content: {revision_id}")
            continue
        merged.append(entry)
        by_revision[revision_id] = entry
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", action="append", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--combined-output", type=Path)
    args = parser.parse_args()
    if bool(args.run) != bool(args.ledger):
        parser.error("--run and --ledger must be supplied together")
    result = build(args.proposal, args.inventory, args.workspace, args.run, args.ledger)
    write_jsonl(args.output, result)
    combined = None
    if args.combined_output:
        if not args.ledger:
            parser.error("--combined-output requires --ledger")
        combined = merge_ledger(args.ledger, result)
        write_jsonl(args.combined_output, combined)
    print(json.dumps({
        "records": len(result),
        "reference_ids": [row["reference_id"] for row in result],
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "combined_records": len(combined) if combined is not None else None,
        "combined_output_sha256": (
            hashlib.sha256(args.combined_output.read_bytes()).hexdigest()
            if args.combined_output else None),
        "external_generation_api_requests": 0,
    }, ensure_ascii=False, indent=2))
