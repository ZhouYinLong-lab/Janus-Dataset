"""Find negative-wording candidates on BRENDA species pages for EC-annotated sample taxa.

Page-level phrase hits are discovery leads only: they may refer to another enzyme
or literature observation and must never be counted as coverage of a pilot row.
"""

from __future__ import annotations

import csv
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
NCBI = HERE / "ncbi_accession_crosswalk.csv"
BRENDA = HERE / "brenda_species_ec_crosswalk.csv"
OUTPUT = HERE / "brenda_negative_commentary_candidates.csv"
DELAY_SECONDS = 1.1
PATTERN = re.compile(
    r"no\s+(?:detectable\s+|significant\s+|measurable\s+)?(?:activity|hydrolysis|conversion|effect)"
    r"|(?:no|not|did not|does not|failed to)\s+(?:show\s+)?(?:hydroly[sz]|react|convert|cleave|inhibit)"
    r"|inactive|not active|without activity",
    re.IGNORECASE,
)


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


def fetch_text(species: str) -> tuple[str, str]:
    url = "https://brenda-enzymes.org/organism.php?organism=" + quote(species, safe="")
    request = Request(url, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            status = str(response.status)
    except (HTTPError, URLError, TimeoutError) as error:
        return "error", str(error)
    parser = VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return status, text


def main() -> None:
    ncbi_rows = list(csv.DictReader(NCBI.open(encoding="utf-8-sig", newline="")))
    brenda_rows = list(csv.DictReader(BRENDA.open(encoding="utf-8-sig", newline="")))
    confirmed = {
        row["organism_query"]: row for row in brenda_rows
        if row.get("organism_query") and row.get("page_entity_confirmed") == "true"
    }
    taxa: dict[str, list[dict[str, str]]] = {}
    for row in ncbi_rows:
        if not row.get("ncbi_ec_numbers"):
            continue
        organism = row.get("ncbi_organism", "").split()
        species = " ".join(organism[:2]) if len(organism) >= 2 else ""
        if species in confirmed:
            taxa.setdefault(species, []).append(row)

    output: list[dict[str, str]] = []
    for index, (species, accessions) in enumerate(sorted(taxa.items())):
        if index:
            time.sleep(DELAY_SECONDS)
        status, text = fetch_text(species)
        page = confirmed[species]
        matches = list(PATTERN.finditer(text)) if status == "200" else []
        seen: set[tuple[str, str]] = set()
        for match in matches:
            excerpt = text[max(0, match.start() - 150):min(len(text), match.end() + 180)]
            key = (match.group(0).casefold(), excerpt.casefold())
            if key in seen:
                continue
            seen.add(key)
            output.append({
                "organism_query": species,
                "sample_accessions_with_ec": ";".join(r["ncbi_accession"] for r in accessions),
                "sample_ec_numbers": ";".join(sorted({
                    ec for r in accessions for ec in r.get("ncbi_ec_numbers", "").split(";") if ec
                })),
                "sample_protein_definitions": " | ".join(r["ncbi_definition"] for r in accessions),
                "brenda_url": page["brenda_url"],
                "http_status": status,
                "phrase": match.group(0),
                "visible_text_excerpt": excerpt,
                "interpretation": "species-page discovery lead only; enzyme/accession and assay linkage unverified",
            })
        if status != "200" or not matches:
            output.append({
                "organism_query": species,
                "sample_accessions_with_ec": ";".join(r["ncbi_accession"] for r in accessions),
                "sample_ec_numbers": ";".join(sorted({
                    ec for r in accessions for ec in r.get("ncbi_ec_numbers", "").split(";") if ec
                })),
                "sample_protein_definitions": " | ".join(r["ncbi_definition"] for r in accessions),
                "brenda_url": page["brenda_url"],
                "http_status": status,
                "phrase": "",
                "visible_text_excerpt": "",
                "interpretation": "no phrase hit in fetched page text" if status == "200" else "fetch failed",
            })

    fields = list(output[0]) if output else []
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    hits = [row for row in output if row["phrase"]]
    print(f"confirmed_taxa_with_sample_EC={len(taxa)}")
    print(f"taxa_with_phrase_hits={len({row['organism_query'] for row in hits})}")
    print(f"deduplicated_phrase_candidates={len(hits)}")
    print(f"output={OUTPUT}")
    print("interpretation=discovery only; phrase hit is not exact sample-row coverage")


if __name__ == "__main__":
    main()
