import copy

import pytest

import blind_review_completion_v1 as blind


def _row(evidence_id, paper_id):
    return {"evidence_id": evidence_id, "paper_id": paper_id,
            "source_sha256": "s", "final_status": "reliable",
            "reviewer_a_status": "reliable", "scope_class": "other_endpoint"}


def test_partition_keeps_papers_together_and_balances_records():
    rows = ([_row(f"A{i}", "P1") for i in range(5)] +
            [_row(f"B{i}", "P2") for i in range(4)] +
            [_row(f"C{i}", "P3") for i in range(3)] +
            [_row(f"D{i}", "P4") for i in range(2)])
    shards = blind.partition_by_paper(rows, 3)
    owners = {}
    for index, shard in enumerate(shards):
        for row in shard:
            owners.setdefault(row["paper_id"], set()).add(index)
    assert all(len(value) == 1 for value in owners.values())
    assert sum(map(len, shards)) == len(rows)


def test_blind_task_removes_all_decision_fields():
    row = _row("E1", "P1")
    row["model_eligibility"] = {"training": True}
    row["evidence_spans"] = [{"unit_id": "U2", "quote": "No effect."}]
    document = {"units": [{"unit_id": "U1", "text": "before"},
                           {"unit_id": "U2", "text": "No effect."},
                           {"unit_id": "U3", "text": "after"}]}
    task = blind.build_task(row, document, "reviewer_b")
    assert blind.LEAKED_KEYS.isdisjoint(task["record"])
    assert [unit["unit_id"] for unit in task["context_units"]] == ["U1", "U2", "U3"]


def test_review_validation_requires_exact_ids_and_source_hash():
    tasks = [{"evidence_id": "E1", "source_sha256": "s"}]
    result = {"evidence_id": "E1", "worker_id": "W1", "review_role": "reviewer_b",
              "verdict": "pending_review", "scope_class": "other_endpoint",
              "evidence_origin": "unclear", "citation_direct_support": True,
              "required_fields_supported": True, "source_sha256": "s",
              "reason": "Object remains ambiguous.", "external_generation_api_requests": 0}
    assert blind.validate_review_rows([result], tasks, "W1", "reviewer_b")["records"] == 1
    changed = copy.deepcopy(result); changed["source_sha256"] = "changed"
    with pytest.raises(ValueError, match="Source hash"):
        blind.validate_review_rows([changed], tasks, "W1", "reviewer_b")
    with pytest.raises(ValueError, match="exactly match"):
        blind.validate_review_rows([], tasks, "W1", "reviewer_b")
