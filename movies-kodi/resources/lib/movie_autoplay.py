"""Conservative 1080p/AVC/English preference, not a hardware capability claim."""
import re


def start_video(xbmc, monitor, path, item, current):
    """A queued play command is not evidence of playback (15-second bound)."""
    class StartupPlayer(xbmc.Player):
        av_started = False
        outcome = None

        def onAVStarted(self):
            if owned():
                self.av_started = True

        def onPlayBackError(self):
            if owned():
                self.outcome = 'failed'

        def onPlayBackStopped(self):
            if owned():
                self.outcome = 'cancelled'

        def onPlayBackEnded(self):
            if owned():
                self.outcome = 'cancelled'

    player = StartupPlayer()

    def owner():
        try:
            return player.getVideoInfoTag().getUniqueID('aperture_session') or None
        except (AttributeError, RuntimeError):
            return None

    token = item.getVideoInfoTag().getUniqueID('aperture_session')

    def owned():
        return bool(token) and owner() == token

    def stop_owned():
        if owned():
            player.stop()

    if not current():
        return 'cancelled'
    predecessor = owner()
    cancelled = False
    player.play(path, item)
    for _ in range(150):
        observed = owner()
        if observed and observed not in (token, predecessor):
            return 'cancelled'  # Another player owns playback; never stop it.
        cancelled = cancelled or not current()
        if cancelled:
            if owned():
                stop_owned()
                return 'cancelled'
            if monitor.waitForAbort(0.1):
                stop_owned()
                return 'cancelled'
            continue
        if player.outcome:
            if player.outcome == 'failed':
                if player.isPlayingVideo():
                    stop_owned()
                    return 'timeout'  # Do not overlap a possibly active player.
                if not owned():
                    return 'timeout'  # Lost attribution is not permission to retry.
            return player.outcome
        if player.av_started and player.isPlayingVideo() and owned():
            return 'started'
        if monitor.waitForAbort(0.1):
            stop_owned()
            return 'cancelled'
    stop_owned()
    return 'cancelled' if cancelled else 'timeout'



def rank_sources(sources):
    """Rank finite sanitized labels; missing metadata stays explicitly unknown.

    Resolution/codec/language are provider hints, not verified media inspection.
    Byte size deliberately cannot outweigh decode/display suitability.
    """
    def score(source):
        text = source.label.lower()
        language = 0 if 'english' in text else 1 if 'multi' in text else 2 if 'language unspecified' in text else 3
        codec = 0 if re.search(r'\b(avc|x264|h\.?264)\b', text) else 1 if 'codec unspecified' in text else 2 if re.search(r'\b(hevc|x265|h\.?265)\b', text) else 3
        resolution = next((rank for value, rank in [('1080p', 0), ('720p', 1), ('480p', 2), ('2160p', 4), ('4k', 4)] if value in text), 3)
        return language, resolution == 4, codec, resolution
    unique = {}
    for source in sources:
        unique.setdefault(source.id, source)
    return sorted(unique.values(), key=score)
