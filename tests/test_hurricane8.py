import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane7 as H7
import hurricane8 as H8


class Hurricane8Tests(unittest.TestCase):
    def setUp(self):
        self.data = H7.prepare_smoke()
        self.train, self.test, self.held = H7.outer_split(self.data["parents"], "cuprate")

    def test_u0_is_exact_old_main_effect_baseline(self):
        actual = H8.fit_split(self.data, "U0", .1, self.train, self.held, seed=7)
        expected = H7.fit_split(self.data, "R0", .1, self.train, self.held, seed=7)
        self.assertEqual(actual.identity(), expected.identity())
        np.testing.assert_array_equal(actual.predict(self.data["geometry"][self.test], self.data["extras"][self.test]),
                                      expected.predict(self.data["geometry"][self.test], self.data["extras"][self.test]))

    def test_held_family_data_and_labels_cannot_change_representation_or_selection(self):
        other = copy.deepcopy(self.data)
        other["geometry"][self.test] = 1e9
        other["extras"][self.test] = np.nan
        other["parents"].loc[self.test, "tc"] = 1 - (other["parents"].loc[self.test, "tc"] > 0).astype(int)
        alpha, inner = H8.select_alpha(self.data, "U1", self.train, self.held)
        other_alpha, other_inner = H8.select_alpha(other, "U1", self.train, self.held)
        self.assertEqual(alpha, other_alpha)
        self.assertEqual(inner, other_inner)
        fit = H8.fit_split(self.data, "U1", alpha, self.train, self.held, seed=7)
        changed = H8.fit_split(other, "U1", alpha, self.train, self.held, seed=7)
        self.assertEqual(fit.identity(), changed.identity())
        for row in inner:
            for fold in row["folds"]:
                self.assertFalse(set(fold["training_systems"]) & (set(fold["validation_systems"]) | self.held))
                self.assertEqual(fold["prototype_identity"]["fit_rows"], len(fold["training_ids"]))

    def test_training_labels_cannot_change_prototypes(self):
        other = copy.deepcopy(self.data)
        other["parents"]["tc"] = 1 - (other["parents"].tc > 0).astype(int)
        a = H8.fit_split(self.data, "U1", .1, self.train, self.held, seed=7)
        b = H8.fit_split(other, "U1", .1, self.train, self.held, seed=7)
        self.assertEqual(a.features.prototype.identity(), b.features.prototype.identity())
        self.assertFalse(np.array_equal(a.coefficient, b.coefficient))

    def test_held_system_rejected_before_unsupervised_fit(self):
        invalid = np.concatenate([self.train, self.test[:1]])
        with patch.object(H8.PrototypeFeatures, "fit", side_effect=AssertionError("fit must not be called")):
            with self.assertRaisesRegex(ValueError, "Held chemical system"):
                H8.fit_split(self.data, "U1", .1, invalid, self.held, seed=7)

    def test_snapshot_byte_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "parents.csv"
            p.write_text("made-up,unverified\n1,2\n")
            with self.assertRaisesRegex(ValueError, "frozen H7"):
                H8.load_snapshot(p)

    def test_failed_fold_is_not_zero_filled_or_included_in_macro(self):
        original = H8.fit_split
        def fail_first(data, design, alpha, train, held_systems, *, seed):
            if design == "U1" and "system-0-0" in held_systems:
                raise ValueError("intentional test-only failure")
            return original(data, design, alpha, train, held_systems, seed=seed)
        with tempfile.TemporaryDirectory() as d, patch.object(H8, "fit_split", side_effect=fail_first):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                H8.run(smoke=True, output_dir=d)
            r = json.loads((Path(d) / "report.json").read_text())
            self.assertFalse(r["adopted"])
            self.assertEqual(r["designs"]["U1"]["status"], "incomplete")
            self.assertIsNone(r["macro"]["U1"]["observed_pu_auc"])
            self.assertEqual(r["paired_intervals"]["U1-U0"]["status"], "unavailable_incomplete_design")

    def test_protocol_frozen_before_data_loading_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            def refuse_load():
                self.assertTrue((Path(d) / "protocol.sha256").is_file())
                raise ValueError("test-only preparation error")
            with patch.object(H7, "prepare_smoke", side_effect=refuse_load):
                with self.assertRaisesRegex(ValueError, "preparation error"):
                    H8.run(smoke=True, output_dir=d)
            p = Path(d) / "protocol.json"
            p.write_bytes(b"different frozen protocol")
            with self.assertRaisesRegex(ValueError, "different frozen"):
                H8.freeze_protocol(d)


if __name__ == "__main__":
    unittest.main()
