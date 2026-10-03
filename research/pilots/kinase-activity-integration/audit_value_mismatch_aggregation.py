"""Test whether unmatched prepared pActivity values resemble ChEMBL IC50 aggregates.

The article says it summarized multiple measurements using the "geometric mean
of the pIC50 values." This script tests the arithmetic mean in pIC50 space,
equivalent to the geometric mean of IC50 concentrations; it does not assume this
is exactly what the authors implemented. It tests current ChEMBL 37 activity
rows for the 39 sample rows with pair activity but no individual pChEMBL match.
This is exploratory, not a reconstruction of the authors' source version.
Structure resolution is connectivity-level and stereochemistry may be ambiguous.
"""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PILOT_DIR = Path(__file__).resolve().parent
RESULTS = PILOT_DIR / "theisen_linkage_sample_100_results.csv"
ACTIVITIES = PILOT_DIR / "theisen_linkage_sample_100_activity_records.csv"
OUTPUT = PILOT_DIR / "theisen_100_value_mismatch_adjudication.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def floats(rows: list[dict[str, str]], field: str) -> list[float]:
    result = []
    for row in rows:
        try:
            result.append(float(row[field]))
        except (TypeError, ValueError):
            pass
    return result


def molar_value(row: dict[str, str]) -> float | None:
    """Convert a positive standard value with supported units to molar."""
    try:
        value = float(row["standard_value"])
    except (TypeError, ValueError, KeyError):
        return None
    unit = row.get("standard_units", "").strip().lower()
    factors = {"m": 1.0, "mm": 1e-3, "um": 1e-6, "µm": 1e-6, "nm": 1e-9}
    factor = factors.get(unit)
    if factor is None or value <= 0:
        return None
    return value * factor


def main() -> None:
    summaries = read_csv(RESULTS)
    activity_rows = read_csv(ACTIVITIES)
    by_source: dict[str, list[dict[str, str]]] = {}
    for row in activity_rows:
        by_source.setdefault(row["source_row"], []).append(row)

    output_rows: list[dict[str, str]] = []
    for summary in summaries:
        if summary["match_class"] != "pair_activity_found_no_exact_pchembl_match":
            continue
        source_id = summary["source_row"]
        rows = by_source.get(source_id, [])
        candidate_ids = sorted(
            value for value in summary["chembl_molecule_ids"].split(";") if value
        )
        ic50 = [row for row in rows if row["standard_type"].strip().upper() == "IC50"]
        ic50_pchembl = floats(ic50, "pchembl_value")
        prepared = float(summary["prepared_pactivity"])
        nearest = min((abs(value - prepared) for value in ic50_pchembl), default=None)
        grand_mean = statistics.fmean(ic50_pchembl) if ic50_pchembl else None

        per_candidate_means: list[tuple[str, float, int]] = []
        for candidate_id in candidate_ids:
            candidate_rows = [
                row for row in ic50
                if row["molecule_chembl_id"] == candidate_id and row["pchembl_value"].strip()
            ]
            candidate_values = floats(candidate_rows, "pchembl_value")
            if candidate_values:
                per_candidate_means.append(
                    (candidate_id, statistics.fmean(candidate_values), len(candidate_values))
                )
        nearest_candidate_mean = min(
            (abs(mean - prepared) for _, mean, _ in per_candidate_means), default=None
        )
        best_mean = min(
            per_candidate_means,
            key=lambda item: abs(item[1] - prepared),
            default=None,
        )
        relations = sorted({row["standard_relation"].strip() for row in ic50 if row["standard_relation"].strip()})
        censored_count = sum(1 for row in ic50 if row["standard_relation"].strip() not in ("", "="))
        censored_pactivities = []
        for row in ic50:
            relation = row["standard_relation"].strip()
            molar = molar_value(row)
            if relation not in ("", "=") and molar is not None:
                censored_pactivities.append(-math.log10(molar))
        closest_censor_delta = min(
            (abs(value - prepared) for value in censored_pactivities), default=None
        )
        doi_count = len({row["doi"] for row in rows if row["doi"].strip()})
        assay_count = len({row["assay_chembl_id"] for row in rows if row["assay_chembl_id"].strip()})
        document_count = len({row["document_chembl_id"] for row in rows if row["document_chembl_id"].strip()})

        if not ic50_pchembl:
            category = "no_numeric_IC50_pChEMBL_in_current_candidate_records"
        elif len(candidate_ids) > 1:
            category = "multiple_structure_candidates_aggregate_not_attributable"
        elif nearest_candidate_mean is not None and nearest_candidate_mean <= 0.01:
            category = "single_candidate_IC50_mean_within_0.01"
        elif nearest_candidate_mean is not None and nearest_candidate_mean <= 0.05:
            category = "single_candidate_IC50_mean_within_0.05"
        else:
            category = "single_candidate_current_IC50_mean_not_close"

        output_rows.append(
            {
                "source_row": source_id,
                "stratum": summary["stratum"],
                "prepared_pactivity": summary["prepared_pactivity"],
                "uniprot_id": summary["uniprot_id"],
                "candidate_molecule_count": str(len(candidate_ids)),
                "candidate_molecule_ids": ";".join(candidate_ids),
                "activity_record_count": str(len(rows)),
                "ic50_record_count": str(len(ic50)),
                "numeric_ic50_pchembl_count": str(len(ic50_pchembl)),
                "individual_nearest_abs_delta": f"{nearest:.6f}" if nearest is not None else "",
                "all_candidate_ic50_mean_pchembl": f"{grand_mean:.6f}" if grand_mean is not None else "",
                "all_candidate_mean_abs_delta": f"{abs(grand_mean-prepared):.6f}" if grand_mean is not None else "",
                "best_single_molecule_ic50_mean": f"{best_mean[1]:.6f}" if best_mean else "",
                "best_single_molecule_mean_abs_delta": f"{nearest_candidate_mean:.6f}" if nearest_candidate_mean is not None else "",
                "best_candidate_mean_molecule_id": best_mean[0] if best_mean else "",
                "best_candidate_mean_record_count": str(best_mean[2]) if best_mean else "",
                "ic50_non_equality_relation_count": str(censored_count),
                "ic50_relations": ";".join(relations),
                "censored_bound_derived_pactivity_values": ";".join(f"{v:.6f}" for v in censored_pactivities),
                "closest_censored_bound_abs_delta": f"{closest_censor_delta:.6f}" if closest_censor_delta is not None else "",
                "assay_count": str(assay_count),
                "document_count": str(document_count),
                "doi_count": str(doi_count),
                "adjudication_category": category,
            }
        )

    fields = list(output_rows[0]) if output_rows else []
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Rows adjudicated: {len(output_rows)}")
    for category in sorted({row["adjudication_category"] for row in output_rows}):
        print(f"{category}: {sum(row['adjudication_category'] == category for row in output_rows)}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
