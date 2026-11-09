"""Read-only discovery over Kodi's existing catalogue. No remote provider calls."""
PAGE_SIZE = 60
COLLECTIONS = (
    ('all', 'All movies'), ('recent', 'Recently added'),
    ('resume', 'Continue watching'), ('unwatched', 'Not watched'),
    ('rated', 'Top rated'),
)
PROPERTIES = ['title', 'year', 'plot', 'runtime', 'genre', 'rating', 'art',
              'thumbnail', 'playcount', 'resume', 'file', 'dateadded']


def request(query):
    """Build a bounded Kodi RPC request from a strictly limited set of controls."""
    collection = query.get('collection', ['all'])[0]
    if collection not in dict(COLLECTIONS):
        collection = 'all'
    try:
        start = max(0, min(int(query.get('start', ['0'])[0]), 1000000))
    except (TypeError, ValueError):
        start = 0
    search = query.get('search', [''])[0].strip()[:200]
    genre = query.get('genre', [''])[0].strip()[:100]
    filters = []
    if search:
        filters.append({'field': 'title', 'operator': 'contains', 'value': search})
    if genre:
        filters.append({'field': 'genre', 'operator': 'is', 'value': genre})
    if collection == 'resume':
        filters.append({'field': 'inprogress', 'operator': 'true', 'value': ''})
    elif collection == 'unwatched':
        filters.append({'field': 'playcount', 'operator': 'is', 'value': '0'})
    sort = {'recent': 'dateadded', 'resume': 'lastplayed', 'rated': 'rating'}.get(collection, 'title')
    params = {'properties': PROPERTIES, 'limits': {'start': start, 'end': start + PAGE_SIZE},
              'sort': {'method': sort, 'order': 'ascending' if sort == 'title' else 'descending', 'ignorearticle': True}}
    if filters:
        params['filter'] = filters[0] if len(filters) == 1 else {'and': filters}
    state = {'mode': 'discover', 'collection': collection}
    if search:
        state['search'] = search
    if genre:
        state['genre'] = genre
    heading = dict(COLLECTIONS)[collection]
    if genre:
        heading += ' · ' + genre
    if search:
        heading += ' · Search: ' + search
    return params, state, heading
