# 2026-09-30 GH1 NIMS table-extraction pilot

## Aim and scope

This is the first 100-observation pilot that actually extracts negative-result records from a paper's supplementary material. It tests table-level recoverability and provenance retention; it is **not** a benchmark for NLP on scattered prose, nor evidence that these records are missing from all public databases.

Main paper: Heins et al., *ACS Chemical Biology* (2014), [article/PMC manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC4168791/), DOI [10.1021/cb500244v](https://doi.org/10.1021/cb500244v). The sampled source is ACS Figshare Supplementary Table 2, [DOI 10.1021/cb500244v.s003](https://doi.org/10.1021/cb500244v.s003), under CC BY-NC 4.0.

## Operational label

Supplementary Table 2 says its values are mean conversion rates for xylobiose, cellobiose, and lactose under pH 5/8 and 40/60/80/90 °C conditions; each datapoint has three biological replicates. It states that the background level was set at 0.1 conversion based on negative controls. The extracted label is therefore:

> Source cell explicitly equals `<0.1` = below the reported assay background for that enzyme–substrate–condition observation.

This is a left-censored/below-background observation, **not** a measured numeric zero and not a universal claim that the protein cannot use that substrate. One numeric cell is exactly `0.1`; it was not silently classified as `<0.1` and remains a threshold-boundary case.

## Reproducible sampling and verification

- The source workbook was downloaded from the public ACS Figshare API and retained at [`sources/gh1-2014/`](sources/gh1-2014/).
- The sample generator is [`extract_sample.py`](pilots/gh1-nims/extract_sample.py). It selects only explicit `<0.1` strings, only proteins marked `Expression_binary = 1` in Supplementary Table 3, and distributes 100 records across all 24 substrate × pH × temperature strata. Selection within a stratum is deterministic and evenly spaced through source order.
- The resulting [`gh1_nims_negative_sample_100.csv`](pilots/gh1-nims/gh1_nims_negative_sample_100.csv) contains 100 unique enzyme–substrate–pH–temperature observations: xylobiose 34, cellobiose 33, lactose 33; each of the 24 strata contributes four or five records.
- An independent readback of each CSV source cell against the retained source workbook found 100/100 exact `<0.1` matches, all with `Expression_binary = 1`, and no duplicate observation keys. This verifies transcription/source-cell fidelity for this structured-table sample only; it is not an independent annotator study or an estimate of general NLP precision/recall.
- The full candidate pool contains 1,803 explicit `<0.1` records among NIMS-table rows whose protein IDs join to `Expression_binary = 1`; this is a pool count, not the size of an independently curated biological dataset.

### Candidate-pool granularity and duplicate-condition follow-up

A full source-cell extraction finds that the 1,803 expression-binary-one cells come from 96 proteins and 277 protein–substrate pairs, with 1,800 distinct protein–substrate–pH–temperature keys. 113 of the 277 pairs have below-background values in some conditions and numeric above-background values in others, so “negative” must stay condition-specific. The 100-row sample is 100/100 present in this pool and contains no duplicate condition keys.

The full-table key audit also corrects the earlier 107/108 completeness count: only 106/108 Table 2 proteins have all eight **distinct** pH/temperature keys. `CAJ88232.1` has eight source rows but only seven distinct conditions: rows 694 and 701 both report `<0.1` for all three substrates at pH 8/90 °C, while pH 5/40 °C is absent. `CAA56282.1` has seven rows and lacks pH 8/90 °C. The workbook does not explain the repeated CAJ88232.1 row, so both cells are preserved and flagged rather than deduplicated. Details and full outputs are in [`2026-09-30-gh1-nims-pool-granularity-audit.md`](2026-09-30-gh1-nims-pool-granularity-audit.md).

The 1,803 below-background cells are repeated condition-level readouts, not 1,803 independent negative pairs. The paper reports triplicate experiments, but the supplement supplies aggregate cells rather than individual replicate values; the nominal 5,409 replicates must not be counted as 5,409 individually observed negatives. For any model test, group splits by enzyme–substrate pair to prevent condition-level leakage.

## Cross-supplement coverage reconciliation — unresolved

The extraction exposed a source-integrity issue that must remain visible:

| Check | Count |
|---|---:|
| Supplementary Table 2 assay rows with pH/temperature values | 863 |
| Distinct protein IDs represented in Table 2 | 108 |
| Table 3 rows marked `Expression_binary = 1` | 105 |
| IDs in both sets | 96 |
| Table 2 IDs marked `Expression_binary = 0` in Table 3 | 12 |
| Table 3 expression-positive IDs absent from Table 2 | 9 |
| Table 2 IDs with all eight distinct pH/temperature combinations | 106 of 108 |

The article describes a 105-enzyme soluble-expression NIMS set and 10,080 total experimental conditions. The supplementary crosswalk, using accession/species IDs literally, does not reconcile to that set: 12 Table 2 IDs are marked `Expression_binary = 0`, while nine Table 3 expression-positive IDs are absent from Table 2. The reason is **unresolved**; it may reflect differing definitions, data-release scope, or a source-table issue. This audit does not label it an author error. The 100-record sample was restricted to the 96-ID intersection with `Expression_binary = 1`, but even that restriction cannot explain the nine missing expression-positive IDs.

Table 2 includes three substrates, while the paper states that no maltose activity was observed; its tabulated readout count is not the same object as the headline 10,080 replicate-level assay-condition count. Do not present the supplementary table as a complete reconstruction of all raw replicate data.

### Follow-up audit of the expression field

A second, reproducible audit of all three workbooks found:

- Table 1 and Table 3 contain the same 175 protein IDs, with an exact 175/175 match for Table 1 soluble-expression concentration versus Table 3 `Sol_exp_(mg/ml)`.
- Table 3 contains 105 `Expression_binary=1` and 70 `=0` records. The recorded concentration ranges are completely separated: 0 group 0.0003–0.0253747 mg/ml; 1 group 0.029–1.03 mg/ml.
- This supports treating the field as a binary expression/solubility-status annotation associated with measured soluble-expression concentration, but the supplement does not state the exact operational definition or cutoff. The range separation is an observed association, not proof of a particular threshold or that every `0` means “no protein was expressed.”
- The 12 Table 2 proteins cross-referenced to `Expression_binary=0` each have seven or eight recorded NIMS condition rows. Two also have `Cellobiose NIMS_Activity (Binary)=1` in Table 3. This makes it unsafe to collapse the flag into “assay not performed.”
- Conversely, nine Table 3 proteins marked `1` are absent from Table 2. The paper's main text reports that 105 proteins with soluble expression detected were screened; the retained Table 2 workbook therefore does not straightforwardly reconcile to that narrative. The reason remains unresolved.

The original 100-row sample remains restricted to `Expression_binary=1` as a conservative higher-expression stratum, not because the flag proves that all other records are untested. It still passed source-cell fidelity checks. Do not interpret its 1,803-record pool as the full measured below-background set: all 12 Table 2 proteins flagged `Expression_binary=0` also have assay rows, contributing 273 explicit `<0.1` cells. These should be retained as a separate low-expression stratum because low soluble protein concentration may confound interpretation of weak turnover. See [`2026-09-30-gh1-expression-zero-readout-audit.md`](2026-09-30-gh1-expression-zero-readout-audit.md) and its pair-level output.

Reproducible crosswalk artifacts: [`audit_crosswalk.py`](pilots/gh1-nims/audit_crosswalk.py) and [`gh1_nims_crosswalk_audit.csv`](pilots/gh1-nims/gh1_nims_crosswalk_audit.csv). The CSV preserves all 175 Table 1/Table 3 protein IDs and their Table 2 coverage/status.

## What this changes about the research plan

This establishes that explicit, condition-dependent biochemical non-detections can be extracted from accessible supplementary tables while preserving source coordinates and assay metadata. It does **not** establish retrospective publication bias, unique coverage beyond BRENDA/CAZy, or model benefit from adding these data. Those require separate database joins and controlled model tests. The table mismatch also makes source-level completeness auditing part of any extraction workflow, not an optional cleanup step.

Relevance: **3/3** for extracting and typing molecular-science negative observations; **2/3** for the broader historical-recovery novelty claim because the source is a dense, newly generated screen rather than fragmented prior literature.

## Retained source files and SHA-256

| File | Size | SHA-256 | Role |
|---|---:|---|---|
| `cb500244v_si_002.xlsx` | 105,620 B | `E51E9E0F8820063571B0E790BB94F1F4EF4D611099963FC15BC6F2C0DDD68939` | Supplementary Table 1; candidate proteins and soluble expression |
| `cb500244v_si_003.xlsx` | 104,201 B | `AAA4764B503528FE39F776F59176F33399A91BEC5DE02DD20A0F6832091823D2` | Supplementary Table 2; NIMS mean conversion/CV by assay condition |
| `cb500244v_si_004.xlsx` | 23,233 B | `FAC87A78C3A75D5D5291E58CC9B38EC31B96BF0500BA288285A37AEE7F354A67` | Supplementary Table 3; expression/activity crosswalk |
| `gh1_nims_negative_sample_100.csv` | 29,256 B | `04601081F3C2BC902BCD4DC99B20224A29E004E9BC1D1EE4D0BA137B892228E9` | 100-row, source-cell-linked extraction sample |

The generator requires Python and `openpyxl`. The source artifacts are retained as research inputs; the derived sample is for non-commercial research use consistent with the listed CC BY-NC 4.0 license.
