# 2026-09-30 candidate source audit: CAR substrate panel

## Why inspected

After the Pertusi traceability check showed that a useful prior-art paper may not expose its historical negative rows in the accessible main text, I checked whether a narrower biochemical pilot can be anchored to an openly readable paper with clearly defined assay-level outcomes. This is a candidate-screen audit, not yet a row-level extraction.

## Evidence from the primary paper

Khusnutdinova et al. (2017) report screening 15 purified bacterial carboxylate reductases (CARs) against 87 carboxylic-acid substrates, including mono-, di-, hydroxy-, oxo-, and amino-acids. The article describes a common NADPH-oxidation assay: 0.2 mL, HEPES-K pH 7.5, 1 mM NADPH, 2.5 mM ATP, 10 mM MgCl2, typically 10 mM substrate (5 mM for decanoate), 2.5–5 μg purified CAR, 10 min at 30 °C. Kinetic assays are described as triplicate. The article reports no activity for some substrate classes and points to Table S3 / Figures S3–S4 for the detailed panel; the plotted heatmap defines white as “no detectable activity.”

This offers a promising *structured table/figure extraction test case* because substrate, enzyme, endpoint, conditions and low/no-activity semantics are closely specified. It is not itself historical literature mining: the authors prospectively generated a dense panel, and it does not test model benefit from mined negatives. The table-level observations would be assay-relative, not universal non-substrate claims.

## Important confound to avoid

The same article reports that one expressed, soluble CAR (MAB3367) was inactive toward benzoic acid and suggests a degenerate adenylation domain. That observation is an enzyme/protein-function failure, not evidence that a particular tested molecule is a substrate-level negative for an otherwise active enzyme. Such records must be typed separately or excluded from substrate-negative training sets unless the question explicitly concerns enzyme function.

## Access and status

PMC full text is openly readable, but its linked 1.7 MB supplementary PDF currently resolves to a “Preparing to download” verification page in the browser. Wiley endpoints returned HTTP 403 in a read-only availability probe. Consequently, the 15 × 87 detailed result matrix has **not** been inspected or transcribed, and no negative-record count is asserted. This is a candidate for a benchmark/extraction schema, not yet the chosen 50–100-record literature pilot.

## Main-project relevance

Relevance **2/3**: strong for assay context, threshold/ND label handling, and the extraction schema; only adjacent to publication bias because it is a newly generated complete screen rather than fragmented historical evidence. It is useful as a positive control for recognizing “measured and no detectable activity” versus “not measured,” and as a warning to distinguish inactive enzyme preparations from inactive substrates.

## Source

- Khusnutdinova et al. (2017), *Biotechnology Journal*, [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5681412/), [DOI](https://doi.org/10.1002/biot.201600751).
