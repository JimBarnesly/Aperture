"""Durable cache, restart, concurrency and failed-refresh regression coverage."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

LIB = Path(__file__).resolve().parents[1] / "games-kodi/resources/lib"
sys.path.insert(0, str(LIB))
from apeture_library import cache as c
from apeture_library.scanner import ScanCancelled, ScanError, ScanIssue, ScanResult, scan_library, validate_launch


class CacheTests(unittest.TestCase):
    def setUp(self):
        source = patch.object(c, "inspect_source", return_value={"identity": "a" * 64, "session": "fixture"})
        source.start()
        self.addCleanup(source.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "roms"
        (self.root / "nes").mkdir(parents=True)
        (self.root / "nes/Demo.nes").write_text("synthetic nonplayable test")
        self.now = 100000.0
        self.cache = c.LibraryCache(self.base / "profile", str(self.root), lambda: self.now)
        self.result = scan_library(str(self.root))

    def test_snapshot_roundtrip_in_separate_process_survives_restart(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        code = "import sys; sys.path.insert(0, sys.argv[1]); from apeture_library.cache import LibraryCache; c=LibraryCache(sys.argv[2],sys.argv[3]); print(c.load()[0].libraries[0].games[0].title)"
        output = subprocess.check_output([sys.executable, "-c", code, str(LIB), str(self.base / "profile"), str(self.root)], text=True)
        self.assertEqual(output.strip(), "Demo")

    def test_cache_identity_does_not_depend_on_skin_or_addon_version(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        new_instance = c.LibraryCache(self.base / "profile", str(self.root))
        self.assertEqual(new_instance.path, self.cache.path)
        self.assertEqual(new_instance.load()[0], self.result)

    def test_cache_is_readable_while_media_is_offline(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        (self.root / "nes/Demo.nes").unlink()
        (self.root / "nes").rmdir()
        self.root.rmdir()
        self.assertEqual(self.cache.load()[0], self.result)

    def test_source_change_isolated_and_returning_restores_existing_snapshot(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        other = c.LibraryCache(self.base / "profile", str(self.base / "other"))
        self.assertIsNone(other.load())
        self.assertEqual(self.cache.load()[0], self.result)

    def test_fresh_cache_does_not_scan_again_across_instances(self):
        scanner = Mock(return_value=self.result)
        self.assertTrue(c.refresh(self.cache, scanner))
        for _ in range(3):
            other = c.LibraryCache(self.base / "profile", str(self.root), lambda: self.now)
            self.assertFalse(c.refresh(other, scanner))
        scanner.assert_called_once()

    def test_idle_service_due_check_never_reads_large_game_snapshot(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        with patch.object(self.cache, "load", side_effect=AssertionError("full cache read while idle")):
            self.assertFalse(self.cache.due())
            self.assertFalse(c.refresh(self.cache, Mock()))

    def test_atomic_replacement_keeps_reader_on_whole_old_snapshot(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        old = self.cache.load()[0]
        real_replace = c.os.replace
        observed = []
        def inspect_then_replace(source, target):
            observed.append(self.cache.load()[0])
            real_replace(source, target)
        with patch.object(c.os, "replace", side_effect=inspect_then_replace):
            self.cache.publish(ScanResult((), ()))
        self.assertEqual(observed, [old])
        self.assertEqual(self.cache.load()[0], ScanResult((), ()))

    def test_daily_background_refresh_not_navigation_controls_due_time(self):
        scanner = Mock(return_value=self.result)
        c.refresh(self.cache, scanner)
        self.now += c.REFRESH_SECONDS - 1
        self.assertFalse(c.refresh(self.cache, scanner))
        self.now += 1
        self.assertTrue(c.refresh(self.cache, scanner))
        self.assertEqual(scanner.call_count, 2)

    def test_failure_keeps_byte_exact_snapshot_and_persists_retry_backoff(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        before = self.cache.path.read_bytes()
        self.now += c.REFRESH_SECONDS
        scanner = Mock(side_effect=ScanError("offline"))
        with self.assertRaises(ScanError):
            c.refresh(self.cache, scanner)
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertEqual(self.cache.status(), "unavailable")
        self.assertFalse(c.refresh(self.cache, scanner))
        self.now += c.RETRY_SECONDS
        with self.assertRaises(ScanError):
            c.refresh(self.cache, scanner)

    def test_failed_manual_refresh_retries_despite_a_fresh_old_snapshot(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.cache.request_refresh()
        with self.assertRaises(ScanError):
            c.refresh(self.cache, Mock(side_effect=ScanError("offline")))
        self.assertFalse(self.cache.due())
        self.now += c.RETRY_SECONDS
        self.assertTrue(self.cache.due())
        self.assertTrue(c.refresh(self.cache, lambda: self.result))
        self.assertFalse(self.cache.due())

    def test_empty_disconnected_mount_does_not_erase_saved_library(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.now += c.REFRESH_SECONDS
        self.assertFalse(c.refresh(self.cache, lambda: ScanResult((), ())))
        self.assertEqual(self.cache.load()[0], self.result)

    def test_manual_refresh_of_empty_mount_preserves_byte_exact_index(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        before = self.cache.path.read_bytes()
        (self.root / "nes/Demo.nes").unlink()
        (self.root / "nes").rmdir()
        self.cache.request_refresh()
        self.assertFalse(c.refresh(self.cache, lambda: scan_library(str(self.root))))
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertEqual(self.cache.status(), "empty_retained")
        self.assertFalse(self.cache.due())
        self.now += c.RETRY_SECONDS
        self.assertTrue(self.cache.due())

    def test_manual_refresh_missing_source_retains_index(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        before = self.cache.path.read_bytes()
        (self.root / "nes/Demo.nes").unlink()
        (self.root / "nes").rmdir()
        self.root.rmdir()
        self.cache.request_refresh()
        with self.assertRaises(ScanError):
            c.refresh(self.cache, lambda: scan_library(str(self.root)))
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertEqual(self.cache.status(), "unavailable")

    def test_first_empty_library_and_later_empty_refresh_are_valid(self):
        empty = ScanResult((), ())
        self.assertTrue(c.refresh(self.cache, lambda: empty))
        self.cache.request_refresh()
        self.assertTrue(c.refresh(self.cache, lambda: empty))
        self.assertEqual(self.cache.load()[0], empty)

    def test_separate_confirmation_can_clear_legitimately_empty_library(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.cache.request_refresh()
        self.assertFalse(c.refresh(self.cache, lambda: ScanResult((), ())))
        completed = self.cache.load()[1]
        self.assertTrue(self.cache.confirm_empty(completed))
        self.assertEqual(self.cache.load()[0], ScanResult((), ()))
        self.assertEqual(self.cache.status(), "ready")
        self.assertTrue((self.root / "nes/Demo.nes").exists())

    def test_confirmation_cannot_clear_newer_or_busy_index(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.cache.mark_attempt("empty_retained")
        completed = self.cache.load()[1]
        with self.cache.refresh_lock():
            self.assertFalse(self.cache.confirm_empty(completed))
        self.now += 1
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.assertFalse(self.cache.confirm_empty(completed))
        self.cache.mark_attempt("ready")
        self.assertFalse(self.cache.confirm_empty(self.cache.load()[1]))
        self.assertEqual(self.cache.load()[0], self.result)

    def test_partial_removal_requires_same_source_before_and_after_scan(self):
        (self.root / "nes/Second.nes").write_text("synthetic")
        original = scan_library(str(self.root))
        identity = c.inspect_source(str(self.root))
        self.cache.publish(original, identity["identity"])
        before_bytes = self.cache.path.read_bytes()
        (self.root / "nes/Second.nes").unlink()
        partial = scan_library(str(self.root))
        cases = [(None, None), (identity, None),
                 (identity, dict(identity, session="remounted")),
                 (dict(identity, identity="replacement"), dict(identity, identity="replacement"))]
        for first, last in cases:
            self.cache.request_refresh()
            with patch.object(c, "inspect_source", side_effect=[first, last]):
                self.assertFalse(c.refresh(self.cache, lambda: partial))
            self.assertEqual(self.cache.path.read_bytes(), before_bytes)
            self.assertEqual(self.cache.status(), "source_unverified")
        self.cache.request_refresh()
        self.assertTrue(c.refresh(self.cache, lambda: partial))
        self.assertEqual(len(self.cache.load()[0].libraries[0].games), 1)

    def test_legacy_snapshot_never_adopts_unproven_deletion_identity(self):
        self.cache.publish(self.result)
        self.cache.request_refresh()
        self.assertTrue(c.refresh(self.cache, lambda: self.result))
        self.assertIsNone(self.cache.source_identity())
        before = self.cache.path.read_bytes()
        self.cache.request_refresh()
        self.assertFalse(c.refresh(self.cache, lambda: ScanResult((), ())))
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertEqual(self.cache.status(), "source_unverified")

    def test_empty_confirmation_rechecks_source_identity(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.cache.mark_attempt("empty_retained")
        before = self.cache.path.read_bytes()
        with patch.object(c, "inspect_source", return_value=None):
            self.assertFalse(self.cache.confirm_empty(self.cache.load()[1]))
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertEqual(self.cache.status(), "source_unverified")

    def test_initial_refresh_records_verified_source_identity(self):
        self.assertTrue(c.refresh(self.cache, lambda: self.result))
        self.assertEqual(self.cache.source_identity(), c.inspect_source(str(self.root))["identity"])

    def test_cancellation_never_publishes_partial_or_empty_result(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        self.cache.request_refresh()
        before = self.cache.path.read_bytes()
        with self.assertRaises(ScanCancelled):
            c.refresh(self.cache, lambda: ScanResult((), ()), cancelled=lambda: True)
        self.assertEqual(self.cache.path.read_bytes(), before)

    def test_unreadable_subfolder_keeps_previous_good_snapshot(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        bad = ScanResult((), (ScanIssue("unreadable_directory", "private"),))
        with self.assertRaises(ValueError):
            self.cache.publish(bad)
        self.assertEqual(self.cache.load()[0], self.result)

    def test_unsafe_descriptor_skipped_by_scanner_does_not_block_all_games(self):
        result = ScanResult(self.result.libraries, (ScanIssue("invalid_cue", "private"),))
        self.cache.publish(result)
        self.assertEqual(self.cache.load()[0], self.result)
        self.assertNotIn("private", self.cache.path.read_text())

    def test_replace_failure_preserves_old_snapshot_and_cleans_temp(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        before = self.cache.path.read_bytes()
        with patch.object(c.os, "replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.cache.publish(ScanResult((), ()))
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertFalse(list(self.cache.directory.glob(".snapshot-*")))

    def test_refresh_lock_excludes_second_worker_and_releases_on_exception(self):
        with self.cache.refresh_lock() as first:
            self.assertTrue(first)
            with self.cache.refresh_lock() as second:
                self.assertFalse(second)
            self.assertFalse(c.refresh(self.cache, Mock()))
        with self.cache.refresh_lock() as later:
            self.assertTrue(later)

    def test_process_crash_releases_lock_without_manual_cleanup(self):
        code = "import os,sys; sys.path.insert(0,sys.argv[1]); from apeture_library.cache import LibraryCache; c=LibraryCache(sys.argv[2],sys.argv[3]); lock=c.refresh_lock(); assert lock.__enter__(); os._exit(0)"
        subprocess.check_call([sys.executable, "-c", code, str(LIB), str(self.base / "profile"), str(self.root)])
        with self.cache.refresh_lock() as acquired:
            self.assertTrue(acquired)

    def test_corrupt_or_wrong_schema_cache_is_miss_not_execution(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        for payload in ("not json", "{}", "[]", '{"schema":99}', "null"):
            self.cache.path.write_text(payload)
            self.assertIsNone(self.cache.load())

    def test_cache_rejects_traversal_wrong_system_and_url_injection(self):
        self.cache.publish(self.result, c.inspect_source(str(self.root))["identity"])
        original = json.loads(self.cache.path.read_text())
        for path in ("nes/../../private", "snes/Game.nes", "nes/link|option", "http://host/rom", "nes/%2e%2e/outside"):
            data = json.loads(json.dumps(original))
            data["libraries"][0]["games"][0]["path"] = path
            self.cache.path.write_text(json.dumps(data))
            self.assertIsNone(self.cache.load())

    def test_credentials_are_not_serialized(self):
        from apeture_library.scanner import Game, SystemLibrary
        root = "smb://user:secret@host/share/roms"
        cache = c.LibraryCache(self.base / "profile", root)
        result = ScanResult((SystemLibrary(self.result.libraries[0].system, (Game("nes", "Demo", root + "/nes/Demo.nes"),)),), ())
        cache.publish(result)
        self.assertNotIn("secret", cache.path.read_text())
        self.assertNotIn("host", cache.path.read_text())
        self.assertEqual(cache.load()[0], result)

    def test_request_during_scan_remains_pending(self):
        def scanner():
            self.cache.request_refresh()
            return self.result
        self.assertTrue(c.refresh(self.cache, scanner))
        self.assertTrue(self.cache.due())

    def test_selected_game_validation_has_no_directory_traversal(self):
        from apeture_library.scanner import LocalFileSystem
        with patch.object(LocalFileSystem, "listdir", side_effect=AssertionError("rescan")):
            self.assertTrue(validate_launch(str(self.root / "nes/Demo.nes"), str(self.root), "nes"))

    def test_launch_rejects_replaced_parent_symlink(self):
        path = self.root / "nes/Demo.nes"
        path.unlink()
        (self.root / "nes").rmdir()
        other = self.base / "outside"
        other.mkdir()
        (other / "Demo.nes").write_text("test")
        (self.root / "nes").symlink_to(other, target_is_directory=True)
        self.assertFalse(validate_launch(str(path), str(self.root), "nes"))

    def test_launch_rechecks_cue_members_without_system_scan(self):
        folder = self.root / "psx"
        folder.mkdir()
        cue = folder / "Demo.cue"
        member = folder / "Demo.bin"
        member.write_text("test")
        cue.write_text('FILE "Demo.bin" BINARY\n')
        self.assertTrue(validate_launch(str(cue), str(self.root), "psx"))
        member.unlink()
        self.assertFalse(validate_launch(str(cue), str(self.root), "psx"))
        cue.write_text('FILE "../../private.bin" BINARY\n')
        self.assertFalse(validate_launch(str(cue), str(self.root), "psx"))


if __name__ == "__main__":
    unittest.main()

