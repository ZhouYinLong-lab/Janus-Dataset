"""Audit repeated measured compound-target keys and train/test overlap.

Uses only Python's standard library. It reads the author's public prepared CSV
without modifying the upstream repository and writes auditable summaries next
to this script.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "reproductions"
    / "kinase-activity-integration"
    / "data"
    / "prepped_activities_all_chembl_pubchem.csv"
)
OUT_DIR = Path(__file__).resolve().parent
SPLITS = {
    "ck_split_set": "ck",
    "ligand_split_set": "ligand",
    "cluster_split_set": "cluster",
}


def read_measured_rows() -> dict[tuple[str, str], list[dict[str, str]]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with SOURCE.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["activity_type"] != "measured":
                continue
            key = (row["canonical_smiles"], row["uniprot_id"])
            groups[key].append(row)
    return groups


def write_pair_details(groups: dict[tuple[str, str], list[dict[str, str]]]) -> None:
    fields = [
        "canonical_smiles",
        "uniprot_id",
        "rows",
        "activity_values",
        "distinct_activity_values",
        "activity_range_abs",
        "ck_splits",
        "ligand_splits",
        "cluster_splits",
        "ck_train_test_overlap",
        "ligand_train_test_overlap",
        "cluster_train_test_overlap",
    ]
    destination = OUT_DIR / "theisen_measured_duplicate_pairs.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for (smiles, accession), rows in sorted(groups.items()):
            if len(rows) < 2:
                continue
            values = sorted(float(row["activity_value"]) for row in rows)
            record: dict[str, object] = {
                "canonical_smiles": smiles,
                "uniprot_id": accession,
                "rows": len(rows),
                "activity_values": ";".join(row["activity_value"] for row in rows),
                "distinct_activity_values": len(set(row["activity_value"] for row in rows)),
                "activity_range_abs": max(values) - min(values),
            }
            for column, label in SPLITS.items():
                split_values = sorted({row[column] for row in rows})
                record[f"{label}_splits"] = ";".join(split_values)
                record[f"{label}_train_test_overlap"] = (
                    "true" if {"train", "test"}.issubset(split_values) else "false"
                )
            writer.writerow(record)


def write_summary(groups: dict[tuple[str, str], list[dict[str, str]]]) -> None:
    fields = [
        "split",
        "measured_rows",
        "unique_pair_keys",
        "duplicate_pair_keys",
        "multivalued_duplicate_pair_keys",
        "train_rows",
        "test_rows",
        "train_unique_pair_keys",
        "test_unique_pair_keys",
        "pair_keys_in_train_and_test",
        "percent_test_pairs_also_in_train",
    ]
    destination = OUT_DIR / "theisen_measured_split_integrity_summary.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        duplicate_keys = {key for key, rows in groups.items() if len(rows) > 1}
        multivalued_keys = {
            key
            for key in duplicate_keys
            if len({row["activity_value"] for row in groups[key]}) > 1
        }
        for column, label in SPLITS.items():
            train_keys: set[tuple[str, str]] = set()
            test_keys: set[tuple[str, str]] = set()
            train_rows = 0
            test_rows = 0
            for key, rows in groups.items():
                for row in rows:
                    if row[column] == "train":
                        train_rows += 1
                        train_keys.add(key)
                    elif row[column] == "test":
                        test_rows += 1
                        test_keys.add(key)
            overlap = train_keys & test_keys
            writer.writerow(
                {
                    "split": label,
                    "measured_rows": sum(map(len, groups.values())),
                    "unique_pair_keys": len(groups),
                    "duplicate_pair_keys": len(duplicate_keys),
                    "multivalued_duplicate_pair_keys": len(multivalued_keys),
                    "train_rows": train_rows,
                    "test_rows": test_rows,
                    "train_unique_pair_keys": len(train_keys),
                    "test_unique_pair_keys": len(test_keys),
                    "pair_keys_in_train_and_test": len(overlap),
                    "percent_test_pairs_also_in_train": (
                        f"{100 * len(overlap) / len(test_keys):.6f}" if test_keys else ""
                    ),
                }
            )


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Expected author CSV not found: {SOURCE}")
    groups = read_measured_rows()
    write_pair_details(groups)
    write_summary(groups)
    print(f"Measured rows: {sum(map(len, groups.values())):,}")
    print(f"Unique canonical-SMILES/UniProt pairs: {len(groups):,}")
    print(f"Duplicate pair groups: {sum(len(rows) > 1 for rows in groups.values()):,}")
    print(f"Outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
