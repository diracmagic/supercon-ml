"""The correction to the screening pools (the published candidates against the computed hull), on invented rows: no JARVIS file."""
import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import screen_hull as H

ROOT = Path(__file__).resolve().parents[1]


def row(key, comp, e_form, field=0.0, icsd=False):
    return {"id": key, "comp": {e: float(v) for e, v in comp.items()}, "e_form": e_form, "gap": 0.0, "nat": float(sum(comp.values())), "icsd": icsd,
            "field": field}


class HullTests(unittest.TestCase):
    def test_a_binary_system(self):
        rows = [row("AB", {"A": 1, "B": 1}, -1.0), row("A3B", {"A": 3, "B": 1}, -0.4), row("AB3", {"A": 1, "B": 3}, -0.6),
                row("A2B", {"A": 2, "B": 1}, 0.2), row("A", {"A": 1}, 0.0), row("A-high", {"A": 2}, 0.3)]
        d = H.distances(rows)
        self.assertAlmostEqual(d["AB"], 0.0, places=9)
        self.assertAlmostEqual(d["A3B"], 0.1, places=9)             # half AB and half A, by atoms: -0.5
        self.assertAlmostEqual(d["AB3"], 0.0, places=9)             # below the line from AB to B (-0.5): on the hull
        self.assertAlmostEqual(d["A2B"], 0.2 + 2 / 3, places=9)     # above the elements: measured from the hull below it
        self.assertAlmostEqual(d["A"], 0.0, places=9)
        self.assertAlmostEqual(d["A-high"], 0.3, places=9)          # an element's other form, above the element at zero

    def test_a_ternary_compound_is_measured_against_its_subsystems(self):
        rows = [row("ABC", {"A": 1, "B": 1, "C": 1}, -0.5), row("AB", {"A": 2, "B": 2}, -1.0), row("XY", {"X": 1, "Y": 1}, -3.0)]
        d = H.distances(rows)
        self.assertAlmostEqual(d["ABC"], 2 / 3 - 0.5, places=9)     # two thirds AB and one third C, by atoms
        self.assertAlmostEqual(d["AB"], 0.0, places=9)
        self.assertAlmostEqual(d["XY"], 0.0, places=9)              # another chemical system does not enter

    def test_a_composition_counts_once_at_its_lowest_energy(self):
        d = H.distances([row("low", {"A": 1, "B": 1}, -1.0), row("high", {"A": 4, "B": 4}, -0.8)])
        self.assertAlmostEqual(d["low"], 0.0, places=9)
        self.assertAlmostEqual(d["high"], 0.2, places=9)

    def test_an_entry_without_a_formation_energy_gets_no_distance(self):
        d = H.distances([row("AB", {"A": 1, "B": 1}, -1.0), row("none", {"A": 1, "B": 2}, None)])
        self.assertEqual(set(d), {"AB"})

    def test_the_digest_is_one_line_per_row(self):
        rows = [row("JVASP-1", {"A": 1, "B": 1}, -1.25, icsd=True), row("JVASP-2", {"A": 1}, None)]
        want = hashlib.sha256(b"JVASP-1|-1.25|0.0|2.0|1\nJVASP-2|None|0.0|1.0|0\n").hexdigest()
        self.assertEqual(H.file_digest(rows), want)
        self.assertNotEqual(H.file_digest(rows[::-1]), want)
        with self.assertRaises(SystemExit):
            H.same_file(want)                                        # not the file the record describes
        self.assertEqual(H.same_file(H.ROWS_SHA256), H.ROWS_SHA256)

    def test_field_and_computed_distance_are_counted_over_the_file(self):
        rows = [row("AB", {"A": 1, "B": 1}, -1.0, field=2.0), row("A3B", {"A": 3, "B": 1}, -0.4, field=0.0), row("AB3", {"A": 1, "B": 3}, -0.6, field=0.01),
                row("none", {"A": 1, "B": 2}, None, field=0.0), row("nan", {"A": 2, "B": 3}, -0.1, field=None)]
        c = H.file_counts(rows, H.distances(rows))
        self.assertEqual((c["entries"], c["with_a_formation_energy"], c["field_is_a_number"], c["field_exactly_zero"]), (5, 4, 3, 1))
        self.assertEqual((c["field_within_50_meV"], c["computed_within_50_meV"], c["both_within"]), (2, 2, 1))
        self.assertEqual((c["field_within_computed_beyond"], c["computed_within_field_beyond"], c["neither_within"]), (1, 1, 1))

    def test_a_published_list(self):
        rows = [row("AB", {"A": 1, "B": 1}, -1.0, icsd=True), row("A3B", {"A": 3, "B": 1}, -0.4), row("A2B", {"A": 2, "B": 1}, -0.3),
                row("edge", {"A": 5, "B": 1}, -1 / 3 + 0.05)]
        dist, by_id = H.distances(rows), {r["id"]: r for r in rows}
        cands = [{"id": "AB", "rank": 1, "formula": "AB", "ehull": 0.0}, {"id": "A3B", "rank": 2, "formula": "A3B", "ehull": 0.0},
                 {"id": "A2B", "rank": 3, "formula": "A2B", "ehull": 0.01}, {"id": "edge", "rank": 4, "formula": "A5B", "ehull": 0.0}]
        record, table = H.published("storm", {"round": 5, "date": "2026-10-31"}, cands, dist, by_id)
        self.assertEqual(record["distance_eV_per_atom"], {"AB": 0.0, "A3B": 0.1, "A2B": 0.3667, "edge": 0.05})
        self.assertEqual((record["listed"], record["found"], record["within_50_meV"], record["beyond_50_meV"], record["beyond_200_meV"]), (4, 4, 2, 2, 1))
        self.assertEqual((record["round"], record["date"], record["with_an_icsd_number"]), (5, "2026-10-31", 1))
        self.assertEqual([t["id"] for t in table], ["AB", "A3B", "A2B", "edge"])
        self.assertEqual(table[2]["published_ehull"], 0.01)
        with self.assertRaises(SystemExit):
            H.published("storm", {}, cands + [{"id": "missing", "formula": "X"}], dist, by_id)
        with self.assertRaises(SystemExit):
            H.published("storm", {}, cands + [cands[0]], dist, by_id)

    def test_against_pymatgen_where_it_is_installed(self):
        prog = json.loads((ROOT / "progress/progress.json").read_text(encoding="utf-8"))
        rows = H.synthetic(prog)
        dist = H.distances(rows)
        got = H.pymatgen_check(rows, dist, [r["id"] for r in rows if r["id"].startswith("JVASP-")][:40], sample=60)
        if "skipped" in got:
            self.skipTest(got["skipped"])
        self.assertEqual((got["published_candidates_compared"], got["other_entries_compared"]), (40, 60))
        self.assertLessEqual(got["largest_difference_eV_per_atom"], H.AGREE)
        wrong = dict(dist)
        wrong[next(k for k in dist if k.startswith("JVASP-"))] += 0.01
        with self.assertRaises(SystemExit):
            H.pymatgen_check(rows, wrong, [k for k in dist if k.startswith("JVASP-")][:5], sample=0)


class StepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.before_text = H.P.PROGRESS.read_text(encoding="utf-8")
        cls.before = json.loads(cls.before_text)
        cls.result_there = (H.P.RESULTS / H.RESULT).exists()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            cls.out = H.run(smoke=True, output_dir=Path(cls.tmp.name))
        cls.lines = buffer.getvalue().strip().split("\n")
        cls.after = json.loads((Path(cls.tmp.name) / "progress.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_smoke_run_writes_nothing_in_the_repository(self):
        self.assertEqual(H.P.PROGRESS.read_text(encoding="utf-8"), self.before_text)
        self.assertEqual((H.P.RESULTS / H.RESULT).exists(), self.result_there)
        self.assertTrue(self.out["smoke"])
        self.assertIsNone(self.out["file"]["rows_sha256"])

    def test_the_step_adds_one_field_and_one_log_entry(self):
        before, after = copy.deepcopy(self.before), copy.deepcopy(self.after)
        hull = after["screen"].pop("hull")
        before["screen"].pop("hull", None)                           # after the step has run on main, the published record is replaced
        self.assertEqual(after["screen"], before["screen"])          # every list, rank, score and text as published
        mine = [e for e in after["log"] if e["event"].startswith(H.LOG_PREFIX)]
        self.assertEqual(len(mine), 1)
        self.assertEqual([e for e in after["log"] if e is not mine[0]], [e for e in before["log"] if not e["event"].startswith(H.LOG_PREFIX)])
        self.assertEqual(after["updated"], self.out["run_at"])
        rest = lambda p: {k: v for k, v in p.items() if k not in ("screen", "log", "updated")}   # noqa: E731
        self.assertEqual(rest(after), rest(before))
        self.assertEqual(hull, self.out["screen"]["hull"])

    def test_the_record_covers_both_published_lists_exactly(self):
        hull, screen = self.out["screen"]["hull"], self.before["screen"]
        self.assertEqual((hull["record"], hull["about"]), (H.RECORD, H.ABOUT))
        self.assertTrue((ROOT / hull["record"]).is_file())
        for name, block, cands in (("storm", screen, screen["candidates"]), ("hurricane", screen["hurricane"], screen["hurricane"]["candidates"])):
            rec = hull[name]
            d = rec["distance_eV_per_atom"]
            self.assertEqual(set(d), {c["id"] for c in cands})
            self.assertEqual((rec["round"], rec["date"], rec["listed"], rec["found"]), (block["round"], block["date"], len(cands), len(cands)))
            self.assertEqual(rec["within_50_meV"] + rec["beyond_50_meV"], len(cands))
            self.assertEqual(rec["beyond_50_meV"], sum(1 for v in d.values() if v > 0.05))
            self.assertEqual(rec["beyond_200_meV"], sum(1 for v in d.values() if v > 0.2))
            self.assertTrue(all(isinstance(v, float) and v >= 0 and round(v, 4) == v for v in d.values()))
            self.assertEqual(rec["with_an_icsd_number"], sum(1 for c in cands if c["icsd"]))
        self.assertEqual([t["list"] for t in self.out["candidates"]], ["storm"] * len(screen["candidates"]) + ["hurricane"] * len(screen["hurricane"]["candidates"]))
        self.assertEqual({k for k in hull["file"]}, {"source", "entries", "field_within_50_meV", "computed_within_50_meV", "both_within",
                                                     "field_within_computed_beyond", "computed_within_field_beyond"})

    def test_a_second_run_replaces_the_record_and_the_log_entry(self):
        progress = Path(self.tmp.name) / "again.json"
        progress.write_text((Path(self.tmp.name) / "progress.json").read_text(encoding="utf-8"), encoding="utf-8")
        record = copy.deepcopy(self.out["screen"]["hull"])
        record["storm"]["beyond_50_meV"] += 1                        # as if the numbers had changed
        H.update_progress(record, "2026-11-14T00:00:00-06:00", progress)
        again = json.loads(progress.read_text(encoding="utf-8"))
        self.assertEqual(len([e for e in again["log"] if e["event"].startswith(H.LOG_PREFIX)]), 1)
        self.assertEqual(again["screen"]["hull"], record)
        self.assertEqual(len(again["log"]), len(self.after["log"]))
        self.assertEqual(list(again["screen"]), list(self.after["screen"]))

    def test_the_run_prints_its_record_with_a_hash(self):
        start = self.lines.index("=== screen-hull begin")
        end = next(i for i, line in enumerate(self.lines) if line.startswith("=== screen-hull end sha256 "))
        text = "".join(line.split("|", 2)[2] for line in self.lines[start + 1:end])
        self.assertEqual(self.lines[end], f"=== screen-hull end sha256 {hashlib.sha256(text.encode()).hexdigest()} chars {len(text)}")
        printed = json.loads(text)
        self.assertEqual(printed["screen"], self.out["screen"])
        saved = json.loads((Path(self.tmp.name) / H.RESULT).read_text(encoding="utf-8"))
        self.assertEqual(saved["screen"], self.out["screen"])
        self.assertEqual(len(saved["candidates"]), len(self.before["screen"]["candidates"]) + len(self.before["screen"]["hurricane"]["candidates"]))

    def test_the_message_states_the_counts_of_the_record(self):
        hull = self.out["screen"]["hull"]
        text = H.message(hull)
        self.assertTrue(text.startswith(H.LOG_PREFIX))
        for name in ("storm", "hurricane"):
            self.assertIn(f"{hull[name]['listed']}", text)
        self.assertIn(f"{hull['storm']['beyond_50_meV']} of the {hull['storm']['listed']} candidates on Storm's list", text)
        self.assertIn("No list, rank or score is changed", text)


if __name__ == "__main__":
    unittest.main()
