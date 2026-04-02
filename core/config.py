# core/config.py

CONFIG = {
    'frame_size_ms': 250,
    'dtw_radius': 5,
    'energy_boost': 0.2,
    'energy_decay': 0.05,
    'ghost_echo_ttl': 3.0,
    # New Training Parameters
    'variations': 100,        # Number of synthetic clones to generate per human seed
    'noise_spread': 0.05      # Gaussian variance applied to the human baseline
}

ELEMENTS = {
    'a': 'Linear Velocity',
    'b': 'Vertical Density',
    'c': 'Spatial Leaps',
    'd': 'Oscillation',
    'e': 'Sweeps',
    'f': 'Resonance/Pedal',
    'g': 'Pointillism/Void'
}