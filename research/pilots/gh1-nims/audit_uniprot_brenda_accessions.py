"""Check NCBI-recorded UniProt cross-references against current BRENDA pages.

Only accessions explicitly cross-referenced by the GenBank records are queried.
Page-level UniProt presence is not treated as proof of the NIMS assay row.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
NCBI = HERE / "ncbi_accession_crosswalk.csv"
OUTPUT = HERE / "uniprot_brenda_accession_audit.csv"
DELAY_SECONDS = 1.1


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def fetch(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return str(response.status), response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as error:
        return "error", str(error)


def parse_uniprot(accession: str) -> dict[str, str]:
    status, text = fetch(f"https://rest.uniprot.org/uniprotkb/{quote(accession)}.txt")
    values = {"uniprot_status": status, "uniprot_accession": accession,
              "uniprot_protein_name": "", "uniprot_organism": "",
              "uniprot_ec_numbers": "", "uniprot_sequence_length": "",
              "uniprot_sequence_sha256": ""}
    if status != "200":
        return values
    if not text.strip():
        values["uniprot_status"] = "empty response body"
        return values
    accession_line = re.search(r"^AC\s+(.+?);", text, flags=re.MULTILINE)
    values["uniprot_accession"] = accession_line.group(1) if accession_line else accession
    names = re.findall(r"^DE\s+.*?Full=(.+?);", text, flags=re.MULTILINE)
    values["uniprot_protein_name"] = "; ".join(dict.fromkeys(names))
    organism = re.search(r"^OS\s+(.+?)(?:\.|$)", text, flags=re.MULTILINE)
    values["uniprot_organism"] = organism.group(1).strip() if organism else ""
    values["uniprot_ec_numbers"] = ";".join(sorted(set(re.findall(r"^DE\s+\s+EC=(.+?);", text, flags=re.MULTILINE))))
    sequence_match = re.search(r"^SQ\s+SEQUENCE\s+(\d+) AA;.*?\n(.*?)(?=^//)", text, flags=re.MULTILINE | re.DOTALL)
    if sequence_match:
        sequence = re.sub(r"[^A-Z]", "", sequence_match.group(2).upper())
        values["uniprot_sequence_length"] = sequence_match.group(1)
        values["uniprot_sequence_sha256"] = hashlib.sha256(sequence.encode()).hexdigest().upper()
    return values


def main() -> None:
    records = list(csv.DictReader(NCBI.open(encoding="utf-8-sig", newline="")))
    candidates: list[dict[str, str]] = []
    for record in records:
        xrefs = re.findall(r"UniProtKB/(?:TrEMBL|Swiss-Prot):([A-Z0-9]+)", record.get("ncbi_db_xrefs", ""))
        for uniprot in xrefs:
            organism_tokens = record.get("ncbi_organism", "").split()
            species = " ".join(organism_tokens[:2])
            candidates.append({**record, "uniprot_candidate": uniprot, "species": species})

    output: list[dict[str, str]] = []
    for index, row in enumerate(candidates):
        if index:
            time.sleep(DELAY_SECONDS)
        uniprot = parse_uniprot(row["uniprot_candidate"])
        brenda_url = "https://brenda-enzymes.org/organism.php?organism=" + quote(row["species"], safe="")
        brenda_status, brenda_html = fetch(brenda_url)
        parser = VisibleText()
        if brenda_status == "200":
            parser.feed(brenda_html)
            brenda_text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        else:
            brenda_text = ""
        output.append({
            "ncbi_accession": row["ncbi_accession"],
            "sample_protein_label": row["source_protein_label"],
            "ncbi_organism": row["ncbi_organism"],
            "ncbi_definition": row["ncbi_definition"],
            "ncbi_ec_numbers": row["ncbi_ec_numbers"],
            "ncbi_uniprot_cross_reference": row["uniprot_candidate"],
            **uniprot,
            "brenda_species_url": brenda_url,
            "brenda_status": brenda_status,
            "uniprot_accession_visible_on_brenda_species_page": str(row["uniprot_candidate"] in brenda_text).lower(),
            "interpretation": "exact cross-reference recorded by NCBI; page-level presence is not assay-row coverage",
        })

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(output[0]) if output else []
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(f"NCBI_UniProt_cross_references={len(candidates)}")
    print(f"UniProt_records_retrieved={sum(row['uniprot_status'] == '200' for row in output)}")
    print(f"UniProt_ids_visible_on_BRENDA_species_page={sum(row['uniprot_accession_visible_on_brenda_species_page'] == 'true' for row in output)}")
    print(f"output={OUTPUT}")
    print("interpretation=UniProt accession link is exact as recorded in GenBank; BRENDA visibility still does not establish assay-row coverage")


if __name__ == "__main__":
    main()
