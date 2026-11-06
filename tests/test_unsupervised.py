import inspect
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
from unsupervised import TrainOnlyPrototypes


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        self.X = np.random.default_rng(91).normal(size=(100, 5))

    def test_fit_accepts_no_targets(self):
        self.assertEqual(list(inspect.signature(TrainOnlyPrototypes.fit).parameters), ["self", "X"])
        with self.assertRaises(TypeError):
            TrainOnlyPrototypes().fit(self.X, np.arange(len(self.X)))

    def test_deterministic_and_heldout_data_cannot_change_fit(self):
        a = TrainOnlyPrototypes().fit(self.X)
        before = a.identity()
        a.transform(np.full((10,5), 1e12))
        a.transform(np.full((10,5), np.nan))
        self.assertEqual(before, a.identity())
        b = TrainOnlyPrototypes().fit(self.X)
        self.assertEqual(before, b.identity())
        np.testing.assert_array_equal(a.transform(self.X), b.transform(self.X))

    def test_affine_units_do_not_change_representation(self):
        scale = np.array([2.,3.,4.,5.,6.])
        shifted = self.X*scale + np.arange(5)*100
        a,b = TrainOnlyPrototypes().fit(self.X), TrainOnlyPrototypes().fit(shifted)
        np.testing.assert_allclose(a.transform(self.X),b.transform(shifted),atol=1e-12)

    def test_missing_and_constants_are_training_decisions(self):
        X = np.column_stack([self.X,np.full(100,np.nan),np.ones(100)])
        X[::4,0] = np.nan
        original = X.copy()
        m = TrainOnlyPrototypes().fit(X)
        state = m.identity()
        self.assertEqual(state["all_missing_columns"],[5])
        self.assertEqual(state["constant_columns"],[6])
        self.assertAlmostEqual(state["medians"][0],np.nanmedian(X[:,0]))
        self.assertTrue(np.isfinite(m.transform(np.ones((3,7)))).all())
        np.testing.assert_array_equal(X,original)

    def test_degenerate_inputs_keep_width_and_explicit_reason(self):
        for X in [np.full((5,3),np.nan),np.ones((5,3)),np.empty((5,0))]:
            m=TrainOnlyPrototypes().fit(X)
            self.assertEqual(m.identity()["active_prototypes"],0)
            self.assertIn("no_informative_columns",m.identity()["degenerate"])
            np.testing.assert_array_equal(m.transform(X),np.zeros((5,16)))
            json.dumps(m.identity(),allow_nan=False)
        X=np.array([[0.],[0.],[1.],[1.]])
        m=TrainOnlyPrototypes().fit(X)
        self.assertEqual(m.identity()["active_prototypes"],2)
        self.assertIn("zero_training_nearest_distances",m.identity()["degenerate"])
        np.testing.assert_array_equal(m.transform(X)[:,2:],np.zeros((4,14)))

    def test_saved_state_independently_reconstructs_rbf_and_bandwidth(self):
        m=TrainOnlyPrototypes().fit(self.X)
        s=m.identity()
        z=np.clip((self.X[:,s["selected_columns"]]-s["means"])/s["stds"],-5,5)
        d=np.linalg.norm(z[:,None,:]-np.asarray(s["centers"])[None,:,:],axis=2)
        positive=d.min(axis=1);positive=positive[positive>1e-12]
        self.assertEqual(s["bandwidth"],float(np.median(positive)))
        np.testing.assert_allclose(m.transform(self.X),np.exp(-d*d/(2*s["bandwidth"]**2)),atol=1e-15)
        self.assertTrue(((m.transform(self.X)>=0)&(m.transform(self.X)<=1)).all())
        self.assertFalse(np.allclose(m.transform(self.X).sum(axis=1),1))

    def test_rbf_is_not_the_squared_distance_quadratic_degeneracy(self):
        X=np.linspace(-3,3,100)[:,None]
        m=TrainOnlyPrototypes(n_clusters=2).fit(X)
        basis=np.column_stack([np.ones(100),X[:,0],X[:,0]**2])
        phi=m.transform(X)[:,0]
        reconstructed=basis@np.linalg.lstsq(basis,phi,rcond=None)[0]
        self.assertGreater(np.max(np.abs(phi-reconstructed)),.05)

    def test_bad_shapes_and_empty_fit_fail_explicitly(self):
        with self.assertRaises(ValueError): TrainOnlyPrototypes().fit(np.empty((0,5)))
        with self.assertRaises(ValueError): TrainOnlyPrototypes().fit(np.ones(5))
        with self.assertRaises(ValueError): TrainOnlyPrototypes().transform(self.X)
        with self.assertRaises(ValueError): TrainOnlyPrototypes().fit(self.X).transform(np.ones((2,6)))


if __name__=="__main__": unittest.main()
