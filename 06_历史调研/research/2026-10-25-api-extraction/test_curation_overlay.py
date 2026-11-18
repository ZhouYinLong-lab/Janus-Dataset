import importlib.util
from pathlib import Path

import pytest


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("curation_overlay", HERE / "curation_overlay.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base_record():
    return {
        "evidence_id": "E1",
        "paper_id": "P1",
        "source_sha256": "source-one",
        "facts": {"target": "T1"},
    }


def test_patch_is_hash_guarded_and_duplicate_revision_is_idempotent():
    row = base_record()
    entry = {
        "revision_id": "REV1",
        "operation": "patch_record",
        "record_id": "E1",
        "paper_id": "P1",
        "source_sha256": "source-one",
        "before_sha256": MODULE.sha256_json(row),
        "changes": {"facts.target": "T2", "conditions.dose": None},
    }
    records, audit = MODULE.apply_ledger(
        [row], [entry, entry], source_hashes={"P1": "source-one"}
    )
    assert records[0]["facts"]["target"] == "T2"
    assert records[0]["conditions"]["dose"] is None
    assert records[0]["revision_ids"] == ["REV1"]
    assert [item["status"] for item in audit] == ["applied", "duplicate_ignored"]


def test_changed_source_or_stale_record_fails_closed():
    row = base_record()
    entry = {
        "revision_id": "REV1",
        "operation": "patch_record",
        "record_id": "E1",
        "paper_id": "P1",
        "source_sha256": "wrong",
        "before_sha256": MODULE.sha256_json(row),
        "changes": {"facts.target": "T2"},
    }
    with pytest.raises(ValueError, match="Source hash mismatch"):
        MODULE.apply_ledger([row], [entry], source_hashes={"P1": "source-one"})
    entry["source_sha256"] = "source-one"
    entry["before_sha256"] = "stale"
    with pytest.raises(ValueError, match="Stale revision"):
        MODULE.apply_ledger([row], [entry], source_hashes={"P1": "source-one"})


def test_add_record_requires_new_stable_id():
    added = {
        "evidence_id": "E2",
        "paper_id": "P1",
        "source_sha256": "source-one",
    }
    entry = {
        "revision_id": "REV-ADD",
        "operation": "add_record",
        "record_id": "E2",
        "paper_id": "P1",
        "source_sha256": "source-one",
        "record": added,
    }
    records, _ = MODULE.apply_ledger(
        [base_record()], [entry], source_hashes={"P1": "source-one"}
    )
    assert [MODULE.record_id(row) for row in records] == ["E1", "E2"]
    with pytest.raises(ValueError, match="already exists"):
        MODULE.apply_ledger([base_record(), added], [entry])


def test_append_entries_is_idempotent(tmp_path):
    path = tmp_path / "history.jsonl"
    entry = {"revision_id": "R1", "operation": "add_record"}
    assert MODULE.append_entries(path, [entry])["appended"] == 1
    assert MODULE.append_entries(path, [entry])["appended"] == 0
    with pytest.raises(ValueError, match="Conflicting duplicate revision"):
        MODULE.append_entries(path, [dict(entry, operation="patch_record")])
