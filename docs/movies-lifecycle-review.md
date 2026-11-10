# Autoplay lifecycle review fixes — local only

Base: `7fbcf66ade72cf1ed7c69eedb319062adabcea08`. No deployment, push,
device, live Kodi or account actions.

## Review against the history integration

The new history bridge already supplies a unique `aperture_session` on each
ListItem and records only matching, positive progress. It did **not** fix the
startup helper's global callbacks, premature predecessor rejection, or unguarded
stops. The pause guard still remembered only a fullscreen boolean. These findings
were reproduced on the requested HEAD before changing their implementations.

Startup now reuses the history session, rather than using a URL as ownership.
A metadata/history outage supplies a fresh opaque startup-only token; a valid
history token is never replaced. Existing history persistence, explicit resume,
clear epoch, final samples and suggestions remain intact. Abandoned startup
clears only its matching pending history handoff, so a later history observer
cannot adopt that abandoned request. No URL is added to persisted state.

## Changed behavior

- Retain the startup observer through predecessor playback and its Stop/End
  transition. Only a matching session's AV callback plus active video establishes
  startup success. A predecessor callback cannot certify a later session.
- Ignore unowned errors; they do not authorize fallback while an open is pending.
  Player-error fallback requires a matching callback, no active video and still
  attributable ownership. Unknown/replaced ownership is not retry permission.
- Recheck session ownership immediately before every stop, including after
  navigation checks, abort waits, error checks and the final deadline. Never
  intentionally stop an unknown or different owner.
- Navigation cancellation is sticky. While the original bounded startup loop is
  alive, a late matching open is stopped instead of reported as success. There is
  no new observer that adopts an abandoned request as successful playback.
- Pause-on-exit binds its fullscreen state to the current session (or in-memory
  file identity for untagged local movies), disarms on replacement and rechecks
  identity immediately before explicit pause. It never toggles or auto-resumes.
- Separate versioned `autoplay-effects-v1` allow/decline preference, stored with
  the existing owner-only atomic storage machinery. Fresh native setup/import
  asks once; existing configured profiles ask at their first automatic selection.
  No automatic lookup/resolution occurs before acceptance. Decline persists,
  retains account sharing and metadata/manual Choose source, and can be changed
  explicitly in Sources setup. No repeated rights warning or per-play prompt.

## TDD evidence and verification

Focused unittest RED runs demonstrated: predecessor Stop/AV returned cancelled;
unrelated errors returned failed; current/abort/deadline owner replacement was
stopped; cancelled pending opens were abandoned early; predecessor AV certified
a later open; unreadable ownership escaped as a runtime error; same-file session
replacement was mistaken for the predecessor; lost error attribution allowed
retry; replacement movies inherited fullscreen pause; mid-decision replacement
was paused; history outages lacked a startup token; cancelled startup retained
its pending history; existing configured users resolved without opting in; native
setup/import did not record the preference; and native QA omitted the new dialog.
Each behavior change followed its corresponding failing run and focused GREEN.
Existing callback fakes were updated to expose explicit session identity instead
of relying on file equality/global callback assumptions.

Additional already-GREEN regression coverage checks accepted migration ordering
and no repeat, navigation during consent, owner-only preference mode, preserving
a newer history handoff, and owner replacement during active-error cleanup. These
are regression confirmations, not claimed as new RED cycles.

Full offline suite: **826 tests passed**, using:

```
unshare --user --map-current-user --net --keep-caps sh -c \
  'ip link set lo up && exec python3 -m unittest discover -s tests -q'
```

Only loopback was enabled in the unprivileged network namespace. Installer test
messages concern disposable fixtures. `git diff --check` passes. Native synthetic
QA now requires the versioned opt-in and an actual propagated session tag, but
was **not run**: Xvfb, PulseAudio and pactl are absent. No packages were installed.
Parent independent review remains required; this is not an independent verdict.

## Native guarantees still unresolved

Kodi callbacks contain no event session ID. Sampling the current item's tag is
conservative correlation, not proof of native callback provenance. Delayed native
callbacks that arrive after a replacement exposes its tag need actual Kodi tests.
Kodi has no atomic compare-session-and-stop/pause API: a native replacement in the
interval between the final ownership read and the command remains a platform
race. Untagged local playback uses file identity and cannot distinguish two
unobserved generations of the same file.

Most importantly, an open with no readable session cannot be cancelled safely
using global Stop. On shutdown or the bounded deadline this helper returns
without stopping unknown ownership and without retrying; an unidentifiable
queued open may still complete later. The implementation does not claim that it
can revoke Kodi's native pending-open queue. Tag propagation during open, callback
ordering, shutdown/deadline cancellation, rendering/audio and physical Back remain
native acceptance gates. These limits are deliberately not hidden behind unsafe
global Stop or synthetic claims of cancellation.
