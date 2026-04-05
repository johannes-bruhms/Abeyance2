# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Abeyance Protocol – Case Study 2** is a real-time computer-music interface (CMI) for Yamaha Disklavier (acoustic grand piano with MIDI solenoids). It creates a closed-loop system where a performer's gestures are analyzed via machine learning and autonomously responded to by an AI "Parasite Swarm" that generates its own MIDI output back into the piano.

The system is designed to study **cognitive channel capacity and attentional overload** (motivated by Miller's law, operationalized via Cowan, Pylyshyn, Wickens, and Bregman). All 5 gesture elements can overlap simultaneously, creating conditions where the performer's ability to track independent gesture-response channels degrades measurably. See `docs/RESEARCH_NOTES.md` for the full theoretical framework.

## Running the Application

```bash
python main.py
```

No build step. Tests use `unittest`:
```bash
python -m unittest discover tests -v
```

**Hardware dependency**: Requires a MIDI-capable Disklavier connected via USB/MIDI. The app falls back to a dummy mode when no hardware is detected.

**Dependencies**:
```bash
pip install -r requirements.txt
```
`tkinter` is included with standard Python.

## Architecture & Signal Flow

```
[Disklavier MIDI Input]
  → GhostNoteFilter (midi/io.py)            # suppress AI echo notes (note_on + note_off)
  → 250ms Sliding Window / 125ms Hop (main.py) # overlapping temporal windowing
  → extract_micro_gestalt() (core/gestalt.py)  # → 8D feature vector (dynamics-neutral)
  → GestaltAffinityScorer (ml/classifier.py) # → per-element confidence scores
  → ParasiteSwarm.feed() (agents/parasite.py)  # energy + (pitch, velocity) pairs
  → per-element _attack handler             # element-specific response + dynamic mapping
  → PlaybackEngine (midi/playback.py)       # scheduled MIDI output (with cancel_all)
  → [Disklavier MIDI Output]
```

CC 64 (sustain pedal) bypasses the classification pipeline and routes directly to the swarm to modulate octave transposition with zero latency. Pedal is **not** an element — it is a standalone modifier.

### Design Principles

- **Detection is dynamics-neutral.** The 8D gestalt vector does not include MIDI velocity. A gesture is classified as the same element whether performed pp or ff.
- **Response is dynamics-aware.** Each element has its own dynamic mapping that transforms the performer's input velocity into the swarm's output velocity. This creates element-specific feedback loop characters.

## 5-Element Taxonomy (core/config.py)

The classifier maps gestures to 5 ML-classified elements (a–e). Multiple elements can be active simultaneously. Each element has a distinct **response behavior** and **dynamic mapping** designed for perceptual distinguishability (auditory stream segregation).

Previously a 6-element taxonomy (a–f). Element E (Sweeps) was merged into A (Linear Velocity) on 2026-04-05 because glissandi are essentially fast scales — the distinction was too blurry to classify reliably. Old element F (Extreme Registers) was renumbered to E.

| ID | Name | Gesture Signature | Swarm Response | Dynamic Mapping |
|----|------|-------------------|----------------|-----------------|
| `a` | Linear Velocity | Directional runs, scales, sweeps, glissandi | Counter-motion: inverted direction, neighboring register | Compressed proportional (shadow) |
| `b` | Vertical Density | Dense simultaneous chords/clusters | Sustained cluster resonance: quiet held chord, long decay | Inverse (system compensates) |
| `c` | Transposed Shapes | Interval shape shifting registers, high variance | Tritone echo: shape replayed +6 semitones | Direct proportional (mirror) |
| `d` | Oscillation | Rapid alternation between pitch regions, trills, tremolo | Phase-shifted trill: boundary pitches at offset rate | Expanded (extremes amplified) |
| `e` | Extreme Registers | Both keyboard extremes simultaneously | Fill the gap: gentle notes in avoided middle register | Averaged (median of input) |

### Dynamic Mapping Details

Each mapping creates a distinct feedback loop between performer and system:

| Mapping | Formula | Character |
|---------|---------|-----------|
| Compressed | `64 + (vel - 64) * 0.6` | Stable — system stays subordinate |
| Inverse | `127 - vel` | Balancing — system fills opposite dynamic |
| Direct | `vel` (1:1) | Mirror — exact reflection |
| Expanded | `64 + (vel - 64) * 1.5` | Polarizing — quiet→quieter, loud→louder |
| Averaged | `mean(velocities)` | Mediating — system finds the middle ground |

### C vs E Disambiguation

Elements C and E both produce high spread and variance. The **bimodality** dimension (8th feature) separates them:
- **C (Transposed Shapes)**: Pitches cluster around one *moving* center → low bimodality (~0.3)
- **E (Extreme Registers)**: Pitches concentrated at *both tails* with a gap in the middle → high bimodality (~0.9)

Bimodality is computed as the **gap ratio**: largest gap between consecutive sorted pitches / total pitch spread.

### Mutual Exclusion

These pairs cannot co-occur; the lower-confidence one is suppressed:
- `a` ↔ `c` (linear vs shape transposition)

Previously included a↔d (removed 2026-04-05 to allow oscillation/trills to activate independently of linear velocity), c↔e and d↔e (removed when Sweeps was merged into Linear Velocity).

## 8D Gestalt Vector (core/gestalt.py)

`extract_micro_gestalt()` converts a 250ms window of `(pitch, timestamp)` tuples into:

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

- **`core/config.py`**: All global tuning constants — frame size, hop size, energy thresholds, ghost echo TTL, gestalt parameters, per-element model params. Single source of truth for all magic numbers.
- **`core/gestalt.py`**: `extract_micro_gestalt()` — 8D feature extraction from raw MIDI. Dynamics-neutral.
- **`core/logger.py`**: Centralized logging singleton. `from core.logger import log` then `log.info(...)`, `log.warn(...)`, `log.error(..., exc=True)`. Writes to `abeyance.log` (auto-rotates at 1MB) and GUI event log.
- **`ml/classifier.py`** (`GestaltAffinityScorer`): Affinity-based multi-label scorer. Computes per-element weighted Gaussian proximity every 125ms hop (250ms sliding window) with EMA smoothing and mutual-exclusion suppression (with EMA decay on suppressed elements to prevent hidden accumulation). Multiple elements can be active simultaneously.
- **`ml/forge.py`** (`GestureForge`): Bootstraps training data from `human_seeds.json` by generating Gaussian-perturbed synthetic variants per element. Seed data accumulates across multiple recording takes. Automatically migrates old 6-element seed keys (f→e) on load.
- **`midi/io.py`** (`GhostNoteFilter`): TTL-based dict of AI-generated note fingerprints. Tracks each echo entry until both `note_on` and `note_off` are consumed, preventing feedback loops.
- **`agents/parasite.py`** (`ParasiteSwarm`): 5 independent agents (one per element). Each has `energy` (0.0–1.0) and a `stomach` deque of `(pitch, velocity)` tuples. Energy rises per recognized motif, decays per tick, triggers element-specific `_attack_*` handlers when > `CONFIG['energy_trigger']` (0.6). Each handler implements a distinct response behavior and dynamic mapping.
- **`midi/playback.py`** (`PlaybackEngine`): Non-blocking scheduled note output using `threading.Timer`. Provides `on_note_scheduled` callback list for visual hooks. Tracks all active timers; `cancel_all()` silences the swarm instantly.
- **`gui/app.py`** (`AbeyanceGUI`): Tkinter GUI with left control panel, live piano roll, confidence timeline, per-element training dashboard (with live recording feedback, take accumulation, silence stripping, gap-compressed mini canvas with fixed full MIDI range, separate TRAIN button for on-demand forging/retraining), and event log.
- **`gui/piano_roll.py`** (`PianoRollCanvas`): Scrolling piano roll with per-element color coding, confidence-proportional horizontal bands, and fading detection labels.

## Recording / Training Workflow

Recording and training are **separate steps** — recording accumulates seed data without retraining, so you can batch many takes before forging synthetic data.

1. Connect MIDI ports in the left panel.
2. Go to the **Elements** tab — each element has its own column.
3. Press **REC** → play the gesture → press **STOP**. Silent frames (density < 0.05) are automatically stripped. The mini MIDI canvas (fixed full MIDI range 0–127) compresses temporal gaps to visually confirm truncation.
4. Repeat for more takes — data **accumulates** across REC/STOP cycles. The mini canvas shows all accumulated notes; stats show take count and total frames. Status shows "Untrained" in orange until the model is trained.
5. Adjust **Variations** and **Noise Spread** per element.
6. Press **TRAIN** to forge synthetic variations and retrain the model. Can be re-run with different synth params without re-recording.
7. Press **CLR** to reset an element to its default profile.
8. **Start Analysis** to begin live classification and swarm response.

## Classifier Tuning Rationale

Global `affinity_sigma` is 0.18 (tightened from 0.22) for sharper element discrimination — neighboring profiles bleed less at this width.

EMA alphas recalibrated on 2026-04-05 for 8Hz scoring rate (125ms hop). Formula: `α_new = 1 - (1 - α_4Hz)^0.5` preserves identical per-second smoothing. Energy boost halved from 0.20→0.10 (applied per analysis tick via `swarm.feed()`; energy decay unchanged — consumed by the independent 100ms swarm loop).

Taxonomy reduced from 6→5 elements on 2026-04-05: Sweeps merged into Linear Velocity (glissandi ≈ fast scales), old F renumbered to E. Mutual exclusion reduced to only a↔c (a↔d removed to allow trills/oscillation to activate independently).

| Element | Key Weight Changes | Threshold | EMA Alpha | Rationale |
|---------|-------------------|-----------|-----------|-----------|
| `a` Linear Velocity | spread 0.50 (raised), up/down 0.85 | 0.40 | 0.19 | Now covers sweeps; spread weight raised to detect wide traversals |
| `b` Vertical Density | polyphony 0.90, density 0.60 (lowered) | 0.35 | 0.13 | Polyphony-dominant; density centroid lowered to 0.40 for real chord counts |
| `c` Transposed Shapes | variance 0.90 | 0.35 | 0.19 | Variance is the distinguishing feature |
| `d` Oscillation | up/down 0.90, spread 0.15 (lowered) | 0.35 | 0.19 | Centroid up/down lowered to 0.35 for narrow trills; no longer excluded by A |
| `e` Extreme Registers | bimodality 1.00 + spread 0.80 | 0.35 | 0.11 | Bimodality is the decisive separator from C |

## Known Limitations

- Session logs (`session_*.json`) are saved to the `sessions/` directory during analysis sessions.
- The `templates` dict in the classifier is retained for potential future use but is not currently used for scoring (profiles/centroids are used instead).

## Documentation

- **`docs/RESEARCH_NOTES.md`** — Cognitive overload theoretical framework and thesis framing.
- **`docs/DIRECTORY.md`** — Full project structure map.

### Documentation Maintenance

When making changes to the codebase, **always update all affected documentation** before committing:

- **`CLAUDE.md`** — Update if any architecture, signal flow, element taxonomy, config parameters, key components, or workflows change. This is the primary project reference.
- **`docs/DIRECTORY.md`** — Update if files/directories are added, removed, or renamed.
- **`docs/RESEARCH_NOTES.md`** — Update if the theoretical framework, element design rationale, or experimental methodology changes.
- **Classifier Tuning Rationale** (above) — Update whenever `ELEMENT_PARAMS`, `AFFINITY_WEIGHTS`, `EMA_ALPHAS`, `MUTUAL_EXCLUSION`, or `affinity_sigma` are changed, including the reasoning behind the change.
- **Inline code comments** — Keep `core/config.py` weight comments in sync with the rationale table above.
