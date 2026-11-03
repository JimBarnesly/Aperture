# Music-first implementation and acceptance plan

## Skin baseline

The custom Estuary Home.xml crashed Kodi 21.3 after font load. Do not activate that experimental XML. Install the official Kodi 21 Confluence skin through Kodi's official repository and verify it independently. The `install-confluence-baseline.sh` script clones its known-good XML, fonts and media into `skin.aperture` without changing Home.xml. **This baseline has not been run on the target Pi yet.**

Tests: (1) Confluence activates, (2) Aperture clone activates, (3) navigation and music playback, (4) exit and restart, (5) return to Estuary. If a test fails, stop; do not overwrite the known-working skin.

## Format architecture

Source: `JimBarnesly/Format`. Format is a Node.js 22+ music server; its API exposes `GET /api/library`, `GET /api/cover?id=...`, and `GET /api/audio?id=...` with byte-range support. Format's existing library and acquisition features should remain on the server. The Kodi plugin is a read-only HTTP client, not a copy of the full Format service.

Target user experience: browse artists/albums by cover, open a complete release, play the full ordered track list, show now-playing metadata and cover art, and resume navigation with a remote. Do not expose acquisition/deletion operations in the TV interface.

Initial Kodi client source: `format-kodi/`. Install via `install-format.sh`. Configure server URL to a reachable host. The original deployment address `192.168.68.60:4534` may not be reachable on the new network. Verify `curl http://SERVER:4534/api/library` from Pi before debugging Kodi.

Acceptance: albums display; artwork resolves; track streams play; album queue preserves track order; phone can control play/pause/skip via Kodi's JSON-RPC and Kore. **Not yet verified on the Pi.**

## Phone control

Enable Kodi Settings > Services > Control > Allow remote control via HTTP (use authentication) and allow remote control from applications on other systems. Kore can browse Kodi's library and control playback. This does not make Kodi a certified Google Cast receiver.

## YouTube Music

Keep distinct from Format. YouTube Music does not natively cast to generic Kodi/UPnP. Test an independently maintained Kodi YouTube Music add-on as an in-Kodi browsing source, but do not promise phone Cast support. Alternative is a separate certified Cast receiver; Bluetooth is fallback only.

## Deferred

RetroPlayer systems, game artwork and automatic ROM indexing are deferred until the music experience is stable.
