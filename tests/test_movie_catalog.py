from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog', ROOT/'movies-kodi/resources/lib/catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

class CatalogTests(unittest.TestCase):
    def test_search_encoding_filters_and_bounds(self):
        paths=[]
        movies,state,next_start=catalog.browse({'search':['A & B/../?'], 'start':['-5'], 'genre':['Drama']}, lambda p: paths.append(p) or {'metas':[]})
        self.assertEqual(paths, ['/catalog/movie/top/skip=0&search=A%20%26%20B%2F..%2F%3F&genre=Drama.json'])
        self.assertIsNone(next_start)
    def test_normalize_drops_streams_and_invalid_identity(self):
        rows=[{'id':'tt1234567','name':'Example','streams':[{'url':'secret'}]}, {'id':'../bad','name':'Bad'}, {'id':'tt1234567','name':'Duplicate'}]
        movies,_,next_start=catalog.browse({},lambda _: {'metas':rows})
        self.assertEqual(len(movies),1)
        self.assertNotIn('streams',movies[0])
        self.assertEqual(next_start,3)
    def test_malformed_response(self):
        for value in (None, {}, 'text', [None]*501):
            with self.assertRaises(catalog.CatalogError):
                catalog.browse({},lambda _: {'metas':value})
    def test_safe_artwork(self):
        for value in ('file:///etc/passwd','http://example.org/a','https://user:password@example.org/a','https://example.org/a|Authorization=secret',None, 'https://127.0.0.1/private', 'https://[bad', 'https://images.metahub.space:bad/a'):
            self.assertEqual(catalog.image(value),'')
        self.assertEqual(catalog.image('https://images.metahub.space/a.jpg'),'https://images.metahub.space/a.jpg')
    def test_details_validates_identity_before_network(self):
        calls=[]
        with self.assertRaises(catalog.CatalogError):catalog.details('../secret',lambda p:calls.append(p))
        self.assertFalse(calls)
        with self.assertRaises(catalog.CatalogError):catalog.details('tt1234567',lambda _: {'meta':{'id':'tt9999999','name':'Wrong'}})
    def test_network_failure_is_redacted(self):
        with patch.object(catalog,'build_opener',side_effect=OSError('secret')):
            with self.assertRaisesRegex(catalog.CatalogError,'^Online catalogue unavailable$'):catalog.fetch('/catalog/movie/top.json')
    def test_redirects_refused(self):
        with self.assertRaises(catalog.CatalogError):catalog.CatalogRedirect().redirect_request(None,None,None,None,None,None)
    def test_oversized_response(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b' ' * n
        class Opener:
            def open(self,*args,**kwargs):return Response()
        with patch.object(catalog,'build_opener',return_value=Opener()):
            with self.assertRaises(catalog.CatalogError):catalog.fetch('/catalog/movie/top.json')

    def test_unknown_or_invalid_rating_is_omitted(self):
        for value in (None, 'N/A', 'nan', float('inf'), True, -1, 11, [], {}):
            self.assertEqual(catalog.rating(value), '')
        self.assertEqual(catalog.rating('8.3'), '8.3')
