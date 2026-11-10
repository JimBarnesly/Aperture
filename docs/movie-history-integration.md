# Movies history integration — local candidate

Base: `00c68ef87afa92d86edbdee3700738a9754d0108` (automatic source selection and pause-on-Back).
History core cherry-picked from `974ecc2dba6ab9dbcae47708bcf279e25df3f768`
as `899a400` with no core changes.

## Visible behavior

Discover → Collections now offers **History**, **Continue watching**, and
**Suggested for you**, alongside the existing public collections and Kodi library.
These directories retain Search/Collections/Genres navigation. History/Continue
Select explicitly resumes when a saved position exists; the context menu offers
Play from beginning. Resume always runs the existing source lookup and fresh
resolver, then applies StartOffset to the new item. Returning from Back does not
resume playback automatically. History rows use generic artwork, not saved URLs.

Clear history is available in these directories, including corrupt-history recovery.
It asks for confirmation, preserves media/backups and current playback, cancels the
current recording session, and waits up to five seconds for the service's matching
acknowledgement. No acknowledgement means “Clear not confirmed”, not false success.
An unavailable service can process a queued clear later. Refresh is stale-navigation
safe. Clear is not secure erasure and does not delete backups.

Suggestions fetch exactly the ordinary public default catalogue batch, then rank
locally using the private core. No history-derived genres, searches or watched IDs
are sent for recommendations. Sparse history/no matching genres is visibly labelled
“catalogue suggestions only”. Ordinary explicitly selected movie playback still
uses the existing catalogue/provider movie-ID requests and consent boundaries.

## Actual playback boundary

`history_playback.py` places only allowlisted metadata plus a random opaque session
ID, expiry and clear generation into an in-memory Home-window property. The same
ID is attached to the new ListItem VideoInfoTag as `aperture_session`. No resolved
URL, token, artwork or provider row enters that handoff or history file.

The existing independent Movies service owns all history writes and clear. Every
100 ms it polls actual video playback, verifies the playing VideoInfoTag session
before **and after** collecting progress, and accepts only positive finite progress.
Selection/resolver success/play request alone never writes. Pending handoffs expire
in 30 seconds and are consumed once. Unrelated playback cannot claim pending movie
metadata. Active sample writes are throttled to 20 seconds; stop/end/player replacement
and service shutdown flush the last known-valid observation, never invented stop
progress. A process kill may lose up to a write interval. Completion uses the core's
position threshold, not a claim of watching every second.

Clear requests rotate the in-memory generation before the service cancels pending
and active recording. Late old-generation resolver handoffs are refused. Storage
failure disables that recording session with a generic notice while preserving
playback and existing corrupt bytes. Explicit new selections can record again.
The private bounded store remains `history-private/history.json` below translated
add-on data, with the core's directory/file permission and no-follow protections.

## TDD and verification

Incremental RED → GREEN executions (unittest) were observed for:

- Missing session bridge → matching positive progress, safe metadata only.
- Unthrottled writes → 20-second writes and final valid sample.
- Missing serialized clear → active/pending cancellation and late-generation rejection.
- Unhandled HistoryError → generic notification and uninterrupted player.
- Stale handoff → expiry/one-time consumption and no restart after stop.
- Missing service loop wiring → polling alongside existing pause guard and close.
- Runtime teardown exception → retain last sample and safe shutdown.
- Missing resolved-item handoff → prepare before play, explicit resume flag.
- Missing resume adapter → saved position only, no selection write.
- History/metadata failure → playback survives; no private details in UI.
- Missing collection routes/listings → History/Continue and explicit resume routes.
- Missing recommendations → default-public-batch request plus real local ranking.
- Missing confirmed clear → real-store service clear, matching ack and stale-safe refresh.
- Corrupt history / catalogue failure → useful generic recovery paths.
- Malformed handoff/player switch during sampling → fail closed.
- Missing native QA journey/time budget → controller-driven synthetic acceptance script.
- Invalid IMDb identity → reject before metadata lookup.
- Clear followed immediately by a new selection → reset per-session write throttle.

Additional cross-boundary regression exercises the real UI handoff, real private
store and real polling monitor with synthetic Kodi/provider boundaries, then proves
Resume resolves again to a different URL. Service factory is checked against a
temporary translated directory. Full suite: **806 tests passed**. `git diff --check`
and shell syntax pass. Installer output in this suite refers only to disposable
fixtures, not the live installation.

## Remaining gates / scope

Native synthetic QA was updated for recording, fresh-resolution Resume, Back-pause,
clear decline/accept, 22-second stale-write observation and honest suggestion fallback.
**It was not executed:** Xvfb, pulseaudio and pactl are missing on this host. No packages
were installed and no current Kodi controls were used. Native VideoInfoTag unique-ID
propagation and StartOffset behavior, physical controller/display acceptance and real
provider playback therefore remain unverified; missing tag propagation fails closed
(no history), not guessed URL matching. Parent independent review remains pending.

This integration records catalogue-identified Torrentio automatic/manual playback.
Unidentified local files and direct RD download browsing are not assigned invented
IMDb identities; Kodi's existing local-library history/resume is unchanged. History
artwork is generic. No deployment, push, account access, live profile edits or media
changes were performed.
