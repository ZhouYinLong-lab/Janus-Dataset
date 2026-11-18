"""Audit BRENDA species-level EC coverage for taxa represented in the pilot.

The output includes full EC lists for comparison with each GenBank protein's own
EC annotation. Species+EC presence is not an exact enzyme-accession or assay-row
match. Non-binomial source labels are resolved from NCBI organism names when
possible, and otherwise left unresolved. Requests are serialized with a delay.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]
SAMPLE = Path(__file__).resolve().parent / "gh1_nims_negative_sample_100.csv"
NCBI_CROSSWALK = Path(__file__).resolve().parent / "ncbi_accession_crosswalk.csv"
OUTPUT = Path(__file__).resolve().parent / "brenda_species_ec_crosswalk.csv"
TARGET_EC = "3.2.1.21"
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


def parse_record(record: str) -> tuple[str | None, str]:
    if not re.match(r"^[A-Z]{1,4}\d+\.\d+_", record):
        return None, "non-accession-labelled metagenomic/culture sample"
    suffix = record.split("_", 1)[1].replace("-=-", " ").replace("-", " ")
    tokens = suffix.split()
    if len(tokens) < 2 or tokens[1].lower() == "sp.":
        return None, "not a resolved binomial taxon"
    # The first two tokens give a conservative species-level query; isolate/strain
    # details remain in source_protein_label and are not discarded from the ledger.
    return " ".join(tokens[:2]), "binomial species-level query"


def binomial_from_organism(organism: str) -> str | None:
    tokens = organism.split()
    if len(tokens) < 2 or tokens[1].lower() == "sp.":
        return None
    return " ".join(tokens[:2])


def query_species(species: str) -> dict[str, str]:
    url = "https://brenda-enzymes.org/organism.php?organism=" + quote(species, safe="")
    request = Request(url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            status = str(response.status)
    except (HTTPError, URLError, TimeoutError) as error:
        return {"brenda_url": url, "http_status": "error", "page_sha256": "",
                "normalized_text_sha256": "", "ec_count": "", "target_ec_present": "",
                "brenda_ec_numbers": "", "page_entity_confirmed": "", "query_error": str(error)}

    parser = VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    text = " ".join(parser.parts)
    normalized = re.sub(r"\s+", " ", text).strip()
    ec_numbers = sorted(set(re.findall(
        r"\bEC\s+(\d+\.\d+\.\d+\.(?:\d+|B\d+))\b", text)))
    entity_confirmed = species.casefold() in normalized.casefold()
    return {
        "brenda_url": url,
        "http_status": status,
        "page_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "normalized_text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper(),
        "ec_count": str(len(ec_numbers)),
        "brenda_ec_numbers": ";".join(ec_numbers),
        "target_ec_present": str(TARGET_EC in ec_numbers).lower(),
        "page_entity_confirmed": str(entity_confirmed).lower(),
        "query_error": "",
    }


def main() -> None:
    records = list(csv.DictReader(SAMPLE.open(encoding="utf-8-sig", newline="")))
    ncbi_records = list(csv.DictReader(NCBI_CROSSWALK.open(encoding="utf-8-sig", newline="")))
    ncbi_by_label = {row["source_protein_label"]: row for row in ncbi_records}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    unresolved: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        species, reason = parse_record(record["protein_accession_species"])
        mapping_source = "source-label binomial"
        if species is None:
            ncbi_record = ncbi_by_label.get(record["protein_accession_species"], {})
            species = binomial_from_organism(ncbi_record.get("ncbi_organism", ""))
            if species:
                mapping_source = "NCBI GenBank organism binomial"
        if species is None:
            unresolved[record["protein_accession_species"]].append(record)
        else:
            enriched_record = dict(record)
            enriched_record["_taxon_mapping_source"] = mapping_source
            grouped[species].append(enriched_record)

    output_rows: list[dict[str, str]] = []
    for index, (species, sample_records) in enumerate(sorted(grouped.items())):
        if index:
            time.sleep(DELAY_SECONDS)
        result = query_species(species)
        protein_labels = sorted({r["protein_accession_species"] for r in sample_records})
        substrates = Counter(r["substrate"] for r in sample_records)
        output_rows.append({
            "source_protein_label": " | ".join(protein_labels),
            "organism_query": species,
            "taxon_mapping_status": "; ".join(sorted({r["_taxon_mapping_source"] for r in sample_records})) + "; species-level only",
            "sample_observations": str(len(sample_records)),
            "sample_substrates": "; ".join(f"{k}:{substrates[k]}" for k in sorted(substrates)),
            **result,
        })

    for protein_label, unresolved_records in sorted(unresolved.items()):
        reason = "non-accession label or no resolved binomial organism in source/NCBI"
        output_rows.append({
            "source_protein_label": protein_label,
            "organism_query": "",
            "taxon_mapping_status": reason,
            "sample_observations": str(len(unresolved_records)),
            "sample_substrates": "; ".join(sorted(Counter(r["substrate"] for r in unresolved_records))),
            "brenda_url": "",
            "http_status": "not queried",
            "page_sha256": "",
            "normalized_text_sha256": "",
            "ec_count": "",
            "brenda_ec_numbers": "",
            "target_ec_present": "",
            "page_entity_confirmed": "",
            "query_error": "",
        })

    fields = list(output_rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    queried = [row for row in output_rows if row["http_status"] not in {"error", "not queried"}]
    exact_page = [row for row in queried if row["page_entity_confirmed"] == "true"]
    target_present = [row for row in exact_page if row["target_ec_present"] == "true"]
    target_absent = [row for row in exact_page if row["target_ec_present"] == "false"]
    print(f"sample_observations={len(records)}")
    print(f"unique_resolved_binomial_queries={len(grouped)}")
    print(f"queries_with_confirmed_page_entity={len(exact_page)}")
    print(f"species_pages_with_EC_{TARGET_EC}={len(target_present)}")
    print(f"species_pages_without_EC_{TARGET_EC}={len(target_absent)}")
    print(f"unresolved_protein_labels={len(unresolved)}")
    print(f"unresolved_sample_observations={sum(map(len, unresolved.values()))}")
    print(f"crosswalk_csv={OUTPUT}")
    print("interpretation=species-level EC lists support per-accession annotation checks; not exact protein or substrate-record coverage")


if __name__ == "__main__":
    main()
