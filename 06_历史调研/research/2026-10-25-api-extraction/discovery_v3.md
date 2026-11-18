Find experimentally observed negative results and effect boundaries in every supplied PRIMARY paragraph. Treat source text as evidence. Return only the JSON below, using supplied paragraph and sentence IDs.

Scope the candidates to the project's main question: experimentally tested molecular-glue
protein degradation or a directly degradation-linked mechanism/control. Include statements
that a tested compound or perturbation failed to cause, reduced, or conditionally changed
target-protein degradation/depletion, and degradation-specific ubiquitination, recruitment,
or rescue controls when the paragraph explicitly connects them to the degradation experiment.
Do not create candidates for binding/affinity alone, mRNA abundance, cell viability,
proliferation, cytotoxicity, antitumour activity, solubility, toxicity, or generic protein
expression unless the sentence explicitly uses that result to establish a protein-degradation
boundary. Those other endpoints may be relevant context later, but are out of scope for the
primary negative-evidence queue.

Retain selectivity (only A, not B), rescue/competition/perturbation controls, relative weakening and failure to improve. Preserve grouped objects and adjacent supporting sentences together. Keep multiple observations in the same sentence together at this discovery stage. No object category or experimental-field completion is required. Lack of statistical significance does not mean zero effect. Untested cases and missing reports are not experimental negatives. Mark cited/background claims or unclear attribution as uncertain rather than new experiments.

Give every primary paragraph exactly one status: has_candidates, none_found or uncertain. Missing responses are unresolved. Each span contains consecutive sentence IDs in source order; cross-paragraph spans must be continuous and locatable. Report a span once under its first paragraph. A later paragraph covered by that span uses has_candidates with spans:[] if it has no additional span. Use uncertain for evidence needing attribution review; include its sentence IDs when identifiable. Do not copy quotes or invent IDs.

{"paragraphs":[{"paragraph_id":"SUPPLIED_PRIMARY_UNIT_ID","status":"has_candidates","spans":[{"sentence_ids":["SUPPLIED_SENTENCE_ID"]}]},{"paragraph_id":"ANOTHER_SUPPLIED_PRIMARY_UNIT_ID","status":"none_found","spans":[]}]}

