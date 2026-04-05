"""Tests for core/gestalt.py — extract_micro_gestalt()."""
import numpy as np
import unittest
from core.gestalt import extract_micro_gestalt


class TestExtractMicroGestalt(unittest.TestCase):

    def test_empty_input_returns_zeros(self):
        result = extract_micro_gestalt([], [])
        np.testing.assert_array_equal(result, np.zeros(8))

    def test_single_note_only_density_and_articulation(self):
        result = extract_micro_gestalt([(60, 0.0)], [0.5])
        self.assertAlmostEqual(result[0], 1 / 25.0)  # density = 1/25
        self.assertEqual(result[1], 0.0)  # polyphony
        self.assertEqual(result[2], 0.0)  # spread
        self.assertEqual(result[3], 0.0)  # variance
        self.assertEqual(result[4], 0.0)  # up_vel
        self.assertEqual(result[5], 0.0)  # down_vel
        self.assertAlmostEqual(result[6], 0.25)  # articulation = 0.5/2.0
        self.assertEqual(result[7], 0.0)  # bimodality

    def test_ascending_run_has_up_velocity(self):
        # C4 D4 E4 F4 in sequence
        notes = [(60, 0.0), (62, 0.05), (64, 0.10), (65, 0.15)]
        result = extract_micro_gestalt(notes, [])
        self.assertGreater(result[4], 0.0)  # up_vel > 0
        self.assertEqual(result[5], 0.0)    # down_vel = 0

    def test_descending_run_has_down_velocity(self):
        notes = [(72, 0.0), (70, 0.05), (68, 0.10), (66, 0.15)]
        result = extract_micro_gestalt(notes, [])
        self.assertEqual(result[4], 0.0)    # up_vel = 0
        self.assertGreater(result[5], 0.0)  # down_vel > 0

    def test_simultaneous_chord_high_polyphony(self):
        # All notes within 10ms = below 15ms threshold
        notes = [(60, 0.0), (64, 0.005), (67, 0.010)]
        result = extract_micro_gestalt(notes, [])
        self.assertEqual(result[1], 1.0)  # all pairs simultaneous

    def test_sequential_notes_low_polyphony(self):
        # Notes 100ms apart = well above 15ms threshold
        notes = [(60, 0.0), (64, 0.100), (67, 0.200)]
        result = extract_micro_gestalt(notes, [])
        self.assertEqual(result[1], 0.0)

    def test_extreme_registers_high_bimodality(self):
        # Low cluster + high cluster with big gap in the middle
        notes = [(21, 0.0), (23, 0.01), (24, 0.02),
                 (100, 0.05), (103, 0.06), (105, 0.07)]
        result = extract_micro_gestalt(notes, [])
        self.assertGreater(result[7], 0.7)  # high bimodality

    def test_clustered_notes_low_bimodality(self):
        # All notes within a few semitones
        notes = [(60, 0.0), (61, 0.01), (62, 0.02), (63, 0.03)]
        result = extract_micro_gestalt(notes, [])
        self.assertLess(result[7], 0.5)

    def test_all_dimensions_normalized_0_to_1(self):
        # Dense wide-range input
        notes = [(21 + i * 3, i * 0.01) for i in range(25)]
        result = extract_micro_gestalt(notes, [1.0, 0.5, 2.0])
        for i, val in enumerate(result):
            self.assertGreaterEqual(val, 0.0, f"dim {i} below 0")
            self.assertLessEqual(val, 1.0, f"dim {i} above 1")

    def test_no_durations_means_zero_articulation(self):
        notes = [(60, 0.0), (64, 0.05)]
        result = extract_micro_gestalt(notes, [])
        self.assertEqual(result[6], 0.0)

    def test_long_durations_clamp_articulation(self):
        notes = [(60, 0.0), (64, 0.05)]
        result = extract_micro_gestalt(notes, [5.0, 10.0])
        self.assertEqual(result[6], 1.0)  # clamped at 1.0


if __name__ == '__main__':
    unittest.main()
