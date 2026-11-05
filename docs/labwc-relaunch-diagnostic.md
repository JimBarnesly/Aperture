# Kodi 21.3 Labwc normal-Exit diagnostic

This isolated experiment starts from integration commit
`425400e879add799610524af65dd02783501bad1`. It adds no production workaround,
Kodi patch, display setting change, installer change or physical-device action.
The physical Pi blackout remains unresolved regardless of this experiment.

## Acceptance

Each matrix job uses a separate new Estuary or Aperture profile. One real Labwc
compositor and one profile persist for four Kodi launches, covering three actual
normal-Exit/relaunch cycles. Every launch must show fresh observer state for Home
and compositor-captured pixels containing at least three recognizable Home labels
before any synthetic key is sent. Black/noisy images cannot pass on pixel
variance alone. The selected native power-menu Exit must map uniquely to `Quit()`
in the installed XML; its live focus and English label are checked before Enter.
Only the original child exiting with status zero counts. Signals are failure-only
cleanup and never satisfy normal Exit. Settings before and after each cycle,
process identities and input timestamps remain in the artifacts.

## Environment and evidence

Official Debian Kodi 21.3, native Wayland, headless Labwc Pixman and Kodi Mesa
llvmpipe; unprivileged user, private runtime directory and D-Bus session. No host
Wayland/X11 socket, hardware input/display device, system bus, seatd, uinput,
privileged container, media, emulation or network API is needed. A no-input wtype
client establishes virtual keyboard capability before Kodi; capability timing
and protocol details are retained. Native `s`, navigation and Enter are the only
Kodi inputs. There are no custom keymaps or observer mutations.

Artifacts contain full synthetic Labwc/Kodi/EGL/Wayland logs, screenshots, OCR,
GUI states, package versions, before/after settings and extracted
configure/ack/commit/frame traces. `result.json` distinguishes `harness_failure`,
`harness_visual_validation_failure`, `unexplained_visual_failure`,
`product_reproduction_candidate`, and
`passed`. An initial environment failure is not evidence of a Kodi relaunch bug.
A reproduction candidate still needs trace and screenshot interpretation.

A clean run on headless desktop GL is not equivalent to Raspberry Pi GLES,
physical outputs, CEC, controllers or the downstream Raspberry Pi Kodi build.
The known upstream configure/apply hypothesis is not patched or assumed proven.

Run on a disposable machine with the workflow's dependencies:

    APERTURE_WAYLAND_SKIN=estuary bash tools/ci_labwc_relaunch.sh

Use a new empty output directory for another skin/run. Do not run against a real
user profile or connected hardware session.

## Verified desktop baseline and configure-delay interpretation

At head `ca36d4581936db3f687b14d8d01934b430c55ce6`, both skins passed
[run 42037056930](https://github.com/JimBarnesly/Aperture/actions/runs/42037056930):
four successful Home launches and four native Exit status-zero results per skin.
That runtime used Kodi `2:21.3+dfsg-2`, Labwc/wlroots `0.20.2`, Mesa `26.1.6`
and llvmpipe OpenGL 4.6, not GLES.

Labwc's "did not respond to configure request in 100 ms" warnings also occurred
in these successful runs. In Aperture launch four, the second configure arrived
at 13:36:44.627 UTC; Kodi processed it at 13:36:50.657, applied it at
13:36:50.761 and acknowledged it at 13:36:50.764. The roughly 6.14-second delay
ended in a rendered Home before input. Compare elapsed time, eventual application
state, acknowledgement and frame commits. A warning alone is not a blackout
reproduction or proof that the configure/apply queue remains stuck.

## Exact downstream ARM64 comparison

The additional `rpt3-arm64` jobs use Debian trixie on an ARM64 CI runner, with no
Pi hardware, hardware devices, host session or privileged container. The original
passing lifecycle harness remains unchanged. A wrapper verifies all packages and
requires the real Kodi runtime log to identify native Wayland, llvmpipe and
`OpenGL ES` on all four launches; desktop GL or another package cannot pass.

Pinned packages are Kodi, kodi-bin and kodi-data `3:21.3+dfsg-1+rpt3`; the seven
required Raspberry Pi FFmpeg libraries `8:7.1.5-0+deb13u1+rpt2`; Debian Labwc
`0.8.3-1`; and Debian Mesa graphics `25.0.7-2+deb13u1`. The official Raspberry Pi
trixie repository is scoped by `signed-by`, with signing-key fingerprint
`CF8A1AF502A2AA2D763BAE7E82B129927FA3303E`. The exact official keyring package `2025.1+rpt1` supplies its renewed SHA-512
certifications, with package SHA256
`2e727149d7acb8cc7f604e66d0049161039c8aa1eaf1175e54f9e69d963d60e4`.
The legacy standalone key file was rejected by current APT policy for SHA-1
certifications; verification was not weakened. APT signature verification remains
mandatory. Debian remains preferred for unrelated packages. Missing pinned
versions, signature failures, dependency constraints or a non-GLES runtime stop
the diagnostic instead of silently approximating the requested environment.

Artifacts retain the signed InRelease, signing-key fingerprint, package policy,
installation plan, full installed versions and all lifecycle evidence. This
closes only the package/GLES comparison if it passes. It still cannot establish
physical Pi graphics-driver, output, CEC, controller, audio or persisted-profile
behavior, and it applies no production patch or workaround.

## Source provenance

`commit.txt` and `tree.txt` come from the actual checked-out Git HEAD and tree.
The workflow passes the intended PR head through `APERTURE_EXPECTED_COMMIT`;
a mismatch or modified tracked source fails before GUI startup. The separate
`source-provenance.json` records both identities and the GitHub event SHA for
context. GitHub's protected `GITHUB_SHA` can identify the synthetic PR merge
commit even when checkout explicitly selects the PR head; it must not label the
tested source. Run 42040483312 checked out head `8fb37975` in all four checkout
logs but mislabeled its old `commit.txt` with that event merge SHA.
