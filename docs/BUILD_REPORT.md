# Development build 0.1.0

Built on 28 October 2026 for Kodi 21 Omega. This is a first development slice,
not a production-ready media-centre image.

## Completed checks

- 45 Python unit/contract tests passed: scanner, mocked Kodi adapter, package
  safety/determinism, authored Home focus links, fonts and native Games route.
- Python compile checks and XML parsing passed.
- Add-on identifiers, entry points, complete baseline windows, packaged fonts,
  custom Home textures and declared icon/fanart checks passed.
- Installable ZIPs built; checksum manifests and ZIP CRC/path checks passed.
- Repackaging identical assembled inputs produced identical ZIP SHA-256 hashes.
- Independent source review found and corrected native Games routing, unsafe
  package identifiers/hidden paths, ignored upstream-cache contamination, missing
  full license texts and a game-icon reference.
- The accompanying image was visually inspected as a **design preview** built
  from XML geometry and original art. It is not a Kodi screenshot.

## Not tested

No real Kodi runtime or Raspberry Pi was available for this build. Controller
focus, skin selection/revert, media OSD, actual game-core selection/playback,
network share behaviour and TV scaling remain hardware acceptance work.
Mocked Kodi API tests do not prove those behaviours on a device.

The skin is complete because its retained windows are assembled from a pinned
official Estuary baseline. Most non-Home screens still look like Estuary. The
Format-style album shelf and stream-receiver services are not implemented.

## Delivery and publication

The source archive contains authored code, tests, build recipes, provenance and
instructions. The two add-on ZIPs are the assembled install candidates. Install
the game-library package first. Source and build outputs have been prepared
locally; this report does not claim a GitHub push, PR, CI run or deployment.

Follow [TESTING.md](TESTING.md) on the actual device before using the build as the
default living-room interface. Keep the existing skin and back up Kodi's profile.
