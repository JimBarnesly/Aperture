import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import setup_gaming as g

class SetupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
 def test_discovery_hdd_spaces_and_rom_directory(self):
  rom=self.root/'Jake HDD'/'ROMs'; (rom/'PSX').mkdir(parents=True); (rom/'nes').mkdir()
  self.assertEqual(g.discover_roots([self.root]),[rom])
 def test_discovery_does_not_follow_symlinks(self):
  rom=self.root/'outside'; (rom/'nes').mkdir(parents=True)
  mount=self.root/'mount'; mount.mkdir(); (mount/'roms').symlink_to(rom)
  self.assertEqual(g.discover_roots([mount]),[])
 def test_discovery_multiple_needs_explicit_choice(self):
  for name in ('one','two'): (self.root/name/'nes').mkdir(parents=True)
  with self.assertRaises(g.SetupError): g.select_root(None,g.discover_roots([self.root]),False)
 def test_root_rejects_relative_empty_and_symlink(self):
  for value in ('relative',str(self.root)):
   with self.assertRaises(g.SetupError): g.select_root(value,[],False)
  (self.root/'nes').mkdir(); (self.root/'alias').symlink_to(self.root)
  with self.assertRaises(g.SetupError): g.select_root(str(self.root/'alias'),[],False)
 def test_core_manifests_use_default_controller_and_local_core(self):
  lib=self.root/'core.so'; lib.write_bytes(b'fake-test-core')
  for core in g.CORES:
   target=self.root/core.key; g.make_core_addon(core,lib,target)
   addon=ET.parse(target/'addon.xml').getroot()
   self.assertEqual(addon.get('id'),g.PREFIX+core.key)
   ext=addon.find("extension[@point='kodi.gameclient']")
   self.assertEqual(ext.get('library_linux'),core.library)
   self.assertEqual(ext.findtext('supports_vfs'),'false')
   self.assertEqual((target/core.library).read_bytes(),b'fake-test-core')
   mapping=ET.parse(target/'resources/buttonmap.xml').find('controller')
   self.assertEqual(mapping.get('id'),'game.controller.default')
   self.assertEqual(mapping.find("feature[@name='a']").get('mapto'),'RETRO_DEVICE_ID_JOYPAD_B')
   if core.key=='pcsxrearmed':
    self.assertEqual(mapping.get('type'),'RETRO_DEVICE_ANALOG'); self.assertEqual(mapping.get('subclass'),'1')
   else: self.assertEqual(mapping.get('type'),'RETRO_DEVICE_JOYPAD')
 def test_atomic_install_backups_outside_addons(self):
  home=self.root/'kodi'; (home/'addons'/'old').mkdir(parents=True); (home/'addons'/'old'/'file').write_text('old')
  stage=self.root/'stage'; (stage/'old').mkdir(parents=True); (stage/'old'/'file').write_text('new')
  backup=g.atomic_install(stage,home)
  self.assertEqual((home/'addons'/'old'/'file').read_text(),'new'); self.assertEqual((backup/'old'/'file').read_text(),'old')
 def test_atomic_install_rolls_back_on_later_bad_target(self):
  home=self.root/'kodi'; (home/'addons'/'a').mkdir(parents=True); (home/'addons'/'a'/'file').write_text('old')
  (home/'addons'/'z').symlink_to(self.root/'somewhere')
  stage=self.root/'stage'; (stage/'a').mkdir(parents=True); (stage/'a'/'file').write_text('new'); (stage/'z').mkdir()
  with self.assertRaises(g.SetupError): g.atomic_install(stage,home)
  self.assertEqual((home/'addons'/'a'/'file').read_text(),'old')
 def test_rom_setting_preserves_unrelated_settings(self):
  settings=self.root/'userdata/addon_data'/g.LIBRARY_ID/'settings.xml'; settings.parent.mkdir(parents=True)
  settings.write_text('<settings version="2"><setting id="other">keep</setting></settings>')
  g.set_rom_root(self.root,Path('/media/HDD & more/roms'))
  tree=ET.parse(settings)
  self.assertEqual(tree.find("setting[@id='other']").text,'keep')
  self.assertEqual(tree.find("setting[@id='rom_root']").text,'/media/HDD & more/roms')
  self.assertEqual(len(list(settings.parent.glob('settings.xml.before-*'))),1)
 def test_bios_detection_size_and_destination(self):
  rom=self.root/'roms'; (rom/'bios').mkdir(parents=True)
  bios=rom/'bios'/'SCPH5501.BIN'; bios.write_bytes(bytes(524288))
  (rom/'bios'/'scph5502.bin').write_bytes(b'wrong')
  self.assertEqual(g.bios_status(rom),[bios])
  home=self.root/'kodi'; self.assertEqual(g.install_bios([bios],home),['scph5501.bin'])
  destination=home/'userdata/addon_data'/ (g.PREFIX+'pcsxrearmed')/'resources/system/scph5501.bin'
  destination.write_bytes(b'keep existing'); g.install_bios([bios],home)
  self.assertEqual(destination.read_bytes(),b'keep existing')
 def test_live_kodi_refused(self):
  with patch.object(g,'kodi_running',return_value=True):
   with self.assertRaises(g.SetupError): g.require_stopped()
 def test_package_candidate_missing(self):
  for output in ('','pkg:\n  Candidate: (none)'):
   with patch.object(g,'command_output',return_value=output): self.assertFalse(g.package_candidate('pkg'))
  with patch.object(g,'command_output',return_value='pkg:\n  Candidate: 1.2.3'):
   self.assertTrue(g.package_candidate('pkg'))

class SetupSafetyRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def staged(self, name="example", data="new"):
        stage = self.root / "stage"
        (stage / name).mkdir(parents=True)
        (stage / name / "marker").write_text(data)
        return stage

    def settings_path(self, home=None):
        return (home or self.root) / "userdata/addon_data" / g.LIBRARY_ID / "settings.xml"

    def test_addons_symlink_parent_cannot_redirect_install(self):
        outside = self.root / "outside"
        outside.mkdir()
        home = self.root / "home"
        home.mkdir()
        (home / "addons").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(g.SetupError):
            g.atomic_install(self.staged(), home)
        self.assertEqual(list(outside.iterdir()), [])

    def test_profile_ancestor_symlink_and_parent_traversal_are_rejected(self):
        actual = self.root / "actual"
        actual.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(g.SetupError):
            g.safe_profile_path(alias / "home", alias / "home/addons")
        home = self.root / "home"
        with self.assertRaises(g.SetupError):
            g.safe_profile_path(home, home / "../outside")

    def test_backup_symlink_parent_cannot_move_old_addon_outside_profile(self):
        outside = self.root / "outside"
        outside.mkdir()
        home = self.root / "home"
        (home / "addons/example").mkdir(parents=True)
        (home / "addons/example/marker").write_text("old")
        (home / "aperture-backups").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(g.SetupError):
            g.atomic_install(self.staged(), home)
        self.assertEqual((home / "addons/example/marker").read_text(), "old")
        self.assertEqual(list(outside.iterdir()), [])

    def test_atomic_install_restores_first_addon_if_its_replacement_fails(self):
        home = self.root / "home"
        (home / "addons/example").mkdir(parents=True)
        (home / "addons/example/marker").write_text("old")
        stage = self.staged()
        original = Path.rename

        def fail_staged_source(path, target):
            if path == stage / "example":
                raise OSError("injected destination failure")
            return original(path, target)

        with patch.object(Path, "rename", fail_staged_source):
            with self.assertRaises(OSError):
                g.atomic_install(stage, home)
        self.assertEqual((home / "addons/example/marker").read_text(), "old")

    def test_atomic_install_removes_new_addon_on_later_failure(self):
        home = self.root / "home"
        (home / "addons").mkdir(parents=True)
        (home / "addons/z").symlink_to(self.root / "missing")
        stage = self.staged("a")
        (stage / "z").mkdir()
        with self.assertRaises(g.SetupError):
            g.atomic_install(stage, home)
        self.assertFalse((home / "addons/a").exists())
        self.assertTrue((home / "addons/z").is_symlink())

    def test_combined_transaction_rolls_back_addons_settings_and_new_bios(self):
        home = self.root / "home"
        addon = home / "addons/example"
        addon.mkdir(parents=True)
        (addon / "marker").write_text("old addon")
        settings = self.settings_path(home)
        settings.parent.mkdir(parents=True)
        settings.write_text("old settings")
        stage = self.staged("example")
        source_settings = stage / "settings.xml"
        source_settings.write_text("new settings")
        source_bios = stage / "scph5501.bin"
        source_bios.write_bytes(b"fixture BIOS")
        target_bios = home / "userdata/addon_data/core/resources/system/scph5501.bin"
        items = [(stage / "example", addon), (source_bios, target_bios), (source_settings, settings)]
        original = Path.rename

        def fail_settings(path, target):
            if path == source_settings:
                raise OSError("injected settings commit failure")
            return original(path, target)

        with patch.object(Path, "rename", fail_settings):
            with self.assertRaises(OSError):
                g.atomic_apply(items, home)
        self.assertEqual((addon / "marker").read_text(), "old addon")
        self.assertEqual(settings.read_text(), "old settings")
        self.assertFalse(target_bios.exists())

    def test_atomic_apply_rejects_duplicate_targets_before_replacing_anything(self):
        home = self.root / "home"
        home.mkdir()
        target = home / "settings.xml"
        target.write_text("original")
        source1, source2 = self.root / "new1", self.root / "new2"
        source1.write_text("first")
        source2.write_text("second")
        with self.assertRaises(g.SetupError):
            g.atomic_apply([(source1, target), (source2, target)], home)
        self.assertEqual(target.read_text(), "original")
        self.assertTrue(source1.is_file())
        self.assertTrue(source2.is_file())

    def test_settings_symlink_parents_are_rejected(self):
        for relative in ("userdata", "userdata/addon_data", "userdata/addon_data/" + g.LIBRARY_ID):
            with self.subTest(parent=relative), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                home = Path(temporary) / "home"
                home.mkdir()
                outside = Path(temporary) / "outside"
                outside.mkdir()
                link = home / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(g.SetupError):
                    g.set_rom_root(home, Path("/mounted/roms"))
                self.assertEqual(list(outside.iterdir()), [])

    def test_existing_predictable_settings_temp_symlink_is_never_followed(self):
        settings = self.settings_path()
        settings.parent.mkdir(parents=True)
        outside = self.root / "important"
        outside.write_text("must stay unchanged")
        settings.with_name("settings.xml.aperture-new").symlink_to(outside)
        try:
            g.set_rom_root(self.root, Path("/mounted/roms"))
        except g.SetupError:
            pass
        self.assertEqual(outside.read_text(), "must stay unchanged")

    def test_settings_invalid_xml_or_root_never_changes_original(self):
        path = self.settings_path()
        path.parent.mkdir(parents=True)
        for text in ("<settings", "<not-settings/>"):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises((g.SetupError, ET.ParseError)):
                    g.set_rom_root(self.root, Path("/mounted/roms"))
                self.assertEqual(path.read_text(), text)

    def test_legacy_settings_are_preserved_or_safely_rejected(self):
        path = self.settings_path()
        path.parent.mkdir(parents=True)
        original = '<settings><setting id="rom_root" value="OLD"/><setting id="other" value="keep"/></settings>'
        path.write_text(original)
        try:
            g.set_rom_root(self.root, Path("/mounted/new"))
        except g.SetupError:
            self.assertEqual(path.read_text(), original)
        else:
            tree = ET.parse(path)
            root = tree.find("setting[@id='rom_root']")
            other = tree.find("setting[@id='other']")
            self.assertEqual(root.get("value", root.text), "/mounted/new")
            self.assertEqual(other.get("value", other.text), "keep")

    def test_duplicate_rom_root_is_normalized_or_rejected_before_writing(self):
        path = self.settings_path()
        path.parent.mkdir(parents=True)
        original = '<settings version="2"><setting id="rom_root">OLD1</setting><setting id="rom_root">OLD2</setting></settings>'
        path.write_text(original)
        try:
            g.set_rom_root(self.root, Path("/mounted/new"))
        except g.SetupError:
            self.assertEqual(path.read_text(), original)
        else:
            entries = ET.parse(path).findall("setting[@id='rom_root']")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].text, "/mounted/new")

    def test_bios_symlink_parents_are_rejected(self):
        prefix = "userdata/addon_data/" + g.PREFIX + "pcsxrearmed"
        for relative in ("userdata", "userdata/addon_data", prefix, prefix + "/resources"):
            with self.subTest(parent=relative), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                base = Path(temporary)
                home = base / "home"
                home.mkdir()
                outside = base / "outside"
                outside.mkdir()
                link = home / relative
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                source = base / "scph5501.bin"
                source.write_bytes(bytes(524288))
                with self.assertRaises(g.SetupError):
                    g.install_bios([source], home)
                self.assertEqual(list(outside.iterdir()), [])

    def test_existing_bios_file_symlink_is_not_overwritten(self):
        home = self.root / "home"
        folder = home / "userdata/addon_data" / (g.PREFIX + "pcsxrearmed") / "resources/system"
        folder.mkdir(parents=True)
        source = self.root / "scph5501.bin"
        source.write_bytes(bytes(524288))
        outside = self.root / "important"
        outside.write_bytes(b"unchanged")
        (folder / source.name).symlink_to(outside)
        try:
            g.install_bios([source], home)
        except g.SetupError:
            pass
        self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_bios_detection_rejects_symlink_files_and_folders(self):
        rom = self.root / "roms"
        (rom / "bios").mkdir(parents=True)
        source = self.root / "scph5501.bin"
        source.write_bytes(bytes(524288))
        (rom / "bios/scph5501.bin").symlink_to(source)
        self.assertEqual(g.bios_status(rom), [])
        (rom / "bios/scph5501.bin").unlink()
        (rom / "bios").rmdir()
        (rom / "bios").symlink_to(self.root, target_is_directory=True)
        self.assertEqual(g.bios_status(rom), [])

    def test_additional_officially_supported_psx_bios_names_are_detected(self):
        rom = self.root / "roms"
        folder = rom / "bios"
        folder.mkdir(parents=True)
        for name in ("scph101.bin", "scph7001.bin"):
            (folder / name).write_bytes(bytes(524288))
        self.assertEqual({path.name for path in g.bios_status(rom)}, {"scph101.bin", "scph7001.bin"})

    def test_psx_wrapper_has_all_inputs_and_exact_dualshock_subclass(self):
        core = next(core for core in g.CORES if core.key == "pcsxrearmed")
        library = self.root / "pcsx_rearmed_libretro.so"
        library.write_bytes(b"synthetic fixture, not an executable")
        target = self.root / "addon"
        g.make_core_addon(core, library, target)
        mapping = ET.parse(target / "resources/buttonmap.xml").find("controller")
        features = {entry.get("name"): entry.get("mapto") for entry in mapping}
        self.assertEqual(mapping.get("type"), "RETRO_DEVICE_ANALOG")
        self.assertEqual(mapping.get("subclass"), "1")
        self.assertEqual(len(features), 20)
        for key, value in {"back": "RETRO_DEVICE_ID_JOYPAD_SELECT",
                           "leftthumb": "RETRO_DEVICE_ID_JOYPAD_L3",
                           "rightthumb": "RETRO_DEVICE_ID_JOYPAD_R3",
                           "leftstick": "RETRO_DEVICE_INDEX_ANALOG_LEFT",
                           "rightstick": "RETRO_DEVICE_INDEX_ANALOG_RIGHT",
                           "leftmotor": "RETRO_RUMBLE_STRONG",
                           "rightmotor": "RETRO_RUMBLE_WEAK"}.items():
            self.assertEqual(features[key], value)
        ports = ET.parse(target / "resources/topology.xml").findall("port")
        self.assertEqual([p.get("id") for p in ports], ["1", "2"])
        self.assertTrue(all(p.find("accepts").get("controller") == "game.controller.default" for p in ports))

    def test_invalid_settings_do_not_commit_any_addons(self):
        home = self.root / "home"
        old = home / "addons" / g.LIBRARY_ID
        old.mkdir(parents=True)
        (old / "marker").write_text("previous installation")
        settings = self.settings_path(home)
        settings.parent.mkdir(parents=True)
        settings.write_text("<wrong-root/>")
        roms = self.root / "roms"
        (roms / "nes").mkdir(parents=True)
        fake_core = self.root / "core.so"
        fake_core.write_bytes(b"synthetic core")

        def output(args):
            return "21.2-1" if args[0] == "dpkg-query" else "amd64"

        with patch.object(g, "command_output", side_effect=output), \
                patch.object(g, "package_candidate", return_value=True), \
                patch.object(g, "installed_core", return_value=fake_core), \
                patch.object(g, "kodi_running", return_value=False), \
                patch.object(g, "run"), patch.object(g.os, "geteuid", return_value=1000):
            with self.assertRaises(g.SetupError):
                g.main(["--install", "--skip-psx-build", "--rom-root", str(roms), "--kodi-home", str(home)])
        self.assertEqual((old / "marker").read_text(), "previous installation")
        self.assertEqual([p.name for p in (home / "addons").iterdir()], [g.LIBRARY_ID])
        self.assertEqual(settings.read_text(), "<wrong-root/>")


if __name__=='__main__': unittest.main()
