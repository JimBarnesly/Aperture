# Cancellation-before-transmission: executed vertical TDD

Base: `aa8bd9fb2325b83d5401c094904ca7687d78b86f`.
Only synthetic credentials/replies, disposable HOME/configuration and isolated
loopback fixtures were used. No account traffic, external network, live Kodi,
package installation, deployment or push.

## Root cause and contract

The playback gate preceded blocking DNS/TCP/TLS work. A cancellation observed
inside those stages did not reach the real transport, so it still transmitted
the token-bearing resolver GET. The transport now checks after public DNS and
immediately before `HTTPSConnection.request`, after connection setup. Existing
cleanup closes the connection and cancels its deadline timer on refusal.

The UI supplies a client-level callback for check/find/play; playback also passes
its per-call callback through source re-fetch and resolver transport. Late resolver
replies are discarded before redirect processing. There are no automatic retries.
One-argument injected transports remain supported, including the disposable native
fixture's constructor-default override. Such injected transports own their internal
blocking-stage behavior; the real built-in transport receives the callback. No
TypeError-driven retry or signature guessing was introduced.

This is a last pre-send gate, not an atomic guarantee against cancellation after
that gate or after transmission starts. Blocking DNS/TLS is not interrupted, and
already-sent requests cannot be recalled.

## Observed RED → minimal implementation → GREEN

Each row was completed before writing the next failing behavior test. Each GREEN
was followed by the complete offline suite. Logs are temporary local evidence in
`/home/jake/.hermes/cache/scratch` (`$TMPDIR`).

| Slice / log prefix | Observed RED | Targeted GREEN | Full suite GREEN |
| --- | --- | --- | --- |
| `aperture-cancel-dns` | Resolver DNS cancellation still called HTTP request once | 1 test OK; zero HTTP requests or connections | 718 tests OK |
| `aperture-cancel-tls` | 3 UI subtests (Cancel/navigation/shutdown) each still sent resolver GET | 1 test OK; zero resolver HTTP requests, closed connection, no playback/stale error | 719 tests OK |
| `aperture-cancel-lookup` | Cancel during initial lookup DNS still disclosed synthetic token | 1 test OK; zero HTTP requests, no playback/error | 720 tests OK |
| `aperture-cancel-late` | Successful reply after cancellation returned instead of raising | 1 test OK; successful/failed late replies, exactly one send, cleanup, no final-host DNS | 721 tests OK |
| `aperture-smoke-scratch` | Runtime template parent was `/tmp`, not supplied TMPDIR | 1 test OK; real mktemp creates runtime under scratch path containing spaces | 722 tests OK |
| `aperture-cancel-refetch` | Playback-only callback was not forwarded through refetch DNS | 1 test OK; zero HTTP requests | 723 tests OK |

Each prefix has `-red.log`, `-green.log`, `-suite.log`. The smoke test's first
post-fix run exposed a test-fixture issue: empty fake dpkg output made grep's exit
1 override the expected sentinel 99 under pipefail. The fixture now prints a
synthetic matching path and exits 99, stopping before any native binary access.
The original TMPDIR RED was an actual product failure, not this fixture issue.

A subsequent **passing regression check**, not another RED cycle, exercises the
real client/transport path through the UI for all six late-result combinations:
Cancel/navigation/shutdown × successful/failed response. Exactly one resolver
request, no retry, no playback, no stale error. DNS and HTTPS connection objects
are synthetic; real network TLS and native Kodi were not exercised.

## Exact offline runner and commands

The local runner `$TMPDIR/aperture-offline-tests.sh` sets up isolation as follows:

```sh
export TMPDIR=/home/jake/.hermes/cache/scratch
RUN=$(mktemp -d "$TMPDIR/aperture-cancel-tests.XXXXXXXX")
export HOME="$RUN/home" XDG_CONFIG_HOME="$RUN/config" XDG_CACHE_HOME="$RUN/cache" XDG_DATA_HOME="$RUN/data" PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
export PYTHONPATH=tests
# $1 is log basename; remaining arguments are unittest arguments.
LOG=$1
shift
unshare --user --map-current-user --net --keep-caps sh -c 'ip link set lo up && exec python -m unittest "$@"' sh "$@" > "$TMPDIR/$LOG" 2>&1
```

Targeted selectors, each run with `-v` before/after implementation:

```
test_movie_torrentio.NetworkTests.test_cancel_during_resolver_dns_sends_no_http_request
test_movie_torrentio_ui.TorrentioUITests.test_cancel_navigation_shutdown_during_resolver_tls_sends_nothing
test_movie_torrentio_ui.TorrentioUITests.test_cancel_during_lookup_dns_prevents_token_disclosure
test_movie_torrentio.NetworkTests.test_cancel_after_resolver_send_discards_reply_without_retry
test_movies_smoke
test_movie_torrentio.NetworkTests.test_cancel_during_playback_refetch_dns_sends_nothing
```

Final commands from repository root:

```sh
sh "$TMPDIR/aperture-offline-tests.sh" aperture-cancel-regressions.log test_movie_torrentio test_movie_torrentio_ui test_movies_online_fixture test_movies_smoke -v
# Ran 43 tests in 3.342s; OK
sh "$TMPDIR/aperture-offline-tests.sh" aperture-cancel-final-suite.log discover -s tests -q
# Ran 724 tests in 32.295s; OK
git diff --check
bash -n tools/movies_smoke.sh
# Both exit 0, no output.
```

Installer/status output in the suite log comes from synthetic temporary-profile
tests, not deployment or inspection of real credentials. Native smoke regression
executes bootstrap only and substitutes dpkg before Kodi discovery; no GUI, audio,
package access or actual smoke acceptance is claimed.

## Remaining gates

Independent review; disposable native Kodi 21.3 UI/video acceptance; physical
remote/audio/video checks; explicit user approval of disclosure to
`torrentio.strem.fun` before any real-token provider request; separately authorized
live source/resolver/playback acceptance. Local tests do not satisfy those gates.
