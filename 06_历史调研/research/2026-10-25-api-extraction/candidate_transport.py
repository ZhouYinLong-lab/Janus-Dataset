"""Explicit network route and bounded diagnostics; never retry a paid POST."""
import time
import urllib.request

from api import NoRedirect
from stream_http import StreamingClient


class DiagnosticResponse:
    def __init__(self, response, owner):
        self.response, self.owner = response, owner

    def __getattr__(self, name):
        return getattr(self.response, name)

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def _read(self, method, *args):
        self.owner.diagnostic['phase'] = 'read'
        try:
            data = getattr(self.response, method)(*args)
            self.owner.diagnostic['bytes_read'] += len(data)
            if data and 'first_data_seconds' not in self.owner.diagnostic:
                self.owner.diagnostic['first_data_seconds'] = round(time.monotonic()-self.owner.started, 3)
            return data
        except Exception as error:
            self.owner.record_error(error)
            raise

    def read(self, *args):
        return self._read('read', *args)

    def readline(self, *args):
        return self._read('readline', *args)


class DiagnosticOpener:
    def __init__(self, delegate):
        self.delegate = delegate
        self.started = time.monotonic()
        self.diagnostic = {}

    def record_error(self, error):
        reason = getattr(error, 'reason', None)
        number = getattr(reason, 'errno', getattr(error, 'errno', None))
        self.diagnostic.update(error_type=type(error).__name__, reason_type=type(reason).__name__,
                               errno=number if type(number) is int else None)

    def open(self, *args, **kwargs):
        self.started = time.monotonic()
        self.diagnostic = {'phase': 'open', 'bytes_read': 0}
        try:
            response = self.delegate.open(*args, **kwargs)
            self.diagnostic['headers_seconds'] = round(time.monotonic()-self.started, 3)
            self.diagnostic['http_status'] = getattr(response, 'status', None)
            return DiagnosticResponse(response, self)
        except Exception as error:
            self.record_error(error)
            raise


class DiagnosticStreamingClient(StreamingClient):
    def __init__(self, config, key, route='environment'):
        if route not in {'environment', 'direct'}:
            raise ValueError('Network route must be environment or direct')
        super().__init__(config, key)
        if route == 'direct':
            self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.opener = DiagnosticOpener(self.opener)
        self.route = route

    def complete(self, payload):
        started = time.monotonic()
        try:
            return super().complete(payload)
        finally:
            self.opener.diagnostic['elapsed_seconds'] = round(time.monotonic()-started, 3)
            self.opener.diagnostic['route'] = self.route
