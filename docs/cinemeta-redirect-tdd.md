# Cinemeta catalogue redirect fix — local evidence

2026-11-10 UTC. Base: `98e61d8c0243cf5a1fcc3e7fc864ef735289514a`.
Branch: `fix/cinemeta-catalog-redirect`, isolated worktree; no shared-owner
checkout edits, push, deployment, Kodi/UI, account or provider-credential access.

## Public contract and reproduction

Public GET probes with automatic redirects disabled returned:

| Original path on `https://v3-cinemeta.strem.io` | Status | Location |
| --- | --- | --- |
| `/manifest.json` | 200 | none |
| `/catalog/movie/top/skip=0.json` | 307 | `https://cinemeta-catalogs.strem.io/top/catalog/movie/top/skip=0.json` |
| `/catalog/movie/imdbRating/skip=0.json` | 307 | `https://cinemeta-catalogs.strem.io/imdbRating/catalog/movie/imdbRating/skip=0.json` |
| `/catalog/movie/top/skip=100&genre=Drama.json` | 307 | `https://cinemeta-catalogs.strem.io/top/catalog/movie/top/skip=100&genre=Drama.json` |
| `/catalog/movie/top/skip=0&search=matrix.json` | 200 | none |
| `/catalog/movie/top/skip=0&search=matrix&genre=Drama.json` | 200 | none |
| `/meta/movie/tt0133093.json` | 200 | none |

The [official addon index source](https://github.com/Stremio/stremio-official-addons/blob/master/index.json)
confirms the v3 manifest transport, movie `top` extras `search`, `genre`, `skip`,
and movie `imdbRating` extras `genre`, `skip`. An attempted `Stremio/cinemeta`
source lookup returned 404; no server-source claim is made. Actual endpoint
responses above establish the precise redirect contract used here.

The unconditional `NoRedirect` handler turned the legitimate 307 into
`CatalogError: Online catalogue unavailable`. Search and details require no
redirect exception; they remain fail-closed if that contract changes.

## RED → GREEN

Command for each focused cycle:

```
python3 -m unittest discover -s tests -p test_movie_catalog_redirect.py -v
```

1. Wrote `test_observed_catalogue_307_returns_json` before production edits.
   RED: one error, `CatalogError: Online catalogue unavailable`, from the
   unchanged redirect rejection. Implemented the exact observed route. A test
   expectation for urllib's `Connection` header was corrected: that header is
   added later by the actual socket transport, not by the Request processor.
   GREEN: original catalogue suite plus regression, 10 tests passed.
2. Added paging/genre/Featured route coverage before generalizing the rule.
   RED: seven route subtests raised `CatalogError`. Constrained source matching
   to the two collections, existing offset bounds and genre list; derived the
   sole exact destination. GREEN: 11 tests passed.
3. Added rejected-status response-closure coverage before changing closure.
   RED: 301/302/303/308 responses were not closed. Added explicit close/refuse
   handlers. GREEN: 12 tests passed.
4. Added defense-in-depth tests for existing refusal/size/error invariants:
   arbitrary hosts, credentials, ports (including 443), queries, fragments,
   relative URLs, path substitutions/traversal, raw and encoded injection,
   duplicate Location, non-GET, search/details redirects, second hops/loops,
   fresh headers, unread redirect body, invalid JSON and 2 MiB boundaries.
   All passed without further behavior changes. Renamed the handler to
   `CatalogRedirect` in a green refactor. Focused suite: 19 tests passed.

Tests use actual urllib opener/error dispatch with a scripted HTTPS transport,
not a replacement redirect implementation. Redirect bodies are never drained.
Only the original host can match the source rule, structurally limiting each
fetch to one hop; fresh GET requests carry only public Accept/User-Agent headers
plus urllib's generated transport headers. Eight-second **socket** timeouts
remain per connection, not a newly claimed total-operation deadline.

## Final verification

```
python3 -m unittest discover -s tests -q
Ran 734 tests in 35.840s
OK

mypy movies-kodi/resources/lib/catalog.py tests/test_movie_catalog_redirect.py --ignore-missing-imports --follow-imports=silent
Success: no issues found in 2 source files

git diff --check
# exit 0
```

Installer output in the full suite belongs to temporary test profiles, not a
live installation. Static changed-line checks found no hardcoded secrets,
shell execution, eval/exec or pickle calls. Parent independent review remains
separate from this implementer's self-review.

Real public requests through the patched `catalog.browse` / `catalog.details`:

| Case | Result |
| --- | --- |
| Popular | 50 normalized movies, next offset 50 |
| Featured | 50 normalized movies, next offset 50 |
| Drama at offset 100 | 50 normalized movies, next offset 150 |
| Search `matrix` | 20 normalized movies, next offset 20 |
| Search `matrix`, Drama | 20 normalized movies, next offset 20 |
| Details `tt0133093` | matching ID and nonempty title |

These prove the public metadata path at verification time, not playback,
provider availability, or native TV navigation. Deployment belongs to the parent
owner and was not performed.
