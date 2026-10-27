"""Append-only curation overlays for immutable extraction records.

The raw worker artifacts remain the source of truth.  A ledger entry either
adds a recovered record or changes fields on an existing record, with hashes
that make stale or conflicting edits fail closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def record_id(record: dict[str, Any]) -> str | None:
    return (
        record.get("evidence_id")
        or record.get("record_id")
        or record.get("candidate_id")
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Ledger line {line_no} is not an object")
        rows.append(value)
    return rows


def _set_path(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    if not dotted_path or dotted_path.startswith(".") or dotted_path.endswith("."):
        raise ValueError(f"Invalid change path: {dotted_path!r}")
    cursor: dict[str, Any] = target
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        child = cursor.get(part)
        if child is None:
            child = {}
            cursor[part] = child
        if not isinstance(child, dict):
            raise ValueError(f"Cannot descend through non-object field: {dotted_path}")
        cursor = child
    cursor[parts[-1]] = copy.deepcopy(value)


def apply_ledger(
    records: Iterable[dict[str, Any]],
    entries: Iterable[dict[str, Any]],
    source_hashes: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply ledger entries and return records plus an application audit.

    Repeating an identical ``revision_id`` is idempotent.  Reusing an ID with
    different content, changing a stale record, or targeting a changed source
    raises ``ValueError``.
    """

    indexed: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for original in records:
        rid = record_id(original)
        if not rid or rid in indexed:
            raise ValueError(f"Missing or duplicate record ID: {rid!r}")
        indexed[rid] = copy.deepcopy(original)
        order.append(rid)

    seen_revisions: dict[str, str] = {}
    audit: list[dict[str, Any]] = []
    for entry in entries:
        revision_id = entry.get("revision_id")
        if not revision_id:
            raise ValueError("Every ledger entry needs revision_id")
        entry_hash = sha256_json(entry)
        if revision_id in seen_revisions:
            if seen_revisions[revision_id] != entry_hash:
                raise ValueError(f"Conflicting duplicate revision: {revision_id}")
            audit.append({"revision_id": revision_id, "status": "duplicate_ignored"})
            continue
        seen_revisions[revision_id] = entry_hash

        rid = entry.get("record_id")
        operation = entry.get("operation")
        source_sha = entry.get("source_sha256")
        paper_id = entry.get("paper_id")
        if source_hashes is not None and paper_id:
            expected = source_hashes.get(paper_id)
            if expected != source_sha:
                raise ValueError(
                    f"Source hash mismatch for {paper_id}: {source_sha} != {expected}"
                )

        if operation == "add_record":
            added = copy.deepcopy(entry.get("record"))
            if not isinstance(added, dict) or record_id(added) != rid:
                raise ValueError(f"Invalid added record for {revision_id}")
            if rid in indexed:
                raise ValueError(f"Added record already exists: {rid}")
            added.setdefault("revision_ids", []).append(revision_id)
            indexed[rid] = added
            order.append(rid)
            audit.append(
                {
                    "revision_id": revision_id,
                    "record_id": rid,
                    "operation": operation,
                    "before_sha256": None,
                    "after_sha256": sha256_json(added),
                    "status": "applied",
                }
            )
            continue

        if operation != "patch_record" or rid not in indexed:
            raise ValueError(f"Invalid operation or target for {revision_id}")
        before = indexed[rid]
        before_hash = sha256_json(before)
        expected_before = entry.get("before_sha256")
        if expected_before and expected_before != before_hash:
            raise ValueError(f"Stale revision {revision_id}: record hash changed")
        changed = copy.deepcopy(before)
        changes = entry.get("changes")
        if not isinstance(changes, dict) or not changes:
            raise ValueError(f"Patch {revision_id} has no changes")
        for dotted_path, value in changes.items():
            _set_path(changed, dotted_path, value)
        changed.setdefault("revision_ids", []).append(revision_id)
        indexed[rid] = changed
        audit.append(
            {
                "revision_id": revision_id,
                "record_id": rid,
                "operation": operation,
                "before_sha256": before_hash,
                "after_sha256": sha256_json(changed),
                "status": "applied",
            }
        )

    return [indexed[rid] for rid in order], audit

