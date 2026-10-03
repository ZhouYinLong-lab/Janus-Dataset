# Theisen measured activity rows: stratified ChEMBL source-linkage and censoring pilot

**Date:** 2026-09-30  
**Research question:** When source IDs are absent from a published model-ready bioactivity table, can measured rows be linked back to compound/target activity records, assays and source publications—and does the link preserve censored negative-side evidence?

## Scope and reproducibility

The source is the authors' public `prepped_activities_all_chembl_pubchem.csv`, pinned locally at repository commit `c185bedde8a7081045bc8414906a5775f4271a1c`. A deterministic SHA-256 ranking selected 10 measured rows with pActivity ≤6 and 10 with pActivity >6. The manifest was written before any API lookup and is retained as [`theisen_linkage_sample_manifest.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_manifest.csv). The code is [`theisen_linkage_sample.py`](pilots/kinase-activity-integration/theisen_linkage_sample.py); the sample-level summary is [`theisen_linkage_sample_results.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_results.csv); the activity-by-activity crosswalk, including assay and document links, is [`theisen_linkage_activity_records.csv`](pilots/kinase-activity-integration/theisen_linkage_activity_records.csv).

The script queries ChEMBL's connectivity search, UniProt target-component field, activity, assay, document and status endpoints. The API status returned **ChEMBL 37**, release date **2026-05-01**. The structure step is explicitly a connectivity-level search: where the prepared SMILES does not specify stereochemistry, this audit does not claim stereochemical identity. A numeric match means pActivity and current ChEMBL pChEMBL agree within 0.005; it is a useful crosswalk candidate, not proof that the exact upstream source row or measurement has been uniquely recovered. Activity records and their assay/document IDs are kept as separate rows to prevent many-to-many links from being flattened.

## Results

| Result | pActivity ≤6 stratum | pActivity >6 stratum | Overall |
|---|---:|---:|---:|
| Fixed measured rows | 10 | 10 | 20 |
| Rows with ≥1 connectivity-level activity whose pChEMBL matches within 0.005 | 4 | 6 | 10 |
| Rows with activity records found but no such numeric match | 6 | 4 | 10 |
| Activity-level crosswalk rows retained | 19 | 19 | 38 |

The ≤6 cutoff here defines sampling strata; it does **not** mean the source table supplies a categorical inactive label for every such row. The 20 rows were intentionally selected as a small audit, not a probability sample designed to estimate population coverage.

## Independent structured-database cross-check

Four of the five censored examples were checked against BindingDB's public API as well as ChEMBL. Full row-level responses and query routes are retained in [`theisen_bindingdb_censor_crosscheck.csv`](pilots/kinase-activity-integration/theisen_bindingdb_censor_crosscheck.csv). For sample row 24754, the API's similarity lookup returned the same molecular graph (RDKit 2023.03.1b1 canonicalized the source and BindingDB SMILES to the same canonical SMILES), human VEGFR1, IC50 `>10,000 nM`, BindingDB monomer 50276965; a UniProt P17948 query links that monomer to PMID 19124243 and DOI 10.1016/j.bmcl.2008.12.078. Row 28198's EGFR IC50 and EC50 `>10,000 nM` records (monomer 50304200) link to PMID 19692247 / DOI 10.1016/j.bmc.2009.07.047, while row 55998's mTOR IC50 `>10,000 nM` (monomer 50396815) links to PMID 22897589 / DOI 10.1021/jm300846z. For row 55045, the input SMILES itself is returned unchanged; the P48736 (PI3Kγ) query returns IC50 `>10,000 nM`, PMID 22981333, DOI 10.1016/j.bmcl.2012.08.072, monomer 50392452. A compound-structure lookup also returns PI3Kδ IC50 611 nM for the same SMILES, associated with that same BindingDB monomer. This is not a contradiction: it is target-specific activity for the same chemical structure and illustrates why a weak result against one target must not be propagated as a global compound-level negative.

This cross-check shows that at least four of these five censored observations are already represented in structured resources; they are provenance/label-semantics examples, not newly recovered data. BindingDB's compound lookup is similarity-based (cutoff 0.99), so exact-structure claims for rows 24754, 28198 and 55998 were checked by RDKit canonicalization; row 55045 is returned as the identical input SMILES. The original Kiselyov paper's accessible PubMed abstract describes a VEGFR1/2 inhibitor series but does not expose the specific compound-level table row; full text/SI was not available in this audit. Thus database-to-source linkage is stronger than before, but direct article-row verification remains open.

### Censored weak/inactive-side observations

Within the ten-row ≤6 stratum, five source rows have a corresponding current ChEMBL single-protein activity record with a right-censored `>` relation at **10,000 nM**. In the prepared table, each of those rows is represented by pActivity `4.999999999999999` (approximately 5.0), which is a point-valued boundary representation rather than the original inequality. The retained activity-level table preserves the relation, bound, assay, DOI and activity ID:

| Sample row | Target | ChEMBL activity | Assay / source DOI |
|---:|---|---|---|
| 24754 | VEGFR1 | IC50 `> 10,000 nM` | CHEMBL1034023; [10.1016/j.bmcl.2008.12.078](https://doi.org/10.1016/j.bmcl.2008.12.078) |
| 28198 | EGFR | EC50 `> 10,000 nM`; IC50 `> 10,000 nM` | CHEMBL1073385 / CHEMBL1073378; [10.1016/j.bmc.2009.07.047](https://doi.org/10.1016/j.bmc.2009.07.047) |
| 40079 | MAP3K1/MEKK1 | IC50 `> 10,000 nM` in two returned records | CHEMBL2214713 and CHEMBL5468238; [10.1016/j.bmcl.2012.10.084](https://doi.org/10.1016/j.bmcl.2012.10.084) plus a separate ChEMBL dataset document |
| 55045 | PI3Kγ | IC50 `> 10,000 nM` | CHEMBL2156791; [10.1016/j.bmcl.2012.08.072](https://doi.org/10.1016/j.bmcl.2012.08.072) |
| 55998 | mTOR | IC50 `> 10,000 nM` | CHEMBL2173749; [10.1021/jm300846z](https://doi.org/10.1021/jm300846z) |

These are not necessarily five independent papers or five uniquely resolved source rows; row 40079 has more than one linked record/document. They are five sample compound–target rows whose prepared value coincides with a 10 μM censoring boundary in the current ChEMBL crosswalk. This is evidence that context and relation operators can be lost when measurements are reduced to a single model-ready scalar. It does **not** establish that the authors intentionally transformed these exact ChEMBL records, that the relation existed in the exact source version used, or that this pattern is prevalent in the full table.

### Exact-value matches still do not guarantee complete provenance

Ten of the 20 sampled rows have at least one current ChEMBL pChEMBL within 0.005 of the prepared pActivity. For instance, row 12714 (DNA-PK) maps to IC50 6,300 nM, pChEMBL 5.20, assay CHEMBL916755 and DOI 10.1021/jm061121y; row 56401 maps to IC50 10 nM, pChEMBL 8.00, assay CHEMBL2188027 and DOI 10.1021/jm301024w. A value match can still be non-unique: row 19186 has two matching pChEMBL records across different assays/documents, as well as other activity records. Conversely, rows such as 9298 and 9813 link to measured compound–target records but do not numerically match the prepared value, and row 71052 has several condition-specific p38/ERK2 results with different potencies. Those are ambiguity/context cases, not evidence that a measurement is absent.

## Interpretation for Janus

This pilot strengthens the case for treating a scientific observation as more than `(molecule, target, scalar label)`. At minimum, a recoverable record should keep the endpoint, relation operator, threshold/bound, assay, source document and the link-confidence level. An IC50 reported as `>10 μM` is informative weak-activity evidence, but it is not an exact IC50 of 10 μM; whether it qualifies as “inactive” depends on the assay/task threshold. Likewise, missing activity or no API hit is not a negative result.

The result narrows—not proves—the research gap: some prepared rows can be crosswalked to existing ChEMBL records, so a future recovery benchmark must exclude or mark already-curated observations and separately count direct record matches, connectivity/pair-level links, censored-value matches, ambiguous multi-assay links and unresolved cases. A model experiment should then compare the original scalarized labels against relation-aware censored labels on the same compounds, split and training budget; this pilot itself evaluates no model utility.

## Limitations and next checks

- `n=20` is a deterministic exploratory sample stratified by label range, not a representative prevalence estimate.
- Connectivity search and pChEMBL rounding are insufficient to prove exact stereochemical or source-row identity; several rows have multiple activity records.
- ChEMBL 37 is a current snapshot. The paper's source export may have used an earlier database release or PubChem-derived rows; current matches cannot identify the exact source version.
- The prepared table omits per-row relation and assay/source columns; the linked relation may come from current curation, and the mapping from that source record to the authors' row is inferred.
- The API query uses the exact UniProt accession among target components, but those components may belong to different target constructs; assay target and format therefore remain essential context.
- Next, manually inspect the five 10 μM-bound source records in their linked primary papers/supplementary tables and verify chemical stereochemistry plus exact assay target. If that succeeds, expand to a pre-registered 100-row audit with adjudication rules and double-label a subset. Do not estimate extraction recall until the denominator and source version are fixed.

## Evidence sources

- Theisen et al. (2024), *Nature Communications*, [10.1038/s41467-024-52055-5](https://doi.org/10.1038/s41467-024-52055-5), plus the authors' [public code and prepared data](https://github.com/Harmonic-Discovery/activity-integration).
- Official [ChEMBL Data Web Services documentation](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), which documents connectivity search, activity, assay, document and status resources, filters and pagination.
- Official [BindingDB Web Services documentation](https://bdb8.ucsd.edu/rwd/bind/BindingDBRESTfulAPI.jsp); targeted API responses for sample rows 24754 and 55045 independently return the censored activity, target and article identifiers described above.
- ChEMBL API snapshot queried 2026-09-30: status endpoint reported ChEMBL 37 (release date 2026-05-01); per-row activity/assay/document identifiers are in the retained CSV artifacts above.
