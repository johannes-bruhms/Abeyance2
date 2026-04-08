"""Tests for midi/io.py — GhostNoteFilter."""
import time
import unittest
from unittest.mock import MagicMock


class FakeMsg:
    """Minimal stand-in for a mido Message."""
    def __init__(self, type, note=None, velocity=None):
        self.type = type
        self.note = note
        self.velocity = velocity


from midi.io import GhostNoteFilter


class TestGhostNoteFilter(unittest.TestCase):

    def setUp(self):
        self.gf = GhostNoteFilter(echo_ttl=2.0)

    # ---- basic suppression ----

    def test_human_note_passes_through(self):
        """A note with no registered AI note should pass through."""
        msg = FakeMsg('note_on', note=60, velocity=80)
        self.assertIsNotNone(self.gf.filter_incoming(msg))

    def test_registered_note_on_suppressed(self):
        """A note_on echo for a registered AI note should be suppressed."""
        self.gf.register_ai_note(60)
        msg = FakeMsg('note_on', note=60, velocity=80)
        self.assertIsNone(self.gf.filter_incoming(msg))

    def test_registered_note_off_suppressed(self):
        """A note_off echo for a registered AI note should be suppressed."""
        self.gf.register_ai_note(60)
        # Consume note_on first
        self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=80))
        # Now note_off
        msg = FakeMsg('note_off', note=60, velocity=0)
        self.assertIsNone(self.gf.filter_incoming(msg))

    def test_after_full_echo_human_passes(self):
        """After both note_on and note_off echoes are consumed, human notes pass."""
        self.gf.register_ai_note(60)
        self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=80))
        self.gf.filter_incoming(FakeMsg('note_off', note=60, velocity=0))
        # Now a human plays the same pitch
        msg = FakeMsg('note_on', note=60, velocity=90)
        self.assertIsNotNone(self.gf.filter_incoming(msg))

    def test_different_pitch_not_suppressed(self):
        """Registering note 60 should not suppress note 64."""
        self.gf.register_ai_note(60)
        msg = FakeMsg('note_on', note=64, velocity=80)
        self.assertIsNotNone(self.gf.filter_incoming(msg))

    # ---- overlapping same-pitch (C2 fix) ----

    def test_overlapping_same_pitch_both_suppressed(self):
        """Two AI notes on the same pitch: both echoes should be suppressed."""
        self.gf.register_ai_note(60)
        self.gf.register_ai_note(60)

        # First echo pair
        self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=80)))
        self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_off', note=60, velocity=0)))

        # Second echo pair
        self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=70)))
        self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_off', note=60, velocity=0)))

        # Now human note passes
        self.assertIsNotNone(self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=90)))

    def test_three_overlapping_notes(self):
        """Three AI notes on the same pitch (e.g. fast trill re-attacks)."""
        for _ in range(3):
            self.gf.register_ai_note(60)

        for _ in range(3):
            self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=80)))
            self.assertIsNone(self.gf.filter_incoming(FakeMsg('note_off', note=60, velocity=0)))

        # Human note passes after all echoes consumed
        self.assertIsNotNone(self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=90)))

    # ---- TTL expiry ----

    def test_expired_entry_passes_through(self):
        """After TTL expires, the echo entry is pruned and notes pass through."""
        self.gf = GhostNoteFilter(echo_ttl=0.01)  # very short TTL
        self.gf.register_ai_note(60)
        time.sleep(0.02)  # let it expire
        msg = FakeMsg('note_on', note=60, velocity=80)
        self.assertIsNotNone(self.gf.filter_incoming(msg))

    # ---- note_on with velocity 0 = note_off ----

    def test_note_on_velocity_zero_treated_as_off(self):
        """note_on with velocity=0 should be treated as note_off (MIDI convention)."""
        self.gf.register_ai_note(60)
        self.gf.filter_incoming(FakeMsg('note_on', note=60, velocity=80))
        # note_on vel=0 is note_off
        msg = FakeMsg('note_on', note=60, velocity=0)
        self.assertIsNone(self.gf.filter_incoming(msg))

    # ---- non-note messages pass through ----

    def test_control_change_passes_through(self):
        """Non-note messages should always pass through."""
        msg = FakeMsg('control_change')
        msg.note = None
        self.assertIsNotNone(self.gf.filter_incoming(msg))


if __name__ == '__main__':
    unittest.main()
