# core/config.py

CONFIG = {
    'frame_size_ms': 250,
    'energy_boost': 0.2,
    'energy_decay': 0.05,
    'energy_trigger': 0.6,      # Minimum energy to trigger a swarm attack
    'ghost_echo_ttl': 3.0,
    'variations': 100,          # Synthetic clones per human seed
    'noise_spread': 0.05,       # Gaussian variance on synthetic clones
    'hop_size_ms': 125,         # Analysis loop tick interval (window remains frame_size_ms)
    'agent_tick_ms': 100,       # Swarm loop tick interval (ms)
    # Affinity-based multi-gesture detection
    'affinity_sigma': 0.18,     # Gaussian kernel width — lower = sharper element discrimination
    'affinity_threshold': 0.35, # Minimum EMA-smoothed confidence to activate an element
    # Gestalt feature extraction
    'polyphony_threshold_ms': 15,   # Max inter-onset gap (ms) to count as simultaneous
    'density_max_notes': 25,        # Max note-on count per frame for density normalization
    'piano_keys': 88,               # Number of keys for spread/velocity normalization
    # Piano roll
    'roll_scroll_px': 4,            # Pixels per animation tick the roll scrolls left
    # Split-keyboard pseudo-polyphonic detection
    'split_point': 60,              # MIDI note dividing low/high halves (60 = middle C)
}

# Per-element tunable model parameters.
# Each element can be tuned independently via the GUI Elements tab.
ELEMENT_PARAMS = {
    'a': {'frame_size_ms': 250, 'affinity_threshold': 0.40, 'affinity_sigma': 0.18, 'energy_boost': 0.10, 'energy_decay': 0.05, 'energy_drain': 0.30},
    'b': {'frame_size_ms': 150, 'scoring_mode': 'chord', 'chord_min_notes': 3, 'chord_onset_ms': 30, 'affinity_threshold': 0.35, 'affinity_sigma': 0.18, 'energy_boost': 0.10, 'energy_decay': 0.05, 'energy_drain': 0.40},
    'c': {'frame_size_ms': 600, 'affinity_threshold': 0.35, 'affinity_sigma': 0.18, 'energy_boost': 0.10, 'energy_decay': 0.05, 'energy_drain': 0.30},
    'd': {'frame_size_ms': 500, 'affinity_threshold': 0.35, 'affinity_sigma': 0.18, 'energy_boost': 0.10, 'energy_decay': 0.05, 'energy_drain': 0.35},
    'e': {'frame_size_ms': 350, 'affinity_threshold': 0.35, 'affinity_sigma': 0.18, 'energy_boost': 0.10, 'energy_decay': 0.05, 'energy_drain': 0.40},
}

ELEMENTS = {
    'a': 'Linear Velocity',
    'b': 'Vertical Density',
    'c': 'Transposed Shapes',
    'd': 'Oscillation',
    'e': 'Extreme Registers',
}

# Default element profiles
# [density, polyphony, spread, variance, up_vel, down_vel, articulation, bimodality]
# Used when no human seed has been recorded. Overridden automatically after recording.
DEFAULT_CENTROIDS = {
    'a': [0.60, 0.15, 0.45, 0.25, 0.70, 0.20, 0.35, 0.10],  # runs + sweeps, directional, moderate-wide spread
    'b': [0.40, 0.90, 0.25, 0.15, 0.10, 0.10, 0.70, 0.10],  # chords: lowered density to match real 5-10 note chords
    'c': [0.40, 0.60, 0.65, 0.70, 0.35, 0.35, 0.25, 0.15],  # interval shapes transposing, high variance
    'd': [0.35, 0.10, 0.15, 0.10, 0.15, 0.15, 0.15, 0.50],  # trills/oscillation: up/down matches narrow trills, bimodality ~0.5
    'e': [0.50, 0.70, 0.85, 0.80, 0.30, 0.30, 0.50, 0.85],  # simultaneous extreme registers, high bimodality
}

# Dimension importance weights per element
# [density, polyphony, spread, variance, up_vel, down_vel, articulation, bimodality]
AFFINITY_WEIGHTS = {
    'a': [0.30, 0.10, 0.50, 0.20, 0.85, 0.85, 0.30, 0.05],  # direction-dominant + spread for sweeps
    'b': [0.60, 0.90, 0.15, 0.10, 0.15, 0.15, 0.50, 0.10],  # polyphony-dominant, lowered density weight
    'c': [0.20, 0.80, 0.50, 0.90, 0.20, 0.20, 0.30, 0.20],  # variance dominant, low bimodality
    'd': [0.40, 0.10, 0.15, 0.15, 0.90, 0.90, 0.50, 0.05],  # up/down velocity for oscillation, low spread
    'e': [0.30, 0.60, 0.80, 0.40, 0.10, 0.10, 0.30, 1.00],  # bimodality + spread dominant, separates from C
}

# Per-element EMA alpha (8Hz scoring rate — raised from recalibrated values for faster live response)
EMA_ALPHAS = {
    'a': 0.30,  # transient directional events — fast response
    'b': 0.25,  # chords — raised for 2-3 frame activation
    'c': 0.30,  # transient leap events
    'd': 0.30,  # transient oscillation/trills
    'e': 0.20,  # extreme registers — slightly slower (sustained gestures)
}

# Element pairs that are acoustically contradictory and cannot co-occur.
# When both score above threshold, the lower-confidence one is suppressed.
MUTUAL_EXCLUSION = [('a', 'c')]
