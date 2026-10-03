"""Read BRENDA's filtered enzyme tables after client-side JavaScript runs.

This records what the public EC/organism/UniProt-filtered page exposes. A zero
count is scoped to that filtered BRENDA page, not to all possible records or
the source literature.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup


CASES = [
    {
        "genbank_accession": "CBL17177.1",
        "uniprot_accession": "D4LC32",
        "organism": "Ruminococcus champanellensis",
        "pilot_observations": 7,
    },
    {
        "genbank_accession": "CAJ88232.1",
        "uniprot_accession": "A0ACM7",
        "organism": "Streptomyces ambofaciens",
        "pilot_observations": 1,
    },
]
BASE_URL = "https://www.brenda-enzymes.org/enzyme.php"


def find_edge() -> str:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for name in ("msedge", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("Microsoft Edge or Google Chrome executable not found")


def fetch_rendered_dom(browser: str, case: dict[str, object]) -> str:
    params = {
        "ecno": "3.2.1.21",
        "organism[]": str(case["organism"]),
        "showtm": "0",
        "UniProtAcc": str(case["uniprot_accession"]),
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    with tempfile.TemporaryDirectory(prefix="brenda-headless-") as profile:
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--disable-background-networking",
            "--virtual-time-budget=20000",
            "--dump-dom",
            f"--user-data-dir={profile}",
            url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=75)
    if result.returncode != 0 and not result.stdout:
        raise RuntimeError(f"Headless browser failed: {result.stderr[-1000:]}")
    if "<html" not in result.stdout.lower():
        raise RuntimeError(f"No rendered HTML returned: {result.stderr[-1000:]}")
    return result.stdout


def page_summary(html: str, case: dict[str, object]) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1 = soup.select_one("#flatheader h1")
    header = h1.get_text(" ", strip=True) if h1 else ""

    category_counts: dict[str, str] = {}
    for category_id, label in (("nav37", "Substrates/Products"), ("nav17", "Natural Substrates")):
        node = soup.select_one(f"#{category_id} .naventrnr")
        category_counts[label] = node.get_text(" ", strip=True) if node else "not exposed"

    ref_total_node = soup.select_one("#tab30_nav .red.bold")
    ref_total = ref_total_node.get_text(" ", strip=True) if ref_total_node else "not exposed"
    ref_table = soup.select_one("#tab30")
    ref_rows = len(ref_table.select("[id^='tab30r']")) if ref_table else 0
    exact_query_visible = (
        str(case["uniprot_accession"]) in title
        and str(case["organism"]) in title
        and str(case["uniprot_accession"]) in header
    )
    return {
        **case,
        "ec_number": "3.2.1.21",
        "filtered_page_identity_confirmed": str(exact_query_visible).lower(),
        "substrate_product_rows": category_counts["Substrates/Products"],
        "natural_substrate_rows": category_counts["Natural Substrates"],
        "reference_entry_total": ref_total,
        "rendered_reference_data_rows": ref_rows,
        "interpretation": (
            "No rows exposed by this exact filtered public BRENDA page after JavaScript rendering; "
            "not evidence of absence from all BRENDA records or source literature"
        ),
    }


def main() -> None:
    browser = find_edge()
    output = Path(__file__).with_name("brenda_js_filtered_tables_audit.csv")
    rows = [page_summary(fetch_rendered_dom(browser, case), case) for case in CASES]
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(
            row["uniprot_accession"],
            "verified=", row["filtered_page_identity_confirmed"],
            "substrates=", row["substrate_product_rows"],
            "natural=", row["natural_substrate_rows"],
            "reference_total=", row["reference_entry_total"],
            "rendered_reference_rows=", row["rendered_reference_data_rows"],
        )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
