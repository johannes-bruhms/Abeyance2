import mido
import time
import math
import threading
from collections import deque
import numpy as np
import tkinter as tk
from tkinter import ttk

# ===================== CONFIG =====================
CONFIG = {
    "midi_in_port": "Disklavier",          
    "midi_out_port": "Disklavier",
    "gestalt_window_ms": 1200,             # Longer window to capture full motifs
    "novelty_threshold": 35.0,             # How "different" a motif must be to become a new element
    "max_elements": 7,                     # Miller's Law
    "eval_interval_ms": 200,
}

# ===================== GESTALT WINDOW =====================
class GestaltWindow:
    def __init__(self, window_size_ms):
        self.window_size_ms = window_size_ms
        self.events = deque()
        self.active_notes = set()
        self.raw_midi_log = deque() # Stores the actual MIDI messages for playback

    def add_event(self, msg, time_ms):
        self.raw_midi_log.append((time_ms, msg))
        
        if msg.type in ['note_on', 'note_off']:
            m_type = 'note_off' if msg.type == 'note_off' or msg.velocity == 0 else 'note_on'
            if m_type == 'note_on':
                self.active_notes.add(msg.note)
            elif m_type == 'note_off' and msg.note in self.active_notes:
                self.active_notes.remove(msg.note)
                
            polyphony_at_onset = len(self.active_notes)
            self.events.append((time_ms, msg.note, polyphony_at_onset))

    def get_features_and_motif(self, current_time_ms):
        # Prune old events
        cutoff = current_time_ms - self.window_size_ms
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        while self.raw_midi_log and self.raw_midi_log[0][0] < cutoff:
            self.raw_midi_log.popleft()

        if len(self.events) < 3:
            return None, None

        t = np.array([e[0] for e in self.events])
        t = (t - t[0]) / 1000.0  
        p = np.array([e[1] for e in self.events])
        polys = [e[2] for e in self.events]

        density = len(p)
        polyphony = max(polys)
        spread = np.max(p) - np.min(p)

        if len(p) > 1 and np.var(t) > 0:
            slope, intercept = np.polyfit(t, p, 1)
            directionality = slope
            variance = np.mean(np.abs(p - (slope * t + intercept)))
        else:
            directionality = 0
            variance = 0

        features = np.array([density, polyphony, spread, directionality, variance])
        motif = list(self.raw_midi_log)
        return features, motif

# ===================== DISCOVERY ENGINE =====================
class DiscoveryEngine:
    def __init__(self, threshold, max_elements):
        self.threshold = threshold
        self.max_elements = max_elements
        self.elements = [] # Stores dicts: {features, motif, count}

    def _distance(self, f1, f2):
        # Weighted Euclidean distance to handle different scales
        weights = np.array([1.5, 3.0, 1.0, 0.5, 1.0]) 
        return np.sqrt(np.sum(weights * (f1 - f2)**2))

    def evaluate(self, features, motif):
        if not self.elements:
            # First element is always novel
            self.elements.append({"features": features, "motif": motif, "count": 1})
            return 0, True # Returns index, is_novel

        # Find closest existing element
        distances = [self._distance(features, e["features"]) for e in self.elements]
        min_dist = min(distances)
        closest_idx = distances.index(min_dist)

        if min_dist > self.threshold and len(self.elements) < self.max_elements:
            # Novel element discovered!
            self.elements.append({"features": features, "motif": motif, "count": 1})
            return len(self.elements) - 1, True
        else:
            # Matches existing element
            self.elements[closest_idx]["count"] += 1
            # Slowly morph the centroid towards the new playing (learning)
            self.elements[closest_idx]["features"] = (self.elements[closest_idx]["features"] * 0.9) + (features * 0.1)
            return closest_idx, False

# ===================== PLAYBACK ENGINE (MUTATOR) =====================
class PlaybackEngine:
    def __init__(self, midi_out):
        self.midi_out = midi_out

    def play_mutated_motif(self, motif):
        if not self.midi_out: return
        threading.Thread(target=self._playback_thread, args=(motif,), daemon=True).start()

    def _playback_thread(self, motif):
        if not motif: return
        
        # Mutation: Random transposition between -12 and +12 semitones
        transposition = int(np.random.choice([-12, -7, -5, 5, 7, 12]))
        
        start_time = motif[0][0]
        sys_start = time.time()

        for msg_time, msg in motif:
            # Wait until it's time to play this note
            target_time = sys_start + ((msg_time - start_time) / 1000.0)
            now = time.time()
            if target_time > now:
                time.sleep(target_time - now)

            # Apply mutation to Note On/Off messages
            if msg.type in ['note_on', 'note_off']:
                mutated_note = max(0, min(127, msg.note + transposition))
                mutated_msg = msg.copy(note=mutated_note)
                try:
                    self.midi_out.send(mutated_msg)
                except:
                    pass

# ===================== MAIN PROTOCOL =====================
class AbeyanceProtocol:
    def __init__(self):
        self.gestalt_window = GestaltWindow(CONFIG["gestalt_window_ms"])
        self.discovery = DiscoveryEngine(CONFIG["novelty_threshold"], CONFIG["max_elements"])
        
        self.midi_in = None
        self.midi_out = None
        self.playback = None
        
        self.last_eval_time = 0
        self.running = True
        self.gui_root = None
        self.element_labels = []

    def _connect_midi(self):
        if self.midi_in: self.midi_in.close()
        if self.midi_out: self.midi_out.close()
        
        in_port = self.midi_in_var.get()
        out_port = self.midi_out_var.get()
        
        try:
            self.midi_in = mido.open_input(in_port, callback=self.midi_callback)
            print(f"Connected Input: {in_port}")
        except Exception as e: print(f"Input error: {e}")
            
        try:
            self.midi_out = mido.open_output(out_port)
            self.playback = PlaybackEngine(self.midi_out)
            print(f"Connected Output: {out_port}")
        except Exception as e: print(f"Output error: {e}")

    def _init_gui(self):
        self.gui_root = tk.Tk()
        self.gui_root.title("Abeyance Protocol – Discovery Mode")
        self.gui_root.geometry("600x400")
        self.gui_root.protocol("WM_DELETE_WINDOW", self._gui_shutdown)

        # MIDI Frame
        midi_frame = ttk.LabelFrame(self.gui_root, text="Disklavier I/O")
        midi_frame.pack(pady=10, padx=10, fill="x")
        
        self.midi_in_var = tk.StringVar(value=mido.get_input_names()[0] if mido.get_input_names() else "None")
        self.midi_out_var = tk.StringVar(value=mido.get_output_names()[0] if mido.get_output_names() else "None")
        
        ttk.Label(midi_frame, text="IN:").grid(row=0, column=0)
        ttk.OptionMenu(midi_frame, self.midi_in_var, self.midi_in_var.get(), *mido.get_input_names()).grid(row=0, column=1)
        ttk.Label(midi_frame, text="OUT:").grid(row=1, column=0)
        ttk.OptionMenu(midi_frame, self.midi_out_var, self.midi_out_var.get(), *mido.get_output_names()).grid(row=1, column=1)
        ttk.Button(midi_frame, text="Connect", command=self._connect_midi).grid(row=0, column=2, rowspan=2, padx=10)

        # Discovery Tracker
        track_frame = ttk.LabelFrame(self.gui_root, text="Discovered Cognitive Elements")
        track_frame.pack(pady=10, padx=10, fill="both", expand=True)

        for i in range(CONFIG["max_elements"]):
            lbl = tk.Label(track_frame, text=f"[ V O I D ]", font=("Courier", 12), bg="#333333", fg="#555555", width=40, pady=5)
            lbl.pack(pady=2)
            self.element_labels.append(lbl)

    def _gui_shutdown(self):
        self.running = False
        if self.midi_in: self.midi_in.close()
        if self.midi_out: self.midi_out.close()
        self.gui_root.destroy()

    def midi_callback(self, msg):
        now = time.time() * 1000
        self.gestalt_window.add_event(msg, now)

        if now - self.last_eval_time > CONFIG["eval_interval_ms"]:
            self.last_eval_time = now
            features, motif = self.gestalt_window.get_features_and_motif(now)
            
            if features is not None:
                idx, is_novel = self.discovery.evaluate(features, motif)
                
                # Update GUI
                lbl = self.element_labels[idx]
                
                if is_novel:
                    # Formatted feature display
                    stats = f"D:{int(features[0])} P:{int(features[1])} S:{int(features[2])}"
                    self.gui_root.after(0, lambda l=lbl, i=idx, s=stats: l.config(
                        text=f"Element {i+1} Locked [{s}]", bg="#004400", fg="#00ff00"
                    ))
                else:
                    # Flash when triggered
                    current_bg = lbl.cget("bg")
                    self.gui_root.after(0, lambda l=lbl: l.config(bg="#00aa00"))
                    self.gui_root.after(150, lambda l=lbl, bg=current_bg: l.config(bg=bg))
                    
                    # SATURATION PHASE MECHANIC:
                    # If the map is fully discovered, trigger the Disklavier to play a mutated motif back
                    if len(self.discovery.elements) == CONFIG["max_elements"]:
                        # 20% chance to echo back a mutated version of what they just played
                        if np.random.random() < 0.20 and self.playback:
                            saved_motif = self.discovery.elements[idx]["motif"]
                            self.playback.play_mutated_motif(saved_motif)

    def run(self):
        self._init_gui()
        self._connect_midi()
        print("Discovery Mode Active. Awaiting input to map territories...")
        self.gui_root.mainloop()

if __name__ == "__main__":
    protocol = AbeyanceProtocol()
    protocol.run()