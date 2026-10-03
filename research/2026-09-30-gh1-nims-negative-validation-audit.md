# 2026-09-30 GH1 NIMS negative-label scope and orthogonal-validation audit

## Question and relevance

Does the Heins et al. GH1 study provide evidence that its NIMS below-background observations are meaningful experimental negatives, and how broadly should those labels be interpreted?

Relevance: **3/3** to negative-label semantics and validation; **2/3** to extraction schema and feasibility; **1/3** to model utility. The paper does not train a predictive model or test whether adding negative observations improves one.

## Evidence checked

The primary article reports a phylogenomically selected set of 175 synthesized GH1 proteins and 10,080 total assay data points. The NIMS screen used a multiplexed probe mixture, reaction pH and temperature conditions, triplicate experiments, and subtraction of nonenzymatic hydrolysis measured by negative controls. The paper reports activity for 59/105 soluble-expression-positive enzymes on cellobiose, 50/105 on lactose, and 7/105 on xylobiose; roughly one third showed no detected activity against any tested NIMS substrate. No maltose activity was observed across the set. These are assay-scoped outcomes, not counts of negative records in the supplement.

For follow-up, the authors selected 28 diverse enzymes for HPLC profiling, including nine with no NIMS-substrate activity. They report that these nine also had no detectable activity against any of the natural substrates in the follow-up panel. Conversely, all 19 enzymes reported as active toward NIMS substrates were active against corresponding natural substrates under the conditions identified by the screen, although xylobiose activity was sometimes only trace-level (<0.03 U mg⁻¹). This is useful orthogonal support for the study's no-detect signal, but the nine negative enzymes are not named in the article text and are not mapped there to individual Supplementary Table 2 `<0.1` cells. It therefore does not establish per-record HPLC validation for the extracted 1,803-cell pool.

The same study makes the substrate scope limitation concrete. A phylogenetic subgroup that showed no activity toward NIMS and natural substrates was investigated for alternative specificity: 23/26 tested enzymes hydrolyzed the chromogenic phosphorylated substrate pNPβG6P, whereas 19 enzymes outside that subgroup did not. Thus “no activity” in the earlier assays cannot be generalized to “nonfunctional enzyme”; it means no detected turnover for the tested substrate/readout under the specified conditions.

The article also reports 88% concordance between a pNPβG assay at 40 °C/pH 7 and NIMS, underscoring that assay modalities are related but not identical. The supplementary-table extraction retains literal `<0.1` as below the stated 0.1 conversion background, not a numerical zero. The full pool audit separately shows that many enzyme–substrate pairs cross the background in other pH/temperature conditions.

## Interpretation for Janus-Dataset

1. The strongest supportable label is **measured below-background activity for a specified enzyme–substrate–condition–assay observation**. Do not collapse it into universal inactive, failed protein, or never tested.
2. Independent HPLC follow-up strengthens the biological plausibility of no-detect outcomes for a selected group, but group-level prose without accession-to-cell mapping cannot be used to validate every extracted row.
3. Alternative-substrate activity is not a contradiction: enzyme function is substrate- and assay-dependent. A useful evidence schema should preserve the target reaction/substrate, assay modality, tested condition, threshold/background, and whether validation is row-level or cohort-level.
4. This source is a prospectively designed dense screen with structured supplementary tables. It supports a structured-table extraction and label-context pilot, but does not measure historical publication bias, NLP recovery from dispersed prose, unique coverage beyond databases, or ML gains.

## Source

Heins et al. (2014), [primary article](https://doi.org/10.1021/cb500244v) / [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4168791/); source table definitions and literal observations: [Supplementary Table 2](https://doi.org/10.1021/cb500244v.s003), with protein/expression/activity crosswalk in [Supplementary Table 3](https://doi.org/10.1021/cb500244v.s004). The reported 23/26 and 19-enzyme counts come from the article's results text; the accession-level identities of the HPLC no-detect subset are not resolved in this audit.

Related source-cell and pair-level results: [`2026-09-30-gh1-nims-pool-granularity-audit.md`](2026-09-30-gh1-nims-pool-granularity-audit.md), [`gh1_nims_candidate_pool_1803.csv`](pilots/gh1-nims/gh1_nims_candidate_pool_1803.csv), and [`gh1_nims_pair_context_audit.csv`](pilots/gh1-nims/gh1_nims_pair_context_audit.csv).
