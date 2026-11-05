# Exact Pi userspace comparison

This separately selected variant preserves the PR 12 source, timing and original
result at `d7fb354f6d641a0be07202da2e7ed07090d07534`. The old workflow remains
unchanged. Only the new workflow targets `test/labwc-output-size-churn`, and it
requires the explicit `exact-2026-11-05` userspace selector.

The first dimension-churn run used exact rpt3 ARM64 Kodi/GLES but Debian Labwc
0.8.3 and Mesa 25.0.7. It produced recognizable quarter-size Home after output
restoration, not a blackout: no restoring 4K xdg configure reached Kodi. The Pi
uses a newer compositor and graphics stack. This comparison closes that known
userspace-version difference without forcing a configure or shifting timing.

## Exact requested runtime

Use the official signed Raspberry Pi trixie repository for Labwc
`0.20.2-1~bpo13+1`, wlroots `0.20.2-1+rpt4`, Mesa
`26.2.2-1~bpo13+0~rpt1`, Wayland `1.24.0-2~bpo13+1~rpt1`, DRM
`2.4.134-3~bpo13+1+rpt1`, libinput `1.28.1-1+rpt1+deb13u1` and xkbcommon
`1.13.1-1~bpo13+1+rpt1`. Preserve Kodi `3:21.3+dfsg-1+rpt3` and matching
FFmpeg `8:7.1.5-0+deb13u1+rpt2`. Debian remains preferred for unrelated packages.
These are official Raspberry Pi repository packages, not packages from Debian
trixie-backports merely because their versions contain `bpo13`.

The installer first establishes the unchanged signed baseline, records its
package list, then simulates the exact userspace upgrade. Before installation,
reject all package removals and changes outside compositor/userspace libraries
or xkb data. Kernel, firmware, Raspberry Pi service/device packages, udev,
systemd, seatd and PipeWire changes cannot pass this guard. No such services are
started or used by the headless test. The actual headless isolation remains
unprivileged with no hardware devices or system bus. A dependency failure is a
setup limitation, not permission to change the host or physical Pi.

No broad distribution upgrade, unsigned repository, relaxed signature policy or
package-version substitution is permitted. Preserve the simulation, repository
policy, baseline and final package lists, and source/runtime evidence.

## Acceptance and limits

Run the exact same `labwc_output_churn.py` driver and its strict acceptance.
4K30 control, timed second-launch 1080p60/4K30 requests at +2.903/+3.640 seconds,
final application and rendering before keys, native original-PID Exit zero,
same compositor/profile and later unperturbed launches remain unchanged. Require
actual llvmpipe GLES with Mesa 26.2.2 in every completed Kodi launch.

No Pi hardware, physical V3D, HDMI/EDID disappearance, zero-Hz mode or audio
churn is reproduced. The incident's 1080p refresh remains unknown and software
Home loading can occur at a different lifecycle phase. Source similarity or a
passing software-only result is not proof about the physical blackout.
