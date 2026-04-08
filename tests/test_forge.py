"""Tests for ml/forge.py — GestureForge."""
import json
import os
import tempfile
import unittest

from ml.forge import GestureForge, GESTALT_DIM


class TestGestureForge(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.seed_file = os.path.join(self.tmpdir, 'test_seeds.json')

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    # ---- basic seed operations ----

    def test_empty_start(self):
        """Without a seed file, forge starts with empty seeds."""
        forge = GestureForge(self.seed_file)
        self.assertEqual(forge.seeds, {})

    def test_add_and_persist(self):
        """add_human_seed should persist to disk immediately."""
        forge = GestureForge(self.seed_file)
        vec = [[0.5] * GESTALT_DIM]
        forge.add_human_seed('a', vec)
        self.assertEqual(len(forge.seeds['a']), 1)
        # Verify file on disk
        with open(self.seed_file) as f:
            data = json.load(f)
        self.assertIn('a', data)
        self.assertEqual(len(data['a']), 1)

    def test_accumulate_across_takes(self):
        """Multiple add_human_seed calls should accumulate."""
        forge = GestureForge(self.seed_file)
        forge.add_human_seed('a', [[0.1] * GESTALT_DIM])
        forge.add_human_seed('a', [[0.2] * GESTALT_DIM])
        self.assertEqual(len(forge.seeds['a']), 2)

    def test_clear_seed(self):
        """clear_seed should remove all data for an element."""
        forge = GestureForge(self.seed_file)
        forge.add_human_seed('a', [[0.5] * GESTALT_DIM])
        forge.clear_seed('a')
        self.assertNotIn('a', forge.seeds)

    def test_clear_nonexistent_element(self):
        """clear_seed on a missing element should not crash."""
        forge = GestureForge(self.seed_file)
        forge.clear_seed('z')  # no-op

    # ---- persistence across loads ----

    def test_reload_from_disk(self):
        """A second GestureForge instance should load saved seeds."""
        forge1 = GestureForge(self.seed_file)
        forge1.add_human_seed('b', [[0.3] * GESTALT_DIM])

        forge2 = GestureForge(self.seed_file)
        self.assertIn('b', forge2.seeds)
        self.assertEqual(len(forge2.seeds['b']), 1)

    # ---- corrupt file recovery (H5 fix) ----

    def test_corrupt_json_recovers(self):
        """A corrupt seed file should be backed up and forge starts fresh."""
        with open(self.seed_file, 'w') as f:
            f.write('{invalid json!!!}')
        forge = GestureForge(self.seed_file)
        self.assertEqual(forge.seeds, {})
        # Corrupt file should be backed up
        self.assertTrue(os.path.exists(self.seed_file + '.corrupt'))

    def test_truncated_json_recovers(self):
        """A truncated JSON file (crash mid-write) should recover."""
        with open(self.seed_file, 'w') as f:
            f.write('{"a": [[0.5, 0.5, 0.5')  # truncated
        forge = GestureForge(self.seed_file)
        self.assertEqual(forge.seeds, {})

    # ---- dimensionality migration ----

    def test_old_7d_vectors_padded(self):
        """Vectors with fewer than 8 dimensions should be zero-padded."""
        old_data = {'a': [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]]}
        with open(self.seed_file, 'w') as f:
            json.dump(old_data, f)
        forge = GestureForge(self.seed_file)
        self.assertEqual(len(forge.seeds['a'][0]), GESTALT_DIM)
        self.assertEqual(forge.seeds['a'][0][-1], 0.0)

    # ---- taxonomy migration (M9 fix) ----

    def test_f_renamed_to_e(self):
        """Old 'f' key should be renamed to 'e'."""
        old_data = {'f': [[0.5] * GESTALT_DIM]}
        with open(self.seed_file, 'w') as f:
            json.dump(old_data, f)
        forge = GestureForge(self.seed_file)
        self.assertIn('e', forge.seeds)
        self.assertNotIn('f', forge.seeds)

    def test_e_and_f_migration(self):
        """Old 'e' (Sweeps) discarded, 'f' renamed to 'e'."""
        old_data = {
            'e': [[0.1] * GESTALT_DIM],  # old Sweeps
            'f': [[0.9] * GESTALT_DIM],  # old Extreme Registers
        }
        with open(self.seed_file, 'w') as f:
            json.dump(old_data, f)
        forge = GestureForge(self.seed_file)
        self.assertIn('e', forge.seeds)
        self.assertEqual(forge.seeds['e'][0][0], 0.9)  # from old 'f'

    def test_migration_idempotent(self):
        """Loading already-migrated data should not delete valid 'e'."""
        valid_data = {'a': [[0.1] * GESTALT_DIM], 'e': [[0.5] * GESTALT_DIM]}
        with open(self.seed_file, 'w') as f:
            json.dump(valid_data, f)
        forge = GestureForge(self.seed_file)
        self.assertIn('e', forge.seeds)
        self.assertEqual(forge.seeds['e'][0][0], 0.5)  # unchanged

    # ---- forge_variations ----

    def test_forge_variations_shape(self):
        """forge_variations should return the correct number of variations."""
        forge = GestureForge(self.seed_file)
        forge.add_human_seed('a', [[0.5] * GESTALT_DIM] * 3)
        variations = forge.forge_variations('a', 50, 0.05)
        self.assertEqual(len(variations), 50)
        self.assertEqual(len(variations[0]), 3)  # 3 frames per seed
        self.assertEqual(len(variations[0][0]), GESTALT_DIM)

    def test_forge_variations_no_seed_uses_random(self):
        """Without seeds, forge_variations should still return data."""
        forge = GestureForge(self.seed_file)
        variations = forge.forge_variations('a', 10, 0.05)
        self.assertEqual(len(variations), 10)

    def test_forge_values_in_range(self):
        """Forged values should be clamped to [0, 1]."""
        forge = GestureForge(self.seed_file)
        forge.add_human_seed('a', [[0.5] * GESTALT_DIM])
        variations = forge.forge_variations('a', 100, 0.1)
        for var in variations:
            for vec in var:
                for val in vec:
                    self.assertGreaterEqual(val, 0.0)
                    self.assertLessEqual(val, 1.0)


if __name__ == '__main__':
    unittest.main()
