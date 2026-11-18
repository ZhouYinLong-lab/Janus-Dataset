# Theisen kinase activity table: 100-row stratified ChEMBL crosswalk audit

**Date:** 2026-09-30  
**Purpose:** Expand the 20-row pilot without replacing it, quantify how often model-ready measured values can be connected to current structured activity records, and inspect whether low-activity-side bounds survive the export.

## Protocol and retained outputs

The same deterministic SHA-256 ranking used in the 20-row pilot selected the first 50 measured rows with pActivity ≤6 and first 50 with pActivity >6. The 20 pilot rows are nested within this expanded sample. The 100-row manifest was frozen before querying ChEMBL. All outputs are retained separately:

- [`theisen_linkage_sample_100_manifest.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_manifest.csv)
- [`theisen_linkage_sample_100_results.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_results.csv)
- [`theisen_linkage_sample_100_activity_records.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_activity_records.csv)
- Reproducible script: [`theisen_linkage_sample.py`](pilots/kinase-activity-integration/theisen_linkage_sample.py), invoked with `--n-per-stratum 50 --output-prefix theisen_linkage_sample_100`.

The live ChEMBL API reported ChEMBL 37 (release date 2026-05-01). Structure lookup is a connectivity search, not a claim of exact stereochemical identity. A pChEMBL match is within 0.005 of the prepared pActivity; it is still only a candidate row link when a pair has multiple records or the original source version is unknown. The pActivity≤6 stratum is an audit stratum, not a categorical inactive annotation for every row.

## Results

| ChEMBL crosswalk outcome | pActivity ≤6 (n=50) | pActivity >6 (n=50) | Total |
|---|---:|---:|---:|
| At least one activity with pChEMBL within 0.005 | 28 | 32 | 60 |
| Target/structure activity rows found, but none numerically match prepared pActivity | 21 | 18 | 39 |
| No structure candidate returned by this ChEMBL connectivity query | 1 | 0 | 1 |
| API errors | 0 | 0 | 0 |

Six of the 60 numerically matched rows had multiple matching activity records; the table therefore records 54 unique-record and 6 multiple-record match cases. Across the 100 source rows, 210 activity-level rows were retained. Every row had a ChEMBL assay ID and assay description and a ChEMBL document ID; 146/210 had a DOI, 133/210 had a nonempty pChEMBL, and 209/210 had a nonempty relation operator. Missing pChEMBL is expected for some relation-coded/censored values; missing DOI is a provenance limitation, not a failed assay.

The observed numeric-match fraction is 60/100 in this SHA-selected stratified audit; it must not be reported as a full-table match rate. It is higher than the 20-row pilot's 10/20, demonstrating why the smaller pilot should not be used to imply prevalence. The sample is useful for estimating review workload and defining categories, not for claiming corpus-wide completeness.

## Censoring and scalar boundary values

In the ≤6 stratum, eight of 50 sample rows have at least one returned ChEMBL biochemical/affinity record encoded as `>10,000 nM` (14 activity records across those eight rows). Seven of the eight prepared pActivity values are approximately 5.0; the eighth is about 4.83. This is a bounded, direct example of a relation-bearing result coinciding with a scalar boundary in the model-ready table. It does **not** establish that the authors intentionally converted those exact current ChEMBL records, nor does it mean that pActivity 5.0 universally encodes `>10 μM`.

That last limitation matters: the same pActivity value may arise from different sources, endpoints and inequality directions. One apparent ChEMBL no-hit case below illustrates this directly through a PubChem record with the opposite relation (`<=10 μM`) and `Activity Outcome=Unspecified`; that record is documented separately in [`2026-09-30-theisen-pubchem-no-chembl-followup.md`](2026-09-30-theisen-pubchem-no-chembl-followup.md). Therefore, a scalar pActivity alone does not preserve enough information to infer inactive status, censoring direction, exact potency or original assay.

## Follow-up of the one ChEMBL structure-search no-hit

Sample row 129369 (UniProt Q96RG2; pActivity≈5.0) returned no structure candidate in the current ChEMBL connectivity query. A PubChem PUG REST structure lookup returned CID 70925370, and the compound assay summary links the same CID/SID to four PASK (Q96RG2) confirmatory assays. The row-level PubChem records say `Activity Outcome=Unspecified`, standardized IC50 10,000 nM, and `Standard Relation=<=`; assay registration says “SureChEMBL Patent Bioactivity Data.” This is evidence that a ChEMBL no-hit is not a global data absence, but it is **not an explicit negative**. Since the prepared model row has no source ID, the PubChem record is a plausible crosswalk candidate, not uniquely proven as the row's exact upstream contribution. The details and limits are recorded in the separate follow-up note and CSV.

## Relevance to the main question

The expanded audit directly bears on whether measured bioactivity labels in an existing ML resource can be given assay/source context and whether relation operators are flattened. It reduces the rationale for “just build another inactive kinase dataset”: most rows in this stratified sample already connect to ChEMBL activities, many have assay/source document IDs, and multiple censored examples are already represented in structured ChEMBL/BindingDB records. A genuine incremental contribution would need to show (a) provenance/context not recoverable from current structured resources, (b) label semantics that the model-ready export loses, and (c) an independent utility test after matching data size, split and label type.

It does **not** estimate publication bias, source-wide negative prevalence, automated literature-extraction precision/recall, or model benefit. The no-hit case was recoverable in PubChem and was not an inactive label, so it must not count as a new recovered negative.

## Next work

1. Adjudicate a subset of the 39 activity-but-no-value-match rows: distinguish aggregation, different assay/readout, different source version, stereochemistry, and genuinely unresolved pairs.
2. For the 8 rows with `>10 μM` in the low stratum, verify structure and exact table/patent row in primary sources where accessible; retain each relation/threshold separately.
3. Track the 64 activity records with missing DOI and establish which are dataset/patent records versus resolvable publications.
4. Only after this provenance audit, design a fixed-test-set model comparison for exact values versus interval/censor-aware values. This sample is not itself a model experiment.

## Sources

- Theisen et al. (2024), [DOI 10.1038/s41467-024-52055-5](https://doi.org/10.1038/s41467-024-52055-5), and authors' [public repository](https://github.com/Harmonic-Discovery/activity-integration).
- Official [ChEMBL Web Services documentation](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services).
- Official [PubChem PUG REST documentation](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), which specifies structure lookup, assay data, target and assay-summary resources.
