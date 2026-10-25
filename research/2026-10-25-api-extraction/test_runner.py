from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from api import RequestFailure,check_config,parse_completion
from contract import FIELDS
from corpus import read,save
from export import export,safe_cell
from prepare import prepare
from runner import lock,run,status
from estimate import estimate


def config():
    return {'base_url':'https://example.invalid/v1','model':'fixture-only',
            'api_key_env':'JANUS_TEST_ONLY_KEY','timeout_seconds':3,'max_output_tokens':500,
            'output_token_parameter':'max_tokens','response_format':'json_object',
            'max_requests':3,'max_reserved_tokens':1_000_000}


def completion(job,invalid=False):
    unit=job['primary_units'][0]
    fields={k:None for k in FIELDS}
    fields.update(compound='Compound X',target='GSPT1',result_text='No degradation reported')
    record={'domain':'molecular_glue','negative_type':'no_degradation',
            'experimental_setting':'unperturbed','directness':'explicit','fields':fields,
            'evidence':[{'field':f,'unit_id':unit['unit_id'],'quote':unit['text'][:150]}
                        for f in ['compound','target','result_text']], 'qualifiers':[]}
    if invalid:record['evidence'][0]['quote']='This quote was invented by the fixture.'
    return {'model':'fixture-model','choices':[{'finish_reason':'stop','message':{'content':json.dumps({
        'schema_version':1,'paper_id':job['paper_id'],'records':[record],
        'coverage_notes':[],'no_negative_reason':None})}}],
        'usage':{'prompt_tokens':100,'completion_tokens':80,'total_tokens':180}}


class Client:
    def __init__(self,workspace,invalid=False,failure=None):
        self.workspace=workspace;self.calls=0;self.invalid=invalid;self.failure=failure
    def complete(self,request):
        self.calls+=1
        if self.failure:raise self.failure
        evidence=json.loads(request['messages'][1]['content'])
        jobs=[read(p) for p in (self.workspace/'jobs').glob('*.json')]
        job=next(j for j in jobs if j['primary_chunk_index']==evidence['primary_chunk_index'])
        return completion(job,self.invalid)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.workspace=self.root/'work'
    def prepare(self,long=False):
        source=self.root/'paper.xml'
        p='<p>Compound X did not degrade GSPT1 in this molecular glue experiment.</p>'
        source.write_text('<article><body>'+p*(400 if long else 1)+'</body></article>',encoding='utf-8')
        manifest=self.root/'papers.json'
        save(manifest,[{'paper_id':'P1','path':str(source),'doi':'10.fixture/test','title':'Fixture'}])
        return prepare(self.workspace,custom=manifest,limit=1)

    def test_no_live_no_request(self):
        self.prepare();c=Client(self.workspace)
        with self.assertRaises(ValueError):run(self.workspace,config(),client=c)
        self.assertEqual(c.calls,0)

    def test_unset_secret_no_request(self):
        self.prepare()
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):run(self.workspace,config(),live=True)
        self.assertFalse((self.workspace/'state.json').exists())

    def test_success_and_resume_cached(self):
        self.prepare();c=Client(self.workspace)
        run(self.workspace,config(),True,client=c)
        run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,1)
        self.assertEqual(export(self.workspace)['primary_candidates'],1)

    def test_workspace_lifetime_request_budget(self):
        self.prepare(long=True);c=Client(self.workspace);cfg=config();cfg['max_requests']=1
        run(self.workspace,cfg,True,client=c);run(self.workspace,cfg,True,client=c)
        self.assertEqual(c.calls,1)
        self.assertIn('partial',[p['status'] for p in export(self.workspace)['papers']])

    def test_token_budget_before_send(self):
        self.prepare();c=Client(self.workspace);cfg=config();cfg['max_reserved_tokens']=1
        run(self.workspace,cfg,True,client=c)
        self.assertEqual(c.calls,0)

    def test_estimate_needs_no_key_or_network(self):
        self.prepare()
        with patch.dict(os.environ,{},clear=True):result=estimate(self.workspace,config())
        self.assertEqual(result['api_requests_sent'],0)
        self.assertFalse(result['credentials_read'])
        self.assertGreater(result['total_estimated_reservation_all_jobs'],0)

    def test_unknown_network_outcome_not_resent(self):
        self.prepare();c=Client(self.workspace,failure=RequestFailure('timeout',ambiguous=True))
        run(self.workspace,config(),True,client=c)
        run(self.workspace,config(),True,retry_failed=True,client=c)
        self.assertEqual(c.calls,1)
        self.assertEqual(status(self.workspace)['job_status'],{'needs_attention':1})

    def test_known_failure_only_explicit_retry(self):
        self.prepare();c=Client(self.workspace,failure=RequestFailure('http_error',429))
        run(self.workspace,config(),True,client=c);run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,1)
        c.failure=None;run(self.workspace,config(),True,retry_failed=True,client=c)
        self.assertEqual(c.calls,2)

    def test_crashed_in_flight_not_resent(self):
        self.prepare();c=Client(self.workspace)
        run(self.workspace,config(),True,client=c)
        p=self.workspace/'state.json';s=read(p);s['attempts'][0]['status']='in_flight';save(p,s)
        with self.assertRaises(ValueError):run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,1)

    def test_changed_model_refuses_resume(self):
        self.prepare();c=Client(self.workspace);run(self.workspace,config(),True,client=c)
        cfg=config();cfg['model']='different'
        with self.assertRaises(ValueError):run(self.workspace,cfg,True,client=c)

    def test_changed_prompt_refuses(self):
        self.prepare();c=Client(self.workspace)
        with (self.workspace/'prompt.md').open('a',encoding='utf-8') as f:f.write('changed')
        with self.assertRaises(ValueError):run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,0)

    def test_changed_job_refuses(self):
        plan=self.prepare();c=Client(self.workspace)
        p=self.workspace/'jobs'/f'{plan["job_ids"][0]}.json';j=read(p);j['title']='tampered';save(p,j)
        with self.assertRaises(ValueError):run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,0)

    def test_changed_source_refuses(self):
        self.prepare();c=Client(self.workspace)
        (self.root/'paper.xml').write_text('<changed/>',encoding='utf-8')
        with self.assertRaises(ValueError):run(self.workspace,config(),True,client=c)

    def test_changed_result_refuses_resume(self):
        self.prepare();c=Client(self.workspace);run(self.workspace,config(),True,client=c)
        p=next((self.workspace/'results').glob('*.json'));p.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):run(self.workspace,config(),True,client=c)

    def test_invalid_quote_retained_in_quarantine(self):
        self.prepare();c=Client(self.workspace,invalid=True);run(self.workspace,config(),True,client=c)
        result=export(self.workspace)
        self.assertEqual(result['primary_candidates'],0)
        self.assertEqual(result['quarantined_records'],1)
        self.assertEqual(result['papers'][0]['status'],'processed_with_quarantine')

    def test_lock_prevents_parallel_calls(self):
        self.prepare();c=Client(self.workspace)
        with lock(self.workspace):
            with self.assertRaises(FileExistsError):run(self.workspace,config(),True,client=c)
        self.assertEqual(c.calls,0)

    def test_truncated_response_not_empty(self):
        p={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        with self.assertRaises(ValueError):parse_completion(p)

    def test_duplicate_json_keys_rejected(self):
        p={'choices':[{'finish_reason':'stop','message':{'content':'{"records":[],"records":[1]}'}}]}
        with self.assertRaises(ValueError):parse_completion(p)

    def test_config_rejects_inline_key(self):
        cfg=config();cfg['api_key']='do-not-log'
        with self.assertRaises(ValueError):check_config(cfg)

    def test_config_rejects_remote_http_and_url_credentials(self):
        for url in ['http://example.org/v1','https://user:secret@example.org/v1']:
            cfg=config();cfg['base_url']=url
            with self.assertRaises(ValueError):check_config(cfg)

    def test_formula_cells_escaped(self):
        self.assertEqual(safe_cell(' =CMD()'),"' =CMD()")

    def test_redirect_not_followed(self):
        self.prepare();received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.path)
                self.send_response(307);self.send_header('Location','https://example.invalid/leak');self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cfg=config();cfg['base_url']=f'http://127.0.0.1:{server.server_port}/v1'
        try:
            with patch.dict(os.environ,{'JANUS_TEST_ONLY_KEY':'fixture-secret'}):result=run(self.workspace,cfg,True)
        finally:server.shutdown();server.server_close();thread.join()
        self.assertEqual(received,['/v1/chat/completions'])
        self.assertEqual(result['job_status'],{'needs_attention':1})

    def test_http_wire_and_secret_not_persisted(self):
        plan=self.prepare();job=read(self.workspace/'jobs'/f'{plan["job_ids"][0]}.json')
        received=[];response=completion(job)
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body=json.dumps(response).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cfg=config();cfg['base_url']=f'http://127.0.0.1:{server.server_port}/v1'
        try:
            with patch.dict(os.environ,{'JANUS_TEST_ONLY_KEY':'fixture-secret-never-persist'}):
                run(self.workspace,cfg,True)
        finally:server.shutdown();server.server_close();thread.join()
        self.assertEqual(received[0][0],'/v1/chat/completions')
        self.assertEqual(received[0][1],'Bearer fixture-secret-never-persist')
        self.assertNotIn('source_path',received[0][2]['messages'][1]['content'])
        for p in self.workspace.rglob('*.json'):
            self.assertNotIn('fixture-secret-never-persist',p.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
