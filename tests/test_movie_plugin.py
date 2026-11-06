from pathlib import Path
import json,runpy,sys,types,unittest,tempfile
from unittest.mock import patch
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]

class Item:
    def __init__(self,**kw): self.kw=kw; self.art={}; self.props={}
    def setArt(self,a):self.art=a
    def addContextMenuItems(self,a):self.context=a
    def setProperty(self,k,v):self.props[k]=v
    def setInfo(self,*a):pass
    def getVideoInfoTag(self):return self
    def setDuration(self,x):pass

class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.profile=self.temporary.name
        self.addCleanup(self.temporary.cleanup)
    def run_plugin(self,sources,query='',default='',files=None,fail=False,vfs_listing=None,vfs_exists=(),vfs_trace=None,folder_paths=None,busy_checks=0,view_trace=None,abort=False,picture=""):
        calls=[]; entries=[]; dialogs=[]; ended=[]; builtins=[]
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
                return abort
        def rpc(raw):
            r=json.loads(raw);calls.append(r)
            if r['method']=='Files.GetSources':return json.dumps({'result':{'sources':sources}})
            if fail:return json.dumps({'error':{'message':'secret remote URL'}})
            return json.dumps({'result':{'files':files or []}})
        class F:
            def __init__(self,*a):vfs_trace.append(('File', a))
            def read(self):return '<sources><video><default>'+default+'</default></video></sources>'
            def close(self):pass
        dialog=types.SimpleNamespace(ok=lambda *a:dialogs.append(a),notification=lambda *a,**kw:dialogs.append(a),browseSingle=lambda *a:picture)
        mods={
            'xbmc':types.SimpleNamespace(executeJSONRPC=rpc,executebuiltin=builtins.append,log=lambda *a:None,LOGERROR=4,getSupportedMedia=lambda kind:'.avi|.mkv|.mp4',Monitor=Monitor,getInfoLabel=folder_path,getCondVisibility=condition),
            'xbmcaddon':types.SimpleNamespace(Addon=lambda:types.SimpleNamespace(getAddonInfo=lambda key:self.profile)),
            'xbmcgui':types.SimpleNamespace(ListItem=Item,Dialog=lambda:dialog),
            'xbmcplugin':types.SimpleNamespace(setContent=lambda *a:None,setPluginCategory=lambda *a:None,endOfDirectory=lambda *a,**kw:ended.append(kw),addDirectoryItem=lambda *a:entries.append(a)),
            'xbmcvfs':types.SimpleNamespace(translatePath=lambda p:p,File=F,exists=exists,listdir=listdir),
        }
        sys.path.insert(0,str(ROOT/'movies-kodi'))
        saved={k:v for k,v in sys.modules.items() if k=='resources' or k.startswith('resources.')}
        for k in list(saved):sys.modules.pop(k)
        try:
            with patch.dict(sys.modules,mods),patch.object(sys,'argv',['plugin://plugin.video.aperture.movies/','3',query]):
                exec(compile((ROOT/'movies-kodi/addon.py').read_text(), str(ROOT/'movies-kodi/addon.py'), 'exec'), {'__name__':'__main__'})
        finally:
            sys.path.pop(0)
            for k in list(sys.modules):
                if k=='resources' or k.startswith('resources.'):sys.modules.pop(k)
            sys.modules.update(saved)
        return calls,entries,dialogs,ended,builtins
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

if __name__=='__main__':unittest.main()
