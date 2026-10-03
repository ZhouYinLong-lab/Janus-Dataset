"""Compare every pilot GenBank protein sequence to BRENDA's exact sequence index.

This is a protein-entity coverage audit, not an assay-result or negative-observation
coverage audit. NCBI and BRENDA requests are serialized to avoid overloading either
public service. Exact matching uses BRENDA's advertised sequence-search mode.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


HERE = Path(__file__).resolve().parent
NCBI_CROSSWALK = HERE / "ncbi_accession_crosswalk.csv"
OUTPUT = HERE / "brenda_exact_sequence_coverage.csv"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BRENDA_URL = "https://www.brenda-enzymes.org/sequences.php"
NCBI_DELAY = 0.4
BRENDA_DELAY = 1.1


def fetch_ncbi_sequence(accession: str) -> tuple[str, str, str]:
    params = urlencode({"db": "protein", "id": accession, "rettype": "fasta", "retmode": "text"})
    url = f"{NCBI_URL}?{params}"
    request = Request(url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=35) as response:
            fasta = response.read().decode("utf-8", errors="replace")
            status = str(response.status)
    except Exception as error:
        return "error", "", str(error)
    sequence = "".join(line.strip() for line in fasta.splitlines() if line and not line.startswith(">"))
    if not sequence:
        return status, "", "empty FASTA response"
    return status, re.sub(r"[^A-Z]", "", sequence.upper()), ""


def query_brenda_exact_sequence(sequence: str) -> dict[str, str]:
    params = {
        "f[stype_seq]": "1",  # BRENDA's page: exact amino-acid sequence
        "f[seq]": sequence,
        "f[limit_range]": "100",
        "Search": "search",
    }
    query_url = BRENDA_URL + "?" + urlencode(params)
    request = Request(query_url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=50) as response:
            html = response.read().decode("utf-8", errors="replace")
            status = str(response.status)
    except Exception as error:
        return {"brenda_status": "error", "brenda_exact_hit": "", "brenda_result_count": "",
                "brenda_ec_numbers": "", "brenda_names_and_organisms": "",
                "brenda_accessions": "", "brenda_sequence_lengths": "", "brenda_sources": "",
                "brenda_detail_ids": "", "brenda_query_url": query_url, "brenda_error": str(error)}

    soup = BeautifulSoup(html, "html.parser")
    count_match = re.search(r"of\s*<span class=\"red bold\">(\d+)</span>", html)
    matched_rows: list[list[str]] = []
    for row in soup.select("div.row"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
                 for cell in row.select(":scope > div.cell")]
        # A correctly submitted exact search should return a sequence whose length
        # and digest agree with the query, but only the server-side exact mode is
        # available in the result table; row identity is retained for audit.
        if len(cells) >= 6:
            matched_rows.append(cells)
    detail_ids: list[str] = []
    for row in soup.select("div.row"):
        anchor = row.select_one('a[href*="sequences.php?ID="]')
        if anchor:
            match = re.search(r"ID=(\d+)", anchor.get("href", ""))
            if match:
                detail_ids.append(match.group(1))

    return {
        "brenda_status": status,
        "brenda_exact_hit": str(bool(matched_rows)).lower(),
        "brenda_result_count": count_match.group(1) if count_match else (str(len(matched_rows)) if status == "200" else ""),
        "brenda_ec_numbers": "; ".join(row[0] for row in matched_rows),
        "brenda_names_and_organisms": " | ".join(row[1] for row in matched_rows),
        "brenda_accessions": " | ".join(row[2] for row in matched_rows),
        "brenda_sequence_lengths": " | ".join(row[3] for row in matched_rows),
        "brenda_sources": " | ".join(row[5] for row in matched_rows),
        "brenda_detail_ids": "; ".join(detail_ids),
        "brenda_query_url": query_url,
        "brenda_error": "",
    }


def main() -> None:
    with NCBI_CROSSWALK.open(encoding="utf-8-sig", newline="") as handle:
        proteins = list(csv.DictReader(handle))
    results: list[dict[str, str]] = []
    for index, protein in enumerate(proteins):
        if index:
            time.sleep(NCBI_DELAY)
        accession = protein["ncbi_accession"]
        ncbi_status, sequence, ncbi_error = fetch_ncbi_sequence(accession)
        row = {
            "ncbi_accession": accession,
            "source_protein_label": protein["source_protein_label"],
            "sample_observation_count": protein["sample_observation_count"],
            "sample_substrates": protein["sample_substrates"],
            "ncbi_organism": protein["ncbi_organism"],
            "ncbi_definition": protein["ncbi_definition"],
            "ncbi_ec_numbers": protein["ncbi_ec_numbers"],
            "ncbi_sequence_status": ncbi_status,
            "ncbi_sequence_length": str(len(sequence)) if sequence else "",
            "ncbi_sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest().upper() if sequence else "",
            "ncbi_error": ncbi_error,
        }
        if sequence:
            if index:
                time.sleep(BRENDA_DELAY)
            row.update(query_brenda_exact_sequence(sequence))
        else:
            row.update({
                "brenda_status": "not queried", "brenda_exact_hit": "", "brenda_result_count": "",
                "brenda_ec_numbers": "", "brenda_names_and_organisms": "", "brenda_accessions": "",
                "brenda_sequence_lengths": "", "brenda_sources": "", "brenda_detail_ids": "",
                "brenda_query_url": "", "brenda_error": "NCBI sequence unavailable",
            })
        results.append(row)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    queried = [r for r in results if r["brenda_status"] == "200"]
    hits = [r for r in queried if r["brenda_exact_hit"] == "true"]
    hit_observations = sum(int(r["sample_observation_count"]) for r in hits)
    print(f"sample_accessions={len(proteins)}")
    print(f"NCBI_sequences_retrieved={sum(bool(r['ncbi_sequence_length']) for r in results)}")
    print(f"BRENDA_exact_sequence_queries={len(queried)}")
    print(f"BRENDA_exact_sequence_hits={len(hits)}")
    print(f"sample_observations_linked_to_sequence_hits={hit_observations}")
    print(f"output={OUTPUT}")
    print("interpretation=sequence-index coverage only; no assay/negative-observation coverage inferred")


if __name__ == "__main__":
    main()
