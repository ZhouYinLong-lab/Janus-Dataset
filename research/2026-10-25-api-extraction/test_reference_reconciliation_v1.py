import json
from pathlib import Path

import pytest

import reference_reconciliation_v1 as rr


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(tmp_path):
    workspace = tmp_path / "ws"
    write(workspace / "documents" / "P1.json", {
        "units": [{"unit_id": "P1:u1", "text": "negative result", "kind": "body",
                   "locator": "p1"}]})
    inventory = tmp_path / "papers.json"
    write(inventory, [{"paper_id": "P1", "doi": "10.1/x", "source_sha256": "sha"}])
    proposal = tmp_path / "proposal.json"
    write(proposal, {"worker_id": "w1", "recommendations": [{
        "reference_id": "P1-N1", "paper_id": "P1", "source_sha256": "sha",
        "scope_class": "molecular_glue_degradation_negative",
        "evidence_origin": "primary_report",
        "values": {"subject": "S", "target": "T", "endpoint": "protein degradation",
                   "observation": "negative result"},
        "conditions": {},
        "evidence_spans": [{"unit_id": "P1:u1", "char_start": 0, "char_end": 15,
                            "quote": "negative result"}],
    }]})
    return workspace, inventory, proposal


def test_build_is_stable_and_validates_quote_offsets(tmp_path):
    workspace, inventory, proposal = fixture(tmp_path)
    first = rr.build([proposal], inventory, workspace)
    second = rr.build([proposal], inventory, workspace)
    assert first == second
    record = first[0]["record"]
    assert record["reference_reconciliation_id"] == "P1-N1"
    assert record["evidence_spans"][0]["mention_id"].startswith("M_")
    payload = json.loads(proposal.read_text())
    payload["recommendations"][0]["evidence_spans"][0]["char_end"] = 14
    write(proposal, payload)
    with pytest.raises(ValueError, match="Quote/offset"):
        rr.build([proposal], inventory, workspace)


def test_source_hash_change_fails_closed(tmp_path):
    workspace, inventory, proposal = fixture(tmp_path)
    payload = json.loads(proposal.read_text())
    payload["recommendations"][0]["source_sha256"] = "changed"
    write(proposal, payload)
    with pytest.raises(ValueError, match="Source hash"):
        rr.build([proposal], inventory, workspace)


def test_patch_converts_indexed_value_paths_to_hash_guarded_container(tmp_path):
    workspace, inventory, _ = fixture(tmp_path)
    run = tmp_path / "run"
    baseline = {"evidence_id": "E1", "paper_id": "P1", "source_sha256": "sha",
                "facts": {"observations": [{"values": {"target": "old"}}]}}
    write(run / "exports" / "reliable_evidence.json", [baseline])
    write(run / "exports" / "pending_review.json", [])
    write(run / "exports" / "excluded_records.json", [])
    ledger = tmp_path / "history.jsonl"
    ledger.write_text("", encoding="utf-8")
    patch = tmp_path / "patch.json"
    write(patch, {"worker_id": "w", "items": [{
        "reference_id": "P1-N2", "paper_id": "P1", "source_sha256": "sha",
        "action": "patch_existing_record", "evidence_id": "E1",
        "changes": {"facts.observations[0].values.target": "new"},
        "conditions": {"assay": "test"},
    }]})
    entries = rr.build([patch], inventory, workspace, run, ledger)
    assert entries[0]["changes"]["facts"]["observations"][0]["values"]["target"] == "new"
    assert entries[0]["changes"]["conditions"]["items"][0]["values"]["assay"] == "test"


def test_merge_ledger_is_idempotent_and_rejects_revision_collision(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    base = {"revision_id": "R1", "operation": "patch_record", "record_id": "E1"}
    ledger.write_text(json.dumps(base) + "\n", encoding="utf-8")
    entry = {"revision_id": "R2", "operation": "add_record", "record_id": "E2"}
    assert rr.merge_ledger(ledger, [entry, entry]) == [base, entry]
    with pytest.raises(ValueError, match="Revision collision"):
        rr.merge_ledger(ledger, [{**base, "record_id": "different"}])
