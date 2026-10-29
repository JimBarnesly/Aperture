#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Make an explicitly NONPLAYABLE, browse-only Games fixture in disposable CI.

This helper does not install add-ons, change Kodi settings, seed a database,
launch Kodi, or play anything. The runtime driver must NEVER activate a dummy
game item. Files have recognised suffixes solely to exercise folder discovery;
their short text payload is not a ROM and contains no emulator header/code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LABEL = "SYNTHETIC QA - NONPLAYABLE GAME BROWSE"
DIRECTORY = "synthetic-game-browse"
PAYLOAD = b"NOT A ROM. SYNTHETIC QA - BROWSE ONLY. DO NOT PLAY OR LAUNCH.\n"

SYSTEMS = (
    {"id": "gba", "label": "Game Boy Advance", "games": (
        {"title": "SYNTHETIC QA - DO NOT PLAY - GBA",
         "relative_path": "gba/SYNTHETIC QA - DO NOT PLAY - GBA.gba"},
    )},
    {"id": "nes", "label": "Nintendo Entertainment System", "games": (
        {"title": "SYNTHETIC QA - DO NOT PLAY - Alpha",
         "relative_path": "nes/SYNTHETIC QA - DO NOT PLAY - Alpha.nes"},
        {"title": "SYNTHETIC QA - DO NOT PLAY - Nested",
         "relative_path": "nes/nested/SYNTHETIC QA - DO NOT PLAY - Nested.NES"},
    )},
)
IGNORED_FILES = (
    "nes/SYNTHETIC QA - IGNORED - readme.txt",
    "unsupported-system/SYNTHETIC QA - IGNORED - Unknown.nes",
    "SYNTHETIC QA - IGNORED - Root-level.nes",
)

# These are an integration contract, NOT a claim that the runtime checks ran.
ASSERTIONS = (
    "Use only the disposable profile; save its previous ROM-root setting.",
    "Set that profile's ROM root to root, open the native Games plugin, and wait for ready.",
    "Observe exactly two real system rows (GBA and NES), three detected games, plus management/parent rows.",
    "Assert empty SNES, unsupported-system, TXT and root-level candidates are absent from the game catalogue.",
    "Before selecting a system, verify the focused item is a folder and its URL action is system, never play.",
    "Enter NES through native UI; assert exactly the two expected dummy titles and game count two.",
    "Focus a dummy title for screenshot evidence; NEVER select, Play, queue, or activate that item.",
    "Use native Back; verify the root system rows/counts return and no game player was started.",
    "Use unavailable_root in the disposable setting, reopen/refresh, dismiss the expected read-error dialog, and verify error plus Configure ROM folder recovery.",
    "Restore the previous ROM-root setting; verify the original empty/unconfigured view and no active game player.",
    "Label evidence SYNTHETIC QA / NONPLAYABLE: browsing/navigation only, not emulator or controller acceptance.",
)


def _checked_runtime(runtime: Path) -> Path:
    supplied = Path(runtime)
    if supplied.is_symlink():
        raise ValueError("A symlink is not a disposable runtime")
    runtime = supplied.resolve()
    if not runtime.name.startswith("apeture-kodi-smoke.") or not runtime.is_dir():
        raise ValueError("Expected an existing apeture-kodi-smoke.* disposable runtime")
    required = ("system", "system/system", "data", "data/userdata",
                "system/system/addon-manifest.xml", "data/userdata/guisettings.xml")
    for relative in required:
        candidate = runtime / relative
        if candidate.is_symlink() or not candidate.exists() or not candidate.resolve().is_relative_to(runtime):
            raise ValueError("Missing or unsafe disposable Kodi system/profile marker")
    if not (runtime / required[-1]).is_file() or not (runtime / required[-2]).is_file():
        raise ValueError("Expected disposable Kodi system/profile files")
    return runtime


def prepare(runtime: Path) -> dict:
    """Return manifest; only a fresh synthetic-game-browse directory is written.

    Refuses reuse, symlink targets and an already existing 'unavailable' path.
    Kodi settings and system/profile markers are checked but never written.
    """
    runtime = _checked_runtime(runtime)
    destination = runtime / DIRECTORY
    unavailable = runtime / (DIRECTORY + "-unavailable")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to replace an existing Games fixture")
    if unavailable.exists() or unavailable.is_symlink():
        raise ValueError("The unavailable-root test path must not exist")
    systems = [dict(id=system["id"], label=system["label"],
                    game_count=len(system["games"]), games=list(system["games"]))
               for system in SYSTEMS]
    manifest = {
        "label": LABEL,
        "status": "prepared_not_run",
        "never_launch": True,
        "scope": "Native Games directory browsing/navigation only; no emulation claim",
        "runtime": str(runtime),
        "root": str(destination),
        "unavailable_root": str(unavailable),
        "expected": {
            "system_count": len(systems),
            "game_count": sum(system["game_count"] for system in systems),
            "systems": systems,
            "excluded_system_ids": ["snes", "unsupported-system"],
            "ignored_relative_paths": list(IGNORED_FILES),
            "payload_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        },
        "runtime_assertions": list(ASSERTIONS),
    }
    destination.mkdir(mode=0o700)
    for relative in [game["relative_path"] for system in systems for game in system["games"]] + list(IGNORED_FILES):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PAYLOAD)
    (destination / "snes").mkdir()  # Known but empty: must not become a system row.
    (destination / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.runtime), indent=2))


if __name__ == "__main__":
    main()
