"""Synthetic source bytes/curves only; no scientific evidence or model fits."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ml import normal_state as N


class NormalStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.policy = N.policy_document("2025-01-01T00:00:00Z")
        self.conditions = dict(sample_id="synthetic-sample", formula="Bi", sample_form="bulk", phase="synthetic-phase",
                               pressure_GPa=2., field_T=0., t_min_K=2., t_max_K=300., method="resistivity")
        self.reference = dict(doi=None, url="https://example.invalid/synthetic-fixture", inspection_status="full_text_inspected",
                              source_kind="primary_experiment", publication_date="2024-12-01", locator="Synthetic fixture table")
        points = [{"temperature_k": t, "value": 1 + .01 * t + .00001 * (t - 225) ** 2,
                   "source_locator": f"Synthetic CSV row {i + 2}, columns T_K and rho"}
                  for i, t in enumerate([2., 150., 175., 200., 225., 250., 275., 300.])]
        points[0]["value"] = 0.  # An outcome-region raw point; never a predictor.
        self.curve = dict(curve_id="fixture-curve", source_id="fixture-source", material_id="fixture-material",
                          specimen_id="fixture-source:physical-sample-A", series_id="synthetic-pressure-series",
                          measurement_run_id="fixture-run", trace_id="sheet1:T_K-rho", varied_axes=["temperature_k"],
                          observed_at="2025-02-01T00:00:00Z", quantity="resistivity", unit="microohm cm",
                          conditions=self.conditions, fixed_coordinates=dict(pressure_gpa=2., magnetic_field_t=0., doping_fraction=0., strain=None),
                          normal_state_status="verified_normal", normalization={"kind": "none"},
                          normal_state_evidence={"locator": "Synthetic normal-region statement", "statement": "Synthetic normal-state range",
                                                 "verified_range_k": [150., 300.]}, points=points)
        raw = "T_K,rho\n" + "\n".join(f"{p['temperature_k']},{p['value']}" for p in points) + "\n"
        (self.root / "fixture.csv").write_bytes(raw.encode())
        self.source = dict(source_id="fixture-source", raw_path="fixture.csv", sha256=hashlib.sha256(raw.encode()).hexdigest(), reference=self.reference)
        self.registry = N.source_registry({"sources": [self.source]}, source_root=self.root)

    def ledger(self, curve=None, *, same_run=False, target_changes=None):
        curve = copy.deepcopy(curve or self.curve)
        condition = copy.deepcopy(curve["conditions"])
        condition.update(doping_fraction=curve["fixed_coordinates"]["doping_fraction"], strain=curve["fixed_coordinates"]["strain"])
        target = dict(material_id=curve["material_id"], observed_at="2025-02-01T00:00:00Z", statement="Synthetic measured transition, not scientific data",
                      observation_type="sample_superconductivity", assertion_status="source_checked", outcome=True,
                      evidence_kind="measured_transition", tc_K=8., tc_criterion="resistive_midpoint", conditions=condition, reference=self.reference)
        link = dict(curve_id=curve["curve_id"], specimen_id=curve["specimen_id"], same_physical_specimen=True,
                    assertion_status="source_checked", source_locator="Synthetic explicit same specimen/trace proof",
                    curve_sample_id=curve["conditions"]["sample_id"], target_sample_id=target["conditions"]["sample_id"],
                    scope="same_run_measured_tc" if same_run else "same_specimen_condition_matched")
        if same_run:
            for key in ("measurement_run_id", "trace_id", "varied_axes"):
                target[key], link[key] = copy.deepcopy(curve[key]), copy.deepcopy(curve[key])
            target["raw_source_sha256"] = link["raw_source_sha256"] = self.source["sha256"]
            target["derived_from_curve_id"] = curve["curve_id"]
            link["same_raw_trace"] = True
        target.update(target_changes or {})
        path = self.root / f"ledger-{len(list(self.root.glob('ledger-*')))}.jsonl"
        ledger = N.F.FeedbackLedger(path, clock=lambda: datetime(2025, 2, 3, tzinfo=timezone.utc))
        appended = ledger.append_observations(N.curve_observations(curve, self.registry, self.policy) + [target])
        link["target_observation_hash"] = appended[-1]["hash"]
        return ledger.read(), link

    def join(self, curve, events, link):
        return N.join_measured_targets(events, curves=[curve], features=[N.extract_features(curve, self.registry, self.policy)],
                                        links=[link], registry=self.registry, policy=self.policy, as_of="2025-02-04T00:00:00Z")

    def test_raw_source_hash_and_path_are_verified(self):
        wrong = copy.deepcopy(self.source)
        wrong["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            N.source_registry({"sources": [wrong]}, source_root=self.root)
        wrong["raw_path"] = "../outside.csv"
        with self.assertRaisesRegex(ValueError, "escaped collection root"):
            N.source_registry({"sources": [wrong]}, source_root=self.root)

    def test_features_are_scale_free_and_ignore_outcome_temperature_region(self):
        before = N.extract_features(self.curve, self.registry, self.policy)
        changed = copy.deepcopy(self.curve)
        changed["points"][0]["value"] = 100000.
        changed["tc_K"] = 200.  # Extra metadata cannot enter the feature allowlist.
        for point in changed["points"][1:]:
            point["value"] *= 1000
        after = N.extract_features(changed, self.registry, self.policy)
        self.assertEqual(before["status"], "ready")
        for key in before["features"]:
            self.assertAlmostEqual(before["features"][key], after["features"][key])
        self.assertNotIn(0, before["used_point_indices"])

    def test_no_250_anchor_extrapolation_for_short_device_curve(self):
        curve = copy.deepcopy(self.curve)
        curve["points"] = [p for p in curve["points"] if p["temperature_k"] <= 200]
        result = N.extract_features(curve, self.registry, self.policy)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["features"], {})

    def test_wide_interpolation_gaps_and_outcome_normalization_fail(self):
        with self.assertRaisesRegex(ValueError, "bracket too wide"):
            N._interpolate(np.array([150., 300.]), np.array([1., 2.]), 200., 50.)
        curve = copy.deepcopy(self.curve)
        curve["normalization"] = {"kind": "published_constant_scale", "denominator": "R(Tc)"}
        self.assertEqual(N.extract_features(curve, self.registry, self.policy)["status"], "insufficient_data")
        curve["quantity"] = "heat_capacity_jump"
        with self.assertRaisesRegex(ValueError, "SC outcomes"):
            N.extract_features(curve, self.registry, self.policy)

    def test_verified_range_not_merely_anchors_limits_all_interpolation_inputs(self):
        curve = copy.deepcopy(self.curve)
        curve["normal_state_evidence"]["verified_range_k"] = [200., 250.]
        result = N.extract_features(curve, self.registry, self.policy)
        self.assertEqual(result["status"], "insufficient_data")  # Three verified points are fewer than frozen five.

    def test_unknown_strain_export_is_scoped_and_default_stays_strict(self):
        events, link = self.ledger()
        self.assertEqual(N.F.legal_precursor_export(events, as_of="2025-02-04T00:00:00Z")["accepted"], [])
        scoped = N.scoped_precursor_export(events, policy=self.policy, as_of="2025-02-04T00:00:00Z", same_specimen_links=[link])
        self.assertEqual(len(scoped["accepted"]), 7)
        self.assertTrue(all(not row["strict_feature_eligible"] for row in scoped["accepted"]))
        self.assertTrue(all(row["payload"]["coordinates"]["strain"] is None for row in scoped["accepted"]))
        self.assertEqual(len(self.join(self.curve, events, link)["accepted"]), 1)

    def test_same_run_allows_unreported_conditions_without_fabricating_zero(self):
        curve = copy.deepcopy(self.curve)
        for key in ("pressure_GPa", "field_T", "phase"):
            curve["conditions"][key] = None
        for key in ("pressure_gpa", "magnetic_field_t", "doping_fraction"):
            curve["fixed_coordinates"][key] = None
        events, link = self.ledger(curve, same_run=True)
        joined = self.join(curve, events, link)["accepted"]
        self.assertEqual(len(joined), 1)
        self.assertIsNone(joined[0]["conditions"]["pressure_GPa"])
        self.assertTrue(joined[0]["missing_condition_flags"]["pressure_gpa"])
        self.assertFalse(joined[0]["axis_learning_allowed"]["pressure_gpa"])
        self.assertEqual(N.F.legal_precursor_export(events, as_of="2025-02-04T00:00:00Z")["accepted"], [])

    def test_unknown_pressure_cannot_cross_trace_or_sample_link(self):
        curve = copy.deepcopy(self.curve)
        curve["conditions"]["pressure_GPa"] = curve["fixed_coordinates"]["pressure_gpa"] = None
        events, link = self.ledger(curve)
        self.assertEqual(self.join(curve, events, link)["accepted"], [])
        events, link = self.ledger(curve, same_run=True)
        link["trace_id"] = "different-column-in-the-same-file"
        self.assertEqual(self.join(curve, events, link)["accepted"], [])

    def test_same_run_binding_checks_run_hash_controlled_axes_and_known_conflicts(self):
        for key, value in (("measurement_run_id", "wrong-run"), ("raw_source_sha256", "0" * 64), ("varied_axes", ["temperature_k", "pressure_gpa"])):
            with self.subTest(key=key):
                events, link = self.ledger(same_run=True)
                link[key] = value
                self.assertEqual(self.join(self.curve, events, link)["accepted"], [])
        events, link = self.ledger(same_run=True, target_changes={"conditions": dict(self.conditions, pressure_GPa=9., doping_fraction=0., strain=None)})
        self.assertEqual(self.join(self.curve, events, link)["accepted"], [])
        curve = copy.deepcopy(self.curve)
        curve["conditions"]["pressure_GPa"] = curve["fixed_coordinates"]["pressure_gpa"] = None
        curve["varied_axes"] = ["temperature_k", "pressure_gpa"]
        events, link = self.ledger(curve, same_run=True)
        self.assertEqual(self.join(curve, events, link)["accepted"], [])

    def test_future_targets_and_unknown_publication_cannot_cross_feature_cutoff(self):
        curve = copy.deepcopy(self.curve)
        curve["conditions"]["phase"] = None  # This nuisance exception requires an available exact link.
        old_events, link = self.ledger(curve)
        future_target = copy.deepcopy(old_events[-1]["payload"])
        future_target["observed_at"] = "2025-02-05T00:00:00Z"
        future_target["reference"]["publication_date"] = "2025-02-05"
        path = self.root / "future-target.jsonl"
        early = N.F.FeedbackLedger(path, clock=lambda: datetime(2025, 2, 3, tzinfo=timezone.utc))
        early.append_observations(N.curve_observations(curve, self.registry, self.policy))
        later = N.F.FeedbackLedger(path, clock=lambda: datetime(2025, 2, 6, tzinfo=timezone.utc))
        event = later.append_observation(future_target)
        link["target_observation_hash"] = event["hash"]
        events = later.read()
        self.assertEqual(self.join(curve, events, link)["accepted"], [])
        exported = N.scoped_precursor_export(events, policy=self.policy, as_of="2025-02-04T00:00:00Z", same_specimen_links=[link])
        self.assertEqual(exported["accepted"], [])
        unknown_reference = dict(self.reference, publication_date=None)
        events, link = self.ledger(target_changes={"reference": unknown_reference})
        self.assertEqual(self.join(self.curve, events, link)["accepted"], [])

    def test_future_corrections_do_not_remove_past_points_targets_or_cli_target_ids(self):
        events, link = self.ledger(target_changes={"normal_collection_target_id": "fixture-target"})
        path = next(self.root.glob("ledger-*.jsonl"))
        later = N.F.FeedbackLedger(path, clock=lambda: datetime(2030, 1, 4, tzinfo=timezone.utc))
        target = copy.deepcopy(events[-1]["payload"])
        target.update(tc_K=9., observed_at="2030-01-04T00:00:00Z", correction_reason="Synthetic future correction")
        later.append_observation(target, supersedes=events[-1]["hash"])
        point = copy.deepcopy(events[3]["payload"])
        point.update(value=100., observed_at="2030-01-04T00:00:00Z", correction_reason="Synthetic future point correction")
        later.append_observation(point, supersedes=events[3]["hash"])
        historical = self.join(self.curve, later.read(), link)["accepted"]
        self.assertEqual(len(historical), 1)
        self.assertEqual(historical[0]["tc_K"], 8.)
        del link["target_observation_hash"]
        link["target_id"] = "fixture-target"
        result = N.ingest_collection({"curves": [self.curve], "links": [link]}, registry=self.registry, policy=self.policy,
                                     ledger_path=path, output_dir=self.root / "past-audit", as_of="2025-02-04T00:00:00Z")
        self.assertEqual(result["linked_measured_tc_records"], 1)
        self.assertEqual(result["unresolved_links"], [])

    def test_missing_criterion_and_censored_null_never_create_zero_tc(self):
        events, link = self.ledger(target_changes={"tc_criterion": None})
        self.assertEqual(self.join(self.curve, events, link)["accepted"], [])
        events, link = self.ledger(target_changes={"outcome": False, "evidence_kind": "measured_no_transition", "tc_K": None})
        result = self.join(self.curve, events, link)
        self.assertEqual(result["accepted"], [])
        self.assertIn("not Tc=0", " ".join(result["excluded"][0]["reasons"]))

    def test_composition_quality_is_unknown_without_explicit_checked_link_evidence(self):
        events, link = self.ledger()
        row = self.join(self.curve, events, link)["accepted"][0]
        self.assertEqual(row["composition_quality"], "unknown")
        self.assertEqual(N.primary_pilot_cohort([row])[0], [])
        link.update(composition_quality="nominal_sample_formula", composition_source_locator="Synthetic primary sample composition statement")
        row = self.join(self.curve, events, link)["accepted"][0]
        self.assertEqual(row["composition_quality"], "nominal_sample_formula")
        self.assertEqual(len(N.primary_pilot_cohort([row])[0]), 1)

    def test_points_must_exist_in_eligible_verified_ledger_before_join(self):
        events, link = self.ledger()
        only_target = [events[-1]]
        # An edited/truncated chain fails rather than acting like eligible evidence.
        with self.assertRaises(N.F.LedgerIntegrityError):
            self.join(self.curve, only_target, link)
        feature = N.extract_features(self.curve, self.registry, self.policy)
        feature["features"]["log_ratio_250_200"] = 100.
        result = N.join_measured_targets(events, curves=[self.curve], features=[feature], links=[link], registry=self.registry,
                                         policy=self.policy, as_of="2025-02-04T00:00:00Z")
        self.assertEqual(result["accepted"], [])

    def test_modified_curve_cannot_reuse_old_ledger_point_indices(self):
        events, link = self.ledger()
        changed = copy.deepcopy(self.curve)
        changed["points"][3]["value"] += 20.
        self.assertEqual(self.join(changed, events, link)["accepted"], [])
        changed = copy.deepcopy(self.curve)
        changed["points"][3]["source_locator"] = "different raw column"
        self.assertEqual(self.join(changed, events, link)["accepted"], [])

    def test_curve_hash_is_computed_once_not_per_point(self):
        actual = N.sha256
        with patch.object(N, "sha256", wraps=actual) as traced:
            payloads = N.curve_observations(self.curve, self.registry, self.policy)
        self.assertEqual(sum(c.args[0] is self.curve for c in traced.call_args_list), 1)
        self.assertEqual(sum(c.args[0] is self.policy for c in traced.call_args_list), 1)
        self.assertEqual(len(payloads), len(self.curve["points"]))

    def test_measured_point_field_is_recorded_and_multiaxis_curve_cannot_be_fixed_rt(self):
        curve = copy.deepcopy(self.curve)
        curve["conditions"]["field_T"] = curve["fixed_coordinates"]["magnetic_field_t"] = None
        for index, point in enumerate(curve["points"]):
            point["coordinates"] = {"magnetic_field_t": index * .01}
            point["coordinate_provenance"] = {"magnetic_field_t": {"source_unit": "Oe", "canonical_unit": "T",
                                                                  "conversion": "Applied-field convention: Oe x 1e-4", "source_locator": "Synthetic H column"}}
            point["field_orientation"] = {"signed_field_oe": -index * 100., "sign_along_instrument_axis": -1, "crystal_orientation": None}
            point["source_unit_conversion"] = "Explicit magnitude conversion; signed source component preserved, internal B unknown"
        observations = N.curve_observations(curve, self.registry, self.policy)
        self.assertEqual(observations[3]["coordinates"]["magnetic_field_t"], .03)
        self.assertEqual(observations[3]["conditions"]["field_T"], .03)
        self.assertEqual(observations[3]["coordinate_provenance"], curve["points"][3]["coordinate_provenance"])
        self.assertEqual(observations[3]["field_orientation"]["signed_field_oe"], -300.)
        self.assertEqual(N.extract_features(curve, self.registry, self.policy)["status"], "insufficient_data")
        curve["fixed_coordinates"]["magnetic_field_t"] = curve["conditions"]["field_T"] = 0.
        with self.assertRaisesRegex(ValueError, "conflicts with known fixed"):
            N.curve_observations(curve, self.registry, self.policy)

    def test_temperature_replicates_do_not_inflate_independent_samples(self):
        curve = copy.deepcopy(self.curve)
        curve["points"] += copy.deepcopy(curve["points"])
        f = N.extract_features(curve, self.registry, self.policy)
        self.assertEqual(f["unique_temperature_count"], 7)
        self.assertEqual(f["statistical_sample_count"], 1)

    def test_group_components_union_sources_systems_samples_and_series(self):
        rows = []
        for i in range(6):
            rows.append(dict(curve_id=f"curve-{i}", chemical_system=f"X-{i}", source_identity=f"doi:{i}",
                             specimen_id=f"sample-{i}", series_id=None, conditions=dict(pressure_GPa=0., field_T=0., phase="a"),
                             fixed_coordinates=dict(pressure_gpa=0., magnetic_field_t=0., doping_fraction=0., strain=None), tc_criterion="midpoint"))
        self.assertEqual(len(N.independent_components(rows)), 6)
        self.assertEqual(N.cohort_audit(rows, self.policy)["status"], "pending_split_and_criterion_freeze")
        rows[1]["source_identity"] = rows[0]["source_identity"]
        rows[2]["chemical_system"] = rows[1]["chemical_system"]
        self.assertEqual(len(N.independent_components(rows)), 4)
        self.assertEqual(N.cohort_audit(rows, self.policy)["status"], "insufficient_data")

    def test_secondary_units_stay_distinct_and_low_temperature_data_do_not_move_window(self):
        curve = copy.deepcopy(self.curve)
        curve["quantity"], curve["unit"] = "magnetic_susceptibility", "emu per mol"
        result = N.extract_features(curve, self.registry, self.policy)
        self.assertEqual(result["unit"], "emu per mol")
        self.assertIn("value_200", result["features"])
        curve["points"] = [{"temperature_k": t, "value": -1., "source_locator": "Synthetic low-T point"} for t in (2., 3., 4., 5., 6., 7.)]
        self.assertEqual(N.extract_features(curve, self.registry, self.policy)["status"], "insufficient_data")

    def test_ingestion_records_real_measurement_payloads_even_with_zero_target_labels(self):
        ledger_path = self.root / "actual-import-fixture.jsonl"
        result = N.ingest_collection({"curves": [self.curve], "targets": [], "links": []}, registry=self.registry, policy=self.policy,
                                     ledger_path=ledger_path, output_dir=self.root / "audit", append=True)
        self.assertEqual(result["ledger_events_added"], len(self.curve["points"]))
        self.assertEqual(result["linked_measured_tc_records"], 0)
        self.assertEqual(result["cohort"]["status"], "insufficient_data")
        self.assertEqual(result["models_fitted"], 0)
        again = N.ingest_collection({"curves": [self.curve]}, registry=self.registry, policy=self.policy,
                                    ledger_path=ledger_path, output_dir=self.root / "audit", append=True)
        self.assertEqual(again["ledger_events_added"], 0)

    def test_policy_freeze_is_idempotent_and_refuses_window_changes(self):
        document = N.freeze_policy(self.root / "protocol", defined_at=self.policy["defined_at"])
        self.assertEqual(N.freeze_policy(self.root / "protocol"), document)
        changed = copy.deepcopy(document)
        changed["window_k"] = [10., 20.]
        with self.assertRaisesRegex(ValueError, "frozen policy"):
            N.validate_policy(changed)

    def pilot_records(self):
        formulas = ["Bi", "Sn", "PtSb", "NbS2", "MgB2", "Al"]
        rows = []
        for i, formula in enumerate(formulas):
            rows.append(dict(curve_id=f"synthetic-pilot-{i}", chemical_system="-".join(sorted(N.F.ND.composition(formula))),
                             source_identity=f"synthetic-source-{i}", specimen_id=f"synthetic-specimen-{i}", series_id=None,
                             quantity="resistivity", unit="synthetic-unit", conditions=dict(formula=formula, phase="synthetic", pressure_GPa=0., field_T=0.),
                             fixed_coordinates=dict(pressure_gpa=0., magnetic_field_t=0., doping_fraction=0., strain=None),
                             features={k: (.01 + i * .005) for k in N.BASE_POLICY["transport_features"]},
                             axis_learning_allowed={k: True for k in N.PILOT_CONDITIONS}, matching_scope="same_run_measured_tc",
                             policy_sha256=N.sha256(self.policy),
                             composition_quality="reported_sample_formula", tc_criterion="resistive_midpoint", tc_K=float(i + 1)))
        return rows

    def test_primary_rejects_proxy_composition_and_unknown_criterion(self):
        rows = self.pilot_records()
        rows[0]["composition_quality"] = "replica_EDS_proxy"
        rows[1]["tc_criterion"] = "midpoint"  # Ambiguous word is not an explicit alias.
        accepted, excluded = N.primary_pilot_cohort(rows)
        self.assertEqual(len(accepted), 4)
        self.assertEqual(len(excluded), 2)

    def test_too_few_groups_or_training_samples_fits_zero_models(self):
        with patch("sklearn.linear_model.Ridge.fit", side_effect=AssertionError("must not fit")):
            report = N.fit_measured_pilot(self.pilot_records()[:5], policy=self.policy, output_dir=self.root / "blocked-pilot", allow_fit=True, synthetic=True)
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["models_fitted"], 0)
        report = N.fit_measured_pilot(self.pilot_records(), policy=self.policy, output_dir=self.root / "not-authorized", synthetic=True)
        self.assertEqual(report["models_fitted"], 0)

    def test_unknown_condition_has_zero_centered_feature_not_physical_zero(self):
        scale = N.PilotScale().fit(np.array([[1.], [2.], [np.nan]]))
        np.testing.assert_array_equal(scale.transform([[np.nan]]), [[0.]])
        self.assertEqual(scale.mean[0], 1.5)

    def test_detached_real_fit_and_wrong_policy_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "detached fitting is disabled"):
            N.fit_measured_pilot(self.pilot_records(), policy=self.policy, output_dir=self.root / "detached", allow_fit=True)
        records = self.pilot_records()
        records[0]["policy_sha256"] = "0" * 64
        accepted, excluded = N.primary_pilot_cohort(records, expected_policy_sha256=N.sha256(self.policy))
        self.assertEqual(len(accepted), 5)
        self.assertIn("different or unbound extraction policy", excluded[0]["reasons"][0])

    def test_real_evidence_route_rejoins_current_sources_and_cannot_reuse_modified_curve(self):
        events, link = self.ledger()
        link.update(composition_quality="nominal_sample_formula", composition_source_locator="Synthetic composition source")
        path = next(self.root.glob("ledger-*.jsonl"))
        evidence = dict(registry_document={"sources": [self.source]}, source_root=self.root,
                        collection={"curves": [self.curve], "links": [link]}, ledger_path=path,
                        as_of="2025-02-04T00:00:00Z")
        records, binding = N.verified_pilot_records(evidence, policy=self.policy)
        self.assertEqual(len(records), 1)
        self.assertEqual(binding["historical_ledger_head"], events[-1]["hash"])
        report = N.fit_measured_pilot(policy=self.policy, output_dir=self.root / "source-bound-gate", evidence=evidence, allow_fit=True)
        self.assertEqual(report["models_fitted"], 0)
        self.assertEqual(report["status"], "insufficient_data")
        changed = copy.deepcopy(evidence)
        changed["collection"]["curves"][0]["points"][3]["value"] += 100.
        self.assertEqual(N.verified_pilot_records(changed, policy=self.policy)[0], [])

    def test_synthetic_pilot_uses_same_loco_cohort_and_held_label_cannot_change_its_fit(self):
        rows = self.pilot_records()
        a = N.fit_measured_pilot(rows, policy=self.policy, output_dir=self.root / "synthetic-pilot-a", allow_fit=True, synthetic=True)
        changed = copy.deepcopy(rows)
        changed[0]["tc_K"] = 10000.
        b = N.fit_measured_pilot(changed, policy=self.policy, output_dir=self.root / "synthetic-pilot-b", allow_fit=True, synthetic=True)
        self.assertEqual(a["status"], "completed_exploratory")
        self.assertTrue(a["synthetic"])
        self.assertFalse(a["adopted"])
        fold_a = next(f for f in a["folds"] if rows[0]["curve_id"] in f["test_curve_ids"])
        fold_b = next(f for f in b["folds"] if rows[0]["curve_id"] in f["test_curve_ids"])
        for design in ("baseline", "with_normal"):
            for key in ("coefficients", "intercept", "train_mean", "train_std", "keep"):
                self.assertEqual(fold_a["designs"][design][key], fold_b["designs"][design][key])
            self.assertEqual(a["predictions"][0][design], b["predictions"][0][design])
        self.assertEqual(a["paired_bootstrap"]["resamples"], 1000)


if __name__ == "__main__":
    unittest.main()
