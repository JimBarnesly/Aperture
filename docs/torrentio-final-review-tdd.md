# Final review blockers: executed TDD evidence

Base: `892ef2b97cd9ea23f83fa658e468928d621d7b4d`.
All credentials, device approvals, movie metadata and provider replies in these
checks are explicitly synthetic. No account requests, deployment or push occurred.

## Vertical RED → GREEN cycles

| Behavior | Actual RED | Actual GREEN |
| --- | --- | --- |
| Owner FIFO credentials cannot block; special credentials/lock rejected | `Opening a private special file blocked` (bounded SIGALRM regression) | RD suite: 20 tests OK |
| Symlinked ancestors rejected before any read/write/clear/lock | Four subtest failures: no exception / symlinked ancestor accepted | RD suite: 22 tests OK; existing ancestor permissions unchanged |
| Cancel during successful or failing refresh stays silent | Unexpected `dialog.ok` calls after progress cleanup | Torrentio UI suite: 18 tests OK |
| Details must enter Movie actions before returning to browsing | Missing explicit Movie actions transition | Harness test: 1 test OK |
| Disposable RD + Torrentio transport reaches real clients and generated-video handoff | Missing isolated Torrentio transport wiring | Fixture suite: 2 tests OK |
| Native scenario must invoke wizard/search/source/player journey | Missing `torrentio_journey` | Fixture suite: 3 tests OK |
| Search event matches actual catalogue query encoding | `catalogue-search` absent; only `catalogue` recorded | Fixture suite: 3 tests OK |

The native journey contract test is structural, not a native execution claim.
The transport test actually imports the patched disposable modules and exercises
real RD device/token persistence plus Torrentio manifest, stream parsing, refetch,
resolver validation and cancellation, with DNS forbidden. Its placeholder file
only checks handoff path validation; it is not claimed as decoded video.

## Native fixture coverage added (not run on this host)

The existing online Kodi scenario now drives actual native input through:

- Movie actions assertion and explicit Back to browsing (fixes the deterministic
  wait-for-no-modal timeout introduced by the new actions dialog).
- Sources → Torrentio wizard → both consent screens → synthetic device approval.
  The real wizard saves credentials and the native consent marker; the service
  does not pre-seed either file.
- Explicit manifest check, submitted search, details → Find streams, source
  cancellation, playback decline, and then selected-source playback consent.
- Real production stream parsing/refetch/resolver logic over synthetic transports.
  Only its validated final URL is mapped to the fixture's locally generated video.
- Native VideoPlayer identity, exact generated-file path, green-frame screenshot
  evidence, stop, and return to the unchanged search directory. Event counts assert
  no resolution before playback consent and exactly one final resolution/handoff.

All overrides live only in the copied disposable add-on. Production packaging
never imports the QA module. This covers native UI and local decoder playback,
not live Torrentio availability, account validity, CDN delivery or physical Pi QA.

## Executed verification

```
python -m unittest discover -s tests -q
Ran 717 tests in 34.419s
OK
```

Full log: `$TMPDIR/aperture-review-full-tests.log` (temporary local evidence).
Installer messages in that log are from temporary-profile unit tests only.
`git diff --check` passed.

Native prerequisite inspection found no `Xvfb`, `pulseaudio`, `pactl`, `docker`,
or `podman`. No packages were installed and no host Kodi session was started.
Native 21.3 execution and screenshot review remain required on the existing CI
runner; no native pass or independent review is claimed here.
