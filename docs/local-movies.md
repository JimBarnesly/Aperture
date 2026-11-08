# Local movie browser

Aperture Movies opens the configured Kodi default video source, or the only video source, without an extra source chooser. If several sources exist and none is marked default, choose one explicitly; it never guesses a drive. Set a source as default through Kodi's native Files context menu. Existing Sources remains available on Home.

The browser reads one folder at a time, not a recursive whole-drive scan. A source pointing at the disk root will still show its subfolders: point the Kodi source at the actual movie folder if you want films immediately. Nothing changes source definitions, media files, mount policy or library metadata.

## Install

Exit Kodi first, use the normal Kodi desktop user, and use the complete matching checkout:

```
sh install-movies.sh
sh install.sh
```

Each stage preserves a backup under the Kodi profile's aperture-backups. Restart Kodi and enable Aperture Movies in Add-ons → My add-ons if needed. Home Movies then opens the new view. If the add-on is unavailable, Home retains native Kodi movie-library/source fallback. This update does not reinstall emulators, change saves, or reset the ROM folder.

## Artwork and information

Artwork is chosen in this order:

1. An explicit local poster choice made through the movie's context menu.
2. An exact existing sidecar (`Film-poster.jpg`, `Film-fanart.jpg`, or PNG variant).
3. Matched artwork already returned by Kodi.
4. Existing `poster.jpg` / `fanart.jpg` or PNG variants, only when the directory contains one movie file. A shared folder image is not assigned to several unrelated movies.
5. The original cinematic fallback. A video-frame thumbnail is not treated as a portrait poster.

Highlight a movie and open its context menu to **Choose local poster...**, or **Use automatic poster** to clear the choice. Choose an existing local JPEG, PNG or WebP. Only a small reference is stored in the add-on's Kodi profile, not beside the film; neither the picture nor the movie is copied, changed or deleted. Cancelling leaves the previous choice intact. Keep the chosen picture at its location. If it is moved or unavailable, normal artwork selection resumes. To replace cached picture contents immediately, choose an image with a new filename rather than overwriting the same image.

Sources with sharing disabled still use Kodi's local VFS without enabling sharing. That fallback has filenames and local artwork, not JSON-RPC library metadata. Browsing and choosing a local picture do not start a scan, make provider requests or export the collection. No made-up ratings, synopsis, runtime or genres.

## Automatic poster sourcing: next integration

This candidate improves local artwork correctness and manual correction. **It does not yet automatically source missing posters.** First inspect the device's existing scraper/library state read-only. Keep any ongoing pinned installation separate from this candidate.

The recommended first provider is Team Kodi's [The Movie Database Python](https://kodi.tv/addons/omega/metadata.themoviedb.org.python/) scraper from the official repository. It can populate the movie library with metadata and posters. Use an existing TMDB identifier where available; otherwise confirm title/year matches, especially remakes. A filename-only guess must not silently replace a known film identity. Unmatched films keep the fallback and remain playable.

Before an authorized scan, review the **source-specific** scraper settings. [Kodi documents](https://kodi.wiki/view/Add-on:The_Movie_Database_Python) that this scraper can also contact fanart.tv, IMDb and Trakt. For a TMDB-only first pass, turn off those extras and use TMDB poster/fanart settings. Approval must cover sending movie lookup titles/years or IDs to TMDB and downloading their artwork. Scan/database/cache changes belong in the Kodi profile; do not export NFOs or artwork onto the media drive. No new API credential is required by this local-poster candidate.

For selection, prefer a clear portrait poster for the confirmed movie in the chosen language, at a useful display resolution. TMDB's [default poster selection](https://developer.themoviedb.org/docs/image-languages) uses the requested language and falls back to the original language or highest-rated image. This is a useful starting point, not proof of an objectively best image. Keep a manual alternative: Kodi's [Information → Choose Art](https://kodi.wiki/view/Artwork/Changing) exposes other scraper results for library entries; Aperture's local choice remains available independently.

Acceptance still needs to verify that real library artwork reaches Aperture for the configured source, including sharing-disabled sources. Do not enable sharing just to expose metadata. If Kodi refuses those directory RPC results, add a read-only exact-path library lookup or retain local artwork; do not guess a match by filename alone. Test a small approved sample before a full scan, including two same-title films, missing art, offline browsing, manual correction and reset.

## Boundaries

Local files use existing source browsing and native video playback. Online Discover is described below. Network sources already configured in Kodi are supported by Kodi itself, and are not changed by this update. Optional Real-Debrid access is configured separately with explicit consent. Diagnostic errors deliberately omit source URLs, which can contain credentials. Physical Pi/video/audio/controller behavior still needs actual device validation.



## Online Discover (candidate)

Press Up → Discover to browse Cinemeta's public online movie catalogue, not just
films in the Kodi library. Search and genre controls follow the current view.
Online Collections offers Popular, Featured, and My Kodi library; local-library
collections remain available there. Local files still opens the existing drive.
Search/collection/genre cancellation does not navigate. Paging retains filters;
Cinemeta supplies no total, so the last More page can legitimately be empty.

Online cards show provider-supplied posters and synopsis. Select a card for
metadata details (year, genres, IMDb rating where provided and synopsis).
These cards are not playable and **availability is not checked**. Metadata is
not proof that a stream exists or that the user has access to it. There is no
stream resolver, torrent search, account signup, API key or Real-Debrid connection
in this catalogue adapter. The separate Real-Debrid connector can coexist via
Sources; neither adapter guesses a match between a catalogue film and a download.
See [Real-Debrid setup and privacy](real-debrid.md) for application ID, sign-in,
private storage and the remaining live-provider acceptance requirements.

### Provider and privacy

[Cinemeta's official public manifest](https://v3-cinemeta.strem.io/manifest.json)
advertises movie catalogue and metadata resources, not streams. Requests use
fixed HTTPS endpoints with an 8-second socket timeout, a 2 MiB response limit,
no redirects, no credentials and no cookies. Searches send only explicitly
entered search text and selected filters; details send the selected IMDb ID.
Kodi can fetch returned artwork from images.metahub.space or image.tmdb.org.
No local filenames, source paths, library entries or watch history are uploaded.
This is a public service with no availability guarantee, not a bundled licence
to redistribute its artwork or films. Metadata/artwork retain their owners' rights.

Local browsing remains usable when the catalogue fails. Nothing scans the drive,
updates Kodi library metadata, saves online searches, installs a scraper or
changes existing local poster choices. Provider failures are redacted.

### Verification

Focused tests cover catalogue query encoding/bounds, malformed/oversized data,
redirect refusal, artwork host restrictions, details identity, paging, cancellation,
stale navigation and metadata-only cards. A live public read-only search for
Metropolis returned 19 records and the matching tt0017136 details/poster on
2026-11-08. This proves the service/schema at that time, not future uptime.
The online screens still need native Kodi/controller visual acceptance; existing
local-library native smoke coverage does not prove online navigation or playback.
