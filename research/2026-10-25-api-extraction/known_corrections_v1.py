"""Build the first append-only correction ledger for the Codex extraction run."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import curation_overlay


EST1036_EVIDENCE_ID = "E_REC_bdbebdfb7c97513258df"
EST1036_DOI = "10.1021/acscentsci.2c01317"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable_id(prefix: str, value) -> str:
    return prefix + hashlib.sha256(curation_overlay.canonical_bytes(value)).hexdigest()[:20]


def _baseline_records(run: Path) -> list[dict]:
    rows = []
    for name in ("reliable_evidence.json", "pending_review.json", "excluded_records.json"):
        rows.extend(_read(run / "exports" / name))
    return rows


def _condition_patch(record: dict, **values) -> dict:
    conditions = copy.deepcopy(record.get("conditions") or {"items": []})
    if not conditions.get("items"):
        conditions["items"] = [{"record_id": curation_overlay.record_id(record),
                                "values": {}, "evidence": {}}]
    current = conditions["items"][0].setdefault("values", {})
    current.update(values)
    return conditions


def _facts_patch(record: dict, **values) -> dict:
    facts = copy.deepcopy(record.get("facts") or {})
    observations = facts.setdefault("observations", [])
    if not observations:
        observations.append({"values": {}, "evidence": {}})
    observations[0].setdefault("values", {}).update(values)
    return facts


def _patch(record: dict, revision_id: str, changes: dict, reason: str) -> dict:
    return {
        "revision_id": revision_id,
        "operation": "patch_record",
        "record_id": curation_overlay.record_id(record),
        "paper_id": record["paper_id"],
        "source_sha256": record["source_sha256"],
        "before_sha256": curation_overlay.sha256_json(record),
        "changes": changes,
        "reason": reason,
        "curator": "codex-main-v1",
        "expert_gold": False,
    }


def est1036_entry(document: dict, sentences: list[dict], task_id: str) -> dict:
    body = next(row for row in sentences if "EST1036" in row.get("text", ""))
    caption_unit = next(
        unit for unit in document["units"]
        if "EST1036 does not degrade CDK4" in unit.get("text", "")
    )
    caption = caption_unit["text"]
    start = caption.index("(g) Structure of EST1036")
    marker = "Blots shown in (b,e,h) are representative of n = 3 biologically independent replicates/group."
    end = caption.index(marker) + len(marker)
    caption_quote = caption[start:end]
    identity = {
        "paper_id": "B235",
        "source_sha256": document["source_sha256"],
        "subject": "EST1036",
        "target": "CDK4",
        "endpoint": "protein degradation",
        "cell_line": "C33A",
        "dose": "5 μM",
        "time": "24 h",
    }
    evidence_id = _stable_id("E_REC_", identity)
    experiment_id = _stable_id("X_", identity)
    record = {
        "evidence_id": evidence_id,
        "record_id": evidence_id,
        "paper_id": "B235",
        "doi": EST1036_DOI,
        "task_id": task_id,
        "source_sha256": document["source_sha256"],
        "generation_method": "manual_recovery_from_frozen_source",
        "model": None,
        "expert_gold": False,
        "final_status": "pending_review",
        "scope_class": "molecular_glue_degradation_negative",
        "evidence_origin": "primary_report",
        "experiment_id": experiment_id,
        "facts": {
            "status": "observations",
            "reason": None,
            "observations": [{
                "values": {
                    "subject": "EST1036",
                    "target": "CDK4",
                    "endpoint": "protein degradation",
                    "observation": "did not induce degradation of CDK4",
                    "comparator": "DMSO vehicle and EST1027 context",
                    "scope_condition": "C33A cells; 5 μM; 24 h; Western blot; n=3 biological replicates",
                },
                "outcome_type": "not_observed",
                "evidence": {},
            }],
        },
        "conditions": {
            "items": [{
                "record_id": evidence_id,
                "values": {
                    "cell_line": "C33A cells",
                    "treatment_time": "24 h",
                    "tested_concentration": "5 μM",
                    "assay": "Western blotting with vinculin loading control",
                    "perturbation": "EST1036",
                    "endpoint_resolution": "CDK4 protein degradation",
                    "replicates": "n=3 biologically independent replicates/group",
                },
                "evidence": {},
            }],
        },
        "evidence_spans": [
            {
                "mention_id": _stable_id("M_", [evidence_id, body["sentence_id"]]),
                "unit_id": body["unit_id"],
                "sentence_ids": [body["sentence_id"]],
                "char_start": body["char_start"],
                "char_end": body["char_end"],
                "quote": body["text"],
                "kind": body["kind"],
                "locator": body["locator"],
            },
            {
                "mention_id": _stable_id("M_", [evidence_id, caption_unit["unit_id"], start, end]),
                "unit_id": caption_unit["unit_id"],
                "sentence_ids": [],
                "char_start": start,
                "char_end": end,
                "quote": caption_quote,
                "kind": "figure_caption",
                "locator": caption_unit["locator"],
            },
        ],
        "model_eligibility": {"training": False, "rag": False,
                              "reason": "requires_two_independent_reviews"},
    }
    return {
        "revision_id": "REV-B235-EST1036-RECOVERY-v1",
        "operation": "add_record",
        "record_id": evidence_id,
        "paper_id": "B235",
        "source_sha256": document["source_sha256"],
        "record": record,
        "reason": "Explicit body negative was missed; figure caption supplies assay conditions and replicate count.",
        "curator": "codex-main-v1",
        "expert_gold": False,
    }


def est1036_doi_repair_entry(record: dict) -> dict | None:
    """Create the append-only repair needed by ledgers made before the DOI fix."""

    if curation_overlay.record_id(record) != EST1036_EVIDENCE_ID:
        raise ValueError("Unexpected EST1036 record identity")
    if record.get("paper_id") != "B235":
        raise ValueError("EST1036 DOI repair may only target B235")
    if record.get("doi") == EST1036_DOI:
        return None
    return _patch(
        record,
        "REV-B235-EST1036-DOI-FIX-v1",
        {"doi": EST1036_DOI},
        "Correct DOI to the frozen B235 inventory identity; the prior add-record entry copied B209's DOI.",
    )


def b236_entries(records: list[dict]) -> list[dict]:
    by_id = {curation_overlay.record_id(row): row for row in records if row.get("paper_id") == "B236"}
    expected = {
        "R_272304b6b54bd7a5d577", "R_3214e0ba39e9843ee918",
        "R_3e916556de9c190f58c3", "R_a00525b030f97dc1d71f",
        "R_edd8612899b4eec04120", "R_3c0fd648c0868c8c6ead",
        "R_5f330b7a4a2a6793b131",
    }
    if set(by_id) != expected:
        raise ValueError(f"Unexpected B236 IDs: {sorted(by_id)}")

    specifications = {
        "R_272304b6b54bd7a5d577": {
            "conditions": {"cell_line": "MOLM-13 cells", "treatment_time": None,
                           "tested_concentration": "40 μM lenalidomide",
                           "assay": "cell viability/antiproliferative dose-response"},
            "origin": "primary_report",
            "reason": "Same paragraph explicitly gives MOLM-13 and 40 μM lenalidomide competition.",
        },
        "R_3214e0ba39e9843ee918": {
            "conditions": {"cell_line": "MOLM-13 cells", "treatment_time": "72 h",
                           "tested_concentration": None, "assay": "CellTiter-Glo viability assay"},
            "origin": "primary_report",
            "reason": "Figure 2c caption explicitly defines the 72 h CTG cytotoxicity experiment; exact dose series is not stated there.",
        },
        "R_3e916556de9c190f58c3": {
            "conditions": {"cell_line": "MOLM-13 cells", "treatment_time": None,
                           "tested_concentration": None, "assay": None},
            "origin": "secondary_report",
            "secondary_report_of": "B236 reference 19",
            "reason": "The article attributes the CK1α degradation result to a cited prior study.",
        },
        "R_a00525b030f97dc1d71f": {
            "conditions": {"cell_line": "CRBN−/− MOLM-13 cells",
                           "treatment_time": "24 h and 72 h", "tested_concentration": "1 μM",
                           "assay": "annexin-V/DAPI flow cytometry"},
            "facts": {"subject": "SJ7095, SJ0040, and SJ3149",
                      "target": "CRBN−/− MOLM-13 cells"},
            "origin": "primary_report",
            "reason": "The preceding sentences explicitly define all three compounds, 1 μM, both time points and the apoptosis assay.",
        },
        "R_edd8612899b4eec04120": {
            "conditions": {"cell_line": "9-cell acute leukemia/medulloblastoma panel",
                           "treatment_time": "72 h", "tested_concentration": "dose-response",
                           "assay": "CellTiter-Glo viability assay"},
            "origin": "primary_report",
            "reason": "The screen description and Figure 1 caption explicitly provide panel, duration and CTG assay.",
        },
        "R_3c0fd648c0868c8c6ead": {
            "conditions": {"cell_line": "MOLM-13 cells", "treatment_time": None,
                           "tested_concentration": None, "assay": "cell viability"},
            "origin": "primary_report",
            "reason": "MOLM-13 and viability are explicit; dose and duration remain unreported in the supplied context.",
        },
        "R_5f330b7a4a2a6793b131": {
            "conditions": {"cell_line": "115 human cancer cell-line Oncolines panel",
                           "treatment_time": "72 h",
                           "tested_concentration": "duplicate 9-point range, 3.2–31,600 nM",
                           "assay": "ATPlite intracellular-ATP viability assay"},
            "origin": "primary_report",
            "reason": "The methods and Figure 3 caption explicitly provide panel, dose series, duration and assay.",
        },
    }
    entries = []
    for rid, spec in specifications.items():
        record = by_id[rid]
        changes = {
            "conditions": _condition_patch(record, **spec["conditions"]),
            "evidence_origin": spec["origin"],
        }
        if spec.get("facts"):
            changes["facts"] = _facts_patch(record, **spec["facts"])
        if spec.get("secondary_report_of"):
            changes["secondary_report_of"] = spec["secondary_report_of"]
            changes["model_eligibility"] = {
                "training": False, "rag": False,
                "reason": "secondary_report_requires_original_source_verification",
            }
        entries.append(_patch(record, f"REV-B236-{rid}-CONTEXT-v1", changes, spec["reason"]))
    return entries


def build(run: Path, workspace: Path, output: Path) -> list[dict]:
    baseline = _baseline_records(run)
    document = _read(workspace / "documents" / "B235.json")
    sentences = _read(workspace / "sentence_indexes" / "B235.json")
    entries = b236_entries(baseline)
    entries.append(est1036_entry(
        document, sentences,
        "J_64226fbe6480320d743d60d706bea7d4ffdcabb04e6f6fd591db5fc892d40ad5",
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                              for row in entries), encoding="utf-8")
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({"entries": len(build(args.run, args.workspace, args.output)),
                      "output": str(args.output)}, ensure_ascii=False, indent=2))

