import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('movie_library', ROOT/'movies-kodi/resources/lib/library.py')
lib = importlib.util.module_from_spec(spec); spec.loader.exec_module(lib)

class MovieSourceTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'label':'Films','file':'/media/test disk/Movies/'},{'label':'Shows','file':'/media/test disk/TV/'}]
    def test_single_source(self):
        self.assertEqual(lib.select_source(self.sources[:1]), self.sources[0])
    def test_explicit_default_by_name(self):
        self.assertEqual(lib.select_source(self.sources,'Shows'), self.sources[1])
    def test_explicit_default_by_path(self):
        self.assertEqual(lib.select_source(self.sources,self.sources[0]['file']),self.sources[0])
    def test_multiple_never_guessed(self):
        self.assertIsNone(lib.select_source(self.sources))
        self.assertIsNone(lib.select_source(self.sources,'missing'))
    def test_empty(self): self.assertIsNone(lib.select_source([]))
    def test_default_xml(self):
        self.assertEqual(lib.default_from_xml('<sources><video><default>Films</default></video></sources>'),'Films')
        self.assertEqual(lib.default_from_xml('broken'),'')
    def test_path_boundary(self):
        root='/media/test disk/Movies/'
        self.assertTrue(lib.within_source(root,root))
        self.assertTrue(lib.within_source(root+'Series/',root))
        for path in ['/media/test disk/Movies2/a','/etc/','/media/test disk/Movies/../TV','/media/test disk/Movies/%2e%2e/TV','smb://evil/Movies/a']:
            self.assertFalse(lib.within_source(path,root),path)
    def test_remote_boundary(self):
        self.assertTrue(lib.within_source('smb://server/share/Movies/A','smb://server/share/Movies/'))
        self.assertFalse(lib.within_source('smb://other/share/Movies/A','smb://server/share/Movies/'))
    def test_title_no_fake_metadata(self):
        self.assertEqual(lib.display_title({'label':'A.Film_2020.mkv','filetype':'file'}),'A Film 2020')
        self.assertEqual(lib.display_title({'label':'Collections','filetype':'directory'}),'Collections')
    def test_sidecars_bounded(self):
        self.assertEqual(len(lib.sidecar_candidates('/Movies/A.mkv')['poster']),4)
        self.assertEqual(lib.sidecar_candidates('/Movies/A.mkv')['poster'][0],'/Movies/A-poster.jpg')

    def test_explicit_sidecar_overrides_library_and_folder_art(self):
        item = {'file':'/Movies/A.mkv', 'art':{'poster':'library-poster','fanart':'library-fanart'}}
        art = lib.artwork(item, lambda path: path in {'/Movies/A-poster.jpg','/Movies/poster.jpg'}, True)
        self.assertEqual(art['poster'], '/Movies/A-poster.jpg')
        self.assertEqual(art['fanart'], 'library-fanart')

    def test_manual_choice_wins_without_overwriting_other_art(self):
        item = {'file':'/Movies/A.mkv', 'art':{'poster':'library-poster','fanart':'library-fanart'}}
        art = lib.artwork(item, lambda path: True, True, poster='/chosen.png')
        self.assertEqual(art['poster'], '/chosen.png')
        self.assertEqual(item['art']['poster'], 'library-poster')

    def test_folder_art_only_for_single_movie_directory(self):
        exists = lambda path: path in {'/Movies/poster.jpg','/Movies/fanart.jpg'}
        item = {'file':'/Movies/A.mkv'}
        self.assertEqual(lib.artwork(item, exists), {})
        self.assertEqual(lib.artwork(item, exists, True),
                         {'poster':'/Movies/poster.jpg','fanart':'/Movies/fanart.jpg'})

    def test_library_art_preferred_to_generic_folder_art(self):
        item = {'file':'/Movies/A.mkv', 'art':{'poster':'library-poster'}}
        art = lib.artwork(item, lambda path: path == '/Movies/poster.jpg', True)
        self.assertEqual(art['poster'], 'library-poster')

    def test_empty_art_keys_do_not_block_sidecars_and_thumb_is_not_a_poster(self):
        item = {'file':'/Movies/A.mkv', 'art':{'poster':''}, 'thumbnail':'video-frame'}
        art = lib.artwork(item, lambda path: False)
        self.assertNotIn('poster', art)
        self.assertEqual(art['thumb'], 'video-frame')

if __name__=='__main__': unittest.main()
