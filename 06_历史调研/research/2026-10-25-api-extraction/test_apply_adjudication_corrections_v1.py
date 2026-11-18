import apply_adjudication_corrections_v1 as apply


def test_structured_corrections_update_values_conditions_and_duplicate_link():
    record = {"evidence_id": "E1", "experiment_id": "X1",
              "facts": {"observations": [{"values": {"subject": "old", "observation": "old"}}]},
              "conditions": {"items": [{"values": {"assay": "old"}}]}}
    target = {"evidence_id": "R_2", "experiment_id": "X2"}
    changes = apply.correction_changes(
        record,
        {"subject": "new", "result_strength": "reduced", "assay": "Western blot",
         "conditions": {"treatment_time": "24 h"},
         "duplicate_relation": "same experiment as R_2"},
        {"E1": record, "R_2": target})
    values = changes["facts"]["observations"][0]["values"]
    assert values["subject"] == "new"
    assert values["observation"] == "reduced"
    assert changes["conditions"]["items"][0]["values"] == {
        "assay": "Western blot", "treatment_time": "24 h"}
    assert changes["experiment_id"] == "X2"


def test_required_action_alone_does_not_modify_record():
    record = {"evidence_id": "E1", "facts": {"observations": [{"values": {}}]}}
    assert apply.correction_changes(
        record, {"required_action": "needs source"}, {"E1": record}) == {}
