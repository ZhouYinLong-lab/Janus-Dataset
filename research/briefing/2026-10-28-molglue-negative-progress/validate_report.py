"""Validate frozen report facts and the human-readable source before DOCX build."""
import csv
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FACTS = HERE / "report_facts_20261028.json"
SOURCE = HERE / "分子胶非结构化阴性证据进展小结.md"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main():
    facts = load(FACTS)
    for item in facts["sources"]:
        path = ROOT / item["path"]
        assert path.is_file(), f"Missing frozen source: {path}"
        assert sha256(path) == item["sha256"], f"Frozen source changed: {path}"

    inventory = load(ROOT / facts["sources"][0]["path"])
    expected = facts["inventory"]
    assert inventory["inventory_papers"] == expected["papers"]
    coverage = inventory["paper_coverage"]
    assert coverage["completed_with_candidates"] == expected["completed_with_candidates"]
    assert coverage["completed_no_candidates"] == expected["completed_no_candidates"]
    assert coverage["completed_with_candidates"] + coverage["completed_no_candidates"] == expected["scanned"]
    assert coverage["fulltext_missing"] == expected["fulltext_missing"]
    assert coverage["html_pending_format"] == expected["html_pending_format"]
    assert inventory["records"]["total"] == expected["candidate_records"]

    evidence = load(ROOT / facts["sources"][1]["path"])
    negative = [row for row in evidence if row.get("kind") == "negative" and row.get("content_decision") == "reliable"]
    assert len(negative) == expected["formal_negative_evidence"]
    assert len({row["doi"] for row in negative}) == expected["formal_evidence_dois"]
    experiment_ids = [row.get("experiment_id") for row in negative]
    assert len({value for value in experiment_ids if value}) == expected["independent_experiments"]
    assert sum(not value for value in experiment_ids) == expected["records_without_experiment_id"]

    error_summary = load(ROOT / "research/2026-10-27-evidence-utility/error_summary_20261028.json")
    rag = facts["rag"]
    assert error_summary["rag_questions"] == rag["questions"]
    assert error_summary["generation_exceptions"]["original_tasks"] == rag["tasks"]
    assert error_summary["generation_exceptions"]["completed_answers"] == rag["completed"]
    assert error_summary["rag_comparisons"]["recovered_vs_structured"] == {
        "better": rag["recovered_vs_structured"]["better"],
        "equal": rag["recovered_vs_structured"]["equal"],
        "worse": rag["recovered_vs_structured"]["worse"],
    }

    lora_summary = load(ROOT / "research/2026-10-27-evidence-utility/lora_fixed_choice_v2_summary.json")
    for name, model in facts["lora"]["models"].items():
        measured = lora_summary["models"][name]
        assert round(measured["accuracy"], 4) == model["accuracy"]
        assert round(measured["overclaim_rate"], 4) == model["overclaim_rate"]

    mg2act = load(ROOT / "research/2026-10-27-evidence-utility/mg2act_local_v1_summary.json")
    assert mg2act["official_split_counts"] == {"train": 907, "validation": 125, "test": 127, "fine_test": 73}
    assert round(mg2act["model_metrics"]["full_test"]["mae"], 4) == facts["mg2act"]["test_mae"]
    assert round(mg2act["baselines"]["train_mean_mae"], 4) == facts["mg2act"]["train_mean_baseline_mae"]

    with (ROOT / "research/2026-10-27-evidence-utility/typical_cases_20261028.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        cases = {row["case_id"]: row for row in csv.DictReader(handle)}
    for case in facts["cases"]:
        row = cases[case["case_id"]]
        assert row["question_id"] == case["question_id"]
        assert row["doi"] == case["doi"]

    text = SOURCE.read_text(encoding="utf-8")
    required = ["193篇", "70篇", "464条", "148条", "42篇", "146个", "285个", "283个",
                "0.315", "0.327", "0.322", "0.404", "0.673", "41/57", "42/57",
                "0.666666667", "0.2895", "0.2292"]
    for value in required:
        assert value in text, f"Report source omits frozen value: {value}"
    forbidden = ["ChemDFM", "有机反应条件筛选", "全面提升", "阴性数据普遍无用",
                 "local/", "D:\\Projects", "API key"]
    for value in forbidden:
        assert value not in text, f"Forbidden report text: {value}"
    assert "不作为专家金标发布" in text
    assert text.count("独立人工核查") <= 2
    print("report facts and source validated")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
