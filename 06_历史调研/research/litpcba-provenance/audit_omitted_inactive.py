"""Approximate, provenance-labeled audit of AID 995 inactive SIDs absent from LIT-PCBA Full.

This intentionally does NOT claim to reproduce the historical Pipeline Pilot / CORINA /
Filter pipeline. PubChem current CID-level XLogP is only a proxy for historical AlogP.
Run from any working directory: python audit_omitted_inactive.py
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path


DATA = Path(__file__).resolve().parent / "data"
ASSAY_ROWS = DATA / "AID995_not_in_LITPCBA_Full_assay_rows_2026-09-30.csv"
CID_PROPERTIES = DATA / "AID995_omitted_binary_CID_properties_2026-09-30.csv"
OUTPUT = DATA / "AID995_omitted_inactive_candidate_reasons_2026-09-30.csv"

ALLOWED_ELEMENTS = {"H", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"}
def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(record: dict[str, str], field: str) -> float:
    value = record.get(field, "")
    if value == "":
        raise ValueError(f"Missing {field}")
    return float(value)


def classify(record: dict[str, str], properties: dict[str, dict[str, str]]) -> dict[str, str]:
    prop = properties.get(record.get("PUBCHEM_CID", ""))
    result = dict(record)
    if not prop:
        reason = "property_lookup_missing"
        formula_elements: set[str] = set()
    else:
        formula = prop.get("MolecularFormula", "")
        tokens = re.findall(r"[A-Z][a-z]?", formula)
        elements = set(tokens)
        normalized_formula = re.sub(r"[0-9().+\-]", "", formula)
        if not formula or "".join(tokens) != normalized_formula:
            formula_elements = set()
        else:
            formula_elements = elements

    smiles = record.get("PUBCHEM_EXT_DATASOURCE_SMILES", "")
    smiles_elements = set(re.findall(r"Cl|Br|[A-Z][a-z]?", smiles))
    step1_elements = smiles_elements if smiles else formula_elements
    invalid_elements = step1_elements - ALLOWED_ELEMENTS
    if not prop:
        pass
    elif (smiles or formula_elements) and invalid_elements:
        reason = "candidate_step1_inorganic"
    elif not smiles and not formula_elements:
        reason = "formula_unparsed"
    else:
        try:
            mw = number(prop, "MolecularWeight")
            xlogp = number(prop, "XLogP")
            hbd = number(prop, "HBondDonorCount")
            hba = number(prop, "HBondAcceptorCount")
            rotatable = number(prop, "RotatableBondCount")
            charge = number(prop, "Charge")
        except ValueError:
            reason = "property_value_missing"
        else:
            passes = (
                150 < mw < 800
                and -3.0 < xlogp < 5.0
                and rotatable < 15
                and hba < 10
                and hbd < 10
                and -2 < charge < 2
            )
            reason = (
                "residual_possible_step4_or_definition_mismatch"
                if passes
                else "candidate_step3_property"
            )

    result.update(
        {
            "candidate_exclusion_reason": reason,
            "source_smiles_nonallowed_elements": ";".join(sorted(invalid_elements)),
            "PubChem_formula": prop.get("MolecularFormula", "") if prop else "",
            "PubChem_MW": prop.get("MolecularWeight", "") if prop else "",
            "PubChem_XLogP_not_historical_AlogP": prop.get("XLogP", "") if prop else "",
            "PubChem_HBD": prop.get("HBondDonorCount", "") if prop else "",
            "PubChem_HBA": prop.get("HBondAcceptorCount", "") if prop else "",
            "PubChem_rotatable_bonds": prop.get("RotatableBondCount", "") if prop else "",
            "PubChem_charge": prop.get("Charge", "") if prop else "",
        }
    )
    return result


def main() -> None:
    assay = read_csv(ASSAY_ROWS)
    properties = {row["CID"]: row for row in read_csv(CID_PROPERTIES)}
    inactive = [row for row in assay if row["PUBCHEM_ACTIVITY_OUTCOME"] == "Inactive"]
    classified = [classify(row, properties) for row in inactive]
    counts = Counter(row["candidate_exclusion_reason"] for row in classified)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(classified[0]))
        writer.writeheader()
        writer.writerows(classified)

    print(f"Inactive rows: {len(inactive)}")
    print(f"Unique inactive SIDs: {len({row['PUBCHEM_SID'] for row in inactive})}")
    print(f"CID property rows: {len(properties)}")
    for reason, count in sorted(counts.items()):
        print(f"{reason}: {count}")
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    main()
