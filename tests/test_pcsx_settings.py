"""Opt-in PSX enhancement must not silently change users' emulation settings."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import setup_gaming as setup

class PcsxSettingsTests(unittest.TestCase):
    def test_real_libretro_key_and_string_options_native_default(self):
        root = ET.parse(ROOT/'pcsx-settings/resources/settings.xml')
        settings = root.findall('.//setting')
        self.assertEqual(len(settings), 1)
        option = settings[0]
        self.assertEqual(option.get('id'), 'pcsx_rearmed_neon_enhancement_enable')
        self.assertEqual(option.get('type'), 'string')
        self.assertEqual(option.findtext('default'), 'disabled')
        self.assertEqual([e.text for e in option.findall('constraints/options/option')], ['disabled', 'enabled'])
        self.assertNotIn('speed', option.get('id'))
    def test_core_staging_contains_ui_but_no_user_setting_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); core = tmp/'core.so'; core.write_bytes(b'test fixture')
            target = tmp/'addon'
            setup.make_core_addon(setup.CORES[-1], core, target)
            self.assertTrue((target/'resources/settings.xml').is_file())
            self.assertTrue((target/'resources/language/resource.language.en_gb/strings.po').is_file())
            self.assertFalse((target/'settings.xml').exists())
            self.assertFalse((tmp/'userdata').exists())
    def test_other_emulators_do_not_get_psx_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); core = tmp/'core.so'; core.write_bytes(b'test fixture')
            target = tmp/'addon'
            setup.make_core_addon(setup.CORES[0], core, target)
            self.assertFalse((target/'resources/settings.xml').exists())
    def test_help_discloses_restart_performance_and_2d_limits(self):
        helptext = (ROOT/'pcsx-settings/resources/language/resource.language.en_gb/strings.po').read_text()
        for phrase in ('Stop and restart', '2D', 'reduce speed', 'visual glitches', 'Speed hacks stay disabled'):
            self.assertIn(phrase, helptext)

if __name__ == '__main__': unittest.main()

class PcsxSettingsUpdateTests(unittest.TestCase):
    def test_update_preserves_binary_saves_and_preferences(self):
        from unittest.mock import patch
        import update_psx_settings as update
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)/'kodi'; addon=home/'addons'/('game.libretro.aperture.pcsxrearmed')
            addon.mkdir(parents=True)
            (addon/'addon.xml').write_text('<addon id="game.libretro.aperture.pcsxrearmed"/>')
            (addon/'pcsx_rearmed_libretro.so').write_bytes(b'unchanged binary')
            prefs=home/'userdata/addon_data/game.libretro.aperture.pcsxrearmed/settings.xml'
            prefs.parent.mkdir(parents=True); prefs.write_text('<settings>user choice</settings>')
            with patch.object(update,'require_stopped'):
                backup=update.update(home)
            self.assertEqual((addon/'pcsx_rearmed_libretro.so').read_bytes(),b'unchanged binary')
            self.assertEqual(prefs.read_text(),'<settings>user choice</settings>')
            self.assertEqual((backup/addon.name/'pcsx_rearmed_libretro.so').read_bytes(),b'unchanged binary')
            self.assertTrue((addon/'resources/settings.xml').is_file())
    def test_update_refuses_live_kodi_before_changes(self):
        from unittest.mock import patch
        import update_psx_settings as update
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(update,'require_stopped',side_effect=setup.SetupError('running')):
                with self.assertRaises(setup.SetupError): update.update(Path(tmp)/'kodi')
            self.assertEqual(list(Path(tmp).iterdir()),[])
    def test_update_rejects_linked_core(self):
        from unittest.mock import patch
        import update_psx_settings as update
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)/'kodi'; addon=home/'addons'/('game.libretro.aperture.pcsxrearmed')
            addon.mkdir(parents=True)
            (addon/'evil').symlink_to('/tmp')
            with patch.object(update,'require_stopped'):
                with self.assertRaises(setup.SetupError): update.update(home)
