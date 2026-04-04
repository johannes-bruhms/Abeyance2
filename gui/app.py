# gui/app.py
import time
import tkinter as tk
from tkinter import ttk
import mido
from core.logger import log
from gui.piano_roll import PianoRollCanvas, ELEMENT_COLORS
from core.config import CONFIG, ELEMENTS, ELEMENT_PARAMS

TRAINABLE = list(ELEMENTS.keys())
BG = '#2b2b2b'
BG_COL = '#1e1e1e'

# Short gesture hints shown inside each Training column
ELEMENT_HINTS = {
    'a': 'Play smooth runs moving\nconsistently up OR down.\nScales, one-direction arpeggios.',
    'b': 'Play dense simultaneous\nattacks: thick chords,\ntone clusters.',
    'c': 'Play an interval or chord shape\n(e.g. octave, 5th) then shift it\nrapidly to a different register.',
    'd': 'Alternate rapidly between\ntwo pitch regions.\nTrils, tremolo figures.',
    'e': 'Sweep fast across a wide\npitch range. Glissandi,\nrapid scale passages.',
    'f': 'Play simultaneously in the\nhighest and lowest registers.\nBoth hands at extremes.',
}


class AbeyanceGUI:
    def __init__(self, root, app_controller):
        self.root           = root
        self.app_controller = app_controller
        self.root.title("Abeyance II - BCMI Interface")
        self.root.geometry("1200x720")

        self.left_panel = tk.Frame(self.root, width=310, padx=12, pady=12, bg=BG)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)   # children cannot resize the panel

        self.right_panel = tk.Frame(self.root, padx=6, pady=6)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Style().theme_use('clam')

        # Per-element GUI state
        self.el_vars    = {}   # el_id → dict of tk.Vars
        self.el_widgets = {}   # el_id → dict of widget refs
        self.currently_recording_el = None
        self.timeline_data = []   # list of {el_id: conf} dicts, one per analysis frame
        # Accumulated raw notes per element (for mini canvas across takes)
        self.el_accumulated_notes = {k: [] for k in ELEMENTS}
        self.el_take_count = {k: 0 for k in ELEMENTS}

        self._build_controls()
        self._build_visuals()
        self._animate_roll()
        # Resize window to fit all training columns after layout is complete
        self.root.after(100, self._fit_to_columns)

    def _fit_to_columns(self):
        """Resize the window so all element columns are fully visible."""
        self.root.update_idletasks()
        left_w  = self.left_panel.winfo_reqwidth()
        inner_w = self._train_inner_frame.winfo_reqwidth()
        inner_h = self._train_inner_frame.winfo_reqheight()
        total_w = left_w + inner_w + 40       # +40: right padding + notebook chrome
        total_h = inner_h + 80                # +80: notebook tabs + window title bar
        self.root.geometry(f'{total_w}x{total_h}')

    # ---------------------------------------------------------- left panel

    def _build_controls(self):
        self.status_var = tk.StringVar(value="System Idle")

        tk.Label(self.left_panel,
                 text="1. Select MIDI ports & connect.\n"
                      "2. Go to Training tab — record\n"
                      "   a seed for each gesture.\n"
                      "3. Press Start Analysis & play.",
                 font=('Consolas', 8), fg='#888888', bg=BG,
                 justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        tk.Label(self.left_panel, text="MIDI Input Port:", bg=BG, fg='white').pack(anchor=tk.W)
        self.in_port_var = tk.StringVar()
        ttk.Combobox(self.left_panel, textvariable=self.in_port_var,
                     values=mido.get_input_names() or ['No Inputs Found']
                     ).pack(fill=tk.X, pady=(0, 8))

        tk.Label(self.left_panel, text="MIDI Output Port:", bg=BG, fg='white').pack(anchor=tk.W)
        self.out_port_var = tk.StringVar()
        ttk.Combobox(self.left_panel, textvariable=self.out_port_var,
                     values=mido.get_output_names() or ['No Outputs Found']
                     ).pack(fill=tk.X, pady=(0, 12))

        tk.Button(self.left_panel, text="Connect MIDI", command=self._connect_midi,
                  bg='#444', fg='white').pack(fill=tk.X, pady=(0, 16))

        self.start_btn = tk.Button(
            self.left_panel, text="Start Analysis",
            command=self._toggle_analysis,
            state=tk.DISABLED, bg='#0066cc', fg='white',
            font=('Helvetica', 12, 'bold'))
        self.start_btn.pack(fill=tk.X, pady=(18, 4))

        # Detection status — fixed below the toggle button, wraps within panel width
        tk.Label(self.left_panel, textvariable=self.status_var,
                 font=('Consolas', 9), fg='#00ffcc', bg=BG,
                 wraplength=270, justify=tk.LEFT, anchor='w'
                 ).pack(fill=tk.X, pady=(0, 4))

        tk.Frame(self.left_panel, height=1, bg='#444').pack(fill=tk.X, pady=(10, 4))
        tk.Label(self.left_panel, text='Frame Size (ms):', bg=BG,
                 fg='#cccccc', font=('Consolas', 8)).pack(anchor=tk.W)
        self._frame_size_scale = tk.Scale(
            self.left_panel, from_=250, to=3000, resolution=250,
            orient=tk.HORIZONTAL,
            command=lambda v: self._update_config('frame_size_ms', v),
            bg=BG, fg='white', highlightthickness=0)
        self._frame_size_scale.set(CONFIG['frame_size_ms'])
        self._frame_size_scale.pack(fill=tk.X)

    def _make_slider(self, label, config_key, from_, to, resolution, parent=None):
        p = parent or self.left_panel
        tk.Label(p, text=label, bg=p['bg'], fg='#ccc').pack(anchor=tk.W, pady=(4, 0))
        s = tk.Scale(p, from_=from_, to=to, resolution=resolution, orient=tk.HORIZONTAL,
                     command=lambda v, k=config_key: self._update_config(k, v),
                     bg=p['bg'], fg='white', highlightthickness=0)
        s.set(CONFIG[config_key])
        s.pack(fill=tk.X)

    def _update_config(self, key, val):
        CONFIG[key] = float(val) if ('.' in str(val) or isinstance(CONFIG.get(key), float)) \
                      else int(float(val))

    def _toggle_analysis(self):
        if self.app_controller.analysis_running:
            self.app_controller.stop_analysis()
            self.start_btn.config(text="Start Analysis", bg='#0066cc')
            self.status_var.set("Analysis stopped.")
        else:
            self.app_controller.start_analysis()
            self.start_btn.config(text="Stop Analysis", bg='#992200')

    def _toggle_freeze(self):
        self.piano_roll.frozen = not self.piano_roll.frozen
        if self.piano_roll.frozen:
            self.freeze_btn.config(text='Live', bg='#cc5500')
        else:
            self.freeze_btn.config(text='Freeze', bg='#333333')

    def push_timeline(self, scores):
        """Append a frame's scores and redraw the confidence timeline."""
        self.timeline_data.append(dict(scores))
        if len(self.timeline_data) > 600:   # ~2.5 min at 250 ms/frame
            self.timeline_data.pop(0)
        # Only redraw when the timeline tab is actually visible
        if str(self.notebook.select()) == str(self._tl_frame):
            self._redraw_timeline()

    def _redraw_timeline(self):
        c = self.timeline_canvas
        c.delete('plot')
        w = c.winfo_width()  or 800
        h = c.winfo_height() or 300

        n = len(self.timeline_data)
        if n < 2:
            c.create_text(w // 2, h // 2,
                          text='Waiting for analysis data...',
                          fill='#444', font=('Consolas', 10), tags='plot')
            return

        pad_l, pad_r, pad_t, pad_b = 28, 32, 10, 10
        pw = w - pad_l - pad_r
        ph = h - pad_t - pad_b

        # Horizontal grid lines + confidence axis labels
        for level in (0.25, 0.50, 0.75, 1.00):
            gy = pad_t + (1.0 - level) * ph
            c.create_line(pad_l, gy, w - pad_r, gy, fill='#1e1e1e', tags='plot')
            c.create_text(pad_l - 4, gy, text=f'{int(level * 100)}%',
                          anchor='e', fill='#444', font=('Consolas', 7), tags='plot')

        # One polyline per element
        for el_id, color in ELEMENT_COLORS.items():
            pts = []
            for i, frame_scores in enumerate(self.timeline_data):
                x = pad_l + i * pw / (n - 1)
                y = pad_t + (1.0 - frame_scores.get(el_id, 0.0)) * ph
                pts.append(x)
                pts.append(y)
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=2, tags='plot')
            # Short element ID label pinned to right edge at last-frame confidence
            last_conf = self.timeline_data[-1].get(el_id, 0.0)
            label_y   = pad_t + (1.0 - last_conf) * ph
            c.create_text(w - pad_r + 4, label_y, text=el_id.upper(),
                          anchor='w', fill=color,
                          font=('Consolas', 8, 'bold'), tags='plot')

    def _connect_midi(self):
        if self.app_controller.connect_midi(self.in_port_var.get(), self.out_port_var.get()):
            self.start_btn.config(state=tk.NORMAL)
            self.status_var.set("MIDI connected.")

    # ---------------------------------------------------------- right panel

    def _build_visuals(self):
        self.notebook = ttk.Notebook(self.right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1 — Live Piano Roll (with freeze toolbar)
        roll_frame = tk.Frame(self.notebook, bg='black')
        toolbar = tk.Frame(roll_frame, bg='#111111', pady=2)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(toolbar, text='Piano Roll', font=('Consolas', 8),
                 fg='#555555', bg='#111111').pack(side=tk.LEFT, padx=6)
        self.freeze_btn = tk.Button(
            toolbar, text='Freeze', command=self._toggle_freeze,
            font=('Consolas', 8), bg='#333333', fg='white',
            padx=8, pady=1, relief='flat', bd=0)
        self.freeze_btn.pack(side=tk.RIGHT, padx=4)
        self.piano_roll = PianoRollCanvas(roll_frame)
        self.piano_roll.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(roll_frame, text="Live Piano Roll")

        # Tab 2 — Confidence Timeline
        self._tl_frame = tk.Frame(self.notebook, bg='#0a0a0a')
        self.timeline_canvas = tk.Canvas(self._tl_frame, bg='#0a0a0a', highlightthickness=0)
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True)
        self.timeline_canvas.bind('<Configure>', lambda e: self._redraw_timeline())
        self.notebook.add(self._tl_frame, text="Confidence Timeline")

        # Tab 3 — Elements (training)
        self.train_frame = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.train_frame, text="Elements")
        self._build_training_tab()

        # Tab 4 — Event Log
        log_frame = tk.Frame(self.notebook)
        self.log_text = tk.Text(log_frame, height=30, bg='#1e1e1e',
                                fg='#00ffcc', font=('Consolas', 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(log_frame, text="Event Log")

    # --------------------------------------------------------- training tab

    def _build_training_tab(self):
        # Scrollable horizontal container
        outer = tk.Frame(self.train_frame, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        hbar = ttk.Scrollbar(outer, orient='horizontal')
        hbar.pack(side=tk.BOTTOM, fill=tk.X)

        self._train_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0,
                                       xscrollcommand=hbar.set)
        self._train_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        hbar.config(command=self._train_canvas.xview)

        inner = tk.Frame(self._train_canvas, bg=BG)
        self._train_canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>',
                   lambda e: self._train_canvas.configure(
                       scrollregion=self._train_canvas.bbox('all')))
        self._train_inner_frame = inner

        for el_id in TRAINABLE:
            self._build_element_column(inner, el_id)

    def _build_element_column(self, parent, el_id):
        el_name  = ELEMENTS[el_id]
        el_color = ELEMENT_COLORS.get(el_id, '#ffffff')

        # Per-element tk vars
        self.el_vars[el_id] = {
            'variations':  tk.IntVar(value=100),
            'noise_spread': tk.DoubleVar(value=0.05),
            'stat_seed':   tk.StringVar(value='No seed recorded'),
            'stat_synth':  tk.StringVar(value='Synth: not generated'),
            'stat_model':  tk.StringVar(value='Model: default profile'),
        }
        vs = self.el_vars[el_id]

        col = tk.LabelFrame(parent, text=f' {el_id.upper()}  {el_name} ',
                            font=('Helvetica', 10, 'bold'),
                            fg=el_color, bg=BG_COL,
                            bd=2, relief='groove',
                            padx=6, pady=6)
        col.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=8, ipadx=2)

        # Gesture hint
        tk.Label(col, text=ELEMENT_HINTS.get(el_id, ''),
                 font=('Consolas', 8), fg='#666666', bg=BG_COL,
                 justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))

        # Status row
        status_row = tk.Frame(col, bg=BG_COL)
        status_row.pack(fill=tk.X, pady=(0, 6))
        dot = tk.Label(status_row, text='  ', bg='#555555', width=2)
        dot.pack(side=tk.LEFT, padx=(0, 6))
        status_lbl = tk.Label(status_row, text='Idle', font=('Consolas', 9),
                              fg='#888', bg=BG_COL)
        status_lbl.pack(side=tk.LEFT)

        # Mini MIDI canvas
        mini = tk.Canvas(col, width=170, height=80, bg='#111111',
                         highlightthickness=1, highlightbackground='#333')
        mini.pack(pady=(0, 6))
        mini.create_text(85, 40, text='no seed', fill='#444',
                         font=('Consolas', 8), tags='placeholder')

        # Stats
        tk.Label(col, textvariable=vs['stat_seed'],  font=('Consolas', 8),
                 fg='#aaa', bg=BG_COL, anchor='w').pack(fill=tk.X)
        tk.Label(col, textvariable=vs['stat_synth'], font=('Consolas', 8),
                 fg='#aaa', bg=BG_COL, anchor='w').pack(fill=tk.X)
        tk.Label(col, textvariable=vs['stat_model'], font=('Consolas', 8),
                 fg='#aaa', bg=BG_COL, anchor='w').pack(fill=tk.X, pady=(0, 8))

        # Record + Clear buttons
        btn_row = tk.Frame(col, bg=BG_COL)
        btn_row.pack(fill=tk.X, pady=(0, 8))
        rec_btn = tk.Button(btn_row, text='REC',
                            font=('Helvetica', 10, 'bold'),
                            bg='#880000', fg='white',
                            command=lambda e=el_id: self._toggle_recording(e))
        rec_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        clr_btn = tk.Button(btn_row, text='CLR',
                            font=('Helvetica', 8),
                            bg='#444444', fg='#aaaaaa',
                            command=lambda e=el_id: self._clear_seed(e))
        clr_btn.pack(side=tk.LEFT, padx=(4, 0))

        # Sliders
        tk.Label(col, text='Variations:', font=('Consolas', 8),
                 fg='#ccc', bg=BG_COL).pack(anchor=tk.W)
        tk.Scale(col, variable=vs['variations'], from_=10, to=500, resolution=10,
                 orient=tk.HORIZONTAL, bg=BG_COL, fg='white',
                 highlightthickness=0, length=170).pack(fill=tk.X)

        tk.Label(col, text='Noise Spread:', font=('Consolas', 8),
                 fg='#ccc', bg=BG_COL).pack(anchor=tk.W, pady=(6, 0))
        tk.Scale(col, variable=vs['noise_spread'], from_=0.01, to=0.20,
                 resolution=0.01, orient=tk.HORIZONTAL, bg=BG_COL, fg='white',
                 highlightthickness=0, length=170).pack(fill=tk.X)

        # ---- Model Parameters section ----
        tk.Frame(col, height=1, bg='#444').pack(fill=tk.X, pady=(12, 4))
        tk.Label(col, text='MODEL PARAMETERS', font=('Consolas', 8, 'bold'),
                 fg=el_color, bg=BG_COL).pack(anchor=tk.W, pady=(0, 4))
        self._make_el_param_slider(col, el_id, 'Threshold:', 'affinity_threshold', 0.10, 0.90, 0.05)
        self._make_el_param_slider(col, el_id, 'Sigma:',     'affinity_sigma',     0.05, 0.60, 0.01)
        self._make_el_param_slider(col, el_id, 'Boost:',     'energy_boost',       0.10, 1.00, 0.05)
        self._make_el_param_slider(col, el_id, 'Decay:',     'energy_decay',       0.01, 0.10, 0.01)

        self.el_widgets[el_id] = {
            'col':        col,
            'dot':        dot,
            'status_lbl': status_lbl,
            'mini':       mini,
            'rec_btn':    rec_btn,
        }

    def _make_el_param_slider(self, parent, el_id, label, param_key, from_, to, resolution):
        tk.Label(parent, text=label, font=('Consolas', 8),
                 fg='#aaa', bg=BG_COL).pack(anchor=tk.W, pady=(3, 0))
        s = tk.Scale(parent, from_=from_, to=to, resolution=resolution,
                     orient=tk.HORIZONTAL, bg=BG_COL, fg='white',
                     highlightthickness=0, length=170,
                     command=lambda v, e=el_id, k=param_key:
                         ELEMENT_PARAMS[e].__setitem__(k, float(v)))
        s.set(ELEMENT_PARAMS[el_id][param_key])
        s.pack(fill=tk.X)

    def _toggle_recording(self, el_id):
        """Handle REC button press for a specific element column."""
        try:
            self._do_toggle_recording(el_id)
        except Exception as e:
            log.error(f"REC toggle failed: {e}", exc=True)
            # Sync GUI state back to controller state to prevent desync
            self._sync_recording_state()

    def _sync_recording_state(self):
        """Re-sync GUI recording indicators with the controller's actual state."""
        ac = self.app_controller
        if not ac.recording:
            # Controller isn't recording — reset all GUI recording state
            if self.currently_recording_el is not None:
                self._set_col_recording(self.currently_recording_el, False)
            self.currently_recording_el = None
        else:
            # Controller IS recording — make sure GUI reflects it
            el = ac.recording_element
            if el and el != self.currently_recording_el:
                if self.currently_recording_el is not None:
                    self._set_col_recording(self.currently_recording_el, False)
                self._set_col_recording(el, True)
                self.currently_recording_el = el

    def _do_toggle_recording(self, el_id):
        ac = self.app_controller
        prev = self.currently_recording_el

        if prev is not None and prev != el_id:
            # Stop whichever element is currently recording
            ac.toggle_recording(
                prev,
                self.el_vars[prev]['variations'].get(),
                self.el_vars[prev]['noise_spread'].get(),
            )
            self._set_col_recording(prev, False)
            self.currently_recording_el = None

        if prev == el_id:
            # Stop this element
            ac.toggle_recording(
                el_id,
                self.el_vars[el_id]['variations'].get(),
                self.el_vars[el_id]['noise_spread'].get(),
            )
            self._set_col_recording(el_id, False)
            self.currently_recording_el = None
        else:
            # Start this element
            ac.toggle_recording(
                el_id,
                self.el_vars[el_id]['variations'].get(),
                self.el_vars[el_id]['noise_spread'].get(),
            )
            self._set_col_recording(el_id, True)
            self.currently_recording_el = el_id

    def _set_col_recording(self, el_id, is_recording):
        ws = self.el_widgets[el_id]
        if is_recording:
            ws['rec_btn'].config(text='STOP', bg='#cc5500')
            ws['dot'].config(bg='#ff2200')
            ws['status_lbl'].config(text='Recording...', fg='#ff6600')
            self._rec_poll_id = self.root.after(200, self._poll_recording, el_id)
        else:
            ws['rec_btn'].config(text='REC', bg='#880000')
            ws['dot'].config(bg='#555555')
            ws['status_lbl'].config(text='Idle', fg='#888')
            if hasattr(self, '_rec_poll_id') and self._rec_poll_id:
                self.root.after_cancel(self._rec_poll_id)
                self._rec_poll_id = None

    def _poll_recording(self, el_id):
        """Update the status label with live note count during recording."""
        ac = self.app_controller
        if not ac.recording or el_id not in self.el_widgets:
            return
        ws = self.el_widgets[el_id]
        n_notes = len(ac.recording_raw_notes)
        n_frames = len(ac.recording_frames)
        elapsed = round(time.perf_counter() - ac.recording_start_t, 1)
        ws['status_lbl'].config(
            text=f'REC {elapsed}s  {n_notes} notes  {n_frames} frames',
            fg='#ff6600')
        # Blink the dot
        dot_color = '#ff2200' if int(elapsed * 2) % 2 == 0 else '#661100'
        ws['dot'].config(bg=dot_color)
        self._rec_poll_id = self.root.after(200, self._poll_recording, el_id)

    def update_training_ui(self, el_id, raw_notes, total_frames, synth_count):
        """Called by main.py after a recording iteration stops and templates are forged."""
        if el_id not in self.el_vars:
            return
        vs = self.el_vars[el_id]
        ws = self.el_widgets[el_id]
        el_color = ELEMENT_COLORS.get(el_id, '#ffffff')

        # Accumulate notes across takes for the mini canvas
        self.el_accumulated_notes[el_id].extend(raw_notes)
        self.el_take_count[el_id] += 1
        takes = self.el_take_count[el_id]

        vs['stat_seed'].set(f'Seed: {total_frames} frames ({takes} take{"s" if takes != 1 else ""})')
        vs['stat_synth'].set(f'Synth: {synth_count} variations forged')
        vs['stat_model'].set('Model: trained on human seed')

        ws['dot'].config(bg=el_color)
        ws['status_lbl'].config(text='Trained', fg=el_color)

        # Show ALL accumulated notes, not just the last take
        self._draw_mini_midi(el_id, self.el_accumulated_notes[el_id])

    def _clear_seed(self, el_id):
        """Clear all recorded seed data for el_id and reset to default profile."""
        ac = self.app_controller
        ac.dtw.forge.clear_seed(el_id)
        vs = self.el_vars[el_id]
        ac.dtw.update_element(el_id,
                               int(vs['variations'].get()),
                               float(vs['noise_spread'].get()))
        ws = self.el_widgets[el_id]
        vs['stat_seed'].set('No seed recorded')
        vs['stat_synth'].set('Synth: not generated')
        vs['stat_model'].set('Model: default profile')
        ws['dot'].config(bg='#555555')
        ws['status_lbl'].config(text='Cleared', fg='#888888')
        # Reset accumulated take data
        self.el_accumulated_notes[el_id] = []
        self.el_take_count[el_id] = 0
        mini = ws['mini']
        mini.delete('all')
        mini.create_text(85, 40, text='no seed', fill='#444',
                         font=('Consolas', 8), tags='placeholder')
        log.info(f'Seed cleared for: {el_id.upper()} — reverting to default profile.', element=el_id)

    def _draw_mini_midi(self, el_id, raw_notes):
        canvas = self.el_widgets[el_id]['mini']
        canvas.delete('all')
        el_color = ELEMENT_COLORS.get(el_id, '#ffffff')

        if not raw_notes:
            canvas.create_text(85, 40, text='no notes', fill='#444',
                               font=('Consolas', 8))
            return

        w = canvas.winfo_width()  or 170
        h = canvas.winfo_height() or 80
        pad = 6

        pitches = [n[0] for n in raw_notes]
        times   = [n[1] for n in raw_notes]

        t_min, t_max = min(times), max(times)
        p_min, p_max = min(pitches), max(pitches)
        t_range = max(t_max - t_min, 0.001)
        p_range = max(p_max - p_min, 1)

        for pitch, ts in raw_notes:
            x = int((ts - t_min) / t_range * (w - pad * 2)) + pad
            y = int((1.0 - (pitch - p_min) / p_range) * (h - pad * 2)) + pad
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                               fill=el_color, outline='')

    # --------------------------------------------------------- piano roll I/O

    def add_note_visual(self, note, velocity, is_ai=False, frame_id=None):
        self.root.after(0, self.piano_roll.draw_note,
                        note, velocity, is_ai, frame_id)

    def release_note_visual(self, note, is_ai=False):
        self.root.after(0, self.piano_roll.release_note, note, is_ai)

    def resolve_frame_visual(self, frame_id, active_elements):
        self.root.after(0, self.piano_roll.resolve_frame, frame_id, active_elements)

    def log_msg(self, msg):
        self.root.after(0, lambda: [
            self.log_text.insert(tk.END, msg + '\n'),
            self.log_text.see(tk.END)
        ])

    def _animate_roll(self):
        self.piano_roll.update_roll()
        self.root.after(30, self._animate_roll)
