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
        self.tag = MagicMock(spec_set=["setTitle", "setAlbum", "setArtist", "setAlbumArtist",
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

    def test_root_works_offline_without_touching_playback(self):
        self.run_action()
        self.assertEqual([entry[2].label for entry in self.items()], ["Albums", "Configure Format server"])
        self.urlopen.assert_not_called()
        self.xbmc.PlayList.assert_not_called()
        self.assert_directory_result(True)

    def test_settings_returns_root_and_is_not_cached(self):
        self.run_action("configure")
        self.xbmcaddon.Addon.return_value.openSettings.assert_called_once()
        self.assertEqual(len(self.items()), 2)
        self.assert_directory_result(True)

    def test_album_urls_preserve_stable_encoded_id_and_art(self):
        self.run_action("albums")
        entry = self.items()[0]
        self.assertTrue(entry[3])
        self.assertEqual(parse_qs(urlsplit(entry[1]).query)["album_id"], [ALBUM_ID])
        self.assertEqual(parse_qs(urlsplit(entry[2].art["thumb"]).query)["id"], [DATA["tracks"][0]["id"]])
        self.assertIn("RunPlugin(plugin://", entry[2].context[0][1])
        entry[2].tag.setAlbum.assert_called_with("Double Album")
        self.assert_directory_result(True)

    def test_tracks_sort_disc_then_track_and_preserve_commas(self):
        self.run_action("album", album_id=ALBUM_ID)
        entries = self.items()
        self.assertEqual([entry[2].label for entry in entries], ["First track", "Second track", "Second disc"])
        self.assertEqual(parse_qs(urlsplit(entries[-1][1]).query)["id"], ["Disc 2/01, A & B.flac"])
        for _, _, item, folder in entries:
            self.assertFalse(folder)
            self.assertFalse(item.content_lookup)
            self.assertEqual(item.properties["IsPlayable"], "true")
        entries[1][2].tag.setArtist.assert_called_with("Guest")
        entries[1][2].tag.setAlbumArtist.assert_called_with("Artist")
        entries[1][2].tag.setTrack.assert_called_with(2)
        self.xbmc.PlayList.assert_not_called()
        self.assert_directory_result(True)

    def test_album_play_builds_ordered_queue_and_unshuffles(self):
        self.run_action("play_album", handle=-1, album_id=ALBUM_ID)
        playlist = self.xbmc.PlayList.return_value
        self.assertEqual([call.args[1].label for call in playlist.add.call_args_list], ["First track", "Second track", "Second disc"])
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
