# 2026-09-30 robotic enzyme negative-data competitor audit

## Why this belongs in the tracker

Onishchenko et al. (first published 2026-09-11) directly combine experimentally measured active/inactive enzyme–substrate outcomes with a machine-learning evaluation across enzyme families. This narrows claims about the value of negative data and what a new biochemical dataset alone could contribute. It does **not** mine historical papers for omitted results.

Primary sources: [publisher full text](https://doi.org/10.1002/advs.77474), [Zenodo v1 data/code record](https://doi.org/10.5281/zenodo.15846762), [Zenodo v1.1 record](https://zenodo.org/records/15846763).

## What the study measured

The paper reports 374 enzyme–substrate pairs from yeast alcohol dehydrogenase (yADH), horse-liver alcohol dehydrogenase (hlADH), and two fungal ω-transaminases (TA-At, TA-Af), each assayed in triplicate. It operationally labels yields `>1%` active and `≤1%` inactive. The authors explain that the threshold was selected partly for measurement detectability and partly to retain class balance; their supplementary workbook also reports tests at 1%, 3%, and 5%. These labels therefore mean low/no conversion under those particular assay conditions and threshold, not proof that the molecule is universally not a substrate.

## Independent checks against deposited artifacts

The publisher lists a 134 KB workbook `S1_final.xlsx`; the matching Zenodo v1.1 record provides `Table_S1_final.xlsx` (137,227 bytes), four assay sheets and multiple model-result sheets. I downloaded that workbook and the 235,788-byte `experimental_data_analysis.zip`; the latter contains raw instrument-run spreadsheets, processed outcome tables and analysis notebooks. No model was independently rerun in this audit.

Recounting the four main enzyme sheets from the deposited workbook at the paper's 1% threshold gives:

| Enzyme | Pairs | `>1%` active | `≤1%` inactive |
|---|---:|---:|---:|
| yADH | 89 | 42 | 47 |
| hlADH | 89 | 52 | 37 |
| TA-At | 98 | 28 | 70 |
| TA-Af | 98 | 16 | 82 |
| **Total** | **374** | **138** | **236** |

The workbook's Figure 3a summary reports 4-enzyme cross-validation balanced accuracy 0.674 (SD 0.019). It separately reports test performance for the four-enzyme-trained model on external datasets: FDC BA 0.506 / ROC-AUC 0.540; phosphatase BA 0.602 / ROC-AUC 0.601; esterase BA 0.506 / ROC-AUC 0.540. A different supplementary aggregation (Figure S10b) reports FDC/Pase/esterase BA 0.772/0.628/0.665. These are distinct training/evaluation summaries and must not be blended. The comparison shows why the headline “OOD improvement” needs to be tied to its exact model, training set, and split; the raw workbook supports auditing that distinction, not choosing a single result as universal.

## Relevance and limit

This is a strong model-utility and competitor precedent: a new project cannot claim novelty merely by measuring an enzyme active/inactive panel and training a generalizing model. The most defensible residual question is whether older literature contains tested negative observations absent from current resources, whether they can be recovered with molecule–enzyme–assay–condition provenance, and whether adding those historical observations contributes beyond both existing databases and standardized new screens.

This paper's robot-generated outcomes should be a **benchmark/comparison source**, not mislabeled as literature-mined evidence. A practical follow-up can use its published panel as an external benchmark and ask whether a literature-recovery workflow improves coverage or prediction when the test family/compounds are held out. That proposal still requires a careful data-overlap audit before implementation.

## Retained artifacts and checksums

| Local file | Size | SHA-256 | Purpose |
|---|---:|---|---|
| [`robotic-enzyme-negative-data/experimental_data_analysis.zip`](competition/robotic-enzyme-negative-data/experimental_data_analysis.zip) | 235,788 bytes | `712709959781C284D7D71F71E7F6F0E135AC0DDEA92607AF3C612DF300EF54F9` | Raw and processed assay analysis files |
| [`robotic-enzyme-negative-data/Table_S1_final.xlsx`](competition/robotic-enzyme-negative-data/Table_S1_final.xlsx) | 137,227 bytes | `75E8BCC2002AB64F1DADC8E8B0FBAA48D951071DBF3FED8E10D0C627A8D5DD7B` | Main substrate structures/yields and supplementary model metrics |

Zenodo v1.1 lists CC-BY 4.0. The record also offers a 295 MB code archive; it was not downloaded. A separate automation archive was briefly downloaded but not retained because its archive listing includes files named as bot/API tokens; it was never extracted, its contents were not opened, and the downloadable source remains available from Zenodo. No credentials or token contents were accessed.
