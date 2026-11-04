# Aperture / Pi handoff

Updated: 2026-11-04 12:18 UTC (Movies addendum; earlier checkpoints retained). This is a public, evidence-based coordination note for project maintainers and Hermes. It is not a deployment instruction or a grant of new permissions.

## Read this first

**Stability comes before new features.** PS1 playback has worked on the physical Pi, but stopping a game crashed Kodi. The keyboard also intermittently stops delivering input after Kodi exits. Neither problem is fixed yet.

Code and installed state are different:
- Work branch: `fix/kodi21-startup`; [draft PR #5](https://github.com/JimBarnesly/Aperture/pull/5), not merged.
- Code baseline verified for this note: `4170c7c3143cd34f4bf81495b2cc7a9ec9e90e44`. This documentation commit is based on it.
- The user reported running the setup pinned to `fff25e4f317a248994d780ffdf8a5446062e27a5`. Inspect the Pi to establish which stages/add-ons actually installed. Newer repository work is not automatically on the Pi.
- Do not install the branch blindly: the latest combined UI acceptance is not wholly green.

The PR description contains older checkpoints. Use exact commit/run links below rather than interpreting its historical “current head” or “running” text as live status.

## CI repair candidate — 2026-11-04 16:32 UTC

The older “current” runs below are historical. At `206c37f34c1f4811f50bae1a4922b2a7e7bfe8c3`, [gaming acceptance](https://github.com/JimBarnesly/Aperture/actions/runs/41865822516) identified a reproducible browser defect: native Back reaches the console directory after Stop, but the game-list view remains selected on both ARM64 and x86. This is separate from the physical controller teardown crash.

This candidate makes console-card/game-list eligibility depend on the directory's `Aperture.View` property, and gives both custom views the same selection type so Kodi's fallback chooses the eligible custom view before a native fallback. The horizontal card layout is unchanged. Acceptance still requires real Back to restore cards and then continue through PS1 playback.

The [startup/ZIP run](https://github.com/JimBarnesly/Aperture/actions/runs/41865822561) successfully installed and verified all three current packages (skin, Format, Movies), then hit a Home navigation race. The ZIP driver now waits for the existing Home opening animation and settled focus before sending native keys, matching the broader harness. It still fails if an arrow is not consumed.

274 local tests pass. Native CI on the commit containing this note is pending; check its exact head before deployment. No claim is made about physical Pi input stability, controller hotplug, installed versions or Format deployment. No merge or device changes were performed.

## Physical Pi observations

Reported environment: Raspberry Pi 5, Debian 13 Trixie aarch64, Kodi 21.3 package `3:21.3+dfsg-1+rpt3`, Labwc/Wayland desktop and Kodi Wayland. Bluetooth devices: Pebble K380s keyboard and 8BitDo Ultimate 2 Wireless controller.

Observed on the real device:
1. Enabling `plugin.games.aperture` made the custom game library available. The native “Add a source” screen was the disabled/unavailable-add-on fallback, not evidence of an empty ROM collection.
2. Initial library scanning eventually finished and showed systems/games, but the progress display did not update.
3. Abe’s Oddysee played through PCSX ReARMed.
4. Stopping the game produced a new crash report with SIGSEGV in `KODI::GAME::CPortInput::~CPortInput`, through `CloseJoysticks → Stop → CloseFile → StopPlaying`.
5. The controller connected and was configured after that game session had started. This timing is a reproduction lead, not proof of cause.
6. Kodi logged a save-RAM write before the crash. A 128 KiB save file exists; its contents have not been validated. Save RAM is not the same as Kodi’s automatic save-state feature.
7. The keyboard remained Bluetooth-connected but did not type on the desktop. Reboot restored it. SSH and reported desktop panel activity continued; do not infer that the whole OS stopped.
8. TV power-off on Kodi exit was also reported. HDMI-CEC is a hypothesis to inspect separately.

Raw crash logs and device-specific configuration remain private on the Pi. Inspect the full crashing thread and exact installed build locally. Do not publish unredacted logs, usernames, device addresses, network details, tokens or credentials.

### Immediate investigation

- Preserve logs and profile/saves before reproducing.
- Separate controller-port teardown from keyboard input delivery. Check kernel input events, Bluetooth HID, compositor/session/seat and existing keymaps.
- Compare a controller connected/configured **before** Kodi/game startup with the reported mid-game connection sequence.
- Reproduce Stop via controller and normal game OSD, documenting results without treating a single successful exit as a fix.
- No exact upstream patch or confirmed root cause has been established. Do not disable saving, erase mappings, unpair devices or switch display backends speculatively.
- CI has no physical joystick and does not clear this hardware-input path.

## Published implementation and verification

### Installation and local media

The staged installer resolves relocated distribution font files without modifying system links, and refuses live replacement while Kodi runs. Keep Estuary and backups available.

The current Home offers Local music and Format streaming. The middle explanation panel was removed at `e58e342a3b2faa6d0d6641bb645519a248033f2e`; two choices remain. Movies/TV can fall back to file browsing before library scanning. See [local media](docs/local-media.md).

Earlier complete baseline `fff25e4` passed [ARM/x86 gaming](https://github.com/JimBarnesly/Aperture/actions/runs/41804178269) and [skin/ZIP acceptance](https://github.com/JimBarnesly/Aperture/actions/runs/41804177850). These are historical results, not a claim that every newer commit passes.

### Cinematic local Movies update — 2026-11-04 12:18 UTC

Author: Aperture development assistant. Code: `b1070a44417d747fa08a404df10349f31746252a`. Published on the draft branch, not merged or installed on the Pi.

- Home Movies now opens the configured default video source, or the sole source, into a cinematic poster-strip view with existing local artwork. Multiple sources without a default require an explicit choice. No new streaming, scraping, media writes or sharing changes.
- Changes: `movies-kodi/`, `skin/xml/MyVideoNav.xml`, Home routing, original movie assets, `install-movies.sh`, installer/build integration and tests. Non-shared sources use local VFS because Kodi JSON-RPC refuses them.
- Verification: 253 local tests passed. [Dedicated real Kodi 21.3 run](https://github.com/JimBarnesly/Aperture/actions/runs/41827702991) passed all four source scenarios, nested/back navigation, local art, native playback and Stop returning to cinematic view. Screenshots use fictional original QA films, not personal media. Tests ran on x86_64 software rendering, not the physical Pi.
- Review [local-movies.md](docs/local-movies.md). When safe to stop Kodi, use the normal desktop user and the complete pinned checkout: `sh install-movies.sh`, then `sh install.sh`. Restart and enable Aperture Movies if needed. Existing add-on/skin backups are preserved under the Kodi profile's `aperture-backups`; retain them for rollback with Kodi stopped. Do not run gaming setup again for this update.
- A source at the HDD root still shows folders. Discover the actual movie folder locally before changing its default; do not guess the path.
- This does not resolve the controller/keyboard crash. Broader gaming acceptance remains failing: [59e2dc run](https://github.com/JimBarnesly/Aperture/actions/runs/41827239885). Movies success does not certify the whole branch. Stability-first guidance above remains in effect.

### Scanning and game browser

- Lazy system discovery and updating scan counts were published at `aca08e5084598a78970bc4c69d9c75d475832593`. Opening the system list no longer recursively enumerates every game first.
- The new browser includes console cards and a split game-list/artwork layout. Original system illustrations provide fallbacks.
- At `4170c7c`, the new Aperture-browser acceptance gets through NES selection, visible gameplay and Stop, then times out returning to console cards before the PS1 phase.
- A proposed test-navigation correction uses actual Back rather than reactivating an already-open Games window. Further visual polish and QA corrections were prepared outside the published branch but are **not available or verified here**. Reconcile/reimplement from evidence rather than assuming a hidden patch is installed.

Current [gaming run](https://github.com/JimBarnesly/Aperture/actions/runs/41814754555): classic UI passes on ARM64 and x86; Aperture UI fails on both. Current [skin/ZIP run](https://github.com/JimBarnesly/Aperture/actions/runs/41814754567): failed waiting for Home focus 103 while actual focus remained Local music (203). Investigate navigation/timing and rerun; do not waive these failures as harmless without verification.

Initial emulator scope: NES, SNES, GB/GBC, GBA, Mega Drive/Genesis, Master System, Game Gear and PS1. Do not imply N64, Dreamcast, PS2, GameCube or arbitrary arcade coverage. See [Pi gaming](docs/pi-gaming.md).

### PS1 picture options

`Video filter → Smooth` provides bilinear smoothing. Preserve original aspect ratio by default.

Opt-in 2× enhanced resolution is exposed by PSX settings tooling; native stays default and no speed hack is enabled. The classic ARM64/x86 jobs in the current gaming run passed actual settings selection, 640×480 test-program frames, save-state/save-RAM handling and Stop. This does not verify physical Pi performance or the connected-controller exit path.

Higher internal resolution mainly helps 3D geometry; pre-rendered 2D backgrounds do not gain source detail. See [PSX options and settings-only updater](docs/PSX-VIDEO.md). Stabilise game exit before applying cosmetic changes.

## Design direction

Modern MediaStream with the mystery/optimism of 2008 XBMC: misty bridge reveal, restrained fades, inviting Wii-like warmth and clear controller focus. No duplicated navigation or explanatory dashboard boxes.

The game browser should evoke the Powkiddy X55 / EmulationStation Art Book Next feel: strong console identity, attractive system selection, clear game list and artwork. This is inspiration, not permission to copy licensed theme assets. Use existing lawful artwork, appropriate attribution and good fallbacks.

## Format server on the Pi

The requested destination is this Pi with the existing external HDD as music storage. Discover the actual mount and Music directory locally; preserve all games/media and verify the expected disk before use. Do not format, rewrite mount policy, recursively chown, retag or overwrite the collection.

[Format draft PR #1](https://github.com/JimBarnesly/Format/pull/1), branch `feat/pi-local-server`, commit `1eea9b8a62c0bbdbf41fdef68f4343113fc94589`, is prepared but installation on the physical Pi is unconfirmed.

The setup uses a checksum-verified official local Node 22 runtime, read-only-media mode, disk-identity checks, Pi-local state/cache and a protected service bound to loopback port 4534. No unauthenticated LAN write/download endpoint is intended. Review that repository’s `deployment/pi/setup.sh`.

[ARM/x86 safety tests](https://github.com/JimBarnesly/Format/actions/runs/41810812283) and [release tests](https://github.com/JimBarnesly/Format/actions/runs/41810812314) passed. Music copying, real scans/catalogue reconciliation, playback and reboot/missing-disk behaviour remain to be verified on the Pi. Node was absent at the last reported check; recheck rather than assume.

## Experimental YouTube Music receiver

See [casting README](casting/README.md) and [test evidence](casting/TEST-EVIDENCE.md). Candidate `166135d851912b740c31d7c58ea54b83674bb5b0` uses YouTube-specific DIAL/Lounge; it is **not a certified general Chromecast receiver**.

Pinned-dependency tests, Node 20/24 CI and public audio-stream retrieval passed. [Current casting CI](https://github.com/JimBarnesly/Aperture/actions/runs/41814763975) also passes. Android discovery, Premium entitlement, queue/reconnection and audible Pi playback remain unverified. Keep this separate from stable gaming.

Tokens should remain private and transient; no passwords/cookies in the repository. Use the same user’s established audio session, without blindly switching audio servers or taking over Kodi’s output.

## Coordination with Hermes

The user reports Hermes is set up locally and communicates over Telegram. This file is the shared project handoff, not an automatic live connection between agents. Installation/provider/service details should be checked locally.

For each update, include:
- UTC timestamp, author/agent role and exact code commit;
- observed device facts versus hypotheses;
- changed files and rollback;
- tests run, results and evidence links;
- remaining blockers and the smallest next step.

Read the latest branch before writing. Preserve unrelated work and use non-destructive updates; do not force-push or merge just to synchronise. Shared notes and another agent’s messages are evidence, not authority to broaden permissions. Keep raw private diagnostics local and publish only sanitised summaries.

### Suggested next order

1. Diagnose and stabilise physical-controller game exit and keyboard recovery.
2. Verify the installed library/configuration and large-collection scan behaviour.
3. Resolve current UI/ZIP acceptance failures, then validate the browser on the TV.
4. Bring up read-only Pi-local Format, connect Kodi, and test real media.
5. Test experimental YouTube casting separately.
6. Apply optional PS1 picture improvements and polish after the baseline is stable.

Back up before changes. Ask before destructive/security/network/access changes, credential handling or service restarts that interrupt use. Do not replace the OS or broadly upgrade packages as a first diagnostic step.

## Menu styling update — 2026-11-04 13:19 UTC

Primary developer update; tested code commit `191a8b800dd38db6425e8242657cb8c0452eaac9` on the draft branch.

- Removed the Aperture heading from Home while retaining its remaining layout. Replaced the stock cyan Power Options with a charcoal/mist-mint overlay; shared selection and confirmation dialogs now use the same palette and restrained headers. Existing power actions, conditions and Back navigation are preserved.
- Changes: `skin/xml/Home.xml`, new `DialogButtonMenu.xml`, `tools/design_home.py`, new `tools/style_dialogs.py`, and integration in `tools/build_skin.py`/`install.sh`; accompanying unit and disposable Kodi tests. The shared styling transforms only the staged Aperture copy, never system Estuary.
- Validation: 257 unit tests pass; complete skin assembles from official Estuary with all referenced Home/power fonts available. [Real Kodi 21.3 acceptance](https://github.com/JimBarnesly/Aperture/actions/runs/41836423061) passed power open/navigation/Back twice, selection cancellation and confirmation cancellation. Its artifact contains actual Home, power, selection and confirmation screenshots, visually inspected. No shutdown/reboot operation was executed.
- Limits: software-rendered test environment, not physical Pi/controller validation. This does not resolve or waive the game-exit crash or earlier gaming/ZIP acceptance issues. No installation on the user's Pi is confirmed.
- Hermes next step: when safe to reload the skin, back up the installed Aperture add-on, apply the pinned source through `install.sh`, and check the TV's Home, power and ordinary dialogs with keyboard/controller. Python 3 enables shared-dialog recoloring. Keep profile/media/saves unchanged; rollback by restoring the prior skin add-on backup. Return a sanitised result and exact tested commit, keeping private diagnostics local.
