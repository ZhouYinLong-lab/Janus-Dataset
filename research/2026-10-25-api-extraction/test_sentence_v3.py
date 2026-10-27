"""Synthetic offline contract tests; no historical data, credentials or API."""
from copy import deepcopy
import hashlib
import json
import random
import unittest
from unittest.mock import patch

import sentence_v3 as v3


def unit(uid, text, kind='body_paragraph', locator=None):
    return {'unit_id': uid, 'text': text, 'kind': kind,
            'locator': locator if locator is not None else f'/article/body/p[{uid}]',
            'section': 'Results'}


def document(*units):
    digest = hashlib.sha256(json.dumps(units, ensure_ascii=False).encode()).hexdigest()
    return {'paper_id': 'P', 'source_path': 'offline-fixture.xml',
            'source_sha256': digest, 'parser_version': 2, 'units': list(units)}


def build(doc, **kwargs):
    return v3.build_sentence_jobs(doc, {'doi': '10.synthetic/offline', 'title': 'Fixture'}, **kwargs)


def row(job, paragraph=0, status='none_found', spans=None):
    return {'paragraph_id': job['paragraphs'][paragraph]['paragraph_id'],
            'status': status, 'spans': [] if spans is None else spans}


def span(job, *indices):
    return {'sentence_ids': [job['sentences'][i]['sentence_id'] for i in indices]}


def validate(job, *rows):
    return v3.validate_discovery({'paragraphs': list(rows)}, job)


class SentenceIndexTests(unittest.TestCase):
    def assert_roundtrip(self, doc, sentences):
        for source in doc['units']:
            if source['kind'] != 'body_paragraph':
                self.assertFalse(any(s['unit_id'] == source['unit_id'] for s in sentences))
                continue
            cursor = 0
            for s in (s for s in sentences if s['unit_id'] == source['unit_id']):
                self.assertLessEqual(cursor, s['char_start'])
                self.assertFalse(source['text'][cursor:s['char_start']].strip())
                self.assertEqual(source['text'][s['char_start']:s['char_end']], s['text'])
                self.assertTrue(s['text'].strip())
                self.assertEqual(s['kind'], 'body_paragraph')
                self.assertEqual(s['locator'], source['locator'])
                self.assertEqual(s['section'], source['section'])
                cursor = s['char_end']
            self.assertFalse(source['text'][cursor:].strip())

    def test_offsets_whitespace_unicode_and_nonbody(self):
        doc = document(unit('p1', ' \tNo loss.\n  Rescue failed!  蛋白未减少。仍有活性！\r\n'),
                       unit('fig', 'Figure is not body.', 'figure_caption'),
                       unit('p2', '\n \t'), unit('p3', 'Last clause without punctuation'))
        before = deepcopy(doc)
        indexed = v3.index_document(doc)
        self.assertEqual(len(indexed), 5)
        self.assert_roundtrip(doc, indexed)
        self.assertEqual(doc, before)
        self.assertEqual(set(indexed[0]), {'sentence_id', 'unit_id', 'char_start',
                                          'char_end', 'text', 'kind', 'locator', 'section'})

    def test_abbreviations_decimals_and_protein_names(self):
        first = ('Smith et al. tested e.g. IKZF1 and BRD4 in Fig. 2 at 0.25 nM, '
                 'i.e. 2.5-fold below control, using p.V600E and H3.3.')
        second = 'Dr. A. Smith saw no response in Figs. 3 and 4.'
        third = 'No improvement was observed.'
        doc = document(unit('p', ' '.join((first, second, third))))
        indexed = v3.index_document(doc)
        self.assertEqual([s['text'] for s in indexed], [first, second, third])
        self.assert_roundtrip(doc, indexed)

    def test_protein_punctuation_is_not_a_boundary(self):
        text = 'The p. V600E variant, E. coli and IL-1β were tested. No rescue.'
        indexed = v3.index_document(document(unit('p', text)))
        self.assertEqual(len(indexed), 2)
        self.assertTrue(indexed[0]['text'].endswith('tested.'))

    def test_conservative_ambiguous_long_paragraph(self):
        text = 'observed at 0.5 nM; ' * 700 + 'no increase'
        indexed = v3.index_document(document(unit('p', text)))
        self.assertEqual([s['text'] for s in indexed], [text])

    def test_quoted_sentences_and_punctuation_only(self):
        doc = document(unit('p', '  "No effect."  (Rescue failed.) Next? Yes! ...\t'))
        indexed = v3.index_document(doc)
        self.assert_roundtrip(doc, indexed)
        self.assertEqual(indexed[0]['text'], '"No effect."')

    def test_randomized_character_coverage(self):
        rng = random.Random(8721)
        alphabet = 'Abcβ53 .!?。！？\n\t;()[]\"’e.g.蛋白'
        for _ in range(150):
            text = ''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 300)))
            doc = document(unit('p', text))
            self.assert_roundtrip(doc, v3.index_document(doc))

    def test_stable_ids_depend_on_source_uid_offsets_and_version(self):
        doc = document(unit('p', 'No loss. Rescue failed.'))
        original = v3.index_document(doc)
        self.assertEqual(original, v3.index_document(deepcopy(doc)))
        altered = deepcopy(doc)
        altered['title'] = 'Metadata change'
        self.assertEqual(original, v3.index_document(altered))
        for change in ('hash', 'uid', 'offset'):
            altered = deepcopy(doc)
            if change == 'hash':
                altered['source_sha256'] = '0' * 64
            elif change == 'uid':
                altered['units'][0]['unit_id'] = 'other'
            else:
                altered['units'][0]['text'] = ' ' + altered['units'][0]['text']
            self.assertNotEqual(original[0]['sentence_id'], v3.index_document(altered)[0]['sentence_id'])
        with patch.object(v3, 'SPLIT_VERSION', 'future-version'):
            self.assertNotEqual(original[0]['sentence_id'], v3.index_document(doc)[0]['sentence_id'])

    def test_reject_ambiguous_source_identity(self):
        with self.assertRaises(ValueError):
            v3.index_document(document(unit('p', 'A.'), unit('p', 'B.')))
        with self.assertRaises(ValueError):
            v3.index_document(dict(document(), source_sha256=''))


class SentenceJobTests(unittest.TestCase):
    def test_pipeline_fields_and_default_limits(self):
        doc = document(*(unit(f'p{i}', 'No effect.') for i in range(7)))
        original = deepcopy(doc)
        output = build(doc)
        self.assertEqual([len(j['primary_units']) for j in output['jobs']], [3, 3, 1])
        required = {'job_id', 'paper_id', 'doi', 'title', 'source_path', 'source_sha256',
                    'source_parser_version', 'protocol', 'primary_units', 'sentences', 'paragraphs'}
        for job in output['jobs']:
            self.assertLessEqual(sum(len(p['text']) for p in job['primary_units']), 4000)
            self.assertTrue(required <= job.keys())
            self.assertEqual(job['protocol'], 'sentence_v3')
            self.assertEqual(job['source_parser_version'], 2)
            for p, mapping in zip(job['primary_units'], job['paragraphs']):
                self.assertEqual(mapping['paragraph_id'], p['unit_id'])
                self.assertEqual(p['unit_id'], p['parent_unit_id'])
                self.assertEqual((p['char_start'], p['char_end']), (0, len(p['text'])))
        self.assertFalse(output['gaps'])
        self.assertEqual(doc, original)

    def test_char_limit_is_total_and_exact_fit_is_allowed(self):
        doc = document(unit('p1', 'No loss.'), unit('p2', 'No gain.'), unit('p3', 'No help.'))
        output = build(doc, primary_cap=16)
        self.assertEqual([len(j['primary_units']) for j in output['jobs']], [2, 1])

    def test_long_paragraph_fragments_keep_sentence_boundaries(self):
        text = '  No activity.\n\tNo rescue.  Weak binding.   No improvement.  '
        doc = document(unit('p', text))
        output = build(doc, primary_cap=25)
        self.assertGreater(len(output['jobs']), 1)
        covered = []
        cursor = 0
        for job in output['jobs']:
            for p in job['primary_units']:
                self.assertLessEqual(len(p['text']), 25)
                self.assertEqual(p['text'], text[p['char_start']:p['char_end']])
                self.assertFalse(text[cursor:p['char_start']].strip())
                cursor = p['char_end']
                self.assertEqual(p['parent_unit_id'], 'p')
                self.assertNotEqual(p['unit_id'], 'p')
                self.assertEqual(p['locator'], doc['units'][0]['locator'])
                self.assertEqual(p['char_start'], job['sentences'][0]['char_start'])
                self.assertEqual(p['char_end'], job['sentences'][-1]['char_end'])
            covered.extend(s['sentence_id'] for s in job['sentences'])
        self.assertFalse(text[cursor:].strip())
        self.assertEqual(covered, [s['sentence_id'] for s in output['sentences']])
        self.assertFalse(output['gaps'])

    def test_oversize_sentence_remains_unscanned_between_valid_fragments(self):
        text = 'No loss. ' + 'An indivisible observation ' * 40 + '. No gain.'
        doc = document(unit('p', text))
        output = build(doc, primary_cap=40)
        self.assertEqual(len(output['gaps']), 1)
        gap = output['gaps'][0]
        self.assertEqual(gap['status'], 'unscanned')
        self.assertEqual(gap['reason'], 'sentence_exceeds_primary_cap')
        self.assertEqual(gap['text'], text[gap['char_start']:gap['char_end']])
        scanned = [s['sentence_id'] for j in output['jobs'] for s in j['sentences']]
        self.assertNotIn(gap['sentence_id'], scanned)
        self.assertEqual(set(scanned) | {gap['sentence_id']},
                         {s['sentence_id'] for s in output['sentences']})
        self.assertEqual(len(scanned), 2)

    def test_all_oversize_does_not_create_a_scanned_job(self):
        output = build(document(unit('p', 'x' * 4001)))
        self.assertEqual(output['jobs'], [])
        self.assertEqual(len(output['gaps']), 1)
        self.assertEqual(len(output['sentences']), 1)

    def test_large_whitespace_is_verifiable_and_does_not_join_fragments(self):
        text = 'No loss.' + '\t ' * 100 + 'No gain.'
        output = build(document(unit('p', text)), primary_cap=20)
        self.assertEqual(len(output['jobs']), 2)
        self.assertFalse(output['gaps'])
        a, b = (j['primary_units'][0] for j in output['jobs'])
        self.assertFalse(text[a['char_end']:b['char_start']].strip())

    def test_index_independent_of_batch_size_and_jobs_reproducible(self):
        doc = document(unit('p', 'No activity. No improvement. No rescue.'))
        a, b = build(doc), build(doc, primary_cap=20, max_paragraphs=1)
        self.assertEqual(a['sentences'], b['sentences'])
        self.assertEqual(a, build(deepcopy(doc)))
        self.assertEqual(len({j['job_id'] for j in b['jobs']}), len(b['jobs']))

    def test_empty_and_nonbody_document(self):
        output = build(document(unit('fig', 'No activity.', 'figure_caption'), unit('p', ' \n')))
        self.assertEqual(output, {'jobs': [], 'gaps': [], 'sentences': []})

    def test_fragment_ownership_is_complete_and_disjoint_across_caps(self):
        doc = document(unit('a', 'No loss.\tNo gain. ' + 'Long observation ' * 20 + '. No rescue.'),
                       unit('b', '  None responded.  Weak binding.\n'))
        for cap in (1, 8, 15, 30, 60, 4000):
            with self.subTest(cap=cap):
                output = build(doc, primary_cap=cap)
                scanned = [s['sentence_id'] for j in output['jobs'] for s in j['sentences']]
                gaps = [s['sentence_id'] for s in output['gaps']]
                self.assertEqual(len(scanned), len(set(scanned)))
                self.assertFalse(set(scanned) & set(gaps))
                self.assertEqual(set(scanned) | set(gaps),
                                 {s['sentence_id'] for s in output['sentences']})
                for job in output['jobs']:
                    self.assertLessEqual(sum(len(p['text']) for p in job['primary_units']), cap)
                    mapped = [sid for p in job['paragraphs'] for sid in p['sentence_ids']]
                    self.assertEqual(mapped, [s['sentence_id'] for s in job['sentences']])

    def test_invalid_caps(self):
        for cap in (0, -1, True, 2.5, '4000'):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                build(document(), primary_cap=cap)
            with self.subTest(paragraph_cap=cap), self.assertRaises(ValueError):
                build(document(), max_paragraphs=cap)


class DiscoveryValidationTests(unittest.TestCase):
    def setUp(self):
        self.doc = document(unit('p1', 'Compounds 1–8 were tested.\n  None reduced IKZF1 or IKZF3. '
                                 'Binding was weaker.'),
                            unit('p2', 'MG132 rescued the response. No improvement was observed.'),
                            unit('p3', 'The control remained active.'))
        self.job = build(self.doc)['jobs'][0]

    def reasons(self, result):
        return [r['reason'] for r in result['rejected']]

    def test_group_level_evidence_retains_multiple_objects_and_endpoints(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 0, 1)]),
                          row(job, 1), row(job, 2))
        self.assertTrue(output['accounting_complete'])
        self.assertEqual(len(output['accepted']), 1)
        candidate = output['accepted'][0]
        self.assertEqual(candidate['quote'], 'Compounds 1–8 were tested.\n  None reduced IKZF1 or IKZF3.')
        self.assertEqual(candidate['unit_id'], 'p1')
        self.assertEqual(candidate['source_unit_ids'], ['p1'])
        self.assertEqual(candidate['sentence_ids'], span(job, 0, 1)['sentence_ids'])
        self.assertNotIn('category', candidate)
        self.assertFalse(output['rejected'])

    def test_fragment_candidate_uses_primary_id_and_original_offsets(self):
        job = build(self.doc, primary_cap=50)['jobs'][1]
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 0)]))
        c = output['accepted'][0]
        self.assertEqual(c['unit_id'], job['primary_units'][0]['unit_id'])
        self.assertEqual(c['source_unit_ids'], ['p1'])
        part = c['quote_parts'][0]
        self.assertEqual(part['text'], self.doc['units'][0]['text'][part['char_start']:part['char_end']])

    def test_program_ids_stable_and_quote_is_read_from_source(self):
        job = self.job
        responses = [row(job, status='has_candidates', spans=[span(job, 0)]), row(job, 1), row(job, 2)]
        before = deepcopy((job, responses))
        first = validate(job, *responses)
        self.assertEqual(first, validate(deepcopy(job), *deepcopy(responses)))
        other_job = build(self.doc, max_paragraphs=1)['jobs'][0]
        second = validate(other_job, row(other_job, status='has_candidates', spans=[span(other_job, 0)]))
        self.assertEqual(first['accepted'][0]['candidate_id'], second['accepted'][0]['candidate_id'])
        self.assertEqual((job, responses), before)
        tampered = deepcopy(job)
        tampered['sentences'][0]['text'] = 'fabricated quote'
        result = validate(tampered, *responses)
        self.assertFalse(result['accepted'])
        self.assertIn('invalid_source_offsets', self.reasons(result))

    def test_unknown_id_quarantined_and_valid_neighbour_survives(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[
            {'sentence_ids': ['invented']}, span(job, 1)]), row(job, 1), row(job, 2))
        self.assertEqual(len(output['accepted']), 1)
        self.assertIn('unknown_sentence_id', self.reasons(output))
        self.assertEqual(output['coverage'][0]['status'], 'unresolved')
        self.assertEqual(output['coverage'][1]['status'], 'none_found')
        self.assertFalse(output['accounting_complete'])

    def test_mixed_valid_invalid_ids_do_not_shorten_a_span(self):
        job = self.job
        invalid = {'sentence_ids': [job['sentences'][0]['sentence_id'], 'unknown']}
        output = validate(job, row(job, status='has_candidates', spans=[invalid, span(job, 2)]),
                          row(job, 1), row(job, 2))
        self.assertEqual([c['sentence_ids'] for c in output['accepted']], [span(job, 2)['sentence_ids']])

    def test_duplicate_id_and_duplicate_span_are_quarantined(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[
            span(job, 0, 0), span(job, 1), span(job, 1), span(job, 2)]), row(job, 1), row(job, 2))
        self.assertEqual(len(output['accepted']), 2)
        self.assertIn('duplicate_sentence_id', self.reasons(output))
        self.assertIn('duplicate_span', self.reasons(output))

    def test_overlapping_spans_do_not_expand_same_sentence_twice(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[
            span(job, 0, 1), span(job, 1), span(job, 2)]), row(job, 1), row(job, 2))
        self.assertEqual(len(output['accepted']), 2)
        self.assertIn('overlapping_span', self.reasons(output))

    def test_missing_paragraph_is_unresolved(self):
        output = validate(self.job, row(self.job), row(self.job, 2))
        self.assertEqual([c['status'] for c in output['coverage']],
                         ['none_found', 'unresolved', 'none_found'])
        self.assertIn('missing_paragraph_response', output['coverage'][1]['reasons'])
        self.assertTrue(any(r.get('paragraph_id') == 'p2' for r in output['unresolved']))
        self.assertFalse(output['accounting_complete'])

    def test_explicit_none_found_is_complete_for_only_supplied_paragraphs(self):
        job = self.job
        output = validate(job, row(job), row(job, 1), row(job, 2))
        self.assertTrue(output['accounting_complete'])
        self.assertFalse(output['accepted'])
        self.assertFalse(output['unresolved'])
        self.assertEqual([c['status'] for c in output['coverage']], ['none_found'] * 3)

    def test_duplicate_paragraph_does_not_overwrite_first_or_neighbours(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 1)]),
                          row(job), row(job, 1, 'has_candidates', [span(job, 3)]), row(job, 2))
        self.assertEqual(len(output['accepted']), 2)
        self.assertIn('duplicate_paragraph_id', self.reasons(output))
        self.assertEqual(output['coverage'][0]['status'], 'unresolved')
        self.assertEqual(output['coverage'][1]['status'], 'has_candidates')

    def test_uncertain_background_retains_evidence_for_review(self):
        job = self.job
        output = validate(job, row(job, status='uncertain', spans=[span(job, 0, 1)]),
                          row(job, 1), row(job, 2))
        self.assertFalse(output['accepted'])
        self.assertTrue(output['accounting_complete'])
        self.assertEqual(output['coverage'][0]['status'], 'uncertain')
        review = [u for u in output['unresolved'] if u.get('reason') == 'uncertain_span']
        self.assertEqual(len(review), 1)
        self.assertIn('Compounds 1–8', review[0]['quote'])

    def test_none_found_and_empty_has_candidates_conflicts(self):
        job = self.job
        for first in (row(job, spans=[span(job, 0)]), row(job, status='has_candidates')):
            output = validate(job, first, row(job, 1), row(job, 2))
            self.assertEqual(output['coverage'][0]['status'], 'unresolved')
            self.assertFalse(output['accepted'])
            self.assertFalse(output['accounting_complete'])

    def test_continuous_cross_paragraph_group_is_locatable(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 2, 3, 4)]),
                          row(job, 1, 'has_candidates'), row(job, 2))
        self.assertTrue(output['accounting_complete'])
        c = output['accepted'][0]
        self.assertEqual(c['source_unit_ids'], ['p1', 'p2'])
        self.assertEqual(c['quote'], 'Binding was weaker.\n\nMG132 rescued the response. No improvement was observed.')
        self.assertEqual(len(c['quote_parts']), 2)
        for part in c['quote_parts']:
            source = next(u for u in self.doc['units'] if u['unit_id'] == part['unit_id'])
            self.assertEqual(part['text'], source['text'][part['char_start']:part['char_end']])
        self.assertEqual(output['coverage'][0]['candidate_ids'], output['coverage'][1]['candidate_ids'])

    def test_noncontinuous_and_reversed_spans_are_quarantined(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[
            span(job, 0, 2), span(job, 1, 0), span(job, 2, 5), span(job, 1)]), row(job, 1), row(job, 2))
        self.assertEqual(self.reasons(output).count('non_contiguous_span'), 3)
        self.assertEqual(len(output['accepted']), 1)

    def test_cross_paragraph_anchor_must_be_first_primary_fragment(self):
        job = self.job
        output = validate(job, row(job), row(job, 1, 'has_candidates', [span(job, 2, 3)]), row(job, 2))
        self.assertIn('span_anchor_mismatch', self.reasons(output))
        self.assertFalse(output['accepted'])

    def test_cross_paragraph_status_conflict_keeps_evidence_and_marks_unresolved(self):
        job = self.job
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 2, 3)]),
                          row(job, 1), row(job, 2))
        self.assertEqual(len(output['accepted']), 1)
        self.assertEqual(output['coverage'][1]['status'], 'unresolved')
        self.assertIn('cross_paragraph_status_conflict', output['coverage'][1]['reasons'])
        self.assertFalse(output['accounting_complete'])

    def test_nonbody_barrier_prevents_cross_paragraph_join(self):
        doc = document(unit('a', 'No loss.'), unit('fig', 'Figure.', 'figure_caption'),
                       unit('b', 'No rescue.'))
        job = build(doc)['jobs'][0]
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 0, 1)]), row(job, 1))
        self.assertIn('non_contiguous_source_units', self.reasons(output))

    def test_unscanned_oversize_paragraph_is_not_invisible_to_continuity(self):
        doc = document(unit('a', 'No loss.'), unit('gap', 'Long observation ' * 80),
                       unit('b', 'No rescue.'))
        output = build(doc, primary_cap=50)
        self.assertEqual(len(output['gaps']), 1)
        job = output['jobs'][0]
        self.assertEqual([p['parent_unit_id'] for p in job['primary_units']], ['a', 'b'])
        result = validate(job, row(job, status='has_candidates', spans=[span(job, 0, 1)]), row(job, 1))
        self.assertIn('non_contiguous_span', self.reasons(result))
        self.assertFalse(result['accepted'])

    def test_real_sentence_id_from_another_job_is_not_accepted(self):
        output = build(self.doc, max_paragraphs=1)
        job, foreign = output['jobs'][:2]
        response = row(job, status='has_candidates', spans=[span(foreign, 0), span(job, 1)])
        result = validate(job, response)
        self.assertIn('unknown_sentence_id', self.reasons(result))
        self.assertEqual(len(result['accepted']), 1)

    def test_cross_paragraph_requires_locators(self):
        doc = document(unit('a', 'No loss.', locator=''), unit('b', 'No rescue.'))
        job = build(doc)['jobs'][0]
        output = validate(job, row(job, status='has_candidates', spans=[span(job, 0, 1)]), row(job, 1))
        self.assertIn('unlocatable_cross_paragraph_span', self.reasons(output))

    def test_malformed_payloads_are_total_and_preserve_coverage(self):
        for payload in (None, [], 'not JSON', {}, {'paragraphs': None}, {'paragraphs': {}},
                        {'paragraphs': [None, [], {'paragraph_id': []}]}):
            with self.subTest(payload=payload):
                output = v3.validate_discovery(payload, self.job)
                self.assertEqual(len(output['coverage']), 3)
                self.assertTrue(all(c['status'] == 'unresolved' for c in output['coverage']))
                self.assertFalse(output['accounting_complete'])

    def test_malformed_span_neighbours_and_status_are_isolated(self):
        job = self.job
        bad_spans = [None, {'sentence_ids': []}, {'sentence_ids': [None]},
                     {'sentence_ids': 'not a list'}, {'sentence_ids': [[]]},
                     dict(span(job, 0), quote='model copy')]
        output = validate(job, row(job, status='has_candidates', spans=bad_spans + [span(job, 1)]),
                          row(job, 1), row(job, 2, status=[]))
        self.assertEqual(len(output['accepted']), 1)
        self.assertEqual(len(output['rejected']), len(bad_spans) + 1)
        self.assertEqual(output['coverage'][1]['status'], 'none_found')

    def test_unknown_paragraph_does_not_drop_valid_neighbour(self):
        job = self.job
        output = validate(job, {'paragraph_id': 'foreign', 'status': 'none_found', 'spans': []},
                          row(job, status='has_candidates', spans=[span(job, 1)]), row(job, 1), row(job, 2))
        self.assertEqual(len(output['accepted']), 1)
        self.assertIn('unknown_paragraph_id', self.reasons(output))
        self.assertFalse(output['accounting_complete'])


if __name__ == '__main__':
    unittest.main()
