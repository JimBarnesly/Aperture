# Executed Torrentio review-fix TDD evidence

Base: `086f4d1b521570018e01ee94ef9c0e5e0b2ffd6d`.
Checkout: `/home/jake/Documents/pi-maintenance/development/Aperture-torrentio`.
All behavioral changes below followed individual RED → implementation → GREEN
cycles. Outputs are abbreviated from actual tool execution, not simulated results.
Historical first-slice evidence remains in `torrentio-tdd-evidence.md`.

## Vertical cycles

| Test / behavior | Observed RED | Immediate GREEN |
| --- | --- | --- |
| `test_official_missing_index_sentinel_fixture` | `AssertionError: 0 != 1` | adapter 10 tests OK |
| `test_source_identity_survives_token_rotation_only` | SHA-256 IDs differed after token-only rotation | adapter 11 tests OK |
| `test_oauth_token_is_encoded_as_one_config_and_resolver_segment` | `Native OAuth config builder missing` | adapter 12 tests OK |
| `test_native_consent_persists_marker_not_a_token_copy` | `Native consent storage missing` | adapter 13 tests OK |
| `test_native_setup_reuses_existing_grant_only_after_separate_consent` | `None != 'rd-oauth-v1'` | UI 7 tests OK |
| `test_new_user_completes_device_approval_in_app` | `None != 'rd-oauth-v1'` | UI 8 tests OK |
| `test_native_find_refreshes_under_lock_and_discloses_only_access_token` | native marker lacked `.lookup`; explicit assertion: `Native consent marker must resolve to a refreshed in-memory config` | UI 9 tests OK |
| `test_unreadable_configuration_can_be_reset_without_parsing` | `Unreadable saved configuration traps setup` | adapter + UI 23 tests OK |
| `test_labels_expose_only_bounded_recognized_technical_fields` | `'HEVC' not found in 'Real-Debrid · 1080p'` | adapter 14 tests OK |
| `test_known_resolver_states_have_fixed_distinct_messages_without_retry` | `'queued' not found` in generic resolver error | adapter 15 tests OK |
| `test_movie_details_exposes_visible_find_streams_action` | empty builtins rather than expected Find streams action | plugin 42 tests OK |
| `test_disconnect_serializes_with_disclosure_and_explains_irrevocability` | disconnect removed config while disclosure lock held | UI 11 tests OK |
| `test_provider_wait_has_cancellable_progress_and_never_plays_after_cancel` | `Expected 'create' to have been called once. Called 0 times.` | UI 12 tests OK |
| `test_cancel_during_resolver_discards_late_result` | player called once after cancel | movie suite 167 tests OK |
| `test_shutdown_during_device_approval_saves_nothing_and_leaves_ui_closed` | cancellation dialog still shown on shutdown | UI 14 tests OK |
| `test_status_explains_native_setup_not_a_browser_dead_end` | old status lacked `no manual token copying` | UI 15 tests OK |

Two initial test harness errors (non-iterable mocked streams and native marker
AttributeError) were converted to explicit assertions, rerun RED, then implemented.
Two additional integration checks were added after these cycles without production
changes: full selection-to-play token rotation using real adapter/real RD refresh
with injected transport, and expired-token check refusal causing no refresh/network.
They passed as regression validation, not claimed as additional RED cycles.

Existing RD tests also verify device expiry, cancellation before/after token
exchange, revoked/rate-limit failures and refresh. All new tokens, movie entries,
responses, URLs and account data are synthetic fixtures. Public upstream source
files were read; no real provider/account/movie calls occurred.

## Final executed verification

```
$ python -m unittest discover -s tests -p 'test_movie_torrentio*.py'
Ran 32 tests in 3.519s
OK

$ python -m unittest discover -s tests
Ran 710 tests in 35.129s
OK

$ python -m compileall -q movies-kodi tests
# exit 0, no output

$ git diff --check
# exit 0, no output
```

Full-suite installer output is from isolated temporary-profile tests under the
configured scratch directory; no deployed profile or installed add-on was changed.
Static diff review found no new production hardcoded credentials, shell execution,
eval/exec, deserialization or SQL operations. Fixture secrets are explicitly fake.

## Remaining gates

This is synthetic execution plus self-review, not independent approval. Parent
review must examine the final commit. Do not mark it independently verified.
No deployment, push, live account approval, native Kodi run, HDMI/audio, remote
readability or real playback acceptance was attempted. OAuth bearer support is
backed by official Torrentio source, not a tested live-host guarantee. Cancel
suppresses later actions/results but does not interrupt an already-blocking request
before its bounded transport deadline or retract provider-side mutations.
