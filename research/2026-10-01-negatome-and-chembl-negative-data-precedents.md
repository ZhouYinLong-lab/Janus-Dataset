# Negative-result literature and deposition precedents: Negatome 2.0 and ChEMBL

## Why these papers matter to Janus

Two primary sources clarify the novelty boundary from different directions. Negatome 2.0 is a direct precedent for using text mining to guide manual recovery of negative biological relations from papers. ChEMBL's direct-deposition paper explicitly motivates deposition as a way to capture supplementary data and negative results that may not be essential to the published article. Neither paper estimates how often molecular activity negatives are omitted, and neither builds the Janus-style source-linked enzyme/compound–target activity dataset.

## Negatome 2.0: text mining as candidate discovery, human review as evidence adjudication

Blohm et al. (2014) combine literature curation with structural evidence to build a database of non-interacting protein pairs. The text-mining component uses Excerbt to identify negated predicate–argument structures across PubMed abstracts and PMC full text. A broad pass produced 58,733 candidates, only 20% of a manually checked sample of 20 being true negative interactions. Restricting the relation verbs reduced the candidate pool to 2,134; more than half were judged valid in the subsequent evaluation, while precision varied sharply by confidence: 95% for the top 20, 45% for the median 20, and 15% for the bottom 20. The article reports a manually annotated literature set of 2,171 protein non-interactions, including annotations found while reviewers inspected candidate papers beyond the sentence proposed by the system. Species and experimental methods were added during manual review.

The paper also exposes a crucial retrieval/validation trade-off: among 40 randomly selected Negatome 1.0 pairs, Excerbt recovered only one. The authors note that the earlier curation often found negative relations in figures and tables, whereas the new pipeline started from candidate sentences. The text-mining candidate set therefore helped speed curation but did not provide high recall for all previously known evidence.

### What it establishes—and what it does not

- Establishes that literature-level negative-relation mining with manual adjudication and evidence context has been attempted and used to construct a resource.
- Establishes concrete failure modes relevant to Janus: entity ambiguity, negation scope, candidate precision/recall trade-offs, and evidence residing in figures/tables rather than prose.
- Does **not** concern compound–protein bioactivity, enzyme substrate inactivity, censored potency thresholds, assay detection limits, or activity-model utility.
- Does **not** measure publication bias or estimate the number of missing negatives; it is a PPI database/method study, not an assay-outcome corpus.

For Janus, this is a methodological prior-art boundary, not a direct duplicate. A defensible contribution must be more specific than “text mine negative molecular evidence”: it would need assay-grounded entities and typed outcomes, exact evidence spans/table-cell linkage, source/condition provenance, and observation-level comparison against activity databases.

## ChEMBL direct deposition: negative-result omission is recognized, not quantified

Mendez et al. (2019) describe ChEMBL's manually curated literature workflow and propose direct author deposition as a way to reduce transcription errors and capture supplementary data and negative results that might not be essential for the paper itself but could enrich a target's SAR landscape. The same article says ChEMBL contains deposited data sets and discusses schema changes for richer assay/provenance capture.

This is a primary-source statement that published papers may not expose every result useful for SAR. It supports the plausibility of missing-result mechanisms and the value of direct deposition, but it is a rationale for infrastructure—not a representative empirical measurement of publication bias, nor evidence that all unreported results are negative.

## Mainline relevance assessment

| Source | Relevance | Value to Janus | Boundary |
|---|---:|---|---|
| Negatome 2.0 (2014) | 2/3 | Prior art for text-mining negative biological claims, manual verification, provenance context, and retrieval error analysis | Protein–protein non-interaction rather than molecular activity; no assay-level activity labels or model ablation |
| ChEMBL direct deposition (2019) | 2/3 | Documents the recognized need to preserve supplementary and negative results; supports a plausible omission mechanism | Qualitative motivation only; no estimate of omission prevalence or activity-specific negative recovery |

## Evidence-based next step

Treat these papers as comparison strata in the related-work map, not as evidence that the activity-specific question is already solved. The next empirical question remains: among a pre-specified sample of molecular activity papers/assays, which source-confirmed inactive, no-detect, and threshold-censored observations can be recovered, what fraction map exactly to existing resources at the observation/source/condition level, and how reproducible is that adjudication?

## Primary sources

- Blohm et al. (2014), *Negatome 2.0*, [DOI 10.1093/nar/gkt1079](https://doi.org/10.1093/nar/gkt1079), [full text](https://academic.oup.com/nar/article/42/D1/D396/1048129).
- Mendez et al. (2019), *ChEMBL: towards direct deposition of bioassay data*, [DOI 10.1093/nar/gky1075](https://doi.org/10.1093/nar/gky1075), [full text](https://academic.oup.com/nar/article/47/D1/D930/5162468).
