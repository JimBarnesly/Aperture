"""Offline source policy and Kodi-start lifecycle; never uses accounts."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'movies-kodi/resources/lib/movie_autoplay.py'


def load_policy():
    spec = importlib.util.spec_from_file_location('movie_autoplay_test', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlayerTests(unittest.TestCase):
    def test_active_player_error_is_not_safe_to_retry_until_quiescent(self):
        policy = load_policy()
        events = []
        class Player:
            def play(self, path, item): self.onPlayBackError()
            def isPlayingVideo(self): return True
            def getPlayingFile(self): return 'file'
            def stop(self): events.append('stop')
        result = policy.start_video(SimpleNamespace(Player=Player), SimpleNamespace(waitForAbort=lambda _: False), 'file', object(), lambda: True)
        self.assertEqual(result, 'timeout')
        self.assertIn('stop', events)

    def test_cancel_navigation_and_stop_do_not_become_failure_retries(self):
        policy = load_policy()
        for mode in ('cancel', 'shutdown', 'stop', 'error', 'ended', 'wrong-file'):
            with self.subTest(mode=mode):
                events = []
                class Player:
                    def play(self, path, item):
                        events.append('request')
                        getattr(self, {'stop':'onPlayBackStopped', 'error':'onPlayBackError', 'ended':'onPlayBackEnded'}.get(mode, 'onAVStarted'), lambda: None)()
                    def stop(self): events.append('stop')
                    def isPlayingVideo(self): return mode == 'wrong-file'
                    def getPlayingFile(self): return 'other'
                count = [0]
                def current():
                    count[0] += 1
                    return mode != 'cancel' or count[0] < 2
                monitor = SimpleNamespace(waitForAbort=lambda _: mode == 'shutdown')
                result = policy.start_video(SimpleNamespace(Player=Player), monitor, 'file', object(), current)
                self.assertEqual(result, 'failed' if mode == 'error' else 'cancelled')
                if mode in ('cancel', 'shutdown'):
                    self.assertIn('stop', events)
                if mode == 'wrong-file':
                    self.assertNotIn('stop', events)

    def test_only_matching_actual_av_start_is_success(self):
        policy = load_policy()
        events = []
        class Player:
            def play(self, path, item):
                events.append('request')
                self.onAVStarted()
            def onAVStarted(self): pass
            def isPlayingVideo(self): return True
            def getPlayingFile(self): return 'file'
            def stop(self): events.append('stop')
        result = policy.start_video(SimpleNamespace(Player=Player), SimpleNamespace(waitForAbort=lambda _: False), 'file', object(), lambda: True)
        self.assertEqual(result, 'started')
        self.assertEqual(events, ['request'])

    def test_request_queued_is_not_success_and_is_stopped_at_deadline(self):
        policy = load_policy()
        self.assertTrue(hasattr(policy, 'start_video'), 'Missing actual AV-start verification')
        events = []
        class Player:
            def play(self, path, item): events.append('request')
            def stop(self): events.append('stop')
            def isPlayingVideo(self): return False
            def isPlaying(self): return False
        monitor = SimpleNamespace(waitForAbort=lambda seconds: False)
        result = policy.start_video(SimpleNamespace(Player=Player), monitor, 'file', object(), lambda: True)
        self.assertEqual(result, 'timeout')
        self.assertEqual(events, ['request', 'stop'])


class RankingTests(unittest.TestCase):
    def test_1080p_hevc_beats_oversized_4k_avc(self):
        policy = load_policy()
        sources = [SimpleNamespace(id='4k', label='2160p · AVC · English'), SimpleNamespace(id='hd', label='1080p · HEVC · English')]
        self.assertEqual(policy.rank_sources(sources)[0].id, 'hd')

    def test_known_suitable_decode_beats_1080p_av1(self):
        policy = load_policy()
        sources = [SimpleNamespace(id='av1', label='1080p · AV1 · English'), SimpleNamespace(id='avc', label='720p · AVC · English')]
        self.assertEqual(policy.rank_sources(sources)[0].id, 'avc')

    def test_deduplicates_stable_ids_and_keeps_unknown_ties_stable(self):
        policy = load_policy()
        sources = [SimpleNamespace(id=i, label='Real-Debrid · quality unspecified · codec unspecified · language unspecified') for i in ('b', 'a', 'b')]
        self.assertEqual([s.id for s in policy.rank_sources(sources)], ['b', 'a'])

    def test_prefers_english_1080p_avc_not_largest_or_highest(self):
        self.assertTrue(PATH.exists(), 'Missing automatic source policy')
        policy = load_policy()
        sources = [SimpleNamespace(id=str(i), label=label) for i, label in enumerate([
            'Real-Debrid · 2160p · HEVC · English · 80.0 GiB',
            'Real-Debrid · 1080p · H264 · English · 2.0 GiB',
            'Real-Debrid · 1080p · AV1 · English · 8.0 GiB',
            'Real-Debrid · 1080p · x264 · French · 3.0 GiB',
            'Real-Debrid · 720p · AVC · English · 1.0 GiB',
        ])]
        self.assertEqual(policy.rank_sources(sources)[0].id, '1')
        self.assertEqual([s.id for s in sources], ['0', '1', '2', '3', '4'])
