"""Assistant source review: paraphrases and auditable units, not expert annotations.

Question references are never sent to the answering API. All are development cases.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    papers = {}
    def paper(pid, note):
        papers[pid] = {'paper_id': pid, 'scope_note': note, 'cards': [], 'questions': []}
    def card(cid, scope, sources, text, coverage, reason):
        papers[cid[:4]]['cards'].append(dict(id=cid, scope=scope, source_unit_ids=sources.split(),
            text=text, resource_coverage=coverage, coverage_reason=reason))
    def question(qid, kind, text, r1, r2, sources, errors):
        pid='B'+qid[1:4]
        papers[pid]['questions'].append(dict(id=qid, paper_id=pid, kind=kind, question=text,
            rubric=[r1,r2], source_unit_ids=sources.split(), overclaim_errors=errors,
            reference_status='assistant_source_review_not_expert_gold', split='development'))

    paper('B204', 'CK1alpha medicinal chemistry; known structured results and representation controls.')
    card('B204-N1','grouped_negative','B204:6b62cfa156191ac1',
         'Selected compounds in the amide-bioisostere series were reported not to degrade GSPT1 or IKZF1. The body directs readers to supplementary Table S1 and Figure S5; the sentence does not enumerate every selected compound or its individual conditions. Keep this as a group statement.',
         'partly_already_covered','Generic extraction has individual GSPT1 and IKZF1 rows with >10000 nM bounds. No claim of a wholly new negative result.')
    card('B204-N2','relative_negative_with_positive_context','B204:5882683d8f4c32d3 B204:75bc8e26b13b6293 B204:b2d6de825e21227e B204:94a661b658d1f6c8',
         'Compounds 5 and 6 bind CRBN similarly (FP 1.3 and 1.4 uM), yet CK1alpha Dmax falls from 82% to 23%; IKZF1 Dmax falls from 84% to 57%. HiBiT CK1alpha uses HEK293 and IKZF1 uses Jurkat cells. Dmax is maximum degradation over 24 h at 10 uM. NanoBRET complex formation is a separate 2 h experiment. Compound6 is weaker, not non-binding or an exact zero.',
         'already_covered_numeric_context_combination','Both resources contain degradation; MolGlueDB includes binding and time. Useful only as endpoint/context control.')
    card('B204-N3','qualitative_negative_with_positive_context','B204:6b62cfa156191ac1 B204:011d0f37f0a955af',
         'Benzimidazole compound20 was reported inactive up to 10 uM in degradation and antiproliferation assays. The sentence supplies no exact measured Dmax. Compound21 instead has CK1alpha DC50 0.004 uM (4 nM), Dmax 89%, antiproliferation IC50 0.022 uM. Initial endpoint CK1alpha HiBiT screening of this series was at 24 h; MOLM-13 antiproliferation at 72 h. Potent compounds subsequently received kinetic profiling.',
         'known_result_representation_issue','MolGlueDB contains compound20 Dmax=0 and compound21 DC50=2 nM; narrative gives qualitative20 and endpoint21=4 nM. Different assay/curation representations are not automatically errors.')
    question('Q204A','negative','What does the study establish about GSPT1 and IKZF1 degradation for selected amide-bioisostere compounds, and what is the scope of that conclusion?',
             'No observed GSPT1 or IKZF1 degradation for selected compounds.', 'Preserves selected/tested scope, without extending to all compounds and conditions.',
             'B204:6b62cfa156191ac1',['Universal no degradation; exact zeros for every unlisted compound.'])
    question('Q204B','relative_negative','How did changing compound5 to compound6 affect CRBN binding and CK1alpha removal, and how was the degradation maximum defined?',
             'Binding similar 1.3 vs1.4 uM; CK1alpha Dmax82% vs23%.', 'Dmax over24h at10uM, distinct from2h NanoBRET.',
             'B204:5882683d8f4c32d3 B204:75bc8e26b13b6293 B204:b2d6de825e21227e',['Non-binding; exact no degradation; uses2h forDmax.'])
    question('Q204C','positive','What CK1alpha endpoint-screen degradation potency and Dmax did the narrative report for compound21, and how long was the initial screen?',
             'Narrative endpoint DC50 4nM (0.004uM), Dmax89%.', 'Initial endpoint HiBiT screen24h; separates72h proliferation.',
             'B204:6b62cfa156191ac1 B204:011d0f37f0a955af',['Uses72h fordegradation; treats a different assay DC50 as the narrative value.'])
    question('Q204D','insufficient_precision','Does the narrative for compound20 establish an exact measured Dmax of zero? State the supported activity conclusion and its tested range.',
             'Narrative qualitative inactivity up to10uM.', 'Exact measured Dmax zero is not established by that statement; retains assay/range scope.',
             'B204:6b62cfa156191ac1 B204:011d0f37f0a955af',['Exact numerical zero claimed as measured in prose; universal inactivity.'])

    paper('B209','CK1alpha degraders; source conflict in CRBN-null cell identity retained.')
    card('B209-N1','selectivity_negative_and_measurement_limit','B209:2f948f4aa6034ed6 B209:9e0114d992117533',
         'LC-02-105 induces CK1alpha degradation in MOLM13; GSPT1 is spared and IKZF2 effects are minimal. Figure1C immunoblots used24h treatment, with concentrations not enumerated in the caption text. WEE1 was not detected; authors suggest low basal expression. This does not establish that the compound cannot degrade measurable WEE1.',
         'absent_in_both_exports','MolGlueDB19 source rows listCK1alpha, no GSPT1/IKZF2/WEE1 observations. Generic8 rows are quantitativeCK1alpha only.')
    card('B209-N2','conditional_negative','B209:bc201fcc98c07d77 B209:c9ae69757646a5b6',
         'dCK1alpha-1 degrades CK1alpha in wild-type cells but spares CRBN-null cells. The body names MOLM13 for the null comparison, while Figure3C caption names MOLT4 parental/CRBN-null cells and 6h. This cell-line discrepancy remains unresolved. Separately, Figure3D specifies MOLM13 pretreatment 1h with MLN4924, bortezomib or pomalidomide followed by 100nM degrader 6h; these treatments rescue degradation. In MOLM13, 100nM causes degradation from 2h through at least 24h. Do not merge these separate assays.',
         'absent_in_both_exports','No CRBN-null/rescue records in the source-filtered exports; retain source cell-line discrepancy.')
    card('B209-N3','phenotype_boundary','B209:46f95977ba352390 B209:62822d9ac71062a0',
         'dCK1alpha-1 combined with navtemadlin (AMG-232) shows antiproliferative synergy in MOLM13 over3days, evaluated with HSA. No significant combinatorial effect was observed in DLD-1, T98G or HEK293T. This is a combination/viability endpoint, not evidence that either compound has zero degradation or no individual activity. Exact doses for those negative cell lines are not given in the body passage.',
         'absent_in_both_exports','Both exports omit combination-response boundaries. Auxiliary phenotype, not a direct degradation failure.')
    card('B209-P1','positive_context','B209:a489875398e42139 B209:97dc52ea79da031d',
         'LC-04-087, renamed dCK1alpha-1, has CK1alpha DC50=12nM andDmax=90%. Table2 degradation uses CK1alpha-HiBiT MOLT4,24h; proliferation usesMOLM13,72h. The WB and HiBiT experiments should not be conflated.',
         'already_covered','Generic output contains the assay/cell/time; positive control.')
    question('Q209A','negative','For LC-02-105 in MOLM13, how do the CK1alpha, GSPT1 and IKZF2 results compare, and what treatment time supports that protein comparison?',
             'CK1alpha degraded; GSPT1 spared; IKZF2 minimally affected.', 'Immunoblot comparison Figure1C uses24h; does not generalize beyond it.',
             'B209:2f948f4aa6034ed6 B209:9e0114d992117533',['Universal selectivity or exact zero;72hviability transferred toWB.'])
    question('Q209B','insufficient_evidence','Does the WEE1 result establish that LC-02-105 is inactive against WEE1? Explain what was measured and the interpretation limit.',
             'WEE1 was not detected, potentially low basal expression.', 'Cannot infer demonstrated WEE1 non-degradation from missing detectable protein.',
             'B209:2f948f4aa6034ed6',['Non-detection called proven resistance/inactivity.'])
    question('Q209C','positive','What quantitative CK1alpha degradation results are reported for dCK1alpha-1 (LC-04-087), and in which cell line and time was the tabulated HiBiT assay performed?',
             'DC50 12nM andDmax90%.','MOLT4 CK1alpha-HiBiT24h, separate fromMOLM13 proliferation72h.',
             'B209:a489875398e42139 B209:97dc52ea79da031d',['MOLM13WB substituted for tabulatedMOLT4HiBiT.'])
    question('Q209D','conditional_negative','Is the dCK1alpha-1/navtemadlin combination effect equally supported in MOLM13, DLD-1, T98G and HEK293T? State the endpoint and scope.',
             'MOLM13 synergy but no significant combinatorial effect inDLD-1,T98G,HEK293T.', 'This is combination/antiproliferation, not all individual activity or degradation being absent.',
             'B209:46f95977ba352390 B209:62822d9ac71062a0',['Non-significance converted into exact zero or universal degradation failure.'])

    paper('B236','SJ3149 series; generic extraction already covers low IKZF1 and partialIKZF2.')
    card('B236-N1','known_selectivity_negative','B236:74e5a65121a03bfb B236:3a1abd820192eb5f B236:a7a3a53a01a8088d',
         'SJ0040 and SJ3149 show IKZF1 Dmax <10% in Jurkat HiBiT. Here Dmax is maximum over 24h at 10uM; DC50 is measured at 4h. SJ3149 is not devoid of IKZF2 effects: MOLM13 WB 4h shows ~40% IKZF2 reduction at 10uM, while CK1alpha reaches 50% degradation at 4nM. Keep cell, protein, time and dose separate.',
         'generic_already_covered','Generic output includes bothIKZF1<10% rows andIKZF2~40%4h10uM; not newly recovered results.')
    card('B236-N2','conditional_negative','B236:e512d87b6acecae3 B236:475359069ba4bf53',
         'SJ0040 and SJ3149 do not affect CK1alpha levels in CRBN-knockout MOLM13 as reported in Supplementary Fig1c,d; exact degradation conditions are not specified in that body statement. For viability, WT and CRBN-null MOLM13 were treated with 1uM SJ7095, SJ0040 or SJ3149 at 24/72h; at 72h WT death increases (~80% dead/dying for SJ3149), but CRBN-null viability is unaffected. A separate G40N CK1alpha overexpression experiment in MOLM13 confirms degradation resistance and reduced 72h viability response, not necessarily zero cytotoxicity.',
         'absent_in_both_exports','No CRBN-knockout or G40N experimental boundary in either source-filtered export.')
    card('B236-N3','phenotype_boundary_with_positive_context','B236:31e7aecc9e329e1b B236:c51ddcd3356441b3 B236:48fbbc0ae511cd77 B236:231a1850e9def516',
         'Lenalidomide did not show appreciable cytotoxicity in MOLM13 even at high concentrations. This does not mean inability to degrade CK1alpha: 100uM for 24h gave a degradation effect comparable to 100nM SJ7095 for 4h in MOLM13 WB. The screening viability endpoint is 72h CellTiterGlo. Protein removal and cell death are separate endpoints.',
         'context_not_in_export','Generic data contain lenalidomideCK1alphaHEK293HiBiT42%, but not this MOLM13WB100uM24h/viability boundary.')
    question('Q236A','conditional_negative','What evidence tests whether SJ0040/SJ3149 activity depends on CRBN in MOLM13, and what can be concluded separately about protein levels and viability?',
             'CRBN-nullMOLM13: neither compound affectsCK1alpha levels.', 'Viability contrast:1uM24/72hdesign, WTdeath at72h vsCRBN-null unaffected; no exact degradation conditions invented.',
             'B236:e512d87b6acecae3',['Transfers viability1uM72h to degradation assay; claims constitutive inactivity inWT.'])
    question('Q236B','negative_boundary','Does the paper support describing SJ3149 as having no IKZF1 or IKZF2 effects? Give the measured limits and distinguish the assays.',
             'IKZF1 Dmax<10%JurkatHiBiT over24h at10uM.', 'IKZF2~40%reductionMOLM13WB4h10uM, so not zero effects.',
             'B236:74e5a65121a03bfb B236:3a1abd820192eb5f B236:a7a3a53a01a8088d',['Equates<10%orpartial40% with exact no degradation; mergesassays.'])
    question('Q236C','positive','What CK1alpha DC50 was measured for SJ3149 by immunoblotting versus the HiBiT assay, and what cell and time identify each?',
             'ImmunoblotMOLM13,4h,3.7nM.', 'HiBiTHEK293,4h,6nM; distinguishes these assays.',
             'B236:e512d87b6acecae3 B236:74e5a65121a03bfb B236:3a1abd820192eb5f B236:231a1850e9def516',['Single universalDC50 or24h for4hDC50.'])
    question('Q236D','endpoint_boundary','Because lenalidomide showed little MOLM13 cytotoxicity, can it be called unable to degrade CK1alpha? Explain the protein and viability observations.',
             'Little appreciableMOLM13cytotoxicity does not imply noCK1alphaDEG.', '100uM24h lenalidomideWB comparable to100nMSJ7095at4h; separates72hviability.',
             'B236:31e7aecc9e329e1b B236:231a1850e9def516',['Calls lenalidomide incapable ofCK1alphaDEG; mergesviabilityandprotein.'])

    paper('B251','CRBN-binding analogues; no processed generic rows, so compare database only for coverage.')
    card('B251-N1','grouped_negative','B251:e2edd608742e8460 B251:e6c376c1b95f59d9',
         '6- and 7-substituted Len cores are generally inactive in degradation despite retaining CRBN binding. The tested G-loop neosubstrates are IKZF3, CK1alpha, GSPT1, SALL4. The authors propose failure to form a productive ternary complex as an explanation; this is not a direct measurement proving zero complex formation. Four of 24 compounds had CRBN binding IC50 >10uM. Ymin 100%=no protein reduction, 0%=complete degradation.',
         'database_context_loss_generic_unassessed','MolGlueDB has inactiveflags but no retainedCRBNbinding/context here. Genericprocessed/outputhasnoDOIrows; cannot call an extractor miss.')
    card('B251-N2','paired_negative_positive','B251:23196ad2241a6dd5 B251:e6c376c1b95f59d9',
         'For GSPT1, 16a has EC50 >10uM, Ymin 100%; 22a has EC50 1.4uM, Ymin 2.3%. Ymin is remaining protein, not percent degraded, so 22a induces much deeper degradation. For IKZF3, 13a EC50 1.86uM, Ymin 79%; 19a EC50 0.012uM, Ymin 9.2%. These are tested endpoint-specific results, not all proteins.',
         'database_depth_loss_generic_unassessed','MolGlueDB retains someEC50s/inactiveflags but dropsYmin; genericnotassessedonthisDOI.')
    card('B251-N3','non_significant_group','B251:23196ad2241a6dd5 B251:e6c376c1b95f59d9',
         'Compound21a is the outlier among 4-/5-substituted cyclopropenes: no significant degradation of any of the tested neosubstrates IKZF3, CK1alpha, GSPT1, SALL4. This phrasing does not give an exact 0% degradation, individual assay conditions or activity against untested proteins.',
         'database_scope_loss_generic_unassessed','MolGlueDB21aIsActive0butnoindividualtargets/conditions. Genericcohortnotconfirmed.')
    question('Q251A','negative','Why are 6-/7-substituted Len cores not simply non-binders, and how firmly does the study establish the proposed reason for their lack of degradation?',
             'GenerallyinactivebutretainCRBNbinding.', 'Unproductivecomplexisanexplanationauthorssuggest,notdirectproof;scopeinvestigatedneosubstrates.',
             'B251:e2edd608742e8460 B251:e6c376c1b95f59d9',['NoCRBNbinding;provenzeroternarycomplexformation;allproteins.'])
    question('Q251B','positive','For IKZF3, how did compound19a compare with13a in potency and depth, and what does Ymin mean?',
             '19aEC500.012uM,Ymin9.2%vs13a1.86uM,79%.', 'Yminisremainingprotein;19adeeper/morepotent,0complete100noreduction.',
             'B251:23196ad2241a6dd5 B251:e6c376c1b95f59d9',['Ymininterpretedaspercentdegradation;wrongdirection.'])
    question('Q251C','insufficient_precision','Does the compound21a result establish zero degradation of every protein? State the actual reported result and its scope.',
             'No significantdegradationamongtestedneosubstrates.', 'IKZF3,CK1alpha,GSPT1,SALL4scope;notexactzerooruntestedproteome.',
             'B251:23196ad2241a6dd5 B251:e6c376c1b95f59d9',['Exactzero;universalproteomeclaim.'])
    question('Q251D','negative_positive_pair','Compare the GSPT1 effects of16a and22a using EC50 and Ymin. Does a Ymin of100% mean complete degradation?',
             '16a>10uM/Ymin100%;22a1.4uM/Ymin2.3%.', '100%Ymin=no proteinreduction;22a muchdeeperdegradation.',
             'B251:23196ad2241a6dd5 B251:e6c376c1b95f59d9',['ReversesYmin;100%completeDEG.'])

    paper('B280','Reported endogenousCRBN-dependentGCKdegrader; atypical mechanistic claim, kept separate from CK1alpha series. Reports are source-based, not independently replicated here.')
    card('B280-N1','grouped_negative_with_positive_context','B280:aba3ca36aa5e7932 B280:6b508047162e5ab3',
         'Figure3g comparison tested UDP-glucose, UDP-NAG, UDP-galactose and IMiDs thalidomide, lenalidomide, pomalidomide for glucokinase degradation. Only UDP-glucose was reported to induce glucokinase degradation among those compounds. This is a group-level tested comparison; the body passage does not list dose, time, cell line for each negative arm. It does not establish universal IMiD inactivity.',
         'database_missing_comparator_results_generic_unassessed','MolGlueDBonlyUDP-glucoseIsActive0,nocomparators/targets/conditions. Genericnotprocessedhere;noextractorfailureclaim.')
    card('B280-N2','endpoint_boundary','B280:7ef76f74cc013653',
         'In pancreatic NIT-1 cells, the paper reports UDP-glucose dose-dependent endogenous glucokinase protein reduction and a degradation time course 3–72h. Glucokinase transcription was unchanged over that period. Unchanged RNA is not absence of protein reduction. No exact DC50 or Dmax is given in this body passage.',
         'database_missing_endpoint_context_generic_unassessed','OnlyanIsActiveflagintheDB,withoutprotein/transcriptcomparison;genericunassessed.')
    card('B280-P1','positive_context','B280:2f2a1141d05b7c23',
         'The paper reports WB glucokinase protein reduction after 10mM UDP-glucose in HEK293 and 1mM in NCI-H929-1a. Intracellular UDP-glucose was comparatively high in HEK293 and low in NCI-H929-1a. These are administered concentration examples, not measured DC50 values or universal minimum thresholds.',
         'database_polarity_unresolved_generic_unassessed','DBUDP-glucoseIsActive0contrastswithpaperreportedpositiveGCKresult;do notdeclareDBwrongwithoutcurationdefinition.')
    question('Q280A','negative','Which tested UDP-monosaccharides and IMiDs induced glucokinase degradation in the Figure3g comparison, and how broadly can the result be generalized?',
             'OnlyUDP-glucose;notUDP-NAG,UDP-galactose,thalidomide,lenalidomide,pomalidomide.', 'Preservestestedcomparison/contextscope;nouniversalinactivity.',
             'B280:aba3ca36aa5e7932',['UniversalnoeffectofIMiDs/analoguesatallconditions.'])
    question('Q280B','endpoint_boundary','In NIT-1, does unchanged glucokinase transcription mean UDP-glucose failed to reduce the protein? State what the paper reports over time.',
             'Proteinreduction/degradationreported3–72h.', 'Transcriptionunchanged;RNAandproteinendpointsdistinct.',
             'B280:7ef76f74cc013653',['UnchangedRNAconvertedtofailedproteindegradation.'])
    question('Q280C','positive','What administered UDP-glucose concentrations were reported to reduce glucokinase in HEK293 versus NCI-H929-1a, and are these DC50 estimates?',
             'HEK29310mM,NCI-H929-1a1mM.', 'Observedadministrationexamples,notDC50oruniversalminimumthresholds.',
             'B280:2f2a1141d05b7c23',['CallsvaluesDC50orexactminimalnecessarydoses.'])
    question('Q280D','insufficient_evidence','Can the accessible body text assign an exact concentration and duration to each negative comparator in Figure3g? What details would need checking?',
             'Noexactdose/durationforeachnegativecomparatorinthebodytext.', 'NeedFigure3g/fullcaption/supplementaryorprotocol;donotborrowpositivecell/time/dose.',
             'B280:aba3ca36aa5e7932',['InventsnegativeconditionsbyborrowingNIT1/HEK293positiveassays.'])
    for p in papers.values():
        for item in p['cards'] + p['questions']:
            field = 'text' if 'text' in item else 'question'
            item[field] = re.sub(r'\b(compound|with|and|of)(?=\d)', r'\1 ', item[field], flags=re.I)
    return list(papers.values())


if __name__ == '__main__':
    data=build()
    for p in data:
        units={u['unit_id'] for u in json.loads((HERE/f'local/documents/{p["paper_id"]}.json').read_text(encoding='utf-8'))['units']}
        for item in p['cards']+p['questions']:
            assert set(item['source_unit_ids'])<=units,item['id']
    (HERE/'reviewed_cases.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'papers':len(data),'cards':sum(len(p['cards']) for p in data),'questions':sum(len(p['questions']) for p in data),'api_calls':0}))
