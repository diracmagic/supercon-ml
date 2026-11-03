"""Independent physics and fermionic-function checks, without model-target fits."""
import itertools
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import fu_wavefunction as F


def independent_hubbard(mask, U, nup, ndown):
    """Reference via ordered occupation lists and exterior-algebra insertion signs.

    Does not call the production builder, use its bitcount sign rule, or its
    sector-basis generator.
    """
    configs = [tuple(c) for c in itertools.combinations(range(8), nup + ndown)
               if sum(mode % 2 == 0 for mode in c) == nup]
    configs.sort(key=lambda c: sum(2 ** mode for mode in c))
    lookup = {config: i for i, config in enumerate(configs)}
    H = np.zeros((len(configs), len(configs)))
    edges = list(itertools.combinations(range(4), 2))
    for column, config in enumerate(configs):
        H[column, column] = U * sum(2 * site in config and 2 * site + 1 in config for site in range(4))
        for bit, (a, b) in enumerate(edges):
            if not mask & 2 ** bit:
                continue
            for spin in (0, 1):
                for to_site, from_site in ((a, b), (b, a)):
                    source, target = 2 * from_site + spin, 2 * to_site + spin
                    if source not in config or target in config:
                        continue
                    occupied = list(config)
                    removed_at = occupied.index(source)
                    occupied.pop(removed_at)
                    inserted_at = sum(mode < target for mode in occupied)
                    occupied.insert(inserted_at, target)
                    H[lookup[tuple(occupied)], column] += -(-1) ** (removed_at + inserted_at)
    return H, np.asarray([sum(2 ** mode for mode in c) for c in configs])


class FermionPhysicsTests(unittest.TestCase):
    def test_all_eleven_graphs_and_relabeling(self):
        graphs = F.canonical_graphs()
        self.assertEqual(len(graphs), 11)
        self.assertEqual(graphs, sorted(graphs))
        self.assertEqual({F.canonical_mask(mask) for mask in range(64)}, set(graphs))
        self.assertEqual(F.canonical_mask(1), F.canonical_mask(32))

    def test_independent_hamiltonian_all_graphs_sectors(self):
        for graph in F.canonical_graphs():
            for sector in F.SECTORS:
                actual, basis = F.build_hamiltonian(graph, 4.0, *sector)
                reference, reference_basis = independent_hubbard(graph, 4.0, *sector)
                np.testing.assert_array_equal(basis, reference_basis)
                np.testing.assert_array_equal(actual, reference)

    def test_hubbard_dimer_spectrum_and_rayleigh(self):
        # Sites 2/3 are isolated spectator sites, so project to electrons on 0/1.
        for U in (0.0, 4.0, 8.0):
            H, basis = F.build_hamiltonian(1, U, 1, 1)
            keep = np.flatnonzero(basis < 16)
            dimer = H[np.ix_(keep, keep)]
            e, v = np.linalg.eigh(dimer)
            analytic = (U - np.sqrt(U * U + 16.0)) / 2
            self.assertAlmostEqual(e[0], analytic, places=12)
            self.assertAlmostEqual(F.rayleigh_quotient(v[:, 0] * 3.7, dimer), analytic, places=12)
            trial = np.arange(1, len(keep) + 1, dtype=float)
            self.assertGreaterEqual(F.rayleigh_quotient(trial, dimer), analytic - 1e-12)

    @unittest.skipUnless(importlib.util.find_spec("jax") and importlib.util.find_spec("optax"),
                         "JAX/Optax physics checks run in the mandatory dedicated Fu workflow")
    def test_antisymmetry_pooling_and_pauli_zero(self):
        params = F.initialize_parameters(7)
        original = np.asarray([0, 3, 4, 7])
        psi = float(F.wavefunction(params, original))
        self.assertGreater(abs(psi), 1e-8)
        for permutation in itertools.permutations(range(4)):
            inversions = sum(permutation[i] > permutation[j] for i in range(4) for j in range(i + 1, 4))
            actual = float(F.wavefunction(params, original[list(permutation)]))
            self.assertAlmostEqual(actual, (-1) ** inversions * psi, places=11)
        self.assertEqual(float(F.wavefunction(params, [0, 3, 3, 7])), 0.0)

    def test_degenerate_projector_not_single_eigenvector(self):
        H = np.diag([0.0, 0.0, 2.0])
        eigenvalues, projector = F.exact_solution(H)
        # A rotated state in a degenerate ground subspace must pass.
        state = np.array([1., -1., 0.]) / np.sqrt(2)
        qc = F.quality_metrics(H, state, eigenvalues=eigenvalues, projector=projector)
        self.assertTrue(qc["passed"])
        self.assertEqual(qc["ground_space_dimension"], 2)
        self.assertAlmostEqual(qc["ground_subspace_fidelity"], 1.0)
        self.assertFalse(F.quality_metrics(H, [0, 0, 1])["passed"])
        self.assertFalse(F.quality_metrics(H, [0, 0, 0])["passed"])

    def test_feature_correlations_use_own_zero_interaction(self):
        energy = np.asarray([[[1., 2., 3.], [5., 8., 11.], [9., 14., 19.]]])
        features = F.feature_lookup(energy)
        self.assertEqual(features.shape, (1, 14))
        np.testing.assert_allclose(features[0, :7], [1.25, 2., 2.75, 1., 1.5, 2., 0.])
        np.testing.assert_allclose(features[0, 7:], [2.25, 3.5, 4.75, 2., 3., 4., 0.])

    def test_frozen_optimizer_versions_and_schedule_endpoints(self):
        v1 = {"steps": 300, "optimizer": "Adam learning_rate0.01"}
        v2 = {"steps": 2000, "optimizer": "Adam with cosine learning-rate schedule .01 to .00001 over2000steps"}
        self.assertEqual(F.learning_rate_at_step(299, v1), .01)
        self.assertAlmostEqual(F.learning_rate_at_step(0, v2), .01, places=14)
        self.assertAlmostEqual(F.learning_rate_at_step(1999, v2), .00001, places=14)
        self.assertGreater(F.learning_rate_at_step(100, v2), F.learning_rate_at_step(1000, v2))

    @unittest.skipUnless(importlib.util.find_spec("jax") and importlib.util.find_spec("optax"),
                         "JAX/Optax physics checks run in the mandatory dedicated Fu workflow")
    def test_saved_state_reconstruction_and_corruption_rejection(self):
        params = F.initialize_parameters(7)
        H, basis = F.build_hamiltonian(0, 0, 1, 1)
        eigenvalues, projector = F.exact_solution(H)
        psi = np.asarray(F.wavefunction(params, F.configurations(basis)))
        saved = {f"parameter_{key}": np.asarray(value).copy() for key, value in params.items()}
        saved.update(H=H, basis=basis, psi=psi, eigenvalues=eigenvalues,
                     ground_projector=projector, protocol_sha256=np.asarray(F.FROZEN_PROTOCOL_SHA256))
        def validate(archive):
            return F._validate_state_archive(archive, H, basis, F.FROZEN_PROTOCOL_SHA256, None)
        qc, ground, errors = validate(saved)
        self.assertTrue(qc["passed"])
        self.assertEqual(errors, [])
        changed_weights = dict(saved)
        changed_weights["parameter_head"] = np.arange(16, dtype=float)
        self.assertTrue(any("do not reconstruct" in error for error in validate(changed_weights)[2]))
        missing = dict(saved)
        del missing["parameter_query"]
        self.assertTrue(any("keys" in error for error in validate(missing)[2]))
        unknown = dict(saved, parameter_unexpected=np.zeros(1))
        self.assertTrue(any("keys" in error for error in validate(unknown)[2]))
        wrong_shape = dict(saved, parameter_query=np.zeros((15, 16)))
        self.assertTrue(any("shape" in error for error in validate(wrong_shape)[2]))
        self.assertEqual(F._energy_binding_errors(qc["energy"], ground, qc, ground), [])
        self.assertTrue(any("neural energy" in error for error in F._energy_binding_errors(.25, ground, qc, ground)))
        self.assertTrue(any("exact energy" in error for error in F._energy_binding_errors(qc["energy"], .25, qc, ground)))

    def test_all_frozen_seeds_and_minimum_selection_required(self):
        records = [{"seed": 7, "energy": -1., "artifact": "seed7"},
                   {"seed": 107, "energy": -2., "artifact": "seed107"}]
        self.assertEqual(F._selection_errors([7, 107], records, 107, "seed107", -2.), [])
        self.assertTrue(any("minimum" in error for error in F._selection_errors([7, 107], records, 7, "seed7", -1.)))
        self.assertTrue(any("seed set" in error for error in F._selection_errors([7, 107], records[:1], 7, "seed7", -1.)))
        self.assertTrue(any("seed set" in error for error in F._selection_errors([7, 107], records + records[:1], 107, "seed107", -2.)))
        self.assertTrue(any("artifact" in error for error in F._selection_errors([7, 107], records, 107, "seed7", -2.)))


if __name__ == "__main__":
    unittest.main()
