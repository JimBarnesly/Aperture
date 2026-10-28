# Apeture

A modern, controller-first living-room interface for Raspberry Pi 5. The name
is deliberately **Apeture**. This is a native Kodi skin, not a web dashboard or
a retro-console simulation.

## Product commitments

- One interface for games, music and video.
- Games lists only systems that contain detected games.
- Keep game browsing and compatible game playback inside Kodi rather than
  starting the separate RetroArch application.
- Music should ultimately feel like a record shelf: album-centred Cover Flow,
  entering at a random album, inspired by Format.
- Longer-term audio and video receiving from Android, Apple devices and PCs.
- Optimistic early-2000s XBMC/Wii character, with original contemporary designs.
  Prior image concepts are inspiration, not a pixel-perfect implementation target.

## First slice

An installable Kodi 21 skin with original Home navigation and a companion
read-only local game-library add-on. Retain a complete upstream window/dialog
baseline so settings, media browsing, playback and skin rollback remain available.
Use RetroPlayer and compatible Kodi game add-ons for native playback. RetroArch
is a different frontend using libretro; it is not embedded by a skin.

The first package must not pretend to include streaming receivers, emulator cores,
BIOS files, ROM downloads, cloud services or a finished Format integration.
Games and metadata must not be fabricated to make the installed interface look full.

## Later slices

1. Test the initial packages on the actual Pi 5, LibreELEC/Kodi version and controller.
2. Refine systems, game artwork, navigation, playlists and verified core support.
3. Build the album shelf and random-entry behaviour, inspecting Format's actual
   architecture before deciding whether code or an API should be shared.
4. Specify and test receiver protocols as separate services/add-ons. A skin alone
   cannot guarantee AirPlay, Chromecast, Miracast, DRM or every source device.

## Open decisions

- Exact installed Kodi/LibreELEC version and available Pi 5 game cores.
- Actual ROM folder layout and required systems.
- Receiver protocols and audio/video handoff behaviour.
- Whether Format contributes interaction design, an API or reusable implementation.

Do not interpret a visible game file as proof that a compatible emulator core is
available. Keep original media untouched and expose empty/error states honestly.
