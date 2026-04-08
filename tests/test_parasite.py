"""Tests for agents/parasite.py — ParasiteSwarm attack handlers."""
import threading
import time
import unittest
from collections import deque
from core.config import ELEMENTS, ELEMENT_PARAMS


class MockPlaybackEngine:
    """Records scheduled notes for assertion."""
    def __init__(self):
        self.notes = []  # list of (note, velocity, duration, delay)
        self.on_note_scheduled = []

    def schedule_note(self, note, velocity, duration_sec, delay_sec=0.0):
        self.notes.append((note, velocity, duration_sec, delay_sec))


from agents.parasite import ParasiteSwarm, _clamp_vel, _clamp_note


class TestParasiteSwarm(unittest.TestCase):

    def setUp(self):
        self.playback = MockPlaybackEngine()
        self.swarm = ParasiteSwarm(ELEMENTS, self.playback)
        # Stop the background loop so tests are deterministic
        self.swarm.running = False
        time.sleep(0.15)  # let loop exit

    def tearDown(self):
        self.swarm.running = False

    # ---- energy mechanics ----

    def test_feed_increases_energy(self):
        """Feeding an agent should increase its energy."""
        e_before = self.swarm.agents['a']['energy']
        self.swarm.feed('a', [(60, 80)], weight=1.0)
        self.assertGreater(self.swarm.agents['a']['energy'], e_before)

    def test_feed_respects_weight(self):
        """Weight=0.5 should boost half as much as weight=1.0."""
        self.swarm.agents['a']['energy'] = 0.0
        self.swarm.feed('a', [(60, 80)], weight=0.5)
        e_half = self.swarm.agents['a']['energy']
        self.swarm.agents['a']['energy'] = 0.0
        self.swarm.feed('a', [(60, 80)], weight=1.0)
        e_full = self.swarm.agents['a']['energy']
        self.assertAlmostEqual(e_half * 2, e_full, places=5)

    def test_energy_capped_at_1(self):
        """Energy should not exceed 1.0."""
        for _ in range(50):
            self.swarm.feed('a', [(60, 80)], weight=1.0)
        self.assertLessEqual(self.swarm.agents['a']['energy'], 1.0)

    def test_feed_invalid_label_ignored(self):
        """Feeding an unknown label should not crash."""
        self.swarm.feed('z', [(60, 80)])
        self.swarm.feed(None, [(60, 80)])
        self.swarm.feed('', [(60, 80)])

    # ---- energy drain + clamping (M2 fix) ----

    def test_energy_never_negative_after_attack(self):
        """Energy should be clamped to 0.0 after attack drain."""
        agent = self.swarm.agents['a']
        agent['energy'] = 0.65  # just above trigger
        agent['stomach'] = deque([(60, 80), (62, 80), (64, 80), (66, 80)])
        event = self.swarm._attack_a(agent, 'a')
        self.assertIsNotNone(event)
        self.assertGreaterEqual(agent['energy'], 0.0)

    def test_energy_drain_from_element_params(self):
        """Attack should use energy_drain from ELEMENT_PARAMS."""
        agent = self.swarm.agents['b']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (64, 80), (67, 80)])
        drain = ELEMENT_PARAMS['b'].get('energy_drain', 0.4)
        self.swarm._attack_b(agent, 'b')
        self.assertAlmostEqual(agent['energy'], 1.0 - drain, places=5)

    # ---- pedal transposition (C5 fix) ----

    def test_pedal_transpose_off(self):
        """With pedal up, output pitch should not be transposed."""
        self.swarm.sustain_pedal_down = False
        self.assertEqual(self.swarm._pedal_transpose(60), 60)

    def test_pedal_transpose_on(self):
        """With pedal down, output pitch should be +12."""
        self.swarm.sustain_pedal_down = True
        self.assertEqual(self.swarm._pedal_transpose(60), 72)

    def test_pedal_transpose_clamped(self):
        """Transposition should not exceed MIDI range."""
        self.swarm.sustain_pedal_down = True
        self.assertEqual(self.swarm._pedal_transpose(120), 127)

    def test_attack_a_uses_pedal_transpose(self):
        """Attack A output should shift +12 when pedal is held."""
        agent = self.swarm.agents['a']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (62, 80), (64, 80), (66, 80)])

        self.swarm.sustain_pedal_down = False
        self.swarm._attack_a(agent, 'a')
        notes_no_pedal = [n[0] for n in self.playback.notes]

        self.playback.notes.clear()
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (62, 80), (64, 80), (66, 80)])

        self.swarm.sustain_pedal_down = True
        self.swarm._attack_a(agent, 'a')
        notes_pedal = [n[0] for n in self.playback.notes]

        for np_, p_ in zip(notes_no_pedal, notes_pedal):
            self.assertEqual(min(127, np_ + 12), p_)

    # ---- attack handlers produce output ----

    def test_attack_a_produces_notes(self):
        agent = self.swarm.agents['a']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (62, 80), (64, 80), (66, 80)])
        event = self.swarm._attack_a(agent, 'a')
        self.assertIsNotNone(event)
        self.assertEqual(event['element'], 'a')
        self.assertEqual(event['mapping'], 'compressed')
        self.assertGreater(len(self.playback.notes), 0)

    def test_attack_b_produces_notes(self):
        agent = self.swarm.agents['b']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (64, 80), (67, 80)])
        event = self.swarm._attack_b(agent, 'b')
        self.assertIsNotNone(event)
        self.assertEqual(event['mapping'], 'inverse')

    def test_attack_c_produces_notes(self):
        agent = self.swarm.agents['c']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (72, 80)])
        event = self.swarm._attack_c(agent, 'c')
        self.assertIsNotNone(event)
        # Tritone shift: output should be +6 from input
        out_notes = [n[0] for n in self.playback.notes]
        self.assertTrue(all(n == _clamp_note(p + 6)
                            for n, (p, _) in zip(out_notes, [(60, 80), (72, 80)])))

    def test_attack_d_produces_notes(self):
        agent = self.swarm.agents['d']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (72, 80)] * 4)
        event = self.swarm._attack_d(agent, 'd')
        self.assertIsNotNone(event)
        self.assertEqual(event['mapping'], 'expanded')
        self.assertEqual(len(self.playback.notes), 6)

    def test_attack_e_fills_middle(self):
        agent = self.swarm.agents['e']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(24, 80), (96, 80)] * 3)
        event = self.swarm._attack_e(agent, 'e')
        self.assertIsNotNone(event)
        out_notes = [n[0] for n in self.playback.notes]
        # Fill notes should be in the middle range
        for n in out_notes:
            self.assertGreater(n, 24)
            self.assertLess(n, 96)

    # ---- attack with insufficient data returns None ----

    def test_attack_a_needs_2_notes(self):
        agent = self.swarm.agents['a']
        agent['stomach'] = deque([(60, 80)])
        self.assertIsNone(self.swarm._attack_a(agent, 'a'))

    def test_attack_b_needs_notes(self):
        agent = self.swarm.agents['b']
        agent['stomach'] = deque()
        self.assertIsNone(self.swarm._attack_b(agent, 'b'))

    def test_attack_d_needs_2_notes(self):
        agent = self.swarm.agents['d']
        agent['stomach'] = deque([(60, 80)])
        self.assertIsNone(self.swarm._attack_d(agent, 'd'))

    # ---- emit outside lock (C4 fix) ----

    def test_emit_attack_called_outside_lock(self):
        """Verify that _emit_attack callbacks are not called while holding the lock."""
        lock_held_during_callback = []

        def check_lock(event):
            # Try to acquire the lock — if it's held, this would block/fail
            acquired = self.swarm.lock.acquire(blocking=False)
            lock_held_during_callback.append(not acquired)
            if acquired:
                self.swarm.lock.release()

        with self.swarm.lock:
            self.swarm.on_attack.append(check_lock)

        # Manually drive one tick of the swarm loop logic
        agent = self.swarm.agents['a']
        agent['energy'] = 1.0
        agent['stomach'] = deque([(60, 80), (62, 80), (64, 80), (66, 80)])

        pending_events = []
        with self.swarm.lock:
            event = self.swarm._trigger_attack('a', agent)
            if event:
                pending_events.append(event)

        for event in pending_events:
            self.swarm._emit_attack(event)

        self.assertTrue(len(lock_held_during_callback) > 0)
        self.assertFalse(lock_held_during_callback[0],
                         "Callback was invoked while swarm lock was held")

    # ---- dynamic mappings ----

    def test_compressed_at_midpoint(self):
        self.assertEqual(self.swarm._map_vel_compressed(64), 64)

    def test_inverse_symmetry(self):
        self.assertEqual(self.swarm._map_vel_inverse(0), 127)
        self.assertEqual(self.swarm._map_vel_inverse(127), 1)  # clamped to 1

    def test_expanded_extremes(self):
        low = self.swarm._map_vel_expanded(30)
        high = self.swarm._map_vel_expanded(100)
        self.assertLess(low, 30)
        self.assertGreater(high, 100)


if __name__ == '__main__':
    unittest.main()
