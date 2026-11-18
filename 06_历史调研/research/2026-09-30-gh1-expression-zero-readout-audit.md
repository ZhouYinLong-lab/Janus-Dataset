# 2026-09-30 GH1 low-expression records: readout existence and interpretation audit

## Question and relevance

Should the 273 explicit `<0.1` NIMS cells associated with `Expression_binary=0` be discarded as untested, or retained as a separate evidence stratum?

Relevance: **3/3** to distinguishing measured negative evidence from missing data and to label-quality design; **2/3** to extraction completeness; **1/3** to direct model benefit.

## Method

Re-read retained ACS Figshare Supplementary Table 2 and Table 3 using `openpyxl`. For each Table 2 condition row, joined the protein identifier to the original Table 3 expression-status flag and soluble-expression concentration. For the 12 proteins flagged `Expression_binary=0` that have Table 2 rows, classified each of the three substrate cells as literal `<0.1`, numeric above 0.1, exact 0.1, another numeric value, or missing. Grouped outcomes by accession/species × substrate while preserving source Excel rows and cells. The script and pair-level output are retained below.

## Results

- All **12/12** Table 2 proteins with `Expression_binary=0` have actual recorded NIMS assay rows; they are not “untested” in this source table.
- The 12 proteins span **36 enzyme–substrate pairs** across xylobiose, cellobiose, and lactose. Those pairs contain **273 literal `<0.1` cells**: 90 cellobiose, 88 lactose, and 95 xylobiose.
- Across the complete condition rows, **31/36 pairs** have below-background cells and no numeric above-background value in the table; **5/36** show both below-background and above-background values across conditions. As with the expression-positive set, these labels are condition-specific.
- The 12 proteins have low but nonzero soluble-expression concentrations, **0.001–0.014 mg/mL**, compared with 0.029–1.03 mg/mL for the `Expression_binary=1` group. Table 3 does not provide an operational definition of the binary cutoff.
- Two `Expression_binary=0` proteins are marked `Cellobiose NIMS_Activity (Binary)=1` in Table 3. For `ACK43071.1`, Table 2 has four below-background and four above-background cellobiose values across conditions, compatible with an aggregate positive flag. For `ACI21065.1`, all eight Table 2 cellobiose condition cells are `<0.1` although Table 3 marks the NIMS cellobiose binary as 1; this is a specific unresolved cross-table discrepancy. Table 3's note that absorbance >0.1 is positive applies to its pNPG column; the workbook does not define the aggregation rule for its NIMS binary column.

## Interpretation

The earlier 1,803-cell `Expression_binary=1` pool is a conservative high-expression subset, not the complete set of measured below-background outcomes. The other 273 cells must not be described as untested or deleted from the evidence inventory: the source table contains measured readouts. However, low soluble expression is a material confounder for interpreting weak turnover as intrinsic substrate non-reactivity. Preserve these cells in a **separate low-expression stratum**, retain concentration/status/context, and avoid merging them with high-expression negatives without sensitivity analysis. Also keep the ACI21065.1 Table 2/Table 3 flag discrepancy unresolved rather than choosing one source silently. “Measured below assay background” is supportable; “well-expressed enzyme is inactive on this substrate” is not.

This correction improves source-table completeness and the proposed schema but does not establish that either stratum is absent from BRENDA or improves machine-learning performance. The enzyme–substrate pair should remain the grouping unit for any split, with conditions retained as context.

## Reproducibility and sources

- Audit script: [`audit_expression_binary0_context.py`](pilots/gh1-nims/audit_expression_binary0_context.py)
- Pair-level all-outcome audit: [`gh1_nims_expression_binary0_pair_context.csv`](pilots/gh1-nims/gh1_nims_expression_binary0_pair_context.csv)
- Source-linked 273 below-background cells: [`gh1_nims_expression_binary0_candidates_273.csv`](pilots/gh1-nims/gh1_nims_expression_binary0_candidates_273.csv)
- Heins et al. (2014), [article](https://doi.org/10.1021/cb500244v), [Supplementary Table 2](https://doi.org/10.1021/cb500244v.s003), and [Supplementary Table 3](https://doi.org/10.1021/cb500244v.s004).
