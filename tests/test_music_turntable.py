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
    def test_own_progress_remains_visible_during_seek_pause_and_manual_controls(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        self.assertIsNone(tree.find('.//control[@id="7110"]'))
        self.assertEqual(tree.findtext('.//control[@id="7111"]/visible'),
                         '!Window.IsVisible(musicosd)')
        progress = tree.find('.//control[@id="7112"]')
        self.assertEqual(progress.get('type'), 'progress')
        self.assertEqual(progress.findtext('info'), 'Player.Progress')
        self.assertIsNone(progress.find('visible'))
        for label in tree.findall('.//control[@type="label"]'):
            if label.findtext('label') in ('$INFO[Player.Time]', '$INFO[Player.Duration]'):
                self.assertIsNone(label.find('visible'))
        self.assertNotIn('seekbar', (ROOT / 'skin/xml/MusicVisualisation.xml').read_text())
        tilt = tree.find('.//animation[@effect="rotatex"]')
        self.assertEqual(tilt.get('center'), '450,0')
        self.assertEqual(tree.find('.//animation[@effect="zoom"]').get('center'), 'auto')

    def test_inherited_music_info_overlays_are_always_disabled_not_video_or_errors(self):
        for filename in ('DialogSeekBar.xml', 'Custom_1109_TopBarOverlay.xml'):
            tree = ET.parse(ROOT / 'skin/xml' / filename)
            self.assertEqual(tree.getroot().findtext('visible'), '!Window.IsActive(visualisation)')
            self.assertIn('Window.IsActive(fullscreenvideo)', tree.getroot().findall('visible')[1].text)
        tree = ET.parse(ROOT / 'skin/xml/DialogSeekBar.xml')
        self.assertEqual(len(tree.getroot().findall('visible')), 4)
        for identifier in ('401', '403', '40000'):
            self.assertIsNotNone(tree.find('.//control[@id="'+identifier+'"]'))
        self.assertFalse(list(tree.iter('onload')))
        # No generic dialog-closing action can swallow unrelated messages.
        self.assertNotIn('Dialog.Close', (ROOT / 'skin/xml/DialogSeekBar.xml').read_text())

    def test_manual_music_controls_keep_native_actions_and_use_existing_progress_bar(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicOSD.xml')
        self.assertEqual(tree.findtext('.//control[@id="602"]/onclick'), 'PlayerControl(Play)')
        self.assertEqual(tree.findtext('.//control[@id="603"]/onclick'), 'PlayerControl(Stop)')
        self.assertEqual(tree.findtext('.//control[@id="607"]/onclick'), 'PlayerControl(Next)')
        self.assertEqual(tree.findtext('.//control[@id="87"]/onleft'), 'StepBack')
        self.assertEqual(tree.findtext('.//control[@id="87"]/onright'), 'StepForward')
        sliders = tree.findall('.//control[@type="slider"]')
        self.assertEqual(len(sliders), 4)
        for slider in sliders:
            self.assertEqual(slider.findtext('left'), '260')
            self.assertEqual(slider.findtext('width'), '1400')
            self.assertEqual(slider.findtext('top'), '-26')
            self.assertEqual(slider.findtext('height'), '26')
            self.assertIn(slider.findtext('action'), ('seek', 'pvr.seek'))
        help_label = next(c for c in tree.findall('.//control[@type="label"]')
                          if c.findtext('label') == '$VAR[OSDHelpTextVar]')
        self.assertEqual(help_label.findtext('top'), '5')
        self.assertEqual(help_label.findtext('height'), '30')
        for identifier in ('201', '202'):
            self.assertEqual(tree.findtext('.//control[@id="'+identifier+'"]/top'), '40')

    def test_turntable_omits_redundant_top_left_branding_and_now_playing_label(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        labels = [n.text for n in tree.iter('label')]
        self.assertFalse(any('APERTURE' in (label or '').upper() or 'NOW PLAYING' in (label or '').upper()
                             for label in labels if not (label or '').startswith('$INFO[')))
        self.assertIn('$INFO[System.Time]', labels)
        # The Home shortcut is separate and must remain available.
        self.assertIn('Now playing', (ROOT / 'skin/xml/Home.xml').read_text())

    def test_record_captions_are_track_then_album_then_artist(self):
        tree = ET.parse(ROOT / 'skin/xml/MusicVisualisation.xml')
        captions = [tree.find('.//control[@id="'+identifier+'"]') for identifier in ('7104', '7102', '7105')]
        self.assertEqual([c.findtext('label') for c in captions],
                         ['$INFO[MusicPlayer.Title]', '$INFO[MusicPlayer.Album]', '$INFO[MusicPlayer.AlbumArtist]'])
        self.assertEqual([int(c.findtext('top')) for c in captions], [795, 865, 908])
        self.assertEqual(captions[0].findtext('font'), 'font45')
        self.assertTrue(all(c.findtext('scroll') == 'true' for c in captions))

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
        long_list = tree.find('.//control[@id="7122"]')
        self.assertEqual(long_list.findtext('autoscroll'), 'true')
        self.assertIn('Aperture.FormatAlbumTracks', long_list.findtext('label'))
        self.assertTrue(any(x.text == 'ListItem.IsPlaying' for x in listing.iter('visible')))
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
        sha = re.search(r'SEEKBAR_SHA=([a-f0-9]{64})', installer).group(1)
        self.assertEqual(sha, hashlib.sha256((ROOT / 'skin/xml/DialogSeekBar.xml').read_bytes()).hexdigest())
        self.assertIn('cp "$SOURCE_DIR/skin/xml/DialogSeekBar.xml" "$TMP/xml/DialogSeekBar.xml"', installer)
        self.assertIn("shutil.copy2(ROOT / 'skin/xml/DialogSeekBar.xml', staged / 'xml/DialogSeekBar.xml')", (ROOT / 'tools/build_skin.py').read_text())
        for filename, pin in (('Custom_1109_TopBarOverlay.xml', 'TOPBAR'), ('MusicOSD.xml', 'MUSIC_OSD')):
            sha = re.search(pin+r'_SHA=([a-f0-9]{64})', installer).group(1)
            self.assertEqual(sha, hashlib.sha256((ROOT/'skin/xml'/filename).read_bytes()).hexdigest())
            self.assertIn('cp "$SOURCE_DIR/skin/xml/'+filename+'" "$TMP/xml/'+filename+'"', installer)
            self.assertIn("shutil.copy2(ROOT / 'skin/xml/"+filename+"', staged / 'xml/"+filename+"')", (ROOT/'tools/build_skin.py').read_text())

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
