from pathlib import Path
import hashlib
import re
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class GamingHomeTest(unittest.TestCase):
 def test_games_routes_enabled_library_or_native_fallback(self):
  home=ET.parse(ROOT/'skin/xml/Home.xml')
  button=home.find(".//control[@type='button'][@id='102']")
  actions={node.get('condition'):node.text for node in button.findall('onclick')}
  self.assertEqual(actions,{'System.AddonIsEnabled(plugin.games.aperture)':'ActivateWindow(Games,plugin://plugin.games.aperture/,return)','!System.AddonIsEnabled(plugin.games.aperture)':'ActivateWindow(Games)'})
  self.assertEqual(button.findtext('onup'),'103');self.assertEqual(button.findtext('ondown'),'104')
 def test_installer_home_checksum_matches(self):
  expected=re.search(r'HOME_SHA=([a-f0-9]{64})',(ROOT/'install.sh').read_text()).group(1)
  self.assertEqual(expected,hashlib.sha256((ROOT/'skin/xml/Home.xml').read_bytes()).hexdigest())
if __name__=='__main__': unittest.main()
