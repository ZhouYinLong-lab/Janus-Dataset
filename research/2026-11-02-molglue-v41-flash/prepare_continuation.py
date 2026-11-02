"""Create an immutable-input continuation workspace for sentence_v3 runs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parents[1] / '2026-10-25-api-extraction'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _local_path(destination, path):
    return str((destination / Path(path).name).resolve())


def prepare(source, destination, config_path, ledger_path):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        existing = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
        if existing.get('continuation_of') != str(source):
            raise ValueError('Continuation destination already exists')
    else:
        existing = None
    source_manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if source_manifest.get('pipeline') != 'molgluedb_sentence_v3':
        raise ValueError('Only sentence_v3 workspaces are supported')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    if existing is None:
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
            '.candidate_run.lock', '.candidate_run.lock.guard'))

    # Runtime copies are updated together with the manifest; all documents,
    # jobs, responses and results remain byte-identical copies of the source.
    manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
    for name in manifest['code_hashes']:
        source_code = HERE / name
        target_code = destination / 'runtime' / name
        shutil.copyfile(source_code, target_code)
        manifest['code_hashes'][name] = hashlib.sha256(source_code.read_bytes()).hexdigest()

    for paper in manifest['papers']:
        for field, folder in (('document_path', 'documents'),
                              ('sentence_index_path', 'sentence_indexes')):
            old = Path(paper[field])
            paper[field] = _local_path(destination / folder, old)
        for jid in paper['job_ids']:
            job_path = destination / 'jobs' / f'{jid}.json'
            job = json.loads(job_path.read_text(encoding='utf-8'))
            job['document_path'] = paper['document_path']
            job['sentence_index_path'] = paper['sentence_index_path']
            save(job_path, job)
            manifest['file_hashes'][f'jobs/{jid}.json'] = hashlib.sha256(
                job_path.read_bytes()).hexdigest()

    manifest['continuation_of'] = str(source)
    manifest['continuation_created'] = True
    save(destination / 'manifest.json', manifest)

    state_path = destination / 'candidate_state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    source_state = json.loads((source / 'candidate_state.json').read_text(encoding='utf-8'))
    state['historical_stop_reason'] = (state.get('historical_stop_reason')
                                      or source_state.get('stop_reason'))
    state['stop_reason'] = None
    for entry in state.get('tasks', {}).values():
        if entry.get('status') != 'complete' and entry.get('attempt_id'):
            entry['historical_attempt_id'] = entry.pop('attempt_id')
            entry['recovery'] = 'historical_outcome_preserved_in_continuation'
    state['config'] = config
    state['budget_path'] = str(Path(ledger_path).resolve())
    state['network_route'] = 'direct'
    state['identity'] = digest({
        'manifest': hashlib.sha256((destination / 'manifest.json').read_bytes()).hexdigest(),
        'config': {k: v for k, v in config.items()
                   if k not in {'max_requests', 'max_reserved_tokens'}},
        'budget_path': state['budget_path'],
        'network_route': 'direct',
    })
    save(state_path, state)
    return {
        'source': str(source),
        'destination': str(destination),
        'papers': len(manifest['papers']),
        'discovery_jobs': len(manifest['job_ids']),
        'historical_tasks': len(state.get('tasks', {})),
        'historical_stop_reason': state['historical_stop_reason'],
        'code_hashes_updated': len(manifest['code_hashes']),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--ledger', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.destination, args.config, args.ledger),
                     ensure_ascii=False, indent=2))
