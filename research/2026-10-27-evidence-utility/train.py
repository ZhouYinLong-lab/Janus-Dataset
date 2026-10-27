"""Matched-budget continued language-model training of reviewed experimental evidence."""
import argparse
from collections import Counter
import importlib.metadata
from pathlib import Path
import random

from common import digest, doi, fresh, read, seal, sha, verify, write
from rag import validate_questions

ARMS = ('positive_only', 'domain_control', 'balanced_negative')


def training_passage(row):
    # Identical representation for all arms; retain the original and contextual support quotes.
    quotes = [row.get('original_quote') or row.get('quote')]
    quotes.extend(e['quote'] for e in row.get('field_evidence', []))
    return '\n'.join(dict.fromkeys(q for q in quotes if q))


def prepare_training(bundle, questions, config, out, benchmark=None):
    verify(bundle)
    rows, cfg, qs = read(Path(bundle) / 'evidence.json'), read(config), read(questions)
    validate_questions(qs)
    required = {'model_path', 'seed', 'max_steps', 'seq_length', 'micro_batch_size',
                'gradient_accumulation_steps', 'learning_rate', 'lora_r', 'lora_alpha',
                'target_modules', 'min_source_groups'}
    if set(cfg) != required:
        raise ValueError('Training config keys differ from documented interface')
    for k in ('seed', 'max_steps', 'seq_length', 'micro_batch_size', 'gradient_accumulation_steps',
              'lora_r', 'lora_alpha', 'min_source_groups'):
        if type(cfg[k]) is not int or cfg[k] < 1:
            raise ValueError('Positive integer required: ' + k)
    if cfg['seq_length'] < 8 or not isinstance(cfg['target_modules'], list) or not cfg['target_modules']:
        raise ValueError('Sequence length / target modules invalid')
    if type(cfg['learning_rate']) not in (int, float) or not 0 < cfg['learning_rate'] < 1:
        raise ValueError('Invalid learning rate')
    cfg['model_path'] = str((Path(config).resolve().parent / cfg['model_path']).resolve())
    groups = {r['group_id'] for r in rows}
    blockers = []
    if len(groups) < cfg['min_source_groups']:
        blockers.append('insufficient_independent_source_groups')
    test_qs = [q for q in qs if q['split'] == 'test']
    if not test_qs:
        blockers.append('no_frozen_test_questions')
    test_dois = {doi(d) for q in test_qs for d in q['source_dois']}
    if not test_dois:
        blockers.append('test_source_dois_missing')
    trainval_dois = {doi(r['doi']) for r in rows if r['split'] in {'train', 'val'} and r.get('doi')}
    if trainval_dois & test_dois:
        blockers.append('test_question_source_overlaps_train_or_val')
    benchmark_overlaps = []
    if benchmark:
        verify(benchmark)
        benchmark_excluded = set(read(Path(benchmark) / 'overlap_audit.json')['training_excluded_source_dois'])
        benchmark_overlaps = sorted(trainval_dois & benchmark_excluded)
        if benchmark_overlaps:
            blockers.append('mg2act_val_or_test_source_overlaps_train_or_val')
    corpus, stats = {}, {}
    for split in ('train', 'val'):
        kinds = {k: sorted([r for r in rows if r['split'] == split and r['kind'] == k and
                             r.get('training_allowed') is True], key=lambda r: r['evidence_id'])
                 for k in ('positive', 'negative', 'background')}
        n = min(map(len, kinds.values()))
        if n == 0:
            blockers.append(split + '_missing_positive_negative_or_background')
        rng = random.Random(cfg['seed'])
        for rs in kinds.values():
            rng.shuffle(rs)
        selected = {k: v[:n] for k, v in kinds.items()}
        arms = {'positive_only': selected['positive'] * 2,
                'domain_control': selected['positive'] + selected['background'],
                'balanced_negative': selected['positive'] + selected['negative']}
        for arm, rs in arms.items():
            items = [dict(evidence_id=r['evidence_id'], paper_id=r['paper_id'], doi=r.get('doi'),
                          source_sha256=r['source_sha256'], group_id=r['group_id'], kind=r['kind'],
                          text=training_passage(r), review_kind=r.get('review_kind')) for r in rs]
            random.Random(cfg['seed']).shuffle(items)
            corpus[arm + ':' + split] = items
            if len({r['group_id'] for r in items}) < (3 if split == 'train' else 1):
                blockers.append(arm + '_' + split + '_too_few_selected_source_groups')
            stats[arm + ':' + split] = {'records': len(items), 'kind_counts': dict(Counter(r['kind'] for r in items)),
                                         'unique_sources': len({r['source_sha256'] for r in items})}
    out = fresh(out)
    write(out / 'corpora.json', corpus)
    write(out / 'config.json', cfg)
    summary = {'ready': not blockers, 'blockers': sorted(set(blockers)), 'arms': stats,
               'benchmark_overlapping_dois': benchmark_overlaps,
               'benchmark_overlap_check_performed': benchmark is not None,
               'training_executed': False, 'base_arm': 'unmodified pretrained model',
               'objective': 'continued causal language modeling of evidence text, not polarity classification',
               'representation': 'Same verbatim support-quote format in every arm; contextual quotes retained.',
               'balance': '1:1 positive/negative evidence records in balanced_negative; token composition reported at tokenization',
               'tokens_per_arm': cfg['max_steps'] * cfg['micro_batch_size'] * cfg['gradient_accumulation_steps'] * cfg['seq_length'],
               'loss_target_tokens_per_arm': cfg['max_steps'] * cfg['micro_batch_size'] * cfg['gradient_accumulation_steps'] * (cfg['seq_length'] - 1)}
    write(out / 'readiness.json', summary)
    inputs = [Path(bundle) / 'manifest.json', questions, config]
    if benchmark:
        inputs.append(Path(benchmark) / 'manifest.json')
    seal(out, inputs, {'artifact': 'training_material'})
    return summary


def tokenize_blocks(rows, tokenizer, seq_length):
    """Full-document stream with EOS boundaries; drop tail explicitly, no silent example truncation."""
    stream, kind_tokens = [], Counter()
    for row in rows:
        ids = tokenizer.encode(row['text'], add_special_tokens=False) + [tokenizer.eos_token_id]
        stream.extend(ids)
        kind_tokens[row['kind']] += len(ids)
    count = len(stream) // seq_length
    if count < 1:
        raise ValueError('Corpus too small for a single full block')
    return [stream[i * seq_length:(i + 1) * seq_length] for i in range(count)], {
        'corpus_tokens': len(stream), 'kind_tokens': dict(kind_tokens),
        'full_blocks': count, 'dropped_tail_tokens': len(stream) % seq_length}


def optimize(model, train_blocks, val_blocks, cfg, out, resume=None, device=None):
    """Fixed tokens/updates and deterministic order; used by real LoRA and synthetic smoke tests."""
    import torch
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg['learning_rate'])
    start = 0
    cfg_hash = digest(cfg)
    data_hash = digest([train_blocks, val_blocks])
    if resume:
        state = torch.load(resume, map_location=device, weights_only=True)
        if state['config_sha256'] != cfg_hash or state['data_sha256'] != data_hash:
            raise ValueError('Resume config/data changed')
        if 'adapter' in state:
            from peft import set_peft_model_state_dict
            set_peft_model_state_dict(model, state['adapter'])
        else:
            model.load_state_dict(state['model'])
        optimizer.load_state_dict(state['optimizer'])
        start = state['step']
        torch.set_rng_state(state['rng'].cpu())
        if device == 'cuda' and state.get('cuda_rng') is not None:
            torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda_rng']])
    else:
        torch.manual_seed(cfg['seed'])
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(cfg['seed'])
    batch, accum = cfg['micro_batch_size'], cfg['gradient_accumulation_steps']
    losses = []
    for step in range(start, cfg['max_steps']):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        total = 0.
        for micro in range(accum):
            offset = (step * accum + micro) * batch
            x = torch.tensor([train_blocks[(offset + j) % len(train_blocks)] for j in range(batch)], device=device)
            loss = model(input_ids=x, labels=x).loss
            if not torch.isfinite(loss):
                raise ValueError('Non-finite training loss')
            (loss / accum).backward()
            total += float(loss.detach()) / accum
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.)
        optimizer.step()
        losses.append({'step': step + 1, 'loss': total})
        checkpoint = {'step': step + 1, 'optimizer': optimizer.state_dict(), 'rng': torch.get_rng_state(),
                      'cuda_rng': torch.cuda.get_rng_state_all() if device == 'cuda' else None,
                      'config_sha256': cfg_hash, 'data_sha256': data_hash}
        if hasattr(model, 'peft_config'):
            from peft import get_peft_model_state_dict
            checkpoint['adapter'] = get_peft_model_state_dict(model)
        else:
            checkpoint['model'] = model.state_dict()
        tmp = out / 'checkpoint.tmp.pt'
        torch.save(checkpoint, tmp)
        tmp.replace(out / 'checkpoint.pt')
        write(out / 'progress.json', {'step': step + 1, 'max_steps': cfg['max_steps'], 'last_loss': total})
    model.eval()
    with torch.no_grad():
        val = [float(model(input_ids=(x := torch.tensor([block], device=device)), labels=x).loss)
               for block in val_blocks]
    result = {'steps': cfg['max_steps'], 'resumed_from_step': start, 'losses_this_invocation': losses,
              'validation_loss': sum(val) / len(val), 'device': device,
              'input_tokens': cfg['max_steps'] * batch * accum * cfg['seq_length'],
              'loss_target_tokens': cfg['max_steps'] * batch * accum * (cfg['seq_length'] - 1),
              'utility_evaluated': False}
    write(out / 'training_metrics.json', result)
    return result


def train(material, arm, out, execute=False, resume=False):
    verify(material)
    material = Path(material)
    readiness = read(material / 'readiness.json')
    if not execute:
        return readiness
    if not readiness['ready']:
        raise ValueError('Training prerequisites: ' + ', '.join(readiness['blockers']))
    if arm not in ARMS:
        raise ValueError('Unknown training arm')
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model
    cfg = read(material / 'config.json')
    model_path = Path(cfg['model_path']).resolve()
    if not model_path.is_dir():
        raise ValueError('Supply a local pinned base model directory')
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    if tokenizer.eos_token_id is None:
        raise ValueError('Tokenizer needs EOS token')
    corpus = read(material / 'corpora.json')
    train_blocks, train_stats = tokenize_blocks(corpus[arm + ':train'], tokenizer, cfg['seq_length'])
    val_blocks, val_stats = tokenize_blocks(corpus[arm + ':val'], tokenizer, cfg['seq_length'])
    out = Path(out)
    model_hashes = {str(p.relative_to(model_path)): sha(p) for p in sorted(model_path.rglob('*'))
                    if p.is_file() and '.cache' not in p.parts}
    identity = {'material_sha256': sha(material / 'manifest.json'), 'arm': arm,
                'model_path': str(model_path), 'model_hashes': model_hashes, 'config': cfg,
                'packages': {n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'peft')}}
    if resume:
        if read(out / 'run_identity.json') != identity:
            raise ValueError('Training resume identity/model changed')
    else:
        fresh(out)
        write(out / 'run_identity.json', identity)
    # Same base, initialization seed, dtype and LoRA settings for each arm.
    torch.manual_seed(cfg['seed'])
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, trust_remote_code=False,
                                                dtype=torch.float32)
    model = get_peft_model(model, LoraConfig(r=cfg['lora_r'], lora_alpha=cfg['lora_alpha'], lora_dropout=0.,
                                           target_modules=cfg['target_modules'], task_type='CAUSAL_LM'))
    model.config.use_cache = False
    write(out / 'tokenization_report.json', {'train': train_stats, 'val': val_stats})
    # Exclusive lock protects checkpoints from a second training instance.
    import sys
    from common import CORE
    sys.path.insert(0, str(CORE))
    from runner import lock
    with lock(out):
        result = optimize(model, train_blocks, val_blocks, cfg, out,
                          out / 'checkpoint.pt' if resume else None)
        model.save_pretrained(out / 'adapter')
        tokenizer.save_pretrained(out / 'adapter')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare')
    for name in ('bundle', 'questions', 'config', 'out'):
        a.add_argument('--' + name, required=True, type=Path)
    a.add_argument('--benchmark', type=Path)
    a = sub.add_parser('run')
    a.add_argument('--material', type=Path, required=True)
    a.add_argument('--arm', choices=ARMS, required=True)
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--execute', action='store_true')
    a.add_argument('--resume', action='store_true')
    args = vars(p.parse_args())
    print(prepare_training(**args) if args.pop('command') == 'prepare' else train(**args))
