"""Audit frozen local evidence against the fixed MG2Act benchmark, offline.

Run with RDKit, for example::

    uv run --no-project --with rdkit python research/2026-10-26-mg2act-audit/overlap_audit.py

No credentials, environment files, model clients, or network requests are used.
The four generated artifacts contain source pointers, never extracted quotations.

Optional --provenance PATH accepts CSV or JSON (a list, or {"entries": [...]})
with explicit links. The default is local/source_mapping/benchmark_provenance.csv
if present. Every usable entry needs source_url, mapping_evidence, or source_locator;
entries marked unresolved/ambiguous/rejected/unknown are retained only in diagnostics.
Benchmark selectors: benchmark_id (the actual CSV id), optionally split; alternatively
split + row_number (1 based data row). Neither arbitrary external database IDs nor
row order are interpreted as benchmark IDs. Fields doi/source_doi/reference_doi and
optional conditions supply provenance. Darwin's benchmark_split/benchmark_row_number
aliases are accepted. Database-only provenance_scope associations remain candidate
DOI lists, distinct from the definitive benchmark DOI. A local entry selects evidence_uid,
record_id/record_key + optional version, or paper_id/doi + exact compound; it may
supply smiles, target_uniprot, e3_uniprot, evidence_origin, granularity, conditions.
Local paper_id-only mappings are rejected. Paper compound numbers are scoped by
DOI/paper_id and never joined across papers. Conflicting mappings remain unresolved.
Conditions may be JSON or individual endpoint/assay/cell_line/treatment_time/
tested_concentration/construct/genotype/perturbation/cotreatment columns. Empty
conditions mean unknown, not an unperturbed wild-type experiment.

The inventory preserves observations and versions, including grouped statements.
Fingerprints describe possible repeated contexts; they are not experiment counts.
--provenance may be repeated. Verified database associations also derive a separate
local/source_mapping/local_identity_provenance.csv using same DOI, exact compound
name after a Compound/compd prefix, exact target name, and a unique full identity.
An explicit terminal HiBiT tag can be separated for protein identity while the
original target and construct annotations are retained; mutations are not stripped. This local
identity mapping supplies no benchmark assay provenance or experimental conditions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

try:
    from rdkit import Chem, RDLogger, rdBase
    from rdkit.Chem.MolStandardize import rdMolStandardize
except ImportError as exc:
    raise SystemExit("RDKit is required; no string-only fallback is permitted.") from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REVISION = "d3f9d1da48be93d67cfc2be074c0cf0c6bdbb065"
OLD = "research/2026-10-22-sol-extraction/batch02/continuation_2026-10-24"
NEW = "research/2026-10-25-api-extraction"
SOURCES = [
    ("frozen_2026-10-24", f"{OLD}/final_records.json", "records"),
    ("missing_evidence_final", f"{OLD}/missing_evidence_final.json", "entries"),
    *[(name, f"{NEW}/local/{name}/exports/records.json", None) for name in
      ("batch_engineering_02", "batch_quality_02", "model_probe_01", "repair_regression_01")],
    ("repair_citation_recovery", f"{NEW}/local/repair_regression_01/citation_recovery/combined_records.json", None),
]
REVIEWS = {
    "batch_engineering_02": f"{NEW}/engineering_semantic_review.json",
    "batch_quality_02": f"{NEW}/quality_semantic_review.json",
    "model_probe_01": f"{NEW}/probe_semantic_review.json",
    "repair_regression_01": f"{NEW}/local/repair_regression_01/review_snapshots/001_review.json",
    "repair_citation_recovery": f"{NEW}/local/repair_regression_01/review_snapshots/001_review.json",
}
CONDITION_FIELDS = ("endpoint", "assay", "cell_line", "treatment_time", "tested_concentration",
                    "construct", "genotype", "perturbation", "cotreatment")
NEGATIVE = {
    "no_degradation", "no_significant_degradation", "no_abundance_change_reported",
    "no_abundance_change", "degradation_resistance", "relative_weakening",
    "reduced_degradation_potency", "conditional_loss", "true_conditional_negative",
    "no_detectable_induced_polyubiquitination", "threshold_limited_no_additional_hits",
}
POSITIVE = {"nonzero_degradation", "relative_reduction"}
OUTCOMES = ("same_experiment", "same_combination_different_conditions", "same_paper_only",
            "identity_or_conditions_unresolved", "no_match_found")
UNIPROT = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?$")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def norm(value):
    return " ".join(str(value or "").split()).casefold()


def doi(value):
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", norm(value))
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


def accession(value):
    value = str(value or "").strip().upper()
    return value if UNIPROT.fullmatch(value) else ""


@lru_cache(maxsize=10000)
def structure(smiles):
    """RDKit cleanup + canonical isomeric SMILES; keep salts/charge/tautomers.

    Cleanup normalizes functional groups and metals. There is no fragment-parent,
    uncharging or tautomer collapse. Chirality is assigned before serialization.
    The second key removes stereochemistry explicitly and is candidate-only.
    """
    if not smiles:
        return "", "", "missing"
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return "", "", "invalid_smiles"
        mol = rdMolStandardize.Cleanup(mol)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        exact = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        loose = Chem.Mol(mol)
        Chem.RemoveStereochemistry(loose)
        return exact, Chem.MolToSmiles(loose, canonical=True, isomericSmiles=True), "valid"
    except Exception as exc:
        return "", "", f"rdkit_error:{type(exc).__name__}"


def conditions(fields):
    result = {key: fields.get(key) for key in CONDITION_FIELDS if fields.get(key) not in (None, "")}
    if "tested_concentration" not in result and fields.get("tested_concentration_range"):
        result["tested_concentration"] = fields["tested_concentration_range"]
    return result


def origin(record):
    explicit = record.get("result_origin", record.get("evidence_origin", ""))
    if explicit:
        return explicit, "explicit_record_field", [explicit]
    found = set()
    for item in record.get("result_evidence", record.get("evidence", [])):
        loc = norm(item.get("locator"))
        if re.match(r"(?:tbl\s*\d|table\b|table\d|supplement(?:ary|al)\s+table|表\s*\d)", loc):
            found.add("table")
        elif (re.match(r"(?:p\d|par\d|body|s\d|sec\b)", loc) or
              "paragraph" in loc or "段落" in loc or re.search(r"-sec-\d", loc)):
            found.add("body_narrative")
        elif re.match(r"(?:fig|extended data fig|supplement(?:ary|al) fig)", loc) or re.search(r"-fig-\d", loc):
            found.add("figure_caption")
        else:
            found.add("unknown")
    return (next(iter(found)) if len(found) == 1 else "mixed" if found else "unknown"), "result_locator_heuristic", sorted(found)


def grouped(compound, target, declared=""):
    if declared == "aggregate_or_unnamed_group":
        return True
    # Parenthetical synonyms and assay annotations are not compound/target groups.
    compound = re.sub(r"\([^()]*\)", "", norm(compound))
    target = re.sub(r"\([^()]*\)", "", norm(target))
    return bool(re.search(r"\b(?:analogues|analogs|compounds|proteome|proteins|informer set|derivatives)\b|\band\b|\bor\b|;|\b\d+\s*[–−]\s*\d+\b|\b\d+[a-z]?\s*[/,+&]\s*\d+[a-z]?\b",
                          compound + " " + target))


def informative_name(value):
    """Only a named-compound lead, never a confirmed molecular identity."""
    value = norm(value)
    if not value or re.fullmatch(r"(?:compound\s*)?\d+[a-z]?", value):
        return ""
    if re.match(r"(?:compound|analogue|analog|derivative)\b", value):
        return ""
    return value if not grouped(value, "") else ""


def simulated(value):
    if isinstance(value, dict):
        for key, val in value.items():
            if key.lower() in ("simulated", "simulation", "replay", "replayed", "mock", "dry_run") and val not in (False, None, "", 0):
                return True
            if key.lower() in ("transport", "mode", "execution_mode") and norm(val) in ("replay", "mock", "simulated", "simulation"):
                return True
    return False


def load_inventory():
    records, scope, review_inputs = [], [], {}
    for version, relative, container in SOURCES:
        path = REPO / relative
        if not path.exists():
            if version == "missing_evidence_final":
                scope.append({"version": version, "path": relative, "status": "absent_optional", "raw_count": 0})
                continue
            raise FileNotFoundError(path)
        data = read_json(path)
        file_sha256 = digest(path)
        rows = data[container] if container else data
        if not isinstance(rows, list):
            raise ValueError(f"Expected record list: {path}")
        manifest = path.parent.parent / "manifest.json"
        manifest_data = read_json(manifest) if manifest.exists() else {}
        paper_metadata = {p["paper_id"]: p for p in manifest_data.get("papers", [])}
        excluded, reviews = [], {}
        review_path = REPO / REVIEWS[version] if version in REVIEWS else None
        if review_path and review_path.exists():
            reviews = {r["record_key"]: (r, index) for index, r in enumerate(read_json(review_path).get("items", []))}
            review_inputs[REVIEWS[version]] = digest(review_path)
        for index, wrapper in enumerate(rows):
            if simulated(wrapper) or simulated(data) or simulated(manifest_data):
                excluded.append(index)
                continue
            raw = wrapper.get("event", wrapper)
            fields = raw.get("fields", raw)
            identifier = raw.get("record_id", raw.get("record_key", raw.get("event_id", f"row_{index + 1}")))
            uid = f"{version}:{identifier}"
            pointer = f"{relative}#/{container + '/' if container else ''}{index}"
            raw_pointer = f"{pointer}/event" if "event" in wrapper else pointer
            org, org_basis, org_components = origin(raw)
            paper_id = wrapper.get("paper_id", raw.get("paper_id", ""))
            metadata = paper_metadata.get(paper_id, {})
            claim = raw.get("claim_type", raw.get("negative_type", "uncertain"))
            review = reviews.get(identifier)
            record = {
                "evidence_uid": uid, "version": version, "original_id": identifier,
                "record_id": raw.get("record_id", ""), "record_key": raw.get("record_key", ""),
                "event_id": raw.get("event_id", ""), "paper_id": paper_id,
                "doi": doi(wrapper.get("doi", raw.get("doi"))), "compound": fields.get("compound"),
                "original_doi": wrapper.get("doi", raw.get("doi", "")),
                "target": fields.get("target"), "e3": fields.get("e3", fields.get("recruiting_protein")),
                "smiles": fields.get("smiles", fields.get("Molecule_SMILES", "")),
                "target_uniprot": accession(fields.get("target_uniprot", fields.get("PrimaryTarget_UniProtID"))),
                "e3_uniprot": accession(fields.get("e3_uniprot", fields.get("RecruitingProtein_UniProtID"))),
                "conditions": conditions(fields.get("conditions", fields)),
                "claim_type": claim, "result_origin": org, "origin_basis": org_basis,
                "result_origin_components": org_components,
                "body_narrative_result_locator_present": "body_narrative" in org_components,
                "table_result_locator_present": "table" in org_components,
                "review_status": raw.get("review_status", "not_present"),
                "semantic_review": raw.get("semantic_review", "not_present"),
                "negative_evidence_status": raw.get("negative_evidence_status", "not_present"),
                "quote_checks": raw.get("quote_checks", raw.get("mechanical_status", "not_present")),
                "supplemental_review": review[0].get("decision", "") if review else "",
                "supplemental_review_locator": f"{REVIEWS[version]}#/items/{review[1]}" if review else "",
                "expert_gold": raw.get("expert_gold", False), "ready_for_training": raw.get("ready_for_training", False),
                "source_pointer": pointer, "source_file_sha256": file_sha256,
                "source_sha256": raw.get("source_sha256", raw.get("extraction_sha256", "")),
                "source_url": raw.get("source_url", metadata.get("url", "")), "job_id": raw.get("job_id", ""),
                "source_license": metadata.get("source_license", ""),
                "granularity": wrapper.get("granularity", "not_declared"),
                "evidence_role": wrapper.get("evidence_role", "not_declared"),
                "scope_review_status": (wrapper.get("scope_review") or {}).get("status_after_scope_review", ""),
                "eligible_for_individual_core_record_proposal": wrapper.get("eligible_for_individual_core_record_proposal"),
                "possible_duplicate_context": raw.get("possible_duplicate_context", False),
                "review_version": raw.get("review_version", raw.get("revision_version", "")),
                "applied_overlays": raw.get("applied_overlays", []),
                "provenance_locators": [f"{raw_pointer}/provenance/{i}" for i, _ in enumerate(raw.get("provenance", []))],
                "result_evidence_locators": [f"{raw_pointer}/{key}/{i}" for key in ("result_evidence", "evidence") for i, _ in enumerate(raw.get(key, []))],
                "mapping_conflicts": [], "mapping_locators": [],
            }
            if "endpoint" not in record["conditions"] and fields.get("endpoint"):
                record["conditions"]["endpoint"] = fields["endpoint"]
            record["grouped_statement"] = grouped(record["compound"], record["target"], record["granularity"])
            records.append(record)
        scope.append({"version": version, "path": relative, "sha256": file_sha256, "status": "loaded",
                      "raw_count": len(rows), "included_count": len(rows) - len(excluded),
                      "excluded_simulation_replay_count": len(excluded), "excluded_row_indices": excluded})
    return records, scope, review_inputs


def load_benchmark(directory, manifest_path):
    manifest = read_json(manifest_path)
    if manifest.get("revision") != REVISION:
        raise ValueError("Benchmark manifest revision does not match the fixed audit revision")
    hashes = {r["path"]: r["sha256"] for r in manifest["files"]}
    rows, inputs = [], []
    for split in ("train", "val", "test"):
        path = directory / f"{split}.csv"
        sha = digest(path)
        if hashes.get(f"MG_data/{split}.csv") != sha:
            raise ValueError(f"Benchmark file hash differs from pinned manifest: {path}")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            source = list(csv.DictReader(stream))
        for index, raw in enumerate(source, 1):
            exact, loose, status = structure(raw["Molecule_SMILES"])
            rows.append({"benchmark_uid": f"{split}:{index}:{raw['id']}", "split": split,
                         "row_number": index, "benchmark_id": raw["id"], "name": raw["Name"],
                         "target_name": raw["PrimaryTarget"], "e3_name": raw["RecruitingProtein"],
                         "target_uniprot": accession(raw["PrimaryTarget_UniProtID"]),
                         "e3_uniprot": accession(raw["RecruitingProtein_UniProtID"]),
                         "canonical_isomeric_smiles": exact, "canonical_no_stereo_smiles": loose,
                         "structure_status": status, "doi": doi(raw.get("doi")), "conditions": {},
                         "activity": raw.get("activity"), "Score": raw.get("Score"),
                         "target_sequence_sha256": hashlib.sha256(raw["Target_seq"].encode()).hexdigest(),
                         "e3_sequence_sha256": hashlib.sha256(raw["E3_seq"].encode()).hexdigest(),
                         "benchmark_csv_sha256": sha, "source_associations": [],
                         "mapping_locators": [], "mapping_conflicts": []})
        inputs.append({"split": split, "path": str(path), "sha256": sha, "rows": len(source)})
    return rows, inputs


def apply_mapping(path, inventory, benchmark):
    if path is None:
        return {"status": "absent", "entries": 0, "applied_entries": 0}
    # Parse and hash the same immutable byte snapshot while the producer may run.
    payload = path.read_bytes()
    snapshot_sha256 = hashlib.sha256(payload).hexdigest()
    if path.suffix.casefold() == ".csv":
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline="")))
    else:
        data = json.loads(payload.decode("utf-8-sig"))
        rows = data if isinstance(data, list) else data["entries"]
    log, applied = [], 0
    for index, row in enumerate(rows):
        row = dict(row)
        row["split"] = row.get("split") or row.get("benchmark_split", "")
        row["row_number"] = row.get("row_number") or row.get("benchmark_row_number", "")
        locator = f"{path}#/{'csv_data_rows' if path.suffix.casefold() == '.csv' else 'entries'}/{index}"
        status = norm(row.get("mapping_status", row.get("status")))
        association_only = row.get("provenance_scope") == "database_source_association_not_confirmed_benchmark_assay"
        if (status.startswith(("unresolved", "ambiguous", "rejected", "unknown", "not_found", "candidate")) or
                (association_only and not status.startswith("verified_structure_target_e3_")) or
                not any(row.get(key) for key in ("source_url", "mapping_evidence", "source_locator", "mapping_basis"))):
            log.append({"index": index, "status": "unusable_status_or_missing_source"})
            continue
        is_benchmark = bool(str(row.get("benchmark_id", "")).strip() or (row.get("split") and row.get("row_number")))
        if is_benchmark:
            selected = [b for b in benchmark if
                        (not row.get("split") or row["split"] == b["split"]) and
                        (not str(row.get("benchmark_id", "")).strip() or str(row["benchmark_id"]).strip() == b["benchmark_id"]) and
                        (not row.get("row_number") or str(row["row_number"]) == str(b["row_number"]))]
        elif row.get("evidence_uid"):
            selected = [r for r in inventory if r["evidence_uid"] == row["evidence_uid"]]
        elif row.get("record_id") or row.get("record_key"):
            key = "record_id" if row.get("record_id") else "record_key"
            selected = [r for r in inventory if r[key] == row[key] and (not row.get("version") or r["version"] == row["version"])]
        elif (row.get("paper_id") or row.get("doi")) and row.get("compound"):
            selected = [r for r in inventory if norm(r["compound"]) == norm(row["compound"]) and
                        (not row.get("paper_id") or r["paper_id"] == row["paper_id"]) and
                        (not row.get("doi") or r["doi"] == doi(row["doi"]))]
        else:
            selected = []
        if not selected:
            log.append({"index": index, "status": "no_explicit_selector_match"})
            continue
        if is_benchmark and any(
                (row.get("benchmark_revision") and row["benchmark_revision"] != REVISION) or
                (row.get("benchmark_csv_sha256") and row["benchmark_csv_sha256"] != b["benchmark_csv_sha256"]) or
                (row.get("benchmark_structure") and structure(row["benchmark_structure"])[0] != b["canonical_isomeric_smiles"]) or
                (row.get("benchmark_target_uniprot") and accession(row["benchmark_target_uniprot"]) != b["target_uniprot"]) or
                (row.get("benchmark_e3_uniprot") and accession(row["benchmark_e3_uniprot"]) != b["e3_uniprot"])
                or (association_only and row.get("source_structure") and structure(row["source_structure"])[0] != b["canonical_isomeric_smiles"])
                for b in selected):
            log.append({"index": index, "status": "benchmark_snapshot_or_identity_mismatch"})
            continue
        if association_only:
            source_doi = doi(row.get("source_doi"))
            for target in selected:
                target["source_associations"].append({"doi": source_doi, "mapping_status": status,
                    "provenance_scope": row["provenance_scope"], "source_name": row.get("compound_original_name", ""),
                    "source_row_sha256": row.get("source_row_sha256", ""),
                    "source_url": row.get("source_url", ""),
                    "source_locator": locator})
                target["mapping_locators"].append(locator)
            applied += 1
            log.append({"index": index, "status": "source_association_only", "matched_observations": len(selected)})
            continue
        values = {"doi": doi(row.get("source_doi") or row.get("reference_doi") or row.get("doi"))}
        if not is_benchmark:
            values.update({"smiles": row.get("smiles", row.get("Molecule_SMILES", "")),
                           "target_uniprot": accession(row.get("target_uniprot", row.get("PrimaryTarget_UniProtID"))),
                           "e3_uniprot": accession(row.get("e3_uniprot", row.get("RecruitingProtein_UniProtID"))),
                           "result_origin": row.get("evidence_origin", ""), "granularity": row.get("granularity", ""),
                           "identity_mapping_basis": row.get("mapping_basis", ""),
                           "identity_target_tag_annotation": row.get("target_tag_annotation", "")})
        raw_conditions = row.get("conditions", {})
        extra = json.loads(raw_conditions) if isinstance(raw_conditions, str) and raw_conditions.strip() else raw_conditions or {}
        if not isinstance(extra, dict):
            raise ValueError(f"conditions must be an object: {locator}")
        extra = {**conditions(row), **extra}
        for target in selected:
            for key, value in values.items():
                if not value:
                    continue
                existing = target.get(key)
                if existing and norm(existing) != norm(value) and existing not in ("unknown", "not_declared"):
                    target["mapping_conflicts"].append(key)
                else:
                    target[key] = value
            for key, value in extra.items():
                if key not in CONDITION_FIELDS or value in (None, ""):
                    continue
                if key in target["conditions"] and norm(target["conditions"][key]) != norm(value):
                    target["mapping_conflicts"].append(f"conditions.{key}")
                else:
                    target["conditions"][key] = value
            target["mapping_locators"].append(locator)
        applied += 1
        log.append({"index": index, "status": "applied", "matched_observations": len(selected), "kind": "benchmark" if is_benchmark else "local"})
    return {"status": "loaded", "path": str(path), "sha256": snapshot_sha256, "entries": len(rows),
            "applied_entries": applied, "entry_log": log}


def compound_name(value):
    return re.sub(r"^(?:compound|compd)\.?\s+", "", norm(value))


def protein_name(value):
    value = norm(value)
    base = re.sub(r"(?:[-‐‑–]\s*hibit|\s*\(hibit\))$", "", value).strip()
    return base, "terminal HiBiT tag; original target/construct retained" if base != value else ""


def derive_local_identities(path, inventory, benchmark, mapping_runs):
    """Create an independent, source-backed identity overlay, without expanding rows."""
    index, output, decisions = defaultdict(list), [], Counter()
    parent_hashes = {run["path"]: run["sha256"] for run in mapping_runs if run.get("path")}
    for b in benchmark:
        for association in b["source_associations"]:
            if association["doi"] and association["source_name"] and combination(b):
                index[(association["doi"], compound_name(association["source_name"]), norm(b["target_name"]))].append((b, association))
    for record in inventory:
        compound = compound_name(record["compound"])
        if record["grouped_statement"]:
            decisions["group_preserved_without_identity_assignment"] += 1
            continue
        if not record["doi"] or not compound or not record["target"]:
            decisions["missing_local_doi_name_or_target"] += 1
            continue
        protein, tag_annotation = protein_name(record["target"])
        candidates = index.get((record["doi"], compound, protein), [])
        if not candidates:
            decisions["no_same_doi_compound_target_name_match"] += 1
            continue
        identities = {combination(b) for b, _ in candidates}
        base = {"evidence_uid": record["evidence_uid"], "version": record["version"],
                "original_id": record["original_id"], "paper_id": record["paper_id"], "doi": record["doi"],
                "compound": record["compound"], "target": record["target"], "normalized_compound": compound,
                "protein_name_for_identity": protein, "target_tag_annotation": tag_annotation,
                "local_source_pointer": record["source_pointer"], "local_source_file_sha256": record["source_file_sha256"],
                "parent_mapping_sha256": parent_hashes,
                "source_locator": [a["source_locator"] for _, a in candidates],
                "source_row_sha256": sorted({a["source_row_sha256"] for _, a in candidates if a["source_row_sha256"]}),
                "source_doi": record["doi"], "source_names": sorted({a["source_name"] for _, a in candidates}),
                "associated_benchmark_uids": sorted({b["benchmark_uid"] for b, _ in candidates}),
                "candidate_identity_count": len(identities),
                "provenance_scope": "local_identity_only_not_benchmark_assay_provenance"}
        if len(identities) != 1:
            decisions["conflicting_identities_same_doi_name_target"] += 1
            output.append({**base, "mapping_status": "unresolved_conflicting_local_identity", "mapping_basis": "Same scoped names resolve to different structures/accessions; no identity assigned."})
            continue
        exact, target_id, e3_id = next(iter(identities))
        decisions["unique_identity_mapped"] += 1
        output.append({**base, "mapping_status": "verified_same_doi_compound_target_unique_identity",
                       "smiles": exact, "target_uniprot": target_id, "e3_uniprot": e3_id,
                       "mapping_basis": "Same local DOI and database source DOI; exact compound_original_name after Compound/compd prefix removal; exact local protein and benchmark target name after explicit terminal HiBiT tag separation only; unique isomeric structure + target/E3 accessions. Original target/construct preserved. Identity only; no experiment/condition transfer."})
    path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(path, output, ["evidence_uid", "mapping_status", "source_locator"])
    return {"path": str(path), "sha256": digest(path), "observations_considered": len(inventory),
            "decisions": dict(decisions), "output_entries": len(output),
            "unique_mapped_combinations_not_experiments": len({(r["smiles"], r["target_uniprot"], r["e3_uniprot"]) for r in output if r.get("smiles")})}


def label_inventory(records):
    identity_groups, context_groups = defaultdict(list), defaultdict(list)
    for r in records:
        exact, loose, status = structure(r["smiles"])
        r.update(canonical_isomeric_smiles=exact, canonical_no_stereo_smiles=loose, structure_status=status)
        r["grouped_statement"] = grouped(r["compound"], r["target"], r["granularity"])
        claim, review = r["claim_type"], norm(r["supplemental_review"])
        excluded = (r["negative_evidence_status"] in ("excluded_pending_review", "not_eligible_as_negative") or
                    "quarantine" in review or review in ("uncertain", "boundary_only") or
                    r["review_status"] in ("uncertain", "needs_correction"))
        polarity = "uncertain" if excluded else "negative" if claim in NEGATIVE else "positive" if claim in POSITIVE else "uncertain" if claim in ("uncertain", "reported_zero", "target_not_detected", "below_detection") else "other"
        r["polarity"] = polarity
        r["evidence_class"] = f"{r['result_origin']}_negative" if polarity == "negative" else polarity
        r["classification_basis"] = "existing_claim_type_with_review_gate; not_new_scientific_adjudication"
        r["identity_complete"] = bool(exact and r["target_uniprot"] and r["e3_uniprot"] and not r["grouped_statement"] and not r["mapping_conflicts"])
        identity_groups[(r["paper_id"], r["original_id"])].append(r)
        context = (r["doi"] or r["paper_id"], norm(r["compound"]), norm(r["target"]), packed(r["conditions"]))
        fingerprint = hashlib.sha256(packed(context).encode()).hexdigest()[:20]
        r["context_fingerprint"] = fingerprint
        context_groups[fingerprint].append(r)
    for group in identity_groups.values():
        for r in group:
            r["same_original_id_occurrences"] = len(group)
    for group in context_groups.values():
        for r in group:
            r["same_context_signature_occurrences"] = len(group)


def class_counts(records):
    counts = Counter(r["evidence_class"] for r in records)
    return {key: counts[key] for key in ("body_narrative_negative", "table_negative", "figure_caption_negative",
                                       "mixed_negative", "unknown_negative", "positive", "other", "uncertain")}


def combination(row, loose=False):
    molecule = row["canonical_no_stereo_smiles" if loose else "canonical_isomeric_smiles"]
    if not (molecule and row["target_uniprot"] and row["e3_uniprot"]):
        return None
    # The release gives WT IKZF3 and IKZF3-Q147E the same UniProt accession.
    # Preserve explicit substitutions rather than counting them as duplicate targets.
    context = row.get("conditions", {})
    target_label = str(row.get("target_name") or row.get("target") or "")
    target_label += " " + str(context.get("construct", "")) + " " + str(context.get("genotype", ""))
    e3_label = str(row.get("e3_name") or row.get("e3") or "")
    substitutions = lambda value: tuple(sorted(set(re.findall(r"([A-Z]\d{1,5}[A-Z])(?=$|[^A-Z0-9])", value.upper()))))
    return (molecule, row["target_uniprot"], row["e3_uniprot"], substitutions(target_label), substitutions(e3_label))


def split_overlaps(benchmark):
    output = []
    for left_split, right_split in itertools.combinations(("train", "val", "test"), 2):
        left = [r for r in benchmark if r["split"] == left_split]
        right = [r for r in benchmark if r["split"] == right_split]
        for level in ("molecule", "molecule_target_e3"):
            def key(row, loose):
                if level.endswith("e3"):
                    base = combination(row, loose)
                    return base + (row["target_sequence_sha256"], row["e3_sequence_sha256"]) if base else None
                return row["canonical_no_stereo_smiles" if loose else "canonical_isomeric_smiles"] or None
            exact_pairs = {(a["benchmark_uid"], b["benchmark_uid"]) for a in left for b in right if key(a, False) and key(a, False) == key(b, False)}
            for mode in ("exact_isomeric", "no_stereo_candidate"):
                loose = mode == "no_stereo_candidate"
                li, ri = defaultdict(list), defaultdict(list)
                for row in left:
                    if key(row, loose): li[key(row, loose)].append(row)
                for row in right:
                    if key(row, loose): ri[key(row, loose)].append(row)
                for shared in sorted(li.keys() & ri.keys(), key=str):
                    pairs = [(a, b) for a in li[shared] for b in ri[shared] if not loose or (a["benchmark_uid"], b["benchmark_uid"]) not in exact_pairs]
                    if not pairs:
                        continue
                    arows = {a["benchmark_uid"]: a for a, _ in pairs}
                    brows = {b["benchmark_uid"]: b for _, b in pairs}
                    output.append({"left_split": left_split, "right_split": right_split, "level": level,
                                   "match_mode": mode, "shared_key": packed(shared),
                                   "left_rows": len(arows), "right_rows": len(brows), "row_pairs": len(pairs),
                                   "left_benchmark_uids": sorted(arows), "right_benchmark_uids": sorted(brows),
                                   "left_ids": sorted({r["benchmark_id"] for r in arows.values()}),
                                   "right_ids": sorted({r["benchmark_id"] for r in brows.values()}),
                                   "meaning": "same_standardized_identity" if not loose else "stereochemistry_removed_only; identity_requires_review"})
    return output


def condition_relation(local, bench):
    a, b = local["conditions"], bench["conditions"]
    differing = [key for key in CONDITION_FIELDS if a.get(key) and b.get(key) and norm(a[key]) != norm(b[key])]
    required = ("endpoint", "assay", "cell_line", "treatment_time", "tested_concentration", "construct", "genotype", "perturbation", "cotreatment")
    complete = all(a.get(key) and b.get(key) for key in required)
    return differing, complete


def match_records(inventory, benchmark):
    indices = {key: defaultdict(set) for key in ("doi", "associated_source_paper", "molecule", "loose", "name")}
    for i, b in enumerate(benchmark):
        for field, value in (("doi", b["doi"]), ("molecule", b["canonical_isomeric_smiles"]),
                             ("loose", b["canonical_no_stereo_smiles"]), ("name", informative_name(b["name"]))):
            if value: indices[field][value].add(i)
        for association in b["source_associations"]:
            if association["doi"]:
                indices["associated_source_paper"][association["doi"]].add(i)
    output = []
    for r in inventory:
        reasons = defaultdict(set)
        for field, value in (("doi", r["doi"]), ("associated_source_paper", r["doi"]), ("molecule", r["canonical_isomeric_smiles"]),
                             ("loose", r["canonical_no_stereo_smiles"]), ("name", informative_name(r["compound"]))):
            if value:
                for index in indices[field].get(value, ()):
                    reasons[index].add(field)
        if not reasons:
            complete = r["identity_complete"] and all(combination(b) for b in benchmark)
            outcome = "no_match_found" if complete else "identity_or_conditions_unresolved"
            output.append({"evidence_uid": r["evidence_uid"], "benchmark_uid": "", "split": "", "benchmark_id": "",
                           "outcome": outcome, "match_basis": [], "reason": "No standardized molecular identity match in the enumerated benchmark." if complete else "No admissible match lead; local molecular structure/target/E3 identity or grouped identity is unresolved. Numeric compound labels were not joined across papers.",
                           "source_pointer": r["source_pointer"], "different_condition_fields": []})
            continue
        for index, basis in sorted(reasons.items()):
            b = benchmark[index]
            exact_combo = bool(combination(r) and combination(r) == combination(b) and r["identity_complete"])
            same_paper = bool(r["doi"] and r["doi"] == b["doi"])
            associated_paper = "associated_source_paper" in basis
            diff, complete = condition_relation(r, b)
            if r["mapping_conflicts"] or b["mapping_conflicts"]:
                outcome, reason = "identity_or_conditions_unresolved", "Conflicting provenance/identity/condition mapping requires adjudication."
            elif exact_combo and same_paper and complete and not diff:
                outcome, reason = "same_experiment", "Same DOI, explicit isomeric structure and target/E3 accessions, and complete explicit matching condition fields."
            elif exact_combo and b["doi"] and diff:
                outcome, reason = "same_combination_different_conditions", "Explicit isomeric structure and target/E3 match; sourced condition fields differ."
            elif exact_combo:
                outcome, reason = "identity_or_conditions_unresolved", "Explicit isomeric structure and target/E3 match; experiment provenance or conditions remain incomplete."
            elif same_paper:
                outcome, reason = "same_paper_only", "Same DOI; molecular/target/E3 or grouped identity does not establish the same experiment."
            elif associated_paper:
                outcome, reason = "same_paper_only", "Local DOI occurs among verified database source associations for the benchmark structure/target/E3. The benchmark's original assay source remains unresolved; source names and targets are candidate identity leads only."
            else:
                outcome = "identity_or_conditions_unresolved"
                reason = "Named-compound lead only; aliases do not establish chemical identity, target/E3 or experimental context."
                if "molecule" in basis:
                    reason = "Standardized isomeric molecule matches; target/E3 and experimental provenance/conditions require resolution."
                elif "loose" in basis:
                    reason = "Only the stereochemistry-removed molecule matches; stereochemical identity requires resolution."
            if not b["doi"]:
                reason += " Benchmark DOI/source-paper mapping is absent."
            output.append({"evidence_uid": r["evidence_uid"], "benchmark_uid": b["benchmark_uid"],
                           "split": b["split"], "benchmark_id": b["benchmark_id"], "outcome": outcome,
                           "match_basis": sorted(basis), "exact_combination_match": exact_combo,
                           "benchmark_doi": b["doi"], "benchmark_mapping_locators": b["mapping_locators"],
                           "benchmark_candidate_source_dois": sorted({a["doi"] for a in b["source_associations"] if a["doi"]}),
                           "benchmark_association_scope": sorted({a["provenance_scope"] for a in b["source_associations"]}),
                           "reason": reason, "different_condition_fields": diff, "source_pointer": r["source_pointer"]})
    return output


def write_csv(path, rows, empty_fields):
    fields = list(dict.fromkeys(key for row in rows for key in row)) or empty_fields
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: packed(value) if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark-dir", type=Path, default=HERE / "local/upstream/MG_data")
    parser.add_argument("--manifest", type=Path, default=HERE / "source_manifest.json")
    parser.add_argument("--provenance", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    RDLogger.DisableLog("rdApp.warning")
    records, scope, reviews = load_inventory()
    benchmark, benchmark_inputs = load_benchmark(args.benchmark_dir, args.manifest)
    public_mapping = HERE / "source_associations.csv"
    default_mapping = public_mapping if public_mapping.exists() else HERE / "local/source_mapping/benchmark_provenance.csv"
    mapping_paths = [path.resolve() for path in (args.provenance or ([default_mapping] if default_mapping.exists() else []))]
    if public_mapping.resolve() in mapping_paths:
        expected_mapping = read_json(HERE / "mapping_manifest.json")["published_sha256"]
        if digest(public_mapping) != expected_mapping:
            raise ValueError("Frozen public identity/source associations changed")
    mapping_runs = [apply_mapping(path, records, benchmark) for path in mapping_paths]
    local_identity_path = HERE / "local/source_mapping/local_identity_provenance.csv"
    if (any(b["source_associations"] for b in benchmark) and local_identity_path not in mapping_paths
            and not any(r.get("identity_mapping_basis") for r in records)):
        derivation = derive_local_identities(local_identity_path, records, benchmark, mapping_runs)
        mapping_runs.append(apply_mapping(local_identity_path, records, benchmark))
    else:
        derivation = {"status": "not_derived; explicit_overlay_or_no_database_associations"}
    mapping = dict(mapping_runs[0]) if mapping_runs else apply_mapping(None, records, benchmark)
    mapping["additional_mappings"] = mapping_runs[1:]
    mapping["local_identity_derivation"] = derivation
    # Success rows are already preserved in the source-association table.
    # Keep summary counts and exceptional mapping entries instead of repeating every success.
    for run in [mapping, *mapping["additional_mappings"]]:
        entries = run.pop("entry_log", [])
        run["entry_status_counts"] = dict(Counter(r["status"] for r in entries))
        run["exceptional_entries"] = [r for r in entries if r["status"] not in ("applied", "source_association_only")]
    label_inventory(records)
    split_rows = split_overlaps(benchmark)
    matches = match_records(records, benchmark)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "evidence_inventory.csv", records, ["evidence_uid"])
    write_csv(args.output_dir / "overlap_audit.csv", matches, ["evidence_uid", "outcome"])
    write_csv(args.output_dir / "split_overlap.csv", split_rows, ["left_split", "right_split", "level", "match_mode", "row_pairs"])
    outcome_sets = {key: {m["evidence_uid"] for m in matches if m["outcome"] == key} for key in OUTCOMES}
    priority = list(OUTCOMES)
    best = Counter(next(key for key in priority if r["evidence_uid"] in outcome_sets[key]) for r in records)
    split_summary = []
    for left, right in itertools.combinations(("train", "val", "test"), 2):
        for level in ("molecule", "molecule_target_e3"):
            for mode in ("exact_isomeric", "no_stereo_candidate"):
                subset = [r for r in split_rows if (r["left_split"], r["right_split"], r["level"], r["match_mode"]) == (left, right, level, mode)]
                split_summary.append({"left_split": left, "right_split": right, "level": level, "match_mode": mode,
                                      "shared_keys": len(subset), "row_pairs": sum(r["row_pairs"] for r in subset),
                                      "left_rows": len({uid for r in subset for uid in r["left_benchmark_uids"]}),
                                      "right_rows": len({uid for r in subset for uid in r["right_benchmark_uids"]})})
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "script_sha256": digest(Path(__file__)),
        "benchmark_revision": REVISION, "rdkit_version": rdBase.rdkitVersion,
        "normalization": "RDKit Cleanup; canonical isomeric SMILES; retain fragments/charge/tautomers. Separate RemoveStereochemistry candidate key. UniProt accessions plus explicit substitution annotations; split comparisons also require target/E3 sequence hashes. WT and IKZF3-Q147E remain distinct despite shared accession.",
        "research_question": "Evidence identity and provenance overlap relevant to reliability and independent use evaluation.",
        "inventory_scope": scope, "review_inputs": reviews, "provenance_mapping": mapping,
        "inventory": {"observations_including_versions": len(records), "papers": len({r['paper_id'] for r in records}),
                      "doi_count": len({r['doi'] for r in records if r['doi']}),
                      "evidence_classes": class_counts(records),
                      "negative_with_body_narrative_locator_including_mixed": sum(r["polarity"] == "negative" and r["body_narrative_result_locator_present"] for r in records),
                      "negative_with_table_locator_including_mixed": sum(r["polarity"] == "negative" and r["table_result_locator_present"] for r in records),
                      "review_status": dict(Counter(r["review_status"] for r in records)),
                      "supplemental_review": dict(Counter(r["supplemental_review"] or "not_present" for r in records)),
                      "negative_evidence_status": dict(Counter(r["negative_evidence_status"] for r in records)),
                      "grouped_statements": sum(r["grouped_statement"] for r in records),
                      "complete_explicit_identities": sum(r["identity_complete"] for r in records),
                      "valid_smiles": sum(r["structure_status"] == "valid" for r in records),
                      "target_uniprot_known": sum(bool(r["target_uniprot"]) for r in records),
                      "e3_uniprot_known": sum(bool(r["e3_uniprot"]) for r in records),
                      "unique_original_id_keys": len({(r["paper_id"], r["original_id"]) for r in records}),
                      "context_signatures_not_experiments": len({r["context_fingerprint"] for r in records}),
                      "independent_experiment_count": None,
                      "by_version": {v: {"observations": sum(r["version"] == v for r in records),
                                          "evidence_classes": class_counts([r for r in records if r["version"] == v])} for v, _, _ in SOURCES}},
        "benchmark": {"inputs": benchmark_inputs, "rows": len(benchmark),
                      "splits": dict(Counter(r["split"] for r in benchmark)),
                      "valid_smiles": sum(r["structure_status"] == "valid" for r in benchmark),
                      "structure_statuses": dict(Counter(r["structure_status"] for r in benchmark)),
                      "unique_target_names": len({r["target_name"] for r in benchmark}),
                      "unique_target_uniprot": len({r["target_uniprot"] for r in benchmark if r["target_uniprot"]}),
                      "unique_e3_uniprot": sorted({r["e3_uniprot"] for r in benchmark}),
                      "rows_with_doi": sum(bool(r["doi"]) for r in benchmark),
                      "rows_without_doi": sum(not r["doi"] for r in benchmark),
                      "rows_with_database_source_associations": sum(bool(r["source_associations"]) for r in benchmark),
                      "rows_with_candidate_source_dois": sum(any(a["doi"] for a in r["source_associations"]) for r in benchmark),
                      "rows_with_multiple_candidate_source_dois": sum(len({a["doi"] for a in r["source_associations"] if a["doi"]}) > 1 for r in benchmark),
                      "unique_isomeric_molecules": len({r["canonical_isomeric_smiles"] for r in benchmark if r["canonical_isomeric_smiles"]}),
                      "unique_exact_combinations": len({combination(r) for r in benchmark if combination(r)}),
                      "id_duplicates": {key: n for key, n in Counter(r["benchmark_id"] for r in benchmark).items() if n > 1}},
        "split_overlap": split_summary,
        "local_overlap": {"audit_rows": len(matches), "outcome_audit_rows": dict(Counter(m["outcome"] for m in matches)),
                          "best_outcome_observations": {key: best[key] for key in OUTCOMES},
                          "confirmed_same_experiment_observations": best["same_experiment"],
                          "confirmed_exact_combination_observations": len({m["evidence_uid"] for m in matches if m.get("exact_combination_match")}),
                          "confirmed_exact_combination_row_pairs": sum(bool(m.get("exact_combination_match")) for m in matches),
                          "unresolved_experiment_overlap_observations": len(records) - best["same_experiment"] - best["no_match_found"],
                          "observations_with_any_benchmark_lead": len({m["evidence_uid"] for m in matches if m["benchmark_uid"]}),
                          "candidate_benchmark_rows": len({m["benchmark_uid"] for m in matches if m["benchmark_uid"]}),
                          "confirmed_nonoverlapping_independent_experiments": None},
        "interpretation": [
            "All scoped observations and versions are enumerated; grouped statements remain single observations.",
            "Existing labels/reviews are retained; classification is a conservative inventory rule, not expert adjudication.",
            "Frozen negative_evidence_status preserves the original 311 model-supported scoped claims independently of origin/type classification.",
            "Only actual input records are included; planned candidates are absent from this inventory.",
            "No DOI, identity, condition or absence of a match is imputed from missing information.",
            "Database source associations remain candidate DOI lists; they never populate definitive benchmark DOI or establish assay provenance. same_paper_only includes an explicitly scoped associated-source-paper lead.",
            "Local identities are a separate overlay based on same DOI, scoped compound name and exact target name with a unique full identity. Target tags, original evidence/reviews and grouped observations are preserved; no condition transfer is performed.",
            "No-stereo overlap rows contain only additional row pairs excluded from exact-isomeric pairs; shared-key counts are not independent experiments.",
            "Numeric compound labels are never cross-paper match keys; named-compound leads require identity/source confirmation.",
            "Same-experiment matching requires sourced DOI, explicit chemical/protein identities and complete matching conditions, including explicitly stated perturbation/control state.",
            "No quotations or result-text strings are exported; source JSON pointers provide traceability.",
        ],
    }
    (args.output_dir / "overlap_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"inventory_observations": len(records), "benchmark_rows": len(benchmark), "rdkit_version": rdBase.rdkitVersion,
                      "best_outcomes": summary["local_overlap"]["best_outcome_observations"], "output_dir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
