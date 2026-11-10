# Private Movies history core (integration handoff)

Original isolated-library handoff below. For the subsequent local-only Kodi/UI
integration, see [integration behavior and acceptance gates](movie-history-integration.md).
The native integration has not been deployed or physically accepted.
Base: `9d99d02117f025e36325a6c76f4d197ec4abb46a`.

## Integration API

```python
from resources.lib.movie_history import HistoryStore, HistoryError
from resources.lib.movie_recommendations import recommend

# A dedicated directory within the translated local add-on data directory,
# never a media directory, never special:// or a network filesystem.
store = HistoryStore(private_history_directory, max_records=200)

# Only inside an actual video-playback monitor, AFTER playback has started,
# with the metadata/IMDb ID bound to that playback session, NOT selection,
# source resolution, setResolvedUrl success, or a play request.
accepted = store.record_playback(
    normalized_catalogue_movie,
    is_playing=actual_video_is_playing,
    position_seconds=observed_position,
    duration_seconds=observed_duration_or_zero,
    lastplayed=unix_timestamp,
)
rows = store.records()  # newest first, ID tie-break
suggestions = recommend(public_candidate_rows, rows, current_id=current_imdb_id, limit=20)
# suggestions = {'items': metadata_rows, 'mode': 'history'|'catalogue', 'reason': ...}
store.clear()  # only after the user requests clear; no media deletion
```

Caller must catch `HistoryError` without logging metadata or filesystem paths.
Keep playback running if history storage fails. Display a generic history-unavailable
message; do not silently overwrite corrupt history. An explicit clear can recover
invalid JSON but refuses unsafe filesystem objects. There are no implicit profile,
account, filesystem discovery or network calls. `is_playing` is an integration trust
boundary: this pure library cannot independently establish that Kodi is playing.
The parent must connect a real playback callback/polling monitor, match the session
ID, sample while playing and persist its final valid observation. Do not manufacture
`is_playing=True` from a selection or stop event. Serialize lifecycle control and stop
recording before clear so a later genuine sample does not repopulate cleared history.
Throttle periodic writes in the integration (e.g. every 15–30 seconds), not each frame.

## Data and privacy

`history.json` contains `version: 1` and `records` keyed by literal ASCII IMDb IDs
matching `tt[0-9]{5,12}`. Each record contains only `id`, `title` (300 characters),
`year` (four ASCII digits or empty), `genres`, `resume_seconds`, `duration_seconds`,
`lastplayed`, `completed`. Input matches `catalog.normalize()` (`genre`, singular);
stored/output metadata uses `genres`. Only the known catalogue genre vocabulary is
accepted. Invalid metadata returns `False`; unknown extra fields are discarded.
Pass only public catalogue metadata: arbitrary secrets disguised as a movie title
cannot be reliably identified. URL-shaped titles are rejected; URLs, provider rows,
tokens, artwork and local paths are never fields in the stored schema.

Only literal boolean `True` plus positive finite observed progress can write.
Zero/negative progress, invalid IDs, boolean/nonfinite numbers and invalid metadata
are rejected without creating history. Numeric inputs are bounded to `0..1e12`.
Unknown duration is zero and cannot establish completion. At >=90% of a known
duration, mark completed and reset resume to zero. Completion remains sticky during
a later rewatch, but that rewatch can have a nonzero resume position. This is a
position-based threshold, not proof the entire movie was watched (seeking can cross
it). Older timestamps cannot regress a newer sample. Retention defaults to 200,
configurable 1–500; oldest records evict deterministically. Once evicted, a title
is no longer known to have been watched.

Linux/Pi local filesystem only: descriptor-relative, no-follow traversal for every
directory component; dedicated directory must be owner-owned mode 0700 and files
owner-owned regular single-link mode 0600. Existing unsafe permissions, symlinks,
hardlinks and special files are refused rather than chmodded. Atomic unique temp
file + file fsync + same-directory replace + directory fsync; handled failures clean
up the temp. A process killed before rename can leave a private orphan temp; clear
does not sweep unrelated files. Directory advisory flock serializes cooperating
writers/clear; readers see complete old/new snapshots. Permissions do not protect
against root or malicious processes running as the same user. JSON reads are capped
at 1 MiB, schema checked, bounded to 500 records. Local backups may retain history;
clear resets only this JSON, not backups or media, and is not forensic secure erase.

## Recommendations

Pure supplied-data ranking; never obtains candidates itself. Pass an ordinary public
catalogue batch fetched independently of history. Do not send genres, IDs or history
to a remote recommendation endpoint. No upload/sync, provider/account/profile APIs,
tracking or automatic source/playback actions exist here.

Each distinct watched ID votes once per known genre. All retained history IDs
(in-progress as well as completed) and the current ID are excluded. Candidates
normalize to safe metadata only; dedupe by ID with lexicographically smallest
(title, year, sorted genres) resolving inconsistent duplicates. Rank by sum of genre
votes descending, then literal ID ascending. Input order cannot change the result.
Two distinct history IDs and known genres are required for personalization. Sparse
history or no matching genres returns ID-sorted catalogue suggestions with an
explicit honest `mode='catalogue'` explanation. When there are matches, return only
matches, not unrelated filler. Results are limited to the supplied public batch;
there is no claim to cover the whole catalogue, quality or rights/availability.
Rejoin artwork/display fields from the supplied catalogue by ID if needed.

## Verification / remaining integration

See [RED/GREEN evidence](movie-history-tdd.md). Offline core tests exercise real temp
filesystem persistence and concurrent writes; full suite passes. Other existing
suite messages about installation describe temporary test fixtures, not this Pi's
live Kodi. Parent review, callback wiring, settings/clear confirmation, display and
real playback/stop/resume acceptance remain pending. `addon.py`, Format, drives,
installed add-ons and other worktrees were not modified. No push or deployment.
