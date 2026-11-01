import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import storm6 as S


class Storm6Tests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(91)
        self.groups = np.repeat([f"system-{i}" for i in range(100)], 2)
        self.D = rng.normal(size=(200, 5))
        self.G = rng.normal(size=(200, 19))
        lam = .6 + .1 * np.tanh(self.D[:, 0])
        w = 200 + 20 * self.D[:, 1]
        self.targets = {"lambda": lam, "wlog": w, "tc": S.P.allen_dynes(lam, w)}
        self.train, self.test = np.arange(160), np.arange(160, 200)

    def test_outer_answers_cannot_change_forecasts_or_interval_calibration(self):
        changed = {key: value.copy() for key, value in self.targets.items()}
        for value in changed.values():
            value[self.test] = 10000
        for design in S.DESIGNS:
            with self.subTest(design=design):
                a = S.evaluate_fold(self.D, self.G, self.targets, self.groups, self.train, self.test,
                                    design, 0, params=S.SMOKE_PARAMS)
                b = S.evaluate_fold(self.D, self.G, changed, self.groups, self.train, self.test,
                                    design, 0, params=S.SMOKE_PARAMS)
                for key in a["point"]:
                    np.testing.assert_array_equal(a["point"][key], b["point"][key])
                for key in ("interval_center", "lo", "hi"):
                    np.testing.assert_array_equal(a[key], b[key])

    def test_system_calibration_partition_excludes_outer_and_proper_train(self):
        proper, cal = S.calibration_indices(self.train, self.groups, 0)
        self.assertFalse(set(self.groups[proper]) & set(self.groups[cal]))
        self.assertFalse(set(self.groups[cal]) & set(self.groups[self.test]))
        self.assertEqual(set(proper) | set(cal), set(self.train))
        self.assertEqual(len(set(self.groups[cal])), 16)

    def test_group_quantile_uses_worst_row_per_system(self):
        groups = np.array(["large"] * 100 + [f"small-{i}" for i in range(9)])
        scores = np.array([0.] * 99 + [9.] + [0.] * 9)
        self.assertEqual(S.group_quantile(scores, groups), 9.)
        self.assertTrue(np.isinf(S.group_quantile(np.zeros(8), np.arange(8))))

    def test_unbounded_interval_is_explicit_not_a_finite_success(self):
        lo, hi, q = S.split_ranges(np.zeros(8), np.zeros(8), np.arange(8), np.ones(3))
        self.assertIsNone(q)
        self.assertTrue(np.isinf(hi).all())
        m = S.interval_metrics(np.ones(3), lo, hi, np.array(["a", "b", "b"]), np.ones(3, bool), np.zeros(3, bool))
        self.assertEqual(m["unbounded_interval_rows"], 3)
        self.assertIsNone(m["interval_score_k"])

    def test_pca_imputation_and_missing_column_mask_are_train_only(self):
        D = self.D.copy()
        D[:160, 0] = np.nan
        G = self.G.copy()
        G[:160, 0] = np.nan
        m = S.FeatureMap("R4").fit(D[:160], G[:160])
        before = m.transform(D[:160], G[:160]).copy()
        G[160:] = 1e9
        D[160:] = -1e9
        m.transform(D[160:], G[160:])
        np.testing.assert_array_equal(before, m.transform(D[:160], G[:160]))
        self.assertEqual(m.scale.median[0], 0.)
        self.assertFalse(m.keep[0])
        self.assertEqual(m.pca.n_components_, 8)

    def test_native_missing_geometry_does_not_crash_cpu_heads(self):
        G = self.G.copy()
        G[:, :2] = np.nan
        for design in ("R2", "R3"):
            p = S.forecast(design, self.D[:160], G[:160], {k: v[:160] for k, v in self.targets.items()},
                           self.D[160:], G[160:], seed=7, params=S.SMOKE_PARAMS)
            self.assertTrue(np.isfinite(p["tc"]).all())

    def test_component_route_obeys_existing_ad_units_and_zero_semantics(self):
        class FixedRegressor:
            fitted = 0
            def __init__(self, **kwargs):
                pass
            def fit(self, X, y):
                self.value = (.05, 240.)[FixedRegressor.fitted % 2]
                FixedRegressor.fitted += 1
                return self
            def predict(self, X):
                return np.full(len(X), self.value)
        with patch("sklearn.ensemble.HistGradientBoostingRegressor", FixedRegressor):
            p = S.forecast("R1", self.D[:160], self.G[:160], {k: v[:160] for k, v in self.targets.items()},
                           self.D[160:], self.G[160:], seed=7, params=S.SMOKE_PARAMS)
        np.testing.assert_array_equal(p["tc"], np.zeros(40))
        np.testing.assert_array_equal(p["wlog"], np.full(40, 240.))
        self.assertGreater(float(S.P.allen_dynes(.8, 240.)), 0.)

    def test_ood_threshold_does_not_use_test_distribution(self):
        _, _, threshold = S.ood_distance(self.D[:160], self.D[160:], self.groups[:160])
        _, outside, changed = S.ood_distance(self.D[:160], self.D[160:] + 1e6, self.groups[:160])
        self.assertEqual(threshold, changed)
        self.assertTrue(outside.all())

    def test_ood_reference_excludes_same_system_near_duplicates(self):
        D = np.array([[0.], [.00001], [10.], [10.00001]])
        _, _, threshold = S.ood_distance(D, np.array([[5.]]), np.array(["a", "a", "b", "b"]))
        self.assertGreater(threshold, 1.9)

    def test_progress_io_failure_warns_but_scientific_io_failure_propagates(self):
        with patch.object(S, "_json", side_effect=PermissionError("locked")), self.assertWarnsRegex(RuntimeWarning, "progress write failed"):
            S._status("status.json", {"status": "running"})
        with patch.object(Path, "write_text", side_effect=PermissionError("locked")), self.assertRaises(PermissionError):
            S._json("report.json", {"status": "completed"})

    def test_group_coverage_is_distinct_from_material_coverage(self):
        y = np.array([0., 2., 0., 0.])
        m = S.interval_metrics(y, np.zeros(4), np.ones(4), np.array(["a", "a", "b", "b"]),
                               np.ones(4, bool), np.zeros(4, bool))
        self.assertEqual(m["row_coverage"], .75)
        self.assertEqual(m["group_simultaneous_coverage"], .5)

    def test_paired_cluster_bootstrap_is_zero_for_identical_forecasts(self):
        y = self.targets["tc"]
        r = S.paired_bootstrap(y, y + 1, y + 1, self.groups)
        self.assertEqual(r["delta_mae_k_new_minus_reference"], 0.)
        self.assertEqual(r["percentile_95_interval_k"], [0., 0.])
        self.assertEqual(r["repetitions"], 1000)

    def test_historical_artifacts_are_exact_and_detect_fold_misalignment(self):
        r4 = pd.read_csv(S.P.RESULTS / "storm_round4_predictions.csv", dtype={"id": str})
        r5 = pd.read_csv(S.P.RESULTS / "storm_round5_ranges.csv")
        frame = r4[["id", "chemsys", "tc"]].copy()
        references, _ = S.load_references(frame, r5["fold"].to_numpy())
        self.assertEqual(len(references["gnn"]), 7582)
        with self.assertRaisesRegex(ValueError, "folds differ"):
            S.load_references(frame, np.roll(r5["fold"].to_numpy(), 1))
        with tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary:
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                S.load_references(frame, r5["fold"].to_numpy(), temporary)

    def test_real_git_reference_blobs_load_with_lf_or_crlf_only(self):
        r4 = pd.read_csv(S.P.RESULTS / "storm_round4_predictions.csv", dtype={"id": str})
        r5 = pd.read_csv(S.P.RESULTS / "storm_round5_ranges.csv")
        frame = r4[["id", "chemsys", "tc"]].copy()
        for ending in ("LF", "CRLF"):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary:
                root = Path(temporary)
                for name, expected in S.REFERENCE_SHA256.items():
                    blob = subprocess.run(["git", "show", f"HEAD:results/{name}"], cwd=S.P.ROOT,
                                          capture_output=True, check=True).stdout
                    self.assertNotIn(b"\r", blob)  # Actual committed LF blobs, not a mocked digest.
                    self.assertEqual(hashlib.sha256(blob).hexdigest(), expected)
                    (root / name).write_bytes(blob if ending == "LF" else blob.replace(b"\n", b"\r\n"))
                    self.assertEqual(S._reference_sha(root / name), expected)
                references, _ = S.load_references(frame, r5["fold"].to_numpy(), root)
                self.assertEqual(len(references["gnn"]), 7582)

    def test_reference_normalization_rejects_numeric_and_other_byte_changes(self):
        r4 = pd.read_csv(S.P.RESULTS / "storm_round4_predictions.csv", dtype={"id": str})
        r5 = pd.read_csv(S.P.RESULTS / "storm_round5_ranges.csv")
        frame = r4[["id", "chemsys", "tc"]].copy()
        with tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary:
            root = Path(temporary)
            originals = {}
            for name in S.REFERENCE_SHA256:
                originals[name] = (S.P.RESULTS / name).read_bytes().replace(b"\r\n", b"\n")
                (root / name).write_bytes(originals[name])
            for name, original in originals.items():
                with self.subTest(file=name):
                    (root / name).write_bytes(original + b" ")  # Even semantically harmless whitespace changes fail.
                    with self.assertRaisesRegex(ValueError, "missing or changed"):
                        S.load_references(frame, r5["fold"].to_numpy(), root)
                    (root / name).write_bytes(original)
            name = "storm_round4_predictions.csv"
            lines = originals[name].split(b"\n")
            cells = lines[1].split(b",")
            cells[-1] = str(float(cells[-1]) + .125).encode("ascii")
            lines[1] = b",".join(cells)
            (root / name).write_bytes(b"\n".join(lines))
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                S.load_references(frame, r5["fold"].to_numpy(), root)

    def test_protocol_exists_before_target_loading_even_when_input_fails(self):
        with tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary:
            def check_then_fail():
                path = Path(temporary) / "protocol.json"
                self.assertTrue(path.is_file())
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(digest, (Path(temporary) / "protocol.sha256").read_text().strip())
                raise ValueError("deliberate missing input")
            with patch.object(S, "prepare_real", check_then_fail), self.assertRaisesRegex(ValueError, "deliberate"):
                S.run(output_dir=temporary)

    def test_real_protocol_refuses_different_existing_freeze(self):
        with tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary:
            path = Path(temporary) / "protocol.json"
            path.write_text('{"different": true}')
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                S.freeze_protocol(temporary)
            self.assertEqual(path.read_text(), '{"different": true}')

    def test_offline_smoke_reports_all_five_without_release_or_download(self):
        with tempfile.TemporaryDirectory(dir=S.P.ROOT.parent) as temporary, \
                patch.object(S.P, "load_dataset", side_effect=AssertionError("must not download")):
            report = S.run(smoke=True, output_dir=temporary)
            self.assertFalse(report["adopted"])
            self.assertEqual(report["status"], "completed")
            self.assertEqual(set(report["designs"]), set(S.DESIGNS))
            self.assertTrue(all(d["status"] == "completed" for d in report["designs"].values()))
            self.assertEqual(report["oracle_formula_check"]["max_absolute_error_k"], 0.)
            self.assertFalse(report["oracle_formula_check"]["forecast"])
            frame = pd.read_csv(Path(temporary) / "predictions.csv")
            self.assertEqual(len(frame), 5 * 200)
            self.assertFalse(frame.interval_unbounded.any())
            self.assertTrue(np.isfinite(frame.tc_pred_full_outer_k).all())
            strict = json.loads((Path(temporary) / "report.json").read_text(), parse_constant=lambda token: self.fail(token))
            self.assertEqual(strict["feedback_training_records"], 0)


if __name__ == "__main__":
    unittest.main()
