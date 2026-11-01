import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
from crossfit import candidate_predictions


class CandidateCrossFitTests(unittest.TestCase):
    def test_self_negative_never_reaches_a_candidates_model(self):
        # An intentionally memorising classifier makes leakage directly observable.
        systems = np.array(["A-B", "C-D", "E-F", "G-H", "I-J"])
        folds = np.arange(5)
        calls = []

        def fit(tr, keep, fold, seed):
            calls.append((fold, seed))
            return set(systems[keep])

        def predict(seen_negative, query):
            chance = np.array([0.01 if systems[i] in seen_negative else 0.8 for i in query])
            return chance * 10, chance, np.full(len(query), 10.)

        out = candidate_predictions([(np.array([0]), np.array([1]))] * 5, 5, fit, predict,
                                    pool_folds=folds, background_folds=folds,
                                    pool_systems=systems, background_systems=systems)
        np.testing.assert_array_equal(out["p_sc"], np.full((5, 5), 0.8))
        self.assertEqual(len(calls), 25)
        self.assertEqual(set(calls), {(fold, training_fold) for fold in range(5) for training_fold in range(5)})
        self.assertEqual(out["method"], "same-background-fold-training-fold-ensemble")

    def test_inconsistent_system_folds_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "training background"):
            candidate_predictions([(None, None)] * 2, 1, lambda *a: None, lambda *a: None,
                                  pool_folds=[0], background_folds=[1],
                                  pool_systems=["A-B"], background_systems=["A-B"])

    def test_no_background_uses_training_folds_as_members(self):
        out = candidate_predictions([(None, None)] * 2, 2,
                                    lambda tr, keep, fold, seed: fold,
                                    lambda model, query: (np.full(len(query), model),
                                                          np.full(len(query), .5),
                                                          np.full(len(query), 2.)))
        self.assertEqual(out["tc"].shape, (2, 2))
        np.testing.assert_array_equal(out["tc"][:, 0], [0, 1])

    def test_empty_pool_does_not_train(self):
        out = candidate_predictions([(None, None)] * 2, 0,
                                    lambda *a: self.fail("nothing should be fitted"), lambda *a: None,
                                    pool_folds=[], background_folds=[0, 1],
                                    pool_systems=[], background_systems=["A", "B"])
        self.assertEqual(out["tc"].shape, (2, 0))


if __name__ == "__main__":
    unittest.main()
