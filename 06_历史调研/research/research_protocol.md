# Janus-Dataset Literature Review Protocol

**Status:** working draft  
**Review stage:** Stage 2 — landscape mapping and structured comparison  
**Started:** 2026-09-03

## Working topic

Negative data and negative evidence for AI-ready molecular science datasets.

## Working research question

How does missing, underreported, or poorly contextualized negative evidence affect the reliability of molecular datasets and downstream machine-learning tasks, and can evidence-grounded data integration improve that situation?

## Questions to answer

1. Has this problem been explicitly formulated in molecular machine learning, drug discovery, chemistry, or related fields?
2. How are negative, inactive, failed, low-performance, and relative-negative observations defined?
3. What negative observations are already present in public molecular databases?
4. Where does information loss occur: experiment reporting, publication, curation, or model preparation?
5. Which molecular ML tasks are most sensitive to missing negative observations?
6. What methods exist for extracting negative evidence from papers and supplementary information?
7. How are weak, qualitative, uncertain, or contradictory observations handled?
8. What would constitute a meaningful and feasible contribution for Janus-Dataset?

## Scope for the first pass

The first pass prioritizes small-molecule bioactivity and molecular property prediction because these areas provide established assay concepts, public datasets, and reproducible ML benchmarks. Adjacent evidence from chemistry, materials, toxicology, and biomedical data will be retained when it clarifies a method or a general data-quality issue.

The review is not yet limited to one target, assay, property, or model family. That choice is a later decision based on evidence availability and the size of the research gap.

## Operational definitions

- **Negative observation:** A task-specific observation indicating inactivity, low performance, failure, undesired property, or relative degradation under a stated context.
- **Inactive:** A result below a task- or assay-defined activity criterion. The criterion must be recorded rather than assumed to be universal.
- **Failed / unsuccessful:** An experiment, candidate, reaction, or design that did not meet its stated objective, whether or not a numeric value is available.
- **Relative negative:** A comparison such as `activity(B) < activity(A)` or a reported loss after a structural or procedural change.
- **Weak negative evidence:** A qualitative statement such as inactive, weak, reduced, or no improvement without a directly usable numeric measurement.
- **Unknown / untested:** No observation is available. This must never be silently converted into a negative label.
- **AI-ready:** A context-dependent property of a dataset involving machine readability, label quality, provenance, characterization, coverage, representativeness, and computability. It is not equivalent to class balance.

## Inclusion criteria

Include a paper when it does at least one of the following:

- analyzes inactive, negative, failed, low-performance, or missing observations in molecular or chemical data;
- studies publication, reporting, selection, assay, benchmark, or sampling bias relevant to molecular data;
- constructs or evaluates molecular datasets containing experimentally measured negative observations;
- extracts chemical or molecular observations from scientific literature, especially qualitative or failed outcomes;
- studies weak supervision, uncertainty, provenance, or evidence grounding for molecular labels;
- evaluates how data composition or negative examples affect molecular ML performance.

## Exclusion criteria

Exclude or classify as background when a paper:

- only discusses generic class imbalance with no molecular-data or observation-level relevance;
- uses synthetic negatives or decoys without discussing their relationship to experimentally tested negatives;
- concerns clinical or social-science publication bias without a transferable molecular-data method;
- is only a model architecture paper with no relevant data-quality or label question;
- cannot be verified from an accessible abstract, full text, repository record, or reliable bibliographic source.

## Evidence levels

- **E1 — Direct:** The paper analyzes or releases molecular observations and reports a measurable result.
- **E2 — Methodological:** The paper provides a method directly usable for extraction, curation, or evaluation but does not answer the negative-evidence question itself.
- **E3 — Contextual:** The paper supplies a framework or adjacent evidence for AI-readiness, FAIRness, provenance, or reporting bias.
- **E4 — Lead only:** The record may be relevant but requires full-text verification.

## Planned synthesis

The final synthesis will separate:

1. what is already established;
2. what is plausible but not yet demonstrated;
3. what has not been attempted or has only been attempted partially;
4. what Janus-Dataset can feasibly test with open data;
5. what should be narrowed, dropped, or treated as a limitation.

## Reproducibility notes

Every retained paper should have a stable URL or DOI, search source, retrieval date, relevance label, and at least one evidence note. Claims about novelty will be phrased as findings from the documented search, not as absolute claims that no prior work exists.
