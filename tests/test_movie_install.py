from pathlib import Path
import sys, tempfile, unittest, shutil
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import install_movies
from setup_gaming import SetupError

class MovieInstallTests(unittest.TestCase):
    def test_atomic_install_preserves_source_settings_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)/'profile'; (home/'userdata').mkdir(parents=True)
            (home/'userdata/sources.xml').write_text('unchanged sources')
            (home/'userdata/guisettings.xml').write_text('unchanged settings')
            with patch('install_movies.os.geteuid',return_value=1000),patch('install_movies.require_stopped'):
                install_movies.install(home)
                backup=install_movies.install(home)
            self.assertTrue((home/'addons/plugin.video.aperture.movies/addon.xml').exists())
            self.assertTrue((backup/'plugin.video.aperture.movies/addon.xml').exists())
            self.assertEqual((home/'userdata/sources.xml').read_text(),'unchanged sources')
            self.assertEqual((home/'userdata/guisettings.xml').read_text(),'unchanged settings')
    def test_reject_running(self):
        with tempfile.TemporaryDirectory() as tmp,patch('install_movies.os.geteuid',return_value=1000),patch('install_movies.require_stopped',side_effect=SetupError('running')):
            with self.assertRaises(SetupError): install_movies.install(Path(tmp)/'profile')
            self.assertFalse((Path(tmp)/'profile').exists())
    def test_reject_symlinked_addon(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)/'profile'; (home/'addons').mkdir(parents=True)
            outside=Path(tmp)/'outside'; outside.mkdir()
            (home/'addons/plugin.video.aperture.movies').symlink_to(outside)
            with patch('install_movies.os.geteuid',return_value=1000),patch('install_movies.require_stopped'):
                with self.assertRaises(SetupError): install_movies.install(home)
            self.assertEqual(list(outside.iterdir()),[])

if __name__=='__main__':unittest.main()
