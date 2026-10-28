# Separate music smoke extension — integration hooks

The separate fixture/observer/driver files are now wired into the copied proven
main `ci_kodi_smoke.sh` on the Format branch using the **two explicit hooks**
below. The baseline Movies/TV/Files, dialogs, idle notice, game settings Cancel
and skin rollback assertions are retained; the former direct-Music assertion
now checks the new shelf route and its action into native Kodi Music. Its status
remains `not_run` until the resulting runner actually passes in Kodi 21.
No Kodi network RPC server, TCP audio listener, media download or user profile is involved.
The CI audio sink uses a private authenticated Unix socket only.

## 1. Prepare after guisettings, before starting Kodi

After the main runner writes its isolated `$KODI_DATA/userdata/guisettings.xml`
and before it launches the Kodi process, insert:

```sh
python3 "$ROOT/tools/music_smoke_fixture.py" prepare --runtime "$RUNTIME" --out "$OUT"
export APETURE_MUSIC_DRIVER="$ROOT/tools/music_smoke_driver.py"
```

`prepare` requires the existing runner's `apeture-kodi-smoke.*` mktemp tree,
checks the exact `system`/`data` relationships, validates actual fixture audio
metadata/hashes, copies the optional helper and labelled fixtures, and installs a
**test-only** in-process observer in that ephemeral system's add-on manifest.
It sets `musiclibrary.downloadinfo=false` only in the isolated fixture settings
to prevent metadata scraping. Existing network-service-off settings stay intact.
It prepares a clocked PulseAudio null sink with a fresh mode-600 authentication
cookie in a mode-700 directory under `$RUNTIME/pulse`, and selects
`PULSE:apeture_qa` only in that temporary Kodi profile. The main CI runner starts
an owned foreground PulseAudio process from the official Debian package, using
`-n` and only its private script: one authenticated Unix protocol module and one
clocked null sink. No TCP, hardware discovery modules, host instance, system
configuration or real output is involved; extra modules/sinks fail startup checks.
Client autospawn is disabled, and cleanup terminates only the saved process PID.
An existing audio configuration or mismatched HOME/runtime is rejected.
The initial music library remains empty; only an explicit test command scans the
fixture later. No production add-on service is introduced.

Normal CI needs no extra dependency: all FLAC/cover fixture bytes are committed
under `tests/fixtures/music`; only regeneration needs ffmpeg/Pillow.

## 2. Exercise after baseline round trips, before final success

In the main runner's existing inline Python GUI driver, after it returns Home
from its baseline checks and **before** its final log scan/result success, add:

```python
import importlib.util
spec = importlib.util.spec_from_file_location(
    "apeture_music_smoke_driver", os.environ["APETURE_MUSIC_DRIVER"])
music_driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music_driver)
music_checks = music_driver.run(out, focus, press, wait_for, screenshot, state)
checks.extend(music_checks)
```

The function uses those existing actual-X-keypress, actual screenshot and fresh
Kodi-state helpers. An exception must propagate to the existing CI failure path;
never catch it and retain a baseline pass. Include `music-result.json`,
`music-state.json`, `music-states.jsonl`, `music-error.json` (if any),
`music-expected.json` and `music-*.png` screenshots in the normal artifact.

Update the final top-level smoke scope to include the music result only after
`run` returns. Existing baseline assertions must still run and pass. The optional
music helper is required/enabled in this extended run; test missing-helper
fallback separately without changing the running test profile's add-on settings.

## Exact behavior checked

1. Genuine empty library → native shelf → native Kodi Music → Home.
2. Repeated empty shelf open/Back, with no stacked modal or playback.
3. `AudioLibrary.Scan` of the prepared local synthetic FLAC files through
   `xbmc.executeJSONRPC` **inside Kodi**, never an HTTP endpoint or SQLite write.
4. Seven albums read with actual tags; three valid random initial positions (repeats allowed) within the sorted
   shelf, all seven order positions, clamping at both ends, no browsing playback.
5. Explicit Enter on the two-disc fixture: actual native queue is `(1,1), (1,2),
   (2,1), (2,2)`, shuffle is off, active audio starts at disc 1 track 1 and its clock advances
   by at least 500 ms on that same track. The tones last 20 seconds each.
6. Back leaves that album playing; reopening focuses its actual album ID.
7. Only the fixture player is stopped at the end through the test-only observer.

Every fixture screenshot contains visibly labelled synthetic artwork/album
names. `music-result.json` records actual observed state, not manufactured
success. Empty/repeated UI checks alone do not imply the populated/playback checks
passed. No random-distribution assertion is made from a handful of openings.

## Audio and runtime limits

The configured sink is **discard-only clocked PulseAudio null**, named
`apeture_qa` on the private authenticated Unix socket. PulseAudio's official
[module-null-sink implementation](https://github.com/pulseaudio/pulseaudio/blob/v17.0/src/modules/module-null-sink.c)
uses the monotonic clock and timer pacing; the previous ALSA null fixture was
observed consuming four 20-second tracks in about two seconds and was rejected.
This test establishes **native decoding/player-clock progression and ordered
queue state**, not audible output or Pi audio. `music-audio-sink.txt`,
`pulse-sinks.json`, `pulse-modules.json` and the PulseAudio log record this boundary.

The playback assertion **must fail** if Kodi cannot create the player or its
clock does not advance by at least 500 ms on the first fixture track. The observer
records briefly absent startup item metadata as pending, not successful playback;
foreign paths/IDs still fail, and pending identity cannot authorize Stop. No
clock, queue, first-track or current-album focus assertion is relaxed.
Source tests and fixtures verify neither Kodi rendering nor physical sound.
This music extension is not Pi, gamepad/CEC, ZIP-install or network media-source
acceptance. The separate baseline checks still exercise automatic skin rollback.
No local native GUI run is claimed by these files.
