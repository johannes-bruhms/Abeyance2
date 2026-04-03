# core/gestalt.py
import numpy as np

def extract_micro_gestalt(notes_with_times, completed_durations=None):
    """
    Squashes a 250ms frame of MIDI data into a 7D Hybrid Additive-Gestalt vector.

    Args:
        notes_with_times: chronological list of (pitch, timestamp) tuples for note-ons
        completed_durations: list of float durations (seconds) for notes whose note-off
                             arrived during this frame. Used to compute articulation.
                             Pass None or [] if no note-offs occurred.

    Returns:
        np.array of shape (7,):
        [Density, Polyphony, Spread, Variance, Up_Velocity, Down_Velocity, Articulation]

    All values normalized to 0.0 - 1.0.
    Articulation: 0.0 = staccato/short, 1.0 = legato/sustained.
    """
    if not notes_with_times:
        return np.zeros(7)
        
    pitches = [n[0] for n in notes_with_times]
    times = [n[1] for n in notes_with_times]

    # 1. Density: Raw count of attacks (normalized to max 25 notes per 250ms)
    density = min(1.0, len(pitches) / 25.0)

    # 7. Articulation (computed early so single-note frames still return it)
    # Mean duration of completed notes, normalized to 1.0 = 2 seconds.
    # Staccato gestures produce short durations (near 0), legato near 1.
    if completed_durations:
        mean_dur = float(np.mean(completed_durations))
        articulation = min(1.0, mean_dur / 2.0)
    else:
        articulation = 0.0  # no note-offs yet — conservative, not misleading

    if len(pitches) == 1:
        return np.array([density, 0.0, 0.0, 0.0, 0.0, 0.0, articulation])

    # 2. Spread: Bounding box of the pitches (normalized to 88 keys)
    spread = float(max(pitches) - min(pitches)) / 88.0
    
    # 3. Variance: Statistical scatter from the center (normalized to max ~1000)
    variance = min(1.0, float(np.var(pitches)) / 1000.0)
    
    # 4. Polyphony: How many notes were struck practically simultaneously?
    # We count instances where the time delta between sequential notes is < 15ms
    polyphonic_events = 0
    for i in range(1, len(times)):
        if (times[i] - times[i-1]) < 0.015: # 15 milliseconds
            polyphonic_events += 1
            
    # Normalize polyphony against the total possible sequential gaps
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
            
    up_velocity = min(1.0, up_intervals / 88.0)
    down_velocity = min(1.0, down_intervals / 88.0)

    return np.array([density, polyphony, spread, variance,
                     up_velocity, down_velocity, articulation])