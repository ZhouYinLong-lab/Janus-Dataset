"""Map frozen narrative negative evidence to structured MolGlueDB entities.

The mapper is deterministic and DOI-scoped. It never infers a structure from a
name outside the same source paper and keeps condition-specific negative
observations separate from database-level activity labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem, rdBase


OUTCOME_PRIMARY = "not_observed"
BOUNDARY_OUTCOMES = {
    "relative_weakening", "conditional_loss", "reduced",
    "not_significant", "not_improved", "unchanged",
}
GENERIC_TARGET_TERMS = (
    "cellular proteins", "other cdks", "other kinases", "related hdacs",
    "all tested", "protein levels", "degradation activity",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(*parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def normalize_doi(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    return text.rstrip("/")


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"[^a-z0-9αβγδκ-]+", " ", text)
    return " ".join(text.split())


def strip_role_prefix(value: object) -> str:
    text = normalize_text(value)
    return re.sub(
        r"^(?:the )?(?:compound|compounds|cmpd|degrader|degraders|ligand|ligands)\s+",
        "",
        text,
    )


def explicit_numbered_member(subject: object, database_name: object) -> bool:
    """Return true when a numbered compound is explicitly present in a list/range."""
    subject_text = normalize_text(subject)
    database_text = normalize_text(database_name)
    match = re.fullmatch(r"(?:(?:compound|cmpd)\s*)?(\d{1,3}[a-z]?)", database_text)
    if not match or not re.search(r"\b(?:compound|compounds|analog|analogue)s?\b", subject_text):
        return False
    identifier = match.group(1)
    if re.search(rf"(?<![a-z0-9-]){re.escape(identifier)}(?![a-z0-9-])", subject_text):
        return True
    if identifier.isdigit():
        number = int(identifier)
        for start, end in re.findall(r"(?<!\d)(\d{1,3})\s*-\s*(\d{1,3})(?!\d)", subject_text):
            low, high = sorted((int(start), int(end)))
            if low <= number <= high:
                return True
    return False


def canonical_smiles(value: object) -> str | None:
    mol = Chem.MolFromSmiles(str(value or ""))
    return Chem.MolToSmiles(mol, canonical=True) if mol is not None else None


def name_match(subject: object, database_name: object) -> tuple[str | None, float]:
    subject_norm = normalize_text(subject)
    stripped = strip_role_prefix(subject)
    name_norm = normalize_text(database_name)
    if not name_norm or name_norm == "nan":
        return None, 0.0
    if subject_norm == name_norm or stripped == name_norm:
        return "exact", 1.0
    compact_subject = re.sub(r"[-\s]", "", stripped)
    compact_name = re.sub(r"[-\s]", "", strip_role_prefix(database_name))
    if compact_subject and compact_subject == compact_name:
        return "normalized_identifier", 0.98
    if explicit_numbered_member(subject, database_name):
        return "explicit_numbered_member", 0.97
    # A named parent is not equivalent to its analog series or a modified form.
    if re.search(r"\b(?:analog|analogue|derivative)s?\b", subject_norm):
        return None, 0.0
    if "deuterated" in subject_norm and "deuterated" not in name_norm:
        return None, 0.0
    excluded = rf"(?:other than|except)\s+{re.escape(name_norm)}(?:\s|$)"
    if re.search(excluded, subject_norm):
        return None, 0.0
    # Hyphens are treated as part of identifiers, preventing FL2 from matching FL2-14.
    token = rf"(?<![a-z0-9-]){re.escape(name_norm)}(?![a-z0-9-])"
    if re.search(token, subject_norm):
        return "bounded_token", 0.95
    return None, 0.0


def normalize_target(value: object) -> str:
    text = normalize_text(value)
    replacements = {
        "β-catenin": "ctnnb1",
        "beta-catenin": "ctnnb1",
        "cyclin k": "ccnk",
        "cyck": "ccnk",
        "ck1α": "csnk1a1",
        "ck1a": "csnk1a1",
        "plzf-rarα": "zbtb16-rara",
        "plzf": "zbtb16",
    }
    for old, new in replacements.items():
        text = text.replace(normalize_text(old), new)
    text = re.sub(r"\b(?:endogenous|nuclear|protein|proteins|levels?|abundance)\b", " ", text)
    return " ".join(text.split())


def target_is_specific(value: object) -> bool:
    normalized = normalize_target(value)
    return bool(normalized) and not any(term in normalized for term in GENERIC_TARGET_TERMS)


def flatten_conditions(record: dict[str, Any]) -> dict[str, Any]:
    items = (record.get("conditions") or {}).get("items") or []
    values = dict((items[0].get("values") or {}) if items else {})
    values["scope_condition"] = (record.get("values") or {}).get("scope_condition")
    return values


def prepare_database(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "DATAID", "SMILES", "Name", "IsActive", "PrimaryTarget",
        "RecruitingProtein", "SourceAddress_Website",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"MolGlueDB missing columns: {missing}")
    frame = frame.copy()
    frame["doi"] = frame["SourceAddress_Website"].map(normalize_doi)
    frame["canonical_smiles"] = frame["SMILES"].map(canonical_smiles)
    frame["target_normalized"] = frame["PrimaryTarget"].map(normalize_target)
    frame["e3_normalized"] = frame["RecruitingProtein"].map(normalize_text)
    return frame


def map_records(evidence: list[dict[str, Any]], database: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    mapped: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    for record in evidence:
        doi = normalize_doi(record.get("doi"))
        values = record.get("values") or {}
        subject = values.get("subject")
        target = values.get("target")
        candidates = database[database["doi"] == doi]
        matches = []
        for _, row in candidates.iterrows():
            rule, confidence = name_match(subject, row["Name"])
            if not rule:
                continue
            e3 = None if pd.isna(row["RecruitingProtein"]) else str(row["RecruitingProtein"])
            e3_valid = bool(e3 and normalize_text(e3) not in {"", "unknown", "nan"})
            smiles = row["canonical_smiles"]
            combination = bool(re.search(r"\b(?:plus|with|after)\b", normalize_text(subject)))
            specific_target = target_is_specific(target)
            high_confidence = bool(
                confidence >= 0.95 and smiles and e3_valid and specific_target and not combination
            )
            mapping_id = "NM_" + stable_id(
                record.get("evidence_id"), row["DATAID"], smiles, normalize_target(target)
            )
            matches.append({
                "mapping_id": mapping_id,
                "evidence_id": record.get("evidence_id"),
                "experiment_id": record.get("experiment_id"),
                "paper_id": record.get("paper_id"),
                "doi": doi,
                "source_sha256": record.get("source_sha256"),
                "outcome_type": record.get("outcome_type"),
                "subject": subject,
                "database_name": row["Name"],
                "data_id": int(row["DATAID"]),
                "smiles": row["SMILES"],
                "canonical_smiles": smiles,
                "target_reported": target,
                "target_normalized": normalize_target(target),
                "database_primary_target": None if pd.isna(row["PrimaryTarget"]) else str(row["PrimaryTarget"]),
                "e3": e3,
                "conditions": flatten_conditions(record),
                "endpoint": values.get("endpoint"),
                "observation": values.get("observation"),
                "match_rule": rule,
                "match_confidence": confidence,
                "combination_or_perturbation": combination,
                "target_specific": specific_target,
                "high_confidence": high_confidence,
                "database_is_active": int(row["IsActive"]),
            })
        if matches:
            mapped.extend(matches)
        else:
            unmapped.append({
                "evidence_id": record.get("evidence_id"),
                "experiment_id": record.get("experiment_id"),
                "doi": doi,
                "subject": subject,
                "target": target,
                "outcome_type": record.get("outcome_type"),
                "reason": "no_doi_scoped_name_match",
            })
    return mapped, unmapped


def deduplicate_units(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("experiment_id")),
            str(row.get("canonical_smiles")),
            str(row.get("target_normalized")),
            str(row.get("outcome_type")),
        )
        current = best.get(key)
        if current is None or (row["high_confidence"], row["match_confidence"]) > (
            current["high_confidence"], current["match_confidence"]
        ):
            best[key] = row
    return sorted(best.values(), key=lambda row: row["mapping_id"])


def positive_pool(database: pd.DataFrame) -> list[dict[str, Any]]:
    eligible = database[
        (database["IsActive"] == 1)
        & database["canonical_smiles"].notna()
        & database["PrimaryTarget"].notna()
        & database["RecruitingProtein"].notna()
        & ~database["e3_normalized"].isin(["", "unknown", "nan"])
    ]
    rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for _, row in eligible.iterrows():
        key = (row["doi"], row["canonical_smiles"], row["target_normalized"], row["e3_normalized"])
        rows[key] = {
            "positive_id": "PM_" + stable_id(*key),
            "doi": row["doi"],
            "data_id": int(row["DATAID"]),
            "name": row["Name"],
            "smiles": row["SMILES"],
            "canonical_smiles": row["canonical_smiles"],
            "target": row["PrimaryTarget"],
            "target_normalized": row["target_normalized"],
            "e3": row["RecruitingProtein"],
            "e3_normalized": row["e3_normalized"],
            "label_source": "MolGlueDB IsActive=1",
        }
    return sorted(rows.values(), key=lambda row: row["positive_id"])


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--molgluedb", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence_all = json.loads(args.evidence.read_text(encoding="utf-8"))
    evidence = [row for row in evidence_all if row.get("kind") == "negative"]
    if len(evidence) != 148:
        raise ValueError(f"frozen negative evidence identity changed: {len(evidence)}")
    database = prepare_database(args.molgluedb)
    mapped_mentions, unmapped = map_records(evidence, database)
    units = deduplicate_units(mapped_mentions)
    primary = [row for row in units if row["outcome_type"] == OUTCOME_PRIMARY and row["high_confidence"]]
    boundary = [row for row in units if row["outcome_type"] in BOUNDARY_OUTCOMES and row["high_confidence"]]
    positives = positive_pool(database)

    primary_keys = {
        (row["canonical_smiles"], row["target_normalized"], normalize_text(row["e3"]))
        for row in primary
    }
    for row in positives:
        row["entity_overlap_with_recovered_negative"] = (
            row["canonical_smiles"], row["target_normalized"], row["e3_normalized"]
        ) in primary_keys
    usable_positives = [row for row in positives if not row["entity_overlap_with_recovered_negative"]]

    gate_metrics = {
        "high_confidence_not_observed_units": len(primary),
        "not_observed_dois": len({row["doi"] for row in primary}),
        "not_observed_targets": len({row["target_normalized"] for row in primary}),
        "nonconflicting_positive_units": len(usable_positives),
    }
    gate_checks = {
        "at_least_50_negatives": gate_metrics["high_confidence_not_observed_units"] >= 50,
        "at_least_10_dois": gate_metrics["not_observed_dois"] >= 10,
        "at_least_5_targets": gate_metrics["not_observed_targets"] >= 5,
        "enough_nonconflicting_positives": len(usable_positives) >= len(primary),
    }
    report = {
        "input_negative_records": len(evidence),
        "mapped_mentions": len(mapped_mentions),
        "mapped_unique_units": len(units),
        "unmapped_evidence_records": len(unmapped),
        "primary_not_observed": len(primary),
        "boundary_units": len(boundary),
        "positive_pool": len(positives),
        "gate_metrics": gate_metrics,
        "gate_checks": gate_checks,
        "training_gate_passed": all(gate_checks.values()),
        "condition_policy": "Conditions are retained. They are excluded from the primary classifier because comparable positive-condition coverage is absent.",
        "external_generation_requests": 0,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "mapped_mentions.json": mapped_mentions,
        "mapped_units.json": units,
        "primary_negative_units.json": primary,
        "boundary_units.json": boundary,
        "positive_pool.json": positives,
        "unmapped_evidence.json": unmapped,
        "mapping_report.json": report,
    }
    for name, value in outputs.items():
        write_json(args.out / name, value)
    pd.DataFrame([{**row, "conditions": json.dumps(row["conditions"], ensure_ascii=False)} for row in units]).to_csv(
        args.out / "mapped_units.csv", index=False
    )
    manifest = {
        "inputs": {
            str(args.evidence.resolve()): sha256(args.evidence),
            str(args.molgluedb.resolve()): sha256(args.molgluedb),
        },
        "code": {str(Path(__file__).resolve()): sha256(Path(__file__))},
        "outputs": {
            path.name: sha256(path)
            for path in sorted(args.out.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "runtime": {"rdkit": rdBase.rdkitVersion, "pandas": pd.__version__},
        "external_generation_requests": 0,
    }
    write_json(args.out / "manifest.json", manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

