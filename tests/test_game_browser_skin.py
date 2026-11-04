from pathlib import Path
import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class BrowserSkinTests(unittest.TestCase):
 def test_views_keep_native_fallback_and_unique_ids(self):
  tree=ET.parse(ROOT/'skin/xml/MyGames.xml')
  self.assertEqual(tree.findtext('defaultcontrol'),'50')
  self.assertTrue({'59','60','50','55'}.issubset(tree.findtext('views').split(',')))
  ids=[e.get('id') for e in tree.iter('control') if e.get('id')]
  self.assertEqual(len(ids),len(set(ids)))
  for vid in ('59','60'):
   c=tree.find('.//control[@id="'+vid+'"]')
   self.assertEqual(c.findtext('visible'),'String.IsEqual(Container.PluginName,plugin.games.aperture)')
   self.assertIsNone(c.find('content'))
   self.assertEqual(list(c.iter('onclick')),[])
 def test_static_game_textures_are_packaged(self):
  for node in ET.parse(ROOT/'skin/xml/MyGames.xml').iter('texture'):
   if node.text and node.text.startswith('aperture/games/'):
    self.assertTrue((ROOT/'skin/media'/node.text).is_file())
 def test_installer_checks_browser_integrity(self):
  expected=re.search(r'GAMES_SHA=([a-f0-9]{64})',(ROOT/'install.sh').read_text()).group(1)
  self.assertEqual(expected,hashlib.sha256((ROOT/'skin/xml/MyGames.xml').read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
