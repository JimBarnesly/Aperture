# Aperture technical handoff

Updated: 2026-11-04 22:44 UTC. Public, sanitised project status only.
This note is not deployment permission or a claim of physical-device acceptance.

## Branch and verification

- Work branch: `fix/kodi21-startup`, [draft PR #5](https://github.com/JimBarnesly/Aperture/pull/5). Not merged.
- Last fully green baseline: `b9787e1fb6b81a502748cabfa81b0f8f5ce0b7a4`.
- Its [gaming](https://github.com/JimBarnesly/Aperture/actions/runs/41868502505),
  [startup/ZIP](https://github.com/JimBarnesly/Aperture/actions/runs/41868504736),
  [menus](https://github.com/JimBarnesly/Aperture/actions/runs/41868502565),
  [Movies](https://github.com/JimBarnesly/Aperture/actions/runs/41868502657) and
  [casting](https://github.com/JimBarnesly/Aperture/actions/runs/41868519928) workflows passed.
- This integration candidate extends that baseline. 336 local tests and complete
  Omega skin assembly pass. Check native CI at the exact commit containing this
  note before testing an installation. Historical runs do not certify newer code.

## Unified Format music candidate

Music opens the Format-backed library directly. The Local music / Format
streaming split is removed. Native album shelves and lists provide albums,
artists, local library search, artist catalogue previews and download/status
controls. Standalone Format is unchanged; both clients share its backend.

The client confirms acquisition and queue changes, rechecks explicit write
capability at action time, rejects redirects and never automatically retries an
uncertain write. Non-folder actions preserve Kodi Back history. Published-only
playback, ordered releases and server publication validation remain intact.

The protected Pi profile remains read-only. Acquisition, cancellation and
prioritisation are disabled there. A writable deployment also needs compatible
staging/publication and authorised provider access; changing a flag is not enough.
The skin does not change server permissions, expose the API to a LAN, or grant
operator access. See [Format installation and acceptance](docs/format-integration.md).

Install the matching Format add-on and complete skin from one pinned green
checkout with Kodi stopped. Preserve Estuary, backups and existing settings.
Reuse a healthy existing server. Do not rerun gaming setup or modify media as
part of this update. Synthetic CI does not prove physical audio, storage,
controller or provider operation. No animation/background changes are included.

## First integrated GUI run

At `7bb3687ba9a28420adc5f58b2154299f6babf0b2`, the native run verified direct
Music entry, album shelves, track order, Back, playback and offline recovery.
It then [stopped in test navigation](https://github.com/JimBarnesly/Aperture/actions/runs/41927968556)
before catalogue/download acceptance: reactivating the active Music window did
not return to the root. The harness now traverses actual Back history instead.
This candidate also gives each Music section a stable contextual heading.
The full corrected native run is still required; do not treat partial coverage
as a pass or infer real provider/device acceptance.

## Other implementation boundaries

- Console-card restoration after game Stop and native Back is fixed at the green
  baseline. Both ARM64 and x86 tests cover NES/PS1 playback and return navigation.
- Physical controller teardown/input instability remains a separate unresolved
  hardware acceptance issue. CI has no physical joystick and cannot clear it.
- The Movies browser and local artwork/playback paths have dedicated synthetic
  acceptance. See [local Movies](docs/local-movies.md).
- Format server baseline: [draft PR #1](https://github.com/JimBarnesly/Format/pull/1),
  commit `1eea9b8a62c0bbdbf41fdef68f4343113fc94589`. It passed server and ARM/x86 Pi
  safety checks; deployment to a particular device must be established locally.
- Experimental casting is not a certified general Chromecast receiver. See
  [casting documentation](casting/README.md) for its scope and limitations.

## Feedback and safe installation

Before changing or publishing code, read current PR/commit comments and remote
head. Reconcile changes instead of overwriting them. Report exact commit IDs,
versions, steps and outcomes. Do not merge as part of this draft workflow.

For physical tests, inspect actual storage and installed state locally. Preserve
media and saves. Stop at an unexpected crash or data-risk condition, retain local
logs, and keep recovery available. Never publish usernames, private paths,
hostnames, addresses, device identifiers, credentials or unredacted logs.
Public feedback should contain only the minimum sanitised technical evidence.
