"""Synthetic evidence fixtures only; no scientific observations are committed."""
import contextlib
import copy
import hashlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest

from ml import feedback as F


def conditions(**changes):
    out = dict(sample_id="synthetic-sample-A", formula="FeSe", sample_form="bulk",
               phase="synthetic-phase-A", pressure_GPa=0.0, t_min_K=1.0,
               t_max_K=300.0, field_T=0.0, method="resistivity")
    out.update(changes)
    return out


def reference(**changes):
    out = dict(doi=None, url="https://example.invalid/synthetic-fixture",
               inspection_status="full_text_inspected", source_kind="primary_experiment",
               publication_date="2025-01-01", locator="Synthetic fixture, Fig. 1")
    out.update(changes)
    return out


def snapshot(**changes):
    out = dict(material_id="fixture-1", model_version="synthetic-model-v1", run_id="fixture-run",
               source="synthetic-test", predicted_at="2024-01-01T00:00:00Z",
               score=0.9, score_type="sample_probability", target=F.SAMPLE_TARGET,
               threshold_K=2.0, decision_threshold=0.5, conditions=conditions())
    out.update(changes)
    return out


def observation(**changes):
    out = dict(material_id="fixture-1", observed_at="2025-02-01T00:00:00Z",
               statement="Synthetic measured fixture, not a scientific assertion",
               observation_type="sample_superconductivity", assertion_status="source_checked",
               outcome=True, evidence_kind="measured_transition", tc_K=8.0,
               conditions=conditions(), reference=reference())
    out.update(changes)
    return out


def negative(**changes):
    out = observation(outcome=False, tc_K=None, evidence_kind="measured_no_transition")
    out.update(changes)
    return out


def normal(**changes):
    out = observation(observation_type="normal_state_measurement", outcome=None,
                      quantity="resistivity", value=4.2, unit="microohm cm",
                      normal_state_status="verified_normal",
                      coordinates=dict(temperature_k=100.0, pressure_gpa=0.0,
                                       doping_fraction=0.0, strain=0.0, magnetic_field_t=0.0),
                      feature_window=dict(kind="absolute_predeclared", min_K=90.0,
                                          max_K=110.0, defined_at="2024-01-01T00:00:00Z"))
    out.pop("tc_K")
    out.pop("evidence_kind")
    out.update(changes)
    return out


def candidate(ident="fixture-1", **changes):
    out = dict(material_id=ident, score=.9, score_type="sample_probability", conditions=conditions())
    out.update(changes)
    return out


RAW_COMPUTATION = b"synthetic Allen-Dynes fixture; not a physical measurement\n"


def computational_conditions(**changes):
    out = conditions(sample_id=None, t_min_K=None, t_max_K=None, method="DFPT",
                     structure_id="synthetic-structure-1", structure_hash="a" * 64,
                     doping_fraction=0.0, strain=0.0)
    out.update(changes)
    return out


def theory(**changes):
    out = dict(method="Allen-Dynes", mu_star=.1,
               component_units={"lambda": "dimensionless", "omega_log": "K", "tc_K": "K"},
               source_hash=hashlib.sha256(RAW_COMPUTATION).hexdigest())
    out.update(changes)
    return out


def computed(**changes):
    out = observation(observation_type="computed_superconductivity", outcome=None, tc_K=4.0,
                      conditions=computational_conditions(), theory=theory(),
                      reference=reference(source_kind="primary_computation", inspection_status="data_inspected"))
    out.pop("evidence_kind")
    out.update(changes)
    return out


def computation_snapshot(**changes):
    out = snapshot(target=F.DFT_TARGET, score_type="tc_K", score=6.0,
                   conditions=computational_conditions(), theory=theory(source_hash=None))
    out.pop("threshold_K")
    out.pop("decision_threshold")
    out.update(changes)
    return out


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.jsonl"
        self.now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self.ledger = F.FeedbackLedger(self.path, clock=lambda: self.now)

    def append(self, obs):
        self.now = datetime(2025, 2, 2, tzinfo=timezone.utc)
        return self.ledger.append_observation(obs)

    def export(self, events, **changes):
        kw = dict(target=F.SAMPLE_TARGET, threshold_K=2.0, query_conditions=conditions(), material_id="fixture-1")
        kw.update(changes)
        return F.legal_training_export(events, **kw)

    def test_append_chain_snapshot_and_idempotence(self):
        payload = snapshot()
        event = self.ledger.append_snapshot(payload)
        before = self.path.read_bytes()
        self.assertEqual(self.ledger.append_snapshot(payload), event)
        self.assertEqual(self.path.read_bytes(), before)
        payload["score"] = .1
        self.assertEqual(self.ledger.read()[0]["payload"]["score"], .9)
        obs = self.append(observation())
        events = self.ledger.read(expected_head=obs["hash"])
        self.assertEqual(events[1]["previous_hash"], event["hash"])
        self.assertEqual(F.verify_events(events)["active_observations"], 1)

    def test_snapshot_immutable_within_run_new_run_allowed(self):
        self.ledger.append_snapshot(snapshot())
        with self.assertRaises(F.FeedbackValidationError):
            self.ledger.append_snapshot(snapshot(score=.1))
        self.ledger.append_snapshot(snapshot(run_id="another-run", score=.1))
        self.assertEqual(len(self.ledger.read()), 2)

    def test_tamper_and_pinned_head_and_truncation_fail(self):
        original = self.ledger.append_snapshot(snapshot())
        events = self.ledger.read()
        events[0]["payload"]["score"] = .1
        with self.assertRaises(F.LedgerIntegrityError):
            F.verify_events(events)
        with self.assertRaises(F.LedgerIntegrityError):
            self.ledger.read(expected_head=F.GENESIS)
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\n"))
        with self.assertRaises(F.LedgerIntegrityError):
            self.ledger.read(expected_head=original["hash"])

    def test_full_rewrite_detected_by_external_head(self):
        old = self.ledger.append_snapshot(snapshot())
        self.path.unlink()
        self.ledger.append_snapshot(snapshot(score=.1))
        with self.assertRaises(F.LedgerIntegrityError):
            self.ledger.read(expected_head=old["hash"])

    def test_correction_append_only_and_idempotent(self):
        old = self.append(negative())
        before = self.path.read_bytes()
        payload = observation(correction_reason="Synthetic correction for test")
        new = self.ledger.append_observation(payload, supersedes=old["hash"])
        self.assertTrue(self.path.read_bytes().startswith(before))
        self.assertEqual(self.ledger.append_observation(payload, supersedes=old["hash"]), new)
        events = self.ledger.read()
        self.assertEqual(F.verify_events(events)["active_observations"], 1)
        self.assertEqual(self.export(events)["accepted"][0]["label"], 1)
        with self.assertRaises(F.LedgerIntegrityError):
            self.ledger.append_observation(negative(correction_reason="Stale correction"), supersedes=old["hash"])

    def test_correction_requires_reason_same_scope_and_active_observation(self):
        snap = self.ledger.append_snapshot(snapshot())
        old = self.append(negative())
        for payload, supersedes in [(observation(), old["hash"]),
                                    (observation(material_id="fixture-other", correction_reason="Correction"), old["hash"]),
                                    (observation(correction_reason="Correction"), snap["hash"])]:
            with self.subTest(payload=payload, supersedes=supersedes), self.assertRaises(F.LedgerIntegrityError):
                self.ledger.append_observation(payload, supersedes=supersedes)

    def test_existing_writer_lock_not_stolen(self):
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("test-lock", encoding="utf-8")
        with self.assertRaises(F.LedgerBusyError):
            self.ledger.append_snapshot(snapshot())
        self.assertEqual(lock.read_text(), "test-lock")
        self.assertFalse(self.path.exists())

    def test_unknown_conditions_explicit_null_no_imputation(self):
        payload = negative(conditions={k: None for k in F.CONDITION_KEYS})
        payload["assertion_status"] = "unknown"
        payload["outcome"] = None
        self.append(payload)
        stored = self.ledger.read()[0]["payload"]
        self.assertIsNone(stored["conditions"]["pressure_GPa"])
        self.assertFalse(self.export(self.ledger.read())["accepted"])
        del payload["conditions"]["field_T"]
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_observation(payload)

    def test_numeric_and_date_validation(self):
        for value in [float("nan"), float("inf"), True, -1]:
            with self.subTest(value=value), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(negative(conditions=conditions(field_T=value)))
        for changes in [dict(score=True), dict(score=float("nan")), dict(score=1.1),
                        dict(predicted_at="2024-01-01"), dict(score_type="parent_probability")]:
            with self.subTest(changes=changes), self.assertRaises(F.FeedbackValidationError):
                F.validate_snapshot(snapshot(**changes))
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_observation(observation(reference=reference(publication_date="2026-01-01")))

    def test_model_llm_and_phonon_cannot_be_sc_facts(self):
        for source in ["llm_output", "model_prediction", "primary_computation"]:
            with self.subTest(source=source), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(negative(reference=reference(source_kind=source)))
        structural = observation(observation_type="structural_stability", outcome="unstable",
                                 reference=reference(source_kind="primary_computation"))
        self.append(structural)
        self.assertFalse(self.export(self.ledger.read())["accepted"])

    def test_sample_negative_exports_only_exact_matching_target(self):
        self.append(negative())
        events = self.ledger.read()
        self.assertEqual(self.export(events)["accepted"][0]["label"], 0)
        self.assertFalse(self.export(events, target=F.PARENT_TARGET)["accepted"])
        for field, value in [("sample_id", "different"), ("phase", "different"),
                             ("pressure_GPa", 1), ("field_T", 1), ("sample_form", "film"),
                             ("method", "magnetic_susceptibility"),
                             ("formula", "FeS"), ("phase", None), ("field_T", float("nan"))]:
            with self.subTest(field=field, value=value):
                self.assertFalse(self.export(events, query_conditions=conditions(**{field: value}))["accepted"])

    def test_incomplete_temperature_window_or_missing_measured_tc_not_exported(self):
        for payload in [negative(conditions=conditions(t_min_K=None)), negative(conditions=conditions(t_max_K=None)),
                        negative(conditions=conditions(t_min_K=3)), observation(tc_K=None), observation(tc_K=1.5)]:
            with self.subTest(payload=payload):
                ledger = F.FeedbackLedger(Path(self.temp.name) / (str(len(list(Path(self.temp.name).glob("*.jsonl")))) + ".jsonl"),
                                          clock=lambda: datetime(2025, 2, 2, tzinfo=timezone.utc))
                ledger.append_observation(payload)
                self.assertFalse(self.export(ledger.read())["accepted"])

    def test_prospective_feedback_exact_sample(self):
        snap = self.ledger.append_snapshot(snapshot())
        obs = self.append(observation())
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=obs["hash"])
        self.assertEqual(result["evaluation_mode"], "prospective")
        self.assertTrue(result["strict_hit"])
        self.assertTrue(result["eligible_for_prospective_metrics"])

    def test_old_paper_found_later_retrospective_not_hit(self):
        snap = self.ledger.append_snapshot(snapshot())
        obs = self.append(observation(reference=reference(publication_date="2020-01-01")))
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=obs["hash"])
        self.assertEqual(result["evaluation_mode"], "retrospective")
        self.assertIsNone(result["strict_hit"])
        self.assertTrue(result["retrospective_agreement"])

    def test_missing_date_and_unknown_phase_never_strict_hit(self):
        snap = self.ledger.append_snapshot(snapshot())
        for payload in [observation(reference=reference(publication_date=None)),
                        observation(conditions=conditions(phase=None))]:
            obs = self.append(payload)
            result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=obs["hash"])
            self.assertIsNone(result["strict_hit"])
            self.assertFalse(result["eligible_for_prospective_metrics"])

    def test_same_day_or_late_snapshot_freeze_not_prospective(self):
        for freeze, publication, expected in [("2024-01-01", "2024-01-01", "same_day_uncertain"),
                                              ("2025-01-02", "2025-01-01", "retrospective_late_freeze")]:
            self.path.unlink(missing_ok=True)
            self.now = datetime.fromisoformat(freeze).replace(tzinfo=timezone.utc)
            snap = self.ledger.append_snapshot(snapshot())
            obs = self.append(observation(reference=reference(publication_date=publication)))
            result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=obs["hash"])
            self.assertEqual(result["evaluation_mode"], expected)
            self.assertIsNone(result["strict_hit"])

    def test_conflicting_evidence_not_exported_not_counted_and_stays_queued(self):
        snap = self.ledger.append_snapshot(snapshot())
        pos = self.append(observation())
        self.append(negative())
        events = self.ledger.read()
        self.assertFalse(self.export(events)["accepted"])
        result = F.evaluate_feedback(events, snapshot_hash=snap["hash"], observation_hash=pos["hash"])
        self.assertIsNone(result["strict_hit"])
        self.assertIn("conflicting", " ".join(result["reasons"]))
        self.assertEqual(len(F.select_next_batch([candidate()], events, budget=1, target=F.SAMPLE_TARGET, threshold_K=2)), 1)

    def test_superseded_observation_not_counted(self):
        snap = self.ledger.append_snapshot(snapshot())
        old = self.append(negative())
        self.ledger.append_observation(observation(correction_reason="Synthetic adjudication"), supersedes=old["hash"])
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=old["hash"])
        self.assertIsNone(result["strict_hit"])
        self.assertIn("observation was superseded", result["reasons"])

    def test_queue_mixes_policies_deterministically_without_duplicates(self):
        candidates = [candidate("a", score=.99), candidate("b", score=.98),
                      candidate("c", score=.2, disagreement=8), candidate("d", score=.1, domain_distance=9)]
        result = F.select_next_batch(candidates + [copy.deepcopy(candidates[0])], budget=4, target=F.SAMPLE_TARGET)
        self.assertEqual([(r["material_id"], r["selection_reason"]) for r in result],
                         [("a", "high_score"), ("b", "high_score"), ("c", "disagreement"), ("d", "exploration")])
        self.assertEqual(F.select_next_batch(candidates, budget=0, target=F.SAMPLE_TARGET), [])

    def test_unknown_search_does_not_remove_candidate_and_known_only_exact_conditions(self):
        self.append(observation(observation_type="literature_search", outcome="not_found",
                                reference=reference(source_kind="search_log", inspection_status="search_results_only")))
        self.assertEqual(len(F.select_next_batch([candidate()], self.ledger.read(), budget=1,
                                                target=F.SAMPLE_TARGET, threshold_K=2)), 1)
        self.append(negative())
        self.assertFalse(F.select_next_batch([candidate()], self.ledger.read(), budget=1,
                                            target=F.SAMPLE_TARGET, threshold_K=2))
        self.assertEqual(len(F.select_next_batch([candidate(conditions=conditions(phase="another-phase"))], self.ledger.read(),
                                                budget=1, target=F.SAMPLE_TARGET, threshold_K=2)), 1)
        self.assertEqual(len(F.select_next_batch([candidate(score_type="parent_probability")], self.ledger.read(),
                                                budget=1, target=F.PARENT_TARGET, threshold_K=2)), 1)

    def test_queue_rejects_ambiguous_or_invalid_scores(self):
        for changes in [dict(score=True), dict(score=float("nan")), dict(score=1.1),
                        dict(disagreement=-1), dict(domain_distance=float("nan")), dict(score_type="untyped")]:
            with self.subTest(changes=changes), self.assertRaises(F.FeedbackValidationError):
                F.select_next_batch([candidate(**changes)], budget=1, target=F.SAMPLE_TARGET)
        with self.assertRaises(F.FeedbackValidationError):
            F.select_next_batch([], budget=True, target=F.SAMPLE_TARGET)
        with self.assertRaises(F.FeedbackValidationError):
            F.select_next_batch([], budget=1, target=F.SAMPLE_TARGET, threshold_K=float("nan"))

    def test_normal_individual_points_feature_export_no_cross_sample_join(self):
        first = self.append(normal(series_id="explicit-source-series"))
        self.append(normal(conditions=conditions(sample_id="synthetic-sample-B"), quantity="Hall_coefficient", value=-2.0, unit="m3/C"))
        events = self.ledger.read()
        self.assertTrue(first["payload"]["feature_eligible"])
        report = F.legal_precursor_export(events, as_of="2025-02-03T00:00:00Z")
        self.assertEqual(len(report["accepted"]), 2)
        self.assertEqual({r["sample_id"] for r in report["accepted"]}, {"synthetic-sample-A", "synthetic-sample-B"})
        self.assertFalse(report["automatic_retraining"])
        self.assertEqual(report["accepted"][1]["value"], -2)
        self.assertEqual(report["accepted"][0]["series_id"], "explicit-source-series")
        self.assertIsNone(report["accepted"][1]["series_id"])

    def test_normal_unknowns_preserved_and_never_zero_filled(self):
        payload = normal(value=None, unit=None, normal_state_status="unknown", assertion_status="unknown",
                         conditions={k: None for k in F.CONDITION_KEYS},
                         coordinates={k: None for k in F.COORDINATES},
                         reference=reference(publication_date=None, inspection_status="not_inspected"),
                         feature_window=dict(kind="unspecified", min_K=None, max_K=None, defined_at=None))
        event = self.append(payload)
        self.assertFalse(event["payload"]["feature_eligible"])
        self.assertIsNone(event["payload"]["value"])
        self.assertTrue(all(v is None for v in event["payload"]["coordinates"].values()))
        self.assertFalse(F.legal_precursor_export(self.ledger.read(), as_of="2025-02-03T00:00:00Z")["accepted"])

    def test_normal_coordinate_validation_and_sample_consistency(self):
        for key, value in [("pressure_gpa", 2), ("magnetic_field_t", None), ("temperature_k", 0),
                           ("doping_fraction", 5), ("strain", float("nan")), ("strain", True)]:
            payload = normal()
            payload["coordinates"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(payload)
        payload = normal()
        payload["coordinates"]["strain"] = -.01
        F.validate_observation(payload)

    def test_tc_relative_windows_cannot_be_precursors_or_override_flag(self):
        payload = normal()
        payload["feature_window"]["kind"] = "tc_relative"
        self.assertFalse(F.feature_eligibility(payload)["feature_eligible"])
        payload["feature_eligible"] = True
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_observation(payload)

    def test_sc_outcomes_not_normal_state_quantities(self):
        for quantity in ["zero_resistance", "Meissner_fraction", "SC_heat_capacity_jump", "superconducting_transition"]:
            with self.subTest(quantity=quantity), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(normal(quantity=quantity))
        self.assertFalse(F.feature_eligibility(normal(value=0))["feature_eligible"])
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_observation(normal(normal_state_status="verified_normal", assertion_status="unverified"))

    def test_precursor_cutoff_requires_frozen_record_source_and_window(self):
        self.append(normal())
        report = F.legal_precursor_export(self.ledger.read(), as_of="2025-01-15T00:00:00Z")
        self.assertFalse(report["accepted"])
        self.assertIn("measurement was not frozen by feature cutoff", report["excluded"][0]["reasons"])
        payload = normal()
        payload["feature_window"]["defined_at"] = "2025-02-02T00:00:00Z"
        # An absolute window can be frozen after reading an old paper. It must
        # still precede the prediction feature cutoff, never depend on known Tc.
        self.assertTrue(F.feature_eligibility(payload)["feature_eligible"])
        self.assertFalse(F.feature_eligibility(payload, as_of="2025-02-01T12:00:00Z")["feature_eligible"])
        for changes in [dict(reference=reference(publication_date=None)), dict(conditions=conditions(phase=None))]:
            self.assertFalse(F.feature_eligibility(normal(**changes))["feature_eligible"])

    def test_audit_and_cli_missing_ledger_are_read_only(self):
        missing = Path(self.temp.name) / "absent-subdir" / "ledger.jsonl"
        report = F.audit_ledger(missing)
        self.assertTrue(report["valid"])
        self.assertFalse(report["exists"])
        self.assertEqual(report["events"], 0)
        self.assertEqual(report["observation_types"]["normal_state_measurement"], 0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(F.main(["--audit", "--ledger", str(missing)]), 0)
        self.assertFalse(missing.parent.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(F.main(["--verify", str(missing)]), 1)

    def test_queue_cli_prints_only_and_supports_id_alias(self):
        source = Path(self.temp.name) / "candidates.json"
        rec = candidate(score_type="parent_probability")
        rec["id"] = rec.pop("material_id")
        source.write_text(json.dumps([rec]), encoding="utf-8")
        missing = Path(self.temp.name) / "absent" / "ledger.jsonl"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(F.main(["--queue", str(source), "--ledger", str(missing), "--budget", "1"]), 0)
        self.assertEqual(json.loads(out.getvalue())["selected"][0]["material_id"], "fixture-1")
        self.assertFalse(missing.parent.exists())

    def append_computed(self, payload=None):
        self.now = datetime(2025, 2, 2, tzinfo=timezone.utc)
        return self.ledger.append_observation(payload or computed(), source_bytes=RAW_COMPUTATION)

    def computation_export(self, events, **changes):
        args = dict(query_conditions=computational_conditions(), query_theory=theory(source_hash=None), material_id="fixture-1")
        args.update(changes)
        return F.legal_computation_export(events, **args)

    def test_computation_hashes_original_source_and_is_idempotent(self):
        event = self.append_computed()
        self.assertEqual(event["payload"]["source_verification"]["sha256"], hashlib.sha256(RAW_COMPUTATION).hexdigest())
        before = self.path.read_bytes()
        self.assertEqual(self.append_computed(), event)
        self.assertEqual(self.path.read_bytes(), before)
        for raw in [None, b"changed source", b""]:
            with self.subTest(raw=raw), self.assertRaises(F.FeedbackValidationError):
                self.ledger.append_observation(computed(), source_bytes=raw)

    def test_computed_zero_is_numerical_and_never_experimental_negative(self):
        self.append_computed(computed(tc_K=0.0))
        events = self.ledger.read()
        exported = self.computation_export(events)
        self.assertEqual(exported["accepted"][0]["tc_K"], 0.0)
        self.assertEqual(exported["experimental_labels"], 0)
        self.assertFalse(self.export(events)["accepted"])
        self.assertFalse(self.export(events, target=F.PARENT_TARGET)["accepted"])
        self.assertFalse(F.legal_precursor_export(events, as_of="2025-02-03T00:00:00Z")["accepted"])
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_observation(observation(tc_K=0))

    def test_computation_rejects_model_or_llm_truth_and_missing_inspection(self):
        for source in ["model_prediction", "llm_output", "primary_experiment"]:
            with self.subTest(source=source), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(computed(reference=reference(source_kind=source)))
        for inspection in ["abstract_inspected", "not_inspected", "search_results_only"]:
            with self.subTest(inspection=inspection), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(computed(reference=reference(source_kind="primary_computation", inspection_status=inspection)))

    def test_computation_theory_and_same_structure_match_exactly(self):
        self.append_computed()
        events = self.ledger.read()
        self.assertEqual(self.computation_export(events)["accepted"][0]["tc_K"], 4.0)
        for changes in [dict(mu_star=.15), dict(mu_star=None), dict(source_hash="b" * 64),
                        dict(method="Allen-Dynes f1=f2=1"),
                        dict(component_units={"lambda": "dimensionless", "omega_log": "meV", "tc_K": "K"})]:
            with self.subTest(changes=changes):
                self.assertFalse(self.computation_export(events, query_theory=theory(**changes))["accepted"])
        for key, value in [("structure_id", "different"), ("structure_hash", "b" * 64),
                           ("phase", "different"), ("pressure_GPa", 1), ("field_T", None),
                           ("strain", .01), ("doping_fraction", .1), ("formula", "FeS")]:
            with self.subTest(key=key, value=value):
                self.assertFalse(self.computation_export(events, query_conditions=computational_conditions(**{key: value}))["accepted"])

    def test_computation_unknown_conditions_do_not_produce_strict_errors(self):
        snap = self.ledger.append_snapshot(computation_snapshot())
        event = self.append_computed(computed(conditions=computational_conditions(structure_hash=None)))
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=event["hash"])
        self.assertIsNone(result["computed_error_K"])
        self.assertFalse(result["eligible_for_prospective_computation_metrics"])

    def test_computation_metrics_are_separate_with_retrospective_timing(self):
        snap = self.ledger.append_snapshot(computation_snapshot())
        event = self.append_computed()
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=event["hash"])
        self.assertEqual(result["computed_error_K"], 2.0)
        self.assertEqual(result["computed_absolute_error_K"], 2.0)
        self.assertTrue(result["eligible_for_prospective_computation_metrics"])
        self.assertIsNone(result["strict_hit"])
        self.assertFalse(result["eligible_for_prospective_metrics"])
        old = computed(reference=reference(source_kind="primary_computation", inspection_status="data_inspected", publication_date="2020-01-01"))
        event2 = self.append_computed(old)
        result2 = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=event2["hash"])
        self.assertEqual(result2["evaluation_mode"], "retrospective")
        self.assertEqual(result2["computed_absolute_error_K"], 2.0)
        self.assertFalse(result2["eligible_for_prospective_computation_metrics"])

    def test_cross_channel_evaluation_cannot_reward_sc_prediction(self):
        sample_snap = self.ledger.append_snapshot(snapshot())
        dft_snap = self.ledger.append_snapshot(computation_snapshot())
        comp = self.append_computed()
        sample = self.append(observation())
        events = self.ledger.read()
        to_sample = F.evaluate_feedback(events, snapshot_hash=sample_snap["hash"], observation_hash=comp["hash"])
        to_dft = F.evaluate_feedback(events, snapshot_hash=dft_snap["hash"], observation_hash=sample["hash"])
        self.assertIsNone(to_sample["strict_hit"])
        self.assertIsNone(to_dft["computed_error_K"])
        self.assertFalse(to_dft["eligible_for_prospective_computation_metrics"])

    def test_computation_snapshot_and_queue_use_separate_target(self):
        snap = self.ledger.append_snapshot(computation_snapshot(score=0))
        self.assertEqual(snap["payload"]["score"], 0)
        rec = candidate(score_type="tc_K", score=6.0, conditions=computational_conditions(), theory=theory(source_hash=None))
        self.assertEqual(len(F.select_next_batch([rec], budget=1, target=F.DFT_TARGET)), 1)
        self.append_computed()
        self.assertFalse(F.select_next_batch([rec], self.ledger.read(), budget=1, target=F.DFT_TARGET))
        rec["theory"]["mu_star"] = .15
        self.assertEqual(len(F.select_next_batch([rec], self.ledger.read(), budget=1, target=F.DFT_TARGET)), 1)
        with self.assertRaises(F.FeedbackValidationError):
            F.validate_snapshot(computation_snapshot(score_type="sample_probability"))

    def test_computation_additional_theory_settings_and_conflicts_are_not_dropped(self):
        self.append_computed(computed(theory=theory(xc_functional="PBE")))
        events = self.ledger.read()
        self.assertFalse(self.computation_export(events)["accepted"])
        self.assertTrue(self.computation_export(events, query_theory=theory(source_hash=None, xc_functional="PBE"))["accepted"])
        self.append_computed(computed(tc_K=5.0, theory=theory(xc_functional="PBE")))
        self.assertFalse(self.computation_export(self.ledger.read(), query_theory=theory(source_hash=None, xc_functional="PBE"))["accepted"])

    def test_computation_source_hash_and_unknown_date_validation(self):
        for hash_value in ["not-a-sha256", True, None]:
            with self.subTest(hash_value=hash_value), self.assertRaises(F.FeedbackValidationError):
                F.validate_observation(computed(theory=theory(source_hash=hash_value)))
        snap = self.ledger.append_snapshot(computation_snapshot())
        event = self.append_computed(computed(reference=reference(source_kind="primary_computation", inspection_status="data_inspected", publication_date=None)))
        result = F.evaluate_feedback(self.ledger.read(), snapshot_hash=snap["hash"], observation_hash=event["hash"])
        self.assertIsNone(result["computed_error_K"])


if __name__ == "__main__":
    unittest.main()
