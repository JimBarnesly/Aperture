# Aperture 1.0 RC1 — release evidence and gates

Prepared 29 October 2026. All three packages use **`1.0.0~rc1`**. This is a
Kodi 21/Omega candidate for Pi 5 / LibreELEC acceptance, **not a stable release**.

## Verified preceding baseline

[Desktop Kodi run 40695502466](https://github.com/JimBarnesly/Apeture/actions/runs/40695502466)
passed 45 distinct actual GUI/Music checks and retained 22 screenshots. Source
baseline: remote `4e95d006` / subsequent local `0d1e91a`; 106 unit/contract tests.
The Music fixture used seven labelled synthetic albums and ten original generated
songs, a real Kodi scan, full ordered queue, playback clock advancing 588 ms and
return to the currently playing album. A private clocked PulseAudio null sink proves decoder/player
progress, **not audible sound**. Fixture data is not the user's catalogue and is
not bundled into the installable add-ons.

The earlier claim that no Kodi runtime had ever been exercised is obsolete.
These baseline results do not automatically validate subsequent RC source changes.
## Verified RC fresh-install acceptance

[Run 40801720239](https://github.com/JimBarnesly/Apeture/actions/runs/40801720239)
**passed** for exact source commit `296711243206a822caba7997b229a0c885a57384`:

- Started with stock Estuary and no preinstalled Aperture add-ons.
- Installed all three `1.0.0~rc1` packages through Kodi's native ZIP installer.
- Explicitly accepted Keep Aperture and verified the selection after restart.
- Opened the installed Games and Music companions.
- Explicitly accepted recovery to Estuary, then returned to Aperture.
- Verified the final restarted profile had Aperture selected and Unknown sources off.

This closes the desktop fresh-ZIP/accepted-switch gate for that exact head; it is
not inferred from copying an add-on tree into an existing profile. Counts and
package hashes are retained with the run's artifacts rather than guessed here.
Further source, harness or documentation commits require their own final CI run;
this record does not automatically attest a later commit or differently built kit.

An earlier harness crash was traced with GDB to the test observer calling
`Window.getControl` after the observed window was destroyed. That was an observer
lifetime error, not evidence of an installable-package fault. The passing run
uses the corrected observer. This diagnosis does not waive hardware acceptance.

## Build and provenance

Normal release build: `python tools/build.py` after the full test suite. The skin
is freshly materialized from pinned official Omega commit
`f8815ee40f49a700c047982d752be4b2a61420e2`, with retained license notices.
`APETURE_BUILD.json` records input/output content hashes and upstream identities.
`--skip-vendor` rejects changed source, removed/added inputs, legacy manifests and
modified assembled resources rather than silently shipping an old build.

The test kit comprises:

- `plugin.games.apeture-1.0.0~rc1.zip`
- `script.apeture.music-1.0.0~rc1.zip`
- `skin.apeture-1.0.0~rc1.zip`
- `checksums.json`, `README-INSTALL.txt`, `INSTALL_PI5.md`
- `installer/Prepare-Aperture.ps1` and `installer/README.md`: optional guided
  Windows ZIP verification/staging only; not one-click card provisioning.
  Windows execution, USB detection and physical imaging have not been accepted.
  Source tests are included in aggregate validation, not in the distributed kit.

The generated `checksums.json` is authoritative for the exact ZIP bytes; this
source document deliberately does not copy hashes that change after rebuilding.
Do not mix kits or infer a merge, stable tag or successful CI for any head other
than the explicitly identified evidence above.

## Hardware gates still open

Pi performance, actual audible output, controller and HDMI-CEC mapping, TV
scaling/overscan, real game-core/BIOS compatibility, network media reachability and
restart/recovery. Complete [TESTING.md](TESTING.md) with recorded results before
stable 1.0. Keep Estuary and a backed-up profile for recovery.
