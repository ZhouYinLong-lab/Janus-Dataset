# GH1 NIMS candidate-pool granularity and source-row audit

## Question and relevance

How many distinct enzyme–substrate relationships are represented by the 1,803 explicit `<0.1` cells, how many are repeated condition measurements, and does the source table contain duplicate or missing condition keys?

Relevance: **3/3** to negative-evidence extraction and label semantics; **2/3** to historical-mining feasibility; **1/3** as direct evidence of model benefit. This is one dense screen in one paper, not an independent benchmark.

## Method

Re-read ACS Figshare Supplementary Tables 2 and 3 using `openpyxl`. Included only cells whose stored source value is literally `<0.1`; retained the source row/column, accession/species label, substrate, pH, temperature, CV, and expression flag. The main candidate pool uses the same conservative `Expression_binary=1` filter as the existing 100-row sample. Binary-zero observations are separately counted rather than called untested. Keys are compared at three levels: source cell, protein–substrate pair, and protein–substrate–pH–temperature condition. Duplicate keys remain in the source-cell output and are reported, not silently collapsed.

The audit also classifies each of the 96 × 3 possible protein–substrate combinations across observed conditions as having explicit below-background cells, numeric above-background cells, or the exact threshold boundary.

## Results

| Unit | Count | Meaning |
|---|---:|---|
| Explicit `<0.1` cells across Table 2 | 2,076 | Includes both expression flags |
| Expression-binary-one `<0.1` cells | 1,803 | Current filtered candidate pool |
| Expression-binary-zero `<0.1` cells | 273 | Measured rows retained separately as a low-expression stratum; see the follow-up audit |
| Proteins with ≥1 candidate negative cell | 96 | Literal accession/species identifiers |
| Protein–substrate pairs with ≥1 candidate negative | 277 | Out of 288 possible pairs (96 proteins × 3 substrates) |
| Distinct protein–substrate–pH–temperature keys | 1,800 | Three fewer than source-cell rows because of repeated keys |
| Condition cells per negative pair (mean) | 6.51 | Repeated condition-specific values, not independent pairs |
| Reported biological replicates per table datapoint | 3 | Replicate-level values are not supplied here |

The 277 pairs divide as follows across their observed conditions:

- 113 pairs have at least one explicit `<0.1` result and at least one numeric value above the 0.1 background in another condition. These are condition-dependent labels, not globally inactive enzyme–substrate pairs.
- 164 pairs have one or more explicit `<0.1` values and no above-background numeric result elsewhere in these tables. This does not establish universal inactivity outside the tested conditions.
- 11 pairs have numeric above-background values but no explicit `<0.1` cell.

There is one numeric cell exactly equal to 0.1 (ABF87202.1 × lactose at one condition); it remains a threshold boundary, not an explicit negative or an above-background value.

## Source-table anomaly discovered

The previous pilot note said 107 of 108 Table 2 proteins covered all eight pH/temperature combinations. Recounting **distinct** condition keys corrects this to **106/108**:

| Protein | Expression flag | Source rows | Distinct condition keys | Missing key | Duplicate key |
|---|---:|---:|---:|---|---|
| `CAJ88232.1_Streptomyces-ambofaciens-ATCC-23877` | 1 | 8 | 7 | pH 5 / 40 °C | pH 8 / 90 °C (twice) |
| `CAA56282.1_Pantoea-agglomerans` | 0 | 7 | 7 | pH 8 / 90 °C | — |

For CAJ88232.1, the duplicate source rows are 694 and 701. Both repeat `<0.1` for all three substrates and have CV `NA`; the supplement does not explain whether this represents a repeated run, a duplicate row, or another convention. Preserve both original cells and flag the ambiguity. The 100-row stratified sample has no duplicate condition keys and remains 100/100 present in the expanded pool.

The 1,803 below-background cells are repeated condition-level readouts, not 1,803 independent negative pairs. Nominally they correspond to 5,409 biological-replicate measurements, but the supplement supplies aggregate/thresholded cells rather than individual replicate values; do not label all 5,409 as individually negative.

## Consequences for the research plan

This improves the feasibility estimate for structured supplementary-table extraction, but limits what this pilot can establish. A random split across condition cells would put the same enzyme–substrate pair into both training and test sets; any model test should group by enzyme–substrate pair, retain pH/temperature as assay context, and separately test enzyme-level or substrate-level generalization. The 277 observed negative pairs come from one GH1 study and only three probes, so they cannot establish broad molecular-science model benefit.

The audit is still useful to the core project: it gives a concrete example of (i) below-background results recoverable with context and provenance, (ii) repeated condition measurements that must not inflate the negative-pair count, and (iii) source-table duplication/coverage issues that extraction pipelines should surface.

## Reproducibility and files

- Audit script: [`audit_negative_pool_granularity.py`](pilots/gh1-nims/audit_negative_pool_granularity.py)
- All 2,076 explicit `<0.1` cells with original expression-status labels: [`gh1_nims_negative_candidates_all_2076.csv`](pilots/gh1-nims/gh1_nims_negative_candidates_all_2076.csv)
- Full 1,803-row source-linked candidate pool: [`gh1_nims_candidate_pool_1803.csv`](pilots/gh1-nims/gh1_nims_candidate_pool_1803.csv)
- The 273 binary-zero cells retained as a measured low-expression stratum: [`gh1_nims_expression_binary0_candidates_273.csv`](pilots/gh1-nims/gh1_nims_expression_binary0_candidates_273.csv); pair outcomes and interpretation in [`2026-09-30-gh1-expression-zero-readout-audit.md`](2026-09-30-gh1-expression-zero-readout-audit.md)
- One row per negative protein–substrate pair: [`gh1_nims_candidate_pairs.csv`](pilots/gh1-nims/gh1_nims_candidate_pairs.csv)
- Context/outcome state for all 288 protein–substrate pairs: [`gh1_nims_pair_context_audit.csv`](pilots/gh1-nims/gh1_nims_pair_context_audit.csv)
- Per-protein condition completeness and duplicate-key audit: [`gh1_nims_source_condition_key_audit.csv`](pilots/gh1-nims/gh1_nims_source_condition_key_audit.csv)
- Summary counts: [`gh1_nims_candidate_pool_summary.csv`](pilots/gh1-nims/gh1_nims_candidate_pool_summary.csv)

Source article and supplements: Heins et al. (2014), [article](https://doi.org/10.1021/cb500244v), [Supplementary Table 2](https://doi.org/10.1021/cb500244v.s003), [Supplementary Table 3](https://doi.org/10.1021/cb500244v.s004). Retained inputs and license are described in [`2026-09-30-gh1-nims-extraction-pilot.md`](2026-09-30-gh1-nims-extraction-pilot.md).
