# Q25BW5/BGL1A–cellobiose: cross-paper outcome wording and evidence semantics

## Question

Do the apparently different BGL1A–cellobiose statements in 2006–2008 sources establish a contradiction, or do they show why outcome language must be kept separate from assay-level thresholds?

Relevance: **3/3** to the Janus focus on recovering and representing negative evidence with source and experimental context. This follows the Q25BW5 overlap audit; it is a three-paper source-semantics check, not a systematic review.

## Evidence checked

1. **Tsukada et al. 2006 (PMID 16896601).** The abstract says both recombinant enzymes (BGL1A and BGL1B) hydrolyzed several beta-glycosidic compounds and that cellobiose was hydrolyzed more effectively by BGL1B than by BGL1A. This is comparative language: it supports a relative difference but gives no numerical lower bound, detection limit, or specific threshold for BGL1A in the abstract. [PubMed](https://pubmed.ncbi.nlm.nih.gov/16896601/)
2. **Nijikken et al. 2007 (PMID 17376440).** The abstract says BGL1B effectively hydrolyzes cellobiose and cellobionolactone, “but BGL1A does not.” The BRENDA source trace for Q25BW5/cellobiose points to this reference (reference 679851). The publisher full text could not be inspected in the prior audit; the statement is therefore currently verified at abstract level, not at assay-method/LOD level. [PubMed](https://pubmed.ncbi.nlm.nih.gov/17376440/)
3. **Tsukada et al. 2008 (PMID 18023045; DOI 10.1002/bit.21717).** The abstract says five BGL1A residues were mutated to corresponding BGL1B residues and the effects on cellobiose hydrolysis were evaluated; kinetic parameters were compared at the wild-type optimum pH, with mutation-specific changes in efficiency. SABIO-RK represents multiple entries from this one paper as pH-dependent kinetics for wild type and mutants. [PubMed](https://pubmed.ncbi.nlm.nih.gov/18023045/); [SABIO-RK exact Q25BW5 query](https://sabiork.h-its.org/api/ft/proxy-select?q=UniProtKB_AC%3AQ25BW5&context=sabio&view=getEntryResult&rows=100)

The PubMed source records establish that the claims concern the same fungal enzyme family/protein, but the abstracts alone do not establish that the assay conditions, readout sensitivity, enzyme preparations, or operational meaning of “does not” were identical. Therefore the 2006 comparative phrase and 2007 qualitative non-detection-like wording are **not adjudicated here as a proven experimental contradiction**. The correct data representation is source-specific wording plus recoverable assay details, threshold/LOD if available, and a separate normalized interpretation with uncertainty.

## Why this matters for the six Heins pilot observations

The Heins 2014 entries are not a generic claim that “BGL1A does not hydrolyze cellobiose”; they are reported `<0.1` values for particular pH/temperature conditions (60/80/90 °C). Other publications describe cellobiose hydrolysis for BGL1A or BGL1A variants under other contexts. Thus the unit to preserve is the condition-specific experimental observation, not the protein–substrate pair collapsed to one permanent binary class.

## Boundary and implication

This source set is a useful annotation stress test for distinguishing (a) comparative low activity, (b) source-level “does not” statements, (c) censored/below-threshold numeric values, and (d) quantified positive kinetics. It does **not** establish a general rate of contradictory labels, decide which statement is biologically correct, prove that assay conditions alone explain the differences, or demonstrate model benefit. A full resolution would require accessible methods/results for all three studies and extraction of assay sensitivity, substrate/enzyme concentrations, measurement time, controls, and raw or tabulated values.
