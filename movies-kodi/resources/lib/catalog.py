"""Public Cinemeta metadata only. Never accepts provider streams or local paths."""
import json
import re
from urllib.parse import urlencode, quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ORIGIN = 'https://v3-cinemeta.strem.io'
MAX_BYTES = 2 * 1024 * 1024
GENRES = ('Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime',
          'Documentary', 'Drama', 'Family', 'Fantasy', 'History', 'Horror',
          'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western')
COLLECTIONS = (('top', 'Popular online'), ('imdbRating', 'Featured online'))

class CatalogError(Exception):
    pass

class CatalogRedirect(HTTPRedirectHandler):
    """Allow one observed 307 route; all other redirects fail closed."""
    def redirect_request(self, *args, **kwargs):
        raise CatalogError('Catalogue redirect refused')

    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise CatalogError('Catalogue redirect refused')

    http_error_301 = http_error_303 = http_error_308 = http_error_302

    def http_error_307(self, req, fp, code, msg, headers):
        # Validate the raw Location, before urllib can normalize it. Never drain
        # a redirect body: it is untrusted and could exceed the response limit.
        fp.close()
        route = re.fullmatch(
            re.escape(ORIGIN) + r'(/catalog/movie/(top|imdbRating)/'
            r'skip=(0|[1-9][0-9]{0,4})(?:&genre=([A-Za-z-]+))?\.json)',
            req.full_url)
        if (not route or int(route[3]) > 10000
                or (route[4] is not None and route[4] not in GENRES)
                or req.get_method() != 'GET'):
            raise CatalogError('Catalogue redirect refused')
        target = 'https://cinemeta-catalogs.strem.io/' + route[2] + route[1]
        if headers.get_all('Location') != [target]:
            raise CatalogError('Catalogue redirect refused')
        redirected = Request(target, headers={
            'Accept': 'application/json', 'User-Agent': 'ApertureMovies/0.4'})
        # Only the original host matches above: a second hop/loop cannot pass.
        return self.parent.open(redirected, timeout=req.timeout)


def fetch(path):
    """Fixed HTTPS routes, no credentials, 8s socket timeout and 2 MiB limit."""
    try:
        request = Request(ORIGIN + path, headers={'Accept': 'application/json', 'User-Agent': 'ApertureMovies/0.4'})
        with build_opener(CatalogRedirect).open(request, timeout=8) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Oversized response')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('Invalid response')
        return result
    except Exception:
        raise CatalogError('Online catalogue unavailable') from None


def value(query, name, default=''):
    raw = query.get(name, [default])
    return raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], str) else default


def state(query):
    collection = value(query, 'collection', 'top')
    if collection not in dict(COLLECTIONS):
        collection = 'top'
    result = {'mode': 'online', 'collection': collection}
    search = value(query, 'search').strip()[:200]
    if search:
        result.update(search=search, collection='top')
    genre = value(query, 'genre')
    if genre in GENRES:
        result['genre'] = genre
    try:
        result['start'] = max(0, min(int(value(query, 'start', '0')), 10000))
    except ValueError:
        result['start'] = 0
    return result


def text(value, limit=1000):
    return value[:limit] if isinstance(value, str) else ''


def image(value):
    # Do not allow provider-controlled Kodi pipe headers, local paths or credentials.
    if not isinstance(value, str) or len(value) > 2000 or any(c in value for c in '|\\\r\n'):
        return ''
    try:
        parsed = urlsplit(value)
        safe = (parsed.scheme == 'https' and parsed.hostname in ('images.metahub.space', 'image.tmdb.org')
                and parsed.port in (None, 443) and not parsed.username and not parsed.password)
        return value if safe else ''
    except ValueError:
        return ''


def rating(value):
    if isinstance(value, bool) or not isinstance(value, (str, float, int)):
        return ''
    try:
        parsed = float(value)
    except (ValueError, OverflowError):
        return ''
    return format(parsed, 'g') if 0 <= parsed <= 10 else ''


def normalize(raw):
    if not isinstance(raw, dict) or not re.fullmatch(r'tt\d{5,12}', str(raw.get('id', ''))):
        return None
    title = text(raw.get('name'), 300)
    if not title or raw.get('type', 'movie') != 'movie':
        return None
    return {'id': raw['id'], 'title': title, 'plot': text(raw.get('description'), 12000),
            'year': text(raw.get('releaseInfo'), 30), 'poster': image(raw.get('poster')),
            'fanart': image(raw.get('background')), 'rating': rating(raw.get('imdbRating')),
            'genre': [text(g, 60) for g in raw.get('genres', [])[:20] if isinstance(g, str)] if isinstance(raw.get('genres'), list) else []}


def browse(query, get=fetch):
    current = state(query)
    extras = {'skip': current['start']}
    for key in ('search', 'genre'):
        if key in current:
            extras[key] = current[key]
    path = '/catalog/movie/' + current['collection'] + '/' + urlencode(extras, quote_via=quote) + '.json'
    payload = get(path)
    rows = payload.get('metas')
    if not isinstance(rows, list) or len(rows) > 500:
        raise CatalogError('Invalid catalogue response')
    movies = []
    seen = set()
    for raw in rows:
        movie = normalize(raw)
        if movie and movie['id'] not in seen:
            movies.append(movie)
            seen.add(movie['id'])
    # Provider has no total. A nonempty page offers one more request, never claims a total.
    next_start = current['start'] + len(rows) if rows and current['start'] + len(rows) <= 10000 else None
    return movies, current, next_start


def details(identifier, get=fetch):
    if not re.fullmatch(r'tt\d{5,12}', identifier):
        raise CatalogError('Invalid movie identifier')
    movie = normalize(get('/meta/movie/' + identifier + '.json').get('meta'))
    if not movie or movie['id'] != identifier:
        raise CatalogError('Invalid movie metadata')
    return movie
