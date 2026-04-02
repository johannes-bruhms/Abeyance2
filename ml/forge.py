# ml/forge.py
import json
import os
import random

class GestureForge:
    """Handles saving human seeds and generating synthetic datasets via Gaussian noise."""
    def __init__(self, seed_file="human_seeds.json"):
        self.seed_file = seed_file
        self.seeds = self.load_seeds()

    def load_seeds(self):
        """Loads prior human training data on launch."""
        if os.path.exists(self.seed_file):
            with open(self.seed_file, 'r') as f:
                return json.load(f)
        return {}

    def save_seeds(self):
        """Persists human seeds to disk."""
        with open(self.seed_file, 'w') as f:
            json.dump(self.seeds, f, indent=4)

    def add_human_seed(self, element_id, vector_sequence):
        """Records a new human performance as the baseline seed."""
        self.seeds[element_id] = vector_sequence
        self.save_seeds()

    def forge_variations(self, element_id, num_vars, spread):
        """Generates a dataset of synthetic templates based on the human seed."""
        if element_id not in self.seeds or not self.seeds[element_id]:
            # Fallback to random initialization if no human seed exists yet
            base_seq = [[random.random() for _ in range(6)] for _ in range(8)]
        else:
            base_seq = self.seeds[element_id]
            
        variations = []
        for _ in range(num_vars):
            var_seq = []
            for vec in base_seq:
                # Apply targeted Gaussian noise to the human baseline
                new_vec = [max(0.0, min(1.0, v + random.gauss(0, spread))) for v in vec]
                var_seq.append(new_vec)
            variations.append(var_seq)
            
        return variations