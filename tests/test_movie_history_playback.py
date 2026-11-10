"""Real private store, synthetic Kodi boundaries; no live player/profile."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_movie_history import history, MOVIE

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = ROOT / 'movies-kodi/resources/lib/history_playback.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('history_playback_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'resources.lib.movie_history': history}):
        spec.loader.exec_module(module)
    return module


class HistoryPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.module = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = history.HistoryStore(Path(self.tmp.name) / 'history')
        self.props = {}
        self.window = Mock()
        self.window.getProperty.side_effect = lambda k: self.props.get(k, '')
        self.window.setProperty.side_effect = self.props.__setitem__
        self.window.clearProperty.side_effect = lambda k: self.props.pop(k, None)
        self.player = Mock()
        self.player.isPlayingVideo.return_value = True
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = 'unrelated'
        self.player.getTime.return_value = 10
        self.player.getTotalTime.return_value = 100
        self.clock = [100.0]
        self.notice = Mock()

    def monitor(self):
        self.assertIsNotNone(self.module, 'Playback history bridge is missing')
        return self.module.HistoryMonitor(self.store, self.player, self.window,
                                          clock=lambda: self.clock[0], notify=self.notice)

    def arm(self):
        item = Mock()
        token = self.module.prepare(self.window, item, MOVIE, epoch='', now=self.clock[0])
        item.getVideoInfoTag.return_value.setUniqueID.assert_called_once_with(token, 'aperture_session')
        return token

    def test_abandoned_start_does_not_discard_newer_history_handoff(self):
        old = self.arm()
        new = self.arm()
        item = Mock()
        item.getVideoInfoTag.return_value.getUniqueID.return_value = old
        self.module.discard_pending(self.window, item)
        self.assertEqual(json.loads(self.props[self.module.PENDING])['session'], new)

    def test_new_selection_after_clear_records_immediately(self):
        monitor = self.monitor()
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        request = self.module.request_clear(self.window)
        monitor.update()
        token = self.module.prepare(self.window, Mock(), MOVIE, epoch=request, now=self.clock[0])
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        self.assertEqual(len(self.store.records()), 1)

    def test_invalid_identity_is_rejected_before_metadata_lookup(self):
        self.assertIsNotNone(self.module)
        catalog = Mock()
        with patch.dict(sys.modules, {'resources.lib.catalog': catalog}):
            for identifier in ('tt1234567\n', ' tt1234567', 'tt１２３４５６７', 'tt123'):
                with self.assertRaises(history.HistoryError):
                    self.module.prepare_history(self.window, Mock(), identifier,
                                                profile=self.tmp.name, epoch='', store=self.store)
        catalog.details.assert_not_called()
        self.assertEqual(self.props, {})

    def test_malformed_handoff_and_player_switch_mid_sample_fail_closed(self):
        monitor = self.monitor()
        for raw in ('not-json', '[]', '{}', '{"session": "x"}'):
            self.props[self.module.PENDING] = raw
            monitor.update()
            self.assertEqual(self.store.records(), [])
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.side_effect = [token, 'other']
        monitor.update()
        self.assertEqual(self.store.records(), [], 'Do not assign another player progress to pending movie')
        self.player.stop.assert_not_called()

    def test_metadata_outage_becomes_history_error_without_pending_or_write(self):
        self.assertIsNotNone(self.module)
        catalog = Mock()
        class CatalogError(Exception):
            pass
        catalog.CatalogError = CatalogError
        catalog.details.side_effect = CatalogError('private remote value')
        with patch.dict(sys.modules, {'resources.lib.catalog': catalog}):
            with self.assertRaises(history.HistoryError):
                self.module.prepare_history(self.window, Mock(), MOVIE['id'],
                                            profile=self.tmp.name, epoch='', store=self.store)
        self.assertEqual(self.props, {})
        self.assertEqual(self.store.records(), [])

    def test_explicit_resume_uses_only_saved_position_on_new_item(self):
        self.assertIsNotNone(self.module)
        self.assertTrue(hasattr(self.module, 'prepare_history'), 'Missing metadata/resume adapter')
        self.store.record_playback(MOVIE, is_playing=True, position_seconds=42,
                                   duration_seconds=100, lastplayed=1)
        item = Mock()
        catalog = Mock()
        catalog.details.return_value = MOVIE
        with patch.dict(sys.modules, {'resources.lib.catalog': catalog}):
            self.module.prepare_history(self.window, item, MOVIE['id'],
                                        profile=self.tmp.name, epoch='', resume=True,
                                        store=self.store)
        item.setProperty.assert_called_once_with('StartOffset', '42')
        self.assertEqual(self.store.records()[0]['lastplayed'], 1)
        self.assertTrue(self.window.getProperty(self.module.PENDING))
        item.reset_mock()
        with patch.dict(sys.modules, {'resources.lib.catalog': catalog}):
            self.module.prepare_history(self.window, item, MOVIE['id'],
                                        profile=self.tmp.name, epoch='', resume=False,
                                        store=self.store)
        item.setProperty.assert_not_called()

    def test_shutdown_and_teardown_keep_only_last_valid_observation(self):
        monitor = self.monitor()
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        self.player.getTime.return_value = 23
        monitor.update()
        self.player.getTime.side_effect = RuntimeError('private player state')
        monitor.update()
        self.assertTrue(hasattr(monitor, 'close'), 'Service shutdown must flush safely')
        monitor.close()
        self.assertEqual(self.store.records()[0]['resume_seconds'], 23)
        self.assertEqual(self.window.getProperty(self.module.PENDING), '')
        self.player.stop.assert_not_called()

    def test_pending_expires_and_consumed_session_cannot_restart(self):
        monitor = self.monitor()
        token = self.arm()
        pending = self.window.getProperty(self.module.PENDING)
        self.clock[0] += 31
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        self.assertEqual(self.store.records(), [])
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        self.assertTrue(self.store.records())
        self.assertEqual(self.window.getProperty(self.module.PENDING), '')
        self.player.getTime.return_value = 25
        monitor.update()
        self.player.isPlayingVideo.return_value = False
        monitor.update()
        self.player.isPlayingVideo.return_value = True
        self.player.getTime.return_value = 60
        monitor.update()
        self.assertEqual(self.store.records()[0]['resume_seconds'], 25)
        # Even a queued old-epoch handoff cannot revive after clear.
        self.module.request_clear(self.window)
        monitor.update()
        self.props[self.module.PENDING] = pending
        monitor.update()
        self.assertEqual(self.store.records(), [])

    def test_storage_failures_are_generic_and_never_interrupt_player(self):
        monitor = self.monitor()
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        with patch.object(self.store, 'record_playback', side_effect=history.HistoryError('private path')) as write:
            monitor.update()
            monitor.update()
            self.assertEqual(write.call_count, 1)
            self.notice.assert_called_once_with()
            self.player.isPlayingVideo.return_value = False
            monitor.update()
        self.player.stop.assert_not_called()
        self.module.request_clear(self.window)
        with patch.object(self.store, 'clear', side_effect=history.HistoryError('private path')):
            monitor.update()
        self.assertEqual(self.window.getProperty(self.module.CLEAR_ACK), '')
        self.assertEqual(self.window.getProperty(self.module.CLEAR), '')

    def test_clear_cancels_pending_active_and_late_resolver_handoffs(self):
        monitor = self.monitor()
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        monitor.update()
        self.assertTrue(self.store.records())
        self.assertTrue(hasattr(self.module, 'request_clear'), 'Clear must serialize through service')
        request = self.module.request_clear(self.window)
        monitor.update()
        self.assertEqual(self.store.records(), [])
        self.assertEqual(self.window.getProperty(self.module.CLEAR_ACK), request)
        self.player.getTime.return_value = 50
        monitor.update()
        self.player.isPlayingVideo.return_value = False
        monitor.update()
        self.assertEqual(self.store.records(), [])
        self.assertIsNone(self.module.prepare(self.window, Mock(), MOVIE, epoch='', now=self.clock[0]))
        self.player.stop.assert_not_called()

    def test_throttles_writes_and_stop_flushes_last_valid_sample(self):
        monitor = self.monitor()
        token = self.arm()
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        with patch.object(self.store, 'record_playback', wraps=self.store.record_playback) as write:
            monitor.update()
            self.clock[0] += 10
            self.player.getTime.return_value = 30
            monitor.update()
            self.assertEqual(write.call_count, 1, 'Periodic writes must be throttled')
            self.clock[0] += 10
            monitor.update()
            self.assertEqual(write.call_count, 2)
            self.player.getTime.return_value = 42
            monitor.update()
            self.player.isPlayingVideo.return_value = False
            self.player.getTime.side_effect = RuntimeError('player gone')
            monitor.update()
            self.assertEqual(self.store.records()[0]['resume_seconds'], 42)
            monitor.update()
            self.assertEqual(write.call_count, 3)

    def test_only_matching_positive_progress_records_safe_metadata(self):
        monitor = self.monitor()
        token = self.arm()
        monitor.update()
        self.assertEqual(self.store.records(), [])
        self.player.getVideoInfoTag.return_value.getUniqueID.return_value = token
        self.player.getTime.return_value = 0
        monitor.update()
        self.assertEqual(self.store.records(), [])
        self.player.getTime.return_value = 10
        monitor.update()
        self.assertEqual(self.store.records()[0]['resume_seconds'], 10)
        raw = (self.store.directory / 'history.json').read_text()
        for secret in ('https://', 'secret', token, 'poster'):
            self.assertNotIn(secret, raw)
        self.assertNotIn('secret', repr(self.props))
        self.player.getPlayingFile.assert_not_called()
