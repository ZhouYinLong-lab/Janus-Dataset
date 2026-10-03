# Theisen et al. (2024): kinase inactivity prediction and activity-data integration

**Paper:** Theisen R, Wang T, Ravikumar B, Rahman R, Cichońska A. “Leveraging multiple data types for improved compound-kinase bioactivity prediction.” *Nature Communications* 15, 7596 (2024). [DOI](https://doi.org/10.1038/s41467-024-52055-5).  
**Retained copy:** earlier bioRxiv manuscript `research/sources/kinase-negative-utility/Theisen-2024-biorxiv-preprint.pdf` (not the final publisher PDF). The publisher PDF endpoint returned an HTML challenge page in this session; the final article was checked in the indexed PMC full text and Nature PDF text.  
**Code/data:** [author repository](https://github.com/Harmonic-Discovery/activity-integration); the article also cites [Zenodo 10.5281/zenodo.12806494](https://doi.org/10.5281/zenodo.12806494).

## What the study did

The study integrates two experimental readout types for compound–kinase pairs: single-dose point-of-concentration (POC) percentage-inhibition measurements and dose–response affinity measurements (IC50/Ki/Kd), drawing on ChEMBL and PubChem. It first trains a random forest to map POC measurements to IC50-like potency, then adds inferred activities to the training data for five second-stage models. The authors state that around 40% of kinase activity records in ChEMBL are POC-only; their integration step inferred activity values for about 70,000 previously unlabeled compound–kinase pairs with measurements in at least two concentration bins but no IC50/Ki/Kd. Most inferred pActivity values were <=6 (their inactive threshold, corresponding to activity >=1 µM), but these are model-derived labels, not explicit negative statements mined from text.

Across compound–kinase, compound, and chemical-cluster evaluation settings, the two-stage models generally improve on models trained only with measured dose-response pActivities. In a supplemental 10-fold cluster comparison of pairwise kernel ridge regression and one deep-learning model, the authors report improvement in 57/60 evaluations. The comparison does not isolate a negative-label effect: it adds POC-derived inferred labels and substantially more training examples, while retaining the original measured values.

The paper separately evaluates the model's ability to predict inactivity prospectively. It selected 50 compound–kinase pairs predicted at pActivity <=5.5, measured them in a KINOMEscan assay, and defines experimental inactivity as <=25% inhibition at 1,000 nM. Reported negative predictive value is 78%. This validates a practically relevant negative-prediction use case; it is not a controlled comparison of training with versus without verified inactive examples.

## What this changes for Janus

- It weakens any broad claim that kinase/bioactivity work ignores negative prediction or never experimentally validates predicted inactives.
- It confirms a useful route for recovering *implicit experimental evidence*: single-dose readouts may contain information about pairs that never progressed to dose-response follow-up.
- It does **not** demonstrate literature NLP extraction of explicit inactive/no-detect/non-substrate statements, preservation of sentence/table context, or restoration of missing per-assay negative records.
- It does **not** identify an independent causal benefit of negative examples: the principal utility comparison combines extra training volume, a new measurement type and inferred continuous potency labels.
- Its 78% NPV is conditional on the chosen predicted-inactive cohort, target panel, assay concentration and authors' <=25% inhibition threshold; it should not be presented as a general model performance figure.

## Relevance score

**3/3 for the broad Janus question, but only 1/3 for literature-recovery novelty.** This is strong, direct bioactivity precedent for using heterogeneous assay readouts and prospectively testing inactive predictions. For our specific question—whether context-preserving extraction of previously unstructured historical negative observations adds information that structured databases miss—the paper is adjacent, not a completed solution. It also argues that a plausible pilot should compare source-linked observed negatives against (a) only dose-response data, (b) POC-derived/inferred labels, and (c) constructed negatives under fixed data/model budgets.

## Verification and caveats

The article and author repository are publicly accessible. The local reproduction was not attempted in this audit; code/data availability alone is not treated as proof that the reported results reproduce. All counts and results above are author-reported. The article states that POC data generated for the work are in Supplementary Data 1 and training data/code are in the author repository.

