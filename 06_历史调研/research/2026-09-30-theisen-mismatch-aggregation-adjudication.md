# Theisen 100-row source-linkage audit: value-mismatch adjudication

## Question

For the 39 rows in the fixed 100-row sample that had current ChEMBL structure/target activity records but no individual pChEMBL within the pre-set exact-match tolerance, could repeated IC50 measurements and aggregation explain the prepared pActivity value?

## Result

| Category | Rows | Interpretation |
|---|---:|---|
| One connectivity-level molecule candidate; arithmetic mean of numeric IC50 pChEMBL within 0.01 of prepared pActivity | 4 | Numerically compatible with aggregation, not source-row proof |
| One candidate; mean within 0.01–0.05 | 2 | Approximate compatibility, potentially affected by rounded pChEMBL |
| One candidate; current IC50 mean farther than 0.05 | 7 | Current records do not explain the prepared value by this simple mean |
| No numeric IC50 pChEMBL among retrieved candidate activities | 23 | Often relation-coded/censored records; cannot calculate a point-value mean |
| Multiple connectivity-level structure candidates, so aggregate is not attributable to one candidate | 3 | Ambiguous structure mapping |

Thus 6/39 rows (15.4%) are within 0.05 and 4/39 (10.3%) within 0.01 under this aggregation diagnostic. It is not valid to call the remaining 33 rows irrecoverable: source-version differences, omitted records, endpoint/assay selection, stereochemistry, compound standardization and preprocessing could all matter.

### Censored-bound check

For the 23 rows with no numeric IC50 pChEMBL, all 23 have at least one current ChEMBL non-equality IC50 record whose stated threshold, converted from nM/µM/mM to molar and then transformed as `−log10(M)`, matches the prepared pActivity to six decimal places. The relation distribution is 18 `>`, 4 `<`, and 1 `>=`; row 40079 has two matching `>10,000 nM` activity records, so there are 24 matching threshold records across these 23 rows.

This is a strong numerical crosswalk signal, but not proof that these exact ChEMBL rows were the original upstream records: current release, connectivity-level structure resolution, and source-row attribution remain limitations. Crucially, the inequality reverses under `−log10`: `IC50 > threshold` implies `pIC50 < transformed threshold`, while `IC50 < threshold` implies `pIC50 > transformed threshold`. A scalar equal to the transformed cutoff is therefore a **censoring boundary**, not an exact measured potency. If a model-ready file stores only that scalar, the relation direction and interval semantics are lost. This does not by itself prove how the authors intended or implemented the conversion.

## Method and interpretation caveat

The primary paper states that multiple measurements were summarized using the “geometric mean of the pIC50 values.” This audit computes an **arithmetic mean in pIC50 space**, equivalent to a geometric mean of the underlying IC50 concentrations. A literal geometric mean of pIC50 numbers is a different operation and is not generally the conventional way to aggregate concentrations. The article's wording therefore does not uniquely establish the implementation; the author code/data snapshot must be checked before treating this as an exact reproduction. The script makes this operational choice explicit.

Only `standard_type == IC50` records with numeric pChEMBL were averaged; censored relations were not converted into exact values, and Ki/Kd records were not mixed in. The ChEMBL query represents the current release, not necessarily the snapshot used by the 2024 study. Matching is at connectivity/target-component level, not proven stereochemical identity or source-record identity. Rounded pChEMBL values also limit precision.

The authors' public repository at pinned commit `c185bedde8a7081045bc8414906a5775f4271a1c` contains pre-prepared CSVs and training/figure code, but its tracked tree does not contain a data-ingestion/cleaning script that constructs the measured activity table. The README describes the included data as already formatted. Therefore, the published artifacts inspected here do not resolve whether/how censored measurements were converted or aggregated upstream; do not infer author intent from the match alone.

## Relevance to the main project

**Relevance: 3/3.** This directly tests whether model-ready scalar activities can be traced to structured records and whether aggregation may conceal source-level observations. It reinforces a central design requirement for the proposed dataset: preserve each source measurement, relation operator, assay/document, and aggregation lineage rather than only one pair-level scalar.

It does **not** establish that historical literature mining finds new negatives, estimate literature recovery yield, measure publication bias, or show that negative data independently improve a model. Many low-activity/censored records are already represented in ChEMBL, so they cannot count as incremental literature recovery without source-level verification.

## Reproducibility artifacts

- [`audit_value_mismatch_aggregation.py`](pilots/kinase-activity-integration/audit_value_mismatch_aggregation.py)
- [`theisen_100_value_mismatch_adjudication.csv`](pilots/kinase-activity-integration/theisen_100_value_mismatch_adjudication.csv)
- [`2026-09-30-theisen-stratified-source-linkage-100-row-audit.md`](2026-09-30-theisen-stratified-source-linkage-100-row-audit.md)

Primary source: Theisen et al., *Nature Communications* (2024), [10.1038/s41467-024-52055-5](https://doi.org/10.1038/s41467-024-52055-5). Current activity records were retrieved from ChEMBL 37 using the documented [ChEMBL Web Services](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services).
