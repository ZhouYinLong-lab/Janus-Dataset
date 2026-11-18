"""Run exact-protein BRENDA enzyme-table checks for bulk-sequence matches."""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "brenda_ec_sequence_all_sample_audit.csv"
OUTPUT = ROOT / "brenda_js_tables_bulk_audit.csv"
BASE_URL = "https://www.brenda-enzymes.org/enzyme.php"


def find_browser() -> str:
    for path in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ):
        if path.is_file():
            return str(path)
    for executable in ("msedge", "chrome"):
        if shutil.which(executable):
            return shutil.which(executable) or executable
    raise FileNotFoundError("Microsoft Edge or Google Chrome not found")


def parse_match_entries(value: str) -> list[dict[str, str]]:
    entries = []
    for block in value.split(" || "):
        parts = block.split(" | ", 2)
        if len(parts) != 3:
            continue
        ec = parts[0].removeprefix("EC ").strip()
        accession = parts[1].strip()
        header = parts[2].lstrip(">")
        columns = header.split("|")
        if len(columns) < 5:
            continue
        entries.append(
            {
                "uniprot_accession": accession,
                "ec_number": ec,
                "organism": columns[3].strip(),
            }
        )
    return entries


def input_records() -> list[dict[str, str]]:
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    targets: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        if row["exact_brenda_sequence_match"] != "true":
            continue
        for entry in parse_match_entries(row["matching_brenda_entries"]):
            key = (entry["uniprot_accession"], entry["ec_number"], entry["organism"])
            current = targets.setdefault(
                key,
                {
                    **entry,
                    "sample_accessions": row["ncbi_accession"],
                    "sample_observation_count": row["sample_observation_count"],
                },
            )
            if row["ncbi_accession"] not in current["sample_accessions"].split(";"):
                current["sample_accessions"] += ";" + row["ncbi_accession"]
                current["sample_observation_count"] = str(
                    int(current["sample_observation_count"]) + int(row["sample_observation_count"])
                )

    # One exact sequence hit lacked an NCBI /EC_number qualifier, but its
    # BRENDA sequence-index record was independently verified in prior work.
    targets[("A0ACM7", "3.2.1.21", "Streptomyces ambofaciens")] = {
        "uniprot_accession": "A0ACM7",
        "ec_number": "3.2.1.21",
        "organism": "Streptomyces ambofaciens",
        "sample_accessions": "CAJ88232.1",
        "sample_observation_count": "1",
    }
    # These two GenBank proteins were recovered through UniProt/UniParc
    # mapping after the four-EC FASTA comparison; their BRENDA sequence
    # details were independently verified against the original NCBI FASTA.
    targets[("Q6HMK2", "3.2.1.86", "Bacillus thuringiensis subsp. konkukian (strain 97-27)")] = {
        "uniprot_accession": "Q6HMK2",
        "ec_number": "3.2.1.86",
        "organism": "Bacillus thuringiensis subsp. konkukian (strain 97-27)",
        "sample_accessions": "AAT59229.1",
        "sample_observation_count": "1",
    }
    targets[("Q65D52", "3.2.1.86", "Bacillus licheniformis (strain ATCC 14580 / DSM 13 / JCM 2505 / CCUG 7422 / NBRC 12200 / NCIMB 9375 / NCTC 10341 / NRRL NRS-1264 / Gibson 46)")] = {
        "uniprot_accession": "Q65D52",
        "ec_number": "3.2.1.86",
        "organism": "Bacillus licheniformis (strain ATCC 14580 / DSM 13 / JCM 2505 / CCUG 7422 / NBRC 12200 / NCIMB 9375 / NCTC 10341 / NRRL NRS-1264 / Gibson 46)",
        "sample_accessions": "AAU43012.1",
        "sample_observation_count": "4",
    }
    return list(targets.values())


def run_page(browser: str, target: dict[str, str]) -> str:
    params = {
        "ecno": target["ec_number"],
        "organism[]": target["organism"],
        "showtm": "0",
        "UniProtAcc": target["uniprot_accession"],
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    with tempfile.TemporaryDirectory(prefix="brenda-bulk-headless-") as profile:
        result = subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--disable-background-networking",
                "--virtual-time-budget=15000",
                "--dump-dom",
                f"--user-data-dir={profile}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=75,
        )
    if result.returncode != 0 and "<html" not in result.stdout.lower():
        raise RuntimeError(f"Browser query failed for {url}: {result.stderr[-600:]}")
    return result.stdout


def summarize(html: str, target: dict[str, str]) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    header = soup.select_one("#flatheader h1")
    heading = header.get_text(" ", strip=True) if header else ""
    verified = all(
        value in title and value in heading
        for value in (target["uniprot_accession"], target["ec_number"], target["organism"])
    )
    def count(selector: str) -> str:
        node = soup.select_one(selector)
        return node.get_text(" ", strip=True) if node else "not exposed"

    return {
        **target,
        "filtered_page_identity_confirmed": str(verified).lower(),
        "rendered_page_title": title,
        "rendered_page_heading": heading,
        "substrate_product_count": count("#nav37 .naventrnr"),
        "natural_substrate_count": count("#nav17 .naventrnr"),
        "reference_entry_count": count("#tab30_nav .red.bold"),
        "scope_note": "Exact BRENDA EC/organism/UniProt view only; not a global literature-absence claim",
    }


def main() -> None:
    browser = find_browser()
    targets = input_records()
    fields = [
        "uniprot_accession",
        "ec_number",
        "organism",
        "sample_accessions",
        "sample_observation_count",
        "filtered_page_identity_confirmed",
        "rendered_page_title",
        "rendered_page_heading",
        "substrate_product_count",
        "natural_substrate_count",
        "reference_entry_count",
        "scope_note",
    ]
    results = []
    for index, target in enumerate(targets, start=1):
        row = summarize(run_page(browser, target), target)
        results.append(row)
        print(
            f"[{index}/{len(targets)}] {target['uniprot_accession']} {target['ec_number']} "
            f"identity={row['filtered_page_identity_confirmed']} "
            f"substrates={row['substrate_product_count']} refs={row['reference_entry_count']}"
        )
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {OUTPUT}; {len(results)} exact BRENDA protein views checked")


if __name__ == "__main__":
    main()
