# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Abeyance Protocol – Case Study 2** is a real-time computer-music interface (CMI) for Yamaha Disklavier (acoustic grand piano with MIDI solenoids). It creates a closed-loop system where a performer's gestures are analyzed via machine learning and autonomously responded to by an AI "Parasite Swarm" that generates its own MIDI output back into the piano.

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
  → GhostNoteFilter (midi/io.py)       # suppress AI-generated echo notes
  → 250ms Frame Buffer (main.py)       # temporal windowing
  → extract_micro_gestalt() (core/gestalt.py)  # → 6D feature vector
  → HybridGestaltDTW (ml/classifier.py)        # → element label (a–g)
  → ParasiteSwarm.feed() (agents/parasite.py)  # energy-based generative AI
  → PlaybackEngine (midi/playback.py)          # scheduled MIDI output
  → [Disklavier MIDI Output]
```

CC 64 (sustain pedal) bypasses the DTW pipeline entirely and routes directly to the swarm to modulate octave transposition with zero latency.

## 7-Element Taxonomy (core/config.py)

The classifier maps gestures to one of 7 elements:

| ID | Name | Notes |
|----|------|-------|
| `a` | Linear Velocity | |
| `b` | Vertical Density | |
| `c` | Spatial Leaps | |
| `d` | Oscillation | |
| `e` | Sweeps | |
| `f` | Resonance/Pedal | Hardware direct pass-through — bypasses DTW |
| `g` | Pointillism/Void | Special: echoes last note 2 octaves up with 1.5s delay |

## Key Components

- **`core/config.py`**: All global tuning constants — frame size (250ms), DTW radius, energy thresholds, ghost echo TTL (3.0s). Touch this to adjust system behavior.
- **`core/gestalt.py`**: `extract_micro_gestalt()` — converts raw `(pitch, timestamp)` tuples into a normalized 6D vector: density, polyphony, spread, variance, up-velocity, down-velocity.
- **`ml/classifier.py`** (`HybridGestaltDTW`): Maintains an 8-frame rolling window (~2s history), compares live vectors against stored templates, 1.5s debounce cooldown. Currently uses placeholder random detection rather than actual FastDTW.
- **`ml/forge.py`** (`GestureForge`): Bootstraps training data from `human_seeds.json` by generating 100+ Gaussian-perturbed synthetic variants per element.
- **`midi/io.py`** (`GhostNoteFilter`): TTL-based dict of AI-generated note fingerprints. Any incoming MIDI note matching a recently sent AI note is suppressed to prevent infinite feedback loops.
- **`agents/parasite.py`** (`ParasiteSwarm`): 7 independent agents (one per element). Each has `energy` (0.0–1.0) and a `stomach` deque. Energy rises 0.2 per recognized motif, decays 0.05 per tick, triggers a generative response when > 0.6.
- **`midi/playback.py`** (`PlaybackEngine`): Non-blocking scheduled note output using `threading.Timer`.
- **`gui/app.py`** (`AbeyanceGUI`): Tkinter GUI with left control panel, live piano roll, human seed training dashboard, and event log.

## Known Issues

- `agents/parasite.py` line 43 references `CONFIG['agent_tick_ms']` which is not defined in `core/config.py` — will raise `KeyError` at runtime when the swarm tick thread starts.
- `ml/classifier.py` uses mock random classification instead of actual FastDTW distance computation.
- GUI references `toggle_recording()` in the main controller, but the method is not implemented.
