# Abeyance II — Project Structure

```
abeyance2/
├── main.py                    # Application entry point, controller, analysis loop, recording
├── human_seeds.json           # Accumulated training data (8D vectors per element)
├── CLAUDE.md                  # Claude Code project instructions, classifier tuning rationale
├── .gitignore
│
├── core/
│   ├── __init__.py
│   ├── config.py              # All tuning constants, 6-element taxonomy (a–f), centroids, weights
│   ├── gestalt.py             # 8D feature extraction: density, polyphony, spread, variance,
│   │                          #   up_vel, down_vel, articulation, bimodality
│   └── logger.py              # Centralized logging singleton (file + GUI, auto-rotate at 1MB)
│
├── ml/
│   ├── __init__.py
│   ├── classifier.py          # HybridGestaltDTW — affinity-based multi-label scorer with
│   │                          #   per-element EMA smoothing and mutual exclusion
│   └── forge.py               # GestureForge — synthetic training data via Gaussian perturbation,
│                              #   auto-migrates old seed dimensionality on load
│
├── midi/
│   ├── __init__.py
│   ├── io.py                  # MidiIO + GhostNoteFilter (TTL echo suppression, note_on + note_off)
│   └── playback.py            # PlaybackEngine — non-blocking scheduled output with cancel_all()
│
├── agents/
│   ├── __init__.py
│   └── parasite.py            # ParasiteSwarm — 6 independent agents with element-specific
│                              #   attack handlers and dynamic mappings
│
├── gui/
│   ├── __init__.py
│   ├── app.py                 # AbeyanceGUI — control panel, training dashboard, event log,
│   │                          #   confidence timeline, live recording feedback
│   └── piano_roll.py          # PianoRollCanvas — scrolling visualization with element colors
│
└── docs/
    ├── DIRECTORY.md            # This file
    └── RESEARCH_NOTES.md       # Cognitive overload theoretical framework (Miller, Cowan,
                                #   Pylyshyn, Wickens, Bregman)
```

## Signal Flow

```
[Disklavier MIDI In] → GhostNoteFilter → 250ms Frame Buffer → 8D Gestalt
  → Affinity Scorer (per-element EMA) → ParasiteSwarm → PlaybackEngine → [Disklavier MIDI Out]
```

CC 64 (sustain pedal) bypasses classification → routes directly to swarm octave transposition.
