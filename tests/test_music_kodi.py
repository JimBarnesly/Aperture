"""Native adapter/window contracts with mocks, NOT a Kodi renderer or audio test."""
import importlib.util
from pathlib import Path
import random
import sys
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/script.apeture.music/resources/lib"
sys.path.insert(0, str(LIB))
from apeture_music.model import albums_from_rows, songs_from_rows
from apeture_music.library import LibraryError


class FakeWindow:
    def __init__(self, *args):
        self.properties = {}
        self.focus = 100
        self.closed = False
    def setProperty(self, key, value): self.properties[key] = value
    def getProperty(self, key): return self.properties.get(key, "")
    def clearProperty(self, key): self.properties.pop(key, None)
    def setFocusId(self, value): self.focus = value
    def getFocusId(self): return self.focus
    def close(self): self.closed = True
    def doModal(self): self.onInit()


class FakeItem:
    def __init__(self, **kwargs):
        self.args = kwargs
        self.tag = Mock()
    def getMusicInfoTag(self): return self.tag
    def setContentLookup(self, value): self.lookup = value
    def setArt(self, value): self.art = value


class KodiTests(unittest.TestCase):
    def setUp(self):
        self.playlist = Mock()
        self.player = Mock()
        self.dialog = Mock()
        self.home = FakeWindow()
        self.xbmc = types.SimpleNamespace(PLAYLIST_MUSIC=0, PlayList=Mock(return_value=self.playlist),
            Player=Mock(return_value=self.player), getSkinDir=lambda: "skin.apeture", executebuiltin=Mock(),
            Monitor=Mock(), executeJSONRPC=Mock(), log=Mock())
        self.gui = types.SimpleNamespace(ListItem=FakeItem, WindowXML=FakeWindow,
            Window=lambda _: self.home, Dialog=lambda: self.dialog)
        self.addon = Mock()
        self.addon.getAddonInfo.return_value = str(ROOT / 'addons/script.apeture.music')
        mods = {"xbmc": self.xbmc, "xbmcgui": self.gui,
                "xbmcaddon": types.SimpleNamespace(Addon=lambda _: self.addon)}
        spec = importlib.util.spec_from_file_location("apeture_music.kodi_test", LIB / "apeture_music/kodi.py")
        self.kodi = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, mods): spec.loader.exec_module(self.kodi)
        self.library = Mock()
        self.albums = albums_from_rows([{"albumid": i, "title": "Record " + str(i), "artist": ["An Artist"]} for i in range(8)])
        self.library.albums.return_value = self.albums
        self.library.playing_album.return_value = 3
        self.songs = songs_from_rows([{"songid": 2, "title": "Track 2", "disc": 2, "track": 1,
            "file": 'smb://user:private@host/Musíc/2 %20 # "quoted".flac'},
            {"songid": 1, "title": "Track 1", "disc": 1, "track": 1, "file": "/music/1.flac"}])
        self.library.songs.return_value = self.songs
        self.window = self.kodi.AlbumWindow()
        self.window.configure(self.library, random.Random(4))

    def action(self, identifier):
        return types.SimpleNamespace(getId=lambda: identifier)

    def test_initial_focus_is_loaded_current_album_without_playback(self):
        self.window.onInit()
        self.assertEqual(self.window.shelf.current.id, 3)
        self.assertEqual(self.window.focus, 100)
        self.assertEqual(self.window.properties["Shelf.Position"], "4 / 8")
        self.xbmc.PlayList.assert_not_called()
        self.window.onInit()
        self.library.albums.assert_called_once()

    def test_refresh_preserves_browsed_album_without_randomizing_or_playing(self):
        self.window.onInit()
        self.window.move(2)
        self.library.playing_album.return_value = 1
        self.window.onClick(202)
        self.assertEqual(self.window.shelf.current.id, 5)
        self.assertEqual(self.window.focus, 100)
        self.library.playing_album.assert_called_once()  # Initial entry only.
        self.xbmc.PlayList.assert_not_called()

    def test_refresh_removed_selection_uses_current_album_then_safe_random(self):
        self.window.onInit()
        self.library.albums.return_value = [a for a in self.albums if a.id != 3]
        self.library.playing_album.return_value = 6
        self.window.load()
        self.assertEqual(self.window.shelf.current.id, 6)
        self.library.albums.return_value = [self.albums[0]]
        self.window.load()
        self.assertEqual(self.window.shelf.current.id, 0)
        self.assertEqual(self.window.properties["Shelf.HasPrevious"], "")
        self.assertEqual(self.window.properties["Shelf.HasNext"], "")

    def test_refresh_to_empty_or_error_clears_old_metadata_and_art(self):
        for result in ([], LibraryError("Cannot read library")):
            self.window.onInit()
            if isinstance(result, Exception):
                self.library.albums.side_effect = result
            else:
                self.library.albums.return_value = result
            self.window.load()
            self.assertEqual(self.window.getProperty("Shelf.Title"), "")
            self.assertEqual(self.window.getProperty("Shelf.Artist"), "")
            self.assertEqual(self.window.getProperty("Shelf.Position"), "")
            for index in range(7):
                self.assertEqual(self.window.getProperty("Shelf.Cover{}.Art".format(index)), "")
                self.assertEqual(self.window.getProperty("Shelf.Cover{}.Visible".format(index)), "")
            self.library.albums.side_effect = None
            self.library.albums.return_value = self.albums
            self.window.load()

    def test_empty_and_error_are_not_fake_catalogues_and_have_recovery(self):
        self.library.albums.return_value = []
        self.window.onInit()
        self.assertEqual(self.window.focus, 200)
        self.assertIsNone(self.window.shelf.current)
        self.library.albums.side_effect = RuntimeError("smb://user:private@server/secret.flac")
        self.window.load()
        self.assertEqual(self.window.focus, 202)
        self.assertEqual(self.window.properties["Shelf.Error"], "true")
        self.assertNotIn("secret", str(self.window.properties))
        self.assertNotIn("private", str(self.window.properties))
        self.assertFalse(self.window.busy)
        self.library.albums.side_effect = None
        self.library.albums.return_value = self.albums
        self.window.onClick(202)
        self.assertEqual(self.window.focus, 100)

    def test_empty_primary_action_opens_library_without_hidden_focus(self):
        self.library.albums.return_value = []
        self.window.onInit()
        self.assertEqual(self.window.properties["Shelf.Primary"], "Open Kodi Music")
        self.window.onClick(100)
        self.assertTrue(self.window.closed)
        self.assertEqual(self.window.destination, "library")
        self.xbmc.PlayList.assert_not_called()

    def test_render_error_clears_ready_and_exposes_recovery(self):
        with patch.object(self.window, "render", side_effect=RuntimeError("render failed")):
            self.window.onInit()
        self.assertEqual(self.window.properties["Shelf.Ready"], "")
        self.assertEqual(self.window.properties["Shelf.Error"], "true")
        self.assertEqual(self.window.properties["Shelf.Primary"], "Open Kodi Music")

    def test_browse_only_on_shelf_and_does_not_play(self):
        self.window.onInit()
        self.window.onAction(self.action(2))
        self.assertEqual(self.window.shelf.current.id, 4)
        self.window.onAction(self.action(1))
        self.assertEqual(self.window.shelf.current.id, 3)
        self.window.focus = 200
        self.window.onAction(self.action(1))
        self.assertEqual(self.window.shelf.current.id, 3)
        self.xbmc.PlayList.assert_not_called()

    def test_mouse_browse_returns_focus_to_shelf_and_edges_are_not_actionable(self):
        self.window.onInit()
        self.window.focus = 101
        self.window.onClick(101)
        self.assertEqual(self.window.focus, 100)
        self.assertEqual(self.window.shelf.current.id, 2)
        self.window.move(-100)
        self.assertEqual(self.window.properties["Shelf.HasPrevious"], "")
        self.assertEqual(self.window.properties["Shelf.HasNext"], "true")
        self.window.onClick(101)
        self.assertEqual(self.window.shelf.current.id, 0)
        self.window.move(100)
        self.assertEqual(self.window.properties["Shelf.HasPrevious"], "true")
        self.assertEqual(self.window.properties["Shelf.HasNext"], "")
        self.window.onClick(102)
        self.assertEqual(self.window.shelf.current.id, 7)
        self.xbmc.PlayList.assert_not_called()

    def test_busy_refresh_browse_and_play_do_not_reenter(self):
        self.window.onInit()
        self.window.busy = True
        self.library.reset_mock()
        self.window.onClick(202)
        self.window.onClick(101)
        self.window.onClick(102)
        self.window.onAction(self.action(79))
        self.assertEqual(self.window.shelf.current.id, 3)
        self.library.albums.assert_not_called()
        self.library.songs.assert_not_called()
        self.window.onAction(self.action(92))
        self.assertTrue(self.window.closed)  # Back is always an escape route.

    def test_all_back_actions_close_without_changing_playback(self):
        for code in (9, 10, 92):
            self.window.closed = False
            self.window.onAction(self.action(code))
            self.assertTrue(self.window.closed)
        self.xbmc.PlayList.assert_not_called()

    def test_ok_and_play_are_not_double_handled(self):
        self.window.onInit()
        with patch.object(self.kodi, "play_album") as play:
            self.window.onAction(self.action(7))  # SELECT is handled by onClick.
            play.assert_not_called()
            self.window.onClick(100)
            self.assertEqual(play.call_count, 1)
            self.window.onAction(self.action(79))
            self.assertEqual(play.call_count, 2)

    def test_ordered_play_preserves_urls_and_uses_current_omega_tags(self):
        self.kodi.play_album(self.albums[0], self.library)
        self.playlist.clear.assert_called_once()
        calls = self.playlist.add.call_args_list
        self.assertEqual([c.args[0] for c in calls], [s.file for s in self.songs])
        self.assertEqual(calls[1].args[1].args["path"], self.songs[1].file)
        self.assertFalse(calls[1].args[1].lookup)
        calls[1].args[1].tag.setDisc.assert_called_once_with(2)
        calls[1].args[1].tag.setDbId.assert_called_once_with(2, "song")
        self.playlist.unshuffle.assert_called_once()
        self.player.play.assert_called_once_with(self.playlist, startpos=0)
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmc.log.assert_not_called()

    def test_empty_or_unreadable_album_does_not_clear_current_queue(self):
        self.library.songs.return_value = []
        with self.assertRaises(LibraryError): self.kodi.play_album(self.albums[0], self.library)
        self.library.songs.side_effect = LibraryError("Read failed")
        with self.assertRaises(LibraryError): self.kodi.play_album(self.albums[0], self.library)
        self.playlist.clear.assert_not_called()

    def test_shared_file_cue_album_does_not_replace_queue(self):
        self.library.songs.return_value = songs_from_rows([
            {"songid": 1, "file": "/fixture/shared.flac", "track": 1},
            {"songid": 2, "file": "/fixture/shared.flac", "track": 2}])
        with self.assertRaises(LibraryError):
            self.kodi.play_album(self.albums[0], self.library)
        self.playlist.clear.assert_not_called()
        self.player.play.assert_not_called()

    def test_shared_file_album_has_specific_safe_native_recovery(self):
        self.window.onInit()
        self.library.songs.return_value = songs_from_rows([
            {"songid": 1, "file": "/private/shared.flac", "track": 1},
            {"songid": 2, "file": "/private/shared.flac", "track": 2}])
        self.window.play()
        self.assertIn("shared audio files", self.dialog.ok.call_args.args[1])
        self.assertNotIn("private", str(self.dialog.ok.call_args))
        self.assertEqual(self.window.focus, 200)
        self.assertFalse(self.window.busy)
        self.assertEqual(self.window.shelf.current.id, 3)
        self.playlist.clear.assert_not_called()
        self.window.onClick(200)
        self.assertEqual(self.window.destination, "library")
        self.assertTrue(self.window.closed)

    def test_item_preparation_failure_does_not_clear_queue(self):
        with patch.object(self.gui, "ListItem", side_effect=RuntimeError("bad tag")):
            with self.assertRaises(RuntimeError): self.kodi.play_album(self.albums[0], self.library)
        self.playlist.clear.assert_not_called()

    def test_playback_error_is_sanitized_and_repeated_input_not_reentrant(self):
        self.window.onInit()
        self.library.songs.side_effect = RuntimeError("smb://u:secret@server/private.flac")
        self.window.play()
        self.assertNotIn("secret", str(self.dialog.ok.call_args))
        self.assertFalse(self.window.busy)
        self.window.busy = True
        self.library.songs.reset_mock()
        self.window.play()
        self.library.songs.assert_not_called()

    def test_run_clears_lock_after_window_error_and_falls_back(self):
        with patch.object(self.kodi, "AlbumWindow", side_effect=RuntimeError("bad xml")):
            self.kodi.run()
        self.assertEqual(self.home.getProperty("Apeture.Music.Open"), "")
        self.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(Music,root,return)")

    def test_repeated_run_does_not_create_second_window(self):
        self.home.setProperty("Apeture.Music.Open", "true")
        with patch.object(self.kodi, "AlbumWindow") as window:
            self.kodi.run()
            window.assert_not_called()

    def test_repeated_completed_runs_release_lock_and_have_explicit_destinations(self):
        for destination, expected in ((None, None), ("home", "ActivateWindow(Home)"),
                                      ("library", "ActivateWindow(Music,root,return)")):
            window = Mock(destination=destination)
            with patch.object(self.kodi, "AlbumWindow", return_value=window):
                self.kodi.run()
            self.assertEqual(self.home.getProperty("Apeture.Music.Open"), "")
            window.doModal.assert_called_once()
            if expected:
                self.xbmc.executebuiltin.assert_called_once_with(expected)
            else:
                self.xbmc.executebuiltin.assert_not_called()
            self.xbmc.executebuiltin.reset_mock()

    def test_missing_focus_does_not_crash_action(self):
        with patch.object(self.window, "getFocusId", side_effect=RuntimeError("no control")):
            self.window.onAction(self.action(2))


class ShelfXMLTests(unittest.TestCase):
    def setUp(self):
        self.addon = ROOT / "addons/script.apeture.music"
        self.root = ET.parse(self.addon / "resources/skins/Default/1080i/script-apeture-music.xml").getroot()

    def test_controls_have_native_navigation_visible_focus_and_all_fonts_exist(self):
        controls = {c.get("id"): c for c in self.root.iter("control") if c.get("id")}
        self.assertIn(self.root.findtext("defaultcontrol"), controls)
        fonts = {f.findtext("name") for f in ET.parse(ROOT / "addons/skin.apeture/xml/Font.xml").iter("font")}
        for font in self.root.iter("font"): self.assertIn(font.text, fonts)
        for identifier, control in controls.items():
            self.assertTrue(control.findtext("label"))
            self.assertTrue(control.findtext("texturefocus"))
            for direction in ("onleft", "onright", "onup", "ondown"):
                self.assertIn(control.findtext(direction), controls)
        self.assertIsNone(controls['100'].find('visible'))  # No hidden-control initial-focus race.
        self.assertEqual(controls['100'].findtext('onleft'), '100')
        self.assertEqual(controls['100'].findtext('onright'), '100')

    def test_packaged_art_exists_and_perspective_has_no_downloads(self):
        for tag in ("texture", "texturefocus", "texturenofocus"):
            for texture in self.root.iter(tag):
                if texture.text.startswith("shelf/"):
                    self.assertTrue((self.addon / 'resources/skins/Default/media' / texture.text).is_file())
                self.assertNotIn('http', texture.text)
        rotations = [a for a in self.root.iter('animation') if a.get('effect') == 'rotatey']
        self.assertEqual(len(rotations), 6)

    def test_neighbor_pivots_have_no_screen_y_depth_and_angles_stay_readable(self):
        # Omega CRotateEffect passes center.x,center.y into SetYRotation(x,z).
        # 'auto' would use the image's screen Y as a false Z-depth pivot.
        neighbors = [c for c in self.root.iter('control')
                     if c.find("animation[@effect='rotatey']") is not None]
        self.assertEqual(len(neighbors), 6)
        for control in neighbors:
            animation = control.find("animation[@effect='rotatey']")
            x, z = map(float, animation.get('center').split(','))
            self.assertEqual(x, float(control.findtext('left')) + float(control.findtext('width')) / 2)
            self.assertEqual(z, 0)
            self.assertLessEqual(abs(float(animation.get('end'))), 30)
            self.assertEqual(animation.get('start'), animation.get('end'))

    def test_browse_buttons_do_not_overlay_covers_and_disable_at_shelf_edges(self):
        for identifier, prop in (('101', 'HasPrevious'), ('102', 'HasNext')):
            control = self.root.find('.//control[@id="' + identifier + '"]')
            self.assertGreaterEqual(int(control.findtext('top')), 900)
            self.assertEqual(control.findtext('enable'), 'String.IsEqual(Window.Property(Shelf.' + prop + '),true)')
            self.assertTrue(control.findtext('disabledcolor'))

    def test_queue_and_shuffle_consequences_are_visible_before_play(self):
        hints = [c for c in self.root.iter('control')
                 if c.findtext('label') == 'Replaces queue · Shuffle off']
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].findtext('visible'), 'String.IsEqual(Window.Property(Shelf.Ready),true)')

    def test_all_cover_slots_fall_back_when_local_art_is_missing(self):
        covers = [node for node in self.root.iter('texture') if 'Shelf.Cover' in (node.text or '')]
        self.assertEqual(len(covers), 7)
        for cover in covers:
            self.assertEqual(cover.get('fallback'), 'shelf/placeholder.png')

    def test_home_uses_enabled_shelf_with_native_fallback(self):
        home = ET.parse(ROOT / 'addons/skin.apeture/xml/Home.xml')
        for identifier in ('9103', '9303'):
            control = home.find('.//control[@id="' + identifier + '"]')
            actions = {c.get('condition'): c.text for c in control.findall('onclick')}
            self.assertEqual(actions['System.AddonIsEnabled(script.apeture.music)'], 'RunScript(script.apeture.music)')
            self.assertEqual(len(actions), 3)
            for condition, action in actions.items():
                if action.startswith('ActivateWindow'):
                    self.assertIn('!System.AddonIsEnabled(script.apeture.music)', condition)


if __name__ == '__main__': unittest.main()
