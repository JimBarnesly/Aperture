# Narrow Kodi rpt3 failed-stream cleanup builder

Unqualified diagnostic build, not a rollout. No skin or addon changes. Hermes owns Pi installation/testing. Do not merge this branch into main without approval.

## Inputs and build

- Exact Raspberry Pi distro source: `3:21.3+dfsg-1+rpt3`, including all downstream patches; original archives pinned by SHA256 in `source.sha256`, checked against the preserved archive-signature → Sources.gz → exact source-stanza chain.
- Only code delta: two failed-open cleanup calls in GameClientStreams.cpp, taken from upstream 5fa857c3c34bd758a7ad364c3f0a8bc03df1e17e. The broader commit is not applied.
- Local package version: `3:21.3+dfsg-1+rpt3+ff9fix1`.
- Native `ubuntu-24.04-arm` runner; official Debian 13 ARM64 container pinned by digest. Debian and security archives use the 20261107 snapshot with signed metadata verification; snapshot Valid-Until expiry is deliberately disabled, not signature checking.
- RPi repository key pinned to CF8A1AF502A2AA2D763BAE7E82B129927FA3303E. RPi has no selected immutable snapshot, so each build retains authenticated apt indexes, dependency versions and downloaded package bytes. Re-running later against live RPi repos can resolve different dependencies. A successful run is not proof of byte-identical reproducibility; that requires another clean build using the retained dependency set.
- Distribution build rules, RelWithDebInfo, debug-symbol generation and `kodi-test`/`dh_auto_test` are preserved. No nocheck, ignored dependencies or tests are added. Existing distro skips remain and must be reported from logs.

The workflow triggers on pushes to this isolated branch. Committing locally does not trigger it; pushing does. No secrets or Pi logs are referenced. Artifact retention is 14 days. Save qualified results persistently before expiry. Runner disk/time/memory limits can stop compilation; the workflow uploads available evidence on failure.

## Validation boundaries

The focused harness compiles actual client/manager method bodies against controlled doubles. It tests failed opens, null cached audio pointer, exact destruction/manager-close counts, subsequent audio toggles and successful retry. Patched must pass; baseline must fail. ASan/UBSan are enabled; LeakSanitizer is disabled because the original sandbox uses ptrace. This is ownership regression coverage, not actual AudioEngine, invalid PCM/channel layout integration, FFmpeg, controller or FF9 testing. Distro GUI autopkgtest is not currently executed by this workflow; do not describe it as passed.

A successful package build additionally requires AArch64 ELF and a matching same-build kodi-bin-dbgsym Build ID plus actual .debug_info and .debug_line sections. Original target Build ID was fb8d48fe36a5270e5ac3ccdff4e961a18bd3c638; patched ID must differ. Never use rpt2 or original debug symbols with this patched binary.

Build output includes .deb/.dsc/source archives/.buildinfo/.changes, dependencies and cache, test logs and SHA256SUMS. The active streaming build.log is excluded from the manifest to avoid hashing a changing file. GitHub artifacts provide the transfer integrity envelope; hash the final downloaded log separately if required.

## Rollout gates

Before installation, independently review patch and full build/test results, inspect actual dependencies, and run Pi-specific audio/game regression under Hermes. A likely minimal scope is kodi-bin plus its exact-version dbgsym; +ff9fix1 is within the original kodi package's upper bound rpt3.1~. Verify APT simulation rather than installing all generated packages or upgrading the OS.

Preserve the original kodi-bin package and installed-version inventory before rollout. Rollback removes the patched exact-version dbgsym, reinstalls the original binary package via explicit downgrade, and verifies original Build ID. Restore original matching symbols only if previously present. No install or rollback is executed by this workflow.
