# Native CI pause failures — local candidate

Base: `c857deeaa53316d4de47da86afcb26bddbc44e14`; PR #31.
No push, deployment, device changes, live Kodi controls or account/profile access.

## Native evidence

Downloaded public Actions artifacts for runs `42804551458` (menus) and
`42804551586` (online). Their retained `logs/kodi.log` establishes two different
causes, not a timeout needing a larger budget:

- Menus: fullscreen movie exits to Home at **11:06:39.812 UTC**; audio stream
  pauses at **39.991**. After the Home screenshot at **42.259**, the harness's
  `player.pause()` toggles playback back on at **43.168**. Audio's earlier bar
  journey passed. Replace QA's toggle with explicit `Player.PlayPause play:false`,
  using player 0 for audio and 1 for video/episodes. Existing paused-bar,
  same-file, no-auto-resume, D-pad and stop checks remain.
- Online Resume: fullscreen initializes at **11:08:05.259 UTC** and Back
  deinitializes it at **05.287**. The movie spends only **28 ms** fullscreen,
  shorter than the independent service's **100 ms** polling interval. The service
  has no remembered fullscreen state when browsing returns. No service exception
  appears in the retained log. The previous normal-length playback completed,
  session-tag assertion passed, actual history persisted, and fresh Resolve /
  StartOffset Resume reached the requested position. This is the polling gap,
  not evidence that dialog 9999 is blocking Back or history privacy failed.

## Fix and boundaries

At build/source-install time, augment the inherited `VideoFullScreen.xml` with
an unload action that latches the current opaque `aperture_session` into a Home
window property. It runs only for movie video leaving for the existing browser
allowlist (`Window.Next`), not OSD, subtitles or seek overlays. Onload clears stale
signals. Existing upstream controls/actions remain intact. Kodi Omega source
confirms fullscreen calls the base window lifecycle, unload actions execute
synchronously, `$INFO` is expanded before the builtin, and `Window.Next` is set
before deinitialization.

The Movies service consumes the latch once, rechecks actual movie/playing state,
current browser and matching session, then uses the existing explicit pause.
If unload races the initial fullscreen sample, the signal is retained for the
next browser sample. Replacement sessions cannot inherit it. No URLs or history
rows are added to the signal. No global keymap or Format change is involved.

Polling remains the fallback for untagged library/local movies and skins without
the hook; their sub-poll exits remain a documented limitation. The short-exit fix
requires **both the rebuilt skin and Movies service**. Kodi's non-atomic final
ownership-check/Pause limitation remains unchanged.

Native QA retains its immediate Resume → Back assertion (no settling delay to
hide the bug), then adds return-fullscreen-stays-paused, explicit Play, OSD
open/Back, seek-stays-playing and second Back-pauses assertions before the
existing clear-history/privacy/suggestions acceptance. No skip or assertion
removal; no increased timeout.

## Verification

Observed focused RED → GREEN:

1. Menu setup resumed an already-paused movie → explicit idempotent pause.
2. Browser sample after a sub-poll exit sent zero pauses → session latch consumed.
3. Skin ZIP omitted native unload action → inherited window augmented.
4. Source installer omitted the same action → shared hook applied to staged skin.
5. Mid-sample unload was prematurely consumed → retain until nonfullscreen sample.
6. Native journey lacked transient/no-auto-resume checks → added checks while
   preserving adjacent fullscreen-ready and immediate Back.

Additional green coverage: stale/replacement session, transient/nonplaying
signal consumption, one-shot operation despite delayed paused state, exact
movie/session/browser gates, idempotent skin patch and preserved controls.

Full suite: **835 tests passed**, loopback-only network namespace:

```
unshare --user --map-current-user --net --keep-caps sh -c \
  'ip link set lo up && exec python3 -m unittest discover -s tests -q'
```

A real skin build and ZIP validation against the installed distribution Estuary
succeeded in scratch, with inherited fullscreen controls preserved. Only the
source was read; nothing was installed. `git diff --check` passed.

**Native rerun pending**: Xvfb, pulseaudio and pactl are unavailable locally;
no packages were installed. Parent must independently review, publish the exact
candidate when authorized and require both native workflows green before any
deployment. Offline tests and inspected native failure logs are not a native
GREEN result. Physical Pi/controller acceptance remains separate.
