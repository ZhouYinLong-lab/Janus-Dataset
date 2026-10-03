"""Check a superseded GenBank protein accession against its current BRENDA entry.

The script keeps the historical sample sequence separate from the current
replacement sequence; only the latter is expected to match current BRENDA.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests

import audit_brenda_js_tables_bulk as brenda_pages
import audit_brenda_sequence_identity as identity
import query_brenda_sequence_accessions as sequence_index


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "brenda_accession_version_audit.csv"
SAMPLE_ACCESSION = "ABV62413.1"
CURRENT_UNIPROT = "A8FDU6"
CURRENT_EC = "3.2.1.86"
CURRENT_ORGANISM = "Bacillus pumilus (strain SAFR-032)"
OBSERVATIONS = 1
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_text(session: requests.Session, accession: str, rettype: str) -> str:
    response = session.get(
        EUTILS,
        params={"db": "protein", "id": accession, "rettype": rettype, "retmode": "text"},
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def main() -> None:
    session = requests.Session()
    old_record = fetch_text(session, SAMPLE_ACCESSION, "gb")
    replacement = re.search(r"replaced by\s+(ABV\d+\.\d+)", old_record, re.I)
    if not replacement:
        raise RuntimeError(f"No replacement accession found for {SAMPLE_ACCESSION}")
    replacement_accession = replacement.group(1)

    old_sequence = identity.sequence_from_fasta(fetch_text(session, SAMPLE_ACCESSION, "fasta"))
    new_sequence = identity.sequence_from_fasta(fetch_text(session, replacement_accession, "fasta"))
    uniprot_response = session.get(
        f"https://rest.uniprot.org/uniprotkb/{CURRENT_UNIPROT}.fasta", timeout=60
    )
    uniprot_response.raise_for_status()
    uniprot_sequence = identity.sequence_from_fasta(uniprot_response.text)

    index_row = sequence_index.query_accession(CURRENT_UNIPROT)
    if index_row["exact_hit"] != "true":
        raise RuntimeError(f"Expected BRENDA sequence-index hit not found: {index_row}")
    brenda_id = index_row["sequence_detail_id"]
    detail_response = session.get(
        "https://www.brenda-enzymes.org/sequences.php", params={"ID": brenda_id}, timeout=60
    )
    detail_response.raise_for_status()
    brenda_sequence = identity.sequence_from_brenda(detail_response.text)

    target = {
        "uniprot_accession": CURRENT_UNIPROT,
        "ec_number": CURRENT_EC,
        "organism": CURRENT_ORGANISM,
        "sample_accessions": SAMPLE_ACCESSION,
        "sample_observation_count": str(OBSERVATIONS),
    }
    rendered = brenda_pages.summarize(
        brenda_pages.run_page(brenda_pages.find_browser(), target), target
    )

    row = {
        "sample_accession": SAMPLE_ACCESSION,
        "replacement_accession": replacement_accession,
        "sample_sequence_length_aa": len(old_sequence),
        "replacement_sequence_length_aa": len(new_sequence),
        "sample_equals_replacement_sequence": str(old_sequence == new_sequence).lower(),
        "replacement_uniprot_accession": CURRENT_UNIPROT,
        "replacement_equals_uniprot_sequence": str(new_sequence == uniprot_sequence).lower(),
        "brenda_sequence_id": brenda_id,
        "replacement_equals_brenda_sequence": str(new_sequence == brenda_sequence).lower(),
        "sample_observation_count": OBSERVATIONS,
        **rendered,
        "interpretation": (
            "Current replacement/locus candidate only; the 2014 sample accession version is not the current exact sequence. "
            "Do not add its observation to exact-sequence BRENDA coverage or infer assay coverage."
        ),
    }
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    print(f"replacement={replacement_accession}; sample_len={len(old_sequence)}; current_len={len(new_sequence)}")
    print(f"current_uniprot={CURRENT_UNIPROT}; replacement_matches_uniprot={new_sequence == uniprot_sequence}")
    print(f"brenda_sequence_id={brenda_id}; replacement_matches_brenda={new_sequence == brenda_sequence}")
    print(f"activity_page={rendered['substrate_product_count']}/{rendered['natural_substrate_count']}/{rendered['reference_entry_count']}")
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
