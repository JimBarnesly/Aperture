from pathlib import Path
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('debrid', ROOT / 'movies-kodi/resources/lib/debrid.py')
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)
PAIR = {'client_id': 'app-user', 'client_secret': 'secret-fixture'}
TOKEN = {'access_token': 'access-fixture', 'refresh_token': 'refresh-fixture', 'token_type': 'Bearer', 'expires_in': 3600}
DEVICE = {'device_code': 'device-fixture', 'user_code': 'ABC123', 'interval': 5, 'expires_in': 60, 'verification_url': 'https://real-debrid.com/device'}


class DebridTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = rd.Store(self.tmp.name)
        self.now = 1000
        self.calls = []
        self.responses = []
        self.client = rd.Client(self.store, self.transport, lambda: self.now)

    def transport(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def wait(self, seconds):
        self.now += seconds
        return False

    def signed_in(self, expires_at=2000):
        self.store.save(dict(PAIR, access_token='access-fixture', refresh_token='refresh-fixture', expires_at=expires_at))

    def test_device_flow_pending_then_success(self):
        self.responses = [DEVICE, rd.DebridError('denied'), PAIR, TOKEN]
        with self.store.locked():
            session = self.client.begin('public-app')
            self.client.connect(session, self.wait, lambda: False)
        self.assertEqual(self.now, 1010)
        self.assertIn('new_credentials=yes', self.calls[0][0][1])
        self.assertIn('device/credentials?', self.calls[1][0][1])
        self.assertEqual(self.calls[-1][0][2]['grant_type'], rd.GRANT)
        self.assertEqual(self.store.load()['refresh_token'], 'refresh-fixture')
        self.assertEqual(os.stat(self.store.directory).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(Path(self.store.directory) / 'credentials.json').st_mode & 0o777, 0o600)

    def test_cancel_never_exchanges_or_saves(self):
        self.responses = [DEVICE]
        session = self.client.begin('public-app')
        with self.assertRaisesRegex(rd.DebridError, 'cancelled'):
            self.client.connect(session, self.wait, lambda: True)
        self.assertIsNone(self.store.load())
        self.assertEqual(len(self.calls), 1)

    def test_cancel_during_poll_does_not_exchange(self):
        self.responses = [DEVICE, PAIR]
        session = self.client.begin('public-app')
        with self.assertRaises(rd.DebridError):
            self.client.connect(session, self.wait, lambda: len(self.calls) == 2)
        self.assertIsNone(self.store.load())
        self.assertEqual(len(self.calls), 2)

    def test_unsupported_storage_fails_closed(self):
        with patch.object(rd.os, 'name', 'nt'):
            with self.assertRaisesRegex(rd.DebridError, 'storage'):
                with self.store.locked():
                    self.fail('Unsupported platform accepted')

    def test_expiry_during_poll_does_not_exchange(self):
        def transport(*args, **kwargs):
            self.now = 2000
            return PAIR
        self.client.transport = transport
        with self.assertRaisesRegex(rd.DebridError, 'expired'):
            self.client.connect(dict(client_id='app', device_code='device', interval=5, expires_at=1060), self.wait, lambda: False)
        self.assertIsNone(self.store.load())

    def test_cancel_after_exchange_never_saves(self):
        self.responses = [DEVICE, PAIR, TOKEN]
        session = self.client.begin('public-app')
        with self.assertRaises(rd.DebridError):
            self.client.connect(session, self.wait, lambda: len(self.calls) == 3)
        self.assertIsNone(self.store.load())

    def test_expiry_bounded_and_preserves_existing_credentials(self):
        self.signed_in()
        session = dict(client_id='app', device_code='device', interval=5, expires_at=1006)
        self.responses = [rd.DebridError('denied')]
        with self.assertRaisesRegex(rd.DebridError, 'expired'):
            self.client.connect(session, self.wait, lambda: False)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.store.load()['access_token'], 'access-fixture')

    def test_rate_limit_does_not_spin(self):
        self.responses = [rd.DebridError('rate')]
        with self.assertRaisesRegex(rd.DebridError, 'Wait'):
            self.client.connect(dict(client_id='app', device_code='device', interval=5, expires_at=1060), self.wait, lambda: False)
        self.assertEqual(len(self.calls), 1)

    def test_refresh_precedes_download_list(self):
        self.signed_in(1001)
        self.responses = [TOKEN, []]
        self.assertEqual(self.client.downloads(2), [])
        self.assertEqual(self.calls[0][0][2]['code'], 'refresh-fixture')
        self.assertEqual(self.calls[1][1]['token'], 'access-fixture')
        self.assertIn('page=2&limit=60', self.calls[1][0][1])

    def test_revoked_is_not_retried(self):
        self.signed_in()
        self.responses = [rd.DebridError('auth')]
        with self.assertRaises(rd.DebridError):
            self.client.downloads()
        self.assertEqual(len(self.calls), 1)

    def test_download_resolves_current_account_id_only(self):
        self.signed_in()
        self.responses = [[{'id': 'one', 'download': 'https://cdn.example/video?token=private'}]]
        self.assertEqual(self.client.playback('one', 1), 'https://cdn.example/video?token=private')
        self.responses = [[{'id': 'two', 'download': 'https://cdn.example/video'}]]
        with self.assertRaisesRegex(rd.DebridError, 'no longer'):
            self.client.playback('one', 1)

    def test_link_resolution_uses_post_not_remote_traffic(self):
        self.signed_in()
        self.responses = [{'download': 'https://cdn.example/video'}]
        self.client.resolve_link('https://host.example/owned-film')
        self.assertEqual(self.calls[0][0], ('POST', rd.API + 'unrestrict/link', {'link': 'https://host.example/owned-film', 'remote': '0'}))

    def test_unsafe_urls_rejected(self):
        for value in ['http://cdn.example/x', 'file:///etc/passwd', 'https://a:b@host.example/x', 'https://127.0.0.1/x', 'https://127.1/x', 'https://localhost./x', 'https://0x7f.1/x', 'https://[::1]/x', 'https://a.local/x', 'https://host.example/x|Header=secret', 'https://host.example/x\n', 'https://host.example:8443/x']:
            with self.subTest(value=value), self.assertRaises(rd.DebridError):
                rd.web_url(value)

    def test_malformed_device_and_tokens_rejected(self):
        for value in [dict(DEVICE, verification_url='https://attacker.example/device'), dict(DEVICE, interval=float('nan')), dict(DEVICE, expires_in=-1), {}, []]:
            self.responses = [value]
            with self.assertRaises(rd.DebridError):
                self.client.begin('app')
        self.responses = [dict(TOKEN, access_token='a\nAuthorization: injected')]
        with self.assertRaises(rd.DebridError):
            self.client.exchange(PAIR, 'code')

    def test_missing_client_id_makes_no_request(self):
        with self.assertRaises(rd.DebridError):
            self.client.begin('')
        self.assertEqual(self.calls, [])

    def test_store_rejects_unsafe_permissions_and_symlinks(self):
        self.signed_in()
        path = Path(self.store.directory) / 'credentials.json'
        os.chmod(path, 0o644)
        with self.assertRaises(rd.DebridError):
            self.store.load()
        path.unlink()
        path.symlink_to(Path(self.tmp.name) / 'elsewhere')
        with self.assertRaises(OSError):
            self.store.load()
        path.unlink()
        os.chmod(self.store.directory, 0o755)
        with self.assertRaises(rd.DebridError):
            self.store.load()

    def test_exclusive_lock(self):
        with self.store.locked():
            with self.assertRaisesRegex(rd.DebridError, 'Another'):
                with rd.Store(self.tmp.name).locked():
                    self.fail('Second lock acquired')

    def test_disconnect_removes_local_secret_only(self):
        self.signed_in()
        self.store.clear()
        self.assertIsNone(self.store.load())
        self.assertEqual(self.calls, [])

    def test_transport_errors_never_include_secrets(self):
        for status in (301, 401, 403, 429, 500):
            with patch.object(rd, 'build_opener') as opener:
                opener.return_value.open.side_effect = HTTPError('https://secret.example', status, 'secret-body', {}, None)
                with self.assertRaises(rd.DebridError) as caught:
                    rd.request('GET', rd.API + 'downloads', token='secret-token')
                self.assertNotIn('secret', str(caught.exception))
        self.assertIsNone(rd.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://attacker.example'))


if __name__ == '__main__':
    unittest.main()
