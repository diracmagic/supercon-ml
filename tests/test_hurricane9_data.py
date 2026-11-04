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


LSCO = dict(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T", shape="1")
YBCO = dict(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", str3="Y123", tc="90")


class Hurricane9DataTests(unittest.TestCase):
    def test_header_is_validated_by_symbol_and_label_not_position(self):
        text = H.synthetic_table()
        table = H.parse_table(text)
        self.assertEqual(len(table), 12)
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
        # Ver.220808 repeats 'year' in the reference block with the same long name: accepted, first occurrence used,
        # the later one kept apart for the agreement count; a duplicate with a different long name is refused.
        dup = "\n".join([lines[0] + "\t999", lines[1] + "\tpublication year of reference", lines[2] + "\tyear"] + [l + "\t1990" for l in lines[3:] if l]) + "\n"
        table = H.parse_table(dup)
        self.assertEqual((table.attrs["duplicate_symbols"], table["year__2"].iloc[0], table["year"].iloc[0]), ({"year": [symbols.index("year"), len(symbols)]}, "1990", "1987"))
        notes = {}
        observations, _ = H.load_observations(dup, notes)
        self.assertEqual((notes["duplicate_symbols"], notes["duplicate_num_rows"], observations[0]["year"], observations[0]["year_reference_block"]), ({"year": [symbols.index("year"), len(symbols)]}, 0, 1987.0, 1990.0))
        with self.assertRaisesRegex(ValueError, "two different long names"):
            H.parse_table("\n".join([lines[0] + "\t999", lines[1] + "\tyear of something else", lines[2] + "\tyear"] + lines[3:]))

    def test_composition_oxygen_status_and_lossless_identity(self):
        comp, oxygen = H.composition(row(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4-Y"))
        self.assertEqual(comp, {"La": 1.85, "Sr": 0.15, "Cu": 1.0, "O": 4.0})
        self.assertEqual((oxygen["nominal"], oxygen["status"], oxygen["numeric_source"], oxygen["charge_identified"]),
                         (4.0, "variable", "nominal count of a variable expression", False))
        fixed = H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7"))[1]
        self.assertEqual((fixed["status"], fixed["charge_identified"], fixed["exact"]), ("fixed", True, "Ba2 Cu3 Y1 O7"))
        # F-32: 'Oz' instantiates no number: no oxygen coefficient, no identified charge, the expression kept in the identity.
        comp, unknown = H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="z"))
        self.assertNotIn("O", comp)
        self.assertEqual((unknown["status"], unknown["numeric"], unknown["charge_identified"], unknown["exact"]), ("unknown", None, False, "Ba2 Cu3 Y1 Oz"))
        self.assertEqual(H.canonical(comp, unknown["status"]), "Ba0.667 Cu1 Y0.333 O?")
        comp, measured = H.composition(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="7-X", oz="6.93"))
        self.assertEqual((comp["O"], measured["status"], measured["charge_identified"], measured["exact"]), (6.93, "measured", True, "Ba2 Cu3 Y1 O7-X|oz6.93"))
        self.assertEqual(H.composition(row(ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5"))[1]["status"], "none")
        # F-27: lossless identity at source precision; the 1e-3 bin is only an isolation edge.
        a = H.composition(row(ma1="Fe", ma2="1", mb1="Co", mb2="0.0101", mc1="Se", mc2="1"))
        b = H.composition(row(ma1="Fe", ma2="1", mb1="Co", mb2="0.0104", mc1="Se", mc2="1"))
        self.assertNotEqual(a[1]["exact"], b[1]["exact"])
        self.assertEqual(H.canonical(a[0]), H.canonical(b[0]))
        self.assertEqual(H.composition(row(ma1="Ba", ma2="0.60", mb1="K", mb2="0.4", mc1="Bi", mc2="1.0", mo1="O", mo2="3"))[1]["exact"], "Ba0.6 Bi1 K0.4 O3")
        self.assertEqual(H.composition(row(ma1="IN", ma2="0.02", mb1="Ce", mb2="1", mc1="In", mc2="4.98"))[0], {"In": 5.0, "Ce": 1.0})   # capitalised symbols
        # F-45: the coefficient text is normalised without any Decimal context, so every written digit survives.
        long_a, long_b = "0.12345678901234567890123456781", "0.12345678901234567890123456782"
        self.assertNotEqual(H._decimal_text(long_a), H._decimal_text(long_b))
        self.assertEqual((H._decimal_text(long_a), H._decimal_text("007"), H._decimal_text(".5"), H._decimal_text("1e-3"), H._decimal_text("1.50E+2"), H._decimal_text("0.0")),
                         (long_a, "7", "0.5", "0.001", "150", "0"))
        ca = H.composition(row(ma1="Fe", ma2="1", mb1="Co", mb2=long_a, mc1="Se", mc2="1"))[1]["exact"]
        cb = H.composition(row(ma1="Fe", ma2="1", mb1="Co", mb2=long_b, mc1="Se", mc2="1"))[1]["exact"]
        self.assertNotEqual(ca, cb)
        # The numeric identity (the key of the exact 3DSC match) writes the instantiated oxygen number, or nothing when unknown.
        self.assertEqual(measured["numeric_exact"], "Ba2 Cu3 Y1 O6.93")
        self.assertEqual(fixed["numeric_exact"], "Ba2 Cu3 Y1 O7")
        self.assertIsNone(unknown["numeric_exact"])
        self.assertEqual(H.formula_identity("Ba2Cu3O6.93Y1"), "Ba2 Cu3 Y1 O6.93")
        self.assertEqual(H.formula_identity("B0.015C0.985Cu1Sr2O5"), "B0.015 C0.985 Cu1 Sr2 O5")
        self.assertEqual(H.formula_identity("Nb3Sn"), "Nb3 Sn1")
        with self.assertRaisesRegex(ValueError, "cannot parse"):
            H.formula_identity("Sr(GePd)2")
        with self.assertRaisesRegex(ValueError, "bad element"):
            H.composition(row(ma1="Xx", ma2="1"))
        with self.assertRaisesRegex(ValueError, "oxygen expression"):
            H.composition(row(ma1="Cu", ma2="1", mo1="O", mo2="4--"))
        self.assertEqual(H.parse_formula("Y1Ba2Cu3O7-X"), {"Y": 1.0, "Ba": 2.0, "Cu": 3.0, "O": 7.0})

    def test_parent_routes_examples_boundaries_and_failures(self):
        # Common-formula route: the datasheet marks shared sites; the host of a site is the member with the larger coefficient.
        named = {("(La,Sr)2CuO4", "La1.85Sr0.15Cu1O4"): "CuLa2O4", ("(Ba,K)BiO3", "Ba0.6K0.4Bi1O3"): "BaBiO3",
                 ("LaFeAsO1-xFx", "La1Fe1As1O0.9F0.1"): "AsFeLaO", ("(Nd,Sr)NiO2", "Nd0.85Sr0.15Ni1O2"): "NdNiO2",
                 ("Ba(Fe,Co)2As2", "Ba1Fe1.8Co0.2As2"): "As2BaFe2", ("NaFe1-xCoxAs", "Na1Fe0.99Co0.01As1"): "AsFeNa",
                 ("YBa2(Cu,Zn)4O8", "Y1Ba2Cu3.98Zn0.02O8"): "Ba2Cu4O8Y", ("YBa2Cu3(O,S)7", "Y1Ba2Cu3S1O6"): "Ba2Cu3O7Y",
                 ("Y(Y,Ba)2Cu3O7", "Y1.2Ba1.8Cu2O7"): "Ba2Cu3O7Y", ("TlBa2CaCu2O7-D", "Tl1Ba2Ca1Cu2O7"): "Ba2CaCu2O7Tl",
                 ("Bi2Sr2CaCu2O8+d", "Bi2Sr2Ca1Cu2O8.2"): "Bi2CaCu2O8Sr2", ("(Ba,La,)2CuO4", "Ba0.2La1.8Cu1O4"): "CuLa2O4"}
        for (name, formula), expected in named.items():
            self.assertEqual(H.parent(H.parse_formula(formula), name), (expected, "common formula"), name)
        # F-44: a common formula may write a nominal oxygen count that the fields do not instantiate (fields 'Oz'): the
        # route says so; a common formula whose oxygen token has no count ('YBa2Cu3Oz', 'Ox') resolves no parent, and the
        # uninstantiated oxygen is never dropped to make an oxygen-free parent.
        self.assertEqual(H.parent({"Y": 1.0, "Ba": 2.0, "Cu": 3.0}, "YBa2Cu3O7-X", "unknown"),
                         ("Ba2Cu3O7Y", "common formula (nominal oxygen count written by the common formula only)"))
        self.assertEqual(H.parent({"Y": 1.0, "Ba": 2.0, "Cu": 3.0, "O": 7.0}, "YBa2Cu3O7-X", "variable"), ("Ba2Cu3O7Y", "common formula"))
        self.assertIsNone(H.parent_from_name("YBa2Cu3Oz", {"Y": 1.0, "Ba": 2.0, "Cu": 3.0}))
        self.assertIsNone(H.parent_from_name("YBa2Cu3Ox", {"Y": 1.0, "Ba": 2.0, "Cu": 3.0, "O": 6.9}))
        self.assertEqual(H.parent({"Y": 1.0, "Ba": 2.0, "Cu": 3.0}, "YBa2Cu3Oz", "unknown"),
                         ("unresolved", "unresolved: oxygen content not instantiated by any source field"))
        unknown_o = H.observation(row(ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="z", str3="Y123", name="YBa2Cu3Oz", tc="91"))
        self.assertEqual((unknown_o["parent"], unknown_o["status"], unknown_o["oxygen"]["status"]), ("unresolved", "admitted", "unknown"))
        self.assertIsNone(H.parent_from_name("(La,Sr)2CuO4", {"La": 2.0, "Cu": 1.0, "O": 4.0}))   # a member missing from the fields
        self.assertIsNone(H.parent_from_name("", {"La": 2.0}))
        # Coefficient route (blank or unreadable name), with the declared examples and the F-27 counterexample.
        cases = {"La1.85Sr0.15Cu1O4": ("CuLa2O4", 2), "La1Fe1As1O0.9F0.1": ("AsFeLaO", 1), "Nd0.85Sr0.15Ni1O2": ("NdNiO2", 1),
                 "Fe1.01Se1": ("FeSe", 1), "Y1Ba2Cu3O6.5": ("Ba2Cu3O7Y", 3), "Ba1Fe1.8Co0.2As2": ("As2BaFe2", 2),
                 "K0.8Fe2Se2": ("Fe5K2Se5", 5), "Ce1Co1In5": ("CeCoIn5", 5), "Ba0.6K0.4Bi1O3": ("BaBiO3", 1),
                 "Ba0.5K0.5Bi1O3": ("BaBi2KO6", 2), "C8K1": ("C8K", 8), "La1.9Sr0.1Cu1O4": ("CuLa2O4", 2),
                 "Y0.5Ba1Cu1.5O3.5": ("Ba2Cu3O7Y", 3)}
        for formula, (expected, mult) in cases.items():
            self.assertEqual(H.parent(H.parse_formula(formula)), (expected, f"coefficients (multiplier {mult})"), formula)
        # Failures are explicit statuses and never an edge.
        self.assertEqual(H.parent({"O": 2.0}), ("unresolved", "unresolved: no cation"))
        self.assertEqual(H.parent({"Y": 1.0, "Ba": 2.0, "Cu": 3.0}, "", "unknown")[1], "unresolved: oxygen content not instantiated by any source field")
        self.assertEqual(H.parent_from_coefficients({"La": 1.0, "Cu": 0.63}, max_multiplier=2), ("unresolved", "unresolved: no multiplier up to 2 within 0.25 of integers"))
        self.assertEqual(H.parent_from_coefficients({"La": 1.0, "Cu": 0.63}), ("Cu5La8", "coefficients (multiplier 8)"))   # nearest integer host, not chemistry
        self.assertEqual(H.parent({"Cu": 0.4, "La": 0.3})[1], "unresolved: every coefficient below the dopant threshold")

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

    def test_tc_channel_decision_table(self):
        kinds = [(dict(tc="38"), "positive"), (dict(tcn="4.2"), "negative"), (dict(tc="38", tcn="4.2"), "contradictory"),
                 (dict(tcn="4.2", t2="10"), "mixed"), (dict(tc="0"), "zero-without-floor"), (dict(tc="0", tcn="1.8"), "negative"),
                 (dict(t2="10"), "alternate-only"), (dict(tc="-1"), "negative-value"), (dict(), "none"), (dict(tcn="0"), "none")]
        for fields, kind in kinds:
            self.assertEqual(H.tc_evidence(row(**fields))["kind"], kind, fields)
        statuses = {"positive": ("admitted", ""), "negative": ("admitted", ""),
                    "contradictory": ("quarantined", "contradictory evidence within one observation (tc and tcn both present)"),
                    "mixed": ("quarantined", "floor with another positive Tc channel and no recommended tc"),
                    "zero-without-floor": ("excluded", "tc recorded as zero without a floor (censored, not a negative)"),
                    "alternate-only": ("excluded", "no recommended tc; only another Tc channel is positive (no fallback criterion adopted)"),
                    "negative-value": ("excluded", "negative tc value"), "none": ("excluded", "no transition and no floor recorded")}
        for fields, kind in kinds:
            obs = H.observation(row(**dict(LSCO, **fields)))
            self.assertEqual((obs["status"], obs["reason"]), statuses[kind], kind)
            if kind not in ("positive", "negative"):
                self.assertEqual(H.event_label(obs, 4.2), "censored", kind)   # never a negative by default
        # Codex's schema counterexample: a floor with an alternate positive channel is not an event-negative.
        obs = H.observation(row(**dict(LSCO, tcn="4.2", t2="10")))
        self.assertEqual((obs["status"], H.event_label(obs, 4.2)), ("quarantined", "censored"))

    def test_domain_policy_assumptions_and_criterion_checks(self):
        plain = H.observation(row(**YBCO))
        self.assertEqual((plain["status"], plain["assumptions"], plain["unit_status"], plain["pressure"]["status"]),
                         ("admitted", ["A2", "A3"], "explicit K", "unknown, assumed ambient (A2)"))
        blank_unit = H.observation(row(**dict(YBCO, utc="", shape="1")))
        self.assertEqual((blank_unit["status"], blank_unit["assumptions"], blank_unit["unit_status"]), ("admitted", ["A1", "A2"], "blank, assumed K (A1)"))
        self.assertEqual(H.observation(row(**YBCO, shape="4"))["reason"], "sample form film")
        self.assertEqual(H.observation(row(**YBCO, shape="2"))["reason"], "sample form multi-phase bulk")
        self.assertEqual(H.observation(row(**YBCO, pmax="10"))["reason"], "pressure study")
        self.assertEqual(H.observation(row(**YBCO, dtcdp="0.5"))["reason"], "pressure study")
        self.assertEqual(H.observation(row(**YBCO, utc="mK"))["reason"], "temperature unit not K")
        self.assertEqual(H.observation(row(ma1="H", ma2="3", mb1="S", mb2="1", tc="203"))["reason"], "hydrogen-containing compound (project rule)")
        extreme = H.observation(row(**dict(YBCO, tc="275")))
        self.assertEqual((extreme["status"], extreme["reason"]), ("quarantined", "extreme value, unverified: tc above the review ceiling of 140 K"))
        # Criterion policy: ordering, window, midpoint, susceptibility; the weak diamagnetic onset is a flag only.
        self.assertEqual(H.observation(row(**dict(YBCO, t1="60")))["status"], "admitted")   # zero resistance below the recommended value is consistent
        self.assertEqual(H.observation(row(**dict(YBCO, t1="100")))["reason"], "criterion conflict: recommended tc 90 below the zero-resistance temperature t1=100")
        self.assertEqual(H.observation(row(**dict(YBCO, t3="80")))["reason"], "criterion conflict: recommended tc 90 above the resistive onset t3=80")
        self.assertEqual(H.observation(row(**dict(YBCO, t1="92", t2="91", t3="93")))["reason"], "criterion conflict: resistive criterion ordering (t1 > t2)")
        self.assertEqual(H.observation(row(**dict(YBCO, t2="70")))["reason"], "criterion conflict: recommended tc 90 far from the midpoint t2=70")
        self.assertEqual(H.observation(row(**dict(YBCO, t2="88")))["status"], "admitted")
        self.assertEqual(H.observation(row(**dict(YBCO, t1="85", t2="89", t3="93")))["status"], "admitted")
        self.assertEqual(H.observation(row(**dict(YBCO, t3="93", tcsus="110")))["reason"], "criterion conflict: susceptibility value tcsus=110 above the resistive onset")
        weak = H.observation(row(**dict(YBCO, tcsus="40")))
        self.assertEqual((weak["status"], weak["flags"]), ("admitted", ["weak diamagnetic onset"]))
        self.assertEqual(H.observation(row(**dict(YBCO, t2="0", t3="0")))["status"], "admitted")   # zero channels are absent
        for o in (extreme, H.observation(row(**dict(YBCO, t1="100"))), H.observation(row(**dict(YBCO, tcn="4.2")))):
            self.assertEqual(H.event_label(o, 4.2), "censored")

    def test_replicated_extremes_are_lifted_without_project_files(self):
        hg = dict(ma1="Hg", ma2="1", mb1="Ba", mb2="2", mc1="Ca", mc2="2", md1="Cu", md2="3", mo1="O", mo2="8+d", str3="Hg1223", shape="1")
        obs = [H.observation(row(num="1", refno="R1", tc="150", **hg)), H.observation(row(num="2", refno="R2", tc="148", **hg)),
               H.observation(row(num="3", refno="R3", tc="120", **hg)), H.observation(row(num="4", refno="R4", **dict(YBCO, shape="1", tc="275")))]
        self.assertEqual([o["status"] for o in obs], ["quarantined", "quarantined", "admitted", "quarantined"])
        lifted = H.apply_replication_lift(obs)
        self.assertEqual([o["status"] for o in lifted], ["admitted", "admitted", "admitted", "quarantined"])
        self.assertEqual((lifted[0]["flags"], lifted[0]["reason"], lifted[0]["quarantine_reasons"]), (["replicated extreme"], "", []))
        self.assertEqual([o["status"] for o in obs], ["quarantined", "quarantined", "admitted", "quarantined"])   # the inputs are not modified
        self.assertEqual(obs[0]["flags"], [])
        same_ref = [H.observation(row(num="5", refno="R9", tc="150", **hg)), H.observation(row(num="6", refno="R9", tc="149", **hg))]
        self.assertEqual([o["status"] for o in H.apply_replication_lift(same_ref)], ["quarantined"] * 2)   # one reference twice is not a replication

    def test_replication_never_lifts_a_criterion_conflict(self):
        # F-39 (Codex's counterexample): two references at 150 and 149 K whose own onset is 20 K fail the criterion policy;
        # both reasons are recorded, and replication removes neither.
        hg = dict(ma1="Hg", ma2="1", mb1="Ba", mb2="2", mc1="Ca", mc2="2", md1="Cu", md2="3", mo1="O", mo2="8+d", str3="Hg1223", shape="1")
        pair = [H.observation(row(num="1", refno="R1", tc="150", t3="20", **hg)), H.observation(row(num="2", refno="R2", tc="149", t3="20", **hg))]
        self.assertEqual(pair[0]["quarantine_reasons"], ["criterion conflict: recommended tc 150 above the resistive onset t3=20",
                                                         "extreme value, unverified: tc above the review ceiling of 140 K"])
        self.assertEqual(pair[0]["reason"], "; ".join(pair[0]["quarantine_reasons"]))
        self.assertEqual([o["status"] for o in H.apply_replication_lift(pair)], ["quarantined", "quarantined"])
        self.assertEqual(H.canonical_units(pair), [])
        # A conflicting report is no witness either: one clean extreme plus one conflicting one is not a replication.
        mixed = [H.observation(row(num="3", refno="R1", tc="150", **hg)), H.observation(row(num="4", refno="R2", tc="149", t3="20", **hg))]
        self.assertEqual([o["status"] for o in H.apply_replication_lift(mixed)], ["quarantined", "quarantined"])
        # A criterion conflict alone is quarantined with one reason; an extreme alone with one reason.
        self.assertEqual(H.observation(row(num="5", tc="100", t3="20", **hg))["quarantine_reasons"], ["criterion conflict: recommended tc 100 above the resistive onset t3=20"])
        self.assertEqual(len(H.observation(row(num="6", tc="150", **hg))["quarantine_reasons"]), 1)
        report = H.audit(pair)
        self.assertEqual((report["quarantined_with_several_reasons"], report["replicated_extremes"], report["extremes_not_lifted"]), (2, 0, 2))
        self.assertEqual(report["quarantine_reasons"]["extreme value, unverified: tc above the review ceiling of 140 K"], 2)

    def test_replication_is_window_local_and_future_reports_do_not_change_training(self):
        # F-40 (Codex's counterexample): a 2019 report must not lift a 2010 extreme into the pre-2018 training window.
        hg = dict(ma1="Hg", ma2="1", mb1="Ba", mb2="2", mc1="Ca", mc2="2", md1="Cu", md2="3", mo1="O", mo2="8+d", str3="Hg1223", shape="1")
        past = H.observation(row(num="1", refno="R1", year="2010", tc="150", **hg))
        future = H.observation(row(num="2", refno="R2", year="2019", tc="149", **hg))
        with_future = H.temporal_split([past, future], cutoff=2017)
        without_future = H.temporal_split([past], cutoff=2017)
        self.assertEqual((len(with_future["train_units"]), len(without_future["train_units"])), (0, 0))
        self.assertEqual(H.manifest(with_future["train_units"], {}, {})["sha256"], H.manifest(without_future["train_units"], {}, {})["sha256"])
        self.assertEqual((len(with_future["test_new_units"]), len(with_future["repeat_report_units"])), (0, 0))   # the lone 2019 extreme is not lifted either
        # The whole cohort (no window) lifts the pair, and the recorded statuses stay as recorded.
        whole = H.canonical_units([past, future])
        self.assertEqual((len(whole), whole[0]["tc_k"], whole[0]["observation_flags"]), (1, 149.5, ["replicated extreme"]))
        self.assertEqual((past["status"], future["status"]), ("quarantined", "quarantined"))
        self.assertEqual(len(H.canonical_units([past, future], lift=False)), 0)
        # Two pre-cutoff references lift inside the training window; a later third report never changes that median.
        both_past = [past, H.observation(row(num="3", refno="R3", year="2012", tc="148", **hg))]
        a = H.temporal_split(both_past, cutoff=2017)["train_units"]
        b = H.temporal_split(both_past + [H.observation(row(num="4", refno="R4", year="2020", tc="130", **hg))], cutoff=2017)
        self.assertEqual((len(a), a[0]["tc_k"], len(b["train_units"]), b["train_units"][0]["tc_k"], len(b["repeat_report_units"])), (1, 149.0, 1, 149.0, 1))
        self.assertEqual(H.audit(both_past)["temporal"]["train_replicated_extremes"], 1)

    def test_event_labels_are_censoring_aware(self):
        positive = H.observation(row(**dict(LSCO, tc="38")))
        self.assertEqual((H.event_label(positive, 4.2), H.event_label(positive, 30.0), H.event_label(positive, 40.0)), (1, 1, 0))
        low_floor = H.observation(row(**dict(LSCO, tcn="1.8")))
        high_floor = H.observation(row(num="2", **dict(LSCO, tcn="77")))
        self.assertEqual((H.event_label(low_floor, 4.2), H.event_label(high_floor, 4.2)), (0, "censored"))
        self.assertEqual(H.event_label(high_floor, 77.0), 0)
        tiny = H.observation(row(ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5", tc="0.4"))
        self.assertEqual((H.event_label(tiny, 1.0), H.event_label(tiny, 0.2)), (0, 1))

    def test_units_use_the_representative_target_and_keep_flags(self):
        base = dict(LSCO, mo2="4-Y")
        obs = [H.observation(row(num="1", refno="R1", year="1987", tc="36", **base)), H.observation(row(num="2", refno="R2", year="1990", tc="40", **base)),
               H.observation(row(num="3", refno="R3", year="2001", tc="38", **base)),
               H.observation(row(num="4", refno="R4", year="1995", tcn="4.2", **base)),          # a sample that did not superconduct
               H.observation(row(num="5", year="1995", tc="37", **dict(base, shape="3"))),        # single crystal: another unit
               H.observation(row(num="6", year="1995", tc="30", **dict(base, mo2="4"))),          # fixed oxygen: another unit
               H.observation(row(num="7", year="1999", tc="25", **dict(base, shape="4")))]        # film: excluded, not a unit
        units = H.canonical_units(obs)
        self.assertEqual(len(units), 3)
        main = next(u for u in units if u["form_class"] == "bulk-specified" and u["oxygen_status"] == "variable")
        self.assertEqual((main["n_observations"], main["tc_k"], main["tc_spread_k"], main["floor_k"]), (4, 38.0, [36.0, 40.0, 3], 4.2))
        self.assertEqual((main["event"], main["high_tc_event"], main["flags"], main["earliest_year"]), (1, 1, ["sample-dependent"], 1987))
        self.assertEqual(main["members"], ["1", "2", "3", "4"])
        self.assertEqual(main["exact"], "Cu1 La1.85 Sr0.15 O4-Y")
        # Codex's counterexample: reports 1, 1, 5 K at T* = 4.2 K: the stored median is 1 K and the event is 0, flagged 'straddle'.
        hf = dict(ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5", shape="3")
        reports = lambda: [H.observation(row(num=str(i), tc=t, **hf)) for i, t in enumerate(("1", "1", "5"), 1)]
        three = H.canonical_units(reports(), thresholds={"heavy-fermion": 4.2})[0]
        self.assertEqual((three["tc_k"], three["event"], three["flags"]), (1.0, 0, ["straddle"]))
        self.assertEqual(H.canonical_units(reports())[0]["event"], 1)                 # at the family threshold of 1.0 K
        negative_only = H.canonical_units([H.observation(row(num="8", year="2000", tcn="2.0", **base))])[0]
        self.assertEqual((negative_only["event"], negative_only["tc_k"], negative_only["floor_k"]), (0, None, 2.0))
        censored_only = H.canonical_units([H.observation(row(num="9", year="2000", tcn="77", **base))])[0]
        self.assertEqual(censored_only["event"], "censored")
        # F-41: the 30 K event uses the same censoring-aware rule: a floor below or at 30 K supports event 0, above it is censored;
        # a positive labels by its stored target. Floor-only units never carry a regression target.
        high = lambda **f: H.canonical_units([H.observation(row(num="9", year="2000", **dict(base, **f)))])[0]
        self.assertEqual([high(tcn=t)["high_tc_event"] for t in ("1.8", "30", "30.5", "77")], [0, 0, "censored", "censored"])
        self.assertEqual([high(tc=t)["high_tc_event"] for t in ("28", "30", "38")], [0, 1, 1])
        self.assertEqual((high(tcn="1.8")["event"], high(tcn="1.8")["tc_k"]), (0, None))
        self.assertEqual(main["high_tc_event"], 1)
        self.assertEqual(H.unit_event(None, 1.8, 30.0), 0)
        # F-43: reference numbers and every member are kept, in a report-order-independent order.
        self.assertEqual((main["refnos"], main["references"]), (["R1", "R2", "R3", "R4"], 4))
        reversed_main = next(u for u in H.canonical_units(obs[::-1]) if u["form_class"] == "bulk-specified" and u["oxygen_status"] == "variable")
        self.assertEqual((reversed_main["members"], reversed_main["refnos"], reversed_main["tc_k"]), (main["members"], main["refnos"], main["tc_k"]))
        # Source precision separates units; the approximate bin does not merge them.
        pair = H.canonical_units([H.observation(row(num="10", tc="8", ma1="Fe", ma2="1", mb1="Co", mb2="0.0101", mc1="Se", mc2="1", str3="FeSe")),
                                  H.observation(row(num="11", tc="9", ma1="Fe", ma2="1", mb1="Co", mb2="0.0104", mc1="Se", mc2="1", str3="FeSe"))])
        self.assertEqual(len(pair), 2)
        self.assertEqual(pair[0]["canonical"], pair[1]["canonical"])

    def test_components_join_bins_parents_links_and_element_sets_and_purge_anchors(self):
        obs = [H.observation(row(num="1", year="1987", tc="36", ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="2", year="1987", tc="30", ma1="La", ma2="1.9", mb1="Sr", mb2="0.1", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="3", year="1987", tc="20", ma1="La", ma2="1.8", mb1="Ba", mb2="0.2", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T")),
               H.observation(row(num="4", year="2008", tc="26", ma1="La", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", md1="F", md2="0.1", mo1="O", mo2="0.9", str3="oxypnictide")),
               H.observation(row(num="5", year="2001", tc="2.3", ma1="Ce", ma2="1", mb1="Co", mb2="1", mc1="In", mc2="5", str3="HoCoGa5")),
               H.observation(row(num="6", year="1988", tc="91", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="z", str3="Y123")),
               H.observation(row(num="7", year="1988", tc="60", ma1="Nd", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="x", str3="Y123"))]
        units = H.canonical_units(obs)
        by_num = {u["members"][0]: u for u in units}                                  # units come back sorted by key, not by row
        self.assertEqual(sorted(by_num, key=int), ["1", "2", "3", "4", "5", "6", "7"])
        u1, u2, u3, u4, u5, u6, u7 = (by_num[n] for n in ("1", "2", "3", "4", "5", "6", "7"))
        self.assertTrue(u6["parent"].startswith("unresolved") and u7["parent"].startswith("unresolved"))
        extra = [{"kind": "3dsc", "id": "row-77", "canonical": u1["canonical"], "parent": u1["parent"], "elements": u1["elements"], "family": "cuprate", "links": [("mp", "mp-19")]},
                 {"kind": "mp", "id": "mp-19", "canonical": "Cu1 La2 O4", "parent": "CuLa2O4", "elements": ["Cu", "La", "O"], "family": "cuprate"},
                 {"kind": "anchor", "id": "CeCoIn5", "canonical": "Ce1 Co1 In5", "parent": "CeCoIn5", "elements": ["Ce", "Co", "In"], "family": "heavy-fermion"},
                 {"kind": "background", "id": "JVASP-1", "canonical": "As1 Fe1 La1 O1", "parent": "AsFeLaO", "elements": ["As", "Fe", "La", "O"], "family": "iron-nickel"},
                 {"kind": "3dsc", "id": "row-88", "canonical": "Ba1 Cu1.5 Y0.5 O3.5", "parent": "unresolved", "elements": ["Ba", "Cu", "O", "Y"], "family": "cuprate"}]
        comps = H.components(units, extra_nodes=extra)
        by_member = {tuple(m): cid for cid, c in comps.items() for m in c["members"]}
        la_sr = by_member[("unit",) + u1["key"]]
        self.assertEqual(by_member[("unit",) + u2["key"]], la_sr)                    # same parent La2CuO4 (dopant stripped)
        self.assertEqual(by_member[("unit",) + u3["key"]], la_sr)                    # La-Ba-Cu-O shares the parent too
        self.assertEqual(by_member[("3dsc", "row-77")], la_sr)                        # same approximate bin
        self.assertEqual(by_member[("mp", "mp-19")], la_sr)                           # explicit link
        self.assertEqual(by_member[("background", "JVASP-1")], by_member[("unit",) + u4["key"]])   # parent + element set
        self.assertNotEqual(by_member[("unit",) + u4["key"]], la_sr)                 # the iron pnictide is not joined to the cuprates
        self.assertEqual(by_member[("3dsc", "row-88")], by_member[("unit",) + u6["key"]])   # element set within the family, not the sentinel
        self.assertNotEqual(by_member[("unit",) + u6["key"]], by_member[("unit",) + u7["key"]])   # two unresolved parents share no edge
        # Edge ablation: without the element-set edge row-88 stands alone; without the parent edge La-Ba-Cu-O leaves the La-Sr pair.
        no_elements = {tuple(m): cid for cid, c in H.components(units, extra_nodes=extra, edges=("bin", "parent", "links")).items() for m in c["members"]}
        self.assertNotEqual(no_elements[("3dsc", "row-88")], no_elements[("unit",) + u6["key"]])
        self.assertEqual(no_elements[("mp", "mp-19")], no_elements[("unit",) + u1["key"]])
        no_parent = {tuple(m): cid for cid, c in H.components(units, extra_nodes=extra, edges=("bin", "elements", "links")).items() for m in c["members"]}
        self.assertNotEqual(no_parent[("unit",) + u3["key"]], no_parent[("unit",) + u1["key"]])
        ce = by_member[("unit",) + u5["key"]]
        self.assertTrue(comps[ce]["purged"])                                          # anchor member purges the component
        self.assertEqual(comps[ce]["purge_reason"], "anchor or prior-claim member")
        assignment = H.assign_folds(comps)
        self.assertNotIn(ce, assignment)
        self.assertEqual(sorted(assignment), sorted(c for c in comps if not comps[c]["purged"]))
        man = H.manifest(units, comps, assignment)
        self.assertEqual(len(man["rows"]), 7)
        self.assertTrue(all(r["fold"] is None for r in man["rows"] if r["purged"]))
        self.assertEqual(H.manifest(units, comps, assignment)["sha256"], man["sha256"])   # deterministic
        with self.assertRaisesRegex(ValueError, "unknown node"):
            H.components(units, extra_nodes=[{"kind": "3dsc", "id": "x", "links": [("mp", "missing")]}])
        # The manifest carries the member data numbers, the reference numbers and every resolved parent claim.
        r1 = next(r for r in man["rows"] if r["members"] == ["1"])
        self.assertEqual((r1["parents"], r1["refnos"], r1["parent_route"]), (["CuLa2O4"], [""], "coefficients (multiplier 2)"))
        self.assertEqual(set(man["rows"][0]), {"exact", "canonical", "oxygen_status", "structure_name", "form_class", "family", "parent", "parents",
                                               "parent_route", "members", "refnos", "component", "fold", "purged", "event_threshold_k", "event",
                                               "high_tc_event", "tc_k", "flags", "assumptions", "earliest_year"})

    def test_conflicting_parent_claims_are_kept_and_anchor_purge_is_order_invariant(self):
        # F-43 (Codex's counterexample): the same unit reported under '(La,Sr)2CuO4' and 'LaSrCuO4' claims two parents.
        base = dict(ma1="La", ma2="1.85", mb1="Sr", mb2="0.15", mc1="Cu", mc2="1", mo1="O", mo2="4", str3="T", shape="1")
        first = H.observation(row(num="1", refno="R1", year="1990", tc="38", name="(La,Sr)2CuO4", **base))
        second = H.observation(row(num="2", refno="R2", year="1991", tc="37", name="LaSrCuO4", **base))
        anchor = {"kind": "anchor", "id": "synthetic-La2CuO4", "parent": "CuLa2O4", "canonical": "Cu0.5 La1 O2", "elements": ["Cu", "La", "O"], "family": "cuprate"}
        results = []
        for order in ([first, second], [second, first]):
            units = H.canonical_units(order)
            self.assertEqual(len(units), 1)
            u = units[0]
            self.assertEqual((u["parent"], u["parents"], u["parent_route"]), ("ambiguous: CuLa2O4 | CuLaO4Sr", ["CuLa2O4", "CuLaO4Sr"], "conflicting parent claims"))
            self.assertEqual(u["parent_claims"], [{"parent": "CuLa2O4", "route": "common formula", "refnos": ["R1"]},
                                                  {"parent": "CuLaO4Sr", "route": "common formula", "refnos": ["R2"]}])
            comps = H.components(units, extra_nodes=[anchor])
            self.assertEqual(len(comps), 1)                                  # the anchor is linked through every claim
            self.assertTrue(next(iter(comps.values()))["purged"])
            assignment = H.assign_folds(comps)
            results.append(H.manifest(units, comps, assignment)["sha256"])
        self.assertEqual(results[0], results[1])                               # report order changes nothing
        # An agreeing pair keeps one parent; the sentinel of a conflict makes no equal-parent edge of its own.
        agree = H.canonical_units([first, H.observation(row(num="3", refno="R3", year="1992", tc="39", name="(La,Sr)2CuO4", **base))])[0]
        self.assertEqual((agree["parent"], agree["parents"], agree["parent_route"]), ("CuLa2O4", ["CuLa2O4"], "common formula"))
        self.assertEqual(H.node_parents({"parent": "ambiguous: A | B"}), [])
        self.assertEqual(H.node_parents({"parents": ["CuLa2O4", "CuLaO4Sr"]}), ["CuLa2O4", "CuLaO4Sr"])
        # A known parent in the training window counts through every claim (temporal new-parent rule).
        split = H.temporal_split([first, second, H.observation(row(num="4", refno="R4", year="2019", tc="30", name="LaSrCuO4", **dict(base, mb2="0.2", ma2="1.8")))], cutoff=2017)
        self.assertEqual((len(split["test_new_units"]), len(split["test_new_parent_units"])), (1, 0))

    def test_support_grids_are_complete_and_count_eligible_components_only(self):
        # F-42 (Codex's counterexample): 20 positives in one component, 20 negatives in another, 8 censored-only components,
        # all cuprate in fold 1: the labelled population holds 2 components, every other fold is reported as 0.
        rows = ([{"family": "cuprate", "fold": 1, "purged": False, "component": "P", "event": 1, "tc_k": 40.0}] * 20 +
                [{"family": "cuprate", "fold": 1, "purged": False, "component": "N", "event": 0, "tc_k": None}] * 20 +
                [{"family": "cuprate", "fold": 1, "purged": False, "component": f"X{i}", "event": "censored", "tc_k": None} for i in range(8)] +
                [{"family": "cuprate", "fold": 2, "purged": True, "component": "Q", "event": 1, "tc_k": 50.0}])
        sup = H.support(rows)
        cell = sup["per_fold"]["cuprate"][1]
        self.assertEqual(cell, {"units": 48, "positives": 20, "negatives": 20, "censored": 8, "regression_units": 20,
                                "components": 10, "labelled_components": 2, "regression_components": 1})
        self.assertEqual(sup["per_fold"]["cuprate"][3]["units"], 0)
        self.assertEqual(sorted(sup["per_fold"]), sorted(H.EVENT_K))
        self.assertEqual(sup["per_fold"]["heavy-fermion"][5]["labelled_components"], 0)
        self.assertEqual(min(sup["per_fold"]["cuprate"][f]["labelled_components"] for f in sup["folds"]), 0)
        self.assertEqual(sup["pooled_oof"]["cuprate"]["labelled_components"], 2)
        self.assertEqual((sup["training"]["cuprate"][1]["positives"], sup["training"]["cuprate"][2]["positives"]), (0, 20))
        gate = H.support_gate(sup)
        self.assertTrue(gate["cuprate"]["auc"].startswith("unsupported: pooled out-of-fold labelled_components 2 < 10; training side of fold 1 positives 0 < 20"))
        self.assertEqual(gate["heavy-fermion"]["mae"].split(";")[0], "unsupported: pooled out-of-fold regression_units 0 < 20")
        # A grid that meets the gate everywhere: 12 labelled components per fold, 10 positives and 10 negatives in each.
        full = [{"family": "iron-nickel", "fold": f, "purged": False, "component": f"C{f}{i}", "event": i % 2, "tc_k": 20.0 if i % 2 else None}
                for f in H.FOLDS for i in range(12)]
        g = H.support_gate(H.support(full))
        self.assertEqual(g["iron-nickel"], {"auc": "supported", "mae": "supported"})   # 6 positives per fold: 30 pooled, 24 on every training side
        short = H.support_gate(H.support([r for r in full if r["fold"] != 5] + [dict(r, event="censored", tc_k=None) for r in full if r["fold"] == 5]))
        self.assertEqual(short["iron-nickel"]["auc"], "unsupported: training side of fold 1 positives 18 < 20; training side of fold 1 negatives 18 < 20; "
                         "training side of fold 2 positives 18 < 20; training side of fold 2 negatives 18 < 20; training side of fold 3 positives 18 < 20; "
                         "training side of fold 3 negatives 18 < 20; training side of fold 4 positives 18 < 20; training side of fold 4 negatives 18 < 20")
        self.assertEqual(g["cuprate"]["auc"].split(";")[0], "unsupported: pooled out-of-fold positives 0 < 20")

    def test_external_nodes_and_exact_3dsc_match(self):
        observations, _ = H.load_observations(H.synthetic_table())
        units = H.modelled_units(observations)
        self.assertEqual(len(units), 7)   # every synthetic unit is in a modelled family
        nodes, match = H.dsc_nodes(H.synthetic_dsc_csv(), units)
        self.assertEqual((match["rows"], match["mp_ids"], match["units_considered"], match["rows_matched_exactly"], match["units_matched_exactly"],
                          match["rows_matched_approximately_only"], match["rows_unmatched"]), (3, 2, 7, 1, 1, 1, 1))
        with self.assertRaisesRegex(ValueError, "unknown node"):   # a link may only point at a unit of the graph
            H.components([u for u in units if u["exact"] != "Cu1 La2 O4"], extra_nodes=nodes)
        self.assertEqual(match["units_matched_exactly_by_family"], {"cuprate": 1})
        la2cuo4 = next(n for n in nodes if n["kind"] == "3dsc" and n["formula"] == "Cu1La2O4")
        self.assertTrue(la2cuo4["exact_match"])
        self.assertEqual(la2cuo4["links"][0], ("mp", "mp-19"))
        self.assertEqual(la2cuo4["links"][1][0], "unit")
        self.assertEqual(next(n for n in nodes if n["kind"] == "mp")["parent"], "CuLa2O4")
        anchors = H.anchor_nodes({"materials": [{"name": "CeCoIn5", "family": "heavy-fermion", "composition": {"Ce": 1, "Co": 1, "In": 5}}]})
        self.assertEqual((anchors[0]["kind"], anchors[0]["parent"], anchors[0]["family"], anchors[0]["canonical"]), ("anchor", "CeCoIn5", "heavy-fermion", "Ce0.2 Co0.2 In1"))
        claims = H.prior_claim_nodes({"materials": [{"formula": "YRu3B2", "kind": "discovery"}, {"system": ["Nb", "Sn"], "kind": "known"}]})
        self.assertEqual((claims[0]["parent"], claims[1]["any_family"], claims[1]["elements"]), ("B2Ru3Y", True, ["Nb", "Sn"]))
        background = H.background_nodes("jid,formula,chemsys\nJVASP-1,LaFeAsO,As-Fe-La-O\n")
        self.assertEqual((background[0]["id"], background[0]["family"], background[0]["parent"]), ("JVASP-1", "iron-nickel", "AsFeLaO"))
        negatives = H.negative_report_nodes({"records": [{"id": "n1", "composition": {"Ba": 1, "Ti": 2, "Sb": 1, "Bi": 1, "O": 1}}]})
        self.assertEqual(negatives[0]["kind"], "negative-report")
        # In the graph: the exact 3DSC row and its MP id join the La2CuO4 unit; the anchor purges CeCoIn5's component; the
        # system claim joins an unmodelled Nb-Sn node whatever the family; a prior claim purges too.
        extra = nodes + anchors + claims + background + negatives + [{"kind": "mp", "id": "mp-nb3sn", "canonical": "Nb1 Sn0.333", "parent": "Nb3Sn", "elements": ["Nb", "Sn"], "family": "other"}]
        modelled = [u for u in units if u["family"] in H.EVENT_K]
        comps = H.components(modelled, extra_nodes=extra)
        by_member = {tuple(m): cid for cid, c in comps.items() for m in c["members"]}
        la = next(u for u in modelled if u["exact"] == "Cu1 La2 O4")
        self.assertEqual(by_member[("3dsc", "0")], by_member[("unit",) + la["key"]])
        self.assertEqual(by_member[("mp", "mp-19")], by_member[("unit",) + la["key"]])
        self.assertEqual(by_member[("3dsc", "2")], by_member[("prior-claim", "1:Nb-Sn")])
        self.assertEqual(by_member[("mp", "mp-nb3sn")], by_member[("prior-claim", "1:Nb-Sn")])
        self.assertTrue(comps[by_member[("prior-claim", "1:Nb-Sn")]]["purged"])
        ce = next(u for u in modelled if u["exact"] == "Ce1 Co1 In5")
        self.assertTrue(comps[by_member[("unit",) + ce["key"]]]["purged"])
        self.assertEqual(by_member[("background", "JVASP-1")], by_member[("unit",) + next(u for u in modelled if "Fe" in u["elements"])["key"]])
        report = H.audit(observations, extra_nodes=extra)
        self.assertEqual(report["components"]["purged_units"], 1)
        self.assertEqual(report["components"]["purged_units_by_family"], {"heavy-fermion": 1})
        self.assertEqual(report["components"]["purge_detail"][0]["protected_nodes"], ["anchor:0:CeCoIn5"])
        self.assertEqual(report["components"]["purge_detail"][0]["units_by_family"], {"heavy-fermion": 1})
        self.assertGreaterEqual(report["components"]["with_external_nodes"], 3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "results").mkdir()
            (root / "data" / "hurricane_anchors.json").write_text(json.dumps({"materials": [{"name": "CeCoIn5", "composition": {"Ce": 1, "Co": 1, "In": 5}}]}), encoding="utf-8")
            (root / "data" / "prior_claims.json").write_text(json.dumps({"materials": [{"system": ["Nb", "Sn"]}]}), encoding="utf-8")
            (root / "results" / "hurricane_round4_background.csv").write_text("jid,formula,chemsys\nJVASP-1,LaFeAsO,As-Fe-La-O\n", encoding="utf-8")
            built, info = H.project_nodes(root, units, H.synthetic_dsc_csv())
            self.assertEqual((info["anchors"], info["prior_claims"], info["background"], info["files"]["data/hosono2015_negatives.json"], info["3dsc"]["rows_matched_exactly"]), (1, 1, 1, "missing", 1))
            self.assertEqual(info["by_kind"], {"anchor": 1, "prior-claim": 1, "background": 1, "3dsc": 3, "mp": 2})
            self.assertEqual(len(info["files"]["data/hurricane_anchors.json"]["sha256"]), 64)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                H.fetch_dsc(tmp, get=lambda url: b"not the file")

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
               H.observation(row(num="5", year="", tc="30", ma1="Sm", ma2="1", mb1="Fe", mb2="1", mc1="As", mc2="1", mo1="O", mo2="1", str3="oxypnictide")),
               H.observation(row(num="6", year="2021", tc="50", ma1="Y", ma2="1", mb1="Ba", mb2="2", mc1="Cu", mc2="3", mo1="O", mo2="z", str3="Y123"))]  # unresolved parent
        split = H.temporal_split(obs, cutoff=2017)
        self.assertEqual(len(split["train_units"]), 1)
        self.assertEqual(split["train_units"][0]["tc_k"], 26.0)                       # the 2019 report never enters the training median
        self.assertEqual([u["members"] for u in split["repeat_report_units"]], [["2"]])
        self.assertEqual(sorted(u["members"][0] for u in split["test_new_units"]), ["3", "4", "6"])
        self.assertEqual([u["members"] for u in split["test_new_parent_units"]], [["4"]])   # an unresolved parent is not a new parent
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
        self.assertEqual(report["rows"], 12)
        self.assertEqual(report["status"], {"admitted": 7, "excluded": 3, "quarantined": 2})
        self.assertEqual(report["reasons"]["hydrogen-containing compound (project rule)"], 1)
        self.assertEqual(report["evidence_kinds"], {"positive": 9, "negative": 2, "mixed": 1})
        self.assertEqual(report["assumptions"], {"A1": 1, "A2": 12, "A3": 4})
        self.assertEqual(report["parent_routes"]["unresolved: oxygen content not instantiated by any source field"], 1)
        self.assertEqual(report["units"]["events"]["cuprate"], {"1": 2, "0": 1})
        self.assertEqual(report["event_labels"]["heavy-fermion"], {"1": 1, "0": 1})
        self.assertEqual(report["replicated_extremes"], 0)
        self.assertIn("manifest_sha256", report)
        json.dumps(report)   # serialisable
        families = {o["num"]: (o["family"], o["family_status"]) for o in observations}
        self.assertEqual(families["10"], ("other-oxide", "by-structure (nickelate analogue of a cuprate structure type)"))
        self.assertEqual(families["9"][0], "cuprate")
        by_num = {o["num"]: o for o in observations}
        self.assertEqual(by_num["10"]["status"], "excluded")   # a film
        self.assertEqual((by_num["11"]["status"], by_num["11"]["assumptions"], by_num["11"]["parent"]), ("admitted", ["A1", "A2", "A3"], "unresolved"))
        self.assertEqual(by_num["12"]["reason"], "floor with another positive Tc channel and no recommended tc")


if __name__ == "__main__":
    unittest.main()
