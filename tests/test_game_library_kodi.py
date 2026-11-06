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
from apeture_library.cache import LibraryCache
from apeture_library import cache as cache_module
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
        source = patch.object(cache_module, "inspect_source", return_value={"identity": "a" * 64, "session": "fixture"})
        source.start()
        self.addCleanup(source.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addon = Mock()
        self.profile = self.root / ".profile"
        self.addon.getAddonInfo.return_value = str(self.profile)
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
        self.vfs.translatePath.side_effect = lambda path: str(self.root) if path.startswith("special://") else path
        self.player = Mock()
        self.xbmc = types.SimpleNamespace(getSkinDir=lambda: "skin.estuary", getCondVisibility=Mock(return_value=False), executebuiltin=Mock(), Player=lambda: self.player, Monitor=lambda: self.monitor, log=Mock(),
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

    def seed_cache(self):
        cache = LibraryCache(self.profile, str(self.root))
        cache.publish(scan_library(str(self.root)), cache_module.inspect_source(str(self.root))["identity"])
        return cache

    def run_plugin(self, query="", warm=True):
        if warm and self.addon.getSetting.return_value == str(self.root):
            if LibraryCache(self.profile, str(self.root)).load() is None:
                self.seed_cache()
        self.module.run([self.module.BASE_URL, "42", "?" + query])

    def directory_items(self):
        return self.plugin_api.addDirectoryItems.call_args.args[1]

    def one_game(self):
        return self.seed_cache().load()[0].libraries[0].games[0]

    def test_root_lists_system_folders_without_scanning_games(self):
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

    def test_cold_root_is_nonblocking_and_never_scans(self):
        self.put("nes/Demo.nes")
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            self.run_plugin(warm=False)
        self.plugin_api.setProperty.assert_called_with(42, "Aperture.LibraryState", "indexing")
        self.progress.create.assert_not_called()
        self.dialog.ok.assert_not_called()

    def test_missing_source_uses_last_good_cache_without_access(self):
        self.put("nes/Demo.nes")
        self.seed_cache()
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            self.run_plugin()
            self.run_plugin("action=system&system=nes")
        self.progress.create.assert_not_called()
        self.dialog.ok.assert_not_called()
        self.assertEqual(self.directory_items()[0][1].label, "Demo")

    def test_repeated_entries_new_plugin_instances_never_scan(self):
        self.put("nes/Demo.nes")
        self.seed_cache()
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            for _ in range(3):
                self.run_plugin()
                self.run_plugin("action=system&system=nes")
        self.progress.create.assert_not_called()
        self.dialog.ok.assert_not_called()

    def test_refresh_is_queued_without_scanning_or_clearing_list(self):
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            self.run_plugin("action=refresh")
        self.assertTrue(cache.request_path.exists())
        self.assertEqual(self.directory_items()[0][1].properties["Aperture.GameCount"], "1")
        self.progress.create.assert_not_called()

    def test_replaced_symlink_cannot_launch_from_cache(self):
        path = self.put("nes/Demo.nes")
        key = self.module.game_key(self.one_game())
        path.unlink()
        other = self.put("other/Outside.nes")
        path.symlink_to(other)
        self.run_plugin("action=play&system=nes&game=" + key)
        self.player.play.assert_not_called()
        self.dialog.ok.assert_called_once_with("text-32000", "text-32013")

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

    def load_background(self):
        self.xbmc.getInfoLabel = Mock(return_value="")
        modules = {"xbmc": self.xbmc, "xbmcaddon": types.SimpleNamespace(Addon=lambda identifier: self.addon),
                   "xbmcvfs": self.vfs, "apeture_library.kodi": self.module}
        spec = importlib.util.spec_from_file_location("apeture_library.background_test", LIB / "apeture_library/background.py")
        background = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(background)
        return background

    def test_background_service_builds_cache_without_progress_or_navigation(self):
        self.put("nes/Demo.nes")
        background = self.load_background()
        self.assertTrue(background.tick(self.addon, self.monitor))
        self.assertFalse(background.tick(self.addon, self.monitor))
        self.assertEqual(LibraryCache(self.profile, str(self.root)).load()[0].libraries[0].games[0].title, "Demo")
        self.xbmc.executebuiltin.assert_not_called()
        self.progress.create.assert_not_called()

    def test_background_completes_first_run_placeholder_without_stealing_focus(self):
        self.put("nes/Demo.nes")
        background = self.load_background()
        self.xbmc.getInfoLabel.side_effect = lambda label: self.module.BASE_URL if label == "Container.FolderPath" else "indexing"
        self.assertTrue(background.tick(self.addon, self.monitor))
        self.xbmc.executebuiltin.assert_called_once_with("Container.Refresh")

    def test_background_defers_placeholder_refresh_until_modal_closes(self):
        self.put("nes/Demo.nes")
        background = self.load_background()
        self.xbmc.getInfoLabel.side_effect = lambda label: self.module.BASE_URL if label == "Container.FolderPath" else "indexing"
        self.xbmc.getCondVisibility.return_value = True
        self.assertTrue(background.tick(self.addon, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmc.getCondVisibility.return_value = False
        self.assertFalse(background.tick(self.addon, self.monitor))
        self.xbmc.executebuiltin.assert_called_once_with("Container.Refresh")

    def test_publication_race_does_not_enqueue_another_scan(self):
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        cache.mark_attempt("ready")
        snapshot = cache.load()
        with patch.object(LibraryCache, "load", side_effect=[None, snapshot]):
            self.run_plugin(warm=False)
        self.assertFalse(cache.request_path.exists())
        self.plugin_api.setProperty.assert_called_with(42, "Aperture.LibraryState", "ready")

    def test_background_does_not_refresh_a_populated_list(self):
        self.put("nes/Demo.nes")
        background = self.load_background()
        self.xbmc.getInfoLabel.side_effect = lambda label: self.module.BASE_URL if label == "Container.FolderPath" else "ready"
        self.assertTrue(background.tick(self.addon, self.monitor))
        self.xbmc.executebuiltin.assert_not_called()

    def test_service_missing_root_defers_without_dialog_or_cache_erasure(self):
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        cache.request_refresh()
        background = self.load_background()
        before = cache.path.read_bytes()
        with patch.object(background, "scan_library", side_effect=self.module.ScanError("private root offline")):
            self.monitor.waitForAbort.return_value = True
            background.run_service()
        self.assertEqual(cache.path.read_bytes(), before)
        self.assertEqual(cache.status(), "unavailable")
        self.assertNotIn("private", self.xbmc.log.call_args.args[0])
        self.dialog.ok.assert_not_called()
        self.progress.create.assert_not_called()

    def test_ambiguous_empty_vfs_manual_refresh_preserves_snapshot(self):
        from apeture_library.cache import refresh
        from apeture_library.scanner import ScanResult
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        before = cache.path.read_bytes()
        cache.request_refresh()
        self.vfs.exists.return_value = True
        self.vfs.listdir.return_value = ([], [])
        result = scan_library("smb://host/share", self.module.KodiFileSystem())
        self.assertEqual(result, ScanResult((), ()))
        self.assertFalse(refresh(cache, lambda: result))
        self.assertEqual(cache.path.read_bytes(), before)
        self.run_plugin(warm=False)
        items = self.plugin_api.addDirectoryItems.call_args.args[1]
        self.assertTrue(any("confirm_empty" in item[0] for item in items))
        self.plugin_api.setProperty.assert_any_call(42, "Aperture.RefreshState", "empty_retained")

    def test_clear_confirmation_cancel_and_accept_do_not_scan(self):
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        cache.mark_attempt("empty_retained")
        before = cache.path.read_bytes()
        self.dialog.yesno.return_value = False
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            self.run_plugin("?action=confirm_empty", warm=False)
            self.assertEqual(cache.path.read_bytes(), before)
            self.dialog.yesno.return_value = True
            self.run_plugin("?action=confirm_empty", warm=False)
        self.assertFalse(cache.load()[0].libraries)
        self.assertTrue((self.root / "nes/Demo.nes").exists())

    def test_clear_confirmation_source_change_preserves_original(self):
        self.put("nes/Demo.nes")
        cache = self.seed_cache()
        cache.mark_attempt("empty_retained")
        before = cache.path.read_bytes()
        def answer(*args, **kwargs):
            self.addon.getSetting.return_value = str(self.root / "other")
            return True
        self.dialog.yesno.side_effect = answer
        self.run_plugin("?action=confirm_empty", warm=False)
        self.assertEqual(cache.path.read_bytes(), before)
        self.dialog.ok.assert_called()

    def test_vfs_directory_exists_check_retains_trailing_slash(self):
        fs = self.module.KodiFileSystem()
        self.vfs.listdir.return_value = (["nes"], [])
        fs.listdir("smb://host/share")
        self.vfs.exists.assert_called_once_with("smb://host/share/")


if __name__ == "__main__":
    unittest.main()

