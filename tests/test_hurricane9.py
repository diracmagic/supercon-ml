import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane9 as F
import hurricane9_data as D


def fake_table(symbols):
    """Invented element properties: the tests need a table, not pymatgen."""
    order = sorted(D.ELEMENTS)
    rows = {}
    for s in symbols:
        z = order.index(s) + 1
        rows[s] = {"Z": float(z), "atomic_mass": 2.2 * z, "X": 0.7 + (z * 37 % 30) / 10, "row": float(1 + z // 18), "group": float(1 + z % 18),
                   "atomic_radius": 0.5 + (z * 13 % 20) / 10, "mendeleev_no": float(z * 7 % 103), "valence": float(z % 8)}
    return pd.DataFrame.from_dict(rows, orient="index")


def table_rows(text):
    lines = text.rstrip("\n").split("\n")
    symbols = lines[2].split("\t")
    return lines[:3], [dict(zip(symbols, line.split("\t"))) for line in lines[3:]]


def table_text(head, rows):
    symbols = head[2].split("\t")
    return "\n".join(head + ["\t".join(r[s] for s in symbols) for r in rows]) + "\n"


def observations(rows=None, change=None):
    head, base = table_rows(F.synthetic_table())
    rows = base if rows is None else rows
    if change:
        rows = [change(dict(r)) for r in rows]
    return D.load_observations(table_text(head, rows))[0]


def half(obs):
    return {u["canonical"] for i, u in enumerate(D.canonical_units(obs, lift=True)) if i % 2 == 0}


def leaves(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from leaves(v)
    elif isinstance(node, list):
        for v in node:
            yield from leaves(v)
    else:
        yield node


class Hurricane9FitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = patch.object(F, "element_table", fake_table)
        cls.patch.start()
        cls.obs = observations()
        cls.table = fake_table(sorted({e for o in cls.obs for e in o["composition"]}))
        cls.tmp = tempfile.TemporaryDirectory()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            F.main(["--smoke", "--output-dir", cls.tmp.name])
        cls.lines = buffer.getvalue().strip().split("\n")
        cls.text = "".join(line.split("|", 2)[2] for line in cls.lines if line.startswith("h9f|"))
        cls.report = json.loads(cls.text)

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.tmp.cleanup()

    def test_the_protocol_is_hashed_and_a_run_refuses_another_hash(self):
        self.assertEqual(F.protocol_sha256(), hashlib.sha256(F.protocol_text().encode("utf-8")).hexdigest())
        self.assertEqual(json.loads(F.protocol_text()), json.loads(json.dumps(F.PROTOCOL)))
        self.assertEqual((F.PROTOCOL["adopted"], [c["id"] for c in F.PROTOCOL["claims"]]), (False, ["C0", "C1", "C2", "C3", "C4"]))
        with patch.object(D, "fetch", side_effect=AssertionError("data was read")):
            for given in ("", "0" * 64):
                with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                    F.main(["--run", "--expect-protocol-sha256", given])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            F.main(["--protocol"])
        self.assertTrue(buffer.getvalue().strip().endswith("protocol sha256 " + F.protocol_sha256()))

    def test_the_smoke_run_reports_every_window_and_claim(self):
        r = self.report
        self.assertEqual((r["smoke"], r["adopted"], r["version"], r["protocol"]["sha256"]), (True, False, F.VERSION, F.protocol_sha256()))
        self.assertEqual(sorted(r["windows"]), ["1985", "1990", "1995", "2000", "2005", "2010", "2015"])
        self.assertTrue(all(w["cohort_agrees_with_counts"] for w in r["windows"].values()))
        self.assertEqual({f: sorted(v["windows"]) for f, v in r["families"].items()}, {f: [str(t) for t in ts] for f, ts in F.WINDOWS.items()})
        self.assertEqual(sorted(r["new_family"]), ["cuprate:1985", "iron-nickel:2005"])
        self.assertEqual([c["id"] for c in r["claims"]], ["C0", "C1", "C2", "C3", "C4:cuprate:1985", "C4:iron-nickel:2005"])
        self.assertIn("transfer", r["windows"]["1985"]["designs"])
        self.assertNotIn("transfer", r["windows"]["1990"]["designs"])
        self.assertEqual(self.lines[-1], "=== hurricane9-fit end sha256 " + hashlib.sha256(self.text.encode("utf-8")).hexdigest() + " chars " + str(len(self.text)))
        self.assertEqual(self.text + "\n", (Path(self.tmp.name) / "hurricane9-report.json").read_text(encoding="utf-8"))
        saved = pd.read_csv(Path(self.tmp.name) / "hurricane9-predictions.csv")
        self.assertEqual(len(saved), sum(sum(w["cohort"]["test_rows"].values()) for w in r["windows"].values()))
        self.assertTrue({"cutoff", "family", "exact", "parents", "tc_k", "R0", "R1", "previous", "data", "names", "measured", "measured_score"} <= set(saved.columns))
        self.assertNotIn("NaN", self.text)

    def test_each_design_trains_on_its_own_rows(self):
        w = F.window_rows(self.obs, 2005, half(self.obs))
        modelled = [r for r in w["train"] if r["unit"]["family"] in D.EVENT_K]
        got = {n: F.fit_predict(n, w["train"], w["test"], self.table, {}) for n in F.DESIGNS}
        self.assertEqual(got["previous"]["train_rows"], sum(r["supported"] for r in modelled))
        self.assertEqual((got["data"]["train_rows"], got["names"]["train_rows"], got["measured"]["train_rows"]), (len(modelled),) * 3)
        self.assertEqual(got["transfer"]["train_rows"], len(w["train"]))
        self.assertGreater(len(w["train"]), len(modelled))
        self.assertLess(got["previous"]["train_rows"], got["data"]["train_rows"])
        self.assertLess(got["data"]["features"], got["names"]["features"])
        self.assertEqual(got["measured"]["features"], got["names"]["features"] + len(F.MEASURED))
        self.assertFalse(got["transfer"]["classifier"])

    def test_nothing_reported_after_the_cutoff_reaches_the_training_side(self):
        head, rows = table_rows(F.synthetic_table())
        # reports after the window (2012, 2013) and a report inside it (2008) on a unit the training side already holds
        later = observations(rows + [dict(rows[2], num="9001", refno="L9001", year="2012", tc="77.7"), dict(rows[40], num="9002", refno="L9002", year="2013", tc="5.5"),
                                     dict(rows[2], num="9004", refno="L9004", year="2008", tc="30.0")])
        halved = observations(change=lambda r: dict(r, tc=f"{float(r['tc']) * 0.5:.2f}") if r["tc"] and 2005 < int(r["year"]) <= 2010 else r)
        self.assertEqual((len(later), len(halved)), (len(self.obs) + 3, len(self.obs)))
        self.assertTrue(all(o["status"] == "admitted" for o in later + halved))
        base = F.window_rows(self.obs, 2005, half(self.obs))
        self.assertGreater(len(base["test"]), 20)
        ref = {n: F.fit_predict(n, base["train"], base["test"], self.table, {}) for n in ("previous", "measured")}
        self.assertTrue(ref["measured"]["regressor"] and ref["measured"]["classifier"] and np.isfinite(ref["measured"]["tc"]).all())
        for other in (later, halved):
            w = F.window_rows(other, 2005, half(self.obs))
            self.assertEqual([r["unit"]["exact"] for r in w["test"]], [r["unit"]["exact"] for r in base["test"]])
            self.assertEqual([(r["unit"]["exact"], r["unit"]["tc_k"], r["supported"], r["c"]) for r in w["train"]],
                             [(r["unit"]["exact"], r["unit"]["tc_k"], r["supported"], r["c"]) for r in base["train"]])
            for n in ref:   # a later report, or the test units' own Tc, changes no prediction and no score
                got = F.fit_predict(n, w["train"], w["test"], self.table, {})
                np.testing.assert_array_equal(got["tc"], ref[n]["tc"])
                np.testing.assert_array_equal(got["score"], ref[n]["score"])
        self.assertNotEqual([r["unit"]["tc_k"] for r in F.window_rows(halved, 2005, set())["test"]], [r["unit"]["tc_k"] for r in base["test"]])

    def test_units_with_unknown_oxygen_and_flagged_units_take_no_part(self):
        head, rows = table_rows(F.synthetic_table())
        unknown = dict(rows[2], num="9003", refno="U9003", mo2="z", year="1987")
        w = F.window_rows(observations(rows + [unknown]), 1990, set())
        self.assertEqual(w["cohort"]["train_units"], F.window_rows(self.obs, 1990, set())["cohort"]["train_units"] + 1)
        self.assertEqual(w["cohort"]["train_rows"], F.window_rows(self.obs, 1990, set())["cohort"]["train_rows"])
        first = F.window_rows(self.obs, 1990, set())["train"][0]["unit"]["exact"]
        with patch.object(F, "FLAGGED", [first]):
            self.assertNotIn(first, [r["unit"]["exact"] for r in F.window_rows(self.obs, 1990, set())["train"]])

    def test_the_previous_models_rows_are_the_bins_of_its_3dsc_classes(self):
        text = ("# a comment line, as in the 3DSC file\nformula_sc,tc,sc_class\nLa1.85Sr0.15Cu1O4,36.0,Cuprate\nLa3.7Sr0.3Cu2O8,35.0,Cuprate\n"
                "Ba1Fe1.8Co0.2As2,22.0,Ferrite\nCe1Cu2Si2,0.6,Heavy_fermion\nCe1Co1In5,2.3,OxideHeavy_fermion\nBa0.6K0.4Bi1O3,30.0,Oxide\n"
                "Nb3Sn1,18.0,Other\nMo6S8Pb1,14.0,Chevrel\nY1Ba2Cu3O7,,Cuprate\nY1Ba2Cu3O6.5,-1,Cuprate\n(La)2CuO4,30,Cuprate\nLa2Cu1O4,0,Cuprate\n")
        bins, counts = F.supported_bins(text)
        self.assertEqual(counts, {"rows": 12, "rows_in_the_five_classes": 10, "rows_unreadable": 2, "rows_without_tc": 1, "formulas": 7, "bins": 6})
        self.assertEqual(bins, {"Cu0.541 La1 O2.162 Sr0.081", "As1 Ba0.5 Co0.1 Fe0.9", "Ce0.5 Cu1 Si1", "Ce0.2 Co0.2 In1", "Ba0.6 Bi1 K0.4 O3", "Cu0.5 La1 O2"})
        obs = observations()
        unit = next(u for u in D.canonical_units(obs, lift=True) if u["exact"].startswith("Cu1 La1.85 Sr0.15"))
        self.assertIn(unit["canonical"], bins)        # the datasheet unit and the 3DSC formula land in one bin
        w = F.window_rows(obs, 1990, bins)
        self.assertEqual({r["unit"]["exact"] for r in w["train"] if r["supported"]}, {"Ba0.6 Bi1 K0.4 O3", "Ce1 Cu2 Si2", unit["exact"]})
        self.assertEqual(w["cohort"]["train_rows_supported"], 3)

    def test_the_dry_run_holds_counts_only_and_fits_nothing(self):
        with patch.object(F.HU, "_fit", side_effect=AssertionError("a model was fitted")), contextlib.redirect_stderr(io.StringIO()):
            out = F.preflight(self.obs, half(self.obs), self.table)
        self.assertEqual(sorted(out["windows"]), sorted(self.report["windows"]))
        for t, cell in out["windows"].items():
            fitted = self.report["windows"][t]
            self.assertEqual(cell["cohort"], fitted["cohort"])
            self.assertEqual(sorted(cell["designs"]), sorted(fitted["designs"]))
            for n, d in cell["designs"].items():   # the dry run announces exactly what the run then does
                self.assertEqual((d["train_rows"], d["train_rows_with_tc"], d["features"], d["regressor"], d["classifier"]),
                                 tuple(fitted["designs"][n][k] for k in ("train_rows", "train_rows_with_tc", "features", "regressor", "classifier")))
        self.assertTrue(all(isinstance(v, (int, str)) and not isinstance(v, float) for v in leaves(F.clean(out))))
        self.assertFalse(any(isinstance(v, str) and any(c.isdigit() for c in v) for v in leaves(F.clean(out))))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            F.main(["--smoke", "--preflight"])
        lines = buffer.getvalue().strip().split("\n")
        text = "".join(line.split("|", 2)[2] for line in lines if line.startswith("h9p|"))
        self.assertEqual((lines[0], lines[-1]), ("=== hurricane9-preflight begin", "=== hurricane9-preflight end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text))))
        self.assertNotIn("claims", json.loads(text))

    def test_the_lattice_unit_rule(self):
        self.assertEqual([F.angstrom(v, u) for v, u in ((0.38, "nm"), (3.8, "nm"), (0.38, ""), (3.8, "A"), (150.0, "A"), (1.5, "A"), (None, "A"), (0.0, "nm"))],
                         [0.38 * 10.0, 3.8, 0.38 * 10.0, 3.8, None, None, None, None])

    def test_rank_correlation_auc_and_parent_clusters(self):
        self.assertAlmostEqual(F.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(F.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(F.spearman([1, 1, 1, 1], [1, 2, 3, 4]))
        self.assertIsNone(F.spearman([1, 2], [1, 2]))
        self.assertIsNone(F.spearman([float("nan")] * 4, [1, 2, 3, 4]))
        label = np.array([1] * 10 + [0] * 10)
        self.assertEqual((F.auc(np.arange(20)[::-1], label), F.auc(np.arange(20), label), F.auc(np.ones(20), label)), (1.0, 0.0, 0.5))
        self.assertIsNone(F.auc(np.arange(19), label[:19]))
        unit = lambda *parents: {"unit": {"parents": list(parents)}}
        self.assertEqual(F.clusters([unit("A"), unit("B"), unit("A", "C"), unit("C"), unit()]).tolist(), [0, 1, 0, 0, 2])

    def test_a_contrast_is_pooled_over_shared_windows_and_needs_enough_parents(self):
        rng = np.random.default_rng(0)

        def window(cutoff, parents, good, bad):
            y = rng.normal(size=parents * 3)
            return {"cutoff": cutoff, "y": y, "cluster": np.repeat(np.arange(parents), 3),
                    "pred": {"good": y + rng.normal(scale=0.1, size=len(y)) if good else np.full(len(y), np.nan), "bad": rng.normal(size=len(y)) if bad else np.full(len(y), np.nan)}}

        out = F.pooled_report([window(1990, 30, True, True), window(1995, 30, True, False)], ["good", "bad"], [("good", "bad")], 7)
        d = out["difference"]["good-bad"]
        self.assertEqual((out["windows"], d["windows"], d["parents"], out["parents"]), ([1990, 1995], [1990], 30, 60))
        self.assertAlmostEqual(d["estimate"], d["good"] - d["bad"])
        self.assertTrue(d["met"] and d["lower95"] > 0 and d["valid_replicates"] == F.REPLICATES)
        self.assertEqual(out["spearman"]["bad"]["estimate"], d["bad"])
        few = F.pooled_report([window(1990, 6, True, True)], ["good", "bad"], [("good", "bad")], 7)["difference"]["good-bad"]
        self.assertFalse(few["met"])
        self.assertEqual(F.pooled_report([], ["good"], [], 7)["spearman"]["good"]["estimate"], None)

    def test_the_released_measure_counts_a_measured_negative_as_zero_kelvin(self):
        unit = lambda tc, event: {"unit": {"tc_k": tc, "event": event, "parents": ["P"]}}
        rows = [unit(30.0, 1), unit(None, 0), unit(None, None), unit(2.0, 0), unit(None, 1)]
        idx, y0 = F.outcome_rows(rows)
        self.assertEqual((idx, y0.tolist()), ([0, 1, 3], [30.0, 0.0, 2.0]))
        nan = float("nan")
        sets = [{"cutoff": 1990, "y": np.array([10.0, 20.0]), "pred": {"a": np.array([12.0, 20.0]), "b": np.array([10.0, 30.0])}},
                {"cutoff": 1995, "y": np.array([5.0]), "pred": {"a": np.array([5.0]), "b": np.array([nan])}},
                {"cutoff": 2000, "y": np.array([]), "pred": {"a": np.array([]), "b": np.array([])}}]
        self.assertEqual(F.pooled_error(sets, ["a", "b"]), {"windows": [1990], "units": 2, "values": {"a": 1.0, "b": 5.0}})   # only where both are defined
        self.assertEqual(F.pooled_error(sets, ["a"]), {"windows": [1990, 1995], "units": 3, "values": {"a": 2.0 / 3.0}})
        self.assertEqual(F.pooled_error([], ["a"]), {"windows": [], "units": 0, "values": {"a": None}})
        family = self.report["families"]["cuprate"]
        window = family["windows"]["1995"]
        self.assertEqual(sorted(window["product"]["mae_k"]), sorted(F.LADDER))
        self.assertGreaterEqual(window["product"]["units"], window["units_with_tc"])
        self.assertEqual(sorted(family["pooled_product"]["mae_k"]["values"]), sorted(F.LADDER))
        self.assertEqual(sorted(family["pooled_all"]["mae_k"]["values"]), sorted(["R0", "R1"] + F.LADDER))

    def test_the_new_family_auc_counts_only_the_new_familys_positives(self):
        unit = lambda family, event, parent: {"unit": {"family": family, "high_tc_event": event, "parents": [parent]}}
        rows = ([unit("cuprate", 1, f"c{i}") for i in range(12)] + [unit("cuprate", 0, f"n{i}") for i in range(6)] + [unit("other", 0, f"o{i}") for i in range(6)]
                + [unit("other-oxide", 1, f"x{i}") for i in range(3)] + [unit("other", None, "u")])
        tc = np.array([50.0] * 12 + [5.0] * 12 + [90.0] * 3 + [1.0])
        out = F.new_family_auc(rows, tc, 7, "cuprate")     # the three other-oxide units that pass the event are left out
        self.assertEqual((out["units"], out["positives"], out["negatives"], out["positives_of_other_families_left_out"], out["auc"]), (24, 12, 12, 3, 1.0))
        self.assertTrue(out["above_chance"])
        self.assertEqual(F.new_family_auc(rows, tc, 7, "other-oxide")["positives"], 3)
        none = F.new_family_auc(rows, np.full(len(rows), np.nan), 7, "cuprate")
        self.assertEqual((none["auc"], none["above_chance"], none["positives_of_other_families_left_out"]), (None, False, 3))
        claim = next(c for c in self.report["claims"] if c["id"] == "C4:cuprate:1985")
        self.assertEqual(claim["positives_of_other_families_left_out"], 0)

    def test_the_report_has_no_non_finite_number(self):
        self.assertEqual(F.clean({"a": float("nan"), "b": [np.float64(1.5), np.int64(2), np.bool_(True), float("inf")], 3: None}),
                         {"a": None, "b": [1.5, 2, True, None], "3": None})
        json.dumps(F.clean(self.report), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
