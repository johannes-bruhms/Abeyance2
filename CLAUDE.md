# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Abeyance Protocol – Case Study 2** is a real-time computer-music interface (CMI) for Yamaha Disklavier (acoustic grand piano with MIDI solenoids). It creates a closed-loop system where a performer's gestures are analyzed via machine learning and autonomously responded to by an AI "Parasite Swarm" that generates its own MIDI output back into the piano.

The system is designed to study **cognitive channel capacity and attentional overload** (motivated by Miller's law, operationalized via Cowan, Pylyshyn, Wickens, and Bregman). All 6 gesture elements can overlap simultaneously, creating conditions where the performer's ability to track independent gesture-response channels degrades measurably. See `docs/RESEARCH_NOTES.md` for the full theoretical framework.

## Running the Application

```bash
python main.py
```

No build step. No test suite or linter is currently configured.

**Hardware dependency**: Requires a MIDI-capable Disklavier connected via USB/MIDI. The app falls back to a dummy mode when no hardware is detected.

**Dependencies** (no requirements.txt — install manually):
```bash
pip install mido numpy
```
`tkinter` is included with standard Python.

## Architecture & Signal Flow

```
[Disklavier MIDI Input]
  → GhostNoteFilter (midi/io.py)            # suppress AI echo notes (note_on + note_off)
  → 250ms Frame Buffer (main.py)            # temporal windowing
  → extract_micro_gestalt() (core/gestalt.py)  # → 8D feature vector (dynamics-neutral)
  → HybridGestaltDTW (ml/classifier.py)     # → per-element confidence scores
  → ParasiteSwarm.feed() (agents/parasite.py)  # energy + (pitch, velocity) pairs
  → per-element _attack handler             # element-specific response + dynamic mapping
  → PlaybackEngine (midi/playback.py)       # scheduled MIDI output (with cancel_all)
  → [Disklavier MIDI Output]
```

CC 64 (sustain pedal) bypasses the classification pipeline and routes directly to the swarm to modulate octave transposition with zero latency. Pedal is **not** an element — it is a standalone modifier.

### Design Principles

- **Detection is dynamics-neutral.** The 8D gestalt vector does not include MIDI velocity. A gesture is classified as the same element whether performed pp or ff.
- **Response is dynamics-aware.** Each element has its own dynamic mapping that transforms the performer's input velocity into the swarm's output velocity. This creates element-specific feedback loop characters.

## 6-Element Taxonomy (core/config.py)

The classifier maps gestures to 6 ML-classified elements (a–f). Multiple elements can be active simultaneously. Each element has a distinct **response behavior** and **dynamic mapping** designed for perceptual distinguishability (auditory stream segregation).

| ID | Name | Gesture Signature | Swarm Response | Dynamic Mapping |
|----|------|-------------------|----------------|-----------------|
| `a` | Linear Velocity | Directional runs, high up/down velocity | Counter-motion: inverted direction, neighboring register | Compressed proportional (shadow) |
| `b` | Vertical Density | Dense simultaneous chords/clusters | Sustained cluster resonance: quiet held chord, long decay | Inverse (system compensates) |
| `c` | Transposed Shapes | Interval shape shifting registers, high variance | Tritone echo: shape replayed +6 semitones | Direct proportional (mirror) |
| `d` | Oscillation | Rapid alternation between pitch regions | Phase-shifted trill: boundary pitches at offset rate | Expanded (extremes amplified) |
| `e` | Sweeps | Fast wide-range traversals | Reverse sweep: opposite direction, staccato | Escalating (system one-ups) |
| `f` | Extreme Registers | Both keyboard extremes simultaneously | Fill the gap: gentle notes in avoided middle register | Averaged (median of input) |

### Dynamic Mapping Details

Each mapping creates a distinct feedback loop between performer and system:

| Mapping | Formula | Character |
|---------|---------|-----------|
| Compressed | `64 + (vel - 64) * 0.6` | Stable — system stays subordinate |
| Inverse | `127 - vel` | Balancing — system fills opposite dynamic |
| Direct | `vel` (1:1) | Mirror — exact reflection |
| Expanded | `64 + (vel - 64) * 1.5` | Polarizing — quiet→quieter, loud→louder |
| Escalating | `vel + 20` (capped at 127) | Provocative — system pushes the performer |
| Averaged | `mean(velocities)` | Mediating — system finds the middle ground |

### C vs F Disambiguation

Elements C and F both produce high spread and variance. The **bimodality** dimension (8th feature) separates them:
- **C (Transposed Shapes)**: Pitches cluster around one *moving* center → low bimodality (~0.3)
- **F (Extreme Registers)**: Pitches concentrated at *both tails* with a gap in the middle → high bimodality (~0.9)

Bimodality is computed as the **gap ratio**: largest gap between consecutive sorted pitches / total pitch spread.

### Mutual Exclusion

These pairs cannot co-occur; the lower-confidence one is suppressed:
- `a` ↔ `d` (linear vs oscillation)
- `a` ↔ `c` (linear vs shape transposition)
- `c` ↔ `e` (shape transposition vs sweeps)

## 8D Gestalt Vector (core/gestalt.py)

`extract_micro_gestalt()` converts a 250ms frame of `(pitch, timestamp)` tuples into:

| Dim | Name | Description |
|-----|------|-------------|
| 0 | Density | Note-on count / `CONFIG['density_max_notes']` (25) |
| 1 | Polyphony | Fraction of note-pairs with inter-onset < `CONFIG['polyphony_threshold_ms']` (15ms) |
| 2 | Spread | Pitch bounding box / 88 keys |
| 3 | Variance | `np.var(pitches) / 1000` |
| 4 | Up Velocity | Sum of ascending intervals / 88 |
| 5 | Down Velocity | Sum of descending intervals / 88 |
| 6 | Articulation | Mean completed note duration / 2s (0=staccato, 1=legato) |
| 7 | Bimodality | Largest inter-pitch gap / total spread (0=evenly spaced, 1=split at extremes) |

**Note:** MIDI velocity is intentionally excluded. Detection is dynamics-neutral; velocity is passed separately to the swarm for dynamics-aware response generation.

## Key Components

- **`core/config.py`**: All global tuning constants — frame size, energy thresholds, ghost echo TTL, gestalt parameters, per-element model params. Single source of truth for all magic numbers.
- **`core/gestalt.py`**: `extract_micro_gestalt()` — 8D feature extraction from raw MIDI. Dynamics-neutral.
- **`core/logger.py`**: Centralized logging singleton. `from core.logger import log` then `log.info(...)`, `log.warn(...)`, `log.error(..., exc=True)`. Writes to `abeyance.log` (auto-rotates at 1MB) and GUI event log.
- **`ml/classifier.py`** (`HybridGestaltDTW`): Affinity-based multi-label scorer. Computes per-element weighted Gaussian proximity on every 250ms frame with EMA smoothing and mutual-exclusion suppression. Multiple elements can be active simultaneously.
- **`ml/forge.py`** (`GestureForge`): Bootstraps training data from `human_seeds.json` by generating Gaussian-perturbed synthetic variants per element. Seed data accumulates across multiple recording takes.
- **`midi/io.py`** (`GhostNoteFilter`): TTL-based dict of AI-generated note fingerprints. Suppresses both `note_on` and `note_off` echoes to prevent infinite feedback loops.
- **`agents/parasite.py`** (`ParasiteSwarm`): 6 independent agents (one per element). Each has `energy` (0.0–1.0) and a `stomach` deque of `(pitch, velocity)` tuples. Energy rises per recognized motif, decays per tick, triggers element-specific `_attack_*` handlers when > `CONFIG['energy_trigger']` (0.6). Each handler implements a distinct response behavior and dynamic mapping.
- **`midi/playback.py`** (`PlaybackEngine`): Non-blocking scheduled note output using `threading.Timer`. Tracks all active timers; `cancel_all()` silences the swarm instantly.
- **`gui/app.py`** (`AbeyanceGUI`): Tkinter GUI with left control panel, live piano roll, confidence timeline, per-element training dashboard (with live recording feedback, take accumulation, silence stripping), and event log.
- **`gui/piano_roll.py`** (`PianoRollCanvas`): Scrolling piano roll with per-element color coding, confidence-proportional horizontal bands, and fading detection labels.

## Recording / Training Workflow

1. Connect MIDI ports in the left panel.
2. Go to the **Elements** tab — each element has its own column.
3. Press **REC** → play the gesture → press **STOP**. Silent frames (density < 0.05) are automatically stripped. The mini MIDI canvas only shows notes from surviving frames.
4. Repeat for more takes — data **accumulates** across REC/STOP cycles. The mini canvas shows all accumulated notes; stats show take count and total frames.
5. Adjust **Variations** and **Noise Spread** per element before or after recording.
6. Press **CLR** to reset an element to its default profile.
7. **Start Analysis** to begin live classification and swarm response.

## Known Limitations

- `ml/classifier.py` class name is `HybridGestaltDTW` but no longer uses DTW — it is a pure affinity scorer. Name kept for continuity.
- Session logs (`session_*.json`) accumulate in the project root during analysis sessions.

## Documentation

- **`docs/RESEARCH_NOTES.md`** — Cognitive overload theoretical framework and thesis framing.
- **`docs/DIRECTORY.md`** — Full project structure map.
