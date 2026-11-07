# Native music now playing

Aperture's music player now uses a native Kodi turntable presentation. The
record displays actual current-track artwork, with a local fallback when art is
missing. It rotates during playback, stops on pause, and shows current metadata
and progress. Kodi remains the sole audio player; Select opens its existing
music playback controls. No browser, second player, network-facing service or
background library scan is added.

Selecting an album plays the complete ordered release and opens the turntable
after the requested stream starts. **Browse tracks** is available in the album
context menu; **Play album** remains there too.
The short wait is bounded to five seconds and gives up if the user changes
windows/folders or opens a dialog. A presentation error does not stop playback.
Back returns to browsing without touching the queue. **Now playing** reopens it
from the album shelf (Down) or track list (Right). Individual track selection
retains direct native stream URLs, so automatic queue advances never reopen the
presentation while the user is browsing. The button is available for any audio.

This ports the standalone visual concept, not its browser runtime. It does not
implement the web UI's card-to-disc morph or timed return after browsing.

## Verification

Unit tests check native player bindings, bounded presentation/navigation guards,
packaging, artwork masks and deterministic generated textures. The isolated
real-Kodi workflow checks full-resolution screenshots, changing record pixels
while playing and stable record pixels while paused, playback controls, Back,
reopening without changing position/queue, next/previous, missing artwork and
selected-track playback. The native ZIP phase selects **Exit** from the actual
power menu, requires the original process to exit with status 0, then relaunches
the same profile. Forced termination is only failure cleanup, never acceptance.

The workflow uses X11/GLX software rendering, synthetic loopback media and a
discard audio sink. It does not establish physical Pi Wayland/Labwc, HDMI/audio,
controller or black-display recovery. Keep those acceptance gates separate.

## Coverflow shelf candidate

The album shelf now uses a native centered fixed list rather than a flat panel.
The selected cover stays in the middle; neighbouring covers are smaller, dimmed
and angled toward it. Left/Right, parent-folder navigation, context menus and
Now playing remain owned by Kodi. A one-based display position is client-only
presentation metadata and does not alter Format's library or playback queue.

Album selection restores the original Format controller behavior: Enter plays
the centred complete album and opens its turntable. The historical reference is
Format commit db10318d9171cae0e6fb0e04d8aa1f2104b2b087 (9 August 2026),
public/app.js playSelectedLibraryAlbum and the Coverflow key handler. The old
Kodi route opened tracks, so a track-list screenshot without a record was not
evidence of an animation failure. Browse tracks remains an explicit context
action. This candidate does not yet port random initial selection, the browser
card-to-disc morph, or its 30-second idle return. Native CI adds a six-release synthetic shelf capture
and forward/reverse navigation checks; physical Pi and visual parity with the
standalone Format interface require separate acceptance.
