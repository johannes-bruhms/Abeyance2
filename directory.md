Abeyance2/
├── main.py                  # Main application loop, routing, and threading
├── directory structure.txt  # Project map (this file)
├── core/
│ ├── config.py            # Global settings and the 7-Element Taxonomy (A-G)
│ └── gestalt.py           # 6D Hybrid Additive-Gestalt feature extractor (density, polyphony, spread, variance, up/down velocity)
├── ml/
│ └── classifier.py        #HybridGestaltDTW
├── midi/
│ ├── io.py              # MIDI I/O, CC 64 (Pedal) routing, and Ghost Note Filtering
│ └── playback.py        # Scheduled playback engine for AI-generated notes
├── agents/
│ └── parasite.py        # Parasite Swarm AI (Swarm logic, F,G)
└── gui/
└── app.py               # Tkinter GUI (AbeyanceGUI visualizer and status monitor)