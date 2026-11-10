# Aperture integration handoff

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
