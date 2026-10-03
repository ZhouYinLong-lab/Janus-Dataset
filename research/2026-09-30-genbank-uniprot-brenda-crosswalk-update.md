# GenBank → UniProt/UniParc → BRENDA crosswalk update

## Why this check was needed

The prior BRENDA sequence-page audit queried 13 versioned GenBank protein accessions directly and received no result rows. That input field had previously been tested with UniProt accessions, so the no-hit result could reflect an identifier-namespace mismatch rather than missing proteins. This pass used UniProt's official ID Mapping service for the relevant supported source type, then compared returned UniProt/UniParc sequences against the original NCBI protein FASTA before querying BRENDA.

Relevance: **3/3** to the core database-coverage audit. It changes the count of sample proteins whose sequence entity is discoverable in BRENDA, while still not proving BRENDA has curated their source-cell assay results.

## Results

Of the 13 unmatched GenBank proteins (24 sample observations):

- 7 mapped directly to UniProtKB entries.
- 5 were returned as UniParc sequence suggestions. The UniParc records contain source/accession cross-references and linked UniProtKB/TrEMBL accessions.
- 1 (`ABV62413.1`) had no UniProtKB mapping result in this job and remains unresolved.
- The full amino-acid sequences were fetched from NCBI and compared against the matched UniProtKB or UniParc FASTA for the 12 mapped proteins: **all 12 were identical end to end**, with matching lengths.

### BRENDA sequence-index follow-up

The 12 mapped proteins' UniProtKB accession(s) were queried through BRENDA's public sequence index. The results were:

| GenBank accession | Pilot rows | UniProt/UniParc mapping | BRENDA sequence index | Exact filtered activity tables |
|---|---:|---|---|---|
| AAT59229.1 | 1 | UPI00003B366D; Q6HMK2 | Exact match, BRENDA sequence ID 24116899, EC 3.2.1.86 | 0 substrate/product, 0 natural-substrate, 0 reference rows |
| AAU43012.1 | 4 | UPI000043DDAC; Q65D52 | Exact match, BRENDA sequence ID 24101727, EC 3.2.1.86 | 0 substrate/product, 0 natural-substrate, 0 reference rows |
| CAJ88232.1 | 1 | UPI0000E65ECA; A0ACM7 | Exact match already known from the prior accessions pass, sequence ID 21664329, EC 3.2.1.21 | Previously rendered exact page also showed 0/0/0 |
| CAA52344.1 | 1 | UPI00000B8B13; includes Q55000 | No exact row for any of five linked UniProtKB accessions tested | Not established |
| CBL32986.1 | 3 | UPI0001CE52BD; D4MF92 | No exact row for tested linked accession | Not established |
| Seven direct-UniProtKB mappings | 13 combined | A8MBR0, A8MCI6, A9WDK4, C4L0E2, D3T6K4, Q97AX4, Q5KYU5 | No exact row for each tested accession | Not established |
| ABV62413.1 | 1 | No mapping result | Unresolved | Not established |

For AAT59229.1 and AAU43012.1, the BRENDA sequence-detail records were fetched and their amino-acid strings independently compared with NCBI FASTA: 479/479 and 472/472 residues identical. Their exact `EC 3.2.1.86 + organism + UniProt` enzyme pages were rendered in headless Edge; titles/headings confirmed the requested filters, and the three activity/reference counters were each zero.

Among the 13 proteins, this pass adds **two new exact BRENDA sequence-index matches** covering five sample observations. Together with the prior exact-sequence crosswalk, the working count increases from 21 proteins/62 observations in the four downloaded EC sequence sets, plus the already-known CAJ88232.1/A0ACM7 entry, to **24 of 34 proteins and 68 of 86 accession-linked observations with exact BRENDA sequence-index presence**. This is sequence-entity coverage, not assay/negative-observation coverage.

## Correction to the earlier dynamic-page count

An independent recomputation from the row-level [dynamic-page audit CSV](pilots/gh1-nims/brenda_js_tables_bulk_audit.csv), deduplicating by GenBank accession and joining observation counts to the NCBI crosswalk, corrects an earlier summary that said “21 accessions / 62 observations.” Before adding the two new pages, the 24 page rows represented **22 distinct sample accessions and 63 observations**; the page-row observation counts sum to 68 because two proteins have duplicate BRENDA sequence entries. After adding the AAT59229.1 and AAU43012.1 pages, the current exact-filter audit is **26 rendered pages / 24 distinct sample proteins / 68 distinct observations** (73 summed page-row observations). All 26 views tested show zero substrate/product, natural-substrate, and reference rows. The positive control remains 18/1/7.

The original four-EC bulk sequence-set result—21/34 proteins and 62/86 observations—remains correct for that specific collection. The correction is to the broader union/dynamic-page summary, which must also include CAJ88232.1/A0ACM7 and, now, AAT59229.1/Q6HMK2 and AAU43012.1/Q65D52.

## Limits and next step

- A protein sequence-index hit establishes that the sequence entity is indexed, not that BRENDA curated the Heins source paper's assay, tested substrate set, pH/temperature, or `<0.1` outcome.
- A zero exact-filtered table count is limited to the rendered EC/organism/UniProt view. It does not prove absence under alternative annotations, comments, references, broader literature search, or other database views.
- `ABV62413.1` remains an identifier/sequence-mapping exception, not a demonstrated database absence.
- The next useful step is to audit the cited BRENDA literature/reference routes for a stratified sample of the 68 candidate observations and classify exact assay match, related positive-only record, unrelated protein/EC match, and unresolved. Only exact assay-level evidence can reduce the candidate incremental-coverage count.

## Reproduction and evidence

- Mapping API: [UniProt ID Mapping documentation](https://www.uniprot.org/help/id_mapping) and [supported mapping-field configuration](https://rest.uniprot.org/configure/idmapping/fields).
- Archive semantics: [UniParc documentation](https://www.uniprot.org/help/uniparc), which describes stable sequence identifiers and source-database cross-references.
- Mapping details, sequence-identity checks, BRENDA index lookups, and page counts: [`genbank_uniprot_brenda_mapping_audit.csv`](pilots/gh1-nims/genbank_uniprot_brenda_mapping_audit.csv).
- Original inputs/results: [`ncbi_accession_crosswalk.csv`](pilots/gh1-nims/ncbi_accession_crosswalk.csv), [`brenda_ec_sequence_all_sample_audit.csv`](pilots/gh1-nims/brenda_ec_sequence_all_sample_audit.csv), [`brenda_js_tables_bulk_audit.csv`](pilots/gh1-nims/brenda_js_tables_bulk_audit.csv), [`query_brenda_sequence_accessions.py`](pilots/gh1-nims/query_brenda_sequence_accessions.py), and [`audit_brenda_js_tables_bulk.py`](pilots/gh1-nims/audit_brenda_js_tables_bulk.py).

