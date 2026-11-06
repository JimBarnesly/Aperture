"""Adversarial adapter acceptance. Synthetic files and mocked Kodi, not GUI QA."""
import subprocess
import selectors
import sys
import unittest
from unittest.mock import patch
import test_game_library_kodi as adapter
from apeture_library import cache as c
from apeture_library.scanner import scan_library


class ConfirmationAcceptance(unittest.TestCase):
    setUp = adapter.AdapterTests.setUp
    put = adapter.AdapterTests.put
    seed_cache = adapter.AdapterTests.seed_cache
    run_plugin = adapter.AdapterTests.run_plugin

    def prepared(self):
        self.media = self.put("nes/Demo.nes", "synthetic nonplayable fixture")
        self.cache = self.seed_cache()
        self.cache.mark_attempt("empty_retained")
        self.before = self.cache.path.read_bytes()
        self.dialog.yesno.return_value = True

    def invoke(self):
        with patch.object(self.module, "scan_library", side_effect=AssertionError("foreground scan")):
            self.run_plugin("action=confirm_empty", warm=False)
        self.assertEqual(self.media.read_text(), "synthetic nonplayable fixture")
        self.player.play.assert_not_called()
        self.assertEqual(self.plugin_api.endOfDirectory.call_count, 1)

    def assert_preserved(self):
        self.assertEqual(self.cache.path.read_bytes(), self.before)

    def test_cancel_repeatedly_preserves_snapshot_and_dismisses(self):
        self.prepared()
        self.dialog.yesno.return_value = False
        for _ in range(3):
            self.plugin_api.reset_mock()
            self.invoke()
            self.assert_preserved()
        self.dialog.ok.assert_not_called()

    def test_dialog_exception_preserves_snapshot_and_completes_callback(self):
        self.prepared()
        self.dialog.yesno.side_effect = RuntimeError("dialog interrupted")
        self.invoke()
        self.assert_preserved()
        self.plugin_api.endOfDirectory.assert_called_once_with(42, succeeded=False, cacheToDisc=False)

    def test_source_disappears_while_confirmation_open(self):
        self.prepared()
        with patch.object(c, "inspect_source", return_value=None):
            self.invoke()
        self.assert_preserved()
        self.assertEqual(self.cache.status(), "source_unverified")

    def test_source_replacement_while_confirmation_open(self):
        self.prepared()
        with patch.object(c, "inspect_source", return_value={"identity": "b" * 64, "session": "replacement"}):
            self.invoke()
        self.assert_preserved()

    def test_newer_worker_snapshot_wins_over_open_dialog(self):
        self.prepared()
        def answer(*args, **kwargs):
            self.put("nes/New.nes", "synthetic")
            self.cache.now = lambda: self.cache.load()[1] + 10
            self.cache.publish(scan_library(str(self.root)), "a" * 64)
            self.before = self.cache.path.read_bytes()
            return True
        self.dialog.yesno.side_effect = answer
        self.invoke()
        self.assert_preserved()
        self.assertEqual(len(self.cache.load()[0].libraries[0].games), 2)

    def test_worker_status_change_rejects_old_confirmation(self):
        self.prepared()
        def answer(*args, **kwargs):
            self.cache.mark_attempt("indexing")
            return True
        self.dialog.yesno.side_effect = answer
        self.invoke()
        self.assert_preserved()

    def test_actual_cross_process_lock_blocks_confirmation(self):
        self.prepared()
        code = "import sys; sys.path.insert(0,sys.argv[1]); from apeture_library.cache import LibraryCache; c=LibraryCache(sys.argv[2],sys.argv[3]);\nwith c.refresh_lock() as ok:\n print(ok, flush=True); sys.stdin.readline()"
        process = subprocess.Popen([sys.executable, "-c", code, str(c.Path(c.__file__).parents[1]), str(self.profile), str(self.root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(ready.select(timeout=10), "lock-holder did not become ready")
                self.assertEqual(process.stdout.readline().strip(), "True")
            self.invoke()
            self.assert_preserved()
        finally:
            try:
                process.communicate("release\n", timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
                self.fail("lock-holder did not exit after release")
        self.assertEqual(process.returncode, 0)

    def test_success_then_repeated_action_does_not_prompt_again(self):
        self.prepared()
        self.invoke()
        self.assertFalse(self.cache.load()[0].libraries)
        self.dialog.yesno.reset_mock()
        self.plugin_api.reset_mock()
        self.invoke()
        self.dialog.yesno.assert_not_called()

    def test_pending_refresh_survives_explicit_cache_clear(self):
        self.prepared()
        self.cache.request_refresh()
        request = self.cache.request_path.read_bytes()
        self.invoke()
        self.assertEqual(self.cache.request_path.read_bytes(), request)
        self.assertTrue(self.cache.due())

    def test_atomic_replace_failure_keeps_old_cache(self):
        self.prepared()
        with patch.object(c.os, "replace", side_effect=OSError("synthetic disk full")):
            self.invoke()
        self.assert_preserved()
        self.assertEqual(list(self.cache.directory.glob(".snapshot-*")), [])

    def test_legacy_snapshot_without_identity_cannot_be_cleared(self):
        self.prepared()
        self.cache.publish(scan_library(str(self.root)))
        self.before = self.cache.path.read_bytes()
        self.invoke()
        self.assert_preserved()

    def test_action_without_retained_empty_state_never_prompts(self):
        self.prepared()
        self.cache.mark_attempt("ready")
        self.invoke()
        self.assert_preserved()
        self.dialog.yesno.assert_not_called()


if __name__ == "__main__":
    unittest.main()
