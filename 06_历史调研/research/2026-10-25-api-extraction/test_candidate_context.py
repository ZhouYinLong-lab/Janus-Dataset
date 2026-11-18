"""Synthetic offline context regressions; no API, keys, or historical sources."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import candidate_context as context
from corpus import parse_source, sha


def unit(uid, text, section='Results', kind='body_paragraph'):
    return {'unit_id': uid, 'text': text, 'kind': kind,
            'section': section, 'locator': uid}


def candidate(cid, anchor, quote=None):
    return {'candidate_id': cid, 'unit_id': anchor['unit_id'],
            'quote': quote or anchor['text'], 'compound_mentions': [],
            'condition_mentions': []}


class CandidateContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='janus_candidate_context_')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def frozen_job(self, units, primary=None, suffix='.html', raw=b'normalized fixture'):
        source = self.directory / ('source' + suffix)
        source.write_bytes(raw)
        document = {'paper_id': 'P', 'source_path': str(source),
                    'source_sha256': sha(source), 'units': units}
        parsed = self.directory / 'document.json'
        parsed.write_text(json.dumps(document), encoding='utf-8')
        return {'paper_id': 'P', 'source_path': str(source),
                'source_sha256': document['source_sha256'],
                'document_path': str(parsed),
                'primary_units': deepcopy(primary if primary is not None else units[:1]),
                'context_units': []}

    def xml_job(self, xml):
        source = self.directory / 'source.xml'
        source.write_text(xml, encoding='utf-8')
        document = parse_source(source, 'P')
        parsed = self.directory / 'document.json'
        parsed.write_text(json.dumps(document), encoding='utf-8')
        job = {'paper_id': 'P', 'source_path': str(source),
               'source_sha256': sha(source), 'document_path': str(parsed),
               'primary_units': deepcopy([u for u in document['units']
                                         if u['kind'] == 'body_paragraph']),
               'context_units': []}
        return job, document

    def assert_group_cap(self, groups):
        for group in groups:
            units = group['context_units']
            self.assertEqual(len({u['unit_id'] for u in units}), len(units))
            self.assertLessEqual(sum(len(u['text']) for u in units), 18_000)
            supplied = {u['unit_id'] for u in units}
            for mapping in group['candidate_contexts']:
                self.assertLessEqual(set(mapping['allowed_evidence_unit_ids']), supplied)

    def test_two_quotes_share_complete_frozen_paragraph(self):
        paragraph = unit('p', 'Cells received 10 uM for 24 h. Drug A had no effect. '
                         'Drug B did not degrade BRD4.')
        job = self.frozen_job([paragraph])
        candidates = [candidate('A', paragraph, 'Drug A had no effect.'),
                      candidate('B', paragraph, 'Drug B did not degrade BRD4.')]
        before = deepcopy((job, candidates))
        maps, supplied = context.build_candidate_contexts(job, candidates)
        self.assertEqual(supplied, [paragraph])
        self.assertEqual([m['allowed_evidence_unit_ids'] for m in maps], [['p'], ['p']])
        self.assertTrue(all(m['context_complete'] for m in maps))
        groups = context.plan_candidate_groups(job, candidates)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['candidates'], candidates)
        self.assertEqual(groups[0]['candidate_contexts'], maps)
        self.assertEqual(groups[0]['context_units'], [paragraph])
        self.assertEqual((job, candidates), before)
        self.assert_group_cap(groups)

    def test_anchor_preserves_frozen_primary_fragment_not_full_source(self):
        paragraph = unit('p', 'Earlier sentence. Cells received 1 uM. No effect. Later sentence.')
        start, end = 18, 55
        fragment = dict(paragraph, unit_id='p:chars:18:55', parent_unit_id='p',
                        char_start=start, char_end=end, text=paragraph['text'][start:end])
        job = self.frozen_job([paragraph], [fragment])
        maps, supplied = context.build_candidate_contexts(
            job, [candidate('C', fragment, 'No effect.')])
        self.assertEqual(supplied, [fragment])
        self.assertEqual(maps[0]['anchor_unit_id'], fragment['unit_id'])

    def test_shared_support_and_another_anchor_are_counted_once(self):
        left = unit('left', 'A failed. ' + 'a' * 2990)
        shared = unit('shared', 'Cells were treated. ' + 's' * 10000)
        right = unit('right', 'B failed. ' + 'b' * 2990)
        job = self.frozen_job([left, shared, right], [left, right])
        candidates = [candidate('A', left, 'A failed.'), candidate('B', right, 'B failed.')]
        groups = context.plan_candidate_groups(job, candidates)
        self.assertEqual(len(groups), 1)
        self.assertTrue(all(m['context_complete'] for m in groups[0]['candidate_contexts']))
        self.assertEqual([u['unit_id'] for u in groups[0]['context_units']],
                         ['left', 'right', 'shared'])
        self.assert_group_cap(groups)
        # When adjacent prose is also another anchor it is already supplied.
        job = self.frozen_job([left, right], [left, right])
        maps, supplied = context.build_candidate_contexts(job, candidates)
        self.assertEqual(len(supplied), 2)
        self.assertEqual(maps[0]['context_unit_ids'], ['right'])
        self.assertEqual(maps[1]['context_unit_ids'], ['left'])
        self.assertTrue(all(m['context_complete'] for m in maps))

    def test_oversized_group_recursively_splits_and_keeps_order(self):
        primary, units = [], []
        for index in range(8):
            anchor = unit(f'p{index}', f'Drug {index} failed.', section=f'R{index}')
            primary.append(anchor)
            units.extend([anchor, unit(f'n{index}', 'n' * 6000, section=f'R{index}')])
        job = self.frozen_job(units, primary)
        candidates = [candidate(str(i), anchor) for i, anchor in enumerate(primary)]
        maps, _ = context.build_candidate_contexts(job, candidates)
        self.assertTrue(any(not m['context_complete'] for m in maps))
        groups = context.plan_candidate_groups(job, candidates)
        self.assertEqual([len(g['candidates']) for g in groups], [2, 2, 2, 2])
        self.assertEqual([c['candidate_id'] for g in groups for c in g['candidates']],
                         [str(i) for i in range(8)])
        self.assertTrue(all(m['context_complete'] for g in groups for m in g['candidate_contexts']))
        self.assert_group_cap(groups)

    def test_singleton_gap_keeps_full_anchor_and_omitted_ids(self):
        anchor = unit('p', 'Drug A failed.')
        too_large = unit('n', 'x' * 18_001)
        job = self.frozen_job([anchor, too_large])
        groups = context.plan_candidate_groups(job, [candidate('C', anchor)])
        self.assertEqual(len(groups), 1)
        mapping = groups[0]['candidate_contexts'][0]
        self.assertFalse(mapping['context_complete'])
        self.assertEqual(mapping['omission_reason'], 'context_cap')
        self.assertEqual(mapping['omitted_context_unit_ids'], ['n'])
        self.assertEqual(groups[0]['context_units'], [anchor])
        self.assert_group_cap(groups)

    def test_oversized_anchor_is_reported_without_truncation_or_cap_overflow(self):
        anchor = unit('p', 'No effect. ' + 'x' * 18_000)
        job = self.frozen_job([anchor])
        groups = context.plan_candidate_groups(job, [candidate('C', anchor, 'No effect.')])
        self.assertEqual(groups[0]['context_units'], [])
        mapping = groups[0]['candidate_contexts'][0]
        self.assertFalse(mapping['context_complete'])
        self.assertEqual(mapping['omitted_context_unit_ids'], ['p'])
        self.assertEqual(mapping['allowed_evidence_unit_ids'], [])
        self.assert_group_cap(groups)

    def test_max_candidates_and_empty_plan(self):
        anchor = unit('p', 'No effect.')
        job = self.frozen_job([anchor])
        candidates = [candidate(str(i), anchor) for i in range(9)]
        self.assertEqual([len(g['candidates']) for g in context.plan_candidate_groups(job, candidates)],
                         [8, 1])
        self.assertEqual([len(g['candidates']) for g in context.plan_candidate_groups(job, candidates, 3)],
                         [3, 3, 3])
        self.assertEqual(context.plan_candidate_groups(job, []), [])
        self.assertEqual(context.build_candidate_contexts(job, []), ([], []))
        for value in (0, -1, True, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                context.plan_candidate_groups(job, candidates, value)

    def test_explicit_figure_precedes_nearby_body_and_methods(self):
        job, document = self.xml_job(
            '<article><body><sec id="r"><title>Results</title>'
            '<p id="p">Alpha failed (Figure <xref ref-type="fig" rid="f">2A</xref>).</p>'
            '<p id="near">' + 'n' * 10000 + '</p>'
            '<fig id="f"><label>Figure 2</label><caption><p>' + 'c' * 9000 + '</p></caption></fig>'
            '</sec><sec id="m"><title>Methods</title><p id="method">Alpha cells were treated.</p>'
            '</sec></body></article>')
        anchor = next(u for u in document['units'] if u['locator'] == 'p')
        maps, supplied = context.build_candidate_contexts(job, [candidate('C', anchor)])
        by_locator = {u['locator']: u['unit_id'] for u in document['units']}
        self.assertEqual([u['locator'] for u in supplied], ['p', 'f', 'method'])
        self.assertEqual(maps[0]['context_roles'][by_locator['f']], context.CONTEXT_ROLES[0])
        self.assertEqual(maps[0]['omitted_context_unit_ids'], [by_locator['near']])
        self.assertEqual(maps[0]['references'][0]['via'], 'xml_xref')
        self.assertNotIn('panel', maps[0]['references'][0])

    def test_explicit_oversized_table_uses_existing_fragments_and_reports_rest(self):
        job, document = self.xml_job(
            '<article><body><p id="p">Drug failed (<xref ref-type="table" rid="t">Table 1</xref>).</p>'
            '<table-wrap id="t"><label>Table 1</label><caption><p>' + 'x' * 21000 +
            '</p></caption></table-wrap></body></article>')
        anchor = job['primary_units'][0]
        table = next(u for u in document['units'] if u['kind'] == 'table')
        pieces = []
        for start in range(0, len(table['text']), 7000):
            end = min(start + 7000, len(table['text']))
            pieces.append(dict(table, unit_id=f't:{start}:{end}', parent_unit_id=table['unit_id'],
                               char_start=start, char_end=end, text=table['text'][start:end]))
        job['context_units'] = pieces
        groups = context.plan_candidate_groups(job, [candidate('C', anchor)])
        mapping = groups[0]['candidate_contexts'][0]
        self.assertIn(pieces[0]['unit_id'], mapping['context_unit_ids'])
        self.assertNotIn(table['unit_id'], mapping['allowed_evidence_unit_ids'])
        self.assertEqual(mapping['omitted_context_unit_ids'], [pieces[2]['unit_id']])
        self.assertEqual(mapping['references'][0]['status'], 'partial_context_cap')
        self.assertTrue(all(role == context.CONTEXT_ROLES[0]
                            for role in mapping['context_roles'].values()))
        self.assert_group_cap(groups)
        # A job containing only one old slice cannot imply the rest was supplied.
        job['context_units'] = pieces[:1]
        maps, _ = context.build_candidate_contexts(job, [candidate('C', anchor)])
        self.assertFalse(maps[0]['context_complete'])
        self.assertIn(table['unit_id'], maps[0]['omitted_context_unit_ids'])
        self.assertEqual(maps[0]['omission_reason'], 'incomplete_explicit_unit_fragments')

    def test_bioc_explicit_label_and_methods(self):
        job, document = self.xml_job(
            '<collection><document><passage><infon key="section_type">RESULTS</infon>'
            '<offset>0</offset><text>Alpha failed (Figure 2).</text></passage>'
            '<passage><infon key="type">FIG</infon><offset>50</offset>'
            '<text>Figure 2. Conditions for alpha.</text></passage>'
            '<passage><infon key="section_type">METHODS</infon><offset>100</offset>'
            '<text>Alpha cells were treated for 2 h.</text></passage></document></collection>')
        anchor = job['primary_units'][0]
        maps, supplied = context.build_candidate_contexts(job, [candidate('C', anchor)])
        self.assertEqual(maps[0]['references'][0]['via'], 'text_label')
        self.assertEqual(maps[0]['references'][0]['status'], 'selected')
        self.assertIn('lexically_linked_method', maps[0]['context_roles'].values())
        self.assertTrue(maps[0]['context_complete'])
        self.assertEqual(len(supplied), 3)

    def test_existing_fragments_can_supply_part_of_a_target_smaller_than_cap(self):
        job, document = self.xml_job(
            '<article><body><p id="p">Drug failed (<xref ref-type="table" rid="t">Table 1</xref>).'
            + 'a' * 5000 + '</p><table-wrap id="t"><label>Table 1</label><caption><p>'
            + 'x' * 14000 + '</p></caption></table-wrap></body></article>')
        anchor = job['primary_units'][0]
        table = next(u for u in document['units'] if u['kind'] == 'table')
        pieces = []
        for start in range(0, len(table['text']), 7000):
            end = min(start + 7000, len(table['text']))
            pieces.append(dict(table, unit_id=f't:{start}:{end}', parent_unit_id=table['unit_id'],
                               char_start=start, char_end=end, text=table['text'][start:end]))
        job['context_units'] = pieces
        groups = context.plan_candidate_groups(job, [candidate('C', anchor, 'Drug failed')])
        mapping = groups[0]['candidate_contexts'][0]
        self.assertFalse(mapping['context_complete'])
        self.assertIn(pieces[0]['unit_id'], mapping['context_unit_ids'])
        self.assertEqual(mapping['omitted_context_unit_ids'], [pieces[1]['unit_id']])
        self.assert_group_cap(groups)

    def test_normalized_html_pdf_use_kind_section_without_fabricated_refs(self):
        for suffix, raw in (('.html', b'<html>not closed'), ('.pdf', b'%PDF synthetic'),
                            ('.htm', b'<html><body><p>Alpha failed (Figure 2).</p></body></html>')):
            with self.subTest(suffix=suffix):
                anchor = unit('p', 'Alpha failed (Figure 2).')
                nearby = unit('n', 'Cells received 1 uM for 2 h.')
                other = unit('other', 'Unrelated prose.', section='Discussion')
                method = unit('m', 'Alpha cells were treated.', section='Methods')
                figure = unit('f', 'Figure 2. Different observation.', kind='figure_caption')
                units = [anchor, nearby, other, method, figure]
                # Normalized PDF units can omit locators entirely.
                if suffix == '.pdf':
                    for value in units:
                        value.pop('locator')
                job = self.frozen_job(units, suffix=suffix, raw=raw)
                maps, supplied = context.build_candidate_contexts(job, [candidate('C', anchor)])
                self.assertEqual([u['unit_id'] for u in supplied], ['p', 'n', 'm'])
                self.assertEqual(maps[0]['references'], [])
                self.assertEqual(maps[0]['context_roles'],
                                 {'n': 'adjacent_body_paragraph', 'm': 'lexically_linked_method'})

    def test_unresolved_explicit_reference_reports_scope_gap(self):
        job, _ = self.xml_job('<article><body><p id="p">No effect '
                             '(<xref ref-type="fig" rid="absent">Figure 9</xref>).</p>'
                             '</body></article>')
        maps, _ = context.build_candidate_contexts(job, [candidate('C', job['primary_units'][0])])
        self.assertFalse(maps[0]['context_complete'])
        self.assertEqual(maps[0]['omission_reason'], 'unresolved_explicit_reference')
        self.assertEqual(maps[0]['omitted_context_unit_ids'], [])
        self.assertEqual(maps[0]['references'][0]['rid'], 'absent')

    def test_disk_change_is_rejected_after_success_for_both_interfaces(self):
        anchor = unit('p', 'No effect.')
        job = self.frozen_job([anchor])
        candidates = [candidate('C', anchor)]
        context.build_candidate_contexts(job, candidates)
        context.plan_candidate_groups(job, candidates)
        # Same-length replacement also defeats mtime/size-only caches.
        source = Path(job['source_path'])
        original_stat = source.stat()
        source.write_bytes(b'X' * original_stat.st_size)
        os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        for function in (context.build_candidate_contexts, context.plan_candidate_groups):
            with self.subTest(interface=function.__name__), self.assertRaisesRegex(ValueError, 'Source changed'):
                function(job, candidates)

    def test_frozen_document_precedes_parsers_and_rejects_identity_changes(self):
        anchor = unit('p', 'No effect.')
        job = self.frozen_job([anchor])
        parser = ModuleType('source_formats')
        parser.parse_document = unittest.mock.Mock(side_effect=AssertionError('must use frozen document'))
        with patch.dict(sys.modules, {'source_formats': parser}), patch.object(
                context, 'parse_source', side_effect=AssertionError('must use frozen document')):
            context.build_candidate_contexts(job, [candidate('C', anchor)])
        document_path = Path(job['document_path'])
        original = json.loads(document_path.read_text(encoding='utf-8'))
        for field, value in (('paper_id', 'OTHER'), ('source_sha256', 'changed')):
            with self.subTest(field=field):
                changed = dict(original, **{field: value})
                document_path.write_text(json.dumps(changed), encoding='utf-8')
                with self.assertRaises(ValueError):
                    context.build_candidate_contexts(job, [candidate('C', anchor)])

    def test_parser_preference_and_legacy_fallback_without_frozen_document(self):
        anchor = unit('p', 'No effect.')
        job = self.frozen_job([anchor])
        document = json.loads(Path(job.pop('document_path')).read_text(encoding='utf-8'))
        candidates = [candidate('C', anchor)]
        parser = ModuleType('source_formats')
        parser.parse_document = unittest.mock.Mock(return_value=document)
        with patch.dict(sys.modules, {'source_formats': parser}), patch.object(context, 'parse_source') as legacy:
            context.build_candidate_contexts(job, candidates)
            parser.parse_document.assert_called_once_with(job['source_path'], 'P')
            legacy.assert_not_called()
        with patch.dict(sys.modules, {'source_formats': None}), patch.object(
                context, 'parse_source', return_value=document) as legacy:
            context.build_candidate_contexts(job, candidates)
            legacy.assert_called_once_with(job['source_path'], 'P')
        # A parser error is an input error, not a reason to silently reparse.
        parser.parse_document.side_effect = ValueError('unsupported source')
        with patch.dict(sys.modules, {'source_formats': parser}), self.assertRaisesRegex(ValueError, 'unsupported'):
            context.build_candidate_contexts(job, candidates)

    @unittest.skipUnless(importlib.util.find_spec('source_formats'), 'source adapter not installed yet')
    def test_available_source_formats_xml_adapter_without_snapshot(self):
        job, _ = self.xml_job('<article><body><sec id="r"><title>Results</title>'
                             '<p id="p">No effect.</p><p id="n">Cells received 1 uM.</p>'
                             '</sec></body></article>')
        job.pop('document_path')
        maps, supplied = context.build_candidate_contexts(job, [candidate('C', job['primary_units'][0])])
        self.assertTrue(maps[0]['context_complete'])
        self.assertEqual([u['locator'] for u in supplied], ['p', 'n'])

    def test_rejects_unscanned_anchor_and_duplicate_candidate_ids(self):
        anchor = unit('p', 'No effect.')
        job = self.frozen_job([anchor])
        with self.assertRaisesRegex(ValueError, 'scanned body unit'):
            context.build_candidate_contexts(job, [candidate('C', unit('other', 'No effect.'))])
        with self.assertRaisesRegex(ValueError, 'Duplicate candidate_id'):
            context.plan_candidate_groups(job, [candidate('C', anchor), candidate('C', anchor)])


if __name__ == '__main__':
    unittest.main()
