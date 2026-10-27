import copy

import known_corrections_v1 as known


def test_b236_restores_supported_conditions_and_marks_secondary():
    rows = []
    for rid in [
        "R_272304b6b54bd7a5d577", "R_3214e0ba39e9843ee918",
        "R_3e916556de9c190f58c3", "R_a00525b030f97dc1d71f",
        "R_edd8612899b4eec04120", "R_3c0fd648c0868c8c6ead",
        "R_5f330b7a4a2a6793b131",
    ]:
        rows.append({"record_id": rid, "paper_id": "B236", "source_sha256": "s",
                     "facts": {"observations": [{"values": {}}]},
                     "conditions": {"items": [{"values": {}}]}})
    entries = known.b236_entries(rows)
    assert len(entries) == 7
    secondary = next(row for row in entries if row["record_id"] == "R_3e916556de9c190f58c3")
    assert secondary["changes"]["evidence_origin"] == "secondary_report"
    assert secondary["changes"]["secondary_report_of"] == "B236 reference 19"
    panel = next(row for row in entries if row["record_id"] == "R_5f330b7a4a2a6793b131")
    values = panel["changes"]["conditions"]["items"][0]["values"]
    assert values["treatment_time"] == "72 h"
    assert "ATPlite" in values["assay"]


def test_est1036_body_and_caption_are_two_mentions_of_one_experiment():
    body = {
        "sentence_id": "S1", "unit_id": "U1", "char_start": 1, "char_end": 12,
        "text": "EST1036 did not induce the degradation of CDK4 in C33A cells.",
        "kind": "body_paragraph", "locator": "p1",
    }
    marker = "Blots shown in (b,e,h) are representative of n = 3 biologically independent replicates/group."
    caption = ("prefix (g) Structure of EST1036. (h) EST1036 does not degrade CDK4. "
               "C33A cells were treated with compounds (5 μM) for 24 h and assessed by Western blotting. "
               + marker + " suffix")
    document = {"source_sha256": "s", "units": [{"unit_id": "U2", "kind": "figure_caption",
                                                     "locator": "fig1", "text": caption}]}
    entry = known.est1036_entry(document, [body], "J1")
    record = entry["record"]
    assert len(record["evidence_spans"]) == 2
    assert len({record["experiment_id"] for _ in record["evidence_spans"]}) == 1
    assert record["conditions"]["items"][0]["values"]["tested_concentration"] == "5 μM"
    assert record["final_status"] == "pending_review"
