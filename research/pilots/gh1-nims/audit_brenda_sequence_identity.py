"""Compare exact BRENDA sequence-index records with sample GenBank proteins."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PAIRS = [
    ("CBL17177.1", "D4LC32", 22386123, 7),
    ("CAJ88232.1", "A0ACM7", 21664329, 1),
    ("AAT59229.1", "Q6HMK2", 24116899, 1),
    ("AAU43012.1", "Q65D52", 24101727, 4),
]
NCBI_FASTA = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BRENDA_PAGE = "https://www.brenda-enzymes.org/sequences.php"


def sequence_from_fasta(text: str) -> str:
    return "".join(line.strip() for line in text.splitlines() if line and not line.startswith(">"))


def sequence_from_brenda(html: str) -> str:
    page_text = BeautifulSoup(html, "html.parser").get_text("\n")
    section = page_text.split("General information:", 1)[1].split("Download this sequence", 1)[0]
    chunks = []
    for line in section.splitlines():
        # The final sequence row can contain only a few residues (e.g. "420 ARAG").
        match = re.match(r"\s*\d+\s+([A-Z ]+)\s*$", line)
        if match:
            chunks.append(re.sub(r"\s+", "", match.group(1)))
    if not chunks:
        raise ValueError("Could not parse amino-acid rows from BRENDA sequence page")
    return "".join(chunks)


def main() -> None:
    session = requests.Session()
    output = Path(__file__).with_name("brenda_sequence_identity_audit.csv")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "genbank_accession",
            "uniprot_accession",
            "brenda_sequence_id",
            "pilot_observations",
            "ncbi_length_aa",
            "brenda_length_aa",
            "exact_sequence_match",
            "interpretation",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for accession, uniprot, brenda_id, observations in PAIRS:
            ncbi_response = session.get(
                NCBI_FASTA,
                params={"db": "protein", "id": accession, "rettype": "fasta", "retmode": "text"},
                timeout=60,
            )
            ncbi_response.raise_for_status()
            brenda_response = session.get(
                BRENDA_PAGE,
                params={"ID": brenda_id},
                timeout=60,
            )
            brenda_response.raise_for_status()
            ncbi_sequence = sequence_from_fasta(ncbi_response.text)
            brenda_sequence = sequence_from_brenda(brenda_response.text)
            exact = ncbi_sequence == brenda_sequence
            writer.writerow(
                {
                    "genbank_accession": accession,
                    "uniprot_accession": uniprot,
                    "brenda_sequence_id": brenda_id,
                    "pilot_observations": observations,
                    "ncbi_length_aa": len(ncbi_sequence),
                    "brenda_length_aa": len(brenda_sequence),
                    "exact_sequence_match": str(exact).lower(),
                    "interpretation": (
                        "Exact protein identity verified; this still does not establish assay-row coverage"
                        if exact
                        else "Sequence mismatch; investigate accession/version or sequence processing"
                    ),
                }
            )
            print(f"{accession} / {uniprot}: NCBI={len(ncbi_sequence)} aa, BRENDA={len(brenda_sequence)} aa, exact={exact}")


if __name__ == "__main__":
    main()
