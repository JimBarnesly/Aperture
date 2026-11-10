"""Conservative 1080p/AVC/English preference, not a hardware capability claim."""
import re


def start_video(xbmc, monitor, path, item, current):
    """A queued play command is not evidence of playback (15-second bound)."""
    class StartupPlayer(xbmc.Player):
        av_started = False
        outcome = None

        def onAVStarted(self):
            self.av_started = True

        def onPlayBackError(self):
            self.outcome = 'failed'

        def onPlayBackStopped(self):
            self.outcome = 'cancelled'

        def onPlayBackEnded(self):
            self.outcome = 'cancelled'

    player = StartupPlayer()
    if not current():
        return 'cancelled'
    player.play(path, item)
    for _ in range(150):
        if player.isPlayingVideo() and player.getPlayingFile() != path.split('|', 1)[0]:
            return 'cancelled'  # Another player owns playback; never stop it.
        if not current():
            player.stop()
            return 'cancelled'
        if player.outcome:
            if player.outcome == 'failed' and player.isPlayingVideo():
                player.stop()
                return 'timeout'  # Do not overlap a possibly active player.
            return player.outcome
        if player.av_started and player.isPlayingVideo():
            return 'started'
        if monitor.waitForAbort(0.1):
            player.stop()
            return 'cancelled'
    player.stop()
    return 'timeout'



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
