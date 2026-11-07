"""Native turntable contracts. Actual rendered motion is checked in Kodi CI."""
import hashlib
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class TurntableTests(unittest.TestCase):
    def test_native_overlays_do_not_duplicate_header_or_footer(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        for identifier in ('7110', '7111'):
            self.assertEqual(tree.findtext('.//control[@id="'+identifier+'"]/visible'),
                             '!Window.IsVisible(seekbar)')
        self.assertEqual(tree.findtext('.//control[@type="progress"]/visible'),
                         '!Window.IsVisible(seekbar)')
        tilt = tree.find('.//animation[@effect="rotatex"]')
        self.assertEqual(tilt.get('center'), '450,0')  # Kodi's rotatex pivot is Y,Z.
        self.assertEqual(tree.find('.//animation[@effect="zoom"]').get('center'), 'auto')

    def test_native_player_state_and_controls(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml').getroot()
        self.assertEqual(tree.find('.//control[@id="7100"]/visible').text, 'Player.HasAudio')
        texture = tree.find('.//control[@id="7101"]/texture')
        self.assertEqual(texture.text, '$INFO[MusicPlayer.Cover]')
        self.assertEqual(texture.get('fallback'), 'DefaultAlbumCover.png')
        animation = tree.find('.//control[@id="7101"]/animation')
        self.assertEqual(animation.get('loop'), 'true')
        self.assertIn('!Player.Paused', animation.get('condition'))
        self.assertEqual(tree.find('.//control[@id="7103"]/visible').text, 'Player.Paused')
        self.assertIn('$INFO[MusicPlayer.Title]', [n.text for n in tree.iter('label')])
        self.assertFalse(list(tree.iter('onload')))  # No scripts, scan or external player.
        self.assertFalse(list(tree.iter('onunload')))
        self.assertFalse(list(tree.iter('onclick')))  # Built-in music OSD owns controls.

    def test_album_track_listing_is_secondary_bottom_left_and_read_only(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        listing = tree.find('.//control[@id="7120"]')
        self.assertEqual(tree.findtext('.//control[@id="7102"]/label'), '$INFO[MusicPlayer.Album]')
        self.assertEqual(listing.findtext('content'), 'playlistmusic://')
        self.assertEqual(listing.findtext('enable'), 'false')
        self.assertIn('MusicPlayer.Position(0).AlbumArtist', listing.findtext('visible'))
        self.assertLessEqual(int(listing.findtext('left')) + int(listing.findtext('width')), 520)
        self.assertGreaterEqual(int(listing.findtext('top')), 500)
        self.assertLessEqual(int(listing.findtext('top')) + int(listing.findtext('height')), 930)
        self.assertGreaterEqual(int(tree.findtext('.//control[@id="7102"]/left')), 580)
        self.assertFalse(list(listing.iter('onclick')))
        self.assertTrue(all('ListItem.Title' in label.text for label in listing.iter('label')))

    def test_art_is_packaged_and_deterministic(self):
        spec = importlib.util.spec_from_file_location('music_art', ROOT / 'tools/build_music_art.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            module.generate(temp)
            for file in Path(temp).iterdir():
                self.assertEqual(file.read_bytes(), (ROOT / 'skin/media/aperture/music' / file.name).read_bytes())
            with Image.open(Path(temp) / 'disc-mask.png') as mask:
                self.assertEqual(mask.getpixel((0, 0))[3], 0)
                self.assertEqual(mask.getpixel((512, 512)), (255, 255, 255, 255))
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        for node in tree.iter('texture'):
            for value in (node.text, node.get('diffuse')):
                if value and value.startswith('aperture/'):
                    self.assertTrue((ROOT / 'skin/media' / value).is_file(), value)

    def test_installer_and_builder_include_exact_screen(self):
        installer = (ROOT / 'install.sh').read_text()
        sha = re.search(r'VISUALISATION_SHA=([a-f0-9]{64})', installer).group(1)
        self.assertEqual(sha, hashlib.sha256((ROOT / 'skin/xml/MusicVisualisation.xml').read_bytes()).hexdigest())
        self.assertIn('cp "$SOURCE_DIR/skin/xml/MusicVisualisation.xml" "$TMP/xml/MusicVisualisation.xml"', installer)
        self.assertIn("shutil.copy2(ROOT / 'skin/xml/MusicVisualisation.xml', staged / 'xml/MusicVisualisation.xml')", (ROOT / 'tools/build_skin.py').read_text())

    def test_browser_can_reopen_without_restarting_playback(self):
        tree = ET.parse(ROOT / 'skin/xml/MyMusicNav.xml')
        button = tree.find('.//control[@id="65"]')
        self.assertEqual(button.findtext('visible'), 'Player.HasAudio')
        self.assertEqual(button.findtext('onclick'), 'ActivateWindow(visualisation)')
        for identifier, direction in (('63', 'onright'), ('64', 'ondown')):
            view = tree.find('.//control[@id="'+identifier+'"]')
            self.assertIn(('Player.HasAudio', '65'), [(n.get('condition'), n.text) for n in view.findall(direction)])


if __name__ == '__main__':
    unittest.main()
