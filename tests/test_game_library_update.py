import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import update_game_library as u
class BrowserUpdateTests(unittest.TestCase):
 def test_update_preserves_settings_and_cores(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);home=root/'profile';target=home/'addons'/u.LIBRARY_ID
   target.mkdir(parents=True);(target/'addon.xml').write_text('<addon id="plugin.games.aperture"/>');(target/'old').touch()
   core=home/'addons/game.libretro.aperture.pcsxrearmed';core.mkdir();(core/'save').write_text('untouched')
   settings=home/'userdata/settings.xml';settings.parent.mkdir();settings.write_text('keep')
   source=root/'repo/games-kodi';source.mkdir(parents=True);(source/'addon.xml').write_text('<addon id="plugin.games.aperture"/>');(source/'new.py').write_text('x=1')
   with patch.object(u,'ROOT',root/'repo'),patch.object(u,'require_stopped'),patch.object(u.os,'geteuid',return_value=1000):
    backup=u.update(home)
   self.assertTrue((target/'new.py').is_file());self.assertFalse((target/'old').exists())
   self.assertTrue((backup/u.LIBRARY_ID/'old').exists())
   self.assertEqual(settings.read_text(),'keep');self.assertEqual((core/'save').read_text(),'untouched')
 def test_missing_install_is_not_silently_created(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(u,'require_stopped'),patch.object(u.os,'geteuid',return_value=1000):
   with self.assertRaises(u.SetupError):u.update(Path(tmp))
if __name__=='__main__':unittest.main()
