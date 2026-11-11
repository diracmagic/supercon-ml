import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane9_counts as C
import hurricane9_data as H


def row(**fields):
    base = {s: "" for s in H.REQUIRED_FIELDS}
    base.update(num=fields.pop("num", "1"), utc="K")
    base.update(fields)
    return base


def observations(rows):
    return [H.observation(row(**r)) for r in rows]


LSCO = dict(name="(La,Sr)2CuO4", ma1="La", mb1="Sr", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T", shape="1")
ROWS = [
    dict(num="1", refno="A1", **LSCO, ma2="1.85", mb2="0.15", year="1987", tc="37.123"),
    dict(num="2", refno="A2", **LSCO, ma2="1.9", mb2="0.1", year="1989", tc="29.777"),                      # new doping, same parent
    dict(num="3", refno="A3", name="(Nd,Ce)2CuO4", ma1="Nd", ma2="1.85", mb1="Ce", mb2="0.15", mc1="Cu", mc2="1", mo1="O",
         mo2="4", str3="T'", shape="1", year="1989", tc="24.555"),                                          # new parent, new structure
    dict(num="4", refno="A4", name="(La,Sr)3Cu2O6", ma1="La", ma2="1.9", mb1="Sr", mb2="1.1", mc1="Cu", mc2="2", mo1="O",
         mo2="6", str3="2126", shape="1", year="1990", tc="55.111"),                                        # new parent, known element set
    dict(num="5", refno="A5", name="(Pr,Ce)2CuO4", ma1="Pr", ma2="1.85", mb1="Ce", mb2="0.15", mc1="Cu", mc2="1", mo1="O",
         mo2="4", str3="T'", shape="1", year="1991", tc="22.333"),                                          # new parent, known structure
    dict(num="6", refno="A6", name="HgBa2CuO4+d", ma1="Hg", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="1", mo1="O",
         mo2="4+d", str3="Hg1201", shape="1", year="1993", tc="94.444"),                                    # new parent, no relative
    dict(num="7", refno="A7", name="CeCoIn5", ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5",
         shape="3", year="2001", tc="2.345"),
    dict(num="8", refno="A8", name="CeRhIn5", ma1="Ce", ma2="1", mb1="Rh", mb2="1", mc1="In", mc2="5", str3="HoCoGa5",
         shape="3", year="2003", tcn="0.35"),                                                               # a measured negative
    dict(num="9", refno="A9", name="LaFeAsO1-xFx", ma1="La", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", md1="F",
         md2="0.1", mo1="O", mo2="0.9", str3="ZrCuSiAs", shape="1", year="2008", tc="26.666"),
    dict(num="10", refno="A10", name="Sr2CuO3+d", ma1="Sr", ma2="2", mb1="Cu", mb2="1", mo1="O", mo2="3+d", shape="1",
         year="", tc="70.888"),                                                                             # undated
]


def window(obs, cutoff, width=5):
    return C.window_counts(obs, cutoff, width)


class Hurricane9CountsTests(unittest.TestCase):
    def test_a_new_doping_is_a_new_unit_but_not_a_new_parent(self):
        w = window(observations(ROWS), 1988)["new_units"]["cuprate"]
        p = window(observations(ROWS), 1988)["new_parent_units"]["cuprate"]
        # 1989 to 1993: rows 2 to 6 are new units; row 2 shares La2CuO4 with the 1987 report, so four are new parents
        self.assertEqual((w["units"], p["units"], p["parents"]), (5, 4, 4))
        self.assertEqual(window(observations(ROWS), 1988)["train"]["cuprate"]["units"], 1)

    def test_earlier_relatives_are_counted_within_the_family_and_only_from_the_training_side(self):
        p = window(observations(ROWS), 1990)["new_parent_units"]["cuprate"]
        # 1991 to 1995: (Pr,Ce)2CuO4 shares the structure name T' with the 1989 report; HgBa2CuO4 shares nothing
        self.assertEqual((p["units"], p["earlier_same_structure_name"], p["earlier_same_element_set"], p["no_earlier_relative"]), (2, 1, 0, 1))
        self.assertEqual((p["positive"], p["high_tc_positive"], p["positive_with_no_earlier_relative"],
                          p["parents_of_positives_with_no_earlier_relative"]), (2, 1, 1, 1))
        q = window(observations(ROWS), 1989)["new_parent_units"]["cuprate"]
        # 1990 to 1994: (La,Sr)3Cu2O6 has the element set of the 1987 and 1989 La-Sr-Cu-O reports and a new structure
        self.assertEqual((q["units"], q["earlier_same_element_set"], q["earlier_same_structure_name"], q["no_earlier_relative"]), (3, 1, 1, 1))
        # two members of one new structure type inside the same window are not each other's earlier relative
        h = window(observations(ROWS), 2000)["new_parent_units"]["heavy-fermion"]
        self.assertEqual((h["units"], h["positive"], h["negative"], h["censored"], h["with_tc_value"], h["no_earlier_relative"]), (2, 1, 1, 0, 1, 2))

    def test_the_window_has_an_end_and_undated_reports_enter_no_window(self):
        obs = observations(ROWS)
        first = window(obs, 1986)["new_parent_units"]["cuprate"]
        # 1987 to 1991: both La-Sr dopings count (their parent is new to the training side), Hg (1993) is outside
        self.assertEqual((first["units"], first["parents"]), (5, 4))
        self.assertEqual(C.window_counts(obs, 1986, None)["new_parent_units"]["cuprate"]["units"], 6)   # open-ended: Hg is inside
        self.assertEqual([w["window"] for w in C.report(obs)["rolling"]["windows"]][:3], [[1986, 1990], [1991, 1995], [1996, 2000]])
        totals = C.report(obs)["totals"]
        self.assertEqual((totals["admitted_without_year"], totals["observations"]), (1, 10))
        self.assertEqual(sum(c["units"] for w in C.report(obs)["rolling"]["windows"] for c in w["new_units"].values()), 9)   # nine dated units, each new exactly once
        self.assertEqual(C.report(obs)["first_report"]["cuprate"]["undated_units"], 1)

    def test_a_later_report_cannot_change_a_window(self):
        obs = observations(ROWS)
        later = observations(ROWS + [dict(num="11", refno="B1", **LSCO, ma2="1.85", mb2="0.15", year="2012", tc="39.999")])
        extreme = observations(ROWS + [dict(num="11", refno="B1", **LSCO, ma2="1.85", mb2="0.15", year="2012", tc="250")])
        for cutoff in (1985, 1990, 1995, 2000, 2005):
            self.assertEqual(window(obs, cutoff), window(later, cutoff))
            self.assertEqual(window(obs, cutoff), window(extreme, cutoff))
        self.assertEqual((window(obs, 2010)["repeat_units"]["cuprate"]["units"], window(later, 2010)["repeat_units"]["cuprate"]["units"]), (0, 1))
        self.assertEqual(window(extreme, 2010)["repeat_units"]["cuprate"]["units"], 0)       # quarantined above the review ceiling: no unit

    def test_the_open_window_reproduces_the_reviewed_temporal_split(self):
        for rows in (ROWS, None):
            obs = observations(rows) if rows else H.load_observations(H.synthetic_table())[0]
            self.assertTrue(C.report(obs)["open_window_agrees_with_temporal_split"])
        split = H.temporal_split(observations(ROWS), cutoff=2005)
        mine = C.window_counts(observations(ROWS), 2005, None)
        self.assertEqual(len(split["test_new_parent_units"]), sum(c["units"] for c in mine["new_parent_units"].values()))
        self.assertEqual(len(split["train_units"]), sum(c["units"] for c in mine["train"].values()))

    def test_field_coverage_counts_reports_units_and_series(self):
        y123 = dict(name="YBa2Cu3O7-x", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", str3="Y123", shape="1", ulat="A")
        rows = [dict(num=str(i), refno=f"Y{i}", **y123, oz=f"6.{4 + i}", lata="3.84", latc=f"11.{80 - i}", year="1988", tc=f"{50 + 7 * i}.5")
                for i in range(1, 6)]
        rows += [dict(num=str(10 + i), refno=f"L{i}", **LSCO, ma2=f"1.{95 - 5 * i}", mb2=f"0.{5 + 5 * i:02d}", latc="13.2", year="1988", tc=f"{20 + i}.5")
                 for i in range(1, 6)]
        rows += [dict(num="30", refno="L9", name="La2CuO4", ma1="La", ma2="2", mb1="Cu", mb2="1", mo1="O", mo2="4", str3="T", shape="1",
                      year="1988", tcn="4.2")]                                                            # a negative: no Tc value, no series member
        cov = C.field_coverage(observations(rows), H.canonical_units(observations(rows), lift=True))
        rep, units, series = cov["admitted_reports"]["cuprate"], cov["units"]["cuprate"], cov["parent_series"]["cuprate"]
        self.assertEqual((rep["reports"], rep["oxygen_measured"], rep["oxygen_fixed"], rep["lattice_c"], rep["lattice_a_and_c"], rep["floor"], rep["lattice_unit_stated"]),
                         (11, 5, 6, 10, 5, 1, 5))
        self.assertEqual((units["units"], units["units_with_tc_value"], units["with_tc_value_and_lattice_c"], units["with_tc_value_and_oxygen_measured"],
                          units["with_tc_value_and_both"]), (11, 10, 10, 5, 5))
        # both parents have five Tc-bearing units with a c axis; only the Y123 series has a c axis that varies
        self.assertEqual((series["parents_with_min_units"], series["parents_with_min_units_having_lattice_c"],
                          series["parents_with_min_units_and_varying_lattice_c"], series["units_in_varying_lattice_c_series"],
                          series["parents_with_min_units_having_oxygen_measured"], series["units_in_oxygen_measured_series"]), (2, 2, 1, 5, 1, 5))
        self.assertEqual(cov["all_rows"]["cuprate"]["pressure_study"], 0)
        self.assertEqual((cov["admitted_reports_after_lift"], cov["reports_matched_to_units"]), (11, 11))
        # a repeated data number must not move a report to another unit: the La2CuO4 floor reuses data number 1
        twin = [dict(r, num="1") if r["num"] == "30" else r for r in rows]
        again = C.field_coverage(observations(twin), H.canonical_units(observations(twin), lift=True))
        self.assertEqual((again["units"], again["parent_series"], again["admitted_reports"]), (cov["units"], cov["parent_series"], cov["admitted_reports"]))
        pressed = observations(rows + [dict(num="40", refno="P1", **LSCO, ma2="1.85", mb2="0.15", year="1990", tc="40", pmax="2")])
        self.assertEqual(C.field_coverage(pressed, H.canonical_units(pressed, lift=True))["all_rows"]["cuprate"], {"rows": 12, "pressure_study": 1, "pmax_positive": 1, "dtcdp_stated": 0})

    def test_a_window_counts_its_own_series_and_measured_fields(self):
        y123 = dict(name="YBa2Cu3O7-x", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", str3="Y123", shape="1", ulat="A")
        rows = [dict(num=str(i), refno=f"Y{i}", **y123, oz=f"6.{4 + i}", lata="3.84", latc=f"11.{80 - i}", year="1988", tc=f"{50 + 7 * i}.5")
                for i in range(1, 6)]
        rows += [dict(num=str(10 + i), refno=f"L{i}", **LSCO, ma2=f"1.{95 - 5 * i}", mb2=f"0.{5 + 5 * i:02d}", latc="13.2", year="1992", tc=f"{20 + i}.5")
                 for i in range(1, 6)]
        rows += [dict(num="30", refno="Y9", **y123, oz="6.95", lata="3.82", latc="11.69", year="1993", tc="92.5")]   # a later Y123 unit
        obs = observations(rows)
        first = window(obs, 1985)["new_parent_units"]["cuprate"]
        # 1986 to 1990: the five Y123 units are one new-parent series with a varying c axis and a measured oxygen content
        self.assertEqual((first["units"], first["with_tc_value_and_lattice_c"], first["with_tc_value_and_oxygen_measured"], first["with_tc_value_and_both"]), (5, 5, 5, 5))
        self.assertEqual((first["series"]["parents_with_min_units"], first["series"]["parents_with_min_units_and_varying_lattice_c"],
                          first["series"]["units_in_varying_lattice_c_series"], first["series"]["units_in_oxygen_measured_series"]), (1, 1, 5, 5))
        second = window(obs, 1990)
        # 1991 to 1995: the La-Sr series is a new parent with one c value; the 1993 Y123 unit is new but its parent is known
        cell = second["new_parent_units"]["cuprate"]
        self.assertEqual((second["new_units"]["cuprate"]["units"], cell["units"], cell["with_tc_value_and_lattice_c"], cell["with_tc_value_and_oxygen_measured"]), (6, 5, 5, 0))
        self.assertEqual((cell["series"]["parents_with_min_units_having_lattice_c"], cell["series"]["parents_with_min_units_and_varying_lattice_c"]), (1, 0))
        # the training side of a window counts only what was reported up to the cutoff
        self.assertEqual(second["train_measured"]["cuprate"], {"with_tc_value_and_lattice_c": 5, "with_tc_value_and_oxygen_measured": 5, "with_tc_value_and_both": 5})
        self.assertEqual(window(obs, 1995)["train_measured"]["cuprate"]["with_tc_value_and_lattice_c"], 11)

    def test_lattice_lengths_are_counted_by_stated_unit_and_size(self):
        y123 = dict(name="YBa2Cu3O7-x", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", str3="Y123", shape="1")
        rows = [dict(num="1", refno="U1", **y123, oz="6.9", lata="3.82", latc="11.68", ulat="A", year="1988", tc="91.5"),
                dict(num="2", refno="U2", **y123, oz="6.8", lata="0.382", latc="1.168", ulat="nm", year="1988", tc="88.5"),
                dict(num="3", refno="U3", **y123, oz="6.7", latc="11.71", year="1988", tc="80.5"),
                dict(num="4", refno="U4", **y123, oz="6.6", lata="3.84", latc="11.73", ulat="A", year="1988", tc="250")]   # quarantined: not counted
        self.assertEqual(C.lattice_magnitudes(observations(rows)),
                         {"a": {"A": {"2.5 to 20": 1}, "nm": {"below 1": 1}},
                          "c": {"A": {"2.5 to 20": 1}, "nm": {"1 to 2.5": 1}, "not stated": {"2.5 to 20": 1}}})

    def test_early_high_tc_units_are_listed_by_identity_and_year_only(self):
        y123 = dict(name="YBa2Cu3O7-x", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7", str3="Y123", shape="1")
        fe = dict(name="LaFeAsO1-xFx", ma1="La", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", md1="F", mo1="O", str3="ZrCuSiAs", shape="1")
        rows = [dict(num="1", refno="E1", **y123, year="1978", tc="91.234"),                                # a year that cannot be right
                dict(num="2", refno="E2", **y123, year="1988", tc="92.345"),                                # the same unit, dated correctly
                dict(num="3", refno="E3", **fe, md2="0.11", mo2="0.89", year="2001", tc="35.456"),
                dict(num="4", refno="E4", **fe, md2="0.05", mo2="0.95", year="2001", tc="12.567"),          # below 30 K: not listed
                dict(num="5", refno="E5", **fe, md2="0.12", mo2="0.88", year="2008", tc="36.678")]          # in its era: not listed
        listed = C.early_high_tc_units(H.canonical_units(observations(rows), lift=True))
        self.assertEqual([(r["family"], r["exact"], r["earliest_year"], r["latest_year"], r["reports"], r["references"]) for r in listed],
                         [("cuprate", "Ba2 Cu3 Y1 O7", 1978, 1988, 2, 2), ("iron-nickel", "As1 F0.11 Fe1 La1 O0.89", 2001, 2001, 1, 1)])
        text = json.dumps(C.report(observations(rows)))
        for tc in ("91.234", "92.345", "35.456", "12.567", "36.678"):
            self.assertNotIn(tc, text)

    def test_the_report_holds_counts_only(self):
        rep = C.report(observations(ROWS))

        def leaves(node):
            if isinstance(node, dict):
                for v in node.values():
                    yield from leaves(v)
            elif isinstance(node, list):
                for v in node:
                    yield from leaves(v)
            else:
                yield node

        for leaf in leaves(rep):
            self.assertIsInstance(leaf, (int, str, type(None)), msg=repr(leaf))     # bool is an int; no float can carry a Tc or a lattice value
        text = json.dumps(rep)
        for tc in ("37.123", "29.777", "24.555", "55.111", "22.333", "94.444", "2.345", "26.666", "70.888"):
            self.assertNotIn(tc, text)

    def test_command_line_smoke_prints_a_hashed_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "counts.json"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                C.main(["--smoke", "--output", str(out)])
            lines = buffer.getvalue().strip().split("\n")
            self.assertEqual(lines[0], "=== hurricane9-counts begin")
            self.assertTrue(lines[-1].startswith("=== hurricane9-counts end sha256 "))
            pieces = [line.split("|", 2) for line in lines[1:-1]]
            self.assertEqual([(p[0], p[1]) for p in pieces], [("h9c", f"{i:03d}") for i in range(len(pieces))])
            self.assertTrue(all(len(p[2]) <= C.PIECE for p in pieces))
            text = "".join(p[2] for p in pieces)
            self.assertEqual(text + "\n", out.read_text(encoding="utf-8"))
            self.assertIn(hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)), lines[-1])
            saved = json.loads(text)
            self.assertEqual((saved["smoke"], saved["version"], saved["data_module"], saved["rolling"]["width"]), (True, C.VERSION, H.VERSION, C.WIDTH))
            self.assertEqual(saved["rolling"]["cutoffs"], list(C.CUTOFFS))


if __name__ == "__main__":
    unittest.main()
