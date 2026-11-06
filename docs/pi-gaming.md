# Raspberry Pi OS gaming candidate

This is an opt-in Kodi 21 gaming setup, not an OS image, RetroPie replacement,
or claim that every console/game works. It keeps playback inside Kodi RetroPlayer.
The original read-only library is now `plugin.games.aperture`; old Apeture add-ons
are not deleted or overwritten.

## Install

Use the complete pinned checkout provided with the tested release. Exit Kodi
normally before running these as the Kodi desktop user, **not sudo**:

```sh
sh install-gaming.sh --check
sh install-gaming.sh --install
```

`--check` only reports Kodi package/version, architecture, available signed distro
packages and candidate mounted ROM folders. It does not refresh apt lists, mount
a drive, install anything, configure Bluetooth, or touch the Kodi profile.

`--install` supports distro Kodi 21 on 64-bit Raspberry Pi OS/Debian (arm64) and
amd64 test systems. It discovers a folder containing system folders below
`/media/$USER`, `/run/media/$USER`, or `/mnt`, stopping after bounded shallow
inspection. A single candidate is selected; multiple candidates require a
number. Supply `--rom-root "/media/jake/HDD/roms"` if discovery is ambiguous.
The drive must already be mounted normally. No fstab, permissions or mounts change.

The script shows APT's normal confirmation and may ask for sudo. It installs only
from the machine's configured signed repositories, simulates first, refuses
removals and does not upgrade existing packages or add repository sources.
If package indexes are missing/stale, refresh them normally and rerun. It does
not silently add `non-free` to obtain optional SNES/Genesis packages.

Installed components:
- `kodi-game-libretro`, Kodi's official game API/libretro bridge.
- `kodi-peripheral-joystick`, Kodi's controller input support.
- Available cartridge cores: Nestopia (NES), Snes9x (SNES), Gambatte (GB/GBC),
  mGBA (GBA), Genesis Plus GX (Mega Drive/Master System/Game Gear).
- PCSX ReARMed from one pinned official source commit, built locally as the user
  with CHD support. Source SHA256, extraction safety, ELF architecture and exported
  libretro functions are checked. No opaque community binary or unstable Debian
  repository is used. Build tools come from APT. `--skip-psx-build` opts out.
- Aperture game browser and per-core metadata/controller mappings. Libraries are
  copied into user-owned add-ons; package copyright and build provenance are kept.

A failed stage does not replace add-ons. Profile commit rolls back previous
add-ons/settings if a later file swap fails. Previous files are backed up outside
Kodi's add-on scan folder. Existing saves, other add-ons, libraries, GUI settings,
Bluetooth bonds and the Kodi add-on database are not edited. Package installation
is a separate operation; already-installed packages are not removed on failure.
Do not run Kodi or another installer concurrently. This is a trusted-user install,
not a security sandbox against concurrent hostile filesystem changes.

## First run

Restart Kodi and enable **Aperture Game Library** and the **Aperture · …** emulator
add-ons in Add-ons → My add-ons if Kodi asks. A copied user add-on can be disabled
until this explicit enable; the installer does not bypass this by editing its DB.
Open Games → Game add-ons → Aperture Game Library. Choose a system and game.
The updated skin's Games entry opens Aperture Game Library when enabled, with native Games as its fallback; no dashboard duplication is added.

Pair the 8BitDo yourself. The mode/transport determines its reported device name
and layout; automatic mapping is not guaranteed. If necessary use Kodi Settings
→ System → Input → Configure attached controllers, selecting Default Controller.
Mappings are positional Xbox-style: south=A, east=B, west=X, north=Y in Kodi,
independent of the printed Nintendo face labels. PSX uses a DualShock mapping with
both sticks and shoulder buttons. The guide/home button opens Kodi's game menu
when mapped; choose Stop to return. Keep keyboard Escape available for recovery.
Physical pairing, rumble, Bluetooth latency, HDMI sound and real-game performance
still need testing on the Pi. A paired controller is not evidence of correct input.

## Games and firmware

The root contains `nes/`, `snes/`, `gb/`, `gbc/`, `gba/`, `megadrive/` (or
`genesis/`), `mastersystem/`, `gamegear/`, and `psx/` (or `ps1/`). Files may be nested.
PS1 BIN tracks are not separately listed; use valid CUEs, CHD, PBP, ISO or original
PS-X EXE homebrew. CUE references must match actual case and stay within the
system folder. M3U can group discs but the browser asks which disc to launch;
it is not a promise of seamless in-game disc changes. Cartridge ZIP archives
must be extracted beforehand. No games, firmware, covers or metadata are downloaded.

The scanner recognizes some additional systems (N64, PC Engine, Atari, arcade),
but this installer does **not** install their cores or claim their compatibility.
PS2, PSP, Dreamcast, GameCube and Wii are outside this first native setup.

For best PS1 compatibility, provide your own legally obtained BIOS. The installer
recognizes known 512-KiB BIOS filenames in `bios/` or `BIOS/` beside/within the ROM
root and copies missing files to:
`~/.kodi/userdata/addon_data/game.libretro.aperture.pcsxrearmed/resources/system/`.
Existing BIOS files are preserved. Size/name detection is **not authenticity
verification**. The core has HLE fallback, but it is not a guarantee a game boots.
Saved games stay in Kodi's per-core userdata. Music/movie files are never scanned
or changed, and nothing here synchronizes or deletes media.

## Verification boundaries

Unit tests cover discovery, path bounds, broken descriptors, cancellation, Kodi
adapter contract, package planning, controller manifests and install rollback.
The dedicated CI workflow builds PCSX from pinned source and attempts actual Kodi
NES/PSX playback on x86_64 and ARM64 using original tiny hardware-test programs,
with start/stop and screenshots. Consult the exact commit's CI result;
prepared tests do not mean they passed. Cloud ARM64 is not a physical Pi 5.

## Updating only the browser and skin

When the cores already work, exit Kodi normally and use a verified complete
checkout. `python3 tools/update_game_library.py` updates only the existing browser,
with backup/rollback, leaving the ROM-root setting, emulators, BIOS and saves alone.
Then `sh install.sh` updates the skin. Neither command needs sudo or rebuilds cores.

The Aperture console view uses original bundled illustrations and a horizontal
strip. Games use a readable list and an artwork panel. Existing local sidecars
are supported: `Game.png`/`.jpg`, or `images/Game-image.png`, `Game-thumb.png`,
`Game-boxart.png`, `Game-cover.png` (JPEG variants also supported). No covers or
metadata are downloaded, and missing pictures show the console illustration.
Other skins and native Kodi game sources retain normal browsing.
