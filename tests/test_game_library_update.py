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
   cache=home/'userdata/addon_data'/u.LIBRARY_ID/'library-v1/snapshot.json';cache.parent.mkdir(parents=True);cache.write_bytes(b'cached library survives upgrades')
   rom_settings=cache.parent.parent/'settings.xml';rom_settings.write_bytes(b'<settings><setting id="rom_root">/existing/roms</setting></settings>')
   game_save=home/'userdata/addon_data/game.libretro.aperture.pcsxrearmed/save.sav';game_save.parent.mkdir(parents=True);game_save.write_bytes(b'existing save data')
   source=root/'repo/games-kodi';source.mkdir(parents=True);(source/'addon.xml').write_text('<addon id="plugin.games.aperture"/>');(source/'new.py').write_text('x=1')
   with patch.object(u,'ROOT',root/'repo'),patch.object(u,'require_stopped'),patch.object(u.os,'geteuid',return_value=1000):
    backup=u.update(home)
   self.assertTrue((target/'new.py').is_file());self.assertFalse((target/'old').exists())
   self.assertTrue((backup/u.LIBRARY_ID/'old').exists())
   self.assertEqual(settings.read_text(),'keep');self.assertEqual((core/'save').read_text(),'untouched')
   self.assertEqual(cache.read_bytes(),b'cached library survives upgrades')
   self.assertEqual(rom_settings.read_bytes(),b'<settings><setting id="rom_root">/existing/roms</setting></settings>')
   self.assertEqual(game_save.read_bytes(),b'existing save data')
 def test_missing_install_is_not_silently_created(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(u,'require_stopped'),patch.object(u.os,'geteuid',return_value=1000):
   with self.assertRaises(u.SetupError):u.update(Path(tmp))
if __name__=='__main__':unittest.main()
