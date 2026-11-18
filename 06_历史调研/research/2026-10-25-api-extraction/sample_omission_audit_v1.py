"""Deterministic full-text spot audit of 15 non-zero-candidate papers."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import curation_overlay
from zero_candidate_audit_v1 import recovered_entry


SEED = "20261027"
SAMPLE = {
    "low": ["B243", "MG_f60d444b00d76c870270413c", "MG_7ea266d5248089c09271b572",
            "MG_d9b6c6cf9cc9432b57799dba", "MG_55ff5e65728f678d1577f177"],
    "medium": ["MG_955a78dec1ee51a56736d5b5", "MG_757e0ec7833b2b363fd5b667",
               "MG_6550693930def87fc298ebd3", "MG_23ad1e92988f07785012d05b",
               "MG_2b8b555d0c28016afcc0021b"],
    "high": ["B204", "MG_e29492adcc9f28f35ebeaa6a", "MG_bbb57a05121411228d461934",
             "MG_f3f56594d6286fda36e579a0", "B212"],
}


RECOVERIES = {
    "MG_d9b6c6cf9cc9432b57799dba": [
        {"fragment": "ZBED3 and ASS1 showed frequent enrichment", "subject": "pomalidomide and profiled IMiD analogs", "target": "ZBED3 and ASS1", "endpoint": "productive protein degradation", "observation": "chemical recruitment without productive degradation, including pomalidomide up to 5 μM", "condition": "MOLT4 and Kelly lysate enrichment; pomalidomide tested up to 5 μM", "scope": "molecular_glue_degradation_negative"},
    ],
    "MG_55ff5e65728f678d1577f177": [
        {"fragment": "levels of HDAC1 and HDAC2 did not substantially increase", "subject": "KBTBD4-PR base editing", "target": "HDAC1 and HDAC2", "endpoint": "protein abundance", "observation": "did not substantially increase", "scope": "mechanism_or_control"},
        {"fragment": "knockout of LSD1 had minimal effect on CoREST degradation", "subject": "LSD1 knockout", "target": "CoREST complex", "endpoint": "protein degradation", "observation": "minimal effect on degradation", "scope": "mechanism_or_control"},
    ],
    "MG_955a78dec1ee51a56736d5b5": [
        {"fragment": "PLK1 1–584, which missed those amino acids, was resistant", "subject": "CC-885", "target": "PLK1 1–584", "endpoint": "ubiquitination-dependent protein degradation", "observation": "resistant to degradation", "scope": "molecular_glue_degradation_negative"},
    ],
    "MG_6550693930def87fc298ebd3": [
        {"fragment": "Compound 5 did not induce any significant degradation", "subject": "compound 5", "target": "IKZF1/3, GSPT1, and CK1α", "endpoint": "protein degradation", "observation": "did not induce significant degradation up to 10 µM", "condition": "up to 10 µM", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "Compound 5 showed significantly reduced degradation potency and efficacy on SALL4", "subject": "compound 5", "target": "SALL4", "endpoint": "protein degradation", "observation": "reduced potency and efficacy; DC50 >1000 nM and Dmax 33% versus DKY709", "scope": "molecular_glue_degradation_negative"},
    ],
    "MG_23ad1e92988f07785012d05b": [
        {"fragment": "compounds in pathways B and C with opened glutarimide rings do not bind CRBN", "subject": "thalidomide hydrolysis products in pathways B and C", "target": "CRBN", "endpoint": "binding", "observation": "do not bind CRBN", "scope": "other_endpoint"},
    ],
    "MG_2b8b555d0c28016afcc0021b": [
        {"fragment": "neither the non-degradative covalent nor non-covalent analogs showed any significant BRD4 degradation", "subject": "non-degradative covalent and non-covalent analogs", "target": "BRD4", "endpoint": "protein degradation", "observation": "no significant degradation", "scope": "molecular_glue_degradation_negative"},
    ],
    "B204": [
        {"fragment": "did not impact CRBN binding affinity", "subject": "compound 6", "target": "CRBN", "endpoint": "binding affinity", "observation": "did not change binding affinity (1.3 versus 1.4 μM)", "scope": "other_endpoint"},
        {"fragment": "detrimental to the degradation efficacy of CK1α", "subject": "compound 6", "target": "CK1α and IKZF1", "endpoint": "protein degradation", "observation": "reduced degradation efficacy; Dmax 23% and 57%", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "7 displayed a promising CK1α selective profile with minimal degradation of IKZF1", "subject": "compound 7", "target": "IKZF1", "endpoint": "protein degradation", "observation": "minimal degradation; Dmax 12%", "scope": "molecular_glue_degradation_negative"},
        {"fragment": "did not exhibit cytotoxicity over the measured time frame", "subject": "compounds in the series", "target": "HiBiT cell lines", "endpoint": "cytotoxicity", "observation": "did not exhibit cytotoxicity", "scope": "other_endpoint"},
        {"fragment": "degradation of GSPT1 or IKZF1 was not observed", "subject": "selected compounds", "target": "GSPT1 and IKZF1", "endpoint": "protein degradation", "observation": "degradation was not observed", "scope": "molecular_glue_degradation_negative"},
    ],
    "MG_e29492adcc9f28f35ebeaa6a": [
        {"fragment": "no known substrate-specific receptor of the DDB1-CRL4 complex", "subject": "S656 with Cas9-edited DCAF genes", "target": "cellular resistance", "endpoint": "DCAF resistance screen", "observation": "no tested known DCAF conferred resistance", "scope": "mechanism_or_control"},
    ],
    "MG_bbb57a05121411228d461934": [
        {"fragment": "the level of SALL4 protein did not change", "subject": "thalidomide and 5-hydroxythalidomide", "target": "SALL4", "endpoint": "protein abundance in chick limb buds", "observation": "protein level did not change", "scope": "molecular_glue_degradation_negative"},
    ],
    "MG_f3f56594d6286fda36e579a0": [
        {"fragment": "TMX-4100 and TMX-4116, with a greatly reduced ability to degrade IKZF1/IKZF3", "subject": "TMX-4100 and TMX-4116", "target": "IKZF1 and IKZF3", "endpoint": "protein degradation", "observation": "greatly reduced degradation ability", "scope": "molecular_glue_degradation_negative"},
    ],
    "B212": [
        {"fragment": "Both analogues showed reduced degradation ability compared to CR8", "subject": "compounds 19 and 20", "target": "cyclin K", "endpoint": "protein degradation", "observation": "reduced degradation ability compared with CR8", "condition": "HEK293T; 1 μM; 2 h; Western blot", "scope": "molecular_glue_degradation_negative"},
    ],
}

CUE = re.compile(r"\b(no|not|without|failed|inactive|insensitive|unchanged|unaffected|little|"
                 r"minimal|lack|unable|resistant|could not|did not|does not|reduced)\b|"
                 r"no significant|less effective|less potent", re.I)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit(workspace: Path, inventory_path: Path):
    inventory = {row["paper_id"]: row for row in read(inventory_path)}
    entries, reports = [], []
    for stratum, papers in SAMPLE.items():
        for paper_id in papers:
            document = read(workspace / "documents" / f"{paper_id}.json")
            sentences = read(workspace / "sentence_indexes" / f"{paper_id}.json")
            recovered = []
            for spec in RECOVERIES.get(paper_id, []):
                matches = [row for row in sentences if spec["fragment"].casefold() in row["text"].casefold()]
                if len(matches) != 1:
                    raise ValueError(f"Expected one sentence for {paper_id}: {spec['fragment']} ({len(matches)})")
                entry = recovered_entry(inventory[paper_id], matches[0], spec)
                entry["revision_id"] = entry["revision_id"].replace("REV-ZERO-", "REV-SAMPLE-")
                entry["reason"] = "Recovered by deterministic full-text spot audit of the 15-paper sample."
                entries.append(entry); recovered.append(entry["record_id"])
            reports.append({
                "paper_id": paper_id, "stratum": stratum,
                "selection_seed": SEED, "source_sha256": inventory[paper_id]["source_sha256"],
                "document_units_scanned": len(document["units"]),
                "sentences_scanned": len(sentences),
                "negative_cue_sentences": sum(bool(CUE.search(row["text"])) for row in sentences),
                "recovered_records": recovered, "recovered_count": len(recovered),
                "audit_status": "complete_model_assisted_not_expert_gold",
            })
    return entries, reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    entries, report = audit(args.workspace, args.inventory)
    result = curation_overlay.append_entries(args.ledger, entries)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"papers": len(report), "recovered": len(entries), "ledger": result},
                     ensure_ascii=False, indent=2))

