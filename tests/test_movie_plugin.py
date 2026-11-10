from pathlib import Path
import json,runpy,sys,types,unittest,tempfile,io
from unittest.mock import patch
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]

class Item:
    def __init__(self,**kw): self.kw=kw; self.art={}; self.props={}
    def setArt(self,a):self.art=a
    def addContextMenuItems(self,a):self.context=a
    def setProperty(self,k,v):self.props[k]=v
    def setInfo(self,kind,info):self.info=info
    def getVideoInfoTag(self):return self
    def setDuration(self,x):pass
    def setDbId(self,x):self.dbid=x
    def setMediaType(self,x):self.media_type=x
    def setResumePoint(self,*x):self.resume=x

class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.profile=self.temporary.name
        self.addCleanup(self.temporary.cleanup)
    def run_plugin(self,sources,query='',default='',files=None,fail=False,vfs_listing=None,vfs_exists=(),vfs_trace=None,folder_paths=None,busy_checks=0,view_trace=None,abort=False,picture="",movies=None,limits=None,search="",selection=-1,genres=None,catalog_payload=None,http_trace=None,categories=None,confirm=False,properties=None,on_wait=None,window_ids=None,catalog_payloads=None):
        calls=[]; entries=[]; dialogs=[]; ended=[]; builtins=[]
        windows = iter(window_ids or [10025]); current_window = [10025]
        def window_id():
            current_window[0] = next(windows, current_window[0])
            return current_window[0]
        properties = properties if properties is not None else {}
        window = types.SimpleNamespace(getProperty=lambda k:properties.get(k, ''),
            setProperty=properties.__setitem__, clearProperty=lambda k:properties.pop(k, None))
        categories = categories if categories is not None else []
        payloads = iter(catalog_payloads) if catalog_payloads is not None else None
        def fetch(request, **kwargs):
            if http_trace is not None: http_trace.append(request.full_url)
            return io.BytesIO(json.dumps(next(payloads) if payloads is not None else catalog_payload or {'metas': []}).encode())
        vfs_trace = vfs_trace if vfs_trace is not None else []
        def exists(path):
            vfs_trace.append(('exists', path))
            return path in vfs_exists
        def listdir(path):
            vfs_trace.append(('listdir', path))
            return vfs_listing if vfs_listing is not None else ([], [])
        view_trace = view_trace if view_trace is not None else []
        paths = iter(folder_paths or ['plugin://plugin.video.aperture.movies/'+query])
        current_path = ['']
        busy = [busy_checks]
        def folder_path(label):
            current_path[0] = next(paths,current_path[0])
            view_trace.append(('path',current_path[0]))
            return current_path[0]
        def condition(expression):
            if expression == 'System.HasModalDialog' and busy[0]:
                busy[0] -= 1
                return True
            return False
        class Monitor:
            def abortRequested(self): return abort
            def waitForAbort(self,seconds):
                view_trace.append(('wait',seconds))
                if on_wait: on_wait(window)
                return abort
        def rpc(raw):
            r=json.loads(raw);calls.append(r)
            if r['method']=='Files.GetSources':return json.dumps({'result':{'sources':sources}})
            if fail:return json.dumps({'error':{'message':'secret remote URL'}})
            if r['method']=='VideoLibrary.GetMovies':return json.dumps({'result':{'movies':movies or [],'limits':limits or {}}})
            if r['method']=='VideoLibrary.GetGenres':return json.dumps({'result':{'genres':genres or []}})
            return json.dumps({'result':{'files':files or []}})
        class F:
            def __init__(self,*a):vfs_trace.append(('File', a))
            def read(self):return '<sources><video><default>'+default+'</default></video></sources>'
            def close(self):pass
        dialog=types.SimpleNamespace(yesno=lambda *a:dialogs.append(a) or confirm,ok=lambda *a:dialogs.append(a),notification=lambda *a,**kw:dialogs.append(a),browseSingle=lambda *a:picture,input=lambda *a,**kw:search,select=lambda *a:selection)
        mods={
            'xbmc':types.SimpleNamespace(executeJSONRPC=rpc,executebuiltin=builtins.append,log=lambda *a:None,LOGERROR=4,getSupportedMedia=lambda kind:'.avi|.mkv|.mp4',Monitor=Monitor,getInfoLabel=folder_path,getCondVisibility=condition),
            'xbmcaddon':types.SimpleNamespace(Addon=lambda:types.SimpleNamespace(getAddonInfo=lambda key:self.profile)),
            'xbmcgui':types.SimpleNamespace(Window=lambda *a:window,ListItem=Item,Dialog=lambda:dialog,getCurrentWindowId=window_id),
            'xbmcplugin':types.SimpleNamespace(setContent=lambda *a:None,setPluginCategory=lambda *a:categories.append(a),endOfDirectory=lambda *a,**kw:ended.append(kw),addDirectoryItem=lambda *a:entries.append(a)),
            'xbmcvfs':types.SimpleNamespace(translatePath=lambda p:p,File=F,exists=exists,listdir=listdir),
        }
        sys.path.insert(0,str(ROOT/'movies-kodi'))
        saved={k:v for k,v in sys.modules.items() if k=='resources' or k.startswith('resources.')}
        for k in list(saved):sys.modules.pop(k)
        try:
            with patch('urllib.request.OpenerDirector.open', side_effect=fetch),patch.dict(sys.modules,mods),patch.object(sys,'argv',['plugin://plugin.video.aperture.movies/','3',query]):
                exec(compile((ROOT/'movies-kodi/addon.py').read_text(), str(ROOT/'movies-kodi/addon.py'), 'exec'), {'__name__':'__main__'})
        finally:
            sys.path.pop(0)
            for k in list(sys.modules):
                if k=='resources' or k.startswith('resources.'):sys.modules.pop(k)
            sys.modules.update(saved)
        return calls,entries,dialogs,ended,builtins
    def test_online_catalogue_never_calls_local_library_or_plays(self):
        c,e,d,x,b=self.run_plugin([],query='?mode=online',catalog_payload={'metas':[{'id':'tt1234567','name':'Online Film','poster':'https://example.org/p.jpg','streams':[{'url':'https://example.org/film'}]}]})
        self.assertEqual(c,[])
        self.assertEqual(e[0][2].props['IsPlayable'],'false')
        self.assertIn('action=torrentio_auto',e[0][1])
        self.assertNotIn('https://example.org/film',repr(e))
        self.assertIn('start=1',e[-1][1])
    def test_local_playable_is_tagged_as_movie_for_pause_policy(self):
        c,e,d,x,b=self.run_plugin([{'file':'/movies/','label':'Movies'}],files=[{'file':'/movies/a.mkv','filetype':'file','label':'A'}])
        self.assertEqual(getattr(e[0][2], 'media_type', None), 'movie')
    def test_online_movie_has_manual_chooser_and_automatic_default(self):
        c,e,d,x,b=self.run_plugin([],query='?mode=online',catalog_payload={'metas':[{'id':'tt1234567','name':'Example'}]})
        self.assertIn(('Choose source', 'RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_find&id=tt1234567)'), e[0][2].context)
        self.assertIn('action=torrentio_auto', e[0][1])
        self.assertEqual(e[0][2].props['IsPlayable'], 'false')

    def test_auto_action_dispatches_without_local_source_access(self):
        c,e,d,x,b=self.run_plugin([],query='?action=torrentio_auto&id=tt1234567')
        self.assertEqual(c, [])
        self.assertIn('Online playback is not connected', repr(d))
        self.assertEqual((e,x,b), ([],[],[]))

    def test_torrentio_action_dispatches_without_local_source_access(self):
        c,e,d,x,b=self.run_plugin([],query='?action=torrentio_find&id=tt1234567')
        self.assertEqual(c, [])
        self.assertIn('Online playback is not connected', repr(d))
        self.assertEqual((e,x,b), ([],[],[]))

    def test_online_search_cancel_does_not_navigate(self):
        c,e,d,x,b=self.run_plugin([],query='?action=search',folder_paths=['plugin://plugin.video.aperture.movies/?mode=online'],search='')
        self.assertEqual((c,e,x,b),([],[],[],[]))
    def test_online_search_navigation_is_stale_safe(self):
        c,e,d,x,b=self.run_plugin([],query='?action=search',folder_paths=['plugin://plugin.video.aperture.movies/?mode=online','plugin://other/'],search='Example')
        self.assertEqual(b,[])
    def test_movie_details_exposes_visible_find_streams_action(self):
        c,e,d,x,b=self.run_plugin([],query='?action=online_details&id=tt1234567',selection=0,catalog_payload={'meta':{'id':'tt1234567','name':'Example','description':'A plot'}})
        self.assertEqual(b, ['RunPlugin(plugin://plugin.video.aperture.movies/?action=torrentio_find&id=tt1234567)'])
        self.assertIn('Playback availability not checked', repr(d))
        self.assertEqual(c, [])

    def test_online_details_is_metadata_only(self):
        c,e,d,x,b=self.run_plugin([],query='?action=online_details&id=tt1234567',catalog_payload={'meta':{'id':'tt1234567','name':'Example','description':'A plot'}})
        self.assertEqual((c,e,b),([],[],[]))
        self.assertIn('Playback availability not checked',repr(d))
    def test_suggestions_catalogue_failure_is_generic_and_keeps_clear_available(self):
        trace = []
        c,e,d,x,b = self.run_plugin([], query='?mode=suggested', catalog_payload={'metas': 'invalid'}, http_trace=trace)
        self.assertEqual(c, [])
        self.assertIn('Suggestions unavailable', repr(d))
        self.assertTrue(any('clear_history' in row[1] for row in e))

    def test_unreadable_history_shows_generic_error_and_clear_recovery(self):
        directory = Path(self.profile) / 'history-private'
        directory.mkdir(mode=0o700)
        path = directory / 'history.json'
        path.write_text('broken-private-data')
        path.chmod(0o600)
        c,e,d,x,b = self.run_plugin([], query='?mode=history')
        self.assertEqual(c, [])
        self.assertIn('History unavailable', repr(d))
        self.assertNotIn('broken-private-data', repr(d))
        self.assertTrue(any('clear_history' in row[1] for row in e))
        self.assertEqual(path.read_text(), 'broken-private-data')

    def test_confirmed_clear_waits_for_service_and_refreshes_only_same_directory(self):
        from test_movie_history_playback import load
        from test_movie_history import history, MOVIE
        from unittest.mock import Mock
        bridge = load()
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        store.record_playback(MOVIE, is_playing=True, position_seconds=10, duration_seconds=100, lastplayed=1)
        def service(window):
            bridge.HistoryMonitor(store, Mock(), window).update()
        c,e,d,x,b = self.run_plugin([], query='?action=clear_history', confirm=True,
                                    on_wait=service, properties={})
        self.assertEqual(store.records(), [])
        self.assertEqual((c,e,x), ([],[],[]))
        self.assertEqual(b, ['Container.Refresh'])
        c,e,d,x,b = self.run_plugin([], query='?action=clear_history', confirm=True, properties={})
        self.assertIn('not confirmed', repr(d))
        self.assertEqual(b, [])
        c,e,d,x,b = self.run_plugin([], query='?action=clear_history', confirm=True,
            on_wait=service, properties={}, folder_paths=['plugin://plugin.video.aperture.movies/?mode=history', 'plugin://other/'])
        self.assertEqual(b, [])

    def test_history_collections_remain_navigable_and_clear_is_confirmed(self):
        for mode in ('history', 'continue', 'suggested'):
            c,e,d,x,b = self.run_plugin([], query='?action=collection', selection=3,
                folder_paths=['plugin://plugin.video.aperture.movies/?mode=' + mode])
            self.assertEqual(b, ['Container.Update(plugin://plugin.video.aperture.movies/?mode=history)'])
        c,e,d,x,b = self.run_plugin([], query='?action=clear_history')
        self.assertEqual((c,e,x,b), ([],[],[],[]))
        self.assertIn('backups', repr(d))

    def test_suggestions_rank_locally_over_default_public_batch(self):
        from test_movie_history import history, MOVIE
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        for ident in ('tt1234567', 'tt7654321'):
            store.record_playback(dict(MOVIE, id=ident), is_playing=True, position_seconds=10,
                                  duration_seconds=100, lastplayed=1)
        payload = {'metas': [{'id': 'tt1234567', 'name': 'Watched', 'genres': ['Drama']},
                             {'id': 'tt1111111', 'name': 'Match', 'genres': ['Drama']},
                             {'id': 'tt2222222', 'name': 'Other', 'genres': ['Horror']}]}
        trace = []
        c,e,d,x,b = self.run_plugin([], query='?mode=suggested&genre=Drama&search=private&start=60',
                                    catalog_payload=payload, http_trace=trace)
        self.assertEqual(c, [])
        self.assertEqual(trace, ['https://v3-cinemeta.strem.io/catalog/movie/top/skip=0.json'])
        films = [entry for entry in e if 'id=' in entry[1]]
        self.assertEqual([entry[2].kw['label'] for entry in films], ['Match'])
        self.assertIn('action=torrentio_auto', films[0][1])
        self.assertEqual(d, [])
        store.clear()
        categories = []
        self.run_plugin([], query='?mode=suggested', catalog_payload=payload, categories=categories)
        self.assertIn('catalogue suggestions only', repr(categories))

    def test_history_and_continue_list_saved_metadata_with_explicit_resume(self):
        from test_movie_history import history, MOVIE
        store = history.HistoryStore(Path(self.profile) / 'history-private')
        store.record_playback(MOVIE, is_playing=True, position_seconds=42, duration_seconds=100, lastplayed=1)
        store.record_playback(dict(MOVIE, id='tt7654321', title='Finished'), is_playing=True,
                              position_seconds=95, duration_seconds=100, lastplayed=2)
        for mode, count in [('history', 2), ('continue', 1)]:
            c,e,d,x,b = self.run_plugin([], query='?mode=' + mode)
            self.assertEqual(c, [], 'History must not query local sources/accounts')
            films = [entry for entry in e if 'id=' in entry[1]]
            self.assertEqual(len(films), count)
            film = next(entry for entry in films if 'tt1234567' in entry[1])
            self.assertIn('resume=1', film[1])
            self.assertIn('Play from beginning', repr(film[2].context))
            self.assertIn('Clear history', repr([entry[2].kw for entry in e]))
            self.assertNotIn('https://', repr(e))
            self.assertEqual(d, [])
            self.assertTrue(x[-1]['succeeded'])
        self.assertEqual(len(store.records()), 2)

    def test_online_collections_exposes_private_history_sections(self):
        for selected, mode in ((3, 'history'), (4, 'continue'), (5, 'suggested')):
            with self.subTest(mode=mode):
                c,e,d,x,b=self.run_plugin([], query='?action=collection',
                    folder_paths=['plugin://plugin.video.aperture.movies/?mode=online'], selection=selected)
                self.assertEqual(b, ['Container.Update(plugin://plugin.video.aperture.movies/?mode=' + mode + ')'])
                self.assertEqual(c, [])

    def test_online_collection_can_open_local_library(self):
        c,e,d,x,b=self.run_plugin([],query='?action=collection',folder_paths=['plugin://plugin.video.aperture.movies/?mode=online'],selection=2)
        self.assertEqual(b,['Container.Update(plugin://plugin.video.aperture.movies/?mode=discover)'])
    def test_single_source_opens_without_chooser(self):
        c,e,d,x,b=self.run_plugin([{'label':'Drive','file':'/movies/'}],files=[{'label':'Film.mkv','file':'/movies/Film.mkv','filetype':'file'}])
        self.assertEqual(c[1]['params']['directory'],'/movies/')
        self.assertEqual(e[0][1],'/movies/Film.mkv')
        self.assertEqual(e[0][2].props['IsPlayable'],'true')
        self.assertIn('Container.SetViewMode(61)',b)
    def test_folder_is_encoded_plugin_route(self):
        c,e,*_=self.run_plugin([{'label':'Drive','file':'/movies/'}],files=[{'label':'A & B','file':'/movies/A & B/','filetype':'directory'}])
        self.assertIn('path=%2Fmovies%2FA+%26+B%2F',e[0][1]);self.assertTrue(e[0][3])
    def test_multiple_choices_do_not_scan(self):
        c,e,d,x,b=self.run_plugin([{'label':'A','file':'/a/'},{'label':'B','file':'/b/'}])
        self.assertEqual(len(c),1);self.assertEqual(len(e),2);self.assertIn('Container.SetViewMode(61)',b)
    def test_default_skips_multiple_choices(self):
        c,e,*_=self.run_plugin([{'label':'A','file':'/a/'},{'label':'B','file':'/b/'}],default='B')
        self.assertEqual(c[1]['params']['directory'],'/b/')
    def test_invalid_path_never_read(self):
        c,e,d,x,b=self.run_plugin([{'label':'A','file':'/a/'}],query='?source=%2Fa%2F&path=%2Fetc')
        self.assertEqual(len(c),1);self.assertEqual(e,[]);self.assertFalse(x[-1]['succeeded'])
    def test_no_source_explains_without_writing(self):
        c,e,d,x,b=self.run_plugin([]);self.assertEqual(len(c),1);self.assertTrue(d);self.assertEqual(e,[])
    def test_error_is_generic_and_fails_closed(self):
        c,e,d,x,b=self.run_plugin([{'label':'A','file':'/a/'}],fail=True)
        self.assertFalse(x[-1]['succeeded']);self.assertNotIn('secret',repr(d))

    def test_vfs_fallback_filters_supported_extensions_case_insensitively(self):
        c,e,d,x,b=self.run_plugin(
            [{'label':'Drive','file':'/movies/'}], fail=True,
            vfs_exists={'/movies/'},
            vfs_listing=([], ['Film.MKV','Other.mp4','Third.avi','cover.jpg','notes.txt','Fake.mkv.bak']))
        self.assertEqual({entry[1] for entry in e},
                         {'/movies/Film.MKV','/movies/Other.mp4','/movies/Third.avi'})
        self.assertTrue(all(entry[2].props['IsPlayable']=='true' for entry in e))
        self.assertTrue(x[-1]['succeeded'])
        self.assertEqual(d, [])

    def test_vfs_fallback_keeps_folders_and_encodes_routes(self):
        c,e,d,x,b=self.run_plugin(
            [{'label':'Drive','file':'/movies/'}], fail=True,
            vfs_exists={'/movies/'},
            vfs_listing=(['A & B','Extras.txt'], ['Zebra.mkv']))
        folders=[entry for entry in e if entry[3]]
        self.assertEqual(len(folders),2)
        self.assertIn('path=%2Fmovies%2FA+%26+B%2F',folders[0][1])
        self.assertIn('path=%2Fmovies%2FExtras.txt%2F',folders[1][1])
        self.assertTrue(all(entry[2].props['Aperture.MovieFolder']=='true' for entry in folders))
        self.assertTrue(x[-1]['succeeded'])

    def test_denied_rpc_fallback_does_not_enable_source_sharing(self):
        trace=[]
        c,e,d,x,b=self.run_plugin(
            [{'label':'Private drive','file':'/movies/','allowsharing':False}],
            fail=True,vfs_exists={'/movies/'},vfs_listing=([],['Film.mkv']),vfs_trace=trace)
        self.assertEqual([call['method'] for call in c],['Files.GetSources','Files.GetDirectory'])
        self.assertEqual(b,['Container.SetViewMode(61)'])
        self.assertEqual([event for event in trace if event[0]=='File'],
                         [('File',('special://profile/sources.xml',))])
        self.assertEqual([event for event in trace if event[0]=='listdir'],
                         [('listdir','/movies/')])
        self.assertTrue(x[-1]['succeeded'])

    def test_vfs_fallback_nonexistent_path_fails_gracefully(self):
        trace=[]
        c,e,d,x,b=self.run_plugin(
            [{'label':'Missing drive','file':'/missing/'}],fail=True,vfs_trace=trace)
        self.assertEqual(e,[])
        self.assertFalse(x[-1]['succeeded'])
        self.assertTrue(d)
        self.assertNotIn('secret',repr(d))
        self.assertNotIn('listdir',[event[0] for event in trace])
        self.assertEqual(b,[])

    def test_view_waits_for_nested_directory_and_modal_to_clear(self):
        trace=[]
        query='?source=%2Fmovies%2F&path=%2Fmovies%2FA+%26+B%2F'
        # Same URL with reordered query keys and percent-encoded spaces is equivalent.
        ready='plugin://plugin.video.aperture.movies/?path=%2Fmovies%2FA%20%26%20B%2F&source=%2Fmovies%2F'
        c,e,d,x,b=self.run_plugin([{'label':'Drive','file':'/movies/'}],query=query,
            folder_paths=['plugin://plugin.video.aperture.movies/',ready],busy_checks=1,view_trace=trace)
        self.assertEqual(b,['Container.SetViewMode(61)'])
        self.assertEqual([event for event in trace if event[0]=='wait'],[('wait',0.05),('wait',0.05)])

    def test_view_wait_is_bounded_and_never_changes_another_directory(self):
        trace=[]
        c,e,d,x,b=self.run_plugin([{'label':'Drive','file':'/movies/'}],
            folder_paths=['plugin://other/'],view_trace=trace)
        self.assertEqual(b,[])
        waits=[event[1] for event in trace if event[0]=='wait']
        self.assertEqual(len(waits),60)
        self.assertAlmostEqual(sum(waits),3.0)
        self.assertTrue(x[-1]['succeeded'])

    def test_view_wait_obeys_abort(self):
        trace=[]
        c,e,d,x,b=self.run_plugin([{'label':'Drive','file':'/movies/'}],abort=True,view_trace=trace)
        self.assertEqual(b,[])
        self.assertEqual(trace,[])

    def poster_query(self, action='choose_poster', source='/movies/', movie='/movies/Film.mkv'):
        return '?'+urlencode({'action':action,'source':source,'movie':movie})

    def picture(self, name='chosen.png'):
        path=Path(self.profile)/name
        path.write_bytes(b'original fixture image')
        return str(path)

    def test_context_actions_are_encoded_and_browse_does_not_write(self):
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],files=[{'file':'/movies/A & B (2026).mkv','filetype':'file'}])
        menu=e[0][2].context
        self.assertEqual([item[0] for item in menu],['Choose local poster...','Use automatic poster'])
        self.assertIn('movie=%2Fmovies%2FA+%26+B+%282026%29.mkv',menu[0][1])
        self.assertEqual(list(Path(self.profile).iterdir()), [])

    def test_choose_persists_then_browse_uses_choice_and_reset_preserves_image(self):
        picture=self.picture()
        for _ in range(2):
            c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=self.poster_query(),picture=picture)
            self.assertEqual([call['method'] for call in c], ['Files.GetSources'])
            self.assertEqual(b,['Container.Refresh']); self.assertEqual(x,[])
        self.assertEqual(len(list((Path(self.profile)/'posters').iterdir())),1)
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],files=[{'file':'/movies/Film.mkv','filetype':'file','art':{'poster':'kodi-poster'}}])
        self.assertEqual(e[0][2].art['poster'],picture)
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=self.poster_query('reset_poster'))
        self.assertTrue(Path(picture).is_file()); self.assertEqual(b,['Container.Refresh'])
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],files=[{'file':'/movies/Film.mkv','filetype':'file','art':{'poster':'kodi-poster'}}])
        self.assertEqual(e[0][2].art['poster'],'kodi-poster')

    def test_cancel_preserves_choice_without_refresh_or_directory_completion(self):
        self.run_plugin([{'file':'/movies/'}],query=self.poster_query(),picture=self.picture())
        choice=next((Path(self.profile)/'posters').glob('*.json')); before=choice.read_bytes()
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=self.poster_query())
        self.assertEqual(choice.read_bytes(),before)
        self.assertEqual((e,d,x,b),([],[],[],[]))

    def test_poster_action_never_refreshes_newer_navigation(self):
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=self.poster_query(),picture=self.picture(),
                                folder_paths=['plugin://plugin.video.aperture.movies/','plugin://different/'])
        self.assertEqual(b,[])
        self.assertEqual(len(list((Path(self.profile)/'posters').glob('*.json'))),1)

    def test_invalid_action_source_or_movie_never_saves(self):
        picture=self.picture()
        for query in (self.poster_query(source='/other/'),self.poster_query(movie='/outside/Film.mkv'),
                      self.poster_query(movie='/movies/../outside/Film.mkv'),
                      self.poster_query(movie='/movies/poster.jpg'),self.poster_query('unknown')):
            c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=query,picture=picture)
            self.assertFalse((Path(self.profile)/'posters').exists())
            self.assertEqual((e,x,b),([],[],[]))

    def test_invalid_external_picture_keeps_browsing_and_state_unchanged(self):
        c,e,d,x,b=self.run_plugin([{'file':'/movies/'}],query=self.poster_query(),picture='https://example.invalid/poster.jpg')
        self.assertFalse((Path(self.profile)/'posters').exists())
        self.assertTrue(d); self.assertEqual(b,[])
        self.assertNotIn('example.invalid',str(d))

    def test_directory_thumbnail_is_preserved(self):
        c,e,*_=self.run_plugin([{'file':'/movies/'}],files=[{'file':'/movies/Collection/','filetype':'directory','thumbnail':'folder-cover'}])
        self.assertEqual(e[0][2].art['thumb'],'folder-cover')

    def test_generic_poster_is_not_reused_for_multiple_movies(self):
        files=[{'file':'/movies/One.mkv','filetype':'file'},{'file':'/movies/Two.mkv','filetype':'file'}]
        c,e,*_=self.run_plugin([{'file':'/movies/'}],files=files,vfs_exists={'/movies/poster.jpg'})
        self.assertTrue(all('poster' not in entry[2].art for entry in e))
        c,e,*_=self.run_plugin([{'file':'/movies/'}],files=files[:1],vfs_exists={'/movies/poster.jpg'})
        self.assertEqual(e[0][2].art['poster'],'/movies/poster.jpg')



class DiscoveryTests(unittest.TestCase):
    setUp = PluginTests.setUp
    run_plugin = PluginTests.run_plugin
    def test_catalogue_is_read_only_and_paged(self):
        c,e,d,x,b=self.run_plugin([],query='?mode=discover',movies=[{'movieid':12,'title':'Example','file':'/films/Example.mkv','resume':{'position':12,'total':120}}],limits={'end':60,'total':80})
        self.assertEqual([r['method'] for r in c],['VideoLibrary.GetMovies'])
        self.assertEqual(c[0]['params']['limits'],{'start':0,'end':60})
        self.assertEqual(e[0][1],'/films/Example.mkv')
        self.assertEqual(e[0][2].dbid,12)
        self.assertEqual(e[0][2].resume,(12,120))
        self.assertIn('start=60',e[1][1])
        self.assertEqual(e[1][2].kw['label'],'More movies')
        self.assertTrue(x[-1]['succeeded'])
    def test_filters_and_pagination_preserve_state(self):
        c,e,*_=self.run_plugin([],query='?mode=discover&collection=unwatched&genre=Drama&search=Example&start=60',movies=[{'title':'Example','file':'/film.mkv'}],limits={'end':120,'total':200})
        filters=c[0]['params']['filter']['and']
        self.assertEqual({f['field'] for f in filters},{'title','genre','playcount'})
        self.assertIn('genre=Drama',e[-1][1]);self.assertIn('search=Example',e[-1][1]);self.assertIn('start=120',e[-1][1])
    def test_empty_discover_keeps_files_available(self):
        c,e,d,x,b=self.run_plugin([],query='?mode=discover')
        self.assertIn('Local files',d[0][1]);self.assertTrue(x[-1]['succeeded'])
    def test_discover_failure_redacts_and_fails(self):
        c,e,d,x,b=self.run_plugin([],query='?mode=discover',fail=True)
        self.assertFalse(x[-1]['succeeded']);self.assertNotIn('secret',repr(d))
    def test_cancelled_search_does_not_change_history(self):
        c,e,d,x,b=self.run_plugin([],query='?action=search')
        self.assertEqual((c,e,x,b),([],[],[],[]))
    def test_search_is_encoded_and_does_not_scan_or_write(self):
        c,e,d,x,b=self.run_plugin([],query='?action=search',search='Title & More)')
        self.assertEqual((c,e,x),([],[],[]));self.assertEqual(len(b),1)
        self.assertIn('search=Title+%26+More%29',b[0])
    def test_stale_search_cannot_replace_new_destination(self):
        c,e,d,x,b=self.run_plugin([],query='?action=search',search='Title',folder_paths=['plugin://plugin.video.aperture.movies/?mode=discover','videodb://movies/'])
        self.assertEqual(b,[])
    def test_cancelled_collection_keeps_history(self):
        c,e,d,x,b=self.run_plugin([],query='?action=collection',selection=-1)
        self.assertEqual((c,e,x,b),([],[],[],[]))
    def test_collection_select_routes_without_playback(self):
        c,e,d,x,b=self.run_plugin([],query='?action=collection',selection=2)
        self.assertEqual(c,[]);self.assertIn('collection=resume',b[0])
    def test_genre_choice_uses_existing_kodi_metadata(self):
        c,e,d,x,b=self.run_plugin([],query='?action=genre',selection=1,genres=[{'label':'Drama'}])
        self.assertEqual(c[0]['method'],'VideoLibrary.GetGenres');self.assertIn('genre=Drama',b[0])
    def test_provider_status_never_authenticates(self):
        c,e,d,x,b=self.run_plugin([],query='?action=providers')
        self.assertEqual((c,e,d,x,b),([],[],[],[],[]))  # Closing Sources does not authenticate.

    def test_genre_failure_does_not_finish_current_directory(self):
        c,e,d,x,b=self.run_plugin([],query='?action=genre',fail=True)
        self.assertEqual((e,x,b),([],[],[]));self.assertNotIn('secret',repr(d))

if __name__ == '__main__':
    unittest.main()
