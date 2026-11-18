# Bosc et al. (2019): literature-derived ChEMBL records and censored activity labels in large-scale QSAR

**Paper:** Bosc et al., “Large scale comparison of QSAR and conformal prediction methods and their applications in drug discovery,” *Journal of Cheminformatics* 11, 4 (2019), [10.1186/s13321-018-0325-4](https://doi.org/10.1186/s13321-018-0325-4).  
**Audit date:** 2026-09-30  
**Main-project relevance:** 2/3 as prior art for literature-sourced, threshold/censor-aware bioactivity modeling; not a direct negative-data utility experiment or historical extraction evaluation.

## What the study did

The authors compared random-forest QSAR and Mondrian conformal prediction on ChEMBL-derived data for 550 human protein targets, followed by temporal evaluation using a later ChEMBL release. For the main ChEMBL extraction, they selected literature-source records (`src_id=1`) after excluding potential duplicates, records with validity comments, and activity comments “inconclusive” or “undetermined”; they also included DrugMatrix profiles as a separate source.

The methods say pChEMBL is calculated only for records with standard relation `=` and that a set of “high quality inactive data” was additionally selected from the same activity types, with standard relation `<`. Pair-level duplicates (including stereochemistry-collapsed structures) were summarized by median activity. Classes were then assigned using protein-family thresholds or, when needed, a default 6.5 log-unit threshold. The final modeling set contained 550 targets. The paper reports mean QSAR sensitivity 0.80, specificity 0.81 and correct classification rate 0.81 over 100 repeated splits; these are model-performance results on the assembled active/inactive dataset.

## What this does and does not establish

This is a substantial precedent for building target-specific classifiers from literature-sourced ChEMBL measurements while retaining non-equality relation records in the data-selection procedure. It makes a broad “nobody has used measured negative bioactivity data in models” claim untenable.

However, the paper's main comparison is **QSAR versus conformal prediction**, not a matched intervention comparing the same model with versus without the relation-`<` records. The reported sensitivity/specificity therefore does not quantify the independent benefit of adding those observations. The work also consumes ChEMBL-curated records rather than recovering source-level negative statements from papers, and the reported aggregate pair median does not preserve the full set of source measurements as a model-ready provenance object.

One point requires careful interpretation: a relation-coded concentration bound is not automatically a definite inactive label. Its inequality must be interpreted in the original endpoint/unit and compared with the target-specific decision threshold. The article's methods summarize the selection and labeling pipeline at scale; we did not reproduce its row-level ChEMBL query or resolve every censored record's class implication. Therefore this audit records the paper as evidence that such records were incorporated, not as proof that every relation-`<` observation is a valid negative or was categorized correctly.

The QSAR-versus-conformal-prediction comparison also received a published letter criticizing generalization, variability reporting, validation description and treatment of uncertain conformal predictions; the authors replied that they found no errors, clarified the repeated-split procedure and defended their implementation. This exchange concerns interpretation and reporting of the model comparison, not an independent audit of the relation-coded inactive-label construction. It neither upgrades this paper into a negative-data ablation nor invalidates the narrower prior-art fact that the published workflow selected those records.

## Relevance to Janus-Dataset

- **Prior-art impact:** narrows novelty. A curated, large-scale activity-modeling workflow using literature-sourced ChEMBL records and non-equality relations already exists.
- **Still open:** whether the original paper/SI source contains recoverable negative context not represented in ChEMBL; how often censored results can be assigned unambiguous classes under assay-specific thresholds; and whether source-linked additions improve models beyond matched sample-size/class-balance controls.
- **Design implication:** retain raw relation, value, unit, endpoint, assay and source for each observation; do not collapse a censoring boundary to an exact scalar or binary negative without checking the threshold logic.

## Sources

- [Publisher full text](https://link.springer.com/article/10.1186/s13321-018-0325-4)
- [PubMed record](https://pubmed.ncbi.nlm.nih.gov/30631996/)
- [Full-text source mirror indexed by Europe PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6690068/)
- [Letter to the Editor](https://doi.org/10.1186/s13321-019-0387-y) and [authors' reply](https://doi.org/10.1186/s13321-019-0388-x)
