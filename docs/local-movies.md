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

Uses metadata/art already returned by Kodi plus exact existing sidecar files (`Film-poster.jpg`, `Film-fanart.jpg`, `poster.jpg`, `fanart.jpg`, and PNG variants). Sources with sharing disabled are browsed through Kodi's local VFS without enabling sharing; that fallback uses filenames and local artwork rather than JSON-RPC library metadata. No automatic internet scraping or downloads. Files without artwork get an original cinematic fallback. No made-up ratings, synopsis, runtime or genres. For extensive library metadata, configure Kodi's ordinary scraper separately with the user's permission.

## Boundaries

This is local-source browsing and native video playback, not a Stremio or Real-Debrid implementation. Network sources already configured in Kodi are supported by Kodi itself, but no new remote source or credential is created. Diagnostic errors deliberately omit source URLs, which can contain credentials. Physical Pi/video/audio/controller behavior still needs actual device validation.
