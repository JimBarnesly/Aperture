#!/usr/bin/env python3
"""Build deterministic, installable add-on ZIPs. Never installs into Kodi."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package_addon(source: Path, destination: Path) -> dict:
    """Package one complete addon under its identifier, with stable timestamps."""
    manifest = ET.parse(source / "addon.xml").getroot()
    addon_id, version = manifest.attrib["id"], manifest.attrib["version"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+", addon_id):
        raise ValueError("Unsafe addon identifier")
    if not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in version):
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-vendor", action="store_true", help="Use an already materialized build/skin.apeture")
    args = parser.parse_args()
    if not args.skip_vendor:
        subprocess.run([sys.executable, str(ROOT / "tools/vendor_estuary.py"),
                        "--output", str(ROOT / "build/skin.apeture")], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/validate.py")], check=True)
    packages = [package_addon(ROOT / "addons/plugin.games.apeture", ROOT / "dist"),
                package_addon(ROOT / "build/skin.apeture", ROOT / "dist")]
    (ROOT / "dist/checksums.json").write_text(json.dumps(packages, indent=2) + "\n")
    print(json.dumps(packages, indent=2))


if __name__ == "__main__":
    main()
