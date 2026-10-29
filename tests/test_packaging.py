import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("apeture_build", Path(__file__).resolve().parents[1] / "tools/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PackagingTests(unittest.TestCase):
    def test_install_guide_uses_actual_package_names_and_distinguishes_outer_zip(self):
        packages = [
            {"addon": "plugin.games.apeture", "file": "plugin.games.apeture-7.2.1.zip"},
            {"addon": "script.apeture.music", "file": "script.apeture.music-4.3.2.zip"},
            {"addon": "skin.apeture", "file": "skin.apeture-9.8.7.zip"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            build.write_install_guide(packages, destination)
            guide = (destination / "README-INSTALL.txt").read_text(encoding="utf-8")
            for item in packages:
                self.assertIn(item["file"], guide)
            self.assertIn("OUTER wrapper", guide)
            self.assertIn("INNER add-on ZIPs", guide)
            self.assertIn("scanning it into the library", guide)
            self.assertIn("HDMI-CEC", guide)
            self.assertIn("NOT one-click SD provisioning", guide)
            self.assertEqual(sorted(p.name for p in (destination / "installer").iterdir()),
                             ["Prepare-Aperture.ps1", "README.md"])
            self.assertEqual((destination / "installer/Prepare-Aperture.ps1").read_bytes(),
                             (build.ROOT / "installer/Prepare-Aperture.ps1").read_bytes())
            self.assertEqual((destination / "INSTALL_PI5.md").read_bytes(),
                             (build.ROOT / "docs/INSTALL_PI5.md").read_bytes())

    def test_incomplete_install_kit_is_not_described_as_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build.write_install_guide([], Path(directory))
            self.assertFalse((Path(directory) / "README-INSTALL.txt").exists())

    def test_zip_is_deterministic_and_uses_addon_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "addon.xml").write_text('<addon id="plugin.games.test" version="0.1.0"/>')
            (source / "main.py").write_text("print('test')\n")
            (source / "__pycache__").mkdir()
            (source / "__pycache__/junk.pyc").write_bytes(b"no")
            (source / ".private").mkdir()
            (source / ".private/secret.txt").write_text("not a package resource")
            first = build.package_addon(source, root / "dist")
            second = build.package_addon(source, root / "dist")
            self.assertEqual(first["sha256"], second["sha256"])
            with zipfile.ZipFile(root / "dist" / first["file"]) as archive:
                self.assertEqual(archive.namelist(), ["plugin.games.test/addon.xml", "plugin.games.test/main.py"])

    def test_kodi_prerelease_version_has_exact_package_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "addon.xml").write_text('<addon id="skin.apeture" version="1.0.0~rc1"/>')
            package = build.package_addon(source, root / "dist")
            self.assertEqual(package["file"], "skin.apeture-1.0.0~rc1.zip")
            self.assertEqual(package["version"], "1.0.0~rc1")

    def test_materialized_content_verification_rejects_stale_inputs_and_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("addons/skin.apeture/addon.xml", "assets/art.png", "tools/build.py",
                         "tools/vendor_estuary.py", "tools/vendor_estuary_assets.py",
                         "docs/UPSTREAM.md", "docs/DESIGN.md"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original")
            source = root / "build/skin.apeture"
            source.mkdir(parents=True)
            (source / "addon.xml").write_text("original output")
            marker = source / "APETURE_BUILD.json"
            def stamp():
                marker.write_text(json.dumps({
                    "inputs_sha256": build.skin_input_fingerprints(root),
                    "files_sha256": build.file_fingerprints(source, exclude=("APETURE_BUILD.json",)),
                }))
            stamp()
            build.verify_materialized_skin(source, root)
            for relative in ("addons/skin.apeture/addon.xml", "assets/art.png",
                             "tools/vendor_estuary_assets.py", "docs/UPSTREAM.md"):
                path = root / relative
                path.write_text("changed")
                with self.assertRaisesRegex(ValueError, "without --skip-vendor"):
                    build.verify_materialized_skin(source, root)
                path.write_text("original")
                build.verify_materialized_skin(source, root)
            added = root / "addons/skin.apeture/new.xml"
            added.write_text("new")
            with self.assertRaises(ValueError):
                build.verify_materialized_skin(source, root)
            added.unlink()
            (source / "addon.xml").write_text("modified output")
            with self.assertRaisesRegex(ValueError, "assembled skin files changed"):
                build.verify_materialized_skin(source, root)
            stamp()
            (source / "addon.xml").unlink()
            with self.assertRaises(ValueError):
                build.verify_materialized_skin(source, root)
            marker.write_text('{}')
            with self.assertRaises(ValueError):
                build.verify_materialized_skin(source, root)

    def test_materialization_fingerprints_reject_symlink_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                build.file_fingerprints(root)

    def test_completed_kit_removes_only_obsolete_matching_addon_zips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("skin.apeture-0.3.0.zip", "skin.apeture-1.0.0~rc1.zip",
                         "other-addon.zip", "notes.txt"):
                (root / name).write_text("fixture")
            build.remove_obsolete_packages([
                {"addon": "skin.apeture", "file": "skin.apeture-1.0.0~rc1.zip"}], root)
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["notes.txt", "other-addon.zip", "skin.apeture-1.0.0~rc1.zip"])

    def test_unsafe_identifier_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for identifier in ("../escape", "..", ".", "plugin..test", ".plugin", "plugin."):
                with self.subTest(identifier=identifier):
                    (root / "addon.xml").write_text(f'<addon id="{identifier}" version="1"/>')
                    with self.assertRaises(ValueError):
                        build.package_addon(root, root / "dist")


if __name__ == "__main__":
    unittest.main()
