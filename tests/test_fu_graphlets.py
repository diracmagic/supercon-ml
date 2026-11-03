"""Meaningful mapping/QC tests; no supervised fitting or material labels."""
from itertools import permutations
import unittest

from ase import Atoms
from ase.build import bulk
import numpy as np

from ml import fu_graphlets as G


def as_dict(crystal, *, cartesian=False):
    return {"lattice_mat": crystal.cell.array.tolist(),
            "coords": (crystal.positions if cartesian else crystal.get_scaled_positions()).tolist(),
            "elements": crystal.get_chemical_symbols(), "cartesian": cartesian}


class RegistryTests(unittest.TestCase):
    def test_complete_eleven_graph_classes_and_permutation_invariance(self):
        self.assertEqual(len(G.GRAPH_MASKS), 11)
        self.assertEqual(G.GRAPH_MASKS[0], 0)
        self.assertEqual(G.GRAPH_MASKS[-1], 63)
        edge_index = {edge: bit for bit, edge in enumerate(G.EDGE_ORDER)}
        for mask in range(64):
            for perm in permutations(range(4)):
                changed = sum(1 << edge_index[tuple(sorted((perm[a], perm[b])))]
                              for bit, (a, b) in enumerate(G.EDGE_ORDER) if mask & (1 << bit))
                self.assertEqual(G.canonical_mask(mask), G.canonical_mask(changed))

    def test_mask_validation(self):
        for bad in (-1, 64, 1.5, True):
            with self.assertRaises(ValueError):
                G.canonical_mask(bad)


class CrystalMappingTests(unittest.TestCase):
    def assertMapped(self, atoms):
        frequency, diagnostics = G.extract_graphlets(atoms)
        self.assertEqual(diagnostics["status"], "ok", diagnostics)
        np.testing.assert_allclose(frequency.sum(), 1, atol=1e-14)
        self.assertEqual(diagnostics["mapped_centers"], diagnostics["n_sites"])
        np.testing.assert_array_equal(G.coverage_features(diagnostics), [1, 1])
        return frequency, diagnostics

    def test_periodic_images_are_distinct_and_all_ties_averaged(self):
        crystal = Atoms("Cu", positions=[[0, 0, 0]], cell=np.eye(3) * 4, pbc=True)
        frequency, diagnostics = self.assertMapped(crystal)
        center = diagnostics["centers"][0]
        self.assertEqual(center["tied_boundary_neighbors"], 6)
        self.assertEqual(center["tie_combination_count"], 20)
        images = center["shell_image_identities"]
        self.assertEqual({image["site_index"] for image in images}, {0})
        self.assertEqual(len({tuple(image["shift"]) for image in images}), 6)
        self.assertEqual(sum(center["motif_counts"].values()), 20)
        self.assertEqual(frequency[G.GRAPH_MASKS.index(G.canonical_mask(7))], 1)

    def test_rotation_translation_permutation_supercell_and_coordinate_modes(self):
        crystal = bulk("Cu", "fcc", a=3.6, cubic=True)
        reference, _ = self.assertMapped(crystal)
        transformed = crystal.copy()
        transformed.rotate(37, [1, 2, 3], rotate_cell=True)
        transformed.translate([3.14159, -5.25, 0.71])
        transformed = transformed[[2, 0, 3, 1]]
        variants = [transformed, crystal.repeat((2, 1, 1)),
                    bulk("Cu", "fcc", a=3.6), as_dict(crystal),
                    as_dict(transformed, cartesian=True)]
        for variant in variants:
            with self.subTest(kind=type(variant).__name__):
                result, _ = self.assertMapped(variant)
                np.testing.assert_allclose(result, reference, rtol=0, atol=1e-13)

    def test_species_do_not_set_graph_or_hamiltonian_parameters(self):
        crystal = bulk("Cu", "fcc", a=3.6, cubic=True)
        reference, _ = self.assertMapped(crystal)
        crystal.set_chemical_symbols(["Fe", "O", "C", "W"])
        changed, _ = self.assertMapped(crystal)
        np.testing.assert_array_equal(changed, reference)

    def test_jarvis_object_and_complete_tetrahedral_graph(self):
        from jarvis.core.atoms import Atoms as JarvisAtoms

        positions = [[0, 0, 0], [1, 0, 0], [0.5, np.sqrt(3) / 2, 0],
                     [0.5, np.sqrt(3) / 6, np.sqrt(2 / 3)]]
        crystal = Atoms("C4", positions=positions, cell=np.eye(3) * 30, pbc=True)
        frequency, _ = self.assertMapped(crystal)
        self.assertEqual(frequency[G.GRAPH_MASKS.index(63)], 1)
        jarvis = JarvisAtoms(**as_dict(crystal, cartesian=True))
        from_jarvis, _ = self.assertMapped(jarvis)
        np.testing.assert_array_equal(from_jarvis, frequency)

    def test_ties_within_tolerance_are_not_arbitrarily_broken(self):
        # Three noncollinear close neighbors and one tied near the third shell.
        crystal = Atoms("C5", positions=[[0, 0, 0], [1, 0, 0], [0, 2, 0],
                                         [0, 0, 3], [-3 - 0.5e-8, 0, 0]],
                        cell=np.eye(3) * 30, pbc=True)
        _, diagnostics = G.extract_graphlets(crystal)
        center = diagnostics["centers"][0]
        self.assertEqual(center["strict_neighbors"], 2)
        self.assertEqual(center["tied_boundary_neighbors"], 2)
        self.assertEqual(center["tie_combination_count"], 2)

    def test_tie_budget_returns_missing_instead_of_sampling(self):
        # 13 equidistant neighbors have 286 third-neighbor choices (>256).
        n = 13
        k = np.arange(n)
        z = 1 - 2 * (k + 0.5) / n
        phi = k * np.pi * (3 - np.sqrt(5))
        ring = np.sqrt(1 - z * z)
        shell = np.column_stack([ring * np.cos(phi), ring * np.sin(phi), z]) * 2
        crystal = Atoms("C14", positions=np.vstack([np.zeros(3), shell]),
                        cell=np.eye(3) * 30, pbc=True)
        frequency, diagnostics = G.extract_graphlets(crystal)
        self.assertTrue(np.isnan(frequency).all())
        self.assertFalse(diagnostics["structure_mapped"])
        self.assertEqual(diagnostics["centers"][0]["status"], "tie_budget_exceeded")
        self.assertEqual(diagnostics["centers"][0]["tie_combination_count"], 286)

    def test_insufficient_neighbors_and_partial_coverage_preserve_missing(self):
        isolated = Atoms("Cu", positions=[[0, 0, 0]], cell=np.eye(3) * 30, pbc=True)
        frequency, diagnostics = G.extract_graphlets(isolated)
        self.assertTrue(np.isnan(frequency).all())
        self.assertEqual(diagnostics["centers"][0]["status"], "insufficient_neighbors")
        np.testing.assert_array_equal(G.coverage_features(diagnostics), [0, 0])
        crystal = Atoms("C5", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0],
                                         [0, 0, 1], [15, 15, 15]],
                        cell=np.eye(3) * 40, pbc=True)
        frequency, diagnostics = G.extract_graphlets(crystal)
        self.assertTrue(np.isnan(frequency).all())
        self.assertEqual(diagnostics["mapped_centers"], 4)
        self.assertAlmostEqual(diagnostics["center_coverage_fraction"], 0.8)

    def test_actual_structure_required_and_malformed_input_missing(self):
        partially_occupied = Atoms("Cu", positions=[[0, 0, 0]], cell=np.eye(3) * 4, pbc=True)
        partially_occupied.info["occupancy"] = {"0": {"Cu": 0.5}}
        invalid = [None, {"coordination_mean": 6},
                   {"lattice_mat": np.eye(3), "coords": [[0, 0, 0]], "elements": ["Cu"], "occupancies": [0.5]},
                   Atoms("Cu", positions=[[0, 0, 0]], cell=np.eye(3) * 4, pbc=False),
                   Atoms("Cu2", positions=[[0, 0, 0], [0, 0, 0]], cell=np.eye(3) * 4, pbc=True),
                   partially_occupied]
        for value in invalid:
            with self.subTest(value=str(value)[:80]):
                frequency, diagnostics = G.extract_graphlets(value)
                self.assertTrue(np.isnan(frequency).all())
                self.assertFalse(diagnostics["structure_mapped"])


class AggregationTests(unittest.TestCase):
    def test_exact_weighting_array_and_mask_lookup(self):
        frequency = np.zeros(11)
        frequency[[0, 7]] = [0.25, 0.75]
        bank = np.arange(154, dtype=float).reshape(11, 14)
        expected = 0.25 * bank[0] + 0.75 * bank[7]
        np.testing.assert_allclose(G.aggregate_features(frequency, bank), expected)
        lookup = {str(mask): row for mask, row in zip(G.GRAPH_MASKS, bank)}
        np.testing.assert_allclose(G.aggregate_features(frequency, lookup), expected)

    def test_no_failed_bank_fallback_or_missing_structure_imputation(self):
        frequency = np.zeros(11)
        frequency[0] = 1
        bank = np.zeros((11, 14))
        bank[10, 0] = np.nan
        with self.assertRaises(ValueError):
            G.aggregate_features(frequency, bank)
        self.assertTrue(np.isnan(G.aggregate_features(np.full(11, np.nan), bank)).all())
        with self.assertRaises(ValueError):
            G.aggregate_features(np.zeros(11), np.zeros((11, 14)))


if __name__ == "__main__":
    unittest.main()
