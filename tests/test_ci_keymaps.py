"""Window-specific default keys must not swallow isolated CI entry shortcuts."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

class KeymapTests(unittest.TestCase):
    def test_interface_shortcut_overrides_home_default(self):
        source=(ROOT/'tools/ci_kodi_smoke.sh').read_text()
        keymap=ET.fromstring(re.search(r'<keymap>.*?</keymap>',source,re.S).group())
        self.assertEqual(keymap.findtext('global/keyboard/i'),'ActivateWindow(10032,lookandfeel.skin)')
        self.assertEqual(keymap.findtext('Home/keyboard/i'),'ActivateWindow(10032,lookandfeel.skin)')

    def test_zip_interface_shortcut_overrides_home_default(self):
        source=(ROOT/'tools/zip_smoke_fixture.py').read_text()
        keymap=ET.fromstring(re.search(r'<keymap>.*?</keymap>',source,re.S).group())
        self.assertEqual(keymap.findtext('Home/keyboard/i'),'ActivateWindow(10032,lookandfeel.skin)')

if __name__=='__main__':unittest.main()
