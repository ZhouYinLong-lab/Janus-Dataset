"""Build the internal v1 evidence package from immutable Codex artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import curation_overlay
import reference_recall_v1


PARTITIONS = ("reliable_evidence", "pending_review", "excluded_records")
SCOPES = {
    "molecular_glue_degradation_negative", "mechanism_or_control",
    "other_endpoint", "out_of_scope",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(prefix: str, value) -> str:
    return prefix + curation_overlay.sha256_json(value)[:20]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = sorted({key for row in rows for key in row}) or ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def load_baseline(run: Path) -> list[dict]:
    rows = []
    for name in PARTITIONS:
        for row in read(run / "exports" / f"{name}.json"):
            rows.append(dict(row))
    ids = [curation_overlay.record_id(row) for row in rows]
    if len(rows) != 429 or len(set(ids)) != 429:
        raise ValueError(f"Expected frozen 429 unique baseline records, found {len(rows)}/{len(set(ids))}")
    return rows


def load_review_a(run: Path) -> dict[str, dict]:
    result = {}
    for path in sorted((run / "review").glob("*_review.json")):
        value = read(path)
        rows = value if isinstance(value, list) else value.get("records", [])
        for row in rows:
            rid = curation_overlay.record_id(row)
            if rid:
                result[rid] = row
    return result


def load_jsonl_dir(path: Path) -> dict[str, dict]:
    result = {}
    if not path.is_dir():
        return result
    for file in sorted(path.glob("*.jsonl")):
        for row in curation_overlay.read_jsonl(file):
            rid = curation_overlay.record_id(row)
            if rid:
                if rid in result:
                    raise ValueError(f"Duplicate blind-review decision: {rid}")
                result[rid] = row
    return result


def _values(row: dict) -> dict:
    observations = (row.get("facts") or {}).get("observations") or []
    if observations:
        return observations[0].get("values") or {}
    return (row.get("observation") or {}).get("values") or {}


def _conditions(row: dict) -> dict:
    items = (row.get("conditions") or {}).get("items") or []
    return items[0].get("values") or {} if items else {}


def infer_scope(row: dict) -> tuple[str, str]:
    if row.get("scope_class") in SCOPES:
        return row["scope_class"], "curation"
    values = _values(row)
    text = " ".join(str(values.get(key) or "") for key in
                    ("target", "endpoint", "observation", "scope_condition")).lower()
    if any(token in text for token in
           ("viability", "cytotoxic", "prolifer", "binding", "affinity", "mrna",
            "rna ", "transcription", "phosphorylation", "interaction")):
        return "other_endpoint", "endpoint_heuristic_pending_review"
    if any(token in text for token in
           ("crbn−/−", "crbn knockout", "proteasome", "competition", "rescue",
            "ubiquitin", "dependency", "required for")):
        return "mechanism_or_control", "endpoint_heuristic_pending_review"
    if any(token in text for token in ("degrad", "protein level", "protein abundance")):
        return "molecular_glue_degradation_negative", "endpoint_heuristic_pending_review"
    return "out_of_scope", "endpoint_heuristic_pending_review"


def infer_origin(row: dict) -> tuple[str, str]:
    if row.get("evidence_origin") in {"primary_report", "secondary_report", "unclear"}:
        return row["evidence_origin"], "curation"
    quote = " ".join(span.get("quote", "") for span in row.get("evidence_spans", []))
    if re.search(r"\b(a study|previously reported|has been reported|reported by)\b", quote, re.I):
        return "secondary_report", "citation_phrase_heuristic_pending_review"
    return "primary_report", "direct_article_report_heuristic_pending_review"


def enrich_identity(row: dict) -> dict:
    result = dict(row)
    rid = curation_overlay.record_id(result)
    values, conditions = _values(result), _conditions(result)
    source_spans = result.get("evidence_spans") or (result.get("observation") or {}).get("evidence_detail") or []
    if not source_spans:
        discovery = result.get("discovery") or {}
        if discovery.get("quote"):
            source_spans = [{"unit_id": discovery.get("unit_id"),
                             "sentence_ids": discovery.get("sentence_ids", []),
                             "quote": discovery["quote"], "kind": "discovery_quote"}]
    spans = []
    for index, span in enumerate(source_spans):
        copied = dict(span)
        copied.setdefault("mention_id", stable_id("M_", [rid, copied.get("unit_id"),
                                                          copied.get("char_start"), index]))
        spans.append(copied)
    result["evidence_spans"] = spans
    result.setdefault("mention_id", spans[0]["mention_id"] if spans else stable_id("M_", rid))
    scope, scope_basis = infer_scope(result)
    origin, origin_basis = infer_origin(result)
    result["scope_class"], result["scope_basis"] = scope, scope_basis
    result["evidence_origin"], result["evidence_origin_basis"] = origin, origin_basis
    if origin == "secondary_report":
        result.setdefault("secondary_report_of", None)
        result.setdefault("experiment_id", None)
    else:
        experiment_identity = {
            "doi": result.get("doi"), "paper_id": result.get("paper_id"),
            "task_id": result.get("task_id"), "subject": values.get("subject"),
            "target": values.get("target"), "endpoint": values.get("endpoint"),
            "cell_line": conditions.get("cell_line"),
            "treatment_time": conditions.get("treatment_time"),
            "tested_concentration": conditions.get("tested_concentration"),
            "assay": conditions.get("assay"),
        }
        result.setdefault("experiment_id", stable_id("X_", experiment_identity))
    return result


def citation_exact(row: dict, documents: dict[str, dict]) -> bool:
    units = {unit["unit_id"]: unit.get("text", "")
             for unit in documents.get(row.get("paper_id"), {}).get("units", [])}
    spans = row.get("evidence_spans") or []
    if not spans:
        return False
    for span in spans:
        quote = span.get("quote") or ""
        text = units.get(span.get("unit_id"), "")
        if not quote or quote not in text:
            return False
        start, end = span.get("char_start"), span.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and text[start:end] != quote:
            return False
    return True


def normalize_verdict(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("verdict") or value.get("review_status") or value.get("status")
    if value in {"reliable", "reliable_candidate", "reliable_evidence"}:
        return "reliable"
    if value in {"excluded", "exclude", "excluded_record"}:
        return "excluded"
    if value in {"pending", "pending_review", "uncertain", "needs_review"}:
        return "pending_review"
    return None


def assign_final_status(row: dict, review_a: dict, review_b: dict,
                        adjudication: dict | None) -> tuple[str, str]:
    if adjudication:
        verdict = normalize_verdict(adjudication)
        if verdict:
            return verdict, "adjudicated"
    a, b = normalize_verdict(review_a), normalize_verdict(review_b)
    if a == b and a in {"reliable", "excluded"}:
        return a, "two_review_agreement"
    return "pending_review", "requires_second_review_or_adjudication"


def mg2act_doi_splits(source_associations: Path) -> dict[str, set[str]]:
    result = defaultdict(set)
    if not source_associations.is_file():
        return result
    with source_associations.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            doi = (row.get("source_doi") or row.get("doi") or "").lower().strip()
            split = row.get("benchmark_split")
            if doi and split:
                result[doi].add(split)
    return result


def make_paper_splits(paper_ids: list[str], doi_by_paper: dict[str, str],
                      blocked_dois: set[str], seed: str = "20261027") -> dict[str, str]:
    ranked = sorted(paper_ids, key=lambda pid: hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest())
    result = {}
    blocked_dois = {doi.lower() for doi in blocked_dois}
    target_train, target_validation = round(len(ranked) * .70), round(len(ranked) * .15)
    train_candidates = [pid for pid in ranked if doi_by_paper.get(pid, "").lower() not in blocked_dois]
    train = set(train_candidates[:target_train])
    remaining = [pid for pid in ranked if pid not in train]
    validation = set(remaining[:target_validation])
    for pid in ranked:
        result[pid] = "train" if pid in train else "validation" if pid in validation else "test"
    return result


def positive_candidates(inputs_dir: Path, split_by_paper: dict[str, str]) -> list[dict]:
    rows = []
    for path in sorted(inputs_dir.glob("positive_*.json")):
        for row in read(path).get("records", []):
            if row.get("paper_id") not in split_by_paper:
                continue
            rows.append({
                "evidence_id": "POS_" + row["record_id"], "paper_id": row.get("paper_id"),
                "doi": row.get("doi"), "subject": row.get("compound"),
                "target": row.get("target"), "endpoint": row.get("endpoint"),
                "observation": row.get("claim_type"), "assay": row.get("assay"),
                "cell_line": row.get("cell_line"), "treatment_time": row.get("treatment_time"),
                "tested_concentration": row.get("tested_concentration_range"),
                "evidence_spans": row.get("result_evidence", []),
                "condition_evidence": row.get("condition_evidence", []),
                "split": split_by_paper[row["paper_id"]],
                "review_status": "pending_two_independent_reviews",
                "model_eligibility": {"training": False, "reason": "positive_source_review_incomplete"},
                "source_record_id": row["record_id"], "expert_gold": False,
            })
    return rows


def build(args) -> dict:
    run, workspace, output = args.run.resolve(), args.workspace.resolve(), args.output.resolve()
    inventory = read(args.inventory)
    inventory_by_id = {row["paper_id"]: row for row in inventory}
    source_hashes = {pid: row.get("source_sha256") for pid, row in inventory_by_id.items()}
    baseline = load_baseline(run)
    ledger = curation_overlay.read_jsonl(args.ledger)
    overlaid, application_audit = curation_overlay.apply_ledger(baseline, ledger, source_hashes)
    review_a, review_b = load_review_a(run), load_jsonl_dir(args.review_b)
    adjudications = {curation_overlay.record_id(row): row
                     for row in curation_overlay.read_jsonl(args.adjudications)}
    documents = {}
    for pid in {row.get("paper_id") for row in overlaid}:
        path = workspace / "documents" / f"{pid}.json"
        if path.is_file():
            documents[pid] = read(path)

    doi_splits = mg2act_doi_splits(args.mg2act_associations)
    blocked_dois = {doi for doi, splits in doi_splits.items() if splits & {"validation", "test", "val"}}
    scanned_papers = [row["paper_id"] for row in read(run / "exports" / "paper_coverage.json")
                      if str(row.get("status", "")).startswith("completed")]
    doi_by_paper = {pid: inventory_by_id[pid].get("doi") or "" for pid in scanned_papers}
    split_by_paper = make_paper_splits(scanned_papers, doi_by_paper, blocked_dois)

    records, decisions = [], []
    for original in overlaid:
        row = enrich_identity(original)
        row.setdefault("provisional_status", original.get("final_status"))
        rid = curation_overlay.record_id(row)
        a, b, adjudication = review_a.get(rid, {}), review_b.get(rid, {}), adjudications.get(rid)
        status, basis = assign_final_status(row, a, b, adjudication)
        row["final_status"], row["final_status_basis"] = status, basis
        row["citation_exact"] = citation_exact(row, documents)
        row["split"] = split_by_paper.get(row.get("paper_id"))
        doi = (row.get("doi") or "").lower()
        benchmark_splits = sorted(doi_splits.get(doi, set()))
        row["database_overlap"] = "source_only_overlap" if doi else "unknown"
        row["mg2act_source_splits"] = benchmark_splits
        row["mg2act_train_blocked"] = bool(set(benchmark_splits) & {"validation", "test", "val"})
        eligible = (status == "reliable" and row["evidence_origin"] == "primary_report"
                    and row["scope_class"] == "molecular_glue_degradation_negative"
                    and row["citation_exact"] and not row["mg2act_train_blocked"])
        row["model_eligibility"] = {
            "training": eligible and row["split"] == "train",
            "rag": eligible,
            "reason": "eligible" if eligible else basis if status != "reliable"
            else "scope_origin_citation_or_benchmark_gate",
        }
        records.append(row)
        decisions.append({
            "evidence_id": rid, "paper_id": row.get("paper_id"),
            "reviewer_a_status": normalize_verdict(a), "reviewer_b_status": normalize_verdict(b),
            "adjudication_status": normalize_verdict(adjudication),
            "final_status": status, "basis": basis,
            "scope_class": row["scope_class"], "evidence_origin": row["evidence_origin"],
            "citation_exact": row["citation_exact"], "expert_gold": False,
        })

    partitions = {
        "reliable_evidence": [row for row in records if row["final_status"] == "reliable"],
        "pending_review": [row for row in records if row["final_status"] == "pending_review"],
        "excluded_records": [row for row in records if row["final_status"] == "excluded"],
    }
    for name, rows in partitions.items():
        write_json(output / f"{name}.json", rows); write_csv(output / f"{name}.csv", rows)

    mentions, experiments_by_id = [], defaultdict(list)
    possible_groups = defaultdict(list)
    for row in records:
        rid = curation_overlay.record_id(row)
        for span in row.get("evidence_spans", []):
            mentions.append({"mention_id": span["mention_id"], "evidence_id": rid,
                             "experiment_id": row.get("experiment_id"), "paper_id": row.get("paper_id"),
                             "unit_id": span.get("unit_id"), "sentence_ids": span.get("sentence_ids"),
                             "char_start": span.get("char_start"), "char_end": span.get("char_end"),
                             "quote": span.get("quote"), "kind": span.get("kind"),
                             "locator": span.get("locator")})
        if row.get("experiment_id"):
            experiments_by_id[row["experiment_id"]].append(rid)
        values = _values(row)
        key = curation_overlay.sha256_json([row.get("paper_id"), values.get("subject"),
                                             values.get("target"), values.get("endpoint")])
        possible_groups[key].append(rid)
    experiments = [{"experiment_id": xid, "evidence_ids": ids,
                    "evidence_count": len(ids), "status": "single" if len(ids) == 1 else "linked"}
                   for xid, ids in sorted(experiments_by_id.items())]
    possible_duplicates = [{"group_id": key, "evidence_ids": ids,
                            "status": "possible_duplicate_requires_adjudication"}
                           for key, ids in possible_groups.items() if len(ids) > 1]
    write_json(output / "experiments.json", experiments); write_csv(output / "experiments.csv", experiments)
    write_json(output / "evidence_mentions.json", mentions); write_csv(output / "evidence_mentions.csv", mentions)
    write_json(output / "possible_duplicates.json", possible_duplicates)
    write_json(output / "review_decisions.json", decisions); write_csv(output / "review_decisions.csv", decisions)
    (output / "curation_history.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")

    baseline_coverage = read(run / "exports" / "paper_coverage.json")
    counts = defaultdict(Counter)
    for row in records:
        counts[row.get("paper_id")][row["final_status"]] += 1
    paper_coverage = []
    for source in baseline_coverage:
        row = dict(source); count = counts[row["paper_id"]]
        row.update({"raw_candidate_count": source.get("raw_candidate_count", source.get("candidate_count", 0)),
                    "candidate_count": sum(count.values()), "reliable_count": count["reliable"],
                    "pending_count": count["pending_review"], "excluded_count": count["excluded"],
                    "partition_total": sum(count.values()), "split": split_by_paper.get(row["paper_id"])})
        paper_coverage.append(row)
    write_json(output / "paper_coverage.json", paper_coverage); write_csv(output / "paper_coverage.csv", paper_coverage)
    context_coverage = read(run / "exports" / "context_coverage.json")
    write_json(output / "context_coverage.json", context_coverage); write_csv(output / "context_coverage.csv", context_coverage)

    overlap = [{"evidence_id": curation_overlay.record_id(row), "paper_id": row.get("paper_id"),
                "doi": row.get("doi"), "database_overlap": row["database_overlap"],
                "mg2act_source_splits": row["mg2act_source_splits"],
                "mg2act_train_blocked": row["mg2act_train_blocked"],
                "exact_experiment_overlap": False,
                "reason": "DOI/source association only; experiment-level match not established."}
               for row in records]
    write_json(output / "overlap_audit.json", overlap); write_csv(output / "overlap_audit.csv", overlap)
    eligibility = [{"evidence_id": curation_overlay.record_id(row), "paper_id": row.get("paper_id"),
                    "split": row.get("split"), "scope_class": row["scope_class"],
                    "evidence_origin": row["evidence_origin"], **row["model_eligibility"]}
                   for row in records]
    write_json(output / "model_eligibility.json", eligibility); write_csv(output / "model_eligibility.csv", eligibility)
    write_json(output / "splits.json", {"seed": "20261027", "unit": "paper_doi",
                                         "papers": split_by_paper,
                                         "counts": dict(Counter(split_by_paper.values())),
                                         "mg2act_val_test_dois_blocked_from_train": sorted(blocked_dois)})
    positives = positive_candidates(args.positive_inputs, split_by_paper)
    write_json(output / "positive_evidence.json", positives); write_csv(output / "positive_evidence.csv", positives)

    citation_ok = sum(row["citation_exact"] for row in records)
    second_reviewed = sum(bool(decision["reviewer_b_status"]) for decision in decisions)
    review_b_rows = [review_b[curation_overlay.record_id(row)] for row in records
                     if curation_overlay.record_id(row) in review_b]
    review_b_field_supported = sum(bool(row.get("required_fields_supported"))
                                   for row in review_b_rows)
    review_b_citation_supported = sum(bool(row.get("citation_direct_support"))
                                      for row in review_b_rows)
    metrics = {
        "baseline_records": 429, "recovered_records": len(records) - 429,
        "evidence_records": len(records), "evidence_mentions": len(mentions),
        "independent_experiments": len(experiments),
        "possible_duplicate_groups": len(possible_duplicates),
        "citation_exact": {"numerator": citation_ok, "denominator": len(records),
                           "rate": citation_ok / len(records) if records else None},
        "second_review_complete": {"numerator": second_reviewed, "denominator": len(records),
                                   "rate": second_reviewed / len(records) if records else None},
        "reviewer_b_citation_support": {
            "numerator": review_b_citation_supported, "denominator": len(review_b_rows),
            "rate": review_b_citation_supported / len(review_b_rows) if review_b_rows else None,
            "scope": "records with completed second blind review",
        },
        "required_field_support": {
            "numerator": review_b_field_supported, "denominator": len(review_b_rows),
            "rate": review_b_field_supported / len(review_b_rows) if review_b_rows else None,
            "scope": "records with completed second blind review",
        },
        "expert_gold": False,
    }
    reference_rows, reference_summary = reference_recall_v1.audit(records, read(args.reference))
    write_json(output / "reference_coverage.json", reference_rows)
    write_csv(output / "reference_coverage.csv", reference_rows)
    metrics["fixed_reference_recall"] = reference_summary
    write_json(output / "quality_metrics.json", metrics)
    review_complete = second_reviewed == len(records)
    release_status = "candidate_blocked_second_review" if not review_complete else "candidate_requires_adjudication"
    report = {
        "release_status": release_status, "baseline_records": 429,
        "records_after_recovery": len(records), "partition_counts": {k: len(v) for k, v in partitions.items()},
        "review_b_complete": second_reviewed, "review_b_required": len(records),
        "external_generation_api_requests": 0, "expert_gold": False,
        "zero_candidate_audit": str(args.zero_audit), "positive_candidates": len(positives),
        "split_counts": dict(Counter(split_by_paper.values())),
    }
    write_json(output / "run_report.json", report)
    (output / "第一版数据报告.md").write_text(
        "# 分子胶阴性证据第一版候选包\n\n"
        f"- 状态：{release_status}\n- 冻结基线：429条；补录后：{len(records)}条。\n"
        f"- 最终分区：可靠{len(partitions['reliable_evidence'])}；"
        f"待确认{len(partitions['pending_review'])}；排除{len(partitions['excluded_records'])}。\n"
        f"- 第二盲审：{second_reviewed}/{len(records)}。\n"
        f"- 引用机械定位：{citation_ok}/{len(records)}。\n"
        "- 当前包为内部候选版本；第二盲审和争议裁定完成后才能冻结为可用于模型的v1。\n",
        encoding="utf-8")

    output_files = sorted(path for path in output.iterdir() if path.is_file()
                          and path.name != "release_manifest.json")
    manifest = {
        "release_id": "molglue_negative_v1_20261027", "status": release_status,
        "created_utc": time.time(), "expert_gold": False,
        "input_hashes": {
            "inventory": sha256_file(args.inventory),
            "workspace_manifest": sha256_file(args.workspace_manifest),
            "baseline_run_report": sha256_file(run / "exports" / "run_report.json"),
            "curation_history": sha256_file(args.ledger),
        },
        "output_hashes": {path.name: sha256_file(path) for path in output_files},
        "code_hashes": {path.name: sha256_file(path) for path in
                        (Path(__file__), Path(__file__).with_name("curation_overlay.py"))},
        "external_generation_api_requests": 0,
    }
    write_json(output / "release_manifest.json", manifest)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--workspace-manifest", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--review-b", required=True, type=Path)
    parser.add_argument("--adjudications", required=True, type=Path)
    parser.add_argument("--mg2act-associations", required=True, type=Path)
    parser.add_argument("--positive-inputs", required=True, type=Path)
    parser.add_argument("--zero-audit", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments), ensure_ascii=False, indent=2))

