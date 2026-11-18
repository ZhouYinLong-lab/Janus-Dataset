# LpBgl5 negative observations: BRENDA near-match is not exact observation coverage

**Date:** 2026-09-30  
**Main-project relevance:** 2/3 (database-coverage boundary for source-linked negative observations).  
**Scope:** Follow-up of the earlier unresolved BRENDA crosswalk for four negative observations in Godse et al. (2025).

## Query and result

The article studies LpBgl5 from *Lactiplantibacillus plantarum* NCIM 2903 (gene accession PQ462659; protein accession XOT41254.1, 480 aa). Because the article concerns a 6-phospho-β-glucosidase with promiscuous β-glycosidase activity, BRENDA was checked under EC 3.2.1.86 as well as the previously searched β-glucosidase EC 3.2.1.21.

BRENDA's EC 3.2.1.86 page exposes a *L. plantarum* WCFS1 record associated with UniProt F9UU25 and structure 4GZE. The UniProt sequence record identifies F9UU25 as a 6-phospho-β-glucosidase from a different strain (ATCC BAA-793 / NCIMB 8826 / WCFS1). An exploratory end-to-end Needleman–Wunsch alignment of the two retrieved sequences (match +2, mismatch −1, gap −2) gave 264 identical residues over 467 aligned residue pairs (56.53% identity; 24 gap characters across the alignment). This supports a related protein/family-level near-match, not exact protein identity. The alignment was not a curated orthology call or BLAST result.

The public BRENDA EC page lists phosphorylated substrates such as cellobiose 6-phosphate for other organisms and contains a different *L. plantarum* protein record. Neither establishes coverage of LpBgl5's specific unphosphorylated observations: two aryl glycosides reported as zero relative activity and arbutin/cellobiose with no hydrolysis through 96 h. In particular, cellobiose 6-phosphate is chemically and experimentally distinct from cellobiose. The queried BRENDA page/reference snapshot did not yield an exact accession-to-paper-to-substrate-result match for the 2025 source.

## Coverage ruling

| LpBgl5 source observation | Exact BRENDA observation match established? | Reason |
|---|---|---|
| p-nitrophenyl-α-D-glucopyranoside, 0 relative activity | No | No exact XOT41254.1/source-paper/result link found; an EC-level or homolog record cannot substitute |
| p-nitrophenyl-β-D-galactopyranoside, 0 relative activity | No | Same; do not infer from another enzyme's aryl-glycoside panel |
| arbutin, no hydrolysis through 96 h | No | No exact protein–substrate–source observation established |
| cellobiose, no hydrolysis through 96 h | No | Any phospho-cellobiose entry is a different chemical substrate and assay |

“No exact match established in the queried public BRENDA pages” is the supported statement. It is **not** proof that no equivalent record exists elsewhere in BRENDA, another database, or a non-indexed source. We therefore do not count these four observations as database-unique or as a population-level incremental-recovery estimate.

## Why this matters

The case separates four notions that are often collapsed: EC/organism overlap, homolog-level protein overlap, exact assayed protein identity, and exact observation coverage. It also shows that substrate identity must preserve chemical modification/state (here, phosphorylation), not just a shared name stem. This is directly useful for the proposed dataset's entity-resolution and source-coverage rules, but it does not establish literature-mining performance, model utility, or general database incompleteness.

## Sources and retained data

- Godse et al. (2025), [primary article](https://doi.org/10.1007/s00253-025-13472-8), [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11978721/).
- [BRENDA EC 3.2.1.86](https://www.brenda-enzymes.org/enzyme.php?ecno=3.2.1.86) and [BRENDA sequence search for EC 3.2.1.86](https://www.brenda-enzymes.org/sequences.php?f%5Bec%5D=3.2.1.86&f%5Bstype_ec%5D=1).
- [UniProt F9UU25](https://www.uniprot.org/uniprotkb/F9UU25/entry); [NCBI protein XOT41254.1](https://www.ncbi.nlm.nih.gov/protein/XOT41254.1).
- Updated observation-level crosswalk: [`lpbgl5_negative_extraction.csv`](pilots/enzyme-negative-literature/lpbgl5_negative_extraction.csv); annotation challenge set: [`annotation_pilot_v0.csv`](pilots/enzyme-negative-literature/annotation_pilot_v0.csv); reproducible exploratory alignment: [`compare_lpbgl5_brenda_homolog.py`](pilots/enzyme-negative-literature/compare_lpbgl5_brenda_homolog.py).
