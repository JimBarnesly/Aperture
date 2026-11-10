"""In-memory session handoff. Never stores a playback URL or provider data."""
import json
import secrets
import time
from resources.lib.movie_history import HistoryError, HistoryStore, metadata, number, valid_id

PENDING = 'Aperture.Movies.PendingHistory'
EPOCH = 'Aperture.Movies.HistoryEpoch'
CLEAR_ACK = 'Aperture.Movies.HistoryClearAck'
CLEAR = 'Aperture.Movies.HistoryClear'


def request_clear(window):
    request = secrets.token_hex(16)
    window.setProperty(EPOCH, request)
    window.setProperty(CLEAR, request)
    return request


def prepare(window, item, movie, *, epoch='', now=None):
    safe = metadata(movie)
    if safe is None or epoch != window.getProperty(EPOCH):
        return None
    token = secrets.token_hex(16)
    item.getVideoInfoTag().setUniqueID(token, 'aperture_session')
    window.setProperty(PENDING, json.dumps(dict(session=token, movie=safe, epoch=epoch,
                                               expires=(time.monotonic() if now is None else now) + 30)))
    return token


def prepare_history(window, item, identifier, *, profile, epoch, resume=False, store=None):
    import os
    if not valid_id(identifier):
        raise HistoryError('Invalid movie identity')
    store = store or HistoryStore(os.path.join(profile, 'history-private'))
    row = next((r for r in store.records() if r['id'] == identifier), None)
    if row:
        movie = dict(row, genre=row['genres'])
    else:
        from resources.lib.catalog import CatalogError, details
        try:
            movie = details(identifier)
        except CatalogError:
            raise HistoryError('History metadata unavailable') from None
    if resume and row and row['resume_seconds'] > 0:
        item.setProperty('StartOffset', str(row['resume_seconds']))
    return prepare(window, item, movie, epoch=epoch)


class HistoryMonitor:
    def __init__(self, store, player, window, *, clock=time.monotonic, notify=lambda: None):
        self.store, self.player, self.window = store, player, window
        self.clock, self.notify = clock, notify
        self.session = None
        self.sample = None
        self.last_write = float('-inf')

    def finish(self):
        if self.sample:
            self.store.record_playback(**self.sample)
        self.sample = None
        self.session = None
        self.last_write = float('-inf')

    def close(self):
        # Process a queued clear before any final write on service shutdown.
        self.update()
        try:
            self.finish()
        except HistoryError:
            self.notify()
        self.window.clearProperty(PENDING)

    def update(self):
        try:
            self._update()
        except RuntimeError:
            pass  # Player disappeared mid-sample; retain the last valid sample.
        except (ValueError, TypeError, KeyError):
            self.window.clearProperty(PENDING)
        except HistoryError:
            self.sample = None
            self.session = None
            self.window.clearProperty(PENDING)
            self.window.clearProperty(CLEAR)
            self.notify()

    def _update(self):
        request = self.window.getProperty(CLEAR)
        if request:
            self.sample = None
            self.session = None
            self.window.clearProperty(PENDING)
            self.store.clear()
            self.window.clearProperty(CLEAR)
            self.window.setProperty(CLEAR_ACK, request)
        raw = self.window.getProperty(PENDING)
        data = json.loads(raw) if raw else None
        if data and (data['epoch'] != self.window.getProperty(EPOCH)
                     or self.clock() > data['expires']):
            self.window.clearProperty(PENDING)
            data = None
        if not self.player.isPlayingVideo():
            self.finish()
            return
        playing = self.player.getVideoInfoTag().getUniqueID('aperture_session')
        if self.session and self.session['session'] != playing:
            self.finish()
        if not self.session and data and data['session'] == playing:
            self.last_write = float('-inf')
            self.session = data
            self.window.clearProperty(PENDING)
        if not self.session:
            return
        position, duration = self.player.getTime(), self.player.getTotalTime()
        if (not self.player.isPlayingVideo()
                or self.player.getVideoInfoTag().getUniqueID('aperture_session') != playing):
            self.finish()
            return
        if not number(position) or not number(duration) or position <= 0:
            return
        movie = dict(self.session['movie'], genre=self.session['movie']['genres'])
        self.sample = dict(movie=movie, is_playing=True, position_seconds=position,
                           duration_seconds=duration, lastplayed=time.time())
        if self.clock() - self.last_write >= 20:
            self.store.record_playback(**self.sample)
            self.last_write = self.clock()
