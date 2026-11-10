# Movies home native CI: keyboard close/input readiness

## Evidence and root cause

PR32 run `42818993595`, exact head
`add9d428a9ac15d506c2029ea15f782fa2cefd99`, failed only `movies (online)`.
The retained `aperture-movies-online-add9d428a9ac15d506c2029ea15f782fa2cefd99`
artifact contains `result.json` and `logs/kodi.log`:

- `result.json`: `movies_home_journey` line387 timed out waiting for the keyboard;
  underlying window11120, dialog9999.
- Log811: native Search invoked `?action=home_search` normally.
- Log836: keyboard initialized at12:50:38.655.
- Log837: at12:50:38.839, `HandleAction` ignored action7 because the topmost
  modal's closing animation was still running.
- Log838: keyboard deinitialized at12:50:38.964.
- Log839: the Search script completed successfully. No second Search invocation
  occurred before the timeout.

Thus the timeout was the **second** open, not a broken Search route. QA sent
Select before the first keyboard had finished closing. Investigated alternatives
were an invalid custom-window route/window guard and a focus-loss/failed plugin
invocation; the successful first open and explicit ignored-action log instead
identify the QA input-readiness boundary.

Kodi21.3 source confirms `System.HasModalDialog` is removed from the condition
registry. Unsupported conditions evaluate false. Even the supported
`System.HasActiveModalDialog` ignores closing animations; it is not an input-ready
barrier. `System.HasVisibleModalDialog` calls `HasModalDialog(false)`, including
closing dialogs, matching the `HandleAction` blocker.

References (pinned upstream tag):
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/GUIInfoManager.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/guiinfo/GUIControlsGUIInfo.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/GUIWindowManager.cpp

## Change and scope audit

- Search cancellation now requires window11120, no **visible** modal and restored
  Search control720 focus before another key. Both real Select/Back cycles remain.
- The same unsupported predicate was found in the online QA `settled()` helper
  and the new home source-directory nonmodal/cancel checks; all use the supported
  visible-modal condition now.
- Reviewed Home XML Search/Browse/History/Local/Sources/Retry/Home routes, row
  click/source buttons and `home_search`, `home_sources`, `home_refresh`,
  `home_row`, `online_details` handlers. The new home handlers do not use the
  removed predicate. Source identity/resume, invocation/generation/window guards,
  history and account/privacy behavior remain unchanged; no product or skin edits.
- Existing older predicates in other add-on/QA paths remain a separate audit item;
  they are not evidence of this failure and are not mechanically rewritten here.
- No added sleep, timeout extension, Select retry, direct-route bypass or weakened
  acceptance. Immediate playback Back/pause checks are unchanged.

## Verification

TDD: the replay regression failed on the premature second Select, then passed
with the real cancellation predicate fix. A second regression failed because
`settled()` accepted a closing modal, then passed after the online QA audit fix.
The tests execute extracted real harness functions with fake native boundaries;
they do not claim native acceptance.

- Focused `test_movies_online_fixture.py`: **10 passed**.
- Full suite: **880 passed**,41.428s, in an unprivileged loopback-only network
  namespace (`unshare -Urn sh -c 'ip link set lo up && python3 -m unittest discover -s tests -q'`).
- `git diff --check` passes.

Native exact-head rerun remains required after parent review/push. Xvfb,
PulseAudio and pactl are absent on this host; no dependencies installed, live Kodi,
real display, account or deployment actions taken. The working live revision is
untouched. Rollback is parent `add9d428`; only QA/tests/docs change.
