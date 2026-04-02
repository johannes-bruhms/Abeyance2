import numpy as np

def extract_micro_gestalt(notes_with_times):
    """
    Squashes a 250ms frame of MIDI data into a 6D Hybrid Additive-Gestalt vector.
    
    Expected input: A chronological list of tuples: [(pitch1, time1), (pitch2, time2), ...]
    Returns: [Density, Polyphony, Spread, Variance, Up_Velocity, Down_Velocity]
    All values normalized to approx 0.0 - 1.0.
    """
    if not notes_with_times:
        return np.zeros(6)
        
    pitches = [n[0] for n in notes_with_times]
    times = [n[1] for n in notes_with_times]
    
    # 1. Density: Raw count of attacks (normalized to max 25 notes per 250ms)
    density = min(1.0, len(pitches) / 25.0)
    
    if len(pitches) == 1:
        return np.array([density, 0.0, 0.0, 0.0, 0.0, 0.0])

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
    
    # Normalize polyphony against the total density
    polyphony = min(1.0, polyphonic_events / max(1, (len(pitches) - 1)))
    
    # 5 & 6. Directionality (Up_Velocity & Down_Velocity)
    # By splitting slope into Up and Down bins, contrary motion adds up rather than canceling out!
    up_intervals = 0
    down_intervals = 0
    
    for i in range(1, len(pitches)):
        delta = pitches[i] - pitches[i-1]
        if delta > 0:
            up_intervals += delta
        elif delta < 0:
            down_intervals += abs(delta)
            
    # Normalize velocities (Assume max 88 semitones traveled in a 250ms window)
    up_velocity = min(1.0, up_intervals / 88.0)
    down_velocity = min(1.0, down_intervals / 88.0)

    return np.array([
        density, 
        polyphony, 
        spread, 
        variance, 
        up_velocity, 
        down_velocity
    ])