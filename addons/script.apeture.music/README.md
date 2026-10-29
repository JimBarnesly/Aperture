# Native album shelf — 1.0 release candidate

The optional **Aperture Album Shelf** is a native Kodi 21 Python/WindowXML add-on,
not a browser embedded in Kodi. The scenic Home's Music destination runs it when
`script.apeture.music` is enabled. Without it, Music continues to open Kodi's
native album library or music sources. Games, other Home routes and inherited
settings/playback windows are unchanged.

## Interaction

- Read the albums already indexed by Kodi with `AudioLibrary.GetAlbums`.
- Sort by album artist (ignore a leading “The”, case-insensitively), then year,
  title and database ID. Unknown years sort before dated releases. No sort is
  delegated to an online catalogue or inferred from a folder name.
- Start at the currently playing album's **database ID** when present. Otherwise,
  pick a random starting position **without shuffling the ordered shelf**.
- Left/right move one record, clamped at the beginning/end. The selected cover is
  prominent; six neighboring covers are smaller, muted and gently perspective-rotated.
  Below-cover arrow buttons show the shelf boundaries without covering the art.
- OK/Enter on **Play album**, or a controller's Kodi Play action, reads that album's
  songs and replaces Kodi's current music queue in disc/track order. This disables
  music-queue shuffle for ordered playback. A visible hint beside Play explains
  both effects before activation. It does not alter the shelf's order.
- Up/down reaches Kodi Music, Refresh and Home. Back/Escape closes the shelf,
  returning to its caller; Home explicitly returns Home. Browsing/closing never
  stops, starts or replaces playback. Refresh reloads the library and applies the
  current-playing/random focus rule if the selected record is no longer present.
  Otherwise Refresh preserves the record being browsed; opening a fresh shelf
  still uses the current-playing/random rule.
- An empty library explains how to add/scan music in Kodi. A read failure exposes
  Refresh, Kodi Music and Home, not a fake catalogue. A failed/empty/incomplete album read
  does not clear an existing queue. Cue/shared-file albums are directed to native
  Kodi Music rather than replaying an entire file for each cue track.

The seven visible slots are original Kodi image controls bound to window
properties. A native button holds the shelf focus, with self-targeting horizontal
navigation; Python handles one left/right step after Kodi handles focus. This
avoids container selection races and arbitrary fixed-delay focus initialization.
No album is selected until the complete library snapshot is loaded.

## Install and build

```sh
python -m unittest discover -s tests -v
python tools/build.py
```

The build produces these independent packages:

- `dist/skin.apeture-1.0.0~rc1.zip` — assembled pinned Estuary foundation plus scenic
  Home and the enabled-companion Music route.
- `dist/script.apeture.music-1.0.0~rc1.zip` — self-contained album-shelf script/XML.
- `dist/plugin.games.apeture-1.0.0~rc1.zip` — native game companion.

On a backed-up Kodi 21 test profile, install the album-shelf ZIP through Kodi's
normal add-on UI and install/select the assembled skin. The helper has no forced
skin dependency; its bundled fallback XML uses the existing Omega Estuary fonts.
The scenic backdrop is used only when the active skin is Aperture. Other skins
without these standard font names are not a compatibility claim.

Installation does not enable unknown sources, add media sources, scan the library
or install a music scraper. Those are explicit user actions in Kodi. No account,
Node process, web server, HTTP JSON-RPC endpoint or background service is needed.

## Privacy and media boundaries

- JSON-RPC goes through `xbmc.executeJSONRPC` **inside Kodi**. There is no socket,
  HTTP request, downloader, telemetry, credential store or catalogue export.
- The helper writes no media files, database tags or source settings.
- To avoid artwork-triggered network requests, only local artwork and explicit
  local cache paths are displayed. `image://` wrappers around local artwork are
  preserved, including Kodi’s native `image://music@...` embedded-art URLs;
  HTTP(S), SMB/NFS and UNC artwork use an original record placeholder. Missing or
  unreadable local artwork also falls back to that placeholder.
  A remote artwork URL is not assumed cached merely because Kodi knows its URL.
- **Explicit playback** preserves the exact file/URL returned by the user's Kodi
  music library. Kodi, not this helper, opens that source. Configured network
  music sources may therefore use the network when the user selects Play.
- There are no helper log calls. Failure dialogs omit exception strings, source
  paths, URLs and credentials. Kodi itself retains its own normal logging rules.
- Album and track titles come from the real library. Missing tags get plain
  “Unknown artist”/“Untitled album”/“Untitled track” labels, never invented metadata.
- Artwork bundled with this helper is simple original procedural UI artwork;
  no commercial album covers or catalogue data are bundled.

## Format relationship and source evidence

Format was examined for **behavior**, not copied into this repository:

- Reference revision: `48ce2518341644a44bb36714347fa20416a160eb`.
- [Album behavior reference](https://github.com/JimBarnesly/Format/blob/48ce2518341644a44bb36714347fa20416a160eb/public/app.js#L421-L583).
- Perspective/selected-cover visual behavior was also used as a design reference.

No Format server, JavaScript, CSS, downloader, assets or licensing statement is
imported. Format's repository did not present a license at inspection; ownership
is not treated as permission to silently relicense its contents. The helper is
an original implementation under GPL-3.0-or-later. The skin Home route remains
GPL-2.0-or-later and the inherited skin's licenses remain intact.

Kodi 21 APIs and control behavior were checked against primary sources:

- [Omega JSON-RPC 13.5](https://kodi.wiki/view/JSON-RPC_API/v13.5): album properties
  use `artist`, not `albumartist`; song properties include `disc`, `track`, `file`;
  `Player.GetItem` supports `albumid`.
- [Pinned WindowXML implementation](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/interfaces/legacy/WindowXML.cpp):
  active-skin/fallback XML lookup, texture lookup and action/click callbacks.
- [Pinned Window implementation](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/interfaces/legacy/Window.cpp):
  window properties, focus and explicit Python Back handling.
- [Native navigation cycle handling](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/guilib/GUIWindow.cpp#L951-L985):
  centre-button self-navigation does not double-step.
- [Native rotatey implementation](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/guilib/VisibleEffect.cpp#L249-L285):
  conditional fixed-angle perspective. The `rotatey` centre is X,Z, not X,Y:
  use explicit zero-depth pivots, not `center="auto"` (which supplies screen Y).
  See also the [rotation matrix implementation](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/utils/TransformMatrix.h).
- [Playlist API](https://github.com/xbmc/xbmc/blob/f8815ee40f49a700c047982d752be4b2a61420e2/xbmc/interfaces/legacy/PlayList.h):
  `clear`, `add`, `unshuffle`; Player uses `play(playlist, startpos=0)`.
- [Music tag API](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/legacy/InfoTagMusic.h):
  native song ID, album/artist, disc/track/duration setters.

## Design preview

`python tools/preview_music_shelf.py` creates
`build/apeture-music-shelf-design-preview.png` from the shelf XML geometry,
packaged font outlines, actual scenic backdrop and original placeholder artwork.
Its synthetic names, covers and permanent banner explicitly label it a **design
preview, not a Kodi runtime screenshot**. Perspective is approximated by the
preview renderer, not proof of native rotation or focus behavior.

## Verification status and acceptance

**Previous baseline verified:** the pre-RC build at `4e95d006` passed 106
unit/static checks and 45 actual Kodi GUI/Music checks in
[run 40695502466](https://github.com/JimBarnesly/Apeture/actions/runs/40695502466).
That includes native WindowXML, empty/repeated entry, a real scan of seven
explicitly synthetic albums, exact ordered browsing/queue construction, advancing
playback and current-album focus after reopening. No user's music was involved.
The disposable CI profile used a private, authenticated Unix-socket **PulseAudio
clocked null sink**: decoded playback was discarded, not sent to real speakers.

**RC changes require a fresh runtime pass:** corrected cover-rotation pivots,
readable neighbors, queue/shuffle hint, Refresh selection retention and more
specific shared-file recovery have unit/XML contracts; the prior runtime pass
must not be presented as proof of this changed layout. Current release evidence
belongs in the repository's release report, not a stale fixed test count here.

**Still separate acceptance:** actual Pi performance, physical controller/HDMI-CEC,
audible audio, network source reachability and real user media. Unit mocks and
source review do not establish those. A clean native ZIP-install test is being
added separately; use its result, not copied add-on folders, as installation
evidence. Details and headless audio boundaries are in
`tools/MUSIC_SMOKE_INTEGRATION.md`.

Native acceptance checklist:

1. Empty library: open from Home Music; verify readable empty text, Refresh,
   Kodi Music, Home and Back; repeat entry/exit without stacked windows.
2. Labelled synthetic test library: scan owned/generated media with seven albums,
   a leading-“The” artist and a two-disc album. Verify actual ordering and visible
   perspective; screenshots must say fixture data, not the user's catalogue.
3. Reopen while a fixture album is playing: verify database-ID focus. Stop and
   reopen repeatedly: verify valid initial positions with unchanged shelf order (random repeats are valid).
4. Move left/right rapidly and at both ends; OK starts one complete ordered album,
   not a duplicate queue. Verify paused/current player transitions and Play key.
5. Check missing art, long Unicode titles, unreadable sources, queue protection on
   failed reads, repeated Refresh and player continuation after Back/Home.
6. Check missing/disabled helper: Home still reaches native Kodi Music.
7. Only after the desktop checks, validate Pi/controller/audio/720p/1080p behavior.

Known first-slice limits: cue/shared-file albums require native Kodi Music;
no inertial animation, gestures, artist jump/search,
track picker, queue editor or receiver protocol. Album loading is a synchronous,
paged local library snapshot; very large libraries may take time. Only seven
images are shown, and no song list is loaded until Play. The previous queue is
replaced only after songs and list items have been prepared; an unusual Kodi API
failure during queue construction itself cannot be made transactional by the
Python playlist API and is reported rather than called successful.
