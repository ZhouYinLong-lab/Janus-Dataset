import tempfile
import unittest
from pathlib import Path
from corpus import locate_quote, parse_source


class CorpusTests(unittest.TestCase):
    def parse(self,xml):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.xml';p.write_text(xml,encoding='utf-8')
            return parse_source(p,'P1')

    def test_body_table_caption_not_conflated(self):
        d=self.parse('<article><body><sec><title>Results</title><p id="p1">No significant <italic>degradation</italic> at 10 μM.</p><table-wrap id="t1"><table><tr><td>No degradation</td></tr></table></table-wrap><fig id="f1"><caption><p>Not detected.</p></caption></fig></sec></body></article>')
        self.assertEqual([u['kind'] for u in d['units']],['body_paragraph','table','figure_caption'])
        self.assertEqual(locate_quote(d['units'],'No significant degradation at 10 µM.')[0]['locator'],'p1')
        self.assertEqual(locate_quote(d['units'],'Not detected.')[0]['kind'],'figure_caption')

    def test_pdf_placeholder_not_fulltext(self):
        d=self.parse('<article><body><sec><title>pdf-only-notice</title></sec></body></article>')
        self.assertEqual(d['status'],'no_structured_body')

    def test_bioc_roles(self):
        d=self.parse('<collection><document><passage><infon key="section_type">RESULTS</infon><offset>10</offset><text>No effect.</text></passage><passage><infon key="section_type">TABLE</infon><text>A zero</text></passage></document></collection>')
        self.assertEqual([u['kind'] for u in d['units']],['body_paragraph','table'])

    def test_ids_deterministic(self):
        xml='<article><body><p>Data.</p></body></article>'
        self.assertEqual(self.parse(xml)['units'],self.parse(xml)['units'])

    def test_abstract_and_references_excluded(self):
        d=self.parse('<article><front><abstract><p>no effect</p></abstract></front><body><p>Results.</p><ref-list><p>Other study.</p></ref-list></body></article>')
        self.assertEqual(len(d['units']),1)

    def test_entities_rejected(self):
        with self.assertRaises(ValueError):self.parse('<!DOCTYPE a [<!ENTITY x "bad">]><article/>')

    def test_quote_not_present(self):
        self.assertEqual(locate_quote(self.parse('<article><body><p>Data.</p></body></article>')['units'],'invented'),[])


if __name__=='__main__':unittest.main()
