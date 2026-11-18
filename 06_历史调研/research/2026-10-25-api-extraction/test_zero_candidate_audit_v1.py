import zero_candidate_audit_v1 as audit


def test_recovered_record_keeps_missing_optional_conditions_null():
    paper = {"paper_id": "P1", "doi": "10.1/x", "source_sha256": "s"}
    sentence = {"sentence_id": "S1", "unit_id": "U1", "char_start": 2, "char_end": 20,
                "text": "Compound A did not degrade protein B.",
                "kind": "body_paragraph", "locator": "p1"}
    spec = {"subject": "A", "target": "B", "endpoint": "protein degradation",
            "observation": "did not degrade", "scope": "molecular_glue_degradation_negative"}
    entry = audit.recovered_entry(paper, sentence, spec)
    record = entry["record"]
    values = record["conditions"]["items"][0]["values"]
    assert values["tested_concentration"] is None
    assert record["final_status"] == "pending_review"
    assert record["scope_class"] == "molecular_glue_degradation_negative"
