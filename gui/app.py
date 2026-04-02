# gui/app.py
import tkinter as tk
from tkinter import ttk
import mido
from gui.piano_roll import PianoRollCanvas
from core.config import CONFIG, ELEMENTS

class AbeyanceGUI:
    def __init__(self, root, app_controller):
        self.root = root
        self.app_controller = app_controller
        self.root.title("Abeyance II - BCMI Interface")
        self.root.geometry("1000x700")
        
        self.left_panel = tk.Frame(self.root, width=320, padx=15, pady=15, bg="#2b2b2b")
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        self.right_panel = tk.Frame(self.root, padx=10, pady=10)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use('clam')
        
        self._build_controls()
        self._build_visuals()
        self._animate_roll()

    def _build_controls(self):
        self.status_var = tk.StringVar(value="System Idle")
        tk.Label(self.left_panel, textvariable=self.status_var, font=("Helvetica", 14, "bold"), fg="#00ffcc", bg="#2b2b2b").pack(pady=(0, 15))
        
        tk.Label(self.left_panel, text="MIDI Input Port:", bg="#2b2b2b", fg="white").pack(anchor=tk.W)
        self.in_port_var = tk.StringVar()
        self.in_dropdown = ttk.Combobox(self.left_panel, textvariable=self.in_port_var, values=mido.get_input_names() or ["No Inputs Found"])
        self.in_dropdown.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(self.left_panel, text="MIDI Output Port:", bg="#2b2b2b", fg="white").pack(anchor=tk.W)
        self.out_port_var = tk.StringVar()
        self.out_dropdown = ttk.Combobox(self.left_panel, textvariable=self.out_port_var, values=mido.get_output_names() or ["No Outputs Found"])
        self.out_dropdown.pack(fill=tk.X, pady=(0, 15))
        
        self.connect_btn = tk.Button(self.left_panel, text="Connect MIDI", command=self._connect_midi, bg="#444", fg="white")
        self.connect_btn.pack(fill=tk.X, pady=(0, 20))

        tk.Label(self.left_panel, text="Model Parameters", font=("Helvetica", 12, "bold"), bg="#2b2b2b", fg="white").pack(anchor=tk.W, pady=(10, 5))
        self._make_slider("DTW Radius:", 'dtw_radius', 1, 10, 1)
        self._make_slider("Energy Boost:", 'energy_boost', 0.1, 1.0, 0.05)
        self._make_slider("Energy Decay:", 'energy_decay', 0.01, 0.1, 0.01)

        self.start_btn = tk.Button(self.left_panel, text="Start Analysis", command=self.app_controller.start_analysis, state=tk.DISABLED, bg="#0066cc", fg="white", font=("Helvetica", 12, "bold"))
        self.start_btn.pack(fill=tk.X, pady=(20, 0))

    def _make_slider(self, label, config_key, from_, to, resolution, parent=None):
        parent = parent or self.left_panel
        tk.Label(parent, text=label, bg=parent['bg'], fg="#ccc").pack(anchor=tk.W, pady=(5, 0))
        slider = tk.Scale(parent, from_=from_, to=to, resolution=resolution, orient=tk.HORIZONTAL, 
                          command=lambda val, k=config_key: self._update_config(k, val), bg=parent['bg'], fg="white", highlightthickness=0)
        slider.set(CONFIG[config_key])
        slider.pack(fill=tk.X)

    def _update_config(self, key, val):
        CONFIG[key] = float(val) if '.' in str(val) or isinstance(CONFIG[key], float) else int(float(val))

    def _connect_midi(self):
        # Simplified connection feedback
        if self.app_controller.connect_midi(self.in_port_var.get(), self.out_port_var.get()):
            self.start_btn.config(state=tk.NORMAL)
            self.status_var.set("MIDI Connected")

    def _build_visuals(self):
        self.notebook = ttk.Notebook(self.right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 1. Piano Roll Tab
        self.roll_frame = tk.Frame(self.notebook, bg="black")
        self.piano_roll = PianoRollCanvas(self.roll_frame)
        self.piano_roll.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.roll_frame, text="Live Piano Roll")
        
        # 2. Training Dashboard Tab (NEW)
        self.train_frame = tk.Frame(self.notebook, bg="#2b2b2b", padx=20, pady=20)
        self.notebook.add(self.train_frame, text="Human Seed Training")
        self._build_training_tab()
        
        # 3. Log Tab
        self.log_frame = tk.Frame(self.notebook)
        self.log_text = tk.Text(self.log_frame, height=30, bg="#1e1e1e", fg="#00ffcc", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.log_frame, text="Event Log")

    def _build_training_tab(self):
        # 1. Selection & Config Frame
        config_frame = tk.LabelFrame(self.train_frame, text="1. Select & Configure Gesture", font=("Helvetica", 12, "bold"), bg="#2b2b2b", fg="white", padx=10, pady=10)
        config_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(config_frame, text="Target Gesture to Train:", bg="#2b2b2b", fg="#00ffcc", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        
        # Dropdown mapping Element names to IDs
        self.target_element_var = tk.StringVar()
        self.element_mapping = {v: k for k, v in ELEMENTS.items() if k != 'f'} # Exclude pedal
        options = list(self.element_mapping.keys())
        self.target_element_var.set(options[0])
        ttk.Combobox(config_frame, textvariable=self.target_element_var, values=options, state="readonly", width=30).pack(anchor=tk.W, pady=(5, 15))
        
        tk.Label(config_frame, text="Synthetic Generation Parameters for this Gesture:", bg="#2b2b2b", fg="white").pack(anchor=tk.W)
        self._make_slider("Synthetic Variations to Forge:", 'variations', 10, 500, 10, parent=config_frame)
        self._make_slider("Gaussian Noise Spread (Variance):", 'noise_spread', 0.01, 0.20, 0.01, parent=config_frame)
        
        # 2. Recording Frame
        record_frame = tk.LabelFrame(self.train_frame, text="2. Record Human Seed", font=("Helvetica", 12, "bold"), bg="#2b2b2b", fg="white", padx=10, pady=10)
        record_frame.pack(fill=tk.X)
        
        tk.Label(record_frame, text="Play your interpretation of the selected gesture on the piano.", bg="#2b2b2b", fg="#ccc").pack(anchor=tk.W, pady=(0, 10))
        self.record_btn = tk.Button(record_frame, text="🔴 Start Recording Human Seed", bg="#aa0000", fg="white", font=("Helvetica", 12, "bold"), command=self._toggle_recording)
        self.record_btn.pack(anchor=tk.W, pady=5, ipadx=10, ipady=5)

    def _toggle_recording(self):
        element_name = self.target_element_var.get()
        element_id = self.element_mapping[element_name]
        is_recording = self.app_controller.toggle_recording(element_id)
        
        if is_recording:
            self.record_btn.config(text="⏹ Stop & Forge Synthetic Data", bg="#ff8c00")
        else:
            self.record_btn.config(text="🔴 Start Recording Human Seed", bg="#aa0000")

    def log_msg(self, msg):
        self.root.after(0, lambda: [self.log_text.insert(tk.END, msg + "\n"), self.log_text.see(tk.END)])

    def add_note_visual(self, note, velocity, is_ai=False):
        self.root.after(0, self.piano_roll.draw_note, note, velocity, is_ai)

    def _animate_roll(self):
        self.piano_roll.update_roll()
        self.root.after(30, self._animate_roll)