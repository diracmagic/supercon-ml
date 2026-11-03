import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane9_data as H


def row(**fields):
    base = {s: "" for s in H.REQUIRED_FIELDS}
    base.update(num=fields.pop("num", "1"), utc="K")
    base.update(fields)
    return base


class Hurricane9DataTests(unittest.TestCase):
    def test_header_is_validated_by_symbol_and_label_not_position(self):
        text = H.synthetic_table()
        table = H.parse_table(text)
        self.assertEqual(len(table), 10)
        lines = text.split("\n")
        symbols = lines[2].split("\t")
        # Shuffle the columns: the parser must still find every field by its symbol.
        order = list(range(len(symbols)))[::-1]
        shuffled = "\n".join("\t".join(line.split("\t")[i] for i in order) for line in lines if line)
        self.assertEqual(H.parse_table(shuffled + "\n")["element"].tolist(), table["element"].tolist())
        # A renamed label is refused.
        bad = lines[1].replace("Tc (of this sample) recommended", "Tc of the compound")
        with self.assertRaisesRegex(ValueError, "labelled"):
            H.parse_table("\n".join([lines[0], bad] + lines[2:]))
        # A missing symbol is refused.
        with self.assertRaisesRegex(ValueError, "missing"):
            H.parse_table("\n".join([lines[0], lines[1], lines[2].replace("\ttcn\t", "\ttcx\t")] + lines[3:]))

    def test_composition_and_oxygen_status(self):
        comp, oxygen = H.composition(row(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4-Y"))
        self.assertEqual(comp, {"La": 1.85, "Sr": 0.15, "Cu": 1.0, "O": 4.0})
        self.assertEqual((oxygen["nominal"], oxygen["status"]), (4.0, "variable"))
        self.assertEqual(H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7"))[1]["status"], "fixed")
        self.assertEqual(H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="z"))[1], {"nominal": None, "status": "unknown", "expression": "z"})
        comp, oxygen = H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", oz="6.93"))
        self.assertEqual((comp["O"], oxygen["status"]), (6.93, "measured"))
        self.assertEqual(H.composition(row(ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5"))[1]["status"], "none")
        with self.assertRaisesRegex(ValueError, "bad element"):
            H.composition(row(ma1="Xx", ma2="1"))
        with self.assertRaisesRegex(ValueError, "oxygen expression"):
            H.composition(row(ma1="Cu", ma2="1", mo1="O", mo2="4--"))
        self.assertEqual(H.parse_formula("Y1Ba2Cu3O7-X"), {"Y": 1.0, "Ba": 2.0, "Cu": 3.0, "O": 7.0})

    def test_integer_rounded_parent_rule(self):
        # Common-formula route: the datasheet marks shared sites; the host of a site is the member with the larger coefficient.
        named = {("(La,Sr)2CuO4", "La1.85Sr0.15Cu1O4"): "CuLa2O4", ("(Ba,K)BiO3", "Ba0.6K0.4Bi1O3"): "BaBiO3",
                 ("LaFeAsO1-xFx", "La1Fe1As1O0.9F0.1"): "AsFeLaO", ("(Nd,Sr)NiO2", "Nd0.85Sr0.15Ni1O2"): "NdNiO2",
                 ("Ba(Fe,Co)2As2", "Ba1Fe1.8Co0.2As2"): "As2BaFe2", ("NaFe1-xCoxAs", "Na1Fe0.99Co0.01As1"): "AsFeNa",
                 ("YBa2(Cu,Zn)4O8", "Y1Ba2Cu3.98Zn0.02O8"): "Ba2Cu4O8Y", ("YBa2Cu3(O,S)7", "Y1Ba2Cu3S1O6"): "Ba2Cu3O7Y",
                 ("Y(Y,Ba)2Cu3O7", "Y1.2Ba1.8Cu2O7"): "Ba2Cu3O7Y", ("TlBa2CaCu2O7-D", "Tl1Ba2Ca1Cu2O7"): "Ba2CaCu2O7Tl",
                 ("Bi2Sr2CaCu2O8+d", "Bi2Sr2Ca1Cu2O8.2"): "Bi2CaCu2O8Sr2", ("(Ba,La,)2CuO4", "Ba0.2La1.8Cu1O4"): "CuLa2O4"}
        for (name, formula), expected in named.items():
            self.assertEqual(H.parent(H.parse_formula(formula), name), expected, name)
        self.assertIsNone(H.parent_from_name("(La,Sr)2CuO4", {"La": 2.0, "Cu": 1.0, "O": 4.0}))   # a member missing from the fields
        self.assertIsNone(H.parent_from_name("", {"La": 2.0}))
        # Coefficient route (blank or unreadable name): strip elements below half a formula unit, round the rest half up.
        cases = {"La1.85Sr0.15Cu1O4": "CuLa2O4", "La1Fe1As1O0.9F0.1": "AsFeLaO", "Nd0.85Sr0.15Ni1O2": "NdNiO2", "Fe1.01Se1": "FeSe",
                 "Y1Ba2Cu3O6.5": "Ba2Cu3O7Y", "Ba1Fe1.8Co0.2As2": "As2BaFe2", "K0.8Fe2Se2": "Fe5K2Se5", "Ce1Co1In5": "CeCoIn5",
                 "Ba0.6K0.4Bi1O3": "BaBiO3", "Ba0.5K0.5Bi1O3": "BaBi2KO6", "C8K1": "C8K", "La1.9Sr0.1Cu1O4": "CuLa2O4"}
        for formula, expected in cases.items():
            self.assertEqual(H.parent(H.parse_formula(formula)), expected, formula)
        self.assertEqual(H.parent({"O": 2.0}), "unresolved")

    def test_family_rule_precedence_and_statuses(self):
        self.assertEqual(H.family({"Y": 1, "Ba": 2, "Cu": 3, "O": 7}, "Y123"), ("cuprate", "by-structure"))
        self.assertEqual(H.family({"La": 1, "Fe": 1, "As": 1, "O": 1}, "oxypnictide"), ("iron-nickel", "by-structure"))
        self.assertEqual(H.family({"Ce": 1, "Co": 1, "In": 5}, "HoCoGa5"), ("heavy-fermion", "by-structure"))
        self.assertEqual(H.family({"Nd": .85, "Sr": .15, "Ni": 1, "O": 2}, "infinite layer")[0], "other-oxide")
        self.assertEqual(H.family({"Ba": 1, "Fe": 2, "As": 2}, "ThCr2Si2"), ("iron-nickel", "by-composition (uncertain)"))
        self.assertEqual(H.family({"Ce": 1, "Cu": 2, "Si": 2}, "ThCr2Si2"), ("heavy-fermion", "by-composition (uncertain)"))
        self.assertEqual(H.family({"Ba": .6, "K": .4, "Bi": 1, "O": 3}, "")[0], "other-oxide")
        self.assertEqual(H.family({"Fe": 1, "Cu": 1, "O": 2, "As": 1}, "")[0], "mixed")
        self.assertEqual(H.family({"Nb": 3, "Sn": 1}, "Cr3Si(A15)"), ("other", "unknown"))
        self.assertEqual(H.family({"Ce": 1, "Cu": 1, "O": 3}, "")[0], "cuprate")   # Cu-O wins over the f element

    def test_domain_policy_never_makes_negatives_from_exclusions(self):
        base = dict(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", str3="Y123", tc="90")
        self.assertEqual(H.observation(row(**base))["status"], "admitted")
        self.assertEqual(H.observation(row(**base, shape="4"))["reason"], "sample form film")
        self.assertEqual(H.observation(row(**base, shape="2"))["reason"], "sample form multi-phase bulk")
        self.assertEqual(H.observation(row(**base, pmax="10"))["reason"], "pressure study")
        self.assertEqual(H.observation(row(**base, dtcdp="0.5"))["reason"], "pressure study")
        self.assertEqual(H.observation(row(**base, utc="mK"))["reason"], "temperature unit not K")
        self.assertEqual(H.observation(row(ma1="H", ma2="3", mb1="S", mb2="1", tc="203"))["reason"], "hydrogen-containing compound (project rule)")
        quarantined = H.observation(row(**dict(base, tc="275")))
        self.assertEqual(quarantined["status"], "quarantined")
        self.assertTrue(quarantined["reason"].startswith("tc above the frozen ambient-bulk ceiling of 140.0 K"))
        conflict = H.observation(row(**dict(base, t1="60")))
        self.assertEqual((conflict["status"], conflict["reason"]), ("quarantined", "criterion conflict: t1=60.0 against tc=90.0"))
        self.assertEqual(H.observation(row(**dict(base, t2="88")))["status"], "admitted")   # within 20% and 5 K
        both = H.observation(row(**dict(base, tcn="4.2")))
        self.assertEqual(both["status"], "quarantined")
        nothing = H.observation(row(**dict(base, tc="")))
        self.assertEqual(nothing["reason"], "no transition and no floor recorded")
        for o in (quarantined, conflict, both, nothing):
            self.assertEqual(H.event_label(o, 4.2), "censored")

    def test_event_labels_are_censoring_aware(self):
        positive = H.observation(row(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T", tc="38"))
        self.assertEqual((H.event_label(positive, 4.2), H.event_label(positive, 30.0), H.event_label(positive, 40.0)), (1, 1, 0))
        low_floor = H.observation(row(ma1="La", ma2="2", mb1="Cu", mb2="1", mo1="O", mo2="4", str3="T", tcn="1.8"))
        high_floor = H.observation(row(num="2", ma1="La", ma2="2", mb1="Cu", mb2="1", mo1="O", mo2="4", str3="T", tcn="77"))
        self.assertEqual((H.event_label(low_floor, 4.2), H.event_label(high_floor, 4.2)), (0, "censored"))
        self.assertEqual(H.event_label(high_floor, 77.0), 0)
        zero = H.observation(row(ma1="La", ma2="2", mb1="Cu", mb2="1", mo1="O", mo2="4", str3="T", tc="0"))
        self.assertEqual(H.event_label(zero, 4.2), "censored")   # a recorded zero without a floor is not a supported negative
        tiny = H.observation(row(ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5", tc="0.4"))
        self.assertEqual((H.event_label(tiny, 1.0), H.event_label(tiny, 0.2)), (0, 1))

    def test_units_aggregate_only_compatible_observations_and_keep_conflicts(self):
        base = dict(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4-Y", str3="T", shape="1")
        obs = [H.observation(row(num="1", year="1987", tc="36", **base)), H.observation(row(num="2", year="1990", tc="40", **base)),
               H.observation(row(num="3", year="2001", tc="38", **base)),
               H.observation(row(num="4", year="1995", tcn="4.2", **base)),                       # a sample that did not superconduct
               H.observation(row(num="5", year="1995", tc="37", **dict(base, shape="3"))),        # single crystal: another unit
               H.observation(row(num="6", year="1995", tc="30", **dict(base, mo2="4"))),          # fixed oxygen: another unit
               H.observation(row(num="7", year="1999", tc="25", **dict(base, shape="4")))]        # film: excluded, not a unit
        units = H.canonical_units(obs)
        self.assertEqual(len(units), 3)
        main = next(u for u in units if u["form_class"] == "bulk-specified" and u["oxygen_status"] == "variable")
        self.assertEqual((main["n_observations"], main["tc_k"], main["tc_spread_k"], main["floor_k"]), (4, 38.0, [36.0, 40.0, 3], 4.2))
        self.assertEqual((main["event"], main["high_tc_event"], main["conflict"], main["earliest_year"]), (1, 1, "sample-dependent", 1987))
        self.assertEqual(main["members"], ["1", "2", "3", "4"])
        negative_only = H.canonical_units([H.observation(row(num="8", year="2000", tcn="2.0", **base))])[0]
        self.assertEqual((negative_only["event"], negative_only["tc_k"], negative_only["floor_k"]), (0, None, 2.0))
        censored_only = H.canonical_units([H.observation(row(num="9", year="2000", tcn="77", **base))])[0]
        self.assertEqual(censored_only["event"], "censored")

    def test_components_join_formula_parent_links_and_element_sets_and_purge_anchors(self):
        obs = [H.observation(row(num="1", year="1987", tc="36", ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="2", year="1987", tc="30", ma1="La", ma2="1.9", mb1="Sr", mb2="0.1", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="3", year="1987", tc="20", ma1="La", ma2="1.8", mb1="Ba", mb2="0.2", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="4", year="2008", tc="26", ma1="La", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", md1="F", md2="0.1", mo1="O", mo2="0.9", str3="oxypnictide")),
               H.observation(row(num="5", year="2001", tc="2.3", ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5"))]
        units = H.canonical_units(obs)
        by_num = {u["members"][0]: u for u in units}                                  # units come back sorted by key, not by row
        self.assertEqual(sorted(by_num), ["1", "2", "3", "4", "5"])                   # five distinct units, one per row
        u1, u2, u3, u4, u5 = (by_num[n] for n in ("1", "2", "3", "4", "5"))
        extra = [{"kind": "3dsc", "id": "row-77", "canonical": u1["canonical"], "parent": u1["parent"], "elements": u1["elements"], "family": "cuprate", "links": [("mp", "mp-19")]},
                 {"kind": "mp", "id": "mp-19", "canonical": "Cu1 La2 O4", "parent": "CuLa2O4", "elements": ["Cu", "La", "O"], "family": "cuprate"},
                 {"kind": "anchor", "id": "CeCoIn5", "canonical": "Ce1 Co1 In5", "parent": "CeCoIn5", "elements": ["Ce", "Co", "In"], "family": "heavy-fermion"},
                 {"kind": "background", "id": "JVASP-1", "canonical": "As1 Fe1 La1 O1", "parent": "AsFeLaO", "elements": ["As", "Fe", "La", "O"], "family": "iron-nickel"}]
        comps = H.components(units, extra_nodes=extra)
        by_member = {tuple(m): cid for cid, c in comps.items() for m in c["members"]}
        la_sr = by_member[("unit",) + u1["key"]]
        self.assertEqual(by_member[("unit",) + u2["key"]], la_sr)                    # same parent La2CuO4 (dopant stripped)
        self.assertEqual(by_member[("unit",) + u3["key"]], la_sr)                    # La-Ba-Cu-O shares the parent too
        self.assertEqual(by_member[("3dsc", "row-77")], la_sr)                        # same canonical composition
        self.assertEqual(by_member[("mp", "mp-19")], la_sr)                           # explicit link
        self.assertEqual(by_member[("background", "JVASP-1")], by_member[("unit",) + u4["key"]])   # parent + element set
        self.assertNotEqual(by_member[("unit",) + u4["key"]], la_sr)                 # the iron pnictide is not joined to the cuprates
        ce = by_member[("unit",) + u5["key"]]
        self.assertTrue(comps[ce]["purged"])                                          # anchor member purges the component
        self.assertEqual(comps[ce]["purge_reason"], "anchor or prior-claim member")
        assignment = H.assign_folds(comps)
        self.assertNotIn(ce, assignment)
        self.assertEqual(sorted(assignment), sorted(c for c in comps if not comps[c]["purged"]))
        man = H.manifest(units, comps, assignment)
        self.assertEqual(len(man["rows"]), 5)
        self.assertTrue(all(r["fold"] is None for r in man["rows"] if r["purged"]))
        self.assertEqual(H.manifest(units, comps, assignment)["sha256"], man["sha256"])   # deterministic
        with self.assertRaisesRegex(ValueError, "unknown node"):
            H.components(units, extra_nodes=[{"kind": "3dsc", "id": "x", "links": [("mp", "missing")]}])

    def test_assign_folds_balances_components_by_family(self):
        comps = {f"C{i}": {"size": 1, "families": {"cuprate": 1}, "purged": False} for i in range(10)}
        comps.update({f"D{i}": {"size": 1, "families": {"iron-nickel": 1}, "purged": False} for i in range(5)})
        comps["X"] = {"size": 50, "families": {"cuprate": 50}, "purged": True}
        assignment = H.assign_folds(comps)
        from collections import Counter
        per_fold = Counter(assignment[c] for c in comps if c.startswith("C"))
        self.assertEqual(sorted(per_fold.values()), [2, 2, 2, 2, 2])
        self.assertEqual(sorted(Counter(assignment[c] for c in comps if c.startswith("D")).values()), [1, 1, 1, 1, 1])
        self.assertNotIn("X", assignment)

    def test_temporal_split_is_date_first_and_separates_new_materials_from_repeat_reports(self):
        base = dict(ma1="La", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", md1="F", md2="0.1", mo1="O", mo2="0.9", str3="oxypnictide")
        obs = [H.observation(row(num="1", year="2008", tc="26", **base)),
               H.observation(row(num="2", year="2019", tc="27", **base)),                                  # repeat report of a known unit
               H.observation(row(num="3", year="2019", tc="20", **dict(base, md2="0.2", mo2="0.8"))),     # new unit, same parent
               H.observation(row(num="4", year="2020", tc="2.3", ma1="Ce", ma2="1", mb1="Rh", mb2="1", mc1="In", mc2="5", str3="HoCoGa5")),   # new parent
               H.observation(row(num="5", year="", tc="30", ma1="Sm", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", mo1="O", mo2="1", str3="oxypnictide"))]
        split = H.temporal_split(obs, cutoff=2017)
        self.assertEqual(len(split["train_units"]), 1)
        self.assertEqual(split["train_units"][0]["tc_k"], 26.0)                       # the 2019 report never enters the training median
        self.assertEqual([u["members"] for u in split["repeat_report_units"]], [["2"]])
        self.assertEqual(sorted(u["members"][0] for u in split["test_new_units"]), ["3", "4"])
        self.assertEqual([u["members"] for u in split["test_new_parent_units"]], [["4"]])
        self.assertEqual(split["undated_excluded"], 1)

    def test_fetch_verifies_pinned_size_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                H.fetch("primary.tsv", tmp, get=lambda url: b"not the file")
            self.assertFalse(any(Path(tmp).iterdir()) and (Path(tmp) / "primary.tsv").stat().st_size == H.SOURCES["primary.tsv"]["bytes"])
            with self.assertRaisesRegex(ValueError, "offline"):
                H.fetch("ReadmeTbl.xlsx", tmp, offline=True)

    def test_smoke_audit_runs_and_reports_counts(self):
        observations, unreadable = H.load_observations(H.synthetic_table())
        self.assertEqual(unreadable, [])
        report = H.audit(observations)
        self.assertEqual(report["rows"], 10)
        self.assertEqual(report["status"], {"admitted": 6, "excluded": 3, "quarantined": 1})
        self.assertEqual(report["reasons"]["hydrogen-containing compound (project rule)"], 1)
        self.assertEqual(report["units"]["events"]["cuprate"], {"1": 1, "0": 1})
        self.assertEqual(report["event_labels"]["heavy-fermion"], {"1": 1, "0": 1})
        self.assertIn("manifest_sha256", report)
        json.dumps(report)   # serialisable
        families = {o["num"]: (o["family"], o["family_status"]) for o in observations}
        self.assertEqual(families["10"], ("other-oxide", "by-structure (nickelate analogue of a cuprate structure type)"))
        self.assertEqual(families["9"][0], "cuprate")
        self.assertEqual(next(o["status"] for o in observations if o["num"] == "10"), "excluded")   # a film


if __name__ == "__main__":
    unittest.main()
