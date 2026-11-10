# Online-first native Movies home

Local candidate on `feat/movies-home`, based exactly on
`9d4858102e9d297a3a98815539b64ad06ab15b92`. Not deployed or pushed.
Requires the matching skin **and** Movies client. Main is unchanged.

## Experience

Main Home → Movies opens native custom window 1120 (runtime ID 11120), not
local folders. Three horizontal rows remain visible: Continue watching,
Suggested for you, Popular / Featured. Search starts focused on first entry;
Left/Right browse posters, Up/Down traverse rows/header, Back returns. Empty
rows are disabled, not populated with fake cards. Retry and local fallback stay
reachable without a catalogue. Header also offers Browse all, History, discreet
Local files, Sources / settings and Home. Local files preserves the existing
source/default-folder logic; the legacy bare plugin root remains that local
route for compatibility, but is no longer the main Home entry.

Select explicitly runs the existing `torrentio_auto` action; Continue watching
adds `resume=1`, resolves a fresh source and reads the real saved position.
Context menu retains Choose source and Play from beginning, and offers Movie
details (Cinemeta). No source/account lookup occurs on home load or focus.
Metadata is not a promise of streaming availability. Existing setup/sharing
permissions and autoplay preferences remain unchanged.

Focused-title panels display supplied title, year, genres and synopsis. A missing
synopsis says **Details unavailable** and points to the explicit metadata details
action. No per-focus detail requests, debounce workers or guessed file identity:
rapid scrolling makes no extra metadata/source requests. Movie catalogue and
details routes reject declared `series` results, including a same-title series;
IMDb identity is retained, never fuzzy relabelled. This is not a TV catalogue.
Browse-all/search also retains the supplied year and a missing-plot fallback;
its footer now displays the actual category instead of the misleading static
KODI LIBRARY / FILES label.
Continue watching uses privacy-minimized saved metadata and packaged art fallback;
it does not remotely fetch posters for watched IDs on load.

## Data and recovery

Continue watching reads only the existing private history store, with no network.
Suggestions locally rank a default public top catalogue batch, exclude watched
IDs and reuse its public artwork. History, genres inferred from history, refresh
nonces and resume positions are never sent as catalogue query parameters.
Sparse-history recommendations are labelled catalogue suggestions only.
Popular / Featured interleaves and deduplicates the two default public batches,
with a 20-card row limit; Browse all retains existing pagination. Each failed
public collection is isolated so the other collection can still render.

Catalogue failures and corrupt history produce generic inline statuses, not
startup modal traps. Retry changes an opaque window-property nonce in the local
widget URL. Kodi's directory provider notices the changed URL and refetches; the
nonce is discarded before constructing public requests. Window load does the
same, refreshing history after playback/clear. No persistent cache was added.
A corrupt history file is preserved until the existing explicit clear flow.
History errors cannot hide Local files or prevent public browsing.

Kodi source inspection confirmed custom list `onclick` overrides directory
provider selection, avoiding the native video-select setting and routing directly
to the existing action. It also confirmed there is no `Control.Refresh` builtin;
refresh uses the directory provider's URL-change mechanism instead. The new
window is included in the existing session-bound pause-on-fullscreen-exit policy.

## TDD and executed evidence

Each behavior was introduced after an observed failing focused test, then made
green: metadata-only popular row; local resume; private suggestions/art; isolated
errors/retry; home focus graph; search cancellation/stale navigation; Sources
landing; packaging/assets; home pause/latch; featured inclusion; native QA
contracts; explicit select dispatch; empty states; supported widget refresh;
focused genuine metadata/type separation and missing-details fallback.

Final full offline command (isolated network namespace, loopback fixtures only):

```
unshare -Urn sh -c 'ip link set lo up && python3 -m unittest discover -s tests -q'
```

852 tests passed in the final full run (43.310 seconds), with 16 focused home
tests and 32 ZIP-driver tests also passing independently. Initial full run lacked namespace
loopback and failed only HTTP-fixture connections; rerunning with loopback enabled
removed that environmental failure. A later full run caught the Home generator
still emitting the old route; corrected the generator, then reran successfully.

Real complete Estuary-based skin and Movies ZIP assembly passed for the original
home candidate, before the async review fixes below. Historical SHA256:

- Skin: `5768b4589ca2bac890428c2b865a69854f6673ba6e6d9e82539beaf04e617427`
- Movies: `1aa35fca52b0797c14980cca8f5832d161d36cd79963ba1dff9cc888d3f786dd`

All fonts used
by the custom home exist in the assembled skin. Source installer checksum and ZIP
builder include the same custom window. Full tests exercise only disposable
profiles, including preservation of unrelated Format/Games/settings files.

Public-only probe: Cinemeta top and imdbRating each returned 50 movie records;
all 50 in each batch contained plot, year and genres. No account/source requests
were made. Missing metadata remains covered synthetically rather than assumed
impossible.

## Async review fixes (base `26ad95f`)

Row status publication is now fenced by the refresh generation carried in the
widget URL, compared immediately before writing the Home property. Do not claim
ownership by overwriting the generation at job startup: an old queued job can
start after Retry. Kodi can cancel the directory completion callback while the
old Python invocation continues; completing that invocation must not overwrite a
newer row's success or failure status. Directory completion remains native; no
new source lookup, remote query parameters, history write or modal error is added.

Explicit details capture both the originating window ID and FolderPath. Success
and error dialogs, the following Movie actions menu and its selected action are
guarded after every blocking step. An opaque in-memory invocation token prevents
a newer details request in the same window from being superseded by an old one.
No movie identity, title or URL is stored in that property.

Review TDD evidence:

- Baseline: **852 tests passed** before edits.
- Overlapping Retry regression failed with `Cinemeta unavailable` replacing a
  newer successful row. The new invocation completes inside the old fetch before
  the old failure is released; this is not a sequential retry test. GREEN after
  generation gating; full suite **853 passed**.
- Details fetch transitions **11120 → 10000 with both FolderPaths empty** failed
  for both success and error responses. Transition after each modal also failed
  (stale menu or stale Find streams action). Window checks made these GREEN;
  full suite **855 passed**.
- Same-window replacement details requests failed at fetch/dialog/action-menu
  boundaries; invocation fencing made these GREEN; full suite **856 passed**.
- Additional late-start/old-success coverage exercises all three row names. It
  fails against the pinned base source and passes against the candidate.
- Final loopback-only network-namespace run: **72 focused tests passed**;
  **857 full-suite tests passed** (44.943 seconds), preserving all baseline tests.
- The modal-transition fake initially exhausted its window-ID iterator before
  the transition. Replaced it with mutable window state, reran against the pinned
  base (four expected assertion failures), then GREEN without changing assertions.

Python property comparison plus publication/dialog opening is not an atomic Kodi
transaction. These checks suppress results stale at each boundary; they cannot
prove no navigation can happen between the check and the next native API call.
Native execution is not claimed by the deterministic offline tests.

### Additional exact-head native synthetic acceptance

Keep the existing immediate Back and offline Retry assertions unchanged. In the
disposable native transport, use explicit request-start/release barriers rather
than sleeps to exercise these additional cases before deployment:

1. Hold an old catalogue failure, trigger Retry, let the newer row succeed, then
   release the old failure. Assert the new cards **and** successful inline status
   remain after the old Python invocation has finished.
2. Hold a movie-details success, Back from Movies home to main Home, release it,
   and assert no details dialog, Movie actions menu or source lookup appears.
   Repeat with a failed metadata response. Verify the transition is 11120 → 10000,
   not only a FolderPath change, and keep both paths empty for this case.
3. Supersede details in the same window while its fetch is pending; only the newer
   request may present UI or dispatch a source action. Repeat replacement while
   the older details/actions modal is closing.

These added native race cases are a pending acceptance recipe, **not implemented
or executed native coverage**. Existing native synthetic scripts and assertions
are unchanged; this task performs no Kodi/profile/account actions.

## Native acceptance still pending

Updated online native synthetic QA covers Home Movies entry, empty Continue,
row traversal, repeated cancelled Search, focused synopsis/year/genres, no source
lookups while browsing, Local files/Back, catalogue outage/Retry, home Resume and
immediate Back pause. ZIP QA now enters the online-first home before explicitly
checking no-local-source guidance. Existing local-source QA remains independent.

Native execution is **blocked here**: Xvfb, pulseaudio and pactl are absent.
No package installation, live Kodi controls, profile writes, restart, deployment,
account calls or push were performed. Parent must run exact-head native workflows
and visually review poster layout, focus restoration, remote text readability,
context-menu action routing and playback/Back/resume before deployment. Offline
XML/fakes and public metadata responses do not establish those native guarantees.
