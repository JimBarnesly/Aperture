# PR32 native SIGSEGV: evidence, not a navigation diagnosis

## Retained evidence

Run `42826398013`, exact head `b773579e6c77079708b663863f8ccfff484f6d94`:
only `movies (online)` failed; the four other matrix cases passed. Downloaded
online artifact `13768773725` and default-case control artifact `13769497191`.
The online archive contains 42 files: full Kodi log, screenshots, synthetic
transport events and generic failed result, **no core, crash backtrace, or
persisted QA progress**. The shell reports a real segmentation fault and
`timeout: the monitored command dumped core`; that message does not establish
that a retrievable core was uploaded. Result exit_code1 is the harness's
failure, not a Python assertion or Kodi's original signal status.

Kodi is Debian `2:21.3+dfsg-2`; embedded interpreter paths show Python3.14.
The same missing `libvdpau_nvidia.so` warning exists in the passing default
artifact. It is not evidence of the faulting component.

## Sequence reconstructed from full log

-13:41:59.486 and13:42:04.336: exactly two `home_source_back` launches, one
  for each tested nonempty row. Each returns to Movies home (00.266,05.143).
- Both source-directory screenshots exist. Execution advances beyond the
  restored-focus/identity/resume/no-resolution assertions to home playback.
-13:42:07.812 fullscreen;07.879 immediate native Back;07.881 Movies home.
  `home-resume-back-pauses.png` saved09.271, after the harness's pause and fresh
  resolution assertions. This is progress evidence, not full acceptance.
-09.558 Stop,09.813 OnPlayBackStopped;10.060 deinit Movies home and10.061 init
  Videos;10.079 `mode=online` lookup. This matches `home_resume_journey`'s final
  Browse all operation, before `history_journey`.
- Last log10.869: row invokers completing/initializing concurrently; shell
  notices death13.790. No native faulting thread or instruction was retained.

Across the full run, each home row launches13 times. Final refresh token
`20806e973f016f6f` has two three-row batches, not unbounded nonce recursion.
The second batch is invalidated09.855 after Stop and starts as older jobs finish.
Upstream21.3 `CDirectoryProvider::Announce` invalidates unsorted providers on
OnPlay/OnResume/OnStop; Update cancels/requeues jobs. Home onload changes the
nonce once per entry. This explains repeated rows without proving a crash cause.
Reference: https://github.com/xbmc/xbmc/blob/21.3-Omega/xbmc/guilib/listproviders/DirectoryProvider.cpp

## Ranked leads and falsification

1. Native provider/job or embedded-Python lifetime race while leaving home with
   refresh jobs outstanding. Prediction: fault stack involves those lifecycles.
2. Native player/renderer/audio teardown race overlapping Browse all. Prediction:
   faulting stack points there, not necessarily the last logged Python thread.
3. Delayed corruption from the new scoped Back/focus/ReplaceWindow path.
   Prediction: stack/reduced replay links it to control lifetime; no immediate
   recursive navigation is present in retained evidence. Both Back tests advanced.

These are **leads only**. Prior runs stopped at earlier assertions, so this run
is not proof b773579 introduced the SIGSEGV rather than exposed a later path.
Do not revert navigation or throttle rows on this evidence. Existing six offline
source-Back tests pass but cannot reproduce or rule out native memory corruption.

## Minimal next-run instrumentation (local only)

No product/skin/navigation changes. Online CI alone launches the same isolated
fixture under child GDB, bounded to240s plus5s forced exit. It saves all-thread
backtraces (40 frames/thread), registers, shared-library map, binary SHA256/Build
ID and package versions. No attach, host core-policy changes, raw core/profile
upload, network symbol downloads, live accounts or device access. GDB/binutils
are installed only in that future CI job, not on the host. Existing always-upload
retains the diagnostic text. Ptrace restrictions or stripped symbols remain
possible blockers and must be reported, not bypassed silently.

Online QA atomically overwrites one `progress.json` at wait entry with stage,
completed checks and native window/dialog/folder/focus state. It does not add
polling, sleeps, retries, alter assertions, or put I/O between fullscreen-ready
and immediate Back. The snapshot describes entry into a wait, not its completion.

Diagnostic regressions observed RED before implementation; GREEN with an actual
small compiled child producing SIGSEGV under installed GDB, a normal child, and
non-disposable-profile rejection. Snapshot regression fails on the old harness
and passes with atomic state persistence. Full offline suite:890 passed in a
loopback-only unprivileged network namespace. Shell syntax and diff checks pass.
Native Kodi not run locally (Xvfb/Pulse prerequisites absent); no CI rerun/push or
deployment. Parent may review/push this diagnostic-only candidate for one bounded
capture; **failed exact-head native gate stays closed**, even if instrumentation
changes timing and that next run happens to pass. Read fault stack before a fix.
