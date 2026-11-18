"""Extract exact-pool-substrate rows from non-empty BRENDA core-96 pages.

The output is an entity/substrate overlap audit only. It does not assume that
the BRENDA entry reports the same assay, condition, direction, or source study
as the Heins et al. NIMS observation.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup


HERE = Path(__file__).resolve().parent
POOL = HERE / "gh1_nims_negative_candidates_all_2076.csv"
PAGES = HERE / "brenda_core96_exact_activity_views.csv"
OUTPUT = HERE / "brenda_core96_substrate_overlap_rows.csv"
FIELDS = [
    "uniprot_accession",
    "ec_number",
    "organism",
    "sample_accessions",
    "pool_substrates",
    "table_type",
    "brenda_substrate_reaction",
    "brenda_product_reaction",
    "brenda_organism",
    "brenda_uniprot_ids",
    "brenda_reference_ids",
    "brenda_commentary",
    "page_url",
    "interpretation_boundary",
]


def find_browser() -> str:
    for path in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ):
        if path.is_file():
            return str(path)
    for executable in ("msedge", "chrome"):
        if shutil.which(executable):
            return shutil.which(executable) or executable
    raise FileNotFoundError("Microsoft Edge or Google Chrome not found")


def render(browser: str, url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="brenda-core96-overlap-") as profile:
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
            timeout=90,
        )
    if result.returncode != 0 and "<html" not in result.stdout.lower():
        raise RuntimeError(result.stderr[-600:] or f"Browser failed for {url}")
    return result.stdout


def cell_text(row, index: int) -> str:
    cell = row.find(id=lambda value: value and value.endswith(f"c{index}"))
    return cell.get_text(" ", strip=True) if cell else ""


def main() -> None:
    with POOL.open(encoding="utf-8-sig", newline="") as stream:
        pool_rows = list(csv.DictReader(stream))
    pool_by_accession: dict[str, dict[str, object]] = {}
    for row in pool_rows:
        if row.get("included_in_core_candidate_pool") != "true" or not row.get("ncbi_accession"):
            continue
        entry = pool_by_accession.setdefault(
            row["ncbi_accession"],
            {"substrates": set(), "cells": 0},
        )
        entry["substrates"].add(row["substrate"])
        entry["cells"] += 1
    with PAGES.open(encoding="utf-8-sig", newline="") as stream:
        page_rows = list(csv.DictReader(stream))

    nonempty = [
        row
        for row in page_rows
        if row["query_status"] == "ok"
        and any(
            int(row.get(field, "0") or 0) > 0
            for field in (
                "substrate_product_count",
                "natural_substrate_count",
                "reference_entry_count",
            )
        )
    ]
    output_rows: list[dict[str, str]] = []
    browser = find_browser()
    for page in nonempty:
        accessions = [item for item in page["sample_accessions"].split(";") if item]
        source_rows = [pool_by_accession[item] for item in accessions if item in pool_by_accession]
        substrate_names: set[str] = set()
        for source in source_rows:
            substrate_names.update(source["substrates"])

        html = render(browser, page["page_url"])
        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if page["uniprot_accession"] not in page_title or page["ec_number"] not in page_title:
            raise ValueError(f"Rendered page identity mismatch: {page['page_url']}")

        for table_type, table_id in (("substrate_product", "tab37"), ("natural_substrate", "tab17")):
            table = soup.find(id=table_id)
            if not table:
                continue
            # Detailed rows for grouped reactions are nested under a summary
            # row, often hidden until the user expands the group.
            prefix = "tab37" if table_type == "substrate_product" else "tab17"
            row_pattern = re.compile(rf"^{prefix}r\d+sr\d+$")
            for row in table.find_all("div", id=row_pattern):
                substrate = cell_text(row, 0)
                products = cell_text(row, 1)
                organisms = cell_text(row, 3)
                uniprot_ids = cell_text(row, 4)
                references = cell_text(row, 5)
                commentary = cell_text(row, 6)
                if page["uniprot_accession"] not in uniprot_ids:
                    continue
                if not any(name.casefold() in substrate.casefold() for name in substrate_names):
                    continue
                output_rows.append(
                    {
                        "uniprot_accession": page["uniprot_accession"],
                        "ec_number": page["ec_number"],
                        "organism": page["organism"],
                        "sample_accessions": ";".join(accessions),
                        "pool_substrates": ";".join(sorted(substrate_names)),
                        "table_type": table_type,
                        "brenda_substrate_reaction": substrate,
                        "brenda_product_reaction": products,
                        "brenda_organism": organisms,
                        "brenda_uniprot_ids": uniprot_ids,
                        "brenda_reference_ids": references,
                        "brenda_commentary": commentary,
                        "page_url": page["page_url"],
                        "interpretation_boundary": (
                            "Exact protein and substrate name overlap only; does not establish same assay, "
                            "conditions, negative result, source paper, or direction of activity"
                        ),
                    }
                )

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"nonempty_exact_pages={len(nonempty)}")
    print(f"matched_protein_substrate_rows={len(output_rows)}")
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
