import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane7 as H7


class Hurricane7Tests(unittest.TestCase):
    def setUp(self):
        self.data = H7.prepare_smoke()
        self.parents = self.data["parents"]
        self.train, self.test, self.held = H7.outer_split(self.parents, "cuprate")

    def test_outer_labels_and_features_cannot_choose_alpha_coefficients_terms_or_stability(self):
        variants = []
        changed_labels = copy.deepcopy(self.data)
        changed_labels["parents"].loc[self.test, "tc"] = np.where(self.parents.loc[self.test, "tc"] > 0, 0., 10000.)
        variants.append(changed_labels)
        changed_features = copy.deepcopy(self.data)
        changed_features["geometry"][self.test] = 1e8
        changed_features["extras"][self.test, 0] = 1e10
        changed_features["extras"][self.test, 1:] = 1 - changed_features["extras"][self.test, 1:]
        variants.append(changed_features)
        for design in H7.DESIGNS:
            with self.subTest(design=design):
                alpha, record = H7.select_alpha(self.data, design, self.train, self.held)
                fitted = H7.fit_split(self.data, design, alpha, self.train, self.held, seed=7)
                stability = H7.stable_terms(fitted, self.parents.iloc[self.train].tc.to_numpy() > 0,
                                           self.parents.iloc[self.train].family.to_numpy(),
                                           self.parents.iloc[self.train].system.to_numpy(), resamples=4)
                for changed in variants:
                    other_alpha, other_record = H7.select_alpha(changed, design, self.train, self.held)
                    other = H7.fit_split(changed, design, other_alpha, self.train, self.held, seed=7)
                    self.assertEqual(alpha, other_alpha)
                    self.assertEqual(record, other_record)
                    self.assertEqual(fitted.identity(), other.identity())
                    other_stability = H7.stable_terms(other, changed["parents"].iloc[self.train].tc.to_numpy() > 0,
                                                     self.parents.iloc[self.train].family.to_numpy(),
                                                     self.parents.iloc[self.train].system.to_numpy(), resamples=4)
                    self.assertEqual(stability, other_stability)

    def test_inner_systems_and_pca_rows_are_train_only_for_every_alpha(self):
        for design in H7.DESIGNS:
            alpha, records = H7.select_alpha(self.data, design, self.train, self.held)
            self.assertIn(alpha, H7.PROTOCOL["alpha_grid"])
            self.assertEqual(len(records), 4)
            for record in records:
                self.assertEqual(len(record["family_mean_fold_auc"]), 3)
                self.assertAlmostEqual(record["mean_observed_pu_auc"], np.mean([v["mean_fold_auc"] for v in record["family_mean_fold_auc"].values()]))
                for fold in record["folds"]:
                    self.assertFalse(set(fold["training_systems"]) & set(fold["validation_systems"]))
                    self.assertFalse(set(fold["training_systems"]) & self.held)
                    self.assertFalse(set(fold["training_ids"]) & set(fold["validation_ids"]))
                    self.assertEqual(fold["pca_auxiliary_rows"], 0)

    def test_inner_selection_metric_is_invariant_to_each_fold_score_origin_and_scale(self):
        families = list(H7.PROTOCOL["families"])[1:]
        rng = np.random.default_rng(87)
        folds, transformed = [], []
        for fold in range(3):
            rows = pd.DataFrame({"family": np.repeat(families, 4), "tc": np.tile([0., 1., 0., 1.], 3)})
            score = rng.normal(size=len(rows))
            folds.append({"family_metrics": H7.validation_family_metrics(rows, score, families)})
            transformed.append({"family_metrics": H7.validation_family_metrics(rows, score * (fold + 2) + 10000 * fold, families)})
        self.assertEqual(H7.inner_objective(folds, families), H7.inner_objective(transformed, families))
        invalid = copy.deepcopy(folds)
        for fold in invalid:
            fold["family_metrics"][families[0]]["observed_pu_auc"] = None
        self.assertIsNone(H7.inner_objective(invalid, families)["macro"])

    def test_held_system_is_removed_from_other_training_families_too(self):
        parents = self.parents.copy(deep=True)
        iron = np.flatnonzero(parents.family.to_numpy() == "iron-based")[0]
        parents.loc[iron, "system"] = parents.loc[self.test[0], "system"]
        train, _, _ = H7.outer_split(parents, "cuprate")
        self.assertNotIn(iron, train)

    def test_complete_membership_exclusions_precede_deduplication(self):
        rows, parents = [], []
        for mid, families in H7.MIXED_FAMILIES.items():
            parents.append({"material_id": mid, "family": families[0], "tc": 0.})
            for family in families:
                cls = {"cuprate": "Cuprate", "iron-based": "Ferrite", "other oxide": "Oxide"}[family]
                rows.append({"material_id_2": mid, "sc_class": cls, "formula_sc": "duplicate-formula"})
        parents.append({"material_id": "mp-pure", "family": "heavy-fermion", "tc": 1.})
        rows.append({"material_id_2": "mp-pure", "sc_class": "Heavy_fermion", "formula_sc": "duplicate-formula"})
        with patch.object(H7.H5, "parent_frame", return_value=pd.DataFrame(parents)), \
                patch.dict(H7.PROTOCOL, {"cohort": {"h7": 1, "positive": 1, "unlabeled": 0}}):
            result, exclusions = H7.parent_cohort(pd.DataFrame(rows))
        self.assertEqual(result.material_id.tolist(), ["mp-pure"])
        self.assertEqual(result.full_family_membership.tolist(), [["heavy-fermion"]])
        self.assertEqual({r["material_id"] for r in exclusions}, set(H7.MIXED_FAMILIES))

    def test_hidden_secondary_family_or_known_mixed_id_is_rejected(self):
        data = copy.deepcopy(self.data)
        data["parents"].at[0, "full_family_membership"] = ["cuprate", "other oxide"]
        with self.assertRaisesRegex(ValueError, "Complete original family membership"):
            H7.validate_data(data, smoke=True)
        data = copy.deepcopy(self.data)
        data["parents"].at[0, "material_id"] = "mp-5670"
        with self.assertRaisesRegex(ValueError, "mixed-family"):
            H7.validate_data(data, smoke=True)

    def test_pair_weights_are_equal_by_eligible_family_and_positive_system(self):
        rows = [("a", "p-a1", True)] * 10 + [("a", "p-a2", True), ("a", "u-a1", False), ("a", "u-a2", False)]
        rows += [("b", "p-b", True), ("b", "u-b", False)]
        rows += [("c", "c-only-u", True), ("c", "c-only-u", False), ("c", "c-other-p", True)]
        families, systems, positive = map(np.array, zip(*rows))
        matrix = np.arange(len(rows), dtype=float)[:, None]
        _, weights, diagnostic = H7.pair_data(matrix, positive, families, systems, seed=7)
        self.assertAlmostEqual(weights.mean(), 1.)
        for value in diagnostic["family_weight_fraction"].values():
            self.assertAlmostEqual(value, 1 / 3)
        self.assertAlmostEqual(diagnostic["positive_system_weight_fraction_within_family"]["a"]["p-a1"], .5)
        self.assertEqual(set(diagnostic["positive_system_weight_fraction_within_family"]["c"]), {"c-other-p"})

    def test_pair_preferences_never_cross_family_or_same_system(self):
        X = np.eye(6)
        families = np.array(["a", "a", "a", "b", "b", "b"])
        systems = np.array(["same", "same", "other", "same", "same", "other"])
        positive = np.array([True, False, False, True, False, False])
        pairs, _, _ = H7.pair_data(X, positive, families, systems, seed=7)
        for pair in pairs:
            p, u = np.flatnonzero(pair > 0)[0], np.flatnonzero(pair < 0)[0]
            self.assertTrue(positive[p])
            self.assertFalse(positive[u])
            self.assertEqual(families[p], families[u])
            self.assertNotEqual(systems[p], systems[u])

    def test_system_bootstrap_multiplicity_cannot_split_rows_of_same_system(self):
        with self.assertRaisesRegex(ValueError, "constant across every row"):
            H7.pair_data(np.eye(3), [True, False, False], ["a"] * 3, ["same", "same", "other"],
                         seed=7, multiplicity=[1, 2, 1])

    def test_missing_tetrahedral_columns_drop_using_train_fraction_only(self):
        data = copy.deepcopy(self.data)
        j = list(H7.MF.FEATURE_NAMES).index("tetrahedral_order_mean")
        data["geometry"][self.train, j] = np.nan
        data["geometry"][self.test, j] = 1.
        fitted = H7.fit_split(data, "R1", .1, self.train, self.held, seed=7)
        self.assertNotIn("tetrahedral_order_mean", fitted.features.names)
        coverage = H7.feature_coverage(data["parents"].iloc[self.train], data["geometry"][self.train], data["extras"][self.train])
        self.assertEqual(coverage["all"]["features"]["tetrahedral_order_mean"]["finite_fraction"], 0.)

    def test_empty_rule_is_legal_and_all_ties_have_fractional_budget_recall(self):
        data = copy.deepcopy(self.data)
        data["geometry"][:] = np.nan
        data["extras"][:] = 0.
        data["extras"][:, 0] = 10.
        for design in ("R0", "R1"):
            fitted = H7.fit_split(data, design, .1, self.train, self.held, seed=7)
            self.assertEqual(fitted.fit_info["status"], "empty")
            np.testing.assert_array_equal(fitted.predict(data["geometry"][self.test], data["extras"][self.test]), np.zeros(len(self.test)))
        score = H7.metrics(np.array([True, True, True, False, False]), np.zeros(5))
        self.assertEqual(score["observed_pu_auc"], .5)
        self.assertAlmostEqual(score["recall_at_budget"], .2)
        self.assertNotIn("brier", score)

    def test_nonconverged_stability_cannot_become_a_common_rule(self):
        fitted = types.SimpleNamespace(matrix=np.tile([[-1.], [1.]], (3, 1)), design="R1", alpha=.1,
                                       coefficient=np.array([1.]), terms=types.SimpleNamespace(names=["toy"]),
                                       fit_info={"status": "completed"})
        families = np.repeat(["a", "b", "c"], 2)
        with patch.object(H7, "fit_head", return_value=(np.array([1.]), {"status": "not_converged"})):
            result = H7.stable_terms(fitted, np.tile([False, True], 3), families, np.arange(6), resamples=4)
        self.assertEqual(result["common_terms"], [])
        self.assertEqual(result["status"], "inconclusive_nonconvergence")

    def test_forbidden_source_metadata_and_raw_dft_do_not_enter_features(self):
        parents = pd.DataFrame([{"elec": H7.H5.electronic_row(.1, 0., .2, -1.), "tc": 1., "material_id": "id", "n_entries": 1}])
        before = H7.parent_extras(parents, np.array([10.]))
        parents.at[0, "tc"], parents.at[0, "n_entries"], parents.at[0, "material_id"] = 10000., 100000, "other-id"
        parents.at[0, "elec"] = H7.H5.electronic_row(.9, 0., 100000., -100000.)
        np.testing.assert_array_equal(before, H7.parent_extras(parents, np.array([10.])))
        self.assertEqual(set(H7.EXTRA_NAMES), {"volume_per_atom_angstrom3", *H7.FLAGS})

    def test_geometry_and_per_atom_volume_preserve_equivalent_supercell_source(self):
        atom = {"lattice_mat": (np.eye(3) * 3).tolist(), "coords": [[0., 0., 0.]], "elements": ["Cu"], "cartesian": False}
        doubled = {"lattice_mat": np.diag([6., 3., 3.]).tolist(), "coords": [[0., 0., 0.], [.5, 0., 0.]],
                   "elements": ["Cu", "Cu"], "cartesian": False}
        frame = pd.DataFrame([{"id": "first", "atoms": atom}, {"id": "doubled", "atoms": doubled}])
        geometry, volume, diagnostic = H7.geometry_rows(frame, None)
        np.testing.assert_allclose(geometry[0], geometry[1], atol=1e-10, equal_nan=True)
        self.assertAlmostEqual(volume[0], volume[1])
        self.assertTrue(all(d["status"] == "ok" for d in diagnostic))

    def test_safe_flags_match_frozen_h5_threshold_units(self):
        self.assertEqual(H7.H5.electronic_row(.005, 1e-4, 0, 0)["is_metal"], 1.)
        self.assertEqual(H7.H5.electronic_row(.006, 1.01e-4, 0, 0)["small_gap"], 1.)
        self.assertEqual(H7.H5.electronic_row(.006, 1.01e-4, 0, 0)["is_magnetic"], 1.)
        self.assertEqual(H7.H5.electronic_row(.006, 1e-4, 0, 0)["is_magnetic"], 0.)

    def test_paired_system_bootstrap_is_zero_for_identical_forecasts(self):
        rng = np.random.default_rng(2)
        score = rng.normal(size=len(self.parents))
        result = H7.paired_intervals(self.parents, {d: score for d in H7.DESIGNS}, resamples=50)
        for comparison in result.values():
            for quantity in comparison["quantities"].values():
                self.assertEqual(quantity["delta_new_minus_reference"], 0.)
                self.assertEqual(quantity["lower95"], 0.)
                self.assertEqual(quantity["upper95"], 0.)

    def test_effort_strata_compare_only_within_family_and_handle_empty_strata(self):
        rng = np.random.default_rng(51)
        scores = rng.normal(size=len(self.parents))
        shifted = scores.copy()
        for index, family in enumerate(H7.PROTOCOL["families"]):
            shifted[self.parents.family.to_numpy() == family] += index * 10000
        a = H7.stratum_metrics(self.parents, scores, np.ones(len(scores), bool))
        b = H7.stratum_metrics(self.parents, shifted, np.ones(len(scores), bool))
        self.assertEqual(a, b)
        empty = H7.stratum_metrics(self.parents, scores, np.zeros(len(scores), bool))
        self.assertIsNone(empty["macro_among_defined_families"]["observed_pu_auc"]["macro"])
        self.assertEqual(empty["macro_among_defined_families"]["observed_pu_auc"]["n_defined_families"], 0)

    def test_protocol_is_written_before_real_input_loading_and_failure_is_explicit(self):
        with tempfile.TemporaryDirectory(dir=H7.P.ROOT.parent) as temporary:
            path = Path(temporary)
            def fail_input():
                self.assertTrue((path / "protocol.json").exists())
                frozen = json.loads((path / "protocol.json").read_text())
                self.assertEqual(H7.digest(frozen), (path / "protocol.sha256").read_text().strip())
                raise ValueError("no source")
            with patch.object(H7, "prepare_real", fail_input), self.assertRaisesRegex(ValueError, "no source"):
                H7.run(output_dir=path)
            self.assertEqual(json.loads((path / "report.json").read_text())["status"], "failed_preparation")

    def test_offline_smoke_has_all_models_manifests_finite_scores_and_no_release(self):
        with tempfile.TemporaryDirectory(dir=H7.P.ROOT.parent) as temporary, \
                patch.object(H7, "prepare_real", side_effect=AssertionError("offline only")):
            report = H7.run(smoke=True, output_dir=Path(temporary))
            self.assertEqual(report["status"], "completed")
            self.assertFalse(report["adopted"])
            self.assertEqual(report["actual_precursor_training_records"], 0)
            self.assertEqual(len(report["fits"]), 12)
            for name in ("protocol.json", "protocol.sha256", "run.json", "input-manifest.json", "input-parents.csv", "folds.json", "parents.csv"):
                self.assertTrue((Path(temporary) / name).is_file(), name)
            predictions = pd.read_csv(Path(temporary) / "parents.csv")
            self.assertTrue(np.isfinite(predictions.catalog_rank_score).all())
            self.assertEqual(set(predictions.design), set(H7.DESIGNS))
            json.loads((Path(temporary) / "report.json").read_text(), parse_constant=lambda t: self.fail(t))

    def test_failed_design_is_retained_without_fabricated_zero_forecasts(self):
        actual = H7.select_alpha
        def one_failure(data, design, train, held):
            if design == "R1":
                raise ValueError("deliberate fit failure")
            return actual(data, design, train, held)
        with tempfile.TemporaryDirectory(dir=H7.P.ROOT.parent) as temporary, patch.object(H7, "select_alpha", one_failure):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                H7.run(smoke=True, output_dir=Path(temporary))
            report = json.loads((Path(temporary) / "report.json").read_text())
            self.assertIsNone(report["macro"]["R1"]["observed_pu_auc"])
            self.assertEqual(report["designs"]["R1"]["status"], "incomplete")
            frame = pd.read_csv(Path(temporary) / "parents.csv")
            self.assertTrue(frame.loc[frame.design == "R1", "catalog_rank_score"].isna().all())


if __name__ == "__main__":
    unittest.main()
