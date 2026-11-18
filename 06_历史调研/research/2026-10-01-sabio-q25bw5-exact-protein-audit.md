# SABIO-RK exact-protein crosswalk for the GH1 NIMS pilot (Q25BW5)

## Question and scope

Does SABIO-RK contain the six Heins et al. 2014 BGL1A/cellobiose measurements in the enzyme-negative pilot, or only related measurements for the same protein and substrate under a different source/assay context?

Relevance to the Janus question: **3/3**. Exact database overlap determines whether a source-recovered observation adds coverage beyond existing resources. This is a bounded exact-accession query, not a comprehensive SABIO-RK completeness claim.

## Query and result

On 2026-10-01, queried the live SABIO-RK endpoint with the exact UniProt accession Q25BW5 and requested up to 100 rows:

`https://sabiork.h-its.org/api/ft/proxy-select?q=UniProtKB_AC%3AQ25BW5&context=sabio&view=getEntryResult&rows=100`

The response reported `numFound=13` and returned 13 entries (IDs 38521–38533, with no missing IDs in that interval). All 13 identify *Phanerochaete chrysosporium* BGL1A/Q25BW5, include cellobiose hydrolysis, and cite the same 2008 paper (PMID 18023045; Tsukada et al.). These are multiple SABIO-RK records/kinetic representations from **one paper**, not 13 independent studies. The paper explicitly evaluates mutations around the active site for effects on cellobiose hydrolysis and reports restoration of hydrolytic activity for a double mutant at neutral pH ([PubMed record](https://pubmed.ncbi.nlm.nih.gov/18023045/)).

The entries include a fitted pH-dependent kinetic law for wild-type BGL1A and several variants. Examples represented in the API include wild-type kcat 1.81 s⁻¹ and Km 6.80 mM; V173C kcat 4.35 s⁻¹ and Km 13.30 mM; M177L 2.53 s⁻¹ and 9.22 mM; D229N 3.23 s⁻¹ and 114 mM; H231D 3.94 s⁻¹ and 21.0 mM; and K253A 4.47 s⁻¹ and 46.5 mM. These are kinetic-model parameters reported/curated for the 2008 study, not direct measurements at the Heins pilot's high-temperature conditions. SABIO-RK lists the kinetic-law pH span as 4–8 and 30 °C; its comments say the temperature is given in PMID 16896601. The listed reaction is cellobiose + water → two glucose molecules.

The 13 returned entry IDs and variant labels were: 38521 wild type; 38522 wild-type pH-dependent law; 38523 V173C; 38524 M177L; 38525 D229N; 38526 H231D; 38527 K253A; 38528 V173C pH-dependent law; 38529 M177L pH-dependent law; 38530 D229N pH-dependent law; 38531 H231D pH-dependent law; 38532 K253A pH-dependent law; and 38533 D229N/K253A. Some point-condition variant entries do not expose a complete fitted kcat/Km pair in the API representation; the table above reports only entries with those parameters populated.

## Adjudication against the six pilot rows

The six Heins et al. 2014 pilot observations are Q25BW5/BGL1A × cellobiose with reported conversion `<0.1` at pH 5 or 8 and 60, 80 or 90 °C (source Table 2 / SI row references 32E–38E; DOI [10.1021/cb500244v](https://doi.org/10.1021/cb500244v), [official SI DOI](https://doi.org/10.1021/cb500244v.s003)). The SABIO-RK entries establish **same exact accession + same substrate + a different paper and condition regime**. They do **not** establish that the six Heins condition-specific outcomes are present in SABIO-RK: no Q25BW5 result retrieved in this query cites the Heins 2014 paper, and the returned kinetics are for the 2008 study at 30 °C, not those high-temperature conditions.

Accordingly, the six rows are adjudicated as:

- exact entity/substrate has related structured positive kinetic evidence in SABIO-RK;
- exact Heins source-observation/condition match: **not established by the scoped query**;
- database absence: **not claimed** beyond the query and fields inspected;
- interpretation: preserve the experimental context. A molecule–protein pair must not be globally labeled inactive from the high-temperature observations, nor globally active from the 2008 kinetics.

The BRENDA crosswalk previously identified a same-entity/substrate qualitative negative comment from a separate 2007 source (reference 679851; DOI 10.1016/j.febslet.2007.03.009), but that also does not cover the six 2014 high-temperature observations. Thus the pilot illustrates why cross-database matching should be hierarchical: exact observation/source/conditions, same entity and substrate under different conditions, homolog/near-match, and not assessed are distinct states.

## Boundary and next step

This finding improves the overlap adjudication for NP009–NP014, but does not quantify the overall share of enzyme-literature negatives absent from databases and does not demonstrate automatic extraction or model benefit. The new row-level status table is [`database_coverage_adjudication_v0.csv`](pilots/enzyme-negative-literature/database_coverage_adjudication_v0.csv). The initial broader SABIO-RK check remains at [`2026-09-30-sabio-rk-cross-database-audit.md`](2026-09-30-sabio-rk-cross-database-audit.md).
