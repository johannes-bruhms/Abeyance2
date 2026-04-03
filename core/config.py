# core/config.py

CONFIG = {
    'frame_size_ms': 250,
    'energy_boost': 0.2,
    'energy_decay': 0.05,
    'ghost_echo_ttl': 3.0,
    'variations': 100,          # Synthetic clones per human seed
    'noise_spread': 0.05,       # Gaussian variance on synthetic clones
    'agent_tick_ms': 100,       # Swarm loop tick interval (ms)
    # Affinity-based multi-gesture detection
    'affinity_sigma': 0.22,     # Gaussian kernel width — lower = sharper element discrimination
    'affinity_threshold': 0.35, # Minimum EMA-smoothed confidence to activate an element
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
    for el in ('a', 'b', 'c', 'd', 'e', 'g')
}

ELEMENTS = {
    'a': 'Linear Velocity',
    'b': 'Vertical Density',
    'c': 'Transposed Shapes',
    'd': 'Oscillation',
    'e': 'Sweeps',
    'f': 'Resonance/Pedal',
    'g': 'Pointillism/Void'
}

# Default element profiles [density, polyphony, spread, variance, up_vel, down_vel, articulation]
# Used when no human seed has been recorded. Overridden automatically after recording.
DEFAULT_CENTROIDS = {
    'a': [0.50, 0.10, 0.20, 0.10, 0.70, 0.20, 0.50],  # directional, moderate sustain
    'b': [0.80, 0.80, 0.20, 0.20, 0.20, 0.20, 0.70],  # dense chords, held
    'c': [0.40, 0.60, 0.65, 0.70, 0.35, 0.35, 0.25],  # interval shapes transposing, high polyphony+variance
    'd': [0.45, 0.15, 0.30, 0.30, 0.60, 0.60, 0.20],  # oscillation, staccato
    'e': [0.80, 0.20, 0.70, 0.40, 0.65, 0.20, 0.15],  # sweeps, very staccato
    'g': [0.08, 0.00, 0.20, 0.15, 0.08, 0.08, 0.80],  # sparse, long sustained tones
}

# Dimension importance weights per element
# [density, polyphony, spread, variance, up_vel, down_vel, articulation]
AFFINITY_WEIGHTS = {
    'a': [0.30, 0.10, 0.10, 0.10, 0.80, 0.80, 0.30],
    'b': [0.90, 0.90, 0.10, 0.10, 0.20, 0.20, 0.50],
    'c': [0.20, 0.80, 0.50, 0.80, 0.20, 0.20, 0.30],  # polyphony (shapes) + variance (register jumps) dominant
    'd': [0.40, 0.10, 0.30, 0.30, 0.90, 0.90, 0.60],
    'e': [0.80, 0.20, 0.70, 0.40, 0.50, 0.50, 0.60],
    'g': [1.00, 0.80, 0.20, 0.20, 0.10, 0.10, 0.70],
}

# Per-element EMA alpha: fast (0.35) for transient gestures, slow (0.15) for sustained states
EMA_ALPHAS = {
    'a': 0.35,  # transient directional events
    'b': 0.15,  # sustained dense texture
    'c': 0.35,  # transient leap events
    'd': 0.35,  # transient oscillation
    'e': 0.35,  # transient sweep
    'g': 0.15,  # sustained sparse void state
}

# Element pairs that are acoustically contradictory and cannot co-occur.
# When both score above threshold, the lower-confidence one is suppressed.
MUTUAL_EXCLUSION = [('b', 'g'), ('a', 'd'), ('g', 'e'), ('a', 'c'), ('c', 'e')]
