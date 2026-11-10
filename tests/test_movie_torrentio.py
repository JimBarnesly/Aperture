"""Synthetic-only tests; never contact a provider or use account credentials."""
import importlib.util
from pathlib import Path
import unittest
import os
import tempfile
import io
import json
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'movies-kodi/resources/lib/torrentio.py'


def load():
    if not MODULE.exists():
        return None
    spec = importlib.util.spec_from_file_location('torrentio_test', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t = load()
TOKEN = 'SYNTHETIC1234567890'
MANIFEST = 'https://torrentio.strem.fun/realdebrid=' + TOKEN + '|debridoptions=nodownloadlinks/manifest.json'


class ConfigurationTests(unittest.TestCase):
    def test_oauth_token_is_encoded_as_one_config_and_resolver_segment(self):
        self.assertTrue(hasattr(t.Config, 'from_token'), 'Native OAuth config builder missing')
        token = 'SYNTHETIC.oauth~token+/ABC_-123'
        config = t.Config.from_token(token)
        self.assertEqual(config._token, token)
        self.assertIn('%2F', config._manifest)
        from urllib.parse import quote
        resolver = t.ORIGIN + '/resolve/realdebrid/' + quote(token, safe='') + '/' + 'a' * 40 + '/null/undefined'
        self.assertEqual(len(t.parse_streams({'streams': [{'name': '[RD+]', 'url': resolver}]}, config)), 1)
        for bad in ['', 'short', 'a' * 4097, 'token|injection', 'token%2Fencoded', 'token?query', 'token\ncontrol']:
            with self.assertRaises(t.ProviderError):
                t.Config.from_token(bad)

    def test_only_strict_rd_configured_manifest_can_build_movie_lookup(self):
        self.assertIsNotNone(t, 'Torrentio adapter is missing')
        config = t.Config(MANIFEST)
        self.assertEqual(config.lookup('tt1234567'), MANIFEST.removesuffix('/manifest.json') + '/stream/movie/tt1234567.json')
        invalid = [MANIFEST.replace('https:', 'http:'), MANIFEST.replace('torrentio.strem.fun', 'evil.example'),
                   MANIFEST.replace('torrentio.strem.fun', 'torrentio.strem.fun@evil.example'),
                   MANIFEST + '?key=value', MANIFEST + '#fragment',
                   MANIFEST.replace('realdebrid=', 'alldebrid='), MANIFEST.replace(TOKEN, ''),
                   MANIFEST.replace('nodownloadlinks', 'p2p'), MANIFEST.replace('realdebrid=', 'realdebrid=x|realdebrid='),
                   MANIFEST.replace(TOKEN, TOKEN + '%0a'), MANIFEST.replace(TOKEN, TOKEN + '%252f'),
                   'https://torrentio.strem.fun/manifest.json']
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(t.ProviderError) as error:
                t.Config(url)
            self.assertNotIn(TOKEN, str(error.exception))
        for identifier in ['tt1/../../x', 'tt1234567\n', 'https://evil.example', 'tt1']:
            with self.assertRaises(t.ProviderError):
                config.lookup(identifier)
        self.assertNotIn(TOKEN, repr(config))


class StorageTests(unittest.TestCase):
    def test_native_consent_persists_marker_not_a_token_copy(self):
        self.assertTrue(hasattr(t.Store, 'enable_native'), 'Native consent storage missing')
        with tempfile.TemporaryDirectory() as root:
            store = t.Store(root)
            store.enable_native()
            self.assertEqual(store.load(), 'rd-oauth-v1')
            saved = Path(root) / 'torrentio-private/connection'
            self.assertEqual(saved.read_text(), 'rd-oauth-v1')
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            store.clear()
            self.assertIsNone(store.load())

    def test_private_atomic_import_load_disconnect_with_symlink_refusal(self):
        self.assertTrue(hasattr(t, 'Store'), 'Private configuration store is missing')
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'input.txt'
            source.write_text(MANIFEST + '\n')
            source.chmod(0o600)
            store = t.Store(root)
            self.assertIsNone(store.load())
            store.import_file(str(source))
            self.assertEqual(store.load().lookup('tt1234567'), t.Config(MANIFEST).lookup('tt1234567'))
            private = Path(root) / 'torrentio-private'
            self.assertEqual(private.stat().st_mode & 0o777, 0o700)
            self.assertEqual((private / 'connection').stat().st_mode & 0o777, 0o600)
            source.chmod(0o644)
            with self.assertRaises(t.ProviderError):
                store.import_file(str(source))
            source.chmod(0o600)
            link = Path(root) / 'link'
            link.symlink_to(source)
            with self.assertRaises(t.ProviderError):
                store.import_file(str(link))
            with self.assertRaises(t.ProviderError):
                store.import_file('smb://server/secret.txt')
            # Refuse parent symlinks as well as leaf symlinks.
            parent_link = Path(root) / 'linked'
            parent_link.symlink_to(root, target_is_directory=True)
            with self.assertRaises(t.ProviderError):
                store.import_file(str(parent_link / 'input.txt'))
            with patch.object(t.os, 'replace', side_effect=OSError('secret path')):
                with self.assertRaises(t.ProviderError) as error:
                    store.import_file(str(source))
                self.assertNotIn('secret path', str(error.exception))
            self.assertEqual(len(list(private.iterdir())), 1)
            store.clear()
            self.assertIsNone(store.load())
            (private / 'connection').symlink_to(source)
            with self.assertRaises(t.ProviderError):
                store.load()
            with self.assertRaises(t.ProviderError):
                store.clear()
            self.assertTrue(source.exists())


class StreamTests(unittest.TestCase):
    def test_official_missing_index_sentinel_fixture(self):
        # support.rs index_text(None), upstream f347bf5181da82a79a9f2527864125187ea95bd3.
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        self.assertEqual(len(t.parse_streams(payload, t.Config(MANIFEST))), 1)
        for bad in ['Undefined', 'undefinedx', '-1', '1.0', '1000000']:
            payload['streams'][0]['url'] = payload['streams'][0]['url'].rsplit('/', 1)[0] + '/' + bad
            self.assertEqual(t.parse_streams(payload, t.Config(MANIFEST)), [])

    def test_labels_expose_only_bounded_recognized_technical_fields(self):
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        entry = payload['streams'][0]
        entry['title'] += ' ' + TOKEN + ' https://evil.example [B]BAD[/B]'
        label = t.parse_streams(payload, t.Config(MANIFEST))[0].label
        for value in ['1080p', 'HEVC', 'English', '2.0 GiB']:
            self.assertIn(value, label)
        for value in [TOKEN, 'https', '[B]', 'BAD']:
            self.assertNotIn(value, label)
        self.assertLessEqual(len(label), 140)
        entry['title'] = '[B]evil[/B] ' * 10000
        entry['behaviorHints']['videoSize'] = float('inf')
        self.assertLessEqual(len(t.parse_streams(payload, t.Config(MANIFEST))[0].label), 140)

    def test_source_identity_survives_token_rotation_only(self):
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        first = t.parse_streams(payload, t.Config(MANIFEST))[0]
        rotated = 'ROTATED1234567890'
        payload['streams'][0]['url'] = payload['streams'][0]['url'].replace(TOKEN, rotated)
        second = t.parse_streams(payload, t.Config(MANIFEST.replace(TOKEN, rotated)))[0]
        self.assertEqual(first.id, second.id)
        payload['streams'][0]['url'] = payload['streams'][0]['url'].replace('/undefined', '/1')
        self.assertNotEqual(first.id, t.parse_streams(payload, t.Config(MANIFEST.replace(TOKEN, rotated)))[0].id)

    def test_resolver_path_accepts_optional_filename_but_no_extra_segments(self):
        bare = 'https://torrentio.strem.fun/resolve/realdebrid/' + TOKEN + '/' + 'a' * 40 + '/null/0'
        for suffix, count in [('', 1), ('/Example.mkv', 1), ('/Example%20Movie.mkv', 1), ('/Example.mkv/extra', 0)]:
            entries = t.parse_streams({'streams': [{'name': '[RD+] Torrentio', 'url': bare + suffix}]}, t.Config(MANIFEST))
            self.assertEqual(len(entries), count)

    def test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels(self):
        self.assertTrue(hasattr(t, 'parse_streams'), 'Stream adapter is missing')
        url = 'https://torrentio.strem.fun/resolve/realdebrid/' + TOKEN + '/' + 'a' * 40 + '/null/0/Example.mkv'
        good = {'name': '[RD+] Torrentio 1080p', 'title': 'Example', 'url': url}
        bad = [{'infoHash': 'a' * 40}, dict(good, url='magnet:?xt=urn:btih:abc'),
               dict(good, url=url.replace('https:', 'http:')), dict(good, url=url.replace(TOKEN, 'WRONGTOKEN0123456')),
               dict(good, url=url.replace('realdebrid/', 'alldebrid/')), dict(good, infoHash='a' * 40),
               dict(good, name='[RD download] Torrentio'), dict(good, behaviorHints={'proxyHeaders': {'request': {'X': 'evil'}}}),
               dict(good, url=url + '|User-Agent=evil'), dict(good, url=url + '%0d%0aInjected'),
               dict(good, url=url.replace('/null/', '/../../')), dict(good, externalUrl='https://evil.example')]
        items = t.parse_streams({'streams': [good, good] + bad}, t.Config(MANIFEST))
        self.assertEqual(len(items), 1)
        self.assertRegex(items[0].id, r'^[a-f0-9]{64}$')
        self.assertIn('1080p', items[0].label)
        self.assertNotIn(TOKEN, repr(items))
        self.assertNotIn('cached', items[0].label.lower())
        malicious = dict(good, title=TOKEN + ' https://evil.example [B]Bad[/B]')
        self.assertNotIn(TOKEN, t.parse_streams({'streams': [malicious]}, t.Config(MANIFEST))[0].label)
        for payload in [[], {}, {'streams': {}}, {'streams': [good] * 201}]:
            with self.assertRaises(t.ProviderError):
                t.parse_streams(payload, t.Config(MANIFEST))


class Response(io.BytesIO):
    def __init__(self, body=b'{}', status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {'Content-Type': 'application/json'}


class NetworkTests(unittest.TestCase):
    def setUp(self):
        dns = patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))])
        dns.start()
        self.addCleanup(dns.stop)

    def test_known_resolver_states_have_fixed_distinct_messages_without_retry(self):
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        cases = {'downloading_v3.mp4': 'queued', 'download_failed_v3.mp4': 'failed',
                 'failed_access_v3.mp4': 'access', 'failed_rar_v3.mp4': 'archive',
                 'failed_too_big_v2.mp4': 'large', 'failed_opening_v3.mp4': 'open',
                 'failed_unexpected_v3.mp4': 'unexpected', 'failed_infringement_v3.mp4': 'removed',
                 'limits_exceeded_v2.mp4': 'limit', 'blocked_access_v2.mp4': 'blocked',
                 'failed_unavailable_v1.mp4': 'unavailable'}
        messages = set()
        for path, expected in cases.items():
            replies = [Response(json.dumps(payload).encode()), Response(status=302, headers={'Location': t.ORIGIN + '/videos/' + path})]
            calls = []
            def request(url):
                calls.append(url)
                return replies.pop(0)
            with self.assertRaises(t.ProviderError) as error:
                t.Client(t.Config(MANIFEST), request=request).playback('tt1234567', source.id)
            self.assertIn(expected, str(error.exception).lower())
            self.assertNotIn(TOKEN, str(error.exception))
            messages.add(str(error.exception))
            self.assertEqual(len(calls), 2)
        self.assertEqual(len(messages), len(cases))

    def test_manifest_check_is_bounded_and_does_not_validate_account(self):
        self.assertTrue(hasattr(t.Client, 'check'), 'Manifest check is missing')
        calls = []
        def request(url):
            calls.append(url)
            return Response(b'{"id":"com.stremio.torrentio.addon","resources":["stream"],"types":["movie"]}')
        t.Client(t.Config(MANIFEST), request=request).check()
        self.assertEqual(calls, [MANIFEST])
        for body in [b'{}', b'{"id":"wrong","resources":["stream"],"types":["movie"]}']:
            with self.assertRaises(t.ProviderError):
                t.Client(t.Config(MANIFEST), request=lambda _: Response(body)).check()

    def test_lookup_limits_redirect_refusal_and_refetch_before_resolution(self):
        self.assertTrue(hasattr(t, 'Client'), 'Bounded client is missing')
        resolver = 'https://torrentio.strem.fun/resolve/realdebrid/' + TOKEN + '/' + 'b' * 40 + '/null/0/Example.mkv'
        body = json.dumps({'streams': [{'name': '[RD+] Torrentio 720p', 'url': resolver}]}).encode()
        final = 'https://seed.download.real-debrid.com/d/opaque/Example.mkv'
        calls = []
        replies = [Response(body), Response(body), Response(status=302, headers={'Location': final})]
        def request(url):
            calls.append(url)
            return replies.pop(0)
        client = t.Client(t.Config(MANIFEST), request=request)
        sources = client.streams('tt1234567')
        self.assertEqual(client.playback('tt1234567', sources[0].id), final + '|redirect-limit=0')
        self.assertEqual(calls, [t.Config(MANIFEST).lookup('tt1234567')] * 2 + [resolver])
        for response in [Response(status=302, headers={'Location': 'http://127.0.0.1/'}),
                         Response(b'x' * (512 * 1024 + 1)), Response(b'not-json'), Response(b'{}', headers={'Content-Encoding': 'gzip'})]:
            with self.assertRaises(t.ProviderError):
                t.Client(t.Config(MANIFEST), request=lambda _: response).streams('tt1234567')
        for target in ['http://seed.download.real-debrid.com/file.mkv', 'https://127.0.0.1/file',
                       final + '|Header=bad', final.replace('real-debrid.com', 'real-debrid.com.evil.example'),
                       'https://torrentio.strem.fun/videos/failed_access.mp4']:
            responses = [Response(body), Response(status=302, headers={'Location': target})]
            with self.assertRaises(t.ProviderError):
                t.Client(t.Config(MANIFEST), request=lambda _: responses.pop(0)).playback('tt1234567', sources[0].id)
        with self.assertRaises(t.ProviderError):
            t.Client(t.Config(MANIFEST), request=lambda _: Response(b'{"streams":[]}')).playback('tt1234567', sources[0].id)

    def test_rejects_malformed_manifest_types_and_private_playback_dns(self):
        with self.assertRaises(t.ProviderError):
            t.Client(t.Config(MANIFEST), request=lambda _: Response(b'{"id":"com.stremio.torrentio.addon","types":null}')).check()
        resolver = 'https://torrentio.strem.fun/resolve/realdebrid/' + TOKEN + '/' + 'b' * 40 + '/null/0/Example.mkv'
        payload = {'streams': [{'name': '[RD+] Torrentio', 'url': resolver}]}
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        replies = [Response(json.dumps(payload).encode()), Response(status=302, headers={'Location': 'https://seed.download.real-debrid.com/file.mkv'})]
        with patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(t.ProviderError):
                t.Client(t.Config(MANIFEST), request=lambda _: replies.pop(0)).playback('tt1234567', source.id)

    def test_cancel_between_refetch_and_resolver_prevents_provider_mutation(self):
        self.assertTrue('cancelled' in __import__('inspect').signature(t.Client.playback).parameters, 'Playback cancellation gate is missing')
        resolver = 'https://torrentio.strem.fun/resolve/realdebrid/' + TOKEN + '/' + 'b' * 40 + '/null/0/Example.mkv'
        payload = {'streams': [{'name': '[RD+] Torrentio', 'url': resolver}]}
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        calls = []
        def request(url):
            calls.append(url)
            return Response(json.dumps(payload).encode())
        cancelled = iter([False, True])
        with self.assertRaises(t.ProviderError):
            t.Client(t.Config(MANIFEST), request=request).playback('tt1234567', source.id, cancelled=lambda: next(cancelled))
        self.assertEqual(calls, [t.Config(MANIFEST).lookup('tt1234567')])

    def test_cancel_during_resolver_dns_sends_no_http_request(self):
        from unittest.mock import Mock
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        cancelled = [False]
        def dns(*args, **kwargs):
            cancelled[0] = True
            return [(2, 1, 6, '', ('93.184.216.34', 443))]
        connection = Mock()
        connection.getresponse.return_value = Response(status=302, headers={
            'Location': 'https://seed.download.real-debrid.com/file.mkv'})
        client = t.Client(t.Config(MANIFEST))
        with patch.object(client, 'streams', return_value=[source]), patch.object(t.socket, 'getaddrinfo', side_effect=dns), patch.object(t.http.client, 'HTTPSConnection', return_value=connection) as connect:
            try:
                client.playback('tt1234567', source.id, cancelled=lambda: cancelled[0])
            except t.ProviderError:
                pass
        connection.request.assert_not_called()
        connect.assert_not_called()

    def test_cancel_after_resolver_send_discards_reply_without_retry(self):
        from unittest.mock import Mock
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        for failure in (False, True):
            with self.subTest(failure=failure):
                cancelled = [False]
                connection = Mock()
                def response():
                    cancelled[0] = True
                    if failure:
                        raise OSError('synthetic late failure')
                    return Response(status=302, headers={
                        'Location': 'https://seed.download.real-debrid.com/file.mkv'})
                connection.getresponse.side_effect = response
                client = t.Client(t.Config(MANIFEST))
                with patch.object(client, 'streams', return_value=[source]), patch.object(t, 'public_addresses', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]) as dns, patch.object(t.http.client, 'HTTPSConnection', return_value=connection):
                    with self.assertRaises(t.ProviderError):
                        client.playback('tt1234567', source.id, cancelled=lambda: cancelled[0])
                connection.request.assert_called_once()
                connection.close.assert_called_once()
                dns.assert_called_once_with('torrentio.strem.fun')

    def test_cancel_during_playback_refetch_dns_sends_nothing(self):
        from unittest.mock import Mock
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        source = t.parse_streams(payload, t.Config(MANIFEST))[0]
        cancelled = [False]
        def dns(*args, **kwargs):
            cancelled[0] = True
            return [(2, 1, 6, '', ('93.184.216.34', 443))]
        connection = Mock()
        connection.getresponse.return_value = Response(json.dumps(payload).encode())
        with patch.object(t.socket, 'getaddrinfo', side_effect=dns), patch.object(t.http.client, 'HTTPSConnection', return_value=connection):
            with self.assertRaises(t.ProviderError):
                t.Client(t.Config(MANIFEST)).playback('tt1234567', source.id, cancelled=lambda: cancelled[0])
        connection.request.assert_not_called()

    def test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors(self):
        self.assertTrue(hasattr(t, 'request'), 'Safe transport is missing')
        from unittest.mock import Mock
        connection = Mock()
        connection.getresponse.return_value = Response()
        with patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]), patch.object(t.http.client, 'HTTPSConnection', return_value=connection):
            with t.request(t.Config(MANIFEST).lookup('tt1234567')) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(connection.request.call_args.args[0], 'GET')
            self.assertNotIn('Authorization', connection.request.call_args.kwargs['headers'])
        with patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]), patch.object(t.http.client, 'HTTPSConnection') as connect:
            with self.assertRaises(t.ProviderError):
                t.request(t.Config(MANIFEST).lookup('tt1234567'))
            connect.assert_not_called()
        with patch.object(t.socket, 'getaddrinfo', side_effect=OSError(TOKEN)):
            with self.assertRaises(t.ProviderError) as error:
                t.request(t.Config(MANIFEST).lookup('tt1234567'))
            self.assertNotIn(TOKEN, str(error.exception))
