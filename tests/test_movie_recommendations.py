"""Deterministic recommendations from supplied catalogue rows only."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

LIB = Path(__file__).resolve().parents[1] / 'movies-kodi/resources/lib'
# Support the production package's relative imports without changing sys.path.
spec = importlib.util.spec_from_file_location('history_core_lib', LIB / '__init__.py',
                                            submodule_search_locations=[str(LIB)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
try:
    from history_core_lib import movie_recommendations as recommendations
except ImportError:
    recommendations = None


def movie(identifier, genres, title='Example'):
    return dict(id=identifier, title=title, genre=genres, year='2024')


class RecommendationTests(unittest.TestCase):
    def recommend(self, candidates, watched, **kwargs):
        self.assertIsNotNone(recommendations, 'recommendation core not implemented')
        return recommendations.recommend(candidates, watched, **kwargs)

    def test_sparse_or_no_matching_history_has_honest_catalogue_fallback(self):
        candidates = [movie('tt2000002', ['Horror']), movie('tt2000001', ['Comedy'])]
        for watched in [[], [dict(id='tt1000001', genres=['Comedy'])]]:
            result = self.recommend(candidates, watched)
            self.assertEqual(result['mode'], 'catalogue')
            self.assertEqual(result['reason'], 'Not enough local history; catalogue suggestions only')
            self.assertEqual([r['id'] for r in result['items']], ['tt2000001', 'tt2000002'])
        result = self.recommend(candidates, [dict(id='tt1000001', genres=['Drama']),
                                             dict(id='tt1000002', genres=['Drama'])])
        self.assertEqual(result['mode'], 'catalogue')
        self.assertEqual(result['reason'], 'No matching genres in supplied catalogue; catalogue suggestions only')
        self.assertEqual(self.recommend([], [])['items'], [])

    def test_conflicting_duplicates_and_malformed_rows_are_deterministic(self):
        candidates = [movie('tt2000001', ['Drama'], 'Zulu'),
                      movie('tt2000001', ['Comedy'], 'Alpha'),
                      None, {}, movie('tt１２３４５６７', ['Drama']),
                      movie('tt2000002', ['Drama'])]
        watched = [None, {}, dict(id='tt1000001', genres=['Drama']),
                   dict(id='tt1000001', genres=['Drama'])]
        result = self.recommend(candidates, watched, limit=1)
        self.assertEqual(result['items'][0]['title'], 'Alpha')
        self.assertEqual(result['mode'], 'catalogue')
        self.assertEqual(result, self.recommend(list(reversed(candidates)),
                                               list(reversed(watched)), limit=1))
        self.assertEqual(self.recommend(candidates, watched, limit=0)['items'], [])
        for limit in [-1, 501, True, '20']:
            with self.assertRaises(ValueError):
                self.recommend(candidates, watched, limit=limit)

    def test_local_genre_ranking_excludes_history_current_and_duplicates(self):
        watched = [dict(movie('tt1000001', []), genres=['Drama'], completed=False),
                   dict(movie('tt1000002', []), genres=['Drama', 'Comedy'], completed=True)]
        candidates = [movie('tt2000002', ['Comedy']), movie('tt2000003', ['Horror']),
                      movie('tt2000001', ['Drama']), movie('tt1000001', ['Drama']),
                      movie('tt1000002', ['Drama']), movie('tt2000004', ['Drama']),
                      movie('tt2000001', ['Drama'])]
        original = copy.deepcopy((candidates, watched))
        result = self.recommend(candidates, watched, current_id='tt2000004')
        self.assertEqual([r['id'] for r in result['items']], ['tt2000001', 'tt2000002'])
        self.assertEqual(result['mode'], 'history')
        self.assertEqual(result['reason'], 'Based on genres in local playback history')
        self.assertEqual(self.recommend(list(reversed(candidates)), watched,
                                       current_id='tt2000004'), result)
        self.assertEqual((candidates, watched), original)


if __name__ == '__main__':
    unittest.main()
