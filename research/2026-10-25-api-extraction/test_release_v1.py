import release_v1


def test_missing_optional_condition_does_not_change_scope():
    row = {"evidence_id": "E1", "paper_id": "P1", "doi": "10.1/x", "task_id": "J1",
           "facts": {"observations": [{"values": {"subject": "A", "target": "B",
                                                       "endpoint": "protein degradation",
                                                       "observation": "did not degrade"}}]},
           "conditions": {"items": [{"values": {"cell_line": "C", "tested_concentration": None}}]},
           "evidence_spans": []}
    enriched = release_v1.enrich_identity(row)
    assert enriched["scope_class"] == "molecular_glue_degradation_negative"
    assert enriched["experiment_id"].startswith("X_")


def test_endpoints_remain_separate():
    base = {"paper_id": "P1", "doi": "10.1/x", "task_id": "J1",
            "conditions": {"items": [{"values": {}}]}, "evidence_spans": []}
    protein = dict(base, evidence_id="E1", facts={"observations": [{"values": {
        "subject": "A", "target": "B", "endpoint": "protein degradation",
        "observation": "none"}}]})
    mrna = dict(base, evidence_id="E2", facts={"observations": [{"values": {
        "subject": "A", "target": "B", "endpoint": "mRNA abundance",
        "observation": "none"}}]})
    p = release_v1.enrich_identity(protein)
    m = release_v1.enrich_identity(mrna)
    assert p["experiment_id"] != m["experiment_id"]
    assert p["scope_class"] == "molecular_glue_degradation_negative"
    assert m["scope_class"] == "other_endpoint"


def test_observation_evidence_detail_becomes_stable_mention():
    row = {"evidence_id": "E1", "paper_id": "P1", "doi": "10.1/x", "task_id": "J1",
           "observation": {"values": {"subject": "A", "target": "B",
                                          "endpoint": "protein degradation", "observation": "none"},
                           "evidence_detail": [{"unit_id": "U1", "quote": "No degradation."}]}}
    enriched = release_v1.enrich_identity(row)
    assert len(enriched["evidence_spans"]) == 1
    assert enriched["evidence_spans"][0]["mention_id"].startswith("M_")


def test_two_reviews_or_adjudication_are_required():
    row = {}
    assert release_v1.assign_final_status(row, {"status": "reliable"}, {}, None)[0] == "pending_review"
    assert release_v1.assign_final_status(row, {"status": "reliable"}, {"verdict": "reliable"}, None)[0] == "reliable"
    assert release_v1.assign_final_status(row, {"status": "reliable"}, {"verdict": "excluded"}, None)[0] == "pending_review"
    assert release_v1.assign_final_status(row, {}, {}, {"verdict": "excluded"})[0] == "excluded"


def test_split_keeps_blocked_benchmark_doi_out_of_train():
    papers = [f"P{i}" for i in range(10)]
    dois = {pid: f"10.1/{pid}" for pid in papers}
    blocked = {dois["P0"], dois["P1"]}
    splits = release_v1.make_paper_splits(papers, dois, blocked)
    assert splits["P0"] != "train"
    assert splits["P1"] != "train"


def test_split_keeps_duplicate_doi_papers_together():
    papers = [f"P{i}" for i in range(10)]
    dois = {pid: f"10.1/{pid}" for pid in papers}
    dois["P1"] = dois["P0"]
    splits = release_v1.make_paper_splits(papers, dois, set())
    assert splits["P0"] == splits["P1"]


def test_manifest_hashes_only_existing_files(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    missing = tmp_path / "missing.json"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    hashes = release_v1.sha256_files([second, missing, first, first])
    assert list(hashes) == sorted([first.resolve().as_posix(), second.resolve().as_posix()])
    assert len(set(hashes.values())) == 2


def test_linked_mentions_are_not_reported_as_possible_duplicates():
    common = {"paper_id": "P1", "evidence_origin": "primary_report",
              "facts": {"observations": [{"values": {
                  "subject": "A", "target": "B", "endpoint": "protein degradation"}}]}}
    linked = [dict(common, evidence_id="E1", experiment_id="X1"),
              dict(common, evidence_id="E2", experiment_id="X1")]
    assert release_v1.unresolved_duplicate_groups(linked) == []

    unresolved = linked + [dict(common, evidence_id="E3", experiment_id="X2")]
    groups = release_v1.unresolved_duplicate_groups(unresolved)
    assert len(groups) == 1
    assert groups[0]["experiment_ids"] == ["X1", "X2"]
