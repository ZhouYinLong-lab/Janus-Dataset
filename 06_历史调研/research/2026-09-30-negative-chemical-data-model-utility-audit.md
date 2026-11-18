# Negative chemical data and reaction-model utility: Toniato et al. (2025)

**Date:** 2026-09-30  
**Relevance to the main question:** 3/3 for task-specific model utility; 2/3 for negative-label definition/context; 0/3 for literature extraction or direct bioactivity-model transfer.  
**Paper:** A. Toniato, A. C. Vaucher, T. Laino, M. Graziani, “Negative chemical data boosts language models in reaction outcome prediction,” *Science Advances* 11(24), eadt5578 (2025), [DOI: 10.1126/sciadv.adt5578](https://doi.org/10.1126/sciadv.adt5578). Open-access paper; code archived at [Zenodo 10.5281/zenodo.15132405](https://doi.org/10.5281/zenodo.15132405) and [GitHub](https://github.com/rxn4chemistry/negative_learning).

## The question and the result

The authors test whether negative reaction information can help a pretrained transformer generate correct reaction products, especially when positive training examples are scarce. Their method uses a learned reward model to provide reinforcement-learning feedback; the comparison is against conventional maximum-likelihood fine-tuning (FT). This is a direct model-utility study, not a study of extracting negative observations from papers.

Two data regimes are used:

| Dataset | What a negative means | Main comparison/result | Interpretation limit |
|---|---|---|---|
| RegioSQM20 | The original set supplies positive regioselective outcomes. The study constructs negatives by moving the halogen to an incorrect product position. | Low-data training uses 22 positive and 748 negative examples. Reported positive accuracy on the RegioSQM evaluation is 58.55 for RL vs 54.91 for FT; on the USPTO evaluation it is 59.22 vs 59.43, so the gain is not universal across evaluation sets. | The negatives are constructed incorrect regioisomers, not experimentally observed failed reactions. The paper describes this as a controlled setting. |
| HiTEA | Real high-throughput experimental observations. UV-area yield >1% is positive; all other records are negative. | In the low-positive setting, validation positive accuracy is 0.644±0.015 for RL vs 0.610±0.018 for FT; top-10 test accuracy is 0.441 vs 0.427. The high-positive setting also reports a smaller positive-accuracy increase (0.891 vs 0.877). | “≤1%” is a study-specific threshold, not a universal definition of failure. It can include low but nonzero yields. Only 9 of 130 high-yield products had a low-yield counterpart with identical left-hand-side reactants. |

The article reports five data splits/initialization seeds and explicitly discusses variability and hyperparameter sensitivity. In the controlled set, when the full positive set is used, fine-tuning can be stronger; RL's clearest advantage appears in the low-positive regime. Thus the defensible summary is conditional: the method can use negative information to improve reaction-product prediction under some data regimes, not that adding any negative records necessarily improves any model.

## Is this an independent test of negative data itself?

It is evidence that a procedure *using* negative examples can outperform a conventional fine-tuning baseline in these reaction-generation settings. It is not a fully isolated causal ablation that holds the optimization method fixed and changes only whether negative data are included. RL and FT differ in optimization objective and pipeline, while the reward-model training is part of the RL approach. The evidence is therefore strong for method-level utility, but weaker for a general claim that negative labels alone caused the gain.

Evaluation emphasizes positive accuracy in generated products and top-k correctness. It does not evaluate calibration, negative-class recall, scaffold/OOD transfer, or prospective wet-lab success in this paper. The HiTEA authors also report that only 9/130 high-yield products had an observed low-yield counterpart with exactly the same left-hand-side reactants, limiting direct pair-matched inference about competing outcomes.

## What this changes in our research position

We should no longer say that model-utility evidence is generally absent or merely indirect. There is a recent primary study with real HTE low-yield records and a separate constructed-negative regime. The remaining gap is narrower and more defensible:

1. Existing utility results are task- and method-specific; reaction generation is not molecular bioactivity prediction.
2. Constructed wrong-product negatives and measured low-yield outcomes are not interchangeable.
3. A 1% yield threshold is an operational label, and below-threshold does not always mean “no reaction.”
4. The study does not recover negatives from historical papers or test whether literature-recovered observations add value beyond existing curated negatives/unlabeled data under matched training budgets.

For our project, this paper is a design precedent for stratifying negative sources and performing matched ablations. A more informative follow-up should compare, with the same model and splits: no added negatives, measured assay-specific negatives, unlabeled/unobserved pairs, source-matched synthetic negatives, and other database negatives. It should hold positive counts, total training budget, target/scaffold/time splits, and tuning effort as constant as feasible.

## Reproduction feasibility: initial assessment

The authors provide open code and instructions for extracting the small RegioSQM20 set and USPTO data; the repository explicitly says GPU is needed for the base model, fine-tuning and RL steps. The HiTEA dataset is publicly released in the original authors' repository. A faithful full reproduction therefore requires downloading reaction data, installing a dated Python/model stack, and training the base transformer—not merely running an inference script. The original paper describes a 102,500-step transformer pretraining stage. Before launching a long run, inspect the scripts/checkpoints and estimate GPU memory/runtime; an RTX 5070 Ti does not itself guarantee bit-for-bit reproduction. A feasible first replication target is the small RegioSQM low-positive comparison, then the released HiTEA model-selection/evaluation path if the required inputs are accessible.

## Evidence retained and tracking

- Local article PDF: [`Toniato-2025-negative-chemical-data.pdf`](sources/negative-reaction-learning/Toniato-2025-negative-chemical-data.pdf)
- Main literature matrix: [`literature_matrix.csv`](literature_matrix.csv), J061
- Unified tracker: [`research_tracker.md`](research_tracker.md), T110
- Search log: [`search_log.csv`](search_log.csv), Q119
- Evidence ledger: [`evidence_ledger.md`](evidence_ledger.md), E092

Primary source links: [Science Advances article](https://doi.org/10.1126/sciadv.adt5578), [author code/data instructions](https://github.com/rxn4chemistry/negative_learning), [Zenodo code archive](https://doi.org/10.5281/zenodo.15132405), [HiTEA primary article](https://doi.org/10.1038/s41557-023-01393-w), [HiTEA data and code](https://github.com/emmaking-smith/HiTEA).
