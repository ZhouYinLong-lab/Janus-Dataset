# Theisen et al. kinase integration: public model-table provenance audit

**Date:** 2026-09-30  
**Paper:** Theisen et al. (2024), [Nature Communications DOI 10.1038/s41467-024-52055-5](https://doi.org/10.1038/s41467-024-52055-5).  
**Repository:** [Harmonic-Discovery/activity-integration](https://github.com/Harmonic-Discovery/activity-integration), locally inspected at commit `c185bedde8a7081045bc8414906a5775f4271a1c`.

## What the released model-ready tables contain

The repository README says the relevant prepared data are included in `data/`. The inspected files are:

| File | Rows | Columns/summary |
|---|---:|---|
| `prepped_activities_all_chembl_pubchem.csv` | 210,862 | `canonical_smiles`, `uniprot_id`, continuous `activity_value`, `activity_type`, and three split columns; a leading dataframe index column is also present |
| `prepped_labeled_single_dose_data.csv` | 16,514 | `uniprot_id`, `hgnc_symbol`, `canonical_smiles`, seven binned concentration fields (100–1,000,000 nM) and an `activity_value` label; 423 unique UniProt IDs and 8,348 unique SMILES |

In the activity table, `activity_type` divides into 141,193 `measured` and 69,669 `inferred` rows. Applying the paper's pActivity <=6 cutoff to the released values yields 57,606 measured rows and 60,877 inferred rows on the inactive side; the inferred fraction is 87.4% (60,877/69,669). These are our counts from the authors' prepared CSV, not a separate paper-reported count. “Inactive side” here means the paper's thresholded pActivity interpretation, not that every row is an explicit textual inactive assertion.

The public model-ready activity table does **not** have per-row assay ID, source DOI/publication, raw assay endpoint/relation operator, single-dose readout or experimental condition fields. The POC table retains concentration-bin readouts, but likewise has no per-row source DOI or assay identifier in its schema. It is therefore not possible to recover exact source-paper/table provenance for individual model rows from these two prepared files alone.

## Why this is relevant—and the inference boundary

This audit sharpens the distinction between (1) a model-ready activity label, including measured and POC-derived inferred values, and (2) an evidence-level observation that preserves the assay, publication, conditions, tested/not-tested status, relation operator and source passage/table. The article is a strong example of integrating assay information and prospectively checking predicted inactivity, but its released feature tables are not a source-traceable corpus of negative findings.

The missing columns in the public prepared CSVs do **not** prove that authors' upstream queries or private intermediate files lack provenance. Nor does the inspection establish that the underlying ChEMBL/PubChem records cannot be remapped through other identifiers not included in these files. It only establishes what is and is not directly recoverable from the released model tables as checked at the cited repository commit.

## Janus implication

Do not frame the gap as “bioactivity models have no negative data.” This study uses extensive measured and inferred activity labels and tests low-activity predictions. The defensible gap is narrower: whether source-linked, assay-context-preserving recovery of explicit published negative observations adds coverage beyond existing structured activity records, and whether that incremental evidence helps under fixed-size, source-aware, matched model comparisons.

