# Janus-Dataset Search Queries

**Version:** 0.1  
**Date:** 2026-09-03

The query families below are intentionally separated. Combining every term into one query makes the search precise but risks missing work that uses different vocabulary.

## Query family A — Is the problem recognized?

```text
("negative data" OR "negative results" OR inactive OR "failed experiment")
AND
(molecular OR chemical OR bioactivity OR "drug discovery")
AND
(dataset OR database OR benchmark OR "machine learning")
```

```text
("positive-result bias" OR "publication bias" OR "reporting bias" OR "selection bias")
AND
(molecular OR chemical OR bioactivity OR "drug discovery")
```

## Query family B — What counts as negative?

```text
(inactive OR "no activity" OR "low activity" OR "weak activity" OR "poor performance")
AND
(assay OR bioactivity OR "molecular property" OR compound)
AND
(dataset OR database OR label OR benchmark)
```

```text
(failure OR failed OR unsuccessful OR "negative result")
AND
(chemistry OR molecular OR reaction OR synthesis OR catalyst)
AND
(data OR dataset OR mining OR machine learning)
```

## Query family C — Dataset and benchmark bias

```text
("dataset bias" OR "benchmark bias" OR "sampling bias" OR "experimental bias")
AND
(molecular OR chemical OR bioactivity OR QSAR OR "drug discovery")
```

```text
(inactive OR negative OR assay)
AND
("virtual screening" OR "molecular property prediction" OR QSAR)
AND
(bias OR benchmark OR generalization OR leakage)
```

## Query family D — Literature mining and extraction

```text
("literature mining" OR "text mining" OR "information extraction" OR "relation extraction")
AND
(chemistry OR molecular OR chemical OR "drug discovery")
AND
(property OR activity OR assay OR outcome)
```

```text
("negative result extraction" OR "negative information extraction"
OR "failed experiment extraction" OR "unsuccessful reaction")
AND
(scientific literature OR chemistry OR molecular)
```

## Query family E — Weak labels and evidence quality

```text
("weak supervision" OR "weak label" OR "distant supervision" OR pseudo-labeling)
AND
(molecular OR chemical OR bioactivity OR QSAR)
```

```text
(provenance OR uncertainty OR "evidence grounding" OR contradiction)
AND
(molecular dataset OR chemical dataset OR bioactivity dataset)
```

## Query family F — Downstream model impact

```text
(inactive OR "negative examples" OR "negative data")
AND
("molecular property prediction" OR QSAR OR screening OR "drug discovery")
AND
(calibration OR ranking OR generalization OR robustness OR "failure prediction")
```

## Database-specific adaptation

- For PubMed, use title/abstract fields and keep biomedical terms such as assay, bioactivity, toxicity, and compound.
- For OpenAlex, Crossref, and Semantic Scholar, search title/abstract/keyword combinations and use citation expansion.
- For broad web search, use exact phrases for the phenomenon and plain terms for the domain.
- For full-text searches, add `supplementary`, `table`, `inactive`, `failed`, `reduced`, and `not active` only after the first broad pass.

## Search log fields

```text
query_id, query_text, source, date, result_count, retained_count, notes
```
