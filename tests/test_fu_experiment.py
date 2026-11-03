"""Synthetic adapter and isolation checks; no scientific model result is tested."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
import fu_experiment as F


class ExperimentIsolationTests(unittest.TestCase):
    def protocol_path(self, version=1):
        names = ("protocol.json", "fu-lattice-v1.json") if version == 1 else ("protocol-v2.json", "fu-lattice-v2.json")
        candidates = [ROOT / "protocol" / name for name in names]
        return next(p for p in candidates if p.exists())

    def bank(self):
        import fu_graphlets as G
        return {"status": "passed", "qc_passed": True, "protocol_sha256": F.PROTOCOL_SHA256,
                "motif_masks": list(G.GRAPH_MASKS), "exact_features": np.ones((11, 14)).tolist(),
                "neural_features": np.ones((11, 14)).tolist(), "feature_names": [str(i) for i in range(14)]}

    def test_protocol_bytes_and_nonoverwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            out = Path(temporary) / "run"
            _, fingerprint = F.freeze_protocol(self.protocol_path(), out)
            self.assertEqual(fingerprint, F.PROTOCOL_SHA256)
            self.assertEqual((out / "protocol.json").read_bytes(), self.protocol_path().read_bytes())
            with self.assertRaises(ValueError):
                F.freeze_protocol(self.protocol_path(), out)
            changed = Path(temporary) / "changed.json"
            changed.write_bytes(self.protocol_path().read_bytes() + b" ")
            with self.assertRaises(ValueError):
                F.freeze_protocol(changed, Path(temporary) / "other")

    def test_bank_gate_precedes_any_target_loading(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            bad = {"status": "failed", "qc_passed": False, "protocol_sha256": F.PROTOCOL_SHA256}
            with patch.object(F, "load_bank", return_value=bad), patch.object(F, "load_data") as loader:
                report = F.run(model="storm", protocol_path=self.protocol_path(), output_dir=Path(temporary) / "run")
            loader.assert_not_called()
            self.assertEqual(report["status"], "blocked_bank_qc")
            self.assertTrue(all(v["status"] == "not_run" for v in report["arms"].values()))
            self.assertEqual(set(report["contrasts"]), {a + "-" + b for a, b in F.CONTRASTS})

    def test_real_bank_binding_and_no_synthetic_escape(self):
        good = self.bank()
        F.validate_bank(good, F.PROTOCOL_SHA256)
        for alteration in [{"protocol_sha256": "other"}, {"qc_passed": False},
                           {"synthetic": True}, {"motif_masks": list(reversed(good["motif_masks"]))},
                           {"neural_features": None}]:
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                F.validate_bank({**good, **alteration}, F.PROTOCOL_SHA256)
        with self.assertRaisesRegex(ValueError, "different protocol"):
            F.validate_bank(good, F.PROTOCOL_V2_SHA256)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            F.validate_bank({**good, "protocol_sha256": "unknown"}, "unknown")

    def test_v2_freeze_fixture_and_map_are_bound_to_v2(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            out = Path(temporary) / "v2"
            _, fingerprint = F.freeze_protocol(self.protocol_path(2), out)
            self.assertEqual(fingerprint, F.PROTOCOL_V2_SHA256)
            fixture = F.load_bank(None, out / "protocol.json", out, smoke=True)
            self.assertEqual(fixture["protocol_sha256"], fingerprint)
            F.validate_bank(fixture, fingerprint, smoke=True)
            with self.assertRaisesRegex(ValueError, "different protocol"):
                F.validate_bank(fixture, F.PROTOCOL_SHA256, smoke=True)

    def test_real_requires_separate_bank_job(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            with self.assertRaises(ValueError):
                F.load_bank(None, self.protocol_path(), Path(temporary), smoke=False)

    def test_mapping_threshold_retains_rows_and_missingness(self):
        data = {"ids": np.array(["a", "b"]), "groups": np.array(["x", "y"]), "atoms": [{}, {}]}
        good = np.eye(11)[0]
        diagnostics = [{"structure_mapped": True, "center_coverage_fraction": 1.},
                       {"structure_mapped": False, "center_coverage_fraction": .5}]
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            out = Path(temporary)
            with patch("fu_graphlets.extract_graphlets", side_effect=[(good, diagnostics[0]), (np.full(11, np.nan), diagnostics[1])]):
                with self.assertRaisesRegex(ValueError, "95%"):
                    F.map_structures(data, self.bank(), out, fingerprint=F.PROTOCOL_SHA256)
            with np.load(out / "motif-inputs.npz", allow_pickle=False) as saved:
                self.assertEqual(saved["frequencies"].shape, (2, 11))
                self.assertTrue(np.isnan(saved["frequencies"][1]).all())
                self.assertEqual(saved["ids"].tolist(), ["a", "b"])

    def test_storm_baseline_matches_existing_forecaster(self):
        import storm7 as S7
        rng = np.random.default_rng(71)
        D, G = rng.normal(size=(40, 5)), rng.normal(size=(40, 19))
        y = np.exp(D[:, 0])
        train, test = np.arange(30), np.arange(30, 40)
        params = dict(max_iter=3, max_leaf_nodes=3, min_samples_leaf=3)
        ours, _ = F.storm_forecast(D, G, np.empty((40, 0)), y, train, test, seed=7, params=params)
        baseline, _ = S7.forecast("U0", D[train], G[train], y[train], D[test], G[test], seed=7, params=params)
        np.testing.assert_array_equal(ours, baseline)

    def test_storm_added_train_missing_column_cannot_be_rescued_by_test(self):
        rng = np.random.default_rng(11)
        D, G = rng.normal(size=(30, 3)), rng.normal(size=(30, 19))
        additions = np.full((30, 2), np.nan)
        additions[:, 0] = rng.normal(size=30)
        additions[20:, 1] = 1000.
        _, identity = F.storm_forecast(D, G, additions, np.ones(30), np.arange(20), np.arange(20, 30),
            seed=7, params=dict(max_iter=2, max_leaf_nodes=3, min_samples_leaf=3))
        self.assertEqual(identity["added_keep"], [True, False])

    def test_ranker_baseline_and_addition_fit_use_training_rows_only(self):
        import hurricane7 as H
        data = H.prepare_smoke()
        parents = data["parents"]
        train, test, held = H.outer_split(parents, H.PROTOCOL["families"][0])
        added = np.zeros((len(parents), 1))
        added[test] = 1e12
        fitted = F.fit_ranker(data, added, train, held, .1, 7)
        self.assertEqual(fitted.extra_scale.keep.tolist(), [False])
        self.assertFalse(set(fitted.training_systems) & held)
        baseline = H.Ranker("R0", .1, 7).fit(data["geometry"][train], data["extras"][train],
            parents.iloc[train].tc.to_numpy() > 0, parents.iloc[train].family.to_numpy(), parents.iloc[train].system.to_numpy())
        np.testing.assert_allclose(fitted.predict(data["geometry"][test], data["extras"][test], added[test]),
            baseline.predict(data["geometry"][test], data["extras"][test]), rtol=0, atol=0)
        with self.assertRaisesRegex(ValueError, "Held"):
            F.fit_ranker(data, added, np.concatenate([train, test[:1]]), held, .1, 7)

    def test_shared_bootstrap_and_all_contrasts(self):
        y = np.array([1., 3., 2., 5.])
        groups = np.array(["a", "a", "b", "c"], dtype=object)
        predictions = {arm: y + offset for arm, offset in zip(F.ARMS, [1., .8, .6, .4])}
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            result = F.storm_contrasts(y, predictions, groups, {"overall": np.ones(4, bool)},
                                       repetitions=20, out=Path(temporary))
            self.assertEqual(len(result), 6)
            for a, b in F.CONTRASTS:
                expected = abs(y - predictions[a]).mean() - abs(y - predictions[b]).mean()
                self.assertAlmostEqual(result[a + "-" + b]["overall"]["delta_new_minus_reference"], expected)
            with np.load(Path(temporary) / "bootstrap-draws.npz", allow_pickle=False) as draws:
                self.assertEqual(draws["draws"].shape, (20, 3))
                for name in draws.files:
                    self.assertNotEqual(draws[name].dtype.kind, "O")
                self.assertEqual(draws["systems"].tolist(), ["a", "b", "c"])
                np.testing.assert_array_equal(draws["draws"], np.random.default_rng(7).integers(0, 3, (20, 3)))

    def test_complete_synthetic_adapters_have_every_arm_and_contrast(self):
        # This fixture does not run a quantum solver or access real targets.
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            for model in ("storm", "hurricane"):
                with self.subTest(model=model):
                    out = Path(temporary) / model
                    report = F.run(model=model, protocol_path=self.protocol_path(2 if model == "storm" else 1), output_dir=out, smoke=True)
                    self.assertEqual(report["status"], "completed", report["failures"])
                    self.assertFalse(report["scientific_evidence"])
                    self.assertTrue(report["bank"]["synthetic_adapter_fixture"])
                    self.assertTrue(all(v["status"] == "completed" for v in report["arms"].values()))
                    self.assertEqual(len(report["contrasts"]), 6)
                    self.assertTrue((out / "source" / "structures.jsonl").exists())
                    self.assertTrue((out / "predictions.csv").exists())
                    with np.load(out / "baseline-inputs.npz", allow_pickle=False) as inputs:
                        self.assertTrue(all(inputs[name].dtype.kind != "O" for name in inputs.files))


if __name__ == "__main__":
    unittest.main()

