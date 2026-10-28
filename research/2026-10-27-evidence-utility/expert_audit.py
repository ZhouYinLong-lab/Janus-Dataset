"""Build and import a blinded expert audit packet from frozen utility results."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from common import digest, read, seal, sha, verify, write
from utility_error_analysis import stable_key


OUTCOME_TARGETS = {"not_observed": 12, "relative_weakening": 6,
                   "conditional_loss": 5, "reduced": 3, "rare_boundary": 4}
SPLIT_TARGETS = {"train": 20, "val": 5, "test": 5}
OUTCOME_SPLIT_TARGETS = {
    "not_observed": {"train": 6, "val": 3, "test": 3},
    "relative_weakening": {"train": 5, "val": 1, "test": 0},
    "conditional_loss": {"train": 3, "val": 1, "test": 1},
    "reduced": {"train": 2, "val": 0, "test": 1},
    "rare_boundary": {"train": 4, "val": 0, "test": 0},
}
RESPONSE_FIELDS = ("audit_id", "item_type", "experiment_performed",
                   "negative_or_boundary_supported", "subject_correct", "target_correct",
                   "endpoint_correct", "direction_correct", "conditions_correct",
                   "citation_supported", "single_supported_option", "decision",
                   "correct_option_if_applicable", "corrections", "reason", "reviewer_id", "reviewed_at")
BOOLEAN_VALUES = {"", "true", "false", "uncertain", "not_applicable"}
DECISION_VALUES = {"", "accept", "correct", "exclude", "not_assessable"}


def outcome_bucket(row):
    value = row.get("outcome_type")
    return value if value in {"not_observed", "relative_weakening", "conditional_loss", "reduced"} else "rare_boundary"


def endpoint_bucket(row):
    text = str((row.get("values") or {}).get("endpoint") or "").casefold()
    if "degrad" in text or "deplet" in text:
        return "protein_degradation"
    if "abundance" in text or "level" in text:
        return "protein_abundance"
    if "bind" in text or "recruit" in text or "interaction" in text:
        return "binding_or_recruitment"
    return "other_endpoint"


def incomplete_context(row):
    values = row.get("values") or {}
    if not values.get("scope_condition") or not row.get("conditions"):
        return True
    items = (row.get("conditions") or {}).get("items") or []
    condition_values = [x.get("values") or {} for x in items]
    return not condition_values or all(not any(v.get(k) for k in ("cell_line", "treatment_time",
                                                                   "tested_concentration", "assay"))
                                       for v in condition_values)


def select_evidence(rows, seed=20261028):
    rows = [r for r in rows if r.get("kind") == "negative" and r.get("content_decision") == "reliable"]
    if len(rows) != 148:
        raise ValueError("Expected 148 frozen reliable negative records")
    selected, doi_counts, split_counts, endpoint_counts = [], Counter(), Counter(), Counter()
    # Fill scarce held-out strata first, then training strata. This makes the
    # split allocation deterministic instead of merely hoping all splits occur.
    strata = []
    for split in ("test", "val", "train"):
        current = [(bucket, split, splits[split]) for bucket, splits in OUTCOME_SPLIT_TARGETS.items()
                   if splits[split]]
        current.sort(key=lambda item: sum(outcome_bucket(r) == item[0] and r.get("split") == split
                                          for r in rows))
        strata.extend(current)
    for bucket, split, target in strata:
        candidates = [r for r in rows if outcome_bucket(r) == bucket and r.get("split") == split]
        for _ in range(target):
            available = [r for r in candidates if r not in selected and doi_counts[r.get("doi")] < 2]
            if not available:
                raise ValueError(f"Insufficient evidence diversity for {bucket}/{split}")
            def rank(row):
                new_endpoint = int(endpoint_counts[endpoint_bucket(row)] == 0)
                context_bonus = int(incomplete_context(row) and sum(incomplete_context(x) for x in selected) < 4)
                return (-new_endpoint, -context_bonus,
                        stable_key(seed, f"evidence:{bucket}:{split}", row["evidence_id"]))
            row = sorted(available, key=rank)[0]
            selected.append(row)
            doi_counts[row.get("doi")] += 1
            split_counts[split] += 1
            endpoint_counts[endpoint_bucket(row)] += 1
    if (len(selected) != 30 or dict(split_counts) != SPLIT_TARGETS or
            Counter(outcome_bucket(x) for x in selected) != Counter(OUTCOME_TARGETS)):
        raise ValueError("Evidence sample failed exact outcome/split allocation")
    return selected


def blind_evidence(row):
    return {"audit_id": "AUD_E_" + digest(row["evidence_id"])[:12], "item_type": "evidence",
            "doi": row.get("doi"), "paper_id": row.get("paper_id"),
            "extracted_fields": row.get("values"), "reported_conditions": row.get("conditions"),
            "source_quote": row.get("original_quote"),
            "source_locator": [{k: x.get(k) for k in ("unit_id", "char_start", "char_end", "locator")}
                               for x in row.get("field_evidence", [])]}


def pick(rows, count, stratum, used, seed, predicate):
    candidates = [r for r in rows if predicate(r) and r["question_id"] not in used]
    ordered = sorted(candidates, key=lambda r: stable_key(seed, stratum, r["question_id"]))
    chosen = ordered[:count]
    if len(chosen) != count:
        raise ValueError(f"Insufficient RAG rows for {stratum}: {len(chosen)}/{count}")
    used.update(x["question_id"] for x in chosen)
    return [(x, stratum) for x in chosen]


def select_rag(rows, seed=20261028):
    used, chosen = set(), []
    chosen += pick(rows, 1, "historical_unknown", used, seed,
                   lambda r: any(x["status"] == "historical_unknown" for x in r["arms"].values()))
    chosen += pick(rows, 1, "invalid_response", used, seed,
                   lambda r: any(x["status"] == "invalid_response" for x in r["arms"].values()))
    chosen += pick(rows, 2, "recovered_regression", used, seed,
                   lambda r: r["recovered_vs_structured"] == "worse")
    chosen += pick(rows, 5, "recovered_gain", used, seed,
                   lambda r: r["recovered_vs_structured"] == "better")
    chosen += pick(rows, 4, "raw_advantage", used, seed,
                   lambda r: r["recovered_vs_raw"] == "worse")
    chosen += pick(rows, 4, "recovered_equal", used, seed,
                   lambda r: r["recovered_vs_structured"] == "equal")
    chosen += pick(rows, 3, "background_control", used, seed,
                   lambda r: r["recovered_vs_background"] == "equal")
    if len(chosen) != 20:
        raise ValueError("RAG expert sample must contain 20 items")
    return chosen


def rag_arm_for(row, stratum):
    if stratum == "historical_unknown":
        return next(a for a, x in row["arms"].items() if x["status"] == "historical_unknown")
    if stratum == "invalid_response":
        return next(a for a, x in row["arms"].items() if x["status"] == "invalid_response")
    if stratum == "raw_advantage":
        return "raw"
    return "recovered"


def blind_rag(row, stratum, evidence_map):
    arm = rag_arm_for(row, stratum)
    data = row["arms"][arm]
    if stratum not in {"historical_unknown", "invalid_response"} and not data.get("answer"):
        raise ValueError("Selected RAG answer is missing: " + row["question_id"])
    supplied, id_map = [], {}
    for i, original_id in enumerate(data.get("evidence_ids") or [], 1):
        if original_id not in evidence_map:
            raise ValueError("RAG evidence is absent from frozen inputs: " + original_id)
        blind_id = f"E{i:02d}"
        id_map[original_id] = blind_id
        source = evidence_map.get(original_id, {})
        supplied.append({"evidence_id": blind_id, "text": source.get("text"), "doi": source.get("doi")})
    return ({"audit_id": "AUD_R_" + digest([row["question_id"], arm])[:12], "item_type": "rag_answer",
             "question": row["question"], "reference_evidence": row.get("reference_evidence", []),
             "supplied_evidence": supplied, "answer": data.get("answer"),
             "citations": [id_map.get(x, "UNMAPPED") for x in (data.get("citations") or [])],
             "response_status": "available" if data.get("answer") else "not_available"},
            arm, data, id_map)


def select_fixed(rows, seed=20261028):
    used, selected = set(), []
    selected += pick(rows, 4, "model_disagreement", used, seed, lambda r: r["model_disagreement"])
    selected += pick(rows, 6, "common_failure", used, seed, lambda r: r["all_wrong"])
    selected += pick(rows, 5, "common_correct_control", used, seed, lambda r: r["all_correct"])
    if len(selected) != 15:
        raise ValueError("Fixed-choice expert sample must contain 15 items")
    return selected


def blind_fixed(row):
    return {"audit_id": "AUD_F_" + digest(row["question_id"])[:12], "item_type": "fixed_choice",
            "question": row["question"], "reference_evidence": row.get("reference_evidence", []),
            "options": [x["text"] for x in row["options"]]}


def write_csv(path, fields, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ensure_blinded(packet):
    forbidden = {"arm", "model", "stratum", "correct_option", "current_judgment",
                 "predicted_category", "selection_reason"}
    def walk(value):
        if isinstance(value, dict):
            if forbidden & set(value):
                raise ValueError("Blinded packet leaks private keys")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(packet)


def build(analysis, evidence, raw, out, seed=20261028):
    analysis, out = Path(analysis), Path(out)
    verify(analysis)
    if Path(evidence).parent != Path(raw).parent:
        raise ValueError("Evidence and raw contexts must come from the same frozen bundle")
    verify(Path(evidence).parent)
    evidence_rows = read(evidence)
    raw_rows = read(raw)
    evidence_map = {x["evidence_id"]: x for x in evidence_rows + raw_rows}
    rag_rows, lora_rows = read(analysis / "rag_question_analysis.json"), read(analysis / "lora_question_analysis.json")
    packet, key = [], []
    selected_evidence = select_evidence(evidence_rows, seed)
    for row in selected_evidence:
        item = blind_evidence(row)
        packet.append(item)
        key.append({"audit_id": item["audit_id"], "item_type": "evidence",
                    "evidence_id": row["evidence_id"], "outcome_bucket": outcome_bucket(row),
                    "endpoint_bucket": endpoint_bucket(row), "split": row.get("split"),
                    "current_decision": row.get("content_decision"), "expected_fields": row.get("values")})
    rag_selected = select_rag(rag_rows, seed)
    for row, stratum in rag_selected:
        item, arm, data, id_map = blind_rag(row, stratum, evidence_map)
        packet.append(item)
        key.append({"audit_id": item["audit_id"], "item_type": "rag_answer",
                    "question_id": row["question_id"], "task_id": data["task_id"], "arm": arm,
                    "selection_stratum": stratum, "current_judgment": {
                        "score": data.get("score"), "criteria": data.get("criteria"),
                        "overclaim": data.get("overclaim"), "citation_supported": data.get("citation_supported")},
                    "evidence_id_map": id_map})
    fixed_selected = select_fixed(lora_rows, seed)
    for row, stratum in fixed_selected:
        item = blind_fixed(row)
        packet.append(item)
        key.append({"audit_id": item["audit_id"], "item_type": "fixed_choice",
                    "question_id": row["question_id"], "selection_stratum": stratum,
                    "correct_option": row["correct_option"],
                    "model_predictions": {m: x["predicted_category"] for m, x in row["models"].items()}})
    if len(packet) != 65 or len({x["audit_id"] for x in packet}) != 65:
        raise ValueError("Expert packet must contain 65 unique audit IDs")
    ensure_blinded(packet)
    out.mkdir(parents=True, exist_ok=False)
    write(out / "expert_packet.json", packet)
    write(out / "expert_private_key.json", key)
    write_csv(out / "expert_packet.csv", ("audit_id", "item_type", "payload_json"),
              [{"audit_id": x["audit_id"], "item_type": x["item_type"],
                "payload_json": json.dumps(x, ensure_ascii=False, sort_keys=True)} for x in packet])
    response_rows = [{field: (x["audit_id"] if field == "audit_id" else x["item_type"] if field == "item_type" else "")
                      for field in RESPONSE_FIELDS} for x in packet]
    write_csv(out / "expert_response_form.csv", RESPONSE_FIELDS, response_rows)
    summary = {"total": 65, "evidence": 30, "rag_answer": 20, "fixed_choice": 15,
               "rag_available_answers": sum(x["item_type"] == "rag_answer" and x["response_status"] == "available"
                                            for x in packet),
               "rag_system_exceptions": sum(x["item_type"] == "rag_answer" and x["response_status"] != "available"
                                            for x in packet),
               "evidence_outcomes": dict(Counter(outcome_bucket(x) for x in selected_evidence)),
               "evidence_splits": dict(Counter(x.get("split") for x in selected_evidence)),
               "evidence_endpoint_buckets": dict(Counter(endpoint_bucket(x) for x in selected_evidence)),
               "evidence_incomplete_context": sum(incomplete_context(x) for x in selected_evidence),
               "rag_strata": dict(Counter(s for _, s in rag_selected)),
               "fixed_strata": dict(Counter(s for _, s in fixed_selected)),
               "seed": seed, "expert_reviews_completed": 0, "external_generation_requests": 0,
               "review_status": "packet_prepared_not_reviewed"}
    write(out / "sampling_report.json", summary)
    write(out / "response_schema.json", {"fields": list(RESPONSE_FIELDS),
                                          "boolean_values": ["true", "false", "uncertain", "not_applicable"],
                                          "decision_values": ["accept", "correct", "exclude", "not_assessable"]})
    seal(out, [analysis / "manifest.json", evidence, raw],
         {"artifact": "expert_audit_packet", "seed": seed, "external_generation_requests": 0})
    write(out / "expert_packet_manifest.json", read(out / "manifest.json"))
    return summary


def import_reviews(package, responses, out):
    package, out = Path(package), Path(out)
    verify(package)
    allowed = {x["audit_id"] for x in read(package / "expert_packet.json")}
    merged = {}
    for response in responses:
        with Path(response).open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if not row.get("audit_id") or not row.get("reviewer_id"):
                    continue
                if row["audit_id"] not in allowed:
                    raise ValueError("Unknown expert audit ID")
                key = (row["audit_id"], row["reviewer_id"])
                normalized = {field: row.get(field, "").strip() for field in RESPONSE_FIELDS}
                for field in ("experiment_performed", "negative_or_boundary_supported",
                              "subject_correct", "target_correct", "endpoint_correct",
                              "direction_correct", "conditions_correct", "citation_supported",
                              "single_supported_option"):
                    if normalized[field] not in BOOLEAN_VALUES:
                        raise ValueError(f"Invalid value for {field}: {normalized[field]}")
                if normalized["decision"] not in DECISION_VALUES:
                    raise ValueError("Invalid expert decision: " + normalized["decision"])
                option = normalized["correct_option_if_applicable"]
                if option and option not in {"0", "1", "2", "3"}:
                    raise ValueError("Correct option must be 0, 1, 2, or 3")
                if key in merged and merged[key] != normalized:
                    raise ValueError("Conflicting duplicate expert review")
                merged[key] = normalized
    out.mkdir(parents=True, exist_ok=False)
    reviews = [merged[k] for k in sorted(merged)]
    write(out / "expert_reviews.json", reviews)
    write(out / "import_report.json", {"unique_reviews": len(reviews), "duplicates_ignored": True,
                                        "covered_items": len({x["audit_id"] for x in reviews})})
    seal(out, [package / "manifest.json"] + list(responses), {"artifact": "expert_review_import"})
    return {"unique_reviews": len(reviews)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--analysis", required=True, type=Path)
    b.add_argument("--evidence", required=True, type=Path)
    b.add_argument("--raw", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--seed", type=int, default=20261028)
    i = sub.add_parser("import")
    i.add_argument("--package", required=True, type=Path)
    i.add_argument("--responses", required=True, type=Path, nargs="+")
    i.add_argument("--out", required=True, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(build(**args) if command == "build" else import_reviews(**args),
                     ensure_ascii=False, indent=2))
