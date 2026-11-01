"""Offline evidence ledger; predictions and evidence never train a model implicitly.

``FeedbackLedger(path).append_snapshot(payload)`` freezes a prediction.
``append_observation(payload, supersedes=previous_hash)`` appends evidence/corrections.
``read_events`` verifies the entire canonical SHA256 chain before any consumer runs.
``legal_training_export`` is an explicit, exact-sample-only export, not parent labels.
``legal_computation_export`` separately exports matched Allen-Dynes numerical Tc;
checked computation appends require ``source_bytes`` to verify the original SHA256.
``evaluate_feedback(events, snapshot_hash=..., observation_hash=...)`` checks both
timing and sample conditions. ``select_next_batch`` only plans independent checks.

Prediction score_type is sample_probability, parent_probability, tc_K, or ranking_score.
Targets reuse negative_data's explicit sample/parent definitions. Observation types
are sample_superconductivity, structural_stability, literature_search,
normal_state_measurement, and computed_superconductivity. Unknown
conditions must be present as null. A source_checked assertion describes evidence
inspected by a person/caller; this module cannot authenticate a paper's contents.

Hash chains detect edits relative to their history or a pinned expected_head. They
are not signatures or trusted timestamps: a fully rewritten ledger needs an
external checkpoint to detect it. No data files, network calls, or ML dependencies.

    python ml/feedback.py --verify /path/to/ledger.jsonl --expected-head <sha256>
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

try:
    from . import negative_data as ND
except ImportError:
    import negative_data as ND

SAMPLE_TARGET = ND.SAMPLE_TARGET
PARENT_TARGET = ND.PARENT_TARGET
DFT_TARGET = "dft_allen_dynes_tc_at_declared_conditions"
GENESIS = "0" * 64
CONDITION_KEYS = ("sample_id", "formula", "sample_form", "phase", "pressure_GPa",
                  "t_min_K", "t_max_K", "field_T", "method")
IDENTITY_KEYS = ("sample_id", "formula", "sample_form", "phase", "pressure_GPa", "field_T", "method")
SCORE_TYPES = {"sample_probability", "parent_probability", "tc_K", "ranking_score"}
SOURCE_KINDS = {"primary_experiment", "primary_computation", "secondary_literature",
                "model_prediction", "llm_output", "search_log"}
INSPECTION_STATES = {"full_text_inspected", "data_inspected", "abstract_inspected", "not_inspected", "search_results_only"}
ASSERTION_STATES = {"source_checked", "unverified", "unknown"}
OBSERVATION_TYPES = {"sample_superconductivity", "structural_stability", "literature_search",
                     "normal_state_measurement", "computed_superconductivity"}
COORDINATES = ("temperature_k", "pressure_gpa", "doping_fraction", "strain", "magnetic_field_t")
COMPUTATION_KEYS = ("structure_id", "structure_hash", "formula", "phase", "pressure_GPa", "field_T",
                    "doping_fraction", "strain")
THEORY_KEYS = ("method", "mu_star", "component_units", "source_hash")
SC_METHODS = {"resistivity", "magnetic_susceptibility", "ac_susceptibility", "dc_susceptibility",
              "magnetization", "heat_capacity", "transport_and_magnetic"}


class FeedbackValidationError(ValueError):
    pass


class LedgerIntegrityError(ValueError):
    pass


class LedgerBusyError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise FeedbackValidationError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value, minimum=None):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (minimum is None or value >= minimum))


def _timestamp(value):
    _require(_text(value), "timestamp must be an ISO8601 string with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FeedbackValidationError("invalid ISO8601 timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def _publication(value):
    if value is None:
        return None
    if isinstance(value, str) and len(value) == 10:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise FeedbackValidationError("invalid publication_date") from exc
    return _timestamp(value)


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FeedbackValidationError("records must contain finite JSON values") from exc


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _computation_conditions(value):
    _require(all(k in value for k in COMPUTATION_KEYS), "computational structural conditions must be explicit")
    _require(value["structure_id"] is None or _text(value["structure_id"]), "invalid structure_id")
    _require(value["structure_hash"] is None or _sha256(value["structure_hash"]), "structure_hash must be SHA256 or null")
    _require(value["doping_fraction"] is None or (_number(value["doping_fraction"], 0) and value["doping_fraction"] <= 1),
             "invalid computational doping_fraction")
    _require(value["strain"] is None or _number(value["strain"]), "invalid computational strain")


def _theory(value, *, require_source=False):
    _require(isinstance(value, dict) and all(k in value for k in THEORY_KEYS), "theory fields must be explicit")
    method = value["method"]
    _require(method is None or (_text(method) and re.sub(r"[^a-z0-9]", "", method.lower()).removeprefix("dft").startswith("allendynes")),
             "this target requires an explicit Allen-Dynes method")
    _require(value["mu_star"] is None or (_number(value["mu_star"], 0) and value["mu_star"] <= 1), "invalid mu_star")
    units = value["component_units"]
    _require(units is None or (isinstance(units, dict) and all(k in units for k in ("lambda", "omega_log", "tc_K"))
             and all(_text(k) and _text(v) for k, v in units.items()) and units["tc_K"] == "K"),
             "component_units must declare lambda, omega_log, and tc_K=K")
    _require(value["source_hash"] is None or _sha256(value["source_hash"]), "source_hash must be SHA256 or null")
    if require_source:
        _require(_sha256(value["source_hash"]), "checked computation needs the original source SHA256")


def _conditions(value):
    _require(isinstance(value, dict), "conditions must be an object")
    _require(all(key in value for key in CONDITION_KEYS), "unknown conditions must be explicit null fields")
    for key in ("sample_id", "formula", "sample_form", "phase", "method"):
        _require(value[key] is None or (_text(value[key]) and value[key].lower() not in
                 {"unknown", "not_reported", "n/a"}), f"{key} must be text or explicit null")
    if value["formula"] is not None:
        try:
            ND.composition(value["formula"])
        except ValueError as exc:
            raise FeedbackValidationError("formula must be expanded and explicit") from exc
    for key in ("pressure_GPa", "field_T", "t_min_K", "t_max_K"):
        v = value[key]
        _require(v is None or (_number(v, 0) and (not key.startswith("t_") or v > 0)),
                 f"invalid {key}")
    if value["t_min_K"] is not None and value["t_max_K"] is not None:
        _require(value["t_max_K"] >= value["t_min_K"], "invalid measured temperature interval")


def validate_snapshot(payload):
    _require(isinstance(payload, dict), "snapshot must be an object")
    for key in ("material_id", "model_version", "run_id", "source", "predicted_at", "score_type", "target"):
        _require(_text(payload.get(key)), f"missing snapshot {key}")
    _timestamp(payload["predicted_at"])
    _conditions(payload.get("conditions"))
    kind, target, score = payload["score_type"], payload["target"], payload.get("score")
    _require(kind in SCORE_TYPES, "unknown score_type")
    _require(target in {SAMPLE_TARGET, PARENT_TARGET, DFT_TARGET}, "unknown prediction target")
    _require(_number(score), "score must be finite numeric")
    if kind.endswith("probability"):
        _require(0 <= score <= 1, "probability score must be between zero and one")
        expected = PARENT_TARGET if kind == "parent_probability" else SAMPLE_TARGET
        _require(target == expected, "probability score_type disagrees with target")
    if kind == "tc_K":
        _require(score >= 0 and target in {SAMPLE_TARGET, DFT_TARGET}, "tc_K needs an explicit sample or DFT target")
    if target == DFT_TARGET:
        _require(kind == "tc_K", "DFT target uses a separate tc_K score")
        _computation_conditions(payload["conditions"])
        _theory(payload.get("theory"))
    if payload.get("threshold_K") is not None:
        _require(_number(payload["threshold_K"], 0) and payload["threshold_K"] > 0, "invalid threshold_K")
    if payload.get("decision_threshold") is not None:
        v = payload["decision_threshold"]
        _require(_number(v, 0) and v <= 1, "invalid decision_threshold")
    _canonical(payload)


def validate_observation(payload):
    _require(isinstance(payload, dict), "observation must be an object")
    for key in ("material_id", "observed_at", "statement", "observation_type", "assertion_status"):
        _require(_text(payload.get(key)), f"missing observation {key}")
    _timestamp(payload["observed_at"])
    _conditions(payload.get("conditions"))
    _require(payload["observation_type"] in OBSERVATION_TYPES, "unknown observation_type")
    _require(payload["assertion_status"] in ASSERTION_STATES, "unknown assertion_status")
    ref = payload.get("reference")
    _require(isinstance(ref, dict), "reference must be an object")
    _require(all(k in ref for k in ("doi", "url", "inspection_status", "source_kind", "publication_date", "locator")),
             "reference fields must be explicit, including unknown publication_date/locator")
    _require(_text(ref["doi"]) or _text(ref["url"]), "reference needs a DOI or URL")
    if ref["doi"] is not None:
        _require(_text(ref["doi"]) and re.fullmatch(r"10\.\d{4,9}/\S+", ref["doi"].removeprefix("https://doi.org/"), re.I),
                 "invalid DOI")
    if ref["url"] is not None:
        _require(_text(ref["url"]) and urlsplit(ref["url"]).scheme in {"http", "https"}
                 and bool(urlsplit(ref["url"]).netloc), "invalid reference URL")
    _require(ref["inspection_status"] in INSPECTION_STATES, "unknown inspection_status")
    _require(ref["source_kind"] in SOURCE_KINDS, "unknown source_kind")
    _require(ref["locator"] is None or _text(ref["locator"]), "locator must be text or null")
    published = _publication(ref["publication_date"])
    _require("outcome" in payload, "unknown outcome must be explicit null")
    typ, outcome = payload["observation_type"], payload["outcome"]
    checked = payload["assertion_status"] == "source_checked"
    if checked and published is not None:
        observed = _timestamp(payload["observed_at"])
        _require(published <= observed if isinstance(published, datetime) else published <= observed.date(),
                 "source publication is after its claimed inspection time")
    if typ == "sample_superconductivity":
        _require(outcome is None or type(outcome) is bool, "sample outcome must be boolean or null")
        if ref["source_kind"] in {"model_prediction", "llm_output", "primary_computation"}:
            _require(outcome is None and not checked, "predictions/LLM/computation cannot assert sample SC facts")
        if checked and outcome is not None:
            _require(ref["source_kind"] == "primary_experiment" and
                     ref["inspection_status"] == "full_text_inspected" and _text(ref["locator"]),
                     "sample facts require inspected primary experiment and locator")
            expected = "measured_transition" if outcome else "measured_no_transition"
            _require(payload.get("evidence_kind") == expected, "explicit measured SC statement required")
            _require(payload["conditions"]["method"] in SC_METHODS, "SC facts need an experimental SC measurement method")
        tc = payload.get("tc_K")
        _require(tc is None or (_number(tc, 0) and tc > 0), "invalid measured tc_K")
        if outcome is False:
            _require(tc is None, "censored sample negatives must not carry Tc=0 or a measured Tc")
    elif typ == "structural_stability":
        _require(outcome in {None, "stable", "unstable"}, "invalid structural outcome")
        if checked:
            _require(ref["source_kind"] in {"primary_computation", "primary_experiment"}
                     and ref["inspection_status"] == "full_text_inspected" and _text(ref["locator"]),
                     "structural assertions require inspected primary evidence and locator")
    elif typ == "literature_search":
        _require(outcome in {None, "found", "not_found", "unknown"}, "invalid literature-search outcome")
        if checked:
            _require(ref["source_kind"] == "search_log" and ref["inspection_status"] == "search_results_only",
                     "search results must remain search-log evidence")
    elif typ == "normal_state_measurement":
        _validate_normal_measurement(payload)
    else:
        _validate_computed_observation(payload)
    if checked:
        _require(ref["source_kind"] not in {"model_prediction", "llm_output"}, "unverified generated text is not evidence")
    if "label" in payload or "parent_label" in payload or "unconditional_negative" in payload:
        raise FeedbackValidationError("observations are evidence, not unconditional training labels")
    _canonical(payload)


def _validate_computed_observation(payload):
    _require(payload["outcome"] is None, "computed Tc is numerical, not an experimental SC outcome")
    _require("tc_K" in payload and (payload["tc_K"] is None or _number(payload["tc_K"], 0)), "invalid computed tc_K")
    _computation_conditions(payload["conditions"])
    checked = payload["assertion_status"] == "source_checked"
    _theory(payload.get("theory"), require_source=checked)
    _require(payload["reference"]["source_kind"] == "primary_computation", "computed truth requires a primary computation, not a model prediction")
    if checked:
        ref = payload["reference"]
        _require(ref["inspection_status"] in {"full_text_inspected", "data_inspected"} and _text(ref["locator"]),
                 "computed truth needs inspected original text/data and a locator")


def verify_computation_source(payload, raw_source):
    """Bind original inspected bytes to an asserted computation; no network/authentication."""
    validate_observation(payload)
    _require(payload["observation_type"] == "computed_superconductivity", "source hashing is for the computation channel")
    _require(isinstance(raw_source, bytes) and bool(raw_source), "original computation source bytes are required")
    digest = hashlib.sha256(raw_source).hexdigest()
    _require(digest == payload["theory"]["source_hash"], "original computation source SHA256 mismatch")
    return {"sha256": digest, "byte_count": len(raw_source), "method": "sha256_raw_bytes"}


def _validate_normal_measurement(payload):
    """One quantity at one reported point; fractional doping/strain never imputed."""
    _require(payload["outcome"] is None, "normal measurements cannot carry an SC outcome")
    for key in ("quantity", "value", "unit", "coordinates", "normal_state_status", "feature_window"):
        _require(key in payload, f"missing normal measurement {key}")
    _require(_text(payload["quantity"]), "quantity must be explicit")
    _require(payload.get("series_id") is None or _text(payload["series_id"]), "series_id must be text or null")
    quantity = re.sub(r"[^a-z0-9]", "", payload["quantity"].lower())
    _require(not ("meissner" in quantity or "zeroresistan" in quantity or
                  "heatcapacityjump" in quantity or "specificheatjump" in quantity or
                  "superconductingtransition" in quantity),
             "superconducting outcomes cannot be precursor quantities")
    _require(payload["value"] is None or _number(payload["value"]), "normal value must be finite or null")
    _require(payload["unit"] is None or _text(payload["unit"]), "normal unit must be text or null")
    coordinates = payload["coordinates"]
    _require(isinstance(coordinates, dict) and all(k in coordinates for k in COORDINATES),
             "all five coordinates must be explicit, with unknown values null")
    for key in COORDINATES:
        v = coordinates[key]
        _require(v is None or _number(v, None if key == "strain" else 0), f"invalid coordinate {key}")
    if coordinates["temperature_k"] is not None:
        _require(coordinates["temperature_k"] > 0, "measurement temperature must be positive")
    if coordinates["doping_fraction"] is not None:
        _require(coordinates["doping_fraction"] <= 1, "doping_fraction uses fractions, not percent")
    cond = payload["conditions"]
    for c_key, old_key in (("pressure_gpa", "pressure_GPa"), ("magnetic_field_t", "field_T")):
        left, right = coordinates[c_key], cond[old_key]
        _require((left is None and right is None) or (left is not None and right is not None
                 and abs(left - right) <= 1e-8), f"coordinate disagrees with conditions: {c_key}")
    temp = coordinates["temperature_k"]
    if temp is not None:
        _require(cond["t_min_K"] is None or temp >= cond["t_min_K"], "point is below measured interval")
        _require(cond["t_max_K"] is None or temp <= cond["t_max_K"], "point is above measured interval")
    _require(payload["normal_state_status"] in {"verified_normal", "unknown"}, "invalid normal_state_status")
    if payload["normal_state_status"] == "verified_normal":
        _require(payload["assertion_status"] == "source_checked" and
                 payload["reference"]["source_kind"] == "primary_experiment" and
                 payload["reference"]["inspection_status"] == "full_text_inspected" and
                 _text(payload["reference"]["locator"]), "verified_normal needs inspected primary experiment and locator")
    window = payload["feature_window"]
    _require(isinstance(window, dict) and all(k in window for k in ("kind", "min_K", "max_K", "defined_at")),
             "feature_window needs explicit kind/min_K/max_K/defined_at")
    _require(window["kind"] in {"absolute_predeclared", "tc_relative", "unspecified"}, "unknown feature-window kind")
    for key in ("min_K", "max_K"):
        _require(window[key] is None or (_number(window[key], 0) and window[key] > 0), "invalid feature-window temperature")
    if window["min_K"] is not None and window["max_K"] is not None:
        _require(window["min_K"] <= window["max_K"], "feature window is reversed")
    if window["defined_at"] is not None:
        _timestamp(window["defined_at"])
    if "feature_eligible" in payload:
        _require(type(payload["feature_eligible"]) is bool and payload["feature_eligible"] == (not _feature_reasons(payload)),
                 "feature_eligible must match the derived eligibility")


def _feature_reasons(payload, *, as_of=None):
    reasons = []
    if payload.get("observation_type") != "normal_state_measurement":
        return ["not a normal-state measurement"]
    if payload["normal_state_status"] != "verified_normal":
        reasons.append("normal state has not been verified")
    if payload["value"] is None or not _text(payload["unit"]):
        reasons.append("quantity value or unit is missing")
    quantity = re.sub(r"[^a-z0-9]", "", payload["quantity"].lower())
    if quantity in {"resistivity", "resistance", "electricalresistivity"} and payload["value"] == 0:
        reasons.append("zero resistance belongs to outcome evidence, not precursor features")
    if payload.get("curation_exclusion_reason"):
        reasons.append("curator excluded this measurement from predictive features")
    for key in IDENTITY_KEYS:
        if payload["conditions"].get(key) is None:
            reasons.append(f"unknown {key}")
    if any(payload["coordinates"][k] is None for k in COORDINATES):
        reasons.append("one or more parameter coordinates are unknown")
    window = payload["feature_window"]
    if window["kind"] != "absolute_predeclared":
        reasons.append("Tc-relative or unspecified windows cannot supply prediction features")
    if window["defined_at"] is None or window["min_K"] is None or window["max_K"] is None:
        reasons.append("absolute window was not fully frozen")
    temp = payload["coordinates"]["temperature_k"]
    if temp is None or window["min_K"] is None or window["max_K"] is None or not window["min_K"] <= temp <= window["max_K"]:
        reasons.append("point is outside the frozen absolute temperature window")
    if payload["reference"]["publication_date"] is None:
        reasons.append("publication date is unknown")
    if as_of is not None:
        cutoff = _timestamp(as_of)
        published = _publication(payload["reference"]["publication_date"])
        if _timestamp(payload["observed_at"]) > cutoff:
            reasons.append("source was not inspected by feature cutoff")
        if window["defined_at"] is not None and _timestamp(window["defined_at"]) > cutoff:
            reasons.append("window was not frozen by feature cutoff")
        if published is not None and (published > cutoff if isinstance(published, datetime) else published > cutoff.date()):
            reasons.append("source was published after feature cutoff")
    return sorted(set(reasons))


def feature_eligibility(payload, *, as_of=None):
    """Return derived feature_eligible, never treat a claimed flag as evidence."""
    validate_observation(payload)
    reasons = _feature_reasons(payload, as_of=as_of)
    return {"feature_eligible": not reasons, "reasons": reasons}


def _record_id(kind, payload, supersedes):
    return _digest({"event_type": kind, "payload": payload, "supersedes": supersedes})


def verify_events(events, *, expected_head=None):
    """Validate chain, schemas, immutable run snapshots, and correction references."""
    previous, seen, replaced, frozen, identities = GENESIS, {}, set(), {}, set()
    for index, event in enumerate(events, 1):
        try:
            _require(isinstance(event, dict), "event must be an object")
            required = {"schema_version", "sequence", "event_type", "payload", "supersedes",
                        "record_id", "recorded_at", "previous_hash", "hash"}
            _require(set(event) == required and type(event["schema_version"]) is int and event["schema_version"] == 1,
                     "invalid event envelope")
            _require(type(event["sequence"]) is int and event["sequence"] == index, "sequence changed")
            _require(event["previous_hash"] == previous, "previous hash mismatch")
            body = {k: v for k, v in event.items() if k != "hash"}
            _require(event["hash"] == _digest(body), "event hash mismatch")
            kind, payload, supersedes = event["event_type"], event["payload"], event["supersedes"]
            _require(event["record_id"] == _record_id(kind, payload, supersedes), "record identity changed")
            _require(event["record_id"] not in identities, "duplicate ledger event")
            recorded = _timestamp(event["recorded_at"])
            if kind == "prediction_snapshot":
                validate_snapshot(payload)
                _require(supersedes is None, "snapshots cannot supersede earlier predictions")
                _require(_timestamp(payload["predicted_at"]) <= recorded, "prediction timestamp is in the future")
                key = _snapshot_key(payload)
                _require(key not in frozen, "a frozen run snapshot was replaced")
                frozen[key] = event["hash"]
            elif kind == "observation":
                validate_observation(payload)
                if payload["observation_type"] == "computed_superconductivity" and payload["assertion_status"] == "source_checked":
                    proof = payload.get("source_verification")
                    _require(isinstance(proof, dict) and proof.get("sha256") == payload["theory"]["source_hash"]
                             and type(proof.get("byte_count")) is int and proof["byte_count"] > 0
                             and proof.get("method") == "sha256_raw_bytes", "original computation source verification is missing")
                _require(_timestamp(payload["observed_at"]) <= recorded, "observation timestamp is in the future")
                if supersedes is not None:
                    old = seen.get(supersedes)
                    _require(old is not None and supersedes not in replaced and old["event_type"] == "observation",
                             "supersedes must name an active earlier observation")
                    _require(old["payload"]["material_id"] == payload["material_id"] and
                             old["payload"]["observation_type"] == payload["observation_type"], "correction scope changed")
                    _require(_text(payload.get("correction_reason")), "correction needs correction_reason")
                    replaced.add(supersedes)
            else:
                raise FeedbackValidationError("unknown event_type")
            if seen:
                _require(recorded >= _timestamp(next(reversed(seen.values()))["recorded_at"]), "ledger clock moved backwards")
            previous = event["hash"]
            seen[previous] = event
            identities.add(event["record_id"])
        except (FeedbackValidationError, KeyError, TypeError) as exc:
            raise LedgerIntegrityError(f"event {index}: {exc}") from exc
    if expected_head is not None and previous != expected_head:
        raise LedgerIntegrityError("head differs from pinned checkpoint")
    return {"events": len(events), "head": previous,
            "snapshots": sum(e["event_type"] == "prediction_snapshot" for e in events),
            "active_observations": sum(e["event_type"] == "observation" and e["hash"] not in replaced for e in events)}


def read_events(path, *, expected_head=None):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise LedgerIntegrityError("unterminated ledger; explicit recovery is required")
    try:
        events = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerIntegrityError("invalid ledger JSONL") from exc
    verify_events(events, expected_head=expected_head)
    return events


def _snapshot_key(payload):
    identity = {k: payload[k] for k in ("material_id", "model_version", "run_id", "target", "score_type", "conditions")}
    if payload["target"] == DFT_TARGET:
        identity["theory"] = payload["theory"]
    return _canonical(identity)


class FeedbackLedger:
    def __init__(self, path, *, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def read(self, *, expected_head=None):
        return read_events(self.path, expected_head=expected_head)

    def append_snapshot(self, payload):
        validate_snapshot(payload)
        return self._append("prediction_snapshot", payload, None)

    def append_observation(self, payload, *, supersedes=None, source_bytes=None):
        validate_observation(payload)
        payload = copy.deepcopy(payload)
        if payload["observation_type"] == "normal_state_measurement":
            payload["feature_eligible"] = not _feature_reasons(payload)
        if payload["observation_type"] == "computed_superconductivity" and payload["assertion_status"] == "source_checked":
            payload["source_verification"] = verify_computation_source(payload, source_bytes)
        elif source_bytes is not None:
            raise FeedbackValidationError("source_bytes are only consumed by checked computation observations")
        return self._append("observation", payload, supersedes)

    def append_observations(self, payloads, *, supersedes=None):
        """Atomically import experimental observations/corrections in input order.

        Repeated records are idempotent, including duplicates within the batch.
        Corrections require an aligned explicit supersedes list and the same
        active-observation/scope/reason checks as individual appends. Checked
        computations retain the single-record source_bytes API. Ledger bytes remain
        an exact prefix; invalid input or a failed write cannot leave half a batch.
        """
        payloads = list(payloads)
        supersedes = [None] * len(payloads) if supersedes is None else list(supersedes)
        _require(len(supersedes) == len(payloads), "supersedes must align with payloads")
        prepared = []
        for payload in payloads:
            validate_observation(payload)
            payload = copy.deepcopy(payload)
            _require(payload["observation_type"] != "computed_superconductivity",
                     "bulk computation imports require per-record source_bytes; use append_observation")
            if payload["observation_type"] == "normal_state_measurement":
                payload["feature_eligible"] = not _feature_reasons(payload)
            prepared.append(json.loads(_canonical(payload)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name + ".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LedgerBusyError("ledger writer lock exists; no automatic lock takeover") from exc
        os.close(fd)
        temporary = None
        try:
            events = read_events(self.path) if self.path.exists() else []
            original = self.path.read_bytes() if self.path.exists() else b""
            by_id = {e["record_id"]: e for e in events}
            added, returned = [], []
            for payload, previous in zip(prepared, supersedes):
                ident = _record_id("observation", payload, previous)
                if ident in by_id:
                    returned.append(by_id[ident])
                    continue
                now = self.clock()
                _require(isinstance(now, datetime) and now.tzinfo is not None,
                         "clock must return aware datetime")
                body = {"schema_version": 1, "sequence": len(events) + 1,
                        "event_type": "observation", "payload": payload,
                        "supersedes": previous, "record_id": ident,
                        "recorded_at": now.astimezone(timezone.utc).isoformat(),
                        "previous_hash": events[-1]["hash"] if events else GENESIS}
                event = dict(body, hash=_digest(body))
                events.append(event)
                by_id[ident] = event
                added.append(event)
                returned.append(event)
            verify_events(events)
            if added:
                with tempfile.NamedTemporaryFile(mode="wb", dir=self.path.parent,
                                                 prefix=self.path.name + ".", suffix=".tmp",
                                                 delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(original)
                    for event in added:
                        handle.write(_canonical(event) + b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                temporary = None
            return copy.deepcopy(returned)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
            lock.unlink()

    def _append(self, kind, payload, supersedes):
        payload = json.loads(_canonical(payload))
        ident = _record_id(kind, payload, supersedes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name + ".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LedgerBusyError("ledger writer lock exists; no automatic lock takeover") from exc
        os.close(fd)
        try:
            events = read_events(self.path) if self.path.exists() else []
            for old in events:
                if old["record_id"] == ident:
                    return copy.deepcopy(old)
                if kind == "prediction_snapshot" and old["event_type"] == kind and _snapshot_key(old["payload"]) == _snapshot_key(payload):
                    raise FeedbackValidationError("prediction for this material/model/run/target is already frozen")
            now = self.clock()
            _require(isinstance(now, datetime) and now.tzinfo is not None, "clock must return aware datetime")
            body = {"schema_version": 1, "sequence": len(events) + 1, "event_type": kind,
                    "payload": payload, "supersedes": supersedes, "record_id": ident,
                    "recorded_at": now.astimezone(timezone.utc).isoformat(),
                    "previous_hash": events[-1]["hash"] if events else GENESIS}
            event = dict(body, hash=_digest(body))
            verify_events(events + [event])
            with self.path.open("ab") as handle:
                handle.write(_canonical(event) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            return copy.deepcopy(event)
        finally:
            lock.unlink()


def _active_observations(events):
    verify_events(events)
    superseded = {e["supersedes"] for e in events if e["supersedes"] is not None}
    return [e for e in events if e["event_type"] == "observation" and e["hash"] not in superseded]


def _sample_label(observation, *, target, threshold_K, query_conditions):
    """A condition-matched binary label, or explicit exclusion reasons; no Tc=0."""
    reasons, observed = [], observation["conditions"]
    if target != SAMPLE_TARGET:
        return None, ["sample evidence cannot label parent doping potential"]
    if observation["observation_type"] != "sample_superconductivity":
        return None, ["not a sample superconductivity observation"]
    if observation["assertion_status"] != "source_checked" or observation["outcome"] is None:
        return None, ["sample result is unknown or not source checked"]
    ref = observation["reference"]
    if ref["source_kind"] != "primary_experiment" or ref["inspection_status"] != "full_text_inspected":
        reasons.append("inspected primary experimental text is required")
    if not isinstance(query_conditions, dict):
        return None, ["query_conditions must be an object"]
    for key in IDENTITY_KEYS:
        actual, wanted = observed.get(key), query_conditions.get(key)
        if actual is None or wanted is None or actual == "" or wanted == "":
            reasons.append(f"unknown {key}")
        elif key in {"pressure_GPa", "field_T"}:
            if not _number(actual, 0) or not _number(wanted, 0):
                reasons.append(f"invalid {key}")
            elif abs(actual - wanted) > 1e-8:
                reasons.append(f"different {key}")
        elif key == "formula":
            try:
                if ND.composition(actual) != ND.composition(wanted):
                    reasons.append("different formula")
            except ValueError:
                reasons.append("invalid formula")
        elif not _text(wanted) or wanted.lower() in {"unknown", "n/a", "not_reported"} or actual != wanted:
            reasons.append(f"different or invalid {key}")
    # Reuse the censored-null condition/window checks for both signs. Positives
    # additionally need the measured transition inside this measured interval.
    record = {"sample_form": observed["sample_form"], "measurement": observed}
    reasons.extend(ND.eligibility(record, target=target, threshold_K=threshold_K,
                                 pressure_GPa=query_conditions.get("pressure_GPa"),
                                 sample_form=query_conditions.get("sample_form"), field_T=query_conditions.get("field_T")))
    if observation["outcome"] is True:
        tc = observation.get("tc_K")
        if not _number(tc, 0) or tc < threshold_K:
            reasons.append("no measured transition at or above target threshold")
        elif observed["t_min_K"] is not None and observed["t_max_K"] is not None and not observed["t_min_K"] <= tc <= observed["t_max_K"]:
            reasons.append("measured Tc lies outside the recorded measurement interval")
    return (None, sorted(set(reasons))) if reasons else (int(observation["outcome"]), [])


def legal_training_export(events, *, target, threshold_K, query_conditions, material_id=None):
    """Explicit export only. Unknown conditions never become zero pressure/labels."""
    _require(target in {SAMPLE_TARGET, PARENT_TARGET}, "unknown training target")
    _require(_number(threshold_K, 0) and threshold_K > 0, "threshold_K must be positive and finite")
    accepted, excluded = [], []
    for event in _active_observations(events):
        obs = event["payload"]
        if material_id is not None and obs["material_id"] != material_id:
            continue
        label, reasons = _sample_label(obs, target=target, threshold_K=threshold_K, query_conditions=query_conditions)
        if reasons:
            excluded.append({"observation_hash": event["hash"], "material_id": obs["material_id"], "reasons": reasons})
        else:
            accepted.append({"observation_hash": event["hash"], "material_id": obs["material_id"],
                             "target": target, "threshold_K": threshold_K, "label": label,
                             "conditions": copy.deepcopy(obs["conditions"]), "reference": copy.deepcopy(obs["reference"])})
    # Contradictory independent records require adjudication, not majority voting.
    conflicting_ids = {r["material_id"] for r in accepted
                       if len({other["label"] for other in accepted if other["material_id"] == r["material_id"]}) > 1}
    excluded.extend({"observation_hash": r["observation_hash"], "material_id": r["material_id"],
                     "reasons": ["conflicting exact-sample observations require a correction/adjudication"]}
                    for r in accepted if r["material_id"] in conflicting_ids)
    accepted = [r for r in accepted if r["material_id"] not in conflicting_ids]
    return {"target": target, "accepted": accepted, "excluded": excluded, "automatic_retraining": False}


def legal_precursor_export(events, *, as_of):
    """Export independent measured points available at a frozen feature cutoff.

    No cross-sample joining, imputation, fitting, or training labels are produced.
    Unknown coordinates remain in the ledger but cannot enter this strict export.
    """
    cutoff = _timestamp(as_of)
    accepted, excluded = [], []
    for event in _active_observations(events):
        payload = event["payload"]
        if payload["observation_type"] != "normal_state_measurement":
            continue
        reasons = _feature_reasons(payload, as_of=as_of)
        if _timestamp(event["recorded_at"]) > cutoff:
            reasons.append("measurement was not frozen by feature cutoff")
        if reasons:
            excluded.append({"observation_hash": event["hash"], "material_id": payload["material_id"],
                             "reasons": sorted(set(reasons))})
            continue
        accepted.append({"observation_hash": event["hash"], "material_id": payload["material_id"],
                         "series_id": payload.get("series_id"),
                         "sample_id": payload["conditions"]["sample_id"], "phase": payload["conditions"]["phase"],
                         "quantity": payload["quantity"], "value": payload["value"], "unit": payload["unit"],
                         "coordinates": copy.deepcopy(payload["coordinates"]),
                         "conditions": copy.deepcopy(payload["conditions"]),
                         "feature_window": copy.deepcopy(payload["feature_window"]),
                         "reference": copy.deepcopy(payload["reference"])})
    return {"as_of": as_of, "accepted": accepted, "excluded": excluded, "automatic_retraining": False}


def _computation_result(payload, *, query_conditions, query_theory):
    if payload["observation_type"] != "computed_superconductivity":
        return None, ["not a computed-superconductivity observation"]
    reasons = []
    if payload["assertion_status"] != "source_checked" or payload["tc_K"] is None:
        reasons.append("computed result is missing or not source checked")
    _require(isinstance(query_conditions, dict), "query_conditions must be an object")
    _theory(query_theory)
    actual = payload["conditions"]
    for key in COMPUTATION_KEYS:
        left, right = actual.get(key), query_conditions.get(key)
        if left is None or right is None:
            reasons.append(f"unknown computational {key}")
        elif key in {"pressure_GPa", "field_T", "doping_fraction", "strain"}:
            lower = None if key == "strain" else 0
            if not _number(right, lower) or (key == "doping_fraction" and right > 1):
                reasons.append(f"invalid computational {key}")
            elif abs(left - right) > 1e-8:
                reasons.append(f"different computational {key}")
        elif key == "formula":
            try:
                if ND.composition(left) != ND.composition(right):
                    reasons.append("different computational formula")
            except ValueError:
                reasons.append("invalid computational formula")
        elif left != right:
            reasons.append(f"different computational {key}")
    actual_theory = payload["theory"]
    for key in ("method", "mu_star", "component_units"):
        left, right = actual_theory[key], query_theory[key]
        if left is None or right is None:
            reasons.append(f"unknown theory {key}")
        elif key == "mu_star":
            if abs(left - right) > 1e-12:
                reasons.append("different theory mu_star")
        elif key == "method":
            normalize = lambda value: re.sub(r"[^a-z0-9]", "", value.lower()).removeprefix("dft")
            if normalize(left) != normalize(right):
                reasons.append("different theory method")
        elif left != right:
            reasons.append("different theory component_units")
    if query_theory["source_hash"] is not None and actual_theory["source_hash"] != query_theory["source_hash"]:
        reasons.append("different original computation source hash")
    # Additional declared theory settings (e.g. XC functional) are not dropped.
    extra_keys = (set(actual_theory) | set(query_theory)) - set(THEORY_KEYS)
    for key in extra_keys:
        if actual_theory.get(key) is None or query_theory.get(key) is None:
            reasons.append(f"unknown theory {key}")
        elif actual_theory[key] != query_theory[key]:
            reasons.append(f"different theory {key}")
    return (None, sorted(set(reasons))) if reasons else (payload["tc_K"], [])


def legal_computation_export(events, *, query_conditions, query_theory, material_id=None):
    """Separate numerical DFT targets; never sample/parent SC labels or rewards.

    A query's source_hash may be null when the future source does not yet exist.
    Actual source provenance is mandatory and verified when appended. All physical
    theory settings must match; supplied source_hash constraints also must match.
    """
    _theory(query_theory)
    accepted, excluded = [], []
    for event in _active_observations(events):
        payload = event["payload"]
        if material_id is not None and payload["material_id"] != material_id:
            continue
        value, reasons = _computation_result(payload, query_conditions=query_conditions, query_theory=query_theory)
        if reasons:
            excluded.append({"observation_hash": event["hash"], "material_id": payload["material_id"], "reasons": reasons})
        else:
            accepted.append({"observation_hash": event["hash"], "material_id": payload["material_id"],
                             "target": DFT_TARGET, "tc_K": value, "conditions": copy.deepcopy(payload["conditions"]),
                             "theory": copy.deepcopy(payload["theory"]), "reference": copy.deepcopy(payload["reference"]),
                             "source_verification": copy.deepcopy(payload["source_verification"])})
    conflicting = {r["material_id"] for r in accepted
                   if len({x["tc_K"] for x in accepted if x["material_id"] == r["material_id"]}) > 1}
    excluded.extend({"observation_hash": r["observation_hash"], "material_id": r["material_id"],
                     "reasons": ["conflicting computed Tc records require correction/adjudication"]}
                    for r in accepted if r["material_id"] in conflicting)
    return {"target": DFT_TARGET, "accepted": [r for r in accepted if r["material_id"] not in conflicting],
            "excluded": excluded, "automatic_retraining": False, "experimental_labels": 0}


def _timing(snapshot, observation):
    published = _publication(observation["payload"]["reference"]["publication_date"])
    predicted, frozen = _timestamp(snapshot["payload"]["predicted_at"]), _timestamp(snapshot["recorded_at"])
    if published is None:
        return "undated"
    if isinstance(published, datetime):
        if published <= predicted:
            return "retrospective"
        return "prospective" if frozen < published else "retrospective_late_freeze"
    if published < predicted.date():
        return "retrospective"
    if published == predicted.date() or published == frozen.date():
        return "same_day_uncertain"
    return "prospective" if frozen.date() < published else "retrospective_late_freeze"


def evaluate_feedback(events, *, snapshot_hash, observation_hash):
    """Only prospective exact-sample outcomes get SC hits; DFT error is predicted minus observed K."""
    verify_events(events)
    by_hash = {e["hash"]: e for e in events}
    _require(snapshot_hash in by_hash and observation_hash in by_hash, "evaluation event not in verified ledger")
    snapshot, observation = by_hash[snapshot_hash], by_hash[observation_hash]
    _require(snapshot["event_type"] == "prediction_snapshot" and observation["event_type"] == "observation", "wrong evaluation event types")
    p, obs, reasons = snapshot["payload"], observation["payload"], []
    mode = _timing(snapshot, observation)
    if snapshot["sequence"] >= observation["sequence"]:
        reasons.append("snapshot was not frozen before this feedback event")
    if observation_hash not in {e["hash"] for e in _active_observations(events)}:
        reasons.append("observation was superseded")
    if p["material_id"] != obs["material_id"]:
        reasons.append("different material_id")
    if p["target"] == DFT_TARGET:
        value, more = _computation_result(obs, query_conditions=p["conditions"], query_theory=p["theory"])
        reasons.extend(more)
        exported = legal_computation_export(events, query_conditions=p["conditions"], query_theory=p["theory"],
                                             material_id=p["material_id"])
        for excluded in exported["excluded"]:
            if excluded["observation_hash"] == observation_hash:
                reasons.extend(excluded["reasons"])
        if obs["reference"]["publication_date"] is None:
            reasons.append("computed source publication date is unknown")
        comparable = not reasons and value is not None
        error = p["score"] - value if comparable else None
        return {"snapshot_hash": snapshot_hash, "observation_hash": observation_hash, "target": DFT_TARGET,
                "evaluation_channel": "computation", "evaluation_mode": mode,
                "computed_error_K": error, "computed_absolute_error_K": abs(error) if error is not None else None,
                "strict_hit": None, "retrospective_agreement": None, "eligible_for_prospective_metrics": False,
                "eligible_for_prospective_computation_metrics": comparable and mode == "prospective",
                "experimental_labels": 0, "automatic_retraining": False,
                "reasons": sorted(set(reasons + ([] if mode == "prospective" else ["not a dated prospective computation validation"])))}
    threshold = p.get("threshold_K")
    if not _number(threshold, 0) or threshold <= 0:
        label = None
        reasons.append("prediction did not freeze a sample threshold_K")
    else:
        label, more = _sample_label(obs, target=p["target"], threshold_K=threshold, query_conditions=p["conditions"])
        reasons.extend(more)
        exported = legal_training_export(events, target=p["target"], threshold_K=threshold,
                                         query_conditions=p["conditions"], material_id=p["material_id"])
        for excluded in exported["excluded"]:
            if excluded["observation_hash"] == observation_hash:
                reasons.extend(excluded["reasons"])
    prediction = None
    if p["score_type"] == "sample_probability" and p.get("decision_threshold") is not None:
        prediction = p["score"] >= p["decision_threshold"]
    elif p["score_type"] == "tc_K" and threshold is not None:
        prediction = p["score"] >= threshold
    else:
        reasons.append("score has no frozen sample decision rule")
    comparable = not reasons and prediction is not None and label is not None
    agreement = bool(prediction == bool(label)) if comparable else None
    return {"snapshot_hash": snapshot_hash, "observation_hash": observation_hash, "evaluation_mode": mode,
            "strict_hit": agreement if mode == "prospective" else None,
            "retrospective_agreement": agreement if mode.startswith("retrospective") else None,
            "eligible_for_prospective_metrics": comparable and mode == "prospective",
            "reasons": sorted(set(reasons + ([] if mode == "prospective" else ["not a dated prospective validation"]))) }


def select_next_batch(candidates, events=(), *, budget, target, threshold_K=None, mix=None):
    """Mix score/disagreement/domain-distance checks, without training or imputing labels.

    Each candidate supplies material_id, score, score_type and optional conditions,
    disagreement, domain_distance. Higher is selected first for each policy. Only
    exact-sample results that pass legal export remove a matching planned check.
    A literature search with no result never removes an otherwise eligible check.
    """
    _require(type(budget) is int and budget >= 0, "budget must be a nonnegative integer")
    _require(target in {SAMPLE_TARGET, PARENT_TARGET, DFT_TARGET}, "unknown selection target")
    _active_observations(events)  # Verify even an empty candidate batch.
    if threshold_K is not None:
        _require(_number(threshold_K, 0) and threshold_K > 0, "invalid selection threshold_K")
    rules = {"high_score": "score", "disagreement": "disagreement", "exploration": "domain_distance"}
    weights = {"high_score": .5, "disagreement": .25, "exploration": .25} if mix is None else mix
    _require(isinstance(weights, dict) and set(weights) == set(rules) and
             all(_number(v, 0) for v in weights.values()) and sum(weights.values()) > 0, "invalid selection mix")
    prepared, seen, score_types = [], set(), set()
    for rec in candidates:
        _require(isinstance(rec, dict) and _text(rec.get("material_id")) and
                 rec.get("score_type") in SCORE_TYPES and _number(rec.get("score")), "invalid candidate score/identity")
        if rec["score_type"].endswith("probability"):
            _require(0 <= rec["score"] <= 1, "candidate probability must be between zero and one")
            expected = PARENT_TARGET if rec["score_type"] == "parent_probability" else SAMPLE_TARGET
            _require(target == expected, "candidate probability score_type disagrees with target")
        if rec["score_type"] == "tc_K":
            _require(rec["score"] >= 0 and target in {SAMPLE_TARGET, DFT_TARGET}, "invalid candidate tc_K target/score")
        if target == DFT_TARGET:
            _require(rec["score_type"] == "tc_K", "DFT candidates need tc_K scores")
        for name in ("disagreement", "domain_distance"):
            _require(name not in rec or _number(rec[name], 0), f"invalid candidate {name}")
        cond = rec.get("conditions", {})
        _require(isinstance(cond, dict), "candidate conditions must be an object")
        if target == DFT_TARGET:
            _conditions(cond)
            _computation_conditions(cond)
            _theory(rec.get("theory"))
        key = _canonical([rec["material_id"], target, cond, rec.get("theory") if target == DFT_TARGET else None])
        if key in seen:
            continue
        seen.add(key)
        known = False
        if target == DFT_TARGET:
            known = bool(legal_computation_export(events, query_conditions=cond, query_theory=rec["theory"],
                                                   material_id=rec["material_id"])["accepted"])
        elif threshold_K is not None:
            exported = legal_training_export(events, target=target, threshold_K=threshold_K,
                                             query_conditions=cond, material_id=rec["material_id"])
            known = bool(exported["accepted"])
        if not known:
            prepared.append((key, rec))
            score_types.add(rec["score_type"])
    _require(len(score_types) <= 1, "batch scores must have a common score_type")
    count = min(budget, len(prepared))
    raw = {k: count * weights[k] / sum(weights.values()) for k in rules}
    quotas = {k: math.floor(raw[k]) for k in rules}
    for k in sorted(rules, key=lambda k: (-(raw[k] - quotas[k]), list(rules).index(k)))[:count-sum(quotas.values())]:
        quotas[k] += 1
    chosen, selected = [], set()
    for policy, field in rules.items():
        queue = sorted(prepared, key=lambda item: (-item[1].get(field, 0), item[1]["material_id"], item[0]))
        for key, rec in queue:
            if key in selected:
                continue
            if quotas[policy] == 0:
                break
            selected.add(key)
            chosen.append(dict(copy.deepcopy(rec), selection_reason=policy))
            quotas[policy] -= 1
    return chosen


def audit_ledger(path=None, *, expected_head=None):
    """Read-only audit; an absent optional ledger is explicitly empty, never created."""
    exists = path is not None and Path(path).exists()
    if exists:
        events = read_events(path, expected_head=expected_head)
    else:
        events = []
    report = verify_events(events, expected_head=expected_head)
    active = _active_observations(events)
    report.update(valid=True, exists=exists, ledger=str(path) if path is not None else None,
                  observation_types={kind: sum(e["payload"]["observation_type"] == kind for e in active)
                                     for kind in sorted(OBSERVATION_TYPES)},
                  normal_state_feature_eligible=sum(e["payload"]["observation_type"] == "normal_state_measurement"
                                                    and not _feature_reasons(e["payload"]) for e in active),
                  automatic_retraining=False,
                  normal_state_policy="Experimental precursor export only; computed normal properties use a separate simulation channel, not silently mixed. Existing DFT training loaders are unaffected.",
                  computation_policy="Computed Allen-Dynes Tc has a separate target/export/error metric; never experimental SC hits or sample/parent negatives.")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", type=Path)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--queue", type=Path, help="flat JSON array with explicit score and score_type")
    parser.add_argument("--ledger", type=Path, help="optional existing ledger for audit/queue; never created")
    parser.add_argument("--expected-head")
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--target", choices=sorted({SAMPLE_TARGET, PARENT_TARGET, DFT_TARGET}), default=PARENT_TARGET)
    parser.add_argument("--threshold-K", type=float)
    args = parser.parse_args(argv)
    try:
        if args.verify is not None:
            events = read_events(args.verify, expected_head=args.expected_head)
            result = dict(valid=True, **verify_events(events, expected_head=args.expected_head))
        elif args.audit:
            result = audit_ledger(args.ledger, expected_head=args.expected_head)
        else:
            candidates = json.loads(args.queue.read_text(encoding="utf-8"))
            _require(isinstance(candidates, list), "queue input must be a flat JSON array")
            candidates = [dict(row, material_id=row.get("material_id", row.get("id"))) if isinstance(row, dict)
                          else row for row in candidates]
            events = read_events(args.ledger, expected_head=args.expected_head) if args.ledger and args.ledger.exists() else []
            verify_events(events, expected_head=args.expected_head)
            result = {"valid": True, "target": args.target, "automatic_retraining": False,
                      "selected": select_next_batch(candidates, events, budget=args.budget, target=args.target,
                                                     threshold_K=args.threshold_K)}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, json.JSONDecodeError, LedgerIntegrityError, FeedbackValidationError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
