# HDD music and movies

Aperture keeps one **Music** home item. Select it, or press Right, to choose:

- **Local music**: Kodi's music root, with Albums and Artists when scanned and
  **Files** for browsing your existing drives and adding a music source.
- **Format streaming**: the independent Format add-on and its configured server.
  This choice is disabled when the add-on is unavailable.

Left or Back returns from either choice to the Music home item. Local music
always opens the native root even if Format was the last music page visited.
Neither route copies music or creates another music database.

**Movies** and **TV shows** open their scanned libraries when present. With an
empty library, they open Kodi's video sources so unscanned files remain usable.
**Sources** always opens video files, including when a movie library exists.

## Add the actual HDD folders

Use **Music > Local music > Files > Add music** for music, and **Sources > Add
videos** for movies. Browse to the drive Kodi actually shows; no label, username,
mount path or filesystem is assumed. Select the media folder rather than a whole
mixed games/music/movie drive. For movies, set its content to Movies if you want
Kodi's scanned library. You can browse and play without a scan.

The OS must already mount the drive with read access for the Kodi user. This UI
does not format or mount disks, edit fstab, change permissions, move existing
sources, export metadata to media folders or start a scan automatically. A
disconnected drive can leave library entries visible but unavailable. Reconnect
it before updating; do not clean the library merely because the drive is absent.

## Copying music from another HDD

Syncing is a separate operation. Establish the exact source and destination
folders, free space, copy direction and handling of existing files first. Preview
an additive copy before running it. Do not use deletion or mirror options by
default. After the copy, update the existing Kodi music source; no second import
destination or automatic Format upload is needed.

## Verification boundaries

Static tests cover routing, controller navigation, unavailable Format, generator
parity and the absence of drive assumptions or mutation commands. GUI runners
cover the Music choice, Back/reopen, native local root, empty video libraries and
the separate Format route after ZIP installation. These are separate from Pi
hardware, actual HDD access, controller and audio-output verification.
