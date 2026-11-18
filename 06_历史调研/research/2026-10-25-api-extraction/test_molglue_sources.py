"""Offline tests for source identity, provenance, access rules and input gaps.

Run: python -m unittest discover -s research/2026-10-25-api-extraction
     -p test_molglue_sources.py -v
"""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from corpus import ROOT, parse_source, read, save, sha
import molglue_sources as sources
from molglue_sources import fetch_sources, inventory, normalize_doi, normalize_url
from source_formats import parse_document

XML = b'<article><body><sec><title>Results</title><p id="p1">No significant decrease at 10 uM.</p></sec></body></article>'
DOI_URL = 'https://doi.org/10.1234/example'


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.export = self.root / 'MolGlueDB_full.csv'
        self.out = self.root / 'inventory'
        self.legacy = self.root / 'legacy' / 'source_manifest.json'
        save(self.legacy, [])

    def write_export(self, urls=None):
        urls = urls if urls is not None else [DOI_URL]
        with self.export.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.DictWriter(handle, fieldnames=['DATAID', 'Name', 'SourceAddress_Website'])
            writer.writeheader()
            for index, url in enumerate(urls):
                writer.writerow({'DATAID': str(index // 2 + 1), 'Name': 'compound',
                                 'SourceAddress_Website': url})

    def make_inventory(self, urls=None):
        self.write_export(urls)
        return inventory(self.export, self.out, self.legacy)

    def papers(self):
        return read(self.out / 'papers.json')

    def fake_get(self, url):
        if '/search?' in url:
            return json.dumps({'resultList': {'result': [self.search_record]}}).encode(), url, 'application/json'
        if '/fullTextXML' in url:
            return XML, url, 'application/xml'
        raise AssertionError('Unexpected network request: ' + url)

    def test_normalization_doi_url_and_tracking(self):
        self.assertEqual(normalize_doi(' DOI:10.1234/AbC '), '10.1234/abc')
        self.assertEqual(normalize_url('https://DX.DOI.ORG/10.1234/AbC '), 'https://doi.org/10.1234/abc')
        self.assertEqual(normalize_url('https://doi.org/10.1234/AbC?utm_source=x#top'),
                         'https://doi.org/10.1234/abc')
        self.assertEqual(normalize_url('https://Example.org/article/?b=2&utm_source=x&a=1#top'),
                         'https://example.org/article?a=1&b=2')
        self.assertIsNone(normalize_url('file:///private.xml'))
        self.assertIsNone(normalize_url('https://user:password@example.org/'))

    def test_dedup_keeps_every_entry_and_original_version(self):
        summary = self.make_inventory([DOI_URL, DOI_URL.upper() + ' ', '', 'https://example.org/a#fragment'])
        papers = self.papers()
        self.assertEqual(summary['source_count'], 2)
        self.assertEqual(summary['associated_rows'], 3)
        self.assertEqual(len(summary['unresolved_source_rows']), 1)
        self.assertEqual(summary['export_sha256'], sha(self.export))
        paper = next(p for p in papers if p['doi'])
        self.assertEqual(paper['publication_kind'], 'paper')
        self.assertEqual(next(p for p in papers if not p['doi'])['publication_kind'], 'corporate_material')
        self.assertIsNone(paper['source_format'])
        self.assertEqual(paper['entry_count'], 2)
        self.assertEqual(len(paper['data_ids']), 1)
        self.assertNotEqual(paper['entries'][0]['row_sha256'], paper['entries'][1]['row_sha256'])
        self.assertEqual(paper['entries'][1]['raw_source'], DOI_URL.upper() + ' ')
        self.assertIsNone(paper['path'])
        self.assertEqual(summary['reported241']['reported_minus_export_source_count'], 239)
        self.assertFalse(summary['reported241']['set_difference_verified'])
        with (self.out / 'source_inventory.csv').open(encoding='utf-8-sig', newline='') as handle:
            csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 2)
            self.assertEqual({r['publication_kind'] for r in csv_rows}, {'paper', 'corporate_material'})
            self.assertTrue(all('source_format' in r for r in csv_rows))

    def test_source_id_stable_across_order_and_legacy_identity(self):
        source = self.legacy.parent / 'sources' / 'B212_PMC123.xml'
        source.parent.mkdir()
        source.write_bytes(XML)
        save(self.legacy, [{'paper_id': 'B212', 'doi': '10.1234/example', 'title': 'Example',
                            'sha256': sha(source), 'url': DOI_URL}])
        summary = self.make_inventory([DOI_URL, 'https://example.org/a'])
        before = {p['canonical_identity']: p['source_id'] for p in self.papers()}
        paper = next(p for p in self.papers() if p['doi'])
        self.assertEqual(paper['paper_id'], 'B212')
        self.assertEqual(paper['legacy_paper_id'], 'B212')
        self.assertEqual(paper['path'], str(source.resolve()))
        self.assertEqual(paper['source_format'], paper['source_kind'])
        self.assertEqual(paper['source_format'], 'xml')
        self.assertTrue(paper['sources'][0]['legacy_hash_matches'])
        self.assertEqual(summary['legacy_reused_papers'], 1)
        self.write_export(['https://example.org/a', DOI_URL.upper()])
        inventory(self.export, self.root / 'other', self.root / 'missing_manifest.json')
        after = {p['canonical_identity']: p['source_id'] for p in read(self.root / 'other' / 'papers.json')}
        self.assertEqual(before, after)

    def test_all_legacy_versions_retained_xml_preferred(self):
        files = self.legacy.parent / 'sources'
        files.mkdir()
        (files / 'B212_test.pdf').write_bytes(b'%PDF-placeholder')
        (files / 'B212_test.xml').write_bytes(XML)
        save(self.legacy, [{'paper_id': 'B212', 'doi': '10.1234/example', 'sha256': 'bad'}])
        self.make_inventory()
        paper = self.papers()[0]
        self.assertEqual(paper['source_kind'], 'xml')
        self.assertEqual(len(paper['sources']), 2)
        self.assertFalse(paper['sources'][0]['legacy_hash_matches'])

    def test_existing_inventory_not_overwritten(self):
        self.make_inventory()
        digest = sha(self.out / 'papers.json')
        with self.assertRaises(FileExistsError):
            inventory(self.export, self.out, self.legacy)
        self.assertEqual(digest, sha(self.out / 'papers.json'))

    def test_reject_wrong_export_schema(self):
        self.export.write_text('id,url\n1,x\n')
        with self.assertRaises(ValueError):
            inventory(self.export, self.out, self.legacy)
        self.assertFalse(self.out.exists())

    def test_fetch_limit_zero_and_validation(self):
        self.make_inventory()
        with patch.object(sources.PublicClient, 'get', side_effect=AssertionError('network')):
            self.assertEqual(fetch_sources(self.out, 0)['last_fetch']['processed'], 0)
        for value in (-1, True, 1.2):
            with self.assertRaises(ValueError):
                fetch_sources(self.out, value)

    def test_fetch_xml_preferred_and_all_rows_retained(self):
        self.make_inventory([DOI_URL, 'https://example.org/missing'])
        self.search_record = {'doi': '10.1234/example', 'pmcid': 'PMC123',
                              'isOpenAccess': 'Y', 'title': 'Title',
                              'fullTextUrlList': {'fullTextUrl': [
                                  {'url': 'https://publisher.example/a.pdf',
                                   'documentStyle': 'pdf', 'availabilityCode': 'OA'}]}}
        with patch.object(sources.PublicClient, 'get', side_effect=self.fake_get) as request:
            summary = fetch_sources(self.out, 1)
        paper = self.papers()[0]
        self.assertEqual(summary['last_fetch']['processed'], 1)
        self.assertEqual(len(self.papers()), 2)
        self.assertEqual(paper['source_kind'], 'xml')
        self.assertIn('local', Path(paper['path']).parts)
        self.assertEqual(paper['source_format'], 'xml')
        self.assertEqual(paper['source_sha256'], sha(paper['path']))
        self.assertEqual(request.call_count, 2)
        with patch.object(sources.PublicClient, 'get', side_effect=AssertionError('network')):
            # Only this paper selected; use a single-item list to test resume.
            save(self.out / 'papers.json', [paper])
            self.assertEqual(fetch_sources(self.out)['last_fetch']['processed'], 0)

    def test_no_doi_search_false_match(self):
        self.make_inventory()
        self.search_record = {'doi': '10.9999/other', 'pmcid': 'PMC123', 'isOpenAccess': 'Y'}

        def get(url):
            if '/search?' in url:
                return self.fake_get(url)
            return b'<html><article><p>Purchase access</p></article></html>', url, 'text/html'

        with patch.object(sources.PublicClient, 'get', side_effect=get) as request:
            fetch_sources(self.out)
        paper = self.papers()[0]
        self.assertEqual(request.call_count, 2)
        self.assertIsNone(paper['path'])
        self.assertEqual(paper['availability_reason'], 'publisher_identity_unconfirmed')

    def test_access_failure_saved_and_never_automatically_retried(self):
        self.make_inventory()
        error = HTTPError(DOI_URL, 403, 'Forbidden', {}, None)
        with patch.object(sources.PublicClient, 'get', side_effect=error):
            fetch_sources(self.out)
        paper = self.papers()[0]
        self.assertIsNone(paper['path'])
        self.assertTrue(all(a['status'] == 'access_denied' for a in paper['fetch_attempts']))
        with patch.object(sources.PublicClient, 'get', side_effect=AssertionError('retry')):
            self.assertEqual(fetch_sources(self.out)['last_fetch']['processed'], 0)

    def test_fetch_progress_flushed_after_persist_without_source_content(self):
        self.make_inventory()
        progress = []

        def capture(value, **kwargs):
            persisted = self.papers()[0]
            self.assertEqual(set(value), {'paper_id', 'availability', 'processed'})
            self.assertEqual(value['paper_id'], persisted['paper_id'])
            self.assertEqual(value['availability'], persisted['availability'])
            self.assertEqual(value['processed'], 1)
            self.assertEqual(kwargs, {'flush': True})
            progress.append(value)

        with patch.object(sources.PublicClient, 'get', side_effect=URLError('offline')), \
                patch('builtins.print', side_effect=capture):
            fetch_sources(self.out)
        self.assertEqual(len(progress), 1)

    def test_attempt_is_persisted_before_network_and_interrupt_not_retried(self):
        self.make_inventory()

        def interrupt(url):
            persisted = self.papers()[0]['fetch_attempts']
            self.assertEqual(persisted[-1]['status'], 'in_flight')
            raise KeyboardInterrupt()

        with patch.object(sources.PublicClient, 'get', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                fetch_sources(self.out)
        with patch.object(sources.PublicClient, 'get', side_effect=AssertionError('retry')):
            self.assertEqual(fetch_sources(self.out)['last_fetch']['processed'], 0)

    def test_official_open_html_precedes_europepmc_pdf(self):
        self.make_inventory()
        self.search_record = {'doi': '10.1234/example', 'isOpenAccess': 'N',
                              'fullTextUrlList': {'fullTextUrl': [
                                  {'url': 'https://publisher.example/a.pdf',
                                   'documentStyle': 'pdf', 'availabilityCode': 'OA'}]}}
        html = (b'<html><head><meta name="citation_doi" content="10.1234/example"></head>'
                b'<article><a href="https://creativecommons.org/licenses/by/4.0/">License</a>'
                b'<h2>Results</h2><p>No effect.</p></article></html>')

        def get(url):
            if '/search?' in url:
                return self.fake_get(url)
            if url == DOI_URL:
                return html, 'https://publisher.example/a', 'text/html'
            raise AssertionError('PDF should not be fetched before available HTML')

        with patch.object(sources.PublicClient, 'get', side_effect=get):
            fetch_sources(self.out)
        self.assertEqual(self.papers()[0]['source_kind'], 'html')

    def test_paywall_html_cannot_masquerade_as_xml(self):
        self.make_inventory()
        self.search_record = {'doi': '10.1234/example', 'pmcid': 'PMC123', 'isOpenAccess': 'Y'}

        def get(url):
            if '/search?' in url:
                return self.fake_get(url)
            return b'<html>Please sign in</html>', url, 'text/html'

        with patch.object(sources.PublicClient, 'get', side_effect=get):
            fetch_sources(self.out)
        paper = self.papers()[0]
        self.assertIsNone(paper['path'])
        self.assertEqual(paper['fetch_attempts'][1]['status'], 'invalid_or_unparseable_document')

    def test_publisher_xml_preferred_over_html(self):
        self.make_inventory(['https://publisher.example/a'])
        html = (b'<html><meta name="citation_open_access" content="true">'
                b'<meta name="citation_xml_url" content="/a.xml">'
                b'<article><h2>Results</h2><p>Result.</p></article></html>')

        def get(url):
            return (XML, url, 'application/xml') if url.endswith('.xml') else (html, url, 'text/html')

        with patch.object(sources.PublicClient, 'get', side_effect=get):
            fetch_sources(self.out)
        self.assertEqual(self.papers()[0]['source_kind'], 'xml')

    def test_timeout_and_bad_search_json_recorded(self):
        self.make_inventory()
        with patch.object(sources.PublicClient, 'get', side_effect=[
                (b'not json', DOI_URL, 'application/json'), URLError('timed out')]):
            fetch_sources(self.out)
        self.assertEqual([a['status'] for a in self.papers()[0]['fetch_attempts']],
                         ['invalid_metadata', 'request_failed'])

    def test_downloaded_parse_failure_is_retained_as_source_gap(self):
        self.make_inventory()
        self.search_record = {'doi': '10.1234/example', 'pmcid': 'PMC123', 'isOpenAccess': 'Y'}

        def get(url):
            if '/search?' in url:
                return self.fake_get(url)
            if '/fullTextXML' in url:
                return b'<article><body>broken', url, 'application/xml'
            raise URLError('offline')

        with patch.object(sources.PublicClient, 'get', side_effect=get):
            fetch_sources(self.out)
        paper = self.papers()[0]
        self.assertIsNone(paper['path'])
        self.assertEqual(paper['availability'], 'input_gap')
        self.assertEqual(paper['sources'][0]['parse_status'], 'parse_error')
        self.assertEqual(sha(paper['sources'][0]['path']), paper['sources'][0]['source_sha256'])

    def test_client_rate_limit_timeout_and_size_bound(self):
        class Response:
            headers = {'Content-Type': 'application/xml'}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def geturl(self):
                return DOI_URL

            def read(self, cap):
                self.cap = cap
                return XML

        response = Response()
        with patch.object(sources, 'urlopen', return_value=response) as opening, \
                patch.object(sources.time, 'monotonic', side_effect=[0, .1, .2]), \
                patch.object(sources.time, 'sleep') as sleeping:
            client = sources.PublicClient()
            client.get(DOI_URL)
            client.get(DOI_URL)
        self.assertEqual(opening.call_args.kwargs['timeout'], sources.TIMEOUT)
        self.assertEqual(response.cap, sources.MAX_BYTES + 1)
        sleeping.assert_called_once()
        self.assertAlmostEqual(sleeping.call_args.args[0], .9)

    def test_real_export_regression_when_available(self):
        export = ROOT / 'research/2026-10-26-mg2act-audit/local/source_mapping/MolGlueDB_full.csv'
        if not export.is_file():
            self.skipTest('Local raw export not installed')
        summary = inventory(export, self.out)
        self.assertEqual(summary['export_rows'], 1840)
        self.assertEqual(summary['source_count'], 193)
        self.assertEqual(summary['doi_sources'], 192)
        self.assertEqual(summary['url_only_sources'], 1)
        self.assertEqual(sum(p['publication_kind'] == 'paper' for p in self.papers()), 192)
        self.assertEqual(sum(p['publication_kind'] == 'corporate_material' for p in self.papers()), 1)
        self.assertEqual(summary['legacy_reused_papers'], 23)
        self.assertEqual(summary['reported241']['reported_minus_export_source_count'], 48)
        self.assertTrue(summary['current193']['matches_reference'])
        self.assertEqual(sum(p['entry_count'] for p in self.papers()), 1840)
        self.assertTrue(next(p for p in self.papers() if p['paper_id'] == 'B212')['path'])


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, data):
        path = self.root / name
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        return path

    def test_xml_is_exact_legacy_parser_result(self):
        path = self.write('article.xml', XML)
        self.assertEqual(parse_document(path, 'B212'), parse_source(path, 'B212'))
        self.assertIsInstance(parse_document(path, 'B212')['parser_version'], int)

    def test_xml_entities_rejected(self):
        path = self.write('bad.xml', '<!DOCTYPE a [<!ENTITY x "bad">]><article/>')
        with self.assertRaises(ValueError):
            parse_document(path, 'P1')

    def test_html_body_tables_captions_and_sections(self):
        path = self.write('article.html', '''<html><nav><p>Menu</p></nav><article>
          <section class="abstract"><p>Abstract negative.</p></section>
          <h2>Results</h2><p id="p1">No <b>significant</b> decrease.</p>
          <table id="t1"><caption>Table 1</caption><tr><td>0.1</td></tr></table>
          <figure><figcaption><p>Not detected.</p></figcaption></figure>
          <section id="references"><p>Unrelated reference.</p></section>
          <h2>Methods</h2><p>24 hours.</p><footer><p>Copyright</p></footer>
          </article></html>''')
        doc = parse_document(path, 'P1')
        self.assertEqual([u['kind'] for u in doc['units']],
                         ['body_paragraph', 'table', 'figure_caption', 'body_paragraph'])
        self.assertEqual([u['section'] for u in doc['units']], ['Results'] * 3 + ['Methods'])
        self.assertEqual(doc['units'][0]['text'], 'No significant decrease.')
        self.assertEqual(doc['units'][2]['text'], 'Not detected.')
        self.assertEqual(doc['source_sha256'], sha(path))
        self.assertEqual(doc['units'], parse_document(path, 'P1')['units'])
        self.assertIn('completeness unverified', doc['coverage'])

    def test_html_heading_only_abstract_and_references_excluded(self):
        path = self.write('headings.html', '<article><h2>Abstract</h2><p>No effect.</p>'
                          '<h2>Results</h2><p>Result.</p><h2>References</h2><p>Citation.</p></article>')
        self.assertEqual([u['text'] for u in parse_document(path, 'P1')['units']], ['Result.'])

    def test_html_publisher_caption_classes_not_prose(self):
        path = self.write('captions.html', '<article><h2>Results</h2><p>Result.</p>'
                          '<div class="figure-caption"><p>Figure 1. No degradation.</p></div></article>')
        doc = parse_document(path, 'P1')
        self.assertEqual([u['kind'] for u in doc['units']], ['body_paragraph', 'figure_caption'])

    def test_html_navigation_only_is_input_gap(self):
        for name, html in [('no_container', '<html><p>Login.</p></html>'),
                           ('empty_main', '<main><nav><p>Login.</p></nav></main>')]:
            doc = parse_document(self.write(name + '.html', html), 'P1')
            self.assertEqual(doc['status'], 'input_gap')
            self.assertEqual(doc['units'], [])

    def test_snapshot_round_trip_and_hash_mismatch(self):
        source = self.write('article.xml', XML)
        doc = parse_document(source, 'P1')
        snapshot = self.root / 'document.json'
        save(snapshot, doc)
        loaded = parse_document(snapshot, 'P1')
        self.assertEqual(loaded['units'], doc['units'])
        self.assertEqual(loaded['source_sha256'], doc['source_sha256'])
        self.assertEqual(loaded['snapshot_sha256'], sha(snapshot))
        source.write_bytes(XML + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            parse_document(snapshot, 'P1')

    def test_snapshot_missing_source_identity_and_duplicate_units(self):
        source = self.write('article.xml', XML)
        doc = parse_document(source, 'P1')
        path = self.root / 'snapshot.json'
        save(path, doc)
        with self.assertRaises(ValueError):
            parse_document(path, 'WRONG')
        doc['units'].append(dict(doc['units'][0]))
        save(path, doc)
        with self.assertRaisesRegex(ValueError, 'unit identity'):
            parse_document(path, 'P1')
        source.unlink()
        with self.assertRaisesRegex(ValueError, 'source missing'):
            parse_document(path, 'P1')

    def test_snapshot_relative_source(self):
        source = self.write('article.xml', XML)
        doc = parse_document(source, 'P1')
        doc['source_path'] = 'article.xml'
        path = self.root / 'snapshot.json'
        save(path, doc)
        self.assertEqual(parse_document(path, 'P1')['source_path'], str(source.resolve()))

    def pdf(self, name, columns=False, scan=False, heading=True):
        import fitz
        path = self.root / name
        with fitz.open() as pdf:
            page = pdf.new_page()
            if not scan:
                if heading:
                    page.insert_text((50, 70), 'Results')
                if columns:
                    for x in (50, 320):
                        page.insert_text((x, 110), 'No significant decrease.\nAt 10 uM for 24 h.\nThe target was retained.')
                else:
                    page.insert_text((50, 110), 'No significant decrease at 10 uM after 24 hours of treatment.')
                    page.insert_text((50, 180), 'References')
                    page.insert_text((50, 210), 'Unrelated reference should be excluded from the body.')
            pdf.save(path)
        return path

    def test_pdf_single_column_named_body_with_page_locator(self):
        path = self.pdf('body.pdf')
        doc = parse_document(path, 'P1')
        self.assertEqual(doc['status'], 'readable_partial')
        self.assertEqual(len(doc['units']), 1)
        self.assertEqual(doc['units'][0]['section'], 'Results')
        self.assertEqual(doc['units'][0]['page'], 1)
        self.assertIn('pdf:page:1:', doc['units'][0]['locator'])
        self.assertIn('Partial PDF', doc['coverage'])

    def test_pdf_scan_columns_and_no_confirmed_section_are_gaps(self):
        for kwargs in ({'scan': True}, {'columns': True}, {'heading': False}):
            doc = parse_document(self.pdf('gap.pdf', **kwargs), 'P1')
            self.assertEqual(doc['status'], 'input_gap', kwargs)
            self.assertEqual(doc['units'], [], kwargs)
            self.assertTrue(doc['input_gaps'])

    def test_unsupported_document(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            parse_document(self.write('input.txt', 'Unsegmented source.'), 'P1')


if __name__ == '__main__':
    unittest.main()
