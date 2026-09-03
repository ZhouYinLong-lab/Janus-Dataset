# Evidence ledger

**Pass:** 1  
**Date:** 2026-09-03  
**Purpose:** Keep claims separate from interpretation and record what still needs verification.

## Direct evidence

### E001 — Failed experiments can carry predictive information

- **Claim:** Failed or unsuccessful experiments can be used as training observations for discovery models.
- **Source:** [Raccuglia et al., Nature (2016)](https://doi.org/10.1038/nature17439)
- **Evidence:** The study used failed hydrothermal syntheses from archived laboratory notebooks, retained 3,955 complete reactions, and evaluated prospective synthesis recommendations.
- **Interpretation:** This is a strong proof of value for negative outcomes, but it is a materials-reaction case rather than a general molecular bioactivity result.
- **Confidence:** High for the specific case; low for generalization.

### E002 — Constructed negatives can encode benchmark bias

- **Claim:** A model can obtain strong virtual-screening performance by exploiting analogue or decoy bias rather than learning the intended molecular-recognition signal.
- **Source:** [Chen et al., PLOS ONE (2019)](https://doi.org/10.1371/journal.pone.0220113)
- **Evidence:** The paper tested DUD-E and compared ligand-topology behavior with structure-based models.
- **Interpretation:** Synthetic decoys must not be treated as interchangeable with experimentally tested inactive compounds.
- **Confidence:** High for the DUD-E case.

### E003 — Measured inactive records and leakage-aware splits are already used

- **Claim:** Existing activity-model studies curate experimentally measured inactive records and use scaffold, structure, or temporal splits to reduce chemical bias.
- **Source:** [DEEPScreen, Chemical Science (2020)](https://doi.org/10.1039/C9SC03414E)
- **Evidence:** The study explicitly analyzes negative selection bias and builds target-specific datasets from ChEMBL activity records.
- **Interpretation:** A new project cannot claim novelty merely for collecting inactive examples or using scaffold splits.
- **Confidence:** High.

### E004 — Activity data are assay-dependent and labels are not globally interchangeable

- **Claim:** Compound activity datasets contain sparse compound-target observations, assay-specific distributions, measurement effects, and differences between virtual-screening and lead-optimization settings.
- **Source:** [Tian et al., Communications Chemistry (2024)](https://doi.org/10.1038/s42004-024-01204-4)
- **Evidence:** CARA organizes data at assay level and reports sparse labels, heterogeneous distributions, measurement/batch effects, and differences between task settings.
- **Interpretation:** Janus should treat assay and experimental context as part of the observation rather than as optional metadata.
- **Confidence:** High for the analyzed ChEMBL-derived data.

### E005 — Coverage bias is broader than class imbalance

- **Claim:** Widely used small-molecule datasets can under-cover parts of known molecular structure space.
- **Source:** [Kretschmer et al., Nature Communications (2025)](https://doi.org/10.1038/s41467-024-55462-w)
- **Evidence:** The paper proposes an MCES-based coverage measure and reports non-uniform coverage in common datasets.
- **Interpretation:** The AI-ready assessment should include representativeness and chemical-space coverage, not only positive-negative ratios.
- **Confidence:** High for the study’s coverage analysis.

### E006 — A directly overlapping inactive-compound resource exists

- **Claim:** InertDB is a recent resource explicitly built around biologically inactive small molecules.
- **Source:** [InertDB, Journal of Cheminformatics (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11983867/)
- **Evidence:** The paper reports curated inactive compounds from PubChem and a generative expansion, with downstream model comparisons.
- **Interpretation:** Janus must differentiate itself from a database whose central contribution is simply a large inactive-compound collection. The strongest possible distinction is evidence-grounded, context-rich, observation-level negative data, including failures and qualitative evidence.
- **Confidence:** High that the resource exists; medium for the reported downstream gains until independently reproduced.

### E007 — Literature extraction is technically active but not yet standardized end to end

- **Claim:** Chemical literature extraction has expanding LLM capability, but evaluation, ground truth, and domain validation remain central problems.
- **Source:** [From text to insight, Chemical Society Reviews (2025)](https://doi.org/10.1039/D4CS00913D)
- **Evidence:** The review discusses precision, recall, false positives, false negatives, ground truth construction, and the bias toward positive and curated information.
- **Interpretation:** A Janus extraction contribution would need a small human-verified benchmark and source-linked evidence, not just prompts or an extraction demo.
- **Confidence:** High as a methodological landscape statement; the source is a review rather than a dedicated negative-evidence benchmark.

### E008 — AI-readiness is multidimensional and context-dependent

- **Claim:** AI-readiness includes provenance, characterization, explainability, sustainability, computability, and FAIRness; it is not a pass/fail property reducible to class balance.
- **Source:** [Clark et al., AI-readiness Criteria for Biomedical Data](https://doi.org/10.1101/2024.10.23.619844)
- **Evidence:** The Bridge2AI criteria define seven dimensions and evaluate datasets with machine-actionable metadata.
- **Interpretation:** Janus should treat provenance and context as core schema fields and define readiness for a stated molecular task.
- **Confidence:** High as a framework; adaptation to molecular assays remains our work.

### E009 — Large-scale negative bioactivity modeling predates recent resources

- **Claim:** Negative bioactivity data have been incorporated into large-scale molecular target-prediction workflows for more than a decade.
- **Source:** [Mervin et al., Journal of Cheminformatics (2015)](https://doi.org/10.1186/s13321-015-0098-y)
- **Evidence:** The study combined more than 195 million ChEMBL and PubChem bioactivity points, selected presumed inactive compounds, and compared inactivity-inclusive models with active-only models using internal and external evaluation.
- **Interpretation:** Janus cannot claim that using negative bioactivity data in molecular ML is new. The unresolved issue is the scientific status and provenance of the negative observation, not the mere inclusion of a negative class.
- **Confidence:** High for the reported study; medium for generalization beyond target prediction.

### E010 — Open screening infrastructure can preserve both positive and negative pipeline outcomes

- **Claim:** An open chemical-biology infrastructure can store positive and negative activity data from primary and counter-screening assays.
- **Source:** [Škuta et al., ECBD, Nucleic Acids Research (2025)](https://doi.org/10.1093/nar/gkae904)
- **Evidence:** ECBD is designed as a FAIR repository for EU-OPENSCREEN data and explicitly includes primary and counter-screening results.
- **Interpretation:** The project must distinguish retrospective literature recovery from prospective data governance. “Preserving complete assay-pipeline outcomes” is an existing direction; Janus may add value by connecting such records with literature evidence, heterogeneous sources, and a cross-resource evaluation protocol.
- **Confidence:** High for the repository scope.

### E011 — Negative data have also been used to clean activity-related chemical signals

- **Claim:** Negative data have been used in statistical analysis of active-negative chemical correlations, not only as binary labels for classifiers.
- **Source:** [Lee et al., Ligand biological activity predicted by cleaning positive and negative chemical correlations](https://www.repository.cam.ac.uk/items/2a26b764-7e66-4db3-b5d0-2e41192c33c3)
- **Evidence:** The work combines high-quality negative data with a random-matrix-inspired framework to separate activity-related chemical differences from undersampling noise.
- **Interpretation:** The second-pass search must include statistical and representation-learning uses of negatives, not only dataset construction and literature mining.
- **Confidence:** Medium pending full bibliographic and full-text verification.

## Open questions from pass 1

- How often are qualitative negative statements present in molecular papers and supplementary information?
- Can published papers support a defensible estimate of publication bias, or only a reporting/curation bias estimate?
- Which negative categories are most useful: measured inactive, failed experiment, relative decrease, or weak qualitative evidence?
- Can extraction recall and precision be evaluated without a biased ground-truth corpus?
- Does evidence-grounded enrichment improve realistic assay-level or time-split model performance?
- How does Janus differ from older presumed-inactive target-prediction datasets and newer complete screening repositories?
