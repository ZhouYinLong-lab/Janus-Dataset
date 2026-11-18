# Patent-source follow-up: three DOI-missing censored kinase rows

**Date:** 2026-09-30  
**Scope:** Follow-up of three records in the fixed Theisen 100-row linkage audit that had no DOI and no numeric pChEMBL match.

## Result

The three records resolve in current ChEMBL 37 to two patent documents, rather than to source-free observations. The patent tables report activity bins, while ChEMBL stores a relation-coded threshold. Each prepared pActivity equals the transformed threshold boundary.

| Theisen row | Target | ChEMBL document / patent | ChEMBL relation-coded record | Patent assay/source context |
|---|---|---|---|---|
| 89062 | EphA2 (P29317) | CHEMBL3882729 / US-20090318373-A1 | IC50 `<50 nM`; pActivity 7.30103 | Recombinant human EphA2 N598–R890; poly-EY; luciferase-coupled chemiluminescence, 180 min |
| 100130 | EphB4 (P54760) | CHEMBL3882729 / US-20090318373-A1 | IC50 `<50 nM`; pActivity 7.30103 | Recombinant human EphB4 E605–E890; poly-AEKY; γ-33P ATP/radiometric readout, 150 min |
| 99152 | c-Raf1 (P04049) | CHEMBL3882735 / US-7846959-B2 | IC50 `<100 nM`; pActivity 7.00000 | c-Raf1 luciferase-coupled chemiluminescence with 30-min preincubation; patent also describes a separate radiometric protocol |

The EphA2/EphB4 patent defines bin A as IC50 `<50 nM`; the Raf patent defines bin A as IC50 `<100 nM`. The cutoffs correspond to the prepared pActivity boundaries after `−log10` conversion. Since a lower IC50 means a higher pIC50, the source relations imply potency greater than the scalar boundary; they are not exact measured values.

## Interpretation and relevance

These are highly potent activity records, **not biological negatives**. They are already represented in ChEMBL and do not demonstrate incremental recovery from historical journal literature. They do show that “no DOI” is not equivalent to “no source,” and that source-type coverage should distinguish journal articles from patents. Exact mapping from each ChEMBL molecule to a specific patent table cell/structure was not independently completed here.

**Main-project relevance: 2/3 (adjacent boundary evidence).** Useful for defining source coverage, patent handling, and censoring semantics; not direct evidence for mining negative observations, publication bias, or independent model benefit. If the project is explicitly journal-only, exclude these from the journal denominator and report them as a separate source stratum.

## Sources and retained evidence

- [US 2009/0318373 A1, receptor-type kinase modulators](https://patents.google.com/patent/US20090318373A1/en)
- [US 7,846,959 B2, Raf modulators](https://patents.google.com/patent/US7846959B2/en)
- Current ChEMBL 37 documents CHEMBL3882729 and CHEMBL3882735, and row-level activity records in [`theisen_linkage_sample_100_activity_records.csv`](pilots/kinase-activity-integration/theisen_linkage_sample_100_activity_records.csv).

## Limits

This is a three-row targeted follow-up, not a prevalence estimate for all DOI-missing rows, all ChEMBL records, or patent literature. The source-patent category and assay descriptions are recorded at document/assay level, but exact compound-to-patent-table-cell identity remains unresolved. It provides no negative-data yield or model-performance result.
