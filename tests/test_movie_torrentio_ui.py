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
        from test_movie_autoplay import load_policy
        from test_movie_history_playback import load as load_history
        bridge = load_history()
        bridge.prepare_history = Mock()
        with patch.dict(sys.modules, {'resources.lib.history_playback': bridge, 'resources.lib.movie_autoplay': load_policy(), 'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin, 'resources.lib.torrentio': t, 'resources.lib.debrid': rd}):
            spec = importlib.util.spec_from_file_location('torrentio_ui_test', path)
            self.ui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.ui)
        self.client = Mock()
        self.ui.Client = Mock(return_value=self.client)
        def started(xbmc, monitor, path, item, current):
            xbmc.Player().play(path, item)
            return 'started'
        self.ui.start_video = Mock(side_effect=started)

    def run_ui(self, query=None):
        self.ui.run(query or {'action': ['torrentio_setup']}, self.temp.name, 'plugin://movies/', 3)

    def connect(self, autoplay=True):
        source = Path(self.temp.name) / 'input.txt'
        source.write_text(MANIFEST)
        source.chmod(0o600)
        t.Store(self.temp.name).import_file(str(source))
        if autoplay:
            t.Store(self.temp.name).set_autoplay_preference(True)
        return str(source)

    def test_sources_directory_never_opens_select_or_resolves_and_uses_only_ids(self):
        from urllib.parse import urlsplit, parse_qs
        self.connect()
        source = t.Source('private-url', 'Example 1998 · 1080p · content unknown', 'one')
        self.client.streams.return_value = [source]
        self.gui.DialogProgress.reset_mock()
        self.run_ui({'action': ['torrentio_sources'], 'home': ['1'], 'id': ['tt1234567'], 'resume': ['1']})
        self.client.streams.assert_called_once_with('tt1234567')
        self.dialog.select.assert_not_called()
        self.gui.DialogProgress.assert_not_called()
        self.client.playback.assert_not_called()
        self.xbmc.Player.assert_not_called()
        self.plugin.addDirectoryItem.assert_called_once()
        args = self.plugin.addDirectoryItem.call_args.args
        query = parse_qs(urlsplit(args[1]).query)
        self.assertEqual(query, {'action': ['torrentio_pick'], 'id': ['tt1234567'],
                                 'source': [source.id], 'resume': ['1']})
        self.assertFalse(args[3])
        self.gui.ListItem.assert_called_with(label='1. ' + source.label)
        self.plugin.endOfDirectory.assert_called_with(3, cacheToDisc=False)

    def test_directory_pick_resolves_exact_fresh_id_with_explicit_resume(self):
        self.connect()
        source = t.Source('private-url', 'Example', 'one')
        self.client.streams.return_value = [source]
        self.gui.DialogProgress.reset_mock()
        self.run_ui({'action': ['torrentio_pick'], 'id': ['tt1234567'],
                     'source': [source.id], 'resume': ['1']})
        self.gui.DialogProgress.assert_not_called()
        self.client.playback.assert_called_once()
        self.assertEqual(self.client.playback.call_args.args, ('tt1234567', source.id))
        self.assertTrue(self.ui.prepare_history.call_args.kwargs['resume'])
        self.gui.ListItem.return_value.getVideoInfoTag.return_value.setUniqueID.assert_any_call('tt1234567', 'aperture_movie')
        self.dialog.select.assert_not_called()
        self.dialog.yesno.assert_not_called()
        self.client.reset_mock()
        self.client.streams.return_value = []
        self.run_ui({'action': ['torrentio_pick'], 'id': ['tt1234567'], 'source': [source.id]})
        self.client.playback.assert_not_called()

    def test_change_source_navigates_only_for_owned_tagged_movie_without_player_control(self):
        player = self.xbmc.Player.return_value
        player.isPlayingVideo.return_value = True
        tag = player.getVideoInfoTag.return_value
        tag.getMediaType.return_value = 'movie'
        ids = {'aperture_session': 'a' * 32, 'aperture_movie': 'tt1234567'}
        tag.getUniqueID.side_effect = ids.get
        self.run_ui({'action': ['torrentio_change']})
        self.xbmc.executebuiltin.assert_called_once_with('ActivateWindow(Videos,plugin://movies/?action=torrentio_sources&id=tt1234567,return)')
        player.pause.assert_not_called()
        player.stop.assert_not_called()
        self.assertEqual(self.client.mock_calls, [])
        self.xbmc.executebuiltin.reset_mock()
        ids['aperture_session'] = ''
        self.run_ui({'action': ['torrentio_change']})
        self.xbmc.executebuiltin.assert_not_called()

    def test_only_extra_sources_explain_auto_rejection_without_resolution(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Trailer', 'one', suitability='extra')]
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.client.playback.assert_not_called()
        self.assertIn('Choose source', str(self.dialog.ok.call_args))
        self.assertIn('trailer', str(self.dialog.ok.call_args).lower())

    def test_directory_error_finishes_without_focused_modal(self):
        self.connect()
        self.client.streams.side_effect = t.ProviderError()
        self.run_ui({'action': ['torrentio_sources'], 'id': ['tt1234567']})
        self.dialog.ok.assert_not_called()
        self.plugin.endOfDirectory.assert_called_once_with(3, succeeded=False, cacheToDisc=False)

    def test_directory_missing_or_empty_connection_has_no_focusable_modal(self):
        self.run_ui({'action': ['torrentio_sources'], 'id': ['tt1234567']})
        self.dialog.ok.assert_not_called()
        self.plugin.endOfDirectory.assert_called_with(3, succeeded=False, cacheToDisc=False)
        self.connect()
        self.client.streams.return_value = []
        self.run_ui({'action': ['torrentio_sources'], 'id': ['tt1234567']})
        self.dialog.ok.assert_not_called()

    def test_cancelled_start_discards_only_its_pending_history(self):
        from test_movie_history import MOVIE, history
        from test_movie_history_playback import load
        import types
        bridge = load()
        self.connect()
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        props = {}
        window = types.SimpleNamespace(getProperty=lambda k: props.get(k, ''),
            setProperty=props.__setitem__, clearProperty=lambda k: props.pop(k, None))
        self.gui.Window.return_value = window
        item = self.gui.ListItem.return_value
        tag = item.getVideoInfoTag.return_value
        tag.setUniqueID.side_effect = lambda token, kind: setattr(tag.getUniqueID, 'return_value', token)
        self.ui.prepare_history = lambda w, i, *a, **kw: bridge.prepare(w, i, MOVIE)
        self.ui.start_video.side_effect = None
        self.ui.start_video.return_value = 'cancelled'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.assertFalse(props.get(bridge.PENDING))
        player = Mock()
        player.isPlayingVideo.return_value = True
        player.getVideoInfoTag.return_value = tag
        player.getTime.return_value = 10
        player.getTotalTime.return_value = 100
        store = history.HistoryStore(Path(self.temp.name) / 'history-private')
        bridge.HistoryMonitor(store, player, window).update()
        self.assertEqual(store.records(), [])

    def test_migration_accepts_once_before_resolver_and_never_repeats(self):
        self.connect(autoplay=False)
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.dialog.yesno.return_value = True
        def resolve(*args, **kwargs):
            self.assertIs(t.Store(self.temp.name).autoplay_preference(), True)
            return 'https://seed.download.real-debrid.com/file.mkv'
        self.client.playback.side_effect = resolve
        for _ in range(2):
            self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.dialog.yesno.assert_called_once()
        self.assertEqual(self.client.playback.call_count, 2)
        marker = Path(self.temp.name) / 'torrentio-private/autoplay-effects-v1'
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)

    def test_navigation_during_migration_prompt_records_no_preference(self):
        self.connect(autoplay=False)
        def answer(*args):
            self.xbmc.getInfoLabel.return_value = 'other'
            return True
        self.dialog.yesno.side_effect = answer
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.assertIsNone(t.Store(self.temp.name).autoplay_preference())
        self.assertEqual(self.client.mock_calls, [])

    def test_existing_connection_declines_versioned_autoplay_once_without_resolving(self):
        self.connect(autoplay=False)
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.dialog.yesno.return_value = False
        for _ in range(2):
            self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.client.playback.assert_not_called()
        self.client.streams.assert_not_called()
        self.dialog.yesno.assert_called_once()
        message = self.dialog.yesno.call_args.args[1]
        for phrase in ('traffic', 'history', 'transfer', 'Choose source'):
            self.assertIn(phrase, message)
        self.assertIsNotNone(t.Store(self.temp.name).load())
        self.dialog.select.return_value = 0
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.client.playback.assert_called_once()
        self.dialog.yesno.assert_called_once()

    def test_setup_records_autoplay_preference_without_revoking_sharing_on_decline(self):
        rd.Store(self.temp.name).save(dict(PAIR, access_token=TOKEN, refresh_token='refresh-fixture', expires_at=1e11))
        self.dialog.select.return_value = 0
        self.dialog.yesno.side_effect = [True, True, False]
        self.run_ui()
        self.assertEqual(t.Store(self.temp.name).load(), 'rd-oauth-v1')
        self.assertIs(t.Store(self.temp.name).autoplay_preference(), False)
        self.assertEqual(self.client.mock_calls, [])

    def test_import_records_autoplay_decline_and_setup_can_change_it(self):
        source = self.connect(autoplay=False)
        t.Store(self.temp.name).clear()
        self.dialog.select.return_value = 1
        self.dialog.browseSingle.return_value = source
        self.dialog.yesno.side_effect = [True, True, False]
        self.run_ui()
        self.assertIsNotNone(t.Store(self.temp.name).load())
        self.assertIs(t.Store(self.temp.name).autoplay_preference(), False)
        self.dialog.select.return_value = 5
        self.dialog.yesno.side_effect = [True]
        self.run_ui()
        self.assertIs(t.Store(self.temp.name).autoplay_preference(), True)
        self.assertEqual(self.client.mock_calls, [])

    def test_real_ui_handoff_records_only_monitor_progress_and_resumes_fresh_url(self):
        from test_movie_history import history, MOVIE
        from test_movie_history_playback import load
        import types
        bridge = load()
        self.connect()
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/new.mkv'
        props = {}
        window = types.SimpleNamespace(getProperty=lambda k: props.get(k, ''),
            setProperty=props.__setitem__, clearProperty=lambda k: props.pop(k, None))
        self.gui.Window.return_value = window
        self.ui.prepare_history = bridge.prepare_history
        item = self.gui.ListItem.return_value
        player = Mock()
        player.isPlayingVideo.return_value = True
        player.getTime.return_value = 14
        player.getTotalTime.return_value = 100
        store = history.HistoryStore(Path(self.temp.name) / 'history-private')
        tracker = bridge.HistoryMonitor(store, player, window)
        def start(*args):
            self.assertEqual(store.records(), [])
            token = item.getVideoInfoTag.return_value.setUniqueID.call_args.args[0]
            player.getVideoInfoTag.return_value.getUniqueID.return_value = token
            tracker.update()
            return 'started'
        self.ui.start_video.side_effect = start
        catalog = types.SimpleNamespace(details=lambda identifier: MOVIE, CatalogError=ValueError)
        with patch.dict(sys.modules, {'resources.lib.catalog': catalog}):
            self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.assertEqual(store.records()[0]['resume_seconds'], 14)
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/rotated.mkv'
        self.ui.start_video.side_effect = None
        self.ui.start_video.return_value = 'started'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567'], 'resume': ['1']})
        self.assertEqual(self.client.playback.call_count, 2)
        self.assertEqual(self.ui.start_video.call_args.args[2], self.client.playback.return_value)
        item.setProperty.assert_called_once_with('StartOffset', '14')
        self.assertNotIn('https://', (store.directory / 'history.json').read_text())

    def test_history_failure_still_tags_unique_startup_session(self):
        from test_movie_history import history
        self.connect()
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.ui.prepare_history.side_effect = history.HistoryError('unavailable')
        item = self.gui.ListItem.return_value
        item.getVideoInfoTag.return_value.getUniqueID.return_value = ''
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        tag = item.getVideoInfoTag.return_value
        self.assertEqual(tag.setUniqueID.call_count, 2)
        tag.setUniqueID.assert_any_call('tt1234567', 'aperture_movie')
        token, kind = tag.setUniqueID.call_args.args
        self.assertRegex(token, r'^[a-f0-9]{32}$')
        self.assertEqual(kind, 'aperture_session')
        self.ui.start_video.assert_called_once()

    def test_history_failure_does_not_prevent_resolved_playback(self):
        from test_movie_history import history
        self.connect()
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/new.mkv'
        self.ui.prepare_history.side_effect = history.HistoryError('private path')
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.ui.start_video.assert_called_once()
        self.assertIn('History unavailable', repr(self.dialog.notification.call_args))
        self.assertNotIn('private path', repr(self.dialog.mock_calls))

    def test_resolved_item_prepares_history_before_play_without_logging_selection(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', '1080p', 'one')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/new.mkv'
        self.assertTrue(hasattr(self.ui, 'prepare_history'), 'Resolved playback needs session handoff')
        events = []
        self.ui.prepare_history.side_effect = lambda *a, **kw: events.append(('prepare', a, kw))
        self.ui.start_video.side_effect = lambda *a: events.append(('play',)) or 'started'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567'], 'resume': ['1']})
        self.assertEqual([e[0] for e in events], ['prepare', 'play'])
        self.assertEqual(events[0][1][2], 'tt1234567')
        self.assertTrue(events[0][2]['resume'])
        self.assertNotIn('new.mkv', repr(events[0]))

    def test_auto_cancel_navigation_or_shutdown_during_resolve_never_retries_or_plays(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', str(i)) for i in range(3)]
        for mode in ('cancel', 'navigation', 'shutdown'):
            for fail in (False, True):
                with self.subTest(mode=mode, fail=fail):
                    self.client.playback.reset_mock()
                    self.gui.DialogProgress.return_value.iscanceled.return_value = False
                    self.xbmc.getInfoLabel.return_value = 'plugin://movies/?mode=online'
                    self.xbmc.Monitor.return_value.abortRequested.return_value = False
                    def resolve(*args, **kwargs):
                        if mode == 'cancel': self.gui.DialogProgress.return_value.iscanceled.return_value = True
                        if mode == 'navigation': self.xbmc.getInfoLabel.return_value = 'other'
                        if mode == 'shutdown': self.xbmc.Monitor.return_value.abortRequested.return_value = True
                        if fail: raise t.ProviderError('failed_rar_v3.mp4')
                        return 'https://seed.download.real-debrid.com/file.mkv'
                    self.client.playback.side_effect = resolve
                    self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
                    self.client.playback.assert_called_once()
                    self.ui.start_video.assert_not_called()
                    self.dialog.ok.assert_not_called()

    def test_auto_real_parser_refetch_resolver_and_av_callbacks_end_to_end(self):
        import json
        from test_movie_torrentio import Response
        from test_movie_autoplay import load_policy
        self.connect()
        events = []
        path = 'https://seed.download.real-debrid.com/file.mkv'
        payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
        def request(url):
            if '/resolve/' in url:
                events.append('resolve')
                return Response(status=302, headers={'Location': path})
            events.append('lookup')
            return Response(json.dumps(payload).encode())
        class Player:
            item = None
            def getVideoInfoTag(self):
                return self.item.getVideoInfoTag() if self.item else Mock(getUniqueID=lambda key: '')
            def play(self, target, item):
                self.item = item
                events.append('play')
                self.target = target
                self.onAVStarted()
            def stop(self): events.append('stop')
            def isPlayingVideo(self): return True
            def getPlayingFile(self): return self.target.split('|', 1)[0]
        self.xbmc.Player = Player
        self.ui.start_video = Mock(wraps=load_policy().start_video)
        self.xbmc.Monitor.return_value.waitForAbort.return_value = False
        with patch.object(self.ui, 'Client', lambda config, **kw: t.Client(config, request=request, **kw)), patch.object(t, 'public_addresses', return_value=[]):
            self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.assertEqual(events, ['lookup', 'lookup', 'resolve', 'play'])
        self.assertEqual(self.xbmc.Monitor.return_value.waitForAbort.call_count, 0)
        self.ui.start_video.assert_called_once()
        self.dialog.yesno.assert_not_called()
        self.dialog.select.assert_not_called()
        self.dialog.ok.assert_not_called()

    def test_manual_selection_verifies_start_but_never_falls_back(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', str(i)) for i in range(3)]
        self.dialog.select.return_value = 0
        self.ui.start_video.side_effect = None
        self.ui.start_video.return_value = 'failed'
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.ui.start_video.assert_called_once()
        self.client.playback.assert_called_once()
        self.assertIn('Choose source', repr(self.dialog.ok.call_args))

    def test_manual_source_choice_has_no_repeated_play_prompt(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', 'one')]
        self.dialog.select.return_value = 0
        self.run_ui({'action': ['torrentio_find'], 'id': ['tt1234567']})
        self.dialog.yesno.assert_not_called()
        self.client.playback.assert_called_once()

    def test_import_and_status_disclose_automatic_effects(self):
        for selected in (1, 3):
            self.dialog.select.return_value = selected
            self.run_ui()
            message = repr(self.dialog.yesno.call_args if selected == 1 else self.dialog.ok.call_args)
            for text in ('automatically', 'history', 'transfer', 'traffic', 'signed URL', 'Choose source'):
                self.assertIn(text, message)

    def test_auto_timeout_explains_manual_recovery_without_retry(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', str(i)) for i in range(3)]
        self.ui.start_video.side_effect = None
        self.ui.start_video.return_value = 'timeout'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.client.playback.assert_called_once()
        self.assertIn('Choose source', repr(self.dialog.ok.call_args))

    def test_auto_home_navigation_during_resolve_discards_late_result(self):
        self.connect()
        self.gui.getCurrentWindowId.return_value = 10025
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', 'one')]
        def resolve(*args, **kwargs):
            self.gui.getCurrentWindowId.return_value = 10000
            return 'https://seed.download.real-debrid.com/file.mkv'
        self.client.playback.side_effect = resolve
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.ui.start_video.assert_not_called()
        self.dialog.ok.assert_not_called()

    def test_auto_skips_explicit_unsupported_source_but_never_retries_account_or_uncertain_errors(self):
        self.connect()
        sources = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', str(i)) for i in range(5)]
        self.client.streams.return_value = sources
        for kind in ('failed_rar_v3.mp4', 'failed_too_big_v2.mp4', 'downloading_v3.mp4',
                     'failed_access_v3.mp4', 'limits_exceeded_v2.mp4', 'resolve', 'network', 'changed'):
            with self.subTest(kind=kind):
                self.client.playback.reset_mock()
                self.client.playback.side_effect = t.ProviderError(kind)
                self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
                expected = 3 if kind in ('failed_rar_v3.mp4', 'failed_too_big_v2.mp4') else 1
                self.assertEqual(self.client.playback.call_count, expected)
                self.assertEqual(len({c.args[1] for c in self.client.playback.call_args_list}), expected)
        self.ui.start_video.assert_not_called()

    def test_auto_fallback_is_three_distinct_sources_after_explicit_player_error(self):
        self.connect()
        sources = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', str(i)) for i in range(5)]
        self.client.streams.return_value = sources
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv'
        self.ui.start_video.side_effect = None
        self.ui.start_video.return_value = 'failed'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.assertEqual([c.args[1] for c in self.client.playback.call_args_list], [s.id for s in sources[:3]])
        self.assertIn('Choose source', repr(self.dialog.ok.call_args))

    def test_auto_uses_av_start_verification(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', 'one')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv'
        self.assertTrue(hasattr(self.ui, 'start_video'), 'UI must verify actual AV start')
        with patch.object(self.ui, 'start_video', return_value='started') as start:
            self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        start.assert_called_once()
        self.assertEqual(start.call_args.args[2], self.client.playback.return_value)
        self.dialog.ok.assert_not_called()

    def test_auto_has_no_repeated_effect_or_rights_confirmation(self):
        self.connect()
        self.client.streams.return_value = [t.Source('unused', 'Real-Debrid · 1080p · AVC · English', 'one')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.dialog.yesno.assert_not_called()
        self.client.playback.assert_called_once()

    def test_setup_discloses_automatic_play_account_effects(self):
        self.dialog.select.return_value = 0
        self.run_ui()
        message = self.dialog.yesno.call_args.args[1]
        for text in ('automatically', 'history', 'transfer', 'traffic', 'signed URL', 'Choose source'):
            self.assertIn(text, message)

    def test_auto_selects_best_source_without_picker(self):
        self.connect()
        self.dialog.yesno.return_value = True
        self.client.streams.return_value = [
            t.Source('unused', 'Real-Debrid · 2160p · HEVC · English', 'large'),
            t.Source('unused', 'Real-Debrid · 1080p · AVC · English', 'suitable')]
        self.client.playback.return_value = 'https://seed.download.real-debrid.com/file.mkv'
        self.run_ui({'action': ['torrentio_auto'], 'id': ['tt1234567']})
        self.client.streams.assert_called_once_with('tt1234567')
        self.assertEqual(self.client.playback.call_args.args, ('tt1234567', self.client.streams.return_value[1].id))
        self.dialog.select.assert_not_called()
        self.xbmc.Player.return_value.play.assert_called_once()

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
        self.dialog.yesno.side_effect = [True, True, True]
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
