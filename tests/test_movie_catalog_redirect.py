"""Exercise the real urllib redirect/error machinery without network access."""
from email.message import Message
import io
import unittest
from unittest.mock import patch
from urllib.request import BaseHandler, Request, build_opener
from urllib.response import addinfourl

from test_movie_catalog import catalog


class ScriptedHTTPS(BaseHandler):
    handler_order = 100  # Intercept before the real HTTPS transport.

    def __init__(self, replies):
        super().__init__()
        self.replies = iter(replies)
        self.requests = []
        self.responses = []

    def https_open(self, request):
        self.requests.append(request)
        status, location, body = next(self.replies)
        headers = Message()
        if location is not None:
            headers['Location'] = location
        response = addinfourl(io.BytesIO(body), headers, request.full_url, status)
        setattr(response, 'msg', 'fixture')
        self.responses.append(response)
        return response


class CatalogRedirectTests(unittest.TestCase):
    path = '/catalog/movie/top/skip=0.json'
    target = 'https://cinemeta-catalogs.strem.io/top' + path

    def fetch_with(self, replies, path=None):
        transport = ScriptedHTTPS(replies)
        opener = build_opener(catalog.CatalogRedirect, transport)
        with patch.object(catalog, 'build_opener', return_value=opener):
            result = catalog.fetch(path or self.path)
        return result, transport

    def test_paging_genre_and_featured_keep_exact_route(self):
        for collection in ('top', 'imdbRating'):
            for extras in ('skip=0', 'skip=100', 'skip=10000&genre=Sci-Fi',
                           'skip=100&genre=Drama'):
                with self.subTest(collection=collection, extras=extras):
                    path = '/catalog/movie/' + collection + '/' + extras + '.json'
                    target = 'https://cinemeta-catalogs.strem.io/' + collection + path
                    result, transport = self.fetch_with([
                        (307, target, b''), (200, None, b'{"metas": []}')], path)
                    self.assertEqual(result, {'metas': []})
                    self.assertEqual(transport.requests[-1].full_url, target)

    def test_other_redirect_statuses_are_closed_without_following(self):
        for status in (301, 302, 303, 308):
            with self.subTest(status=status):
                transport = ScriptedHTTPS([(status, self.target, b'')])
                opener = build_opener(catalog.CatalogRedirect, transport)
                with patch.object(catalog, 'build_opener', return_value=opener):
                    with self.assertRaisesRegex(catalog.CatalogError,
                                                '^Online catalogue unavailable$'):
                        catalog.fetch(self.path)
                self.assertEqual(len(transport.requests), 1)
                self.assertTrue(transport.responses[0].closed)

    def test_untrusted_locations_never_make_second_request(self):
        locations = (
            None, '', '/top' + self.path, '//cinemeta-catalogs.strem.io/top' + self.path,
            self.target.replace('https:', 'http:'),
            self.target.replace('cinemeta-catalogs.strem.io', 'evil.example'),
            self.target.replace('cinemeta-catalogs.strem.io', 'cinemeta-catalogs.strem.io.evil.example'),
            self.target.replace('cinemeta-catalogs.strem.io', '127.0.0.1'),
            self.target.replace('cinemeta-catalogs.strem.io', 'user:pass@cinemeta-catalogs.strem.io'),
            self.target.replace('cinemeta-catalogs.strem.io', 'cinemeta-catalogs.strem.io:443'),
            self.target.replace('cinemeta-catalogs.strem.io', 'cinemeta-catalogs.strem.io:8443'),
            self.target.replace('/top/catalog', '/imdbRating/catalog'),
            self.target.replace('skip=0', 'skip=100'),
            self.target.replace('/movie/', '/series/'),
            self.target.replace('/top/catalog', '/top/../top/catalog'),
            self.target.replace('/top/catalog', '/%74op/catalog'),
            self.target + '?token=secret', self.target + '#fragment',
            self.target + '|Authorization=secret', self.target + '\r\nX-Evil: yes',
            self.target + '%0d%0aX-Evil:yes', ' ' + self.target, self.target + '\n',
            self.target.replace('https://', 'https:\\\\'),
        )
        for location in locations:
            with self.subTest(location=location):
                transport = ScriptedHTTPS([(307, location, b'')])
                opener = build_opener(catalog.CatalogRedirect, transport)
                with patch.object(catalog, 'build_opener', return_value=opener):
                    with self.assertRaisesRegex(catalog.CatalogError,
                                                '^Online catalogue unavailable$'):
                        catalog.fetch(self.path)
                self.assertEqual(len(transport.requests), 1)
                self.assertTrue(transport.responses[0].closed)

    def test_search_and_details_work_directly_but_cannot_redirect(self):
        paths = ('/catalog/movie/top/skip=0&search=matrix.json',
                 '/catalog/movie/top/skip=0&search=matrix&genre=Drama.json',
                 '/meta/movie/tt0133093.json')
        for path in paths:
            with self.subTest(path=path):
                result, transport = self.fetch_with([(200, None, b'{"ok": true}')], path)
                self.assertEqual(result, {'ok': True})
                self.assertEqual(len(transport.requests), 1)
                with self.assertRaises(catalog.CatalogError):
                    self.fetch_with([(307, self.target, b'')], path)

    def test_out_of_scope_source_routes_cannot_redirect(self):
        paths = ('/catalog/series/top/skip=0.json', '/catalog/movie/year/skip=0.json',
                 '/catalog/movie/top/skip=10001.json', '/catalog/movie/top/skip=-1.json',
                 '/catalog/movie/top/skip=00.json', '/catalog/movie/top/skip=0&genre=Unknown.json',
                 self.path + '?extra=yes', self.path + '#fragment',
                 '/catalog/movie/top/skip=0&extra=yes.json')
        for path in paths:
            with self.subTest(path=path):
                with self.assertRaises(catalog.CatalogError):
                    self.fetch_with([(307, 'https://cinemeta-catalogs.strem.io/top' + path, b'')], path)

    def test_second_hop_and_loops_are_refused(self):
        for location in (self.target, catalog.ORIGIN + self.path,
                         self.target.replace('skip=0', 'skip=100'), 'https://evil.example/'):
            with self.subTest(location=location):
                transport = ScriptedHTTPS([(307, self.target, b''), (307, location, b'')])
                opener = build_opener(catalog.CatalogRedirect, transport)
                with patch.object(catalog, 'build_opener', return_value=opener):
                    with self.assertRaises(catalog.CatalogError):
                        catalog.fetch(self.path)
                self.assertEqual(len(transport.requests), 2)
                self.assertTrue(all(r.closed for r in transport.responses))

    def test_redirect_does_not_copy_headers_or_read_body(self):
        transport = ScriptedHTTPS([(200, None, b'{}')])
        handler = catalog.CatalogRedirect()
        build_opener(handler, transport)
        request = Request(catalog.ORIGIN + self.path, headers={
            'Authorization': 'secret', 'Cookie': 'secret', 'X-Secret': 'secret',
            'Proxy-Authorization': 'secret'})
        request.timeout = 8
        headers = Message()
        headers['Location'] = self.target
        class UnreadableBody(io.BytesIO):
            def read(self, *args):
                raise AssertionError('Redirect body must not be read')

        with UnreadableBody() as response:
            with handler.http_error_307(request, response, 307, '', headers):
                pass
            self.assertTrue(response.closed)
        self.assertEqual(dict(transport.requests[0].header_items()), {
            'Host': 'cinemeta-catalogs.strem.io', 'Accept': 'application/json',
            'User-agent': 'ApertureMovies/0.4'})

    def test_duplicate_location_and_non_get_are_refused(self):
        for duplicate, method in ((True, 'GET'), (False, 'POST'), (False, 'HEAD')):
            headers = Message()
            headers['Location'] = self.target
            if duplicate:
                headers['Location'] = self.target
            request = Request(catalog.ORIGIN + self.path, method=method)
            with io.BytesIO() as response:
                with self.assertRaises(catalog.CatalogError):
                    catalog.CatalogRedirect().http_error_307(request, response, 307, '', headers)
                self.assertTrue(response.closed)

    def test_redirected_response_size_and_json_guards(self):
        for body in (b' ' * (catalog.MAX_BYTES + 1), b'not json', b'[]'):
            with self.subTest(size=len(body)):
                with self.assertRaisesRegex(catalog.CatalogError,
                                            '^Online catalogue unavailable$'):
                    self.fetch_with([(307, self.target, b''), (200, None, body)])
        body = b'{}' + b' ' * (catalog.MAX_BYTES - 2)
        result, _ = self.fetch_with([(307, self.target, b''), (200, None, body)])
        self.assertEqual(result, {})

    def test_observed_catalogue_307_returns_json(self):
        result, transport = self.fetch_with([
            (307, self.target, b'redirect'),
            (200, None, b'{"metas": []}'),
        ])
        self.assertEqual(result, {'metas': []})
        self.assertEqual([r.full_url for r in transport.requests],
                         [catalog.ORIGIN + self.path, self.target])
        for request in transport.requests:
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.timeout, 8)
            self.assertEqual(dict(request.header_items()), {
                'Host': request.host, 'Accept': 'application/json',
                'User-agent': 'ApertureMovies/0.4',
            })
        self.assertTrue(all(response.closed for response in transport.responses))
