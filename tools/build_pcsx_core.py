#!/usr/bin/env python3
"""Build one pinned official PCSX ReARMed libretro core, without installing it.

Requires Linux, Python 3.9+, make, GCC/G++ and binutils. Compression code is bundled.
No root, package-manager, Git clone, submodule or third-party build script is used.
The fixed upstream Makefile runs in a fresh user-owned directory. Our subprocess
calls never use a shell; make itself necessarily runs its upstream build recipes.

The output includes the complete pinned source archive and upstream notices.
Keep those files with the binary when redistributing it under its licenses.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request


COMMIT = "7b0e8f8fadfbce3d170d195b9d9eecaabfa08c8e"
SOURCE_URL = "https://codeload.github.com/libretro/pcsx_rearmed/tar.gz/" + COMMIT
SOURCE_SHA256 = "4f47bd98bac6cdf62dd4f7a56069b0b0d9999aa6800e636334d1788c5cf38ccf"
SOURCE_ROOT = "pcsx_rearmed-" + COMMIT
SOURCE_FILENAME = SOURCE_ROOT + ".tar.gz"
CORE_FILENAME = "pcsx_rearmed_libretro.so"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXTRACTED_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000
MAX_JOBS = 4
BUILD_TIMEOUT = 1800
REQUIRED_SYMBOLS = (
    "retro_api_version", "retro_get_system_info", "retro_init", "retro_deinit",
    "retro_load_game", "retro_unload_game", "retro_run",
    "retro_set_environment", "retro_set_controller_port_device",
)


class BuildError(RuntimeError):
    """A recoverable build, dependency, platform or source-validation failure."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise BuildError("Source archive is missing, not a file, or exceeds the size limit")
    actual = sha256_file(path)
    if actual != SOURCE_SHA256:
        raise BuildError("Source SHA256 mismatch: expected %s, got %s" % (SOURCE_SHA256, actual))


class _OfficialRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        if url.scheme != "https" or url.hostname != "codeload.github.com" or url.port not in (None, 443):
            raise BuildError("Refusing a source download redirect outside official HTTPS codeload.github.com")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_archive(destination):
    """Download only the pinned official URL, then verify its committed checksum."""
    destination = Path(destination)
    opener = urllib.request.build_opener(_OfficialRedirects())
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Apeture-PCSX-builder/1"})
    try:
        with opener.open(request, timeout=60) as response, destination.open("xb") as target:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise BuildError("Source download exceeds size limit")
            size = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > MAX_ARCHIVE_BYTES:
                    raise BuildError("Source download exceeds size limit")
                target.write(block)
        verify_archive(destination)
    except (OSError, ValueError) as exc:
        raise BuildError("Cannot download the pinned official source: %s" % exc) from exc


def safe_extract(archive, destination):
    """Extract only ordinary files/directories from a single expected root.

    Reject links, devices, traversal, duplicates and size bombs before writing.
    The destination must be an empty real directory owned by this process's user.
    """
    destination = Path(destination)
    if destination.is_symlink() or not destination.is_dir() or any(destination.iterdir()):
        raise BuildError("Source extraction requires an empty, real directory")
    if destination.stat().st_uid != os.geteuid():
        raise BuildError("Source extraction directory must be owned by the current user")
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise BuildError("Source archive contains too many entries")
            seen = set()
            total = 0
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                        or not path.parts or path.parts[0] != SOURCE_ROOT):
                    raise BuildError("Unsafe source archive path: %s" % member.name)
                if not (member.isfile() or member.isdir()):
                    raise BuildError("Source archive links and special files are not permitted")
                if str(path) in seen:
                    raise BuildError("Duplicate source archive path: %s" % member.name)
                seen.add(str(path))
                total += member.size
                if member.size < 0 or total > MAX_EXTRACTED_BYTES:
                    raise BuildError("Source archive exceeds extracted size limit")
            for member in members:
                target = destination.joinpath(*PurePosixPath(member.name).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o700)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    source = bundle.extractfile(member)
                    if source is None:
                        raise BuildError("Cannot read source archive entry")
                    with source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o700 if member.mode & 0o111 else 0o600)
    except (OSError, tarfile.TarError) as exc:
        raise BuildError("Cannot safely extract source: %s" % exc) from exc
    return destination / SOURCE_ROOT


def native_arch(machine=None):
    value = (machine or platform.machine()).lower()
    if value in ("aarch64", "arm64"):
        return "arm64"
    if value in ("x86_64", "amd64"):
        return "x86_64"
    raise BuildError("Unsupported native architecture %r; use 64-bit ARM or x86 Linux" % value)


def job_count(requested=None):
    if requested is not None and requested < 1:
        raise BuildError("Jobs must be a positive integer")
    return min(MAX_JOBS, requested if requested is not None else (os.cpu_count() or 1))


def build_command(arch, jobs, tools):
    if arch not in ("arm64", "x86_64"):
        raise BuildError("Unsupported build architecture")
    return [
        tools["make"], "-f", "Makefile.libretro", "-j%d" % job_count(jobs),
        "platform=" + ("arm64" if arch == "arm64" else "unix"),
        "HAVE_CHD=1", "USE_MINIZ=1", "HAVE_PHYSICAL_CDROM=0", "USE_LIBRETRO_VFS=0",
        "GIT_VERSION= " + COMMIT[:7],
        "CC=" + tools["gcc"], "CXX=" + tools["g++"], "AS=" + tools["as"],
        "LD=" + tools["ld"], "AR=" + tools["ar"], "OBJCOPY=" + tools["objcopy"],
    ]


def validate_elf(path, arch):
    with Path(path).open("rb") as binary:
        header = binary.read(64)
    if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01":
        raise BuildError("Built core is not a 64-bit little-endian ELF library")
    elf_type, machine = struct.unpack_from("<HH", header, 16)
    if elf_type != 3 or machine != {"arm64": 183, "x86_64": 62}[arch]:
        raise BuildError("Built core ELF type or architecture does not match this host")


def _user_directory(path):
    path = Path(path).expanduser().absolute()
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise BuildError("Build output path must not pass through symlinks")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = path.stat()
    if not stat.S_ISDIR(mode.st_mode) or mode.st_uid != os.geteuid():
        raise BuildError("Build output directory must belong to the current user")
    if mode.st_mode & 0o022:
        raise BuildError("Build output directory must not be group- or world-writable")
    return path


def _publish_file(source, target):
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise BuildError("Refusing to replace non-regular output: %s" % target)
    os.replace(source, target)


def _run_build(command, source, environment, log):
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=source, env=environment, stdout=output,
                                   stderr=subprocess.STDOUT, shell=False, start_new_session=True)
        try:
            status = process.wait(timeout=BUILD_TIMEOUT)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise BuildError("Build interrupted or exceeded the 30-minute limit; see build.log")
    if status:
        raise BuildError("PCSX core compilation failed (exit %d); see build.log" % status)


def build_core(output_dir, *, jobs=None, archive=None):
    """Build natively and return the .so path. This never installs system files.

    archive can be an offline copy of the exact pinned tarball; its hash is always
    checked. Existing output artifacts are replaced only after a successful build.
    """
    if platform.system() != "Linux":
        raise BuildError("The PCSX builder currently supports Linux only")
    if os.geteuid() == 0:
        raise BuildError("Run this build as your normal user, not root or sudo")
    arch = native_arch()
    jobs = job_count(jobs)
    output_dir = _user_directory(output_dir)
    programs = ("make", "gcc", "g++", "as", "ld", "ar", "objcopy", "nm")
    tools = {name: shutil.which(name, path=os.defpath) for name in programs}
    missing = [name for name, path in tools.items() if path is None]
    if missing:
        raise BuildError("Missing build tools: %s. Install build-essential and binutils first."
                         % ", ".join(missing))

    with tempfile.TemporaryDirectory(prefix=".pcsx-build-", dir=output_dir) as temporary:
        work = Path(temporary)
        home = work / "home"
        home.mkdir(mode=0o700)
        environment = {"PATH": os.defpath, "HOME": str(home), "LANG": "C", "LC_ALL": "C",
                       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                       "GIT_CEILING_DIRECTORIES": str(work), "SOURCE_DATE_EPOCH": "1793309867"}
        compiler_target = subprocess.run([tools["gcc"], "-dumpmachine"], check=True,
                                        capture_output=True, text=True, env=environment, shell=False).stdout.strip()
        if native_arch(compiler_target.split("-")[0]) != arch:
            raise BuildError("The available GCC does not target the native architecture")
        source_archive = work / SOURCE_FILENAME
        archive = Path(archive) if archive is not None else output_dir / SOURCE_FILENAME
        if archive.exists():
            verify_archive(archive)
            shutil.copyfile(archive, source_archive)
            verify_archive(source_archive)
        elif archive != output_dir / SOURCE_FILENAME:
            raise BuildError("Requested offline source archive does not exist: %s" % archive)
        else:
            download_archive(source_archive)
        extraction = work / "source"
        extraction.mkdir(mode=0o700)
        source = safe_extract(source_archive, extraction)
        command = build_command(arch, jobs, tools)
        log = work / "build.log"
        try:
            _run_build(command, source, environment, log)
        finally:
            if log.exists():
                _publish_file(log, output_dir / "build.log")
        core = source / CORE_FILENAME
        validate_elf(core, arch)
        symbols = subprocess.run([tools["nm"], "-D", "--defined-only", str(core)], check=True,
                                 capture_output=True, text=True, env=environment, shell=False).stdout
        exported = {line.split()[-1] for line in symbols.splitlines() if line.split()}
        if not set(REQUIRED_SYMBOLS).issubset(exported):
            raise BuildError("Built library is missing required libretro entry points")
        provenance = {
            "name": "PCSX ReARMed", "upstream": "https://github.com/libretro/pcsx_rearmed",
            "commit": COMMIT, "source_url": SOURCE_URL, "source_sha256": SOURCE_SHA256,
            "source_archive": SOURCE_FILENAME, "binary": CORE_FILENAME,
            "binary_sha256": sha256_file(core), "architecture": arch,
            "built_at_utc": datetime.now(timezone.utc).isoformat(),
            "compiler_target": compiler_target, "build_command": command,
            "license": "GPL-2.0-or-later; bundled components retain their own notices",
            "source_modified": False,
            "notes": "Native software-rendered libretro core; CHD enabled; no BIOS or games included.",
        }
        metadata = work / "provenance.json"
        metadata.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
        notice = work / "COPYRIGHT.txt"
        notice.write_text(
            "PCSX ReARMed, built from the official pinned source identified in provenance.json.\n"
            "The complete corresponding source and component notices are in " + SOURCE_FILENAME + ".\n"
            "Keep that source archive and these notices with any redistribution.\n"
            "No warranty is provided. No BIOS or game content is included.\n\n"
            + (source / "AUTHORS").read_text(encoding="utf-8") + "\n\n"
            + (source / "COPYING").read_text(encoding="utf-8"), encoding="utf-8")
        core.chmod(0o755)
        for item in (source_archive, notice, metadata):
            item.chmod(0o644)
            _publish_file(item, output_dir / item.name)
        _publish_file(core, output_dir / CORE_FILENAME)
    return output_dir / CORE_FILENAME


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="User-owned directory for core, source archive, notices and provenance")
    parser.add_argument("--jobs", type=int, help="Parallel compile jobs (capped at 4)")
    parser.add_argument("--archive", type=Path, help="Offline copy of the exact pinned source archive")
    args = parser.parse_args(argv)
    try:
        print(build_core(args.output_dir, jobs=args.jobs, archive=args.archive))
    except (BuildError, OSError, subprocess.SubprocessError) as exc:
        print("PCSX build failed: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
