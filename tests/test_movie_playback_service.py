"""Offline Kodi boundary fakes; never contacts or controls a running Kodi."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class MoviePlaybackServiceTests(unittest.TestCase):
    def setUp(self):
        self.xbmc, self.gui = Mock(), Mock()
        self.gui.Window.return_value.getProperty.return_value = ''
        self.window = 12005  # Fullscreen video, not the topmost dialog.
        self.video, self.movie, self.playing = True, True, True
        self.gui.getCurrentWindowId.side_effect = lambda: self.window
        self.xbmc.getCondVisibility.side_effect = lambda key: {
            'Player.HasVideo': self.video,
            'VideoPlayer.Content(movies)': self.movie,
            'Player.Playing': self.playing,
        }.get(key, False)
        path = ROOT / 'movies-kodi/playback_service.py'
        self.assertTrue(path.is_file(), 'Missing independent Movies playback service')
        with patch.dict(sys.modules, {'xbmc': self.xbmc, 'xbmcgui': self.gui}):
            spec = importlib.util.spec_from_file_location('movie_playback_test', path)
            assert spec is not None and spec.loader is not None
            self.service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.service)
        self.guard = self.service.MoviePauseOnExit()
        # Service lifecycle tests isolate Kodi's unavailable profile boundary.
        self.history_factory = self.service.history_monitor
        factory = patch.object(self.service, 'history_monitor')
        factory.start()
        self.addCleanup(factory.stop)

    def test_native_exit_signal_pauses_even_when_fullscreen_falls_between_polls(self):
        # CI: fullscreen init 11:08:05.259, deinit .287, polls every 100 ms.
        home = self.gui.Window.return_value
        home.getProperty.return_value = 'resume-session'
        tag = self.xbmc.Player.return_value.getVideoInfoTag.return_value
        tag.getUniqueID.return_value = 'resume-session'
        self.window = 10025
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_called_once()
        home.clearProperty.assert_called_once_with('Aperture.Movies.FullscreenExit')

    def test_native_exit_signal_is_consumed_without_pausing_replacement_or_transient(self):
        for token, current, window, playing in (
                ('old-session', 'new-session', 10025, True),
                ('same-session', 'same-session', 12901, True),
                ('same-session', 'same-session', 10025, False)):
            with self.subTest(token=token, window=window, playing=playing):
                self.gui.Window.return_value.getProperty.return_value = token
                self.xbmc.Player.return_value.getVideoInfoTag.return_value.getUniqueID.return_value = current
                self.window, self.playing = window, playing
                self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()
        self.assertEqual(self.gui.Window.return_value.clearProperty.call_count, 3)

    def test_native_exit_signal_is_one_shot_even_if_pause_state_lags(self):
        home = self.gui.Window.return_value
        home.getProperty.side_effect = ['session', '']
        self.xbmc.Player.return_value.getVideoInfoTag.return_value.getUniqueID.return_value = 'session'
        self.window = 10025
        self.guard.update()
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_called_once()

    def test_exit_arriving_mid_sample_is_retained_until_browser_sample(self):
        home = self.gui.Window.return_value
        home.getProperty.return_value = 'session'
        self.xbmc.Player.return_value.getVideoInfoTag.return_value.getUniqueID.return_value = 'session'
        # Native unload can publish after the service already read window 12005.
        self.guard.update()
        home.clearProperty.assert_not_called()
        self.window = 10025
        self.guard.update()
        home.clearProperty.assert_called_once_with('Aperture.Movies.FullscreenExit')
        self.xbmc.executeJSONRPC.assert_called_once()

    def test_owner_change_during_pause_decision_does_not_pause_replacement(self):
        tag = self.xbmc.Player.return_value.getVideoInfoTag.return_value
        tag.getUniqueID.return_value = 'movie-a'
        self.guard.update()
        self.window = 10025
        tag.getUniqueID.side_effect = ['movie-a', 'movie-b']
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()

    def test_replacement_movie_in_browser_does_not_inherit_fullscreen(self):
        player = self.xbmc.Player.return_value
        tag = player.getVideoInfoTag.return_value
        tag.getUniqueID.return_value = 'movie-a-session'
        player.getPlayingFile.return_value = 'same-file'
        self.guard.update()
        tag.getUniqueID.return_value = 'movie-b-session'
        self.window = 10025
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()
        self.window = 12005
        self.guard.update()
        self.window = 10025
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_called_once()

    def test_non_movie_or_stopped_player_is_never_paused(self):
        for video, movie, playing in ((False, True, True), (True, False, True),
                                      (True, True, False)):
            with self.subTest(video=video, movie=movie, playing=playing):
                self.video, self.movie, self.playing = video, movie, playing
                self.window = 12005
                self.guard.update()
                self.window = 10000
                self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()

    def test_transient_windows_do_not_count_as_browsing(self):
        for window in (12901, 12002, 10160, 10124):  # OSD, info, subtitle, seek
            self.window = 12005
            self.guard.update()
            self.window = window
            self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()

    def test_home_pauses_but_startup_and_overlay_dialogs_do_not(self):
        self.window = 10000
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()
        self.window = 12005
        for dialog in (9999, 12901, 10160, 10124):
            self.gui.getCurrentWindowDialogId.return_value = dialog
            self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()
        self.window = 10000
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_called_once()

    def test_transient_sample_then_home_still_pauses(self):
        self.guard.update()
        self.window = 12901
        self.guard.update()
        self.window = 10000
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_called_once()

    def test_non_movie_fullscreen_cannot_arm_next_movie_in_browser(self):
        self.movie = False
        self.guard.update()
        self.movie = True
        self.window = 10025
        self.guard.update()
        self.xbmc.executeJSONRPC.assert_not_called()

    def test_service_factory_uses_only_translated_private_history_directory(self):
        import tempfile
        import types
        from test_movie_history import history
        from test_movie_history_playback import load
        with tempfile.TemporaryDirectory() as profile:
            addon = types.SimpleNamespace(getAddonInfo=lambda key: 'special://synthetic-profile')
            vfs = Mock()
            vfs.translatePath.return_value = profile
            with patch.dict(sys.modules, {'xbmcaddon': types.SimpleNamespace(Addon=lambda: addon),
                    'xbmcvfs': vfs, 'resources.lib.movie_history': history,
                    'resources.lib.history_playback': load()}):
                tracker = self.history_factory()
            self.assertEqual(tracker.store.directory, Path(profile) / 'history-private')
            self.assertEqual(list(Path(profile).iterdir()), [])
            vfs.translatePath.assert_called_once_with('special://synthetic-profile')
            self.assertIs(tracker.player, self.xbmc.Player.return_value)
            self.gui.Window.assert_called_once_with(10000)

    def test_service_polls_history_in_same_serial_loop_as_pause(self):
        monitor = self.xbmc.Monitor.return_value
        monitor.abortRequested.return_value = False
        monitor.waitForAbort.side_effect = [False, True]
        self.assertTrue(hasattr(self.service, 'history_monitor'), 'Service must construct real history monitor')
        with patch.object(self.service, 'history_monitor') as factory:
            self.service.run()
        self.assertEqual(factory.return_value.update.call_count, 2)
        factory.return_value.close.assert_called_once_with()

    def test_service_runs_until_abort_without_touching_format(self):
        monitor = self.xbmc.Monitor.return_value
        monitor.abortRequested.return_value = False
        monitor.waitForAbort.side_effect = [False, True]
        self.assertTrue(hasattr(self.service, 'run'), 'Service needs a bounded Kodi monitor loop')
        with patch.object(self.service, 'MoviePauseOnExit') as guard:
            self.service.run()
        self.assertEqual(guard.return_value.update.call_count, 2)
        monitor.waitForAbort.assert_called_with(0.1)
        self.xbmc.executebuiltin.assert_not_called()

    def test_player_teardown_error_does_not_kill_service_or_retry_pause(self):
        monitor = self.xbmc.Monitor.return_value
        monitor.abortRequested.return_value = False
        monitor.waitForAbort.side_effect = [False, True]
        self.gui.getCurrentWindowId.side_effect = RuntimeError('private player detail')
        self.service.run()
        self.xbmc.executeJSONRPC.assert_not_called()
        self.xbmc.log.assert_not_called()

    def test_manifest_registers_independent_service(self):
        import xml.etree.ElementTree as ET
        root = ET.parse(ROOT / 'movies-kodi/addon.xml').getroot()
        service = root.find("extension[@point='xbmc.service']")
        self.assertIsNotNone(service, 'Movies must start its own service')
        assert service is not None
        self.assertEqual(service.get('library'), 'playback_service.py')

    def test_back_to_browsing_pauses_movie_once_without_resume(self):
        self.guard.update()
        self.window = 10025
        self.guard.update()
        self.guard.update()
        self.window = 12005
        self.guard.update()
        self.assertEqual(self.xbmc.executeJSONRPC.call_count, 1)
        import json
        request = json.loads(self.xbmc.executeJSONRPC.call_args.args[0])
        self.assertEqual(request['method'], 'Player.PlayPause')
        self.assertEqual(request['params'], {'playerid': 1, 'play': False})
