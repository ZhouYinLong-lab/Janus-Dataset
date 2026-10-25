from copy import deepcopy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from api import RequestFailure
from batch_budget import create, status
from batch_contract import discovery, enrichment
from batch_export import export
from batch_plan import estimate, prepare, request_for
from batch_run import run
from contract import FIELDS
from corpus import HERE, read, save
from test_runner import config


class Client:
    def __init__(self, fail=None):
        self.calls = 0; self.fail = fail

    def complete(self, request):
        self.calls += 1
        if self.fail and self.calls == 1:
            raise self.fail
        user = json.loads(request['messages'][1]['content'])
        pid = user['paper_id']; unit = user['primary_units'][0]
        quote = unit['text']
        if 'candidates' not in user:
            has_negative = 'did not' in quote
            payload = {'paper_id': pid, 'candidates': [{
                'candidate_id': 'C1', 'unit_id': unit['unit_id'], 'quote': quote,
                'compound_mentions': ['Compound X'], 'condition_mentions': ['Z'],
                'category': 'conditional_loss', 'notes': []}] if has_negative else [],
                'coverage_notes': [], 'no_candidate_reason': None if has_negative else 'Methods only.'}
        else:
            items = []
            for c in user['candidates']:
                fields = dict.fromkeys(FIELDS)
                fields.update(compound='Compound X', target='protein T', perturbation='Z',
                              result_text='No degradation with Z')
                record = {'domain': 'molecular_glue', 'negative_type': 'conditional_loss',
                          'experimental_setting': 'special_condition', 'directness': 'explicit',
                          'fields': fields, 'qualifiers': [], 'evidence': [
                              {'field': f, 'unit_id': c['unit_id'], 'quote': c['quote']}
                              for f in ['compound', 'target', 'perturbation', 'result_text']]}
                items.append({'candidate_id': c['candidate_id'], 'record': record})
            payload = {'paper_id': pid, 'items': items, 'unresolved': [], 'coverage_notes': []}
        return {'model': 'fixture-only', 'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(payload)}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 80, 'total_tokens': 180}}


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.work = self.root / 'work'
        self.ledger = self.root / 'budget.json'; self.cfg = config()
        create(self.ledger, 40, 5_000_000, 'Synthetic fixture only')

    def prepare(self, negative=True, empty=False, bad=False):
        items = []
        for i in range(2 if empty else 1):
            source = self.root / f'source{i}.xml'
            quote = ('Compound X did not degrade protein T after cotreatment with Z.'
                     if negative and i == 0 else 'Cells were maintained in RPMI medium.')
            source.write_text('<article><body><sec><title>Results</title><p id="p1">'
                              + quote + '</p></sec></body></article>', encoding='utf-8')
            items.append({'paper_id': f'P{i}', 'path': str(source), 'doi': f'10.fixture/{i}', 'title': 'Fixture'})
        if bad:
            source = self.root / 'bad.xml'; source.write_text('not XML', encoding='utf-8')
            items.append({'paper_id': 'BAD', 'path': str(source), 'title': 'Invalid fixture'})
        manifest = self.root / 'input.json'; save(manifest, items)
        return prepare(self.work, custom=manifest, limit=10)

    def execute(self, client=None, **kwargs):
        return run(self.work, self.cfg, self.ledger, live=True, client=client or Client(), **kwargs)

    def test_full_batch_and_csv_resume_no_duplicate_charge(self):
        self.prepare(empty=True); c = Client()
        result = self.execute(c)
        self.assertEqual(c.calls, 3)
        self.assertEqual(result['unique_records'], 1)
        self.assertEqual(result['failed_tasks'], 0)
        self.assertTrue((self.work / 'exports/records.csv').exists())
        self.execute(c); export(self.work)
        self.assertEqual(c.calls, 3)
        self.assertEqual(status(self.ledger)['requests_reserved'], 3)
        self.assertTrue(all(p['status'] == 'processed_not_semantically_reviewed' for p in result['papers']))

    def test_no_live_no_request(self):
        self.prepare(); c = Client()
        with self.assertRaises(ValueError): run(self.work, self.cfg, self.ledger, client=c)
        self.assertEqual(c.calls, 0)

    def test_bad_paper_does_not_block_readable_paper(self):
        self.prepare(bad=True); result = self.execute()
        self.assertEqual(result['unique_records'], 1)
        bad = next(p for p in result['papers'] if p['paper_id'] == 'BAD')
        self.assertEqual(bad['status'], 'input_gap')

    def test_unknown_failure_blocks_dependency_not_other_paper(self):
        self.prepare(empty=True); c = Client(RequestFailure('network_outcome_unknown', ambiguous=True))
        result = self.execute(c)
        self.assertEqual(c.calls, 2)
        self.assertEqual(result['failed_tasks'], 1)
        self.assertEqual(status(self.ledger)['attempts_without_usage'], 1)
        self.execute(c)
        self.assertEqual(c.calls, 2)

    def test_auth_failure_stops_all_sends_and_future_runs(self):
        self.prepare(empty=True); c = Client(RequestFailure('http_error', 401))
        self.execute(c); self.execute(c)
        self.assertEqual(c.calls, 1)
        self.assertEqual(status(self.ledger)['global_stop'], 'provider_http_401')

    def test_resume_enrichment_without_redo_discovery(self):
        self.prepare(); c = Client()
        first = self.execute(c, max_new_requests=1)
        self.assertEqual(c.calls, 1)
        self.assertEqual(first['unique_records'], 0)
        self.assertEqual(first['unresolved_candidates'], 1)
        self.execute(c)
        self.assertEqual(c.calls, 2)

    def test_changed_model_blocks_resume(self):
        self.prepare(); self.execute(max_new_requests=1)
        self.cfg['model'] = 'different'
        c = Client()
        with self.assertRaises(ValueError): self.execute(c)
        self.assertEqual(c.calls, 0)

    def test_saved_result_change_blocks_before_new_request(self):
        self.prepare(); self.execute(max_new_requests=1)
        s = read(self.work / 'batch_state.json'); entry = next(iter(s['tasks'].values()))
        save(self.work / entry['result_path'], {'accepted': []})
        c = Client()
        with self.assertRaises(ValueError): self.execute(c)
        self.assertEqual(c.calls, 0)

    def test_empty_discovery_skips_enrichment(self):
        self.prepare(negative=False); c = Client(); r = self.execute(c)
        self.assertEqual(c.calls, 1)
        self.assertEqual(r['job_status'], {'processed_no_candidates_found': 1})

    def test_all_quarantined_not_reported_no_negatives(self):
        self.prepare()
        class BadQuote(Client):
            def complete(self, request):
                e = super().complete(request); p = json.loads(e['choices'][0]['message']['content'])
                p['candidates'][0]['quote'] = 'Invented result did not exist.'
                e['choices'][0]['message']['content'] = json.dumps(p); return e
        c = BadQuote(); r = self.execute(c)
        self.assertEqual(c.calls, 1)
        self.assertEqual(r['job_status'], {'processed_with_issues': 1})
        self.assertEqual(r['quarantined_entries'], 1)

    def test_discovery_partial_bad_row_preserves_good(self):
        m = self.prepare(); job = read(self.work / f'jobs/{m["job_ids"][0]}.json')
        e = Client().complete(request_for(self.work, job, 'discovery', self.cfg))
        p = json.loads(e['choices'][0]['message']['content'])
        bad = deepcopy(p['candidates'][0]); bad['candidate_id'] = 'C2'; bad['category'] = []
        p['candidates'].append(bad)
        r = discovery(p, job)
        self.assertEqual(len(r['accepted']), 1); self.assertEqual(len(r['rejected']), 1)

    def test_duplicate_discovery_ids_quarantined(self):
        m = self.prepare(); job = read(self.work / f'jobs/{m["job_ids"][0]}.json')
        e = Client().complete(request_for(self.work, job, 'discovery', self.cfg))
        p = json.loads(e['choices'][0]['message']['content']); p['candidates'] *= 2
        r = discovery(p, job)
        self.assertEqual(len(r['accepted']), 0); self.assertEqual(len(r['rejected']), 2)

    def test_enrichment_missing_item_retains_other_items(self):
        m = self.prepare(); job = read(self.work / f'jobs/{m["job_ids"][0]}.json')
        req = request_for(self.work, job, 'discovery', self.cfg)
        e = Client().complete(req); cs = json.loads(e['choices'][0]['message']['content'])['candidates']
        cs.append(dict(cs[0], candidate_id='C2'))
        e = Client().complete(request_for(self.work, job, 'enrichment', self.cfg, cs, 'hash'))
        p = json.loads(e['choices'][0]['message']['content']); p['items'] = p['items'][:1]
        r = enrichment(p, job, cs)
        self.assertEqual(len(r['accepted']), 1); self.assertEqual(r['missing_candidate_ids'], ['C2'])

    def test_estimate_offline_and_no_reference_answers(self):
        m = self.prepare(); e = estimate(self.work, self.cfg)
        self.assertFalse(e['credentials_read']); self.assertEqual(e['discovery_requests'], 1)
        self.assertFalse((self.work / 'batch_state.json').exists())
        job = read(self.work / f'jobs/{m["job_ids"][0]}.json')
        req = request_for(self.work, job, 'discovery', self.cfg)
        user = json.loads(req['messages'][1]['content'])
        self.assertNotIn('context_units', user); self.assertNotIn('source_path', user)

    def test_crashed_saved_response_recovered_without_new_call(self):
        self.prepare(); c = Client(); self.execute(c, max_new_requests=1)
        s = read(self.work / 'batch_state.json'); entry = next(iter(s['tasks'].values()))
        entry['status'] = 'in_flight'; entry.pop('result_path'); entry.pop('result_sha256')
        save(self.work / 'batch_state.json', s)
        self.execute(c)
        self.assertEqual(c.calls, 2)

    def test_budget_cap_shared_across_two_workspaces(self):
        self.prepare(); c = Client(); self.execute(c)
        first = status(self.ledger)['requests_reserved']
        other = self.root / 'other'; prepare(other, custom=self.root / 'input.json', limit=10)
        run(other, self.cfg, self.ledger, live=True, client=c)
        self.assertEqual(c.calls, first)

    def test_source_change_blocks_send(self):
        self.prepare(); (self.root / 'source0.xml').write_text('changed', encoding='utf-8')
        c = Client()
        with self.assertRaises(ValueError): self.execute(c)
        self.assertEqual(c.calls, 0)

    def test_one_command_cli_http_and_repeat_resume(self):
        self.prepare(empty=True)
        # Prepare a second workspace via the actual CLI, not the injected test client.
        work = self.root / 'cli'; client = Client()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                body = json.dumps(client.complete(request)).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        cfg = dict(self.cfg, base_url=f'http://127.0.0.1:{server.server_port}/v1')
        save(self.root / 'config.json', cfg)
        env = dict(os.environ); env[cfg['api_key_env']] = 'synthetic-local-only'
        command = [os.sys.executable, str(HERE / 'batch.py'), 'start',
                   '--workspace', str(work), '--manifest', str(self.root / 'input.json'),
                   '--limit', '10', '--config', str(self.root / 'config.json'),
                   '--ledger', str(self.ledger), '--live']
        for _ in range(2):
            r = subprocess.run(command, capture_output=True, env=env, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr.decode())
        self.assertEqual(client.calls, 3)
        summary = read(work / 'exports/summary.json')
        self.assertEqual(summary['unique_records'], 1)
        self.assertEqual(summary['workspace_requests'], 3)

    def test_response_file_before_hash_save_recovered_offline(self):
        self.prepare(); c = Client(); self.execute(c, max_new_requests=1)
        s = read(self.work / 'batch_state.json'); entry = next(iter(s['tasks'].values()))
        entry['status'] = 'in_flight'; entry.pop('response_sha256')
        entry.pop('result_path'); entry.pop('result_sha256')
        save(self.work / 'batch_state.json', s)
        result = self.execute(c)
        self.assertEqual(c.calls, 2)
        self.assertEqual(result['unique_records'], 1)

    def test_local_processing_error_revalidated_without_regeneration(self):
        self.prepare(); c = Client(); self.execute(c, max_new_requests=1)
        s = read(self.work / 'batch_state.json'); entry = next(iter(s['tasks'].values()))
        entry['status'] = 'local_processing_error'; entry.pop('result_path'); entry.pop('result_sha256')
        save(self.work / 'batch_state.json', s)
        result = self.execute(c)
        self.assertEqual(c.calls, 2)
        self.assertEqual(result['unique_records'], 1)

    def test_ledger_known_http_failure_recovers_retry_eligibility(self):
        self.prepare(); c = Client(RequestFailure('http_error', 500)); self.execute(c)
        s = read(self.work / 'batch_state.json'); entry = next(iter(s['tasks'].values()))
        entry['status'] = 'in_flight'; entry.pop('http_status')
        save(self.work / 'batch_state.json', s)
        c.fail = None
        result = self.execute(c, retry_known=True)
        self.assertEqual(c.calls, 3)
        self.assertEqual(result['unique_records'], 1)

    def test_all_inputs_invalid_cli_nonzero_without_generation(self):
        source = self.root / 'bad.xml'; source.write_text('bad', encoding='utf-8')
        save(self.root / 'input.json', [{'paper_id': 'BAD', 'path': str(source)}])
        save(self.root / 'config.json', self.cfg)
        r = subprocess.run([os.sys.executable, str(HERE / 'batch.py'), 'start',
            '--workspace', str(self.work), '--manifest', str(self.root / 'input.json'),
            '--config', str(self.root / 'config.json'), '--ledger', str(self.ledger), '--live'],
            capture_output=True, timeout=20)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(status(self.ledger)['requests_reserved'], 0)

    def test_workspace_config_cap_and_global_cap_both_apply(self):
        self.prepare(); c = Client(); self.cfg['max_requests'] = 1
        first = self.execute(c)
        self.assertEqual(c.calls, 1)
        self.assertEqual(first['stop_reason'], 'workspace_request_budget')
        self.cfg['max_requests'] = 3
        self.execute(c)
        self.assertEqual(c.calls, 2)
