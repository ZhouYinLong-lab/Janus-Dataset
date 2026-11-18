"""Local regression checks; never read requests, responses, or credentials."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from corpus import HERE, LEGACY, normal, parse_source, read, sha
from prepare import build_jobs, split_units


def unit(uid, kind, content, section='Results', locator=None):
    return {'unit_id': uid, 'kind': kind, 'text': content,
            'section': section, 'locator': locator or uid}


def document(units):
    return {'paper_id': 'P', 'source_path': str(HERE / 'absent_fixture.xml'),
            'source_sha256': 'unavailable', 'units': units}


class LinkedContextTests(unittest.TestCase):
    def xml_jobs(self, xml, **kwargs):
        # In-memory source fixture, including the XML reread by LinkedContext.
        with patch.object(Path, 'read_bytes', return_value=xml.encode('utf-8')):
            d = parse_source(HERE / 'fixture.xml', 'P')
            return d, build_jobs(d, {}, **kwargs)

    def test_explicit_low_overlap_precedes_overlap(self):
        d = document([unit('p', 'body_paragraph', 'Drug failed in assay (Figure 2).'),
                      unit('high', 'table', 'Drug failed in assay ' * 2),
                      unit('low', 'figure_caption', 'Figure 2. HEK293T, 1 uM, 2 h.')])
        job = build_jobs(d, {}, context_cap=45)[0]
        self.assertEqual(job['context_units'][0]['unit_id'], 'low')
        self.assertEqual(job['context_selection_audit']['references'][0]['status'], 'selected')

    def test_rid_works_without_caption_label(self):
        _, jobs = self.xml_jobs('<article><body><sec id="r"><title>Results</title>'
            '<p id="p">No effect (Figure <xref ref-type="fig" rid="opaque-id">2</xref>).</p>'
            '<fig id="opaque-id"><label>Figure 2</label><caption><p>HEK293T 2 h.</p></caption></fig>'
            '</sec></body></article>', context_cap=12)
        job = jobs[0]
        self.assertEqual(job['context_units'][0]['locator'], 'opaque-id')
        ref = job['context_selection_audit']['references'][0]
        self.assertEqual((ref['via'], ref['rid'], ref['status']), ('xml_xref', 'opaque-id', 'selected'))

    def test_xml_addresses_embedded_targets_and_table_footnotes(self):
        _, jobs = self.xml_jobs('<article><body><sec><title>Results</title>'
            '<p>No effect (Table <xref ref-type="table" rid="t1">1</xref>).'
            '<table-wrap id="t1"><label>Table 1</label><table><tr><td>0</td></tr></table>'
            '<table-wrap-foot><fn><p>1 uM for 2 h.</p></fn></table-wrap-foot></table-wrap>'
            '</p></sec></body></article>')
        self.assertIn('1 uM for 2 h.', jobs[0]['context_units'][0]['text'])
        self.assertEqual(jobs[0]['context_selection_audit']['references'][0]['rid'], 't1')

    def test_other_ref_type_still_resolves_table_rid(self):
        _, jobs = self.xml_jobs('<article><body><p>See '
            '<xref ref-type="other" rid="t">Table <xref ref-type="other" rid="t">1</xref></xref>.</p>'
            '<table-wrap id="t"><label>Table 1</label><caption><p>Dose.</p></caption></table-wrap>'
            '</body></article>')
        refs = jobs[0]['context_selection_audit']['references']
        self.assertEqual([(r['rid'], r['status']) for r in refs], [('t', 'selected')])

    def test_budget_gap_and_all_candidates_audited(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 2).'),
                      unit('f', 'figure_caption', 'Figure 2. Caption too long.'),
                      unit('small', 'table', 'tiny')])
        job = build_jobs(d, {}, context_cap=5)[0]
        audit = job['context_selection_audit']
        self.assertEqual(audit['references'][0]['status'], 'omitted_context_cap')
        self.assertEqual(audit['references'][0]['omitted_unit_ids'], ['f'])
        self.assertEqual(audit['context_chars'], 4)
        self.assertEqual(len(audit['candidates']), 2)
        self.assertEqual(job['context_omitted_units'], 1)
        zero = build_jobs(d, {}, context_cap=0)[0]
        self.assertEqual(zero['context_units'], [])
        self.assertEqual(zero['context_selection_audit']['context_chars'], 0)
        with self.assertRaises(ValueError):
            build_jobs(d, {}, context_cap=-1)

    def test_no_reference_preserves_old_word_overlap_order(self):
        d = document([unit('p', 'body_paragraph', 'alpha beta gamma'),
                      unit('z', 'table', 'alpha beta'), unit('a', 'table', 'unrelated'),
                      unit('b', 'figure_caption', 'alpha beta')])
        job = build_jobs(d, {})[0]
        self.assertEqual([u['unit_id'] for u in job['context_units']], ['b', 'z', 'a'])
        self.assertEqual(job['context_selection_audit']['references'], [])

    def test_nearby_method_precedes_lexical_but_follows_reference(self):
        xml = ('<article><body><sec id="r"><title>Results</title>'
               '<p id="p">Alpha beta gamma failed (Figure 1).</p>'
               '<p id="method">Cells were incubated for two hours.</p>'
               '<fig id="f"><label>Figure 1</label><caption><p>Specific dosage.</p></caption></fig>'
               '</sec><sec id="other"><title>Results</title>'
               '<p id="othermethod">Cells were washed extensively.</p>'
               '<table-wrap id="t"><label>Table 8</label><caption><p>Alpha beta gamma failed.</p>'
               '</caption></table-wrap></sec></body></article>')
        _, jobs = self.xml_jobs(xml, primary_cap=1)
        candidates = jobs[0]['context_selection_audit']['candidates']
        self.assertEqual([(c['locator'], c['priority']) for c in candidates[:2]],
                         [('f', 'explicit_reference'), ('method', 'nearby_method')])
        other = next(c for c in candidates if c['locator'] == 'othermethod')
        self.assertEqual(other['priority'], 'word_overlap')

    def test_distant_method_not_promoted(self):
        d = document([unit('p', 'body_paragraph', 'alpha'),
                      unit('a', 'body_paragraph', 'one'),
                      unit('b', 'body_paragraph', 'two'),
                      unit('c', 'body_paragraph', 'Cells were incubated overnight.')])
        audit = build_jobs(d, {}, primary_cap=1)[0]['context_selection_audit']
        self.assertEqual(next(c for c in audit['candidates'] if c['unit_id'] == 'c')['priority'],
                         'word_overlap')

    def test_main_and_supplement_labels_are_distinct(self):
        for reference, target in [('Figure 1', 'main'), ('Figure S1', 's'),
                                  ('Supplementary Figure 1', 'supp'),
                                  ('Figure 1 (Supporting Information)', 'supp')]:
            with self.subTest(reference=reference):
                d = document([unit('p', 'body_paragraph', f'No effect ({reference}).'),
                              unit('main', 'figure_caption', 'Figure 1. Main conditions.'),
                              unit('s', 'figure_caption', 'Figure S1. Separate data.')])
                if target == 'supp':
                    d['units'][2] = unit('supp', 'figure_caption', 'Supplementary Figure 1. Separate data.')
                audit = build_jobs(d, {})[0]['context_selection_audit']
                # S1 and Supplementary Figure 1 share the supplement namespace.
                self.assertEqual(audit['references'][0]['target_unit_ids'], [target])
                promoted = [c['unit_id'] for c in audit['candidates']
                            if c['priority'] == 'explicit_reference']
                self.assertEqual(promoted, [target])

    def test_missing_supplement_is_not_main_figure(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Supplementary Figure 1).'),
                      unit('main', 'figure_caption', 'Figure 1. Main data.')])
        audit = build_jobs(d, {}, context_cap=0)[0]['context_selection_audit']
        self.assertEqual(audit['references'][0]['status'], 'unresolved')
        self.assertEqual(audit['references'][0]['target_unit_ids'], [])

    def test_supplement_prefix_and_group_suffix_never_link_main(self):
        for reference in ('Supporting Information Figure 1',
                          'Figures 1 and 2 (Supporting Information)',
                          'Figure 1, Supporting Information'):
            with self.subTest(reference=reference):
                d = document([unit('p', 'body_paragraph', f'No effect ({reference}).'),
                              unit('main1', 'figure_caption', 'Figure 1. Main data.'),
                              unit('main2', 'figure_caption', 'Figure 2. Main data.')])
                refs = build_jobs(d, {})[0]['context_selection_audit']['references']
                self.assertTrue(refs)
                self.assertTrue(all(r['status'] == 'unresolved' for r in refs))
                self.assertTrue(all(r['label_key'][1] for r in refs))

    def test_supplement_section_with_same_number_is_separate(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 1).'),
                      unit('main', 'figure_caption', 'Figure 1. Main data.'),
                      unit('supp', 'figure_caption', 'Figure 1. Other data.', section='SUPPLEMENTARY FIG')])
        self.assertEqual(build_jobs(d, {})[0]['context_selection_audit']['references'][0]['target_unit_ids'],
                         ['main'])
        _, jobs = self.xml_jobs('<article><body><sec><title>Results</title><p>See Figure 1.</p>'
            '<fig id="f"><label>Figure 1</label><caption><p>Main.</p></caption></fig></sec>'
            '<sec><title>Supporting Information</title>'
            '<fig id="s"><label>Figure 1</label><caption><p>Extra.</p></caption></fig></sec>'
            '</body></article>')
        ref = jobs[0]['context_selection_audit']['references'][0]
        self.assertEqual(len(ref['target_unit_ids']), 1)
        selected = next(u for u in jobs[0]['context_units'] if u['unit_id'] == ref['target_unit_ids'][0])
        self.assertEqual(selected['locator'], 'f')

    def test_caption_mentions_do_not_create_target_labels(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 2).'),
                      unit('f', 'figure_caption', 'Figure 1. Compare with Figure 2.')])
        self.assertEqual(build_jobs(d, {})[0]['context_selection_audit']['references'][0]['status'],
                         'unresolved')

    def test_authoritative_missing_rid_does_not_fall_back_to_main_label(self):
        _, jobs = self.xml_jobs('<article><body><p>No effect (Figure '
            '<xref ref-type="supplementary-material" rid="missing-supp">1</xref>).</p>'
            '<fig id="main"><label>Figure 1</label><caption><p>Main conditions.</p></caption></fig>'
            '</body></article>')
        refs = jobs[0]['context_selection_audit']['references']
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]['status'], 'unresolved')
        self.assertEqual(refs[0]['rid'], 'missing-supp')

    def test_ambiguous_text_label_stays_unresolved(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 1).'),
                      unit('a', 'figure_caption', 'Figure 1. First.'),
                      unit('b', 'figure_caption', 'Figure 1. Duplicate.')])
        ref = build_jobs(d, {})[0]['context_selection_audit']['references'][0]
        self.assertEqual((ref['status'], ref['resolution']), ('unresolved', 'ambiguous_label'))

    def test_bioc_fallback_uses_anchored_label(self):
        _, jobs = self.xml_jobs('<collection><document>'
            '<passage><infon key="section_type">RESULTS</infon><text>No effect (Fig. 2A).</text></passage>'
            '<passage><infon key="section_type">FIG</infon><text>Figure 2. Low overlap dose.</text></passage>'
            '</document></collection>')
        audit = jobs[0]['context_selection_audit']
        self.assertEqual(audit['xml_status'], 'bioc_text_labels')
        self.assertEqual(audit['references'][0]['status'], 'selected')

    def test_text_label_cannot_be_inferred_from_locator(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 1).'),
                      unit('f', 'figure_caption', 'Unlabelled caption.', locator='fig1')])
        self.assertEqual(build_jobs(d, {})[0]['context_selection_audit']['references'][0]['status'],
                         'unresolved')

    def test_multi_rid_and_number_lists(self):
        _, jobs = self.xml_jobs('<article><body><p>See <xref ref-type="fig" rid="a b">Figures 1 and 2</xref>.</p>'
            '<fig id="a"><label>Figure 1</label><caption><p>A.</p></caption></fig>'
            '<fig id="b"><label>Figure 2</label><caption><p>B.</p></caption></fig></body></article>')
        self.assertEqual([r['rid'] for r in jobs[0]['context_selection_audit']['references']], ['a', 'b'])
        d = document([unit('p', 'body_paragraph', 'See Figures 1–3 and Table 2.'),
                      *[unit(f'f{i}', 'figure_caption', f'Figure {i}. Data.') for i in range(1, 4)],
                      unit('t2', 'table', 'Table 2. Data.')])
        targets = {t for r in build_jobs(d, {})[0]['context_selection_audit']['references']
                   for t in r['target_unit_ids']}
        self.assertEqual(targets, {'f1', 'f2', 'f3', 't2'})

    def test_split_reference_audits_partial_caption_and_preserves_input(self):
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 2).'),
                      unit('f', 'figure_caption', 'Figure 2. ' + 'x' * 8000)])
        before = deepcopy(d)
        job = build_jobs(d, {}, context_cap=7000)[0]
        ref = job['context_selection_audit']['references'][0]
        self.assertEqual(ref['status'], 'partial_context_cap')
        self.assertEqual(len(ref['selected_unit_ids']), 1)
        self.assertEqual(len(ref['omitted_unit_ids']), 1)
        self.assertEqual(d, before)
        self.assertEqual(build_jobs(d, {}, context_cap=7000), [job])
        self.assertLessEqual(sum(len(u['text']) for u in job['context_units']), 7000)
        json.dumps(job)

    def test_changed_source_is_not_used_for_rids(self):
        xml = '<article><body><p id="p">Other.</p></body></article>'
        d = document([unit('p', 'body_paragraph', 'No effect (Figure 1).'),
                      unit('f', 'figure_caption', 'Figure 1. Data.')])
        with patch.object(Path, 'read_bytes', return_value=xml.encode()):
            audit = build_jobs(d, {})[0]['context_selection_audit']
        self.assertEqual(audit['xml_status'], 'source_hash_mismatch')
        self.assertEqual(audit['references'][0]['via'], 'text_label')


class ExistingDocumentTests(unittest.TestCase):
    def check_case(self, pid, result_id, targets, condition_strings):
        path = HERE / 'local/batch_quality_02/documents' / f'{pid}.json'
        source = next((LEGACY / 'sources').glob(f'{pid}_*.xml'), None)
        if not path.exists() or source is None:
            self.skipTest(f'Local {pid} source/document not present')
        d = read(path)
        before = deepcopy(d)
        self.assertEqual(sha(source), d['source_sha256'])
        # The existing document's unit text and identities still equal parse_source.
        self.assertEqual(parse_source(source, pid)['units'], d['units'])
        jobs = build_jobs(d, {})
        job = next(j for j in jobs if any(_u.get('parent_unit_id', _u['unit_id']) == result_id
                                        for _u in j['primary_units']))
        actual = {u['unit_id']: u for u in job['context_units']}
        self.assertTrue(set(targets) <= actual.keys())
        explicit = {t for r in job['context_selection_audit']['references']
                    if r['status'] == 'selected' for t in r['target_unit_ids']}
        self.assertTrue(set(targets) <= explicit)
        for target in targets:
            for condition in condition_strings:
                self.assertIn(normal(condition), normal(actual[target]['text']))
        self.assertLessEqual(sum(len(u['text']) for u in actual.values()), 18000)
        expected_primary = split_units([u for u in d['units'] if u['kind'] == 'body_paragraph'])
        self.assertEqual([u for j in jobs for u in j['primary_units']], expected_primary)
        self.assertEqual(d, before)

    def test_b212_compound_15_has_table1_and_figure2(self):
        self.check_case('B212', 'B212:dac6cdd3a4cbdc6c',
                        ['B212:a4ae56d9169d93cb', 'B212:37ceff5fa1db6ae0'],
                        ['HEK293T', '1 μM', '2 h'])

    def test_b151_handle8_has_figure4(self):
        self.check_case('B151', 'B151:6102e6e6e505e7bc', ['B151:270a897bda0aa98e'],
                        ['MM.1S', '10 μM', '24 h'])


if __name__ == '__main__':
    unittest.main()
