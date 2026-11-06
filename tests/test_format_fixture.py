import importlib.util
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import wave
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("format_fixture", ROOT / "tests/kodi_format_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FixtureTest(unittest.TestCase):
    def test_range_requests(self):
        self.assertEqual(fixture.byte_range(None, 100), (0, 99, False))
        self.assertEqual(fixture.byte_range("bytes=10-19", 100), (10, 19, True))
        self.assertEqual(fixture.byte_range("bytes=10-", 100), (10, 99, True))
        self.assertEqual(fixture.byte_range("bytes=-10", 100), (90, 99, True))
        self.assertEqual(fixture.byte_range("bytes=10-199", 100), (10, 99, True))
        for value in ("bytes=101-", "bytes=19-10", "bytes=-0", "bytes=1-2,3-4", "items=0-1", "bytes=invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fixture.byte_range(value, 100)

    def test_original_wav_and_png(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            fixture.write_wav(path, 220)
            with wave.open(str(path)) as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getsampwidth(), 2)
                self.assertEqual(stream.getnframes() / stream.getframerate(), fixture.TRACK_SECONDS)
        self.assertTrue(fixture.cover_png().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_fixture_requires_sorting_and_encodes_real_path_edge_cases(self):
        library = fixture.fixture_library()
        self.assertNotEqual(library["albums"][0]["trackIds"], fixture.TRACK_IDS)
        ordered = sorted(library["tracks"], key=lambda t: (t["disc"], t["track"]))
        self.assertEqual([item["id"] for item in ordered], fixture.TRACK_IDS)
        self.assertIn(",", fixture.TRACK_IDS[0])
        self.assertIn("&", fixture.TRACK_IDS[0])

    def test_guarded_prepare_and_observer_syntax(self):
        with tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.") as directory:
            runtime = Path(directory)
            for suffix in ("home", "system/system", "system/addons", "data/userdata", "out"):
                (runtime / suffix).mkdir(parents=True, exist_ok=True)
            (runtime / "system/system/addon-manifest.xml").write_text("<addons/>")
            (runtime / "data/userdata/guisettings.xml").write_text('<settings version="2"/>')
            env = {"HOME":str(runtime / "home"), "KODI_HOME":str(runtime / "system"),
                   "KODI_DATA":str(runtime / "data"), "APERTURE_SMOKE_OUT":str(runtime / "out")}
            with patch.dict(os.environ, env):
                config = fixture.prepare(runtime, runtime / "out")
                self.assertEqual(config["expected_ids"], fixture.TRACK_IDS)
                self.assertEqual(config["album_title"], fixture.fixture_library()["albums"][0]["title"])
                self.assertEqual(config["catalog_id"], fixture.CATALOG_ID)
                self.assertEqual(json.loads((runtime / "format-fixture/health.json").read_text()), fixture.fixture_health())
                self.assertEqual(json.loads((runtime / "format-fixture/acquisitions.json").read_text()), [])
                self.assertIn('"focused_title":xbmc.getInfoLabel("ListItem.Title")', fixture.OBSERVER_SOURCE)
                self.assertIn('Container.Property(Aperture.FormatView)', fixture.OBSERVER_SOURCE)
                self.assertIn('Control.IsVisible(64)', fixture.OBSERVER_SOURCE)
                self.assertIn('Control.IsVisible(63)', fixture.OBSERVER_SOURCE)
                self.assertTrue((runtime / "system/addons" / fixture.ADDON / "addon.py").is_file())
                self.assertFalse((runtime / "out/format-ready.json").exists())
                self.assertEqual(json.loads((runtime / "out/format-result.json").read_text())["status"], "not_run")
                ET.parse(runtime / "data/userdata/keymaps/format-ci.xml")
                compile((runtime / "system/addons" / fixture.OBSERVER / "service.py").read_text(), "service.py", "exec")
                with self.assertRaises(ValueError):
                    fixture.prepare(runtime, runtime / "out")

    def test_rejects_non_disposable_profile(self):
        with tempfile.TemporaryDirectory(prefix="ordinary-profile.") as directory:
            with self.assertRaises(ValueError):
                fixture.validated_runtime(Path(directory))


class FixtureHTTPTest(unittest.TestCase):
    """Real HTTP, isolated loopback synthetic files; never a provider connection."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="aperture-kodi-smoke.")
        self.addCleanup(self.directory.cleanup)
        runtime = Path(self.directory.name)
        self.files, self.out = runtime / "format-fixture", runtime / "out"
        self.files.mkdir()
        self.out.mkdir()
        fixture.atomic(self.files / "library.json", fixture.fixture_library())
        fixture.atomic(self.files / "health.json", fixture.fixture_health())
        fixture.atomic(self.files / "acquisitions.json", [])
        fixture.write_wav(self.files / "tone.wav", 220)
        (self.files / "cover.png").write_bytes(fixture.cover_png())
        config = {"files":{identifier:"tone.wav" for identifier in fixture.TRACK_IDS}}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), fixture.fixture_handler(config, self.files, self.out))
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = "http://127.0.0.1:{}".format(self.server.server_port)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method="GET", headers=None, **query):
        url = self.url + path + ("?" + urlencode(query) if query else "")
        try:
            response = urlopen(Request(url, method=method, headers=headers or {}), timeout=3)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            if response.headers.get("Content-Type") == "application/json" and payload:
                payload = json.loads(payload)
            return response.status, payload

    def requests(self):
        return [json.loads(line) for line in (self.out / "format-requests.jsonl").read_text().splitlines()]

    def test_read_only_browsing_cannot_queue_or_contact_a_provider(self):
        health = self.request("/api/health")[1]
        self.assertTrue(health["readOnly"])
        self.assertEqual(health["capabilities"], fixture.fixture_health()["capabilities"])
        self.assertEqual(self.request("/api/library")[1], fixture.fixture_library())
        catalogue = self.request("/api/catalog/search", q=fixture.ARTIST)[1]
        self.assertEqual(catalogue, fixture.fixture_catalogue())
        self.assertEqual(self.request("/api/catalog/album", id=fixture.CATALOG_ID)[1], fixture.fixture_preview())
        self.assertNotIn("http", json.dumps(catalogue) + json.dumps(fixture.fixture_preview()))
        self.assertEqual(self.request("/api/acquisitions"), (200, []))
        self.assertEqual({row["method"] for row in self.requests()}, {"GET"})
        self.assertEqual(json.loads((self.files / "acquisitions.json").read_text()), [])

    def test_explicit_mock_acquisition_priority_and_cancel(self):
        status, item = self.request("/api/acquire-album", "POST", id=fixture.CATALOG_ID)
        self.assertEqual((status, item["status"], item["id"]), (202, "queued", fixture.CATALOG_ID))
        self.assertEqual(self.request("/api/acquisitions")[1], [item])
        # Acquisition permission is independent of controlling existing jobs.
        fixture.atomic(self.files / "health.json", fixture.fixture_health(acquire=False))
        status, item = self.request("/api/acquisitions/prioritize", "POST", id=fixture.CATALOG_ID)
        self.assertEqual((status, item["priority"]), (202, 100))
        status, item = self.request("/api/acquisitions/cancel", "POST", id=fixture.CATALOG_ID)
        self.assertEqual((status, item["status"]), (202, "cancelled"))
        self.assertEqual(self.request("/api/acquisitions")[1], [item])
        self.assertEqual(self.request("/api/acquisitions/cancel", "POST", id=fixture.CATALOG_ID)[0], 404)
        self.assertEqual({path.name for path in self.files.iterdir()},
                         {"library.json", "health.json", "acquisitions.json", "tone.wav", "cover.png"})
        posts = [row for row in self.requests() if row["method"] == "POST"]
        self.assertEqual([row["status"] for row in posts], [202, 202, 202, 404])
        self.assertTrue(all(row["id"] == [fixture.CATALOG_ID] for row in posts))
        self.assertTrue(all(row["health"]["readOnly"] is True for row in posts))
        self.assertFalse(posts[1]["health"]["capabilities"]["acquire"])
        self.assertTrue(posts[1]["health"]["capabilities"]["prioritize"])
        self.assertTrue(posts[2]["health"]["capabilities"]["cancel"])

    def test_legacy_write_access_only_when_capabilities_are_absent(self):
        fixture.atomic(self.files / "health.json", {"readOnly":False})
        self.assertEqual(self.request("/api/acquire-album", "POST", id=fixture.CATALOG_ID)[0], 202)
        for capabilities in (None, [], "true", {}, {"cancel":1}, {"cancel":"true"}, {"acquire":True}):
            with self.subTest(capabilities=capabilities):
                fixture.atomic(self.files / "health.json", {"readOnly":False, "capabilities":capabilities})
                self.assertEqual(self.request("/api/acquisitions/cancel", "POST", id=fixture.CATALOG_ID)[0], 403)
        fixture.atomic(self.files / "health.json", {"readOnly":False})
        self.assertEqual(self.request("/api/acquisitions/cancel", "POST", id=fixture.CATALOG_ID)[0], 202)

    def test_each_capability_is_independent_and_unknown_health_fails_closed(self):
        paths = fixture.WRITE_CAPABILITIES
        for path, action in paths.items():
            for value in (False, None, 0, 1, "true", "false", [], {}):
                with self.subTest(action=action, value=value):
                    health = fixture.fixture_health(**{action:value})
                    self.assertFalse(fixture.fixture_write_allowed(health, path))
                    for other_path, other_action in paths.items():
                        if other_action != action:
                            self.assertTrue(fixture.fixture_write_allowed(health, other_path))
        for health in (None, [], "true", {}, {"readOnly":True}, {"readOnly":"false"}):
            fixture.atomic(self.files / "health.json", health)
            self.assertEqual(self.request("/api/health")[0], 200)
            self.assertEqual(self.request("/api/acquire-album", "POST", id=fixture.CATALOG_ID)[0], 403)
        self.assertEqual(json.loads((self.files / "acquisitions.json").read_text()), [])
        self.assertFalse(fixture.fixture_write_allowed(fixture.fixture_health(), "/api/library/trash-album"))

    def test_readonly_unknown_and_invalid_writes_fail_closed_and_are_logged(self):
        for health in ({"readOnly":True}, {}, {"readOnly":"false"}):
            fixture.atomic(self.files / "health.json", health)
            self.assertEqual(self.request("/api/acquire-album", "POST", id=fixture.CATALOG_ID)[0], 403)
        fixture.atomic(self.files / "health.json", {"readOnly":False})
        for method, path, identifier, status in (
                ("POST", "/api/acquire-album", "not-the-fixture", 404),
                ("GET", "/api/acquire-album", fixture.CATALOG_ID, 405),
                ("POST", "/api/library/trash-album", fixture.CATALOG_ID, 405),
                ("PUT", "/api/library", fixture.CATALOG_ID, 405),
                ("DELETE", "/api/acquisitions/history", fixture.CATALOG_ID, 405)):
            self.assertEqual(self.request(path, method, id=identifier)[0], status)
        self.assertEqual(len(self.requests()), 8)
        self.assertEqual(json.loads((self.files / "acquisitions.json").read_text()), [])

    def test_audio_ranges_offline_recovery_and_health_failure_log_real_status(self):
        status, payload = self.request("/api/audio", headers={"Range":"bytes=0-15"}, id=fixture.TRACK_IDS[0])
        self.assertEqual((status, len(payload)), (206, 16))
        self.assertEqual(self.request("/api/audio", headers={"Range":"bytes=999999999-"}, id=fixture.TRACK_IDS[0])[0], 416)
        self.assertEqual(self.request("/api/audio", "HEAD", id=fixture.TRACK_IDS[0]), (200, b""))
        (self.files / "health-offline").touch()
        self.assertEqual(self.request("/api/health")[0], 503)
        self.assertEqual(self.request("/api/library")[0], 200)
        (self.files / "offline").touch()
        self.assertEqual(self.request("/api/library")[0], 503)
        self.assertEqual(self.request("/api/acquire-album", "POST", id=fixture.CATALOG_ID)[0], 503)
        (self.files / "offline").unlink()
        self.assertEqual(self.request("/api/library")[0], 200)
        self.assertEqual([row["status"] for row in self.requests()], [206, 416, 200, 503, 200, 503, 503, 200])


if __name__ == "__main__":
    unittest.main()
