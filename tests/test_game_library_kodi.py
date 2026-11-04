"""Kodi adapter contract tests; not a real Kodi/RetroPlayer runtime test."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

LIB = Path(__file__).resolve().parents[1] / "games-kodi/resources/lib"
sys.path.insert(0, str(LIB))
from apeture_library.scanner import scan_library  # noqa: E402


class FakeGameTag:
    def setTitle(self, value):
        self.title = value

    def setPlatform(self, value):
        self.platform = value


class FakeListItem:
    def __init__(self, label="", label2="", path="", offscreen=False):
        self.label, self.label2, self.path = label, label2, path
        self.properties = {}
        self.tag = None
        self.content_lookup = True

    def setProperty(self, key, value):
        self.properties[key] = value

    def setArt(self, art):
        self.art = art

    def setContentLookup(self, value):
        self.content_lookup = value

    def getGameInfoTag(self):
        self.tag = FakeGameTag()
        return self.tag

    def addContextMenuItems(self, items):
        self.context = items


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addon = Mock()
        self.addon.getSetting.return_value = str(self.root)
        self.addon.getLocalizedString.side_effect = lambda identifier: "text-{}".format(identifier)
        self.dialog = Mock()
        self.dialog.select.return_value = 0
        self.progress = Mock()
        self.progress.iscanceled.return_value = False
        self.monitor = Mock()
        self.monitor.abortRequested.return_value = False
        self.plugin_api = Mock()
        self.vfs = Mock()
        self.vfs.translatePath.return_value = str(self.root)
        self.player = Mock()
        self.xbmc = types.SimpleNamespace(Player=lambda: self.player, Monitor=lambda: self.monitor, log=Mock(),
                                         LOGWARNING=2, LOGERROR=3)
        modules = {
            "xbmc": self.xbmc,
            "xbmcaddon": types.SimpleNamespace(Addon=lambda addon_id: self.addon),
            "xbmcgui": types.SimpleNamespace(ListItem=FakeListItem, Dialog=lambda: self.dialog,
                                              DialogProgress=lambda: self.progress,
                                              NOTIFICATION_WARNING="warning"),
            "xbmcplugin": self.plugin_api,
            "xbmcvfs": self.vfs,
        }
        specification = importlib.util.spec_from_file_location("apeture_library.kodi_test", LIB / "apeture_library/kodi.py")
        self.module = importlib.util.module_from_spec(specification)
        with patch.dict(sys.modules, modules):
            specification.loader.exec_module(self.module)

    def put(self, relative, content=""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_plugin(self, query=""):
        self.module.run([self.module.BASE_URL, "42", "?" + query])

    def directory_items(self):
        return self.plugin_api.addDirectoryItems.call_args.args[1]

    def one_game(self):
        return scan_library(str(self.root)).libraries[0].games[0]

    def test_root_contains_only_populated_systems_plus_explicit_actions(self):
        self.put("nes/Game.nes")
        (self.root / "snes").mkdir()
        self.run_plugin()
        systems = [(uri, item, folder) for uri, item, folder in self.directory_items()
                   if "Aperture.System" in item.properties]
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0][1].properties["Aperture.System"], "nes")
        self.assertEqual(systems[0][1].properties["Aperture.GameCount"], "1")
        self.assertTrue(systems[0][2])
        self.plugin_api.setContent.assert_called_once_with(42, "games")
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=True, updateListing=False, cacheToDisc=False)

    def test_system_items_use_native_game_tags_and_opaque_play_links(self):
        self.put('nes/A & B "demo" café.nes')
        self.run_plugin("action=system&system=nes")
        uri, item, folder = self.directory_items()[0]
        self.assertTrue(folder)
        self.assertEqual(item.properties["IsPlayable"], "false")
        self.assertFalse(item.content_lookup)
        self.assertEqual(item.label, 'A & B "demo" café')
        # A tagged folder is misclassified as a playable archive by Kodi's Play action.
        self.assertIsNone(item.tag)
        self.assertEqual(item.art["icon"], "DefaultAddonGame.png")
        self.assertNotIn(str(self.root), uri)
        self.assertNotIn("café", uri)
        self.assertEqual(len(parse_qs(urlsplit(uri).query)["game"][0]), 64)

    def test_play_resolves_actual_file_with_game_tag_and_no_forced_core(self):
        path = self.put("nes/Demo.nes")
        key = self.module.game_key(self.one_game())
        self.run_plugin("action=play&system=nes&game=" + key)
        actual_path, item = self.player.play.call_args.args
        self.assertEqual(actual_path, str(path))
        self.plugin_api.setResolvedUrl.assert_not_called()
        self.assertEqual(item.path, str(path))
        self.assertEqual(item.properties["IsPlayable"], "true")
        self.assertEqual(item.tag.title, "Demo")
        self.assertFalse(hasattr(item.tag, "gameclient"))
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)

    def test_playlist_disc_picker_resolves_disc_not_m3u(self):
        self.put("psx/Disc 1.chd")
        chosen = self.put("psx/Disc 2.chd")
        self.put("psx/Example.m3u", "Disc 1.chd\nDisc 2.chd")
        self.dialog.select.return_value = 1
        key = self.module.game_key(self.one_game())
        self.run_plugin("action=play&system=psx&game=" + key)
        self.assertEqual(self.player.play.call_args.args[1].path, str(chosen))
        self.dialog.select.assert_called_once_with("text-32014", ["Disc 1.chd", "Disc 2.chd"])

    def test_disc_picker_cancel_is_failed_resolution_not_first_disc(self):
        self.put("psx/Disc.chd")
        self.put("psx/Example.m3u", "Disc.chd")
        self.dialog.select.return_value = -1
        key = self.module.game_key(self.one_game())
        self.run_plugin("action=play&system=psx&game=" + key)
        self.player.play.assert_not_called()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)
        self.dialog.ok.assert_not_called()

    def test_removed_game_cannot_be_resolved_from_stale_link(self):
        path = self.put("nes/Demo.nes")
        key = self.module.game_key(self.one_game())
        path.unlink()
        self.run_plugin("action=play&system=nes&game=" + key)
        self.player.play.assert_not_called()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)
        self.dialog.ok.assert_called_once_with("text-32000", "text-32013")

    def test_unconfigured_root_offers_settings_not_fake_systems(self):
        self.addon.getSetting.return_value = ""
        self.run_plugin()
        self.plugin_api.setProperty.assert_called_with(42, "Aperture.LibraryState", "unconfigured")
        uri, item, folder = self.directory_items()[0]
        self.assertIn("action=settings", uri)
        self.assertEqual(item.label, "text-32004")
        self.assertTrue(folder)

    def test_unavailable_root_has_recovery_settings_and_no_path_in_log(self):
        self.addon.getSetting.return_value = str(self.root / "private-missing")
        self.run_plugin()
        self.plugin_api.setProperty.assert_called_with(42, "Aperture.LibraryState", "error")
        self.assertIn("action=settings", self.directory_items()[0][0])
        self.assertNotIn("private-missing", self.xbmc.log.call_args.args[0])
        self.progress.close.assert_called_once()

    def test_scan_cancel_closes_progress_and_finishes_directory(self):
        self.progress.iscanceled.return_value = True
        self.run_plugin()
        self.progress.close.assert_called_once()
        self.plugin_api.addDirectoryItems.assert_not_called()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)
        self.dialog.ok.assert_not_called()

    def test_settings_cancel_returns_to_empty_directory_without_loop(self):
        self.addon.getSetting.return_value = ""
        self.run_plugin("action=settings")
        self.addon.openSettings.assert_called_once()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=True, updateListing=True, cacheToDisc=False)

    def test_runplugin_help_has_no_invalid_directory_callback(self):
        self.module.run([self.module.BASE_URL, "-1", "?action=help"])
        self.dialog.ok.assert_called_once_with("text-32007", "text-32008")
        self.plugin_api.endOfDirectory.assert_not_called()

    def test_unknown_action_is_not_executed(self):
        self.run_plugin("action=RunScript%28bad%29")
        self.dialog.ok.assert_called_once_with("text-32000", "text-32015")
        self.plugin_api.endOfDirectory.assert_called_once()

    def test_untrusted_play_path_cannot_bypass_discovery(self):
        self.run_plugin("action=play&system=nes&game=../../private&path=/outside.nes")
        self.player.play.assert_not_called()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)

    def test_excessive_query_has_terminal_callback(self):
        self.run_plugin("&".join("x{}=a".format(index) for index in range(13)))
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)

    def test_special_root_is_translated_and_file_uri_supported(self):
        root, fs = self.module.configured_source("special://profile/roms")
        self.assertEqual(root, str(self.root))
        self.vfs.translatePath.assert_called_once_with("special://profile/roms")
        root, fs = self.module.configured_source(self.root.as_uri())
        self.assertEqual(root, str(self.root))

    def test_smb_nfs_root_preserved_and_unsupported_uri_rejected(self):
        for uri in ("smb://host/share/ROMs", "nfs://host/share/ROMs"):
            root, fs = self.module.configured_source(uri + "/")
            self.assertEqual(root, uri)
            self.assertIsInstance(fs, self.module.KodiFileSystem)
        for uri in ("https://host/roms", "plugin://other/", "zip://archive/", "relative/path",
                    "smb://host/share/../private", "smb://host/share?option=1"):
            with self.subTest(uri=uri), self.assertRaises(self.module.ScanError):
                self.module.configured_source(uri)

    def test_vfs_directory_exists_check_retains_trailing_slash(self):
        fs = self.module.KodiFileSystem()
        self.vfs.listdir.return_value = (["nes"], [])
        fs.listdir("smb://host/share")
        self.vfs.exists.assert_called_once_with("smb://host/share/")


if __name__ == "__main__":
    unittest.main()
