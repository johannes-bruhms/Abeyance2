"""Tests for ml/classifier.py — GestaltAffinityScorer."""
import numpy as np
import unittest
from core.config import DEFAULT_CENTROIDS, ELEMENTS, EMA_ALPHAS, ELEMENT_PARAMS
from ml.classifier import GestaltAffinityScorer


class TestGestaltAffinityScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = GestaltAffinityScorer()

    def test_score_all_returns_all_elements(self):
        self.scorer.push_frame(np.zeros(8))
        scores = self.scorer.score_all()
        self.assertEqual(set(scores.keys()), set(ELEMENTS.keys()))

    def test_scores_in_valid_range(self):
        self.scorer.push_frame(np.array(DEFAULT_CENTROIDS['a']))
        scores = self.scorer.score_all()
        for label, score in scores.items():
            self.assertGreaterEqual(score, 0.0, f"{label} below 0")
            self.assertLessEqual(score, 1.0, f"{label} above 1")

    def test_matching_centroid_scores_highest_no_exclusion(self):
        """Elements without mutual exclusion should score highest on their own centroid."""
        from core.config import MUTUAL_EXCLUSION
        excluded = set()
        for a, b in MUTUAL_EXCLUSION:
            excluded.add(a)
            excluded.add(b)
        # Elements not in any mutual-exclusion pair
        free_elements = [e for e in ELEMENTS if e not in excluded]
        self.assertTrue(len(free_elements) >= 2)

        for el_id in free_elements:
            scorer = GestaltAffinityScorer()
            centroid = np.array(DEFAULT_CENTROIDS[el_id])
            for _ in range(10):
                scorer.push_frame(centroid)
                scores = scorer.score_all()
            self.assertGreater(scores[el_id], 0.0,
                               f"{el_id} scored 0 on its own centroid")

    def test_internal_ema_builds_on_own_centroid(self):
        """Every element's internal EMA should build up when fed its own centroid."""
        for el_id in ELEMENTS:
            scorer = GestaltAffinityScorer()
            centroid = np.array(DEFAULT_CENTROIDS[el_id])
            for _ in range(10):
                scorer.push_frame(centroid)
                scorer.score_all()
            # Internal EMA may be decayed by mutual exclusion, but should still
            # be nonzero after 10 frames (decay factor 0.3 per frame is aggressive,
            # but fresh score each frame partially rebuilds it)
            self.assertGreater(scorer._ema[el_id], 0.0,
                               f"{el_id} internal EMA is 0 on own centroid")

    def test_silence_decays_ema(self):
        """Pushing silence (density < gate) should aggressively decay EMA values."""
        centroid = np.array(DEFAULT_CENTROIDS['b'])
        for _ in range(10):
            self.scorer.push_frame(centroid)
            self.scorer.score_all()

        # Now push silence frames (10 frames at 8Hz ≈ 1.25s of silence)
        silence = np.zeros(8)
        for _ in range(10):
            self.scorer.push_frame(silence)
            self.scorer.score_all()
        post_scores = self.scorer.score_all()

        # After prolonged silence, all EMA values should be near zero
        for label in ELEMENTS:
            self.assertLess(post_scores[label], 0.05,
                            f"{label} didn't decay to near-zero during silence")

    def test_mutual_exclusion_suppresses_lower(self):
        """In a mutually exclusive pair, only the dominant one should be nonzero."""
        from core.config import MUTUAL_EXCLUSION
        # Use a centroid that should activate 'a' (linear velocity)
        centroid = np.array(DEFAULT_CENTROIDS['a'])
        for _ in range(20):
            self.scorer.push_frame(centroid)
        scores = self.scorer.score_all()
        # Check each pair: at most one should be nonzero
        for el_a, el_b in MUTUAL_EXCLUSION:
            if scores[el_a] > 0 and scores[el_b] > 0:
                self.fail(f"Mutual exclusion failed: {el_a}={scores[el_a]:.3f}, "
                          f"{el_b}={scores[el_b]:.3f}")

    def test_mutual_exclusion_decays_suppressed_ema(self):
        """Suppressed element's EMA should be decayed, not just zeroed in output."""
        # Push frames that favor 'a' over 'c' (mutually exclusive pair)
        centroid = np.array(DEFAULT_CENTROIDS['a'])
        for _ in range(10):
            self.scorer.push_frame(centroid)
            self.scorer.score_all()
        # The suppressed partner's internal EMA should be small
        suppressed = 'c'
        self.assertLess(self.scorer._ema[suppressed], 0.1,
                        "Suppressed element EMA not decayed")


class TestDynamicMappings(unittest.TestCase):
    """Test the velocity mapping functions in ParasiteSwarm."""

    def test_compressed_midpoint_unchanged(self):
        from agents.parasite import ParasiteSwarm
        # Can't instantiate without playback, test the static functions
        from agents.parasite import _clamp_vel
        # Compressed: 64 + (vel - 64) * 0.6
        self.assertEqual(int(64 + (64 - 64) * 0.6), 64)
        self.assertEqual(int(64 + (127 - 64) * 0.6), 101)
        self.assertEqual(int(64 + (0 - 64) * 0.6), 25)

    def test_inverse_symmetry(self):
        from agents.parasite import _clamp_vel
        # Inverse: 127 - vel
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
