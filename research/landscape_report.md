# Stage 2 landscape report — first pass

**Date:** 2026-09-03  
**Status:** preliminary; based on the seed search documented in [`search_log.csv`](search_log.csv)  
**Scope:** small-molecule bioactivity and molecular ML, with adjacent chemistry and materials evidence retained when directly informative.

## Executive assessment

The broad premise is supported, but the original version is not yet a sufficient novelty claim.

There is already substantial work on:

1. experimentally measured inactive compounds and negative examples;
2. dataset, benchmark, scaffold, decoy, and sampling bias;
3. using failed experiments for materials discovery;
4. chemical literature extraction;
5. provenance and AI-readiness criteria.

The most important new finding in this pass is the existence of InertDB, a 2025 resource explicitly centered on biologically inactive small molecules. This makes “build a negative molecular database” too close to existing work. Janus needs a sharper contribution.

## Second-pass correction

The targeted follow-up found that the direct precedent is older and broader than the first pass suggested. Mervin et al. used presumed-inactive ChEMBL and PubChem data for large-scale target prediction in 2015, and ECBD now preserves positive and negative results from primary and counter-screening assays. Lee et al. also used high-quality negative data to study active-negative chemical correlations.

The novelty risk is therefore not limited to InertDB. The project must avoid claiming that negative bioactivity data have not been used, that negative-data resources do not exist, or that adding an inactive class is itself a new contribution.

## What appears established

### 1. Negative observations can be useful

The Nature study by Raccuglia et al. used failed synthesis reactions from laboratory notebooks to train a model and guide new experiments. This demonstrates value in a concrete materials setting, but does not establish that all negative molecular observations are useful or transferable across tasks.

### 2. Public activity data already contain inactive records

ChEMBL-derived and PubChem-derived workflows use experimentally measured inactive outcomes. Some benchmark studies explicitly analyze negative-selection or decoy bias. Therefore, the research question is not whether negative data exist at all.

### 3. Context changes the meaning of a label

CARA shows why a compound activity value should be tied to assay, target, measurement type, condition, and data source. A global `molecule = negative` label is scientifically inadequate.

### 4. Benchmark performance can be misleading

DUD-E and other benchmark analyses show that high scores can come from chemical or decoy artifacts. Random splits and synthetic negatives are not enough to establish real-world usefulness.

### 5. Literature mining is feasible but evidence quality is unresolved

Chemical information extraction is an active area. The unresolved part for Janus is not whether an LLM can extract a sentence, but whether the extracted negative observation is correctly linked to the molecule, task, context, outcome, and source evidence.

### 6. Negative data have already shown model and analysis value

Earlier target-prediction work reported gains from including presumed-inactive data, and other work used negative data to disentangle active-negative chemical correlations. The remaining question is not whether negative data can ever help, but which types of negative observation help which task, under which validation design, and with what reliability.

## What is not established by this pass

The following claims should not yet be made:

- that molecular papers universally contain only positive results;
- that publication bias is the dominant source of missing negative data;
- that adding more inactive compounds improves every molecular ML task;
- that qualitative negative statements can be converted into reliable numeric labels;
- that no one has built a negative molecular dataset;
- that an LLM-based extraction pipeline will be reliable without human-verified evaluation.

## Current gap hypothesis

The most defensible gap hypothesis is:

> Existing work treats negative data mainly as inactive examples, decoys, failed reactions, or model-side bias variables. There is room for a context-preserving and evidence-grounded representation that distinguishes tested negative observations from unknown or untested cases, records qualitative and relative evidence without inventing numbers, and evaluates whether the resulting data improves realistic molecular ML tasks.

This is a hypothesis from the first-pass landscape, not a final novelty conclusion.

## Candidate contributions ranked by strength

### Strongest candidate: evidence-grounded negative observation benchmark

Build a small, human-verified corpus in which each observation contains:

```text
molecule/entity
task or property
target or system
assay / experimental context
observation type
numeric value or qualitative relation
source DOI
evidence span / table / page
confidence
contradiction status
```

The benchmark should explicitly separate `unknown`, `not tested`, `inactive`, `failed`, `low performance`, and `relative decrease`.

### Strong candidate: realistic evaluation of negative-evidence enrichment

Compare the original dataset, ordinary inactive augmentation, and evidence-grounded augmentation under assay-level, scaffold-level, and temporal splits. Evaluate calibration, ranking, enrichment, and failure prediction in addition to classification metrics.

### Moderate candidate: negative-result extraction method

Develop an extraction pipeline only if the first corpus shows that the task is difficult enough and existing extraction systems do not already solve it. The pipeline should be judged against a gold set and should abstain when evidence is ambiguous.

### Weak candidate: another large inactive compound database

This is not recommended as the primary contribution because InertDB is already a direct precedent and because generated inactive molecules are not equivalent to experimentally tested negatives.

## Recommended next decision

Do not enter large-scale dataset construction yet. Complete a second, targeted pass focused on the three closest overlaps:

1. InertDB and other inactive-compound resources;
2. literature or patent extraction of activity status and failed outcomes;
3. studies evaluating negative data under realistic molecular ML splits.

The second pass should answer whether the proposed gap is genuinely underexplored or merely scattered across different vocabularies.

## Go / narrow / stop criteria

### Go

Proceed if we find that no existing work provides all of the following together:

- observation-level negative definitions;
- explicit unknown-versus-negative distinction;
- experimental context and provenance;
- human-verified extraction or curation;
- realistic downstream model evaluation.

### Narrow

Narrow to a specific assay, target family, property, or evidence type if the general molecular scope produces inconsistent definitions or inaccessible data.

### Stop or pivot

Stop the current framing if a recent resource already provides the complete schema, evidence links, validation corpus, and downstream evaluation. Possible pivots would then be a better benchmark split, contradiction handling, or a domain-specific extension.

## Sources used in this pass

- [Raccuglia et al. — failed experiments and materials discovery](https://doi.org/10.1038/nature17439)
- [Chen et al. — hidden DUD-E bias](https://doi.org/10.1371/journal.pone.0220113)
- [DEEPScreen — measured inactive data and bias-aware benchmarks](https://doi.org/10.1039/C9SC03414E)
- [Chemical property prediction under experimental biases](https://doi.org/10.1038/s41598-022-12116-5)
- [CARA — real-world compound activity benchmark](https://doi.org/10.1038/s42004-024-01204-4)
- [InertDB — biologically inactive small molecules](https://pmc.ncbi.nlm.nih.gov/articles/PMC11983867/)
- [Mervin et al. — target prediction using negative bioactivity data](https://doi.org/10.1186/s13321-015-0098-y)
- [Lee et al. — cleaning positive and negative chemical correlations](https://www.repository.cam.ac.uk/items/2a26b764-7e66-4db3-b5d0-2e41192c33c3)
- [ECBD — European chemical biology database](https://doi.org/10.1093/nar/gkae904)
- [Coverage bias in small molecule machine learning](https://doi.org/10.1038/s41467-024-55462-w)
- [LLM-based chemical data extraction review](https://doi.org/10.1039/D4CS00913D)
- [AI-readiness Criteria for Biomedical Data](https://doi.org/10.1101/2024.10.23.619844)
