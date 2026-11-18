# Cross-domain negative-data resource update

**Audit date:** 2026-10-02  
**Purpose:** Extend the landscape beyond enzyme and small-molecule bioactivity work, while separating experimentally observed negatives from database-thresholded, inferred, and computationally defined labels.  
**Scope:** Targeted web search and inspection of public dataset cards/repository documentation; not a systematic review, independent data reproduction, or exhaustive source-code audit.

## Bottom line

The new search surfaced two recent resource-level precedents that materially constrain broad novelty claims, but neither is equivalent to a source-grounded corpus of historical experimental negative observations.

1. **NegBioDB** publicly describes a large multi-domain biomedical negative-results database and ML/LLM benchmarks. Its drug–target component draws on ChEMBL, PubChem BioAssay, BindingDB, and DAVIS; its published configuration uses explicit potency cutoffs (for example, inactive at IC50/Ki/Kd >10 μM, positives at pChEMBL ≥6, and an excluded borderline band). This is important prior art for aggregating molecular inactive records and evaluating different negative sampling schemes. The public card's umbrella count and the row count shown for the DTI parquet do not match (30,459,583 versus approximately 25 million); the card is self-authored, and this search did not locate a peer-reviewed article/DOI or independently inspect the complete source datasets. More importantly, its five domains do not share one negative ontology: clinical-trial failure, thresholded DTI inactivity, PPI non-interaction, gene essentiality, and variant benignity are distinct claims. The documentation also lists computational/model-derived sources among some domain inputs. The dataset card's general statement that records are experimentally confirmed should therefore not be generalized to every record without field-level provenance adjudication.

2. **Scandium Labs Solid-State Battery Dataset** is an adjacent materials-science resource whose public repository documents a dedicated `negative.is_negative_result` field. The documented negative reasons are computational/material-screening proxies (e.g. energy above hull >0.025 eV/atom, metallic/electronic-conductor status, and a long Li-hopping-distance proxy). The repository explicitly leaves records with no computable signal unknown (`None`), which is a useful design precedent. However, these labels classify predicted/material properties or candidate suitability; they are not reports that a synthesis failed, an experiment measured no effect, or a paper observed an inactive compound. The repository's own inventory also distinguishes a large DFT structural backbone from a much smaller set of literature-derived experimental transport measurements. No peer-reviewed paper was located in this targeted search; treat repository and dataset-card claims as project documentation pending independent audit.

## Comparison against Janus's central question

| Resource | Molecular-science relevance | What its negative label means | What it demonstrates | What it does not establish |
|---|---:|---|---|---|
| NegBioDB (public Hugging Face dataset card and configuration) | 3/3 for broad negative-resource and benchmark novelty; 2/3 for historical literature recovery | A mixture across domains. DTI uses thresholded records from named activity resources; other domains include trial failure, non-interaction, non-essentiality, and benignity, with source-specific semantics. | A broad, multi-domain resource/benchmark is publicly described; DTI inactivity thresholding and degree-matched/random controls are explicit in its docs. | That all records are experimentally confirmed; that it extracts negative statements from primary molecular papers; that its full counts, provenance, and results have been independently reproduced; or that its DTI records add exact observations beyond source databases. |
| Scandium Labs SSB dataset (repository/dataset documentation) | 2/3 as adjacent materials-data schema precedent; 1/3 for bioactivity | Deterministic computational screening/proxy flags for poor electrolyte candidacy; unknown is retained when evidence cannot be computed. | A typed negative-status block with reason, raw evidence, confidence, and an explicit unknown state; a model-evaluation task is documented. | Experimental synthesis failure recovery, measured inactive bioassays, publication-bias estimation, or source-grounded negative extraction from papers. |

## Implication for scope and novelty

The safe claim is no longer “there is no unified negative-data resource in molecular science.” At least one recent public project claims a cross-domain biomedical resource, and at least one materials project exposes computational negative-result labels with explicit unknown handling. These claims must be cited as **project-reported and not yet independently verified here**.

The distinction that remains potentially meaningful is the *evidence object*: a tested molecular/material system; a source-linked observation; the author's outcome relation (numeric, censored, explicit no-detect, weak/relative, or failure); assay/synthesis context; and a clear separation from not-tested, model-inferred, and computationally screened labels. The proposed work must first test whether such source-grounded observations are incrementally missing from existing resources and whether preserving them changes a controlled downstream evaluation.

This update also argues against describing the target as a single universal “negative dataset.” A defensible cross-domain design would need a shared evidence/provenance envelope around domain-specific outcome ontologies, not a forced common binary label.

## Evidence and verification limits

- NegBioDB sources inspected: [public Hugging Face dataset card](https://huggingface.co/datasets/jang1563/NegBioDB), [public configuration](https://huggingface.co/datasets/jang1563/NegBioDB/blob/main/config.yaml), and [public safety-repository description of withheld parent materials](https://github.com/jang1563/negbiodb-safety-calibration/blob/main/SAFETY.md). The Hugging Face viewer did not expose data rows in the browser used for this audit. The publicly linked parent GitHub route could not be inspected as an accessible repository in this pass.
- Scandium sources inspected: [repository README](https://github.com/ScandiumLabs-in/Scandium-Labs-Solid-State-Battery-Dataset), [negative-result definition/release notes](https://github.com/ScandiumLabs-in/Scandium-Labs-Solid-State-Battery-Dataset/blob/main/AGENTS.md), [dataset card/site overview](https://scandium-labs.com/dataset), and [technical documentation](https://github.com/ScandiumLabs-in/Scandium-Labs-Solid-State-Battery-Dataset/blob/main/DOCUMENTATION.md). This is documentation-level inspection, not independent validation of the released rows or benchmark.
- Counts and versions may change; the values above are transcribed as displayed by the respective public pages during this audit. The NegBioDB count mismatch is an audit flag, not evidence of misconduct or a resolved error.

## Next checks

1. If NegBioDB is accessible in a stable version, inspect DTI row-level provenance and reproduce a small stratified sample from each source and evidence tier; verify whether paper/full-text extraction occurs or whether this is source-database aggregation.
2. For Scandium, inspect the released negative parquet and task construction to verify which feature columns define each label, class prevalence, and whether evaluation excludes all defining/leaky variables under every split.
3. Continue broad landscape work only where it can clarify evidence type, exact source coverage, or independent model utility. Do not let these adjacent resources displace the still-open source-grounded bioactivity/enzyme pilot.
