import json
from pathlib import Path
import tempfile
import unittest

from batch_budget import create, status
from corpus import save, read
from rag_trial import prepare, retrieve, run, validate_answer
from test_runner import config


class RagTests(unittest.TestCase):
    def test_retrieval_respects_text_cap(self):
        items = [{'evidence_id': str(i), 'text': 'TNG961 response ' * 30, 'source_units': []} for i in range(20)]
        selected = retrieve('TNG961', items, cap=1000)
        self.assertLessEqual(sum(len(i['text']) for i in selected), 1000)
        self.assertTrue(selected)

    def test_unknown_citation_invalid(self):
        e = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'answer': 'Answer', 'citations': ['fabricated'], 'uncertainty': ''})}}]}
        with self.assertRaises(ValueError): validate_answer(e, {'evidence_ids': []})

    def test_prepare_run_resume_and_answer_key_not_sent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); work = root / 'data'; work.mkdir()
            save(work / 'documents/P.json', {'paper_id': 'P', 'units': [
                {'unit_id': 'P1', 'kind': 'body_paragraph', 'text': 'Compound X did not degrade T.'}]})
            save(work / 'exports/records.json', [{'record_key': 'P:R', 'paper_id': 'P',
                'fields': {'compound': 'X', 'result_text': 'No degradation'},
                'evidence': [{'field': 'result_text', 'quote': 'Compound X did not degrade T.'}],
                'result_units': ['P1']}])
            save(root / 'review.json', {'items': [{'record_key': 'P:R', 'decision': 'supported_with_limits'}]})
            save(root / 'questions.json', {'questions': [{'id': 'Q1', 'paper_id': 'P', 'split': 'evaluation',
                'question': 'Does X degrade T?', 'source_unit_ids': ['P1'], 'rubric': ['GOLD_ONLY_NOT_SENT']}]})
            qa = root / 'qa'; result = prepare(qa, [work], [root / 'review.json'], root / 'questions.json')
            self.assertEqual(result['planned_requests'], 3)
            for p in (qa / 'tasks').glob('*.json'):
                self.assertNotIn('GOLD_ONLY_NOT_SENT', p.read_text(encoding='utf-8'))
            class Client:
                calls = 0
                def complete(self, request):
                    self.calls += 1
                    user = json.loads(request['messages'][1]['content'])
                    value = {'answer': 'It does not under the stated conditions.',
                             'citations': [e['evidence_id'] for e in user['evidence']], 'uncertainty': ''}
                    return {'model': 'fixture', 'usage': {'total_tokens': 10}, 'choices': [
                        {'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]}
            client = Client(); ledger = root / 'ledger.json'; create(ledger, 10, 1_000_000, 'Fixture')
            cfg = config(); cfg['max_requests'] = 10
            r = run(qa, cfg, ledger, None, live=True, client=client)
            self.assertEqual(r['completed'], 3)
            run(qa, cfg, ledger, None, live=True, client=client)
            self.assertEqual(client.calls, 3)
            self.assertEqual(status(ledger)['requests_reserved'], 3)
            self.assertEqual(len(read(qa / 'blind_answers.json')), 3)
