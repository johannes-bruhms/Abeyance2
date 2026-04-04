# midi/io.py
import mido
import time
import threading
from core.logger import log

class GhostNoteFilter:
    def __init__(self, echo_ttl):
        self.expected_echoes = {}  
        self.lock = threading.Lock()
        self.echo_ttl = echo_ttl

    def register_ai_note(self, note):
        with self.lock:
            self.expected_echoes[note] = time.perf_counter() + self.echo_ttl

    def filter_incoming(self, msg):
        now = time.perf_counter()
        with self.lock:
            self.expected_echoes = {k: v for k, v in self.expected_echoes.items() if v > now}
            if msg.type in ['note_on', 'note_off'] and getattr(msg, 'note', -1) in self.expected_echoes:
                is_note_off = (msg.type == 'note_off') or \
                              (msg.type == 'note_on' and msg.velocity == 0)
                if is_note_off:
                    return None  # suppress echo note-off
                # note_on with velocity > 0: consume the echo entry
                del self.expected_echoes[msg.note]
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