import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ml"))
import storm6 as S6
import storm7 as S


class Storm7Tests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(91)
        self.D=rng.normal(size=(200,5));self.G=rng.normal(size=(200,19))
        self.groups=np.repeat([f"system-{i}" for i in range(100)],2)
        self.y=np.expm1(.4+.1*np.tanh(self.D[:,0]))
        self.train,self.test=np.arange(160),np.arange(160,200)

    def evaluate(self,design,y=None,G=None):
        return S.evaluate_fold(self.D,self.G if G is None else G,self.y if y is None else y,
                               self.groups,self.train,self.test,design,0,params=S.SMOKE_PARAMS)

    def test_u0_exactly_reproduces_storm6_r2_point_and_intervals(self):
        a=self.evaluate("U0")
        b=S6.evaluate_fold(self.D,self.G,{"tc":self.y},self.groups,self.train,self.test,"R2",0,params=S.SMOKE_PARAMS)
        np.testing.assert_array_equal(a["point"],b["point"]["tc"])
        for x,z in [("center","interval_center"),("lo","lo"),("hi","hi")]:
            np.testing.assert_array_equal(a[x],b[z])
        self.assertEqual(a["q"],b["q"])

    def test_test_labels_cannot_change_forecasts_representation_or_intervals(self):
        altered=self.y.copy();altered[self.test]=10000
        a,b=self.evaluate("U1"),self.evaluate("U1",y=altered)
        for k in ("point","center","lo","hi"):np.testing.assert_array_equal(a[k],b[k])
        self.assertEqual(a["point_fit"],b["point_fit"])
        self.assertEqual(a["split_fit"],b["split_fit"])

    def test_calibration_inputs_are_excluded_from_interval_representation(self):
        a=self.evaluate("U1")
        changed=self.G.copy();changed[a["calibration"]]=1e9
        b=self.evaluate("U1",G=changed)
        self.assertEqual(a["split_fit"],b["split_fit"])
        np.testing.assert_array_equal(a["center"],b["center"])
        self.assertEqual(a["point_fit"]["prototype"]["fit_rows"],len(self.train))
        self.assertEqual(a["split_fit"]["prototype"]["fit_rows"],len(a["proper"]))
        self.assertNotEqual(a["point_fit"]["prototype"]["training_sha256"],b["point_fit"]["prototype"]["training_sha256"])

    def test_calibration_labels_change_only_ranges_not_interval_center(self):
        a=self.evaluate("U1")
        y=self.y.copy();y[a["calibration"]]=100
        b=self.evaluate("U1",y=y)
        np.testing.assert_array_equal(a["center"],b["center"])
        self.assertEqual(a["split_fit"],b["split_fit"])
        self.assertNotEqual(a["q"],b["q"])

    def test_protocol_exists_before_real_data_or_targets_are_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            def blocked():
                p=json.loads((out/"protocol.json").read_text())
                self.assertEqual(set(p["designs"]),{"U0","U1"})
                self.assertFalse(p["adopted"])
                self.assertIn("ml/unsupervised.py",p["source_sha256_lf"])
                self.assertEqual(p["experimental_context"]["sha256_crlf_to_lf_only"],hashlib.sha256(Path(S.P.EXPERIMENTS).read_bytes().replace(b"\r\n", b"\n")).hexdigest())
                raise RuntimeError("sentinel_before_real_data")
            with patch.object(S.S,"prepare_real",side_effect=blocked):
                with self.assertRaisesRegex(RuntimeError,"sentinel_before_real_data"):S.run(output_dir=out)

    def test_preparation_failures_are_explicit_and_never_filled_with_zero_metrics(self):
        synthetic=S6.synthetic_data()
        for failing in ("prepare_real","load_references","ood_distance"):
            with self.subTest(stage=failing),tempfile.TemporaryDirectory() as folder:
                with patch.object(S.S,"prepare_real",return_value=synthetic) as prepare, \
                     patch.object(S.S,"load_references",return_value=({},{})) as references, \
                     patch.object(S.S,"ood_distance",wraps=S6.ood_distance) as ood, \
                     patch.object(S,"forecast") as forecast:
                    {"prepare_real":prepare,"load_references":references,"ood_distance":ood}[failing].side_effect=RuntimeError("preparation sentinel")
                    with self.assertRaisesRegex(RuntimeError,"preparation sentinel"):S.run(output_dir=folder)
                    forecast.assert_not_called()
                report=json.loads((Path(folder)/"report.json").read_text())
                self.assertEqual(report["status"],"failed_preparation")
                self.assertIn("preparation sentinel",report["reason"])
                self.assertIsNone(report["cohort"])
                self.assertFalse(report["adopted"])
                self.assertEqual(set(report["designs"]),{"U0","U1"})
                for entry in report["designs"].values():
                    self.assertEqual(entry["status"],"not_run_preparation_failed")
                    self.assertNotIn("point",entry)
                    self.assertNotIn("intervals",entry)
                self.assertFalse((Path(folder)/"predictions.csv").exists())

    def test_protocol_mutation_and_run_overwrite_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder);S.freeze_protocol(out,smoke=True)
            with self.assertRaisesRegex(ValueError,"different frozen"):S.freeze_protocol(out,smoke=False)
            (out/"run.json").write_text('{}')
            with self.assertRaisesRegex(ValueError,"non-overwriting"):S.run(smoke=True,output_dir=out)

    def test_full_smoke_has_exact_ids_both_designs_and_recomputable_calibration(self):
        with tempfile.TemporaryDirectory() as folder:
            report=S.run(smoke=True,output_dir=folder)
            self.assertEqual(report["status"],"completed");self.assertFalse(report["adopted"])
            p=pd.read_csv(Path(folder)/"predictions.csv")
            self.assertEqual(len(p),400)
            self.assertEqual(p.groupby("design")["id"].nunique().to_dict(),{"U0":200,"U1":200})
            c=pd.read_csv(Path(folder)/"calibration-predictions.csv")
            for design,entry in report["designs"].items():
                for fold in entry["folds"]:
                    rows=c[(c.design==design)&(c.fold==fold["fold"])]
                    q=S6.group_quantile(np.abs(np.log1p(rows.target_dft_k)-np.log1p(rows.proper_pred_k)),rows.chemsys.to_numpy())
                    self.assertAlmostEqual(q,fold["calibration_q"])
            with np.load(Path(folder)/"feature-inputs.npz",allow_pickle=False) as data:
                self.assertEqual(data['geometry'].shape,(200,19))
            self.assertEqual(set(report["paired_U1_minus_U0"]),{"overall","tail","ood"})


if __name__=="__main__":unittest.main()
