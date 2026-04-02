import mido
import time
from collections import deque
import numpy as np
from hmmlearn.hmm import GaussianHMM
import argparse
import tkinter as tk

# ===================== CONFIG =====================
CONFIG = {
    "midi_in_port": "Disklavier",          # ← change to exact name shown by mido.get_input_names()
    "ignore_window_ms": 150,
    "abeyance_window_ms": 1500,
    "overlap_threshold_ms": 50,
    "hhmm_thresholds": {                   # only a-e and g (no f)
        "a": 0.85, "b": 0.85, "c": 0.85, "d": 0.85,
        "e": 0.80, "g": 0.85
    },
    "hhmm_n_components": 3,
    "hhmm_n_iter": 200,                    # increased for stability with richer data
    "hhmm_min_covar": 1e-3,                # prevents convergence warnings
}

# ===================== FEEDBACK FILTER =====================
class FeedbackFilter:
    def __init__(self, ignore_window_ms=150):
        self.generated = deque(maxlen=100)
        self.ignore_window_ms = ignore_window_ms

    def list(self, pitch, vel):
        if vel == 0:
            return None
        now = time.time() * 1000
        while self.generated and self.generated[0][0] < now - 1000:
            self.generated.popleft()
        for ts, p, v in self.generated:
            if p == pitch and abs(v - vel) < 20 and now - ts < self.ignore_window_ms:
                return None
        return (pitch, vel)

    def add_generated(self, pitch, vel):
        now = time.time() * 1000
        self.generated.append((now, pitch, vel))

    def ignore(self, ms):
        self.ignore_window_ms = max(50, int(ms))
        print(f"Ignore window set to {self.ignore_window_ms} ms")

    def clear(self):
        self.generated.clear()
        print("Generated note cache cleared")

# ===================== SYNTHETIC GENERATOR (FULL VARIATION) =====================
class SyntheticGenerator:
    def __init__(self):
        self.black_keys = [i for i in range(21, 109) if i % 12 in [1, 3, 6, 8, 10]]

    def gen(self, cls, num_examples=300):
        sequences = []
        for _ in range(num_examples):
            length = 8 + np.random.randint(0, 13)
            seq = []
            if cls == "a":  # OCTAVES – full register & span variation
                base = np.random.randint(36, 84)          # any low register
                span = np.random.choice([12, 24, 36])     # octave, double, triple
                direction = np.random.choice([1, -1])
                for i in range(length):
                    low = base + np.random.uniform(-2, 2)
                    high = low + span * direction
                    p = low if i % 2 == 0 else high
                    interv = span * direction if i % 2 == 0 else -span * direction
                    ioi = 60 + np.random.uniform(-20, 60)
                    v = 85 + np.random.uniform(0, 30)
                    seq.append([p, v, ioi, interv])
            elif cls == "b":  # small clusters – wide register coverage
                for i in range(length):
                    p = 48 + np.random.randint(-24, 36)
                    interv = np.random.uniform(-4, 4)
                    ioi = 25 + np.random.uniform(-10, 30)
                    v = 95 + np.random.uniform(0, 20)
                    seq.append([p, v, ioi, interv])
            elif cls == "c":  # large clusters – full piano range
                for i in range(length):
                    p = 21 + np.random.uniform(0, 88)
                    interv = np.random.uniform(-20, 20)
                    ioi = 35 + np.random.uniform(-15, 40)
                    v = 80 + np.random.uniform(0, 35)
                    seq.append([p, v, ioi, interv])
            elif cls == "d":  # scalar – varied direction, step, register
                start = np.random.randint(36, 84)
                step = np.random.choice([-3, -2, -1, 1, 2, 3])
                for i in range(length):
                    p = start + i * step + np.random.uniform(-1, 1)
                    interv = float(step)
                    ioi = 110 + np.random.uniform(-30, 60)
                    v = 70 + np.random.uniform(0, 30)
                    seq.append([p, v, ioi, interv])
            elif cls == "e":  # outlier – full range & extreme variation
                for i in range(length):
                    p = np.random.uniform(21, 108)
                    interv = np.random.uniform(-30, 30)
                    ioi = 40 + np.random.uniform(-20, 120)
                    v = 50 + np.random.uniform(0, 70)
                    seq.append([p, v, ioi, interv])
            elif cls == "g":  # black keys glissando – already excellent
                direction = np.random.choice([1, -1])
                start_idx = np.random.randint(0, len(self.black_keys) - length)
                pitches = self.black_keys[start_idx:start_idx + length]
                if direction == -1:
                    pitches = pitches[::-1]
                speed = np.random.uniform(6, 40)
                for i in range(length):
                    p = float(pitches[i])
                    interv = (pitches[i] - pitches[i - 1]) if i > 0 else 0.0
                    ioi = speed + np.random.uniform(-4, 6)
                    v = 95 + np.random.uniform(0, 20)
                    seq.append([p, v, ioi, interv])
            sequences.append(np.array(seq))
        print(f"Synthetic data generated for class {cls} – {num_examples} examples")
        return sequences

# ===================== ABEYANCE BUFFER =====================
class AbeyanceBuffer:
    def __init__(self, window_ms=1500, overlap_threshold_ms=50):
        self.window_ms = window_ms
        self.overlap_threshold_ms = overlap_threshold_ms
        self.events = deque()

    def add(self, elem):
        now = time.time() * 1000
        self.events.append((now, elem))
        self._prune(now)
        state = self.compute_state(now)
        return state

    def _prune(self, now):
        while self.events and self.events[0][0] < now - self.window_ms:
            self.events.popleft()

    def compute_state(self, now):
        counts = {"a":0,"b":0,"c":0,"d":0,"e":0,"f":0,"g":0}
        distinct = 0
        overlap = 0
        total = len(self.events)
        ev_list = list(self.events)
        for i, (t, e) in enumerate(ev_list):
            if counts[e] == 0:
                distinct += 1
            counts[e] += 1
            for j in range(i):
                if abs(ev_list[j][0] - t) < self.overlap_threshold_ms and ev_list[j][1] != e:
                    overlap = 1
        return [counts["a"], counts["b"], counts["c"], counts["d"],
                counts["e"], counts["f"], counts["g"],
                distinct, overlap, total]

    def window(self, ms):
        self.window_ms = max(100, int(ms))

    def bang(self):
        now = time.time() * 1000
        self._prune(now)
        return self.compute_state(now)

# ===================== SYMBOLIC CLASSIFIERS =====================
class SymbolicClassifiers:
    def __init__(self):
        self.models = {}
        self.letters = "abcdeg"
        for letter in self.letters:
            self.models[letter] = GaussianHMM(
                n_components=CONFIG["hhmm_n_components"],
                covariance_type="diag",
                n_iter=CONFIG["hhmm_n_iter"],
                min_covar=CONFIG["hhmm_min_covar"],
                random_state=42
            )
        self.likelihood_thresholds = CONFIG["hhmm_thresholds"].copy()

    def train(self, letter, live_sequences=None, synthetic_num=300):
        if live_sequences is None:
            live_sequences = []
        gen = SyntheticGenerator()
        synth_seqs = gen.gen(letter, synthetic_num)
        all_seqs = live_sequences + synth_seqs
        lengths = [len(s) for s in all_seqs]
        X = np.vstack(all_seqs)
        self.models[letter].fit(X, lengths)
        print(f"Trained HHMM for class {letter}")

    def predict(self, feature_vector):
        results = {}
        for letter, model in self.models.items():
            try:
                logprob = model.score(feature_vector)
                results[letter] = logprob
            except:
                results[letter] = -np.inf
        return results

# ===================== OVERLOAD STUB =====================
class PlaceholderOverload:
    def __init__(self):
        self.overload = 1.0
        print("EEG disabled – using neutral overload value (1.0)")

    def get_overload(self):
        return self.overload

    def shutdown(self):
        pass

# ===================== MAIN PROTOCOL =====================
class AbeyanceProtocol:
    def __init__(self):
        self.filter = FeedbackFilter(CONFIG["ignore_window_ms"])
        self.buffer = AbeyanceBuffer(CONFIG["abeyance_window_ms"], CONFIG["overlap_threshold_ms"])
        self.classifiers = SymbolicClassifiers()
        self.overload_handler = PlaceholderOverload()

        self.last_note_time = 0
        self.last_note_pitch = 0
        self.ioi_history = deque(maxlen=5)

        self.midi_in = None
        self.running = True

        self.gui_enabled = False
        self.gui_root = None
        self.piano_canvas = None
        self.key_rects = {}
        self.key_colors = {}
        self.indicators = {}
        self.overload_var = None

    def _init_gui(self):
        self.gui_root = tk.Tk()
        self.gui_root.title("Abeyance Protocol - MIDI Visualizer")
        self.gui_root.protocol("WM_DELETE_WINDOW", self._gui_shutdown)

        # Piano visualizer (rudimentary linear keyboard – 88 keys, input only)
        self.piano_canvas = tk.Canvas(self.gui_root, width=880, height=180, bg="#aaaaaa")
        self.piano_canvas.pack(pady=10)
        key_width = 10
        for i in range(88):
            note = 21 + i
            x = i * key_width
            mod12 = note % 12
            is_black = mod12 in [1, 3, 6, 8, 10]
            color = "#222222" if is_black else "#eeeeee"
            rect = self.piano_canvas.create_rectangle(
                x, 20, x + key_width, 170,
                fill=color, outline="#111111", width=1
            )
            self.key_rects[note] = rect
            self.key_colors[note] = color

        # MIDI output note (Python side has no output generation yet)
        out_label = tk.Label(
            self.gui_root,
            text="MIDI Output: monitored externally via Max/MSP (no Python-side output yet)",
            font=("Courier", 10),
            fg="#666666"
        )
        out_label.pack()

        # Element indicators (a-g including f)
        ind_frame = tk.Frame(self.gui_root)
        ind_frame.pack(pady=5)
        letters = list("abcdegf")
        for letter in letters:
            lbl = tk.Label(
                ind_frame,
                text=letter.upper(),
                font=("Courier", 14, "bold"),
                width=3,
                height=2,
                bg="#cccccc",
                relief="sunken"
            )
            lbl.pack(side=tk.LEFT, padx=3)
            self.indicators[letter] = lbl

        # Overload number display
        self.overload_var = tk.StringVar(value="Overload: 1.000")
        ol_label = tk.Label(
            self.gui_root,
            textvariable=self.overload_var,
            font=("Courier", 18, "bold"),
            fg="#006600"
        )
        ol_label.pack(pady=10)

        # Quit button
        quit_btn = tk.Button(
            self.gui_root,
            text="Quit Protocol",
            command=self._gui_shutdown,
            font=("Courier", 12),
            bg="#ffdddd"
        )
        quit_btn.pack(pady=5)

    def _highlight_key(self, note):
        if note not in self.key_rects:
            return
        self.piano_canvas.itemconfig(self.key_rects[note], fill="#00cc00")
        self.gui_root.after(150, lambda n=note: self._reset_key(n))

    def _reset_key(self, note):
        if note in self.key_rects:
            self.piano_canvas.itemconfig(self.key_rects[note], fill=self.key_colors[note])

    def _flash_element(self, letter):
        if letter not in self.indicators:
            return
        lbl = self.indicators[letter]
        orig = lbl.cget("bg")
        lbl.config(bg="#00cc00")
        self.gui_root.after(300, lambda: lbl.config(bg=orig))

    def update_overload_display(self):
        if not self.gui_enabled or not self.gui_root:
            return
        ol = round(self.overload_handler.get_overload(), 3)
        self.overload_var.set(f"Overload: {ol}")
        self.gui_root.after(500, self.update_overload_display)

    def _gui_shutdown(self):
        self.running = False
        if self.midi_in:
            self.midi_in.close()
        self.overload_handler.shutdown()
        if self.gui_root:
            self.gui_root.destroy()
        print("GUI shutdown complete")

    def midi_callback(self, msg):
        now = time.time() * 1000

        if msg.type == "note_on" and msg.velocity > 0:
            # always visualize raw MIDI input (even if filtered)
            if self.gui_enabled and self.gui_root:
                self.gui_root.after(0, lambda n=msg.note: self._highlight_key(n))

            ioi = now - self.last_note_time if self.last_note_time else 120.0
            self.ioi_history.append(ioi)
            interv = msg.note - self.last_note_pitch if self.last_note_pitch else 0.0
            self.last_note_time = now
            self.last_note_pitch = msg.note

            feature_vec = np.array([[msg.note, msg.velocity, ioi, interv]])

            passed = self.filter.list(msg.note, msg.velocity)
            if passed is None:
                return

            lik = self.classifiers.predict(feature_vec)
            max_lik_letter = max(lik, key=lik.get)
            max_score = lik[max_lik_letter]
            thresh = self.classifiers.likelihood_thresholds[max_lik_letter]

            if max_score > thresh:
                self.buffer.add(max_lik_letter)
                if self.gui_enabled and self.gui_root:
                    self.gui_root.after(0, lambda l=max_lik_letter: self._flash_element(l))

        elif msg.type == "control_change" and msg.control == 64:
            if msg.value >= 64:
                self.buffer.add("f")
                if self.gui_enabled and self.gui_root:
                    self.gui_root.after(0, lambda: self._flash_element("f"))

    def start_midi(self):
        ports = mido.get_input_names()
        print("Available MIDI ports:", ports)
        for p in ports:
            if CONFIG["midi_in_port"].lower() in p.lower():
                self.midi_in = mido.open_input(p, callback=self.midi_callback)
                print(f"Opened MIDI input: {p}")
                return
        print("MIDI port not found – edit CONFIG['midi_in_port']")

    def training_mode(self, letter, live_seconds=30, synth_num=300):
        print(f"TRAINING CLASS {letter.upper()} – record live for {live_seconds}s")
        live_seqs = []
        self.classifiers.train(letter, live_seqs, synth_num)

    def run(self):
        self.gui_enabled = True
        self._init_gui()
        self.start_midi()
        print("Abeyance Protocol Python v3 running with GUI – close window to stop")
        self.update_overload_display()
        self.gui_root.mainloop()

# ===================== TRAINING SUB-PROTOCOL =====================
def run_training_sub_protocol():
    protocol = AbeyanceProtocol()
    for letter in "abcdeg":
        protocol.training_mode(letter, live_seconds=30, synth_num=300)
    print("Training sub-protocol complete – models ready for live use")

# ===================== ENTRY POINT =====================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="Run full training sub-protocol")
    parser.add_argument("--run", action="store_true", help="Run real-time protocol")
    args = parser.parse_args()

    if args.train:
        run_training_sub_protocol()
    elif args.run:
        protocol = AbeyanceProtocol()
        protocol.run()
    else:
        print("Usage: python main.py --train  OR  python main.py --run")