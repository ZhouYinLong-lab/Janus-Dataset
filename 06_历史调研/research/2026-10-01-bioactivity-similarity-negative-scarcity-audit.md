# 2026-10-01 ChEMBL inactives, decoy augmentation, and the unresolved independent value of measured negatives

## Question and relevance

Does recent protein–ligand modeling research (a) use experimentally derived inactive bioactivity data, (b) report a scarcity of reliable negatives, and (c) show that the measured negatives themselves improve model performance?

**Relevance: 2/3** to negative-label utility and the distinction between measured and constructed negatives; adjacent evidence for literature-mining novelty. The task is pairwise bioactivity similarity, not historical extraction of negative source statements.

## What the 2025 paper did

Schottlender et al., “Beyond Tanimoto: a learned bioactivity similarity index enhances ligand discovery,” *Frontiers in Bioinformatics*, published 2025-11-28 ([DOI 10.3389/fbinf.2025.1695353](https://doi.org/10.3389/fbinf.2025.1695353)).

- The authors queried ChEMBL v33 and define active compounds as pChEMBL >6.5 and experimentally verified inactive compounds as pChEMBL <4.5 (roughly Ki ≥30 μM); they also include compounds explicitly annotated inactive in ChEMBL comments. Records between the thresholds are not assigned to either class by those rules.
- Their task is to predict whether two molecules have similar bioactivity for the same protein group. Positive S pairs consist of two actives; N pairs consist of one active and one inactive compound. They train on both ChEMBL-derived inactives and generated DUD-E-style decoys.
- The decoys are target-conditioned and property-matched to actives (molecular weight ±25 Da, logP ±1, rotatable bonds ±2, hydrogen-bond donor/acceptor counts ±1, same net charge, and Tanimoto coefficient <0.3). The paper reports that active–decoy similarity distributions approximate those of active–experimentally-inactive pairs below TC 0.4 (KS D=0.019; Jensen–Shannon divergence 0.02).
- The BSI model uses leave-one-protein-out evaluation, compares to Tanimoto/ChemBERTa/CLAMP, and is additionally assessed on ChEMBL v35 records. These evaluate the combined training/data-construction strategy, not a measured-negative-only intervention.
- In its Discussion, the paper explicitly identifies reliable negative-data scarcity, noting that inactive compounds are typically not reported/published and that improving their availability could strengthen such models.

## What this is—and is not—evidence for

This is a concrete example of measured inactive bioactivity records being used alongside constructed decoys in a molecular model. It shows that researchers treat the two as distinct sources but mix them to obtain enough N-pairs. It also provides a recent published statement about negative-data scarcity.

It does **not** isolate the independent effect of source-confirmed measured inactives: the reported model comparisons do not match training-set size and composition while replacing measured inactives with decoys or other controls. AUC/enrichment gains therefore support the BSI pipeline, not a causal claim that experimentally observed negatives drove the gain. Similarity-distribution matching of decoys to measured negatives is a descriptor-level distributional comparison; it is not proof that each generated decoy is a true non-binder, nor that it preserves assay-level evidence.

Nor is this a literature-mining study. The work queries ChEMBL v33 and builds target-specific decoys; it does not extract negative-result evidence spans, recover full assay context from original papers, or estimate how many source observations are absent from current databases.

## Implications for our question

1. Avoid saying that molecular ML never uses measured negatives: this study explicitly uses threshold-defined ChEMBL inactives and inactive comments.
2. Avoid treating decoys, random negatives, thresholded low-potency measurements, and source-reported no-detect observations as interchangeable. The paper's modeling pool contains a mixture, while the ontology and provenance of a historical source observation are different objects.
3. Existing evidence remains insufficient to answer whether measured negatives provide independent benefit beyond matched sample size, class balance, target-conditioned decoys, or additional positive data. A useful experiment would hold target, test set, train size, feature/model budget, and class ratio fixed while comparing (i) source-confirmed measured negatives, (ii) censored/threshold-derived negatives, and (iii) matched decoys or assumed negatives.
4. The most defensible contribution remains observation-level recovery and comparison of source-confirmed negative evidence, not simply adding “inactive” labels to a predictive model.

## Sources and limits

- Primary article: [Frontiers full text](https://www.frontiersin.org/journals/bioinformatics/articles/10.3389/fbinf.2025.1695353/full), [DOI](https://doi.org/10.3389/fbinf.2025.1695353), [public code](https://github.com/gschottlender/bioactivity-similarity-index).
- Claims above were checked in Methods (inactive thresholds, decoy design and training construction), Results (LOPO and benchmark evaluations), and Discussion (negative-data scarcity).
- We did not rerun the code or independently recalculate model metrics, ChEMBL selection, the negative pool, or decoy purity. The authors' conclusions and reported metrics are not treated as our reproduction.

