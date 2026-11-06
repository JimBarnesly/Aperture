"""Native Format workflows against synthetic data only; never a real downloader."""
import copy
import io
import json
from itertools import product
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
import unittest

import test_format_addon as legacy

DATA = legacy.DATA

SERVER = "http://format.test:4534"
CATALOG_ID = "catalogue%00release, A & B"
ACQUISITION_ID = "acquisition:specific%00release, A & B"
PREVIEW = {"id": CATALOG_ID, "artist": "Test Artist", "title": "Test Album", "year": "2025",
           "cover": "https://external.invalid/private-cover", "tracks": [
               {"disc": 1, "position": 1, "title": "Catalogue song", "artist": "Test Artist", "duration": 25}]}
QUEUED = {"id": ACQUISITION_ID, "artist": "Test Artist", "title": "Test Album", "status": "queued", "queuePosition": 2, "progress": 0}


class WorkflowTest(unittest.TestCase):
    run_action = legacy.FormatTest.run_action
    items = legacy.FormatTest.items
    assert_directory_result = legacy.FormatTest.assert_directory_result

    def setUp(self):
        legacy.FormatTest.setUp(self)
        self.responses = {
            "/api/library": self.data,
            "/api/health": {"readOnly": False},
            "/api/catalog/search": {"artist": {"name": "Test Artist"}, "albums": [dict(PREVIEW, owned=False)]},
            "/api/catalog/album": copy.deepcopy(PREVIEW),
            "/api/acquisitions": [copy.deepcopy(QUEUED)],
            "/api/shadow-albums": [],
        }
        self.calls = []
        self.post_response = dict(QUEUED)
        self.urlopen.side_effect = self.response
        self.xbmcgui.Dialog.return_value.yesno.return_value = False
        self.xbmcgui.Dialog.return_value.select.return_value = -1
        self.xbmcgui.Dialog.return_value.input.return_value = ""

    def response(self, request, **kwargs):
        method = request.get_method() if hasattr(request, "get_method") else "GET"
        url = request.full_url if hasattr(request, "full_url") else request
        parsed = urlsplit(url)
        self.calls.append((method, parsed.path, parse_qs(parsed.query)))
        self.assertEqual((parsed.scheme, parsed.netloc), ("http", "format.test:4534"))
        value = self.post_response if method == "POST" else self.responses[parsed.path]
        if callable(value):
            value = value()
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(json.dumps(value).encode())

    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]

    def labels(self):
        return [entry[2].label for entry in self.items()]

    def property(self, key):
        return [call.args[2] for call in self.xbmcplugin.setProperty.call_args_list if call.args[1] == key][-1]

    def test_publishing_download_has_no_cancel_action(self):
        self.responses["/api/health"] = {"readOnly": True,
            "capabilities": {"acquire": True, "cancel": True, "prioritize": True}}
        self.responses["/api/acquisitions"] = [dict(QUEUED, status="running", publicationStarted=True)]
        self.run_action("downloads")
        row = next(entry for entry in self.items()
                   if entry[2].properties.get("Aperture.FormatStatus") == "Running")
        self.assertFalse(row[2].context)
        self.assertEqual(parse_qs(urlsplit(row[1]).query)["action"], ["noop"])
        self.assertFalse(self.posts())

    def test_stale_cancel_rechecks_publication_before_confirmation(self):
        self.responses["/api/acquisitions"] = [dict(QUEUED, status="running", publicationStarted=True)]
        for action in (None, "cancel_download"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(self.addon.FormatError, "being finalised"):
                    self.addon.download_action(SERVER, ACQUISITION_ID, action)
        self.xbmcgui.Dialog.return_value.select.assert_not_called()
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()
        self.assertFalse(self.posts())

    def test_protected_server_explicitly_allows_only_acquisition(self):
        self.responses["/api/health"] = {
            "readOnly": True, "capabilities": {"acquire": True, "cancel": False, "prioritize": False,
                "editMetadata": False, "deleteMedia": False, "repair": False},
            "downloads": {"enabled": True, "ready": True, "reason": None}}
        self.run_action("catalog_album", album_id=CATALOG_ID)
        self.assertIn("Download album", self.labels())
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertEqual(self.posts(), [("POST", "/api/acquire-album", {"id": [CATALOG_ID]})])
        for action in ("cancel_download", "prioritize_download"):
            with self.assertRaises(self.addon.FormatError):
                self.addon.download_action(SERVER, ACQUISITION_ID, action)
        self.assertEqual(len(self.posts()), 1)

    def test_explicit_capability_keys_are_independent_in_download_ui(self):
        for acquire, cancel, prioritize in product((False, True), repeat=3):
            with self.subTest(acquire=acquire, cancel=cancel, prioritize=prioritize):
                self.xbmcplugin.addDirectoryItem.reset_mock()
                self.responses["/api/health"] = {"readOnly": True, "capabilities": {
                    "acquire": acquire, "cancel": cancel, "prioritize": prioritize}}
                self.run_action("downloads")
                row = next(entry for entry in self.items()
                           if entry[2].properties.get("Aperture.FormatStatus") == "Queued")
                labels = (["Cancel download"] if cancel else []) + (["Move to front"] if prioritize else [])
                self.assertEqual([entry[0] for entry in row[2].context], labels)
                self.assertEqual(parse_qs(urlsplit(row[1]).query)["action"], ["download" if labels else "noop"])
                self.assertFalse(row[3])
                self.assertFalse(self.posts())

    def test_explicit_denial_overrides_broad_readwrite_legacy_field(self):
        self.responses["/api/health"] = {"readOnly": False, "capabilities": {"acquire": False}}
        permissions, _ = self.addon.download_access(SERVER)
        self.assertEqual(permissions, {"acquire": False, "cancel": False, "prioritize": False})
        with self.assertRaises(self.addon.FormatError):
            self.addon.acquire(SERVER, CATALOG_ID)
        self.assertFalse(self.posts())
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()

    def test_present_malformed_capabilities_never_use_legacy_fallback(self):
        for malformed in (None, [], "true", True, 1, {}):
            with self.subTest(malformed=malformed):
                self.responses["/api/health"] = {"readOnly": False, "capabilities": malformed}
                permissions, _ = self.addon.download_access(SERVER)
                self.assertEqual(permissions, {"acquire": False, "cancel": False, "prioritize": False})
        self.assertFalse(self.posts())

    def test_nonboolean_and_missing_capability_values_fail_closed(self):
        for value in (1, 0, "true", "false", None, [], {}):
            with self.subTest(value=value):
                self.responses["/api/health"] = {"readOnly": False, "capabilities": {
                    "acquire": value, "cancel": True}}
                permissions, _ = self.addon.download_access(SERVER)
                self.assertEqual(permissions, {"acquire": False, "cancel": True, "prioritize": False})
        self.assertFalse(self.posts())

    def test_legacy_fallback_requires_wholly_absent_capabilities(self):
        for read_only in (True, False, 0, 1, None, "false"):
            with self.subTest(read_only=read_only):
                self.responses["/api/health"] = {"readOnly": read_only}
                permissions, _ = self.addon.download_access(SERVER)
                self.assertEqual(permissions, {key: read_only is False for key in ("acquire", "cancel", "prioritize")})
        self.responses["/api/health"] = {}
        self.assertFalse(any(self.addon.download_access(SERVER)[0].values()))

    def test_readiness_and_unrelated_capabilities_never_grant_actions(self):
        self.responses["/api/health"] = {"readOnly": False, "capabilities": {
            "editMetadata": True, "deleteMedia": True, "repair": True},
            "downloads": {"enabled": True, "ready": True, "reason": None}}
        self.assertFalse(any(self.addon.download_access(SERVER)[0].values()))
        self.assertFalse(self.posts())

    def test_readiness_diagnostics_do_not_override_authoritative_capability(self):
        self.responses["/api/health"] = {"readOnly": True, "capabilities": {"acquire": True},
            "downloads": {"enabled": False, "ready": False, "reason": "disabled"}}
        permissions, notices = self.addon.download_access(SERVER)
        self.assertTrue(permissions["acquire"])
        self.assertEqual(notices["acquire"], "Downloads are saved to your Format server.")

    def test_known_download_reasons_are_safe_and_controls_remain_independent(self):
        for reason in self.addon.DOWNLOAD_REASON_NOTICES:
            with self.subTest(reason=reason):
                self.responses["/api/health"] = {"readOnly": True,
                    "capabilities": {"acquire": False, "cancel": True, "prioritize": True},
                    "downloads": {"enabled": True, "ready": False, "reason": reason}}
                permissions, notices = self.addon.download_access(SERVER)
                self.assertEqual(notices["acquire"], self.addon.DOWNLOAD_REASON_NOTICES[reason])
                self.assertEqual(permissions, {"acquire": False, "cancel": True, "prioritize": True})
                self.assertNotIn("does not allow", notices["acquire"])

    def test_unknown_and_malformed_download_reasons_are_never_displayed(self):
        for details in ({"reason": "secret http://private.invalid/token"}, {"reason": ["secret"]},
                        {"reason": {"secret": True}}, None, "secret"):
            with self.subTest(details=details):
                self.responses["/api/health"] = {"readOnly": False, "capabilities": {"acquire": False},
                                                "downloads": details}
                _, notices = self.addon.download_access(SERVER)
                self.assertIn("has not enabled album acquisition", notices["acquire"])
                self.assertNotIn("secret", str(notices))
                self.assertNotIn("private", str(notices))

    def test_acquire_capability_revoked_while_confirmation_is_open(self):
        self.responses["/api/health"] = {"readOnly": True, "capabilities": {"acquire": True}}
        def revoke(*args):
            self.responses["/api/health"]["capabilities"]["acquire"] = False
            return True
        self.xbmcgui.Dialog.return_value.yesno.side_effect = revoke
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertFalse(self.posts())
        self.assertIn("has not enabled", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])
        self.xbmc.executebuiltin.assert_not_called()

    def test_each_control_rechecks_its_capability_after_confirmation(self):
        for action, capability in (("cancel_download", "cancel"), ("prioritize_download", "prioritize")):
            with self.subTest(action=action):
                self.responses["/api/health"] = {"readOnly": False, "capabilities": {
                    "acquire": True, "cancel": True, "prioritize": True}}
                def revoke(*args):
                    self.responses["/api/health"]["capabilities"][capability] = False
                    return True
                self.xbmcgui.Dialog.return_value.yesno.side_effect = revoke
                self.run_action(action, handle=-1, acquisition_id=ACQUISITION_ID)
                self.assertFalse(self.posts())
                self.assertIn("does not allow", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])
        self.xbmc.executebuiltin.assert_not_called()

    def test_queue_controls_work_when_acquisition_is_blocked(self):
        self.responses["/api/health"] = {"readOnly": True,
            "capabilities": {"acquire": False, "cancel": True, "prioritize": True},
            "downloads": {"enabled": True, "ready": False, "reason": "storage_unavailable"}}
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("prioritize_download", handle=-1, acquisition_id=ACQUISITION_ID)
        self.run_action("cancel_download", handle=-1, acquisition_id=ACQUISITION_ID)
        self.assertEqual([call[1] for call in self.posts()], ["/api/acquisitions/prioritize", "/api/acquisitions/cancel"])

    def test_action_dialog_exposes_only_permitted_control(self):
        for capability, label in (("cancel", "Cancel download"), ("prioritize", "Move to front")):
            with self.subTest(capability=capability):
                self.responses["/api/health"] = {"readOnly": True, "capabilities": {capability: True}}
                self.xbmcgui.Dialog.return_value.select.reset_mock()
                self.run_action("download", handle=-1, acquisition_id=ACQUISITION_ID)
                self.xbmcgui.Dialog.return_value.select.assert_called_once_with("Download actions", [label])
                self.assertFalse(self.posts())

    def test_priority_permission_does_not_offer_controls_for_running_item(self):
        self.responses["/api/health"] = {"readOnly": True, "capabilities": {"prioritize": True}}
        self.responses["/api/acquisitions"] = [dict(QUEUED, status="running")]
        self.run_action("downloads")
        row = next(entry for entry in self.items() if entry[2].properties.get("Aperture.FormatStatus") == "Running")
        self.assertFalse(row[2].context)
        self.assertEqual(parse_qs(urlsplit(row[1]).query)["action"], ["noop"])
        with self.assertRaises(self.addon.FormatError):
            self.addon.download_action(SERVER, ACQUISITION_ID)
        self.assertFalse(self.posts())

    def test_mutation_endpoint_maps_to_only_its_own_capability(self):
        for endpoint, capability in self.addon.MUTATION_CAPABILITIES.items():
            with self.subTest(endpoint=endpoint):
                self.calls.clear()
                self.responses["/api/health"] = {"readOnly": True, "capabilities": {capability: True}}
                self.addon.mutate(SERVER, endpoint, ACQUISITION_ID)
                self.assertEqual(self.posts(), [("POST", endpoint, {"id": [ACQUISITION_ID]})])
                self.calls.clear()
                self.responses["/api/health"] = {"readOnly": False,
                    "capabilities": {key: key != capability for key in ("acquire", "cancel", "prioritize")}}
                with self.assertRaises(self.addon.FormatError):
                    self.addon.mutate(SERVER, endpoint, ACQUISITION_ID)
                self.assertFalse(self.posts())

    def test_directory_title_tracks_current_navigation_category(self):
        for action, params, expected in (
                ("root", {}, "Music"), ("albums", {}, "Albums"),
                ("artists", {}, "Artists"), ("downloads", {}, "Downloads"),
                ("artist", {"artist": "Artist"}, "Artist"),
                ("album", {"album_id": DATA["albums"][0]["id"]}, "Double Album"),
                ("search", {"q": "Guest"}, "Library: Guest"),
                ("catalog_album", {"album_id": CATALOG_ID}, "Test Album")):
            with self.subTest(action=action):
                self.run_action(action, **params)
                self.assertEqual(self.property("Aperture.FormatTitle"), expected)
                self.xbmcplugin.setPluginCategory.assert_called_with(7, expected)

    def test_root_prompts_are_nonfolder_actions_without_history_entries(self):
        self.run_action("root")
        for _, url, item, folder in self.items():
            action = parse_qs(urlsplit(url).query)["action"][0]
            self.assertEqual(folder, action not in ("search", "find_music", "configure"))
            if not folder:
                self.assertEqual(item.properties["IsPlayable"], "false")

    def test_artist_groups_ignore_case_and_skip_unpublished_albums(self):
        self.data["albums"] += [dict(DATA["albums"][0], id="other", artist="ARTIST", title="Another"),
                                 {"id": "empty", "artist": "Invisible", "trackIds": []}]
        self.run_action("artists")
        self.assertEqual(self.labels(), ["Artist"])
        self.assertEqual(self.items()[0][2].properties["Aperture.FormatDetail"], "2 albums")
        self.assertEqual(self.property("Aperture.FormatView"), "menu")
        self.assertEqual([call[1] for call in self.calls], ["/api/library"])

    def test_artist_route_lists_matching_albums_only(self):
        self.data["albums"] += [dict(DATA["albums"][0], id="other", artist="Someone else")]
        self.run_action("artist", artist="ARTIST")
        self.assertEqual(len(self.items()), 1)
        self.assertEqual(self.property("Aperture.FormatView"), "albums")

    def test_search_is_local_case_insensitive_and_published_only(self):
        self.data["tracks"].append({"id": "unpublished", "title": "Artist unpublished"})
        self.run_action("search", q="aRtIsT")
        self.assertEqual(len(self.items()), 3)  # Album and the two Artist tracks.
        self.assertEqual([call[1] for call in self.calls], ["/api/library"])
        self.assertEqual(self.property("Aperture.FormatView"), "menu")
        self.assertNotIn("Artist unpublished", self.labels())
        self.xbmc.PlayList.assert_not_called()

    def test_search_matches_guest_artist_and_preserves_album_metadata(self):
        self.run_action("search", q="Guest")
        self.assertEqual(self.labels(), ["Second track"])
        self.items()[0][2].tag.setAlbumArtist.assert_called_once_with("Artist")
        self.items()[0][2].tag.setMediaType.assert_called_once_with("song")

    def test_empty_search_is_clear(self):
        self.run_action("search", q="nothing matches")
        self.assertEqual(self.labels(), ["No matching albums or tracks in your library"])
        self.assert_directory_result(True)

    def test_cancelled_prompts_have_no_network_and_return_canonical_root(self):
        for action in ("search", "find_music"):
            with self.subTest(action=action):
                self.run_action(action, handle=-1)
                self.assertFalse(self.calls)
                self.xbmc.executebuiltin.assert_not_called()
        self.xbmc.PlayList.assert_not_called()

    def test_prompt_query_is_canonicalized_without_fetching_twice(self):
        for action in ("search", "find_music"):
            with self.subTest(action=action):
                self.xbmcgui.Dialog.return_value.input.return_value = "  Test Artist  "
                self.run_action(action, handle=-1)
                self.assertFalse(self.calls)
                expected = self.addon.plugin_url(action, q="Test Artist")
                self.xbmc.executebuiltin.assert_called_with("Container.Update({})".format(expected))

    def test_queries_are_bounded_before_network(self):
        for action, value in (("find_music", "a"), ("search", "x" * 201), ("find_music", "x" * 201)):
            with self.subTest(action=action, value=value):
                with self.assertRaises(self.addon.FormatError):
                    self.addon.search_query({"q": [value]}, "Search", minimum=2 if action == "find_music" else 1)
        self.assertFalse(self.calls)

    def test_catalogue_is_artist_oriented_without_external_art(self):
        self.run_action("find_music", q="Test Artist")
        self.assertIn("up to 100 studio", self.labels()[0])
        self.assertEqual(self.property("Aperture.FormatView"), "catalog")
        self.assertIn("artist", self.xbmcplugin.setPluginCategory.call_args.args[1].lower())
        self.assertEqual(self.calls[0], ("GET", "/api/catalog/search", {"q": ["Test Artist"]}))
        for entry in self.items():
            self.assertNotIn("https://external", str(entry[2].art))
        self.assertFalse(self.posts())

    def test_catalogue_no_matches_is_honest(self):
        self.responses["/api/catalog/search"] = {"artist": None, "albums": []}
        self.run_action("find_music", q="Unknown artist")
        self.assertIn("No matching studio albums", self.labels()[-1])

    def test_catalogue_malformed_response_fails_without_download(self):
        for bad in ({}, [], {"albums": [None], "artist": {}}, {"albums": [], "artist": "bad"}):
            with self.subTest(bad=bad):
                self.responses["/api/catalog/search"] = bad
                with self.assertRaises(self.addon.FormatError):
                    self.addon.find_music(7, SERVER, "Artist")
        self.assertFalse(self.posts())

    def test_preview_has_tracks_and_one_explicit_download_action(self):
        self.run_action("catalog_album", album_id=CATALOG_ID)
        self.assertEqual(self.labels(), ["Download album", "1.1  Catalogue song"])
        self.assertFalse(self.items()[0][3])
        self.assertFalse(self.items()[1][3])
        self.assertEqual(self.items()[1][2].properties["IsPlayable"], "false")
        self.assertEqual(self.property("Aperture.FormatView"), "catalog")
        self.assertFalse(self.posts())

    def test_preview_checks_server_identity_and_schema(self):
        for bad in ({}, dict(PREVIEW, id="other"), dict(PREVIEW, tracks=[]), dict(PREVIEW, tracks=[None]),
                    dict(PREVIEW, artist=None), dict(PREVIEW, title="")):
            with self.subTest(bad=bad):
                self.responses["/api/catalog/album"] = bad
                with self.assertRaises(self.addon.FormatError):
                    self.addon.catalogue_preview(SERVER, CATALOG_ID)
        self.assertFalse(self.posts())

    def test_readonly_catalogue_still_browses_without_download_action(self):
        self.responses["/api/health"] = {"readOnly": True}
        self.run_action("catalog_album", album_id=CATALOG_ID)
        self.assertNotIn("Download album", self.labels())
        self.assertIn("read-only", self.labels()[0])
        self.assertIn("Browsing and status", self.property("Aperture.FormatNotice"))
        self.assertFalse(self.posts())

    def test_write_health_requires_exact_false(self):
        for health in ({"readOnly": True}, {"readOnly": 0}, {"readOnly": "false"}, {}, [], None,
                       URLError("http://secret.invalid/token")):
            with self.subTest(health=health):
                self.responses["/api/health"] = health
                self.assertFalse(self.addon.download_access(SERVER)[0]["acquire"])
                with self.assertRaises(self.addon.FormatError):
                    self.addon.acquire(SERVER, CATALOG_ID)
        self.assertFalse(self.posts())
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()

    def test_cancelled_acquire_never_posts_or_changes_preview_history(self):
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertFalse(self.posts())
        self.xbmcgui.Dialog.return_value.yesno.assert_called_once()
        self.assertEqual([call[1] for call in self.calls], ["/api/health", "/api/catalog/album"])
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmcplugin.endOfDirectory.assert_not_called()

    def test_confirmed_acquire_uses_server_id_and_rechecks_health(self):
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertEqual(self.posts(), [("POST", "/api/acquire-album", {"id": [CATALOG_ID]})])
        self.assertEqual([call[1] for call in self.calls], ["/api/health", "/api/catalog/album", "/api/health", "/api/acquire-album"])
        self.xbmc.executebuiltin.assert_called_once_with("Container.Update({})".format(self.addon.plugin_url("downloads")))
        self.xbmcplugin.endOfDirectory.assert_not_called()

    def test_acquire_opens_status_only_after_completion(self):
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertEqual(len(self.posts()), 1)
        self.xbmc.executebuiltin.assert_called_once_with("Container.Update({})".format(self.addon.plugin_url("downloads")))
        self.xbmcplugin.endOfDirectory.assert_not_called()

    def test_health_change_while_confirmation_open_blocks_post(self):
        self.responses["/api/health"] = lambda: {"readOnly": False if len(self.calls) == 1 else True}
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
        self.assertFalse(self.posts())
        self.xbmc.executebuiltin.assert_not_called()
        self.assertIn("read-only", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])

    def test_missing_catalogue_id_never_reaches_confirmation(self):
        self.responses["/api/catalog/album"] = HTTPError(SERVER, 404, "secret", {}, None)
        self.run_action("acquire", handle=-1, album_id="invented")
        self.assertFalse(self.posts())
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()

    def test_uncertain_post_is_not_retried_and_refreshes_status(self):
        for failure in (TimeoutError("http://secret.invalid/token"), URLError("private"), {}, [],
                        {"id": ACQUISITION_ID, "status": []},
                        HTTPError("http://secret.invalid", 302, "secret", {}, None)):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.post_response = failure
                self.xbmc.executebuiltin.reset_mock()
                self.xbmcgui.Dialog.return_value.yesno.return_value = True
                self.run_action("acquire", handle=-1, album_id=CATALOG_ID)
                self.assertEqual(len(self.posts()), 1)
                message = self.xbmcgui.Dialog.return_value.ok.call_args.args[1]
                self.assertIn("may already have happened", message)
                self.assertNotIn("secret", message)
                self.assertNotIn("private", message)
                self.xbmc.executebuiltin.assert_called_once_with("Container.Update({})".format(self.addon.plugin_url("downloads")))

    def test_directory_mutations_are_rejected_before_network_or_confirmation(self):
        for action in ("acquire", "download", "cancel_download", "prioritize_download"):
            with self.subTest(action=action):
                self.run_action(action, handle=7, album_id=CATALOG_ID, acquisition_id=ACQUISITION_ID)
                self.assertFalse(self.calls)
                self.xbmcgui.Dialog.return_value.yesno.assert_not_called()
                self.xbmc.executebuiltin.assert_not_called()
                self.assertFalse(self.xbmcplugin.endOfDirectory.call_args.kwargs["succeeded"])

    def test_downloads_show_every_known_state_and_manual_refresh_only(self):
        self.responses["/api/acquisitions"] = [dict(QUEUED, id=state, status=state, progress=35) for state in self.addon.ACQUISITION_STATES]
        self.run_action("downloads")
        self.assertEqual(self.labels()[0], "Refresh downloads")
        statuses = {entry[2].properties.get("Aperture.FormatStatus") for entry in self.items()}
        self.assertTrue({s.capitalize() for s in self.addon.ACQUISITION_STATES}.issubset(statuses))
        self.assertEqual(self.property("Aperture.FormatView"), "downloads")
        self.assertEqual([call[1] for call in self.calls], ["/api/health", "/api/acquisitions", "/api/shadow-albums"])
        self.assertFalse(self.posts())
        self.xbmc.executebuiltin.assert_not_called()

    def test_shadow_states_are_distinct_and_never_offer_mutations(self):
        self.responses["/api/shadow-albums"] = [dict(QUEUED, id="shadow-id", status=state, localTrackCount=1,
            expectedTrackCount=2, manifest=[{"status": "validated"}, {"status": "missing"}], lastError="private http://secret")
            for state in self.addon.SHADOW_STATES]
        self.run_action("downloads")
        shadows = [entry for entry in self.items() if entry[2].properties.get("Aperture.FormatStatus", "").startswith("Shadow:")]
        self.assertEqual(len(shadows), len(self.addon.SHADOW_STATES))
        for entry in shadows:
            self.assertFalse(entry[3])
            self.assertFalse(entry[2].context)
            self.assertEqual(entry[2].properties["Aperture.FormatDetail"], "1 local / 1 validated / 2 expected")
            self.assertNotIn("secret", str(entry[2].properties))
            self.assertEqual(parse_qs(urlsplit(entry[1]).query)["action"], ["noop"])

    def test_cancel_requested_is_truthful_and_no_longer_actionable(self):
        self.responses["/api/acquisitions"] = [dict(QUEUED, status="running", cancelRequested=True)]
        self.run_action("downloads")
        entry = self.items()[1]
        self.assertIn("Cancellation requested", entry[2].label)
        self.assertFalse(entry[3])
        self.assertFalse(entry[2].context)
        with self.assertRaises(self.addon.FormatError):
            self.addon.download_action(SERVER, ACQUISITION_ID, "cancel_download")
        self.assertFalse(self.posts())

    def test_malformed_status_metadata_has_safe_fallback(self):
        self.responses["/api/acquisitions"] = [dict(QUEUED, status=[], progress="nan", message="http://secret")]
        self.responses["/api/shadow-albums"] = [dict(QUEUED, status={}, manifest=[None])]
        self.run_action("downloads")
        self.assertEqual(len(self.items()), 3)
        self.assertIn("Unknown", self.labels()[1])
        self.assertIn("Unknown", self.labels()[2])
        self.assert_directory_result(True)

    def test_status_sources_fail_independently(self):
        self.responses["/api/shadow-albums"] = URLError("private")
        self.run_action("downloads")
        self.assertTrue(any("Queued" in label for label in self.labels()))
        self.assertIn("Shadow album status unavailable", self.labels())
        self.assertFalse(self.posts())

    def test_malformed_status_list_is_not_empty_success(self):
        self.responses["/api/acquisitions"] = {"items": []}
        self.run_action("downloads")
        self.assertIn("Download status unavailable", self.labels())
        self.assertNotIn("No downloads yet", self.labels())

    def test_readonly_downloads_keep_status_but_hide_actions(self):
        self.responses["/api/health"] = {"readOnly": True}
        self.run_action("downloads")
        self.assertIn("read-only", self.labels()[1])
        for entry in self.items()[2:]:
            self.assertFalse(entry[2].context)
        self.assertTrue(any("Queued" in label for label in self.labels()))
        self.assertFalse(self.posts())

    def test_health_offline_status_still_works(self):
        self.responses["/api/health"] = URLError("secret")
        self.run_action("downloads")
        self.assertIn("cannot verify", self.labels()[1])
        self.assertTrue(any("Queued" in label for label in self.labels()))
        self.assertFalse(self.posts())

    def test_download_dialog_cancel_has_no_side_effect(self):
        self.run_action("download", handle=-1, acquisition_id=ACQUISITION_ID)
        self.xbmcgui.Dialog.return_value.select.assert_called_once_with("Download actions", ["Cancel download", "Move to front"])
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()
        self.assertFalse(self.posts())
        self.xbmc.executebuiltin.assert_not_called()

    def test_mutation_confirmation_refusal_never_posts(self):
        for action in ("cancel_download", "prioritize_download"):
            with self.subTest(action=action):
                self.run_action(action, handle=-1, acquisition_id=ACQUISITION_ID)
        self.assertFalse(self.posts())
        self.xbmc.executebuiltin.assert_not_called()

    def test_cancel_and_prioritize_use_verified_specific_id(self):
        for action, endpoint in (("cancel_download", "/api/acquisitions/cancel"), ("prioritize_download", "/api/acquisitions/prioritize")):
            with self.subTest(action=action):
                self.calls.clear()
                self.xbmc.executebuiltin.reset_mock()
                self.xbmcgui.Dialog.return_value.yesno.return_value = True
                self.run_action(action, handle=-1, acquisition_id=ACQUISITION_ID)
                self.assertEqual(self.posts(), [("POST", endpoint, {"id": [ACQUISITION_ID]})])
                self.assertEqual([call[1] for call in self.calls], ["/api/health", "/api/acquisitions", "/api/health", endpoint])
                self.xbmc.executebuiltin.assert_called_once_with("Container.Refresh")

    def test_wrong_returned_cancel_id_is_an_uncertain_outcome(self):
        self.post_response = dict(QUEUED, id="another download")
        self.xbmcgui.Dialog.return_value.yesno.return_value = True
        self.run_action("cancel_download", handle=-1, acquisition_id=ACQUISITION_ID)
        self.assertEqual(len(self.posts()), 1)
        self.assertIn("could not confirm", self.xbmcgui.Dialog.return_value.ok.call_args.args[1])

    def test_unknown_shadow_and_duplicate_ids_never_target_acquisition(self):
        for items, target in (([QUEUED], "shadow-id"), ([QUEUED, dict(QUEUED)], ACQUISITION_ID),
                              ([dict(QUEUED, status="complete")], ACQUISITION_ID)):
            with self.subTest(items=items, target=target):
                self.responses["/api/acquisitions"] = items
                with self.assertRaises(self.addon.FormatError):
                    self.addon.download_action(SERVER, target, "cancel_download")
        self.assertFalse(self.posts())
        self.xbmcgui.Dialog.return_value.yesno.assert_not_called()

    def test_running_download_cannot_be_prioritized(self):
        self.responses["/api/acquisitions"] = [dict(QUEUED, status="running")]
        with self.assertRaises(self.addon.FormatError):
            self.addon.download_action(SERVER, ACQUISITION_ID, "prioritize_download")
        self.assertFalse(self.posts())

    def test_noop_context_action_has_no_network_playback_or_navigation(self):
        self.run_action("noop", handle=-1)
        self.assertFalse(self.calls)
        self.xbmc.PlayList.assert_not_called()
        self.xbmc.Player.assert_not_called()
        self.xbmc.executebuiltin.assert_not_called()
        self.xbmcplugin.endOfDirectory.assert_not_called()

    def test_display_metadata_cannot_inject_kodi_markup(self):
        self.assertEqual(self.addon.display("[B]Hello[/B]\nworld"), "(B)Hello(/B) world")
        self.assertEqual(len(self.addon.display("x" * 1000)), 240)
        self.assertEqual(self.addon.display({"token": "private"}, "Unknown"), "Unknown")

    def test_native_metadata_is_plain_text_without_changing_ids(self):
        album = self.data["albums"][0]
        album["title"] = "[COLOR red]Album[/COLOR]"
        album["artist"] = "[B]Artist[/B]"
        self.run_action("albums")
        item = self.items()[0][2]
        item.tag.setTitle.assert_called_once_with("(COLOR red)Album(/COLOR)")
        item.tag.setAlbum.assert_called_once_with("(COLOR red)Album(/COLOR)")
        item.tag.setArtist.assert_called_once_with("(B)Artist(/B)")
        self.assertEqual(parse_qs(urlsplit(self.items()[0][1]).query)["album_id"], [album["id"]])

    def test_items_are_fully_annotated_before_kodi_copies_them(self):
        snapshots = []
        def snapshot(handle, url, item, folder):
            snapshots.append({"label": item.label, "art": dict(item.art),
                              "properties": dict(item.properties), "context": list(item.context)})
        self.xbmcplugin.addDirectoryItem.side_effect = snapshot
        self.run_action("artists")
        self.assertIn("thumb", snapshots[0]["art"])
        snapshots.clear()
        self.run_action("find_music", q="Test Artist")
        self.assertEqual(snapshots[1]["properties"]["Aperture.FormatStatus"], "Catalogue")
        snapshots.clear()
        self.run_action("catalog_album", album_id=CATALOG_ID)
        self.assertEqual(snapshots[0]["properties"]["Aperture.FormatStatus"], "Available to download")
        self.assertEqual(snapshots[1]["properties"]["Aperture.FormatStatus"], "Preview")
        snapshots.clear()
        self.run_action("downloads")
        self.assertEqual(snapshots[1]["properties"]["Aperture.FormatStatus"], "Queued")
        self.assertEqual([entry[0] for entry in snapshots[1]["context"]], ["Cancel download", "Move to front"])

    def test_end_directory_precedes_aperture_view_selection(self):
        order = []
        self.xbmc.getSkinDir.return_value = "skin.aperture"
        self.xbmcplugin.endOfDirectory.side_effect = lambda *a, **k: order.append("ended")
        self.xbmc.executebuiltin.side_effect = lambda value: order.append(value)
        self.run_action("albums")
        self.assertEqual(order, ["ended", "Container.SetViewMode(64)"])

    def test_non_aperture_skin_never_has_its_view_overridden(self):
        self.xbmc.getSkinDir.return_value = "skin.estuary"
        self.run_action("albums")
        self.xbmc.executebuiltin.assert_not_called()

    def test_all_api_payloads_use_size_limit_and_close_response(self):
        response = io.BytesIO(b"[" + b" " * 100 + b"]")
        self.urlopen.side_effect = lambda *a, **k: response
        with self.assertRaisesRegex(self.addon.FormatError, "too large"):
            self.addon.request_json(SERVER, "/api/acquisitions", maximum=10)
        self.assertTrue(response.closed)

    def test_endpoint_allowlist_excludes_archive_repair_and_operator_apis(self):
        for endpoint in ("/api/download-album", "/api/rescan", "/api/shadow-albums/acquire", "/api/download-approvals", "/api/acquisitions/history", "/api/library/trash-album"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(self.addon.FormatError):
                    self.addon.request_json(SERVER, endpoint, post=True)
        self.assertFalse(self.calls)


class RedirectTest(unittest.TestCase):
    """Real disposable HTTP verifies urllib never follows GET or POST redirects."""
    def setUp(self):
        legacy.FormatTest.setUp(self)
        self.network.stop()  # Exercise the production HTTP opener, localhost only.
        self.requests = []
        requests = self.requests
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.respond("GET")
            def do_POST(self):
                self.respond("POST")
            def respond(self, method):
                requests.append((method, self.path))
                self.send_response(self.server.redirect_code)
                self.send_header("Location", self.server.redirect_target)
                self.end_headers()
            def log_message(self, *args):
                pass
        self.target = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.source = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.source.redirect_target = "http://127.0.0.1:{}/must-not-receive-id".format(self.target.server_port)
        for server in (self.source, self.target):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        self.server = "http://127.0.0.1:{}".format(self.source.server_port)

    def test_no_cross_origin_redirect_or_post_retry(self):
        for code in (301, 302, 303, 307, 308):
            for post in (False, True):
                with self.subTest(code=code, post=post):
                    self.requests.clear()
                    self.source.redirect_code = code
                    endpoint = "/api/acquire-album" if post else "/api/catalog/album"
                    with self.assertRaises(self.addon.FormatError):
                        self.addon.request_json(self.server, endpoint, {"id": "private-specific-id"}, post=post)
                    self.assertEqual(len(self.requests), 1)
                    self.assertEqual(self.requests[0][0], "POST" if post else "GET")
                    self.assertNotIn("must-not-receive", self.requests[0][1])


if __name__ == "__main__":
    unittest.main()
