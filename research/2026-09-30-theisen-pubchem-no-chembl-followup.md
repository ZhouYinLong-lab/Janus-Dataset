# ChEMBL no-hit follow-up: PubChem returns a PASK result with unresolved outcome and opposite censoring direction

**Date:** 2026-09-30  
**Parent audit:** [`2026-09-30-theisen-stratified-source-linkage-100-row-audit.md`](2026-09-30-theisen-stratified-source-linkage-100-row-audit.md)  
**Sample row:** 129369; source pActivity 4.999999999999999; UniProt Q96RG2; SMILES `Nc1[nH]n2c(=O)cc(-c3ccc(Cl)cc3)nc2c1-c1ccccn1`.

## Queries and observed records

The frozen sample row had no structure candidate returned by the live ChEMBL 37 connectivity query. A structure lookup via the official PubChem PUG REST endpoint `compound/smiles/{SMILES}/cids/JSON` returned CID **70925370**. The CID assay summary links it to SID **336863075** and PASK (UniProt Q96RG2; gene ID 23178). Four AIDs have this CID/SID, PASK target and confirmatory assay descriptions: **1259918, 1259919, 1634375 and 1634376**. Their descriptions include distinct PASK constructs/readouts (radiochemical/MBP and TR-FRET assay variants).

For SID 336863075, the PUG REST AID CSV responses give, for each of those four assays:

| Field | Returned value |
|---|---|
| PubChem Activity Outcome | `Unspecified` |
| PubChem Standard Value | 10 µM |
| Standard Type | IC50 |
| Standard Relation | `<=` |
| Standard Value / Units | 10,000 nM |

The AID metadata for 1259918 identifies the data source as **SureChEMBL Patent Bioactivity Data** and includes ChEMBL target ID CHEMBL6054; the PUG output contains no PMID for these four result rows. Exact assay data and identifiers are retained in [`theisen_linkage_pubchem_followup.csv`](pilots/kinase-activity-integration/theisen_linkage_pubchem_followup.csv).

## Interpretation

This is a useful correction to treating a ChEMBL structure no-hit as global absence: PubChem contains same-structure/target assay records. But it is **not evidence of an inactive result**. PubChem labels the outcome `Unspecified`, and its standard relation is `<=10,000 nM`, not `>10,000 nM`. The assay result is compatible with an IC50 at or below 10 µM, but cannot be collapsed into an exact IC50 or an inactive label without further source interpretation.

It also demonstrates why a model-ready pActivity around 5.0 does not uniquely identify an inactive class or even the direction of a censored bound. The measured table lacks source/AID/SID fields, so although structure, target and value align plausibly, the link from this specific PubChem observation to row 129369 is not uniquely proven. Treat it as a crosswalk candidate, not a confirmed source-row attribution or newly recovered negative.

## Relevance and limits

- **Relevance:** 3/3. Directly tests how an apparent missing ChEMBL structure maps to another structured assay resource, and shows that inequality direction/outcome semantics must be preserved.
- **What this supports:** Cross-database checking is necessary; “no ChEMBL match” is not “no existing data”; `Unspecified` and a bound are distinct from explicit inactive evidence.
- **What this does not support:** It does not measure coverage, establish the authors' exact row source, recover a primary-paper negative, or demonstrate model improvement.
- **Next check:** Resolve the SureChEMBL `DOCID: 97176` / linked patent source and inspect the original table if accessible; otherwise keep this row unresolved at the source-document layer.

## Sources

- Official [PubChem PUG REST documentation](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest): documents compound-by-SMILES lookup, assay result CSV retrieval, assay descriptions and assay summaries.
- Live API retrieval on 2026-09-30: CID 70925370; SID 336863075; AIDs 1259918, 1259919, 1634375, 1634376; row-level output retained in the linked CSV.
