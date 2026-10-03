# 2026-10-01 Matched-budget sensitivity analysis of low-activity inferred kinase labels

## Question and relation to the main project

Does replacing an equal number of measured kinase–compound training records with model-inferred low-pActivity records change activity regression or inactive-threshold classification?

**Relevance: 2/3.** This is a feasibility check on the broad “do negative-like labels help?” question and directly challenges attribution of Theisen et al.'s reported gains. It uses model-inferred labels, not source-confirmed inactive measurements, so it does not test historical literature recovery or Janus data directly.

## Source, design, and verification

The local input is the author's prepared `prepped_activities_all_chembl_pubchem.csv` from the Theisen et al. (2024) author repository, retained at [`research/reproductions/kinase-activity-integration/data/`](reproductions/kinase-activity-integration/data/). The source file has 210,862 unique compound–target rows: 141,193 marked `measured` and 69,669 marked `inferred`. Within the inferred rows, 60,877 have pActivity ≤6 and 8,792 have pActivity >6. The paper's threshold of 6 is an operational potency threshold; it does not convert inferred pActivity values into experimental negative observations.

The fixed-budget design is paired within each of five random seeds and run under all three supplied splits (`cluster_split_set`, `ligand_split_set`, `ck_split_set`):

1. Take the split's measured training pool and reserve the same N rows for one of three arms.
2. Keep the remaining measured rows as a common training core across the arms.
3. Fill the reserved N rows with either measured records (control), inferred pActivity ≤6 (low-activity arm), or inferred pActivity >6 (high-activity control).
4. Evaluate all arms on the same split's measured-only held-out test set.

N was set to 2,000 and 8,000. All arms within each split/seed have identical training size; no hyperparameter tuning was performed. The model is a fixed Ridge regression (`alpha=10`) over 512-bit radius-2 Morgan fingerprints, UniProt one-hot features, and target-specific fingerprints. It is a simple local baseline, not the authors' random forest / pairwise-kernel / deep-learning suite. Test outcomes are thresholded at pActivity ≤6 only for the secondary classification metrics.

The reproducible runner is [`matched_inferred_low_ablation.py`](reproductions/kinase-activity-integration/matched_inferred_low_ablation.py). Full outputs: [`matched_inferred_low_ablation_results.json`](reproductions/kinase-activity-integration/matched_inferred_low_ablation_results.json) (N=8,000) and [`matched_inferred_low_ablation_n2000.json`](reproductions/kinase-activity-integration/matched_inferred_low_ablation_n2000.json) (N=2,000). Smoke outputs use N=200 and are not used in the interpretation.

## Paired results: low-inferred arm minus measured replacement control

Positive ΔMAE means regression worsened; positive Δrecall means more held-out measured observations below the paper's pActivity cutoff were identified. All deltas are means across five paired seeds.

| Split | N replaced | ΔMAE | Δinactive precision | Δinactive recall | ΔF1 | Δbalanced accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Chemical cluster | 2,000 | +0.003636 | −0.008082 | +0.018893 | +0.005798 | +0.003259 |
| Chemical cluster | 8,000 | +0.009805 | −0.018014 | +0.040297 | +0.011208 | +0.006247 |
| Ligand | 2,000 | +0.000661 | −0.000259 | +0.002189 | +0.001157 | +0.000842 |
| Ligand | 8,000 | +0.003244 | −0.001804 | +0.001961 | +0.000362 | +0.000175 |
| Compound–target | 2,000 | +0.000901 | −0.002630 | +0.000758 | −0.000683 | −0.000615 |
| Compound–target | 8,000 | +0.003504 | −0.004074 | +0.002596 | −0.000242 | −0.000346 |

The high-inferred control did not produce uniform improvement either. For example, at N=8,000 it reduced cluster-split MAE by 0.011227 but increased ligand- and compound–target-split MAE by 0.006022 and 0.006131, respectively. See the JSON for every seed and metric.

## Interpretation

- Under this model and budget, low-pActivity inferred rows consistently shift the threshold classifier toward higher inactive recall, but also lower precision; the regression MAE worsens in all three splits.
- The trade-off is clearest for chemical-cluster holdout. For ligand and compound–target splits, the F1/balanced-accuracy changes are negligible and do not consistently favor the low-inferred arm across sample budgets.
- Thus, these local results do **not** support the claim “more negative-like examples improve the model overall.” They suggest that the apparent value depends on endpoint, metric, split, and the provenance/quality of the added labels.
- This is a matched-count *replacement* experiment, not a comparison of full measured-only training against a larger augmented set; it controls sample count, but answers a different question from the authors' full-data integration experiment.

## Limitations / next validation

1. Inferred pActivity values are model predictions from POC assay measurements; they are not source-confirmed non-binder or no-detect assay observations. The low group is only negative-like under the paper's threshold.
2. A single Ridge architecture and fixed regularization cannot stand in for the original model suite. No feature/model tuning or confidence intervals over compounds/targets were performed; the five seeds characterize sampling variability under this setup, not scientific uncertainty.
3. The “measured replacement” arm removes N measured examples to maintain equal budget. The result cannot be interpreted as the value of *adding* historical negatives when training examples are otherwise held constant.
4. The result cannot estimate publication bias, extraction accuracy, database novelty, or utility of source-linked literature negatives. It establishes that this particular controlled comparison is computationally inexpensive on CPU and does not require GPU training.
5. A decisive follow-up would use a sufficiently large, independently source-adjudicated set of measured inactive/censored observations, keep target and assay-grouped test sets fixed, and compare source-confirmed negatives against matched decoys, inferred/PU negatives, and measured positives at equal count and class ratio across at least one nonlinear baseline.

## Primary source

Theisen et al., *Leveraging multiple data types for improved compound-kinase bioactivity prediction*, *Nature Communications* (2024), [DOI 10.1038/s41467-024-52055-5](https://doi.org/10.1038/s41467-024-52055-5). The source paper's reported model gains and prospective inactive-prediction experiment are summarized separately in [`2026-09-30-kinase-negative-prediction-prior-art-audit.md`](2026-09-30-kinase-negative-prediction-prior-art-audit.md); this file reports only our local sensitivity analysis.

