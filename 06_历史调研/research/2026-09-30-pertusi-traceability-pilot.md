# 2026-09-30 Pertusi 2017 negative-observation traceability pilot

## Question and relevance

Does the direct prior-art example in Pertusi et al. (2017) expose enough record-level information to reproduce its literature-recovered negative enzyme–substrate observations, and what does that imply for a Janus-style contribution?

Relevance: **3/3**. This directly tests whether literature negatives can be recovered, linked to their primary sources, and retained with enough assay context to be independently checked.

## What the primary article establishes

Pertusi et al. state that they searched primary literature manually for tested inactive compounds not listed in BRENDA. Their examples cover MenD, carboxylic acid reductase (Car), amino-acid ester hydrolase (AAEH), and HAPMO. They preferred inactive compounds containing the functional group required by the enzyme when possible, but included other experimentally tested inactive compounds as more reliable than random negatives. The paper plots active/inactive molecule distributions and trains SVM classifiers using both classes.

For MenD, the paper gives an experimental protocol for its *new* compounds (eight initially selected compounds, followed by three additional predictions): protein source and preparation, reaction mixture, triplicates, 30 °C shaking, and a comparison against BSA or enzyme-free controls. All eleven tested compounds were reported as substrates. This protocol validates newly tested positive candidates; it does **not** describe the assay conditions or primary-source location for each historical inactive training observation.

The main text cites Kurutsch et al. (2009) for the MenD dataset, but does not enumerate which negative training compounds came from which article/table or provide a row-level mapping in the accessible article text. The JATS XML registers one DOCX supplement (`NIHMS914501-supplement-1.docx`). The public PMC attachment endpoint returned a download-verification page in this audit, and the Europe PMC full-text endpoint returned HTTP 500; therefore its contents were not inspected. This is an access limitation, not evidence that the supplement lacks a mapping.

## Assay-context caution

Kurutsch et al. describe MenD catalyzing both 1,2-additions to aldehyde acceptors and its physiological 1,4-addition involving unsaturated carboxylic-acid acceptors. Their article reports broad aldehyde acceptance for the 1,2 reaction but stronger substrate constraints for the 1,4 reaction. Therefore, “inactive with MenD” is underspecified unless the reaction type, donor/acceptor roles, assay conditions, and operational readout are attached. This is a domain-specific inference from the two papers, not a claim that Pertusi mislabeled any observation.

## Pilot result

| Audit check | Result | Status |
|---|---|---|
| Does a peer-reviewed study report manual recovery of measured enzyme negatives from primary papers? | Yes; Pertusi et al. explicitly say so. | Confirmed |
| Is there evidence the negatives were model inputs rather than merely mentioned? | Yes; figures and methods describe active/inactive training sets used for SVMs. | Confirmed |
| Can a reader of the accessible main text reproduce the exact historical negative rows and their per-row source locations? | Not from the material inspected: no row-level mapping was found in the accessible article text. | Unresolved; supplement not inspected |
| Is there assay context for the historical negative rows sufficient to normalize their labels? | Not established in the inspected article text. | Unresolved |
| Does the prospective MenD validation prove that literature negatives improve the model? | No; the eleven follow-up compounds were all positive substrates, and the study tests active-learning selection, not a source-matched negative-data ablation. | No |

## Interpretation for the main project

This pilot **does not support** a novelty claim that nobody has manually found experimental biochemical negatives in papers or used them in models. It does support a narrower, testable gap: whether a workflow can recover observations at scale with an auditable molecule–enzyme/reaction–assay–condition–result–source link, estimate unique coverage beyond databases, and evaluate their incremental utility against matched controls.

The key pilot lesson is to make “negative” an observation-level, assay-relative label. A substrate pair should not be represented as a context-free, universal negative where the same enzyme catalyzes different reaction classes or assay definitions.

## Sources

- Pertusi et al. (2017), *Metabolic Engineering*, [full-text manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC7055960/), [DOI](https://doi.org/10.1016/j.ymben.2017.09.016).
- Kurutsch et al. (2009), *Journal of Molecular Catalysis B: Enzymatic*, [publisher article](https://www.sciencedirect.com/science/article/pii/S1381117709000757), [DOI](https://doi.org/10.1016/j.molcatb.2009.03.011).

## Next action

Do not scale this into a broad NLP benchmark yet. First choose one well-defined assay/reaction family where candidate primary articles and tables are openly accessible; manually trace a small set of positive and negative rows to source passages, then use that annotation schema for a 50–100-candidate extraction pilot. Keep unresolved source mappings explicitly unresolved.
