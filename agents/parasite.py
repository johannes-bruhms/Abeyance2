# agents/parasite.py
import time
import threading
from collections import deque
from core.config import CONFIG, ELEMENT_PARAMS


def _clamp_vel(v):
    return max(1, min(127, int(v)))


def _clamp_note(n):
    return max(0, min(127, int(n)))


class ParasiteSwarm:
    def __init__(self, elements, playback_engine):
        self.playback = playback_engine
        self.agents = {}
        self.lock = threading.Lock()

        self.sustain_pedal_down = False

        for k in elements:
            self.agents[k] = {
                'energy': 0.1,
                'stomach': deque(maxlen=50),  # stores (pitch, velocity) tuples
            }

        self.running = True
        self.thread = threading.Thread(target=self._swarm_loop, daemon=True)
        self.thread.start()

    def set_pedal(self, is_down):
        """Direct sustain pedal state — not an element, just modulates octave transposition."""
        with self.lock:
            self.sustain_pedal_down = is_down

    def feed(self, label, note_vel_pairs, weight=1.0):
        """
        Energize one agent with (pitch, velocity) pairs.
        weight (0.0-1.0) scales the energy boost by detection confidence.
        """
        if not label or label not in self.agents:
            return
        with self.lock:
            boost_val = ELEMENT_PARAMS[label]['energy_boost']
            self.agents[label]['energy'] = min(
                1.0, self.agents[label]['energy'] + boost_val * weight)
            self.agents[label]['stomach'].extend(note_vel_pairs)

    def _swarm_loop(self):
        tick_sec = CONFIG['agent_tick_ms'] / 1000.0
        while self.running:
            time.sleep(tick_sec)

            with self.lock:
                for label, agent in self.agents.items():
                    agent['energy'] = max(
                        0.0, agent['energy'] - ELEMENT_PARAMS[label]['energy_decay'])

                    if agent['energy'] > CONFIG['energy_trigger'] and len(agent['stomach']) > 0:
                        self._trigger_attack(label, agent)

    # -------------------------------------------------------------- dynamic mappings

    def _map_vel_compressed(self, vel):
        """A — Compressed proportional: compress toward midpoint (64)."""
        return _clamp_vel(64 + (vel - 64) * 0.6)

    def _map_vel_inverse(self, vel):
        """B — Inverse: quiet input → loud response, loud input → quiet response."""
        return _clamp_vel(127 - vel)

    def _map_vel_direct(self, vel):
        """C — Direct proportional: 1:1 mirror."""
        return _clamp_vel(vel)

    def _map_vel_expanded(self, vel):
        """D — Expanded: quiet gets quieter, loud gets louder."""
        center = 64
        deviation = vel - center
        return _clamp_vel(center + deviation * 1.5)

    def _map_vel_escalating(self, vel):
        """E — Escalating: always respond slightly louder than input."""
        return _clamp_vel(vel + 20)

    def _map_vel_averaged(self, velocities):
        """F — Averaged: mean of all input velocities."""
        if not velocities:
            return 64
        return _clamp_vel(sum(velocities) / len(velocities))

    # -------------------------------------------------------------- attack behaviors

    def _trigger_attack(self, label, agent):
        dispatch = {
            'a': self._attack_a,
            'b': self._attack_b,
            'c': self._attack_c,
            'd': self._attack_d,
            'e': self._attack_e,
            'f': self._attack_f,
        }
        handler = dispatch.get(label)
        if handler:
            handler(agent)

    def _attack_a(self, agent):
        """Linear Velocity — Counter-motion: invert pitch direction, compressed dynamics."""
        recent = list(agent['stomach'])[-4:]
        if len(recent) < 2:
            return
        pitches = [p for p, v in recent]
        # Determine direction: ascending or descending
        direction = pitches[-1] - pitches[0]
        # Reverse the interval sequence in a neighboring register (+/- octave)
        offset = -12 if direction > 0 else 12
        for i, (pitch, vel) in enumerate(reversed(recent)):
            out_vel = self._map_vel_compressed(vel)
            out_note = _clamp_note(pitch + offset)
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=0.4,
                delay_sec=i * 0.1)
        agent['energy'] -= 0.3

    def _attack_b(self, agent):
        """Vertical Density — Sustained cluster resonance: quiet chord, slow build."""
        recent = list(agent['stomach'])[-6:]
        if not recent:
            return
        # Use unique pitches for the resonance chord
        seen = set()
        chord = []
        for pitch, vel in recent:
            if pitch not in seen:
                seen.add(pitch)
                chord.append((pitch, vel))
        if not chord:
            return
        # Inverse dynamics: quiet input → louder resonance, loud input → softer
        for pitch, vel in chord:
            out_vel = self._map_vel_inverse(vel)
            self.playback.schedule_note(
                _clamp_note(pitch), out_vel,
                duration_sec=2.5,
                delay_sec=0.05)
        agent['energy'] -= 0.4

    def _attack_c(self, agent):
        """Transposed Shapes — Tritone echo: replay shape transposed by 6 semitones."""
        recent = list(agent['stomach'])[-4:]
        if not recent:
            return
        tritone = 6
        for i, (pitch, vel) in enumerate(recent):
            out_vel = self._map_vel_direct(vel)
            out_note = _clamp_note(pitch + tritone)
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=0.3,
                delay_sec=i * 0.08)
        agent['energy'] -= 0.3

    def _attack_d(self, agent):
        """Oscillation — Phase-shifted trill: oscillate between boundary pitches at offset rate."""
        recent = list(agent['stomach'])[-8:]
        if len(recent) < 2:
            return
        pitches = [p for p, v in recent]
        velocities = [v for p, v in recent]
        lo, hi = min(pitches), max(pitches)
        mean_vel = sum(velocities) / len(velocities)
        # Generate a phase-shifted oscillation: 6 notes alternating, slightly slower
        for i in range(6):
            pitch = lo if i % 2 == 0 else hi
            out_vel = self._map_vel_expanded(mean_vel)
            self.playback.schedule_note(
                _clamp_note(pitch), out_vel,
                duration_sec=0.15,
                delay_sec=i * 0.12)  # slightly different rate than typical trill
        agent['energy'] -= 0.35

    def _attack_e(self, agent):
        """Sweeps — Reverse sweep: play detected range back in opposite direction, escalating."""
        recent = list(agent['stomach'])[-6:]
        if len(recent) < 2:
            return
        pitches = [p for p, v in recent]
        velocities = [v for p, v in recent]
        mean_vel = sum(velocities) / len(velocities)
        # Build a reversed chromatic sweep across the detected range
        lo, hi = min(pitches), max(pitches)
        direction = pitches[-1] - pitches[0]
        if direction >= 0:
            # Input was ascending → respond descending
            sweep_notes = list(range(hi, lo - 1, -3))  # chromatic thirds down
        else:
            # Input was descending → respond ascending
            sweep_notes = list(range(lo, hi + 1, 3))    # chromatic thirds up
        # Limit sweep length
        sweep_notes = sweep_notes[:8]
        for i, pitch in enumerate(sweep_notes):
            out_vel = self._map_vel_escalating(mean_vel)
            self.playback.schedule_note(
                _clamp_note(pitch), out_vel,
                duration_sec=0.12,
                delay_sec=i * 0.05)
        agent['energy'] -= 0.35

    def _attack_f(self, agent):
        """Extreme Registers — Fill the gap: respond in the middle register the performer avoids."""
        recent = list(agent['stomach'])[-6:]
        if not recent:
            return
        pitches = [p for p, v in recent]
        velocities = [v for p, v in recent]
        avg_vel = self._map_vel_averaged(velocities)
        # Find the midpoint of the performer's extreme pitches
        lo, hi = min(pitches), max(pitches)
        mid = (lo + hi) // 2
        # Play gentle notes around the center of the gap
        fill_notes = [mid - 2, mid, mid + 2, mid + 4]
        for i, pitch in enumerate(fill_notes):
            self.playback.schedule_note(
                _clamp_note(pitch), avg_vel,
                duration_sec=1.0,
                delay_sec=i * 0.2)
        agent['energy'] -= 0.4
