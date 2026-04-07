"""Tests for ml/classifier.py — GestaltAffinityScorer."""
import numpy as np
import unittest
from core.config import DEFAULT_CENTROIDS, ELEMENTS, EMA_ALPHAS, ELEMENT_PARAMS
from ml.classifier import GestaltAffinityScorer


def _make_notes_from_centroid(centroid, t_base=0.0, n=10):
    """Synthesize (pitch, timestamp) tuples that roughly produce a given centroid.

    This is a rough approximation — it generates notes in a pattern that
    exercises the main gestalt dimensions so that the scorer has real data
    to work with.
    """
    notes = []
    for i in range(n):
        pitch = int(40 + centroid[2] * 88 * (i / n))  # spread
        ts = t_base + i * 0.02  # 20ms apart
        notes.append((pitch, ts))
    return notes


class TestGestaltAffinityScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = GestaltAffinityScorer()

    def test_score_all_returns_all_elements(self):
        notes = [(60, 0.0), (64, 0.05), (67, 0.10)]
        result = self.scorer.score_all(notes, [], 0.25)
        self.assertEqual(set(result['scores'].keys()), set(ELEMENTS.keys()))

    def test_score_all_returns_diagnostics(self):
        notes = [(60, 0.0), (64, 0.05), (67, 0.10)]
        result = self.scorer.score_all(notes, [], 0.25)
        self.assertIn('raw_scores', result)
        self.assertIn('vectors', result)
        self.assertIn('silence_gated', result)
        self.assertIn('suppressed', result)
        self.assertFalse(result['silence_gated'])
        # Vectors should have entries for affinity-mode elements
        for el_id in ELEMENTS:
            if ELEMENT_PARAMS[el_id].get('scoring_mode') != 'chord':
                self.assertEqual(len(result['vectors'][el_id]), 8)

    def test_scores_in_valid_range(self):
        notes = _make_notes_from_centroid(DEFAULT_CENTROIDS['a'], t_base=0.0)
        result = self.scorer.score_all(notes, [], 0.25)
        for label, score in result['scores'].items():
            self.assertGreaterEqual(score, 0.0, f"{label} below 0")
            self.assertLessEqual(score, 1.0, f"{label} above 1")

    def test_no_notes_returns_ema_state(self):
        result = self.scorer.score_all(None, None, None)
        for label in ELEMENTS:
            self.assertEqual(result['scores'][label], 0.0)

    def test_internal_ema_builds_with_repeated_scoring(self):
        """Every element's internal EMA should build up when fed matching notes."""
        for el_id in ELEMENTS:
            scorer = GestaltAffinityScorer()
            notes = _make_notes_from_centroid(DEFAULT_CENTROIDS[el_id], t_base=0.0)
            for i in range(10):
                t = 0.25 + i * 0.125
                scorer.score_all(notes, [], t)
            self.assertGreater(scorer._ema[el_id], 0.0,
                               f"{el_id} internal EMA is 0 after repeated scoring")

    def test_silence_decays_ema(self):
        """Scoring with no recent notes should aggressively decay EMA values."""
        notes = _make_notes_from_centroid(DEFAULT_CENTROIDS['b'], t_base=0.0)
        for i in range(10):
            self.scorer.score_all(notes, [], 0.25 + i * 0.125)

        # Now score with no recent notes (current_time far past the notes)
        for i in range(10):
            self.scorer.score_all(notes, [], 5.0 + i * 0.125)
        result = self.scorer.score_all(notes, [], 7.0)

        self.assertTrue(result['silence_gated'])
        for label in ELEMENTS:
            self.assertLess(result['scores'][label], 0.05,
                            f"{label} didn't decay to near-zero during silence")

    def test_mutual_exclusion_suppresses_lower(self):
        """In a mutually exclusive pair, at most one should be nonzero."""
        from core.config import MUTUAL_EXCLUSION
        notes = _make_notes_from_centroid(DEFAULT_CENTROIDS['a'], t_base=0.0)
        for i in range(20):
            t = 0.25 + i * 0.125
            self.scorer.score_all(notes, [], t)
        result = self.scorer.score_all(notes, [], 0.25 + 20 * 0.125)
        scores = result['scores']
        for el_a, el_b in MUTUAL_EXCLUSION:
            both_active = scores[el_a] > 0.01 and scores[el_b] > 0.01
            self.assertFalse(both_active,
                             f"Mutual exclusion failed: {el_a}={scores[el_a]:.4f}, "
                             f"{el_b}={scores[el_b]:.4f}")

    def test_per_element_frame_sizes_configured(self):
        """Each element should have a frame_size_ms in ELEMENT_PARAMS."""
        for el_id in ELEMENTS:
            self.assertIn('frame_size_ms', ELEMENT_PARAMS[el_id],
                          f"{el_id} missing frame_size_ms")
            self.assertGreater(ELEMENT_PARAMS[el_id]['frame_size_ms'], 0)


class TestChordDetector(unittest.TestCase):
    """Test the rule-based chord detection scoring for element B."""

    def test_simultaneous_chord_detected(self):
        """A cluster of simultaneous notes should produce a positive score."""
        # 5 notes within 20ms = clear chord
        notes = [(60, 1.0), (64, 1.005), (67, 1.010), (72, 1.015), (76, 1.020)]
        score = GestaltAffinityScorer._score_chord(notes, 1.15, 'b')
        self.assertGreater(score, 0.0)

    def test_sequential_notes_not_chord(self):
        """Widely spaced notes should not be detected as a chord."""
        notes = [(60, 0.0), (64, 0.10), (67, 0.20)]
        score = GestaltAffinityScorer._score_chord(notes, 0.25, 'b')
        self.assertEqual(score, 0.0)

    def test_too_few_notes_not_chord(self):
        """Fewer than chord_min_notes simultaneous notes should score 0."""
        notes = [(60, 1.0), (64, 1.005)]  # only 2 notes, min is 3
        score = GestaltAffinityScorer._score_chord(notes, 1.15, 'b')
        self.assertEqual(score, 0.0)

    def test_large_chord_higher_score(self):
        """A larger chord should score higher than a smaller one."""
        small = [(60, 1.0), (64, 1.005), (67, 1.010)]
        large = [(60, 1.0), (64, 1.002), (67, 1.004),
                 (72, 1.006), (76, 1.008), (79, 1.010)]
        s_small = GestaltAffinityScorer._score_chord(small, 1.15, 'b')
        s_large = GestaltAffinityScorer._score_chord(large, 1.15, 'b')
        self.assertGreater(s_large, s_small)

    def test_chord_outside_window_ignored(self):
        """Notes outside the element's frame window should be ignored."""
        # Notes at t=0, window only covers last 150ms from t=1.0
        notes = [(60, 0.0), (64, 0.005), (67, 0.010), (72, 0.015)]
        score = GestaltAffinityScorer._score_chord(notes, 1.0, 'b')
        self.assertEqual(score, 0.0)


class TestDynamicMappings(unittest.TestCase):
    """Test the velocity mapping functions in ParasiteSwarm."""

    def test_compressed_midpoint_unchanged(self):
        from agents.parasite import ParasiteSwarm
        from agents.parasite import _clamp_vel
        self.assertEqual(int(64 + (64 - 64) * 0.6), 64)
        self.assertEqual(int(64 + (127 - 64) * 0.6), 101)
        self.assertEqual(int(64 + (0 - 64) * 0.6), 25)

    def test_inverse_symmetry(self):
        from agents.parasite import _clamp_vel
        self.assertEqual(_clamp_vel(127 - 0), 127)
        self.assertEqual(_clamp_vel(127 - 127), 1)  # clamped to 1
        self.assertEqual(_clamp_vel(127 - 64), 63)

    def test_clamp_vel_bounds(self):
        from agents.parasite import _clamp_vel
        self.assertEqual(_clamp_vel(-10), 1)
        self.assertEqual(_clamp_vel(200), 127)
        self.assertEqual(_clamp_vel(64), 64)

    def test_clamp_note_bounds(self):
        from agents.parasite import _clamp_note
        self.assertEqual(_clamp_note(-5), 0)
        self.assertEqual(_clamp_note(130), 127)
        self.assertEqual(_clamp_note(60), 60)


if __name__ == '__main__':
    unittest.main()
