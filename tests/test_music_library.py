"""Injected JSON-RPC adapter tests; no Kodi process, real media or networking."""
import io
import json
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'addons/script.apeture.music/resources/lib'))
from apeture_music.library import Library, LibraryError


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(json.loads(request))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps({'jsonrpc': '2.0', 'id': self.requests[-1]['id'], 'result': response})


class LibraryAdapterTests(unittest.TestCase):
    def test_album_pagination_requests_real_metadata_and_sorts_complete_result(self):
        transport = FakeTransport([
            {'albums': [{'albumid': 3, 'title': 'Late', 'artist': ['The Bees'], 'year': 2002},
                        {'albumid': 1, 'title': 'Early', 'artist': ['Apples'], 'year': 2000}],
             'limits': {'start': 0, 'end': 2, 'total': 3}},
            {'albums': [{'albumid': 2, 'title': 'First', 'artist': ['The Bees'], 'year': 2001}],
             'limits': {'start': 2, 'end': 3, 'total': 3}}])
        library = Library(transport)
        library.PAGE_SIZE = 2
        self.assertEqual([a.id for a in library.albums()], [1, 2, 3])
        self.assertEqual([r['params']['limits'] for r in transport.requests],
                         [{'start': 0, 'end': 2}, {'start': 2, 'end': 4}])
        self.assertEqual([r['id'] for r in transport.requests], [1, 2])
        for request in transport.requests:
            self.assertEqual(request['method'], 'AudioLibrary.GetAlbums')
            self.assertEqual(request['jsonrpc'], '2.0')
            self.assertEqual(request['params']['properties'], ['title', 'artist', 'year', 'thumbnail'])
            self.assertNotIn('albumartist', request['params']['properties'])

    def test_songs_filter_album_and_keep_multidisc_order_and_exact_url(self):
        path = 'smb://fixture-user:fixture-secret@fixture-host/é%20&file.flac'
        transport = FakeTransport([{'songs': [
            {'songid': 2, 'file': '/fixture/earlier-name.flac', 'disc': 2, 'track': 1},
            {'songid': 1, 'file': path, 'disc': 1, 'track': 2}],
            'limits': {'start': 0, 'end': 2, 'total': 2}}])
        result = Library(transport).songs(72)
        self.assertEqual([s.id for s in result], [1, 2])
        self.assertEqual(result[0].file, path)
        request = transport.requests[0]
        self.assertEqual(request['method'], 'AudioLibrary.GetSongs')
        self.assertEqual(request['params']['filter'], {'albumid': 72})
        self.assertTrue({'disc', 'track', 'file', 'albumartist'} <= set(request['params']['properties']))

    def test_incomplete_or_duplicate_track_rows_fail_the_whole_album(self):
        valid = {"songid": 1, "file": "/fixture/one.flac", "track": 1}
        for other in ({"songid": 2, "file": ""}, {"songid": -1, "file": "/fixture/two.flac"}, valid, None):
            transport = FakeTransport([{"songs": [valid, other], "limits": {"end": 2, "total": 2}}])
            with self.subTest(other=other), self.assertRaises(LibraryError):
                Library(transport).songs(1)

    def test_invalid_album_id_rejected_without_transport(self):
        transport = FakeTransport([])
        for identifier in (None, '1', True, -1, [], {}):
            with self.subTest(identifier=identifier), self.assertRaises(LibraryError):
                Library(transport).songs(identifier)
        self.assertEqual(transport.requests, [])

    def test_empty_library_with_and_without_optional_array(self):
        for response in ({'albums': [], 'limits': {'start': 0, 'end': 0, 'total': 0}},
                         {'limits': {'start': 0, 'end': 0, 'total': 0}}):
            self.assertEqual(Library(FakeTransport([response])).albums(), [])

    def test_nonadvancing_or_malformed_pages_fail_instead_of_looping(self):
        first = {'albums': [{'albumid': 1}], 'limits': {'end': 1, 'total': 3}}
        invalid_pages = [
            {'albums': [], 'limits': {'end': 1, 'total': 3}},
            {'albums': [{'albumid': 2}], 'limits': {'end': 1, 'total': 3}},
            {'albums': {}, 'limits': {'end': 2, 'total': 3}},
            {'albums': [], 'limits': []}, None, []]
        for response in invalid_pages:
            transport = FakeTransport([first, response])
            with self.subTest(response=response), self.assertRaises(LibraryError):
                Library(transport).albums()
            self.assertEqual(len(transport.requests), 2)

    def test_page_error_never_returns_partial_album_catalogue(self):
        transport = FakeTransport([
            {'albums': [{'albumid': 1}], 'limits': {'end': 1, 'total': 2}},
            RuntimeError('/fixture/private/filename.flac')])
        with self.assertRaises(LibraryError) as raised:
            Library(transport).albums()
        self.assertNotIn('filename', str(raised.exception))

    def test_cancel_before_loading_and_between_pages(self):
        transport = FakeTransport([])
        with self.assertRaisesRegex(LibraryError, 'cancelled'):
            Library(transport, cancelled=lambda: True).albums()
        self.assertEqual(transport.requests, [])
        transport = FakeTransport([{'albums': [{'albumid': 1}],
                                    'limits': {'end': 1, 'total': 10}}])
        library = Library(transport, cancelled=lambda: bool(transport.requests))
        with self.assertRaisesRegex(LibraryError, 'cancelled'):
            library.albums()
        self.assertEqual(len(transport.requests), 1)

    def test_rpc_errors_do_not_log_or_expose_private_payloads(self):
        secret = 'smb://fixture-user:fixture-secret@fixture-host/private.flac'
        failures = [lambda request: secret,
                    lambda request: json.dumps({'error': {'message': secret}}),
                    lambda request: json.dumps({'private': secret}),
                    lambda request: json.dumps([secret]),
                    lambda request: json.dumps(None)]
        def raised_transport(request):
            raise RuntimeError(secret)
        failures.append(raised_transport)
        for execute in failures:
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(execute=execute), redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaises(LibraryError) as raised:
                    Library(execute).albums()
            self.assertEqual(stdout.getvalue(), '')
            self.assertEqual(stderr.getvalue(), '')
            self.assertEqual(str(raised.exception), 'Kodi could not read the music library.')
            self.assertIsNone(raised.exception.__cause__)
            self.assertTrue(raised.exception.__suppress_context__)


class PlayingAlbumTests(unittest.TestCase):
    def test_selects_audio_player_and_requests_database_album_id(self):
        transport = FakeTransport([[{'type': 'video', 'playerid': 1},
                                    {'type': 'audio', 'playerid': 0}],
                                   {'item': {'type': 'song', 'albumid': 91}}])
        self.assertEqual(Library(transport).playing_album(), 91)
        self.assertEqual(transport.requests[1]['method'], 'Player.GetItem')
        self.assertEqual(transport.requests[1]['params'], {'playerid': 0, 'properties': ['albumid']})

    def test_player_transition_errors_do_not_block_browsing(self):
        transport = FakeTransport([[{'type': 'audio', 'playerid': 0}],
                                   RuntimeError('player disappeared'),
                                   {'albums': [], 'limits': {'end': 0, 'total': 0}}])
        library = Library(transport)
        self.assertIsNone(library.playing_album())
        self.assertEqual(library.albums(), [])

    def test_no_audio_or_invalid_player_is_not_a_current_album(self):
        for players in ([], None, {}, [None], [{'type': 'video', 'playerid': 1}],
                        [{'type': 'audio', 'playerid': True}], [{'type': 'audio'}]):
            transport = FakeTransport([players])
            with self.subTest(players=players):
                self.assertIsNone(Library(transport).playing_album())
                self.assertEqual(len(transport.requests), 1)

    def test_missing_or_malformed_current_item_returns_none(self):
        for result in (None, [], {}, {'item': None}, {'item': []}, {'item': 'bad'},
                       {'item': {}}, {'item': {'albumid': True}},
                       {'item': {'albumid': -1}}, {'item': {'albumid': '2'}}):
            transport = FakeTransport([[{'type': 'audio', 'playerid': 0}], result])
            with self.subTest(result=result):
                self.assertIsNone(Library(transport).playing_album())

    def test_cancelled_current_query_is_harmless(self):
        transport = FakeTransport([])
        self.assertIsNone(Library(transport, cancelled=lambda: True).playing_album())
        self.assertEqual(transport.requests, [])


if __name__ == '__main__':
    unittest.main()
