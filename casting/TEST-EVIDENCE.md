# Experimental candidate evidence, 4 November 2026

## Executed in isolated cloud environment

- Node 24.22.1, Linux x86_64, no Google account or cookies.
- Pinned upstream tarballs installed successfully, including the required
  Volumio-YouTube.js Git dependency compile step.
- Initial npm audit: 11 advisories (5 high, 6 moderate).
- After exact overrides in package.json/package-lock.json: **0 advisories**.
  This is an audit snapshot, not a guarantee of security.
- Own offline tests + installed dependency compatibility tests: **16 passed**
  on both Node 24 and Node 20 (Linux x86_64). Clean npm ci also reproduced the build.
- EJS XML escaping, UUID generation, query parsing and Happy DOM canvas API tested.
- Patch script is idempotent and fails closed on unexpected upstream source.
- Actual YouTube Music public track dQw4w9WgXcQ resolved, signed googlevideo audio
  URL passed ranged HTTP request. URL/token values were not recorded.
- Resolver successfully initialized, including PO-token helper. A non-music public
  video was rejected by YouTube Music, so this is not a general video receiver.

Cloud-only test adaptation: upstream helper drops environment variables. Its test
copy forwarded the existing HTTP(S) proxy and NODE_EXTRA_CA_CERTS settings, with
Node's environment-proxy option, to retain the cloud's network routing and trust.
TLS verification was never disabled. This adaptation is not in the Pi candidate.

## Not established

- SSDP discovery is blocked by cloud network-interface enumeration restrictions.
  No official Android app was connected.
- No proof of Premium/paid-only content, ad-free entitlement, account library,
  autoplay queues, phone lock/reconnect or casting-session lifecycle.
- No physical Pi, mpv audio device, HDMI, Kodi coexistence or Bluetooth-controller
  acceptance test. mpv IPC behaviour is tested with injected mock socket events.
- Node 22 and ARM64 are intended targets but not executed here.
- No automatic installation/startup or Pi changes occurred during tests.

## Reproduction and acceptance

In a disposable test directory copy casting/, run npm ci,
node patch-support.mjs, npm audit --omit=dev, and node --test test/*.test.mjs.
Use node probe-public.mjs --run for the network probe. These commands run the
explicitly listed dependencies; no user account is necessary for this probe.

Before treating this as production-ready, test on the Pi and confirm the
current dependency audit. The explicit --install PI_LAN_IPV4 opt-in installs a
user service but does not start or enable it.

Live acceptance: same LAN phone, select Aperture Music in YouTube Music, verify
one ordinary track audibly plays, then pause/resume, seek, next, queue, phone lock,
disconnect/reconnect, stop service, and check Kodi/controller remain functional.
Use a Premium-only track only after understanding that the phone's per-video
playback token is handled in memory by the receiver. No Google password needed.
