# ml/classifier.py
import numpy as np
from ml.forge import GestureForge
from core.config import (
    ELEMENTS, CONFIG, ELEMENT_PARAMS,
    DEFAULT_CENTROIDS, AFFINITY_WEIGHTS, EMA_ALPHAS, MUTUAL_EXCLUSION
)
from core.gestalt import extract_micro_gestalt


class GestaltAffinityScorer:
    """
    Affinity-based multi-label gesture scorer for polyphonic piano playing.

    Each element uses its own temporal window (frame_size_ms) to compute the
    8D gestalt vector, allowing gestures with different natural timescales
    to be detected independently — e.g. a 150ms window for instantaneous
    chords vs. a 500ms window for oscillation patterns.

    Detection pipeline per hop:
      1. For each element, extract an 8D gestalt vector from that element's
         configured time window of raw MIDI note data.
      2. Compute weighted Gaussian affinity between the vector and the
         element's profile (centroid in feature space).
      3. Apply per-element EMA smoothing (alphas calibrated for 8 updates/sec).
      4. Apply mutual-exclusion logic to suppress acoustically contradictory pairs.
      5. Return the full {element_id: confidence} dict — all values, not just winners.
    """

    def __init__(self):
        self.forge = GestureForge()
        self.templates = {}    # time-series templates (kept for potential future use)
        self.profiles = {}     # (8,) feature profile per element — the affinity target
        self._ema = {k: 0.0 for k in ELEMENTS}
        self._last_vectors = {}  # populated by _score_affinity for diagnostics

        self.load_all_from_forge()

    def load_all_from_forge(self):
        for el_id in ELEMENTS:
            self.update_element(el_id, CONFIG['variations'], CONFIG['noise_spread'])

    def update_element(self, element_id, num_vars, spread):
        """Re-forge templates and recompute the affinity profile for one element."""
        templates = self.forge.forge_variations(element_id, int(num_vars), spread)
        self.templates[element_id] = templates

        if self.forge.seeds.get(element_id):
            # Human seed recorded — derive profile as mean over all frames x all variations
            arr = np.array(templates, dtype=float)   # (num_vars, n_frames, 8)
            self.profiles[element_id] = arr.mean(axis=(0, 1))  # -> (8,)
        else:
            # No training data yet — use the musically-informed hardcoded default
            self.profiles[element_id] = np.array(DEFAULT_CENTROIDS[element_id], dtype=float)

    def score_all(self, notes_with_times=None, completed_durations=None, current_time=None):
        """
        Score all elements against their per-element time windows of raw MIDI data.

        Args:
            notes_with_times: list of (pitch, timestamp) tuples, covering at least
                              the longest element window. Pass None for legacy
                              push_frame-style usage (returns current EMA state).
            completed_durations: list of (timestamp_of_noteoff, duration) tuples.
            current_time: float, the current timestamp for windowing.

        Returns:
            dict with keys:
                'scores': {element_id: confidence} — post-EMA, post-mutual-exclusion
                'raw_scores': {element_id: float} — pre-EMA raw affinity/chord scores
                'vectors': {element_id: list[float]} — per-element 8D gestalt vectors
                'silence_gated': bool — True if the silence gate fired this hop
                'suppressed': list[str] — element IDs suppressed by mutual exclusion
        """
        result = {
            'scores': dict(self._ema),
            'raw_scores': {},
            'vectors': {},
            'silence_gated': False,
            'suppressed': [],
        }

        if notes_with_times is None or current_time is None:
            return result

        # Silence gate: check if there are any recent notes (within 1 second)
        one_sec_ago = current_time - 1.0
        recent_notes = [n for n in notes_with_times if n[1] >= one_sec_ago]
        if len(recent_notes) < 2:
            for label in self._ema:
                self._ema[label] *= 0.50
            result['scores'] = dict(self._ema)
            result['silence_gated'] = True
            return result

        durations = completed_durations or []

        # Compute raw score for each element using its own window and scoring mode
        raw = {}
        for label, profile in self.profiles.items():
            params = ELEMENT_PARAMS[label]
            scoring_mode = params.get('scoring_mode', 'affinity')

            if scoring_mode == 'chord':
                raw[label] = self._score_chord(notes_with_times, current_time, label)
            else:
                raw[label] = self._score_affinity(notes_with_times, durations,
                                                  current_time, label, profile)

        result['raw_scores'] = dict(raw)
        result['vectors'] = {k: v.tolist() for k, v in self._last_vectors.items()}

        # Apply per-element EMA smoothing
        for label, score in raw.items():
            alpha = EMA_ALPHAS[label]
            self._ema[label] = alpha * score + (1.0 - alpha) * self._ema[label]

        scores = dict(self._ema)

        # Mutual exclusion: suppress the lower-confidence partner in contradictory pairs.
        # Decay the suppressed element's EMA directly to prevent hidden accumulation
        # that would cause jittery activation when dominance flips.
        for el_a, el_b in MUTUAL_EXCLUSION:
            if el_a in scores and el_b in scores:
                if scores[el_a] < scores[el_b]:
                    scores[el_a] = 0.0
                    self._ema[el_a] *= 0.55
                    result['suppressed'].append(el_a)
                else:
                    scores[el_b] = 0.0
                    self._ema[el_b] *= 0.55
                    result['suppressed'].append(el_b)

        result['scores'] = scores
        return result

    # -------------------------------------------------------- scoring backends

    def _score_affinity(self, notes_with_times, durations, current_time, label, profile):
        """Standard gestalt-affinity scoring: 8D vector distance to centroid."""
        frame_ms = ELEMENT_PARAMS[label].get('frame_size_ms', CONFIG['frame_size_ms'])
        frame_sec = frame_ms / 1000.0
        window_start = current_time - frame_sec

        el_notes = [(p, t) for p, t in notes_with_times if t >= window_start]
        el_durations = [d for ts, d in durations if ts >= window_start]

        v = extract_micro_gestalt(el_notes, el_durations, frame_ms)
        self._last_vectors[label] = v

        sigma = float(ELEMENT_PARAMS[label]['affinity_sigma'])
        denom = 2.0 * sigma * sigma
        w = np.array(AFFINITY_WEIGHTS[label], dtype=float)
        w /= w.sum()
        diff_sq = (v - profile) ** 2
        weighted_dist = float(np.dot(w, diff_sq))
        return float(np.exp(-weighted_dist / denom))

    @staticmethod
    def _score_chord(notes_with_times, current_time, label):
        """Simple chord detector: count near-simultaneous notes in the window.

        Returns a raw confidence proportional to the size of the largest
        chord cluster found.  A cluster is a group of notes whose successive
        onsets are each within ``chord_onset_ms`` of the previous note.
        """
        params = ELEMENT_PARAMS[label]
        frame_ms = params.get('frame_size_ms', CONFIG['frame_size_ms'])
        window_start = current_time - frame_ms / 1000.0
        onset_sec = params.get('chord_onset_ms', 30) / 1000.0
        min_notes = int(params.get('chord_min_notes', 3))

        el_notes = [n for n in notes_with_times if n[1] >= window_start]
        if len(el_notes) < min_notes:
            return 0.0

        # Find the largest cluster of near-simultaneous onsets
        times = sorted(n[1] for n in el_notes)
        best = 1
        run = 1
        for i in range(1, len(times)):
            if times[i] - times[i - 1] <= onset_sec:
                run += 1
            else:
                best = max(best, run)
                run = 1
        best = max(best, run)

        if best < min_notes:
            return 0.0

        # Scale: min_notes → 0.5, 2×min_notes → 1.0
        return min(1.0, best / (min_notes * 2.0))
