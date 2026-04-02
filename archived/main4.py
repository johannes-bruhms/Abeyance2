import mido
import time
import threading
from collections import deque
import numpy as np
import tkinter as tk
from tkinter import ttk
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.calibration import CalibratedClassifierCV
except ImportError:
    print("CRITICAL: scikit-learn is not installed. Please run: pip install scikit-learn")
    exit(1)

# ===================== CONFIG & CONSTANTS =====================
CONFIG = {
    "eval_interval_ms": 250,               
    "agent_tick_ms": 500,        # How often agents decide to attack
    "energy_decay": 0.02,        # How much energy an agent loses per tick
    "energy_boost": 0.25,        # Energy gained when fed a motif
    "max_buffer_ms": 5000,       # Maximum memory for the Gestalt Window
    "ignore_window_ms": 20      # Time in ms to ignore mechanical feedback from Disklavier
}

ELEMENTS = {
    'a': 'Linear Velocity (Scales)',   
    'b': 'Vertical Density (Clusters)',  
    'c': 'Spatial Leaps (Octaves)',     
    'd': 'Oscillation (Trills)',       
    'e': 'Sweeps (Glissandos)',            
    'f': 'Resonance (Sustain)',         
    'g': 'Stochastic Chaos (Entropy)'   
}

# ===================== FEEDBACK FILTER =====================
class FeedbackFilter:
    def __init__(self, ignore_window_ms):
        self.ignore_window_ms = ignore_window_ms
        self.sent_notes = {}

    def log_sent(self, msg, time_ms):
        if msg.type in ['note_on', 'note_off']:
            self.sent_notes[msg.note] = time_ms

    def is_feedback(self, msg, time_ms):
        if msg.type in ['note_on', 'note_off'] and msg.note in self.sent_notes:
            # If the incoming note matches a recently sent note's pitch, and it's within the window
            if time_ms - self.sent_notes[msg.note] < self.ignore_window_ms:
                return True
        return False

# ===================== FEATURE EXTRACTION =====================
class GestaltWindow:
    def __init__(self, max_buffer_ms=5000):
        self.max_buffer_ms = max_buffer_ms
        self.events = deque()
        self.active_notes = set()
        self.raw_midi_log = deque()

    def add_event(self, msg, time_ms):
        self.raw_midi_log.append((time_ms, msg))
        if msg.type in ['note_on', 'note_off']:
            m_type = 'note_off' if msg.type == 'note_off' or msg.velocity == 0 else 'note_on'
            if m_type == 'note_on':
                self.active_notes.add(msg.note)
            elif m_type == 'note_off' and msg.note in self.active_notes:
                self.active_notes.remove(msg.note)
            self.events.append((time_ms, msg.note, len(self.active_notes)))
            
        # Prune max buffer to save memory
        cutoff = time_ms - self.max_buffer_ms
        while self.events and self.events[0][0] < cutoff: self.events.popleft()
        while self.raw_midi_log and self.raw_midi_log[0][0] < cutoff: self.raw_midi_log.popleft()

    def extract_features_and_motif(self, pedal_down, current_time_ms, target_window_ms):
        cutoff = current_time_ms - target_window_ms
        
        # Filter to specific dynamic window size
        window_events = [e for e in self.events if e[0] >= cutoff]
        window_raw = [e for e in self.raw_midi_log if e[0] >= cutoff]

        if len(window_events) < 2:
            if pedal_down and len(self.active_notes) >= 3:
                return np.array([1, len(self.active_notes), 10, 0, 0, 1, target_window_ms/1000.0]), window_raw
            return None, None

        t = np.array([e[0] for e in window_events])
        t = (t - t[0]) / 1000.0  
        p = np.array([e[1] for e in window_events])
        
        density = len(p)
        polyphony = max([e[2] for e in window_events])
        spread = np.max(p) - np.min(p)

        if len(p) > 1 and np.var(t) > 0:
            slope, intercept = np.polyfit(t, p, 1)
            directionality = slope
            variance = np.mean(np.abs(p - (slope * t + intercept)))
        else:
            directionality, variance = 0, 0

        # Features now include window size, preventing cross-contamination of shapes
        features = np.array([density, polyphony, spread, directionality, variance, 1 if pedal_down else 0, target_window_ms/1000.0])
        return features, window_raw

# ===================== THE GAUSSIAN FORGE =====================
class Bootstrapper:
    def __init__(self):
        self.seeds = {k: [] for k in ELEMENTS.keys()}
        # Base model wrapped in Calibration Layer to fix overfitting and human messiness
        base_rf = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
        self.model = CalibratedClassifierCV(base_rf, cv=3)
        self.is_trained = False

    def add_seed(self, letter, features):
        self.seeds[letter].append(features)

    def train_model(self):
        valid_classes = [k for k, v in self.seeds.items() if len(v) > 0]
        if len(valid_classes) < 2:
            print("Forge requires at least 2 seeded elements to train.")
            self.is_trained = False
            return

        print("Forging Gaussian data from live seeds...")
        X_train, y_train = [], []
        
        # Standard deviations for [Density, Poly, Spread, Dir, Var, Pedal, WindowSec]
        std_devs = np.array([3.0, 1.5, 8.0, 15.0, 5.0, 0.1, 0.2]) 

        for letter in valid_classes:
            features_list = self.seeds[letter]
            centroid = np.mean(features_list, axis=0)
            
            # Generate 1000 synthetic variations of your playing
            cloud = np.random.normal(loc=centroid, scale=std_devs, size=(1000, 7))
            cloud[:, 5] = np.clip(np.round(cloud[:, 5]), 0, 1) # Pedal must be 0 or 1
            
            X_train.extend(cloud)
            y_train.extend([letter] * 1000)

        self.model.fit(X_train, y_train)
        self.is_trained = True
        print("Model Trained and Calibrated successfully.")

    def predict(self, features):
        if not self.is_trained: return None, 0.0
        probs = self.model.predict_proba([features])[0]
        max_idx = np.argmax(probs)
        return self.model.classes_[max_idx], probs[max_idx]

# ===================== PARASITE AGENTS =====================
class ParasiteAgent:
    def __init__(self, letter, name, play_callback):
        self.letter = letter
        self.name = name
        self.play_callback = play_callback
        self.energy = 0.0
        self.stomach = deque(maxlen=5) # Stores recent motifs

    def feed(self, motif):
        if motif:
            self.stomach.append(motif)
            self.energy = min(1.0, self.energy + CONFIG["energy_boost"])

    def tick(self):
        self.energy = max(0.0, self.energy - CONFIG["energy_decay"])
        if self.energy > 0.2 and np.random.random() < (self.energy * 0.4):
            self._attack()

    def _attack(self):
        if not self.stomach: return
        motif = self.stomach[np.random.randint(0, len(self.stomach))]
        transposition = int(np.random.choice([-12, -7, 7, 12])) if self.energy > 0.6 else int(np.random.choice([-5, -2, 2, 5]))
        threading.Thread(target=self._playback_thread, args=(motif, transposition), daemon=True).start()

    def _playback_thread(self, motif, transposition):
        start_time = motif[0][0]
        sys_start = time.perf_counter() # Precise performance counter
        
        for msg_time, msg in motif:
            target_time = sys_start + ((msg_time - start_time) / 1000.0)
            
            # Spin-lock timing fix: Drastically reduces jitter compared to standard time.sleep()
            while (now := time.perf_counter()) < target_time:
                if target_time - now > 0.002: # Sleep only if more than 2ms away
                    time.sleep(0.001)

            if msg.type in ['note_on', 'note_off']:
                mutated_note = max(0, min(127, msg.note + transposition))
                mutated_vel = msg.velocity
                if msg.type == 'note_on' and self.energy > 0.7:
                    mutated_vel = min(127, int(msg.velocity * 1.3))
                    
                try: self.play_callback(msg.copy(note=mutated_note, velocity=mutated_vel))
                except: pass

# ===================== GUI PIANO ROLL =====================
class PianoRoll(tk.Canvas):
    def __init__(self, parent, inverted=False, width=700, height=40):
        super().__init__(parent, width=width, height=height, bg="#2a2a2a", highlightthickness=0)
        self.inverted = inverted
        self.keys = {} # midi_note -> rect_id
        self.active_color = "#ff3333" if inverted else "#33ff33"
        self._draw_keys(width, height)

    def _draw_keys(self, w, h):
        white_keys = [0, 2, 4, 5, 7, 9, 11]
        num_whites = 52 # 88 keys total (MIDI 21 to 108)
        key_w = w / num_whites
        
        # Draw white keys
        w_idx = 0
        for note in range(21, 109):
            if note % 12 in white_keys:
                x1 = w_idx * key_w
                x2 = x1 + key_w
                color = "black" if self.inverted else "white"
                rect = self.create_rectangle(x1, 0, x2, h, fill=color, outline="gray")
                self.keys[note] = {"id": rect, "base_color": color}
                w_idx += 1
                
        # Draw black keys
        w_idx = 0
        for note in range(21, 109):
            if note % 12 in white_keys:
                w_idx += 1
            else:
                x1 = w_idx * key_w - (key_w * 0.3)
                x2 = x1 + (key_w * 0.6)
                color = "white" if self.inverted else "black"
                rect = self.create_rectangle(x1, 0, x2, h * 0.6, fill=color, outline="gray")
                self.keys[note] = {"id": rect, "base_color": color}

    def set_note(self, note, is_on):
        if note in self.keys:
            k = self.keys[note]
            color = self.active_color if is_on else k["base_color"]
            self.itemconfig(k["id"], fill=color)

# ===================== THE SWARM PROTOCOL =====================
class AbeyanceSwarm:
    def __init__(self):
        self.gestalt_window = GestaltWindow(CONFIG["max_buffer_ms"])
        self.forge = Bootstrapper()
        self.feedback_filter = FeedbackFilter(CONFIG["ignore_window_ms"])
        
        self.midi_in, self.midi_out = None, None
        self.agents = {}
        
        self.running = True
        self.pedal_down = False
        self.last_eval_time = 0
        
        # Recording & Voice Stealing State
        self.record_state = "IDLE" # IDLE, RECORDING
        self.recording_target = None
        self.last_seed_time = 0
        self.active_ai_notes = {} 
        
        # --- NEW: Phrase Collector Variables ---
        self.has_uncommitted_phrase = False
        self.last_user_activity_time = 0
        self.phrase_pause_var = None

        self.gui_root = None
        self.element_windows = {}
        self.status_labels = {}
        self.max_poly_var = None
        self.max_lifespan_var = None # Added for garbage collector
        
        self._init_gui()
        threading.Thread(target=self._agent_loop, daemon=True).start()

    def _agent_loop(self):
        while self.running:
            time.sleep(CONFIG["agent_tick_ms"] / 1000.0)
            now = time.perf_counter() * 1000
            
            # --- PHRASE COLLECTOR (Auto-Truncate) ---
            if self.phrase_pause_var:
                threshold = self.phrase_pause_var.get()
                if self.has_uncommitted_phrase and (now - self.last_user_activity_time) >= threshold:
                    self._commit_phrase()
            
            # --- GARBAGE COLLECTOR (Active Monitoring) ---
            if self.max_lifespan_var:
    # --- NEW METHOD: Phrase Committer ---
    def _commit_phrase(self):
        """Packages collected notes into a single element/sample after a pause."""
        self.has_uncommitted_phrase = False
        now = time.perf_counter() * 1000
        
        if self.record_state == "RECORDING" and self.recording_target:
            letter = self.recording_target
            window_ms = self.element_windows[letter].get()
            
            # Extract the shape of the phrase that just finished
            features, _ = self.gestalt_window.extract_features_and_motif(self.pedal_down, now, window_ms)
            
            if features is not None:
                self.forge.add_seed(letter, features)
                count = len(self.forge.seeds[letter])
                self._update_status(letter, f"Recording... ({count}/10)")
                print(f"Phrase Committed! Sample {count}/10 for Element {letter.upper()}")
                
                if count >= 10:
                    self.record_state = "IDLE"
                    self.recording_target = None
                    self._update_status(letter, "Seeded: 10")
                    threading.Thread(target=self._background_train).start()

    def _agent_play_callback(self, msg):
        now = time.perf_counter() * 1000
        self.feedback_filter.log_sent(msg, now)
        
        # Hardware Out & Polyphony Voice Stealer
        if self.midi_out:
            if msg.type == 'note_on' and msg.velocity > 0:
                self.active_ai_notes[msg.note] = now # Track start time
                
                # Steal oldest note if over limit
                limit = self.max_poly_var.get()
                while len(self.active_ai_notes) > limit:
                    stolen_note = min(self.active_ai_notes, key=self.active_ai_notes.get) # Get oldest note
                    del self.active_ai_notes[stolen_note]
                    try: 
                        off_msg = mido.Message('note_off', note=stolen_note, velocity=0)
                        self.midi_out.send(off_msg)
                        self.feedback_filter.log_sent(off_msg, now) # Log stolen release
                        if self.gui_root:
                            self.gui_root.after(0, lambda n=stolen_note: self.ai_roll.set_note(n, False))
                    except: pass
                    
                try: self.midi_out.send(msg)
                except: pass
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in self.active_ai_notes:
                    del self.active_ai_notes[msg.note]
                try: self.midi_out.send(msg)
                except: pass
            else:
                try: self.midi_out.send(msg)
                except: pass
            
        # Update AI visualizer
        if msg.type in ['note_on', 'note_off'] and self.gui_root:
            is_on = (msg.type == 'note_on' and msg.velocity > 0)
            self.gui_root.after(0, lambda: self.ai_roll.set_note(msg.note, is_on))

    def _connect_midi(self):
        if self.midi_in: self.midi_in.close()
        if self.midi_out: self.midi_out.close()
        try:
            self.midi_in = mido.open_input(self.in_var.get(), callback=self.midi_callback)
            self.midi_out = mido.open_output(self.out_var.get())
            self.agents = {k: ParasiteAgent(k, v, self._agent_play_callback) for k, v in ELEMENTS.items()}
            print("MIDI Connected. Swarm Agents Initialized.")
        except Exception as e: print(f"MIDI Error: {e}")

    def midi_callback(self, msg):
        now = time.perf_counter() * 1000
        
        # --- FEEDBACK FILTER & VISUALIZER ---
        if self.feedback_filter.is_feedback(msg, now):
            return # Ignore physical keys moving from the AI's playback
            
        if msg.type in ['note_on', 'note_off']:
            # Track user activity for the Phrase Collector
            self.last_user_activity_time = now
            if msg.type == 'note_on' and msg.velocity > 0:
                self.has_uncommitted_phrase = True
                
            if self.gui_root:
                is_on = (msg.type == 'note_on' and msg.velocity > 0)
                self.gui_root.after(0, lambda: self.performer_roll.set_note(msg.note, is_on))
        
        if msg.type == "control_change" and msg.control == 64:
            self.pedal_down = msg.value >= 64
        self.gestalt_window.add_event(msg, now)

        # (The old SEED COLLECTION INTERCEPT block that polled every 200ms 
        # is completely removed, because _commit_phrase handles it intelligently now!)

        # --- LIVE SWARM EVALUATION ---
        if self.forge.is_trained and (now - self.last_eval_time > CONFIG["eval_interval_ms"]):
            self.last_eval_time = now
            
            # Evaluate using every element's specific dynamic window size
            best_letter, best_score, best_motif = None, 0, None
            
            for letter in ELEMENTS.keys():
                window_ms = self.element_windows[letter].get()
                features, motif = self.gestalt_window.extract_features_and_motif(self.pedal_down, now, window_ms)
                
                if features is not None:
                    pred_letter, score = self.forge.predict(features)
                    # Does the model confidentally think it's THIS letter using THIS letter's window size?
                    if pred_letter == letter and score > best_score:
                        best_score = score
                        best_letter = letter
                        best_motif = motif
            
            if best_score > 0.60 and best_letter in self.agents:
                self.agents[best_letter].feed(best_motif)

    def _start_recording(self, letter):
        self.forge.seeds[letter] = [] # Clear previous list
        self.recording_target = letter
        self.record_state = "RECORDING"
        self.last_seed_time = time.perf_counter() * 1000
        self._update_status(letter, "Recording... (0/10)")

    def _clear_seeds(self, letter):
        self.forge.seeds[letter] = []
        self._update_status(letter, "0 seeds")
        threading.Thread(target=self._background_train).start()

    def _background_train(self):
        self.gui_root.after(0, lambda: self.btn_train.config(state="disabled", text="Forging Swarm..."))
        self.forge.train_model()
        self.gui_root.after(0, lambda: self.btn_train.config(state="normal", text="Force Re-Train All"))

    def _update_status(self, letter, text):
        if letter in self.status_labels:
            self.gui_root.after(0, lambda: self.status_labels[letter].config(text=text))

    def _init_gui(self):
        self.gui_root = tk.Tk()
        self.gui_root.title("Abeyance Protocol – Parasite Swarm (Adaptive)")
        self.gui_root.geometry("750x800")
        self.gui_root.protocol("WM_DELETE_WINDOW", lambda: exit(0))

        # IO Frame
        io_frame = ttk.Frame(self.gui_root)
        io_frame.pack(fill="x", padx=10, pady=5)
        ins, outs = mido.get_input_names() or ["None"], mido.get_output_names() or ["None"]
        self.in_var, self.out_var = tk.StringVar(value=ins[0]), tk.StringVar(value=outs[0])
        ttk.OptionMenu(io_frame, self.in_var, self.in_var.get(), *ins).pack(side="left", padx=5)
        ttk.OptionMenu(io_frame, self.out_var, self.out_var.get(), *outs).pack(side="left", padx=5)
        ttk.Button(io_frame, text="Connect Hardware", command=self._connect_midi).pack(side="left", padx=5)

        # Polyphony Control Frame
        poly_frame = ttk.Frame(self.gui_root)
        poly_frame.pack(fill="x", padx=10, pady=0)
        ttk.Label(poly_frame, text="Max AI Polyphony (Notes):", font=("", 9)).pack(side="left", padx=5)
        self.max_poly_var = tk.IntVar(value=16)
        ttk.Spinbox(poly_frame, from_=2, to=64, increment=2, textvariable=self.max_poly_var, width=5).pack(side="left")

        # Garbage Collector Lifespan Control
        ttk.Label(poly_frame, text=" | Max Note Lifespan (ms):", font=("", 9)).pack(side="left", padx=(10, 5))
        self.max_lifespan_var = tk.IntVar(value=8000)
        ttk.Spinbox(poly_frame, from_=1000, to=60000, increment=500, textvariable=self.max_lifespan_var, width=6).pack(side="left")

        # --- NEW: Phrase Truncation Control ---
        ttk.Label(poly_frame, text=" | Phrase Pause (ms):", font=("", 9)).pack(side="left", padx=(10, 5))
        self.phrase_pause_var = tk.IntVar(value=1000)
        ttk.Spinbox(poly_frame, from_=100, to=10000, increment=100, textvariable=self.phrase_pause_var, width=5).pack(side="left")

        # Visualizer Frame
        vis_frame = ttk.Frame(self.gui_root)
        vis_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(vis_frame, text="Performer Input", font=("", 9, "bold")).pack(anchor="w")
        self.performer_roll = PianoRoll(vis_frame, inverted=False)
        self.performer_roll.pack(fill="x", pady=(0, 10))
        
        ttk.Label(vis_frame, text="AI Swarm Output", font=("", 9, "bold")).pack(anchor="w")
        self.ai_roll = PianoRoll(vis_frame, inverted=True)
        self.ai_roll.pack(fill="x")

        self.notebook = ttk.Notebook(self.gui_root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # TAB 1: Calibration
        tab_calib = ttk.Frame(self.notebook)
        self.notebook.add(tab_calib, text="1. Seed Data & Calibrate")
        
        ttk.Label(tab_calib, text="Click 'Record' and play. The system will collect 10 motif samples.", font=("", 10, "italic")).pack(pady=10)
        
        for letter, name in ELEMENTS.items():
            row = ttk.Frame(tab_calib)
            row.pack(fill="x", pady=4, padx=10)
            ttk.Label(row, text=name, width=22).pack(side="left")
            
            # Independent Window Size Control
            ttk.Label(row, text="Win(ms):").pack(side="left")
            win_var = tk.IntVar(value=1200 if letter not in ['a','d'] else 600) 
            self.element_windows[letter] = win_var
            ttk.Spinbox(row, from_=200, to=5000, increment=100, textvariable=win_var, width=5).pack(side="left", padx=5)
            
            btn_rec = ttk.Button(row, text="Record", command=lambda l=letter: self._start_recording(l))
            btn_rec.pack(side="left", padx=5)
            
            btn_clr = ttk.Button(row, text="Clear", command=lambda l=letter: self._clear_seeds(l))
            btn_clr.pack(side="left", padx=5)
            
            lbl = ttk.Label(row, text="0 seeds", width=20)
            lbl.pack(side="left", padx=10)
            self.status_labels[letter] = lbl

        self.btn_train = ttk.Button(tab_calib, text="Force Re-Train All", command=lambda: threading.Thread(target=self._background_train).start())
        self.btn_train.pack(pady=20)

        # TAB 2: Swarm Monitoring
        tab_swarm = ttk.Frame(self.notebook)
        self.notebook.add(tab_swarm, text="2. Live Swarm")
        
        self.energy_bars = {}
        for letter, name in ELEMENTS.items():
            row = ttk.Frame(tab_swarm)
            row.pack(fill="x", pady=10, padx=20)
            ttk.Label(row, text=name, width=25).pack(side="left")
            
            bar = ttk.Progressbar(row, orient="horizontal", length=300, mode="determinate")
            bar.pack(side="left", padx=10)
            self.energy_bars[letter] = bar

    def run(self):
        self.gui_root.mainloop()

if __name__ == "__main__":
    app = AbeyanceSwarm()
    app.run()