# ml/classifier.py
import numpy as np
from ml.forge import GestureForge
from core.config import (
    ELEMENTS, CONFIG, ELEMENT_PARAMS,
    DEFAULT_CENTROIDS, AFFINITY_WEIGHTS, EMA_ALPHAS, MUTUAL_EXCLUSION
)


class HybridGestaltDTW:
    """
    Affinity-based multi-label gesture scorer for polyphonic piano playing.

    Rather than sequential DTW pattern matching (which requires isolating a single
    gesture), this scorer computes per-element feature-space proximity on every 250ms
    frame. Multiple elements can score above threshold simultaneously, allowing the
    system to detect overlapping gestures — e.g. dense left-hand chords (Element B)
    while the right hand makes spatial leaps (Element C).

    Detection pipeline per frame:
      1. Compute weighted Gaussian affinity between the live 6D vector and each
         element's profile (centroid collapsed to a single point in feature space).
      2. Apply per-element EMA smoothing (fast alpha for transient gestures,
         slow alpha for sustained states).
      3. Apply mutual-exclusion logic to suppress acoustically contradictory pairs.
      4. Return the full {element_id: confidence} dict — all values, not just winners.
    """

    def __init__(self):
        self.forge = GestureForge()
        self.templates = {}    # time-series templates (kept for potential future use)
        self.profiles = {}     # (6,) feature profile per element — the affinity target
        self.rolling_window = []
        self._ema = {k: 0.0 for k in ELEMENTS if k != 'f'}

        self.load_all_from_forge()

    def load_all_from_forge(self):
        for el_id in ELEMENTS:
            if el_id == 'f':
                continue
            self.update_element(el_id, CONFIG['variations'], CONFIG['noise_spread'])

    def update_element(self, element_id, num_vars, spread):
        """Re-forge templates and recompute the affinity profile for one element."""
        templates = self.forge.forge_variations(element_id, int(num_vars), spread)
        self.templates[element_id] = templates

        if self.forge.seeds.get(element_id):
            # Human seed recorded — derive profile as mean over all frames × all variations
            arr = np.array(templates, dtype=float)   # (num_vars, n_frames, 6)
            self.profiles[element_id] = arr.mean(axis=(0, 1))  # → (6,)
        else:
            # No training data yet — use the musically-informed hardcoded default
            self.profiles[element_id] = np.array(DEFAULT_CENTROIDS[element_id], dtype=float)

    def push_frame(self, vector_6d):
        self.rolling_window.append(np.asarray(vector_6d, dtype=float))
        if len(self.rolling_window) > 4:   # ~1 second of history for note-gate check
            self.rolling_window.pop(0)

    def score_all(self):
        """
        Score all elements against the current frame. Returns {element_id: confidence}.

        Multiple elements can simultaneously exceed CONFIG['affinity_threshold'],
        which is the mechanism that enables multi-gesture detection in dense playing.
        """
        if not self.rolling_window:
            return dict(self._ema)

        # Note-gate: don't inject new scores during true silence between phrases.
        # Density < 0.02 means ~0 notes per 250ms frame averaged over 2 frames.
        # This threshold is intentionally low so that sparse pointillist playing
        # (1 note/frame = density ~0.04) still passes through to score element g.
        recent_density = float(np.mean([v[0] for v in self.rolling_window[-2:]]))
        if recent_density < 0.02:
            # Silence: decay EMA aggressively so phantom activations don't
            # persist across multiple frames after notes stop.
            for label in self._ema:
                self._ema[label] *= 0.25
            return dict(self._ema)

        v = self.rolling_window[-1]

        # Compute raw affinity for each element using its own sigma
        raw = {}
        for label, profile in self.profiles.items():
            sigma = float(ELEMENT_PARAMS[label]['affinity_sigma'])
            denom = 2.0 * sigma * sigma
            w = np.array(AFFINITY_WEIGHTS[label], dtype=float)
            w /= w.sum()  # normalize so the weighted distance is interpretable
            diff_sq = (v - profile) ** 2
            weighted_dist = float(np.dot(w, diff_sq))
            raw[label] = float(np.exp(-weighted_dist / denom))

        # Apply per-element EMA smoothing
        for label, score in raw.items():
            alpha = EMA_ALPHAS[label]
            self._ema[label] = alpha * score + (1.0 - alpha) * self._ema[label]

        scores = dict(self._ema)

        # Mutual exclusion: suppress the lower-confidence partner in contradictory pairs
        for el_a, el_b in MUTUAL_EXCLUSION:
            if el_a in scores and el_b in scores:
                if scores[el_a] < scores[el_b]:
                    scores[el_a] = 0.0
                else:
                    scores[el_b] = 0.0

        return scores
