"""Compare NCBI accession EC qualifiers with BRENDA species-page EC lists.

This is a coarse annotation crosswalk only. A species+EC intersection is not an
exact protein accession, substrate, assay-condition, or observation match.
"""

from __future__ import annotations

import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
NCBI = HERE / "ncbi_accession_crosswalk.csv"
BRENDA = HERE / "brenda_species_ec_crosswalk.csv"
OUTPUT = HERE / "ncbi_brenda_species_ec_join.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    ncbi_rows = read_csv(NCBI)
    brenda_rows = read_csv(BRENDA)
    brenda_by_species = {
        row["organism_query"].casefold(): row
        for row in brenda_rows if row.get("organism_query")
    }
    joined: list[dict[str, str]] = []
    for record in ncbi_rows:
        organism_tokens = record.get("ncbi_organism", "").split()
        species = " ".join(organism_tokens[:2]) if len(organism_tokens) >= 2 else ""
        page = brenda_by_species.get(species.casefold(), {})
        accession_ecs = sorted(set(filter(None, record.get("ncbi_ec_numbers", "").split(";"))))
        brenda_ecs = set(filter(None, page.get("brenda_ec_numbers", "").split(";")))
        intersections = sorted(set(accession_ecs) & brenda_ecs)
        joined.append({
            "ncbi_accession": record.get("ncbi_accession", ""),
            "source_protein_label": record.get("source_protein_label", ""),
            "sample_observation_count": record.get("sample_observation_count", ""),
            "ncbi_organism": record.get("ncbi_organism", ""),
            "organism_query": species,
            "ncbi_definition": record.get("ncbi_definition", ""),
            "ncbi_ec_numbers": ";".join(accession_ecs),
            "brenda_page_queried": str(
                bool(page) and page.get("page_entity_confirmed") == "true"
            ).lower(),
            "brenda_page_entity_confirmed": page.get("page_entity_confirmed", ""),
            "brenda_ec_numbers": page.get("brenda_ec_numbers", ""),
            "species_ec_intersection": ";".join(intersections),
            "interpretation": (
                "species+EC annotation intersection only" if intersections else
                "species page found; no EC intersection" if page and accession_ecs else
                "no BRENDA species-page match for NCBI binomial" if accession_ecs else
                "no explicit NCBI EC qualifier"
            ),
        })

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(joined[0]))
        writer.writeheader()
        writer.writerows(joined)

    ec_records = [row for row in joined if row["ncbi_ec_numbers"]]
    page_ec_records = [row for row in ec_records if row["brenda_page_queried"] == "true"]
    hits = [row for row in page_ec_records if row["species_ec_intersection"]]
    no_hits = [row for row in page_ec_records if not row["species_ec_intersection"]]
    unresolved = [row for row in ec_records if row["brenda_page_queried"] != "true"]
    print(f"accessions={len(joined)}")
    print(f"accessions_with_NCBI_EC={len(ec_records)}")
    print(f"EC_records_with_BRENDA_species_page={len(page_ec_records)}")
    print(f"species_EC_intersections={len(hits)}")
    print(f"species_page_no_intersection={len(no_hits)}")
    print(f"EC_records_without_BRENDA_species_page={len(unresolved)}")
    print(f"join_csv={OUTPUT}")
    print("interpretation=annotation-level only; not exact protein or assay-row coverage")


if __name__ == "__main__":
    main()
