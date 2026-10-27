"""Serial v2/v3 runner. All sends require live=True; injected clients need no key.

The original batch_budget owns reservations and final accounting. The adjacent
*.candidate_index.json and *.candidate_run.lock files provide v2 identity and
process coordination without changing the old ledger or its locking protocol.
There are no retries, including for HTTP 429 and 500.
"""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import psutil

from api import RequestFailure, check_config, parse_completion, reserve_tokens
import batch_budget as budget
from batch_contract import discovery
import candidate_context
from corpus import read, save, sha


SENTENCE_PIPELINE = 'molgluedb_sentence_v3'
_SENTENCE_PROTOCOL_FILES = frozenset({
    'discovery_v3.md', 'facts_v3.md', 'conditions_v3.md',
    'discovery_schema.json', 'discovery_example.json',
    'facts_schema.json', 'facts_example.json',
    'conditions_schema.json', 'conditions_example.json', 'sentence_protocol.json'})


class IntegrityError(ValueError):
    """Frozen input, dependency or saved artifact failed verification."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()


def _path(workspace, name):
    path = (Path(workspace) / name).resolve()
    if not path.is_relative_to(Path(workspace).resolve()):
        raise IntegrityError('Artifact path escapes workspace')
    return path


def _checked(workspace, name, digest):
    path = _path(workspace, name)
    if not digest or not path.is_file() or sha(path) != digest:
        raise IntegrityError('Saved artifact hash mismatch: ' + str(name))
    return path


def _verify_workspace(workspace):
    from candidate_workspace import verify
    manifest = read(Path(workspace) / 'manifest.json')
    if manifest.get('pipeline') != SENTENCE_PIPELINE:
        return verify(workspace)
    from sentence_workspace import verify as verify_sentence
    try:
        return verify_sentence(workspace)
    except ValueError as exc:
        raise IntegrityError(str(exc)) from exc


def _task_key(jid, stage, group=0):
    return jid + ':' + stage + (f':{group:03d}' if stage in {'enrichment', 'facts', 'conditions'} else '')


def _audit(path, event):
    with Path(str(path) + '.audit.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(event, time=time.time()), sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class RunLock:
    """OS guard closes the stale-file takeover race; JSON records PID identity.

    The guard is permanent and never unlinked. Only a proven dead original
    process (including PID reuse) permits recovery of the metadata lock.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None
        self.owner = None

    def __enter__(self):
        self.stream = Path(str(self.path) + '.guard').open('a+b')
        self.stream.seek(0, 2)
        if not self.stream.tell():
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Another candidate run holds the lock') from None
        try:
            if self.path.exists():
                prior = read(self.path)
                if (type(prior.get('pid')) is not int
                        or not isinstance(prior.get('create_time'), (int, float))):
                    raise IntegrityError('Lock owner cannot be verified')
                try:
                    current = psutil.Process(prior['pid']).create_time()
                except psutil.NoSuchProcess:
                    current = None
                except psutil.AccessDenied:
                    raise RuntimeError('Cannot verify lock owner') from None
                if current is not None and abs(current - prior['create_time']) < 0.001:
                    raise RuntimeError('Candidate lock owner is still alive')
                _audit(self.path, {'event': 'recovered_dead_process_lock', 'owner': prior})
                self.path.unlink()
            self.owner = {'pid': os.getpid(),
                          'create_time': psutil.Process().create_time(),
                          'nonce': uuid.uuid4().hex}
            with self.path.open('x', encoding='utf-8') as stream:
                json.dump(self.owner, stream)
                stream.flush()
                os.fsync(stream.fileno())
            return self
        except BaseException:
            self.stream.close()
            raise

    def __exit__(self, *exc):
        try:
            if not self.path.exists() or read(self.path) != self.owner:
                raise IntegrityError('Run lock ownership changed')
            self.path.unlink()
        finally:
            self.stream.close()


def _scope(job):
    units = []
    for unit in job['primary_units']:
        uid = unit['unit_id']
        match = re.fullmatch(r'(.+):chars:(\d+):(\d+)', uid)
        parent = unit.get('parent_unit_id', match[1] if match else uid)
        start = unit.get('char_start', int(match[2]) if match else 0)
        end = unit.get('char_end', int(match[3]) if match else None)
        # Corpus unit hashes include paper_id. XML locators retain the same
        # source scope when a v2 inventory assigns a different paper label.
        canonical = (unit.get('kind', '') + ':' + unit['locator']
                     if unit.get('locator') else parent)
        units.append({'unit_id': canonical, 'start': start, 'end': end})
    if not units or not job.get('source_sha256'):
        raise ValueError('Source hash and nonempty primary scope required')
    return {'source_sha256': job['source_sha256'], 'units': units}


def _overlaps(left, right):
    if left['source_sha256'] != right['source_sha256']:
        return False
    return any(a['unit_id'] == b['unit_id']
               and (a['end'] is None or b['start'] < a['end'])
               and (b['end'] is None or a['start'] < b['end'])
               for a in left['units'] for b in right['units'])


def _portable(value):
    """Strip local paths, including JSON embedded in chat message content."""
    if isinstance(value, dict):
        return {k: _portable(v) for k, v in value.items()
                if k not in {'source_path', 'document_path', 'workspace'}}
    if isinstance(value, list):
        return [_portable(v) for v in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return value
        if isinstance(decoded, (dict, list)):
            return _portable(decoded)
    return value


def _logical(job, stage, candidates, request, config, manifest):
    sentence = manifest['pipeline'] == SENTENCE_PIPELINE
    prompts = {k: v for k, v in manifest['file_hashes'].items()
               if (k in _SENTENCE_PROTOCOL_FILES if sentence else
                   not k.startswith(('jobs/', 'documents/')))}
    identity = {'scope': _scope(job), 'paper_id': job['paper_id'],
                    'stage': stage, 'candidates': _portable(candidates),
                    'request': _portable(request),
                    'config': {k: v for k, v in config.items()
                               if k not in {'max_requests', 'max_reserved_tokens', 'api_key_env'}},
                    'prompts': prompts,
                    'code_hashes': manifest['code_hashes']}
    if sentence:
        identity.update(pipeline=SENTENCE_PIPELINE, protocol=job['protocol'],
                        discovery_result_sha256=job.get('discovery_result_sha256'),
                        facts_result_sha256=job.get('facts_result_sha256'),
                        frozen_context=_portable(job.get('frozen_context')))
    return _digest(identity)


def _entry(jid, stage, group, dependency=None):
    return dict(job_id=jid, stage=stage, group=group, status='pending',
                request_path=None, request_sha256=None,
                response_path=None, response_sha256=None,
                result_path=None, result_sha256=None, attempt_id=None,
                discovery_result_sha256=dependency)


def _check_state(workspace, state):
    sentence = state.get('pipeline') == SENTENCE_PIPELINE
    for tid, entry in state['tasks'].items():
        if sentence and (entry['stage'] not in {'discovery', 'facts', 'conditions'} or
                         type(entry['group']) is not int or entry['group'] < 0 or
                         tid != _task_key(entry['job_id'], entry['stage'], entry['group'])):
            raise IntegrityError('Invalid sentence task identity')
        for kind in ('request', 'response', 'result'):
            if entry.get(kind + '_sha256'):
                _checked(workspace, entry[kind + '_path'], entry[kind + '_sha256'])
        if entry['status'] == 'complete':
            _checked(workspace, entry['result_path'], entry['result_sha256'])
            _checked(workspace, entry['response_path'], entry['response_sha256'])
            _checked(workspace, entry['request_path'], entry['request_sha256'])
        if entry['stage'] in {'enrichment', 'facts', 'conditions'}:
            discovery_entry = state['tasks'].get(entry['job_id'] + ':discovery', {})
            if (discovery_entry.get('status') != 'complete' or
                    discovery_entry.get('result_sha256') != entry['discovery_result_sha256']):
                raise IntegrityError('Enrichment discovery dependency changed')
            if entry['job_id'] not in state.get('groups', {}):
                raise IntegrityError('Enrichment has no frozen context groups')
            if sentence:
                descriptor = (state.get('condition_groups', {}).get(tid)
                              if entry['stage'] == 'conditions' else state['groups'][entry['job_id']])
                if not descriptor or entry.get('context_plan_sha256') != descriptor['sha256']:
                    raise IntegrityError('Sentence context plan dependency changed')
                if entry['stage'] == 'conditions':
                    if entry.get('facts_result_sha256') != descriptor['facts_result_sha256']:
                        raise IntegrityError('Conditions facts dependency changed')
    for jid, descriptor in state.get('groups', {}).items():
        frozen = read(_checked(workspace, descriptor['path'], descriptor['sha256']))
        dependency = state['tasks'][jid + ':discovery']['result_sha256']
        if (frozen['discovery_result_sha256'] != dependency
                or descriptor['discovery_result_sha256'] != dependency):
            raise IntegrityError('Frozen groups discovery dependency changed')
        if sentence:
            for entry in state['tasks'].values():
                if entry['job_id'] == jid and entry['stage'] in {'facts', 'conditions'}:
                    _group_at(frozen['groups'], entry['group'])
    for tid, descriptor in state.get('condition_groups', {}).items():
        frozen = read(_checked(workspace, descriptor['path'], descriptor['sha256']))
        jid, group = descriptor['job_id'], descriptor['group']
        facts = state['tasks'].get(_task_key(jid, 'facts', group), {})
        groups = state.get('groups', {}).get(jid, {})
        if (tid != _task_key(jid, 'conditions', group) or facts.get('status') != 'complete' or
                descriptor['facts_result_sha256'] != facts.get('result_sha256') or
                frozen['facts_result_sha256'] != facts.get('result_sha256') or
                frozen['facts_context_sha256'] != groups.get('sha256') or
                descriptor['facts_context_sha256'] != groups.get('sha256') or
                frozen['discovery_result_sha256'] != facts.get('discovery_result_sha256')):
            raise IntegrityError('Frozen conditions dependency changed')
        condition = state['tasks'].get(tid)
        if condition and frozen['group'] is None:
            raise IntegrityError('Conditions task has no planned context')
        if frozen['group'] is None and descriptor.get('reason') != frozen.get('reason'):
            raise IntegrityError('Frozen conditions reason changed')


def _group_at(groups, group):
    if type(group) is not int or not 0 <= group < len(groups):
        raise IntegrityError('Frozen group index changed')
    return groups[group]


def _groups(workspace, state, job):
    jid = job['job_id']
    entry = state['tasks'][jid + ':discovery']
    dependency = entry['result_sha256']
    descriptor = state['groups'].get(jid)
    path = f'groups/{jid}.json'
    if descriptor:
        frozen = read(_checked(workspace, descriptor['path'], descriptor['sha256']))
    else:
        candidates = read(_checked(workspace, entry['result_path'], dependency))['accepted']
        sentence = job.get('protocol') == 'sentence_v3'
        if sentence:
            from sentence_workflow import plan_facts
            groups = plan_facts(deepcopy(job), deepcopy(candidates))
        else:
            groups = candidate_context.plan_candidate_groups(deepcopy(job), deepcopy(candidates))
        if not isinstance(groups, list) or any(
                not isinstance(g, dict) or not all(k in g for k in
                    ('candidates', 'candidate_contexts', 'context_units')) for g in groups):
            raise ValueError('Invalid candidate group plan')
        if sentence and any(len(g['candidates']) != 1 or any(
                not isinstance(g.get(k), list) for k in
                ('candidates', 'sentences', 'candidate_contexts', 'context_units')) for g in groups):
            raise ValueError('Facts require one candidate and sentence context per group')
        planned = [c for g in groups for c in g['candidates']]
        expected = candidates
        if sentence:
            # The facts adapter may add the explicit anchor alias required by
            # its validator, while all discovery evidence must stay identical.
            expected = [dict(c, anchor_sentence_ids=c['sentence_ids']) for c in candidates]
            planned = [dict(c, anchor_sentence_ids=c.get('anchor_sentence_ids', c.get('sentence_ids')))
                       for c in planned]
        if sorted(map(_digest, planned)) != sorted(map(_digest, expected)):
            raise IntegrityError('Group plan lost or duplicated discovery candidates')
        frozen = {'discovery_result_sha256': dependency, 'groups': groups}
        if _path(workspace, path).exists():
            # A crash after the file write may leave an unbound group file.
            # Recompute it from verified discovery and require exact equality.
            if read(_path(workspace, path)) != frozen:
                raise IntegrityError('Unbound frozen group file changed')
        else:
            save(_path(workspace, path), frozen)
        state['groups'][jid] = {'path': path, 'sha256': sha(_path(workspace, path)),
                                'discovery_result_sha256': dependency}
        save(Path(workspace) / 'candidate_state.json', state)
    if frozen['discovery_result_sha256'] != dependency:
        raise IntegrityError('Frozen group dependency changed')
    return frozen['groups']


def _condition_group(workspace, state, job, group):
    """Freeze one optional conditions plan per facts group, including None."""
    jid = job['job_id']
    tid = _task_key(jid, 'conditions', group)
    descriptors = state.setdefault('condition_groups', {})
    descriptor = descriptors.get(tid)
    facts = state['tasks'][_task_key(jid, 'facts', group)]
    if facts['status'] != 'complete':
        raise IntegrityError('Conditions require complete facts')
    if descriptor:
        frozen = read(_checked(workspace, descriptor['path'], descriptor['sha256']))
    else:
        from sentence_workflow import plan_conditions
        context = _group_at(_groups(workspace, state, job), group)
        result = read(_checked(workspace, facts['result_path'], facts['result_sha256']))
        effective = dict(deepcopy(job), frozen_context=deepcopy(context), active_stage='conditions',
                         facts_result_sha256=facts['result_sha256'],
                         discovery_result_sha256=facts['discovery_result_sha256'])
        plan = plan_conditions(effective, deepcopy(result), deepcopy(context['candidates'][0]))
        if plan is not None and (not isinstance(plan, dict) or any(
                not isinstance(plan.get(k), list) for k in
                ('candidates', 'sentences', 'candidate_contexts', 'context_units')) or
                plan['candidates'] != context['candidates']):
            raise ValueError('Invalid conditions group plan')
        frozen = {'group': plan, 'facts_result_sha256': facts['result_sha256'],
                  'discovery_result_sha256': facts['discovery_result_sha256'],
                  'facts_context_sha256': state['groups'][jid]['sha256']}
        if plan is None:
            required = any(
                record.get('endpoint_verification_required') or
                record.get('record_status') == 'semantic_pending' or
                (record.get('outcome_type') == 'conditional_loss' and
                 not record.get('values', {}).get('scope_condition'))
                for record in (item['record'] for item in result['accepted']))
            frozen['reason'] = ('required_context_unavailable_or_already_supplied'
                                if required else 'not_needed')
        path = f'groups/{jid}_conditions_{group:03d}.json'
        if _path(workspace, path).exists():
            if read(_path(workspace, path)) != frozen:
                raise IntegrityError('Unbound frozen conditions plan changed')
        else:
            save(_path(workspace, path), frozen)
        descriptors[tid] = {'path': path, 'sha256': sha(_path(workspace, path)),
                            'job_id': jid, 'group': group,
                            'facts_result_sha256': facts['result_sha256'],
                            'facts_context_sha256': state['groups'][jid]['sha256']}
        if plan is None:
            descriptors[tid]['reason'] = frozen['reason']
        save(Path(workspace) / 'candidate_state.json', state)
    if (frozen['facts_result_sha256'] != facts['result_sha256'] or
            frozen['discovery_result_sha256'] != facts['discovery_result_sha256'] or
            frozen['facts_context_sha256'] != state['groups'][jid]['sha256']):
        raise IntegrityError('Conditions plan dependency changed')
    return frozen['group']


def _material(workspace, state, entry):
    job = read(_path(workspace, f'jobs/{entry["job_id"]}.json'))
    candidates = None
    job['active_stage'] = entry['stage']
    if entry['stage'] in {'enrichment', 'facts', 'conditions'}:
        groups = _groups(workspace, state, job)
        frozen = (_condition_group(workspace, state, job, entry['group'])
                  if entry['stage'] == 'conditions' else _group_at(groups, entry['group']))
        if frozen is None:
            raise IntegrityError('Missing frozen conditions context')
        job['frozen_context'] = deepcopy(frozen)
        candidates = deepcopy(frozen['candidates'])
        job['discovery_result_sha256'] = entry['discovery_result_sha256']
        if entry['stage'] == 'conditions':
            job['facts_result_sha256'] = entry['facts_result_sha256']
    return job, candidates


def _validate(workspace, entry, job, candidates, validator):
    envelope = read(_checked(workspace, entry['response_path'], entry['response_sha256']))
    payload = parse_completion(envelope)
    job['active_stage'] = entry['stage']
    if entry['stage'] == 'discovery':
        if job.get('protocol') == 'sentence_v3':
            from sentence_v3 import validate_discovery
            result = validate_discovery(payload, job)
        else:
            result = discovery(payload, job)
    else:
        result = validator(payload, job, candidates)
    if not isinstance(result, dict) or any(not isinstance(result.get(k, []), list)
                                          for k in ('accepted', 'rejected', 'unresolved')):
        raise ValueError('Invalid validator result contract')
    if 'accepted' not in result or 'rejected' not in result:
        raise ValueError('Missing accepted/rejected result contract')
    path = f'results/{entry["job_id"]}_{entry["stage"]}_{entry["group"]:03d}.json'
    if _path(workspace, path).exists() and entry.get('result_sha256'):
        _checked(workspace, path, entry['result_sha256'])
    save(_path(workspace, path), result)
    entry.update(status='complete', result_path=path, result_sha256=sha(_path(workspace, path)),
                 accepted=len(result['accepted']), rejected=len(result['rejected']),
                 unresolved=len(result.get('unresolved', [])))
    entry.pop('failure_kind', None)


def _usage(workspace, entry):
    envelope = read(_checked(workspace, entry['response_path'], entry['response_sha256']))
    if isinstance(envelope, dict):
        usage = envelope.get('usage')
        entry['usage'] = ({k: v for k, v in usage.items()
                           if k in {'prompt_tokens', 'completion_tokens', 'total_tokens'}
                           and type(v) is int and v >= 0} if isinstance(usage, dict) else None)
        entry['returned_model'] = envelope.get('model')


def _finish(ledger_path, entry):
    if not entry.get('attempt_id') or entry.get('reused_from'):
        return
    ledger = read(ledger_path)
    attempt = next(a for a in ledger['attempts'] if a['attempt_id'] == entry['attempt_id'])
    if attempt['status'] == 'in_flight':
        details = {k: entry[k] for k in ('failure_kind', 'http_status', 'usage', 'returned_model')
                   if k in entry}
        if entry.get('http_status') in {401, 402, 403}:
            details['global_stop'] = f'provider_http_{entry["http_status"]}'
        budget.finish(ledger_path, entry['attempt_id'], entry['status'], **details)


def _recover(workspace, state, ledger_path, validator):
    paid_status = {a['attempt_id']: a['status'] for a in read(ledger_path)['attempts']}
    for entry in state['tasks'].values():
        if not entry.get('attempt_id'):
            continue
        if entry['status'] == 'complete':
            if paid_status.get(entry['attempt_id']) == 'in_flight':
                _finish(ledger_path, entry)
            continue
        if entry['status'] != 'complete':
            path = entry.get('response_path')
            if path and not entry.get('response_sha256') and _path(workspace, path).is_file():
                entry['response_sha256'] = sha(_path(workspace, path))
                entry['recovery'] = 'predeclared_response_file'
            if entry.get('response_sha256'):
                job, candidates = _material(workspace, state, entry)
                try:
                    _usage(workspace, entry)
                    _validate(workspace, entry, job, candidates, validator)
                except IntegrityError:
                    raise
                except (ValueError, TypeError, KeyError):
                    entry.update(status='invalid_response', failure_kind='saved_response_contract_invalid')
            elif entry['status'] == 'in_flight':
                entry.update(status='needs_attention', failure_kind='interrupted_request_outcome_unknown')
        save(Path(workspace) / 'candidate_state.json', state)
        _finish(ledger_path, entry)


def _record(workspace, tid, entry, job):
    return dict(deepcopy(entry), workspace=str(Path(workspace).resolve()),
                task_key=tid, scope=_scope(job))


def _unknown(attempt):
    return (attempt['status'] in {'in_flight', 'needs_attention'}
            or (attempt['status'] == 'http_failure' and attempt.get('http_status', 0) >= 500)
            or ('unknown' in (attempt.get('failure_kind') or '')))


def _refresh_index(index, ledger_path):
    """Map old unknowns conservatively. Never edit old state or ledger history."""
    unknowns, unmapped = [], []
    states = {}
    checked_states = set()
    for attempt in read(ledger_path)['attempts']:
        workspace = Path(attempt['workspace'])
        key = str(workspace)
        if key not in states:
            candidate = workspace / 'candidate_state.json'
            legacy = workspace / 'batch_state.json'
            states[key] = read(candidate if candidate.exists() else legacy) if (
                candidate.exists() or legacy.exists()) else {}
        source_state = states[key]
        entries = source_state.get('tasks', {})
        matches = [(tid, e) for tid, e in entries.items()
                   if e.get('attempt_id') == attempt['attempt_id']]
        if matches:
            tid, entry = matches[0]
            logical = entry.get('logical_id')
            if logical:
                if key not in checked_states:
                    _check_state(workspace, source_state)
                    checked_states.add(key)
                job = read(_path(workspace, f'jobs/{entry["job_id"]}.json'))
                if not entry.get('reused_from'):
                    index['tasks'][logical] = _record(workspace, tid, entry, job)
        if not _unknown(attempt):
            continue
        try:
            tid = matches[0][0] if matches else attempt['task']
            entry = matches[0][1] if matches else None
            # Saved complete responses have a known execution outcome, even if
            # the ledger finish was interrupted. Their logical task stays reserved.
            if entry and entry.get('response_sha256'):
                _checked(workspace, entry['response_path'], entry['response_sha256'])
                continue
            jid = (entry['job_id'] if entry else
                   re.split(r':(?:discovery|enrichment|facts|conditions)(?::\d+)?$', tid)[0])
            job = read(_path(workspace, f'jobs/{jid}.json'))
            unknowns.append({'attempt_id': attempt['attempt_id'], 'scope': _scope(job),
                             'workspace': str(workspace), 'task': tid})
        except IntegrityError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            unmapped.append({'attempt_id': attempt['attempt_id'], 'workspace': str(workspace),
                             'source_sha256': attempt.get('source_sha256')})
    index['unknowns'] = unknowns
    index['blocked_unknown_mapping'] = unmapped


def _reuse(workspace, entry, record):
    origin = Path(record['workspace'])
    for kind in ('request', 'response', 'result'):
        source = _checked(origin, record[kind + '_path'], record[kind + '_sha256'])
        target = f'{kind}s/reused_{entry["job_id"]}_{entry["stage"]}_{entry["group"]:03d}.json'
        dest = _path(workspace, target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and sha(dest) != record[kind + '_sha256']:
            raise IntegrityError('Reuse destination changed')
        if not dest.exists():
            dest.write_bytes(source.read_bytes())
        _checked(workspace, target, record[kind + '_sha256'])
        entry[kind + '_path'] = target
        entry[kind + '_sha256'] = record[kind + '_sha256']
    entry.update(status='complete', attempt_id=record['attempt_id'],
                 reused_from={'workspace': str(origin), 'task': record['task_key']})
    for key in ('accepted', 'rejected', 'unresolved', 'usage', 'returned_model'):
        if key in record:
            entry[key] = deepcopy(record[key])


def _legacy_discovery(workspace, entry, request, job, ledger_path, provider):
    """Reuse only byte-content-equivalent old discovery requests, then recheck.

    Provider identity and canonical request hash must both match. The old
    request, envelope and result files remain untouched, with all three hashes
    checked before copying. Old enrichment never enters this path.
    """
    if entry['stage'] != 'discovery' or job.get('protocol') == 'sentence_v3':
        return False
    parsed = urlsplit(provider)
    normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(),
                            parsed.path.rstrip('/'), '', ''))
    content_hash = budget.request_hash(request)
    paid_hash = budget.request_hash({'provider': normalized, 'request': request})
    for attempt in read(ledger_path)['attempts']:
        if (attempt['status'] != 'complete'
                or attempt.get('provider_identity') != normalized
                or attempt.get('content_sha256') != content_hash
                or attempt.get('request_sha256') != paid_hash):
            continue
        origin = Path(attempt['workspace'])
        old_state_path = origin / 'batch_state.json'
        if not old_state_path.is_file():
            continue
        old_state = read(old_state_path)
        matches = [(tid, old) for tid, old in old_state['tasks'].items()
                   if old.get('attempt_id') == attempt['attempt_id']
                   and old.get('stage') == 'discovery' and old.get('status') == 'complete']
        if not matches:
            continue
        tid, old = matches[0]
        files = {kind: _checked(origin, old[kind + '_path'], old[kind + '_sha256'])
                 for kind in ('request', 'response', 'result')}
        if budget.request_hash(read(files['request'])) != content_hash:
            raise IntegrityError('Legacy saved request differs from ledger content hash')
        for kind in ('request', 'response'):
            relative = f'{kind}s/legacy_{entry["job_id"]}_discovery.json'
            target = _path(workspace, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha(target) != old[kind + '_sha256']:
                raise IntegrityError('Legacy reuse destination changed')
            if not target.exists():
                target.write_bytes(files[kind].read_bytes())
            entry[kind + '_path'] = relative
            entry[kind + '_sha256'] = old[kind + '_sha256']
        entry.update(attempt_id=attempt['attempt_id'],
                     reused_from={'workspace': str(origin), 'task': tid,
                                  'kind': 'legacy_exact_discovery',
                                  'old_result_sha256': old['result_sha256']})
        _usage(workspace, entry)
        _validate(workspace, entry, job, None, None)
        return True
    return False


def _sentence_response_reuse(workspace, entry, request, job, candidates, ledger_path, provider, validator):
    """Revalidate exact successes or preserve definite failures; never send."""
    if job.get('protocol') != 'sentence_v3':
        return False
    parsed = urlsplit(provider)
    normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    content_hash = budget.request_hash(request)
    paid_hash = budget.request_hash({'provider': normalized, 'request': request})
    for attempt in read(ledger_path)['attempts']:
        if (attempt['status'] not in {'complete', 'http_failure'} or _unknown(attempt)
                or attempt.get('provider_identity') != normalized
                or attempt.get('requested_model') != request['model']
                or attempt.get('content_sha256') != content_hash
                or attempt.get('request_sha256') != paid_hash):
            continue
        origin = Path(attempt['workspace'])
        state_path = origin / 'candidate_state.json'
        if not state_path.is_file():
            continue
        source = read(state_path)
        if source.get('pipeline') != SENTENCE_PIPELINE:
            continue
        matches = [(tid, old) for tid, old in source['tasks'].items()
                   if old.get('attempt_id') == attempt['attempt_id']
                   and old.get('stage') == entry['stage'] and old.get('status') == attempt['status']
                   and not old.get('reused_from')]
        if len(matches) != 1:
            continue
        tid, old = matches[0]
        source_job = read(_path(origin, f'jobs/{old["job_id"]}.json'))
        if (source_job.get('source_sha256') != job.get('source_sha256')
                or source_job.get('paper_id') != job.get('paper_id')
                or _scope(source_job) != _scope(job)):
            continue
        failed = attempt['status'] == 'http_failure'
        files = {kind: _checked(origin, old[kind + '_path'], old[kind + '_sha256'])
                 for kind in (('request',) if failed else ('request', 'response', 'result'))}
        if budget.request_hash(read(files['request'])) != content_hash:
            raise IntegrityError('Saved response reuse request differs from paid content hash')
        for kind in (('request',) if failed else ('request', 'response')):
            name = f'{kind}s/revalidated_{entry["job_id"]}_{entry["stage"]}_{entry["group"]:03d}.json'
            target = _path(workspace, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha(target) != old[kind + '_sha256']:
                raise IntegrityError('Revalidation destination changed')
            if not target.exists():
                target.write_bytes(files[kind].read_bytes())
            entry[kind + '_path'], entry[kind + '_sha256'] = name, old[kind + '_sha256']
        entry.update(attempt_id=attempt['attempt_id'], reused_from={
            'workspace': str(origin.resolve()), 'task': tid,
            'kind': 'known_http_failure_preserved' if failed else 'exact_response_revalidated',
            'old_result_sha256': old.get('result_sha256')})
        if failed:
            entry.update(status='http_failure', http_status=old.get('http_status'),
                         failure_kind='previous_http_failure_preserved')
            return True
        _usage(workspace, entry)
        try:
            _validate(workspace, entry, job, candidates, validator)
        except IntegrityError:
            raise
        except (ValueError, TypeError, KeyError) as error:
            entry.update(status='invalid_response', failure_kind='saved_response_contract_invalid',
                         exception_type=type(error).__name__)
        return True
    return False


def run(workspace, config, ledger_path, request_builder, enrichment_validator,
        live=False, env_file=None, client=None, max_new_requests=None,
        resume_operator_pause=False, phase='pilot', on_progress=None, network_route='environment'):
    """Return candidate_state.json state; live=False permits only offline work.

    on_progress(workspace) runs after each paper and in finally. Integrity and
    callback errors propagate. max_new_requests=0 is an offline invocation cap.
    No client or credentials are constructed until a permitted send is needed.
    """
    check_config(config)
    if phase not in {'pilot', 'full'}:
        raise ValueError('phase must be pilot or full')
    if network_route not in {'environment', 'direct'}:
        raise ValueError('Invalid network route')
    if max_new_requests is not None and (type(max_new_requests) is not int or max_new_requests < 0):
        raise ValueError('Nonnegative invocation request limit required')
    workspace, ledger_path = Path(workspace).resolve(), Path(ledger_path).resolve()
    read(ledger_path)  # The authorized ledger must already exist.
    index_path = Path(str(ledger_path) + '.candidate_index.json')
    state_path = workspace / 'candidate_state.json'
    actual_client, secret = client, None
    with ExitStack() as stack:
        stack.enter_context(RunLock(str(ledger_path) + '.candidate_run.lock'))
        stack.enter_context(RunLock(workspace / '.candidate_run.lock'))
        manifest = _verify_workspace(workspace)
        if manifest.get('pipeline') not in {'molgluedb_candidates_v2', SENTENCE_PIPELINE}:
            raise IntegrityError('Expected a v2 or sentence_v3 MolGlueDB manifest')
        sentence = manifest['pipeline'] == SENTENCE_PIPELINE
        identity = _digest({'manifest': sha(workspace / 'manifest.json'),
                            'config': {k: v for k, v in config.items()
                                       if k not in {'max_requests', 'max_reserved_tokens'}},
                            'budget_path': str(ledger_path), 'network_route': network_route})
        reference_path = workspace / 'acceptance_reference.json'
        reference_hash = sha(reference_path) if reference_path.is_file() else None
        state = read(state_path) if state_path.exists() else {
            'version': 3 if sentence else 2, 'pipeline': manifest['pipeline'], 'identity': identity,
            'config': deepcopy(config), 'reference_sha256': reference_hash, 'network_route': network_route,
            'budget_path': str(ledger_path), 'tasks': {}, 'attempts': [],
            'groups': {}, 'stop_reason': None, 'audit': []}
        if (state['identity'] != identity or state['budget_path'] != str(ledger_path) or
                state.get('pipeline') != manifest['pipeline']):
            raise IntegrityError('Workspace/config/budget identity changed')
        if state.get('config') != config:
            raise IntegrityError('Stored config changed')
        if state.get('reference_sha256') != reference_hash:
            raise IntegrityError('Acceptance reference changed after first run')
        _check_state(workspace, state)
        index = read(index_path) if index_path.exists() else {'version': 2, 'tasks': {}}
        sent = 0

        def persist():
            save(state_path, state)
            save(index_path, index)

        def progress():
            if on_progress is not None:
                on_progress(workspace)

        def process(job, stage, group=0, candidates=None, dependency=None, frozen=None):
            nonlocal sent, actual_client, secret
            jid = job['job_id']
            tid = _task_key(jid, stage, group)
            previous = state['tasks'].get(tid)
            if previous and previous['status'] not in {'pending', 'blocked_unknown_scope',
                                                       'blocked_unknown_mapping'}:
                return True  # Completed and uncertain tasks are never resent.
            effective_job = deepcopy(job)
            effective_job['active_stage'] = stage
            if frozen is not None:
                effective_job['frozen_context'] = deepcopy(frozen)
            if sentence:
                effective_job['discovery_result_sha256'] = dependency
                if stage == 'conditions':
                    effective_job['facts_result_sha256'] = state['tasks'][_task_key(jid, 'facts', group)]['result_sha256']
            request = request_builder(workspace, effective_job, stage, config,
                                      candidates=deepcopy(candidates), discovery_hash=dependency)
            logical = _logical(effective_job, stage, candidates, request, config, manifest)
            entry = _entry(jid, stage, group, dependency)
            if sentence and stage in {'facts', 'conditions'}:
                descriptor = (state['condition_groups'][tid] if stage == 'conditions' else state['groups'][jid])
                entry['context_plan_sha256'] = descriptor['sha256']
                if stage == 'conditions':
                    entry['facts_result_sha256'] = descriptor['facts_result_sha256']
            entry['logical_id'] = logical
            record = index['tasks'].get(logical)
            if record and record['status'] == 'complete':
                _reuse(workspace, entry, record)
                state['tasks'][tid] = entry
                persist()
                return True
            if record:
                entry.update(status='needs_attention', failure_kind='logical_task_already_reserved')
                state['tasks'][tid] = entry
                persist()
                return True
            if sentence and _sentence_response_reuse(workspace, entry, request, effective_job,
                    candidates, ledger_path, config['base_url'], enrichment_validator):
                state['tasks'][tid] = entry
                index['tasks'][logical] = _record(workspace, tid, entry, job)
                persist()
                return True
            if not sentence and _legacy_discovery(workspace, entry, request, effective_job,
                                 ledger_path, config['base_url']):
                state['tasks'][tid] = entry
                index['tasks'][logical] = _record(workspace, tid, entry, job)
                persist()
                return True
            scope = _scope(job)
            blocked = [a['attempt_id'] for a in index.get('unknowns', [])
                       if _overlaps(scope, a['scope'])]
            if blocked:
                entry.update(status='blocked_unknown_scope', blocked_attempt_ids=blocked)
                state['tasks'][tid] = entry
                persist()
                return True
            unmapped = index.get('blocked_unknown_mapping', [])
            if unmapped and (phase == 'full' or any(
                    a.get('source_sha256') == scope['source_sha256'] for a in unmapped)):
                # Full runs require every legacy unknown to be mapped. Pilots
                # on verified unrelated sources retain the mapping gaps in state.
                entry.update(status='blocked_unknown_mapping')
                state['tasks'][tid] = entry
                state['stop_reason'] = 'blocked_unknown_mapping'
                persist()
                return False
            stop = read(ledger_path).get('global_stop')
            if stop:
                state['stop_reason'] = stop
                return False
            if not live:
                state['stop_reason'] = 'live_required'
                return False
            if max_new_requests is not None and sent >= max_new_requests:
                state['stop_reason'] = 'invocation_request_limit'
                return False
            attempts = [a for a in read(ledger_path)['attempts']
                        if a['workspace'] == str(workspace)]
            tokens = reserve_tokens(request, config)
            if len(attempts) >= config['max_requests']:
                state['stop_reason'] = 'workspace_request_budget'
                return False
            if sum(a['reserved_tokens'] for a in attempts) + tokens > config['max_reserved_tokens']:
                state['stop_reason'] = 'workspace_token_reservation_budget'
                return False
            ledger = read(ledger_path)
            if (len(ledger['attempts']) >= ledger['max_requests'] or
                    sum(a['reserved_tokens'] for a in ledger['attempts']) + tokens > ledger['max_reserved_tokens']):
                state['stop_reason'] = 'Shared request/token budget exhausted'
                return False
            if actual_client is None:
                from credentials import load_key
                from candidate_transport import DiagnosticStreamingClient
                secret = load_key(config['api_key_env'], env_file)
                actual_client = DiagnosticStreamingClient(config, secret, network_route)
            # Write request and intended response location before reservation.
            nonce = uuid.uuid4().hex
            request_path = f'requests/{nonce}.json'
            response_path = f'responses/{nonce}.json'
            save(_path(workspace, request_path), request)
            try:
                attempt = budget.reserve(ledger_path, workspace, tid, request, tokens,
                                         provider_identity=config['base_url'])
            except ValueError as exc:
                # Ledger exceptions contain only fixed local diagnostics.
                state['stop_reason'] = str(exc)
                return False
            sent += 1
            entry.update(status='in_flight', attempt_id=attempt['attempt_id'],
                         request_path=request_path, request_sha256=sha(_path(workspace, request_path)),
                         response_path=response_path, started=time.time())
            state['tasks'][tid] = entry
            state['attempts'].append(attempt['attempt_id'])
            index['tasks'][logical] = _record(workspace, tid, entry, job)
            persist()
            try:
                envelope = actual_client.complete(deepcopy(request))
                if secret:
                    envelope = json.loads(json.dumps(envelope, ensure_ascii=False).replace(secret, '[REDACTED]'))
                save(_path(workspace, response_path), envelope)
                entry['response_sha256'] = sha(_path(workspace, response_path))
                persist()  # Keep the response even if parsing/validation fails.
                _usage(workspace, entry)
                _validate(workspace, entry, effective_job, candidates, enrichment_validator)
            except IntegrityError:
                raise
            except RequestFailure as exc:
                unknown = exc.ambiguous or (exc.http_status is not None and exc.http_status >= 500)
                entry.update(status='needs_attention' if unknown else 'http_failure',
                             failure_kind='http_server_outcome_unknown' if unknown and exc.http_status else exc.kind,
                             http_status=exc.http_status)
            except Exception as exc:
                entry.update(status='invalid_response' if entry.get('response_sha256') else 'needs_attention',
                             failure_kind='saved_response_contract_invalid' if entry.get('response_sha256')
                             else 'request_outcome_unknown', exception_type=type(exc).__name__)
            finally:
                if entry['status'] == 'in_flight':
                    entry.update(status='needs_attention', failure_kind='interrupted_request_outcome_unknown')
                entry['finished'] = time.time()
                diagnostic = getattr(getattr(actual_client, 'opener', None), 'diagnostic', None)
                if diagnostic:
                    entry['transport_diagnostic'] = deepcopy(diagnostic)
                events = getattr(actual_client, 'wire_events', None)
                if events:
                    encoded = json.dumps(events, ensure_ascii=False)
                    if secret:
                        encoded = encoded.replace(secret, '[REDACTED]')
                    trace_path = response_path + '.events.json'
                    save(_path(workspace, trace_path), json.loads(encoded))
                    entry['stream_events_path'] = trace_path
                    entry['stream_events_sha256'] = sha(_path(workspace, trace_path))
                index['tasks'][logical] = _record(workspace, tid, entry, job)
                persist()
                _finish(ledger_path, entry)
                _refresh_index(index, ledger_path)
                persist()
                print(json.dumps({'paper_id': job['paper_id'], 'stage': stage,
                    'group': group, 'status': entry['status'], 'accepted': entry.get('accepted'),
                    'rejected': entry.get('rejected'), 'new_requests_this_run': sent},
                    ensure_ascii=False), flush=True)
            stopped = read(ledger_path).get('global_stop')
            if stopped:
                state['stop_reason'] = stopped
                persist()
            return not bool(stopped)

        try:
            _recover(workspace, state, ledger_path, enrichment_validator)
            _refresh_index(index, ledger_path)
            state['blocked_unknown_mapping'] = deepcopy(index['blocked_unknown_mapping'])
            if resume_operator_pause:
                with budget.ledger_lock(ledger_path):
                    ledger = read(ledger_path)
                    if ledger.get('global_stop') == 'operator_pause':
                        event = {'event': 'resume_operator_pause', 'time': time.time(),
                                 'workspace': str(workspace)}
                        _audit(str(ledger_path) + '.candidate_run.lock', event)
                        state['audit'].append(event)
                        ledger.setdefault('operator_events', []).append({
                            'action': 'resume', 'reason': 'candidate_runtime explicit resume_operator_pause',
                            'time': event['time'], 'requests_reserved_at_action': len(ledger['attempts'])})
                        ledger.pop('global_stop')
                        save(ledger_path, ledger)
            state['stop_reason'] = None
            persist()
            if phase == 'full' and state['blocked_unknown_mapping']:
                state['stop_reason'] = 'blocked_unknown_mapping'
                return state
            jobs = {jid: read(_path(workspace, f'jobs/{jid}.json')) for jid in manifest['job_ids']}
            # Group by paper even when the supplied job list is interleaved.
            for paper in manifest['papers']:
                paper_id = paper['paper_id'] if isinstance(paper, dict) else paper
                try:
                    for jid, job in jobs.items():
                        if job['paper_id'] != paper_id:
                            continue
                        if not process(job, 'discovery'):
                            return state
                        discovered = state['tasks'][jid + ':discovery']
                        if discovered['status'] != 'complete':
                            continue
                        groups = _groups(workspace, state, job)
                        for n, frozen in enumerate(groups):
                            stage = 'facts' if sentence else 'enrichment'
                            if not process(job, stage, n, frozen['candidates'],
                                           discovered['result_sha256'], frozen):
                                return state
                            if sentence:
                                facts = state['tasks'][_task_key(jid, 'facts', n)]
                                if facts['status'] != 'complete':
                                    continue
                                condition = _condition_group(workspace, state, job, n)
                                if condition is not None and not process(
                                        job, 'conditions', n, condition['candidates'],
                                        discovered['result_sha256'], condition):
                                    return state
                finally:
                    persist()
                    progress()
            return state
        except BaseException as exc:
            state['stop_reason'] = 'interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'runtime_error'
            state['exception_type'] = type(exc).__name__
            raise
        finally:
            persist()
            progress()
