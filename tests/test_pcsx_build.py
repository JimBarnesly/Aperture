"""Offline safety tests; no game content, source downloads or builds in this suite."""

import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "build_pcsx_core", Path(__file__).resolve().parents[1] / "tools/build_pcsx_core.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PCSXBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def archive(self, entries):
        path = self.root / "source.tar.gz"
        with tarfile.open(path, "w:gz") as output:
            for name, kind, value in entries:
                item = tarfile.TarInfo(name)
                item.type = kind
                if kind == tarfile.REGTYPE:
                    item.size = len(value)
                    output.addfile(item, io.BytesIO(value))
                else:
                    item.linkname = value
                    output.addfile(item)
        return path

    def extract(self, entries):
        archive = self.archive(entries)
        destination = self.root / "extracted"
        destination.mkdir()
        return builder.safe_extract(archive, destination)

    def test_commit_hash_and_url_are_fixed(self):
        self.assertRegex(builder.COMMIT, r"^[0-9a-f]{40}$")
        self.assertRegex(builder.SOURCE_SHA256, r"^[0-9a-f]{64}$")
        self.assertEqual(builder.SOURCE_URL,
                         "https://codeload.github.com/libretro/pcsx_rearmed/tar.gz/" + builder.COMMIT)

    def test_checksum_mismatch_is_rejected(self):
        source = self.root / "bad.tar.gz"
        source.write_bytes(b"not the pinned source")
        with self.assertRaisesRegex(builder.BuildError, "SHA256 mismatch"):
            builder.verify_archive(source)

    def test_checksum_success(self):
        source = self.root / "source.tar.gz"
        source.write_bytes(b"sample")
        with mock.patch.object(builder, "SOURCE_SHA256", builder.sha256_file(source)):
            builder.verify_archive(source)

    def test_reject_missing_and_oversized_source(self):
        with self.assertRaises(builder.BuildError):
            builder.verify_archive(self.root / "missing")
        source = self.root / "huge"
        with source.open("wb") as output:
            output.truncate(builder.MAX_ARCHIVE_BYTES + 1)
        with self.assertRaisesRegex(builder.BuildError, "size limit"):
            builder.verify_archive(source)

    def test_safe_extract_ordinary_files(self):
        path = builder.SOURCE_ROOT + "/dir/hello.c"
        source = self.extract([(path, tarfile.REGTYPE, b"int answer = 42;\n")])
        self.assertEqual((source / "dir/hello.c").read_text(), "int answer = 42;\n")

    def test_reject_traversal_and_unexpected_roots(self):
        for name in ("../escape", "/tmp/escape", builder.SOURCE_ROOT + "/../escape",
                     "other/project.c", builder.SOURCE_ROOT + "/a\\b"):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                archive = self.archive([(name, tarfile.REGTYPE, b"no")])
                with self.assertRaises(builder.BuildError):
                    builder.safe_extract(archive, Path(temporary))

    def test_reject_links_and_special_files(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=self.root) as temporary:
                archive = self.archive([(builder.SOURCE_ROOT + "/danger", kind, "/tmp/escape")])
                with self.assertRaises(builder.BuildError):
                    builder.safe_extract(archive, Path(temporary))

    def test_reject_duplicate_paths(self):
        entry = (builder.SOURCE_ROOT + "/same", tarfile.REGTYPE, b"data")
        with self.assertRaisesRegex(builder.BuildError, "Duplicate"):
            self.extract([entry, entry])

    def test_reject_nonempty_extraction_directory(self):
        archive = self.archive([(builder.SOURCE_ROOT + "/new", tarfile.REGTYPE, b"new")])
        with self.assertRaisesRegex(builder.BuildError, "empty"):
            builder.safe_extract(archive, self.root)

    def test_reject_oversized_extraction_before_writing(self):
        with mock.patch.object(builder, "MAX_EXTRACTED_BYTES", 2):
            with self.assertRaisesRegex(builder.BuildError, "size limit"):
                self.extract([(builder.SOURCE_ROOT + "/large", tarfile.REGTYPE, b"large")])
        self.assertEqual(list((self.root / "extracted").iterdir()), [])

    def test_native_architectures(self):
        for machine in ("aarch64", "arm64"):
            self.assertEqual(builder.native_arch(machine), "arm64")
        for machine in ("x86_64", "AMD64"):
            self.assertEqual(builder.native_arch(machine), "x86_64")
        for machine in ("armv7l", "i686", "ppc64"):
            with self.assertRaises(builder.BuildError):
                builder.native_arch(machine)

    def test_build_jobs_are_bounded(self):
        self.assertEqual(builder.job_count(999), 4)
        self.assertEqual(builder.job_count(1), 1)
        for jobs in (0, -1):
            with self.assertRaises(builder.BuildError):
                builder.job_count(jobs)

    def test_build_command_is_an_argument_array_with_explicit_targets(self):
        tools = {name: "/usr/bin/" + name for name in
                 ("make", "gcc", "g++", "as", "ld", "ar", "objcopy")}
        for arch, target in (("arm64", "arm64"), ("x86_64", "unix")):
            command = builder.build_command(arch, 99, tools)
            self.assertIsInstance(command, list)
            self.assertEqual(command[:4], ["/usr/bin/make", "-f", "Makefile.libretro", "-j4"])
            self.assertIn("platform=" + target, command)
            self.assertIn("HAVE_CHD=1", command)
            self.assertIn("USE_MINIZ=1", command)
            self.assertIn("HAVE_PHYSICAL_CDROM=0", command)
            self.assertIn("USE_LIBRETRO_VFS=0", command)
            self.assertFalse(any(x in command for x in ("sudo", "git", "curl", "sh", "bash")))

    def test_elf_validation_checks_architecture_and_library_type(self):
        path = self.root / "core.so"
        header = bytearray(64)
        header[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<HH", header, 16, 3, 62)
        path.write_bytes(header)
        builder.validate_elf(path, "x86_64")
        with self.assertRaises(builder.BuildError):
            builder.validate_elf(path, "arm64")
        header[4] = 1
        path.write_bytes(header)
        with self.assertRaises(builder.BuildError):
            builder.validate_elf(path, "x86_64")

    def test_output_symlink_and_world_writable_directory_are_rejected(self):
        link = self.root / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(builder.BuildError):
            builder._user_directory(link / "child")
        unsafe = self.root / "unsafe"
        unsafe.mkdir(mode=0o700)
        unsafe.chmod(0o777)
        with self.assertRaises(builder.BuildError):
            builder._user_directory(unsafe)

    def test_publish_does_not_follow_symlink(self):
        source = self.root / "source"
        source.write_bytes(b"replacement")
        untouched = self.root / "untouched"
        untouched.write_bytes(b"original")
        link = self.root / "target"
        link.symlink_to(untouched)
        with self.assertRaises(builder.BuildError):
            builder._publish_file(source, link)
        self.assertEqual(untouched.read_bytes(), b"original")

    def test_untrusted_redirect_is_rejected(self):
        for url in ("http://codeload.github.com/a", "https://example.com/a",
                    "https://codeload.github.com:444/a"):
            with self.assertRaises(builder.BuildError):
                builder._OfficialRedirects().redirect_request(None, None, 302, "", {}, url)

    @mock.patch.object(builder.os, "geteuid", return_value=0)
    def test_root_build_is_rejected_before_writing(self, _uid):
        with self.assertRaisesRegex(builder.BuildError, "normal user"):
            builder.build_core(self.root / "never-created")
        self.assertFalse((self.root / "never-created").exists())


if __name__ == "__main__":
    unittest.main()
