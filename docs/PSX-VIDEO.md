# PlayStation image options

For soft pixel edges, open Kodi's in-game menu (Select + X with the default
controller mapping), choose **Video filter → Smooth**. Pixelate restores crisp
nearest-neighbour pixels. Keep the original 4:3 aspect ratio unless intentionally
stretching the image.

The Aperture PCSX ReARMed settings optionally expose **Enhanced resolution (2x)**.
It is off by default and does not turn on any speed hack. The pinned ARM64 and
x86 builds use the NEON renderer, which supports this option. It renders supported
low-resolution modes at double internal resolution. This primarily benefits 3D
geometry. Pre-rendered 2D scenes and sprites, such as Abe's Oddysee, do not gain
new source detail; smoothing is often the more relevant change for them.

Stop the game, open **Settings → Add-ons → My add-ons → Game add-ons → Emulators**,
select **Aperture · PlayStation (PCSX ReARMed)**, then **Configure → PlayStation
video**. Choose the enhanced option and start the game again. If performance,
audio stability or graphics regress, select **Native (recommended)** and restart
the game. Per-title performance and visuals on the user's Pi remain unverified.

## Existing installation

With Kodi closed, run `python3 tools/update_psx_settings.py --install` from a
verified Aperture checkout. This changes only settings definitions and their
English labels, leaves the core binary and all saved preferences/BIOS/ROMs/saves
unchanged, and backs up the existing emulator add-on outside Kodi's addon folder.
It does not turn enhancement on. A live game is never interrupted by the updater.

## Evidence and limits

- Source: official PCSX ReARMed commit
  `7b0e8f8fadfbce3d170d195b9d9eecaabfa08c8e`, Makefile.libretro and
  frontend/libretro_core_options.h.
- Headless x86 probe rendered the original test program at 320×240 with the option
  disabled and 640×480 when enabled. This is not a commercial-game or Pi test.
- Kodi UI and ARM rendering acceptance are checked separately in gaming CI.
