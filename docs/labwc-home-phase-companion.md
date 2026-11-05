# Home-phase-aligned companion

This is one separately labelled companion to the retained PR 12 and PR 13
first-log-timed experiments. It uses the exact signed Pi userspace from PR 13
without modifying that runtime, the previous workflows or original drivers.
It is **event-aligned, not timestamp-identical** to the physical incident.

The incident loaded Home.xml at +0.638 seconds from the first Kodi log entry,
then changed dimensions at +2.903 and +3.640 seconds. In software CI, Home loaded
around +6.288 seconds, after both first-log-scheduled changes. That phase
mismatch prevented the previous runs from exercising the observed applied-size
sequence, although they established a separate compositor geometry behavior.

This companion anchors only to the first fresh current-PID
`Loading skin file: Home.xml` log entry, after the current launch's fresh first
log. It then schedules 1080p after 2.265 seconds and restores 4K after 3.002
seconds. The 0.737-second gap is unchanged. Both Home-relative and first-log-
relative requested/observed times are retained. Request and observation must
still meet the original 100 ms lateness tolerance; there is no catch-up, extra
configure, broader timing sweep or additional fallback variant.

Use one compositor/profile for four launches. Only launch two is perturbed.
The inherited pre-input barrier still requires real ordered 4K/1080p/4K xdg
configures and final matching apply/ack/same-surface frame/commit/callback. This
companion additionally requires intermediate 1080p processing and application,
with actual configured, surface and buffer dimensions all changing 4K→1080p→4K.
Only that full evidence qualifies an applied-size sequence match. Each launch
must show fresh 4K Home state plus recognizable compositor-captured Home before
keys, followed by native Exit of the original PID with status zero. Signals
remain failure-only cleanup. Subsequent launches are unperturbed.

The session setup is identical to the original isolation script except for an
explicit phase-companion driver selection. Hash tests protect the original
churn driver, native lifecycle driver and session script from accidental edits.
The separate workflow targets `test/labwc-pi-userspace-churn`, so previous jobs
are not repeated or relabelled.

A pass establishes geometry-only acceptance in this event-aligned software
fixture. A failure retains its precise classification without silently changing
the schedule. Neither result establishes a physical blackout cause. No V3D
hardware, HDMI/EDID disappearance, zero-Hz mode, audio/PipeWire enumeration churn,
CEC or production profile is reproduced. The incident's 1080p refresh remains
unknown; synthetic 60 Hz is explicitly chosen. No Pi or production action occurs.
