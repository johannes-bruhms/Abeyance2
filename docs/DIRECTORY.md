# Abeyance II — Project Structure

```
abeyance2/
├── main.py                    # Application entry point, controller, analysis loop, recording
├── human_seeds.json           # Accumulated training data (8D vectors per element)
├── requirements.txt           # Python dependencies (mido, numpy)
├── CLAUDE.md                  # Claude Code project instructions, classifier tuning rationale
├── .gitignore
│
├── .claude/
│   ├── settings.json
│   └── agents/
│       ├── session-analyst.md     # Post-performance session log analysis
│       ├── gesture-tuner.md       # ML classifier tuning and diagnostics
│       ├── midi-debugger.md       # MIDI I/O, ghost filter, stuck notes
│       ├── swarm-designer.md      # Parasite swarm attack behavior design
│       └── thesis-advisor.md      # Cognitive science framing and methodology
│
├── core/
│   ├── __init__.py
│   ├── config.py              # All tuning constants, 5-element taxonomy (a–e), centroids, weights
│   ├── gestalt.py             # 8D feature extraction: density, polyphony, spread, variance,
│   │                          #   up_vel, down_vel, articulation, bimodality
│   └── logger.py              # Centralized logging singleton (file + GUI, auto-rotate at 1MB)
│
├── ml/
│   ├── __init__.py
│   ├── classifier.py          # GestaltAffinityScorer — affinity-based multi-label scorer with
│   │                          #   per-element window sizes, EMA smoothing, and mutual exclusion
│   └── forge.py               # GestureForge — synthetic training data via Gaussian perturbation,
│                              #   auto-migrates old seed dimensionality on load
│
├── midi/
│   ├── __init__.py
│   ├── io.py                  # MidiIO + GhostNoteFilter (TTL echo suppression, tracks both
│   │                          #   note_on and note_off before removing entry)
│   └── playback.py            # PlaybackEngine — non-blocking scheduled output with cancel_all()
│                              #   and on_note_scheduled callback list
│
├── agents/
│   ├── __init__.py
│   └── parasite.py            # ParasiteSwarm — 5 independent agents with element-specific
│                              #   attack handlers and dynamic mappings
│
├── gui/
│   ├── __init__.py
│   ├── app.py                 # AbeyanceGUI — control panel, training dashboard (separate
│   │                          #   REC/TRAIN/CLR workflow), event log, confidence timeline
│   └── piano_roll.py          # PianoRollCanvas — scrolling visualization, winner-takes-all
│                              #   element colors, legend
│
├── tests/
│   ├── __init__.py
│   ├── test_gestalt.py        # Unit tests for 8D gestalt extraction
│   ├── test_classifier.py     # Unit tests for affinity scorer, mutual exclusion, dynamic mappings
│   ├── test_forge.py          # Unit tests for GestureForge seed persistence and migration
│   ├── test_ghost_filter.py   # Unit tests for GhostNoteFilter echo suppression
│   ├── test_parasite.py       # Unit tests for ParasiteSwarm attacks, energy, dynamic mappings
│   └── test_playback.py       # Unit tests for PlaybackEngine scheduling and cancel
│
├── sessions/                  # Session logs (auto-created, JSON data gitignored)
│   └── digest.py              # Generates compact .digest.json files (~5% of full size)
│
├── archived/                  # Archived/deprecated code (gitignored)
│
└── docs/
    ├── AUDIT.md                # Comprehensive project audit with prioritized fixes
    ├── DIRECTORY.md            # This file
    └── RESEARCH_NOTES.md       # Cognitive overload theoretical framework (Miller, Cowan,
                                #   Pylyshkin, Wickens, Bregman)
```

## Signal Flow

```
[Disklavier MIDI In] → GhostNoteFilter → Note Buffer
  → Split by pitch (low / high halves at middle C)
  → per-half 8D Gestalt extraction
  → Affinity Scorer ×2 (elements a–d per half) + full-stream scorer (element e)
  → Merge (max confidence per element)
  → ParasiteSwarm (fed with winning-half notes)
  → PlaybackEngine → [Disklavier MIDI Out]
```

CC 64 (sustain pedal) bypasses classification → routes directly to swarm octave transposition (+12 semitones).
