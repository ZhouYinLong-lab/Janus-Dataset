"""Map frozen reference cases to v1 evidence without creating new answers."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


STOP = {"the", "a", "an", "and", "or", "of", "in", "to", "with", "compound",
        "analogue", "analog", "group", "all", "endogenous", "exogenous"}


def tokens(value) -> set[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return {token for token in re.findall(r"[a-z0-9α-ω]+", text)
            if (len(token) > 1 or token.isdigit()) and token not in STOP}


def _values(row):
    observations = (row.get("facts") or {}).get("observations") or []
    if observations:
        return observations[0].get("values") or {}
    return (row.get("observation") or {}).get("values") or {}


def _similar(left, right) -> bool:
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return False
    return bool(a & b) and (len(a & b) / min(len(a), len(b)) >= .5)


def _endpoint_match(left, right) -> bool:
    a, b = str(left or "").casefold(), str(right or "").casefold()
    if "degrad" in a and ("degrad" in b or "protein abundance" in b):
        return True
    if "protein abundance" in a and ("degrad" in b or "protein abundance" in b):
        return True
    return _similar(a, b)


def audit(records: list[dict], reference: dict) -> tuple[list[dict], dict]:
    by_paper = defaultdict(list)
    for row in records:
        by_paper[row.get("paper_id")].append(row)
    rows = []
    for case in reference.get("cases", []):
        if not case.get("core_case"):
            continue
        required = case.get("required_mapping") or {}
        source_units = set(case.get("source_unit_ids") or [])
        candidates = []
        for record in by_paper.get(case.get("paper_id"), []):
            values = _values(record)
            record_units = {span.get("unit_id") for span in record.get("evidence_spans", [])}
            dimensions = {
                "source_unit": bool(source_units & record_units),
                "compound": _similar(values.get("subject"), required.get("compound")),
                "target": _similar(values.get("target"), required.get("target")),
                "endpoint": _endpoint_match(values.get("endpoint"), required.get("endpoint")),
            }
            score = sum(dimensions.values())
            if dimensions["source_unit"] or score >= 2:
                candidates.append((score, record, dimensions))
        candidates.sort(key=lambda item: (-item[0], str(item[1].get("evidence_id"))))
        if candidates:
            score, best, dimensions = candidates[0]
            discovery_status = "matched" if all(dimensions.values()) else "partial"
            final_status = discovery_status if best.get("final_status") == "reliable" else "not_reliable"
            evidence_id = best.get("evidence_id") or best.get("record_id")
        else:
            score, dimensions, discovery_status, final_status, evidence_id = 0, {}, "missed", "missed", None
        rows.append({
            "reference_id": case.get("id"), "paper_id": case.get("paper_id"),
            "core_case": True, "evidence_id": evidence_id,
            "discovery_status": discovery_status, "reliable_status": final_status,
            "match_score": score, "dimensions": dimensions,
            "expected_core": case.get("expected_core"),
            "mapping_method": "frozen_reference_fields_and_source_units",
            "expert_gold": False,
        })
    discovery_matched = sum(row["discovery_status"] == "matched" for row in rows)
    discovery_partial = sum(row["discovery_status"] == "partial" for row in rows)
    reliable_matched = sum(row["reliable_status"] == "matched" for row in rows)
    summary = {
        "denominator": len(rows), "reference_status": reference.get("reference_status"),
        "discovery_strict": discovery_matched,
        "discovery_partial": discovery_partial,
        "discovery_strict_recall": discovery_matched / len(rows) if rows else None,
        "discovery_including_partial_recall": (discovery_matched + discovery_partial) / len(rows) if rows else None,
        "reliable_strict": reliable_matched,
        "reliable_strict_recall": reliable_matched / len(rows) if rows else None,
        "reviewer_kind": "deterministic_mapping_to_frozen_model_assisted_reference",
        "expert_gold": False,
    }
    return rows, summary

