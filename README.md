# Aperture

A Kodi-native, controller-oriented home for Raspberry Pi 5. Music is fully
backed by the [Format music server](https://github.com/JimBarnesly/Format): one
library, album playback, catalogue discovery and download management in the skin.
Format also retains its standalone web application.

## Consolidated integration candidate

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
See [integration scope and gates](docs/main-integration.md) for the consolidated
features, retained alternatives and exact-source verification requirements.

## Install the complete ZIPs

Use the complete, tested ZIPs from the candidate kit or matching CI artifact:

1. Keep Estuary installed and back up your Kodi profile.
2. Install `plugin.audio.aperture.format-0.4.0.zip` through Kodi's ZIP installer.
3. Install `plugin.video.aperture.movies-0.1.1.zip`, then `skin.aperture-4.0.1~rc1.zip` through Kodi's ZIP installer.
4. If Kodi presents an unknown-sources warning, review it yourself. The software
   does not silently enable that setting. Disable it again after installation.
5. Choose Aperture in Settings > Interface > Skin. Select Keep only when the
   screen and controls respond. Otherwise let the automatic rollback happen.
6. Open Music to enter the record shelf directly. If needed, use Store >
   Configure Format server to set the reachable server address.
   Select an album to play the complete release in disc/track order and open
   the native turntable. Long-press (or press C) and choose **Browse tracks**
   when you want a particular track. Music is one Format library, without a separate
   local/streaming choice. See [Format integration](docs/format-integration.md)
   for server setup, download restrictions and Pi acceptance.

Do not ZIP the `skin/` override directory. It is not a complete skin. Do not install
both this prototype and an older `skin.apeture` kit expecting them to be the same
add-on; their internal IDs are different.

## Shell installation

For an existing Kodi 21 installation, a checked-out copy can be installed using
`sh install.sh` and `sh install-format.sh`. Run as the Kodi desktop user on
Raspberry Pi OS, or as root on LibreELEC. Exit Kodi first. The installers refuse
live replacement, preserve older add-ons outside Kodi's scan directory and leave
settings, libraries, credentials and the add-on database alone.

On Raspberry Pi OS, if Estuary has a broken link to an installed font, the skin
installer uses Python 3 to find the **exact same filename** recursively under
`/usr/share/fonts`, then copies the font bytes into staging. This handles Debian's
`truetype/roboto/unhinted/RobotoTTF/Roboto-Thin.ttf` layout without editing system
files or substituting a different font. Missing, empty or ambiguous matches fail
before replacing the old skin. Intact resources still install without Python 3.
Use the complete checkout so `tools/build_skin.py` is present, or use the complete
ZIP. `APERTURE_FONT_ROOT` can select one other absolute search root; it replaces,
rather than adds to, the default. No fonts are downloaded.

For an offline checkout set `APERTURE_SOURCE_DIR` to its absolute path. A custom
profile can be supplied as `APERTURE_KODI_HOME`. The skin installer requires the
complete matching checkout, including artwork and notices. A detached Format
installer requires an explicit immutable `APERTURE_REF` commit SHA. Skin `--baseline` mode
retains unmodified Estuary Home for diagnosis. It does not install or reconfigure
the OS, stop services, flash storage, enable SSH or provision Format.

## Format service and limits

Format must run on a server reachable by Kodi. For the protected same-Pi setup,
use `http://127.0.0.1:4534`; the client does not guess a server or install one.
Native album shelves, artists, library search, ordered playback, catalogue search
and download status share Format's existing backend with its standalone UI.

Download actions require the matching explicit server capability, an action in
Kodi and a confirmation. Acquisition, cancellation and prioritisation are checked
independently, including after confirmation. A protected server can permit new
downloads while keeping existing-library edits disabled. Missing or malformed
capabilities fail closed; older servers without a capability object use their
explicit read-only flag. Changing the skin does not enable server permissions.
No automatic acquisition, metadata rewriting, deletion, upload, operator
privileges or LAN exposure is added. The verified default Pi deployment disables
download writes. An opt-in download profile needs separate server verification,
a safe destination/staging setup and authorised provider access.

The native Kodi client does not embed a web browser or clone Format's database.
Game systems and receiver services remain separate; generic Kodi is not a
certified Google Cast receiver. See [integration and installation](docs/format-integration.md).

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

## Optional Pi gaming and local media

The independent [Pi gaming installer](docs/pi-gaming.md) adds a read-only ROM
browser and native RetroPlayer cores. The home Games item opens that browser
when enabled and keeps native Games as the fallback. Physical controller, HDMI
and game compatibility still need testing on your Pi.

[HDD music and movies](docs/local-media.md) explains shared Format music and video sources
and HDD browsing without moving media or changing mounts.
