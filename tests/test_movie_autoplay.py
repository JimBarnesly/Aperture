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


class LifecycleTests(unittest.TestCase):
    """Callbacks and waits can switch global Kodi ownership at any boundary."""
    def setUp(self):
        self.owner = 'predecessor'
        self.video = True
        self.events = []
        self.ticks = 0
        self.on_wait = lambda: None
        self.on_play = lambda: None
        self.is_current = lambda: True
        self.aborting = False
        test = self
        self.item = SimpleNamespace(getVideoInfoTag=lambda: SimpleNamespace(
            getUniqueID=lambda key: 'requested'))
        class Player:
            def __init__(self): test.player = self
            def getVideoInfoTag(self):
                return SimpleNamespace(getUniqueID=lambda key: test.owner)
            def getPlayingFile(self): return 'new-file' if test.owner == 'requested' else 'old-file'
            def isPlayingVideo(self): return test.video
            def isPlaying(self): return test.video
            def play(self, path, item):
                test.events.append('play')
                test.on_play()
            def stop(self): test.events.append(('stop', test.owner))
        self.xbmc = SimpleNamespace(Player=Player)
        def wait(seconds):
            self.ticks += 1
            self.on_wait()
            return self.aborting
        self.monitor = SimpleNamespace(waitForAbort=wait)

    def start(self):
        return load_policy().start_video(self.xbmc, self.monitor, 'new-file',
                                         self.item, lambda: self.is_current())

    def test_owned_error_switch_during_active_check_never_stops_replacement(self):
        self.owner = 'requested'
        def play():
            self.player.onPlayBackError()
            def active():
                self.owner = 'replacement'
                return True
            self.player.isPlayingVideo = active
        self.on_play = play
        self.assertEqual(self.start(), 'timeout')
        self.assertEqual(self.events, ['play'])

    def test_failure_owner_lost_before_quiescence_check_never_retries(self):
        self.owner = 'requested'
        def play():
            self.player.onPlayBackError()
            def quiescent():
                self.owner = ''
                return False
            self.player.isPlayingVideo = quiescent
        self.on_play = play
        self.assertNotEqual(self.start(), 'failed')
        self.assertEqual(self.events, ['play'])

    def test_replacement_same_file_does_not_inherit_predecessor_ownership(self):
        self.on_wait = lambda: setattr(self, 'owner', 'replacement')
        self.assertEqual(self.start(), 'cancelled')
        self.assertEqual(self.ticks, 1)
        self.assertEqual(self.events, ['play'])

    def test_missing_session_never_uses_same_file_as_ownership(self):
        self.owner = ''
        self.item = SimpleNamespace(getVideoInfoTag=lambda: SimpleNamespace(
            getUniqueID=lambda key: ''))
        self.on_play = lambda: self.player.onAVStarted()
        self.assertEqual(self.start(), 'timeout')
        self.assertEqual(self.events, ['play'])

    def test_unreadable_owner_is_not_stopped_or_reported_as_started(self):
        self.owner = 'requested'
        def play():
            def unavailable():
                raise RuntimeError('player gone')
            self.player.getVideoInfoTag = unavailable
            self.player.onAVStarted()
        self.on_play = play
        self.assertEqual(self.start(), 'timeout')
        self.assertEqual(self.events, ['play'])

    def test_predecessor_av_callback_cannot_certify_requested_session(self):
        self.on_play = lambda: self.player.onAVStarted()
        self.on_wait = lambda: setattr(self, 'owner', 'requested')
        self.assertEqual(self.start(), 'timeout')

    def test_cancelled_pending_open_is_observed_until_owned_then_stopped(self):
        self.is_current = lambda: self.ticks == 0
        def wait():
            if self.ticks == 2:
                self.owner = 'requested'
                self.player.onAVStarted()
        self.on_wait = wait
        self.assertEqual(self.start(), 'cancelled')
        self.assertEqual(self.ticks, 2)
        self.assertEqual(self.events, ['play', ('stop', 'requested')])

    def test_stop_rechecks_owner_after_current_abort_and_deadline(self):
        for boundary in ('current', 'abort', 'deadline', 'unknown'):
            with self.subTest(boundary=boundary):
                self.setUp()
                self.owner = 'requested'
                def changed():
                    if boundary == 'current' and 'play' in self.events:
                        self.owner = 'replacement'
                        return False
                    return True
                self.is_current = changed
                def wait():
                    if boundary != 'deadline' or self.ticks == 150:
                        self.owner = '' if boundary == 'unknown' else 'replacement'
                        self.aborting = boundary in ('abort', 'unknown')
                self.on_wait = wait
                self.assertIn(self.start(), ('cancelled', 'timeout'))
                self.assertEqual(self.events, ['play'])

    def test_unrelated_error_during_pending_open_does_not_allow_fallback(self):
        def transition():
            if self.ticks == 1:
                self.video = False
                self.player.onPlayBackError()
            else:
                self.video = True
                self.owner = 'requested'
                self.player.onAVStarted()
        self.on_wait = transition
        self.assertEqual(self.start(), 'started')
        self.assertEqual(self.ticks, 2)
        self.assertEqual(self.events, ['play'])

    def test_predecessor_stop_then_requested_av_start_is_not_cancelled(self):
        def transition():
            self.player.onPlayBackStopped()
            self.owner = 'requested'
            self.player.onAVStarted()
        self.on_wait = transition
        self.assertEqual(self.start(), 'started')
        self.assertEqual(self.events, ['play'])
        self.assertEqual(self.ticks, 1)


def tagged_item(token='requested'):
    return SimpleNamespace(getVideoInfoTag=lambda: SimpleNamespace(
        getUniqueID=lambda key: token))


class PlayerTests(unittest.TestCase):
    def test_active_player_error_is_not_safe_to_retry_until_quiescent(self):
        policy = load_policy()
        events = []
        class Player:
            def getVideoInfoTag(self): return tagged_item().getVideoInfoTag()
            def play(self, path, item): self.onPlayBackError()
            def isPlayingVideo(self): return True
            def getPlayingFile(self): return 'file'
            def stop(self): events.append('stop')
        result = policy.start_video(SimpleNamespace(Player=Player), SimpleNamespace(waitForAbort=lambda _: False), 'file', tagged_item(), lambda: True)
        self.assertEqual(result, 'timeout')
        self.assertIn('stop', events)

    def test_cancel_navigation_and_stop_do_not_become_failure_retries(self):
        policy = load_policy()
        for mode in ('cancel', 'shutdown', 'stop', 'error', 'ended', 'wrong-file'):
            with self.subTest(mode=mode):
                events = []
                class Player:
                    def getVideoInfoTag(self):
                        return tagged_item('other' if mode == 'wrong-file' else 'requested').getVideoInfoTag()
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
                result = policy.start_video(SimpleNamespace(Player=Player), monitor, 'file', tagged_item(), current)
                self.assertEqual(result, 'failed' if mode == 'error' else 'timeout' if mode == 'wrong-file' else 'cancelled')
                if mode in ('cancel', 'shutdown'):
                    self.assertIn('stop', events)
                if mode == 'wrong-file':
                    self.assertNotIn('stop', events)

    def test_only_matching_actual_av_start_is_success(self):
        policy = load_policy()
        events = []
        class Player:
            def getVideoInfoTag(self): return tagged_item().getVideoInfoTag()
            def play(self, path, item):
                events.append('request')
                self.onAVStarted()
            def onAVStarted(self): pass
            def isPlayingVideo(self): return True
            def getPlayingFile(self): return 'file'
            def stop(self): events.append('stop')
        result = policy.start_video(SimpleNamespace(Player=Player), SimpleNamespace(waitForAbort=lambda _: False), 'file', tagged_item(), lambda: True)
        self.assertEqual(result, 'started')
        self.assertEqual(events, ['request'])

    def test_request_queued_is_not_success_and_is_stopped_at_deadline(self):
        policy = load_policy()
        self.assertTrue(hasattr(policy, 'start_video'), 'Missing actual AV-start verification')
        events = []
        class Player:
            def getVideoInfoTag(self): return tagged_item().getVideoInfoTag()
            def play(self, path, item): events.append('request')
            def stop(self): events.append('stop')
            def isPlayingVideo(self): return False
            def isPlaying(self): return False
        monitor = SimpleNamespace(waitForAbort=lambda seconds: False)
        result = policy.start_video(SimpleNamespace(Player=Player), monitor, 'file', tagged_item(), lambda: True)
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
