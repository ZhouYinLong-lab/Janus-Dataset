"""Render BRENDA enzyme tables for every exact sequence entry in the core pool.

This is a bounded EC/organism/UniProt view audit. A zero count is not a global
claim that the source paper or every related negative statement is absent.
Rows are checkpointed after each page so the audit can resume safely.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup


HERE = Path(__file__).resolve().parent
INPUT = HERE / "brenda_ec_sequence_core96_audit.csv"
OUTPUT = HERE / "brenda_core96_exact_activity_views.csv"
BASE_URL = "https://www.brenda-enzymes.org/enzyme.php"
FIELDS = [
    "uniprot_accession",
    "ec_number",
    "organism",
    "sample_accessions",
    "core_pool_below_background_cells",
    "filtered_page_identity_confirmed",
    "rendered_page_title",
    "rendered_page_heading",
    "substrate_product_count",
    "natural_substrate_count",
    "reference_entry_count",
    "query_status",
    "page_url",
    "scope_note",
]


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


def targets_from_audit() -> list[dict[str, str]]:
    by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if row["exact_brenda_sequence_match_any_ec"] != "true":
            continue
        for block in row["matching_brenda_entries"].split(" || "):
            parts = block.split(" | ", 2)
            if len(parts) != 3:
                continue
            ec = parts[0].removeprefix("EC ").strip()
            uniprot = parts[1].strip()
            columns = parts[2].lstrip(">").split("|")
            if len(columns) < 5:
                continue
            organism = columns[3].strip()
            key = (uniprot, ec, organism)
            entry = by_key.setdefault(
                key,
                {
                    "uniprot_accession": uniprot,
                    "ec_number": ec,
                    "organism": organism,
                    "sample_accessions": set(),
                    "core_pool_below_background_cells": 0,
                },
            )
            entry["sample_accessions"].add(row["ncbi_accession"])
            entry["core_pool_below_background_cells"] += int(row["core_pool_below_background_cells"])
    targets = []
    for entry in by_key.values():
        entry["sample_accessions"] = ";".join(sorted(entry["sample_accessions"]))
        entry["core_pool_below_background_cells"] = str(entry["core_pool_below_background_cells"])
        targets.append({key: str(value) for key, value in entry.items()})
    return sorted(targets, key=lambda row: (row["ec_number"], row["uniprot_accession"], row["organism"]))


def page_url(target: dict[str, str]) -> str:
    params = {
        "ecno": target["ec_number"],
        "organism[]": target["organism"],
        "showtm": "0",
        "UniProtAcc": target["uniprot_accession"],
    }
    return f"{BASE_URL}?{urlencode(params)}"


def run_page(browser: str, target: dict[str, str]) -> str:
    url = page_url(target)
    with tempfile.TemporaryDirectory(prefix="brenda-core96-") as profile:
        result = subprocess.run(
            [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--disable-background-networking",
                "--virtual-time-budget=12000",
                "--dump-dom",
                f"--user-data-dir={profile}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=75,
        )
    if result.returncode != 0 and "<html" not in result.stdout.lower():
        raise RuntimeError(result.stderr[-600:] or f"Browser failed for {url}")
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
        "query_status": "ok" if verified else "identity_unconfirmed",
        "page_url": page_url(target),
        "scope_note": "Exact EC/organism/UniProt activity-table view only; not global literature or commentary absence",
    }


def checkpoint(rows: list[dict[str, str]]) -> None:
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    browser = find_browser()
    targets = targets_from_audit()
    completed: dict[tuple[str, str, str], dict[str, str]] = {}
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("query_status") == "ok":
                    completed[(row["uniprot_accession"], row["ec_number"], row["organism"])] = row

    results = list(completed.values())
    for index, target in enumerate(targets, start=1):
        key = (target["uniprot_accession"], target["ec_number"], target["organism"])
        if key in completed:
            continue
        try:
            row = summarize(run_page(browser, target), target)
        except Exception as error:
            row = {
                **target,
                "filtered_page_identity_confirmed": "",
                "rendered_page_title": "",
                "rendered_page_heading": "",
                "substrate_product_count": "",
                "natural_substrate_count": "",
                "reference_entry_count": "",
                "query_status": f"error:{type(error).__name__}:{error}",
                "page_url": page_url(target),
                "scope_note": "Query failed; not interpreted as no match",
            }
        results.append(row)
        checkpoint(results)
        print(
            f"[{index}/{len(targets)}] {target['uniprot_accession']} EC {target['ec_number']} "
            f"identity={row['filtered_page_identity_confirmed']} "
            f"tables={row['substrate_product_count']}/{row['natural_substrate_count']}/{row['reference_entry_count']}"
        )
    print(f"unique_BRENDA_entries={len(targets)}")
    print(f"successful_identity_confirmations={sum(row['query_status'] == 'ok' for row in results)}")
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
