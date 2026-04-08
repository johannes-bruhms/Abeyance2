"""Tests for midi/playback.py — PlaybackEngine."""
import threading
import time
import unittest


class MockMidiIO:
    """Records send_note_on / send_note_off calls for assertion."""
    def __init__(self):
        self.on_calls = []   # list of (note, velocity)
        self.off_calls = []  # list of (note,)
        self.lock = threading.Lock()

    def send_note_on(self, note, velocity):
        with self.lock:
            self.on_calls.append((note, velocity))

    def send_note_off(self, note):
        with self.lock:
            self.off_calls.append((note,))


from midi.playback import PlaybackEngine


class TestPlaybackEngine(unittest.TestCase):

    def setUp(self):
        self.midi = MockMidiIO()
        self.engine = PlaybackEngine(self.midi)

    def tearDown(self):
        self.engine.cancel_all()

    # ---- basic scheduling ----

    def test_schedule_note_sends_on_and_off(self):
        """A scheduled note should produce a note_on then note_off."""
        self.engine.schedule_note(60, 80, duration_sec=0.05)
        time.sleep(0.15)
        with self.midi.lock:
            self.assertEqual(len(self.midi.on_calls), 1)
            self.assertEqual(self.midi.on_calls[0], (60, 80))
            self.assertEqual(len(self.midi.off_calls), 1)
            self.assertEqual(self.midi.off_calls[0], (60,))

    def test_delayed_note(self):
        """A note with delay_sec should not sound immediately."""
        self.engine.schedule_note(60, 80, duration_sec=0.05, delay_sec=0.1)
        time.sleep(0.05)
        with self.midi.lock:
            self.assertEqual(len(self.midi.on_calls), 0)
        time.sleep(0.2)
        with self.midi.lock:
            self.assertEqual(len(self.midi.on_calls), 1)

    # ---- velocity clamping (H3 fix) ----

    def test_velocity_clamped_min_1(self):
        """Velocity 0 should be clamped to 1 to avoid note_off semantics."""
        self.engine.schedule_note(60, 0, duration_sec=0.05)
        time.sleep(0.1)
        with self.midi.lock:
            self.assertEqual(self.midi.on_calls[0][1], 1)

    def test_velocity_clamped_max_127(self):
        """Velocity >127 should be clamped to 127."""
        self.engine.schedule_note(60, 200, duration_sec=0.05)
        time.sleep(0.1)
        with self.midi.lock:
            self.assertEqual(self.midi.on_calls[0][1], 127)

    def test_note_clamped_to_range(self):
        """Notes outside 0-127 should be clamped."""
        self.engine.schedule_note(-5, 80, duration_sec=0.05)
        self.engine.schedule_note(200, 80, duration_sec=0.05)
        time.sleep(0.15)
        with self.midi.lock:
            notes = [c[0] for c in self.midi.on_calls]
            self.assertIn(0, notes)
            self.assertIn(127, notes)

    # ---- cancel_all (C1 fix) ----

    def test_cancel_all_stops_pending_notes(self):
        """cancel_all should prevent delayed notes from sounding."""
        self.engine.schedule_note(60, 80, duration_sec=0.5, delay_sec=0.2)
        time.sleep(0.05)
        self.engine.cancel_all()
        time.sleep(0.4)
        with self.midi.lock:
            self.assertEqual(len(self.midi.on_calls), 0)

    def test_cancel_all_sends_off_for_sounding_notes(self):
        """cancel_all should send note_off for notes that are currently sounding."""
        self.engine.schedule_note(60, 80, duration_sec=5.0)  # very long note
        time.sleep(0.1)  # let note_on fire
        with self.midi.lock:
            self.assertEqual(len(self.midi.on_calls), 1)
        self.engine.cancel_all()
        time.sleep(0.05)
        with self.midi.lock:
            # Should have gotten a note_off from cancel_all
            self.assertGreaterEqual(len(self.midi.off_calls), 1)
            self.assertEqual(self.midi.off_calls[0], (60,))

    # ---- on_note_scheduled callback ----

    def test_on_note_scheduled_callback_fired(self):
        """The on_note_scheduled callback should fire with correct args."""
        calls = []
        self.engine.on_note_scheduled.append(
            lambda n, v, d, dl: calls.append((n, v, d, dl)))
        self.engine.schedule_note(60, 80, duration_sec=0.5, delay_sec=0.1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], (60, 80, 0.5, 0.1))


if __name__ == '__main__':
    unittest.main()
