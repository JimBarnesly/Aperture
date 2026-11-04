from pathlib import Path
import json,runpy,sys,types,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]

class Item:
    def __init__(self,**kw): self.kw=kw; self.art={}; self.props={}
    def setArt(self,a):self.art=a
    def setProperty(self,k,v):self.props[k]=v
    def setInfo(self,*a):pass
    def getVideoInfoTag(self):return self
    def setDuration(self,x):pass

class PluginTests(unittest.TestCase):
    def run_plugin(self,sources,query='',default='',files=None,fail=False,vfs_listing=None,vfs_exists=(),vfs_trace=None):
        calls=[]; entries=[]; dialogs=[]; ended=[]; builtins=[]
        vfs_trace = vfs_trace if vfs_trace is not None else []
        def exists(path):
            vfs_trace.append(('exists', path))
            return path in vfs_exists
        def listdir(path):
            vfs_trace.append(('listdir', path))
            return vfs_listing if vfs_listing is not None else ([], [])
        def rpc(raw):
            r=json.loads(raw);calls.append(r)
            if r['method']=='Files.GetSources':return json.dumps({'result':{'sources':sources}})
            if fail:return json.dumps({'error':{'message':'secret remote URL'}})
            return json.dumps({'result':{'files':files or []}})
        class F:
            def __init__(self,*a):vfs_trace.append(('File', a))
            def read(self):return '<sources><video><default>'+default+'</default></video></sources>'
            def close(self):pass
        dialog=types.SimpleNamespace(ok=lambda *a:dialogs.append(a),notification=lambda *a,**kw:dialogs.append(a))
        mods={
            'xbmc':types.SimpleNamespace(executeJSONRPC=rpc,executebuiltin=builtins.append,log=lambda *a:None,LOGERROR=4,getSupportedMedia=lambda kind:'.avi|.mkv|.mp4'),
            'xbmcaddon':types.SimpleNamespace(Addon=lambda:None),
            'xbmcgui':types.SimpleNamespace(ListItem=Item,Dialog=lambda:dialog),
            'xbmcplugin':types.SimpleNamespace(setContent=lambda *a:None,setPluginCategory=lambda *a:None,endOfDirectory=lambda *a,**kw:ended.append(kw),addDirectoryItem=lambda *a:entries.append(a)),
            'xbmcvfs':types.SimpleNamespace(translatePath=lambda p:p,File=F,exists=exists,listdir=listdir),
        }
        sys.path.insert(0,str(ROOT/'movies-kodi'))
        saved={k:v for k,v in sys.modules.items() if k=='resources' or k.startswith('resources.')}
        for k in list(saved):sys.modules.pop(k)
        try:
            with patch.dict(sys.modules,mods),patch.object(sys,'argv',['plugin://plugin.video.aperture.movies/','3',query]):
                runpy.run_path(str(ROOT/'movies-kodi/addon.py'),run_name='__main__')
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

if __name__=='__main__':unittest.main()
