# Isolated output-size-churn diagnostic

This is a diagnostic branch based on PR 11 source-provenance repair
`063c857816e510e1be7ad2bd713ddb55b7eb1488`. It changes no product source and
preserves the completed desktop/ARM64 baseline workflows. Its draft PR targets
`test/labwc-relaunch`, so only one new Aperture ARM64 job runs. The exact signed
Raspberry Pi `3:21.3+dfsg-1+rpt3` Kodi/GLES, Labwc `0.8.3-1` and Mesa
`25.0.7-2+deb13u1` requirements are inherited without substitutions.

## Perturbation and acceptance

Before starting Kodi, preflight the actual headless compositor through 3840x2160
at 30 Hz, 1920x1080 at 60 Hz and back to 4K30. Require actual current output
mode, scale 1 and normal transform. Unsupported modes are a harness limitation,
not a product failure.

Use one compositor and one disposable profile for four launches. Launch one is
an unperturbed 4K30 control. An independent thread watches the second launch's
first Kodi log timestamp, then requests 1080p at +2.903 seconds and restores 4K
at +3.640 seconds. These offsets are not anchored to Popen, Home or keyboard
input. Both request and verified-output timestamps must fall between the target
offset and 100 milliseconds afterward. Missed timing fails distinctly; there is
no delayed substitute or timing sweep. All later launches are unperturbed 4K30.

The first-log wall clock is UTC and is mapped to a monotonic deadline. More than
20 ms divergence fails. Actual requested/observed output mode, raw Wayland
configure timestamps, live log-receipt timestamps and skin/Home-load milestones
are retained. Original Wayland clock values are not falsely labelled UTC; live
receipt timestamps are separately identified and may lag event generation.

Before any keys on launch two, require actual ordered xdg_toplevel sizes
4K/1080p/4K. The final restored configure serial must have an eventual matching
Kodi ApplyNextState and xdg_surface acknowledgement. The same wl_surface must
then request a frame, commit and receive that callback. Only then may the
compositor capture be taken. All four launches retain the independent fresh Home
state, recognizable compositor-captured Home text/pixels before input, stable
native Exit focus, original child PID exit status zero and same profile/compositor
checks. The only baseline harness changes add no-op hooks and explicit image/state
size parameters whose defaults remain 1920x1080.

## Interpretation and limitations

The observed Pi incident loaded Home at +0.638 seconds, before both mode changes.
Software rendering may still be loading at +2.903 seconds. The report records
that difference. Matching elapsed offsets does not establish the same lifecycle
phase or physical failure conditions. Kodi can coalesce queued configures, so the
report separately records actual ProcessMessages, ApplyNextState and configured,
surface and buffer size changes. Protocol delivery alone does not establish that
the intermediate 1080p size was applied. A final Home after coalescing cannot be
presented as reproduction of the Pi's actual applied-size sequence.

This test changes dimensions only. It does not reproduce HDMI/EDID disappearance,
a transient 0 Hz mode, PipeWire/audio enumeration changes, hardware V3D or physical
Pi behavior. The incident's 1080p refresh is unknown; synthetic 60 Hz is an
explicit test choice, not a claim about the incident. A passing run rules out only
this exact synthetic perturbation under the measured lifecycle conditions.

`result.json` distinguishes unsupported modes, missed timing, harness configure
validation failures, inconclusive perturbations and product reproduction
candidates. An unverified injection cannot count as a reproduction. A missing
final apply/ack/frame after verified modes/configures remains a candidate for
manual trace review, never an automatic claim about the physical Pi.

No production patch, workaround, deployment, device action or remote coordination
message is part of this experiment.
