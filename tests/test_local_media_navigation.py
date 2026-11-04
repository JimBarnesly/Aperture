"""Local media must remain available without guessing or changing drive paths."""
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

    def test_music_opens_one_choice_instead_of_hijacking_local_music(self):
        self.assertEqual(self.actions(103), {None: 'SetFocus(203)'})
        self.assertEqual(self.buttons['103'].findtext('onright'), '203')
        self.assertEqual(sum(b.findtext('label') == 'Music' for b in self.buttons.values()), 1)

    def test_local_music_explicitly_resets_to_native_root(self):
        # Bare ActivateWindow(Music) can reopen the last-used Format directory.
        self.assertEqual(self.actions(203), {None: 'ActivateWindow(Music,library://music/,return)'})
        self.assertIsNone(self.buttons['203'].find('enable'))

    def test_format_is_separate_and_disabled_when_unavailable(self):
        enabled = 'System.AddonIsEnabled(plugin.audio.aperture.format)'
        self.assertEqual(self.buttons['204'].findtext('enable'), enabled)
        self.assertEqual(self.actions(204), {enabled: 'ActivateWindow(Music,plugin://plugin.audio.aperture.format/,return)'})
        labels = [node.text for node in self.home.iter('label')]
        self.assertIn('Install or enable the Format add-on to stream music', labels)

    def test_choice_back_and_left_both_return_to_music(self):
        for ident in ('203', '204'):
            for event in ('onleft', 'onback'):
                self.assertEqual(self.buttons[ident].findtext(event), '103')

    def test_choice_is_visible_before_setfocus_and_while_navigating(self):
        group = next(node for node in self.home.iter('control')
                     if node.find("control[@id='203']") is not None)
        self.assertEqual(group.findtext('visible'),
                         'Control.HasFocus(103) | Control.HasFocus(203) | Control.HasFocus(204)')

    def test_movies_and_television_browse_files_before_scanning(self):
        for ident, content, folder in ((100, 'Movies', 'movies'), (101, 'TVShows', 'tvshows')):
            self.assertEqual(self.actions(ident), {
                f'Library.HasContent({content})': f'ActivateWindow(Videos,videodb://{folder}/titles/,return)',
                f'!Library.HasContent({content})': 'ActivateWindow(Videos,sources://video/,return)',
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
        self.assertEqual(len(self.buttons), 9)

    def test_home_does_not_run_media_mutations_or_assume_hdd_paths(self):
        for action in self.home.iter('onclick'):
            self.assertTrue(action.text.startswith(('ActivateWindow(', 'SetFocus(')), action.text)
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

    def test_real_gui_runners_cover_cancel_local_and_format_routes(self):
        smoke = (ROOT / 'tools/ci_kodi_smoke.sh').read_text()
        self.assertIn('Music choice Back returns to Music', smoke)
        self.assertIn('Unscanned video sources are reachable', smoke)
        zipper = (ROOT / 'tools/zip_smoke_driver.py').read_text()
        self.assertIn('ZIP-installed local music', zipper)
        self.assertIn('Format choice focused', zipper)

    def test_choice_cancel_uses_controller_equivalent_back_not_previousmenu(self):
        smoke = (ROOT / 'tools/ci_kodi_smoke.sh').read_text()
        self.assertIn("before=press('BackSpace')\n                wait_for('Music choice Back returns to Music'", smoke)
        zipper = (ROOT / 'tools/zip_smoke_driver.py').read_text()
        self.assertIn("before = self.key('BackSpace')\n        self.wait('Music choice cancels to Home Music'", zipper)


if __name__ == '__main__':
    unittest.main()
