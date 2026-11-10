"""Pure local ranking: consumes supplied public metadata, never fetches it."""
from collections import Counter
from .movie_history import GENRES, metadata, valid_id


def recommend(candidates, watched, *, current_id=None, limit=20):
    if type(limit) is not int or not 0 <= limit <= 500:
        raise ValueError('limit must be between 0 and 500')
    seen = {}
    for row in watched:
        if not isinstance(row, dict) or not valid_id(row.get('id')):
            continue
        genres = row.get('genres', [])
        if not isinstance(genres, list):
            genres = []
        seen.setdefault(row['id'], set()).update(
            g for g in genres if isinstance(g, str) and g in GENRES)
    excluded = set(seen) | ({current_id} if valid_id(current_id) else set())
    weights = Counter(g for genres in seen.values() for g in genres)
    unique = {}
    for row in candidates:
        item = metadata(row)
        if item and item['id'] not in excluded:
            item['genres'].sort()
            previous = unique.get(item['id'])
            key = lambda value: (value['title'], value['year'], tuple(value['genres']))
            if previous is None or key(item) < key(previous):
                unique[item['id']] = item
    scored = [(sum(weights[g] for g in row['genres']), row) for row in unique.values()]
    scored.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    matches = [row for score, row in scored if score > 0]
    if len(seen) < 2 or not weights or not matches:
        reason = ('Not enough local history; catalogue suggestions only'
                  if len(seen) < 2 or not weights else
                  'No matching genres in supplied catalogue; catalogue suggestions only')
        return {'items': sorted(unique.values(), key=lambda row: row['id'])[:limit],
                'mode': 'catalogue', 'reason': reason}
    return {'items': matches[:limit],
            'mode': 'history', 'reason': 'Based on genres in local playback history'}
