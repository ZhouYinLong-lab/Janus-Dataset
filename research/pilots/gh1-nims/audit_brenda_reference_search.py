"""Audit public BRENDA full-text/reference searches for the GH1 NIMS paper.

The page reports field-level hit counts. It does not expose article-level
results here, so author-name hits must not be treated as a paper match.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import requests


BASE_URL = "https://www.brenda-enzymes.org/fulltext.php"
TARGET_DOI = "10.1021/cb500244v"
QUERIES = [
    ("doi_full_database", TARGET_DOI, "complete_database"),
    ("doi_reference_field", TARGET_DOI, "reference"),
    ("doi_suffix_reference_field", "cb500244v", "reference"),
    ("pmid_reference_field", "25046136", "reference"),
    ("title_lead_reference_field", "Phylogenomically Guided Identification", "reference"),
    (
        "title_method_reference_field",
        "DNA Synthesis and Nanostructure-Initiator Mass Spectrometry",
        "reference",
    ),
    ("author_year_reference_field", "Heins et al. 2014", "reference"),
    ("author_fullname_reference_field", "Katherine Heins", "reference"),
    ("author_surname_reference_field", "Heins", "reference"),
    ("boolean_author_year_reference_field", "Heins AND 2014", "reference_boolean"),
    ("boolean_author_family_reference_field", "Heins AND GH1", "reference_boolean"),
    ("boolean_author_assay_reference_field", "Heins AND NIMS", "reference_boolean"),
    ("author_initials_reference_field", "Heins K M", "reference"),
    ("boolean_author_function_reference_field", "Heins AND glycosidase", "reference_boolean"),
]
COUNT_RE = re.compile(
    r"(?is)<table><thead><tr><th>Field</th><th>Hits found</th>.*?</thead>"
    r"<tbody>.*?<td><a[^>]*>Reference</a>\s*</td>\s*<td>(\d+)</td>.*?</tbody></table>"
)
NO_HITS = "There have been no hits for your query"


def main() -> None:
    rows = []
    with requests.Session() as session:
        for query_id, term, scope in QUERIES:
            search_type = "6" if scope == "reference_boolean" else "2"
            params: dict[str, str] = {"Searchterm": term, "stype": search_type}
            if scope == "complete_database":
                params["compl_db"] = "on"
            else:
                params["tables[]"] = "30"  # BRENDA's Reference field
            response = session.get(BASE_URL, params=params, timeout=45)
            response.raise_for_status()
            match = COUNT_RE.search(response.text)
            if match:
                status, hits = "field_hits", match.group(1)
            elif NO_HITS in response.text:
                status, hits = "no_hits", "0"
            else:
                status, hits = "unparsed", ""
            rows.append(
                {
                    "query_id": query_id,
                    "term": term,
                    "scope": scope,
                    "reference_field_hits": hits,
                    "status": status,
                    "query_url": response.url,
                    "release_note": "BRENDA website identifies release 2026.1 (March 2026)",
                }
            )

    output = Path(__file__).with_name("brenda_reference_search_audit.csv")
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output}; {len(rows)} BRENDA full-text/reference queries")


if __name__ == "__main__":
    main()
