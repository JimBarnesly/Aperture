# HDD music and movies

Aperture's **Music** home item opens the integrated Format library directly.
Format indexes the actual music folder; Kodi does not maintain a second music
source or offer a separate “local” versus “streaming” choice. Both the skin and
standalone Format use the same backend and library. See [Format integration](format-integration.md).

**Movies** and **TV shows** open their scanned libraries when present. With an
empty library, they open Kodi's video sources so unscanned files remain usable.
**Sources** always opens video files, including when a movie library exists.

## Add the actual HDD folders

Configure Format with the verified existing music folder. For movies, use
**Sources > Add videos** and browse to the drive Kodi actually shows. No label,
username, mount path or filesystem is assumed. Select the media folder rather than a whole
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
default. After the copy, scan and reconcile the existing Format library; no second import
destination or automatic upload is needed. Reconciliation identifies metadata;
it must not rewrite tags or acquire missing tracks in the protected Pi profile.

## Verification boundaries

Static tests cover routing, controller navigation, unavailable Format, generator
parity and the absence of drive assumptions or mutation commands. GUI runners
cover direct Format entry, Back/reopen, empty video libraries and the same
Format route after ZIP installation. These are separate from Pi
hardware, actual HDD access, controller and audio-output verification.
