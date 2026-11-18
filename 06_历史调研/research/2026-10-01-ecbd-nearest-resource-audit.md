# ECBD as the nearest existing resource for contextualized molecular negative data

## Why this audit matters

ECBD is a closer comparator to Janus than a conventional confirmed-hit database: it intentionally preserves active and inactive results from primary, confirmatory, and counter-screening stages, alongside per-compound assay endpoints and detailed assay descriptions. This rules out a broad claim that contextualized molecular negative-data resources do not exist. The remaining question must concern retrospective recovery from historical literature and incremental coverage beyond resources such as ECBD, PubChem BioAssay, and ChEMBL.

## What ECBD already provides

The 2025 *Nucleic Acids Research* description reports that ECBD is the central repository for experimental campaigns conducted through EU-OPENSCREEN. The consortium says it makes complete project datasets available, including active and inactive outcomes. The acquisition process is controlled: compounds undergo central identity/purity quality control, sites follow common assay-quality guidance, and trained staff upload data from the screening site.

Its data model has three linked objects—compound, assay, and target. A submitted assay can include a free-text protocol and hit-selection description; controlled descriptions of assay stage, format, detection method, target/context, and readout; and optional protocol or visualization attachments. An assay stores one or more numeric endpoints (including raw and transformed values) and a mandatory result/activity call for each tested compound. For activity assays, the submitter-defined result vocabulary includes `active`, `inconclusive`, `inactive`, `error`, and `undefined`. Therefore ECBD can preserve the distinction between a negative call and inconclusive/erroneous/unclassified outcomes instead of converting every non-hit into a binary zero.

As of the article's August 2024 snapshot, ECBD had 89 submissions, 48 public; 107,414 compounds; 33 targets across public plus embargoed data; about 4.32 million endpoint values and 2.40 million result values overall. Public records at that snapshot included about 2.46 million endpoints and 1.68 million result values. The paper stated the then-current embargoed data were expected to become public by H1 2027. These are time-stamped article counts, not live counts for 2026.

## What this does not settle for Janus

ECBD is a prospective/infrastructure-deposited screen resource built around defined EU-OPENSCREEN libraries and projects. The article does not claim a systematic retrospective full-text search across molecular-science papers, nor does it estimate what fraction of historical negative observations were absent from papers or existing databases. Its outcome call is defined by the submitting assay provider; the data model supports context and endpoints, but that does not imply every record has the same detection limit or that raw replicate-level observations are universally available. Some datasets were embargoed in the paper's snapshot. The article also notes that validated confirmatory screens are shared with ChEMBL, making exact cross-resource observation deduplication relevant rather than optional.

Thus ECBD provides strong prior art for preserving complete tested-compound panels, typed outcomes, endpoints, and assay context. It does **not** establish that historical literature recovery is solved or that Janus would contribute incremental observations. A defensible Janus pilot should query exact enzyme/substrate or compound/target/source/assay matches against ECBD and other resources, report exact versus near matches, and avoid treating a resource not searched as evidence of novelty.

## Mainline update

The study is a direct counterexample to the framing “molecular negative datasets do not exist.” A narrower, testable framing is: “Can we recover source-confirmed inactive/no-detect/censored assay observations from a pre-specified historical literature sample, quantify the observation-level increment beyond existing resources, and preserve evidence and condition semantics with reproducible adjudication?” Whether this increment is large enough to justify a project is still empirical.

## Primary source

Škuta et al. (2025), *ECBD: European chemical biology database*, [DOI 10.1093/nar/gkae904](https://doi.org/10.1093/nar/gkae904), [full text](https://academic.oup.com/nar/article/53/D1/D1383/7832351).
