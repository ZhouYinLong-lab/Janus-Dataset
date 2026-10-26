"""Route isolation, redacted diagnostics and one-shot ledger recovery."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from candidate_transport import DiagnosticStreamingClient, DiagnosticOpener
from candidate_recovery import resume_network_after_diagnosis
from corpus import read, save


class Response(io.BytesIO):
    status = 200


class TransportTests(unittest.TestCase):
    def test_direct_route_does_not_change_environment_or_retry(self):
        import os
        original = dict(os.environ)
        with patch('candidate_transport.urllib.request.build_opener') as build:
            client = DiagnosticStreamingClient({}, 'not-a-real-key', 'direct')
        self.assertEqual(original, dict(os.environ))
        self.assertEqual(build.call_args.args[0].proxies, {})
        build.return_value.open.assert_not_called()
        self.assertEqual(client.route, 'direct')

    def test_open_and_read_diagnostics_record_no_exception_message(self):
        class Delegate:
            def open(self, *args, **kwargs):
                return Response(b'abc\n')
        opener = DiagnosticOpener(Delegate())
        with opener.open('ignored') as response:
            self.assertEqual(response.readline(), b'abc\n')
        self.assertEqual(opener.diagnostic['bytes_read'], 4)
        self.assertIn('headers_seconds', opener.diagnostic)
        self.assertIn('first_data_seconds', opener.diagnostic)
        opener.record_error(OSError('do-not-log-this-message'))
        self.assertNotIn('do-not-log-this-message', str(opener.diagnostic))

    def test_diagnosed_recovery_preserves_attempts_and_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); ledger = root/'ledger.json'; diag = root/'diagnostic.json'
            attempts = [{'status': 'needs_attention', 'attempt_id': 'kept'}]
            save(ledger, {'global_stop': 'two_consecutive_network_failures', 'attempts': attempts,
                          'max_requests': 200})
            save(diag, {'status': 'reachable', 'generation_requests': 0,
                        'configured_model_listed': True, 'base_url': 'https://example.invalid/v1',
                        'model': 'm', 'route': 'direct'})
            config = {'base_url': 'https://example.invalid/v1', 'model': 'm'}
            resume_network_after_diagnosis(ledger, diag, config)
            self.assertEqual(read(ledger)['attempts'], attempts)
            self.assertEqual(read(ledger)['max_requests'], 200)
            restored = read(ledger); restored['global_stop'] = 'two_consecutive_network_failures'
            save(ledger, restored)
            with self.assertRaises(ValueError):
                resume_network_after_diagnosis(ledger, diag, config)

    def test_failed_diagnosis_does_not_clear_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); ledger = root/'ledger.json'; diag = root/'diagnostic.json'
            save(ledger, {'global_stop': 'two_consecutive_network_failures', 'attempts': []})
            save(diag, {'status': 'failed', 'generation_requests': 0})
            with self.assertRaises(ValueError):
                resume_network_after_diagnosis(ledger, diag, {'base_url': 'x', 'model': 'm'})
            self.assertEqual(read(ledger)['global_stop'], 'two_consecutive_network_failures')


if __name__ == '__main__':
    unittest.main()
