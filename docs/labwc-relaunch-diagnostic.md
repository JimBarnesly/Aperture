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
