"""Convert accepted v1 adjudication corrections into append-only record patches."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

import curation_overlay
import release_v1


def _values_container(record: dict) -> tuple[str, dict, dict]:
    if (record.get("facts") or {}).get("observations"):
        facts = copy.deepcopy(record["facts"])
        return "facts", facts, facts["observations"][0].setdefault("values", {})
    observation = copy.deepcopy(record.get("observation") or {"values": {}})
    return "observation", observation, observation.setdefault("values", {})


def _conditions(record: dict) -> tuple[dict, dict]:
    conditions = copy.deepcopy(record.get("conditions") or {"items": []})
    if not conditions.get("items"):
        conditions["items"] = [{"record_id": curation_overlay.record_id(record),
                                "values": {}, "evidence": {}}]
    return conditions, conditions["items"][0].setdefault("values", {})


def correction_changes(record: dict, corrections: dict,
                       records_by_id: dict[str, dict]) -> dict:
    changes = {}
    value_fields = {key: corrections[key] for key in
                    ("subject", "subject_scope", "target", "endpoint", "scope_condition")
                    if key in corrections}
    if "subject_scope" in value_fields and "subject" not in value_fields:
        value_fields["subject"] = value_fields.pop("subject_scope")
    observation = next((corrections[key] for key in
                        ("observation", "result_strength", "observation_strength", "observation_boundary")
                        if key in corrections), None)
    if observation is not None:
        value_fields["observation"] = observation
    if value_fields:
        name, container, values = _values_container(record)
        values.update(value_fields)
        changes[name] = container

    condition_values = {}
    if isinstance(corrections.get("conditions"), dict):
        condition_values.update(corrections["conditions"])
    for key in ("assay", "tested_concentration"):
        if key in corrections:
            condition_values[key] = corrections[key]
    if condition_values:
        conditions, values = _conditions(record)
        values.update(condition_values)
        changes["conditions"] = conditions

    relation = corrections.get("duplicate_relation")
    if relation:
        match = re.search(r"\b(?:R|E)_[A-Za-z0-9_–-]+", str(relation))
        if match and match.group(0) in records_by_id:
            target_experiment = records_by_id[match.group(0)].get("experiment_id")
            if target_experiment:
                changes["experiment_id"] = target_experiment
    secondary = corrections.get("secondary_citation")
    if isinstance(secondary, dict) and secondary.get("reference_label"):
        changes["secondary_report_of"] = f"reference {secondary['reference_label']}"
    return changes


def build_entries(run: Path, inventory_path: Path, ledger_path: Path,
                  adjudications_path: Path) -> list[dict]:
    inventory = release_v1.read(inventory_path)
    source_hashes = {row["paper_id"]: row.get("source_sha256") for row in inventory}
    baseline = release_v1.load_baseline(run)
    current, _ = curation_overlay.apply_ledger(
        baseline, curation_overlay.read_jsonl(ledger_path), source_hashes)
    by_id = {curation_overlay.record_id(row): row for row in current}
    adjudications = curation_overlay.read_jsonl(adjudications_path)
    entries = []
    for adjudication in adjudications:
        if adjudication.get("verdict") != "reliable":
            continue
        rid = adjudication["evidence_id"]
        record = by_id[rid]
        changes = correction_changes(record, adjudication.get("accepted_corrections") or {}, by_id)
        changes = {key: value for key, value in changes.items() if record.get(key) != value}
        if not changes:
            continue
        entry = {
            "revision_id": f"REV-ADJ-{rid}-FIELDS-v1",
            "operation": "patch_record",
            "record_id": rid,
            "paper_id": record["paper_id"],
            "source_sha256": record["source_sha256"],
            "before_sha256": curation_overlay.sha256_json(record),
            "changes": changes,
            "reason": "Accepted field correction from source-grounded v1 adjudication.",
            "adjudication_id": adjudication["adjudication_id"],
            "curator": "codex-main-v1",
            "expert_gold": False,
        }
        entries.append(entry)
        patched, _ = curation_overlay.apply_ledger([record], [entry], source_hashes)
        by_id[rid] = patched[0]
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--adjudications", required=True, type=Path)
    args = parser.parse_args()
    entries = build_entries(args.run, args.inventory, args.ledger, args.adjudications)
    result = curation_overlay.append_entries(args.ledger, entries)
    print(json.dumps({"patches": len(entries), "ledger": result}, ensure_ascii=False, indent=2))
