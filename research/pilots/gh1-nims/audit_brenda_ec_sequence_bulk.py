"""Exact-sequence screen of all NCBI GH1 pilot proteins against sampled BRENDA EC FASTA sets.

This checks BRENDA protein-entity representation, not activity/negative-record
coverage. The BRENDA FASTA sets are limited to EC numbers explicitly present in
the pilot crosswalk. Exact sequence identity is used deliberately; a non-match
does not exclude other EC classes, fragments, mature-chain processing, or
alternative annotations.
"""

from __future__ import annotations

import csv
import re
import time
from collections import defaultdict
from pathlib import Path

import requests
from requests.exceptions import RequestException


ROOT = Path(__file__).resolve().parent
NCBI_CROSSWALK = ROOT / "ncbi_accession_crosswalk.csv"
BRENDA_SEQUENCES = "https://www.brenda-enzymes.org/sequences.php"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def get_with_retries(session: requests.Session, url: str, *, params: dict[str, str], timeout: int) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except RequestException as exc:
            last_error = exc
            if attempt == 3:
                break
            delay = attempt * 4
            print(f"Request failed (attempt {attempt}/3); retrying in {delay}s: {exc}")
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def parse_fasta(text: str) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    header: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, header.split("|", 1)[0].lstrip(">"), "".join(chunks)))
            header = line
            chunks = []
        elif header is not None:
            chunks.append(re.sub(r"\s+", "", line))
    if header is not None:
        records.append((header, header.split("|", 1)[0].lstrip(">"), "".join(chunks)))
    return records


def main() -> None:
    with NCBI_CROSSWALK.open(encoding="utf-8-sig", newline="") as stream:
        sample_rows = list(csv.DictReader(stream))
    eligible = [row for row in sample_rows if row.get("ncbi_accession", "").strip()]
    ec_numbers = sorted(
        {
            ec.strip()
            for row in eligible
            for ec in row["ncbi_ec_numbers"].split(";")
            if ec.strip()
        }
    )
    if not eligible or not ec_numbers:
        raise RuntimeError("No sample accessions or explicit EC annotations found in NCBI crosswalk")

    session = requests.Session()
    session.headers.update({"User-Agent": "Janus-Dataset research audit/1.0"})
    brenda_by_ec: dict[str, list[tuple[str, str, str]]] = {}
    for ec in ec_numbers:
        response = get_with_retries(
            session,
            BRENDA_SEQUENCES,
            params={"download": "allfasta", "ec": ec},
            timeout=180,
        )
        parsed = parse_fasta(response.text)
        if not parsed:
            raise RuntimeError(f"BRENDA returned no FASTA records for EC {ec}")
        brenda_by_ec[ec] = parsed
        print(f"BRENDA EC {ec}: {len(parsed)} sequences ({len(response.content):,} bytes)")
        time.sleep(0.5)

    records_by_seq: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for ec, records in brenda_by_ec.items():
        for header, accession, sequence in records:
            records_by_seq[sequence].append((ec, accession, header))

    output = ROOT / "brenda_ec_sequence_all_sample_audit.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "ncbi_accession",
            "sample_observation_count",
            "sample_substrates",
            "ncbi_ec_numbers",
            "ncbi_sequence_length_aa",
            "exact_brenda_sequence_match",
            "exact_match_same_ec",
            "matching_brenda_entries",
            "scope_note",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(eligible):
            accession = row["ncbi_accession"].strip()
            response = get_with_retries(
                session,
                NCBI_EFETCH,
                params={"db": "protein", "id": accession, "rettype": "fasta", "retmode": "text"},
                timeout=90,
            )
            ncbi_records = parse_fasta(response.text)
            if len(ncbi_records) != 1 or not ncbi_records[0][2]:
                raise RuntimeError(f"Could not retrieve one protein FASTA for {accession}")
            sequence = ncbi_records[0][2]
            matches = records_by_seq.get(sequence, [])
            sample_ecs = {ec.strip() for ec in row["ncbi_ec_numbers"].split(";") if ec.strip()}
            exact_same_ec = [entry for entry in matches if entry[0] in sample_ecs]
            match_text = " || ".join(f"EC {ec} | {uniprot} | {header}" for ec, uniprot, header in matches)
            writer.writerow(
                {
                    "ncbi_accession": accession,
                    "sample_observation_count": row["sample_observation_count"],
                    "sample_substrates": row["sample_substrates"],
                    "ncbi_ec_numbers": row["ncbi_ec_numbers"],
                    "ncbi_sequence_length_aa": len(sequence),
                    "exact_brenda_sequence_match": str(bool(matches)).lower(),
                    "exact_match_same_ec": str(bool(exact_same_ec)).lower() if sample_ecs else "not_applicable",
                    "matching_brenda_entries": match_text,
                    "scope_note": (
                        "Exact protein-entity match only; not evidence that the sample assay outcome is curated"
                    ),
                }
            )
            print(f"NCBI {accession}: {len(sequence)} aa; exact BRENDA matches={len(matches)}; same-EC={len(exact_same_ec)}")
            time.sleep(0.4)

    print(f"Wrote {output}; {len(eligible)} NCBI proteins compared with {len(ec_numbers)} BRENDA EC FASTA sets")


if __name__ == "__main__":
    main()
