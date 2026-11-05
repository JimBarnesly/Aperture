import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('movie_posters', ROOT/'movies-kodi/resources/lib/posters.py')
posters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(posters)


class PosterChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root/'profile'
        self.picture = self.root/'manual poster.png'
        self.picture.write_bytes(b'original picture bytes')
        self.movie = '/media/Movies/An Original Fixture (2026).mkv'

    def test_write_is_only_hashed_profile_preference(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        choice = posters.choice_path(str(self.profile), self.movie)
        self.assertEqual(list(self.profile.rglob('*.json')), [choice])
        self.assertNotIn('Original', choice.name)
        self.assertNotIn(self.movie, choice.read_text())
        self.assertEqual(posters.read_choice(str(self.profile), self.movie), str(self.picture))
        self.assertEqual(self.picture.read_bytes(), b'original picture bytes')

    def test_remakes_keep_separate_choices(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        remake = self.movie.replace('2026', '2025')
        self.assertEqual(posters.read_choice(str(self.profile), remake), '')
        self.assertNotEqual(posters.choice_path(str(self.profile), remake),
                            posters.choice_path(str(self.profile), self.movie))

    def test_reset_is_idempotent_and_does_not_delete_picture(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        for _ in range(2):
            posters.reset_choice(str(self.profile), self.movie)
        self.assertEqual(posters.read_choice(str(self.profile), self.movie), '')
        self.assertTrue(self.picture.is_file())

    def test_missing_picture_falls_back_without_writing(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        before = posters.choice_path(str(self.profile), self.movie).read_bytes()
        self.picture.unlink()
        self.assertEqual(posters.read_choice(str(self.profile), self.movie), '')
        self.assertEqual(posters.choice_path(str(self.profile), self.movie).read_bytes(), before)

    def test_invalid_choices_do_not_replace_existing_preference(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        for value in ('', 'relative.jpg', 'https://example.invalid/poster.jpg',
                      'smb://server/poster.jpg', '//server/share/poster.jpg',
                      '/missing.jpg', str(self.root/'movie.mkv'), '/tmp/bad\x00.jpg'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    posters.save_choice(str(self.profile), self.movie, value)
                self.assertEqual(posters.read_choice(str(self.profile), self.movie), str(self.picture))

    def test_cancel_or_browse_only_never_creates_profile(self):
        self.assertEqual(posters.read_choice(str(self.profile), self.movie), '')
        self.assertFalse(self.profile.exists())

    def test_bad_json_and_oversized_state_fall_back(self):
        target = posters.choice_path(str(self.profile), self.movie)
        target.parent.mkdir(parents=True)
        for value in ('broken', '[]', 'null', '{"path":2}', ' '*17000,
                      json.dumps({'path':'https://example.invalid/image.jpg'})):
            target.write_text(value)
            self.assertEqual(posters.read_choice(str(self.profile), self.movie), '')

    def test_atomic_failure_preserves_choice_and_cleans_temporary_file(self):
        posters.save_choice(str(self.profile), self.movie, str(self.picture))
        before = posters.choice_path(str(self.profile), self.movie).read_bytes()
        other = self.root/'new.jpg'; other.write_bytes(b'new picture')
        with patch.object(posters.os, 'replace', side_effect=OSError('failed')):
            with self.assertRaises(OSError):
                posters.save_choice(str(self.profile), self.movie, str(other))
        self.assertEqual(posters.choice_path(str(self.profile), self.movie).read_bytes(), before)
        self.assertEqual(len(list((self.profile/'posters').iterdir())), 1)

    def test_invalid_profile_never_writes_relative_files(self):
        with self.assertRaises(ValueError):
            posters.save_choice('', self.movie, str(self.picture))
        self.assertEqual(posters.read_choice('', self.movie), '')


if __name__ == '__main__':
    unittest.main()
