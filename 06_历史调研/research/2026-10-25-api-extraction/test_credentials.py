from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os

from api import HTTPClient
from credentials import load_key


class CredentialTests(unittest.TestCase):
    def parse(self,content):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'.env';p.write_text(content,encoding='utf-8')
            return load_key('JANUS_TEST_KEY',p)

    def test_explicit_file(self):
        self.assertEqual(self.parse('JANUS_TEST_KEY=fixture-secret'),'fixture-secret')

    def test_bom_quotes_comments(self):
        self.assertEqual(self.parse('\ufeff# note\nexport JANUS_TEST_KEY="fixture-secret"\n'),'fixture-secret')

    def test_environment(self):
        with patch.dict(os.environ,{'JANUS_TEST_KEY':'fixture'}):self.assertEqual(load_key('JANUS_TEST_KEY'),'fixture')

    def test_no_shell_expansion(self):
        self.assertEqual(self.parse('JANUS_TEST_KEY=$(fixture)'), '$(fixture)')

    def test_duplicate_assignment_rejected_without_value(self):
        with self.assertRaises(ValueError) as caught:self.parse('JANUS_TEST_KEY=private1\nJANUS_TEST_KEY=private2')
        self.assertNotIn('private',str(caught.exception))

    def test_missing_assignment(self):
        with self.assertRaises(ValueError):self.parse('OTHER=private')

    def test_whitespace_rejected(self):
        with self.assertRaises(ValueError):self.parse('JANUS_TEST_KEY=private extra')

    def test_model_list_only_ids(self):
        client=HTTPClient({'base_url':'https://example.invalid'},'fixture-secret')
        with patch.object(client,'_request',return_value={'data':[{'id':'model-z','owner':'private'}, {'id':'model-a'}]}):
            self.assertEqual(client.models(),['model-a','model-z'])


if __name__=='__main__':unittest.main()
