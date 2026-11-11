"""Online home: real catalogue/history logic, fake Kodi/network boundaries."""
from pathlib import Path
import unittest
import test_movie_plugin as plugin_tests

ROOT = Path(__file__).resolve().parents[1]


class HomeTests(unittest.TestCase):
    setUp = plugin_tests.PluginTests.setUp
    run_plugin = plugin_tests.PluginTests.run_plugin

    def test_continue_row_uses_private_resume_without_network_or_fake_cards(self):
        from test_movie_history import history, MOVIE
        trace = []
        calls, entries, dialogs, ended, builtins = self.run_plugin([], query='?mode=home_row&row=continue', http_trace=trace)
        self.assertEqual((calls, entries, dialogs, builtins, trace), ([], [], [], [], []))
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        store.record_playback(MOVIE, is_playing=True, position_seconds=42, duration_seconds=100, lastplayed=1)
        store.record_playback(dict(MOVIE, id='tt7654321'), is_playing=True, position_seconds=95, duration_seconds=100, lastplayed=2)
        _, entries, _, _, _ = self.run_plugin([], query='?mode=home_row&row=continue', http_trace=trace)
        self.assertEqual(len(entries), 1)
        self.assertIn('resume=1', entries[0][1])
        self.assertIn('Play from beginning', repr(entries[0][2].context))
        self.assertEqual(trace, [])

    def test_suggested_row_ranks_default_batch_locally_and_retains_public_art(self):
        from test_movie_history import history, MOVIE
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        for ident in ('tt1234567', 'tt7654321'):
            store.record_playback(dict(MOVIE, id=ident), is_playing=True, position_seconds=10, duration_seconds=100, lastplayed=1)
        trace, props = [], {}
        payload = {'metas': [{'id': 'tt1234567', 'name': 'Watched', 'genres': ['Drama']},
            {'id': 'tt1111111', 'name': 'Match', 'genres': ['Drama'],
             'poster': 'https://images.metahub.space/poster/medium/tt1111111/img'},
            {'id': 'tt2222222', 'name': 'Other', 'genres': ['Horror']}]}
        c,e,d,x,b = self.run_plugin([], query='?mode=home_row&row=suggested&search=private&genre=Drama',
            http_trace=trace, properties=props, catalog_payload=payload)
        self.assertEqual([entry[2].kw['label'] for entry in e], ['Match'])
        self.assertTrue(e[0][2].art['poster'])
        self.assertEqual(trace, ['https://v3-cinemeta.strem.io/catalog/movie/top/skip=0.json'])
        self.assertIn('local playback history', props['Aperture.Home.suggested.status'])
        self.assertEqual((c,d,b), ([],[],[]))
        store.clear()
        self.run_plugin([], query='?mode=home_row&row=suggested', properties=props, catalog_payload=payload)
        self.assertIn('catalogue suggestions only', props['Aperture.Home.suggested.status'])

    def test_row_failures_are_nonmodal_recoverable_and_do_not_erase_history(self):
        props, trace = {}, []
        c,e,d,x,b = self.run_plugin([], query='?mode=home_row&row=popular',
            catalog_payload={'metas': 'invalid'}, properties=props, http_trace=trace)
        self.assertEqual((c,e,d,b), ([],[],[],[]))
        self.assertTrue(x[-1]['succeeded'])
        self.assertIn('unavailable', props['Aperture.Home.popular.status'])
        self.run_plugin([], query='?mode=home_row&row=popular', properties=props,
                        catalog_payload={'metas': [{'id': 'tt1234567', 'name': 'Recovered'}]})
        self.assertNotIn('unavailable', props['Aperture.Home.popular.status'])
        directory = Path(self.profile) / 'history-private'
        directory.mkdir(mode=0o700)
        path = directory / 'history.json'
        path.write_text('broken-private-data'); path.chmod(0o600)
        c,e,d,x,b = self.run_plugin([], query='?mode=home_row&row=continue', properties=props)
        self.assertEqual((c,e,d,b), ([],[],[],[]))
        self.assertTrue(x[-1]['succeeded'])
        self.assertIn('History unavailable', props['Aperture.Home.continue.status'])
        self.assertEqual(path.read_text(), 'broken-private-data')
        self.assertNotIn('broken-private-data', repr(props))

    def test_overlapping_retry_does_not_publish_old_failure_status(self):
        props = {'Aperture.Home.refresh': 'old'}
        retried = []
        trace = []

        def retry_before_old_fetch_returns():
            if retried:
                return
            retried.append(True)
            self.run_plugin([], query='?action=home_refresh', properties=props)
            generation = props['Aperture.Home.refresh']
            c,e,d,x,b = self.run_plugin([], properties=props,
                query='?mode=home_row&row=popular&refresh=' + generation,
                catalog_payload={'metas': [{'id': 'tt1234567', 'name': 'Recovered'}]},
                http_trace=trace)
            self.assertEqual([entry[2].kw['label'] for entry in e], ['Recovered'])
            self.assertEqual((c,d,b), ([],[],[]))
            self.assertTrue(x[-1]['succeeded'])
            self.assertEqual(props['Aperture.Home.popular.status'], '')

        c,e,d,x,b = self.run_plugin([], properties=props,
            query='?mode=home_row&row=popular&refresh=old',
            catalog_payload={'metas': 'invalid'}, on_fetch=retry_before_old_fetch_returns,
            http_trace=trace)
        self.assertEqual(retried, [True])
        self.assertEqual((c,e,d,b), ([],[],[],[]))
        self.assertTrue(x[-1]['succeeded'])
        self.assertEqual(props['Aperture.Home.popular.status'], '',
                         'Cancelled directory jobs can still finish Python execution')
        self.assertFalse(any('refresh=' in url for url in trace))

    def test_row_generation_fences_late_start_and_old_success_for_each_row(self):
        for row in ('continue', 'suggested', 'popular'):
            with self.subTest(row=row):
                key = 'Aperture.Home.' + row + '.status'
                props = {'Aperture.Home.refresh': 'new', key: 'Current row status'}
                c,e,d,x,b = self.run_plugin([], properties=props,
                    query='?mode=home_row&row=' + row + '&refresh=old',
                    catalog_payload={'metas': [{'id': 'tt1234567', 'name': 'Old success'}]})
                self.assertEqual(props[key], 'Current row status')
                self.assertEqual((c,d,b), ([],[],[]))
                self.assertTrue(x[-1]['succeeded'])

    def test_home_search_cancel_stale_guard_and_explicit_online_navigation(self):
        for search, windows, expected in [('', [11120], []), ('Private & title', [11120, 10000], []),
                ('Private & title', [11120], ['ActivateWindow(Videos,plugin://plugin.video.aperture.movies/?mode=online&search=Private+%26+title,return)'])]:
            c,e,d,x,b = self.run_plugin([], query='?action=home_search', search=search, window_ids=windows)
            self.assertEqual(b, expected)
            self.assertEqual((c,e,x), ([],[],[]))

    def test_home_source_shim_validates_identity_resume_and_origin_without_lookup(self):
        cases = [
            ('tt1234567', '1', [11120], False, True),
            ('tt1234567', '0', [11120], False, True),
            ('tt1234567', '1', [11120, 10000], False, False),
            ('tt1234567', '1', [10025], False, False),
            ('tt1234567', '1', [11120], True, False),
            ('tt1234567%29', '1', [11120], False, False),
            ('tt１２３４５６７', '1', [11120], False, False),
            ('', '1', [11120], False, False),
            ('tt1234567', 'invalid', [11120], False, False),
        ]
        for ident, resume, windows, abort, allowed in cases:
            with self.subTest(ident=ident, resume=resume, windows=windows, abort=abort):
                trace = []
                c,e,d,x,b = self.run_plugin([], query='?action=home_sources&id=' + ident + '&resume=' + resume,
                    window_ids=windows, abort=abort, http_trace=trace)
                route = 'plugin://plugin.video.aperture.movies/?action=torrentio_sources&home=1&id=tt1234567'
                if resume == '1': route += '&resume=1'
                self.assertEqual(b, ['ActivateWindow(Videos,' + route + ',return)'] if allowed else [])
                self.assertEqual((c,e,d,x,trace), ([],[],[],[],[]),
                                 'RunPlugin has no directory handle and must not perform source lookup')

    def test_sources_landing_is_metadata_free_and_explicit_setup_only(self):
        trace = []
        c,e,d,x,b = self.run_plugin([], query='?mode=sources', http_trace=trace)
        self.assertEqual((c,d,trace), ([],[],[]))
        self.assertEqual([entry[2].kw['label'] for entry in e], ['Sources / account settings', 'My Kodi library'])
        self.assertIn('action=providers', e[0][1])
        self.assertIn('mode=discover', e[1][1])

    def test_native_home_has_three_rows_and_remote_escape_paths(self):
        import xml.etree.ElementTree as ET
        home = ET.parse(ROOT / 'skin/xml/Home.xml')
        action = home.find('.//control[@id="100"]/onclick')
        self.assertEqual(action.text, 'ActivateWindow(1120)')
        path = ROOT / 'skin/xml/Custom_1120_MoviesHome.xml'
        self.assertTrue(path.is_file(), 'Native movie home window missing')
        tree = ET.parse(path)
        self.assertEqual(tree.findtext('defaultcontrol'), '720')
        controls = {c.get('id'): c for c in tree.iter('control') if c.get('id')}
        self.assertEqual(len(controls), len([c for c in tree.iter('control') if c.get('id')]))
        for ident, row in [('730', 'continue'), ('731', 'suggested'), ('732', 'popular')]:
            control = controls[ident]
            self.assertEqual(control.findtext('orientation'), 'horizontal')
            self.assertEqual(control.findtext('content'), 'plugin://plugin.video.aperture.movies/?mode=home_row&row=' + row + '&refresh=$INFO[Window(Home).Property(Aperture.Home.refresh)]')
            self.assertEqual(control.findtext('onback'), 'PreviousMenu')
            self.assertEqual(control.findtext('onclick'), 'RunPlugin($INFO[Container(' + ident + ').ListItem.FileNameAndPath])')
            self.assertTrue(control.findtext('enable'))
        for ident, control in controls.items():
            if control.get('type') in ('button', 'list'):
                for direction in ('onup', 'ondown', 'onleft', 'onright'):
                    self.assertIn(control.findtext(direction), controls)
                self.assertEqual(control.findtext('onback'), 'PreviousMenu')
        labels = [c.findtext('label') for c in controls.values()]
        for label in ('Search', 'Local files', 'Sources / settings', 'Retry', 'History'):
            self.assertIn(label, labels)
        self.assertIn('mode=local', controls['723'].findtext('onclick'))
        self.assertEqual(controls['725'].findtext('onclick'), 'RunPlugin(plugin://plugin.video.aperture.movies/?action=home_refresh)')

    def test_home_rows_publish_explicit_source_identity_and_resume(self):
        from test_movie_history import history, MOVIE
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        store.record_playback(MOVIE, is_playing=True, position_seconds=42, duration_seconds=100, lastplayed=1)
        for row in ('continue', 'suggested', 'popular'):
            with self.subTest(row=row):
                _,entries,_,_,_ = self.run_plugin([], query='?mode=home_row&row=' + row,
                    catalog_payload={'metas': [{'id': 'tt7654321', 'name': 'Movie'}]})
                self.assertTrue(entries)
                for entry in entries:
                    self.assertEqual(entry[2].props.get('Aperture.MovieID'), 'tt1234567' if row == 'continue' else 'tt7654321')
                    self.assertEqual(entry[2].props.get('Aperture.SourceResume'), '1' if row == 'continue' else '0')

    def test_native_home_source_buttons_latch_each_row_and_are_reachable(self):
        import xml.etree.ElementTree as ET
        tree = ET.parse(ROOT / 'skin/xml/Custom_1120_MoviesHome.xml')
        controls = {c.get('id'): c for c in tree.iter('control') if c.get('id')}
        for row, button in (('730', '740'), ('731', '741'), ('732', '742')):
            with self.subTest(row=row):
                self.assertIn(button, controls)
                choice = controls[button]
                self.assertEqual(choice.findtext('label'), 'Choose source')
                self.assertIsNone(choice.find('visible'), 'Keep visible after focus leaves the row')
                self.assertEqual(controls[row].findtext('onright'), button)
                self.assertEqual(choice.findtext('onleft'), row)
                self.assertEqual(choice.findtext('onright'), row)
                self.assertEqual(choice.findtext('onback'), 'PreviousMenu')
                ident = 'Container(' + row + ').ListItem.Property(Aperture.MovieID)'
                resume = 'Container(' + row + ').ListItem.Property(Aperture.SourceResume)'
                self.assertEqual(choice.findtext('enable'), '!String.IsEmpty(' + ident + ')')
                self.assertEqual(choice.findtext('onclick'),
                    'RunPlugin(plugin://plugin.video.aperture.movies/?action=home_sources&id=$INFO[' + ident + ']&resume=$INFO[' + resume + '])')
        self.assertNotIn('Context menu choose source', (ROOT / 'skin/xml/Custom_1120_MoviesHome.xml').read_text())

    def test_home_assets_and_both_install_paths_are_complete(self):
        import hashlib
        import xml.etree.ElementTree as ET
        path = ROOT / 'skin/xml/Custom_1120_MoviesHome.xml'
        tree = ET.parse(path)
        for texture in tree.iter('texture'):
            for value in (texture.text, texture.get('fallback')):
                if value and value.startswith('aperture/'):
                    self.assertTrue((ROOT / 'skin/media' / value).is_file(), value)
        for filename in ('tools/build_skin.py', 'install.sh'):
            self.assertIn('Custom_1120_MoviesHome.xml', (ROOT / filename).read_text())
        self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), (ROOT / 'install.sh').read_text())

    def test_popular_includes_featured_and_survives_one_catalogue_failure(self):
        payloads = [
            {'metas': [{'id': 'tt%07d' % i, 'name': 'Popular %d' % i} for i in range(100, 130)]},
            {'metas': [{'id': 'tt9999999', 'name': 'Featured pick'}]},
        ]
        _, entries, dialogs, ended, _ = self.run_plugin([], query='?mode=home_row&row=popular', catalog_payloads=payloads)
        self.assertEqual(len(entries), 20)
        self.assertIn('Featured pick', [entry[2].kw['label'] for entry in entries])
        props = {}
        _, entries, dialogs, ended, _ = self.run_plugin([], query='?mode=home_row&row=popular',
            catalog_payloads=[{'metas': 'invalid'}, payloads[1]], properties=props)
        self.assertEqual([entry[2].kw['label'] for entry in entries], ['Featured pick'])
        self.assertEqual(dialogs, [])
        self.assertTrue(ended[-1]['succeeded'])
        self.assertIn('unavailable', props['Aperture.Home.popular.status'])

    def test_native_synthetic_home_journey_covers_navigation_and_resume(self):
        source = (ROOT / 'tools/movies_online_qa_service.py').read_text()
        for marker in ('movies_home_journey()', 'home_resume_journey()', 'home-empty-continue',
                       'home-search-cancel', 'home-rows-no-source-lookup', 'home-local-fallback',
                       'home-resume-back-pauses', 'home-offline-retry'):
            self.assertIn(marker, source)
        self.assertIn('home-focused-metadata', source)
        self.assertIn('home-source-button-focus', source)
        mocks = (ROOT / 'tools/movies_online_mocks.py').read_text()
        self.assertIn('catalogue-offline', mocks)

    def test_widget_refresh_changes_only_local_url_nonce(self):
        props, trace = {}, []
        for _ in range(2):
            before = props.get('Aperture.Home.refresh')
            c,e,d,x,b = self.run_plugin([], query='?action=home_refresh', properties=props, http_trace=trace)
            self.assertNotEqual(props.get('Aperture.Home.refresh'), before)
            self.assertEqual((c,e,d,x,b,trace), ([],[],[],[],[],[]))

    def test_empty_public_catalogue_has_actionable_status_and_no_cards(self):
        props = {}
        c,e,d,x,b = self.run_plugin([], query='?mode=home_row&row=popular', properties=props)
        self.assertEqual((c,e,d,b), ([],[],[],[]))
        self.assertIn('No catalogue results', props['Aperture.Home.popular.status'])
        self.assertTrue(x[-1]['succeeded'])

    def test_native_home_refreshes_rows_on_return_and_preserves_focus(self):
        import xml.etree.ElementTree as ET
        tree = ET.parse(ROOT / 'skin/xml/Custom_1120_MoviesHome.xml')
        self.assertNotEqual(tree.find('defaultcontrol').get('always'), 'true')
        self.assertEqual([n.text for n in tree.findall('onload')],
                         ['RunPlugin(plugin://plugin.video.aperture.movies/?action=home_refresh)'])

    def test_home_metadata_is_genuine_movie_only_and_details_are_explicit(self):
        trace = []
        payload = {'metas': [
            {'id': 'tt0387808', 'type': 'movie', 'name': 'Severance', 'releaseInfo': '2006',
             'genres': ['Comedy', 'Horror'], 'description': 'A genuine supplied film synopsis.'},
            {'id': 'tt11280740', 'type': 'series', 'name': 'Severance', 'releaseInfo': '2022'},
            {'id': 'tt1234567', 'type': 'movie', 'name': 'Sparse metadata'}]}
        c,e,d,x,b = self.run_plugin([], query='?mode=home_row&row=popular', catalog_payload=payload, http_trace=trace)
        self.assertEqual([entry[2].kw['label'] for entry in e], ['Severance', 'Sparse metadata'])
        self.assertEqual(e[0][2].info['plot'], 'A genuine supplied film synopsis.')
        self.assertEqual(e[0][2].props.get('Aperture.Year'), '2006')
        self.assertEqual(e[0][2].info['genre'], ['Comedy', 'Horror'])
        self.assertIn('Details unavailable', e[1][2].info['plot'])
        self.assertIn(('Movie details (Cinemeta)', 'RunPlugin(plugin://plugin.video.aperture.movies/?action=online_details&id=tt0387808)'), e[0][2].context)
        self.assertFalse(any('/meta/' in url for url in trace))
        self.assertEqual(c, [])
        import xml.etree.ElementTree as ET
        tree = ET.parse(ROOT / 'skin/xml/Custom_1120_MoviesHome.xml')
        labels = [node.text for node in tree.iter('label')]
        for ident in ('730', '731', '732'):
            self.assertIn('$INFO[Container(' + ident + ').ListItem.Plot]', labels)
            self.assertTrue(any('Container(' + ident + ').ListItem.Property(Aperture.Year)' in (label or '') for label in labels))

    def test_details_fetch_leaving_custom_home_suppresses_success_and_error_dialogs(self):
        for payload in ({'meta': {'id': 'tt1234567', 'name': 'Old movie'}},
                        {'meta': 'invalid'}):
            with self.subTest(payload=payload):
                windows, menus, trace = [11120], [], []
                c,e,d,x,b = self.run_plugin([], query='?action=online_details&id=tt1234567',
                    folder_paths=[''], window_ids=lambda: windows[0], selection=0,
                    catalog_payload=payload, on_fetch=lambda: windows.__setitem__(0, 10000),
                    select_trace=menus, http_trace=trace)
                self.assertEqual(len(trace), 1)
                self.assertEqual((c,e,d,x,b,menus), ([],[],[],[],[],[]),
                                 'Both windows have empty FolderPath; window identity must fence the result')

    def test_details_checks_window_again_after_each_modal(self):
        for hook in ('on_ok', 'on_select'):
            with self.subTest(hook=hook):
                windows, menus = [11120], []
                c,e,d,x,b = self.run_plugin([], query='?action=online_details&id=tt1234567',
                    folder_paths=[''], window_ids=lambda: windows[0], selection=0,
                    catalog_payload={'meta': {'id': 'tt1234567', 'name': 'Movie'}},
                    select_trace=menus,
                    on_ok=(lambda: windows.__setitem__(0, 10000)) if hook == 'on_ok' else None,
                    on_select=(lambda: windows.__setitem__(0, 10000)) if hook == 'on_select' else None)
                self.assertEqual(len(d), 1)
                self.assertEqual(len(menus), 0 if hook == 'on_ok' else 1)
                self.assertEqual((c,e,x,b), ([],[],[],[]))

    def test_new_details_invocation_supersedes_old_fetch_and_modal_actions(self):
        for phase in ('on_fetch', 'on_ok', 'on_select'):
            with self.subTest(phase=phase):
                props, menus, newer = {}, [], []

                def replace():
                    newer.append(self.run_plugin([], properties=props,
                        query='?action=online_details&id=tt7654321', folder_paths=[''],
                        window_ids=[11120], selection=-1,
                        catalog_payload={'meta': {'id': 'tt7654321', 'name': 'New movie'}}))

                c,e,d,x,b = self.run_plugin([], properties=props,
                    query='?action=online_details&id=tt1234567', folder_paths=[''],
                    window_ids=[11120], selection=0, select_trace=menus,
                    catalog_payload={'meta': {'id': 'tt1234567', 'name': 'Old movie'}},
                    on_fetch=replace if phase == 'on_fetch' else None,
                    on_ok=replace if phase == 'on_ok' else None,
                    on_select=replace if phase == 'on_select' else None)
                self.assertEqual(len(newer), 1)
                self.assertEqual(newer[0][2][0][0], 'New movie')
                self.assertEqual(len(d), 0 if phase == 'on_fetch' else 1)
                self.assertEqual(len(menus), 1 if phase == 'on_select' else 0)
                self.assertEqual((c,e,x,b), ([],[],[],[]))
                self.assertNotIn('tt1234567', repr(props))
                self.assertNotIn('tt7654321', repr(props))

    def test_home_details_choose_source_activates_videos_not_custom_container(self):
        trace, menus = [], []
        c,e,d,x,b = self.run_plugin([], query='?action=online_details&id=tt1234567',
            window_ids=[11120], folder_paths=[''], selection=0, http_trace=trace, select_trace=menus,
            catalog_payload={'meta': {'id': 'tt1234567', 'name': 'Movie'}})
        self.assertEqual(b, ['ActivateWindow(Videos,plugin://plugin.video.aperture.movies/?action=torrentio_sources&home=1&id=tt1234567,return)'])
        self.assertEqual(menus[0][1][0], 'Choose source')
        self.assertEqual((c,e,x), ([],[],[]))
        self.assertEqual(len(trace), 1)

    def test_explicit_details_missing_plot_is_honest_and_series_is_rejected(self):
        trace = []
        c,e,d,x,b = self.run_plugin([], query='?action=online_details&id=tt1234567',
            catalog_payload={'meta': {'id': 'tt1234567', 'name': 'Sparse movie', 'type': 'movie'}}, http_trace=trace)
        self.assertIn('Details unavailable', repr(d))
        self.assertEqual(trace, ['https://v3-cinemeta.strem.io/meta/movie/tt1234567.json'])
        self.assertEqual((c,e,b), ([],[],[]))
        c,e,d,x,b = self.run_plugin([], query='?action=online_details&id=tt11280740',
            catalog_payload={'meta': {'id': 'tt11280740', 'name': 'Severance', 'type': 'series'}})
        self.assertIn('unavailable', repr(d))
        self.assertNotIn('Severance', repr(d))

    def test_online_browse_keeps_year_missing_plot_and_truthful_heading(self):
        _,e,_,_,_ = self.run_plugin([], query='?mode=online',
            catalog_payload={'metas': [{'id': 'tt0387808', 'type': 'movie', 'name': 'Severance', 'releaseInfo': '2006'}]})
        self.assertEqual(e[0][2].info.get('year'), 2006)
        self.assertIn('Details unavailable', e[0][2].info['plot'])
        source = (ROOT / 'skin/xml/MyVideoNav.xml').read_text()
        self.assertNotIn('<label>KODI LIBRARY / FILES</label>', source)
        self.assertIn('<label>$INFO[Container.PluginCategory]</label>', source)

    def test_popular_home_row_is_metadata_only_with_existing_play_action(self):
        trace = []
        calls, entries, dialogs, ended, builtins = self.run_plugin([], query='?mode=home_row&row=popular',
            http_trace=trace, catalog_payload={'metas': [{'id': 'tt1234567', 'name': 'Public film',
                'poster': 'https://images.metahub.space/poster/medium/tt1234567/img',
                'streams': [{'url': 'https://private.invalid/secret'}]}]})
        self.assertEqual(calls, [])
        self.assertEqual(trace, ['https://v3-cinemeta.strem.io/catalog/movie/top/skip=0.json',
                                'https://v3-cinemeta.strem.io/catalog/movie/imdbRating/skip=0.json'])
        self.assertEqual(len(entries), 1, 'Deduplicate popular/featured, no fake or paging cards')
        self.assertIn('action=torrentio_auto&id=tt1234567', entries[0][1])
        self.assertEqual(entries[0][2].props['Aperture.Availability'], 'Not checked')
        self.assertIn('Choose source', repr(entries[0][2].context))
        self.assertTrue(entries[0][2].art['poster'])
        self.assertEqual((dialogs, builtins), ([], []))
        self.assertTrue(ended[-1]['succeeded'])
        self.assertNotIn('secret', repr(entries))
