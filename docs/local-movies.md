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

This is local-source browsing and native video playback, not a Stremio or Real-Debrid implementation. Network sources already configured in Kodi are supported by Kodi itself, but no new remote source or credential is created. Diagnostic errors deliberately omit source URLs, which can contain credentials. Physical Pi/video/audio/controller behavior still needs actual device validation.



## Discover interface (candidate)

From the cinematic poster shelf, press Up for Discover, Search, Collections,
Genres, Local files and Sources. Discover reads the **existing Kodi movie
library**, with All movies, Recently added, Continue watching, Not watched and
Top rated collections. Search matches titles; genres combine with the selected
collection and search. Discover resets filters. Results are bounded to 60 per
page with a More movies card. Back returns through native Kodi directory history.
Search and collection cancellation never add a directory or replay an action.

Existing source browsing, playback and local poster choices are unchanged.
Library results retain native movie IDs and resume positions. Metadata is only
what Kodi already knows: no fabricated ratings, titles, or stream availability.
An empty library explains how to use Local files. It does not trigger scraping
or a whole-drive scan. This version does not automatically retrieve posters.

Real-Debrid is optional and starts disconnected. Sources offers explicit device
sign-in, existing account downloads and authorized link playback. See
[Real-Debrid setup and limitations](real-debrid.md). It is not a movie catalogue;
Discover/Search still use Kodi's existing library. No background access occurs.

Verification: focused tests cover paging, combined filters, resume metadata,
redacted failures, empty libraries, cancelled/repeated search, stale navigation,
collection/genre choices, focus links and preservation of local browsing.
The native Movies CI also exercises the navigation strip, empty-library guidance,
repeated keyboard cancellation, collection cancellation, Back and actual Kodi
filter schema acceptance. Populated library discovery and real provider playback
are not proven by that empty-library fixture. No device installation is included.
