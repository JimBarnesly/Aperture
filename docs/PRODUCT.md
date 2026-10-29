# Aperture 1.0 scope

A native Kodi 21/Omega interface for Pi 5 / LibreELEC, authored at 1080p 16:9.
**1.0.0~rc1 is a release candidate, not stable hardware acceptance.**

## Included

- Original misty-bridge Home with quiet horizontal, controller-first navigation;
  restrained early-XBMC/Wii character, not a pixel-perfect historical recreation.
- Read-only Games companion: supported populated system folders only, honest
  empty/error states, native Kodi RetroPlayer dispatch. No standalone RetroArch.
- Original native Format-inspired album shelf over the real Kodi library:
  artist/year/title order, current-playing/random entry and ordered full-album play.
- Native Movies/TV/Music/Files/Settings and full pinned Estuary playback/dialog
  foundation. Most non-Home media screens intentionally retain Estuary styling.
- Deterministic add-on packaging, pinned provenance, content hashes, installation
  guidance, regression tests and desktop runtime evidence with stated boundaries.

## Explicitly deferred

Streaming receivers/protocols, Hermes and Home Assistant are outside 1.0.
No Format server or web dashboard is required. No ROMs, BIOS, emulator cores,
commercial catalogue, automatic metadata/art downloads or background services.
Format contributes behavior reference only; none of its code/assets/license is copied.

## Stable-release gate

Install the exact RC kit on the target Pi 5 test card/profile and complete
[TESTING.md](TESTING.md): fresh ZIP install, skin confirmation/recovery, physical
controller/CEC, TV scaling, audible music/video, native game/core return, restart
and representative populated libraries. Record LibreELEC/Kodi/core versions and
any failures. Desktop tests and mocked APIs cannot stand in for these results.
Do not silently promote an RC to stable because its version number changed.
