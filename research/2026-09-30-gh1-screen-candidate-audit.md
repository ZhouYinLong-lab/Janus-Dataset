# 2026-09-30 candidate source audit: GH1 high-throughput activity screen

## Why this is relevant

This is a second candidate for designing an observation-level label schema after the CAR supplementary matrix proved inaccessible. It is a biochemical activity screen, not a paper-mining method, and is included only as a comparator for what a well-described measured non-detection looks like.

## Primary-paper evidence

Heins et al. (2014) synthesized and expressed 175 GH1 β-glucosidases and report over 10,000 activity data points (the main-text figure caption gives n=10,080). The multiplexed NIMS assay tested four substrate probes (cellobiose, lactose, xylobiose and maltose) across a range of pH and temperatures. The methods state that enzyme reactions were performed in triplicate; activity was calculated as product/(probe + product), with non-enzymatic hydrolysis controls subtracted. The paper describes nine expressed enzymes with no activity detected against the tested NIMS substrates; for a follow-up set, no detectable activity against the natural carbohydrate substrates was also observed for the nine selected no-NIMS-activity enzymes. A unit/threshold for universal enzyme inactivity is not claimed.

This distinction matters: the observation is “no detectable turnover for these substrates under the tested conditions,” not “this protein can never catalyze any reaction.” The study also describes substrates and assay conditions explicitly enough to seed a small structured annotation exercise.

## Limits as a precedent

- It prospectively generated a large screen; it does not mine historical literature or quantify publication bias.
- It does not compare ML models trained with versus without negative observations.
- NIMS no-detect observations and HPLC follow-up results are not identical measurement modalities; they should remain linked but separately typed.
- The paper's 10,080 assay-point total should not be treated as 10,080 negatives; it is the total screen size.
- Some enzyme candidates showed no soluble expression, a separate technical state from a measured substrate-level non-detection.

## Relevance and decision

Relevance **2/3**. This is a stronger label/context schema comparator than a general NLP paper, but not evidence for the core historical-recovery novelty. It can inform pilot annotation rules and serve as an external measured-screen comparator. It should not determine the project's domain or be used to claim independent model benefit.

## Source

- Heins et al. (2014), *ACS Chemical Biology*, [PMC manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC4168791/), [publisher page / DOI](https://doi.org/10.1021/cb500244v).
