# SYNTHETIC QA music — never a user catalogue

These seven albums and ten tracks exist **only** to test Kodi's native library,
Apeture's album-shelf rendering and ordered playback in a disposable CI profile.
They are never bundled into the skin or album-shelf release ZIPs.

- Every audio sample is a quiet, original mathematical sine tone (20 seconds,
  mono, 11,025 Hz, 16-bit), not a recording or commercial song.
- All artist, album and track tags identify themselves as **SYNTHETIC QA**.
- Every cover is original procedural geometry bearing **SYNTHETIC QA** and
  **NOT A REAL ALBUM**. No album covers were retrieved or copied.
- Seven albums test current/random focus and left/right order; “The Beacon” tests
  leading-article filing, and different years test chronological filing.
- The “Double” album contains disc 1 tracks 1/2 then disc 2 tracks 1/2. Deliberately
  reversed lexical filenames ensure filename sorting cannot accidentally pass.
- `expected.json` records actual metadata and SHA-256 audio hashes. Verification
  reads FLAC Vorbis comments directly, so normal CI needs no encoder or mutagen.

To regenerate from the original procedural source (requires ffmpeg and Pillow):

```sh
python tools/music_smoke_fixture.py generate
python tools/music_smoke_fixture.py verify
```

Regeneration records new expected hashes if the encoder version changes. Review
those changes as fixture changes. The fixture/code use the repository's
GPL-3.0-or-later license. The audio is not evidence of hardware sound output;
native CI can establish an active Kodi player and ordered queue only.
