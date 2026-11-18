"""Query BRENDA's public amino-acid sequence index by exact UniProt accession.

This establishes sequence-index presence only. It does not establish that BRENDA
contains a measured substrate result or the Heins NIMS negative observation.
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup


HERE = Path(__file__).resolve().parent
INPUT = HERE / "uniprot_brenda_accession_audit.csv"
NCBI_INPUT = HERE / "ncbi_accession_crosswalk.csv"
OUTPUT = HERE / "brenda_sequence_index_hits.csv"
BASE_URL = "https://www.brenda-enzymes.org/sequences.php"
DELAY_SECONDS = 1.1


def query_accession(accession: str) -> dict[str, str]:
    params = {
        "f[stype_accession_code]": "1",
        "f[accession_code]": accession,
        "f[limit_range]": "100",
        "Search": "search",
    }
    url = BASE_URL + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=45) as response:
            html = response.read().decode("utf-8", errors="replace")
            status = str(response.status)
    except Exception as error:  # preserve endpoint failures as unresolved rows
        return {"query_accession": accession, "query_status": "error", "query_url": url,
                "exact_hit": "", "result_count": "", "enzyme_ec": "", "recommended_name": "",
                "organism": "", "sequence_length": "", "molecular_weight_da": "",
                "source": "", "sequence_detail_id": "", "error": str(error)}

    count_match = re.search(r"of\s*<span class=\"red bold\">(\d+)</span>", html)
    soup = BeautifulSoup(html, "html.parser")
    matching: list[dict[str, str]] = []
    for row_element in soup.select("div.row"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
                 for cell in row_element.select(":scope > div.cell")]
        joined = " | ".join(cells)
        if accession.casefold() not in joined.casefold():
            continue
        detail_anchor = row_element.select_one('a[href*="sequences.php?ID="]')
        detail = re.search(r"ID=(\d+)", detail_anchor.get("href", "")) if detail_anchor else None
        matching.append({
            "enzyme_ec": cells[0] if len(cells) > 0 else "",
            "recommended_name_and_organism": cells[1] if len(cells) > 1 else "",
            "accession_cell": cells[2] if len(cells) > 2 else "",
            "length_and_helices": cells[3] if len(cells) > 3 else "",
            "molecular_weight_da": cells[4] if len(cells) > 4 else "",
            "source": cells[5] if len(cells) > 5 else "",
            "sequence_detail_id": detail.group(1) if detail else "",
        })

    hits = matching or [{}]
    return {
        "query_accession": accession,
        "query_status": status,
        "query_url": url,
        "exact_hit": str(bool(matching)).lower(),
        "result_count": count_match.group(1) if count_match else "",
        "enzyme_ec": "; ".join(hit.get("enzyme_ec", "") for hit in matching),
        "recommended_name": "; ".join(hit.get("recommended_name_and_organism", "") for hit in matching),
        "organism": "; ".join(hit.get("recommended_name_and_organism", "") for hit in matching),
        "sequence_length": "; ".join(hit.get("length_and_helices", "") for hit in matching),
        "molecular_weight_da": "; ".join(hit.get("molecular_weight_da", "") for hit in matching),
        "source": "; ".join(hit.get("source", "") for hit in matching),
        "sequence_detail_id": "; ".join(hit.get("sequence_detail_id", "") for hit in matching),
        "error": "",
    }


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    with NCBI_INPUT.open(encoding="utf-8-sig", newline="") as handle:
        ncbi_rows = list(csv.DictReader(handle))
    ncbi_by_accession = {row["ncbi_accession"]: row for row in ncbi_rows}
    accessions = list(dict.fromkeys(row["ncbi_uniprot_cross_reference"] for row in source_rows))
    results: list[dict[str, str]] = []
    for index, accession in enumerate(accessions):
        if index:
            time.sleep(DELAY_SECONDS)
        source_matches = [row for row in source_rows if row["ncbi_uniprot_cross_reference"] == accession]
        query = query_accession(accession)
        query["sample_ncbi_accessions"] = ";".join(row["ncbi_accession"] for row in source_matches)
        query["sample_source_labels"] = " | ".join(row["sample_protein_label"] for row in source_matches)
        paired_ncbi = [ncbi_by_accession[row["ncbi_accession"]] for row in source_matches
                       if row["ncbi_accession"] in ncbi_by_accession]
        query["sample_ec_annotations"] = ";".join(sorted({
            ec for row in paired_ncbi for ec in row.get("ncbi_ec_numbers", "").split(";") if ec
        }))
        query["sample_observation_count"] = str(sum(
            int(row.get("sample_observation_count", "0") or "0") for row in paired_ncbi
        ))
        query["matching_result_rows"] = str(sum(
            1 for row in query.get("exact_hit", "").split(";") if row == "true"
        ))
        results.append(query)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"unique_uniprot_accessions_queried={len(accessions)}")
    print(f"exact_sequence_index_hits={sum(r['exact_hit'] == 'true' for r in results)}")
    print(f"output={OUTPUT}")
    print("interpretation=exact sequence-index record, not measured assay or negative observation coverage")


if __name__ == "__main__":
    main()
