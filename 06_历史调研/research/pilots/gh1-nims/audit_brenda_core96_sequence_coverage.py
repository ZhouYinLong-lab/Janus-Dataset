"""Compare the full GH1 core-pool protein set to BRENDA EC sequence sets.

Exact sequence hits establish protein-entity sequence-index presence only;
they do not establish source-paper assay or negative-observation coverage.
"""

from __future__ import annotations

import csv
import re
import time
from collections import defaultdict
from pathlib import Path

import requests


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = HERE / "gh1_nims_core96_ncbi_crosswalk.csv"
NCBI_FASTA = HERE / "gh1_nims_core96_ncbi_sequences.fasta"
OUTPUT = HERE / "brenda_ec_sequence_core96_audit.csv"
SOURCE_DIR = ROOT / "research" / "sources" / "brenda-gh1-ec-fasta"
BRENDA_URL = "https://www.brenda-enzymes.org/sequences.php"


def parse_fasta(text: str) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    header = ""
    chunks: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header:
                records.append((header, header.split("|", 1)[0].lstrip(">"), "".join(chunks)))
            header = line
            chunks = []
        elif header:
            chunks.append(re.sub(r"\s+", "", line))
    if header:
        records.append((header, header.split("|", 1)[0].lstrip(">"), "".join(chunks)))
    return records


def load_ncbi_fasta(path: Path) -> dict[str, str]:
    sequences = {}
    for header, _, sequence in parse_fasta(path.read_text(encoding="ascii")):
        accession_match = re.search(r"([A-Z]{1,4}\d+\.\d+)", header)
        if accession_match:
            sequences[accession_match.group(1)] = sequence.upper()
    return sequences


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        core_rows = list(csv.DictReader(stream))
    sequences = load_ncbi_fasta(NCBI_FASTA)
    accessions = {row["ncbi_accession"] for row in core_rows if row["ncbi_accession"]}
    if len(core_rows) != 96 or len(accessions) != 86 or len(sequences) != 86:
        raise RuntimeError(
            f"Expected 96 core proteins / 86 accessioned sequences, got "
            f"{len(core_rows)} / {len(accessions)} / {len(sequences)}"
        )

    ec_numbers = sorted({
        ec
        for row in core_rows
        for ec in row.get("ncbi_ec_numbers", "").split(";")
        if ec
    })
    if not ec_numbers:
        raise RuntimeError("No explicit NCBI EC annotations found in the core pool")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Janus-Dataset research audit/1.0"})
    brenda_by_ec: dict[str, list[tuple[str, str, str]]] = {}
    for index, ec in enumerate(ec_numbers):
        response = session.get(
            BRENDA_URL,
            params={"download": "allfasta", "ec": ec},
            timeout=240,
        )
        response.raise_for_status()
        parsed = parse_fasta(response.text)
        if not parsed:
            raise RuntimeError(f"BRENDA returned no FASTA records for EC {ec}")
        (SOURCE_DIR / f"EC_{ec}.fasta").write_text(response.text, encoding="utf-8")
        brenda_by_ec[ec] = parsed
        print(f"BRENDA EC {ec}: {len(parsed)} sequences ({len(response.content):,} bytes)")
        if index + 1 < len(ec_numbers):
            time.sleep(0.5)

    records_by_sequence: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for ec, records in brenda_by_ec.items():
        for header, accession, sequence in records:
            records_by_sequence[sequence.upper()].append((ec, accession, header))

    output_rows = []
    for row in core_rows:
        accession = row["ncbi_accession"]
        sequence = sequences.get(accession, "")
        matches = records_by_sequence.get(sequence, []) if sequence else []
        ncbi_ecs = {ec for ec in row.get("ncbi_ec_numbers", "").split(";") if ec}
        same_ec = [match for match in matches if match[0] in ncbi_ecs]
        output_rows.append(
            {
                "source_protein_id": row["source_protein_id"],
                "ncbi_accession": accession,
                "core_pool_below_background_cells": row["core_pool_below_background_cells"],
                "core_pool_substrate_counts": row["core_pool_substrate_counts"],
                "ncbi_ec_numbers": row.get("ncbi_ec_numbers", ""),
                "ncbi_sequence_length_aa": len(sequence) if sequence else "",
                "ncbi_sequence_sha256": row.get("ncbi_sequence_sha256", ""),
                "entity_search_status": "exact_sequence_compared" if sequence else "no_accession_sequence_unresolved",
                "exact_brenda_sequence_match_any_ec": str(bool(matches)).lower() if sequence else "unresolved",
                "exact_brenda_sequence_match_same_ec": str(bool(same_ec)).lower() if sequence else "unresolved",
                "matching_brenda_entries": " || ".join(
                    f"EC {ec} | {uniprot} | {header}" for ec, uniprot, header in matches
                ),
                "interpretation": (
                    "Exact protein sequence appears in one of the BRENDA EC FASTA sets; not assay/negative coverage"
                    if matches else (
                        "Compared against these four BRENDA EC sequence sets only; no exact sequence hit"
                        if sequence else "Source label has no versioned accession; entity match unresolved"
                    )
                ),
            }
        )

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    queryable_rows = [row for row in output_rows if row["ncbi_accession"]]
    any_hit_rows = [row for row in queryable_rows if row["exact_brenda_sequence_match_any_ec"] == "true"]
    same_ec_rows = [row for row in queryable_rows if row["exact_brenda_sequence_match_same_ec"] == "true"]
    print(f"core_pool_proteins={len(output_rows)}")
    print(f"queryable_accessioned_proteins={len(queryable_rows)}")
    print(f"exact_BRENDA_sequence_hits_any_EC={len(any_hit_rows)} proteins / "
          f"{sum(int(row['core_pool_below_background_cells']) for row in any_hit_rows)} source cells")
    print(f"exact_BRENDA_sequence_hits_same_EC={len(same_ec_rows)} proteins / "
          f"{sum(int(row['core_pool_below_background_cells']) for row in same_ec_rows)} source cells")
    print(f"no_accession_source_labels={len(output_rows) - len(queryable_rows)}")
    print(f"output={OUTPUT}")
    print(f"retained_BRENDA_FASTA_sources={SOURCE_DIR}")
    print("interpretation=sequence-entity index only; no assay or negative observation coverage inferred")


if __name__ == "__main__":
    main()
