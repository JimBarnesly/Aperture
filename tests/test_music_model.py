"""Offline shelf rules. All metadata and paths below are synthetic fixtures."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'addons/script.apeture.music/resources/lib'))
from apeture_music.model import (Shelf, albums_from_rows, artists, initial_index,
                                local_artwork, number, songs_from_rows)


def album(identifier, artist='The Apples', title='Example', year=2000, **extra):
    return dict(albumid=identifier, artist=artist, title=title, year=year, **extra)


def song(identifier, path='/synthetic/track.flac', **extra):
    return dict(songid=identifier, file=path, **extra)


class AlbumModelTests(unittest.TestCase):
    def test_artist_then_year_then_title_and_id_without_reordering_input(self):
        rows = [album(9, 'The Zebras'), album(4, title='Zulu'),
                album(2, title='Alpha'), album(3, title='alpha'),
                album(7, title='Earlier', year=1999), album(1, 'Bananas'),
                album(8, 'The Apples', year=0)]
        original = list(rows)
        self.assertEqual([a.id for a in albums_from_rows(rows)], [8, 7, 2, 3, 4, 1, 9])
        self.assertEqual(rows, original)

    def test_only_leading_article_ignored_case_insensitively(self):
        rows = [album(1, 'Other The Band'), album(2, 'THE\tBand'),
                album(3, 'Theatre'), album(4, 'Banana')]
        self.assertEqual([a.id for a in albums_from_rows(rows)], [4, 2, 1, 3])

    def test_unicode_is_retained_and_casefold_order_is_deterministic(self):
        rows = [album(4, 'Élan', title='À demain'), album(3, 'Zebra'),
                album(2, 'STRASSE', title='Same'), album(1, 'Straße', title='same')]
        result = albums_from_rows(rows)
        self.assertEqual([a.id for a in result], [1, 2, 3, 4])
        self.assertEqual(result[-1].artist, 'Élan')
        self.assertEqual(result[-1].title, 'À demain')

    def test_missing_fields_malformed_rows_duplicates_and_fallbacks(self):
        rows = [None, [], 'bad', {}, {'albumid': True}, {'albumid': -1},
                {'albumid': '8'}, {'albumid': 3, 'artist': None, 'year': True},
                {'albumid': 3, 'title': 'duplicate'},
                {'albumid': 4, 'title': ' ', 'label': ' Label ', 'artist': 42},
                {'albumid': 5, 'artist': [' ', None, ' A ', ' B '], 'year': -4}]
        result = {a.id: a for a in albums_from_rows(rows)}
        self.assertEqual(set(result), {3, 4, 5})
        self.assertEqual(result[3].title, 'Untitled album')
        self.assertEqual(result[3].artist, 'Unknown artist')
        self.assertEqual(result[3].year, 0)
        self.assertEqual(result[4].title, 'Label')
        self.assertEqual(result[5].artist, 'A / B')
        self.assertEqual(result[5].year, 0)
        self.assertEqual(artists({'bad': 'artist'}), ())
        self.assertEqual(number(True, -1), -1)

    def test_current_album_wins_without_using_randomness(self):
        class NeverRandom:
            def randrange(self, stop):
                self.fail = True
                raise AssertionError('Current album must not choose randomly')
        albums = albums_from_rows([album(1), album(2), album(3)])
        self.assertEqual(initial_index(albums, 2, NeverRandom()), 1)
        self.assertEqual([a.id for a in albums], [1, 2, 3])

    def test_seeded_random_initial_focus_does_not_shuffle_shelf(self):
        albums = albums_from_rows([album(i) for i in range(30)])
        expected = random.Random(481).randrange(len(albums))
        for current in (None, 999, True, '2'):
            shelf = Shelf(albums, current, random.Random(481))
            self.assertEqual(shelf.index, expected)
            self.assertEqual(shelf.albums, tuple(albums))
            self.assertEqual(shelf.current, albums[expected])

    def test_empty_shelf_and_clamped_neighbors(self):
        shelf = Shelf([], None, random.Random(1))
        self.assertIsNone(shelf.index)
        self.assertIsNone(shelf.current)
        self.assertIsNone(shelf.move(1))
        self.assertIsNone(shelf.neighbor(-1))
        albums = albums_from_rows([album(1), album(2), album(3)])
        shelf = Shelf(albums, 2, random.Random(1))
        self.assertEqual(shelf.neighbor(-1).id, 1)
        self.assertEqual(shelf.neighbor(1).id, 3)
        self.assertIsNone(shelf.neighbor(2))
        self.assertEqual(shelf.move(-100).id, 1)
        self.assertIsNone(shelf.neighbor(-1))
        self.assertEqual(shelf.move(100).id, 3)
        self.assertIsNone(shelf.neighbor(1))
        self.assertEqual(shelf.albums, tuple(albums))


class SongModelTests(unittest.TestCase):
    def test_multidisc_track_order_not_filename_order(self):
        rows = [song(4, '/a.flac', disc=2, track=2),
                song(2, '/z.flac', disc=1, track=2),
                song(3, '/b.flac', disc=2, track=1),
                song(1, '/y.flac', disc=1, track=1),
                song(5, '/00.flac', disc=1, track=0)]
        self.assertEqual([s.id for s in songs_from_rows(rows)], [1, 2, 5, 3, 4])

    def test_ties_and_missing_fields_have_stable_fallbacks(self):
        rows = [song(3, title='Zulu'), song(2, title='alpha'),
                song(1, title='Alpha'), song(4, title=' ', label=' Label ',
                disc=-1, track='2', duration=True, artist=None, albumartist=' Owner ')]
        result = songs_from_rows(rows)
        self.assertEqual([s.id for s in result], [1, 2, 4, 3])
        by_id = {s.id: s for s in result}
        self.assertEqual(by_id[4].disc, 1)
        self.assertEqual(by_id[4].track, 0)
        self.assertEqual(by_id[4].duration, 0)
        self.assertEqual(by_id[4].album_artists, ('Owner',))
        self.assertEqual(by_id[4].artists, ())
        self.assertEqual(by_id[4].title, 'Label')

    def test_paths_and_urls_are_preserved_exactly(self):
        paths = ['/synthetic/Un été #1 & [x], "y".flac',
                 'smb://fixture-user:fixture-secret@fixture-host/share/%25%20?.flac',
                 'https://fixture.invalid/a%20b.flac?token=fake&x=%23',
                 'special://musicplaylists/album.xsp',
                 'C:\\Fixture Music\\é & track.flac',
                 '\\\\fixture-server\\share\\track.flac',
                 ' /synthetic/significant whitespace.flac ']
        result = songs_from_rows([song(i, path) for i, path in enumerate(paths)])
        self.assertEqual([s.file for s in result], paths)

    def test_invalid_and_duplicate_rows_are_ignored(self):
        rows = [None, [], {'songid': 1}, song(True), song(-1), song('1'),
                song(2, ''), song(3, '   '), song(4, None), song(5),
                song(5, '/duplicate.flac')]
        result = songs_from_rows(rows)
        self.assertEqual([s.id for s in result], [5])
        self.assertEqual(result[0].title, 'Untitled track')


class ArtworkPrivacyTests(unittest.TestCase):
    def test_existing_local_artwork_preserves_kodi_encoding_and_options(self):
        fixtures = ['/synthetic/covers/é #1.png', 'C:\\Fixture\\cover.png',
                    'file:///synthetic/cover%20one.png', 'file://localhost/synthetic/cover.png',
                    'special://profile/Thumbnails/a/b.jpg',
                    'resource://resource.images.fixture/cover.jpg',
                    'image://%2Fsynthetic%2Fcover%20one.jpg/',
                    'image://special%3A%2F%2Fprofile%2FThumbnails%2Fa.jpg/transform?size=thumb',
                    'image://music@%2Fsynthetic%2Fa.flac/']
        for path in fixtures:
            with self.subTest(path=path):
                self.assertEqual(local_artwork(path), path)

    def test_native_embedded_music_artwork_type_prefix_is_not_a_path(self):
        local = ['image://music@%2Ffixture%2Ftrack.flac/',
                 'image://music@%2Ffixture%2Fname%40artist%20%23.flac/?size=thumb',
                 'image://music@C%3A%5CFixture%5Ctrack.flac/',
                 'image://music@special%3A%2F%2Fprofile%2FThumbnails%2Fcached.flac/']
        for path in local:
            with self.subTest(path=path): self.assertEqual(local_artwork(path), path)
        remote = ['image://music@https%3A%2F%2Ffixture.invalid%2Ftrack.flac/',
                  'image://music@smb%3A%2F%2Ffixture-host%2Fshare%2Ftrack.flac/',
                  'image://music@%2F%2Ffixture-host%2Fshare%2Ftrack.flac/',
                  'image://music@file%3A%2F%2F%2F%2Ffixture-host%2Ftrack.flac/',
                  'image://music@%5C%5Cfixture-host%5Cshare%5Ctrack.flac/',
                  'image://music@https%3A%2F%2Fuser%40fixture.invalid%2Ftrack.flac/']
        for path in remote:
            with self.subTest(path=path): self.assertEqual(local_artwork(path), '')

    def test_remote_and_unc_artwork_is_never_loaded(self):
        fixtures = ['http://fixture.invalid/a.jpg', 'https://fixture.invalid/a.jpg',
                    'smb://fixture-user:fixture-secret@fixture-host/a.jpg',
                    'ftp://fixture.invalid/a.jpg', '//fixture-host/share/cover.jpg',
                    '\\\\fixture-host\\share\\cover.jpg',
                    'file://fixture-host/share/cover.jpg', 'file:////fixture-host/share/cover.jpg',
                    'file:///%2Ffixture-host/share/cover.jpg',
                    'image://https%3A%2F%2Ffixture.invalid%2Fa.jpg/',
                    'image://image%3A%2F%2Fhttp%253A%252F%252Ffixture.invalid%252Fa.jpg%2F/',
                    'image://%5C%5Cfixture-host%5Cshare%5Ccover.jpg/',
                    'image://file%3A%2F%2F%2F%2Ffixture-host%2Fshare%2Fcover.jpg/']
        for path in fixtures:
            with self.subTest(path=path):
                self.assertEqual(local_artwork(path), '')

    def test_invalid_artwork_never_raises_or_becomes_network_path(self):
        for value in (None, False, 3, {}, [], '', '   ', 'cover.jpg',
                      'http://[invalid', 'file://[invalid', 'image://', 'image://image://'):
            with self.subTest(value=value):
                self.assertEqual(local_artwork(value), '')


if __name__ == '__main__':
    unittest.main()
