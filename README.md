# Apeture

## Scenic experiment (0.2.0)

This branch explores a misty stone-bridge backdrop and a quiet horizontal Home
menu. The baseline design remains on `feat/native-kodi-foundation`. Both use the
same native media routes and game-library add-on. See [design notes](docs/DESIGN.md).
The bridge is original generated artwork, not a recovered historical wallpaper.

An opt-in GitHub Actions smoke test on `experiment/scenic-bridge` runs actual
Kodi 21 with an isolated profile and software display. Its result is separate
from static tests and still does not establish Pi/controller/core compatibility.

A modern XBMC-original-inspired Kodi skin. One living-room interface for games,
music and video, with an optimistic early-2000s character and native controller
navigation. **Apeture** is the intentional spelling.

## First development slice

- Original Home screen over a complete, pinned Kodi 21 Omega Estuary foundation.
- Companion game-library add-on that detects supported populated system folders.
- Native Kodi RetroPlayer dispatch, not a standalone RetroArch launcher.
- Reproducible ZIP packaging, XML/manifest checks and Python unit tests.

This is an early development build, not a tested Pi appliance release. Automated
checks do not establish successful Kodi rendering or emulator compatibility.
Receiver protocols and the full Format-inspired album shelf are future work.

## Build

Requires Python 3.10+ and Pillow. No Node toolchain, database or credentials.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build.py
```

The first build fetches the pinned official Estuary baseline. The repository
stores the authored overrides and vendoring recipe rather than duplicating all
upstream binary assets. See [upstream provenance](docs/UPSTREAM.md).

Outputs appear in `dist/`: the game-library ZIP, complete skin ZIP, and SHA-256
checksums. The `addons/skin.apeture` source directory alone is **not** a complete
installable skin. Do not zip it directly. `build/skin.apeture` is the assembled skin.

After materialization, static checks and local repackaging can be repeated:

```sh
python tools/validate.py
python tools/build.py --skip-vendor
```

## Try it safely

1. Back up your Kodi profile and keep your current skin installed.
2. Use a Kodi 21 Omega test installation. Install the game-library ZIP first,
   then the skin ZIP using Kodi's “Install from zip file” flow.
3. Change the skin in Settings → Interface and confirm only if the keep/revert
   dialog is visible and usable. Settings remain accessible from Home.
4. Configure the game-library add-on's ROM root. Read its bundled README for
   supported folder names and formats. Use only media you are entitled to use.
5. Install compatible game add-ons separately through Kodi. Apeture includes no
   emulator cores, BIOS or games. File detection does not guarantee playback.

If Kodi asks to permit unknown-source ZIP installation, decide on that setting
yourself after reviewing the source. This project does not change that setting.

For actual Pi acceptance, work through [the test checklist](docs/TESTING.md).

## Boundaries

- No automatic ROM, BIOS, artwork or metadata downloads.
- No accounts, tracking, network servers, system changes or media-file writes.
- No claim that every RetroArch core runs in Kodi. RetroPlayer and RetroArch are
  separate frontends; compatible Kodi game add-ons are required.
- Format-style album Cover Flow and stream receiving are documented goals, not
  features hidden behind non-functional Home buttons.

See [product scope and roadmap](docs/PRODUCT.md). The game-library and build
tooling use the repository's GPL-3.0 license. The assembled Estuary-derived skin
has separate GPLv2-compatible code, CC-BY-SA artwork and font-license boundaries;
its notices are retained. See [upstream licensing](docs/UPSTREAM.md) rather than
assuming the root [LICENSE](LICENSE) relicenses inherited files.
