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
        self.assertEqual(shelf.find('itemlayout').get('width'), '440')
        self.assertEqual(list(shelf.find('itemlayout')), [])
        neighbours = [node for node in self.root.findall('.//control[@type="group"]')
                      if 'ListItemNoWrap' in node.findtext('visible', '')]
        self.assertEqual(len(neighbours), 14)
        for node in neighbours:
            turn = node.find('./control/animation[@effect="rotatey"]')
            expected = '-45' if 'ListItemNoWrap(-' in node.findtext('visible') else '45'
            self.assertEqual(turn.get('end'), expected)
            self.assertEqual(turn.get('center'), '220,0')
            self.assertIsNone(node.find('animation'))
            self.assertEqual(node.findtext('./control/left'), '0')
            self.assertEqual(node.findtext('./control/top'), '0')
            self.assertIn('Aperture.FormatPosition', node.findtext('visible'))
            self.assertIsNotNone(node.find('.//texture[@flipy="true"]'))
        # Near sleeves draw after far sleeves on each side.
        self.assertIn('ListItemNoWrap(-7)', neighbours[0].findtext('visible'))
        self.assertIn('ListItemNoWrap(1)', neighbours[-1].findtext('visible'))
        # Native container remains responsible for playback and navigation.
        self.assertIsNone(shelf.find('onclick'))
        self.assertEqual(shelf.findtext('orientation'), 'horizontal')
        self.assertIn('String.IsEqual(Container.Property(Aperture.FormatView),albums)', shelf.findtext('visible'))
        listing = self.root.find('.//control[@id="63"]')
        self.assertIn('!String.IsEqual(Container.Property(Aperture.FormatView),albums)', listing.findtext('visible'))

    def test_coverflow_never_crossfades_unrelated_album_identity(self):
        art = [node for node in self.root.findall('.//control[@type="image"]')
               if 'ListItemNoWrap' in node.findtext('texture', '')]
        self.assertEqual(len(art), 28)
        for node in art:
            self.assertEqual(node.findtext('fadetime'), '0')
            # Kodi coerces lazy+fallback into a hold-old crossfade even at zero.
            self.assertNotEqual(node.find('texture').get('background'), 'true')
        textures = list(self.root.iter('texture'))
        selected = next(t for t in textures if t.text == '$INFO[Container(64).ListItem.Art(thumb)]')
        first_wing = next(t for t in textures if 'ListItemNoWrap' in (t.text or ''))
        self.assertLess(textures.index(selected), textures.index(first_wing))
        self.assertEqual(selected.get('background'), 'true')
        self.assertIsNone(selected.get('fallback'))

    def test_store_button_is_visible_and_remote_reachable_from_shelf(self):
        button = self.root.find('.//control[@id="66"]')
        self.assertEqual(button.findtext('label'), 'Store')
        self.assertEqual(button.findtext('visible'), 'Control.IsVisible(64)')
        self.assertEqual(button.findtext('onclick'), 'Container.Update(plugin://plugin.audio.aperture.format/?action=store)')
        shelf = self.root.find('.//control[@id="64"]')
        self.assertIn(('!Player.HasAudio', '66'), [(n.get('condition'), n.text) for n in shelf.findall('ondown')])
        playing = self.root.find('.//control[@id="65"]')
        self.assertIn(('Control.IsVisible(64)', '66'), [(n.get('condition'), n.text) for n in playing.findall('onleft')])
        self.assertEqual(button.findtext('onup'), '64')

    def test_main_shelf_back_explicitly_returns_home_even_in_fresh_profile(self):
        for identifier in ('64', '65', '66'):
            action = self.root.find('.//control[@id="' + identifier + '"]/onback')
            self.assertEqual(action.text, 'ActivateWindow(Home)')
            self.assertEqual(action.get('condition'), 'String.IsEqual(Container.FolderPath,plugin://plugin.audio.aperture.format/?action=albums)')
        self.assertIsNone(self.root.find('.//control[@id="63"]/onback'))

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
