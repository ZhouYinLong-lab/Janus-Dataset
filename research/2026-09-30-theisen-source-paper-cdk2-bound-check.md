# Source-paper check: Theisen sample row 7684 and a CDK2 IC50 bound

## Question and candidate row

The 100-row Theisen source-linkage sample contains row 7684 (UniProt P24941/CDK2; prepared pActivity 4.30103). Current ChEMBL 37 links the connectivity-level candidate CHEMBL194498 to activity 1512659: IC50 `>50,000 nM`, assay CHEMBL828533 (“Inhibition of human cyclin-dependent kinase 2”), and DOI 10.1021/jm0501275. Transforming the 50,000 nM boundary gives pActivity 4.30103.

## What the source paper independently supports

Borzilleri et al. (2005) is primarily a VEGFR-2/FGFR-1 inhibitor paper, but its full text explicitly reports a broader kinase-selectivity panel. In the results, it says the selected analogues were screened against RTKs, non-RTKs and serine/threonine kinases, and that no significant activity was detected for the series against CDK2 and PKC. Table 5 lists IC50 in µM and reports `>50` for each of five selected analogues in the CDK2 column. The methods describe recombinant kinase proteins, a poly(Glu4/Tyr) phosphoacceptor substrate and a radiometric/filter-based kinase assay; some detailed assay procedures are referenced to earlier papers.

This independently corroborates the **target-panel and threshold-level** negative evidence represented by the ChEMBL record: weak/no detectable CDK2 inhibition at the tested cutoff, in a compound-specific kinase assay context. It demonstrates a realistic extraction target: not merely the word “inactive,” but target, compound panel, assay, endpoint, threshold and relation.

## What is and is not verified

- The ChEMBL row's DOI, CDK2 target, IC50 `>50,000 nM`, assay description and the prepared scalar's exact boundary transform are directly present in the captured ChEMBL 37 crosswalk.
- The primary article independently supports the CDK2 panel and `>50 µM` bound for all five tabulated compounds.
- The exact mapping of CHEMBL194498 to one named compound number among the five Table 5 analogues was not independently recovered from the article's supplementary structure table in this check. Therefore this is not yet a fully unique compound-to-table-cell reconstruction.
- The result already exists in ChEMBL and is linked to the source DOI; it is **not** incremental literature-recovery yield. It also does not establish model utility or publication-bias magnitude.

## Main-project relevance

**Relevance: 3/3.** This is a concrete source-level example of a target-specific, threshold-censored weak-activity observation with recoverable assay context. It strengthens the case for a structured evidence record with explicit relation operators and provenance, while also showing that at least some such evidence has already been curated by existing databases. It should be counted as a source-verification example, not as novel data added by Janus.

Sources: Borzilleri et al., *Journal of Medicinal Chemistry* (2005), [DOI 10.1021/jm0501275](https://doi.org/10.1021/jm0501275); publisher [article page](https://pubs.acs.org/doi/10.1021/jm0501275); accessible full-text rendering with Table 5 and assay methods [LookChem mirror](https://www.lookchem.com/FreePDFArticle/658085-65-5.htm); ChEMBL candidate/activity/assay capture in [`theisen_linkage_sample_100_activity_records.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_activity_records.csv).
