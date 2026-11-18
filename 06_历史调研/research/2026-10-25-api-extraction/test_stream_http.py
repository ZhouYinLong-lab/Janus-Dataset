import io
import json
from pathlib import Path
import tempfile
import unittest

from api import RequestFailure, parse_completion
from batch_budget import create, status
from batch_plan import prepare
from batch_run import run
from batch_upgrade import upgrade
from corpus import read, save
from stream_http import assemble
from test_batch import Client
from test_runner import config


def wire(text='{"ok":true}', finish='stop', done=True, usage=True):
    events = [{'id': 'test', 'model': 'fixture', 'choices': [{'index': 0,
               'delta': {'content': p}, 'finish_reason': None}]} for p in [text[:4], text[4:]]]
    events.append({'id': 'test', 'model': 'fixture', 'choices': [
        {'index': 0, 'delta': {}, 'finish_reason': finish}]})
    if usage: events.append({'id': 'test', 'choices': [], 'usage': {'total_tokens': 7}})
    content = ''.join('data: ' + json.dumps(e) + '\r\n\r\n' for e in events)
    if done: content += 'data: [DONE]\r\n\r\n'
    return io.BytesIO(content.encode())


class StreamTests(unittest.TestCase):
    def test_full_stream_reassembles_json_and_usage(self):
        trace = []; e = assemble(wire(), trace)
        self.assertEqual(parse_completion(e), {'ok': True})
        self.assertEqual(e['usage']['total_tokens'], 7)
        self.assertEqual(trace[-1], '[DONE]')

    def test_partial_stream_is_unknown_not_empty(self):
        with self.assertRaises(RequestFailure) as ctx: assemble(wire(done=False), [])
        self.assertTrue(ctx.exception.ambiguous)

    def test_length_finish_not_accepted(self):
        e = assemble(wire(finish='length'), [])
        with self.assertRaises(ValueError): parse_completion(e)

    def test_missing_usage_not_zero(self):
        e = assemble(wire(usage=False), [])
        self.assertIsNone(e['usage'])

    def test_invalid_event_keeps_partial_trace(self):
        trace = []
        with self.assertRaises(RequestFailure): assemble(io.BytesIO(b'data: invalid\n\n'), trace)
        self.assertEqual(trace, ['invalid'])

    def test_unicode_and_comment_keepalive(self):
        e = assemble(io.BytesIO(b': keepalive\n\n' + wire('{"result":"无显著下降"}').read()), [])
        self.assertEqual(parse_completion(e)['result'], '无显著下降')

    def test_upgrade_preserves_unknown_and_paid_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / 's.xml'
            source.write_text('<article><body><p>Compound X did not degrade protein T after cotreatment with Z.</p></body></article>', encoding='utf-8')
            save(root / 'input.json', [{'paper_id': 'P0', 'path': str(source)}])
            w = root / 'work'; prepare(w, custom=root / 'input.json')
            m = read(w / 'manifest.json'); m.pop('transport'); save(w / 'manifest.json', m)
            ledger = root / 'budget.json'; create(ledger, 20, 1_000_000, 'Synthetic fixture')
            c = Client(RequestFailure('network_outcome_unknown', ambiguous=True))
            run(w, config(), ledger, True, client=c)
            tasks_before = read(w / 'batch_state.json')['tasks']
            upgrade(w, config(), 'Test explicit transport upgrade')
            self.assertEqual(read(w / 'batch_state.json')['tasks'], tasks_before)
            run(w, config(), ledger, True, client=c)
            self.assertEqual(c.calls, 1)
            self.assertEqual(status(ledger)['requests_reserved'], 1)
            self.assertTrue((w / 'upgrades/001_manifest_before.json').exists())
