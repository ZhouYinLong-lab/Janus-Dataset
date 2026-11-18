# BglM-G1 alpha-substrate observations: bounded BRENDA/SABIO-RK crosswalk

## Question

Do BRENDA or SABIO-RK expose exact source-linked records for the two BglM-G1 (wild type) alpha-glycoside observations supported by the 2018 paper's Results prose: p-nitrophenyl-alpha-D-arabinofuranoside (NP005) and p-nitrophenyl-alpha-D-rhamnopyranoside (NP007)?

Relevance: **3/3**. This tests whether source-recovered observations add identifiable coverage beyond public enzyme resources. It is a bounded live crosswalk, not a database completeness or prevalence estimate.

## Entity limitation

The paper calls the measured enzyme the synthetic metagenomic protein BglM-G1. It reports **99% sequence identity** to a GenBank protein KRO51423, not identity/equivalence to that accession; no UniProt accession for the measured construct was found in the source reviewed here. KRO51423 is therefore a search lead, not an exact construct identifier. [Primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6192996/)

## SABIO-RK live query

On 2026-10-01, queried the public SABIO-RK API (`https://sabiork.h-its.org/api/ft/proxy-select`, `context=sabio`, `view=getEntryResult`, `rows=1000`). A broad EC 3.2.1.21 query (`ecnumber:3.2.1.21`; equivalently `ECNumber_facet:3.2.1.21`) returned **445 records**. None of the returned records matched PMID 30345395, the paper title/BglM-G1, KRO51423, or either exact D-configured test substrate. The displayed near-name substrate results were alpha-L-arabinopyranosides for human/rice beta-glucosidases, not p-nitrophenyl-alpha-D-arabinofuranoside; no exact match to the BglM-G1 observation was established.

Separate focused API queries returned zero records for each of: `UniProtKB_AC:KRO51423`, `EnzymeNameRecommendedName:BglM-G1`, `Substrate_facet:p-nitrophenyl-alpha-D-arabinofuranoside`, `Substrate_facet:p-nitrophenyl-alpha-D-rhamnopyranoside`, `PubMedID:30345395`, and free-text `KRO51423`, `BglM-G1`, `30345395`, `arabinofuranoside`, `rhamnopyranoside`. Because not all these fields/terms are necessarily indexed or canonicalized equivalently, zero results are recorded only as scoped query outcomes; the 445-row EC query was also inspected for relevant records.

Reproducible API links: [SABIO-RK EC 3.2.1.21 query](https://sabiork.h-its.org/api/ft/proxy-select?q=ecnumber%3A3.2.1.21&context=sabio&view=getEntryResult&rows=1000), [exact KRO51423 query](https://sabiork.h-its.org/api/ft/proxy-select?q=UniProtKB_AC%3AKRO51423&context=sabio&view=getEntryResult&rows=100), [exact source PMID query](https://sabiork.h-its.org/api/ft/proxy-select?q=PubMedID%3A30345395&context=sabio&view=getEntryResult&rows=100). SABIO-RK is a reaction/kinetics resource; it does not provide a complete tested-pair denominator.

## BRENDA public EC page

Fetched the live [BRENDA EC 3.2.1.21 page](https://www.brenda-enzymes.org/enzyme.php?ecno=3.2.1.21) on 2026-10-01 and searched its returned page content for `BglM-G1`, `KRO51423`, DOI `10.1038/s42003-018-0167-7`, and `Mhaindarkar`; none appeared. The page's reaction summary included p-nitrophenyl **alpha-L**-arabinofuranoside entries and p-nitrophenyl **alpha-L**-rhamnopyranoside entries, including a visible non-BglM enzyme row for the latter. These are not the paper's alpha-D substrates and do not establish coverage of the BglM-G1 source observations. This was a public-page string/summary inspection, not an authenticated full BRENDA export or exhaustive synonym/sequence search.

## Row-level ruling and implication

For NP005 and NP007, the source outcome is a qualitative, panel-level author-reported non-detection. In the scoped BRENDA/SABIO-RK searches above, **no exact protein–substrate–source/result record was established**. These rows are candidates for incremental literature-derived evidence relative to the queried public records, but are not proven globally database-unique observations: exact construct identity lacks a public accession, synonym/index coverage may differ, and database snapshots/exports were not audited. The correct status is “no exact match established in scoped current queries,” not “absent from BRENDA/SABIO-RK.”

NP006 and NP008 remain ambiguous H75R table dashes; this crosswalk does not resolve their source outcome. The row-level adjudication table and annotation CSV have been updated accordingly.
