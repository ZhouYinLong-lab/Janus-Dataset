"""Query the public BRENDA SPARQL graph for four GH1-pilot UniProt IDs.

This is an entity-linkage probe only. An empty result is not evidence that
BRENDA's classic enzyme pages or literature tables lack the protein/assay.
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests


ENDPOINT = "https://sparql.dsmz.de/api/brenda"
IDS = {
    "D4LC32": {"sample_accession": "CBL17177.1", "sample_observations": 7},
    "A0ACM7": {"sample_accession": "CAJ88232.1", "sample_observations": 1},
    "Q55000": {"sample_accession": "CAA52344.1", "sample_observations": 1},
    "D4MF92": {"sample_accession": "CBL32986.1", "sample_observations": 3},
}


def main() -> None:
    values = " ".join(
        f"<http://purl.uniprot.org/uniprot/{accession}>" for accession in IDS
    )
    query = (
        "PREFIX d: <https://purl.dsmz.de/schema/>\n"
        "SELECT ?id ?enzyme WHERE {\n"
        f"  VALUES ?id {{ {values} }}\n"
        "  ?enzyme d:hasIdentifier ?id .\n"
        "} ORDER BY ?id"
    )
    response = requests.get(
        ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    hits = {
        row["id"]["value"].rsplit("/", 1)[-1]: row["enzyme"]["value"]
        for row in payload["results"]["bindings"]
    }

    output = Path(__file__).with_name("brenda_sparql_identifier_audit.csv")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "uniprot_accession",
                "sample_accession",
                "sample_observations",
                "sparql_entity_uri",
                "query_status",
                "scope_note",
            ],
        )
        writer.writeheader()
        for accession, metadata in IDS.items():
            writer.writerow(
                {
                    "uniprot_accession": accession,
                    **metadata,
                    "sparql_entity_uri": hits.get(accession, ""),
                    "query_status": "entity_hit" if accession in hits else "no_graph_hit",
                    "scope_note": (
                        "Public prototype graph exact hasIdentifier query; no-hit is not a classic-"
                        "BRENDA or assay-outcome non-match"
                    ),
                }
            )
    print(f"Wrote {output}; {len(hits)}/{len(IDS)} exact graph identifier hits")


if __name__ == "__main__":
    main()
