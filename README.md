# Aperture

A Kodi-native, controller-oriented home for Raspberry Pi 5, with a separate
read-only client for the [Format music server](https://github.com/JimBarnesly/Format).

## Repair candidate

This branch addresses the current `skin.aperture` prototype, **not** the older
`skin.apeture` release-candidate branches. The reported Pi hang has not yet been
reproduced. Do not infer a root cause from the last line of a truncated Kodi log.

The candidate uses complete Kodi 21 Omega Estuary resources with an Aperture Home,
valid font names and native media/settings dialogs. Version **4.0.1~rc1** upgrades
the prototype's inherited 4.0.0 version. Estuary remains available for recovery.

The actual Kodi 21.3 CI job tests activation, repeated navigation and skin recovery
in an isolated software-rendered desktop. Its result is distinct from the unit
tests and is not proof of Pi hardware, controller, HDMI-CEC or audible output.
Until the final test report is recorded, treat this branch as work in progress.

## Install the complete ZIPs

Use the complete, tested ZIPs from the candidate kit or matching CI artifact:

1. Keep Estuary installed and back up your Kodi profile.
2. Install `plugin.audio.aperture.format-0.2.0.zip` through Kodi's ZIP installer.
3. Install `skin.aperture-4.0.1~rc1.zip` through Kodi's ZIP installer.
4. If Kodi presents an unknown-sources warning, review it yourself. The software
   does not silently enable that setting. Disable it again after installation.
5. Choose Aperture in Settings > Interface > Skin. Select Keep only when the
   screen and controls respond. Otherwise let the automatic rollback happen.
6. Open Music. Configure the reachable Format server address in the add-on
   settings, then open Albums. Long-press an album (or press C) and choose **Play
   album** to play the complete release in disc/track order.

Do not ZIP the `skin/` override directory. It is not a complete skin. Do not install
both this prototype and an older `skin.apeture` kit expecting them to be the same
add-on; their internal IDs are different.

## Shell installation

For an existing Kodi 21 installation, a checked-out copy can be installed using
`sh install.sh` and `sh install-format.sh`. Run as the Kodi desktop user on
Raspberry Pi OS, or as root on LibreELEC. Exit Kodi first. The installers refuse
live replacement, preserve older add-ons outside Kodi's scan directory and leave
settings, libraries, credentials and the add-on database alone.

For an offline checkout set `APERTURE_SOURCE_DIR` to its absolute path. A custom
profile can be supplied as `APERTURE_KODI_HOME`. The skin installer requires the
complete matching checkout, including artwork and notices. A detached Format
installer requires an explicit immutable `APERTURE_REF` commit SHA. Skin `--baseline` mode
retains unmodified Estuary Home for diagnosis. It does not install or reconfigure
the OS, stop services, flash storage, enable SSH or provision Format.

## Format service and limits

Format must already be running on a server reachable by the Pi. There is no
hard-coded private server address. The add-on reads `/api/library`, retrieves
cover images and streams audio. It does not acquire, delete, rename or upload
music. It supports release/track IDs containing commas and sorts multi-disc
releases by disc and track metadata before replacing the playback queue.

Native Kodi music views are used in this candidate. Format's original web
cover-flow is not embedded. Game systems, artwork, emulator installation and
receiver services remain separate work. Generic Kodi is not a certified Google
Cast receiver.

## Build and test

On a disposable Debian system with Kodi 21 and Python 3 installed:

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_skin.py
bash tools/ci_kodi_smoke.sh
```

The graphical script has additional dependencies documented in
`.github/workflows/kodi-smoke.yml`. It uses a fresh profile and private display,
never a user's profile. Do not use it as a configuration script on the Pi.

Builds are assembled from the installed official Estuary; use the exact CI runtime
for byte-identical packages. ZIP timestamps/order are deterministic and hashes
are in `dist/checksums.json`. Upstream notices are retained. See
[upstream boundaries](docs/UPSTREAM.md) and [testing](docs/TESTING.md).
