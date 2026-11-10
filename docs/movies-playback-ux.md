# Movies playback UX — bounded local slice

## Provenance and scope

Base: `9d99d02117f025e36325a6c76f4d197ec4abb46a`. Before branching, all
14 tracked `movies-kodi/` files matched deployed Movies bytes, with no extra
non-bytecode files. Work is isolated on `feat/movies-playback-ux`; no installed
add-ons, user settings, accounts, media or other worktrees were changed.

The user's clarification narrows removal to repeated authorized-content/rights
warnings, not blanket removal of provider-effect consent. Exact flow:

- First-time RD permissions, storage and separate Torrentio access-token sharing
  consent remain unchanged, including decline/Back paths and disconnect prompts.
- Once native or imported provider opt-in exists, explicitly choosing **Find
  streams** performs lookup without the redundant sharing/rights confirmation.
  No opt-in still gives the setup error; browsing metadata does not query Torrentio.
- Source selection remains explicit. **Play selected source?** remains because
  existing opt-in covers sharing, not a blanket consent to account mutations.
  It discloses RD history, queued transfers, traffic and signed-URL logging, but
  drops the repeated “Only play content you have permission…” sentence.
- Manual RD link entry uses neutral wording; its traffic/history confirmation
  remains, with only the repetitive rights sentence removed.
- Cancellable progress, all errors, no automatic mutation retries, source
  revalidation and token refresh/disclosure guards are unchanged.

The later request for automatic best-source playback, history and suggestions is
**not implemented in this slice**. Parent integration should introduce a separate
one-time automatic-play preference explaining resolver history/queue/traffic
before removing the retained effect confirmation; the sharing marker alone must
not silently acquire that meaning. No history is newly collected here.

## Pause policy

Movies owns an independent `xbmc.service` entry point, `playback_service.py`.
Format's existing shelf service was inspected but is neither imported nor edited.
No keymaps, persistent preferences, music idle behavior or games are changed.

Every 100 ms, sample the underlying native window (not the focused dialog).
Arm only after playing movie video is observed in fullscreen video (12005).
On transition to Home or native media browsers (10000, 10001, 10002, 10025,
10500, 10501, 10502, 10800), send one explicit video-player pause:
`Player.PlayPause {playerid: 1, play: false}`. Never use a toggle.

- Video + movie content + playing gates exclude audio/music, games and non-movie
  video. Movies local files and RD/Torrentio playback handoffs now supply movie
  media tags; native Kodi library movies already supply them.
- Fullscreen OSD, seeking and subtitle dialogs do not count as leaving video.
  Unknown windows do not trigger pause. Transient samples preserve the arm.
- Starting playback while browsing does not immediately pause it. Stopped/paused
  or non-movie playback disarms. Returning fullscreen never resumes automatically;
  explicit Play remains the user's path. Playback teardown exceptions disarm
  without logging private player details or retrying uncertain commands.
- This is an in-Kodi fullscreen-to-browser policy, not OS window occlusion or
  TV power detection. Custom windows outside the allowlist are deliberately not
  guessed. A transition shorter than the sampling interval can be missed.

## TDD and verification

Baseline command `python3 -m unittest discover -s tests -q`: **734 passed**.
Observed RED before implementation for configured lookup without repeated consent;
retained account-effect Play confirmation after the clarification; movie tagging
in local/Torrentio/RD paths; neutral manual-link wording; service existence,
non-movie gates, transient windows, loop/manifest wiring, transition state reset,
player teardown handling, and the native QA journey's removed lookup prompt.
Each slice was then rerun GREEN. The teardown RED was the expected injected
RuntimeError (not a typo/import failure).

Final regression command `python3 -m unittest discover -s tests -q`:
**747 passed**, zero failures/errors. Installer-test messages refer to disposable
scratch profiles, not the user's Kodi. Native QA harness was adapted to the new
flow but was **not run against a Kodi process**.

## Remaining acceptance / integration gate

No deployment, push, Kodi controls, restart, live provider/account request or
physical playback test occurred. Parent independent review is still required.
Before deployment acceptance, use an isolated native Kodi environment and then
an explicitly authorized on-device session to verify:

1. Setup consent remains readable/cancellable; configured Find streams proceeds
   directly; source cancel and effect-prompt No never resolve.
2. Local and synthetic Torrentio movies expose `VideoPlayer.Content(movies)`
   during actual playback (unit fakes cannot establish native tag propagation).
3. Back to movie browsing and Home pauses; repeated sampling never resumes.
4. OSD/seek/subtitles continue playing; Back from those overlays alone does not
   pause. Return fullscreen stays paused until explicit Play.
5. Music and games keep their existing behavior; Stop/new item does not inherit
   stale state. Check real remote input and the 100 ms polling tradeoff.

Do not claim native/Pi acceptance from these offline tests.
