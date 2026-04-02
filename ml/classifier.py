# ml/classifier.py
from ml.forge import GestureForge
from core.config import ELEMENTS, CONFIG

class HybridGestaltDTW:
    def __init__(self):
        self.forge = GestureForge()
        self.templates = {}
        self.rolling_window = []
        
        # Automatically load human seeds and forge templates on startup
        self.load_all_from_forge()

    def load_all_from_forge(self):
        for el_id in ELEMENTS.keys():
            # Skip Pedal (hardware override)
            if el_id == 'f': continue 
            self.update_element(el_id, CONFIG['variations'], CONFIG['noise_spread'])
            
    def update_element(self, element_id, num_vars, spread):
        """Re-generates synthetic templates for a specific element."""
        self.templates[element_id] = self.forge.forge_variations(element_id, int(num_vars), spread)

    def push_frame(self, vector_6d):
        self.rolling_window.append(vector_6d)
        if len(self.rolling_window) > 8: # Keep 2.0 second window (8 frames of 250ms)
            self.rolling_window.pop(0)

    def classify_current(self):
        # Placeholder for actual FastDTW logic comparing self.rolling_window against self.templates
        # Returns the classified element_id (e.g., 'c') or None
        if len(self.rolling_window) < 8: return None
        
        # Mock detection logic for safety testing
        import random
        if random.random() > 0.95: 
            keys = [k for k in ELEMENTS.keys() if k != 'f']
            return random.choice(keys)
        return None