# Versioned-accession audit: GH1 NIMS sample ABV62413.1

## Question and relevance

Can the one remaining GenBank accession that failed direct UniProt mapping be resolved without confusing the 2014 sample sequence with a later replacement protein record?

Relevance: **3/3** to protein/assay provenance and accurate database-coverage denominators. It is one pilot protein and one observation, so its effect on overall counts is small; its value is methodological—showing why versioned sequence identity matters.

## Findings

The pilot's single ABV62413.1 record represents a `cellobiose` NIMS `<0.1` observation at pH 5 and 40 °C. NCBI's archived protein record says ABV62413.1 was replaced by **ABV62413.2**. The old record is 488 aa and defines the product broadly as “glycosyl hydrolase” with a possible beta-glucosidase note. The replacement is 491 aa and is annotated as 6-phospho-beta-glucosidase, EC 3.2.1.86.

The official UniProt ID-mapping service mapped ABV62413.2 to **A8FDU6**. The replacement sequence is exactly identical to the current UniProt A8FDU6 sequence, and BRENDA's sequence index returns one exact A8FDU6 entry (sequence ID 21823616; EC 3.2.1.86; *Bacillus pumilus* SAFR-032). The BRENDA sequence itself exactly matches ABV62413.2, not ABV62413.1. The sample's historical version and current replacement are not exact sequence matches (488 versus 491 aa; direct sequence comparison false).

The exact EC + organism + UniProt BRENDA activity view was rendered and verified. It reports 0 substrate/product rows, 0 natural-substrate rows, and 0 reference rows. This remains a scoped page result, not a whole-database or source-literature absence claim.

## Interpretation

This resolves the **locus/version crosswalk**, not an exact-sequence match for the sequence used in the source paper. It would be incorrect to count this as a new exact-sequence BRENDA hit for the historical ABV62413.1 assay record. The prior exact-sequence count therefore remains 24/34 proteins and 68/86 observations; separately, there is one current replacement-sequence candidate associated with the same versioned NCBI accession lineage, whose assay relationship is not established by current sequence identity alone.

The result also illustrates a general extraction requirement: store accession **and version**, sequence hash, and database snapshot date. A current protein entry can be related to a historical assay without being the same tested sequence. Do not convert the empty BRENDA activity view into evidence that the cellobiose negative is unique to the literature.

## Reproducibility

[`audit_brenda_accession_version.py`](pilots/gh1-nims/audit_brenda_accession_version.py) re-fetches both NCBI FASTA versions, the UniProt sequence, the BRENDA sequence-index entry and sequence, and the rendered filtered activity page. Its row-level output is [`brenda_accession_version_audit.csv`](pilots/gh1-nims/brenda_accession_version_audit.csv).

## Primary sources

- [NCBI protein record ABV62413.1](https://www.ncbi.nlm.nih.gov/protein/ABV62413.1) — replacement notice and historical protein version.
- [NCBI protein record ABV62413.2](https://www.ncbi.nlm.nih.gov/protein/ABV62413.2) — current replacement annotation.
- [UniProtKB A8FDU6](https://www.uniprot.org/uniprotkb/A8FDU6) — current UniProt protein sequence.
- [UniProt ID Mapping](https://www.uniprot.org/help/id_mapping) — mapping service documentation.
- [BRENDA sequence search](https://www.brenda-enzymes.org/sequences.php) — exact A8FDU6 entry; exact sequence ID 21823616.
