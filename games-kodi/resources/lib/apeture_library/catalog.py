"""Folder-based identification, not an emulator compatibility database.

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class System:
    id: str
    name: str
    folders: Tuple[str, ...]
    extensions: FrozenSet[str]


def _system(identifier, name, folders, extensions):
    return System(identifier, name, tuple(folders.split()), frozenset(extensions.split()))


SYSTEMS = (
    _system("nes", "Nintendo Entertainment System", "nes", ".nes .fds .unf .unif"),
    _system("snes", "Super Nintendo", "snes", ".sfc .smc"),
    _system("gb", "Game Boy", "gb", ".gb"),
    _system("gbc", "Game Boy Color", "gbc", ".gbc .gb"),
    _system("gba", "Game Boy Advance", "gba", ".gba"),
    _system("n64", "Nintendo 64", "n64", ".n64 .z64 .v64"),
    _system("megadrive", "Sega Mega Drive / Genesis", "megadrive genesis", ".md .gen .smd .bin"),
    _system("mastersystem", "Sega Master System", "mastersystem sms", ".sms"),
    _system("gamegear", "Sega Game Gear", "gamegear gg", ".gg"),
    _system("pcengine", "PC Engine / TurboGrafx-16", "pcengine pce", ".pce .sgx"),
    _system("atari2600", "Atari 2600", "atari2600", ".a26 .bin"),
    _system("psx", "Sony PlayStation", "psx ps1", ".cue .chd .iso .pbp .exe .m3u .m3u8"),
    _system("arcade", "Arcade", "arcade", ".zip"),
)
SYSTEM_BY_ID = {system.id: system for system in SYSTEMS}
SYSTEM_BY_FOLDER = {
    folder: system for system in SYSTEMS for folder in system.folders
}
