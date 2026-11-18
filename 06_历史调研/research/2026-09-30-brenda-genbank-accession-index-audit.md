# BRENDA accession-index check for 13 unmatched GH1 pilot proteins

## Question

Can the 13 GH1 pilot proteins that did not match the four downloaded BRENDA EC sequence collections be resolved by directly querying BRENDA's public sequence index with their versioned GenBank protein accessions?

Relevance: **3/3** to clarifying the bounds of the pilot's BRENDA crosswalk. This checks one exact-identifier route; it is not an assay-record audit.

## Method

I reused the existing BRENDA sequence-index query and row parser in [`query_brenda_sequence_accessions.py`](pilots/gh1-nims/query_brenda_sequence_accessions.py), passing each GenBank accession as the requested accession string. All 13 HTTP requests returned status 200. The parser found no result row containing the queried GenBank accession for any of the 13. I also checked the existing NCBI-to-BRENDA crosswalk: these 13 rows have no UniProt cross-reference captured there. The tested identifier-index route is therefore unresolved for these records; a no-row response to a UniProt accession field is not proof that the protein sequence is absent from BRENDA or from all database views.

## Results

| GenBank protein accession | Pilot observation rows | NCBI EC annotation in crosswalk | BRENDA exact accession-index row |
|---|---:|---|---|
| AAT59229.1 | 1 | none recorded | no row returned |
| AAU43012.1 | 4 | 3.2.1.86 | no row returned |
| ABV62413.1 | 1 | none recorded | no row returned |
| ABW01253.1 | 1 | none recorded | no row returned |
| ABW01492.1 | 1 | none recorded | no row returned |
| ABY33610.1 | 1 | none recorded | no row returned |
| ACQ70805.1 | 3 | none recorded | no row returned |
| ADD01617.1 | 1 | none recorded | no row returned |
| BAB59827.1 | 5 | none recorded | no row returned |
| BAD76141.1 | 1 | none recorded | no row returned |
| CAA52344.1 | 1 | none recorded | no row returned |
| CAJ88232.1 | 1 | none recorded | no row returned |
| CBL32986.1 | 3 | 3.2.1.86 | no row returned |
| **Total** | **24** | 2 have an EC value in this crosswalk | **0/13 exact GenBank accession rows** |

## Interpretation

- This does **not** upgrade the prior result into 13 confirmed BRENDA protein absences. The query field was previously validated with UniProtKB accessions, while the 13 strings are versioned GenBank accessions and have no UniProt cross-reference in the local NCBI crosswalk. The namespace mismatch is a plausible explanation for no exact row.
- The 24 associated pilot rows remain unresolved for BRENDA exact-protein identity. They should not be counted as database-unique negative observations.
- A meaningful next check is to map these GenBank records to current UniProt IDs or submit their full amino-acid sequences through a functioning exact-sequence search. The latter route has previously failed at the BRENDA interface for a known sequence, so it must be retried only if an independently working transport/interface becomes available.
- Even a verified BRENDA protein-sequence hit would establish protein identity only, not that the Heins paper's substrate, condition, source cell, and `<0.1` result are curated there.

## Reproduction and source files

- Query implementation: [`query_brenda_sequence_accessions.py`](pilots/gh1-nims/query_brenda_sequence_accessions.py).
- Input list and row counts: [`brenda_ec_sequence_all_sample_audit.csv`](pilots/gh1-nims/brenda_ec_sequence_all_sample_audit.csv), filtering `exact_brenda_sequence_match=false`.
- NCBI annotations and identifier cross-references: [`ncbi_accession_crosswalk.csv`](pilots/gh1-nims/ncbi_accession_crosswalk.csv).
- Exact query form, using the 13 accession values above: [BRENDA amino-acid sequence search](https://www.brenda-enzymes.org/sequences.php).

