# main.py
import os
import tkinter as tk
import threading
import time
from collections import defaultdict
from core.config import CONFIG, ELEMENTS, ELEMENT_PARAMS
from core.gestalt import extract_micro_gestalt
from core.logger import log
from midi.io import MidiIO, GhostNoteFilter
from midi.playback import PlaybackEngine
from ml.classifier import GestaltAffinityScorer
from agents.parasite import ParasiteSwarm
from gui.app import AbeyanceGUI

SESSION_DIR = 'sessions'

class AbeyanceApp:
    def __init__(self):
        self.root = tk.Tk()

        self.dtw          = GestaltAffinityScorer()
        self.ghost_filter = GhostNoteFilter(CONFIG['ghost_echo_ttl'])

        self.midi_io  = None
        self.playback = None
        self.swarm    = None

        self.current_frame_notes = []
        self.lock             = threading.Lock()
        self.analysis_running = False

        # Recording state
        self.recording           = False
        self.recording_element        = None
        self.recording_frames         = []
        self.recording_frame_times    = []   # (t_start, t_end) per frame
        self.recording_raw_notes      = []   # (pitch, timestamp) events during recording
        self.recording_raw_durations  = []   # (timestamp_of_noteoff, duration) during recording
        self.recording_start_t        = 0.0

        # Note-duration tracking for articulation feature
        # pitch → [note-on timestamps] (stack so repeated pitches don't collide)
        self.note_on_times        = defaultdict(list)
        self.completed_durations  = []  # durations collected this frame

        self.current_frame_id = 0

        # Session log for post-performance analysis
        self.session_log   = []
        self.session_start = 0.0

        # Init GUI last, passing self to act as the controller
        self.gui = AbeyanceGUI(self.root, self)

        # Wire logger to GUI event log
        log.set_gui_callback(self.gui.log_msg)

        # Graceful shutdown on window close
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

    # ------------------------------------------------------------------ MIDI

    def connect_midi(self, in_port_name, out_port_name):
        try:
            # Close existing connections before creating new ones
            self._close_midi()

            self.midi_io = MidiIO(
                in_port_name, out_port_name, self.ghost_filter,
                self._on_midi_in, self._on_cc_in,
                note_off_callback=self._on_midi_note_off,
            )
            self.playback = PlaybackEngine(self.midi_io)

            # Route AI note visuals via callback (no monkey-patching)
            def _on_ai_note(note, velocity, duration_sec, delay_sec):
                delay_ms = int(delay_sec * 1000)
                dur_ms   = int(duration_sec * 1000)
                self.root.after(delay_ms,
                                self.gui.piano_roll.draw_note,
                                note, velocity, True, None)
                self.root.after(delay_ms + dur_ms,
                                self.gui.piano_roll.release_note,
                                note, True)
            self.playback.on_note_scheduled.append(_on_ai_note)

            self.swarm = ParasiteSwarm(ELEMENTS, self.playback)
            return True
        except Exception as e:
            log.error(f"Failed to connect MIDI: {e}", exc=True)
            return False

    def _close_midi(self):
        """Close existing MIDI ports and stop the swarm."""
        if self.swarm:
            self.swarm.running = False
            self.swarm = None
        if self.playback:
            self.playback.cancel_all()
            self.playback = None
        if self.midi_io:
            if self.midi_io.inport:
                try:
                    self.midi_io.inport.close()
                except Exception:
                    pass
            if self.midi_io.outport:
                try:
                    self.midi_io.outport.close()
                except Exception:
                    pass
            self.midi_io = None

    def _on_midi_in(self, note, velocity):
        now = time.perf_counter()
        self.gui.add_note_visual(note, velocity, is_ai=False,
                                 frame_id=self.current_frame_id)
        with self.lock:
            self.current_frame_notes.append((note, velocity, now))
            self.note_on_times[note].append(now)
            if self.recording:
                self.recording_raw_notes.append((note, now))

    def _on_midi_note_off(self, note):
        now = time.perf_counter()
        self.gui.release_note_visual(note)
        with self.lock:
            if self.note_on_times[note]:
                onset = self.note_on_times[note].pop(0)  # FIFO: oldest note-on first
                duration = now - onset
                self.completed_durations.append((now, duration))
                if self.recording:
                    self.recording_raw_durations.append((now, duration))

    def _on_cc_in(self, value):
        is_down = value > 63
        if self.swarm:
            self.swarm.set_pedal(is_down)

    def _shutdown(self):
        """Graceful shutdown: stop analysis, close MIDI ports, destroy window."""
        self.analysis_running = False
        self._close_midi()
        log.info("Shutting down.")
        self.root.destroy()

    # --------------------------------------------------------- controller API

    def clear_element_seed(self, el_id, variations, noise_spread):
        """Clear recorded seed data for an element and revert to default profile."""
        self.dtw.forge.clear_seed(el_id)
        self.dtw.update_element(el_id, int(variations), float(noise_spread))

    def train_element(self, el_id, variations, noise_spread):
        """Re-forge synthetic data and retrain the model for one element."""
        n_vars = int(variations)
        n_spread = float(noise_spread)
        self.dtw.update_element(el_id, n_vars, n_spread)
        total_seed = len(self.dtw.forge.seeds.get(el_id, []))
        log.info(
            f"Trained {ELEMENTS[el_id]}: {total_seed} seed frames "
            f"→ {n_vars} synthetic variations (σ={n_spread})",
            element=el_id)
        return n_vars

    # --------------------------------------------------------------- analysis

    def start_analysis(self):
        if not self.analysis_running and self.midi_io:
            self.analysis_running = True
            self.session_log   = []
            self.session_start = time.perf_counter()
            # Flush any notes that accumulated before analysis started so they
            # don't collapse into frame 0 and poison the EMA for seconds.
            with self.lock:
                self.current_frame_notes = []
                self.completed_durations = []
            threading.Thread(target=self._analysis_loop, daemon=True).start()

    def stop_analysis(self):
        self.analysis_running = False
        if self.playback:
            self.playback.cancel_all()
        self._save_session_log()

    def _save_session_log(self):
        with self.lock:
            log_snapshot = list(self.session_log)
            self.session_log = []
        if not log_snapshot:
            return
        import json, datetime
        os.makedirs(SESSION_DIR, exist_ok=True)
        ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(SESSION_DIR, f'session_{ts}.json')
        try:
            with open(path, 'w') as f:
                json.dump(log_snapshot, f, indent=2)
            log.info(f'Session saved → {path}  ({len(log_snapshot)} frames)')
            self.root.after(0, self.gui.status_var.set, f'Saved: {path}')
        except Exception as e:
            log.error(f'Could not save session log: {e}', exc=True)

    def _analysis_loop(self):
        hop_sec = CONFIG['hop_size_ms'] / 1000.0
        # Buffer must cover the longest per-element window
        max_window_ms = max(
            ELEMENT_PARAMS[el].get('frame_size_ms', CONFIG['frame_size_ms'])
            for el in ELEMENTS)
        max_window_sec = max_window_ms / 1000.0

        while self.analysis_running:
            start_time = time.perf_counter()

            frame_id = self.current_frame_id
            self.current_frame_id += 1

            with self.lock:
                # Prune old entries (>2× max window) to bound memory
                cutoff = start_time - 2 * max_window_sec
                self.current_frame_notes = [n for n in self.current_frame_notes
                                            if n[2] >= cutoff]
                self.completed_durations = [(ts, d) for ts, d in self.completed_durations
                                            if ts >= cutoff]
                # Snapshot all recent notes for the classifier
                all_notes = list(self.current_frame_notes)
                all_durations = list(self.completed_durations)

            # Split frame data: (pitch, timestamp) for gestalt, (pitch, velocity) for swarm
            notes_for_gestalt = [(n[0], n[2]) for n in all_notes]
            notes_for_swarm   = [(n[0], n[1]) for n in all_notes
                                 if n[2] >= start_time - max_window_sec]
            durations_for_gestalt = [(ts, d) for ts, d in all_durations]

            # Per-element scoring: classifier extracts its own window per element
            scores = self.dtw.score_all(notes_for_gestalt, durations_for_gestalt, start_time)

            # Log every frame for post-performance analysis
            t_rel = round(time.perf_counter() - self.session_start, 3)
            log_entry = {
                't':      t_rel,
                'frame':  frame_id,
                'scores': {k: round(v, 3) for k, v in scores.items()},
                'notes':  [n[0] for n in all_notes if n[2] >= start_time - max_window_sec],
            }
            with self.lock:
                self.session_log.append(log_entry)
            self.root.after(0, self.gui.push_timeline, scores)

            active = {lbl: c for lbl, c in scores.items()
                      if c >= ELEMENT_PARAMS[lbl]['affinity_threshold']}

            self.gui.resolve_frame_visual(frame_id, active)

            if active:
                if self.swarm:
                    for label, confidence in active.items():
                        self.swarm.feed(label, notes_for_swarm, weight=confidence)

                sorted_active = sorted(active.items(), key=lambda x: x[1], reverse=True)
                status_msg = '  '.join(f'{ELEMENTS[l]} {c:.2f}' for l, c in sorted_active)
                log.debug(status_msg)
                self.gui.root.after(0, self.gui.status_var.set, status_msg)

            elapsed = time.perf_counter() - start_time
            time.sleep(max(0, hop_sec - elapsed))

    # -------------------------------------------------------------- recording

    def toggle_recording(self, element_id, variations=None, noise_spread=None):
        """
        Toggle human seed recording for element_id.
        Returns True if recording just started, False if it just stopped.
        variations / noise_spread override CONFIG defaults when forging.
        """
        if not self.recording:
            self.recording                = True
            self.recording_element        = element_id
            self.recording_frames         = []
            self.recording_frame_times    = []   # (t_start, t_end) per frame
            self.recording_raw_notes      = []
            self.recording_raw_durations  = []
            self.recording_start_t        = time.perf_counter()
            log.info(f"Recording started for: {ELEMENTS[element_id]}", element=element_id)
            return True
        else:
            self.recording = False
            frames        = self.recording_frames
            frame_times   = self.recording_frame_times
            raw_notes     = self.recording_raw_notes
            raw_durations = self.recording_raw_durations
            target        = self.recording_element
            self.recording_frames        = []
            self.recording_frame_times   = []
            self.recording_raw_notes     = []
            self.recording_raw_durations = []
            self.recording_element       = None

            n_vars   = int(variations)   if variations   is not None else CONFIG['variations']
            n_spread = float(noise_spread) if noise_spread is not None else CONFIG['noise_spread']

            # Always recompute gestalt frames from raw notes using the element's
            # own frame_size_ms.  This ensures the training profile matches the
            # temporal window used during live detection.
            frames = []
            frame_times = []
            if raw_notes:
                el_frame_ms = ELEMENT_PARAMS[target].get('frame_size_ms', CONFIG['frame_size_ms'])
                hop_sec   = CONFIG['hop_size_ms'] / 1000.0
                frame_sec = el_frame_ms / 1000.0
                t = raw_notes[0][1]
                t_end = raw_notes[-1][1] + frame_sec
                while t < t_end:
                    chunk = [(p, ts) for p, ts in raw_notes if t <= ts < t + frame_sec]
                    dur_chunk = [d for ts_off, d in raw_durations if t <= ts_off < t + frame_sec]
                    frames.append(extract_micro_gestalt(chunk, dur_chunk, el_frame_ms))
                    frame_times.append((t, t + frame_sec))
                    t += hop_sec

            # Strip near-silent frames (density < 0.05 ≈ fewer than 2 notes per 250ms).
            # Silence before/after/between gestures drags the centroid toward zero.
            total_before = len(frames)
            kept = [(f, ft) for f, ft in zip(frames, frame_times)
                    if float(f[0]) >= 0.05]
            if kept:
                frames, frame_times = zip(*kept)
                frames = list(frames)
                frame_times = list(frame_times)
            else:
                frames, frame_times = [], []
            stripped = total_before - len(frames)

            # Filter raw_notes to only those within surviving frame windows,
            # so the mini canvas accurately reflects the training data.
            surviving_notes = []
            for pitch, ts in raw_notes:
                for t_start, t_end in frame_times:
                    if t_start <= ts < t_end:
                        surviving_notes.append((pitch, ts))
                        break

            if frames:
                frame_list = [v.tolist() for v in frames]
                self.dtw.forge.add_human_seed(target, frame_list)
                total_seed_frames = len(self.dtw.forge.seeds.get(target, []))
                strip_msg = f' ({stripped} silent frames removed)' if stripped else ''
                log.info(
                    f"+{len(frames)} frames → {ELEMENTS[target]}{strip_msg} "
                    f"| seed total: {total_seed_frames} frames",
                    element=target)
                self.gui.update_recording_ui(target, surviving_notes, total_seed_frames)
            else:
                log.warn(
                    f"No active frames captured ({stripped} silent frames removed) "
                    f"— play more densely, or the entire recording was silence.")
            return False


if __name__ == "__main__":
    app = AbeyanceApp()
    app.root.mainloop()
