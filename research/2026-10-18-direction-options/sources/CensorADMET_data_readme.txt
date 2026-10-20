# Benchmark Input

`measurement_records.parquet` is the frozen, measurement-level ChEMBL 36 input used by the released CYP, hERG, and ABCB1 experiments. Each row preserves its activity relation, transformed interval bounds, assay identifier, document identifier, source, publication year, and standardized molecular structure. `endpoints/` contains the ten curated one-row-per-compound–endpoint inputs used by the aggregated endpoint cohort. `admet_endpoints/` contains the solubility, clearance, and half-life inputs used for the broadened-property cohort.

The data are derived from [ChEMBL 36](https://www.ebi.ac.uk/chembl/), which must be cited when the benchmark input is reused. The source database and all original metadata remain attributable to the ChEMBL team. This repository distributes only the curated research input required to audit the accompanying analyses.

`measurement_records.parquet` is an adaptation of ChEMBL data and is released under the [CC BY-SA 3.0 Unported license](../LICENSE_DATA), not the code license. Reusers must preserve the ChEMBL attribution and distribute adaptations under the same license. See [ATTRIBUTION.md](../ATTRIBUTION.md).

The data package is not a claim of assay harmonization or experimental ground truth. Censoring thresholds are assay-specific and the released labels should be interpreted as reported inequalities on the documented transformed scale.

`fixed_splits/` contains compact NumPy archives of the five train/test folds generated with split seed zero. Each archive retains the source row identifiers and integer indices for every train/test fold. The configuration and regeneration command are in `../configs/manuscript-v1.0.0.json` and `../scripts/export_fixed_splits.py`.
