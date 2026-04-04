# core/gestalt.py
import numpy as np
from core.config import CONFIG

def extract_micro_gestalt(notes_with_times, completed_durations=None):
    """
    Squashes a 250ms frame of MIDI data into an 8D Hybrid Additive-Gestalt vector.

    Args:
        notes_with_times: chronological list of (pitch, timestamp) tuples for note-ons
        completed_durations: list of float durations (seconds) for notes whose note-off
                             arrived during this frame. Used to compute articulation.
                             Pass None or [] if no note-offs occurred.

    Returns:
        np.array of shape (8,):
        [Density, Polyphony, Spread, Variance, Up_Velocity, Down_Velocity,
         Articulation, Bimodality]

    All values normalized to 0.0 - 1.0.
    Articulation: 0.0 = staccato/short, 1.0 = legato/sustained.
    Bimodality:   0.0 = pitches evenly spaced or tightly clustered,
                  1.0 = one dominant gap splitting pitches into two extreme groups.
    """
    if not notes_with_times:
        return np.zeros(8)

    pitches = [n[0] for n in notes_with_times]
    times = [n[1] for n in notes_with_times]

    # 1. Density: Raw count of attacks
    density = min(1.0, len(pitches) / float(CONFIG['density_max_notes']))

    # 7. Articulation (computed early so single-note frames still return it)
    if completed_durations:
        mean_dur = float(np.mean(completed_durations))
        articulation = min(1.0, mean_dur / 2.0)
    else:
        articulation = 0.0

    if len(pitches) == 1:
        return np.array([density, 0.0, 0.0, 0.0, 0.0, 0.0, articulation, 0.0])

    piano_keys = float(CONFIG['piano_keys'])

    # 2. Spread: Bounding box of the pitches
    spread = float(max(pitches) - min(pitches)) / piano_keys

    # 3. Variance: Statistical scatter from the center (normalized to max ~1000)
    variance = min(1.0, float(np.var(pitches)) / 1000.0)

    # 4. Polyphony: How many notes were struck practically simultaneously?
    poly_thresh = CONFIG['polyphony_threshold_ms'] / 1000.0
    polyphonic_events = 0
    for i in range(1, len(times)):
        if (times[i] - times[i-1]) < poly_thresh:
            polyphonic_events += 1
    polyphony = min(1.0, polyphonic_events / max(1, (len(pitches) - 1)))

    # 5 & 6. Directionality (Up_Velocity & Down_Velocity)
    up_intervals = 0
    down_intervals = 0
    for i in range(1, len(pitches)):
        delta = pitches[i] - pitches[i-1]
        if delta > 0:
            up_intervals += delta
        elif delta < 0:
            down_intervals += abs(delta)
    up_velocity = min(1.0, up_intervals / piano_keys)
    down_velocity = min(1.0, down_intervals / piano_keys)

    # 8. Bimodality (gap ratio): Largest gap between consecutive sorted pitches
    #    divided by total spread. Extreme register playing produces one dominant
    #    gap in the middle (bimodality ~0.9), while clustered or evenly-spaced
    #    playing produces small uniform gaps (bimodality ~0.2–0.4).
    sorted_p = sorted(pitches)
    p_spread = sorted_p[-1] - sorted_p[0]
    if p_spread < 1:
        bimodality = 0.0
    else:
        max_gap = max(sorted_p[i + 1] - sorted_p[i] for i in range(len(sorted_p) - 1))
        bimodality = min(1.0, max_gap / p_spread)

    return np.array([density, polyphony, spread, variance,
                     up_velocity, down_velocity, articulation, bimodality])
