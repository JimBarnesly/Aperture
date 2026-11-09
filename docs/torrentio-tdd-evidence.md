# Executed unit-test evidence

Synthetic fixtures only. Installer output below refers to isolated temporary test profiles, not deployment. Baseline 674 tests; final 693 tests. RED failures precede implementation; numbered GREEN logs follow fixes. Null manifest types exposed TypeError, then private-DNS rejection. Official manifest ID correction exposed ProviderError. Native Kodi and live account/playback tests are pending.

## torrentio-baseline.log

```text
----------------------------------------------------------------------
Ran 674 tests in 61.340s

OK
Game browser updated. Existing ROM folder, saved library, cores, BIOS and saves are unchanged.
Previous browser backup: <local-path>
Kodi package: 21.2-1 | architecture: amd64
Kodi running: False
Available distribution cores: nestopia, snes9x, gambatte, mgba, genesisplusgx
Unavailable distribution cores: none
Aperture Movies installed. Existing sources and media are unchanged.
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
Aperture Movies installed. Existing sources and media are unchanged.
Previous add-on backup: <local-path>
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
PSX video settings installed. Native resolution remains the default.
Backup: <local-path>
Open Kodi → Add-ons → My add-ons → Game add-ons → Emulators → Aperture PlayStation → Configure.
Stop/restart a game after changing Enhanced resolution. Return to Native if slower or visually incorrect.

```

## torrentio-full.log

```text
----------------------------------------------------------------------
Ran 693 tests in 33.348s

OK
Game browser updated. Existing ROM folder, saved library, cores, BIOS and saves are unchanged.
Previous browser backup: <local-path>
Kodi package: 21.2-1 | architecture: amd64
Kodi running: False
Available distribution cores: nestopia, snes9x, gambatte, mgba, genesisplusgx
Unavailable distribution cores: none
Aperture Movies installed. Existing sources and media are unchanged.
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
Aperture Movies installed. Existing sources and media are unchanged.
Previous add-on backup: <local-path>
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
PSX video settings installed. Native resolution remains the default.
Backup: <local-path>
Open Kodi → Add-ons → My add-ons → Game add-ons → Emulators → Aperture PlayStation → Configure.
Stop/restart a game after changing Enhanced resolution. Return to Native if slower or visually incorrect.

```

## torrentio-green-01.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.001s

OK

```

## torrentio-green-02.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.032s

OK

```

## torrentio-green-03.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... ok
test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels (test_movie_torrentio.StreamTests.test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.041s

OK

```

## torrentio-green-04.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_lookup_limits_redirect_refusal_and_refetch_before_resolution (test_movie_torrentio.NetworkTests.test_lookup_limits_redirect_refusal_and_refetch_before_resolution) ... ok
test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors (test_movie_torrentio.NetworkTests.test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors) ... ok
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... ok
test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels (test_movie_torrentio.StreamTests.test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels) ... ok

----------------------------------------------------------------------
Ran 5 tests in 1.961s

OK

```

## torrentio-green-05.log

```text
test_browser_handoff_is_public_and_honest_not_connected (test_movie_torrentio_ui.TorrentioUITests.test_browser_handoff_is_public_and_honest_not_connected) ... ok
test_cancel_and_decline_setup_never_connect (test_movie_torrentio_ui.TorrentioUITests.test_cancel_and_decline_setup_never_connect) ... ok
test_connection_check_is_explicit_and_does_not_claim_account_valid (test_movie_torrentio_ui.TorrentioUITests.test_connection_check_is_explicit_and_does_not_claim_account_valid) ... ok
test_disconnect_and_status_do_not_contact_provider (test_movie_torrentio_ui.TorrentioUITests.test_disconnect_and_status_do_not_contact_provider) ... ok
test_find_requires_consent_and_explicit_selection_then_refetches (test_movie_torrentio_ui.TorrentioUITests.test_find_requires_consent_and_explicit_selection_then_refetches) ... ok
test_import_requires_all_consents_and_no_network (test_movie_torrentio_ui.TorrentioUITests.test_import_requires_all_consents_and_no_network) ... ok
test_stale_navigation_or_cancel_prevents_network (test_movie_torrentio_ui.TorrentioUITests.test_stale_navigation_or_cancel_prevents_network) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.510s

OK

```

## torrentio-green-06.log

```text
----------------------------------------------------------------------
Ran 150 tests in 4.186s

OK
Aperture Movies installed. Existing sources and media are unchanged.
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
Aperture Movies installed. Existing sources and media are unchanged.
Previous add-on backup: <local-path>
Restart Kodi and enable Aperture Movies in My add-ons if prompted.

```

## torrentio-green-07.log

```text
----------------------------------------------------------------------
Ran 41 tests in 0.593s

OK

```

## torrentio-green-08.log

```text
----------------------------------------------------------------------
Ran 7 tests in 0.058s

OK

```

## torrentio-green-09.log

```text
----------------------------------------------------------------------
Ran 15 tests in 0.204s

OK

```

## torrentio-green-10.log

```text
----------------------------------------------------------------------
Ran 9 tests in 0.058s

OK

```

## torrentio-green-11.log

```text
----------------------------------------------------------------------
Ran 9 tests in 0.057s

OK

```

## torrentio-green-12.log

```text
----------------------------------------------------------------------
Ran 9 tests in 0.058s

OK

```

## torrentio-red-01.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... FAIL

======================================================================
FAIL: test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 26, in test_only_strict_rd_configured_manifest_can_build_movie_lookup
    self.assertIsNotNone(t, 'Torrentio adapter is missing')
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: unexpectedly None : Torrentio adapter is missing

----------------------------------------------------------------------
Ran 1 test in 0.001s

FAILED (failures=1)

```

## torrentio-red-02.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... FAIL

======================================================================
FAIL: test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 51, in test_private_atomic_import_load_disconnect_with_symlink_refusal
    self.assertTrue(hasattr(t, 'Store'), 'Private configuration store is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Private configuration store is missing

----------------------------------------------------------------------
Ran 2 tests in 0.002s

FAILED (failures=1)

```

## torrentio-red-03.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... ok
test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels (test_movie_torrentio.StreamTests.test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels) ... FAIL

======================================================================
FAIL: test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels (test_movie_torrentio.StreamTests.test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 95, in test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels
    self.assertTrue(hasattr(t, 'parse_streams'), 'Stream adapter is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Stream adapter is missing

----------------------------------------------------------------------
Ran 3 tests in 0.032s

FAILED (failures=1)

```

## torrentio-red-04.log

```text
test_only_strict_rd_configured_manifest_can_build_movie_lookup (test_movie_torrentio.ConfigurationTests.test_only_strict_rd_configured_manifest_can_build_movie_lookup) ... ok
test_lookup_limits_redirect_refusal_and_refetch_before_resolution (test_movie_torrentio.NetworkTests.test_lookup_limits_redirect_refusal_and_refetch_before_resolution) ... FAIL
test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors (test_movie_torrentio.NetworkTests.test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors) ... FAIL
test_private_atomic_import_load_disconnect_with_symlink_refusal (test_movie_torrentio.StorageTests.test_private_atomic_import_load_disconnect_with_symlink_refusal) ... ok
test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels (test_movie_torrentio.StreamTests.test_filters_to_rd_resolver_sources_and_returns_opaque_safe_labels) ... ok

======================================================================
FAIL: test_lookup_limits_redirect_refusal_and_refetch_before_resolution (test_movie_torrentio.NetworkTests.test_lookup_limits_redirect_refusal_and_refetch_before_resolution)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 128, in test_lookup_limits_redirect_refusal_and_refetch_before_resolution
    self.assertTrue(hasattr(t, 'Client'), 'Bounded client is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Bounded client is missing

======================================================================
FAIL: test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors (test_movie_torrentio.NetworkTests.test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 155, in test_transport_no_proxy_no_redirect_public_dns_timeout_and_safe_errors
    self.assertTrue(hasattr(t, 'request'), 'Safe transport is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Safe transport is missing

----------------------------------------------------------------------
Ran 5 tests in 0.040s

FAILED (failures=2)

```

## torrentio-red-05.log

```text
test_browser_handoff_is_public_and_honest_not_connected (test_movie_torrentio_ui.TorrentioUITests.test_browser_handoff_is_public_and_honest_not_connected) ... FAIL
test_cancel_and_decline_setup_never_connect (test_movie_torrentio_ui.TorrentioUITests.test_cancel_and_decline_setup_never_connect) ... FAIL
test_connection_check_is_explicit_and_does_not_claim_account_valid (test_movie_torrentio_ui.TorrentioUITests.test_connection_check_is_explicit_and_does_not_claim_account_valid) ... FAIL
test_disconnect_and_status_do_not_contact_provider (test_movie_torrentio_ui.TorrentioUITests.test_disconnect_and_status_do_not_contact_provider) ... FAIL
test_find_requires_consent_and_explicit_selection_then_refetches (test_movie_torrentio_ui.TorrentioUITests.test_find_requires_consent_and_explicit_selection_then_refetches) ... FAIL
test_import_requires_all_consents_and_no_network (test_movie_torrentio_ui.TorrentioUITests.test_import_requires_all_consents_and_no_network) ... FAIL
test_stale_navigation_or_cancel_prevents_network (test_movie_torrentio_ui.TorrentioUITests.test_stale_navigation_or_cancel_prevents_network) ... FAIL

======================================================================
FAIL: test_browser_handoff_is_public_and_honest_not_connected (test_movie_torrentio_ui.TorrentioUITests.test_browser_handoff_is_public_and_honest_not_connected)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_cancel_and_decline_setup_never_connect (test_movie_torrentio_ui.TorrentioUITests.test_cancel_and_decline_setup_never_connect)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_connection_check_is_explicit_and_does_not_claim_account_valid (test_movie_torrentio_ui.TorrentioUITests.test_connection_check_is_explicit_and_does_not_claim_account_valid)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_disconnect_and_status_do_not_contact_provider (test_movie_torrentio_ui.TorrentioUITests.test_disconnect_and_status_do_not_contact_provider)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_find_requires_consent_and_explicit_selection_then_refetches (test_movie_torrentio_ui.TorrentioUITests.test_find_requires_consent_and_explicit_selection_then_refetches)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_import_requires_all_consents_and_no_network (test_movie_torrentio_ui.TorrentioUITests.test_import_requires_all_consents_and_no_network)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

======================================================================
FAIL: test_stale_navigation_or_cancel_prevents_network (test_movie_torrentio_ui.TorrentioUITests.test_stale_navigation_or_cancel_prevents_network)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 23, in setUp
    self.assertTrue(path.exists(), 'Torrentio wizard/UI is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Torrentio wizard/UI is missing

----------------------------------------------------------------------
Ran 7 tests in 0.007s

FAILED (failures=7)

```

## torrentio-red-06.log

```text
======================================================================
FAIL: test_sources_offers_online_playback_setup_without_moving_existing_choices (test_movie_debrid_ui.DebridUITests.test_sources_offers_online_playback_setup_without_moving_existing_choices)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_debrid_ui.py", line 48, in test_sources_offers_online_playback_setup_without_moving_existing_choices
    self.assertEqual(choices[-1], 'Set up online playback (Torrentio)')
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'Application client ID (optional override)' != 'Set up online playback (Torrentio)'
- Application client ID (optional override)
+ Set up online playback (Torrentio)


======================================================================
FAIL: test_online_movie_has_explicit_torrentio_action_without_changing_default (test_movie_plugin.PluginTests.test_online_movie_has_explicit_torrentio_action_without_changing_default)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_plugin.py", line 91, in test_online_movie_has_explicit_torrentio_action_without_changing_default
    self.assertIn(('Find streams (Torrentio)', 'RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_find&id=tt1234567)'), e[0][2].context)
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ('Find streams (Torrentio)', 'RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_find&id=tt1234567)') not found in [('Movie details (Cinemeta)', 'RunPlugin(plugin://plugin.video.aperture.movies/?action=online_details&id=tt1234567)'), ('Check my Real-Debrid downloads (filename IMDb ID)', 'Container.Update(plugin://plugin.video.aperture.movies/?mode=rd&imdb=tt1234567)')]

======================================================================
FAIL: test_manifest_check_is_bounded_and_does_not_validate_account (test_movie_torrentio.NetworkTests.test_manifest_check_is_bounded_and_does_not_validate_account)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 128, in test_manifest_check_is_bounded_and_does_not_validate_account
    self.assertTrue(hasattr(t.Client, 'check'), 'Manifest check is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Manifest check is missing

----------------------------------------------------------------------
Ran 150 tests in 4.527s

FAILED (failures=3)
Aperture Movies installed. Existing sources and media are unchanged.
Restart Kodi and enable Aperture Movies in My add-ons if prompted.
Aperture Movies installed. Existing sources and media are unchanged.
Previous add-on backup: <local-path>
Restart Kodi and enable Aperture Movies in My add-ons if prompted.

```

## torrentio-red-07.log

```text
======================================================================
FAIL: test_torrentio_action_dispatches_without_local_source_access (test_movie_plugin.PluginTests.test_torrentio_action_dispatches_without_local_source_access)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_plugin.py", line 97, in test_torrentio_action_dispatches_without_local_source_access
    self.assertEqual(c, [])
    ~~~~~~~~~~~~~~~~^^^^^^^
AssertionError: Lists differ: [{'jsonrpc': '2.0', 'id': 1, 'method': 'Fi[42 chars]o'}}] != []

First list contains 1 additional elements.
First extra element 0:
{'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetSources', 'params': {'media': 'video'}}

+ []
- [{'id': 1,
-   'jsonrpc': '2.0',
-   'method': 'Files.GetSources',
-   'params': {'media': 'video'}}]

----------------------------------------------------------------------
Ran 41 tests in 0.588s

FAILED (failures=1)

```

## torrentio-red-08.log

```text
======================================================================
ERROR: test_rejects_malformed_manifest_types_and_private_playback_dns (test_movie_torrentio.NetworkTests.test_rejects_malformed_manifest_types_and_private_playback_dns)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 173, in test_rejects_malformed_manifest_types_and_private_playback_dns
    t.Client(t.Config(MANIFEST), request=lambda _: Response(b'{"id":"com.stremio.torrentio","types":null}')).check()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "CHECKOUT/movies-kodi/resources/lib/torrentio.py", line 239, in check
    if not isinstance(manifest, dict) or manifest.get('id') != 'com.stremio.torrentio' or 'movie' not in manifest.get('types', []):
                                                                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: argument of type 'NoneType' is not iterable

----------------------------------------------------------------------
Ran 7 tests in 0.059s

FAILED (errors=1)

```

## torrentio-red-08b.log

```text
======================================================================
FAIL: test_rejects_malformed_manifest_types_and_private_playback_dns (test_movie_torrentio.NetworkTests.test_rejects_malformed_manifest_types_and_private_playback_dns)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 179, in test_rejects_malformed_manifest_types_and_private_playback_dns
    with self.assertRaises(t.ProviderError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
AssertionError: ProviderError not raised

----------------------------------------------------------------------
Ran 7 tests in 0.058s

FAILED (failures=1)

```

## torrentio-red-09.log

```text
======================================================================
FAIL: test_cancel_between_refetch_and_resolver_prevents_provider_mutation (test_movie_torrentio.NetworkTests.test_cancel_between_refetch_and_resolver_prevents_provider_mutation)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 183, in test_cancel_between_refetch_and_resolver_prevents_provider_mutation
    self.assertTrue('cancelled' in __import__('inspect').signature(t.Client.playback).parameters, 'Playback cancellation gate is missing')
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False is not true : Playback cancellation gate is missing

======================================================================
FAIL: test_find_requires_consent_and_explicit_selection_then_refetches (test_movie_torrentio_ui.TorrentioUITests.test_find_requires_consent_and_explicit_selection_then_refetches)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio_ui.py", line 91, in test_find_requires_consent_and_explicit_selection_then_refetches
    self.assertIn('cancelled', self.client.playback.call_args.kwargs)
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'cancelled' not found in {}

----------------------------------------------------------------------
Ran 15 tests in 1.941s

FAILED (failures=2)

```

## torrentio-red-10.log

```text
======================================================================
FAIL: test_resolver_path_accepts_optional_filename_but_no_extra_segments (test_movie_torrentio.StreamTests.test_resolver_path_accepts_optional_filename_but_no_extra_segments)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 100, in test_resolver_path_accepts_optional_filename_but_no_extra_segments
    self.assertEqual(len(entries), count)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
AssertionError: 0 != 1

----------------------------------------------------------------------
Ran 9 tests in 0.060s

FAILED (failures=1)

```

## torrentio-red-11.log

```text
======================================================================
FAIL: test_resolver_path_accepts_optional_filename_but_no_extra_segments (test_movie_torrentio.StreamTests.test_resolver_path_accepts_optional_filename_but_no_extra_segments)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 100, in test_resolver_path_accepts_optional_filename_but_no_extra_segments
    self.assertEqual(len(entries), count)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
AssertionError: 0 != 1

----------------------------------------------------------------------
Ran 9 tests in 0.088s

FAILED (failures=1)

```

## torrentio-red-12.log

```text
======================================================================
ERROR: test_manifest_check_is_bounded_and_does_not_validate_account (test_movie_torrentio.NetworkTests.test_manifest_check_is_bounded_and_does_not_validate_account)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "CHECKOUT/tests/test_movie_torrentio.py", line 144, in test_manifest_check_is_bounded_and_does_not_validate_account
    t.Client(t.Config(MANIFEST), request=request).check()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "CHECKOUT/movies-kodi/resources/lib/torrentio.py", line 239, in check
    raise ProviderError()
torrentio_test.ProviderError: Unsupported Torrentio configuration or response. Use HTTPS Torrentio with Real-Debrid only and exclude download links.

----------------------------------------------------------------------
Ran 9 tests in 0.058s

FAILED (errors=1)

```
