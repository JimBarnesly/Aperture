"""Only Aperture's owned fullscreen-music bindings may be written or removed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'format-kodi/resources/keymaps/aperture-turntable.xml'
spec = importlib.util.spec_from_file_location('turntable_keymap', ROOT / 'format-kodi/turntable_keymap.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TurntableKeymapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reload, self.warn = Mock(), Mock()
        self.keymap = module.TurntableKeymap(self.root / 'keymaps', SOURCE, self.reload, self.warn)

    def test_only_fullscreen_music_keyboard_and_remote_up_down_are_mapped(self):
        keymap = ET.parse(SOURCE).getroot()
        self.assertEqual([child.tag for child in keymap], ['Visualisation'])
        self.assertEqual([child.tag for child in keymap[0]], ['keyboard', 'remote'])
        for device in keymap[0]:
            self.assertEqual([(key.tag, key.text) for key in device],
                             [('up', 'RunPlugin(plugin://plugin.audio.aperture.format/?action=turntable_previous)'),
                              ('down', 'SkipNext')])

    def test_other_skin_does_not_create_profile_files(self):
        self.keymap.sync(False)
        self.keymap.close()
        self.assertFalse(self.keymap.path.parent.exists())
        self.reload.assert_not_called()

    def test_install_and_skin_switch_only_change_owned_file(self):
        self.keymap.path.parent.mkdir()
        custom = self.keymap.path.parent / 'keyboard.xml'
        custom.write_bytes(b'Unrelated user keymap')
        self.keymap.sync(True)
        self.assertEqual(self.keymap.path.read_bytes(), SOURCE.read_bytes())
        self.reload.assert_called_once_with()
        self.keymap.sync(True)
        self.assertEqual(self.reload.call_count, 1)
        self.keymap.sync(False)
        self.assertFalse(self.keymap.path.exists())
        self.assertEqual(custom.read_bytes(), b'Unrelated user keymap')
        self.assertEqual(self.reload.call_count, 2)
        self.keymap.sync(True)
        self.assertTrue(self.keymap.path.exists())
        self.keymap.close()
        self.assertFalse(self.keymap.path.exists())

    def test_existing_matching_file_is_not_rewritten_or_reloaded(self):
        self.keymap.path.parent.mkdir()
        self.keymap.path.write_bytes(SOURCE.read_bytes())
        original = self.keymap.path.stat().st_mtime_ns
        self.keymap.sync(True)
        self.assertEqual(self.keymap.path.stat().st_mtime_ns, original)
        self.reload.assert_not_called()
        self.keymap.close()
        self.assertFalse(self.keymap.path.exists())
        self.reload.assert_called_once_with()

    def test_stale_owned_keymap_is_removed_on_other_skin_startup(self):
        self.keymap.path.parent.mkdir()
        self.keymap.path.write_bytes(SOURCE.read_bytes())
        self.keymap.sync(False)
        self.assertFalse(self.keymap.path.exists())
        self.reload.assert_called_once_with()

    def test_name_collision_and_subsequent_custom_edits_are_preserved(self):
        self.keymap.path.parent.mkdir()
        self.keymap.path.write_bytes(b'User custom keymap')
        for active in (True, False, True):
            self.keymap.sync(active)
        self.keymap.close()
        self.assertEqual(self.keymap.path.read_bytes(), b'User custom keymap')
        self.reload.assert_not_called()
        self.assertEqual(self.warn.call_count, 2)

    def test_custom_edit_after_install_is_not_removed(self):
        self.keymap.sync(True)
        self.keymap.path.write_bytes(b'Customized after installation')
        self.keymap.close()
        self.assertEqual(self.keymap.path.read_bytes(), b'Customized after installation')
        self.reload.assert_called_once_with()

    def test_symlink_is_never_followed_or_removed(self):
        target = self.root / 'target'
        target.write_bytes(SOURCE.read_bytes())
        self.keymap.path.parent.mkdir()
        self.keymap.path.symlink_to(target)
        self.keymap.sync(True)
        self.keymap.close()
        self.assertTrue(self.keymap.path.is_symlink())
        self.assertEqual(target.read_bytes(), SOURCE.read_bytes())
        self.reload.assert_not_called()
        self.warn.assert_called_once()

    def test_directory_name_collision_is_preserved(self):
        self.keymap.path.mkdir(parents=True)
        self.keymap.sync(True)
        self.keymap.close()
        self.assertTrue(self.keymap.path.is_dir())
        self.reload.assert_not_called()
        self.warn.assert_called_once()

    def test_read_only_profile_is_nonfatal_without_reload_or_repeated_writes(self):
        with patch.object(Path, 'mkdir', side_effect=PermissionError):
            self.keymap.sync(True)
            self.keymap.sync(True)
        self.warn.assert_called_once()
        self.reload.assert_not_called()
        self.assertFalse(self.keymap.path.exists())


if __name__ == '__main__':
    unittest.main()
