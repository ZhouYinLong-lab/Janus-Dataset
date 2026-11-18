"""Positive control: verify JS-rendered BRENDA tables expose known entries."""

from __future__ import annotations

import csv
from pathlib import Path

from audit_brenda_js_tables_bulk import find_browser, run_page, summarize


CONTROL = {
    "uniprot_accession": "P49235",
    "ec_number": "3.2.1.21",
    "organism": "Zea mays",
    "sample_accessions": "not_in_GH1_pilot",
    "sample_observation_count": "0",
}


def main() -> None:
    result = summarize(run_page(find_browser(), CONTROL), CONTROL)
    if result["substrate_product_count"] in {"0", "not exposed"}:
        raise RuntimeError(f"Positive control did not expose expected substrate rows: {result}")
    output = Path(__file__).with_name("brenda_js_positive_control.csv")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result))
        writer.writeheader()
        writer.writerow(result)
    print(
        f"P49235 rendered: substrates={result['substrate_product_count']}, "
        f"natural={result['natural_substrate_count']}, refs={result['reference_entry_count']}"
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
