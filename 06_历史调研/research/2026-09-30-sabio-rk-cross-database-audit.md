# SABIO-RK cross-database check for the GH1 NIMS pilot

## Question and relevance

Does a second public enzyme resource expose the pilot's exact enzyme–substrate observations, and can its records serve as a negative-evidence comparator?

Relevance: **3/3** to cross-resource coverage and interpretation of the negative-data gap. This is a bounded live-query audit, not a release-wide completeness assessment.

## What SABIO-RK represents

SABIO-RK describes itself as a manually curated resource for biochemical reactions and reaction kinetics. Its records can include reaction participants, enzyme/protein identifiers, organism, experimental conditions and literature references; the 2017 database paper describes literature curation and distinguishes its reaction-oriented kinetic representation from BRENDA's enzyme-centered organization. SABIO-RK's current documentation still exposes web search and REST-style access, although the public interface was reimplemented in 2026.

These design goals make SABIO-RK a useful comparator for whether a *positive reaction/kinetic observation* is already structured elsewhere. They do not make it a complete tested-pair matrix or a dedicated repository of no-activity results.

## Live query audit (2026-09-30)

Queries were sent to the currently served endpoint `https://sabiork.h-its.org/api/ft/proxy-select` with `context=sabio&view=getEntryResult`. The successful field syntax was tested with the site's own documented UniProt query example and the EC query below. Exact query examples:

- [`ecnumber:3.2.1.86`](https://sabiork.h-its.org/api/ft/proxy-select?q=ecnumber%3A3.2.1.86&context=sabio&view=getEntryResult)
- [`Substrate_facet:Xylobiose`](https://sabiork.h-its.org/api/ft/proxy-select?q=Substrate_facet%3AXylobiose&context=sabio&view=getEntryResult)
- [`Substrate_facet:Cellobiose`](https://sabiork.h-its.org/api/ft/proxy-select?q=Substrate_facet%3ACellobiose&context=sabio&view=getEntryResult)
- [`Substrate_facet:Lactose`](https://sabiork.h-its.org/api/ft/proxy-select?q=Substrate_facet%3ALactose&context=sabio&view=getEntryResult)

The interface returned:

| Query | Returned records | What they establish |
|---|---:|---|
| `Substrate_facet:Xylobiose` | 2 | Positive reaction entries for *Talaromyces emersonii* (UniProt Q8X212) and *Trichoderma reesei* (Q92458), EC 3.2.1.37, PMID 16752410 |
| `Substrate_facet:Cellobiose` | 31 | Structured reaction/kinetic entries across multiple enzymes and organisms |
| `Substrate_facet:Lactose` | 88 | Structured reaction/kinetic entries across multiple enzymes and organisms |
| `ecnumber:3.2.1.86` | 16 | Kinetic entries with this EC, mostly different enzyme/protein/reaction records; they are not a match to the GH1 NIMS observation merely because the EC agrees |
| Exact `UniProtKB_AC` searches for D4LC32, A0ACM7, Q55000, D4MF92 | 0 each | No exact match returned for these four tested identifiers in this query view |
| Source DOI `10.1021/cb500244v`, NCBI accession `AAU43012`, and free-text `Heins` | 0 each | No hit returned in these exact queries |

The xylobiose query therefore demonstrates cross-resource coverage of the *compound and a positive reaction*, not coverage of the sampled protein or its `<0.1` no-detect result. A shared substrate name, organism, or EC number alone is not an observation-level join. Likewise, zero exact-query results are retrieval outcomes, not proof that an article or observation is absent from every SABIO-RK field or upstream source.

## Implications for our project

1. BRENDA and SABIO-RK are not interchangeable coverage comparators: one is enzyme-centered, while the other organizes reaction kinetics and experimental context.
2. A cross-resource audit should distinguish exact protein + substrate + source matches from EC/substrate-only or compound-only matches.
3. SABIO-RK can help test whether measured *positive kinetic reactions* already exist and whether conditions/references are structured. It does not, on this audit, provide a usable denominator of tested negatives or establish that its unreturned pairs were tested.
4. The current GH1 extraction pilot must continue to classify source-cell evidence and database matching at observation level; no “database-unique negative fraction” is calculated from this pass.

## Reproducibility and sources

- Live REST query interface: [SABIO-RK API](https://sabiork.h-its.org/api/ft/proxy-select?q=ecnumber%3A3.2.1.86&context=sabio&view=getEntryResult).
- Current link/query documentation: [SABIO-RK documentation](https://sabiork.h-its.org/layouts/content/documentation.gsp); it gives `UniProtKB_AC:P52789` as an example query.
- Database paper: Wittig et al., “SABIO-RK: an updated resource for manually curated biochemical reaction kinetics,” *Nucleic Acids Research* (2018), [DOI 10.1093/nar/gkx1065](https://doi.org/10.1093/nar/gkx1065).
- Search index demonstrates its kinetic-data orientation: [SABIO-RK REST services manual](https://sabiork.h-its.org/sabioRestWebServices/).
- The Heins NIMS pilot sample and its source-cell provenance remain in [`pilots/gh1-nims/gh1_nims_negative_sample_100.csv`](pilots/gh1-nims/gh1_nims_negative_sample_100.csv).

