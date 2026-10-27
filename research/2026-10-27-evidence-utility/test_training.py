from pathlib import Path
import tempfile
import unittest

from common import HERE, read, write
from local_eval import parse_json, prepare_local, run_local
from train import optimize, prepare_training, tokenize_blocks
from test_rag import trial_fixture


class Tokenizer:
    eos_token_id = 0

    def encode(self, text, add_special_tokens=False):
        return [1 + ord(c) % 25 for c in text]


class TrainingTests(unittest.TestCase):
    def test_balance_and_test_source_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial_fixture(root)
            qs = read(root / 'questions.json')
            test = next(r for r in read(root / 'bundle/evidence.json') if r['split'] == 'test')
            qs[0]['source_dois'] = [test['doi']]
            write(root / 'heldout_questions.json', qs)
            result = prepare_training(root / 'bundle', root / 'heldout_questions.json',
                                      HERE / 'train.example.json', root / 'material')
            self.assertTrue(result['ready'])
            corpus = read(root / 'material/corpora.json')
            kinds = [r['kind'] for r in corpus['balanced_negative:train']]
            self.assertEqual(kinds.count('positive'), kinds.count('negative'))
            self.assertTrue(all(not set(qs[0]['source_dois']) & {r['doi']} for rs in corpus.values() for r in rs))
            qs[0]['source_dois'] = [corpus['positive_only:train'][0]['doi']]
            write(root / 'bad_questions.json', qs)
            bad = prepare_training(root / 'bundle', root / 'bad_questions.json',
                                   HERE / 'train.example.json', root / 'bad')
            self.assertIn('test_question_source_overlaps_train_or_val', bad['blockers'])

    def test_token_budget_and_tail_are_explicit(self):
        blocks, stats = tokenize_blocks([{'text': 'a' * 31, 'kind': 'negative'}], Tokenizer(), 8)
        self.assertEqual(len(blocks), 4)
        self.assertEqual(stats['corpus_tokens'], 32)
        self.assertEqual(stats['dropped_tail_tokens'], 0)
        self.assertEqual(stats['kind_tokens'], {'negative': 32})
        with self.assertRaisesRegex(ValueError, 'too small'):
            tokenize_blocks([{'text': 'a', 'kind': 'negative'}], Tokenizer(), 8)

    def test_local_evaluation_preparation_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = trial_fixture(root)
            write(root / 'models.json', [{'name': 'base', 'model_path': 'no-download'},
                                          {'name': 'balanced_negative', 'model_path': 'no-download', 'adapter_path': 'adapter'}])
            result = prepare_local(trial, root / 'models.json', root / 'eval')
            self.assertEqual(result['tasks'], 2)
            self.assertFalse(run_local(root / 'eval')['model_inference_executed'])
            with self.assertRaises(ValueError):
                parse_json('Text before {"score": 0.2}')

    def test_tiny_random_model_optimizer_and_resume(self):
        # Integration smoke: a randomly initialized 1-layer model and invented tokens, no research training.
        import torch
        from transformers import GPT2Config, GPT2LMHeadModel
        torch.set_num_threads(1)
        cfg = {'seed': 7, 'max_steps': 2, 'seq_length': 8, 'micro_batch_size': 1,
               'gradient_accumulation_steps': 2, 'learning_rate': .001}
        torch.manual_seed(7)
        model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=16, n_embd=16, n_layer=1, n_head=2,
                                         bos_token_id=0, eos_token_id=0))
        before = model.get_input_embeddings().weight.detach().clone()
        with tempfile.TemporaryDirectory() as tmp:
            blocks = [list(range(1, 9)), list(range(9, 17))]
            result = optimize(model, blocks, blocks[:1], cfg, Path(tmp), device='cpu')
            self.assertFalse(torch.equal(before, model.get_input_embeddings().weight.detach()))
            self.assertEqual(result['input_tokens'], 32)
            self.assertEqual(result['loss_target_tokens'], 28)
            result = optimize(model, blocks, blocks[:1], cfg, Path(tmp), Path(tmp) / 'checkpoint.pt', device='cpu')
            self.assertEqual(result['resumed_from_step'], 2)
            self.assertEqual(result['losses_this_invocation'], [])
            cfg['max_steps'] = 3
            with self.assertRaisesRegex(ValueError, 'changed'):
                optimize(model, blocks, blocks[:1], cfg, Path(tmp), Path(tmp) / 'checkpoint.pt', device='cpu')


if __name__ == '__main__':
    unittest.main()
