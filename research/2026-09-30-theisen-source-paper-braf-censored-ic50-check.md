# Source-paper check: Theisen row 69665 and left-censored BRAF V600E IC50

## Candidate record

The 100-row audit includes row 69665 (UniProt P15056/BRAF; prepared pActivity 9.397940). Current ChEMBL 37 maps its connectivity-level structure to CHEMBL3335372 and returns two records from DOI 10.1021/ml5002272:

- biochemical BRAF V600E IC50 `<0.4 nM`;
- cell-based BRAF-mediated ERK-phosphorylation EC50 `=100 nM`.

Only the first record's censoring boundary transforms to the prepared value: `−log10(0.4 × 10⁻⁹ M) = 9.397940`. The second is a different endpoint and must not be averaged or conflated with the biochemical IC50.

## Source-paper corroboration

Subramanian et al. (2014), “Design and Synthesis of Orally Bioavailable Benzimidazole Reverse Amides as Pan RAF Kinase Inhibitors,” presents Table 1 with separate columns for biochemical BRAF V600E IC50 and cellular p-ERK EC50. The row for compound 9 reports `<0.0004 μM` and `0.1 μM`; these convert to `<0.4 nM` and `100 nM`, respectively, matching the two ChEMBL records for the candidate structure. Compound 10 also has the same `<0.0004 μM` biochemical bound but a different p-ERK EC50 (0.05 μM), so the paired cell EC50 supports compound 9 as the likely exact table row. The paper/ChEMBL link and this two-endpoint fingerprint provide substantially stronger compound-cell attribution than the CDK2 example, though a direct SI structure-to-CHEMBL identifier crosswalk was not inspected.

## Interpretation and limits

Under `pIC50 = −log10(IC50 in M)`, an IC50 `<0.4 nM` implies `pIC50 > 9.397940`. The prepared scalar equals the transformed cutoff, so it represents the censoring boundary, not a measured exact IC50. This is a clear example of why relation direction must survive transformation. It is not a biological inactive/negative example: it is a very potent positive BRAF inhibitor whose potency is left-censored at the assay's reported limit.

The source already appears in ChEMBL; this is source-context recovery, not incremental literature coverage. It also illustrates that one compound–target pair can have biochemical and cellular endpoints with different meanings; merging them into one scalar would erase assay context. No model-utility or publication-bias conclusion follows from this single row.

## Main-project relevance

**Relevance: 3/3.** This provides a source-verifiable example of a left-censored biochemical measurement, its inequality reversal under the pIC50 transform, and a separate cellular endpoint for the same candidate. It directly informs a negative/censored-evidence schema and guards against endpoint conflation, while showing this evidence is already curated in a structured database.

Sources: Subramanian et al., *ACS Medicinal Chemistry Letters* (2014), [DOI 10.1021/ml5002272](https://doi.org/10.1021/ml5002272); [PMC full-text article](https://pmc.ncbi.nlm.nih.gov/articles/PMC4160747/); [ACS publisher page](https://pubs.acs.org/doi/10.1021/ml5002272); row-level ChEMBL records in [`theisen_linkage_sample_100_activity_records.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_activity_records.csv).
