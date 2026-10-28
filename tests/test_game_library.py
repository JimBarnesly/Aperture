"""Synthetic filenames only: no ROM, BIOS, account, or personal fixtures."""

import os
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / "addons/plugin.games.apeture/resources/lib"
sys.path.insert(0, str(LIB))

from apeture_library.scanner import (  # noqa: E402
    LocalFileSystem, ScanCancelled, ScanError, join_path, reference_path, scan_library,
)


class MemoryVFS:
    def __init__(self, tree, contents=None):
        self.tree = tree
        self.contents = contents or {}
        self.reads = []

    def listdir(self, path):
        if path not in self.tree:
            raise OSError("Unavailable directory")
        return self.tree[path]

    def read_text(self, path, limit):
        self.reads.append(path)
        value = self.contents[path]
        if len(value.encode("utf-8")) > limit:
            raise ValueError("too long")
        return value

    def safe(self, path, boundary):
        return path == boundary or path.startswith(boundary.rstrip("/") + "/")


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def games(self, result=None):
        result = result if result is not None else scan_library(str(self.root))
        return [game for library in result.libraries for game in library.games]

    def test_unconfigured_and_empty_roots_have_no_systems(self):
        self.assertEqual(scan_library("").libraries, ())
        self.assertEqual(scan_library(str(self.root)).libraries, ())

    def test_missing_root_is_error_not_empty_library(self):
        with self.assertRaises(ScanError):
            scan_library(str(self.root / "missing"))

    def test_unknown_folders_and_root_files_are_not_guessed(self):
        self.put("unknown/Demo.nes")
        self.put("Demo.gba")
        self.put("bios/firmware.bin")
        self.assertEqual(self.games(), [])

    def test_nested_files_case_extensions_and_only_populated_systems(self):
        self.put("NES/subfolder/Second.NES")
        self.put("NES/Alpha.nes")
        self.put("gba/Note.txt")
        (self.root / "snes").mkdir()
        result = scan_library(str(self.root))
        self.assertEqual([library.system.id for library in result.libraries], ["nes"])
        self.assertEqual([game.title for game in self.games(result)], ["Alpha", "Second"])

    def test_overlapping_extensions_are_scoped_to_system_folder(self):
        self.put("megadrive/Cartridge.bin")
        self.put("atari2600/Cartridge.BIN")
        self.put("psx/UnreferencedTrack.bin")
        self.put("gbc/Monochrome.gb")
        self.assertEqual({game.system_id for game in self.games()}, {"megadrive", "atari2600", "gbc"})

    def test_folder_aliases_merge_and_system_filter_is_respected(self):
        self.put("genesis/One.md")
        self.put("megadrive/Two.gen")
        self.put("nes/Three.nes")
        result = scan_library(str(self.root), system_id="megadrive")
        self.assertEqual(len(result.libraries), 1)
        self.assertEqual(len(self.games(result)), 2)
        with self.assertRaises(ScanError):
            scan_library(str(self.root), system_id="../unknown")

    def test_hidden_entries_and_symlinks_are_not_followed(self):
        self.put("nes/.hidden.nes")
        self.put("nes/.private/Hidden.nes")
        target = self.put("unknown/Outside.nes")
        try:
            (self.root / "nes/alias.nes").symlink_to(target)
            (self.root / "nes/loop").symlink_to(self.root / "nes", target_is_directory=True)
            (self.root / "snes").symlink_to(self.root / "nes", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        self.assertEqual(self.games(), [])

    def test_playlist_groups_cues_and_tracks_without_duplicate_entries(self):
        self.put("psx/Example/discs/Disc 1.BIN")
        self.put("psx/Example/discs/Disc 2.bin")
        disc1 = self.put("psx/Example/discs/Disc 1.cue", 'FILE "Disc 1.BIN" BINARY\n TRACK 01 MODE2/2352')
        disc2 = self.put("psx/Example/discs/Disc 2.cue", 'FILE "Disc 2.bin" BINARY')
        playlist = self.put("psx/Example/Example.M3U", '\ufeff#EXTM3U\ndiscs/Disc 1.cue\ndiscs\\Disc 2.cue\ndiscs/Disc 1.cue\n')
        games = self.games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].path, playlist)
        self.assertEqual(games[0].discs, (disc1, disc2))

    def test_cue_hides_an_otherwise_supported_sidecar_iso(self):
        self.put("psx/Data.iso")
        cue = self.put("psx/Game.cue", 'FILE "Data.iso" BINARY')
        self.assertEqual([game.path for game in self.games()], [cue])

    def test_missing_playlist_member_does_not_hide_existing_disc(self):
        disc = self.put("psx/Disc.chd")
        self.put("psx/Broken.m3u", "Disc.chd\nMissing.chd")
        result = scan_library(str(self.root))
        self.assertEqual([game.path for game in self.games(result)], [disc])
        self.assertEqual(result.issues[0].code, "invalid_playlist")

    def test_invalid_cue_is_not_a_game(self):
        self.put("psx/Missing.cue", 'FILE "Missing.bin" BINARY')
        self.put("psx/Empty.cue", "REM nothing here")
        self.put("psx/Bad.cue", 'FILE "broken')
        result = scan_library(str(self.root))
        self.assertEqual(self.games(result), [])
        self.assertEqual(len(result.issues), 3)

    def test_unsafe_playlist_references_never_read_external_targets(self):
        root = "special://profile/roms"
        refs = ["../../private.chd", "/private.chd", "smb://elsewhere/private.chd",
                "C:\\private.chd", "%2e%2e/private.chd", "Disc.chd|option=value"]
        vfs = MemoryVFS({root: (["psx"], []), root + "/psx": ([], ["Disc.chd", "Unsafe.m3u"])},
                        {root + "/psx/Unsafe.m3u": "\n".join(refs)})
        result = scan_library(root, vfs)
        self.assertEqual([game.title for game in self.games(result)], ["Disc"])
        self.assertEqual(vfs.reads, [root + "/psx/Unsafe.m3u"])

    def test_unsafe_cue_references_never_read_or_hide_external_files(self):
        root = "smb://host/share"
        vfs = MemoryVFS({root: (["psx"], []), root + "/psx": ([], ["Unsafe.cue", "Good.chd"])},
                        {root + "/psx/Unsafe.cue": 'FILE "../../private.bin" BINARY'})
        result = scan_library(root, vfs)
        self.assertEqual([game.title for game in self.games(result)], ["Good"])
        self.assertEqual(vfs.reads, [root + "/psx/Unsafe.cue"])
        self.assertEqual(result.issues[0].code, "invalid_cue")

    def test_uri_paths_special_and_smb_preserve_scheme_spaces_and_unicode(self):
        for root in ("special://profile/roms", "smb://host/share/ROM collection", "nfs://host/share"):
            vfs = MemoryVFS({root: (["NES"], []), root + "/NES": (["Nested"], []),
                             root + "/NES/Nested": ([], ["Demo café.NES"])})
            self.assertEqual(self.games(scan_library(root, vfs))[0].path,
                             root + "/NES/Nested/Demo café.NES")

    def test_vfs_malformed_names_never_escape_root(self):
        root = "smb://host/share"
        vfs = MemoryVFS({root: (["nes", "../snes"], []), root + "/nes":
                        (["..", "/other", "https://host"], ["../bad.nes", "ok.nes", "%2fescape.nes",
                                                             "bad?option=.nes", "bad#fragment.nes"])})
        self.assertEqual([game.title for game in self.games(scan_library(root, vfs))], ["ok"])

    def test_unreadable_subdirectory_is_reported_without_losing_other_games(self):
        root = "smb://host/share"
        vfs = MemoryVFS({root: (["nes"], []), root + "/nes": (["Unavailable"], ["ok.nes"])})
        result = scan_library(root, vfs)
        self.assertEqual(len(self.games(result)), 1)
        self.assertEqual(result.issues[0].code, "unreadable_directory")

    def test_cancel_does_not_return_partial_results(self):
        self.put("nes/Game.nes")
        with self.assertRaises(ScanCancelled):
            scan_library(str(self.root), cancelled=lambda: True)

    def test_scan_limits_are_explicit_errors(self):
        self.put("nes/sub/deeper/Game.nes")
        with self.assertRaises(ScanError):
            scan_library(str(self.root), max_depth=1)
        with self.assertRaises(ScanError):
            scan_library(str(self.root), max_entries=1)

    def test_oversized_descriptor_is_skipped(self):
        self.put("psx/Oversized.m3u", "#" * (256 * 1024 + 1))
        result = scan_library(str(self.root))
        self.assertEqual(self.games(result), [])
        self.assertEqual(result.issues[0].code, "invalid_playlist")

    def test_nested_playlists_rejected_without_hiding_valid_discs(self):
        self.put("psx/Disc.chd")
        self.put("psx/Inner.m3u", "Disc.chd")
        self.put("psx/Outer.m3u", "Inner.m3u")
        result = scan_library(str(self.root))
        self.assertEqual([game.title for game in self.games(result)], ["Inner"])
        self.assertEqual(result.issues[0].code, "invalid_playlist")

    def test_reference_parent_may_stay_in_system_but_must_not_escape(self):
        self.assertEqual(reference_path("smb://host/share/psx/set/Game.m3u", "../Disc.chd",
                                        "smb://host/share/psx"), "smb://host/share/psx/Disc.chd")
        self.assertIsNone(reference_path("smb://host/share/psx/Game.m3u", "../Disc.chd",
                                         "smb://host/share/psx"))

    def test_windows_and_posix_join_do_not_rewrite_uri(self):
        self.assertEqual(join_path("C:\\ROMs", "nes"), "C:\\ROMs\\nes")
        self.assertEqual(join_path("/roms/", "nes"), "/roms/nes")
        self.assertEqual(join_path("special://profile/roms/", "nes"), "special://profile/roms/nes")
        with self.assertRaises(ValueError):
            join_path("/roms", "../escape")


if __name__ == "__main__":
    unittest.main()
