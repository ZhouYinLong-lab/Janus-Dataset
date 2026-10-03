"""Find negative/qualifying commentary on the non-empty exact BRENDA pages."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

import audit_brenda_core96_activity_views as page_audit
import audit_brenda_core96_substrate_overlaps as overlap_audit


HERE = Path(__file__).resolve().parent
PAGES = HERE / "brenda_core96_exact_activity_views.csv"
POOL = HERE / "gh1_nims_negative_candidates_all_2076.csv"
OUTPUT = HERE / "brenda_core96_negative_comment_candidates.csv"
FIELDS = [
    "uniprot_accession",
    "ec_number",
    "organism",
    "sample_accessions",
    "table_type",
    "brenda_substrate_reaction",
    "brenda_product_reaction",
    "brenda_uniprot_ids",
    "brenda_reference_ids",
    "brenda_commentary",
    "pool_substrate_overlap",
    "page_url",
]
NEGATIVE_OR_QUALIFIER = re.compile(
    r"\b(no|not|non[- ]?substrate|inactive|inactiv|without|unable|lack|low activity|poor substrate|negligible)\b",
    re.IGNORECASE,
)


def main() -> None:
    with POOL.open(encoding="utf-8-sig", newline="") as stream:
        pool_rows = list(csv.DictReader(stream))
    pool_by_accession: dict[str, set[str]] = {}
    for source in pool_rows:
        if source.get("included_in_core_candidate_pool") == "true" and source.get("ncbi_accession"):
            pool_by_accession.setdefault(source["ncbi_accession"], set()).add(source["substrate"])

    with PAGES.open(encoding="utf-8-sig", newline="") as stream:
        pages = list(csv.DictReader(stream))
    nonempty = [
        row
        for row in pages
        if row["query_status"] == "ok"
        and any(
            int(row.get(field, "0") or 0) > 0
            for field in ("substrate_product_count", "natural_substrate_count", "reference_entry_count")
        )
    ]

    output: list[dict[str, str]] = []
    browser = page_audit.find_browser()
    for page in nonempty:
        accessions = [value for value in page["sample_accessions"].split(";") if value]
        pool_substrates = set().union(*(pool_by_accession.get(value, set()) for value in accessions))
        html = page_audit.run_page(
            browser,
            {
                "ec_number": page["ec_number"],
                "organism": page["organism"],
                "uniprot_accession": page["uniprot_accession"],
            },
        )
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if page["uniprot_accession"] not in title or page["ec_number"] not in title:
            raise ValueError(f"Rendered page identity mismatch: {page['page_url']}")

        for table_type, table_id, row_prefix in (
            ("substrate_product", "tab37", "tab37"),
            ("natural_substrate", "tab17", "tab17"),
        ):
            table = soup.find(id=table_id)
            if not table:
                continue
            pattern = re.compile(rf"^{row_prefix}r\d+sr\d+$")
            for row in table.find_all("div", id=pattern):
                uniprot_ids = overlap_audit.cell_text(row, 4)
                if page["uniprot_accession"] not in uniprot_ids:
                    continue
                comment = overlap_audit.cell_text(row, 6)
                if not NEGATIVE_OR_QUALIFIER.search(comment):
                    continue
                substrate = overlap_audit.cell_text(row, 0)
                output.append(
                    {
                        "uniprot_accession": page["uniprot_accession"],
                        "ec_number": page["ec_number"],
                        "organism": page["organism"],
                        "sample_accessions": ";".join(accessions),
                        "table_type": table_type,
                        "brenda_substrate_reaction": substrate,
                        "brenda_product_reaction": overlap_audit.cell_text(row, 1),
                        "brenda_uniprot_ids": uniprot_ids,
                        "brenda_reference_ids": overlap_audit.cell_text(row, 5),
                        "brenda_commentary": comment,
                        "pool_substrate_overlap": str(
                            any(name.casefold() in substrate.casefold() for name in pool_substrates)
                        ).lower(),
                        "page_url": page["page_url"],
                    }
                )

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    print(f"scanned_nonempty_exact_pages={len(nonempty)}")
    print(f"negative_or_qualifying_comment_candidates={len(output)}")
    print(f"pool_substrate_overlap_candidates={sum(row['pool_substrate_overlap'] == 'true' for row in output)}")
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
