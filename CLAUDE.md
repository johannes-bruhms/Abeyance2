# CLAUDE.md

## Project Overview

Real-time computer-music interface for Yamaha Disklavier. A performer's gestures are classified into 5 overlapping elements via ML; a "Parasite Swarm" generates autonomous MIDI responses back into the piano. Studies cognitive channel capacity and attentional overload (Miller's law → Cowan, Pylyshyn, Wickens, Bregman). See `docs/RESEARCH_NOTES.md` for theory.

## Run & Test

```bash
python main.py                          # Requires MIDI Disklavier (falls back to dummy mode)
python -m unittest discover tests -v    # All tests
pip install -r requirements.txt         # Dependencies (mido, numpy); tkinter is stdlib
```

## Signal Flow

```
[Disklavier MIDI In]
  → GhostNoteFilter (midi/io.py)            # suppress AI echo (note_on + note_off)
  → 125ms Hop / per-element window (main.py)
  → extract_micro_gestalt() (core/gestalt.py)  # → 8D feature vector (dynamics-neutral)
  → GestaltAffinityScorer (ml/classifier.py)   # per-element window + affinity scoring
  → ParasiteSwarm.feed() (agents/parasite.py)  # energy + (pitch, velocity) pairs
  → per-element _attack handler                # element-specific response + dynamic mapping
  → PlaybackEngine (midi/playback.py)          # scheduled MIDI output (with cancel_all)
  → [Disklavier MIDI Out]
```

CC 64 (sustain pedal) bypasses classification → routes directly to swarm octave transposition (+12 semitones on all attack output when pedal is held). See `_pedal_transpose()` in `agents/parasite.py`.

## Design Invariants

- **Split-keyboard detection.** The keyboard is split at `split_point` (CONFIG, default 60 = middle C). Elements a–d are scored independently on each half; the higher-confidence half wins. Element E always scores on the full stream (it needs both extremes to detect the bimodal gap). This enables pseudo-polyphonic detection — e.g. scales in the left hand + clusters in the right hand activate simultaneously. Three scorer instances share one forge; the swarm receives notes from the winning half only.
- **Detection is dynamics-neutral.** The 8D gestalt vector excludes MIDI velocity. A gesture classifies identically whether pp or ff.
- **Response is dynamics-aware.** Each element has its own dynamic mapping (compressed/inverse/direct/expanded/averaged) transforming input velocity → output velocity. See `_attack_*` handlers in `agents/parasite.py`.
- **Per-element temporal windows.** Each element's `frame_size_ms` (in `ELEMENT_PARAMS`, `core/config.py`) is tuned to its gesture timescale. Density normalization scales proportionally so features stay comparable across window sizes.
- **Scoring modes.** `'affinity'` (default): 8D distance to trained centroid. `'chord'` (element B): rule-based simultaneous onset counting, no training needed.

## 5-Element Taxonomy

Defined in `core/config.py` (`ELEMENTS`, `ELEMENT_PARAMS`, `DEFAULT_CENTROIDS`, `AFFINITY_WEIGHTS`).

| ID | Name | Frame | Scoring | Gesture | Response |
|----|------|-------|---------|---------|----------|
| `a` | Linear Velocity | 250ms | affinity | Runs, scales, sweeps, glissandi | Counter-motion in neighboring register |
| `b` | Vertical Density | 150ms | chord | Dense simultaneous chords/clusters | Sustained cluster resonance, long decay |
| `c` | Transposed Shapes | 600ms | affinity | Interval shapes shifting registers | Tritone echo (+6 semitones) |
| `d` | Oscillation | 500ms | affinity | Trills, tremolo, alternation | Phase-shifted trill at offset rate |
| `e` | Extreme Registers | 350ms | affinity | Both keyboard extremes simultaneously | Fill the gap: gentle middle-register notes |

**Mutual exclusion:** `a` ↔ `c` only. Lower-confidence one is suppressed.

**C vs E disambiguation:** Both produce high spread/variance. The **bimodality** dimension (dim 7) separates them — C has low bimodality (~0.3, one moving center), E has high bimodality (~0.9, gap in the middle). Computed as largest inter-pitch gap / total spread.

## 8D Gestalt Vector

`extract_micro_gestalt()` in `core/gestalt.py`. Input: `(pitch, timestamp)` tuples. Output: `[density, polyphony, spread, variance, up_vel, down_vel, articulation, bimodality]`. All normalized 0–1. MIDI velocity intentionally excluded.

## Key Files

- **`core/config.py`** — Single source of truth for all tuning constants, element params, centroids, weights.
- **`core/logger.py`** — `from core.logger import log` → `log.info(...)`, `log.warn(...)`, `log.error(..., exc=True)`. Writes to `abeyance.log` + GUI.
- **`ml/classifier.py`** — `GestaltAffinityScorer`. `score_all()` returns dict: `scores`, `raw_scores`, `vectors`, `silence_gated`, `suppressed`.
- **`ml/forge.py`** — `GestureForge`. Generates Gaussian-perturbed synthetic data from `human_seeds.json`. Seeds accumulate across recording takes.
- **`midi/io.py`** — `GhostNoteFilter`. TTL-based echo suppression tracking note_on + note_off per pitch (supports overlapping notes on same pitch).
- **`agents/parasite.py`** — `ParasiteSwarm`. 5 agents with energy (0–1), element-specific `_attack_*` handlers, `on_attack` callbacks.
- **`midi/playback.py`** — `PlaybackEngine`. Non-blocking `threading.Timer` output, `on_note_scheduled` callbacks, `cancel_all()`.
- **`gui/app.py`** — Tkinter GUI: control panel, piano roll, training dashboard (REC/TRAIN/CLR per element), event log.
- **`gui/piano_roll.py`** — Scrolling piano roll with winner-takes-all element colors, confidence bars, detection labels.
- **`docs/DIRECTORY.md`** — Full project structure map.

## Recording / Training

Separate steps: recording accumulates seed data in `human_seeds.json`; training forges synthetic variants and retrains. REC → play → STOP (repeatable, accumulates). TRAIN forges + retrains. CLR resets element. Silent frames auto-stripped.

## Session Logs

`sessions/session_*.json` — event-driven (activations, deactivations, score shifts >0.1, silence/pedal transitions, mutual exclusion). Heartbeats every ~1s during stable play. Four sections: `metadata`, `summary` (read first — aggregate stats), `frames`, `attacks`.

**Digests:** `sessions/session_*.digest.json` — compact (~5% of full size) versions auto-generated on save. Contains `metadata`, `summary`, `timeline` (activation/deactivation events only), and `attacks`. Use digests for analysis; only open full JSON for per-frame vectors/notes. Generate manually: `python sessions/digest.py`.

## Subagents

Project-specific agents in `.claude/agents/`. Use these for their specialties instead of handling everything in the main conversation.

| Agent | When to Use |
|-------|-------------|
| `session-analyst` | Post-performance analysis of `sessions/session_*.json` — activation stats, overload indicators, cross-session comparison. Delegate any session log reading/interpretation to this agent. |
| `gesture-tuner` | Classifier tuning — when detection is wrong (false positives, missed gestures, element confusion). Adjusts centroids, weights, thresholds, sigmas, EMA alphas in `core/config.py` and `ml/classifier.py`. |
| `midi-debugger` | MIDI problems — connection failures, stuck notes, ghost note filter issues, feedback loops, playback timing. Knows the Disklavier echo behavior and threading model. |
| `swarm-designer` | Changing how the system responds musically — attack patterns, dynamic mappings, energy mechanics, perceptual distinguishability. Modifies `agents/parasite.py`. |
| `thesis-advisor` | Cognitive science framing, experimental design, research methodology, dependent variables, multi-pianist study design. Uses Opus model for deeper reasoning. Read-only (no code edits). |

## Documentation Maintenance

**This file is a living document. Update it as part of any change that alters the information above.** Specifically:

- **`CLAUDE.md`** (this file) — Update when: elements added/removed/renamed, signal flow changes, new design invariants, new key files, scoring modes change, mutual exclusion pairs change, recording/training workflow changes. Do NOT duplicate parameter values from code — point to the source file instead.
- **`docs/DIRECTORY.md`** — Update when files/directories are added, removed, or renamed.
- **`docs/RESEARCH_NOTES.md`** — Update when theoretical framework, element rationale, or methodology changes.
- **`core/config.py` comments** — Keep weight comments in sync with any tuning changes.
