"""Format's native containers remain isolated from other Music sources."""
import hashlib
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class MusicSkinTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(ROOT / 'skin/xml/MyMusicNav.xml').getroot()

    def test_custom_views_are_native_and_prefer_same_type_on_back(self):
        self.assertEqual(self.root.findtext('views').split(',')[:2], ['63', '64'])
        ids = [node.get('id') for node in self.root.iter('control') if node.get('id')]
        self.assertEqual(len(ids), len(set(ids)))
        for identifier in ('63', '64'):
            view = self.root.find('.//control[@id="' + identifier + '"]')
            self.assertEqual(view.findtext('viewtype'), 'list')
            self.assertIn('String.IsEqual(Container.PluginName,plugin.audio.aperture.format)', view.findtext('visible'))
            self.assertIsNone(view.find('content'))
            self.assertEqual(list(view.iter('onclick')), [])
        shelf = self.root.find('.//control[@id="64"]')
        self.assertEqual(shelf.get('type'), 'fixedlist')
        self.assertEqual(shelf.findtext('focusposition'), '2')
        self.assertEqual(shelf.findtext('movement'), '0')
        self.assertEqual(shelf.find('viewtype').get('label'), 'Coverflow')
        turns = shelf.findall('./itemlayout/control/animation[@effect="rotatey"]')
        self.assertEqual({turn.get('end') for turn in turns}, {'45', '-45'})
        for turn in turns:
            self.assertEqual(turn.get('center'), '220,0')
            self.assertIn('Container(64).ListItem.Property(Aperture.FormatPosition)', turn.get('condition'))
        # Native container remains responsible for playback and navigation.
        self.assertIsNone(shelf.find('onclick'))
        self.assertEqual(shelf.findtext('orientation'), 'horizontal')
        self.assertIn('String.IsEqual(Container.Property(Aperture.FormatView),albums)', shelf.findtext('visible'))
        listing = self.root.find('.//control[@id="63"]')
        self.assertIn('!String.IsEqual(Container.Property(Aperture.FormatView),albums)', listing.findtext('visible'))

    def test_native_music_fallback_and_notice_remain(self):
        views = set(self.root.findtext('views').split(','))
        self.assertTrue({'50', '52', '53', '54', '55', '500'}.issubset(views))
        self.assertTrue(any(node.text == 'View_50_List' for node in self.root.iter('include')))
        labels = [node.text for node in self.root.iter('label')]
        self.assertIn('$INFO[Container.Property(Aperture.FormatNotice)]', labels)
        self.assertIn('$INFO[Container.Property(Aperture.FormatTitle)]', labels)
        self.assertNotIn('$INFO[Container.FolderName]', labels)
        self.assertNotIn('Local music', labels)
        self.assertNotIn('Format streaming', labels)

    def test_only_existing_static_assets_are_used(self):
        for node in self.root.iter('texture'):
            if node.text and node.text.startswith('aperture/'):
                self.assertTrue((ROOT / 'skin/media' / node.text).is_file(), node.text)

    def test_installer_checks_exact_music_view(self):
        installer = (ROOT / 'install.sh').read_text()
        digest = re.search(r'MUSIC_SHA=([a-f0-9]{64})', installer).group(1)
        self.assertEqual(digest, hashlib.sha256((ROOT / 'skin/xml/MyMusicNav.xml').read_bytes()).hexdigest())
        self.assertIn('cp "$SOURCE_DIR/skin/xml/MyMusicNav.xml" "$TMP/xml/MyMusicNav.xml"', installer)


if __name__ == '__main__':
    unittest.main()
