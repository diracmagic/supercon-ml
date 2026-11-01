import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from ase import Atoms
from ase.build import bulk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ml'))
import mechanism_features as M


def record(crystal, *, cartesian=False):
    return {'lattice_mat': crystal.cell.array.tolist(), 'coords': (crystal.positions if cartesian else crystal.get_scaled_positions()).tolist(),
            'elements': crystal.get_chemical_symbols(), 'cartesian': cartesian}


class MechanismGeometryTests(unittest.TestCase):
    def assert_equivalent(self, left, right):
        a, b = M.extract_features(left), M.extract_features(right)
        self.assertTrue(a['diagnostics']['structure_valid'], a['diagnostics'])
        self.assertTrue(b['diagnostics']['structure_valid'], b['diagnostics'])
        np.testing.assert_allclose(a['values'], b['values'], rtol=1e-10, atol=1e-10, equal_nan=True)

    def test_rotation_translation_permutation_cartesian_and_basis_equivalence(self):
        crystal = bulk('Al', 'fcc', a=4.05, cubic=True)
        original = record(crystal)
        rotation, _ = np.linalg.qr(np.random.default_rng(42).normal(size=(3, 3)))
        rotated = crystal.copy()
        rotated.set_cell(crystal.cell.array @ rotation, scale_atoms=False)
        rotated.positions = crystal.positions @ rotation + [1.2, -2.3, 3.4]
        self.assert_equivalent(original, record(rotated, cartesian=True))
        self.assert_equivalent(original, record(rotated[[2, 0, 3, 1]]))
        transform = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]])
        changed = Atoms(symbols=crystal.get_chemical_symbols(), cell=transform @ crystal.cell.array,
                        scaled_positions=crystal.get_scaled_positions() @ np.linalg.inv(transform), pbc=True)
        self.assert_equivalent(original, record(changed))

    def test_primitive_conventional_and_directional_supercells(self):
        primitive = bulk('Al', 'fcc', a=4.05)
        conventional = bulk('Al', 'fcc', a=4.05, cubic=True)
        self.assert_equivalent(record(primitive), record(conventional))
        for repeat in [(2, 1, 1), (1, 2, 3)]:
            self.assert_equivalent(record(primitive), record(primitive.repeat(repeat)))

    def test_periodic_self_images_give_chain_sheet_and_bulk_dimensions(self):
        for cell, coordination, dimension in [([1.5, 12, 12], 2, 1), ([1.5, 1.5, 12], 4, 2), ([1.5]*3, 6, 3)]:
            crystal = Atoms('C', positions=[[0, 0, 0]], cell=cell, pbc=True)
            out = M.extract_features(record(crystal))
            self.assertEqual(out['features']['coordination_mean'], coordination)
            self.assertEqual(out['features'][f'connectivity_{dimension}d_site_fraction'], 1)
            self.assert_equivalent(record(crystal), record(crystal.repeat((2, 1, 2))))
        sheet = M.extract_features(record(Atoms('C', positions=[[0, 0, 0]], cell=[1.5, 1.5, 12], pbc=True)))
        self.assertAlmostEqual(sheet['features']['local_planarity_mean'], 1)
        self.assertAlmostEqual(sheet['features']['local_linearity_mean'], 0)

    def test_molecule_crossing_cell_boundary_is_zero_dimensional(self):
        molecule = Atoms('N2', positions=[[0.2, 5, 5], [9.1, 5, 5]], cell=[10]*3, pbc=True)
        out = M.extract_features(record(molecule))
        self.assertEqual(out['features']['coordination_mean'], 1)
        self.assertEqual(out['features']['connectivity_0d_site_fraction'], 1)
        self.assertTrue(math.isnan(out['features']['local_planarity_mean']))
        self.assert_equivalent(record(molecule), record(molecule.repeat((2, 2, 1))))

    def test_disconnected_components_are_weighted_by_sites_under_supercells(self):
        crystal = Atoms('CH', positions=[[0,0,0], [0,6,6]], cell=[1.5,12,12], pbc=True)
        out = M.extract_features(record(crystal))
        self.assertEqual(out['features']['connectivity_0d_site_fraction'], .5)
        self.assertEqual(out['features']['connectivity_1d_site_fraction'], .5)
        self.assert_equivalent(record(crystal), record(crystal.repeat((3, 2, 1))))

    def test_real_tetrahedral_shell_and_metal_ligand_square(self):
        tetra = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) * (1.1/np.sqrt(3))
        molecule = Atoms('CH4', positions=np.vstack([[0, 0, 0], tetra])+6, cell=[12]*3, pbc=True)
        out = M.extract_features(record(molecule))
        self.assertEqual(out['diagnostics']['coverage']['four_contact_sites'], 1)
        self.assertAlmostEqual(out['features']['tetrahedral_order_mean'], 1)
        self.assertAlmostEqual(out['features']['local_planarity_mean'], 0)
        square = Atoms('CuO4', positions=np.array([[0,0,0], [1.9,0,0], [-1.9,0,0], [0,1.9,0], [0,-1.9,0]])+6, cell=[12]*3, pbc=True)
        out = M.extract_features(record(square))
        self.assertEqual(out['features']['metal_ligand_coordination_mean'], 4)
        self.assertAlmostEqual(out['features']['local_planarity_mean'], 1)
        self.assertAlmostEqual(out['features']['tetrahedral_order_mean'], 0.5)

    def test_triangular_pyramid_endpoints_are_not_planar_coordination(self):
        vectors = np.array([[1,0,.5], [-.5,np.sqrt(3)/2,.5], [-.5,-np.sqrt(3)/2,.5]])*1.1
        molecule = Atoms('ZnH3', positions=np.vstack([[0,0,0], vectors])+6, cell=[12]*3, pbc=True)
        out = M.extract_features(record(molecule))
        self.assertEqual(out['diagnostics']['coverage']['planarity_sites'], 1)
        self.assertLess(out['features']['local_planarity_mean'], 0.9)

    def test_isolated_valid_sites_and_missing_chemistry_are_not_fabricated_zero_shapes(self):
        isolated = M.extract_features(record(Atoms('C', positions=[[0,0,0]], cell=[12]*3, pbc=True)))
        self.assertTrue(isolated['diagnostics']['structure_valid'])
        self.assertEqual(isolated['features']['coordination_mean'], 0)
        self.assertEqual(isolated['features']['connectivity_0d_site_fraction'], 1)
        self.assertTrue(math.isnan(isolated['features']['metal_ligand_coordination_mean']))
        self.assertTrue(math.isnan(isolated['features']['tetrahedral_order_mean']))
        self.assertIn('orbital_energies', isolated['diagnostics']['unavailable_properties'])

    def test_cutoff_sensitive_layer_connection_is_visible_in_diagnostics(self):
        contact_cutoff = 2*.76*1.25
        crystal = Atoms('C', positions=[[0,0,0]], cell=[1.5,1.5,1.02*contact_cutoff], pbc=True)
        out = M.extract_features(record(crystal))
        self.assertEqual(out['features']['connectivity_2d_site_fraction'], 1)
        self.assertTrue(out['diagnostics']['dimensionality_changes_with_cutoff'])
        self.assertGreater(out['diagnostics']['near_cutoff_fraction_of_searched_edges'], 0)

    def test_invalid_structures_and_budgets_return_explicit_fixed_missing_vectors(self):
        good = record(Atoms('Al', positions=[[0,0,0]], cell=[4]*3, pbc=True))
        bad = [None, {}, dict(good, lattice_mat=[[0,0,0]]*3), dict(good, elements=['X']),
               dict(good, coords=[[math.nan,0,0]]), dict(good, occupancies=[.5]), dict(good, cartesian='false'),
               dict(good, lattice_mat=(np.eye(3)*1e308).tolist()), dict(good, coords=[[10**1000,0,0]]),
               dict(good, elements=['Al','Al'], coords=[[0,0,0],[0,0,0]])]
        for atoms in bad:
            out = M.extract_features(atoms)
            self.assertEqual(out['diagnostics']['status'], 'invalid')
            self.assertEqual(out['names'], list(M.FEATURE_NAMES))
            self.assertTrue(all(math.isnan(value) for value in out['values']))
        out = M.extract_features(dict(good, elements=['Og']))
        self.assertEqual(out['diagnostics']['status'], 'unsupported')
        out = M.extract_features(record(Atoms('C2', positions=[[0,0,0],[1,0,0]], cell=[4]*3, pbc=True)), config=M.GeometryConfig(max_atoms=1))
        self.assertEqual(out['diagnostics']['status'], 'budget_exceeded')
        out = M.extract_features(record(Atoms('C', positions=[[0,0,0]], cell=[1.5]*3, pbc=True)), config=M.GeometryConfig(max_neighbor_edges=5))
        self.assertEqual(out['diagnostics']['status'], 'budget_exceeded')
        out = M.extract_features(record(Atoms('C', positions=[[0,0,0]], cell=[.01]*3, pbc=True)))
        self.assertEqual(out['diagnostics']['status'], 'budget_exceeded')

    def test_configuration_rejects_nonfinite_or_fractional_budgets(self):
        for settings in [{'cutoff_scale': math.inf}, {'sensitivity_fraction': math.nan},
                         {'max_atoms': True}, {'max_neighbor_edges': 3.5}, {'min_separation_angstrom': math.inf}]:
            with self.assertRaises(ValueError):
                M.GeometryConfig(**settings)

    def test_cache_binds_geometry_parameters_version_and_ignores_targets(self):
        original = record(bulk('Al', 'fcc', a=4.05))
        with tempfile.TemporaryDirectory() as directory:
            first = M.extract_features(original, cache_dir=directory)
            again = M.extract_features(dict(original, tc=9999, family='made-up-label'), cache_dir=directory)
            self.assertFalse(first['diagnostics']['cached'])
            self.assertTrue(again['diagnostics']['cached'])
            np.testing.assert_allclose(first['values'], again['values'], equal_nan=True)
            shifted_atom = dict(original, lattice_mat=(np.asarray(original['lattice_mat'])*1.01).tolist())
            changed = M.extract_features(shifted_atom, cache_dir=directory)
            self.assertNotEqual(first['diagnostics']['cache_key'], changed['diagnostics']['cache_key'])
            settings = M.extract_features(original, config=M.GeometryConfig(cutoff_scale=1.2), cache_dir=directory)
            self.assertNotEqual(first['diagnostics']['cache_key'], settings['diagnostics']['cache_key'])
            with patch.object(M, 'FEATURE_VERSION', 'test-new-generation'):
                version = M.extract_features(original, cache_dir=directory)
                self.assertNotEqual(first['diagnostics']['cache_key'], version['diagnostics']['cache_key'])
            saved = Path(directory, first['diagnostics']['cache_key']+'.json')
            payload = json.loads(saved.read_text())
            self.assertIn(None, payload['values'])
            saved.write_text('{damaged')
            repaired = M.extract_features(original, cache_dir=directory)
            self.assertFalse(repaired['diagnostics']['cached'])
            np.testing.assert_allclose(first['values'], repaired['values'], equal_nan=True)


if __name__ == '__main__':
    unittest.main()
