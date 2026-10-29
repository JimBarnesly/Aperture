# Aperture 1.0 release candidate

**Aperture 1.0 RC1** (`1.0.0~rc1`) is a native Kodi 21/Omega living-room interface
for **Raspberry Pi 5 / LibreELEC, authored at 1080p 16:9**. This is a candidate
for hardware testing, **not a stable or Pi-accepted release**. The visible brand is Aperture; legacy `apeture` add-on IDs remain for upgrades
([compatibility note](docs/RENAME.md)).

- Original misty stone-bridge artwork and restrained early-XBMC/Wii-inspired Home.
- Games shows supported, populated system folders from your own collection and
  dispatches to Kodi RetroPlayer. Compatible cores/BIOS are separate.
- Optional native, Format-inspired album shelf: artist/year/title ordering,
  current-playing or random entry, and complete disc/track-ordered album playback.
- Native Kodi Movies, TV, Files and Settings routes; complete pinned Estuary
  windows, dialogs, fonts and playback foundation, not merely a Home mock-up.
- No Format server, Node toolchain, Hermes, Home Assistant or streaming receivers.
  Those integrations are explicitly deferred, not promised by this release.

## Evidence and remaining acceptance

The preceding desktop baseline passed **106 unit/contract tests** and **45 distinct
actual Kodi GUI/Music checks** in [run 40695502466](https://github.com/JimBarnesly/Apeture/actions/runs/40695502466),
with 22 screenshots. Its synthetic seven-album/ten-song library exercised native
scanning, full ordered queue construction, an advancing playback clock and return
to the playing album. The audio sink was null: this does **not** prove audible output.
These are historical baseline results, not a claim that an edited RC has passed CI.
See [release evidence and gates](docs/BUILD_REPORT.md) and [acceptance checklist](docs/TESTING.md).

Pi performance, physical audio, controller/CEC mapping, TV scaling and compatible
game-core playback remain required before calling 1.0 stable. Fresh ZIP installation
and an accepted skin switch require their own exact-build runtime evidence.

## Install the test kit

Follow [First Pi 5 install](docs/INSTALL_PI5.md). Windows users can use the
[guided preparation aid](installer/README.md) to verify/stage ZIPs; it is not
one-click SD provisioning and has no Windows runtime acceptance yet. Official
imaging and on-Pi installation stay manual. Extract an outer download/artifact
wrapper, but leave these three inner add-on ZIPs zipped:

1. `plugin.games.apeture-1.0.0~rc1.zip` — optional Games companion.
2. `script.apeture.music-1.0.0~rc1.zip` — optional Album Shelf companion.
3. `skin.apeture-1.0.0~rc1.zip` — complete skin; install/select last.

Keep Estuary installed and back up the Kodi profile. Select Aperture in Settings →
Interface → Skin; confirm only if readable and responsive, otherwise let Kodi revert.
Neither companion is a hard dependency: missing Music falls back to Kodi Music;
missing Games shows setup guidance. Configure and scan your own media explicitly.
No ROMs, BIOS, emulator cores, commercial covers or synthetic catalogue are shipped.

## Build

Requires Git, Python 3.10+ and Pillow; no credentials or Node server.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python tools/build.py
```

The first build fetches the [pinned official Estuary baseline](docs/UPSTREAM.md).
`dist/` contains the three add-on ZIPs, `checksums.json`, install guidance and
the optional `installer/` preparation script/README (no tests or CI evidence).
`addons/skin.apeture` contains overrides, **not an installable skin**. Do not zip it
or install a GitHub source archive. The assembled skin is `build/skin.apeture`.

`python tools/build.py --skip-vendor` is an offline repack shortcut only: it rejects
stale/legacy provenance, changed inputs or modified assembled files. Rebuild
normally after source changes. ZIP timestamps/order are deterministic for identical
assembled bytes. Keep the checksum manifest and packages from one build together.

## Boundaries and licensing

No automatic media/metadata downloads, accounts, tracking, servers or media-file
writes. Selecting **Play album replaces the music queue and disables shuffle**;
cue/shared-file albums use native Kodi Music. A detected game is not a guarantee
that its core works on Pi. [Product scope](docs/PRODUCT.md) and [shelf details](docs/MUSIC_SHELF.md).

Format is a behavior reference only: no Format code, assets or license was imported.
The game/music companions and build tooling use GPL-3.0-or-later; the assembled
Estuary-derived skin retains separate GPLv2-compatible, artwork and font-license
boundaries. See [upstream licensing](docs/UPSTREAM.md); the root [LICENSE](LICENSE)
does not relicense inherited files.
