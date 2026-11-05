"""Source proof and mount topology regressions, using synthetic mount tables."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import mock_open, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "games-kodi/resources/lib"))
from apeture_library.source import inspect_source

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "roms"
        self.root.mkdir()
        stat = self.root.stat()
        self.device = "{}:{}".format(os.major(stat.st_dev), os.minor(stat.st_dev))

    def table(self, mount_id="10", extra=""):
        return f"{mount_id} 1 {self.device} / / rw - ext4 /dev/example rw\n" + extra

    def inspect(self, table):
        with patch("builtins.open", mock_open(read_data=table)):
            return inspect_source(str(self.root))

    def test_same_mount_identity_but_new_mount_session_is_detectable(self):
        one, two = self.inspect(self.table()), self.inspect(self.table("20"))
        self.assertEqual(one["identity"], two["identity"])
        self.assertNotEqual(one["session"], two["session"])

    def test_nested_mount_disappearance_changes_identity(self):
        child = f"11 10 9:9 / {self.root}/psx rw - ext4 /dev/second rw\n"
        self.assertNotEqual(self.inspect(self.table(extra=child))["identity"], self.inspect(self.table())["identity"])

    def test_mounted_network_and_unknown_filesystems_are_not_proof(self):
        for filesystem in ("nfs", "cifs", "fuseblk", "fuse.sshfs", "overlay", "unknown"):
            self.assertIsNone(self.inspect(self.table().replace(" ext4 ", " " + filesystem + " ")))

    def test_mount_replacement_changes_identity(self):
        first = self.inspect(self.table())
        second = self.inspect(self.table().replace("/dev/example", "/dev/replacement"))
        self.assertNotEqual(first["identity"], second["identity"])

    def test_replaced_directory_changes_identity(self):
        first = self.inspect(self.table())
        self.root.rename(self.root.with_name("old"))
        self.root.mkdir()
        self.assertNotEqual(first["identity"], self.inspect(self.table())["identity"])

    def test_missing_directory_and_unavailable_mount_table_are_not_proof(self):
        self.root.rmdir()
        self.assertIsNone(self.inspect(self.table()))
        self.root.mkdir()
        with patch("builtins.open", side_effect=OSError("unavailable")):
            self.assertIsNone(inspect_source(str(self.root)))
        self.assertIsNone(self.inspect("not a mount table"))
        self.assertIsNone(inspect_source("smb://host/share"))
        self.assertIsNone(inspect_source("nfs://host/share"))
