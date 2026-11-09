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
