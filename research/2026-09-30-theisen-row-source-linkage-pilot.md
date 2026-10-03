# Exploratory source-linkage pilot for Theisen et al.'s kinase activity table

**Date:** 2026-09-30  
**Source model rows:** three exploratory measured rows sampled from Theisen et al.'s public `prepped_activities_all_chembl_pubchem.csv`; this is a convenience pilot, not a prevalence estimate.  
**Official API documentation:** [ChEMBL Data Web Services](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), [REST API](https://www.ebi.ac.uk/chembl/api/data/docs).

## Starting row and match

| Row | Starting fields | ChEMBL crosswalk result |
|---|---|---|
| 1 | SMILES `Nc1nccc(-n2cc(-c3cccnc3)c3cnccc32)n1`; UniProt P24941; pActivity 5.9586073 | Exact structure maps to CHEMBL2348162; P24941 maps to human CDK2/CHEMBL301. Activity IC50 `= 1100 nM`, pChEMBL 5.96; assay CHEMBL2353290; document CHEMBL2346586; DOI 10.1016/j.bmcl.2013.02.007 (PMID 23481650). Assay description: “Inhibition of CDK2 (unknown origin)”. |
| 2 | SMILES `CCC1C(=O)N(C)c2cnc(Nc3ccc(S(=O)(=O)NCCCO)cc3)nc2N1C1CCCC1`; UniProt Q9NYY3; pActivity 8.0883098 | Exact structure maps to CHEMBL4169129; target CHEMBL5938; IC50 `= 8.16 nM`, pChEMBL 8.09; assay CHEMBL4143483; document CHEMBL4138231; DOI 10.1016/j.ejmech.2017.11.058 (PMID 29220793). Assay description specifies recombinant human Plk2 and a FRET-based Z'-Lyte assay. |
| 3 | SMILES `CC(NC(=O)c1c[nH]c2ncc(-c3cn(C)c4cc(Cl)ccc34)nc12)C(=O)N1CC(C#N)C1`; UniProt O60674; pActivity 7.5773249 | Exact structure maps to CHEMBL2376143 and target maps to JAK2/CHEMBL2971. Current ChEMBL contains two JAK2 IC50 measurements in document CHEMBL2375236, 170 nM (pChEMBL 6.77) and 3.3 nM (8.48), but neither exactly matches the prepared row value; the same compound also has a JAK2/JAK1-complex record. Document DOI 10.1016/j.bmcl.2013.02.012 (PMID 23540648). Thus the molecule–target pair is traceable, but the specific aggregated training value is not uniquely attributable from this match alone. |

Rows 1 and 2 are close numerical/identity matches to individual ChEMBL activity records. Row 3 demonstrates a harder case: molecule and protein resolve, and related measured activities/documents are present, but the prepared aggregate value does not match an individual current ChEMBL pChEMBL record. These cases show both that omitted source IDs can sometimes be reconstructed and that pair-level matching is not always enough to identify the exact contributing measurement.

## What the match does not restore

One matched assay description explicitly says “unknown origin”; another provides assay-system detail. The API records do not by themselves identify exact source-paper table/figure coordinates. Row 3 may reflect aggregation, source-version differences, or a source not resolved by this exact ChEMBL comparison; this pilot cannot decide among those explanations. Three rows do not establish the proportion of 210,862 prepared rows that can be unambiguously linked, nor a false-match rate.

## Janus implication

Before describing a candidate literature observation as “missing from structured databases,” attempt a source-aware crosswalk against ChEMBL/PubChem using structure, target, endpoint, value, unit and relation operator where available. Report at least four outcomes separately: direct record match, pair-level link with unresolved measurement aggregation, no exact current-database match, and no match after a documented search. A single failed exact match must not be called absent globally; a positive match must not be counted as new dataset coverage.

