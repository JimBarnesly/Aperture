# PR32 offline Local files Back: premature QA input

## Retained evidence and cause

Native run `42953881470`, exact head
`04e433d27dab80a21caa3aff5c0cc7912df01e31`, online artifact
`13826073204` was downloaded completely before editing. Inspected result,
progress, full Kodi log, native-backtrace, native environment and failure image.
Result is an assertion timeout (`offline fallback Back`, window10025, empty
folder, Files), not a captured SIGSEGV. GDB output contains thread lifecycle
records, no fault signal/stack. QA records failure then requests shutdown.
The screenshot shows native Videos root: Files, Playlists, Video add-ons.

Kodi log timeline (UTC):

- 03:37:59.030: first Local files opens Videos; mode=local listing loads.
- 03:38:00.899: actual PreviousWindow returns to Movies home11120.
- 03:38:04.499: second Local files reopens retained Videos.
- 03:38:04.547: mode=local GetDirectory begins.
- 03:38:04.648/.670/.691: Busy opens, closes, opens again.
- 03:38:05.000: script runner **cancels** that local directory invocation;
  monitor abort and Python interruption follow, not a source exception.
- 03:38:05.037: GetDirectory fails and Kodi loads the empty-path native root.
  No PreviousWindow occurs on this second visit.
- 03:38:40.694: timeout failure screenshot, then QA finishes and shuts down.

Ranked hypotheses were a premature Back into loading UI, another window-history
collision, and an actual local-source failure while offline. The cancellation
plus absence of PreviousWindow distinguishes this failure from the prior source
history bug. The same synthetic local source loaded on the first visit; the
second invocation has no source-listing Python exception. Offline mode affects
public catalogue fixture responses, not local media.

Kodi21.3 source explains the observed chain:

- `CGUIDialogBusy::OnBack` sets cancelled and consumes Back; `WaitOnEvent`
  propagates cancellation to the background directory runnable.
- `CGUIMediaWindow::GetDirectoryItems` waits with cancellation enabled.
- `CGUIMediaWindow::Update` falls back to `Update("")` when the failed path is
  also the previous path. This produces native Files without changing window.
- Videos is KEEP_IN_MEMORY. Its visible cinematic control is not proof the
  new listing has completed. One instantaneous `cinematic()` sample can pass
  before/between busy dialogs; a queued Back then cancels the pending load.

Pinned references:
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/dialogs/GUIDialogBusy.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/windows/GUIMediaWindow.cpp
- https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/filesystem/PluginDirectory.cpp

## Narrow correction

Both home Local files visits now use the existing `wait_for_movie_idle` guard,
requiring the exact local folder, cinematic view and a continuous quiet interval
without busy/modal/updating state or listing/focus changes. This reuses the
existing bounded UI-settling mechanism, not a sleep, retry, bypass, extended
timeout or claim of an atomic plugin-completion signal.

Back is still sent once through Input.Back; both11120 return assertions are
unchanged. All product code, native/global Back behavior, custom-home source
return marker/origin checks/ReplaceWindow and skin assembly remain untouched.
No speculative local redirect from empty-path native Files: that would change
native navigation to conceal a cancelled listing instead of fixing QA input.
Immediate fullscreen playback Back/pause assertions are also unchanged.

## Strict TDD and verification

A regression executes the actual two local journey slices and real settling
functions with a deterministic native-boundary replay: retained visible view,
outer busy dialog, gap, nested busy dialog, completed listing. It failed before
the harness change because Back was queued at time0 while loading. After the
change both slices pass with exactly one Back and destination11120. Kodi inputs
are faked at the API boundary; this is not native acceptance.

- Focused regression: RED (both visits), then GREEN.
- Full suite:891 tests passed in44.085s, isolated loopback-only namespace.
- `git diff --check` passed. Security scan flags only repository-owned AST
  execution in the test harness, no dynamic user input/secrets/network execution.
- Existing crash-capture tests ran in that full suite; capture workflow/script,
  package/Build-ID evidence and atomic progress instrumentation are unchanged.
- Native rerun is pending: local Xvfb, pulseaudio and pactl are absent. No push,
  CI dispatch, deployment, live Kodi interaction, account/profile/media changes.

Prior run42826398013 at b773579 had a real later Stop/Browse SIGSEGV. This run
never reached it, so that crash remains **unresolved**, not fixed or disproved.
Parent must review the local commit and run exact-head native CI with retained
crash capture; keep the failed-CI gate closed. Physical acceptance remains
separate. Rollback is base04e433d; this correction changes only QA plus evidence.
