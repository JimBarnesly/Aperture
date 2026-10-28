import importlib.util
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
