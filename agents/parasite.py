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
        self.on_attack = []  # list of fn(event_dict) callbacks for logging attacks

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

            pending_events = []
            with self.lock:
                for label, agent in self.agents.items():
                    agent['energy'] = max(
                        0.0, agent['energy'] - ELEMENT_PARAMS[label]['energy_decay'])

                    if agent['energy'] > CONFIG['energy_trigger'] and len(agent['stomach']) > 0:
                        event = self._trigger_attack(label, agent)
                        if event:
                            pending_events.append(event)

            # Emit attack callbacks outside the lock to avoid deadlock
            for event in pending_events:
                self._emit_attack(event)

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

    def _map_vel_averaged(self, velocities):
        """E — Averaged: mean of all input velocities."""
        if not velocities:
            return 64
        return _clamp_vel(sum(velocities) / len(velocities))

    # -------------------------------------------------------------- attack behaviors

    def _emit_attack(self, event):
        for cb in self.on_attack:
            try:
                cb(event)
            except Exception:
                pass

    def get_energy_snapshot(self):
        """Return current energy levels for all agents (thread-safe)."""
        with self.lock:
            return {label: round(agent['energy'], 3) for label, agent in self.agents.items()}

    def _pedal_transpose(self, note):
        """Apply octave transposition when sustain pedal is held."""
        if self.sustain_pedal_down:
            return _clamp_note(note + 12)
        return note

    def _trigger_attack(self, label, agent):
        dispatch = {
            'a': self._attack_a,
            'b': self._attack_b,
            'c': self._attack_c,
            'd': self._attack_d,
            'e': self._attack_e,
        }
        handler = dispatch.get(label)
        if handler:
            return handler(agent, label)
        return None

    def _attack_a(self, agent, label):
        """Linear Velocity — Counter-motion: invert pitch direction, compressed dynamics."""
        recent = list(agent['stomach'])[-4:]
        if len(recent) < 2:
            return
        pitches = [p for p, v in recent]
        direction = pitches[-1] - pitches[0]
        offset = -12 if direction > 0 else 12
        energy_before = agent['energy']
        out_notes = []
        for i, (pitch, vel) in enumerate(reversed(recent)):
            out_vel = self._map_vel_compressed(vel)
            out_note = self._pedal_transpose(_clamp_note(pitch + offset))
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=0.4,
                delay_sec=i * 0.1)
            out_notes.append({'note': out_note, 'vel': out_vel, 'dur': 0.4, 'delay': round(i * 0.1, 3)})
        agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label].get('energy_drain', 0.3))
        return {
            'element': label, 'mapping': 'compressed',
            'input': [list(t) for t in recent],
            'output': out_notes,
            'energy_before': round(energy_before, 3),
            'energy_after': round(agent['energy'], 3),
        }

    def _attack_b(self, agent, label):
        """Vertical Density — Sustained cluster resonance: quiet chord, slow build."""
        recent = list(agent['stomach'])[-6:]
        if not recent:
            return
        seen = set()
        chord = []
        for pitch, vel in recent:
            if pitch not in seen:
                seen.add(pitch)
                chord.append((pitch, vel))
        if not chord:
            return
        energy_before = agent['energy']
        out_notes = []
        for pitch, vel in chord:
            out_vel = self._map_vel_inverse(vel)
            out_note = self._pedal_transpose(_clamp_note(pitch))
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=2.5,
                delay_sec=0.05)
            out_notes.append({'note': out_note, 'vel': out_vel, 'dur': 2.5, 'delay': 0.05})
        agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label].get('energy_drain', 0.4))
        return {
            'element': label, 'mapping': 'inverse',
            'input': [list(t) for t in recent],
            'output': out_notes,
            'energy_before': round(energy_before, 3),
            'energy_after': round(agent['energy'], 3),
        }

    def _attack_c(self, agent, label):
        """Transposed Shapes — Tritone echo: replay shape transposed by 6 semitones."""
        recent = list(agent['stomach'])[-4:]
        if not recent:
            return
        tritone = 6
        energy_before = agent['energy']
        out_notes = []
        for i, (pitch, vel) in enumerate(recent):
            out_vel = self._map_vel_direct(vel)
            out_note = self._pedal_transpose(_clamp_note(pitch + tritone))
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=0.3,
                delay_sec=i * 0.08)
            out_notes.append({'note': out_note, 'vel': out_vel, 'dur': 0.3, 'delay': round(i * 0.08, 3)})
        agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label].get('energy_drain', 0.3))
        return {
            'element': label, 'mapping': 'direct',
            'input': [list(t) for t in recent],
            'output': out_notes,
            'energy_before': round(energy_before, 3),
            'energy_after': round(agent['energy'], 3),
        }

    def _attack_d(self, agent, label):
        """Oscillation — Phase-shifted trill: oscillate between boundary pitches at offset rate."""
        recent = list(agent['stomach'])[-8:]
        if len(recent) < 2:
            return
        pitches = [p for p, v in recent]
        velocities = [v for p, v in recent]
        lo, hi = min(pitches), max(pitches)
        mean_vel = sum(velocities) / len(velocities)
        energy_before = agent['energy']
        out_notes = []
        for i in range(6):
            pitch = lo if i % 2 == 0 else hi
            out_vel = self._map_vel_expanded(mean_vel)
            out_note = self._pedal_transpose(_clamp_note(pitch))
            self.playback.schedule_note(
                out_note, out_vel,
                duration_sec=0.15,
                delay_sec=i * 0.12)
            out_notes.append({'note': out_note, 'vel': out_vel, 'dur': 0.15, 'delay': round(i * 0.12, 3)})
        agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label].get('energy_drain', 0.35))
        return {
            'element': label, 'mapping': 'expanded',
            'input': [list(t) for t in recent],
            'output': out_notes,
            'energy_before': round(energy_before, 3),
            'energy_after': round(agent['energy'], 3),
        }

    def _attack_e(self, agent, label):
        """Extreme Registers — Fill the gap: respond in the middle register the performer avoids."""
        recent = list(agent['stomach'])[-6:]
        if not recent:
            return
        pitches = [p for p, v in recent]
        velocities = [v for p, v in recent]
        avg_vel = self._map_vel_averaged(velocities)
        lo, hi = min(pitches), max(pitches)
        mid = (lo + hi) // 2
        fill_notes = [mid - 2, mid, mid + 2, mid + 4]
        energy_before = agent['energy']
        out_notes = []
        for i, pitch in enumerate(fill_notes):
            out_note = self._pedal_transpose(_clamp_note(pitch))
            self.playback.schedule_note(
                out_note, avg_vel,
                duration_sec=1.0,
                delay_sec=i * 0.2)
            out_notes.append({'note': out_note, 'vel': avg_vel, 'dur': 1.0, 'delay': round(i * 0.2, 3)})
        agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label].get('energy_drain', 0.4))
        return {
            'element': label, 'mapping': 'averaged',
            'input': [list(t) for t in recent],
            'output': out_notes,
            'energy_before': round(energy_before, 3),
            'energy_after': round(agent['energy'], 3),
        }
