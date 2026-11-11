"""Source-shaped synthetic provider metadata; no account or media requests."""
import copy
import json
import unittest
from test_movie_torrentio import t, ROOT, MANIFEST
from test_movie_autoplay import load_policy


def source_payload(title, index=0, **hints):
    payload = json.loads((ROOT / 'tests/fixtures/torrentio_rd_undefined.json').read_text())
    entry = payload['streams'][0]
    entry['name'] = '[RD+] Torrentio\n1080p'
    entry['title'] = title
    entry['url'] = entry['url'].rsplit('/', 1)[0] + '/' + str(index)
    entry['behaviorHints'] = hints
    return entry


def parse(*entries):
    return t.parse_streams({'streams': list(entries)}, t.Config(MANIFEST))


class SuitabilityTests(unittest.TestCase):
    def test_release_extras_are_excluded_but_title_words_and_missing_duration_survive(self):
        for modifier in ('Trailer', 'Teaser', 'Sample', 'Clip', 'Behind.the.scenes'):
            with self.subTest(modifier=modifier):
                extra = parse(source_payload('Example.1998.' + modifier + '.1080p.H264.mkv'))[0]
                self.assertEqual(load_policy().rank_sources([extra]), [])
        for title in ('Trailer Park Boys.2014.1080p.H264.mkv',
                      'The Last Movie Trailer.2020.1080p.mkv',
                      'Sample People.2000.720p.mkv', 'Clip.2012.mkv',
                      'Trailer Park Boys', 'Mystery.1080p.H264.mkv'):
            with self.subTest(title=title):
                feature = parse(source_payload(title))[0]
                self.assertEqual(load_policy().rank_sources([feature]), [feature])
                self.assertEqual(feature.suitability, 'unknown')

    def test_explicit_feature_hint_ranks_before_technical_preferences(self):
        entries = parse(source_payload('Mystery.1998.1080p.H264.English.mkv', 0),
                        source_payload('Mystery.1998.Full.Movie.720p.HEVC.mkv', 1))
        self.assertEqual(entries[1].suitability, 'feature')
        self.assertEqual(load_policy().rank_sources(entries), [entries[1], entries[0]])

    def test_both_filename_and_title_flags_survive_without_retaining_secrets(self):
        entry = source_payload('Example.1998.Official.Trailer.1080p.H264',
                               filename='Example.1998.1080p.H264.mkv')
        candidate = parse(entry)[0]
        self.assertEqual(candidate.suitability, 'extra')
        for unsafe in ('https://example.invalid/secret/Example.1998.Trailer.mkv',
                       'https%3A%2F%2Fexample.invalid%2Fsecret',
                       '[B]secret[/B]', 'token=private-secret', 'a' * 70):
            with self.subTest(unsafe=unsafe):
                candidate = parse(source_payload(unsafe, filename=unsafe))[0]
                self.assertEqual(candidate.hint, '')
                self.assertNotIn('secret', candidate.label)
                self.assertNotIn(unsafe, candidate.label)
        candidate = parse(source_payload('Example.1998.' + 'Word.' * 1000))[0]
        self.assertLessEqual(len(candidate.hint), 100)
        self.assertLessEqual(len(candidate.label), 280)

    def test_explicit_no_year_trailer_and_long_release_suffix_are_rejected(self):
        for title in ('The Big Lebowski - Official Trailer 1080p H264',
                      'Example.1998.' + 'Release.' * 20 + 'Sample.1080p.mkv'):
            with self.subTest(title=title):
                entries = parse(source_payload(title))
                self.assertEqual(load_policy().rank_sources(entries), [])

    def test_trailer_is_not_an_auto_candidate_even_with_preferred_technical_fields(self):
        # Same schema as the committed upstream-derived undefined-index fixture.
        entries = parse(
            source_payload('The.Big.Lebowski.1998.Official.Trailer.1080p.H264.English', 0),
            source_payload('The.Big.Lebowski.1998.720p.HEVC.English.mkv', 1))
        ranked = load_policy().rank_sources(entries)
        self.assertEqual([s.id for s in ranked], [entries[1].id])
        self.assertIn('The.Big.Lebowski', entries[0].label)
        self.assertIn('trailer', entries[0].label.lower())


if __name__ == '__main__':
    unittest.main()
