import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane9 as F
import hurricane9_data as D
import hurricane9_release as R
from test_hurricane9 import fake_table, half, observations


class Hurricane9ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(F, "element_table", fake_table), patch.object(F, "REPLICATES", 40)]
        for p in cls.patches:
            p.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.before = R.P.PROGRESS.read_text(encoding="utf-8")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            cls.out = R.run(smoke=True, output_dir=Path(cls.tmp.name))
        cls.lines = buffer.getvalue().strip().split("\n")
        cls.progress = json.loads((Path(cls.tmp.name) / "progress.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.tmp.cleanup()

    def test_the_release_protocol_binds_the_tested_design_and_the_run_needs_its_declaration(self):
        self.assertEqual(R.PROTOCOL["fit_protocol_sha256"], F.protocol_sha256())
        self.assertEqual((R.PROTOCOL["model"]["design"], R.PROTOCOL["model"]["regressor"], R.PROTOCOL["model"]["classifier"]), ("data", F.REGRESSOR, F.CLASSIFIER))
        self.assertEqual((R.WEIGHT, R.RADIUS, R.ABSTAIN, R.FALSE_ALARM_LIMIT), (0.3, 1.0, 1.0, 0.05))
        with tempfile.TemporaryDirectory() as tmp, patch.object(R, "DECLARATION", Path(tmp) / "declaration.md"), \
                patch.object(D, "fetch", side_effect=AssertionError("data was read")):
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                R.run()
            (Path(tmp) / "declaration.md").write_text("another hash " + "0" * 64, encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                R.run()

    def test_the_released_design_is_the_tested_one(self):
        obs = observations()
        table = fake_table(sorted({e for o in obs for e in o["composition"]}))
        w = F.window_rows(obs, 2005, half(obs))
        tested = F.fit_predict("data", w["train"], w["test"], table, {})
        train = F.design_rows("data", w["train"])
        X, (Xt,), cols = R.inputs(train, [w["test"]], table, {})
        tc, event, groups = R.targets(train)
        d = R.Design9().fit_regressor(X, tc).fit_classifier(X, event)
        self.assertTrue(tested["regressor"] and tested["classifier"] and len(cols) == tested["features"])
        np.testing.assert_array_equal(d.tc(Xt), tested["tc"])
        np.testing.assert_array_equal(d.chance(Xt), tested["score"])
        self.assertEqual(len(set(groups.tolist())), int(groups.max()) + 1)

    def test_the_guard_never_scores_a_background_compound_with_its_own_fold(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(120, 4))
        event = np.array([1] * 60 + [0] * 50 + [-1] * 10)
        groups = np.arange(120) // 3
        Xb = np.vstack([rng.normal(size=(40, 4)), rng.normal(loc=30.0, size=(10, 4))])      # the last ten lie far outside
        fold = np.arange(50) % 5
        sent = np.arange(50) % 2 == 0
        seen = []
        real = R.Design9.fit_classifier

        def spy(self, X_, event_, Xb_=None, weight=R.WEIGHT):
            seen.append(None if Xb_ is None else {tuple(np.round(r, 9)) for r in Xb_})
            return real(self, X_, event_, Xb_, weight)

        with patch.object(R.Design9, "fit_classifier", spy):
            g = R.guard(X, event, groups, Xb, fold, sent)
        self.assertEqual(len(seen), 6)                      # five cross-fitted classifiers and the one without a guard
        for k in range(5):
            held = {tuple(np.round(r, 9)) for r in Xb[fold == k]}
            self.assertFalse(seen[k] & held)
            self.assertTrue(all(row in {tuple(np.round(r, 9)) for r in Xb[g["near"]]} for row in seen[k]))
        self.assertIsNone(seen[5])
        self.assertTrue(g["unknown"][-10:].all() and not g["near"][-10:].any())
        s = g["summary"]
        alarm = (g["p"] >= 0.5) & ~g["unknown"]
        self.assertEqual((s["n"], s["n_sent"], s["n_used"]), (50, 25, int(g["near"].sum())))
        self.assertAlmostEqual(s["false_alarms"], float(alarm[sent].mean()))
        self.assertEqual(s["passed"], s["false_alarms"] <= R.FALSE_ALARM_LIMIT)
        self.assertEqual(R.share(np.array([True, False]), np.array([False, False])), None)

    def test_the_range_is_the_split_conformal_quantile(self):
        self.assertEqual(R.conformal(np.arange(1, 10) / 10.0, 0.1), 0.9)     # nine residuals: the largest
        self.assertEqual(R.conformal(np.arange(1, 101) / 100.0, 0.1), 0.91)  # a hundred: the 91st
        self.assertTrue(np.isnan(R.conformal([])))

    def test_the_smoke_run_writes_only_into_its_own_folder(self):
        self.assertEqual(R.P.PROGRESS.read_text(encoding="utf-8"), self.before)
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()),
                         ["hurricane_round9.json", "hurricane_round9_background.csv", "hurricane_round9_predictions.csv", "progress.json"])
        saved = json.loads((Path(self.tmp.name) / "hurricane_round9.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["smoke"], saved["version"], saved["protocol"]["sha256"], saved["best"]["rows"]), (True, "9.0", R.protocol_sha256(), "datasheet"))
        text = "".join(line.split("|", 2)[2] for line in self.lines if line.startswith("h9r|"))
        self.assertEqual(json.loads(text)["protocol"]["sha256"], R.protocol_sha256())
        self.assertNotIn("NaN", text)

    def test_an_entry_that_misses_the_rule_stays_experimental_and_one_that_meets_it_takes_over(self):
        hu = self.progress["hurricane"]
        e = [v for v in hu["versions"] if v["round"] == 9][0]
        self.assertEqual((self.out["adopted"], e["status"], hu["current"]), (False, "experimental", "4.0"))
        self.assertTrue({"version", "data", "spec", "scores", "previous", "lofo", "importance", "search", "reliability", "anchors", "temporal"} <= set(e))
        self.assertEqual((e["scores"]["kind"], len(e["scores"]["folds"]), len(e["scores"]["fold_labels"])), ("time-windows", 13, 13))
        self.assertEqual([c["id"] for c in e["temporal"]["claims"]], ["C0", "C1", "C2", "C3", "C4:cuprate:1985", "C4:iron-nickel:2005"])
        self.assertEqual(sorted(e["data"]["families"]), ["cuprate", "heavy-fermion", "iron-based", "other oxide"])
        self.assertEqual([m["status"] for m in self.progress["model_family"] if m["id"] == "hurricane"], ["Hurricane 4.0 in use"])
        won = json.loads(json.dumps(self.out))
        won["adopted"] = True
        won["evidence"]["overall"].update(released_measure_k=16.0, released_measure_previous_k=21.5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            path.write_text(self.before, encoding="utf-8")
            R.update_progress(won, path)
            prog = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((prog["hurricane"]["current"], prog["hurricane"]["data"]["kind"]), ("9.0", "datasheet"))
        self.assertEqual([m["status"] for m in prog["model_family"] if m["id"] == "hurricane"], ["Hurricane 9.0 in use"])
        self.assertIn("Hurricane 9.0 for unconventional ones", [s for s in prog["stages"] if s["id"] == "ai-models"][0]["detail"])
        self.assertEqual([v["version"] for v in prog["hurricane"]["versions"]][-2:], ["5.0", "9.0"])
        self.assertTrue(any(r["model"].startswith("Hurricane 9.0") for r in prog["results"]))

    def test_an_anchor_the_training_rows_hold_is_shown_and_not_scored(self):
        obs = observations()
        table = fake_table(sorted({e for o in obs for e in o["composition"]}))
        train = R.final_rows(obs)
        held = dict(train[0]["comp"])
        anchors = [{"name": "held", "composition": held, "tc_exp": 30.0, "status": "replicated", "use": "score", "family": "cuprate"},
                   {"name": "new", "composition": {"La": 1.0, "Fe": 1.0, "As": 1.0, "O": 1.0}, "tc_exp": 26.0, "status": "replicated", "use": "score", "family": "iron-based"},
                   {"name": "outside", "composition": {"U": 1.0, "Te": 2.0}, "tc_exp": 2.0, "status": "replicated", "use": "score", "family": "heavy-fermion"}]
        rows = R.pseudo_rows(["a", "b", "c"], [a["composition"] for a in anchors])
        X, (Xa,), _ = R.inputs(train, [rows], fake_table(sorted({e for o in obs for e in o["composition"]} | {"U", "Te"})), {})
        tc, event, groups = R.targets(train)
        final = R.Design9().fit_regressor(X, tc).fit_classifier(X, event)
        got = R.anchor_table(final, X, groups, train, Xa, anchors)
        by = {r["name"]: r for r in got["table"]}
        self.assertEqual((by["held"]["use"], by["held"]["in_training"], by["new"]["use"], by["new"]["in_training"]), ("show", True, "score", False))
        self.assertEqual((by["outside"]["pred"], by["outside"]["why"]), (None, "element outside the training data"))
        self.assertEqual((got["n_scored"], got["n_listed"], got["scored_as_check"]), (1, 3, False))
        self.assertEqual(R.formula_of({"Ba": 2.0, "Cu": 6.0, "Y": 2.0, "O": 14.0}), "BaCu3O7Y")


if __name__ == "__main__":
    unittest.main()
