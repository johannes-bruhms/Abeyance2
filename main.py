# main.py
import tkinter as tk
import threading
import time
from core.config import CONFIG, ELEMENTS
from midi.io import MidiIO, GhostNoteFilter
from midi.playback import PlaybackEngine
from ml.classifier import HybridGestaltDTW
from agents.parasite import ParasiteSwarm
from gui.app import AbeyanceGUI

class AbeyanceApp:
    def __init__(self):
        self.root = tk.Tk()
        
        self.dtw = HybridGestaltDTW()
        self.ghost_filter = GhostNoteFilter(CONFIG['ghost_echo_ttl'])
        
        self.midi_io = None
        self.playback = None
        self.swarm = None
        
        self.current_frame_notes = []
        self.lock = threading.Lock()
        self.analysis_running = False

        # Init GUI last, passing self to act as the controller
        self.gui = AbeyanceGUI(self.root, self)

    def connect_midi(self, in_port_name, out_port_name):
        """Called by the GUI to establish the hardware connection."""
        try:
            self.midi_io = MidiIO(in_port_name, out_port_name, self.ghost_filter, self._on_midi_in, self._on_cc_in)
            self.playback = PlaybackEngine(self.midi_io)
            
            # Hook the playback engine to feed AI notes back into the GUI Piano Roll
            original_schedule = self.playback.schedule_note
            def hooked_schedule(note, velocity, duration_sec, delay_sec=0.0):
                self.gui.add_note_visual(note, velocity, is_ai=True)
                original_schedule(note, velocity, duration_sec, delay_sec)
            self.playback.schedule_note = hooked_schedule
            
            self.swarm = ParasiteSwarm(ELEMENTS, self.playback)
            return True
        except Exception as e:
            print(f"Failed to connect MIDI: {e}")
            return False

    def _on_midi_in(self, note, velocity):
        # Log to GUI
        self.gui.add_note_visual(note, velocity, is_ai=False)
        # Add tuple of (pitch, timestamp) for Polyphony calculations
        with self.lock:
            self.current_frame_notes.append((note, time.perf_counter()))
            
    def _on_cc_in(self, value):
        # Route CC 64 (Pedal) directly to swarm logic
        is_down = value > 63
        if self.swarm:
            self.swarm.set_pedal(is_down)

    def start_analysis(self):
        if not self.analysis_running and self.midi_io:
            self.analysis_running = True
            threading.Thread(target=self._analysis_loop, daemon=True).start()
            self.gui.status_var.set("Analysis Running")

    def _analysis_loop(self):
        # Fetch dynamically from CONFIG in case user adjusted slider
        while self.analysis_running:
            frame_sec = CONFIG['frame_size_ms'] / 1000.0
            start_time = time.perf_counter()
            
            with self.lock:
                notes_to_process = list(self.current_frame_notes)
                self.current_frame_notes = [] 
                
            # Feed raw tuples into the DTW (which uses extract_micro_gestalt)
            self.dtw.push_frame(notes_to_process)
            
            detected_motif = self.dtw.classify_current()
            if detected_motif:
                # Strip timestamps out before feeding the agent stomachs
                raw_pitches = [n[0] for n in notes_to_process]
                if self.swarm:
                    self.swarm.feed(detected_motif, raw_pitches)
                
                status_msg = f"Gestalt: {ELEMENTS[detected_motif]}"
                print(status_msg)
                self.gui.root.after(0, self.gui.status_var.set, status_msg)

            # Enforce strict timeframe looping
            elapsed = time.perf_counter() - start_time
            sleep_time = max(0, frame_sec - elapsed)
            time.sleep(sleep_time)

if __name__ == "__main__":
    app = AbeyanceApp()
    app.root.mainloop()