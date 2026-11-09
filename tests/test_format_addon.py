"""Format/Kodi contract tests. These do not replace Pi GUI/audio acceptance."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ALBUM_ID = "artist%00release"
DATA = {
    "albums": [{"id": ALBUM_ID, "artist": "Artist", "title": "Double Album", "year": "2004",
                "trackIds": ["Disc 2/01, A & B.flac", "Disc 1/02.flac", "Disc 1/01.flac"]}],
    "tracks": [
        {"id": "Disc 2/01, A & B.flac", "title": "Second disc", "artist": "Artist", "disc": 2, "track": 1, "duration": 20},
        {"id": "Disc 1/02.flac", "title": "Second track", "artist": "Guest", "disc": 1, "track": "2/12", "duration": 21.4},
        {"id": "Disc 1/01.flac", "title": "First track", "artist": "Artist", "disc": 1, "track": 1, "duration": 19},
    ],
}


class FakeItem:
    def __init__(self, label="", path="", offscreen=False):
        self.label, self.path = label, path
        self.art, self.properties, self.context = {}, {}, []
        # Strict Kodi 21.3 InfoTagMusic API names, not an unbounded mock.
        self.tag = MagicMock(spec_set=["setMediaType", "setTitle", "setAlbum", "setArtist", "setAlbumArtist",
                                       "setYear", "setDuration", "setGenres", "setDisc", "setTrack"])
        self.content_lookup = True

    def getMusicInfoTag(self):
        return self.tag

    def setArt(self, value):
        self.art.update(value)

    def setProperty(self, key, value):
        self.properties[key] = value

    def setContentLookup(self, enabled):
        self.content_lookup = enabled

    def addContextMenuItems(self, items):
        self.context.extend(items)


class FormatTest(unittest.TestCase):
    def setUp(self):
        self.xbmc = MagicMock(LOGERROR=4, PLAYLIST_MUSIC=0)
        self.xbmcaddon = MagicMock()
        self.xbmcaddon.Addon.return_value.getSetting.return_value = "http://format.test:4534"
        self.xbmcgui = MagicMock(NOTIFICATION_INFO="info", ListItem=FakeItem)
        self.xbmcplugin = MagicMock(SORT_METHOD_NONE=0)
        self.modules = patch.dict(sys.modules, xbmc=self.xbmc, xbmcaddon=self.xbmcaddon,
                                  xbmcgui=self.xbmcgui, xbmcplugin=self.xbmcplugin)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location("format_addon", ROOT / "format-kodi/addon.py")
        self.addon = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.addon)
        self.data = copy.deepcopy(DATA)
        self.network = patch.object(self.addon, "urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(self.data).encode()))
        self.urlopen = self.network.start()
        self.addCleanup(self.network.stop)

    def run_action(self, action="root", handle=7, **kwargs):
        query = urlsplit(self.addon.plugin_url(action, **kwargs)).query
        self.addon.main([self.addon.BASE, str(handle), "?" + query])

    def items(self):
        return [call.args for call in self.xbmcplugin.addDirectoryItem.call_args_list]

    def assert_directory_result(self, succeeded):
        self.xbmcplugin.endOfDirectory.assert_called_once_with(7, succeeded=succeeded, cacheToDisc=False)

    def ready_turntable_previous(self, position=2, count=4):
        self.xbmc.getSkinDir.return_value = 'skin.aperture'
        self.xbmcgui.getCurrentWindowId.return_value = 12006
        self.xbmcgui.getCurrentWindowDialogId.return_value = 9999
        self.xbmc.Player.return_value.isPlayingAudio.return_value = True
        self.xbmc.PlayList.return_value.size.return_value = count
        self.xbmc.executeJSONRPC.return_value = json.dumps({'result':{'playlistid':0, 'position':position}})

    def test_up_uses_guarded_native_previous_offset_without_network_or_queue_replace(self):
        self.ready_turntable_previous()
        self.run_action('turntable_previous', handle=-1)
        self.xbmc.executebuiltin.assert_called_once_with('Playlist.PlayOffset(music,-1)')
        rpc = json.loads(self.xbmc.executeJSONRPC.call_args.args[0])
        self.assertEqual(rpc['method'], 'Player.GetProperties')
        self.assertEqual(rpc['params'], {'playerid':0, 'properties':['playlistid', 'position']})
        self.urlopen.assert_not_called()
        self.xbmc.PlayList.return_value.clear.assert_not_called()
        self.xbmc.PlayList.return_value.add.assert_not_called()
        self.xbmc.Player.return_value.play.assert_not_called()
        self.xbmcplugin.endOfDirectory.assert_not_called()
        self.xbmcgui.Dialog.assert_not_called()

    def test_up_at_first_track_uses_zero_offset_without_wrapping(self):
        for count in (1, 4):
            self.ready_turntable_previous(position=0, count=count)
            self.assertTrue(self.addon.previous_turntable_track())
            self.xbmc.executebuiltin.assert_called_with('Playlist.PlayOffset(music,0)')
        self.assertEqual(self.xbmc.executebuiltin.call_count, 2)

    def test_up_rechecks_skin_window_dialog_and_audio_after_key_press(self):
        for target, value in ((self.xbmc.getSkinDir, 'skin.estuary'),
                              (self.xbmcgui.getCurrentWindowId, 10502),
                              (self.xbmcgui.getCurrentWindowDialogId, 10120),
                              (self.xbmc.Player.return_value.isPlayingAudio, False)):
            self.ready_turntable_previous()
            target.return_value = value
            self.assertFalse(self.addon.previous_turntable_track())
        self.xbmc.executeJSONRPC.assert_not_called()
        self.xbmc.executebuiltin.assert_not_called()
        self.urlopen.assert_not_called()

    def test_up_does_nothing_without_valid_active_music_queue(self):
        for reply in ({'error':{'message':'no player'}}, {'result':{'playlistid':1, 'position':2}},
                      {'result':{'playlistid':0, 'position':-1}}, {'result':{'playlistid':0, 'position':4}},
                      {'result':{'playlistid':0, 'position':'2'}}, {'result':{'playlistid':False, 'position':2}},
                      {'result':None}, {'result':[]}, {}, None):
            with self.subTest(reply=reply):
                self.ready_turntable_previous()
                self.xbmc.executeJSONRPC.return_value = json.dumps(reply)
                self.assertFalse(self.addon.previous_turntable_track())
        self.ready_turntable_previous(count=0)
        self.assertFalse(self.addon.previous_turntable_track())
        self.xbmc.executebuiltin.assert_not_called()

    def test_up_does_nothing_when_native_player_disappears_or_response_is_invalid(self):
        self.ready_turntable_previous()
        self.xbmc.executeJSONRPC.side_effect = RuntimeError('stopped')
        self.assertFalse(self.addon.previous_turntable_track())
        self.xbmc.executeJSONRPC.side_effect = None
        self.xbmc.executeJSONRPC.return_value = '{broken'
        self.assertFalse(self.addon.previous_turntable_track())
        self.xbmc.executebuiltin.assert_not_called()

    def test_root_works_offline_without_touching_playback(self):
        self.run_action()
        self.assertEqual([entry[2].label for entry in self.items()], ["Albums", "Artists", "Search library", "Find music", "Downloads", "Configure Format server"])
        self.urlopen.assert_not_called()
        self.xbmc.PlayList.assert_not_called()
        self.assert_directory_result(True)

    def test_settings_returns_root_and_is_not_cached(self):
        self.run_action("configure")
        self.xbmcaddon.Addon.return_value.openSettings.assert_called_once()
        self.assertEqual(len(self.items()), 6)
        self.assert_directory_result(True)

    def test_album_urls_preserve_stable_encoded_id_and_art(self):
        self.run_action("albums")
        entry = self.items()[0]
        self.assertFalse(entry[3])
        self.assertEqual(entry[2].properties["IsPlayable"], "false")
        self.assertEqual(parse_qs(urlsplit(entry[1]).query)["album_id"], [ALBUM_ID])
        self.assertEqual(parse_qs(urlsplit(entry[2].art["thumb"]).query)["id"], [DATA["tracks"][0]["id"]])
        self.assertIn("RunPlugin(plugin://", entry[2].context[0][1])
        entry[2].tag.setAlbum.assert_called_with("Double Album")
        entry[2].tag.setMediaType.assert_called_once_with("album")
        self.assert_directory_result(True)

    def test_coverflow_positions_follow_visible_sorted_albums_without_playback(self):
        second = dict(self.data["albums"][0], id="another", artist="Aardvark")
        self.data["albums"].append(second)
        self.data["albums"].append(dict(second, id="empty", trackIds=[]))
        self.run_action("albums")
        entries = self.items()
        self.assertEqual([item.properties["Aperture.FormatPosition"] for _, _, item, _ in entries], ["1", "2"])
        self.assertEqual([parse_qs(urlsplit(url).query)["album_id"][0] for _, url, _, _ in entries], ["another", ALBUM_ID])
        self.assertTrue(all(parse_qs(urlsplit(url).query)["action"] == ["play_album"] for _, url, _, _ in entries))
        self.xbmc.Player.assert_not_called()
        self.xbmc.PlayList.assert_not_called()

    def test_selecting_album_uses_ordered_play_action_and_keeps_track_browsing_explicit(self):
        self.run_action("albums")
        entry = self.items()[0]
        self.assertEqual(parse_qs(urlsplit(entry[1]).query)["action"], ["play_album"])
        browse = dict(entry[2].context)["Browse tracks"]
        self.assertEqual(browse, "Container.Update({})".format(self.addon.plugin_url("album", album_id=ALBUM_ID)))
        self.xbmc.PlayList.assert_not_called()  # Merely opening the shelf is not play.
        self.xbmcplugin.reset_mock()
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = True
        player.getPlayingFile.return_value = self.addon.media("http://format.test:4534", "/api/audio", "Disc 1/01.flac")
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.xbmc.Player.return_value.play.assert_called_once_with(self.xbmc.PlayList.return_value, startpos=0)
        self.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(visualisation)")
        self.xbmcplugin.addDirectoryItem.assert_not_called()
        self.xbmcplugin.setResolvedUrl.assert_not_called()

    def test_repeated_explicit_album_selection_replaces_instead_of_appending(self):
        for _ in range(2):
            self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        playlist = self.xbmc.PlayList.return_value
        self.assertEqual(playlist.clear.call_count, 2)
        self.assertEqual(playlist.add.call_count, 6)
        self.assertEqual(playlist.unshuffle.call_count, 2)
        self.assertEqual(self.xbmc.Player.return_value.play.call_count, 2)

    def test_failed_album_selection_never_clears_queue_or_opens_turntable(self):
        for failure in ("missing_album", "missing_track", "offline"):
            with self.subTest(failure=failure):
                self.data = copy.deepcopy(DATA)
                self.xbmc.reset_mock()
                self.xbmcgui.reset_mock()
                self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(json.dumps(self.data).encode())
                if failure == "missing_album":
                    self.data["albums"] = []
                elif failure == "missing_track":
                    self.data["tracks"].pop()
                else:
                    self.urlopen.side_effect = URLError("unreachable")
                self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
                self.xbmc.PlayList.assert_not_called()
                self.xbmc.Player.assert_not_called()
                self.xbmc.executebuiltin.assert_not_called()
                self.xbmcgui.Dialog.return_value.ok.assert_called_once()

    def test_random_shelf_focus_handles_optional_parent_without_playback(self):
        for parent_offset in (0, 1):
            with self.subTest(parent_offset=parent_offset):
                self.xbmc.reset_mock()
                self.xbmc.getSkinDir.return_value = "skin.aperture"
                self.xbmcgui.getCurrentWindowId.return_value = 10502
                self.xbmcgui.getCurrentWindowDialogId.return_value = 9999
                self.xbmc.Monitor.return_value.abortRequested.return_value = False
                self.xbmc.getCondVisibility.side_effect = lambda condition: condition == "Control.IsVisible(64)"
                target_index = 2 + parent_offset
                self.xbmc.getInfoLabel.side_effect = lambda key: {
                    "Container.Property(Aperture.FormatEntry)":"fresh",
                    "System.CurrentControlId":"64",
                    "Container(64).ListItemAbsolute({}).Property(Aperture.FormatPosition)".format(target_index):"3",
                }.get(key, "")
                with patch.object(self.addon.random, "randint", return_value=3) as choose:
                    self.assertTrue(self.addon.focus_random_album(6, "fresh"))
                    choose.assert_called_once_with(1, 6)
                self.xbmc.executebuiltin.assert_called_once_with("Control.SetFocus(64,{},absolute)".format(target_index), True)
                self.xbmc.Player.assert_not_called()
                self.xbmc.PlayList.assert_not_called()

    def test_random_shelf_does_not_steal_new_navigation_or_focus(self):
        self.xbmc.getSkinDir.return_value = "skin.aperture"
        self.xbmcgui.getCurrentWindowId.return_value = 10502
        self.xbmcgui.getCurrentWindowDialogId.return_value = 9999
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        self.xbmc.Monitor.return_value.waitForAbort.return_value = False
        self.xbmc.getCondVisibility.side_effect = lambda condition: condition == "Control.IsVisible(64)"
        self.xbmc.getInfoLabel.side_effect = lambda key: "newer-entry"
        self.assertFalse(self.addon.focus_random_album(6, "old-entry"))
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmc.Monitor.return_value.waitForAbort.assert_called_with(0.1)
        self.xbmc.getCondVisibility.return_value = True
        self.xbmc.getInfoLabel.side_effect = lambda key: "65" if key == "System.CurrentControlId" else "fresh"
        self.assertFalse(self.addon.focus_random_album(6, "fresh"))
        self.xbmc.executebuiltin.assert_not_called()
        self.assertFalse(self.addon.focus_random_album(0, "fresh"))

    def test_random_shelf_never_reclaims_focus_during_album_playback(self):
        self.xbmc.getCondVisibility.side_effect = lambda condition: condition == "Player.HasAudio"
        with patch.object(self.addon.random, "randint") as choose:
            self.assertFalse(self.addon.focus_random_album(6, "fresh"))
            choose.assert_not_called()
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmc.Player.assert_not_called()
        self.xbmc.PlayList.assert_not_called()

    def enable_memory_cache(self):
        values = {}
        window = self.xbmcgui.Window.return_value
        window.getProperty.side_effect = lambda key: values.get(key, "")
        window.setProperty.side_effect = lambda key, value: values.__setitem__(key, value)
        return values

    def test_cached_shelf_avoids_repeat_fetch_but_playback_revalidates(self):
        self.enable_memory_cache()
        self.run_action("albums")
        self.run_action("albums")
        self.assertEqual(self.urlopen.call_count, 1)
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.assertEqual(self.urlopen.call_count, 2)

    def test_cache_is_server_scoped_and_never_authorizes_writes(self):
        self.enable_memory_cache()
        self.addon.library("http://first.test", allow_cached=True)
        self.addon.library("http://second.test", allow_cached=True)
        self.assertEqual(self.urlopen.call_count, 2)
        self.addon.download_access("http://first.test")
        self.assertEqual(self.urlopen.call_count, 3)
        self.xbmc.PlayList.assert_not_called()

    def test_failed_refresh_preserves_saved_shelf_but_never_uses_it_for_playback(self):
        values = self.enable_memory_cache()
        self.addon.library("http://format.test:4534")
        self.urlopen.side_effect = URLError("offline")
        with self.assertRaises(self.addon.FormatError):
            self.addon.library("http://format.test:4534")
        self.assertEqual(self.addon.library("http://format.test:4534", allow_cached=True), self.data)
        self.assertEqual(json.loads(next(iter(values.values())))["data"], self.data)
        self.assertFalse(json.loads(next(iter(values.values())))["fresh"])
        self.xbmcgui.Dialog.return_value.notification.assert_called_once()
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()

    def test_store_has_only_catalogue_downloads_and_configuration_with_disabled_notice(self):
        with patch.object(self.addon, "download_access", return_value=({"acquire":False}, {"acquire":"Downloading unavailable: backend disabled."})):
            self.run_action("store")
        self.assertEqual([entry[2].label for entry in self.items()], ["Find music", "Downloads", "Configure Format server"])
        self.assertIn(unittest.mock.call(7, "Aperture.FormatNotice", "Downloading unavailable: backend disabled."), self.xbmcplugin.setProperty.call_args_list)
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()

    def test_metadata_type_is_independent_of_local_database_ids(self):
        for is_album, expected in ((True, "album"), (False, "song")):
            with self.subTest(media_type=expected):
                item = FakeItem()
                self.addon.set_metadata(item, self.data["tracks"][0], self.data["albums"][0], is_album=is_album)
                item.tag.setMediaType.assert_called_once_with(expected)
                self.assertFalse(any(call[0] == "setDbId" for call in item.tag.mock_calls))
                # Strict mock deliberately has no database-id method: inventing
                # an ID for these remote-only items must fail this contract.
                with self.assertRaises(AttributeError):
                    item.tag.setDbId

    def test_tracks_sort_disc_then_track_and_preserve_commas(self):
        self.run_action("album", album_id=ALBUM_ID)
        entries = self.items()
        self.assertEqual([entry[2].label for entry in entries], ["First track", "Second track", "Second disc"])
        self.assertEqual(parse_qs(urlsplit(entries[-1][1]).query)["id"], ["Disc 2/01, A & B.flac"])
        for _, _, item, folder in entries:
            self.assertFalse(folder)
            self.assertFalse(item.content_lookup)
            self.assertEqual(item.properties["IsPlayable"], "true")
            item.tag.setMediaType.assert_called_once_with("song")
        entries[1][2].tag.setArtist.assert_called_with("Guest")
        entries[1][2].tag.setAlbumArtist.assert_called_with("Artist")
        entries[1][2].tag.setTrack.assert_called_with(2)
        self.xbmc.PlayList.assert_not_called()
        self.assert_directory_result(True)

    def test_album_play_builds_ordered_queue_and_unshuffles(self):
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        playlist = self.xbmc.PlayList.return_value
        self.assertEqual([call.args[1].label for call in playlist.add.call_args_list], ["First track", "Second track", "Second disc"])
        for call in playlist.add.call_args_list:
            call.args[1].tag.setMediaType.assert_called_once_with("song")
        playlist.clear.assert_called_once()
        playlist.unshuffle.assert_called_once()
        self.xbmc.Player.return_value.play.assert_called_once_with(playlist, startpos=0)
        self.xbmcplugin.endOfDirectory.assert_not_called()

    def test_missing_track_does_not_destroy_existing_queue(self):
        self.data["tracks"].pop()
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()
        self.xbmcgui.Dialog.return_value.ok.assert_called_once()

    def set_browser_origin(self):
        self.xbmc.getSkinDir.return_value = "skin.aperture"
        self.xbmcgui.getCurrentWindowId.return_value = 10502
        self.xbmcgui.getCurrentWindowDialogId.return_value = 9999
        self.xbmc.getInfoLabel.side_effect = lambda key: {"Container.PluginName":self.addon.ADDON_ID,
            "Container.FolderPath":"plugin://format/album"}.get(key, "")
        self.xbmc.Monitor.return_value.abortRequested.return_value = False
        self.xbmc.Monitor.return_value.waitForAbort.return_value = False
        self.xbmc.Player.return_value.getTime.return_value = 1

    def test_now_playing_waits_for_exact_requested_stream(self):
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = True
        player.getPlayingFile.side_effect = ["old-stream", "expected-stream"]
        self.assertTrue(self.addon.show_now_playing("expected-stream", "plugin://format/album", player))
        self.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(visualisation)")
        self.xbmc.Monitor.return_value.waitForAbort.assert_called_once_with(0.1)

    def test_now_playing_never_steals_changed_navigation(self):
        self.set_browser_origin()
        self.xbmcgui.getCurrentWindowId.return_value = 10000
        self.assertFalse(self.addon.show_now_playing("stream", "plugin://format/album"))
        self.xbmc.executebuiltin.assert_not_called()

    def test_now_playing_does_not_interrupt_dialog_or_fail_resolved_playback(self):
        self.set_browser_origin()
        self.xbmcgui.getCurrentWindowDialogId.return_value = 10100
        self.assertIsNone(self.addon.presentation_origin())
        self.xbmcgui.getCurrentWindowDialogId.return_value = 9999
        self.xbmc.Player.return_value.isPlayingAudio.return_value = True
        self.xbmc.Player.return_value.getPlayingFile.return_value = "stream"
        self.xbmc.executebuiltin.side_effect = RuntimeError("private path")
        self.assertFalse(self.addon.show_now_playing("stream", "plugin://format/album"))
        self.assertNotIn("private path", self.xbmc.log.call_args.args[0])
        self.xbmcplugin.setResolvedUrl.assert_not_called()

    def test_now_playing_rechecks_folder_after_player_readiness(self):
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = True
        def changed_folder():
            self.xbmc.getInfoLabel.side_effect = lambda key: {"Container.PluginName":self.addon.ADDON_ID,
                "Container.FolderPath":"plugin://format/different"}.get(key, "")
            return "stream"
        player.getPlayingFile.side_effect = changed_folder
        self.assertFalse(self.addon.show_now_playing("stream", "plugin://format/album", player))
        self.xbmc.executebuiltin.assert_not_called()

    def test_now_playing_waits_for_own_busy_dialog_without_closing_it(self):
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = True
        player.getPlayingFile.return_value = "stream"
        self.xbmcgui.getCurrentWindowDialogId.side_effect = [10138, 10138, 9999, 9999]
        self.assertTrue(self.addon.show_now_playing("stream", "plugin://format/album", player))
        self.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(visualisation)")
        self.xbmc.Monitor.return_value.waitForAbort.assert_called_once_with(0.1)

    def test_now_playing_waits_for_actual_clock_not_early_player_flag(self):
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = True
        player.getPlayingFile.return_value = "stream"
        player.getTime.side_effect = [0, 0, 0.2]
        self.assertTrue(self.addon.show_now_playing("stream", "plugin://format/album", player))
        self.assertEqual(self.xbmc.Monitor.return_value.waitForAbort.call_count, 2)
        self.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(visualisation)")

    def test_track_entries_remain_direct_streams_for_native_queue_advancement(self):
        self.run_action("album", album_id=ALBUM_ID)
        self.assertTrue(all(entry[1].startswith("http://format.test:4534/api/audio?") for entry in self.items()))
        self.xbmc.Player.assert_not_called()
        self.xbmcplugin.setResolvedUrl.assert_not_called()

    def test_now_playing_timeout_abort_and_non_aperture_are_safe(self):
        self.set_browser_origin()
        player = self.xbmc.Player.return_value
        player.isPlayingAudio.return_value = False
        self.assertFalse(self.addon.show_now_playing("stream", "plugin://format/album", player))
        self.assertEqual(self.xbmc.Monitor.return_value.waitForAbort.call_count, 50)
        self.xbmc.Monitor.return_value.abortRequested.return_value = True
        self.assertFalse(self.addon.show_now_playing("stream", "plugin://format/album", player))
        self.xbmc.getSkinDir.return_value = "skin.estuary"
        self.assertIsNone(self.addon.presentation_origin())
        self.assertFalse(self.addon.show_now_playing("stream", None, player))
        self.xbmc.executebuiltin.assert_not_called()
        player.play.assert_not_called()

    def test_missing_album_fails_directory(self):
        self.run_action("album", album_id="gone")
        self.assert_directory_result(False)

    def test_empty_library_has_clear_message(self):
        self.data = {"albums": [], "tracks": []}
        self.run_action("albums")
        self.assertFalse(self.items())
        self.xbmcgui.Dialog.return_value.notification.assert_called_once()
        self.assert_directory_result(True)

    def test_schema_failure_is_not_a_successful_empty_listing(self):
        for invalid in ([], {}, {"albums": {}, "tracks": []}, {"albums": [None], "tracks": []}):
            with self.subTest(invalid=invalid):
                self.data = invalid
                with self.assertRaises(self.addon.FormatError):
                    self.addon.library("http://format.test")

    def test_unreachable_server_is_reported_and_not_cached(self):
        self.urlopen.side_effect = URLError("offline")
        self.run_action("albums")
        self.assert_directory_result(False)
        self.assertIn("Cannot reach Format", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])

    def test_http_error_does_not_leak_response(self):
        self.urlopen.side_effect = HTTPError("http://private.test", 403, "secret diagnostic", {}, None)
        self.run_action("albums")
        message = self.xbmcgui.Dialog.return_value.ok.call_args.args[1]
        self.assertIn("HTTP 403", message)
        self.assertNotIn("secret", message)
        self.assertNotIn("private", message)
        self.assert_directory_result(False)

    def test_html_response_is_reported(self):
        self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(b"<html>Not Format</html>")
        self.run_action("albums")
        self.assert_directory_result(False)

    def test_oversized_library_is_rejected(self):
        self.addon.MAX_LIBRARY_BYTES = 10
        self.run_action("albums")
        self.assert_directory_result(False)

    def test_library_uses_bounded_read1_chunks_and_closes_response(self):
        payload = json.dumps(dict(self.data, padding="x" * 150000)).encode()
        class Response(io.BytesIO):
            sizes = []
            def read(self, *args):
                raise AssertionError("read() can stall on a trickling body")
            def read1(self, size):
                self.sizes.append(size)
                return super().read1(size)
        response = Response(payload)
        self.urlopen.side_effect = lambda *args, **kwargs: response
        result = self.addon.library("http://format.test")
        self.assertEqual(result["tracks"], self.data["tracks"])
        self.assertTrue(response.closed)
        self.assertGreater(len(response.sizes), 2)
        self.assertTrue(all(0 < size <= 64 * 1024 for size in response.sizes))
        self.urlopen.assert_called_once_with("http://format.test/api/library", timeout=12)

    def test_trickling_body_hits_monotonic_budget_without_touching_queue(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read1.return_value = b" "
        self.urlopen.side_effect = lambda *args, **kwargs: response
        # Each read returns bytes, so a per-socket timeout alone never fires.
        with patch.object(self.addon.time, "monotonic", side_effect=[0, 1, 8, 9, 16, 17, 21]):
            self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.assertEqual(response.read1.call_count, 3)
        response.read.assert_not_called()
        response.__exit__.assert_called_once()
        self.assertIn("too long", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()

    def test_deadline_at_end_of_body_rejects_even_valid_json(self):
        response = io.BytesIO(json.dumps(self.data).encode())
        self.urlopen.side_effect = lambda *args, **kwargs: response
        with patch.object(self.addon.time, "monotonic", side_effect=[0, 1, 20]):
            with self.assertRaisesRegex(self.addon.FormatError, "too long"):
                self.addon.library("http://format.test")
        self.assertTrue(response.closed)

    def test_size_limit_accepts_exact_payload_and_rejects_one_extra_byte(self):
        payload = json.dumps(self.data).encode()
        self.addon.MAX_LIBRARY_BYTES = len(payload)
        self.assertEqual(self.addon.library("http://format.test"), self.data)
        self.urlopen.side_effect = lambda *args, **kwargs: io.BytesIO(payload + b" ")
        with self.assertRaisesRegex(self.addon.FormatError, "too large"):
            self.addon.library("http://format.test")

    def test_socket_timeout_is_safe_and_preserves_queue(self):
        self.urlopen.side_effect = TimeoutError("http://private.test/secret")
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()
        message = self.xbmcgui.Dialog.return_value.ok.call_args.args[1]
        self.assertIn("Cannot reach Format", message)
        self.assertNotIn("private", message)
        self.assertNotIn("secret", message)

    def test_no_hard_coded_fallback_server(self):
        self.xbmcaddon.Addon.return_value.getSetting.return_value = ""
        self.run_action("albums")
        self.urlopen.assert_not_called()
        self.assert_directory_result(False)

    def test_invalid_urls_rejected(self):
        for value in ("", "server:4534", "file:///tmp/a", "http://", "http://user:password@server", "http://server/?token=x", "http://server/#anchor", "http://server:abc", "http://server:99999", "http://bad host"):
            with self.subTest(value=value):
                self.xbmcaddon.Addon.return_value.getSetting.return_value = value
                with self.assertRaises(self.addon.FormatError):
                    self.addon.server_url()

    def test_reverse_proxy_prefix_and_setting_change(self):
        self.xbmcaddon.Addon.return_value.getSetting.return_value = "https://music.test/format/"
        self.run_action("albums")
        self.urlopen.assert_called_once_with("https://music.test/format/api/library", timeout=12)
        self.xbmcaddon.Addon.return_value.getSetting.return_value = "http://second.test:4534"
        self.assertEqual(self.addon.server_url(), "http://second.test:4534")

    def test_bad_metadata_does_not_crash(self):
        for value in (None, "", "not a number", -1, float("nan"), float("inf"), {}, []):
            self.assertEqual(self.addon.number(value), 0)
        self.assertEqual(self.addon.number("2/12"), 2)
        self.data["tracks"][0]["duration"] = "unknown"
        self.data["tracks"][0]["disc"] = None
        self.run_action("album", album_id=ALBUM_ID)
        self.assert_directory_result(True)

    def test_track_id_deduplication_and_unknown_numbers_keep_api_order(self):
        self.data["albums"][0]["trackIds"].append("Disc 1/01.flac")
        for track in self.data["tracks"]:
            track.pop("disc")
            track.pop("track")
        result = self.addon.album_tracks(self.data, self.data["albums"][0])
        self.assertEqual([t["id"] for t in result], DATA["albums"][0]["trackIds"])

    def test_unknown_action_fails(self):
        self.run_action("delete")
        self.urlopen.assert_not_called()
        self.assert_directory_result(False)

    def test_settings_schema_matches_addon_and_has_no_old_ip_default(self):
        settings = ET.parse(ROOT / "format-kodi/resources/settings.xml")
        self.assertEqual(settings.find("section").get("id"), self.addon.ADDON_ID)
        self.assertIsNone(settings.find(".//setting[@id='server_url']/default").text)
        labels = [node.get("label") for node in settings.iter() if node.get("label")]
        strings = (ROOT / "format-kodi/resources/language/resource.language.en_gb/strings.po").read_text()
        for label in labels:
            self.assertIn('msgctxt "#{}"'.format(label), strings)


if __name__ == "__main__":
    unittest.main()
