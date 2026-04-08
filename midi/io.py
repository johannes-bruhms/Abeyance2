# midi/io.py
import mido
import time
import threading
from core.logger import log

class GhostNoteFilter:
    def __init__(self, echo_ttl):
        # note → list of {'expiry': float, 'on_seen': bool}
        # Multiple entries per pitch allow overlapping AI notes (e.g. trills).
        self.expected_echoes = {}
        self.lock = threading.Lock()
        self.echo_ttl = echo_ttl

    def register_ai_note(self, note):
        with self.lock:
            if note not in self.expected_echoes:
                self.expected_echoes[note] = []
            self.expected_echoes[note].append({
                'expiry': time.perf_counter() + self.echo_ttl,
                'on_seen': False,
            })

    def filter_incoming(self, msg):
        now = time.perf_counter()
        with self.lock:
            # Prune expired entries
            for note in list(self.expected_echoes):
                self.expected_echoes[note] = [
                    e for e in self.expected_echoes[note] if e['expiry'] > now
                ]
                if not self.expected_echoes[note]:
                    del self.expected_echoes[note]

            if msg.type in ['note_on', 'note_off'] and getattr(msg, 'note', -1) in self.expected_echoes:
                entries = self.expected_echoes[msg.note]
                is_note_off = (msg.type == 'note_off') or \
                              (msg.type == 'note_on' and msg.velocity == 0)
                if is_note_off:
                    # Consume the oldest entry that has seen its note_on
                    for i, entry in enumerate(entries):
                        if entry['on_seen']:
                            entries.pop(i)
                            break
                    else:
                        # No on_seen entry — consume the oldest anyway
                        if entries:
                            entries.pop(0)
                    if not entries:
                        del self.expected_echoes[msg.note]
                    return None
                # note_on with velocity > 0: mark the oldest unmarked entry
                for entry in entries:
                    if not entry['on_seen']:
                        entry['on_seen'] = True
                        break
                return None
        return msg

class MidiIO:
    def __init__(self, in_port_name, out_port_name, ghost_filter,
                 note_callback, cc_callback, note_off_callback=None):
        self.ghost_filter = ghost_filter
        self.note_callback = note_callback
        self.cc_callback = cc_callback
        self.note_off_callback = note_off_callback
        
        try:
            # Note: Update these names based on your Disklavier's actual port names if needed
            self.inport = mido.open_input(in_port_name, callback=self._midi_callback)
            self.outport = mido.open_output(out_port_name)
            log.info(f"MIDI connected: {in_port_name} / {out_port_name}")
        except OSError as e:
            log.warn(f"MIDI unavailable: {e} — starting in offline/dummy mode")
            self.inport = None
            self.outport = None

    def _midi_callback(self, msg):
        # Route CC 64 (Sustain Pedal)
        if msg.type == 'control_change' and msg.control == 64:
            self.cc_callback(msg.value)
            return
            
        filtered_msg = self.ghost_filter.filter_incoming(msg)
        if not filtered_msg:
            return
        is_note_off = (filtered_msg.type == 'note_off') or \
                      (filtered_msg.type == 'note_on' and filtered_msg.velocity == 0)
        if filtered_msg.type == 'note_on' and filtered_msg.velocity > 0:
            self.note_callback(filtered_msg.note, filtered_msg.velocity)
        elif is_note_off and self.note_off_callback:
            self.note_off_callback(filtered_msg.note)

    def send_note_on(self, note, velocity):
        if self.outport:
            self.ghost_filter.register_ai_note(note)
            self.outport.send(mido.Message('note_on', note=note, velocity=velocity))

    def send_note_off(self, note):
        if self.outport:
            self.outport.send(mido.Message('note_off', note=note, velocity=0))

    def send_all_notes_off(self):
        """Send MIDI CC 123 (All Notes Off) on all channels."""
        if self.outport:
            for ch in range(16):
                self.outport.send(mido.Message('control_change',
                                               channel=ch, control=123, value=0))