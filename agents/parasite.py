# agents/parasite.py
import time
import threading
from collections import deque
from core.config import CONFIG, ELEMENT_PARAMS

class ParasiteSwarm:
    def __init__(self, elements, playback_engine):
        self.playback = playback_engine
        self.agents = {}
        self.lock = threading.Lock()
        
        self.sustain_pedal_down = False 
        
        for k in elements.keys():
            self.agents[k] = {
                'energy': 0.1,
                'stomach': deque(maxlen=50) 
            }
            
        self.running = True
        self.thread = threading.Thread(target=self._swarm_loop, daemon=True)
        self.thread.start()

    def set_pedal(self, is_down):
        """Direct injection of Element F (Pedal)"""
        with self.lock:
            self.sustain_pedal_down = is_down
            if is_down:
                self.agents['f']['energy'] = 1.0 
            else:
                self.agents['f']['energy'] = 0.0

    def feed(self, label, notes, weight=1.0):
        """Energize one agent. weight (0.0–1.0) scales the energy boost by detection confidence."""
        if not label or label not in self.agents or label == 'f': return
        with self.lock:
            # Element G requires less energy to trigger, as the notes are sparse
            boost_val = ELEMENT_PARAMS[label]['energy_boost']
            base_boost = boost_val * 1.5 if label == 'g' else boost_val
            self.agents[label]['energy'] = min(1.0, self.agents[label]['energy'] + base_boost * weight)
            self.agents[label]['stomach'].extend(notes)

    def _swarm_loop(self):
        tick_sec = CONFIG['agent_tick_ms'] / 1000.0
        while self.running:
            time.sleep(tick_sec)
            
            with self.lock:
                for label, agent in self.agents.items():
                    if label == 'f': continue 
                    
                    agent['energy'] = max(0.0, agent['energy'] - ELEMENT_PARAMS[label]['energy_decay'])
                    
                    if agent['energy'] > 0.6 and len(agent['stomach']) > 0:
                        self._trigger_attack(label, agent)

    def _trigger_attack(self, label, agent):
        if label == 'g':
            # THE VOID STATE REACTION
            # Wait 1.5 seconds, then play the last note 2 octaves up
            note_to_play = list(agent['stomach'])[-1]
            mod_note = note_to_play + 24 
            
            self.playback.schedule_note(
                mod_note, 
                velocity=35,           # Very delicate
                duration_sec=2.0,      # Long, sustained ring
                delay_sec=1.5          # Cavernous delay
            )
            agent['energy'] -= 0.6     # Heavy drain so it doesn't spam
            
        else:
            # STANDARD REACTION (Elements A through E)
            notes_to_play = list(agent['stomach'])[-3:] 
            for i, note in enumerate(notes_to_play):
                mod_note = note + (12 if self.sustain_pedal_down else 0)
                self.playback.schedule_note(mod_note, velocity=60, duration_sec=0.5, delay_sec=i*0.2)
            
            agent['energy'] -= 0.3