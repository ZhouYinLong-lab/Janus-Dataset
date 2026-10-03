# Beta-glucosidase specificity literature sampling frame: initial screen

**Status:** Search and de-duplication complete; 25/80 consecutive PubMed-ID-sorted records have preliminary title/abstract dispositions. Within this tranche: 12 are queued for full-text review, one has full-text-confirmed eligibility, 11 are excluded at title/abstract stage, and one is unclear. The remaining 55 records have not been screened.
**Search date:** 2026-10-01 (PubMed E-utilities)
**Purpose:** Build a reproducible, denominator-defined paper cohort for estimating how often experimental enzyme-specificity papers expose interpretable negative observations. This is a feasibility cohort, not an estimate of all molecular-science publication bias.

## Search frame

Publication date limited to 2015-01-01 through 2025-12-31. Search fields are title/abstract; exact queries:

1. `(beta-glucosidase[Title/Abstract]) AND (substrate specificity[Title/Abstract]) AND 2015:2025[dp]` — 73 records.
2. `(glycoside hydrolase family 1[Title/Abstract]) AND (substrate specificity[Title/Abstract]) AND 2015:2025[dp]` — 12 records.
3. `(beta-glucosidase[Title/Abstract]) AND (substrate range[Title/Abstract] OR substrate screening[Title/Abstract]) AND 2015:2025[dp]` — 3 records.

The three queries returned 88 hits and 80 unique PubMed IDs (8 duplicate hits). Do not add the individual counts as if they were independent papers. The search was performed through NCBI PubMed E-utilities; its title/abstract vocabulary, date window and single-database scope constrain generalization.

## Intended screening question

Among primary experimental papers about a defined beta-glucosidase (including named enzyme variants) that compare activity across at least two chemically distinct substrates, what fraction make at least one interpretable negative-like observation visible in the article or its supplement, and what evidence/context is retained?

Include at full-text stage if the paper reports a biochemical activity measurement attributable to a defined enzyme/preparation and compares multiple substrate identities or explicitly evaluates substrate specificity/selectivity. Keep papers even if no negative result is visible: those are essential denominator cases.

Exclude from this narrow cohort if it is a review/editorial, entirely computational, measures only bulk environmental/community enzyme activity without an enzyme–substrate observation link, or does not study beta-glucosidase specificity. Record a reason for every exclusion. A broader GH1/GH-family cohort should be a separately declared stratum, not silently merged into the beta-glucosidase cohort.

## Initial title/abstract screen: known boundary cases

These are screening examples, not a completed 80-record adjudication:

| PMID | Initial signal | Screening implication |
|---|---|---|
| [32522206](https://pubmed.ncbi.nlm.nih.gov/32522206/) | PubMed publication type includes Review, but the [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC7288487/) reports heterologous expression, purification, kinetic characterization and enzyme-engineering experiments. It tests multiple named substrates. | **Retain as a primary experimental paper based on content, despite the metadata conflict.** Its Results state that laminaribiose/gentiobiose activity was negligible below 10 U/mg; methods give the panel conditions, while the text does not define 10 U/mg as an LOD. It therefore qualifies as a candidate paper and its outcome is thresholded weak activity rather than a proven zero. |
| [33745010](https://pubmed.ncbi.nlm.nih.gov/33745010/) | Review on microbial diglycosidases | Title/abstract and PubMed type indicate a review; exclude from primary-study denominator after recording reason. |
| [33871765](https://pubmed.ncbi.nlm.nih.gov/33871765/) | Review on unconventional beta-glucosidases | Title/abstract and PubMed type indicate a review; exclude from primary-study denominator after recording reason. |
| [39326155](https://pubmed.ncbi.nlm.nih.gov/39326155/) | Review on plant specialized metabolism | Title/abstract and PubMed type indicate a review; exclude from primary-study denominator after recording reason. |
| [40499858](https://pubmed.ncbi.nlm.nih.gov/40499858/) | Review on beta-glucosidase engineering | Title/abstract and PubMed type indicate a review; exclude from primary-study denominator after recording reason. |
| [26139075](https://pubmed.ncbi.nlm.nih.gov/26139075/) | In-silico ligand-binding study | Likely exclude: no experimental substrate-activity panel in the stated study; verify abstract/full text before final disposition. |
| [27100530](https://pubmed.ncbi.nlm.nih.gov/27100530/) | One-year monitoring of hydrolase activities in wastewater treatment | Likely exclude from this enzyme-specific cohort: community/process-level activity, not clearly a defined enzyme–substrate record. |
| [32758852](https://pubmed.ncbi.nlm.nih.gov/32758852/) | Soil succession and bulk microbial/enzyme activities | Likely exclude from this enzyme-specific cohort for the same unit-of-analysis reason. |
| [33429300](https://pubmed.ncbi.nlm.nih.gov/33429300/) | Microbiome/metabarcoding study | Likely exclude: community composition rather than enzyme-specific substrate measurements. |
| [32277984](https://pubmed.ncbi.nlm.nih.gov/32277984/) | GH35 galactosidase | Off-target for a beta-glucosidase cohort; could enter a separately defined broad enzyme cohort. |
| [32665004](https://pubmed.ncbi.nlm.nih.gov/32665004/) | GH1 beta-mannanase | Off-target enzyme despite GH1 phrase match. |
| [33144261](https://pubmed.ncbi.nlm.nih.gov/33144261/) | Phospho-beta-galactosidase | Off-target enzyme for the narrow cohort. |
| [33449963](https://pubmed.ncbi.nlm.nih.gov/33449963/) | GH3 beta-xylosidase | Off-target enzyme for the narrow cohort. |
| [36194965](https://pubmed.ncbi.nlm.nih.gov/36194965/) | GH12 endocellulase | Off-target enzyme; its GH-family phrase is not enough for inclusion. |

These are boundary examples, not a complete screen and must not be used to report an eligible-paper count. PubMed returned a `Review` publication-type tag for five records, but content inspection confirms that PMID 32522206 reports original wet-lab experiments and a multi-substrate panel. This is a positive eligibility example despite its tag; four other review-like records remain exclusions. Indexing labels alone are insufficient. Complete title/abstract screening for all 80 records, then check full text and supplements for eligible/uncertain records.

### Preliminary continuous screening tranche (PMID-sorted records 36–60)

The first saved batch contains 25 consecutive PubMed-ID-sorted records spanning PMID 32207174 through 37055368. Twelve title/abstract candidates are sent to full-text review, PMID 32522206 is already confirmed as an eligible primary experiment after full-text review, 11 are excluded at the first stage, and PMID 35723691 remains unclear because its abstract emphasizes crystal complexes and binding recognition without establishing a multi-substrate activity panel. The record-by-record decisions and reasons are in [`beta-glucosidase-screening-log.csv`](beta-glucosidase-screening-log.csv). “Include to full text” is not a claim that the full text will meet all criteria; excluded counts are only for this defined narrow beta-glucosidase cohort.

## Outcome coding for the eventual full-text pass

For each included paper, record separately:

- `negative_visible`: explicit no activity/no hydrolysis, reported zero or below-threshold value, or only a relative-low comparison. Do not merge these evidence types.
- `tested_panel_reconstructable`: named enzyme, substrate identity, assay/source location, and conditions can be recovered sufficiently to identify the observation.
- `negative_location`: main text, figure, table, supplement, or not found after checking the available files.
- `context_completeness`: assay conditions, detection threshold/censoring, controls and replicate information as reported; use `not_reported` rather than inferring.
- `supplement_available` and `full_text_available`, with retrieval date and exclusion/unavailable reason.

The denominator must be the set of screened eligible papers, not only papers containing a negative keyword or only papers for which a supplement was easy to download. Report availability exclusions and a sensitivity range if unavailable full texts could change the numerator.

## Mainline relevance and next action

**Relevance: 3/3.** This directly tests feasibility and reporting visibility of negative observations in a tightly specified biochemical literature cohort. It does not establish why negatives are absent, field-wide publication bias, database incremental coverage, or model utility. Next: finish a blinded/reproducible 80-title/abstract screen with one disposition and reason per PMID; retrieve full text/supplements for eligible papers; only then calculate visible-negative frequency and context completeness.

Related records: [`research_tracker.md`](research_tracker.md) T144–T147; [`search_log.csv`](search_log.csv) Q153–Q156; [`beta-glucosidase-screening-log.csv`](beta-glucosidase-screening-log.csv); literature-matrix entry J071 and evidence-ledger item E126.
