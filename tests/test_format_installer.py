"""Run installer against disposable profiles with synthetic local inputs."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADDON_ID = "plugin.audio.aperture.format"


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="format-installer-test.")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / "Kodi profile"
        self.source = self.root / "source"
        shutil.copytree(ROOT / "format-kodi", self.source / "format-kodi",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.command("pidof", "exit 1\n")
        self.env = dict(os.environ, APERTURE_KODI_HOME=str(self.profile),
                        APERTURE_SOURCE_DIR=str(self.source),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        self.target = self.profile / "addons" / ADDON_ID

    def command(self, name, source):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + source)
        path.chmod(0o755)

    def run_installer(self, env=None, script=None):
        return subprocess.run(["sh", str(script or ROOT / "install-format.sh")], env=env or self.env,
                              text=True, capture_output=True)

    def assert_cleaned(self):
        self.assertFalse((self.profile / ".aperture-format-install.lock").exists())
        self.assertFalse(list(self.profile.glob(".aperture-format.*")))

    def existing_install(self):
        self.target.mkdir(parents=True)
        (self.target / "old-marker").write_text("existing addon")
        settings = self.profile / "userdata/addon_data" / ADDON_ID / "settings.xml"
        settings.parent.mkdir(parents=True)
        settings.write_text("saved user settings")
        return settings

    def test_installs_complete_addon_into_profile_with_spaces(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / "addon.py").is_file())
        self.assertTrue((self.target / "resources/language/resource.language.en_gb/strings.po").is_file())
        self.assert_cleaned()

    def test_reinstall_preserves_settings_and_backup_outside_addons(self):
        settings = self.existing_install()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.profile / "aperture-backups").glob("format.*/" + ADDON_ID + "/old-marker"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "existing addon")
        self.assertEqual(settings.read_text(), "saved user settings")
        self.assertEqual([p.name for p in (self.profile / "addons").iterdir()], [ADDON_ID])
        self.assert_cleaned()

    def test_missing_input_leaves_existing_install_untouched(self):
        self.existing_install()
        (self.source / "format-kodi/resources/settings.xml").unlink()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / "old-marker").read_text(), "existing addon")
        self.assertFalse((self.profile / "aperture-backups").exists())
        self.assert_cleaned()

    def test_download_failure_leaves_existing_install_untouched(self):
        self.existing_install()
        env = dict(self.env)
        env.pop("APERTURE_SOURCE_DIR")
        env["APERTURE_REF"] = "a" * 40
        script = self.root / "install-format.sh"
        shutil.copy2(ROOT / "install-format.sh", script)
        self.command("wget", "exit 1\n")
        result = self.run_installer(env, script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to fetch", result.stderr)
        self.assertTrue((self.target / "old-marker").exists())
        self.assert_cleaned()

    def test_defaults_to_adjacent_checkout_without_network(self):
        env = dict(self.env)
        env.pop("APERTURE_SOURCE_DIR")
        self.command("wget", "echo unexpected-network >&2; exit 99\n")
        self.command("curl", "echo unexpected-network >&2; exit 99\n")
        result = self.run_installer(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / "addon.py").read_bytes(), (ROOT / "format-kodi/addon.py").read_bytes())
        self.assert_cleaned()

    def test_detached_script_requires_immutable_explicit_revision(self):
        script = self.root / "install-format.sh"
        shutil.copy2(ROOT / "install-format.sh", script)
        for revision in ("", "main", "v1.0.0", "a" * 39, "a" * 41, "g" * 40):
            with self.subTest(revision=revision):
                env = dict(self.env, APERTURE_REF=revision)
                env.pop("APERTURE_SOURCE_DIR")
                result = self.run_installer(env, script)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("40-character commit SHA", result.stderr)
                self.assertFalse(self.target.exists())
                self.assert_cleaned()

    def test_invalid_manifest_never_replaces_existing_install(self):
        self.existing_install()
        (self.source / "format-kodi/addon.xml").write_text("<addon id='wrong'/>")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.target / "old-marker").exists())
        self.assert_cleaned()

    def test_invalid_python_never_replaces_existing_install(self):
        self.existing_install()
        (self.source / "format-kodi/addon.py").write_text("def broken(:\n")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.target / "old-marker").exists())
        self.assert_cleaned()

    def test_refuses_running_kodi_without_creating_profile(self):
        self.command("pidof", "echo 12345\n")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stop Kodi", result.stderr)
        self.assertFalse(self.profile.exists())

    def test_refuses_existing_lock_without_removing_it(self):
        lock = self.profile / ".aperture-format-install.lock"
        lock.mkdir(parents=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(lock.exists())
        self.assertFalse(self.target.exists())

    def test_refuses_relative_profile(self):
        env = dict(self.env, APERTURE_KODI_HOME="relative")
        result = self.run_installer(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute", result.stderr)

    def test_empty_download_is_not_installed(self):
        (self.source / "format-kodi/addon.py").write_text("")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Empty file", result.stderr)
        self.assertFalse(self.target.exists())
        self.assert_cleaned()

    def test_failed_final_move_restores_previous_install(self):
        self.existing_install()
        # Fail only the staged-directory rename, permit backup and restoration.
        real_mv = shutil.which("mv")
        self.command("mv", 'case "$1" in */.aperture-format.*) exit 1;; esac\nexec "{}" "$@"\n'.format(real_mv))
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / "old-marker").read_text(), "existing addon")
        self.assert_cleaned()


if __name__ == "__main__":
    unittest.main()
