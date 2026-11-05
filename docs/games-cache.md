# Persistent Games library candidate

This candidate is separate from the installed `fix/kodi21-startup` pin. It is not
installation permission or a claim of Raspberry Pi acceptance.

## User-visible behavior

- Games opens from a local saved library. Entering Games, entering a system,
  pressing Back, and selecting a cached game never start a media-tree scan.
- A separate Kodi service performs the initial index and later daily refreshes.
  Navigation never displays a scan/progress dialog. Explicit **Refresh library
  in background** queues work and leaves the saved list available.
- The older 0.1.0 game add-on never wrote a persistent index. Its first upgrade
  therefore needs one initial background index. A nonblocking preparation tile
  changes to the system selector when that index is published, provided that
  placeholder is still open. Leaving the screen does not restart the work.
- Snapshots are stored under the unchanged `plugin.games.aperture` profile, not
  inside the add-on or skin directory. Reboots and ordinary package updates do
  not invalidate them. Each configured source has its own hashed identity.
- A failed, cancelled or unreadable scan retains the previous complete snapshot.
  Automatic empty results cannot erase a populated library when a disk/share is
  absent. Manual refresh can confirm a genuinely empty library. Failed attempts
  retry after 15 minutes. OS locks prevent duplicate workers and release on crash.
- Publication uses flushed temporary files and atomic replacement. Share URLs and
  credentials are not written into cache contents or plugin navigation links.
- Launch validates the selected cached file and CUE members without enumerating
  its system. Removed files, path escapes and replaced symlinks fail closed.
  This is not a sandbox against simultaneous external filesystem modification.

## Add-on-only update and rollback

After reviewing the exact tested candidate and coordinating a stopped-Kodi
window, use its existing `tools/update_game_library.py` as the Kodi desktop user:

    python3 tools/update_game_library.py --kodi-home /absolute/path/to/.kodi

The updater refuses a running Kodi or root execution. It stages and validates
only `plugin.games.aperture`, preserves the prior add-on in `aperture-backups`,
and leaves the database, ROM-root setting, source files, BIOS, core installations,
core settings, save data and saved library untouched. It does not rerun the full
gaming installer or install any emulator. A separate skin update is required for
the new selector artwork; an add-on-only update still fixes foreground scans in
the currently selected skin. Estuary remains usable.

Restart Kodi normally after a coordinated update so its new background-service
extension is loaded. The initial index is read-only against the configured ROM
root. Do not erase the profile to force discovery. For rollback, exit Kodi and
restore only the prior add-on code from the reported backup. Preserve add-on data;
the older add-on ignores the new cache but resumes its older scanning behavior.

## Verification boundaries

Unit/adapter tests cover separate-process cache reuse; upgrade preservation;
source changes; repeated plugin entry; no foreground scan/dialog; selected-file
validation; interrupted/failed replacement; cancellation; unavailable media;
empty-mount protection; crash-released locks; daily/failed retry cadence; relative
credential-free storage; and atomic readers. The updater regression verifies
byte-preservation of real-location ROM-root settings, cache, core and save files.

The gaming CI candidate exercises actual Kodi service indexing, cached native
entry three times, horizontal Right/Left navigation, real synthetic game launch
and Stop, then normal Quit and a second Kodi process with the same profile. It
requires unchanged cache and scan-attempt hashes after restart and reentry.
Check the exact candidate run before treating these runtime checks as passed.
Synthetic desktop/ARM64 CI does not certify physical Pi power cycles, drive mount
timing, physical input, audible output or the user's real collection. A native
Kodi runtime is not installed in the editing workspace.
