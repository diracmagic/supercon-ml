"""Scientific classifications and bounded orchestration, without downloading MACE."""
import builtins
import dataclasses
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import phonon_check as PC
import screen_tracks as ST


def structure(element="B"):
    return {"elements": [element], "lattice_mat": [[3, 0, 0], [0, 3, 0], [0, 0, 3]],
            "coords": [[0, 0, 0]], "cartesian": False}


class PhononNumericsTests(unittest.TestCase):
    def test_numerical_acoustic_noise_is_not_a_significant_imaginary_mode(self):
        result = PC.summarize_modes([[0, -0.0005, 0.01]], [[0, 0, 0]], PC.PhononConfig(), 0.001)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"], "no_significant_imaginary_modes_sampled")
        self.assertEqual(result["significant_imaginary_modes"], 0)

    def test_imaginary_mode_and_non_equilibrium_are_distinct_outcomes(self):
        cfg = PC.PhononConfig()
        result = PC.summarize_modes([[0, -0.003, 0.01]], [[0, 0, 0]], cfg, 0.01)
        self.assertEqual(result["verdict"], "imaginary_modes_sampled")
        self.assertAlmostEqual(result["min_signed_mode_energy_mev"], -3)
        shifted = PC.summarize_modes([[0, -0.003, 0.01]], [[0, 0, 0]], cfg, 0.5)
        self.assertEqual(shifted["status"], "inconclusive")
        self.assertEqual(shifted["verdict"], "not_assessed_non_equilibrium")

    def test_missing_modes_cannot_pass(self):
        for modes in ([], [[float("nan"), 1]], [[]]):
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                PC.summarize_modes(modes, [[0, 0, 0]], PC.PhononConfig(), 0)

    def test_default_mesh_includes_gamma_and_zone_boundaries(self):
        points = PC.q_points((2, 2, 2))
        self.assertEqual(len(points), 8)
        self.assertTrue(np.any(np.all(points == 0, axis=1)))
        self.assertEqual(set(points.ravel()), {0, -0.5})
        with self.assertRaises(ValueError):
            PC.PhononConfig(q_mesh=(3, 3, 3)).validate()

    def test_partial_periodicity_and_singular_cell_are_rejected(self):
        for atoms in (dict(structure(), pbc=[True, True, False]), dict(structure(), lattice_mat=np.zeros((3, 3)))):
            with self.assertRaises(ValueError):
                PC.canonical_structure(atoms)

    def test_cache_identity_changes_with_geometry_method_and_software(self):
        atoms = PC.canonical_structure(structure())
        cfg = PC.PhononConfig()
        key = PC.calculation_key(atoms, cfg)
        changed = PC.canonical_structure(dict(atoms, coords=[[0.1, 0, 0]]))
        self.assertNotEqual(key, PC.calculation_key(changed, cfg))
        self.assertNotEqual(key, PC.calculation_key(atoms, dataclasses.replace(cfg, displacement_angstrom=0.02)))
        with patch.object(PC, "_versions", return_value={"ase": "a-different-version"}):
            self.assertNotEqual(key, PC.calculation_key(atoms, cfg))


class PhononASEIntegrationTests(unittest.TestCase):
    def test_real_ase_finite_displacements_with_emt_interface_fixture(self):
        """Run actual ASE forces/force constants; EMT substitutes for MACE only.

        This is an interface regression test, not a MACE material prediction. No
        checkpoint is downloaded and no scientific result is published.
        """
        try:
            from ase.build import bulk
            from ase.calculators.emt import EMT
        except ImportError:
            self.skipTest("optional ASE dependency is absent")
        atoms = bulk("Al", "fcc", a=4.05)
        raw = {"elements": atoms.get_chemical_symbols(), "lattice_mat": atoms.cell.array.tolist(),
               "coords": atoms.get_scaled_positions().tolist()}
        calculator = EMT()
        calculator.z_table = SimpleNamespace(zs=[13])
        modules = {"torch": SimpleNamespace(set_num_threads=lambda _: None),
                   "mace.calculators": SimpleNamespace(mace_mp=lambda **_: calculator)}
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, modules):
            with patch.object(PC, "_weights_hash", return_value="EMT-interface-fixture-not-MACE"):
                result = PC._calculate(PC.canonical_structure(raw), PC.PhononConfig(), Path(temp) / "forces")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["verdict"], "no_significant_imaginary_modes_sampled")
        self.assertEqual(len(result["sampled_q_points"]), 8)
        self.assertEqual(result["modes_per_q"], 3)
        self.assertTrue(np.isfinite(result["min_signed_mode_energy_mev"]))
        self.assertLess(result["max_residual_force_ev_angstrom"], 1e-6)


class PhononOrchestrationTests(unittest.TestCase):
    def fake_worker(self, request, response, timeout, threads):
        payload = json.loads(request.read_text())
        config = PC.PhononConfig(**payload["config"])
        out = dict(PC._provenance(payload["structure"], config), status="completed",
                   verdict="no_significant_imaginary_modes_sampled")
        PC._write(response, out)
        return SimpleNamespace(returncode=0, stderr="")

    def test_only_top_n_in_domain_storm_are_selected_and_cached(self):
        candidates = [{"jid": "far", "model": "Storm", "novelty": 2, "tc": 100},
                      {"jid": "unknown", "model": "Storm", "tc": 200},
                      {"jid": "hurricane", "model": "Hurricane", "novelty": 0.5, "tc": 200},
                      {"jid": "lower", "novelty": 0.5, "tc": 10},
                      {"jid": "higher", "novelty": 0.5, "tc": 20}]
        atoms = {r["jid"]: structure() for r in candidates}
        config = PC.PhononConfig(max_candidates=1)
        with tempfile.TemporaryDirectory() as temp, patch.object(PC, "_subprocess_check", side_effect=self.fake_worker) as worker:
            out = PC.run_checks(candidates, atoms, temp, config=config)
            self.assertEqual(out["eligible"], 2)
            self.assertEqual(out["selected"], 1)
            self.assertEqual(out["materials"][0]["material_id"], "higher")
            self.assertEqual(worker.call_count, 1)
            reused = PC.run_checks(candidates, atoms, temp, config=config)
            self.assertTrue(reused["materials"][0]["cached"])
            self.assertEqual(worker.call_count, 1)

    def test_atom_budget_prevents_starting_a_worker(self):
        large = structure()
        large["elements"] *= 13
        large["coords"] *= 13
        with tempfile.TemporaryDirectory() as temp, patch.object(PC, "_subprocess_check") as worker:
            result = PC.run_checks([{"jid": "large", "novelty": 0.5}], {"large": large}, temp)
            self.assertEqual(result["materials"][0]["status"], "budget_exceeded")
            worker.assert_not_called()

    def test_timeout_is_not_reused_as_a_success(self):
        candidates = [{"jid": "b", "novelty": 0.5}]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(PC, "_subprocess_check", side_effect=subprocess.TimeoutExpired("worker", 1)):
                first = PC.run_checks(candidates, {"b": structure()}, temp)
            self.assertEqual(first["materials"][0]["status"], "timeout")
            with patch.object(PC, "_subprocess_check", side_effect=self.fake_worker) as worker:
                second = PC.run_checks(candidates, {"b": structure()}, temp)
            self.assertEqual(second["materials"][0]["status"], "completed")
            self.assertEqual(worker.call_count, 1)

    def test_exhausted_total_budget_does_not_start_another_worker(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(PC.time, "monotonic", side_effect=[0, 1, 1]):
            with patch.object(PC, "_subprocess_check") as worker:
                result = PC.run_checks([{"jid": "b", "novelty": 0.5}], {"b": structure()}, temp,
                                       config=PC.PhononConfig(max_total_seconds=0.1))
        self.assertEqual(result["materials"][0]["status"], "budget_exceeded")
        self.assertIn("total", result["materials"][0]["reason"])
        worker.assert_not_called()

    def test_missing_optional_dependency_is_unavailable(self):
        real_import = builtins.__import__
        def no_torch(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("torch deliberately absent")
            return real_import(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=no_torch):
            result = PC._calculate(PC.canonical_structure(structure()), PC.PhononConfig(), Path("unused"))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["verdict"], "not_assessed")

    def test_unsupported_element_is_rejected_before_force_evaluation(self):
        class FakeAtoms:
            def __init__(self, **kwargs):
                self.symbols = kwargs["symbols"]
                self.numbers = [118]
            def get_chemical_symbols(self):
                return self.symbols
        modules = {"torch": SimpleNamespace(set_num_threads=lambda _: None),
                   "ase": SimpleNamespace(Atoms=FakeAtoms), "ase.phonons": SimpleNamespace(Phonons=object),
                   "mace.calculators": SimpleNamespace(mace_mp=lambda **_: SimpleNamespace(z_table=SimpleNamespace(zs=[5])))}
        with patch.dict(sys.modules, modules), patch.object(PC, "_weights_hash", return_value="fixture"):
            result = PC._calculate(PC.canonical_structure(structure("Og")), PC.PhononConfig(), Path("unused"))
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["unsupported_elements"], ["Og"])

    def test_nonstationary_input_stops_before_expensive_displacements(self):
        class FakeAtoms:
            def __init__(self, **kwargs):
                self.numbers = [5]
            def get_chemical_symbols(self):
                return ["B"]
            def get_forces(self):
                return np.array([[0.4, 0, 0]])
        modules = {"torch": SimpleNamespace(set_num_threads=lambda _: None),
                   "ase": SimpleNamespace(Atoms=FakeAtoms), "ase.phonons": SimpleNamespace(Phonons=object),
                   "mace.calculators": SimpleNamespace(mace_mp=lambda **_: SimpleNamespace(z_table=SimpleNamespace(zs=[5])))}
        with patch.dict(sys.modules, modules), patch.object(PC, "_weights_hash", return_value="fixture"):
            result = PC._calculate(PC.canonical_structure(structure()), PC.PhononConfig(), Path("unused"))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["verdict"], "not_assessed_non_equilibrium")
        self.assertIn("were not run", result["reason"])


class DirectedTrackTests(unittest.TestCase):
    def test_borocarbides_are_in_both_tracks_without_hiding_exploration(self):
        ranked = pd.DataFrame([{"jid": "bc", "model": "Storm", "novelty": 0.5, "storm_tc": 10},
                               {"jid": "b", "model": "Storm", "novelty": 2, "storm_tc": 100},
                               {"jid": "c", "model": "Storm", "novelty": float("nan"), "storm_tc": 20},
                               {"jid": "h", "model": "Hurricane", "novelty": 0.5, "storm_tc": 200}])
        atoms = {"bc": {"elements": ["B", "C", "Nb"]}, "b": {"elements": ["B", "Ti"]},
                 "c": {"elements": ["C", "Ti"]}, "h": {"elements": ["B", "C"]}}
        tracks = ST.directed_tracks(ranked, atoms)["tracks"]
        self.assertEqual([r["jid"] for r in tracks["borides"]["in_domain"]], ["bc"])
        self.assertEqual([r["jid"] for r in tracks["carbides"]["in_domain"]], ["bc"])
        self.assertEqual([r["jid"] for r in tracks["borides"]["exploration"]], ["b"])
        self.assertEqual([r["jid"] for r in tracks["carbides"]["exploration"]], ["c"])

    def test_known_nonmetal_is_not_admitted_and_missing_distance_is_not_in_domain(self):
        ranked = pd.DataFrame([{"jid": "b", "model": "Storm", "gap": 1.0, "novelty": 0.1}])
        self.assertFalse(ST.directed_tracks(ranked, {"b": structure()})["tracks"]["borides"]["in_domain"])
        self.assertFalse(ST.in_training_domain({"outside": True, "novelty": 0.5}))
        self.assertFalse(ST.in_training_domain({}))

    def test_film_anchor_is_display_only_and_keeps_onset_distinct_from_zero_resistance(self):
        path = Path(__file__).resolve().parents[1] / "data" / "hurricane_anchors.json"
        anchors = json.loads(path.read_text(encoding="utf-8"))
        film = next(r for r in anchors["materials"] if r.get("source") == "ko2025")
        self.assertEqual(film["use"], "show")
        self.assertEqual(film["tc_criterion"], "resistive onset")
        self.assertGreater(film["tc_exp"], film["tc_zero"])


if __name__ == "__main__":
    unittest.main()
