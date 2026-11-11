"""Screening round 6 (the candidates of Hurricane 9.0), on invented rows: no datasheet, no JARVIS, no Radar."""
import contextlib
import copy
import csv
import io
import json
import math
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
import hurricane9_screen as S
from test_hurricane9 import fake_table


class Hurricane9ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(F, "element_table", fake_table), patch.object(F, "REPLICATES", 40), patch.object(S, "pretty", R.formula_of)]
        for p in cls.patches:
            p.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.before = json.loads(R.P.PROGRESS.read_text(encoding="utf-8"))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            cls.out = S.run(smoke=True, output_dir=Path(cls.tmp.name))
        cls.lines = buffer.getvalue().strip().split("\n")
        cls.progress = json.loads((Path(cls.tmp.name) / "progress.json").read_text(encoding="utf-8"))
        with open(Path(cls.tmp.name) / "screen_round6_hurricane.csv", newline="", encoding="utf-8") as fh:
            cls.table = list(csv.DictReader(fh))
        with open(Path(cls.tmp.name) / S.BACKGROUND, newline="", encoding="utf-8") as fh:
            cls.released = {r["jid"]: r for r in csv.DictReader(fh)}
        cls.block = cls.progress["screen"]["hurricane"]

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.tmp.cleanup()

    def test_the_protocol_binds_the_released_model_and_the_run_needs_its_declaration(self):
        self.assertEqual(S.PROTOCOL["model"]["release_protocol_sha256"], R.protocol_sha256())
        self.assertEqual((S.PROTOCOL["model"]["version"], S.PROTOCOL["screening_round"]), ("9.0", 6))
        self.assertEqual((S.PROTOCOL["listed"]["per_chemical_system"], S.PROTOCOL["listed"]["top"]), (1, 50))
        with tempfile.TemporaryDirectory() as tmp, patch.object(S, "DECLARATION", Path(tmp) / "declaration.md"), \
                patch.object(D, "fetch", side_effect=AssertionError("data was read")):
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                S.run()
            (Path(tmp) / "declaration.md").write_text("another hash " + "0" * 64, encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                S.run()

    def test_every_chance_is_the_cross_fitted_chance_of_the_release_run(self):
        self.assertEqual(self.out["reproduces"]["rows"], len(self.released))
        self.assertLessEqual(self.out["reproduces"]["largest_difference"], S.TOLERANCE)
        sent = {k for k, r in self.released.items() if r["sent"] == "True"}
        self.assertEqual({r["jid"] for r in self.table}, sent)
        for r in self.table:
            ref = self.released[r["jid"]]
            self.assertEqual(r["not_known"], ref["not_known"])
            if ref["p_sc"]:
                self.assertAlmostEqual(float(r["p_sc"]), float(ref["p_sc"]), delta=S.TOLERANCE)
        for c in self.block["candidates"]:
            self.assertAlmostEqual(c["p_sc"], float(self.released[c["id"]]["p_sc"]), delta=6e-4)

    def test_a_different_pool_routing_or_chance_stops_the_run_before_anything_is_written(self):
        observations, _ = D.load_observations(F.synthetic_table())
        bg = R.synthetic_background(R.final_rows(observations))
        sc = S.score(observations, bg, [])
        path = Path(self.tmp.name) / S.BACKGROUND
        self.assertEqual(S.compare_with_release(bg, sc, path)["rows"], len(bg["key"]))
        moved = dict(bg, key=list(reversed(bg["key"])))
        with self.assertRaisesRegex(SystemExit, "not the release run's pool"):
            S.compare_with_release(moved, sc, path)
        routed = dict(bg, sent=~np.asarray(bg["sent"], bool))
        with self.assertRaisesRegex(SystemExit, "routing or the not-known answer differs"):
            S.compare_with_release(routed, sc, path)
        finite = np.flatnonzero(np.isfinite(sc["p"]))
        if len(finite):
            shifted = dict(sc, p=sc["p"].copy())
            shifted["p"][finite[0]] += 0.01
            with self.assertRaisesRegex(SystemExit, "differs from the release run"):
                S.compare_with_release(bg, shifted, path)

    def test_the_list_holds_judged_compounds_only_one_per_chemical_system_in_order(self):
        rows = [dict(r, not_known=r["not_known"] == "True", p_sc=float(r["p_sc"]) if r["p_sc"] else math.nan,
                     tc_sc=float(r["tc_sc"]) if r["tc_sc"] else math.nan, hurricane_tc=float(r["hurricane_tc"]) if r["hurricane_tc"] else math.nan)
                for r in self.table]
        judged = [r for r in rows if S.judged(r)]
        cands = self.block["candidates"]
        self.assertEqual(len(cands), min(S.TOP_N, len({r["chemsys"] for r in judged})))
        self.assertEqual([c["rank"] for c in cands], list(range(1, len(cands) + 1)))
        by_id = {r["jid"]: r for r in rows}
        self.assertEqual(len({by_id[c["id"]]["chemsys"] for c in cands}), len(cands))
        self.assertTrue(all(S.judged(by_id[c["id"]]) for c in cands))
        products = [by_id[c["id"]]["hurricane_tc"] for c in cands]
        self.assertEqual(products, sorted(products, reverse=True))
        for c in cands:                                      # the best of its chemical system, and nothing made up
            system = [r for r in judged if r["chemsys"] == by_id[c["id"]]["chemsys"]]
            self.assertEqual(by_id[c["id"]]["hurricane_tc"], max(r["hurricane_tc"] for r in system))
            self.assertAlmostEqual(c["tc"], c["p_sc"] * c["tc_sc"], delta=0.02 + 0.001 * c["tc_sc"])
            self.assertLessEqual(c["novelty"], 1.0)
            self.assertNotIn("outside", c)
            self.assertNotIn("p_lo", c)
        self.assertEqual(self.block["not_known"]["n"], sum(1 for r in rows if r["not_known"]))
        self.assertEqual(self.block["not_known"]["of"], len(rows))
        self.assertEqual(self.block["pool"]["n_sent"], len(rows))

    def test_the_range_is_the_released_width_and_the_nearest_compound_is_a_training_row(self):
        width = self.block["range"]["width_log"]
        self.assertEqual(self.block["range"]["of"], "the Tc if it superconducts")
        train = {S.nearest_record(r)[0] for r in R.final_rows(D.load_observations(F.synthetic_table())[0])}
        for c in self.block["candidates"]:
            self.assertAlmostEqual(c["lo"], max(math.expm1(math.log1p(c["tc_sc"]) - width), 0.0), delta=0.03 + 0.01 * c["tc_sc"])
            self.assertAlmostEqual(c["hi"], math.expm1(math.log1p(c["tc_sc"]) + width), delta=0.03 + 0.03 * c["tc_sc"])
            self.assertIn(c["nearest"]["formula"], train)
            self.assertEqual(sorted(c["atoms"]), ["elements", "frac", "lattice"])
        self.assertEqual(S.nearest_record({"comp": {"Cu": 1.0, "La": 1.85, "O": 4.0, "Sr": 0.15}, "unit": {"tc_k": 38.0, "event": 1}}), ("Cu1La1.85O4Sr0.15", 38.0))
        self.assertEqual(S.nearest_record({"comp": {"Cu": 1.0, "O": 1.0}, "unit": {"tc_k": None, "event": 0}})[1], 0.0)
        self.assertIsNone(S.nearest_record({"comp": {"Cu": 1.0, "O": 1.0}, "unit": {"tc_k": None, "event": -1}})[1])

    def test_only_hurricanes_list_its_model_name_the_stage_line_and_one_log_entry_change(self):
        before, after = copy.deepcopy(self.before), copy.deepcopy(self.progress)
        self.assertEqual(after["screen"]["models"], [m for m in before["screen"]["models"] if not m.startswith("Hurricane")] + ["Hurricane 9.0"])
        self.assertEqual((self.block["model"], self.block["round"], self.block["design"]), ("Hurricane 9.0", 6, "H90"))
        for payload in (before, after):
            payload["screen"].pop("hurricane")
            payload["screen"].pop("models")
        self.assertEqual(after["screen"], before["screen"])          # Storm's list and every other field of the block
        self.assertEqual(after["screen"]["round"], 5)
        stage_b = next(s for s in before["stages"] if s["id"] == "screen")
        stage_a = next(s for s in after["stages"] if s["id"] == "screen")
        self.assertIn("Hurricane's list is from round 6, screened with Hurricane 9.0", stage_a["detail"])
        self.assertIn(f"{len(before['screen']['candidates'])} Storm candidates and {len(self.block['candidates'])} Hurricane candidates", stage_a["detail"])
        self.assertEqual({k: v for k, v in stage_a.items() if k != "detail"}, {k: v for k, v in stage_b.items() if k != "detail"})
        new = [e for e in after["log"] if e not in before["log"]]
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0]["event"].startswith("Screening round 6: Hurricane 9.0 screened"))
        self.assertIn("Storm's list stays as round 5 published it", new[0]["event"])
        for payload in (before, after):
            payload.pop("screen")
            payload.pop("log")
            payload.pop("updated")
            next(s for s in payload["stages"] if s["id"] == "screen").pop("detail")
        self.assertEqual(after, before)                              # no model, result or other stage is touched

    def test_a_recorded_check_keeps_the_exact_id_correction_of_the_literature_audit(self):
        records = {"X-1": {"check_correction": {"replaces_doi": "10.1/old", "check": {"kind": "experiment", "superconducts": None, "doi": "10.1/old", "note": "unknown"}}}}
        original = {"kind": "experiment", "superconducts": False, "doi": "10.1/old"}
        self.assertEqual(S.corrected_check("X-1", original, records), records["X-1"]["check_correction"]["check"])
        self.assertEqual(S.corrected_check("X-2", original, records), original)
        self.assertEqual(S.corrected_check("X-1", {"kind": "experiment", "doi": "10.1/other"}, records)["doi"], "10.1/other")
        self.assertIsNone(S.corrected_check("X-1", None, records))

    def test_first_listings_come_from_the_published_block_when_results_do_not_hold_the_round(self):
        prog = {"screen": {"candidates": [{"id": "JVASP-1", "formula": "NbTi", "listed": {"date": "2026-10-31", "round": 5, "file": "screen_round5.json"}}],
                           "hurricane": {"candidates": [{"id": "JVASP-2", "formula": "YbIn5Rh", "listed": {"date": "2026-10-31", "round": 2, "file": "screen_round2.json"}},
                                                        {"id": "JVASP-3", "formula": "CeCu5", "listed": {"date": "bad"}}]}}}
        by_id, by_comp = S.published_listings(prog)
        self.assertEqual(set(by_id), {"JVASP-1", "JVASP-2"})
        self.assertEqual((by_id["JVASP-2"]["round"], by_id["JVASP-2"]["file"]), (2, "screen_round2.json"))
        self.assertEqual(len(by_comp), 2)

    def test_the_log_carries_the_block_and_its_hash(self):
        start = self.lines.index("=== hurricane9-screen begin")
        self.assertTrue(self.lines[-1].startswith("=== hurricane9-screen end sha256 "))
        self.assertTrue(all(line.startswith(f"h9s|{i:03d}|") for i, line in enumerate(self.lines[start + 1:-1])))
        text = "".join(line.split("|", 2)[2] for line in self.lines[start + 1:-1])
        shown = json.loads(text)
        self.assertEqual(shown["block"], self.block)
        self.assertTrue(shown["smoke"])
        import hashlib
        self.assertIn(hashlib.sha256(text.encode("utf-8")).hexdigest(), self.lines[-1])
        result = json.loads((Path(self.tmp.name) / "screen_round6.json").read_text(encoding="utf-8"))
        self.assertEqual((result["round"], result["candidates"], result["hurricane"]), (6, [], self.block))


if __name__ == "__main__":
    unittest.main()
