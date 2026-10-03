# 2026-10-01 Assay-Aware BindingDB: direct prior art for literature-derived assay context, not negative-result recovery

## Why this paper matters

Wu et al. posted the arXiv preprint *Assay-Aware BindingDB: Curating Experimental Context for Binding Affinity Prediction* on 2026-09-27 (arXiv:2609.34001). It is unusually close to the broad version of our proposed contribution: the authors link BindingDB protein–ligand records to primary papers, extract experimental assay context, structure it, evaluate extraction against expert references, and test whether the context improves a molecular prediction model. This is a preprint, not yet peer-reviewed evidence.

**Mainline relevance: 3/3.** It changes the novelty boundary and should be included in any related-work map. It does not answer the narrower question of whether source-grounded biochemical negatives can be recovered beyond curated activity databases.

## What the authors report

- The resource augments **74,425 BindingDB protein–ligand pairs** across ITC, SPR, RBA, and FPA with structured assay metadata extracted from linked literature. Candidate selection begins with 113,311 BindingDB pairs; the pipeline retrieves 5,991 papers and retains records with accessible source text and ontology-conforming assay context.
- The two-stage pipeline first localizes evidence spans in the paper, figures, tables, captions, supplementary files, and (when needed) cited protocol papers; a second model maps those spans into assay-specific ontology fields. Each extracted context unit is intended to carry a provenance tag.
- Against expert-curated references from 30 sampled papers per assay type (120 papers total), the paper reports presence F1 from 0.947 to 0.987 and semantic content accuracy from 0.913 to 0.994, depending on assay type/metric.
- A context-conditioned Boltz-2 affinity model is evaluated on a paper-level held-out split. Authors report combined-regime MSE 1.27→1.19 and Pearson correlation 0.64→0.67; gains vary by assay type, with no improvement for ITC.
- The implementation uses Qwen3.5-27B for extraction and Qwen3-Embedding-8B for context encoding. The model experiment uses a modified Boltz-2 affinity module.

These are the authors' reported methods/results, not independently reproduced here.

## What it does not establish for our question

The paper's unit is a BindingDB protein–ligand **affinity record** with assay metadata. Its declared assay types and outputs center on Kd, Ki, and IC50 measurements and on harmonizing protocol context for affinity prediction. The paper does **not present a task, label ontology, benchmark, or result for recovering source-confirmed inactive/non-binder, below-threshold, no-detect, failed, or other negative-outcome observations**. It therefore is not evidence that these negative observations are comprehensively absent from BindingDB or that they are missing from the extracted 74,425-pair resource; those specific coverage questions remain untested in the preprint.

This is also not a broad “all molecular science” dataset: it is limited to four protein–ligand binding assay types and records already indexed in BindingDB. Its value is that it demonstrates the neighboring workflow—literature evidence localization, structured context, quality evaluation, and model utility—in a specific positive-affinity setting.

## Implication for Janus-Dataset

Reject these broad novelty formulations:

1. “No one has extracted experimental context from molecular literature into a structured dataset.”
2. “No one has shown that literature-derived assay context can improve a molecular ML model.”

Both are directly challenged by this preprint, subject to its not-yet-peer-reviewed status and reported evaluation limits.

Potentially defensible, narrower questions remain:

1. Can explicitly reported negative outcomes (e.g., inactive/non-binder with tested concentration, censored bounds, no-detect, no hydrolysis) be recovered as **separate source-grounded observations**, with entity, assay, conditions, threshold/LOD, source span, and certainty retained?
2. For those source-confirmed observations, what fraction is already represented at the same observation/source/assay-condition level in BindingDB, ChEMBL, PubChem BioAssay, BRENDA, or SABIO-RK?
3. Do source-confirmed negatives improve a matched downstream task beyond gains explained by adding examples, class rebalancing, or replacing assumed negatives? This preprint's context-conditioned affinity gains do not answer that causal question.

The adjacent work still overlaps on extraction architecture and context-to-model utility, so any proposed method should differentiate on **outcome direction/semantics, censoring and detection limits, source-to-database traceability, and a matched negative-data ablation**, rather than merely using an LLM or retaining assay context.

## Evidence and caveats

- Primary preprint: [arXiv:2609.34001](https://arxiv.org/abs/2609.34001); [HTML full text](https://arxiv.org/html/2609.34001).
- Preprint status checked on 2026-10-01; arXiv v1 was submitted 2026-09-27.
- Core claims above are taken from the preprint's abstract, Methods, dataset construction, extraction evaluation, model evaluation, and limitations. No source code/data repository was identified in the arXiv record inspected; this is only a bounded page inspection, not proof that none exists elsewhere.
- The paper's non-treatment of negative outcomes is stated as a scope boundary based on the described data unit, schemas, tasks, and reported results. It is **not** a claim that none of its underlying source papers or BindingDB records contain any negative evidence.
- Extraction accuracy is evaluated on 120 papers, while the model utility claim comes from the authors' selected four-assay dataset and one stated paper-level split. We did not independently audit its annotations, split, or model outputs.

