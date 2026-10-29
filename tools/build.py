#!/usr/bin/env python3
"""Build deterministic, installable add-on ZIPs. Never installs into Kodi."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def file_fingerprints(root: Path, *, exclude: tuple[str, ...] = ()) -> dict[str, str]:
    """Hash every materialization resource; reject symlinks, including directories."""
    result = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"Symlink is not a build resource: {path}")
        if path.is_file() and name not in exclude:
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def skin_input_fingerprints(root: Path = ROOT) -> dict[str, str]:
    """Include additions/deletions as well as edits, generators and shipped notices."""
    result = {}
    for directory in ("addons/skin.apeture", "assets"):
        result.update({f"{directory}/{name}": digest
                       for name, digest in file_fingerprints(root / directory).items()})
    for name in ("tools/build.py", "tools/vendor_estuary.py",
                 "tools/vendor_estuary_assets.py", "docs/UPSTREAM.md", "docs/DESIGN.md"):
        result[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return result


def verify_materialized_skin(source: Path, root: Path = ROOT) -> None:
    """Fail closed on legacy, stale or modified vendor output; never silently ship it."""
    try:
        marker = json.loads((source / "APETURE_BUILD.json").read_text())
        if marker.get("inputs_sha256") != skin_input_fingerprints(root):
            raise ValueError("source inputs changed or provenance predates content verification")
        if marker.get("files_sha256") != file_fingerprints(source, exclude=("APETURE_BUILD.json",)):
            raise ValueError("assembled skin files changed")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"Stale or invalid materialized skin: {exc}. "
                         "Run python tools/build.py without --skip-vendor.") from exc


def write_install_guide(packages: list[dict], destination: Path) -> None:
    """Include human installation steps beside the ZIPs, not a source-tree copy."""
    filenames = {item["addon"]: item["file"] for item in packages}
    required = ("plugin.games.apeture", "script.apeture.music", "skin.apeture")
    if any(identifier not in filenames for identifier in required):
        raise ValueError("Install kit requires the skin and both companion packages")
    destination.mkdir(parents=True, exist_ok=True)
    text = f"""APERTURE 1.0 RELEASE CANDIDATE — KODI 21 TEST KIT

Read INSTALL_PI5.md before using a test microSD card/profile. Keep Estuary installed.
Windows users: installer/README.md describes the optional guided preparation aid.
It verifies/copies ZIPs only, NOT one-click SD provisioning. Official imaging and
on-Pi installation remain manual. Windows execution/USB detection is not verified
by the Linux static checks; use only on an authorised computer.
Desktop checks are not Pi, physical audio, gamepad or HDMI-CEC acceptance.

WHAT TO INSTALL
If this arrived inside one download/artifact ZIP, extract that OUTER wrapper.
Keep these three INNER add-on ZIPs zipped; Kodi installs them individually:

1. {filenames['plugin.games.apeture']} — optional game-library companion
2. {filenames['script.apeture.music']} — optional native album-shelf companion
3. {filenames['skin.apeture']} — complete skin; install/select this last

Transfer those files to storage Kodi can browse (for example, a USB drive).
In stock Kodi, open Add-ons > Add-on browser > Install from ZIP file. Review any
Unknown sources warning yourself; this kit does not change that setting.
After each install, wait for Kodi's notification. If a companion is disabled,
review it in Add-ons > My add-ons before expecting its Home integration.

Select Settings > Interface > Skin > Aperture. Confirm only if it is readable and
navigation works; otherwise let the confirmation timer return to Estuary.
The companions are independent, not hard dependencies of the skin: missing
Music helper falls back to native Kodi Music; missing Games helper shows setup.

No Node server, npm/pip installation, SSH or manual build-folder copying is
needed on the Pi. Kodi 21 supplies the required xbmc.python/xbmc.gui APIs.
Do not install a GitHub source archive or zip addons/skin.apeture yourself:
the supplied skin ZIP already includes its complete pinned window/font assets.

FIRST MUSIC / GAMES
Open Music > Kodi Music, then Files > Add music. Choose your own tagged music
folder and confirm scanning it into the library. Merely browsing files does not
populate the album shelf. Wait for scanning to finish, then reopen/Refresh it.
Online metadata scraping is optional and is not required for this shelf.
Play album replaces the current music queue in disc/track order and disables
shuffle; cue/shared-file albums should be played through native Kodi Music.

For Games, choose a ROM root containing supported system subfolders. Compatible
Kodi game/emulator add-ons and any legally required BIOS files are separate;
this kit includes no games, BIOS, emulator cores or synthetic test catalogue.

checksums.json records each inner ZIP's byte count and SHA-256. Keep all files
from the same build together. INSTALL_PI5.md has setup and recovery guidance.
"""
    (destination / "README-INSTALL.txt").write_text(text, encoding="utf-8")
    shutil.copyfile(ROOT / "docs/INSTALL_PI5.md", destination / "INSTALL_PI5.md")
    installer = destination / "installer"
    installer.mkdir(exist_ok=True)
    # Explicit allowlist: never bundle tests, caches, CI evidence or image files.
    for name in ("Prepare-Aperture.ps1", "README.md"):
        shutil.copyfile(ROOT / "installer" / name, installer / name)


def package_addon(source: Path, destination: Path) -> dict:
    """Package one complete addon under its identifier, with stable timestamps."""
    manifest = ET.parse(source / "addon.xml").getroot()
    addon_id, version = manifest.attrib["id"], manifest.attrib["version"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+", addon_id):
        raise ValueError("Unsafe addon identifier")
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-~" for c in version):
        raise ValueError("Unsafe addon version")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"{addon_id}-{version}.zip"
    paths = sorted(p for p in source.rglob("*") if p.is_file()
                   and "__pycache__" not in p.parts
                   and not p.name.endswith((".pyc", ".pyo"))
                   and not any(part.startswith(".") for part in p.relative_to(source).parts))
    if not paths:
        raise ValueError("Empty addon")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            if path.is_symlink():
                raise ValueError(f"Symlink is not an addon resource: {path}")
            name = f"{addon_id}/{path.relative_to(source).as_posix()}"
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Corrupt zip member: {bad}")
        assert f"{addon_id}/addon.xml" in archive.namelist()
    return {"addon": addon_id, "version": version, "file": output.name,
            "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "files": len(paths)}


def remove_obsolete_packages(packages: list[dict], destination: Path) -> None:
    """Keep generated kit unambiguous without deleting unrelated user files."""
    for package in packages:
        for candidate in destination.glob(f"{package['addon']}-*.zip"):
            if candidate.name != package['file'] and candidate.is_file():
                candidate.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-vendor", action="store_true", help="Reuse materialized skin only when source and assembled content hashes match")
    args = parser.parse_args()
    if not args.skip_vendor:
        subprocess.run([sys.executable, str(ROOT / "tools/vendor_estuary.py"),
                        "--output", str(ROOT / "build/skin.apeture")], check=True)
    verify_materialized_skin(ROOT / "build/skin.apeture")
    subprocess.run([sys.executable, str(ROOT / "tools/validate.py")], check=True)
    packages = [package_addon(ROOT / "addons/plugin.games.apeture", ROOT / "dist"),
                package_addon(ROOT / "addons/script.apeture.music", ROOT / "dist"),
                package_addon(ROOT / "build/skin.apeture", ROOT / "dist")]
    (ROOT / "dist/checksums.json").write_text(json.dumps(packages, indent=2) + "\n")
    write_install_guide(packages, ROOT / "dist")
    remove_obsolete_packages(packages, ROOT / "dist")
    print(json.dumps(packages, indent=2))


if __name__ == "__main__":
    main()
