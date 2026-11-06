# Aperture Game Library

A read-only Python game-source add-on targeting **Kodi 21 Omega**. It puts a
folder-organised game collection into Kodi's native Games window and hands
playback to **RetroPlayer and Kodi game add-ons**. It does not start or embed the
standalone RetroArch application.

This is a first foundation, not a tested device/core compatibility matrix. A
file appearing in the library means its **folder and extension were recognised**,
not that its contents, BIOS, emulator, or host device have been validated.

## Try it in a disposable Kodi profile

1. Install the separately packaged `plugin.games.aperture` ZIP using Kodi's
   **Add-ons → Install from zip file**. See the repository README for the build
   command. You can use this add-on with any skin that supports Kodi Games.
2. Open **Games → Game add-ons → Aperture Game Library**.
3. Select **Choose your ROM folder…** or **Configure library…**. Set **ROM root
   folder** to a folder containing the system subfolders below.
4. Supply your own legally obtained game files. Keep BIOS/firmware outside the
   scanned system folders and configure it according to the selected Kodi core.
5. Open a detected system, select a game, and use Kodi's native emulator chooser.
   If there is no compatible available core, Kodi reports that. Kodi may offer
   to install a game add-on; Aperture neither silently installs cores nor
   downloads ROMs, BIOS, covers, or metadata.

You can back out of settings, disc selection, or Kodi's emulator chooser without
a fallback launch. Opening Games or a system reads a saved local library and
never scans the media tree or displays a scan dialog. A separate quiet service
builds the initial library and refreshes it at most once a day. **Refresh library
in background** requests an earlier refresh without blocking browsing.

Snapshots live in Kodi's add-on data profile, not inside the skin or add-on code.
They survive ordinary skin/add-on updates, Kodi restarts and machine reboots.
The last complete snapshot remains usable when a drive/share is unavailable or
an update is cancelled. Publication uses an atomic, flushed replacement;
concurrent workers cannot publish over one another. A missing/empty mount cannot
erase a populated snapshot, even on manual refresh. An empty result retains the
saved list and offers a separate review action. Only confirming **Clear saved
list** there clears the index when you know the source is intentionally empty.
No game files are deleted. Cancelling retains the list. Failures are retried after 15 minutes, independently of menu
entry. Changing the configured ROM root selects a separate snapshot. The initial
index appears automatically if its first-run placeholder is still on screen.

Cached paths are relative to the configured source, so SMB credentials are not
copied into snapshot files or plugin links. Only the selected file and its CUE
members are checked at launch; opening or launching a game never rescans the
whole system. Actual game/core/BIOS compatibility still belongs to Kodi.

## Folder convention

Only immediate child folders of the selected root identify a system. Recognised
folders are searched recursively; arbitrary category folders above them are not.
Folder aliases and file extensions are case-insensitive. Titles come from the
filename without its extension. Other file names and descriptor references retain
their exact case. No content sniffing, filename heuristics, or metadata scraping
is performed.

```text
ROMs/                    ← select this folder
  nes/
    Example Homebrew.nes
  snes/
    Homebrew/Example.sfc  ← nested game folders are supported
  psx/
    Example Set.m3u
    discs/
      Disc 1.cue
      Disc 1.bin
      Disc 2.chd
```

| Folder | Optional alias | Discovery extensions |
| --- | --- | --- |
| `nes` | — | `.nes .fds .unf .unif` |
| `snes` | — | `.sfc .smc` |
| `gb` | — | `.gb` |
| `gbc` | — | `.gbc .gb` |
| `gba` | — | `.gba` |
| `n64` | — | `.n64 .z64 .v64` |
| `megadrive` | `genesis` | `.md .gen .smd .bin` |
| `mastersystem` | `sms` | `.sms` |
| `gamegear` | `gg` | `.gg` |
| `pcengine` | `pce` | `.pce .sgx` |
| `atari2600` | — | `.a26 .bin` |
| `psx` | `ps1` | `.cue .chd .iso .pbp .exe .m3u .m3u8` |
| `arcade` | — | `.zip` |

Aliases combine under one system. Unknown folders, root-level files, hidden entries, and unrelated extensions are omitted. `.bin` in
`megadrive` is a cartridge candidate; `.bin` in `psx` is a disc sidecar and is
never a standalone game. Archives are not expanded or searched; `.zip` is only
listed under `arcade`, where ROM-set/core-version requirements still apply.
Other platforms and archives are intentionally outside this initial catalog.
Child names containing path separators, `:`, `|`, `?`, `#`, control characters,
or encoded traversal are conservatively omitted to avoid VFS interpretation.

The root shows **recognised system folders immediately**, plus clearly labelled settings
and playback-help actions. Game entries are enumerated only when a system is opened.

## CUE and multi-disc handling

- A CUE is listed only when it has valid `FILE` entries and every referenced file
  was found within the same system folder. Referenced tracks are not double-listed.
- UTF-8 (including BOM) `.m3u` and `.m3u8` files may group supported PlayStation
  disc entries. Blank lines and `#` comments are ignored; relative subfolders and
  Windows-style separators are accepted. Repeated entries are deduplicated.
- All playlist members must exist and be recognised candidates. A valid playlist
  replaces its individual disc entries with **one game entry**. Broken, empty,
  unsafe, oversized, or nested playlists are skipped without suppressing valid
  independent discs. CUE/M3U references must match actual filename case exactly.
- Selecting a grouped game opens a **disc picker**; the chosen `.cue`, `.chd`,
  `.iso`, or `.pbp` goes to RetroPlayer. This does **not** claim seamless runtime
  disc switching or native M3U loading. Kodi Omega classifies M3U as a media
  playlist, so directly resolving one would use the wrong playback path.
- Absolute paths, network/URI references, paths outside the same system folder,
  encoded traversal, and nested playlists are rejected. No files are rewritten.

Example `Example Set.m3u` for the tree above:

```text
#EXTM3U
discs/Disc 1.cue
discs/Disc 2.chd
```

## Local files, VFS, and safety boundaries

Local absolute paths, local `file://` URIs, translated Kodi `special://` paths,
and existing Kodi-accessible `smb://` / `nfs://` shares are accepted. HTTP,
plugin, archive, and other virtual roots are rejected. No additional network
service or credential configuration is introduced. Configure share access in
Kodi, not in this add-on.

Local child symlinks are skipped and real-path containment is checked before
descent and descriptor reads. Kodi's portable VFS API does not expose remote
symlink/realpath checks: SMB/NFS confinement is **lexical**, bounded by depth and
entry limits, not a security sandbox for an untrusted share. A provider may also
return an empty list for an access failure; check permissions/connectivity if a
known collection appears empty. Core support for network files is independent
of the scanner; local storage may be required for playback.

Scans stop explicitly at **32 levels beneath a system folder**, **100,000 listed
entries**, or user cancellation. Descriptors have a **256 KiB read cap**. Scan
limits fail visibly rather than publishing a partial result; unreadable
subfolders and invalid descriptors produce a warning and preserve other games.
Cancellation closes progress and terminates the pending Kodi callback. Slow
provider I/O can delay cancellation until the current VFS operation returns.

This is a normal read-only application, not a defence against concurrent hostile
filesystem mutation. Playback validates the selected file and descriptor members, but files can still
change between discovery and Kodi opening them. Use trusted game collections.
Logs contain counts/error types, not ROM paths, filenames, or share credentials.
Plugin URLs/favourites carry only a SHA-256 path identity; no caller-supplied
filesystem path is ever resolved directly. No shell command is constructed.

## Native Kodi contract

`default.py` imports the thin adapter in `resources/lib/apeture_library/kodi.py`.
The scanner/catalog have no Kodi imports and no third-party Python dependencies.

- `xbmc.python.pluginsource` declares `<provides>game</provides>`.
- Listings use `xbmcplugin.setContent(handle, "games")`.
- Game launch actions are folder items with `IsPlayable=false` and disabled
  content lookup. They deliberately have no GameInfoTag, so Kodi's context-menu
  Play action cannot mistake an action folder for a playable game archive.
- Selecting one validates the cached target, handles any disc choice, closes the directory
  action, and calls `xbmc.Player().play(real_path, listitem)` with a playable game tag.
  This is intentional: Kodi 21's plugin resolver retains the plugin URL as Path
  while RetroPlayer requires the real ROM Path. `setResolvedUrl` is not used.
- No synthetic `application/x-game` MIME type, external-player parameter,
  `RetroArch` command, or hard-coded `gameclient` is used.
- Kodi performs native core selection and owns missing-core / install / enable
  dialogs. Its candidates are extension/VFS based, **not filtered by our system
  label**. For overlapping extensions, choose the core for the actual system.

Skin-facing custom properties are `Aperture.System`, `Aperture.GameCount` (system
items), `Aperture.DiscCount` (game items), and container property
`Aperture.LibraryState` (`unconfigured`, `empty`, `ready`, `error`, `cancelled`).
They are presentation metadata, not invented Kodi playback parameters.

Official API/source references checked against Omega:

- [Omega plugin APIs and games content](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/legacy/ModuleXbmcplugin.h)
- [Omega ListItem API](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/legacy/ListItem.h)
- [GameInfoTag setters, added in Kodi 20](https://xbmc.github.io/docs.kodi.tv/master/kodi-dev-kit/group__python___info_tag_game.html)
- [Omega game item recognition](https://github.com/xbmc/xbmc/blob/Omega/xbmc/FileItem.cpp)
- [Omega Games window](https://github.com/xbmc/xbmc/blob/Omega/xbmc/games/windows/GUIWindowGames.cpp)
- [Omega native core selection and errors](https://github.com/xbmc/xbmc/blob/Omega/xbmc/games/GameUtils.cpp)
- [Omega plugin resolution and playback](https://github.com/xbmc/xbmc/blob/Omega/xbmc/application/Application.cpp)
- [Omega M3U playlist classification](https://github.com/xbmc/xbmc/blob/Omega/xbmc/playlists/PlayListFactory.cpp)
- [Omega VFS directory and special-path APIs](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/legacy/ModuleXbmcvfs.cpp)
- [Official settings format](https://kodi.wiki/view/Add-on_settings_conversion)

## Verification

From the repository root:

```sh
python -m unittest discover -s tests -p 'test_game_library*.py' -v
python -m compileall -q games-kodi
```

Fixtures are synthetic empty files and text descriptors, never redistributed
ROM/BIOS data. Tests cover discovery, aliases, overlapping extensions, malformed
descriptors, traversal, symlinks, VFS URI preservation, bounded scans, cancellation,
native item/launch calls, stale links, settings interruption, and disc-picker
cancellation. Mocked Kodi tests verify our API contract; they **do not validate
actual Kodi rendering, emulator availability, controller input, or emulation**.

Before release, test on real Kodi 21: install ZIP, select/cancel/change root,
navigate populated/empty/error views, scan/cancel, launch a lawful homebrew ROM,
exercise missing/multiple cores, exit RetroPlayer back to the same list, and
select/cancel a multi-disc game. No Kodi runtime is assumed by the unit suite.

License: GPL-3.0-or-later; see the bundled `LICENSE.txt` and repository `LICENSE`.

### Large HDD collections

Opening the library reads the saved local snapshot, without enumerating the ROM
root or reading CUE/M3U files. Only populated systems and their cached game counts
appear. The first full index and later daily refreshes run quietly in a separate
service, so a new installation can briefly show a nonblocking preparation tile.
Backing out does not cancel that service or force another scan on the next entry.
A Kodi shutdown cancels before publication and retains the previous snapshot.
A blocked filesystem call can still delay shutdown; the add-on does not forcibly
unmount disks. Real Pi/drive latency and power-cycle acceptance remain separate
from isolated CI.


### Drive identity before removing saved entries

Removing any cached game/disc requires a verified, unchanged local source before
and after the scan, including nested mounts. An unverified or changed source
retains the saved index with a visible status. Legacy indexes without recorded
identity and network/FUSE/unsupported sources remain deletion-protected; an
empty response is never proof that a drive is connected. See
[`docs/games-cache.md`](../docs/games-cache.md#removal-guard) for limits.
