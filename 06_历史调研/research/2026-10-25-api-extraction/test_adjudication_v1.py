import json

import pytest

import adjudication_v1 as adj


def test_queue_reasons_cover_disagreement_joint_pending_and_corrections():
    assert "verdict_disagreement" in adj.adjudication_reasons(
        {"status": "reliable"}, {"verdict": "excluded"})
    assert "joint_pending" in adj.adjudication_reasons(
        {"status": "pending_review"}, {"verdict": "pending_review"})
    assert "reviewer_b_correction_proposed" in adj.adjudication_reasons(
        {"status": "reliable"}, {"verdict": "reliable", "corrections": {"x": 1}})
    assert adj.adjudication_reasons({"status": "reliable"}, {"verdict": "reliable"}) == []


def test_duplicate_validation_requires_exact_groups_and_canonical_merge():
    queue = [{"group_id": "G1", "evidence_ids": ["E1", "E2"]}]
    with pytest.raises(ValueError, match="canonical"):
        adj.validate_duplicate_adjudications(
            [{"group_id": "G1", "evidence_ids": ["E1", "E2"],
              "decision": "same_experiment", "reason": "same assay"}], queue)
    result = adj.validate_duplicate_adjudications(
        [{"group_id": "G1", "evidence_ids": ["E2", "E1"],
          "decision": "distinct_experiments", "reason": "different cells"}], queue)
    assert result["groups"] == 1


def test_finalize_rejects_unsupported_reliable_recommendation(tmp_path):
    queue = [{"evidence_id": "E1", "paper_id": "P1", "source_sha256": "s",
              "queue_sha256": "q", "queue_reasons": ["verdict_disagreement"],
              "reviewer_a": {"status": "pending_review"},
              "reviewer_b": {"verdict": "reliable"}}]
    queue_path = tmp_path / "queue.json"
    queue_path.write_text(json.dumps(queue), encoding="utf-8")
    recommendation = {"evidence_id": "E1", "verdict": "reliable",
                      "scope_class": "molecular_glue_degradation_negative",
                      "evidence_origin": "primary_report", "citation_direct_support": False,
                      "required_fields_supported": True, "source_sha256": "s",
                      "queue_sha256": "q", "reason": "unsupported",
                      "recommendation_worker_id": "W1"}
    recommendation_path = tmp_path / "recommendation.jsonl"
    recommendation_path.write_text(json.dumps(recommendation) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be reliable"):
        adj.finalize_recommendations([recommendation_path], queue_path, tmp_path / "out.jsonl")
