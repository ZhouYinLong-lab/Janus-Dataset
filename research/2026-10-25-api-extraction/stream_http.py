"""Bounded Chat Completions SSE assembly. No automatic retry or downgrade call."""
import json
import time
import urllib.error
import urllib.request

from api import HTTPClient, RequestFailure


def assemble(lines, trace):
    parts = []; usage = None; model = None; response_id = None; finish = None
    data = []; size = 0; done = False; start = time.monotonic()

    def event(value):
        nonlocal usage, model, response_id, finish, done
        if value == '[DONE]':
            done = True; return
        item = json.loads(value)
        if not isinstance(item, dict) or item.get('error'):
            raise ValueError('Invalid stream event')
        if item.get('id'):
            if response_id is not None and item['id'] != response_id:
                raise ValueError('Stream response identity changed')
            response_id = item['id']
        model = item.get('model', model)
        if isinstance(item.get('usage'), dict):
            usage = item['usage']
        choices = item.get('choices', [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise ValueError('Expected one streaming choice')
        for c in choices:
            if c.get('index', 0) != 0:
                raise ValueError('Unexpected choice index')
            delta = c.get('delta', {})
            if delta.get('tool_calls') or delta.get('function_call') or delta.get('refusal'):
                raise ValueError('Unexpected non-text generation')
            content = delta.get('content')
            if content is not None:
                if not isinstance(content, str):
                    raise ValueError('Non-text stream delta')
                parts.append(content)
            if c.get('finish_reason') is not None:
                finish = c['finish_reason']

    try:
        for raw in lines:
            size += len(raw)
            if size > 16_000_000 or len(raw) > 2_000_000 or time.monotonic() - start > 600:
                raise ValueError('Stream size/time cap')
            line = raw.decode('utf-8').rstrip('\r\n')
            if line.startswith('data:'):
                data.append(line[5:].lstrip(' '))
            elif not line and data:
                value = '\n'.join(data); data.clear(); trace.append(value); event(value)
                if done: break
        if data and not done:
            value = '\n'.join(data); trace.append(value); event(value)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise RequestFailure('invalid_or_incomplete_stream', ambiguous=True) from None
    if not done or finish is None:
        raise RequestFailure('incomplete_stream', ambiguous=True)
    return {'id': response_id, 'model': model, 'choices': [{'index': 0, 'finish_reason': finish,
            'message': {'role': 'assistant', 'content': ''.join(parts)}}], 'usage': usage,
            'transport': 'assembled_sse'}


class StreamingClient(HTTPClient):
    def __init__(self, config, key):
        super().__init__(config, key); self.wire_events = []

    def complete(self, payload):
        self.wire_events = []
        if not payload.get('stream'):
            return super().complete(payload)
        request = urllib.request.Request(self.config['base_url'].rstrip('/') + '/chat/completions',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json',
                     'Accept': 'text/event-stream'}, method='POST')
        try:
            with self.opener.open(request, timeout=self.config['timeout_seconds']) as response:
                if 'application/json' in response.headers.get('Content-Type', '').lower():
                    raw = response.read(16_000_001)
                    if len(raw) > 16_000_000:
                        raise RequestFailure('response_too_large', ambiguous=True)
                    envelope = json.loads(raw.decode('utf-8'))
                    envelope['transport'] = 'json_returned_for_stream_request'
                    return envelope
                return assemble(iter(response.readline, b''), self.wire_events)
        except urllib.error.HTTPError as exc:
            raise RequestFailure('http_error', exc.code, ambiguous=False) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise RequestFailure('network_outcome_unknown', ambiguous=True) from None
        except (ValueError, UnicodeError, TypeError):
            raise RequestFailure('invalid_stream_http_response', ambiguous=True) from None
