"""Exercise the actual screening entry point with a memorising background model."""
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import screen as SC
import hurricane5 as H5


class ScreeningCrossFitIntegrationTests(unittest.TestCase):
    def test_screen_queries_only_models_unexposed_to_its_background_labels(self):
        count = 30
        hur = pd.DataFrame({"tc": [0., 10.] * (count // 2), "family": ["other oxide"] * count,
                            "comp": [{f"T{i}": 1} for i in range(count)],
                            "group": [f"parent{i}" for i in range(count)],
                            "formula_sc": [f"T{i}" for i in range(count)], "feature": np.arange(count)})
        pool = pd.DataFrame({"comp": [{f"Q{i}": 1} for i in range(20)],
                             "chemsys": [f"Q{i}" for i in range(20)],
                             "feature": np.arange(1000, 1020)})
        design = {"id": "test", "name": "test", "X": "A", "background": .3,
                  "two_part": "mean", "radius": 1., "abstain": 1.}
        trained = []

        class MemorisingModel:
            def __init__(self, config, seed):
                self.config, self.seed = config, seed

            def fit(self, X, y, fam, Xb=None):
                self.seen = set(Xb[:, 0])
                self.training = tuple(X[:, 0])
                trained.append(self)
                return self

            def predict(self, X, fam):
                if self.seen.intersection(X[:, 0]):
                    raise AssertionError("a candidate was queried after learning its own negative label")
                return np.full(len(X), 8.)

        def parts(model, X, fam):
            model.predict(X, fam)
            return np.full(len(X), .8), np.full(len(X), 10.)

        def novelty(X, groups, query):
            return {"ratio": np.full(len(query), .5), "limit": 1., "nearest": np.zeros(len(query), int)}

        with ExitStack() as stack:
            for target, value in (
                ("hurricane_design", lambda: (design, "test")),
                ("hurricane_reliability", lambda version: None),
                ("hur_parts", parts), ("novelty", novelty)):
                stack.enter_context(patch.object(SC, target, value))
            stack.enter_context(patch.object(SC.H, "load_3dsc", lambda: None))
            stack.enter_context(patch.object(SC.H, "build_frame", lambda *args: hur))
            stack.enter_context(patch.object(SC.H, "feature_blocks", lambda *args: {"A": hur[["feature"]]}))
            stack.enter_context(patch.object(SC.H, "dsc_structure", lambda row: {}))
            stack.enter_context(patch.object(SC.H, "element_fractions", lambda *args: pd.DataFrame(index=hur.index)))
            stack.enter_context(patch.object(SC.P, "element_table", lambda *args: pd.DataFrame()))
            stack.enter_context(patch.object(SC.H2, "Design", MemorisingModel))
            stack.enter_context(patch.object(H5, "pool_blocks", lambda frame, *args: {"A": frame[["feature"]]}))
            import hurricane4 as H4
            stack.enter_context(patch.object(H4, "ratio", lambda X, groups, query: np.full(len(query), .5)))
            result = SC.hurricane_scores(pool, pool)
        np.testing.assert_allclose(result["p_sc"], .8)
        ensemble = result["info"]["jackknife"]
        self.assertEqual(ensemble["method"], "same-background-fold-training-fold-ensemble")
        self.assertTrue(ensemble["no_query_system_in_background"])
        self.assertEqual(ensemble["n"], 5)
        self.assertEqual(len({m.training for m in trained[5:]}), 5)


if __name__ == "__main__":
    unittest.main()
