# core/config.py

CONFIG = {
    'frame_size_ms': 250,
    'energy_boost': 0.2,
    'energy_decay': 0.05,
    'energy_trigger': 0.6,      # Minimum energy to trigger a swarm attack
    'ghost_echo_ttl': 3.0,
    'variations': 100,          # Synthetic clones per human seed
    'noise_spread': 0.05,       # Gaussian variance on synthetic clones
    'agent_tick_ms': 100,       # Swarm loop tick interval (ms)
    # Affinity-based multi-gesture detection
    'affinity_sigma': 0.22,     # Gaussian kernel width — lower = sharper element discrimination
    'affinity_threshold': 0.35, # Minimum EMA-smoothed confidence to activate an element
    # Gestalt feature extraction
    'polyphony_threshold_ms': 15,   # Max inter-onset gap (ms) to count as simultaneous
    'density_max_notes': 25,        # Max note-on count per frame for density normalization
    'piano_keys': 88,               # Number of keys for spread/velocity normalization
    # Classifier silence gate
    'silence_density_gate': 0.02,   # Density below this = silence (no scoring)
    # Piano roll
    'roll_scroll_px': 4,            # Pixels per animation tick the roll scrolls left
}

# Per-element tunable model parameters.
# Each element can be tuned independently via the GUI Elements tab.
ELEMENT_PARAMS = {
    el: {
        'affinity_threshold': 0.35,
        'affinity_sigma':     0.22,
        'energy_boost':       0.20,
        'energy_decay':       0.05,
    }
    for el in ('a', 'b', 'c', 'd', 'e', 'f')
}

ELEMENTS = {
    'a': 'Linear Velocity',
    'b': 'Vertical Density',
    'c': 'Transposed Shapes',
    'd': 'Oscillation',
    'e': 'Sweeps',
    'f': 'Extreme Registers',
}

# Default element profiles
# [density, polyphony, spread, variance, up_vel, down_vel, articulation, bimodality]
# Used when no human seed has been recorded. Overridden automatically after recording.
DEFAULT_CENTROIDS = {
    'a': [0.50, 0.10, 0.20, 0.10, 0.70, 0.20, 0.50, 0.10],  # directional runs, moderate sustain
    'b': [0.80, 0.80, 0.20, 0.20, 0.20, 0.20, 0.70, 0.10],  # dense chords, held, clustered register
    'c': [0.40, 0.60, 0.65, 0.70, 0.35, 0.35, 0.25, 0.15],  # interval shapes transposing, high variance
    'd': [0.45, 0.15, 0.30, 0.30, 0.60, 0.60, 0.20, 0.10],  # oscillation, staccato
    'e': [0.80, 0.20, 0.70, 0.40, 0.65, 0.20, 0.15, 0.10],  # sweeps, very staccato, one direction
    'f': [0.50, 0.70, 0.85, 0.80, 0.30, 0.30, 0.50, 0.85],  # simultaneous extreme registers, high bimodality
}

# Dimension importance weights per element
# [density, polyphony, spread, variance, up_vel, down_vel, articulation, bimodality]
AFFINITY_WEIGHTS = {
    'a': [0.30, 0.10, 0.10, 0.10, 0.80, 0.80, 0.30, 0.05],
    'b': [0.90, 0.90, 0.10, 0.10, 0.20, 0.20, 0.50, 0.10],
    'c': [0.20, 0.80, 0.50, 0.80, 0.20, 0.20, 0.30, 0.20],  # variance dominant, low bimodality weight
    'd': [0.40, 0.10, 0.30, 0.30, 0.90, 0.90, 0.60, 0.05],
    'e': [0.80, 0.20, 0.70, 0.40, 0.50, 0.50, 0.60, 0.05],
    'f': [0.30, 0.60, 0.80, 0.40, 0.10, 0.10, 0.30, 1.00],  # bimodality + spread dominant, separates from C
}

# Per-element EMA alpha: fast (0.35) for transient gestures, slow (0.15) for sustained states
EMA_ALPHAS = {
    'a': 0.35,  # transient directional events
    'b': 0.15,  # sustained dense texture
    'c': 0.35,  # transient leap events
    'd': 0.35,  # transient oscillation
    'e': 0.35,  # transient sweep
    'f': 0.20,  # moderate — extreme register playing tends to sustain but shifts
}

# Element pairs that are acoustically contradictory and cannot co-occur.
# When both score above threshold, the lower-confidence one is suppressed.
MUTUAL_EXCLUSION = [('a', 'd'), ('a', 'c'), ('c', 'e')]
