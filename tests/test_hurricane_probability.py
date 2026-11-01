"""Real-sklearn regression against the pre-extraction probability branch."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane as H
import hurricane2 as H2


def legacy_classifier(c, X, y, seed, Xb=None):
    """Frozen branch from Design.fit before classifier-only extraction."""
    sc = y > 0
    wb = float(c.get("background") or 0)
    if wb > 0 and Xb is not None and len(Xb):
        lab = np.concatenate([sc.astype(int), np.zeros(len(Xb), int)])
        w = np.concatenate([np.ones(len(y)), np.full(len(Xb), wb)])
        return H2._fit_clf(np.vstack([X, Xb]), lab, seed, w) if sc.any() else None
    return H2._fit_clf(X, sc.astype(int), seed) if 0 < sc.sum() < len(y) else None


class ProbabilityOnlyTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(29)
        self.X = rng.normal(size=(64, 5))
        self.X[::7, 2] = np.nan
        self.Xb = rng.normal(size=(21, 5))
        self.query = rng.normal(size=(17, 5))
        self.y = np.where(np.arange(64) % 3 == 0, 0.0, 1 + np.arange(64) / 3)
        self.c = dict(two_part="mean", background=0.3,
                      params=dict(H.PARAMS, max_iter=8, min_samples_leaf=2))
        self.seed = 41

    def assert_probability_identical(self, candidate, y, background):
        old = legacy_classifier(candidate, self.X, y, self.seed, Xb=background)
        with patch.object(H, "_fit", side_effect=AssertionError("probability-only fitting must not train Tc")):
            new = H2.fit_probability_classifier(candidate, self.X, y, self.seed, Xb=background)
        if old is None:
            self.assertIsNone(new)
            self.assertTrue(np.isnan(H2.probability_predictions(new, self.query)).all())
        else:
            np.testing.assert_array_equal(H2.probability_predictions(new, self.query), old.predict_proba(self.query)[:, 1])
        return old, new

    def test_mixed_classes_with_and_without_weak_background_are_bitwise_identical(self):
        for background, weight in ((None, 0.3), (self.Xb, 0.3), (self.Xb[:0], 0.3), (self.Xb, 0.0)):
            with self.subTest(background_rows=0 if background is None else len(background), weight=weight):
                candidate = dict(self.c, background=weight)
                old, _ = self.assert_probability_identical(candidate, self.y, background)
                design = H2.Design(candidate, self.seed).fit(self.X, self.y, np.array(["cuprate"] * len(self.y)), Xb=background)
                np.testing.assert_array_equal(design.clf.predict_proba(self.query)[:, 1], old.predict_proba(self.query)[:, 1])

    def test_single_class_degenerate_paths_match_the_previous_branch(self):
        for y, background in ((np.ones(64), None), (np.zeros(64), None),
                              (np.ones(64), self.Xb), (np.zeros(64), self.Xb)):
            with self.subTest(positive_rows=int((y > 0).sum()), has_background=background is not None):
                self.assert_probability_identical(self.c, y, background)
        # This complete Design is valid with all-positive labels and no classifier.
        design = H2.Design(self.c, self.seed).fit(self.X, np.ones(64), np.array(["cuprate"] * 64))
        self.assertIsNone(design.clf)

    def test_per_family_recursion_stays_with_design(self):
        with self.assertRaisesRegex(ValueError, "per-family"):
            H2.fit_probability_classifier(dict(self.c, per_family=True), self.X, self.y, self.seed, Xb=self.Xb)
        families = np.array(["cuprate"] * 32 + ["iron-based"] * 32)
        grouped = H2.Design(dict(self.c, per_family=True), self.seed).fit(self.X, self.y, families)
        for family in np.unique(families):
            keep = families == family
            reference = H2.Design(dict(self.c, per_family=False), self.seed).fit(self.X[keep], self.y[keep], families[keep])
            np.testing.assert_array_equal(grouped.parts[family].clf.predict_proba(self.query), reference.clf.predict_proba(self.query))


if __name__ == "__main__":
    unittest.main()
