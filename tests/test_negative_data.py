import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import negative_data as ND


class NegativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.document = ND.load()
        self.record = copy.deepcopy(self.document["records"][0])

    def test_source_checked_records_keep_unknown_conditions(self):
        report = ND.validate_document(self.document)
        self.assertEqual(report["validated_observations"], 2)
        self.assertEqual(report["errors"], {})
        self.assertIsNone(self.record["measurement"]["pressure_GPa"])
        self.assertNotIn("tc", self.record)

    def test_parent_target_cannot_consume_a_sample_null(self):
        exported = ND.export_labels(self.document, target=ND.PARENT_TARGET, threshold_K=2,
                                    pressure_GPa=None, sample_form=None, field_T=None)
        self.assertEqual(exported["accepted"], [])
        self.assertEqual(len(exported["excluded"]), 2)
        self.assertTrue(all("parent doping potential" in row["reasons"][0] for row in exported["excluded"]))

    def test_failed_synthesis_is_rejected(self):
        self.record["synthesis_status"] = "failed"
        self.assertIn("failed or unknown synthesis is not a measured negative", ND.validate_record(self.record, self.document["sources"]))

    def test_missing_temperature_is_rejected(self):
        self.record["measurement"]["t_min_K"] = None
        self.assertIn("a positive measured t_min_K is required", ND.validate_record(self.record, self.document["sources"]))

    def test_unconditional_zero_is_rejected(self):
        self.record["tc"] = 0
        self.assertTrue(any("unconditional" in e for e in ND.validate_record(self.record, self.document["sources"])))

    def test_expanded_formula_must_agree(self):
        self.record["composition"]["Bi"] = 1
        self.assertIn("composition disagrees with expanded formula", ND.validate_record(self.record, self.document["sources"]))
        for invalid in ("BaTi2(Sb0.6Bi0.4)2O", "Fe1-xCox", "Xx2O", "Fe0O"):
            with self.assertRaises(ValueError):
                ND.composition(invalid)

    def test_temperature_censoring_and_condition_matching(self):
        # A hypothetical complete record checks export semantics; it is never saved as evidence.
        self.record["measurement"].update(pressure_GPa=0, field_T=0, t_max_K=300)
        self.record["sample_form"] = "bulk"
        query = dict(target=ND.SAMPLE_TARGET, threshold_K=2, pressure_GPa=0, sample_form="bulk", field_T=0)
        self.assertEqual(ND.eligibility(self.record, **query), [])
        self.assertIn("measurement does not reach the target threshold", ND.eligibility(self.record, **dict(query, threshold_K=1)))
        self.assertIn("different pressure_GPa", ND.eligibility(self.record, **dict(query, pressure_GPa=10)))
        self.assertIn("different sample_form", ND.eligibility(self.record, **dict(query, sample_form="thin_film")))

    def test_missing_conditions_do_not_export_as_ambient(self):
        exported = ND.export_labels(self.document, target=ND.SAMPLE_TARGET, threshold_K=2,
                                    pressure_GPa=0, sample_form="bulk", field_T=0)
        self.assertEqual(exported["accepted"], [])
        self.assertIn("unknown pressure_GPa", exported["excluded"][0]["reasons"])

    def test_nan_strings_and_boolean_conditions_cannot_match_zero(self):
        self.record["measurement"].update(pressure_GPa=0, field_T=0, t_max_K=300)
        self.record["sample_form"] = "bulk"
        for value in (float("nan"), float("inf"), "unknown", True, -1):
            broken = copy.deepcopy(self.record)
            broken["measurement"]["field_T"] = value
            self.assertTrue(ND.validate_record(broken, self.document["sources"]))
            reasons = ND.eligibility(self.record, target=ND.SAMPLE_TARGET, threshold_K=2,
                                     pressure_GPa=value, sample_form="bulk", field_T=0)
            self.assertIn("invalid pressure_GPa", reasons)

    def test_duplicate_ids_are_rejected(self):
        self.document["records"].append(copy.deepcopy(self.document["records"][0]))
        with self.assertRaises(ValueError):
            ND.export_labels(self.document, target=ND.SAMPLE_TARGET, threshold_K=2,
                             pressure_GPa=0, sample_form="bulk", field_T=0)


if __name__ == "__main__":
    unittest.main()
