# Movie stream choice — local checkpoint

Base: `9d4858102e9d297a3a98815539b64ad06ab15b92`; isolated branch `development/Aperture-stream-choice`.
Before branching, compared all 19 committed Movies files to installed add-on bytes: zero differences. No private settings/history, live account streams or media were read. No playback, Kodi changes, deployment or push.

## Diagnosis and policy

Code proves provider name/title/filename were collapsed to finite quality/codec/language/size labels. Ranking saw only those labels, so a labelled 1080p/H264 English trailer could outrank a feature. Synthetic regression reproduces that mechanism; it does **not** prove what the provider actually returned for The Big Lebowski. Establishing that exact cause needs separately consented, sanitized source metadata (not signed URLs or media).

Release filename and first title line are now examined within 2048 characters; display hint is bounded to 100, complete label to 280. Unsafe URL/markup/query/path-like lines, the configured token, long token-like strings and controls are discarded, never copied into navigation or persisted. Both filename and title contribute flags. No resolver URL filename extraction.

Explicit post-year trailer/teaser/sample/clip/behind-the-scenes modifiers are excluded from **automatic** candidates. An explicit ` - Official Trailer/Teaser` suffix also qualifies. Title words before the release year (Trailer Park Boys, Sample People, Clip), absent duration and ambiguous metadata remain unknown, not rejected. Explicit post-year Full Movie/Full Film/Feature Film hints rank before existing language/resolution/codec preferences. Flags are provider hints, not verified content. No media inspection, background model or per-request AI decisions. Tiny file size is not treated as proof of wrong content. Manual selection retains every security-validated source including flagged extras.

## Implemented navigation contract

- Browse/search cinema header has always-visible **Choose source** button716, D-pad reachable from715 and returning to61; enabled only for an explicit `Container(61).ListItem.Property(Aperture.MovieID)`. Carries `Aperture.SourceResume` from history items.
- Details' existing action now says Choose source and opens the directory. Legacy context chooser retained for compatibility but is **not** the remote-safe path.
- `Container.Update(plugin://plugin.video.aperture.movies/?action=torrentio_sources&id=<IMDb ID>&resume=1)` opens a native **files** directory (not poster layout). Optional resume; omit for beginning.
- Directory rows show sanitized hints, technical fields and unknown/extra/feature flags. URLs contain only IMDb ID, opaque SHA256 source ID and optional resume. `torrentio_pick` refreshes lookup, rejects vanished IDs, and resolves only the explicit source. Directory caches disabled.
- Listing and explicit pick use no focused progress/select modal. Navigation/abort cancels bounded requests and stale results cannot play. Failure/empty listing ends the directory and gives a nonfocusable notification. A sent provider request cannot be revoked.
- Native Estuary OSD group201 gains **Change source** button699 through the existing build/install transform. `RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_change)` checks video/movie, validated `aperture_movie` IMDb tag and `aperture_session` ownership before navigating to sources. It never stops/toggles/resumes playback; existing fullscreen-exit policy owns pause. Replacement starts from beginning unless explicit resume route used (avoids carrying a trailer position into the feature).
- Existing first-time token-sharing consent, automatic-effects choice, resolver security validation, bounded fallback and resume/history logic remain. Format/Games/saves/drives untouched.

## Required parent integration with online-first home

Read committed `26ad95f1beca211f4d8fdb133c8cd525e2782fd5` XML/docs only; did not edit its worktree. **Custom11120 visible source buttons are not in this base checkpoint.** Parent must integrate while home worker fixes asynchronous details/status races:

1. Each home row730/731/732 needs its own visible adjacent Choose source button (or explicitly latched selected-row action), with D-pad edge from row to button and back. Do not use bare ListItem/FolderPath, don't hide the button when it takes focus, don't infer row from current focus after leaving it.
2. Use explicit `Container(730/731/732).ListItem.Property(Aperture.MovieID)` and publish validated IMDb IDs on every home ListItem. Continue730 must carry `resume=1`; other rows retain their explicit resume intent rather than guess it.
3. Home is not a Videos container: add a validated `RunPlugin` navigation shim which then calls `ActivateWindow(Videos,<torrentio_sources route>,return)`. Do NOT RunPlugin the directory route itself (handle would be invalid). Keep origin/abort checks before navigating; lookup happens only after explicit action, never on focus/home load.
4. Replace footer's context-menu source instruction with single-press/D-pad guidance. Keep default poster autoplay and optional context actions.
5. Reconcile small addon.py/test overlaps and regenerate install.sh MOVIES_SHA after MyVideoNav merge. Preserve the home worker's11120 pause/latch browser target. Existing movie_exit_signal.apply now also patches OSD; retain both behaviors.

## Executed verification and pending acceptance

Strict vertical RED→GREEN cycles were run for source rejection, legitimate title/unknown retention, feature priority, sanitized dual-field extraction, long/no-year release hints, directory listing/pick, no progress modal, error completion, explicit identity routing, resume intent, OSD controls, owned current-source navigation and all-extras explanation. Final isolated suite:

`unshare -Urn sh -c 'ip link set lo up && python3 -m unittest discover -s tests -q'`

**851 tests passed** (48.154s). Real complete Estuary skin ZIP assembly passed; SHA256 `9e1bd1d0cf4588d6dafe90ce1adb6f83246e68841fc7c190c80fa3026fbcac67`. git diff --check passed. Installer tests use disposable profiles only.

**Native/physical acceptance pending:** reproduce user's held OK opening then cancelling dialog; verify single-press Choose source, long-held input/repeat not activating unintended rows, Back/cancel during delayed lookup/resolution, readable source hints/native file list, selecting another source once, OSD D-pad reachability and fullscreen exit pause, no unsolicited resume, explicit Continue resume, history/session correlation, and old movie remaining paused after cancelled choice. Synthetic/XML tests do not establish actual remote key-release behavior. No unsupported timing/debounce guarantee is claimed. Run exact integrated-head native workflows and physical TV remote checks before calling this solved.
