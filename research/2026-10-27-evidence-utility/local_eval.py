"""Run the same frozen tasks through a local base model and LoRA adapters."""
import argparse
import importlib.metadata
import json
from pathlib import Path

from common import digest, fresh, read, seal, sha, verify, write


def prepare_local(trial, models, out, context_arm='no_retrieval'):
    verify(trial)
    trial = Path(trial)
    specs = read(models)
    if not specs or len({m['name'] for m in specs}) != len(specs):
        raise ValueError('Unique model arm names required')
    for m in specs:
        if not m.get('model_path'):
            raise ValueError('Local base model_path required')
        for key in ('model_path', 'adapter_path'):
            if m.get(key):
                m[key] = str((Path(models).resolve().parent / m[key]).resolve())
    template = [t for t in read(trial / 'tasks.json') if t['arm'] == context_arm]
    if not template:
        raise ValueError('Requested context arm missing')
    tasks = []
    for m in specs:
        for t in template:
            tasks.append(dict(t, task_id=digest([m['name'], t['task_id']]), arm=m['name']))
    out = fresh(out)
    write(out / 'tasks.json', tasks)
    write(out / 'models.json', specs)
    if (trial / 'questions.json').exists():
        write(out / 'questions.json', read(trial / 'questions.json'))
    seal(out, [trial / 'manifest.json', models], {'artifact': 'local_model_evaluation',
                                                'context_arm': context_arm, 'api_requests': 0})
    return {'tasks': len(tasks), 'api_requests': 0, 'model_inference_executed': False}


def parse_json(text):
    # No permissive first-brace recovery; invalid output remains a failed task.
    return json.loads(text.strip())


def run_local(out, execute=False, max_new_tasks=None, max_new_tokens=512):
    verify(out)
    out = Path(out)
    tasks = read(out / 'tasks.json')
    if not execute:
        return {'tasks': len(tasks), 'model_inference_executed': False}
    import sys
    from common import CORE
    sys.path.insert(0, str(CORE))
    from runner import lock
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from run import validate
    if max_new_tokens < 1 or (max_new_tasks is not None and max_new_tasks < 1):
        raise ValueError('Positive generation limits required')
    models = {m['name']: m for m in read(out / 'models.json')}
    with lock(out):
        path = out / 'local_state.json'
        state = read(path) if path.exists() else {'tasks': {}, 'model_files': {}}
        policy = {'max_new_tokens': max_new_tokens, 'do_sample': False,
                  'packages': {n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'peft')}}
        if 'policy' in state and state['policy'] != policy:
            raise ValueError('Local decoding/environment policy changed')
        state['policy'] = policy
        active, model, tokenizer, new = None, None, None, 0
        for t in tasks:
            tid = t['task_id']
            if tid in state['tasks']:
                entry = state['tasks'][tid]
                if entry.get('response_sha256') and sha(out / entry['response_path']) != entry['response_sha256']:
                    raise ValueError('Local response changed')
                continue
            if max_new_tasks is not None and new >= max_new_tasks:
                break
            spec = models[t['arm']]
            if active != t['arm']:
                if model is not None:
                    del model
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                roots = [Path(spec['model_path'])] + ([Path(spec['adapter_path'])] if spec.get('adapter_path') else [])
                files = {str(p.resolve()): sha(p) for root in roots for p in sorted(root.rglob('*'))
                         if p.is_file() and '.cache' not in p.parts}
                if not files or not all(r.is_dir() for r in roots):
                    raise ValueError('Missing local model/adapter')
                if spec['name'] in state['model_files'] and state['model_files'][spec['name']] != files:
                    raise ValueError('Model/adapter weights changed')
                state['model_files'][spec['name']] = files
                tokenizer = AutoTokenizer.from_pretrained(spec['model_path'], local_files_only=True, trust_remote_code=False)
                model = AutoModelForCausalLM.from_pretrained(spec['model_path'], local_files_only=True,
                                                            trust_remote_code=False, dtype=torch.float32)
                if spec.get('adapter_path'):
                    from peft import PeftModel
                    model = PeftModel.from_pretrained(model, spec['adapter_path'], local_files_only=True)
                model.to('cuda' if torch.cuda.is_available() else 'cpu').eval()
                active = t['arm']
            if tokenizer.chat_template:
                prompt = tokenizer.apply_chat_template(t['messages'], tokenize=False, add_generation_prompt=True)
            else:
                prompt = '\n\n'.join(m['role'].upper() + ':\n' + m['content'] for m in t['messages']) + '\n\nASSISTANT:\n'
            encoded = tokenizer(prompt, return_tensors='pt', add_special_tokens=False).to(model.device)
            context_limit = getattr(model.config, 'max_position_embeddings', 2048)
            if encoded['input_ids'].shape[1] + max_new_tokens > context_limit:
                state['tasks'][tid] = {'status': 'context_overflow', 'failure_kind': 'no_silent_truncation'}
                write(path, state)
                continue
            with torch.no_grad():
                result = model.generate(**encoded, max_new_tokens=max_new_tokens, do_sample=False,
                                        pad_token_id=tokenizer.eos_token_id)
            ids = result[0, encoded['input_ids'].shape[1]:]
            text = tokenizer.decode(ids, skip_special_tokens=True)
            response_path = 'responses/' + tid + '.json'
            payload = {'generated_text': text, 'output_tokens': len(ids),
                       'input_tokens': encoded['input_ids'].shape[1], 'model_arm': t['arm']}
            write(out / response_path, payload)
            entry = {'response_path': response_path, 'response_sha256': sha(out / response_path)}
            try:
                parsed = parse_json(text)
                envelope = {'model': t['arm'], 'choices': [{'finish_reason': 'stop',
                            'message': {'content': json.dumps(parsed)}}]}
                if len(ids) >= max_new_tokens and int(ids[-1]) != tokenizer.eos_token_id:
                    raise ValueError('Generation hit output cap')
                entry.update(status='complete', result=validate(envelope, t, [t['arm']]))
            except (ValueError, KeyError, TypeError):
                entry.update(status='invalid_response', failure_kind='json_or_citation_contract')
            state['tasks'][tid] = entry
            write(path, state)
            new += 1
        answers = []
        for t in tasks:
            e = state['tasks'].get(t['task_id'], {'status': 'pending'})
            answers.append({k: t[k] for k in ('task_id', 'question_id', 'arm')} |
                           {'status': e['status'], 'result': e.get('result'),
                            'response_sha256': e.get('response_sha256'), 'failure_kind': e.get('failure_kind')})
        write(out / 'exports/answers.json', answers)
    return {'tasks': len(tasks), 'complete': sum(a['status'] == 'complete' for a in answers), 'api_requests': 0}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare')
    for name in ('trial', 'models', 'out'):
        a.add_argument('--' + name, type=Path, required=True)
    a.add_argument('--context-arm', default='no_retrieval')
    a = sub.add_parser('run')
    a.add_argument('--out', type=Path, required=True)
    a.add_argument('--execute', action='store_true')
    a.add_argument('--max-new-tasks', type=int)
    a.add_argument('--max-new-tokens', type=int, default=512)
    args = vars(p.parse_args())
    print(prepare_local(**args) if args.pop('command') == 'prepare' else run_local(**args))
