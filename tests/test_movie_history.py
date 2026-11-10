"""Offline integration tests for the private Movies history core."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'movies-kodi/resources/lib'


def load_module(name):
    path = LIB / (name + '.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


history = load_module('movie_history')
MOVIE = {'id': 'tt1234567', 'title': 'Example', 'year': '2024',
         'genre': ['Drama', 'Comedy'], 'url': 'https://private/secret',
         'token': 'secret', 'poster': 'https://public/image'}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / 'history'

    def store(self, **kwargs):
        self.assertIsNotNone(history, 'movie_history core is not implemented')
        return history.HistoryStore(self.directory, **kwargs)

    def test_selection_or_invalid_playback_never_creates_history(self):
        invalid = [dict(is_playing=False), dict(is_playing='yes'),
                   dict(position_seconds=0), dict(position_seconds=-1),
                   dict(position_seconds=float('nan')),
                   dict(duration_seconds=float('inf')),
                   dict(lastplayed=-1), dict(position_seconds=True)]
        for changes in invalid:
            with self.subTest(changes=changes):
                args = dict(is_playing=True, position_seconds=1,
                            duration_seconds=100, lastplayed=1000)
                args.update(changes)
                self.assertFalse(self.store().record_playback(MOVIE, **args))
                self.assertFalse(self.directory.exists())
        for identifier in ['tt12345\n', ' tt1234567', 'tt１２３４５６７',
                           'tt123', 'tt1234567?token=x', 123]:
            with self.subTest(identifier=identifier):
                self.assertFalse(self.store().record_playback(
                    dict(MOVIE, id=identifier), is_playing=True,
                    position_seconds=1, duration_seconds=100, lastplayed=1000))
                self.assertFalse(self.directory.exists())

    def play(self, store, movie=MOVIE, position=10, duration=100, when=1000):
        return store.record_playback(movie, is_playing=True, position_seconds=position,
                                     duration_seconds=duration, lastplayed=when)

    def test_completion_threshold_and_rewatch_resume(self):
        store = self.store()
        self.play(store, position=89)
        self.assertFalse(store.records()[0]['completed'])
        self.play(store, position=90, when=1001)
        self.assertTrue(store.records()[0]['completed'])
        self.assertEqual(store.records()[0]['resume_seconds'], 0)
        self.play(store, position=10, when=1002)
        self.assertTrue(store.records()[0]['completed'])
        self.assertEqual(store.records()[0]['resume_seconds'], 10)
        self.play(store, position=120, duration=0, when=1003)
        self.assertEqual(store.records()[0]['duration_seconds'], 0)
        self.assertEqual(store.records()[0]['resume_seconds'], 120)
        self.play(store, position=1, when=999)
        self.assertEqual(store.records()[0]['lastplayed'], 1003)

    def test_history_storage_refuses_symlinks_and_unsafe_permissions(self):
        store = self.store()
        self.play(store)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        path = self.directory / 'history.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        original = path.read_bytes()
        target = Path(self.tmp.name) / 'media.txt'
        target.write_bytes(b'untouched media')
        path.unlink()
        path.symlink_to(target)
        for operation in [store.records, lambda: self.play(store)]:
            with self.assertRaises(history.HistoryError):
                operation()
        self.assertEqual(target.read_bytes(), b'untouched media')
        path.unlink()
        path.write_bytes(original)
        path.chmod(0o644)
        with self.assertRaises(history.HistoryError):
            store.records()
        path.chmod(0o600)
        alias = Path(self.tmp.name) / 'alias'
        alias.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(history.HistoryError):
            history.HistoryStore(alias).records()
        with self.assertRaises(history.HistoryError):
            self.play(history.HistoryStore(alias / 'child'))
        self.directory.chmod(0o755)
        with self.assertRaises(history.HistoryError):
            store.records()

    def test_failed_atomic_replace_keeps_previous_history(self):
        from unittest.mock import patch
        store = self.store()
        self.play(store)
        path = self.directory / 'history.json'
        before = path.read_bytes()
        with patch.object(history.os, 'replace', side_effect=OSError('disk failed')):
            with self.assertRaises(history.HistoryError):
                self.play(store, position=50, when=1001)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(any(p.name.endswith('.tmp') for p in self.directory.iterdir()))
        self.play(store, position=50, when=1001)
        self.assertEqual(store.records()[0]['resume_seconds'], 50)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_bounded_recent_records_and_metadata(self):
        import inspect
        self.assertIn('max_records', inspect.signature(history.HistoryStore).parameters)
        store = self.store(max_records=2)
        for i in range(3):
            self.play(store, dict(MOVIE, id='tt123456' + str(i),
                                 title='x' * 400, genre=['Drama'] * 30), when=1000+i)
        self.assertEqual([r['id'] for r in store.records()], ['tt1234562', 'tt1234561'])
        self.assertEqual(len(store.records()[0]['title']), 300)
        self.assertEqual(store.records()[0]['genres'], ['Drama'])
        self.assertLess((self.directory / 'history.json').stat().st_size, 1048576)
        for count in [0, -1, 501, True]:
            with self.assertRaises(ValueError):
                self.store(max_records=count)
        for bad in [dict(MOVIE, title={'token': 'secret'}),
                    dict(MOVIE, title='bad\ud800title'),
                    dict(MOVIE, title='https://private/token'),
                    dict(MOVIE, genre=['https://private/token']),
                    dict(MOVIE, year='token=secret')]:
            self.assertFalse(self.play(store, bad, when=2000))

    def test_corrupt_or_oversized_history_fails_closed_without_overwrite(self):
        store = self.store()
        self.play(store)
        path = self.directory / 'history.json'
        valid = json.loads(path.read_text())
        bad_row = dict(valid['records']['tt1234567'], token='secret')
        cases = [b'{', b'[]', b'null', b'x' * (1048576 + 1),
                 json.dumps(dict(valid, version=2)).encode(),
                 json.dumps({'version': 1, 'records': {'tt1234567': bad_row}}).encode()]
        for raw in cases:
            with self.subTest(size=len(raw)):
                path.write_bytes(raw)
                with self.assertRaises(history.HistoryError):
                    store.records()
                with self.assertRaises(history.HistoryError):
                    self.play(store)
                self.assertEqual(path.read_bytes(), raw)

    def test_clear_only_resets_history_and_recovers_corrupt_json(self):
        store = self.store()
        self.assertTrue(callable(getattr(store, 'clear', None)))
        store.clear()
        self.assertFalse(self.directory.exists())
        self.play(store)
        media = self.directory / 'keep.mkv'
        media.write_bytes(b'not history')
        (self.directory / 'history.json').write_bytes(b'{broken')
        store.clear()
        self.assertEqual(store.records(), [])
        self.assertEqual(media.read_bytes(), b'not history')
        (self.directory / 'history.json').unlink()
        (self.directory / 'history.json').symlink_to(media)
        with self.assertRaises(history.HistoryError):
            store.clear()
        self.assertEqual(media.read_bytes(), b'not history')

    def test_concurrent_playback_updates_do_not_lose_records(self):
        from concurrent.futures import ThreadPoolExecutor
        self.play(self.store())
        def update(i):
            self.play(self.store(), dict(MOVIE, id='tt2000%03d' % i), when=2000+i)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(update, range(24)))
        self.assertEqual(len(self.store().records()), 25)

    def test_maximum_unicode_history_remains_readable_within_byte_limit(self):
        store = self.store(max_records=500)
        self.play(store)
        row = store.records()[0]
        row.update(title='🎬' * 300, genres=sorted(history.GENRES))
        rows = {}
        for i in range(499):
            identifier = 'tt3000%03d' % i
            rows[identifier] = dict(row, id=identifier)
        path = self.directory / 'history.json'
        path.write_text(json.dumps({'version': 1, 'records': rows}, ensure_ascii=False))
        self.play(store, dict(MOVIE, title='🎬' * 300), when=2000)
        self.assertLessEqual(path.stat().st_size, 1048576)
        self.assertEqual(len(store.records()), 500)

    def test_actual_playback_roundtrip_persists_only_allowed_metadata(self):
        store = self.store()
        self.assertTrue(store.record_playback(
            MOVIE, is_playing=True, position_seconds=120,
            duration_seconds=1000, lastplayed=1700000000))
        records = self.store().records()
        self.assertEqual(records, [{'id': 'tt1234567', 'title': 'Example',
            'year': '2024', 'genres': ['Drama', 'Comedy'], 'resume_seconds': 120,
            'duration_seconds': 1000, 'lastplayed': 1700000000,
            'completed': False}])
        raw = (self.directory / 'history.json').read_text()
        self.assertNotIn('secret', raw)
        self.assertNotIn('https:', raw)
        self.assertEqual(json.loads(raw)['version'], 1)
        self.assertEqual(set(json.loads(raw)['records']), {'tt1234567'})


if __name__ == '__main__':
    unittest.main()
