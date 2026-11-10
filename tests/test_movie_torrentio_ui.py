import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_movie_torrentio import t, MANIFEST, TOKEN
from test_movie_debrid import rd, PAIR

ROOT = Path(__file__).resolve().parents[1]


class TorrentioUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dialog, self.xbmc, self.gui, self.plugin = Mock(), Mock(), Mock(), Mock()
        self.dialog.select.return_value = -1
        self.dialog.yesno.return_value = False
        self.gui.Dialog.return_value = self.dialog
        self.gui.DialogProgress.return_value.iscanceled.return_value = False
        self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=online'
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        path = ROOT / 'movies-kodi/resources/lib/torrentio_ui.py'
        self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
        with patch.dict(sys.modules, {'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin, 'resources.lib.torrentio': t, 'resources.lib.debrid': rd}):
            spec = importlib.util.spec_from_file_location('torrentio_ui_test', path)
            self.ui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.ui)
        self.client = Mock()
        self.ui.Client = Mock(return_value=self.client)

    def run_ui(self, query=None):
        self.ui.run(query or {'action': ['torrentio_setup']}, self.temp.name, 'plugin://movies/', 3)

    def connect(self):
        source = Path(self.temp.name) / 'input.txt'
        source.write_text(MANIFEST)
        source.chmod(0o600)
        t.Store(self.temp.name).import_file(str(source))
        return str(source)

    def test_cancel_and_decline_setup_never_connect(self):
        self.run_ui()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.assert_not_called()
        self.assertIn('Set up online playback', self.dialog.select.call_args.args[0])
        self.dialog.select.return_value = 0
        self.run_ui()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.assert_not_called()

    def test_native_setup_reuses_existing_grant_only_after_separate_consent(self):
        rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=1e11))
        self.dialog.select.return_value = 0
        self.dialog.yesno.side_effect = [True, False]
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.dialog.yesno.side_effect = [True, True]
        self.run_ui()
        self.assertEqual(t.Store(self.temp.name).load(), 'rd-oauth-v1')
        self.assertEqual(self.client.mock_calls, [])
        messages = repr(self.dialog.mock_calls)
        for text in ['torrentio.strem.fun', 'access token', 'torrents', 'downloads', 'user information', 'refresh', 'not verified']:
            self.assertIn(text, messages)
        self.assertNotIn(TOKEN, messages)
        self.assertNotIn('secret-fixture', messages)

    def test_new_user_completes_device_approval_in_app(self):
        from test_movie_debrid import DEVICE, TOKEN as RD_TOKEN
        self.dialog.select.return_value = 0
        self.dialog.yesno.return_value = True
        self.gui.DialogProgress.return_value.iscanceled.return_value = False
        now = [1000.0]
        def wait(seconds):
            now[0] += seconds
            return False
        self.xbmc.Monitor.return_value.waitForAbort.side_effect = wait
        transport = Mock(side_effect=[DEVICE, PAIR, RD_TOKEN])
        with patch.object(self.ui, 'RDClient', lambda store: rd.Client(store, transport, lambda: now[0])), patch.object(self.ui.time, 'monotonic', lambda: now[0]):
            self.run_ui()
        self.assertEqual(t.Store(self.temp.name).load(), 'rd-oauth-v1')
        self.assertEqual(transport.call_count, 3)
        self.assertIn('real-debrid.com/device', repr(self.gui.DialogProgress.mock_calls))
        self.assertIn('official shared open-source', repr(self.dialog.mock_calls))
        self.gui.DialogProgress.return_value.close.assert_called_once()
        self.assertEqual(self.client.mock_calls, [])

    def test_native_find_refreshes_under_lock_and_discloses_only_access_token(self):
        t.Store(self.temp.name).enable_native()
        rd.Store(self.temp.name).save(dict(PAIR, access_token='expired-fixture', refresh_token='refresh-fixture', expires_at=1001))
        self.dialog.yesno.return_value = True
        transport = Mock(return_value=dict(access_token=TOKEN, refresh_token='rotated-refresh', expires_in=3600, token_type='Bearer'))
        def streams(identifier):
            with self.assertRaises(rd.DebridError):
                with rd.Store(self.temp.name).locked():
                    self.fail('Disclosure must hold the RD lock')
            return []
        self.client.streams.side_effect = streams
        try:
            with patch.object(self.ui, 'RDClient', lambda store: rd.Client(store, transport, lambda: 1000)):
                self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        except AttributeError:
            self.fail('Native consent marker must resolve to a refreshed in-memory config')
        self.assertEqual(transport.call_count, 1)
        config = self.ui.Client.call_args.args[0]
        self.assertEqual(config._token, TOKEN)
        for secret in ['refresh-fixture', 'rotated-refresh', 'secret-fixture']:
            self.assertNotIn(secret, config._manifest)
        self.assertEqual(t.Store(self.temp.name).load(), 'rd-oauth-v1')
        self.assertNotIn(TOKEN, repr(self.dialog.mock_calls))

    def test_unreadable_configuration_can_be_reset_without_parsing(self):
        self.connect()
        saved = Path(self.temp.name) / 'torrentio-private/connection'
        saved.write_bytes(b'\xff' * 5000)
        self.dialog.select.return_value = 4
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertFalse(saved.exists(), 'Unreadable saved configuration traps setup')
        self.assertIn('unreadable', self.dialog.select.call_args.args[0])
        self.assertEqual(self.client.mock_calls, [])

    def test_disconnect_serializes_with_disclosure_and_explains_irrevocability(self):
        self.connect()
        self.dialog.select.return_value = 4
        self.dialog.yesno.return_value = True
        with rd.Store(self.temp.name).locked():
            self.run_ui()
        self.assertIsNotNone(t.Store(self.temp.name).load(), 'Disconnect must not race an in-flight disclosure')
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.assertIn('cannot retract', repr(self.dialog.mock_calls))

    def test_provider_wait_has_cancellable_progress_and_never_plays_after_cancel(self):
        self.connect()
        self.dialog.yesno.return_value = True
        self.gui.DialogProgress.return_value.iscanceled.return_value = True
        self.client.streams.return_value = []
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.gui.DialogProgress.return_value.create.assert_called_once()
        self.gui.DialogProgress.return_value.close.assert_called_once()
        self.client.streams.assert_not_called()
        self.xbmc.Player.return_value.play.assert_not_called()

    def test_cancel_during_refresh_is_silent_even_when_refresh_fails(self):
        t.Store(self.temp.name).enable_native()
        rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=1))
        self.dialog.yesno.return_value = True
        for failure in (None, rd.DebridError('service')):
            with self.subTest(failure=failure):
                self.gui.DialogProgress.return_value.iscanceled.return_value = False
                rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=1))
                def refresh(*args, **kwargs):
                    self.gui.DialogProgress.return_value.iscanceled.return_value = True
                    if failure:
                        raise failure
                    return dict(access_token=TOKEN, refresh_token='rotated-fixture', expires_in=3600, token_type='Bearer')
                with patch.object(self.ui, 'RDClient', lambda store: rd.Client(store, refresh, lambda: 1000)):
                    self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
                self.client.streams.assert_not_called()
                self.xbmc.Player.return_value.play.assert_not_called()
                self.dialog.ok.assert_not_called()
        self.assertEqual(self.gui.DialogProgress.return_value.close.call_count, 2)

    def test_cancel_during_resolver_discards_late_result(self):
        self.connect()
        self.dialog.yesno.return_value = True
        self.dialog.select.return_value = 0
        self.client.streams.return_value = [Mock(id='a' * 64, label='Real-Debrid')]
        def playback(*args, **kwargs):
            self.gui.DialogProgress.return_value.iscanceled.return_value = True
            return 'https://seed.download.real-debrid.com/file.mkv'
        self.client.playback.side_effect = playback
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.xbmc.Player.return_value.play.assert_not_called()

    def test_cancel_navigation_shutdown_during_resolver_tls_sends_nothing(self):
        import json
        from test_movie_torrentio import Response
        self.connect()
        self.dialog.yesno.return_value = True
        self.dialog.select.return_value = 0
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        for stop in ('cancel', 'navigation', 'shutdown'):
            with self.subTest(stop=stop):
                self.gui.DialogProgress.return_value.iscanceled.return_value = False
                self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=online'
                self.xbmc.Monitor.return_value.abortRequested.return_value = False
                def interrupt():
                    if stop == 'cancel':
                        self.gui.DialogProgress.return_value.iscanceled.return_value = True
                    elif stop == 'navigation':
                        self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=other'
                    else:
                        self.xbmc.Monitor.return_value.abortRequested.return_value = True
                lookup = Mock()
                lookup.getresponse.side_effect = lambda: Response(json.dumps(payload).encode())
                resolver = Mock()
                resolver.connect.side_effect = interrupt
                resolver.getresponse.return_value = Response(status=302, headers={
                    'Location': 'https://seed.download.real-debrid.com/file.mkv'})
                with patch.object(self.ui, 'Client', t.Client), patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]), patch.object(t.http.client, 'HTTPSConnection', side_effect=[lookup, lookup, resolver]):
                    self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
                self.xbmc.Player.return_value.play.assert_not_called()
                self.dialog.ok.assert_not_called()
                resolver.request.assert_not_called()
                resolver.close.assert_called_once()
                self.assertEqual(lookup.request.call_count, 2)

    def test_cancel_during_lookup_dns_prevents_token_disclosure(self):
        import json
        from test_movie_torrentio import Response
        self.connect()
        self.dialog.yesno.return_value = True
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        def dns(*args, **kwargs):
            self.gui.DialogProgress.return_value.iscanceled.return_value = True
            return [(2, 1, 6, '', ('93.184.216.34', 443))]
        connection = Mock()
        connection.getresponse.return_value = Response(json.dumps(payload).encode())
        with patch.object(self.ui, 'Client', t.Client), patch.object(t.socket, 'getaddrinfo', side_effect=dns), patch.object(t.http.client, 'HTTPSConnection', return_value=connection):
            self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        connection.request.assert_not_called()
        self.xbmc.Player.return_value.play.assert_not_called()
        self.dialog.ok.assert_not_called()

    def test_late_real_transport_reply_or_error_is_silent_without_retry(self):
        import json
        from test_movie_torrentio import Response
        self.connect()
        self.dialog.yesno.return_value = True
        self.dialog.select.return_value = 0
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        for stop in ('cancel', 'navigation', 'shutdown'):
            for failure in (False, True):
                with self.subTest(stop=stop, failure=failure):
                    self.gui.DialogProgress.return_value.iscanceled.return_value = False
                    self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=online'
                    self.xbmc.Monitor.return_value.abortRequested.return_value = False
                    def response():
                        if stop == 'cancel':
                            self.gui.DialogProgress.return_value.iscanceled.return_value = True
                        elif stop == 'navigation':
                            self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=other'
                        else:
                            self.xbmc.Monitor.return_value.abortRequested.return_value = True
                        if failure:
                            raise OSError('synthetic late failure')
                        return Response(status=302, headers={
                            'Location': 'https://seed.download.real-debrid.com/file.mkv'})
                    lookup = Mock()
                    lookup.getresponse.side_effect = lambda: Response(json.dumps(payload).encode())
                    resolver = Mock()
                    resolver.getresponse.side_effect = response
                    with patch.object(self.ui, 'Client', t.Client), patch.object(t.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]), patch.object(t.http.client, 'HTTPSConnection', side_effect=[lookup, lookup, resolver]):
                        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
                    self.xbmc.Player.return_value.play.assert_not_called()
                    self.dialog.ok.assert_not_called()
                    resolver.request.assert_called_once()
                    resolver.close.assert_called_once()
                    self.assertEqual(lookup.request.call_count, 2)

    def test_shutdown_during_device_approval_saves_nothing_and_leaves_ui_closed(self):
        from test_movie_debrid import DEVICE
        self.dialog.select.return_value = 0
        self.dialog.yesno.return_value = True
        def transport(*args, **kwargs):
            self.xbmc.Monitor.return_value.abortRequested.return_value = True
            return DEVICE
        with patch.object(self.ui, 'RDClient', lambda store: rd.Client(store, transport, lambda: 1000)):
            self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.assertIsNone(rd.Store(self.temp.name).load())
        self.gui.DialogProgress.return_value.close.assert_called_once()
        self.dialog.ok.assert_not_called()

    def test_status_explains_native_setup_not_a_browser_dead_end(self):
        self.dialog.select.return_value = 3
        self.run_ui()
        message = self.dialog.ok.call_args.args[1]
        self.assertIn('no manual token copying', message)
        self.assertIn('access token', message)
        self.assertNotIn('not supported', message)

    def test_token_rotation_between_selection_and_playback_keeps_validated_source(self):
        import json
        from test_movie_torrentio import Response
        t.Store(self.temp.name).enable_native()
        rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=2000))
        now = [1000]
        self.dialog.yesno.return_value = True
        def select(*args):
            now[0] = 1990
            return 0
        self.dialog.select.side_effect = select
        rotated = 'ROTATED1234567890'
        refresh = Mock(return_value=dict(access_token=rotated, refresh_token='new-refresh', expires_in=3600, token_type='Bearer'))
        requests = []
        def factory(config, **kwargs):
            def request(url):
                requests.append(url)
                if '/resolve/' in url:
                    return Response(status=302, headers={'Location': 'https://seed.download.real-debrid.com/file.mkv'})
                payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
                payload['streams'][0]['url'] = payload['streams'][0]['url'].replace(TOKEN, config._token)
                return Response(json.dumps(payload).encode())
            return t.Client(config, request=request, **kwargs)
        with patch.object(self.ui, 'RDClient', lambda store: rd.Client(store, refresh, lambda: now[0])), patch.object(self.ui, 'Client', factory), patch.object(t, 'public_addresses', return_value=[]):
            self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.assertEqual(refresh.call_count, 1)
        self.assertIn(TOKEN, requests[0])
        self.assertIn(rotated, requests[-1])
        self.assertNotIn(TOKEN, requests[-1])
        self.xbmc.Player.return_value.play.assert_called_once()
        self.assertEqual(t.Store(self.temp.name).load(), 'rd-oauth-v1')

    def test_native_check_decline_never_refreshes_or_contacts_any_provider(self):
        t.Store(self.temp.name).enable_native()
        rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=1))
        self.dialog.select.return_value = 2
        with patch.object(self.ui, 'RDClient') as client:
            self.run_ui()
        client.assert_not_called()
        self.assertEqual(self.client.mock_calls, [])

    def test_import_requires_all_consents_and_no_network(self):
        source = self.connect()
        t.Store(self.temp.name).clear()
        self.dialog.select.return_value = 1
        self.dialog.browseSingle.return_value = source
        self.dialog.yesno.side_effect = [True, False]
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.dialog.yesno.side_effect = None
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertIsNotNone(t.Store(self.temp.name).load())
        self.assertEqual(self.client.mock_calls, [])
        self.assertNotIn(TOKEN, repr(self.dialog.mock_calls))

    def test_configured_find_needs_no_repeat_sharing_consent(self):
        self.connect()
        source = Mock(id='a' * 64, label='Real-Debrid · 1080p')
        self.client.streams.return_value = [source]
        query = {'action': ['torrentio_find'], 'id': ['tt1234567']}
        self.run_ui(query)
        self.client.streams.assert_called_once_with('tt1234567')
        self.client.playback.assert_not_called()  # Cancel in source picker
        self.dialog.yesno.assert_not_called()
        self.dialog.yesno.return_value = True
        self.dialog.select.return_value = 0
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv|redirect-limit=0'
        self.run_ui(query)
        self.assertEqual(self.client.playback.call_args.args, ('tt1234567', 'a' * 64))
        self.assertIn('cancelled', self.client.playback.call_args.kwargs)
        self.xbmc.Player.return_value.play.assert_called_once()
        self.gui.ListItem.return_value.getVideoInfoTag.return_value.setMediaType.assert_called_once_with('movie')
        self.assertIs(self.xbmc.Player.return_value.play.call_args.args[1], self.gui.ListItem.return_value)
        self.assertNotIn(TOKEN, repr(self.xbmc.mock_calls))

    def test_play_retains_account_effect_confirmation_without_rights_warning(self):
        self.connect()
        self.client.streams.return_value = [Mock(id='a' * 64, label='Real-Debrid')]
        self.dialog.select.return_value = 0
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.client.playback.assert_not_called()
        self.dialog.yesno.assert_called_once()
        message = self.dialog.yesno.call_args.args[1]
        for text in ('history', 'transfer', 'traffic', 'signed URL'):
            self.assertIn(text, message)
        for text in ('permission', 'rights', 'Only play', 'Only use'):
            self.assertNotIn(text, message)

    def test_stale_navigation_or_cancel_prevents_network(self):
        self.connect()
        self.dialog.yesno.return_value = True
        self.xbmc.getInfoLabel.side_effect = ['original', 'new']
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.assertEqual(self.client.mock_calls, [])

    def test_disconnect_and_status_do_not_contact_provider(self):
        self.connect()
        self.dialog.select.return_value = 3
        self.run_ui()
        self.assertIn('not verified', self.dialog.ok.call_args.args[1])
        self.dialog.select.return_value = 4
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.assertIsNone(t.Store(self.temp.name).load())
        self.assertEqual(self.client.mock_calls, [])

    def test_connection_check_is_explicit_and_does_not_claim_account_valid(self):
        self.connect()
        self.dialog.select.return_value = 2
        self.run_ui()
        self.client.check.assert_not_called()
        self.dialog.yesno.return_value = True
        self.run_ui()
        self.client.check.assert_called_once()
        self.assertIn('not verified', self.dialog.ok.call_args.args[1])
