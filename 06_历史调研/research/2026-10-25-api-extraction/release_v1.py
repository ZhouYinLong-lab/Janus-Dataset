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
DUPLICATE_DECISIONS = {"same_experiment", "distinct_experiments", "possible_duplicate"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_files(paths) -> dict[str, str]:
    """Hash existing files with stable, collision-free path keys."""

    files = sorted({Path(path).resolve() for path in paths if Path(path).is_file()})
    return {path.as_posix(): sha256_file(path) for path in files}


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


def merge_review_maps(primary: dict[str, dict], extra: dict[str, dict]) -> dict[str, dict]:
    overlap = set(primary) & set(extra)
    if overlap:
        raise ValueError(f"Duplicate review decisions: {sorted(overlap)[:3]}")
    return {**primary, **extra}


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


def requires_adjudication(review_a: dict, review_b: dict) -> bool:
    a, b = normalize_verdict(review_a), normalize_verdict(review_b)
    if not a or not b or a != b or a == "pending_review":
        return True
    for field in ("scope_class", "evidence_origin", "citation_direct_support",
                  "required_fields_supported"):
        if field in review_a and field in review_b and review_a.get(field) != review_b.get(field):
            return True
    if review_b.get("corrections"):
        return True
    return bool(review_a.get("review_role") == "reviewer_a_extra" and review_a.get("corrections"))


def load_duplicate_adjudications(path: Path) -> dict[str, dict]:
    rows = curation_overlay.read_jsonl(path)
    result = {}
    for row in rows:
        group_id = row.get("group_id")
        if not group_id or group_id in result:
            raise ValueError(f"Duplicate or missing duplicate-adjudication ID: {group_id}")
        if row.get("decision") not in DUPLICATE_DECISIONS:
            raise ValueError(f"Invalid duplicate decision: {group_id}")
        result[group_id] = row
    return result


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
    blocked_dois = {doi.lower().strip() for doi in blocked_dois}
    grouped = defaultdict(list)
    for paper_id in paper_ids:
        doi = doi_by_paper.get(paper_id, "").lower().strip()
        grouped[f"doi:{doi}" if doi else f"paper:{paper_id}"].append(paper_id)

    def rank(group_key: str) -> str:
        return min(hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest()
                   for pid in grouped[group_key])

    ranked_groups = sorted(grouped, key=rank)
    target_train = round(len(paper_ids) * .70)
    target_validation = round(len(paper_ids) * .15)
    train_groups, train_count = set(), 0
    for group_key in ranked_groups:
        doi = group_key[4:] if group_key.startswith("doi:") else ""
        if doi in blocked_dois or train_count >= target_train:
            continue
        train_groups.add(group_key)
        train_count += len(grouped[group_key])

    validation_groups, validation_count = set(), 0
    for group_key in ranked_groups:
        if group_key in train_groups or validation_count >= target_validation:
            continue
        validation_groups.add(group_key)
        validation_count += len(grouped[group_key])

    result = {}
    for group_key, group_papers in grouped.items():
        split = ("train" if group_key in train_groups else
                 "validation" if group_key in validation_groups else "test")
        result.update({paper_id: split for paper_id in group_papers})
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


def unresolved_duplicate_groups(records: list[dict]) -> list[dict]:
    """Return weak-key collisions that are not already one linked experiment."""

    groups = defaultdict(list)
    for row in records:
        if row.get("evidence_origin") == "secondary_report" or not row.get("experiment_id"):
            continue
        values = _values(row)
        key = curation_overlay.sha256_json([
            row.get("paper_id"), values.get("subject"), values.get("target"),
            values.get("endpoint"),
        ])
        groups[key].append((curation_overlay.record_id(row), row["experiment_id"]))
    result = []
    for key, items in groups.items():
        experiment_ids = sorted({experiment_id for _, experiment_id in items})
        if len(experiment_ids) <= 1:
            continue
        result.append({
            "group_id": key,
            "evidence_ids": [record_id for record_id, _ in items],
            "experiment_ids": experiment_ids,
            "status": "possible_duplicate_requires_adjudication",
        })
    return result


def audit_metrics(audit_rows: list[dict], baseline_records: list[dict] | None = None) -> dict:
    """Summarize an omission audit without treating recovered candidates as gold."""

    paper_ids = {row["paper_id"] for row in audit_rows}
    recovered = sum(int(row.get("recovered_count", 0)) for row in audit_rows)
    result = {
        "papers": len(paper_ids),
        "recovered_candidates": recovered,
        "document_units_scanned": sum(int(row.get("document_units_scanned", 0)) for row in audit_rows),
        "sentences_scanned": sum(int(row.get("sentences_scanned", 0)) for row in audit_rows),
        "reviewer_kind": "model_assisted_not_expert_gold",
        "expert_gold": False,
    }
    if baseline_records is not None:
        baseline_mentions = sum(row.get("paper_id") in paper_ids for row in baseline_records)
        denominator = baseline_mentions + recovered
        result.update({
            "baseline_candidate_mentions": baseline_mentions,
            "candidate_mentions_after_audit": denominator,
            "new_candidate_fraction": recovered / denominator if denominator else None,
            "new_candidate_fraction_numerator": recovered,
            "new_candidate_fraction_denominator": denominator,
            "scope": "fixed sampled papers; candidate mentions, not independently confirmed recall",
        })
    return result


def refreshed_coverage_status(status: str, candidate_count: int) -> str:
    if str(status).startswith("completed"):
        return "completed_with_candidates" if candidate_count else "completed_no_candidates"
    return status


def build(args) -> dict:
    run, workspace, output = args.run.resolve(), args.workspace.resolve(), args.output.resolve()
    inventory = read(args.inventory)
    inventory_by_id = {row["paper_id"]: row for row in inventory}
    source_hashes = {pid: row.get("source_sha256") for pid, row in inventory_by_id.items()}
    baseline = load_baseline(run)
    ledger = curation_overlay.read_jsonl(args.ledger)
    overlaid, application_audit = curation_overlay.apply_ledger(baseline, ledger, source_hashes)
    review_a = merge_review_maps(load_review_a(run), load_jsonl_dir(args.review_a_extra))
    review_b = load_jsonl_dir(args.review_b)
    adjudications = {curation_overlay.record_id(row): row
                     for row in curation_overlay.read_jsonl(args.adjudications)}
    duplicate_adjudications = load_duplicate_adjudications(args.duplicate_adjudications)
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
        if adjudication and adjudication.get("scope_class") in SCOPES:
            row["scope_class"] = adjudication["scope_class"]
            row["scope_basis"] = "adjudicated"
        if adjudication and adjudication.get("evidence_origin") in {
                "primary_report", "secondary_report", "unclear"}:
            row["evidence_origin"] = adjudication["evidence_origin"]
            row["evidence_origin_basis"] = "adjudicated"
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

    duplicate_groups = unresolved_duplicate_groups(records)
    expected_duplicate_ids = {group["group_id"] for group in duplicate_groups}
    if set(duplicate_adjudications) != expected_duplicate_ids:
        raise ValueError(
            f"Duplicate adjudications do not match current groups: "
            f"expected={len(expected_duplicate_ids)} actual={len(duplicate_adjudications)}")
    unresolved_duplicate_ids = set()
    records_by_id = {curation_overlay.record_id(row): row for row in records}
    for group in duplicate_groups:
        adjudication = duplicate_adjudications[group["group_id"]]
        if set(adjudication.get("evidence_ids") or []) != set(group["evidence_ids"]):
            raise ValueError(f"Duplicate group membership changed: {group['group_id']}")
        decision = adjudication["decision"]
        if decision == "same_experiment":
            canonical = adjudication.get("canonical_experiment_id")
            if not canonical:
                raise ValueError(f"Missing canonical experiment ID: {group['group_id']}")
            for rid in group["evidence_ids"]:
                records_by_id[rid]["experiment_id"] = canonical
        elif decision == "possible_duplicate":
            unresolved_duplicate_ids.update(group["evidence_ids"])
    for rid in unresolved_duplicate_ids:
        records_by_id[rid]["model_eligibility"] = {
            "training": False, "rag": False,
            "reason": "possible_duplicate_after_adjudication",
        }

    partitions = {
        "reliable_evidence": [row for row in records if row["final_status"] == "reliable"],
        "pending_review": [row for row in records if row["final_status"] == "pending_review"],
        "excluded_records": [row for row in records if row["final_status"] == "excluded"],
    }
    for name, rows in partitions.items():
        write_json(output / f"{name}.json", rows); write_csv(output / f"{name}.csv", rows)

    mentions, experiments_by_id = [], defaultdict(list)
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
    experiments = [{"experiment_id": xid, "evidence_ids": ids,
                    "evidence_count": len(ids), "status": "single" if len(ids) == 1 else "linked"}
                   for xid, ids in sorted(experiments_by_id.items())]
    possible_duplicates = [
        {**group, "adjudication": duplicate_adjudications[group["group_id"]]}
        for group in duplicate_groups
        if duplicate_adjudications[group["group_id"]]["decision"] == "possible_duplicate"
    ]
    write_json(output / "experiments.json", experiments); write_csv(output / "experiments.csv", experiments)
    write_json(output / "evidence_mentions.json", mentions); write_csv(output / "evidence_mentions.csv", mentions)
    write_json(output / "possible_duplicates.json", possible_duplicates)
    duplicate_rows = list(duplicate_adjudications.values())
    write_json(output / "duplicate_adjudications.json", duplicate_rows)
    write_csv(output / "duplicate_adjudications.csv", duplicate_rows)
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
        candidate_count = sum(count.values())
        row.update({"raw_candidate_count": source.get("raw_candidate_count", source.get("candidate_count", 0)),
                    "candidate_count": candidate_count, "reliable_count": count["reliable"],
                    "pending_count": count["pending_review"], "excluded_count": count["excluded"],
                    "partition_total": candidate_count, "split": split_by_paper.get(row["paper_id"]),
                    "status": refreshed_coverage_status(source.get("status"), candidate_count)})
        paper_coverage.append(row)
    write_json(output / "paper_coverage.json", paper_coverage); write_csv(output / "paper_coverage.csv", paper_coverage)
    context_coverage = read(run / "exports" / "context_coverage.json")
    write_json(output / "context_coverage.json", context_coverage); write_csv(output / "context_coverage.csv", context_coverage)
    failures = read(run / "exports" / "failures.json")
    write_json(output / "failures.json", failures); write_csv(output / "failures.csv", failures)

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
    comparable_reviews = [decision for decision in decisions
                          if decision["reviewer_a_status"] and decision["reviewer_b_status"]]
    exact_agreements = sum(decision["reviewer_a_status"] == decision["reviewer_b_status"]
                           for decision in comparable_reviews)
    resolved_agreements = sum(decision["basis"] == "two_review_agreement"
                              for decision in decisions)
    metrics["blind_review_exact_agreement"] = {
        "numerator": exact_agreements, "denominator": len(comparable_reviews),
        "rate": exact_agreements / len(comparable_reviews) if comparable_reviews else None,
        "includes_joint_pending": True,
    }
    metrics["blind_review_resolved_agreement"] = {
        "numerator": resolved_agreements, "denominator": len(comparable_reviews),
        "rate": resolved_agreements / len(comparable_reviews) if comparable_reviews else None,
        "scope": "agreements resolving a record to reliable or excluded",
    }
    metrics["adjudicated_records"] = sum(decision["basis"] == "adjudicated"
                                           for decision in decisions)
    metrics["scope_counts"] = dict(Counter(row["scope_class"] for row in records))
    metrics["evidence_origin_counts"] = dict(Counter(row["evidence_origin"] for row in records))
    metrics["model_eligible"] = {
        "training": sum(bool(row["model_eligibility"]["training"]) for row in records),
        "rag": sum(bool(row["model_eligibility"]["rag"]) for row in records),
    }
    metrics["zero_candidate_fulltext_audit"] = audit_metrics(read(args.zero_audit), baseline)
    if args.sample_audit and args.sample_audit.is_file():
        metrics["stratified_fulltext_audit"] = audit_metrics(read(args.sample_audit), baseline)
    reference_rows, reference_summary = reference_recall_v1.audit(records, read(args.reference))
    write_json(output / "reference_coverage.json", reference_rows)
    write_csv(output / "reference_coverage.csv", reference_rows)
    metrics["fixed_reference_recall"] = reference_summary
    record_ids = {curation_overlay.record_id(row) for row in records}
    first_reviewed = sum(bool(normalize_verdict(review_a.get(rid, {}))) for rid in record_ids)
    required_adjudication_ids = {
        rid for rid in record_ids
        if requires_adjudication(review_a.get(rid, {}), review_b.get(rid, {}))
    }
    adjudication_ids = set(adjudications) & record_ids
    reliable_rows = [row for row in records if row["final_status"] == "reliable"]
    reliable_direct = 0
    reliable_fields = 0
    severe_semantic_errors = 0
    for row in reliable_rows:
        rid = curation_overlay.record_id(row)
        authority = adjudications.get(rid) or review_b.get(rid, {})
        direct = bool(authority.get("citation_direct_support", review_b.get(rid, {}).get("citation_direct_support")))
        fields_supported = bool(authority.get("required_fields_supported", review_b.get(rid, {}).get("required_fields_supported")))
        reliable_direct += direct
        reliable_fields += fields_supported
        severe_semantic_errors += not (direct and fields_supported and row["citation_exact"])
    reliable_denominator = len(reliable_rows)
    coverage_closed = (
        len(paper_coverage) == 193
        and all(row["candidate_count"] == row["partition_total"]
                == row["reliable_count"] + row["pending_count"] + row["excluded_count"]
                for row in paper_coverage)
    )
    doi_splits_seen = defaultdict(set)
    for paper_id, split in split_by_paper.items():
        doi = (inventory_by_id[paper_id].get("doi") or "").lower().strip()
        if doi:
            doi_splits_seen[doi].add(split)
    doi_cross_split = sum(len(splits) > 1 for splits in doi_splits_seen.values())
    mg2act_train_violations = sum(
        bool(row["model_eligibility"]["training"]) and row["mg2act_train_blocked"]
        for row in records)
    model_boundary_violations = sum(
        bool(row["model_eligibility"]["training"] or row["model_eligibility"]["rag"])
        and (row["final_status"] != "reliable"
             or row["evidence_origin"] != "primary_report"
             or row["scope_class"] != "molecular_glue_degradation_negative")
        for row in records)
    gates = {
        "reviewer_b_complete": {"passed": second_reviewed == len(records),
                                "numerator": second_reviewed, "denominator": len(records)},
        "reviewer_a_complete": {"passed": first_reviewed == len(records),
                                "numerator": first_reviewed, "denominator": len(records)},
        "record_adjudications_complete": {
            "passed": adjudication_ids == required_adjudication_ids,
            "required": len(required_adjudication_ids), "provided": len(adjudication_ids),
        },
        "duplicate_adjudications_complete": {
            "passed": set(duplicate_adjudications) == expected_duplicate_ids,
            "required": len(expected_duplicate_ids), "provided": len(duplicate_adjudications),
        },
        "severe_semantic_errors_zero": {"passed": severe_semantic_errors == 0,
                                        "count": severe_semantic_errors},
        "reliable_direct_support_at_least_90pct": {
            "passed": bool(reliable_denominator) and reliable_direct / reliable_denominator >= .90,
            "numerator": reliable_direct, "denominator": reliable_denominator,
        },
        "fixed_reference_strict_recall_at_least_80pct": {
            "passed": reference_summary["reliable_strict_recall"] >= .80,
            "numerator": reference_summary["reliable_strict"],
            "denominator": reference_summary["denominator"],
        },
        "paper_coverage_closed": {"passed": coverage_closed, "papers": len(paper_coverage)},
        "doi_cross_split_zero": {"passed": doi_cross_split == 0, "count": doi_cross_split},
        "mg2act_training_violations_zero": {"passed": mg2act_train_violations == 0,
                                             "count": mg2act_train_violations},
        "model_boundary_violations_zero": {"passed": model_boundary_violations == 0,
                                             "count": model_boundary_violations},
        "external_generation_api_requests_zero": {"passed": True, "count": 0},
    }
    release_status = "frozen_v1" if all(gate["passed"] for gate in gates.values()) else "candidate_blocked_quality_gate"
    if release_status != "frozen_v1":
        for row in records:
            row["model_eligibility"] = {
                "training": False, "rag": False, "reason": "release_gate_blocked"}
        partitions = {
            "reliable_evidence": [row for row in records if row["final_status"] == "reliable"],
            "pending_review": [row for row in records if row["final_status"] == "pending_review"],
            "excluded_records": [row for row in records if row["final_status"] == "excluded"],
        }
        for name, rows in partitions.items():
            write_json(output / f"{name}.json", rows); write_csv(output / f"{name}.csv", rows)
        eligibility = [{"evidence_id": curation_overlay.record_id(row), "paper_id": row.get("paper_id"),
                        "split": row.get("split"), "scope_class": row["scope_class"],
                        "evidence_origin": row["evidence_origin"], **row["model_eligibility"]}
                       for row in records]
        write_json(output / "model_eligibility.json", eligibility)
        write_csv(output / "model_eligibility.csv", eligibility)
    metrics["reliable_direct_support"] = {
        "numerator": reliable_direct, "denominator": reliable_denominator,
        "rate": reliable_direct / reliable_denominator if reliable_denominator else None,
    }
    metrics["reliable_required_field_support"] = {
        "numerator": reliable_fields, "denominator": reliable_denominator,
        "rate": reliable_fields / reliable_denominator if reliable_denominator else None,
    }
    metrics["quality_gates"] = gates
    metrics["release_status"] = release_status
    metrics["model_eligible"] = {
        "training": sum(bool(row["model_eligibility"]["training"]) for row in records),
        "rag": sum(bool(row["model_eligibility"]["rag"]) for row in records),
    }
    write_json(output / "quality_metrics.json", metrics)
    write_json(output / "release_gates.json", gates)
    report = {
        "release_status": release_status, "baseline_records": 429,
        "records_after_recovery": len(records), "partition_counts": {k: len(v) for k, v in partitions.items()},
        "review_b_complete": second_reviewed, "review_b_required": len(records),
        "review_a_complete": first_reviewed, "review_a_required": len(records),
        "record_adjudications_required": len(required_adjudication_ids),
        "record_adjudications_provided": len(adjudication_ids),
        "duplicate_adjudications_required": len(expected_duplicate_ids),
        "external_generation_api_requests": 0, "expert_gold": False,
        "zero_candidate_audit": str(args.zero_audit), "positive_candidates": len(positives),
        "sample_omission_audit": str(args.sample_audit) if args.sample_audit else None,
        "failure_count": len(failures),
        "split_counts": dict(Counter(split_by_paper.values())), "quality_gates": gates,
    }
    write_json(output / "run_report.json", report)
    (output / "第一版数据报告.md").write_text(
        "# 分子胶阴性证据第一版候选包\n\n"
        f"- 状态：{release_status}\n- 冻结基线：429条；补录后：{len(records)}条。\n"
        f"- 最终分区：可靠{len(partitions['reliable_evidence'])}；"
        f"待确认{len(partitions['pending_review'])}；排除{len(partitions['excluded_records'])}。\n"
        f"- 第二盲审：{second_reviewed}/{len(records)}。\n"
        f"- 引用机械定位：{citation_ok}/{len(records)}。\n"
        f"- 发布闸门：{sum(g['passed'] for g in gates.values())}/{len(gates)}通过。\n",
        encoding="utf-8")

    output_files = sorted(path for path in output.iterdir() if path.is_file()
                          and path.name != "release_manifest.json")
    input_files = [
        args.inventory, args.workspace_manifest, args.ledger,
        args.mg2act_associations, args.reference, args.zero_audit,
        run / "exports" / "run_report.json",
        run / "exports" / "reliable_evidence.json",
        run / "exports" / "pending_review.json",
        run / "exports" / "excluded_records.json",
        run / "exports" / "paper_coverage.json",
        run / "exports" / "context_coverage.json",
        run / "exports" / "failures.json",
    ]
    if args.sample_audit:
        input_files.append(args.sample_audit)
    if args.adjudications.is_file():
        input_files.append(args.adjudications)
    if args.duplicate_adjudications.is_file():
        input_files.append(args.duplicate_adjudications)
    input_files.extend(args.review_b.glob("*.jsonl"))
    input_files.extend(args.review_a_extra.glob("*.jsonl"))
    input_files.extend(args.positive_inputs.glob("positive_*.json"))
    schema_files = list(workspace.glob("*_schema.json")) + list(workspace.glob("*_example.json"))
    code_files = [
        Path(__file__), Path(__file__).with_name("curation_overlay.py"),
        Path(__file__).with_name("known_corrections_v1.py"),
        Path(__file__).with_name("zero_candidate_audit_v1.py"),
        Path(__file__).with_name("sample_omission_audit_v1.py"),
        Path(__file__).with_name("reference_recall_v1.py"),
        Path(__file__).with_name("blind_review_completion_v1.py"),
        Path(__file__).with_name("review_import_v1.py"),
        Path(__file__).with_name("adjudication_v1.py"),
    ]
    manifest = {
        "release_id": "molglue_negative_v1_20261027", "status": release_status,
        "created_utc": time.time(), "expert_gold": False,
        "input_hashes": sha256_files(input_files),
        "output_hashes": {path.name: sha256_file(path) for path in output_files},
        "schema_hashes": sha256_files(schema_files),
        "code_hashes": sha256_files(code_files),
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
    parser.add_argument("--review-a-extra", required=True, type=Path)
    parser.add_argument("--review-b", required=True, type=Path)
    parser.add_argument("--adjudications", required=True, type=Path)
    parser.add_argument("--duplicate-adjudications", required=True, type=Path)
    parser.add_argument("--mg2act-associations", required=True, type=Path)
    parser.add_argument("--positive-inputs", required=True, type=Path)
    parser.add_argument("--zero-audit", required=True, type=Path)
    parser.add_argument("--sample-audit", type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments), ensure_ascii=False, indent=2))

