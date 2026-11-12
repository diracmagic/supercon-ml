"""Screening round 7 (Hurricane 9.0 on a wider pool), on invented rows: no datasheet, no database, no Radar."""
import contextlib
import copy
import csv
import gzip
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
import hurricane9_screen as S6
import hurricane9_screen7 as S
import screen as SC
from test_hurricane9 import fake_table


def plain(comp: dict) -> str:
    return "".join(f"{e}{float(v):g}" for e, v in sorted(comp.items()))


def rec(db, ident, comp, gap=0.0, hull=0.0, experimental=False, nat=None, **more):
    n = sum(comp.values()) if nat is None else nat
    return S.record(db, ident, comp, n, gap, hull, 0.0, experimental, [[4, 0, 0], [0, 4, 0], [0, 0, 4]], 123, "P4/mmm", **more)


class Hurricane9Screen7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(F, "element_table", fake_table), patch.object(F, "REPLICATES", 40), patch.object(S, "pretty", plain)]
        for p in cls.patches:
            p.start()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.before = json.loads(R.P.PROGRESS.read_text(encoding="utf-8"))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            cls.out = S.run(smoke=True, output_dir=Path(cls.tmp.name))
        cls.lines = buffer.getvalue().strip().split("\n")
        cls.progress = json.loads((Path(cls.tmp.name) / "progress.json").read_text(encoding="utf-8"))
        with open(Path(cls.tmp.name) / "screen_round7_hurricane.csv", newline="", encoding="utf-8") as fh:
            cls.table = list(csv.DictReader(fh))
        with open(Path(cls.tmp.name) / S.BACKGROUND, newline="", encoding="utf-8") as fh:
            cls.released = {r["jid"]: r for r in csv.DictReader(fh)}
        with gzip.open(Path(cls.tmp.name) / S.POOL_FILE, "rt", encoding="utf-8", newline="") as fh:
            cls.pool = list(csv.DictReader(fh))
        cls.block = cls.progress["screen"]["hurricane"]
        cls.counts = {e: S.MIN_ELEMENT for e in ("La", "Sr", "Cu", "O", "Ba", "Y", "Fe", "As", "Nb", "Se", "Ca")}

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.tmp.cleanup()

    # ------------------------------------------------------------ the protocol and the release
    def test_the_protocol_binds_the_released_model_and_the_run_needs_its_declaration(self):
        self.assertEqual(S.PROTOCOL["model"]["release_protocol_sha256"], R.protocol_sha256())
        self.assertEqual((S.PROTOCOL["model"]["version"], S.PROTOCOL["screening_round"]), ("9.0", 7))
        self.assertEqual((S.PROTOCOL["listed"]["per_chemical_system"], S.PROTOCOL["listed"]["top_per_track"]), (1, 50))
        self.assertEqual(set(S.PROTOCOL["sources"]), {"JARVIS-DFT", "Materials Project", "Alexandria", "COD"})
        self.assertTrue(all(v.get("licence") and v.get("cite") for v in S.SOURCES.values()))
        with tempfile.TemporaryDirectory() as tmp, patch.object(S, "DECLARATION", Path(tmp) / "declaration.md"), \
                patch.object(D, "fetch", side_effect=AssertionError("data was read")):
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                S.run()
            (Path(tmp) / "declaration.md").write_text("another hash " + "0" * 64, encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "refusing to read any data"):
                S.run()

    def test_the_background_is_reproduced_and_a_pool_compound_of_the_background_gets_the_released_chance(self):
        self.assertEqual(self.out["reproduces"]["rows"], len(self.released))
        self.assertLessEqual(self.out["reproduces"]["largest_difference"], S.TOLERANCE)
        self.assertLessEqual(self.out["classifier_difference"], 1e-12)
        compared = 0
        for r in self.table:
            ref = self.released.get(r["id"]) if r["source"] == "JARVIS-DFT" else None
            if ref and ref["p_sc"] and r["p_sc"]:
                self.assertAlmostEqual(float(r["p_sc"]), float(ref["p_sc"]), delta=S.TOLERANCE)   # the composition decides, whoever routes it
                self.assertEqual(r["not_known"], ref["not_known"])
                compared += 1
        self.assertGreater(compared, 3)

    def test_classifiers_that_differ_from_the_guards_stop_the_run(self):
        observations, _ = D.load_observations(F.synthetic_table())
        bg = R.synthetic_background(R.final_rows(observations))
        real = R.Design9.chance
        calls = {"n": 0}

        def shifted(self, X):
            calls["n"] += 1
            out = real(self, X)
            return out + (0.01 if calls["n"] == 7 and len(out) else 0.0)      # one of this module's own fits (the guard's come first)
        with patch.object(R.Design9, "chance", shifted):
            with self.assertRaisesRegex(SystemExit, "differ from the guard's"):
                S.score(observations, bg, [], [])

    # ------------------------------------------------------------ the lists
    def rows(self):
        f = lambda v: float(v) if v else math.nan   # noqa: E731
        return [dict(r, not_known=r["not_known"] == "True", p_sc=f(r["p_sc"]), tc_sc=f(r["tc_sc"]), hurricane_tc=f(r["hurricane_tc"])) for r in self.table]

    def test_each_list_holds_judged_compounds_of_its_track_one_per_chemical_system_in_order(self):
        rows = self.rows()
        by_key = {(r["source"], r["id"]): r for r in rows}
        tracks = {t["id"]: t for t in self.block["tracks"]}
        self.assertEqual(list(tracks), ["experimental", "computed"])
        for track, cands in (("experimental", self.block["candidates"]), ("computed", self.block["candidates_computed"])):
            mine = [r for r in rows if r["track"] == track]
            judged = [r for r in mine if S.judged(r)]
            self.assertGreater(len(cands), 0)
            self.assertEqual(len(cands), min(S.TOP_N, len({r["chemsys"] for r in judged})))
            self.assertEqual([c["rank"] for c in cands], list(range(1, len(cands) + 1)))
            picked = [by_key[(c["source"]["source"], c["id"])] for c in cands]
            self.assertTrue(all(r["track"] == track and S.judged(r) for r in picked))
            self.assertEqual(len({r["chemsys"] for r in picked}), len(cands))
            products = [r["hurricane_tc"] for r in picked]
            self.assertEqual(products, sorted(products, reverse=True))
            for c, r in zip(cands, picked):
                self.assertEqual(r["hurricane_tc"], max(x["hurricane_tc"] for x in judged if x["chemsys"] == r["chemsys"]))
                self.assertEqual(c["track"], track)
                self.assertAlmostEqual(c["tc"], c["p_sc"] * c["tc_sc"], delta=0.02 + 0.001 * c["tc_sc"])
                self.assertLessEqual(c["novelty"], 1.0)
            self.assertEqual(len(mine), len(judged))                                   # the table holds the judged compounds only
            sent = [r for r in self.pool if r["track"] == track and r["sent"] == "True"]
            self.assertEqual((tracks[track]["pool"], tracks[track]["sent"], tracks[track]["judged"], tracks[track]["listed"]),
                             (sum(1 for r in self.pool if r["track"] == track), len(sent), len(judged), len(cands)))
            self.assertEqual(tracks[track]["not_known"], sum(1 for r in sent if r["not_known"] == "True"))
            self.assertEqual({(r["source"], r["id"]) for r in sent if r["not_known"] == "False"}, {(r["source"], r["id"]) for r in judged})
        sent = [r for r in self.pool if r["sent"] == "True"]
        self.assertTrue(all(r["not_known"] == "" for r in self.pool if r["sent"] == "False"))
        self.assertEqual(self.block["not_known"]["n"], sum(1 for r in sent if r["not_known"] == "True"))
        self.assertEqual(self.block["pool"]["n_sent"], len(sent))
        self.assertEqual(self.block["pool"]["n_screened"], len(self.pool))
        self.assertEqual(len({(r["source"], r["id"]) for r in self.pool}), len(self.pool))
        self.assertEqual(self.out["files"]["pool_sha256"], __import__("hashlib").sha256((Path(self.tmp.name) / S.POOL_FILE).read_bytes()).hexdigest())

    def test_a_candidate_names_its_source_and_the_experimental_structure_behind_its_track(self):
        for c in self.block["candidates"]:
            self.assertIn(c["source"]["source"], S.ORDER)
            self.assertIn(c["experimental"]["source"], ("JARVIS-DFT", "Materials Project", "COD"))      # Alexandria marks none
            self.assertEqual(c["icsd"], c["experimental"]["source"] != "COD")
            if c["source"]["source"] == "COD":
                self.assertNotIn("atoms", c)
                self.assertNotIn("gap", c)
                self.assertTrue(c["url"].startswith("https://www.crystallography.net/cod/"))
            else:
                self.assertEqual(sorted(c["atoms"]), ["elements", "frac", "lattice"])
        for c in self.block["candidates_computed"]:
            self.assertNotIn("experimental", c)
            self.assertFalse(c["icsd"])
            self.assertLessEqual(c["ehull"], S.EHULL_MAX)
            self.assertNotEqual(c["source"]["source"], "COD")
        marked = [c for c in self.block["candidates"] if c.get("labels")]
        self.assertTrue(all(c["labels"] == [S.NO_GAP] and c["source"]["source"] == "COD" for c in marked))
        self.assertEqual([s["name"] for s in self.block["sources"]], S.ORDER)
        self.assertTrue(all(s["licence"] and s["cite"] for s in self.block["sources"]))
        self.assertEqual(self.block["background"]["cross_fitted"], "fold")       # not every compound is a background compound now

    def test_only_hurricanes_lists_its_model_name_the_stage_line_and_one_log_entry_change(self):
        before, after = copy.deepcopy(self.before), copy.deepcopy(self.progress)
        self.assertEqual(after["screen"]["models"], [m for m in before["screen"]["models"] if not m.startswith("Hurricane")] + ["Hurricane 9.0"])
        self.assertEqual((self.block["model"], self.block["round"], self.block["design"]), ("Hurricane 9.0", 7, "H90"))
        for payload in (before, after):
            payload["screen"].pop("hurricane")
            payload["screen"].pop("models")
        self.assertEqual(after["screen"], before["screen"])          # Storm's list and every other field of the block
        stage_b = next(s for s in before["stages"] if s["id"] == "screen")
        stage_a = next(s for s in after["stages"] if s["id"] == "screen")
        self.assertIn(f"{len(before['screen']['candidates'])} Storm candidates retained from JARVIS-DFT", stage_a["detail"])
        self.assertIn(f"{len(self.block['candidates'])} Hurricane candidates with an experimental structure and "
                      f"{len(self.block['candidates_computed'])} known from calculation only", stage_a["detail"])
        self.assertNotIn("Hurricane candidates retained from JARVIS-DFT", stage_a["detail"])
        self.assertEqual({k: v for k, v in stage_a.items() if k != "detail"}, {k: v for k, v in stage_b.items() if k != "detail"})
        new = [e for e in after["log"] if e not in before["log"]]
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0]["event"].startswith("Screening round 7: Hurricane 9.0 screened a wider pool"))
        self.assertIn("Storm's list stays as round 5 published it", new[0]["event"])
        for payload in (before, after):
            payload.pop("screen")
            payload.pop("log")
            payload.pop("updated")
            next(s for s in payload["stages"] if s["id"] == "screen").pop("detail")
        self.assertEqual(after, before)                              # no model, result or other stage is touched

    def test_a_second_run_keeps_the_first_listing_of_both_lists(self):
        prog = {"screen": {"candidates": [], "hurricane": {
            "candidates": [{"id": "mp-1", "formula": "LaCuO3", "listed": {"date": "2026-11-12", "round": 7, "file": "screen_round7.json"}}],
            "candidates_computed": [{"id": "agm1", "formula": "YBaFe", "listed": {"date": "2026-11-12", "round": 7, "file": "screen_round7.json"}}]}}}
        with tempfile.TemporaryDirectory() as tmp:
            by_id, by_comp = S.first_listings(Path(tmp), prog)
        self.assertEqual(set(by_id), {"mp-1", "agm1"})
        self.assertEqual(len(by_comp), 2)
        self.assertEqual(len(prog["screen"]["hurricane"]["candidates"]), 1)        # the published block is not changed

    def test_the_log_carries_the_block_and_its_hash(self):
        start = self.lines.index("=== hurricane9-screen7 begin")
        self.assertTrue(self.lines[-1].startswith("=== hurricane9-screen7 end sha256 "))
        self.assertTrue(all(line.startswith(f"h9w|{i:03d}|") for i, line in enumerate(self.lines[start + 1:-1])))
        text = "".join(line.split("|", 2)[2] for line in self.lines[start + 1:-1])
        shown = json.loads(text)
        self.assertEqual(shown["block"], self.block)
        import hashlib
        self.assertIn(hashlib.sha256(text.encode("utf-8")).hexdigest(), self.lines[-1])
        result = json.loads((Path(self.tmp.name) / "screen_round7.json").read_text(encoding="utf-8"))
        self.assertEqual((result["round"], result["candidates"], result["hurricane"]), (7, [], self.block))

    # ------------------------------------------------------------ the pool's rules
    def test_size_gap_and_element_rules(self):
        ok = rec(S.MP, "mp-1", {"La": 2, "Cu": 1, "O": 4})
        self.assertTrue(S.size_ok(ok) and S.gap_ok(ok) and S.covered(ok, self.counts))
        self.assertFalse(S.size_ok(rec(S.MP, "a", {"La": 1})))                                       # one element
        self.assertFalse(S.size_ok(rec(S.MP, "b", {e: 1 for e in ("La", "Sr", "Cu", "O", "Ba", "Y", "Fe")})))   # seven
        self.assertTrue(S.size_ok(rec(S.MP, "c", {e: 1 for e in ("La", "Sr", "Cu", "O", "Ba", "Y")})))
        self.assertFalse(S.size_ok(rec(S.MP, "d", {"La": 1, "H": 3})))
        self.assertFalse(S.size_ok(rec(S.MP, "e", {"La": 1, "Xe": 1})))
        self.assertFalse(S.size_ok(rec(S.MP, "f", {"La": 1, "Tc": 1})))
        self.assertTrue(S.size_ok(rec(S.MP, "g", {"La": 50, "Cu": 50})))
        self.assertFalse(S.size_ok(rec(S.MP, "h", {"La": 51, "Cu": 50})))
        self.assertFalse(S.gap_ok(rec(S.MP, "i", {"La": 1, "O": 1}, gap=1.01)))
        self.assertFalse(S.gap_ok(rec(S.MP, "j", {"La": 1, "O": 1}, gap=None)))
        self.assertFalse(S.covered(rec(S.MP, "k", {"La": 1, "Zr": 1}), self.counts))

    def test_tracks_an_experimental_structure_lifts_the_hull_rule_and_nothing_else(self):
        calc = [rec(S.MP, "mp-exp", {"La": 2, "Cu": 1, "O": 4}, hull=0.30, experimental=True),      # synthesized: kept at any distance
                rec(S.MP, "mp-far", {"Y": 1, "Ba": 2, "Cu": 3}, hull=0.30),                          # calculation only and far: out
                rec(S.ALEX, "agm-near", {"Sr": 1, "Fe": 2, "As": 2}, hull=0.049),                    # calculation only and near: in
                rec(S.ALEX, "agm-none", {"Ca": 1, "Fe": 2, "As": 2}, hull=None),                     # no distance: out
                rec(S.MP, "mp-wide", {"La": 2, "O": 3}, gap=4.0, experimental=True),                 # synthesized, but an insulator: out
                rec(S.JARVIS, "JVASP-9", {"Nb": 1, "Se": 2}, hull=0.2, jarvis_tc=None),              # far by itself, but the COD has it
                rec(S.JARVIS, "JVASP-8", {"Nb": 3, "Se": 4}, hull=0.0, jarvis_tc=7.0)]              # a computed Tc: left out as round 6 did
        cod = [rec(S.COD, 1, {"Nb": 1, "Se": 2.02}, gap=None, hull=None, experimental=True)]         # NbSe2 within 2 at.%
        pool, info = S.assemble(calc, cod, self.counts, [], None)
        got = {S.tag(r): r for r in pool}
        self.assertEqual(set(got), {"Materials Project mp-exp", "Alexandria agm-near", "JARVIS-DFT JVASP-9", "COD 1"})
        self.assertEqual({k: r["track"] for k, r in got.items()}, {"Materials Project mp-exp": "experimental", "Alexandria agm-near": "computed",
                                                                  "JARVIS-DFT JVASP-9": "experimental", "COD 1": "experimental"})
        self.assertEqual((got["JARVIS-DFT JVASP-9"]["evidence"], got["JARVIS-DFT JVASP-9"]["same_space_group"]), ("COD 1", True))
        self.assertEqual((got["COD 1"]["gap_from"], got["COD 1"]["gap"]), ("JARVIS-DFT JVASP-9", 0.0))    # the measured composition takes the calculated gap
        self.assertEqual(got["COD 1"]["labels"], [])
        self.assertIsNone(got["Materials Project mp-exp"]["same_space_group"])      # it is the experimental structure itself
        self.assertEqual(info["excluded"], {"computed": 1, "total": 1})
        self.assertEqual(info["tracks"], {"experimental": 3, "computed": 1})

    def test_a_cod_entry_without_a_calculated_gap_stays_marked_and_one_with_a_wide_gap_goes(self):
        calc = [rec(S.MP, "mp-ins", {"La": 2, "O": 3}, gap=4.0, experimental=True)]
        cod = [rec(S.COD, 10, {"La": 2, "O": 3.01}, gap=None, hull=None, experimental=True),         # the insulator, measured
               rec(S.COD, 11, {"La": 1.85, "Sr": 0.15, "Cu": 1, "O": 4}, gap=None, hull=None, experimental=True)]   # nothing calculated
        pool, info = S.assemble(calc, cod, self.counts, [], None)
        self.assertEqual([S.tag(r) for r in pool], ["COD 11"])
        self.assertEqual((pool[0]["labels"], pool[0]["track"], pool[0]["chemsys"]), ([S.NO_GAP], "experimental", "Cu-La-O-Sr"))
        self.assertEqual(info["no_calculated_gap"], 1)

    def test_known_superconductors_their_chemical_systems_and_the_datasheet_are_left_out(self):
        known, system, sheet = SC.Known("supercon"), SC.Known("system"), SC.Known("datasheet")
        known.add({"La": 1.85, "Sr": 0.15, "Cu": 1, "O": 4}, "3DSC")
        system.add_system(["Ba", "Cu", "O", "Y"], "3DSC")
        sheet.add({"Sr": 1, "Fe": 2, "As": 2}, "datasheet")
        calc = [rec(S.MP, "mp-1", {"La": 1.84, "Sr": 0.16, "Cu": 1, "O": 4}, experimental=True),     # the known compound within 2 at.%
                rec(S.MP, "mp-2", {"Y": 1, "Ba": 1, "Cu": 1, "O": 3}, experimental=True),             # another compound of a known system
                rec(S.MP, "mp-3", {"Sr": 1, "Fe": 2, "As": 2}, experimental=True),                    # the datasheet lists it
                rec(S.MP, "mp-4", {"Ca": 1, "Fe": 2, "As": 2}, experimental=True)]
        pool, info = S.assemble(calc, [], self.counts, [known, system], sheet)
        self.assertEqual([r["id"] for r in pool], ["mp-4"])
        self.assertEqual(info["excluded"], {"supercon": 1, "system": 1, "datasheet": 1, "total": 3})

    def test_the_reference_calculation_speaks_for_its_composition(self):
        comp = {"Ca": 1, "Fe": 2, "As": 2}
        # a made compound whose experimental entry is an insulator stays out, whatever a hypothetical structure of it says
        calc = [rec(S.MP, "mp-real", comp, gap=3.0, hull=0.0, experimental=True), rec(S.JARVIS, "JVASP-hyp", comp, hull=0.0, jarvis_tc=None)]
        cod = [rec(S.COD, 5, comp, gap=None, hull=None, experimental=True)]
        pool, info = S.assemble(calc, cod, self.counts, [], None)
        self.assertEqual(pool, [])
        self.assertEqual(info["steps"]["Materials Project"]["reference calculations, one per composition"], 1)
        self.assertNotIn("band gap at most 1 eV", info["steps"]["Materials Project"])
        self.assertNotIn("band gap of the reference calculation at most 1 eV, or no calculation", info["steps"]["COD"])
        # no entry marked experimental: one near its hull before one further away, then the order of the sources, then the hull
        calc = [rec(S.ALEX, "agm-1", comp, hull=0.0), rec(S.MP, "mp-b", comp, hull=0.04, gap=2.0), rec(S.MP, "mp-a", comp, hull=0.01),
                rec(S.JARVIS, "JVASP-2", comp, hull=0.03, jarvis_tc=None), rec(S.JARVIS, "JVASP-1", comp, hull=0.2, gap=3.0, jarvis_tc=None)]
        pool, info = S.assemble(calc, [], self.counts, [], None)
        self.assertEqual([(r["db"], r["id"], r["track"], r["evidence"]) for r in pool], [("JARVIS-DFT", "JVASP-2", "computed", None)])
        self.assertEqual(info["steps"]["JARVIS-DFT"]["one per composition"], 1)
        self.assertEqual(info["steps"]["Materials Project"]["entries"], 2)
        # the JARVIS entries are far from their hull, the Materials Project has one near its own: that one speaks, and it is an insulator
        calc[3] = rec(S.JARVIS, "JVASP-2", comp, hull=0.3, jarvis_tc=None)
        calc[2] = rec(S.MP, "mp-a", comp, hull=0.01, gap=2.5)
        self.assertEqual(S.assemble(calc, [], self.counts, [], None)[0], [])
        # the same with a narrow gap: the Materials Project entry stands for the compound
        calc[2] = rec(S.MP, "mp-a", comp, hull=0.01)
        pool, _ = S.assemble(calc, [], self.counts, [], None)
        self.assertEqual([(r["db"], r["id"], r["track"]) for r in pool], [("Materials Project", "mp-a", "computed")])
        # an entry marked experimental speaks before a calculated one of an earlier source; the COD entry of that composition is named with it
        calc = [rec(S.JARVIS, "JVASP-3", comp, hull=0.0, jarvis_tc=None), rec(S.MP, "mp-c", comp, hull=0.3, experimental=True)]
        cod = [rec(S.COD, 5, comp, gap=None, hull=None, experimental=True)]
        pool, _ = S.assemble(calc, cod, self.counts, [], None)
        self.assertEqual([(r["db"], r["id"], r["track"], r["evidence"]) for r in pool], [("Materials Project", "mp-c", "experimental", "Materials Project mp-c")])
        self.assertEqual(pool[0]["also"], ["COD 5"])
        # a composition is left out if JARVIS-DFT gives any entry of it a computed Tc, whichever entry speaks for it
        calc = [rec(S.JARVIS, "JVASP-4", comp, hull=0.2, jarvis_tc=3.0), rec(S.MP, "mp-d", comp, hull=0.0)]
        pool, info = S.assemble(calc, [], self.counts, [], None)
        self.assertEqual((pool, info["excluded"]), ([], {"computed": 1, "total": 1}))

    def test_the_experimental_structure_named_has_the_reference_s_space_group_if_one_has(self):
        comp = {"Nb": 1, "Se": 2}
        calc = [rec(S.JARVIS, "JVASP-9", comp, hull=0.0, jarvis_tc=None)]                     # space group 123
        other = S.record(S.COD, 7, comp, 3, None, None, None, True, [[4, 0, 0], [0, 4, 0], [0, 0, 4]], 194, "P63/mmc")
        same = S.record(S.COD, 8, comp, 3, None, None, None, True, [[4, 0, 0], [0, 4, 0], [0, 0, 4]], 123, "P4/mmm")
        pool, info = S.assemble(calc, [other], self.counts, [], None)
        self.assertEqual((pool[0]["evidence"], pool[0]["same_space_group"], info["experimental_structure_in_another_space_group"]), ("COD 7", False, 1))
        pool, info = S.assemble(calc, [other, same], self.counts, [], None)
        self.assertEqual((pool[0]["evidence"], pool[0]["same_space_group"], info["experimental_structure_in_another_space_group"]), ("COD 8", True, 0))
        self.assertEqual(pool[0]["also"], ["COD 7", "COD 8"])
        self.assertIsNone(pool[0]["evidence_comp"])
        # a structure of exactly this composition is named before one within 2 at.% that has the reference's space group
        near = S.record(S.COD, 6, {"Nb": 1, "Se": 2.02}, 3.02, None, None, None, True, [[4, 0, 0], [0, 4, 0], [0, 0, 4]], 123, "P4/mmm")
        pool, info = S.assemble(calc, [near, other], self.counts, [], None)
        mine = next(r for r in pool if r["id"] == "JVASP-9")
        self.assertEqual((mine["evidence"], mine["same_space_group"], mine["evidence_comp"]), ("COD 7", False, None))
        pool, info = S.assemble(calc, [near], self.counts, [], None)
        mine = next(r for r in pool if r["id"] == "JVASP-9")
        self.assertEqual((mine["evidence"], mine["same_space_group"], mine["evidence_comp"]), ("COD 6", True, {"Nb": 1.0, "Se": 2.02}))
        self.assertEqual(info["experimental_structure_of_another_composition_within_2_at_percent"], 1)

    def test_a_mark_far_above_the_hull_is_not_taken(self):
        comp = {"Ca": 1, "Fe": 2, "As": 2}
        calc = [rec(S.MP, "mp-odd", comp, hull=2.5, experimental=True)]             # marked experimental, 2.5 eV/atom above the hull
        pool, info = S.assemble(calc, [], self.counts, [], None)
        self.assertEqual(pool, [])
        self.assertEqual(info["steps"]["Materials Project"]["marked experimental, but more than 0.5 eV/atom above the hull: the mark is not taken"], 1)
        self.assertTrue(calc[0]["experimental"])                                    # the records handed in are not changed
        calc = [rec(S.MP, "mp-odd", comp, hull=0.5, experimental=True)]             # at the limit the mark stands
        self.assertEqual([r["track"] for r in S.assemble(calc, [], self.counts, [], None)[0]], ["experimental"])
        # the doubtful entry no longer speaks before a calculated entry near its hull, and a COD entry still makes the compound experimental
        calc = [rec(S.MP, "mp-odd", comp, hull=2.5, gap=3.0, experimental=True), rec(S.ALEX, "agm-1", comp, hull=0.0)]
        pool, _ = S.assemble(calc, [], self.counts, [], None)
        self.assertEqual([(r["id"], r["track"]) for r in pool], [("agm-1", "computed")])
        pool, _ = S.assemble(calc, [rec(S.COD, 5, comp, gap=None, hull=None, experimental=True)], self.counts, [], None)
        self.assertEqual([(r["id"], r["track"], r["evidence"]) for r in pool], [("agm-1", "experimental", "COD 5")])

    def test_a_published_candidate_says_whose_gap_it_shows_and_how_its_experimental_structure_compares(self):
        comp = {"Nb": 1, "Se": 2}
        calc = [rec(S.JARVIS, "JVASP-9", comp, gap=0.3, hull=0.2, jarvis_tc=None, elements=["Nb", "Se", "Se"], frac=[[0, 0, 0], [0.5, 0.5, 0.25], [0.5, 0.5, 0.75]])]
        cod = [S.record(S.COD, 7, {"Nb": 1, "Se": 2.02}, 3.02, None, None, None, True, [[4, 0, 0], [0, 4, 0], [0, 0, 4]], 194, "P63/mmc", published="Nb Se2.02", year=1990)]
        pool, _ = S.assemble(calc, cod, self.counts, [], None)
        rows = [{"track": r["track"], "not_known": False, "chemsys": r["chemsys"], "formula": plain(r["comp"]), "hurricane_tc": 5.0 - i, "tc_sc": 10.0, "lo": 5.0,
                 "hi": 20.0, "p_sc": 0.5, "p_unconventional": 0.9, "family": "other", "types": "", "novelty": 0.5, "nearest_training": "NbSe2",
                 "nearest_training_tc": 7.0, "_record": r} for i, r in enumerate(pool)]
        rows[1]["chemsys"] = "another"                     # so that both are listed
        now = {"date": "2026-11-12", "at": "2026-11-12T00:00:00+00:00", "round": 7, "file": "screen_round7.json"}
        got = S.candidates(rows, "experimental", ({}, {}), now, (SC.Known("checks"), {}), {})
        calc_c, cod_c = got
        self.assertEqual((calc_c["id"], calc_c["experimental"]), ("JVASP-9", {"source": "COD", "id": "7", "url": "https://www.crystallography.net/cod/7.html",
                                                                              "same_space_group": False, "formula": "Nb1Se2.02"}))
        self.assertEqual((calc_c["icsd"], calc_c["gap"], calc_c["ehull"]), (False, 0.3, 0.2))
        self.assertNotIn("gap_from", calc_c)
        self.assertEqual(sorted(calc_c["atoms"]), ["elements", "frac", "lattice"])
        self.assertEqual((cod_c["id"], cod_c["gap"], cod_c["gap_from"]), ("7", 0.3, {"source": "JARVIS-DFT", "id": "JVASP-9",
                                                                                   "url": "https://www.ctcms.nist.gov/~knc6/jsmol/JVASP-9.html"}))
        self.assertEqual(cod_c["experimental"], {"source": "COD", "id": "7", "url": "https://www.crystallography.net/cod/7.html"})
        self.assertEqual((cod_c["published"], cod_c["year"], cod_c["spg"]), ("Nb Se2.02", 1990, "P63/mmc (194)"))
        self.assertNotIn("atoms", cod_c)
        self.assertNotIn("labels", cod_c)
        self.assertNotIn("ehull", cod_c)

    def test_materials_are_matched_within_two_atomic_percent(self):
        m = S.Materials()
        m.add({"Nb": 1, "Se": 2}, "a")
        m.add({"Nb": 1, "Se": 2.02}, "b")
        m.add({"Nb": 1, "Se": 3}, "c")
        m.add({"Nb": 1, "S": 2}, "d")
        self.assertEqual(m.near({"Nb": 2, "Se": 4}), ["a", "b"])
        self.assertEqual(m.near({"Nb": 1, "Se": 2.1}), ["a", "b"])              # 1.1 at.% from NbSe2
        self.assertEqual(m.near({"Nb": 1, "Se": 2.2}), ["b"])                   # 2.1 at.% from NbSe2, 1.9 from NbSe2.02
        self.assertEqual(m.near({"Nb": 1, "Se": 2.5}), [])
        self.assertEqual(m.near({"Nb": 1, "Te": 2}), [])
        m.add({"Nb": 1.02, "Se": 2}, "e")                                        # added after a search
        self.assertEqual(m.near({"Nb": 1, "Se": 2}), ["a", "b", "e"])

    def test_a_correction_of_the_literature_audit_follows_its_check_to_another_source(self):
        records = {"JVASP-1": {"composition": {"Ce": 4, "Ga": 24, "Cu": 2},
                               "check_correction": {"replaces_doi": "10.1/old", "check": {"kind": "experiment", "superconducts": None, "note": "unknown"}}}}
        check = {"kind": "experiment", "superconducts": False, "doi": "10.1/old"}
        mine = rec(S.MP, "mp-9", {"Ce": 2, "Ga": 12, "Cu": 1})
        self.assertEqual(S.corrected_check(mine, check, records), records["JVASP-1"]["check_correction"]["check"])
        self.assertIs(S.corrected_check(rec(S.MP, "mp-8", {"Ce": 2, "Ga": 12, "Ni": 1}), check, records), check)
        self.assertIs(S.corrected_check(mine, dict(check, doi="10.1/other"), records).get("superconducts"), False)
        self.assertIsNone(S.corrected_check(mine, None, records))
        self.assertEqual(S.corrected_check(rec(S.JARVIS, "JVASP-1", {"Ce": 2, "Ga": 12, "Cu": 1}), check, records)["note"], "unknown")
        records["JVASP-2"] = {"formula": "Ce2Ga12Ni", "check_correction": {"replaces_doi": "10.1/old", "check": {"kind": "experiment", "note": "from the formula"}}}
        self.assertEqual(S.corrected_check(rec(S.MP, "mp-8", {"Ce": 2, "Ga": 12, "Ni": 1}), check, records)["note"], "from the formula")
        records["JVASP-3"] = {"formula": "not a formula", "check_correction": {"replaces_doi": "10.1/old", "check": {"kind": "experiment"}}}
        self.assertIs(S.corrected_check(rec(S.MP, "mp-7", {"Ce": 2, "Ga": 12, "Co": 1}), check, records), check)

    # ------------------------------------------------------------ the sources
    def test_the_hull_of_formation_energies(self):
        entries = [({"A": 1, "B": 1}, -1.0), ({"A": 2, "B": 2}, -0.4), ({"A": 1, "B": 2}, -0.2), ({"A": 1}, 0.0), ({"B": 1}, -0.0), ({"A": 3, "B": 1}, 0.3)]
        hull = S.hull_energies(entries, [{"A": 1, "B": 1}, {"A": 3, "B": 1}, {"A": 1, "B": 2}, {"A": 1, "C": 1}])
        self.assertAlmostEqual(hull[0], -1.0)                    # the lower of the two AB entries
        self.assertAlmostEqual(hull[1], -0.5)                    # half AB, half A
        self.assertAlmostEqual(hull[2], -2 / 3)                  # two thirds AB, one third B: AB2 lies 0.47 above
        self.assertEqual(hull[3], 0.0)                           # nothing but the elements

    def test_jarvis_rows_get_the_hull_of_their_own_formation_energies_and_must_be_the_rows_named(self):
        import pandas as pd

        def row(ident, elements, e_form, gap=0.0, icsd=False):
            atoms = {"lattice_mat": [[4, 0, 0], [0, 4, 0], [0, 0, 4]], "elements": elements, "coords": [[0, 0, i / len(elements)] for i in range(len(elements))]}
            return {"id": ident, "atoms": atoms, "gap": gap, "ehull": 9.9, "magmom": 0.0, "spg": "P4/mmm", "spg_number": 123.0, "icsd": icsd,
                    "jarvis_tc": float("nan"), "e_form": e_form, "comp": SC.counts_of(elements), "nat": len(elements)}
        rows = pd.DataFrame([row("J-1", ["La", "Cu"], -1.0, icsd=True), row("J-2", ["La", "La", "Cu", "Cu"], -0.4), row("J-3", ["La", "Cu", "Cu"], -0.2, gap=3.0),
                             row("J-4", ["La", "La", "La", "Cu"], 0.3), row("J-5", ["La", "Zr"], -0.5), row("J-6", ["La", "O"], float("nan"))])
        with patch.object(S, "JARVIS_ROWS_SHA256", None):
            recs, info = S.jarvis_records(rows, self.counts)
        got = {r["id"]: r for r in recs}
        self.assertEqual([round(got[k]["hull"], 4) for k in ("J-1", "J-2", "J-3", "J-4")], [0.0, 0.6, 0.4667, 0.8])     # the file's ehull field (9.9) is not read
        self.assertAlmostEqual(got["J-5"]["hull"], 0.0)
        self.assertIsNone(got["J-6"]["hull"])                                    # no formation energy, no distance
        self.assertEqual((info["rows"], info["hull_distance_computed_for"], info["of_them_within_50_meV"]), (6, 5, 2))
        self.assertTrue(got["J-1"]["experimental"] and got["J-1"]["elements"] == ("La", "Cu"))
        self.assertIsNone(got["J-3"]["lattice"])                                 # a wide gap: it cannot enter, and keeps no cell
        self.assertIsNone(got["J-5"]["lattice"])                                 # an element the training data do not cover
        with patch.object(S, "JARVIS_ROWS_SHA256", info["rows_sha256"]):
            self.assertEqual(S.jarvis_records(rows, self.counts)[1]["rows_sha256"], info["rows_sha256"])
        changed = rows.copy()
        changed.loc[1, "e_form"] = -0.41
        with patch.object(S, "JARVIS_ROWS_SHA256", info["rows_sha256"]):
            with self.assertRaisesRegex(SystemExit, "is not what this protocol names"):
                S.jarvis_records(changed, self.counts)

    def test_a_source_file_other_than_the_one_named_stops_the_run(self):
        S.same_source("a file", "abc", None)
        S.same_source("a file", "abc", "abc")
        with self.assertRaisesRegex(SystemExit, "a file is not what this protocol names"):
            S.same_source("a file", "abd", "abc")
        self.assertEqual({len(v["sha256"]) for k, v in S.PROTOCOL["sources"].items() if k != "COD" and v["sha256"]} - {64}, set())

    def test_a_materials_project_document_is_used_only_if_marked_by_c_current_and_ordered(self):
        site = lambda el, occ=1.0, abc=(0, 0, 0): {"species": [{"element": el, "occu": occ}], "abc": list(abc)}   # noqa: E731
        doc = {"material_id": "mp-1", "builder_meta": {"license": "BY-C"}, "deprecated": False, "theoretical": False, "band_gap": 0.2,
               "energy_above_hull": 0.01, "total_magnetization": 1.5, "symmetry": {"number": 139, "symbol": "I4/mmm"},
               "structure": {"lattice": {"matrix": [[3, 0, 0], [0, 3, 0], [0, 0, 6]]}, "sites": [site("La"), site("Cu", abc=(0.5, 0.5, 0.5)), site("O2-", abc=(0.5, 0, 1.2))]}}
        r = S.mp_record(doc)
        self.assertEqual((r["db"], r["id"], r["comp"], r["nat"], r["experimental"], r["gap"], r["hull"]), ("Materials Project", "mp-1", {"La": 1.0, "Cu": 1.0, "O": 1.0}, 3.0, True, 0.2, 0.01))
        self.assertEqual((r["spg_number"], r["spg"], r["elements"]), (139, "I4/mmm", ("La", "Cu", "O")))
        np.testing.assert_allclose(r["frac"][2], [0.5, 0.0, 0.2], atol=1e-6)
        self.assertEqual(S.slim(dict(r))["lattice"], None)
        self.assertIsNone(S.mp_record(dict(doc, builder_meta={"license": "BY-NC"})))                 # from GNoME: not read
        self.assertIsNone(S.mp_record(dict(doc, builder_meta={})))
        self.assertIsNone(S.mp_record(dict(doc, deprecated=True)))
        self.assertFalse(S.mp_record(dict(doc, theoretical=True))["experimental"])
        shared = copy.deepcopy(doc)
        shared["structure"]["sites"][0]["species"] = [{"element": "La", "occu": 0.5}, {"element": "Sr", "occu": 0.5}]
        self.assertIsNone(S.mp_record(shared))

    def test_an_alexandria_entry_takes_the_phase_separation_energy_where_the_hull_distance_is_empty(self):
        site = lambda el, abc=(0, 0, 0): {"species": [{"element": el, "occu": 1}], "abc": list(abc)}   # noqa: E731
        entry = {"structure": {"lattice": {"matrix": [[3, 0, 0], [0, 3, 0], [0, 0, 3]]}, "sites": [site("Mg"), site("B", (0.3, 0.3, 0.5)), site("B", (0.6, 0.6, 0.5))]},
                 "data": {"mat_id": "agm1", "band_gap_ind": 0.0, "e_above_hull": None, "e_phase_separation": -0.03, "total_mag": 0.0, "spg": 191}}
        with patch.object(S, "spg_symbol", lambda n: "P6/mmm"):
            r = S.alexandria_record(entry)
            self.assertEqual((r["id"], r["comp"], r["hull"], r["experimental"], r["spg"]), ("agm1", {"Mg": 1.0, "B": 2.0}, 0.0, False, "P6/mmm"))
            entry["data"]["e_phase_separation"] = 0.08
            self.assertEqual(S.alexandria_record(entry)["hull"], 0.08)
            entry["data"]["e_above_hull"] = 0.02
            self.assertEqual(S.alexandria_record(entry)["hull"], 0.02)

    def test_a_cod_row_gives_the_measured_composition_and_the_primitive_cell(self):
        row = {"file": 1001764, "a": 3.88, "b": 3.88, "c": 9.5, "alpha": 90, "beta": 90, "gamma": 90, "vol": 143.0, "nel": "4", "sg": "P 4/m m m",
               "sgNumber": 123, "formula": "- Ba2 Cu1.16 Hg0.84 O4.19 -", "calcformula": "- Ba2 Cu1.16 Hg0.84 O4.19 -", "cellformula": "- Ba2 Cu1.16 Hg0.84 O4.19 -",
               "Z": 1, "cellpressure": None, "diffrpressure": None, "year": 1997, "doi": "10.1/x", "method": None, "flags": "has coordinates",
               "status": None, "duplicateof": None, "onhold": None}
        r = S.cod_record(row)
        self.assertEqual((r["db"], r["id"], r["comp"], r["experimental"], r["gap"], r["spg"], r["spg_number"]),
                         ("COD", "1001764", {"Ba": 2.0, "Cu": 1.16, "Hg": 0.84, "O": 4.19}, True, None, "P4/mmm", 123))
        self.assertAlmostEqual(r["nat"], 8.19)
        self.assertEqual((r["published"], r["year"], r["doi"]), ("Ba2 Cu1.16 Hg0.84 O4.19", 1997, "10.1/x"))
        body = dict(row, sg="I 4/m m m", sgNumber=139, cellformula="- La4 Cu2 O8 -", calcformula="- La2 Cu O4 -")
        r = S.cod_record(body)
        self.assertAlmostEqual(r["nat"], 7.0)                                                    # half the conventional cell
        self.assertAlmostEqual(abs(np.linalg.det(np.asarray(r["lattice"]))), 3.88 * 3.88 * 9.5 / 2)
        self.assertAlmostEqual(S.structure_of(r)["vpa"], 3.88 * 3.88 * 9.5 / 14)
        reasons = __import__("collections").Counter()
        for change, reason in (({"method": "theoretical"}, "marked theoretical"), ({"status": "retracted"}, "retracted, with errors or warnings, or on hold"),
                               ({"duplicateof": 1000001}, "marked as a duplicate"), ({"flags": "has Fobs"}, "no coordinates"),
                               ({"calcformula": "- C12 H22 O11 -"}, "hydrogen"), ({"calcformula": None}, "no readable composition"),
                               ({"cellpressure": 5.0e6}, "determined above 0.1 GPa"), ({"sgNumber": None}, "no cell or space-group number")):
            self.assertIsNone(S.cod_record(dict(row, **change), reasons))
            self.assertEqual(reasons[reason], 1, reason)

    def test_cod_formulas_and_centred_cells(self):
        self.assertEqual(S.cod_formula("- Ba2 Cu3 O6.5 Y -"), {"Ba": 2.0, "Cu": 3.0, "O": 6.5, "Y": 1.0})
        self.assertIsNone(S.cod_formula("- Ba2 (Cu3) -"))
        self.assertIsNone(S.cod_formula(""))
        cubic = S.cell_matrix(4, 4, 4, 90, 90, 90)
        for symbol, mult in (("P m -3 m", 1), ("I m -3 m", 2), ("F m -3 m", 4), ("C m c m", 2), ("A m m 2", 2)):
            lat, m = S.primitive(cubic, symbol, [90, 90, 90])
            self.assertEqual(m, mult)
            self.assertAlmostEqual(abs(np.linalg.det(lat)), 64 / mult)
        hexagonal = S.cell_matrix(5, 5, 14, 90, 90, 120)
        lat, m = S.primitive(hexagonal, "R -3 m :H", [90, 90, 120])
        self.assertEqual(m, 3)
        self.assertAlmostEqual(abs(np.linalg.det(lat)), abs(np.linalg.det(hexagonal)) / 3)
        self.assertEqual(S.primitive(S.cell_matrix(5, 5, 5, 60, 60, 60), "R -3 m :R", [60, 60, 60])[1], 1)
        self.assertEqual(S.primitive(S.cell_matrix(5, 5, 5, 60, 60, 60), "R -3 m", [60, 60, 60])[1], 1)
        tri = S.cell_matrix(3, 4, 5, 80, 95, 100)
        self.assertAlmostEqual(np.linalg.norm(tri[2]), 5.0)
        self.assertAlmostEqual(math.degrees(math.acos(tri[1] @ tri[2] / 20)), 80.0)

    def test_the_structure_description_is_radars_own_for_a_whole_number_of_atoms(self):
        atoms = {"lattice_mat": [[3.9, 0, 0], [0, 3.9, 0], [1.95, 1.95, 6.6]], "elements": ["La", "La", "Cu", "O", "O", "O", "O"]}
        mine = S.structure_of(S.record(S.JARVIS, "J", {"La": 2, "Cu": 1, "O": 4}, 7, 0.0, 0.0, 0.0, False, atoms["lattice_mat"], 139, "I4/mmm"))
        self.assertEqual(mine, SC.radar_structure(atoms, 139.0, "I4/mmm"))

    def test_the_cod_is_read_once_and_every_run_screens_the_stored_rows(self):
        row = {k: None for k in S.COD_COLUMNS}
        row.update(file=1001764, a=3.88, b=3.88, c=9.5, alpha=90.0, beta=90.0, gamma=90.0, nel="4", sg="P 4/m m m", sgNumber=123,
                   calcformula="- Ba2 Cu1.16 Hg0.84 O4.19 -", cellformula="- Ba2 Cu1.16 Hg0.84 O4.19 -", Z=1, flags="has coordinates", year=1997)
        other = dict(row, file=1001765, method="theoretical")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(S, "query_cod", return_value=[row, other]):
                note = S.cod_snapshot(Path(tmp))
            self.assertEqual((note["rows_read"], note["rows_stored"], note["left_out"]), (2, 1, {"marked theoretical": 1}))
            first = (Path(tmp) / S.COD_SNAPSHOT).read_bytes()
            self.assertEqual(note["sha256"], __import__("hashlib").sha256(first).hexdigest())
            with patch.object(S, "query_cod", return_value=[row, other]):
                S.cod_snapshot(Path(tmp))
            self.assertEqual((Path(tmp) / S.COD_SNAPSHOT).read_bytes(), first)              # the same rows, the same file
            with patch.object(S, "query_cod", side_effect=AssertionError("the database was read")):
                recs, info = S.read_cod(Path(tmp))
            self.assertEqual(([(r["id"], r["comp"], r["year"]) for r in recs], info["rows_stored"], info["used"], info["left_out"]),
                             ([("1001764", {"Ba": 2.0, "Cu": 1.16, "Hg": 0.84, "O": 4.19}, 1997)], 1, 1, {"marked theoretical": 1}))
            direct = S.cod_record(row)                                                      # the stored text gives the record the database gave
            self.assertEqual((recs[0]["nat"], recs[0]["spg"], recs[0]["spg_number"]), (direct["nat"], direct["spg"], direct["spg_number"]))
            np.testing.assert_array_equal(recs[0]["lattice"], direct["lattice"])
            with gzip.open(Path(tmp) / S.COD_SNAPSHOT, "ab") as fh:
                fh.write(b"tampered\n")
            with self.assertRaisesRegex(SystemExit, "not the file its note describes"):
                S.read_cod(Path(tmp))

    def test_the_pool_file_has_no_time_stamp(self):
        pool = [dict(rec(S.MP, "mp-1", {"La": 2, "Cu": 1, "O": 4}, gap=0.25, hull=0.0123), track="experimental", evidence="COD 7", gap_from=None, labels=[],
                     chemsys="Cu-La-O", p_unconventional=0.7),
                dict(rec(S.COD, 7, {"La": 2, "Cu": 1, "O": 4.02}, gap=None, hull=None), track="experimental", evidence="COD 7", gap_from=None, labels=[S.NO_GAP],
                     chemsys="Cu-La-O", p_unconventional=0.2)]
        rows = [{"source": "Materials Project", "id": "mp-1", "not_known": True}]
        with tempfile.TemporaryDirectory() as tmp:
            a = S.write_pool(Path(tmp) / "a.csv.gz", pool, rows)
            b = S.write_pool(Path(tmp) / "b.csv.gz", pool, rows)
            self.assertEqual(a, b)
            with gzip.open(Path(tmp) / "a.csv.gz", "rt", encoding="utf-8", newline="") as fh:
                got = list(csv.DictReader(fh))
        self.assertEqual([(r["id"], r["source"], r["sent"], r["not_known"], r["labels"], r["gap"], r["ehull"]) for r in got],
                         [("mp-1", "Materials Project", "True", "True", "", "0.25", "0.0123"), ("7", "COD", "False", "", S.NO_GAP, "", "")])


if __name__ == "__main__":
    unittest.main()
