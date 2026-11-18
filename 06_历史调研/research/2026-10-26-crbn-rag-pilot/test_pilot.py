"""Offline billing/citation safeguards; fake ledger never touches paid accounts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import pilot


class FakeClient:
    def __init__(self, unknown=False, invalid=False):
        self.calls=0; self.unknown=unknown; self.invalid=invalid
    def complete(self,request):
        self.calls+=1
        if self.unknown: raise pilot.RequestFailure('network_outcome_unknown',ambiguous=True)
        qs=json.loads(request['messages'][1]['content'])['questions']
        answers=[{'question_id':q['question_id'],'answer':'Insufficient evidence in this offline transport test.',
                  'citations':(['not_supplied'] if self.invalid else []),'uncertainty':'Offline test.'} for q in qs]
        return {'model':'offline-fake','usage':{'total_tokens':1},
                'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'answers':answers})}}]}


class PilotTests(unittest.TestCase):
    def setup_run(self,root):
        root=Path(root); ledger=root/'FAKE_OFFLINE_LEDGER.json'; out=root/'trial'
        cfg=pilot.read(pilot.HERE/'config.json'); cfg['base_url']='http://localhost:12345/v1'
        pilot.budget.create(ledger,15,1000000,'Offline fake transport test only; no provider calls')
        pilot.prepare(out,cfg)
        return out,ledger
    def test_complete_and_resume_skip_all(self):
        with tempfile.TemporaryDirectory() as root:
            out,ledger=self.setup_run(root); fake=FakeClient()
            result=pilot.run(out,ledger,None,live=True,client=fake)
            self.assertEqual(result['statuses'],{'complete':60})
            self.assertEqual(fake.calls,15)
            pilot.run(out,ledger,None,live=True,client=fake)
            self.assertEqual(fake.calls,15)
            self.assertEqual(pilot.budget.status(ledger)['requests_reserved'],15)
    def test_unknown_not_retried_and_consecutive_stop(self):
        with tempfile.TemporaryDirectory() as root:
            out,ledger=self.setup_run(root); fake=FakeClient(unknown=True)
            pilot.run(out,ledger,None,live=True,client=fake)
            self.assertEqual(fake.calls,2)
            self.assertEqual(pilot.budget.status(ledger)['global_stop'],'two_consecutive_network_failures')
            pilot.run(out,ledger,None,live=True,client=fake)
            self.assertEqual(fake.calls,2)
    def test_invalid_citations_preserved_not_repaired(self):
        with tempfile.TemporaryDirectory() as root:
            out,ledger=self.setup_run(root); fake=FakeClient(invalid=True)
            result=pilot.run(out,ledger,None,live=True,client=fake)
            self.assertEqual(result['statuses'],{'invalid_answer':60})
            self.assertEqual(fake.calls,15)
    def test_inputs_and_reference_separation(self):
        with tempfile.TemporaryDirectory() as root:
            out,ledger=self.setup_run(root)
            task=pilot.read(out/'tasks/B204_structured_cards.json')
            sent=json.loads(task['messages'][1]['content'])
            self.assertEqual(len(sent['questions']),4)
            self.assertTrue(all(set(q)=={'question_id','question','evidence'} for q in sent['questions']))
            changed=out/'tasks/B204_structured_cards.json'
            changed.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError): pilot.verify(out)


if __name__=='__main__': unittest.main()
