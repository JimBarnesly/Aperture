from pathlib import Path
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location('source_match', Path(__file__).resolve().parents[1] / 'movies-kodi/resources/lib/source_match.py')
matcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matcher)

class SourceMatchTests(unittest.TestCase):
    def test_explicit_unique_identity_only(self):
        for name in ('Example.[tt1234567].mkv', 'Example.tt1234567.1080p.mp4'):
            self.assertTrue(matcher.matches({'filename': name}, 'tt1234567'))
        for name in ('Example.2020.mp4', 'tt12345678.mp4', 'xtt1234567.mp4',
                     'tt1234567x.mp4', 'tt1234567.tt9999999.mp4',
                     'tt1234567/folder/Example.mp4', 'tt1234567.txt',
                     'tt1234567\n.mp4', 'tt1234567' + 'x'*1024 + '.mp4'):
            self.assertFalse(matcher.matches({'filename': name}, 'tt1234567'), name)

    def test_untrusted_shapes_and_invalid_identity(self):
        for entry in (None, [], {}, {'filename': 42}):
            self.assertFalse(matcher.matches(entry, 'tt1234567'))
        for identifier in (None, '../tt1234567', 'tt12', 'tt1234567890123'):
            self.assertFalse(matcher.matches({'filename':'tt1234567.mp4'}, identifier))
