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
    def run_plugin(self,sources,query='',default='',files=None,fail=False):
        calls=[]; entries=[]; dialogs=[]; ended=[]; builtins=[]
        def rpc(raw):
            r=json.loads(raw);calls.append(r)
            if r['method']=='Files.GetSources':return json.dumps({'result':{'sources':sources}})
            if fail:return json.dumps({'error':{'message':'secret remote URL'}})
            return json.dumps({'result':{'files':files or []}})
        class F:
            def __init__(self,*a):pass
            def read(self):return '<sources><video><default>'+default+'</default></video></sources>'
            def close(self):pass
        dialog=types.SimpleNamespace(ok=lambda *a:dialogs.append(a),notification=lambda *a,**kw:dialogs.append(a))
        mods={
            'xbmc':types.SimpleNamespace(executeJSONRPC=rpc,executebuiltin=builtins.append,log=lambda *a:None,LOGERROR=4),
            'xbmcaddon':types.SimpleNamespace(Addon=lambda:None),
            'xbmcgui':types.SimpleNamespace(ListItem=Item,Dialog=lambda:dialog),
            'xbmcplugin':types.SimpleNamespace(setContent=lambda *a:None,setPluginCategory=lambda *a:None,endOfDirectory=lambda *a,**kw:ended.append(kw),addDirectoryItem=lambda *a:entries.append(a)),
            'xbmcvfs':types.SimpleNamespace(translatePath=lambda p:p,File=F,exists=lambda p:False),
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

if __name__=='__main__':unittest.main()
