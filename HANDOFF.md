# Aperture integration handoff

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
