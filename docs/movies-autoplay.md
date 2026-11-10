# Automatic movie sources — local candidate

Base `570f1176b6a6ed8e0a8a224ec691ac5713ca77dd`; branch
`feat/movies-autoplay`. No deployment, push, account calls or live Kodi actions.

## User path

Discover movie Select now runs `torrentio_auto`: saved opt-in configuration →
source lookup → deterministic ranking → fresh stable-ID refetch → one resolver
request → tagged movie ListItem → Kodi Player → actual AV-start verification.
Browsing/highlighting still performs catalogue requests only, never source lookup.
Movie context menu retains **Movie details (Cinemeta)** and **Choose source**.
Manual selection starts only that source; it does not silently fall back.

No repeated rights or per-play effect confirmations. Existing explicit provider
sharing remains mandatory before configuration exists. Native setup, advanced
import and status/help disclose automatic attempts, RD history/transfer/traffic
and Kodi signed-URL logging. No new grant is inferred from selecting a title.
Existing configured users retain the previously granted scope; this user-requested
selection change does not silently connect an unconfigured provider.

## Conservative policy, not hardware discovery

Sanitized provider labels provide finite hints, not verified codec/language/media
inspection. Prefer English, then multilingual, unknown, other language; deprioritize
2160p/4K; prefer AVC/H.264, unknown codec, HEVC, then AV1; within those groups prefer
1080p, 720p, 480p, unknown. File size never wins. Preserve provider order for ties
and deduplicate stable secret-free IDs. Unknown metadata remains unknown. This
fixed Pi-oriented preference is not a claim that this checkout measured the TV or
decoder, nor a configurable capability detector. Manual source choice is the
escape hatch for mislabeled media or different preferences.

## Bounds and lifecycle

- At most three distinct candidates per automatic selection, one in manual mode.
- Reuse the existing bounded, cancellation-aware provider transports and locked
  credential refresh. Never repeat a mutation-capable resolver for the same ID.
- Next source only after explicit unsupported-archive/too-large provider results,
  or a player error with no active video. Downloading, account/traffic errors,
  network ambiguity and changed sources stop, rather than queueing more work.
- Cancel, changed directory, Home/window navigation and shutdown prevent late
  lookup/resolver results from playing. DNS/TLS cancellation regressions remain.
- Player success requires `onAVStarted`, active video and exact final-file match;
  `Player.play()` returning is not success. Startup is bounded to 150 x 0.1-second
  waits. Timeout stops the pending attempt and offers Choose source, without retry.
  Stop/end are cancellation, not failure. A different active video is not stopped.
  An error while video remains active stops it without initiating fallback.
- No viewing history is written in this checkpoint. History must bind metadata to
  an actual session and positive playback samples, not selection or resolver success.

## Observed TDD evidence

Each implementation slice followed a failing focused unittest run, then GREEN:

1. Catalogue default route/manual context: failed old details route and old label;
   changed listing routes, then 43 plugin tests passed.
2. Ranking: missing module → preference implementation; duplicate IDs failure →
   dedupe; AV1-vs-720p AVC and 4K-AVC-vs-1080p HEVC failures → suitability ordering.
3. Auto UI: zero lookup calls → automatic dispatch/rank; plugin route attempted
   local source RPC → dedicated auto dispatch.
4. Repeated confirmation/setup effects: unwanted yesno and missing disclosure →
   setup/status disclosure with no per-play prompt; manual path separately tested.
5. AV startup: missing helper → timeout bound; queued request wrongly counted/
   callback absent → actual AV event plus matching file; cancellation/error/end/
   wrong-file cases → explicit outcomes. Active-error retry regression → stop/no retry.
6. Three-source fallback failed at one attempt → bounded distinct loop; archive/
   too-large cases failed at one → finite typed error allowlist. Timeout explanation
   and Home navigation both failed → recovery text and underlying-window guard.
7. Manual AV verification failed at zero helper calls → shared verification helper,
   still single candidate. Native fixture assertions failed on obsolete prompt/
   route → manual cancellation plus direct poster Select automatic-play journey.

Added regression-only confirmation (already GREEN, not claimed as new RED cycles):
real parser/refetch/resolver through synthetic transport into fake Kodi AV callbacks;
late successful/failed resolver results under cancel/navigation/shutdown.

Final full offline suite: **768 tests passed**, in an unprivileged network namespace
with only loopback enabled. The suite's installer messages refer to disposable
fixtures, not installed add-ons. `git diff --check` clean. Parent independent review
still required; no independent reviewer verdict is claimed.

Native fixture updated but **not executed**: host lacks Xvfb and PulseAudio required
by `tools/movies_smoke.sh`. Installed Kodi version is not native acceptance. No
packages were installed, no personal Kodi session was launched or modified. Native
AV callback timing, cancellation during actual player opening, rendered video,
physical remote, pause-on-Back and audible output remain acceptance gates.

## Next integration checkpoint

History core `974ecc2dba6ab9dbcae47708bcf279e25df3f768` is ready in the separate
`Aperture-movie-history` worktree. Read `docs/movie-history.md` before cherry-picking.
Do not mark the complete history feature delivered until History / Continue watching /
Suggested for you, resume, clear, and session-correlated service sampling are wired
and tested. Persist only sanitized catalogue metadata, never signed URLs. Use a
volatile session identity, expire pending selection, throttle writes to 15–30 seconds,
flush the last safe positive sample on stop, and disable current-session recording
on clear. Fetch ordinary public catalogue candidates and rank locally; no watched
IDs/genres in remote recommendation requests. This checkpoint deliberately contains
no half-wired history feature.
