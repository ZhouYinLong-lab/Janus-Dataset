import reference_recall_v1 as recall


def test_reference_mapping_requires_object_target_endpoint_and_source():
    record = {"evidence_id": "E1", "paper_id": "P1", "final_status": "reliable",
              "facts": {"observations": [{"values": {"subject": "compound 7",
                                                          "target": "cyclin K",
                                                          "endpoint": "protein degradation",
                                                          "observation": "reduced"}}]},
              "evidence_spans": [{"unit_id": "U1"}]}
    reference = {"cases": [{"id": "N1", "paper_id": "P1", "core_case": True,
                             "source_unit_ids": ["U1"], "expected_core": "x",
                             "required_mapping": {"compound": "7", "target": "cyclin K",
                                                  "endpoint": "protein degradation"}}]}
    rows, summary = recall.audit([record], reference)
    assert rows[0]["discovery_status"] == "matched"
    assert rows[0]["reliable_status"] == "matched"
    assert summary["denominator"] == 1


def test_partial_mapping_is_not_strict_recall():
    record = {"evidence_id": "E1", "paper_id": "P1", "final_status": "pending_review",
              "facts": {"observations": [{"values": {"subject": "unknown group",
                                                          "target": "cyclin K",
                                                          "endpoint": "protein degradation"}}]},
              "evidence_spans": [{"unit_id": "U1"}]}
    reference = {"cases": [{"id": "N1", "paper_id": "P1", "core_case": True,
                             "source_unit_ids": ["U1"],
                             "required_mapping": {"compound": "7", "target": "cyclin K",
                                                  "endpoint": "protein degradation"}}]}
    rows, summary = recall.audit([record], reference)
    assert rows[0]["discovery_status"] == "partial"
    assert summary["discovery_strict"] == 0
