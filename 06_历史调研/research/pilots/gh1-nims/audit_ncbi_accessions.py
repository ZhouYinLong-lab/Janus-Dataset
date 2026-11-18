"""Retrieve GenBank protein definitions for the extracted GH1 sample accessions.

This provides an identity/function check for the species-level BRENDA pilot. It
does not itself map records to UniProt or establish exact BRENDA membership.
NCBI E-utilities requests are serialized below its unauthenticated rate limit.
"""

from __future__ import annotations

import csv
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "gh1_nims_negative_sample_100.csv"
OUTPUT = HERE / "ncbi_accession_crosswalk.csv"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DELAY_SECONDS = 0.4


def accession_of(label: str) -> str | None:
    match = re.match(r"^([A-Z]{1,4}\d+\.\d+)_", label)
    return match.group(1) if match else None


def query_record(accession: str) -> dict[str, str]:
    params = urlencode({"db": "protein", "id": accession, "rettype": "gb", "retmode": "text"})
    request = Request(f"{NCBI_URL}?{params}", headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=25) as response:
            text = response.read().decode("utf-8", errors="replace")
            status = str(response.status)
    except (HTTPError, URLError, TimeoutError) as error:
        return {"ncbi_status": "error", "ncbi_definition": "", "ncbi_organism": "",
                "ncbi_ec_numbers": "", "ncbi_db_xrefs": "", "ncbi_error": str(error)}

    lines = text.splitlines()
    definition_parts: list[str] = []
    in_definition = False
    for line in lines:
        if line.startswith("DEFINITION"):
            in_definition = True
            definition_parts.append(line[len("DEFINITION"):].strip())
        elif in_definition and line.startswith("            "):
            definition_parts.append(line.strip())
        elif in_definition:
            break

    organism_match = re.search(r"^\s+ORGANISM\s+(.+)$", text, flags=re.MULTILINE)
    organism = organism_match.group(1).strip() if organism_match else ""
    ec_numbers = sorted(set(re.findall(r'/EC_number="([0-9.]+)"', text)))
    db_xrefs = sorted(set(re.findall(r'/db_xref="([^"]+)"', text)))
    return {
        "ncbi_status": status,
        "ncbi_definition": " ".join(definition_parts),
        "ncbi_organism": organism,
        "ncbi_ec_numbers": ";".join(ec_numbers),
        "ncbi_db_xrefs": ";".join(db_xrefs),
        "ncbi_error": "",
    }


def main() -> None:
    sample = list(csv.DictReader(SAMPLE.open(encoding="utf-8-sig", newline="")))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in sample:
        accession = accession_of(row["protein_accession_species"])
        if accession:
            grouped[accession].append(row)

    output_rows = []
    for index, (accession, records) in enumerate(sorted(grouped.items())):
        if index:
            time.sleep(DELAY_SECONDS)
        label = records[0]["protein_accession_species"]
        substrates = Counter(row["substrate"] for row in records)
        ncbi = query_record(accession)
        output_rows.append({
            "source_protein_label": label,
            "ncbi_accession": accession,
            "sample_observation_count": str(len(records)),
            "sample_substrates": "; ".join(f"{key}:{substrates[key]}" for key in sorted(substrates)),
            **ncbi,
        })

    fieldnames = list(output_rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    annotated = Counter(row["ncbi_definition"].split(" [", 1)[0]
                        for row in output_rows if row["ncbi_definition"])
    print(f"sample_observations={len(sample)}")
    print(f"unique_genbank_protein_accessions={len(grouped)}")
    print(f"NCBI_successful_records={sum(row['ncbi_status'] == '200' for row in output_rows)}")
    print(f"NCBI_records_with_EC_number={sum(bool(row['ncbi_ec_numbers']) for row in output_rows)}")
    print(f"NCBI_definition_categories={dict(annotated)}")
    print(f"crosswalk_csv={OUTPUT}")
    print("interpretation=GenBank definition/organism labels aid identity review; no BRENDA sequence mapping is asserted")


if __name__ == "__main__":
    main()
