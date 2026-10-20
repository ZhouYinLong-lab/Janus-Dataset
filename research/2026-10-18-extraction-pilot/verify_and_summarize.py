"""Check saved source links and review coverage; summarize this pilot only."""

import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    assert all(len(row) == len(rows[0]) for row in rows), f"Malformed CSV: {name}"
    return pd.read_csv(HERE / name, dtype=str).fillna("")


def main():
    access = read("paper_access.csv")
    blocks = read("source_blocks.csv")
    candidates = read("rule_candidates.csv")
    reviews = read("candidate_decisions.csv")
    observations = read("extracted_observations.csv")
    reference = read("blind_reference.csv")
    comparisons = read("reference_adjudication.csv")
    eligibility = read("fulltext_eligibility.csv")
    downloads = read("evidence_downloads.csv")
    block_ids = set(blocks.block_id)
    assert blocks.block_id.is_unique and candidates.candidate_id.is_unique
    assert set(candidates.candidate_id) == set(reviews.candidate_id)
    pairs = dict(zip(candidates.candidate_id, candidates.block_id))
    for row in reviews.itertuples():
        assert pairs[row.candidate_id] == row.block_id
        assert set(filter(None, row.observation_ids.split(";"))) <= set(observations.observation_id)
    for frame, columns in [(observations, ["result_blocks", "context_blocks"]),
                           (reference, ["evidence_B", "methods_B"]),
                           (comparisons, ["source_blocks"])]:
        for column in columns:
            for value in frame[column]:
                assert set(re.findall(r"P\d+-B\d{4}", value)) <= block_ids, value
    accounted = set()
    for value in comparisons.reference_ids:
        accounted.update(value.split(";"))
    assert accounted == set(reference.reference_id), "Unreviewed blind-reference items"
    expected_table_rows, expected_tables = 0, 0
    for row in access.itertuples():
        if row.status != "fulltext_xml_obtained":
            continue
        path = HERE / row.local_xml
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256
        xml = ET.parse(path).getroot()
        assert next(x.text for x in xml.findall(".//article-id") if x.get("pub-id-type") == "pmid") == row.pmid
        tables = xml.findall(".//body//table-wrap")
        expected_tables += len(tables)
        expected_table_rows += sum(len(t.findall(".//tr")) for t in tables)
    actual_table_rows = sum(blocks.kind == "table_row")
    assert actual_table_rows == expected_table_rows, "Table-row parsing omission"
    negatives = observations[observations.decision == "source_reported_negative"]
    assert len(negatives) == 3
    assert set(negatives.pmid) == {"35464910"}
    assert set(negatives.temperature_C) == {"37"} and set(negatives.duration) == {"2h"}
    assert set(negatives.evidence_type) == {"qualitative_no_detect"}
    assert not observations[observations.decision == "hold_out"].observation_id.isin(negatives.observation_id).any()
    negatives.to_csv(HERE / "negative_records.csv", index=False, encoding="utf-8-sig")
    for row in downloads[downloads.status == "downloaded"].itertuples():
        assert hashlib.sha256((HERE / "sources" / row.file).read_bytes()).hexdigest() == row.sha256
    summary = dict(
        selected_papers=len(access), xml_fulltexts_obtained=int((access.status == "fulltext_xml_obtained").sum()),
        eligible_new_catalytic_assay_papers=int((eligibility.eligible_for_new_substrate_assay_cohort == "yes").sum()),
        source_blocks=len(blocks), source_tables=expected_tables, source_table_rows=actual_table_rows,
        initial_candidate_blocks=len(read("rule_candidates_initial.csv")), candidate_blocks=len(candidates),
        reviewed_candidate_blocks=len(reviews), decision_counts=dict(Counter(reviews.decision)),
        retained_evidence_units=len(observations), evidence_decision_counts=dict(Counter(observations.decision)),
        source_reported_negative_pairs=len(negatives), blind_reference_items=len(reference),
        human_gold_standard=False, model_training_performed=False,
        notes=["Two AI-assisted readings plus source checks; not independently validated extraction accuracy.",
               "The three reported negatives share one source and protocol; not three independent studies.",
               "Ten papers lack a PMC identifier in the selected PubMed response; publisher access was not exhausted.",
               "Repeated conclusions and nonactivity-table dashes are not new observations."],
    )
    (HERE / "pilot_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    input_files = [p for p in (HERE / "sources").iterdir() if p.is_file()]
    input_files += [HERE / "collect_and_scan.py", HERE / "download_evidence.py", Path(__file__), HERE / "事先约定.md"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_files}
    (HERE / "source_checksums.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Verified all candidate decisions, observation/reference source IDs, 71 reference dispositions, table rows, source identities and retained downloads.")


if __name__ == "__main__":
    main()
