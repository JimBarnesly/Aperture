"""Music is integrated Format; other media retain their intended native routes."""
from collections import deque
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class LocalMediaNavigationTests(unittest.TestCase):
    def setUp(self):
        self.home = ET.parse(ROOT / 'skin/xml/Home.xml').getroot()
        self.buttons = {node.get('id'): node for node in self.home.iter('control')
                        if node.get('type') == 'button'}

    def actions(self, ident):
        return {node.get('condition'): node.text
                for node in self.buttons[str(ident)].findall('onclick')}

    def test_music_opens_format_directly_without_a_second_product_choice(self):
        enabled = 'System.AddonIsEnabled(plugin.audio.aperture.format)'
        actions = self.buttons['103'].findall('onclick')
        self.assertEqual([node.text for node in actions if node.get('condition') == enabled],
                         ['ActivateWindow(Music,plugin://plugin.audio.aperture.format/,return)'])
        self.assertEqual(self.buttons['103'].findtext('onright'), '103')
        self.assertEqual(sum(b.findtext('label') == 'Music' for b in self.buttons.values()), 1)
        self.assertIsNone(self.buttons['103'].find('enable'))
        self.assertEqual({node.get('condition') for node in actions}, {enabled, '!' + enabled})

    def test_missing_or_disabled_format_opens_explicit_addon_setup_guidance(self):
        unavailable = '!System.AddonIsEnabled(plugin.audio.aperture.format)'
        actions = self.buttons['103'].findall('onclick')
        self.assertEqual([node.text for node in actions if node.get('condition') == unavailable], [
            'ActivateWindow(AddonBrowser)',
            'Notification(Music needs Format,Install or enable Aperture Format in Add-ons.,8000)',
        ])
        self.assertEqual(len(actions), 3)

    def test_no_local_streaming_submenu_or_hidden_native_music_fallback(self):
        source = ET.tostring(self.home, encoding='unicode')
        for obsolete in ('Local music', 'Format streaming', 'Control.HasFocus(203)',
                         'Control.HasFocus(204)', 'SetFocus(203)', 'library://music/',
                         'ActivateWindow(Music)'):
            self.assertNotIn(obsolete, source)
        self.assertNotIn('203', self.buttons)
        self.assertNotIn('204', self.buttons)

    def test_music_keeps_main_menu_arrows_and_visible_focus(self):
        button = self.buttons['103']
        self.assertEqual({key: button.findtext(key) for key in ('onup', 'ondown', 'onleft', 'onright')},
                         {'onup': '101', 'ondown': '102', 'onleft': '106', 'onright': '103'})
        group = next(node for node in self.home.iter('control')
                     if node.findtext('visible') == 'Control.HasFocus(103)')
        self.assertEqual(group.findtext("control[@type='label']/label"), 'Music')
        self.assertEqual(group.findtext("control[@type='image']/texture"), 'aperture/focus-marker.png')

    def test_movies_prefer_cinematic_plugin_with_native_fallback(self):
        enabled = 'System.AddonIsEnabled(plugin.video.aperture.movies)'
        self.assertEqual(self.actions(100), {
            enabled: 'ActivateWindow(Videos,plugin://plugin.video.aperture.movies/,return)',
            f'!{enabled} + Library.HasContent(Movies)': 'ActivateWindow(Videos,videodb://movies/titles/,return)',
            f'!{enabled} + !Library.HasContent(Movies)': 'ActivateWindow(Videos,sources://video/,return)',
        })
        self.assertEqual(self.actions(101), {
            'Library.HasContent(TVShows)': 'ActivateWindow(Videos,videodb://tvshows/titles/,return)',
            '!Library.HasContent(TVShows)': 'ActivateWindow(Videos,sources://video/,return)',
        })

    def test_sources_always_opens_native_video_files(self):
        self.assertEqual(self.actions(104), {None: 'ActivateWindow(Videos,sources://video/,return)'})

    def test_all_buttons_have_an_arrow_path_and_escape_route(self):
        pending = deque([self.home.findtext('defaultcontrol')])
        seen = set()
        while pending:
            ident = pending.popleft()
            if ident in seen:
                continue
            seen.add(ident)
            button = self.buttons[ident]
            for event in ('onleft', 'onright', 'onup', 'ondown'):
                target = button.findtext(event)
                self.assertIn(target, self.buttons)
                pending.append(target)
        self.assertEqual(seen, set(self.buttons))
        self.assertEqual(len(self.buttons), 7)

    def test_home_does_not_run_media_mutations_or_assume_hdd_paths(self):
        for action in self.home.iter('onclick'):
            self.assertTrue(action.text.startswith(('ActivateWindow(', 'Notification(')), action.text)
            for forbidden in ('/media/', '/mnt/', '/dev/', 'RunScript', 'RunPlugin', 'UpdateLibrary', 'CleanLibrary'):
                self.assertNotIn(forbidden, action.text)

    def test_generated_home_matches_checked_in_xml(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tools').mkdir()
            (root / 'skin/xml').mkdir(parents=True)
            shutil.copy2(ROOT / 'tools/design_home.py', root / 'tools/design_home.py')
            subprocess.run([sys.executable, str(root / 'tools/design_home.py')], check=True)
            self.assertEqual((root / 'skin/xml/Home.xml').read_bytes(), (ROOT / 'skin/xml/Home.xml').read_bytes())

    def test_real_gui_runners_cover_direct_format_back_and_reopen(self):
        smoke = (ROOT / 'tools/ci_kodi_smoke.sh').read_text()
        self.assertIn('Music opens the unified Format root', smoke)
        self.assertIn('Format Back returns to Home Music', smoke)
        self.assertIn('Unscanned video sources are reachable', smoke)
        zipper = (ROOT / 'tools/zip_smoke_driver.py').read_text()
        self.assertIn('ZIP-installed unified Music root', zipper)
        self.assertIn('self.check_music()', zipper)
        for source in (smoke, zipper):
            self.assertNotIn('Music choice', source)
            self.assertNotIn('library://music/', source)

    def test_format_back_uses_controller_equivalent_back_not_previousmenu(self):
        smoke = (ROOT / 'tools/ci_kodi_smoke.sh').read_text()
        self.assertIn("before=press('BackSpace')\n                wait_for('Format Back returns to Home Music'", smoke)
        zipper = (ROOT / 'tools/zip_smoke_driver.py').read_text()
        self.assertIn("before = self.key('BackSpace')\n            self.wait('Format Back returns to Home Music'", zipper)


if __name__ == '__main__':
    unittest.main()
