"""Full-text audit of the five papers whose first pass found no candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import curation_overlay


ZERO_PAPERS = (
    "MG_557706380d28325a23a39f2b",
    "MG_c902a13c22b5f6af5523d5bf",
    "MG_ceb7ffa7efd656ab5bc86de1",
    "MG_d313cddfdcdf91cf7815e8b8",
    "B234",
)


RECOVERIES = {
    "MG_c902a13c22b5f6af5523d5bf": [
        {
            "fragment": "exhibited no changes in MEIS2 levels following addition of 40 µM lenalidomide",
            "subject": "lenalidomide", "target": "MEIS2",
            "endpoint": "MEIS2 protein abundance",
            "observation": "no change in MEIS2 levels",
            "condition": "stable cells expressing epitope-tagged MEIS2 and CRBN YW/AA; 40 µM lenalidomide",
            "scope": "molecular_glue_degradation_negative",
        },
    ],
    "MG_ceb7ffa7efd656ab5bc86de1": [
        {"fragment": "Myc-IKZF1 but not AGIA-SALL4", "subject": "NE-005", "target": "AGIA-SALL4", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "could not degrade Myc-IKZF1 and AGIA-SALL4", "subject": "NE-008 and NE-006", "target": "Myc-IKZF1 and AGIA-SALL4", "endpoint": "protein degradation", "observation": "could not degrade", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "but not SALL4 and PLZF, in cultured cells", "subject": "NE-005", "target": "SALL4 and PLZF", "endpoint": "endogenous protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "F3C-Le and F3CO-Le could not interact with IKZF1", "subject": "F3C-Le and F3CO-Le", "target": "IKZF1, SALL4, and PLZF", "endpoint": "AlphaScreen interaction", "observation": "could not interact", "scope": "other_endpoint"},
        {"fragment": "F3C-Le and F3CO-Le could not degrade IKZF1", "subject": "F3C-Le and F3CO-Le", "target": "IKZF1, IKZF3, CK1α, SALL4, and PLZF", "endpoint": "protein degradation", "observation": "could not degrade", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "Cl-Le, Br-Le, F3C-Le, and F3CO-Le did not", "subject": "Cl-Le, Br-Le, F3C-Le, and F3CO-Le", "target": "ZFP91", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "all 6-position-modified lenalidomides did not degrade GSPT1", "subject": "all 6-position-modified lenalidomides", "target": "GSPT1", "endpoint": "protein degradation", "observation": "did not degrade", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "all 6-position-modified lenalidomides could not degrade IKZF2", "subject": "all 6-position-modified lenalidomides", "target": "IKZF2", "endpoint": "protein degradation", "observation": "could not degrade", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "did not induce protein degradation of p63", "subject": "6-position-modified lenalidomides", "target": "p63 (TP63)", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "Br-Le and F3C-Le degraded RAB28 but did not CK1α", "subject": "Br-Le and F3C-Le", "target": "CK1α, IKZF1, and IKZF3", "endpoint": "protein degradation", "observation": "did not degrade", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "F3CO-Le did not induce protein degradation of detected neosubstrates", "subject": "F3CO-Le", "target": "detected neosubstrates", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "F-P, Cl-P and F3C-P did not induce protein degradation of PLZF and CK1α", "subject": "F-P, Cl-P, and F3C-P", "target": "PLZF and CK1α", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "Le-P, F-P, Cl-P, and F3C-P did not", "subject": "Le-P, F-P, Cl-P, and F3C-P", "target": "ZFP91", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "Po-P, Le-P, and F3C-P did not", "subject": "Po-P, Le-P, and F3C-P", "target": "RAB28", "endpoint": "protein degradation", "observation": "did not induce degradation", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "F-Le and Cl-Le did not have significant cytotoxicity", "subject": "F-Le and Cl-Le", "target": "TK, BJAB, Karpas-1106P, SU-DHL-4, Jurkat, and THP-1 cells", "endpoint": "cytotoxicity", "observation": "did not have significant cytotoxicity", "scope": "other_endpoint"},
        {"fragment": "6-position-modified lenalidomides did not show anti-proliferative effect", "subject": "6-position-modified lenalidomides", "target": "cell proliferation", "endpoint": "anti-proliferative effect", "observation": "did not show an anti-proliferative effect", "scope": "other_endpoint"},
    ],
}


NEGATIVE_CUE = re.compile(
    r"\b(no|not|neither|without|failed|inactive|insensitive|unchanged|unaffected|"
    r"little|minimal|lack|unable|resistant|could not|did not|does not)\b|"
    r"no significant|less effective", re.I,
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable(prefix: str, value) -> str:
    return prefix + hashlib.sha256(curation_overlay.canonical_bytes(value)).hexdigest()[:20]


def recovered_entry(paper: dict, sentence: dict, spec: dict) -> dict:
    identity = {
        "paper_id": paper["paper_id"], "source_sha256": paper["source_sha256"],
        "subject": spec["subject"], "target": spec["target"],
        "endpoint": spec["endpoint"], "sentence_id": sentence["sentence_id"],
    }
    evidence_id = _stable("E_REC_", identity)
    experiment_id = _stable("X_", {key: value for key, value in identity.items()
                                    if key != "sentence_id"})
    mention_id = _stable("M_", [evidence_id, sentence["sentence_id"]])
    record = {
        "evidence_id": evidence_id, "record_id": evidence_id,
        "paper_id": paper["paper_id"], "doi": paper.get("doi"),
        "source_sha256": paper["source_sha256"],
        "generation_method": "manual_recovery_from_frozen_source",
        "model": None, "expert_gold": False, "final_status": "pending_review",
        "scope_class": spec["scope"], "evidence_origin": "primary_report",
        "experiment_id": experiment_id,
        "facts": {"status": "observations", "reason": None, "observations": [{
            "values": {"subject": spec["subject"], "target": spec["target"],
                       "endpoint": spec["endpoint"], "observation": spec["observation"],
                       "comparator": None, "scope_condition": spec.get("condition")},
            "outcome_type": "not_significant" if "significant" in spec["observation"]
                            else "not_observed",
            "evidence": {},
        }]},
        "conditions": {"items": [{"record_id": evidence_id, "values": {
            "cell_line": None, "treatment_time": None, "tested_concentration": None,
            "assay": None, "perturbation": spec["subject"],
            "endpoint_resolution": spec["endpoint"],
        }, "evidence": {}}]},
        "evidence_spans": [{"mention_id": mention_id, "unit_id": sentence["unit_id"],
                            "sentence_ids": [sentence["sentence_id"]],
                            "char_start": sentence["char_start"], "char_end": sentence["char_end"],
                            "quote": sentence["text"], "kind": sentence.get("kind"),
                            "locator": sentence.get("locator")}],
        "model_eligibility": {"training": False, "rag": False,
                              "reason": "requires_two_independent_reviews"},
    }
    return {
        "revision_id": "REV-ZERO-" + evidence_id + "-v1", "operation": "add_record",
        "record_id": evidence_id, "paper_id": paper["paper_id"],
        "source_sha256": paper["source_sha256"], "record": record,
        "reason": "Recovered by full-text audit of a paper previously reported with zero candidates.",
        "curator": "codex-main-v1", "expert_gold": False,
    }


def audit(workspace: Path, inventory_path: Path):
    inventory = {row["paper_id"]: row for row in _read(inventory_path)}
    entries, reports = [], []
    for paper_id in ZERO_PAPERS:
        document = _read(workspace / "documents" / f"{paper_id}.json")
        sentences = _read(workspace / "sentence_indexes" / f"{paper_id}.json")
        specs = RECOVERIES.get(paper_id, [])
        found = []
        for spec in specs:
            matches = [row for row in sentences if spec["fragment"] in row.get("text", "")]
            if len(matches) != 1:
                raise ValueError(f"Expected one match for {paper_id}: {spec['fragment']}")
            entry = recovered_entry(inventory[paper_id], matches[0], spec)
            entries.append(entry)
            found.append(entry["record_id"])
        cue_count = sum(bool(NEGATIVE_CUE.search(row.get("text", ""))) for row in sentences)
        reports.append({
            "paper_id": paper_id, "doi": inventory[paper_id].get("doi"),
            "source_sha256": inventory[paper_id]["source_sha256"],
            "document_units_scanned": len(document["units"]),
            "sentences_scanned": len(sentences), "negative_cue_sentences": cue_count,
            "recovered_records": found, "recovered_count": len(found),
            "audit_status": "complete_model_assisted_not_expert_gold",
            "notes": {
                "MG_557706380d28325a23a39f2b": "No primary in-scope degradation negative; cues concern simulation, general mechanism, or cited work.",
                "MG_d313cddfdcdf91cf7815e8b8": "Negative results concern parkin activation/mitophagy, outside degradation-evidence scope.",
                "B234": "No qualifying experimental negative found in body sentences or available captions.",
            }.get(paper_id, "Explicit experimental negatives recovered and left pending a second independent review."),
        })
    return entries, reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    additions, report = audit(args.workspace, args.inventory)
    append = curation_overlay.append_entries(args.ledger, additions)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"recovered": len(additions), "ledger": append,
                      "papers": len(report)}, ensure_ascii=False, indent=2))

