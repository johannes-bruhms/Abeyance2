# ml/forge.py
import json
import os
import random

GESTALT_DIM = 8  # Current gestalt vector dimensionality


class GestureForge:
    """Handles saving human seeds and generating synthetic datasets via Gaussian noise."""
    def __init__(self, seed_file="human_seeds.json"):
        self.seed_file = seed_file
        self.seeds = self.load_seeds()

    def load_seeds(self):
        if os.path.exists(self.seed_file):
            with open(self.seed_file, 'r') as f:
                data = json.load(f)
            # Migrate old seeds to current dimensionality
            migrated = False
            for el_id, frames in data.items():
                for i, vec in enumerate(frames):
                    if len(vec) < GESTALT_DIM:
                        frames[i] = vec + [0.0] * (GESTALT_DIM - len(vec))
                        migrated = True
            # Migrate taxonomy: remove old 'e' (Sweeps), rename 'f' → 'e'
            if 'e' in data and 'f' in data:
                del data['e']
                data['e'] = data.pop('f')
                migrated = True
            elif 'e' in data and 'f' not in data:
                # Old 'e' exists but no 'f' — just remove old Sweeps data
                del data['e']
                migrated = True
            elif 'f' in data:
                data['e'] = data.pop('f')
                migrated = True
            if migrated:
                with open(self.seed_file, 'w') as f:
                    json.dump(data, f, indent=4)
            return data
        return {}

    def save_seeds(self):
        with open(self.seed_file, 'w') as f:
            json.dump(self.seeds, f, indent=4)

    def add_human_seed(self, element_id, vector_sequence):
        """
        Append one gesture iteration to the seed for element_id.
        Each REC->STOP cycle calls this once. Multiple calls accumulate,
        allowing the model to learn from several distinct iterations.
        Call clear_seed() first to start fresh.
        """
        if element_id not in self.seeds:
            self.seeds[element_id] = []
        self.seeds[element_id].extend(vector_sequence)
        self.save_seeds()

    def clear_seed(self, element_id):
        """Remove all recorded data for element_id."""
        if element_id in self.seeds:
            del self.seeds[element_id]
            self.save_seeds()

    def forge_variations(self, element_id, num_vars, spread):
        """Generates a dataset of synthetic templates based on the human seed."""
        if element_id not in self.seeds or not self.seeds[element_id]:
            base_seq = [[random.random() for _ in range(GESTALT_DIM)] for _ in range(8)]
        else:
            base_seq = self.seeds[element_id]

        variations = []
        for _ in range(num_vars):
            var_seq = []
            for vec in base_seq:
                new_vec = [max(0.0, min(1.0, v + random.gauss(0, spread))) for v in vec]
                var_seq.append(new_vec)
            variations.append(var_seq)

        return variations
