# Aperture integration handoff

## Integrated home / manual sources — local candidate, 2026-11-10 UTC

Owner: delegated async/integration agent; parent owns review/deployment.
Async commit `211207fb1467d687702901f2af4d6019623aa530`; source-choice
`15cd3e2e4cc72a903b72da60f2f3cdcba28402f2` locally cherry-picked as
`5a36a8440b3929a4c2f3d8c806e55ba5d2dc98c2`. Overlap resolution retains both.
READY for review: persistent row730–732 Choose source buttons740–742, explicit
validated identity/resume, origin-checked navigation shim into Videos and correct
Home details navigation. OSD Change source, extras filtering, consent/history,
async stale-result guards and immediate Back assertions retained. Both XML
installer checksums regenerated. 878 full offline tests and 33 focused tests pass;
complete skin ZIP assembly passes. Native synthetic integration updated, not run:
Xvfb/PulseAudio/pactl absent. Physical held-OK and native exact-head acceptance
remain pending. No push/deployment/live Kodi/accounts/personal-profile changes;
source-choice worktree untouched. See [integration evidence](docs/movies-stream-choice.md).

## Movies async UI review fixes — 2026-11-10T12:36:11Z

Owner: delegated async-fix agent; parent owns integration/review and deployment.
Base `26ad95f1beca211f4d8fdb133c8cd525e2782fd5`, branch `feat/movies-home`.
READY for parent review. Row statuses compare the URL refresh generation before
publishing; details guard success/error dialogs and subsequent menu/actions by
window, path and opaque invocation identity. Overlapping Retry and 11120 → 10000
regressions observed RED then GREEN; same-window replacement also covered.
Final loopback-only namespace: 72 focused and 857 full-suite tests pass.
No weakened native assertions; native race recipe is documented but pending.
No push/deploy/live Kodi/account/personal-profile changes. Separate source-choice
tree untouched. Rollback is the base above; next step is parent review/integration
and exact-head native synthetic acceptance. See [evidence](docs/movies-home.md).

## Online-first Movies home — local candidate, 2026-11-10 UTC

Owner: delegated Movies-home agent; parent owns review and any deployment.
Base `9d4858102e9d297a3a98815539b64ad06ab15b92`, branch `feat/movies-home`.
READY for review; native acceptance BLOCKED (Xvfb/PulseAudio/pactl absent).
Home Movies opens native three-row online home, not local folders. Search,
local Continue watching, locally ranked suggestions, public Popular/Featured,
inline recovery and secondary Local files/Sources retained. Focused real
synopsis/year/genres plus explicit metadata-only details; no guessed identity,
TV relabelling or focus-triggered source lookup. Existing auto-source/resume and
pause-on-Back extended to custom home. Matching skin + Movies required.
852 full offline tests pass; complete skin/Movies package build passes.
Native synthetic and ZIP journeys updated, not executed here. No push, deployment,
live Kodi controls, account calls, personal profile/media/settings changes.
Public-only Cinemeta probe: each default batch returned 50, all with plot/year/genres.
See [behavior, TDD evidence and pending gates](docs/movies-home.md).

## Stream suitability / manual choice — local checkpoint

Owner: delegated source-choice worker; parent integrates/deploys. Base `9d48581`
matched all19 installed Movies source files read-only. Branch
`development/Aperture-stream-choice`, READY for review; no push/deploy/device or
account actions. Provider release hints survive bounded sanitization; automatic
selection excludes explicit extras before technical ranking, keeps unknowns and
legitimate Trailer title words. Dedicated nonmodal source directory/pick,
Browse/search single-press Choose source, explicit resume and native OSD Change
source added.851 offline tests pass in isolated network; real skin ZIP passes.
Exact Big Lebowski provider response was not inspected; cause remains plausible,
not confirmed. **Home11120 row730–732 visible source-button integration remains
parent work**, with explicit per-row identity/resume and RunPlugin navigation
shim contract in [docs](docs/movies-stream-choice.md). Long-held remote OK physical
acceptance and exact integrated native CI remain pending; no synthetic-only
claim that remote cancellation is solved. Format/Games/media/credentials unchanged.


## PR31 native pause failures — local candidate, 2026-11-10 UTC

Owner: delegated CI-fix agent; parent review/publish owner. Base `c857dee`.
READY for review, BLOCKED on exact-head native rerun (not pushed).
Public artifacts prove menus toggled an auto-paused movie back on; online Resume
spent only 28 ms fullscreen, below the 100 ms service poll. QA now uses explicit
pause. Rebuilt skin latches native fullscreen exit with the opaque session; Movies
consumes it with existing movie/browser/ownership gates. Requires skin + Movies,
not a Movies-only update. Immediate Back acceptance retained and transient/return
checks expanded. **835 offline tests pass**, real scratch skin ZIP build passes.
No device/accounts/profiles/deployment changes; existing live revision untouched.
Native GREEN not claimed (Xvfb/PulseAudio/pactl missing). Parent must review and run
both workflows before lifting the CI gate. [Evidence and limits](docs/movies-native-ci-fix.md).

## Autoplay lifecycle review — local fixes

Reviewed against history-integrated `7fbcf66ade72cf1ed7c69eedb319062adabcea08`.
Startup now correlates the existing opaque history session, retains predecessor
transitions, refuses unowned-error fallback, and checks ownership before every
stop. Pause state is identity-bound. A separate versioned one-time autoplay
effects preference covers setup/import and existing-profile migration without
revoking sharing or removing manual sources. History/resume/clear preserved.
Full offline suite: **826 passed**, network namespace with loopback only.
No deployment/push/device/accounts. Native QA updated but not run (missing
Xvfb/PulseAudio/pactl); native pending-open revocation and atomic player ownership
remain unproven. Parent review required. [TDD evidence and limits](docs/movies-lifecycle-review.md).

## Private movie history integration — local checkpoint

On `feat/movies-autoplay` above `00c68ef8`, the history core (`974ecc2d`,
cherry-picked as `899a400`) is wired to session-correlated positive playback
progress, 20-second persistence, final samples and serialized clear. Discover →
Collections exposes History / Continue watching / Suggested for you. Explicit
Resume resolves a fresh source; suggestions rank only a default public batch
locally. Full offline suite: 806 passed. Native synthetic journey updated but
not executed: Xvfb/PulseAudio/pactl unavailable. No deployment, push, accounts,
live Kodi controls or profile changes. Parent review and native tag/StartOffset
acceptance remain pending. [Behavior, TDD evidence and limitations](docs/movie-history-integration.md).

## Automatic movie selection — local checkpoint

`feat/movies-autoplay`, based on `570f1176`, routes poster Select through
lookup/ranking/fresh resolution/actual AV-start verification. Manual Choose source
remains; automatic fallback is bounded to three distinct sources after explicit
failures only. Setup/status retains sharing and account-effect disclosure, without
repeated playback prompts. Offline suite: 768 passed. Native synthetic journey
updated; execution blocked by missing Xvfb/PulseAudio. No deployment/push/accounts/
live Kodi. See [policy, TDD evidence and remaining gates](docs/movies-autoplay.md).
History core `974ecc2d` is ready separately; session/UI integration is explicitly
pending, not partially wired into this checkpoint. Parent review required.

## Movies playback UX — local bounded candidate

Based on deployed Movies source `9d99d02117f025e36325a6c76f4d197ec4abb46a`,
verified against all 14 installed source files before branching. Branch
`feat/movies-playback-ux` removes repeated rights wording, retains provider-effect
consent, and adds a separate movie-video fullscreen-exit pause service. Offline
regression: 747 tests pass (baseline 734). See
[exact flow, TDD evidence and acceptance gates](docs/movies-playback-ux.md).
No deployment, push, Kodi/account actions or protected media changes. Native
acceptance and parent independent review pending. Automatic best-source play,
one-time automatic-play effect preference, history and suggestions belong to the
parent's next integration slice, not this candidate.

Updated: 2026-11-09. Public project status only.

## Torrentio development slice (local only)

Review-fix base `086f4d1b521570018e01ee94ef9c0e5e0b2ffd6d` in the isolated
`Aperture-torrentio` checkout. Native setup now uses the existing RD device flow,
separate access-token disclosure consent, marker-only persistence and locked
refresh before check/search/play. No manual token copying is required. Visible
movie-details actions expose Find streams; `undefined` resolver indices, sanitized
technical labels, distinct resolver outcomes and corrupt-config recovery are covered.
See [setup/security and live acceptance gates](docs/torrentio.md),
[review-fix RED/GREEN evidence](docs/torrentio-review-tdd.md), and the historical
[first-slice evidence](docs/torrentio-tdd-evidence.md).

No live account/search/playback requests, deployment, device changes, merge or push.
Official Torrentio source uses bearer authentication, making OAuth access tokens
source-compatible, not live-proven. Physical playback, remote dialog readability
and strict HTTPS resolver compatibility remain unverified. Parent independent
review is still required before deployment.

## Current source candidate

The latest `integration/latest-preserved-main` candidate adds the complete Music
Coverflow/library line and Movies/consent PR21–27 to the merged PR17 foundation. See
[branch reconciliation](docs/main-integration.md) for included commits and the
retained historical alternatives. Source branches are preserved. Consult the
latest PR head and its matching workflow results, not an older green revision.

The combined candidate includes the saved Games carousel, conservative source
removal guard, Format native turntable and permissions, safe local movie poster
choices, and notification/Wayland diagnostic coverage. Legacy `skin.apeture`
packages are a separate historical line and are not interchangeable with this
skin. Online catalogue artwork is available; automatic matching of local files
to online posters is not implemented.

## Verification and deployment boundary

Unit tests, package assembly and isolated native Kodi startup/Format/ZIP, Games,
Movies and menu checks are separate gates. All must match the final source head.
Historical failed output-churn experiments remain failures; the Home-aligned
success does not diagnose or resolve the physical Pi blackout.

The candidate is not installation permission. Device and media-drive work remain
with the existing repair owner. Do not compete with backup, checksum verification,
filesystem repair or preserved runtime evidence. No deployment pin, service,
backend, mount, media, controller pairing or CEC setting is changed by this merge.

Hardware reboot/relaunch, V3D/HDMI, physical controller/CEC, drive disconnect,
audible output and real-library acceptance remain separate. Synthetic CI cannot
clear those risks. Keep Estuary and existing rollback backups available.

## Music and data preservation

Music uses the existing Format server and backend library. The skin neither
installs a server nor expands its permissions. Acquire, cancel and prioritise
capabilities are checked independently and again after confirmation. Failed or
uncertain writes are not automatically replayed. Installer and combined-install
tests preserve Games cache/settings, cores/saves, sources, Format settings and
Movies client data. Clearing a saved game list never deletes game files.

Before subsequent changes, read current heads and feedback and reconcile instead
of overwriting concurrent work. Report exact source revisions, package hashes and
tested layers. Never publish credentials, private paths or unredacted device logs.
