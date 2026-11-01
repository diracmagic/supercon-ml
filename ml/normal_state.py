"""Source-bound normal-state curves and exact-specimen measured-Tc joins.

No model is fit by default. The explicit measured-Tc pilot requires source-bound
evidence, its separately frozen protocol and sufficient independent units. The
module never labels a parent, joins an experiment to a DFT structure by formula,
or alters feedback's strict default exports. It freezes absolute-temperature
features and preserves incomplete observations even when training is refused.
"""
from __future__ import annotations

import argparse
import copy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

try:
    from . import feedback as F
except ImportError:
    import feedback as F

VERSION = "normal-state-sample-pilot-v2"
TRANSPORT = {"resistivity", "resistance", "normalized_resistivity", "normalized_resistance"}
SECONDARY = {"magnetic_susceptibility", "heat_capacity", "specific_heat", "magnetization"}
FIXED_COORDINATES = ("pressure_gpa", "doping_fraction", "strain", "magnetic_field_t")
BASE_POLICY = {
    "version": VERSION,
    "preflight_amendment": {"supersedes": "normal-state-sample-pilot-v1 unrun scaffold",
                            "reason": "Availability-driven same-run scope: unreported P/B may be nuisance only for a trace-bound Tc, never a cross-trace condition match",
                            "no_real_fit_observed": True, "absolute_windows_unchanged": True},
    "target": "measured Tc of the explicitly linked physical specimen at declared conditions; not DFT or parent potential",
    "window_k": [150., 300.], "transport_anchors_k": [200., 250.],
    "curvature_midpoint_k": 225., "minimum_unique_temperatures": 5,
    "maximum_interpolation_bracket_k": 50., "extrapolation": False,
    "transport_features": ["log_ratio_250_200", "normalized_secant_per_k", "normalized_curvature_per_k2"],
    "transport_feature_definitions": {"log_ratio_250_200": "ln(y250/y200)",
                                      "normalized_secant_per_k": "(y250-y200)/(50*(y250+y200)/2)",
                                      "normalized_curvature_per_k2": "(y200-2*y225+y250)/(625*(y250+y200)/2)"},
    "secondary_policy": "Same fixed window/anchors; retain observable and original units. Secondary channels are not primary training inputs.",
    "allowed_unknown_nuisance": ["strain"],
    "unknown_phase": "Only an inspected explicit same-physical-specimen link; no DFT phase binding",
    "unknown_doping": "Only an inspected same-specimen link; retain null and prohibit doping-axis learning for this row",
    "essential_known_conditions_in_cross_trace_scope": ["pressure_gpa", "magnetic_field_t"],
    "matching_scopes": {"same_specimen_condition_matched": "Known matching P/B, inspected physical-specimen link",
                        "same_run_measured_tc": "Same immutable raw-source hash, curve, measurement-run and trace-column identity; explicit varied_axes; no unknown controlled axis. Unknown unused P/B retained null with no condition-generalization claim"},
    "condition_tolerance": 1e-8,
    "normalization": "Never T/Tc, Tc-derived scales, zero resistance, Meissner onset or heat-capacity jumps",
    "primary_model_plan": "Fixed Ridge on log1p measured Tc; same-cohort composition/known-condition reference versus added transport shapes. No fit until split/criterion frozen.",
    "minimum_independent_components": 5, "minimum_training_components": 3, "minimum_training_samples": 5,
    "grouping": "Connected components of chemical system, inspected primary source, physical specimen and source-namespaced series; all conditions/temperatures stay together",
    "independent_unit": "Physical specimen and condition, never individual temperature points",
    "timing": "Frozen during source curation and before any real model fitting/scoring; some paper Tc values and curve ranges already inspected; retrospective exploratory, not blinded.",
    "automatic_training": False,
}
CRITERION_ALIASES = {"resistive_midpoint": "resistive_midpoint", "resistivity_midpoint": "resistive_midpoint",
                     "resistive_midpoint_50pct": "resistive_midpoint", "50_percent_normal_resistance": "resistive_midpoint"}
PILOT_CONDITIONS = ("pressure_gpa", "magnetic_field_t", "doping_fraction")
COMPOSITION_FEATURES = ("mean_atomic_Z", "mean_atomic_mass", "mean_electronegativity", "n_elements")
TRAINING_PROTOCOL = {
    "version": "storm-normal-state-pilot-v1", "model_name": "Storm-normal-state-pilot", "adopted": False,
    "target": "log1p of observed positive same-specimen measured resistive-midpoint Tc in K",
    "criterion_aliases": CRITERION_ALIASES, "censored_null": "Never Tc=0; exclude from this positive-Tc regression",
    "composition_quality": "Require an explicit reported sample formula; exclude unknown, replica proxies and approximations not measured on the sample",
    "baseline": {"composition": list(COMPOSITION_FEATURES), "conditions": list(PILOT_CONDITIONS),
                 "missing_flags": "One indicator for every numeric baseline feature", "quantity_one_hot": sorted(TRANSPORT)},
    "augmented": "Exactly the same baseline plus the frozen three transport-shape features",
    "learner": {"class": "sklearn.linear_model.Ridge", "alpha": 1., "fit_intercept": True, "solver": "svd",
                "sample_weights": "Uniform per unique eligible specimen-condition; no temperature-point replication", "target_transform": "log1p",
                "inverse_transform": "clip(expm1, min=0)", "hyperparameter_search": False},
    "preprocessing": "Training-fold mean/std of observed entries; unknown becomes zero only in centered/scaled space, never a physical zero. Drop all-missing/constant training columns. Shared unknown-condition flags and observable types in both designs.",
    "unknown_condition_axis": "Use a numeric condition only if both measured input and target conditions support it; unknown rows have zero centered feature and cannot identify its coefficient",
    "split": "Leave one complete source/system/specimen/series connected component out, covering all eligible rows",
    "minimum_components": 5, "minimum_training_components": 3, "minimum_training_specimen_conditions": 5,
    "duplicate_unit": "Duplicate specimen-condition/criterion rows require explicit adjudication; never silently count multiple modalities/criteria as extra samples",
    "metrics": {"primary": "Equal-component macro MAE in raw K", "secondary": ["row MAE K", "row RMSE K", "fold errors"],
                "paired_bootstrap": {"resamples": 1000, "seed": 7, "unit": "independent connected component", "quantity": "augmented minus baseline macro MAE", "interval": "percentile 95%, exploratory with few groups"}},
    "timing": "Retrospective replay of already published measurements; source Tc values may already be inspected, no prospective-discovery claim",
    "release": "Separate measured-sample pilot, not an upgrade or validation of Storm's existing DFT Tc model; no winner release",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _time(value):
    _require(_text(value), "Timezone-aware timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "Timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def policy_document(defined_at=None):
    document = copy.deepcopy(BASE_POLICY)
    document["defined_at"] = defined_at or datetime.now(timezone.utc).isoformat()
    _time(document["defined_at"])
    return document


def validate_policy(policy):
    _require(isinstance(policy, dict), "Policy must be explicit")
    _require({k: v for k, v in policy.items() if k != "defined_at"} == BASE_POLICY,
             "Extraction rules differ from this version's frozen policy")
    _time(policy.get("defined_at"))


def freeze_policy(output_dir, *, defined_at=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "normal-state-policy.json"
    document = policy_document(defined_at)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        validate_policy(existing)
        if defined_at is None:
            document = existing
        _require(existing == document, "Refusing to replace a frozen extraction policy")
    path.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "normal-state-policy.sha256").write_text(sha256(document) + "\n", encoding="utf-8")
    return document


def source_registry(document, *, source_root):
    """Bind every supplied raw file to bytes in one explicit collection root."""
    _require(isinstance(document, dict) and isinstance(document.get("sources"), list), "Source registry needs sources[]")
    root, result = Path(source_root).resolve(), {}
    for source in document["sources"]:
        _require(isinstance(source, dict) and _text(source.get("source_id")), "Missing source ID")
        identifier = source["source_id"]
        _require(identifier not in result, "Duplicate source ID")
        relative = source.get("raw_path")
        _require(_text(relative) and not Path(relative).is_absolute(), "Raw path must be relative to collection root")
        path = (root / relative).resolve()
        _require(root in path.parents, "Raw source escaped collection root")
        expected = source.get("sha256")
        _require(isinstance(expected, str) and re.fullmatch("[0-9a-f]{64}", expected), "Raw SHA256 required")
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected, "Raw source SHA256 mismatch")
        reference = source.get("reference")
        _require(isinstance(reference, dict) and reference.get("source_kind") == "primary_experiment", "Primary experimental source required")
        _require(reference.get("inspection_status") in {"full_text_inspected", "data_inspected"}, "Primary source must actually be inspected")
        result[identifier] = copy.deepcopy(source)
    return result


def _source_identity(reference):
    if _text(reference.get("doi")):
        return "doi:" + reference["doi"].removeprefix("https://doi.org/").lower()
    return "url:" + str(reference.get("url"))


def _quantity_forbidden(value):
    name = re.sub("[^a-z0-9]", "", str(value).lower())
    return any(k in name for k in ("meissner", "zeroresistan", "heatcapacityjump", "specificheatjump", "tcrelative", "ttc", "criticaltemperature", "superconductingtransition")) or name in {"tc", "tck"}


def point_coordinates(curve, point):
    coordinates = dict(curve["fixed_coordinates"], temperature_k=point["temperature_k"])
    overrides = point.get("coordinates", {})
    _require(isinstance(overrides, dict) and all(k in F.COORDINATES for k in overrides), "Invalid point coordinate overrides")
    for axis, value in overrides.items():
        _require(value is None or (_number(value) and (axis == "strain" or value >= 0)), "Invalid measured point coordinate")
        _require(axis != "temperature_k" or value == point["temperature_k"], "Point temperature declarations disagree")
        _require(axis != "doping_fraction" or value is None or value <= 1, "Point doping uses fractions")
        if coordinates[axis] is not None:
            _require(value == coordinates[axis], "Measured point coordinate conflicts with known fixed coordinate")
        else:
            coordinates[axis] = value
    return coordinates


def point_conditions(curve, point, coordinates):
    conditions = copy.deepcopy(curve["conditions"])
    conditions["pressure_GPa"], conditions["field_T"] = coordinates["pressure_gpa"], coordinates["magnetic_field_t"]
    for axis in ("doping_fraction", "strain"):
        if axis in point.get("coordinates", {}):
            conditions[axis] = coordinates[axis]
    return conditions


def validate_curve(curve, registry):
    _require(isinstance(curve, dict), "Curve must be an object")
    for key in ("curve_id", "source_id", "material_id", "specimen_id", "quantity"):
        _require(_text(curve.get(key)), f"Missing curve {key}")
    _require(curve["source_id"] in registry, "Curve source not in verified registry")
    _require(not _quantity_forbidden(curve["quantity"]), "SC outcomes cannot be normal-state quantities")
    _require(curve.get("unit") is None or _text(curve["unit"]), "Unit must be original explicit text or null")
    _require(curve.get("series_id") is None or _text(curve["series_id"]), "Series ID must be explicit or null")
    _time(curve.get("observed_at"))
    F._conditions(curve.get("conditions"))
    fixed = curve.get("fixed_coordinates")
    _require(isinstance(fixed, dict) and set(fixed) == set(FIXED_COORDINATES), "All fixed coordinates required, unknown values null")
    for key, value in fixed.items():
        _require(value is None or (_number(value) and (key == "strain" or value >= 0)), f"Invalid {key}")
    _require(fixed["doping_fraction"] is None or fixed["doping_fraction"] <= 1, "Doping uses fractions")
    for key, old in (("pressure_gpa", "pressure_GPa"), ("magnetic_field_t", "field_T")):
        _require(fixed[key] == curve["conditions"][old], "Fixed coordinate disagrees with declared conditions")
    _require(curve.get("normal_state_status") in {"verified_normal", "unknown"}, "Normal-state status must be explicit")
    if curve["normal_state_status"] == "verified_normal":
        proof = curve.get("normal_state_evidence")
        _require(isinstance(proof, dict) and _text(proof.get("locator")) and _text(proof.get("statement")), "Normal-state assertion needs inspected evidence")
        limits = proof.get("verified_range_k")
        _require(isinstance(limits, list) and len(limits) == 2 and all(_number(v) and v > 0 for v in limits) and limits[0] <= limits[1], "Verified normal-state range required")
        _require(registry[curve["source_id"]]["reference"]["inspection_status"] == "full_text_inspected", "Verified normal state needs inspected primary text")
    points = curve.get("points")
    _require(isinstance(points, list) and len(points) > 0, "Measured points required")
    for point in points:
        _require(isinstance(point, dict) and _number(point.get("temperature_k")) and point["temperature_k"] > 0, "Point temperature must be measured in K")
        _require(point.get("value") is None or _number(point["value"]), "Point value must be finite or null")
        _require(_text(point.get("source_locator")), "Every point needs its own row/sheet/figure locator")
        point_coordinates(curve, point)
        if "coordinate_provenance" in point:
            _require(isinstance(point["coordinate_provenance"], dict), "Coordinate conversion provenance must be explicit mapping")
        if "field_orientation" in point:
            _require(isinstance(point["field_orientation"], dict), "Signed field/orientation must be explicit metadata")
        if "source_unit_conversion" in point:
            _require(_text(point["source_unit_conversion"]), "Unit conversion explanation must be explicit text")
    canonical(curve)
    return curve


def curve_observations(curve, registry, policy, *, point_indices=None):
    """Return payloads for the ordinary ledger writer; never write or bypass it."""
    validate_policy(policy)
    validate_curve(curve, registry)
    source = registry[curve["source_id"]]
    curve_hash, policy_hash = sha256(curve), sha256(policy)
    result = []
    indices = range(len(curve["points"])) if point_indices is None else point_indices
    for index in indices:
        _require(type(index) is int and 0 <= index < len(curve["points"]), "Invalid requested point index")
        point = curve["points"][index]
        temp = point["temperature_k"]
        proof = curve.get("normal_state_evidence", {})
        verified = curve["normal_state_status"] == "verified_normal" and proof["verified_range_k"][0] <= temp <= proof["verified_range_k"][1]
        coordinates = point_coordinates(curve, point)
        payload = {"material_id": curve["material_id"], "observed_at": curve["observed_at"],
                   "statement": "Source-bound measured curve point; normal-state status is separately curated.",
                   "observation_type": "normal_state_measurement", "assertion_status": "source_checked", "outcome": None,
                   "quantity": curve["quantity"], "value": point["value"], "unit": curve["unit"],
                   "coordinates": coordinates, "conditions": point_conditions(curve, point, coordinates),
                   "normal_state_status": "verified_normal" if verified else "unknown",
                   "feature_window": {"kind": "absolute_predeclared", "min_K": policy["window_k"][0], "max_K": policy["window_k"][1], "defined_at": policy["defined_at"]},
                   "series_id": curve.get("series_id"), "curve_id": curve["curve_id"], "specimen_id": curve["specimen_id"],
                   "raw_source_sha256": source["sha256"], "normal_state_policy_sha256": policy_hash,
                   "curve_content_sha256": curve_hash,
                   "measurement_run_id": curve.get("measurement_run_id"), "trace_id": curve.get("trace_id"),
                   "varied_axes": curve.get("varied_axes"),
                   "point_provenance": {"source_id": curve["source_id"], "point_index": index, "locator": point["source_locator"]},
                   "reference": copy.deepcopy(source["reference"])}
        if "coordinate_provenance" in point:
            payload["coordinate_provenance"] = copy.deepcopy(point["coordinate_provenance"])
        for key in ("field_orientation", "source_unit_conversion"):
            if key in point:
                payload[key] = copy.deepcopy(point[key])
        F.validate_observation(payload)
        result.append(payload)
    return result


def _interpolate(temperatures, values, anchor, max_gap):
    if anchor in temperatures:
        return float(values[np.flatnonzero(temperatures == anchor)[0]])
    upper = int(np.searchsorted(temperatures, anchor))
    _require(0 < upper < len(temperatures), "Anchor outside measured range; extrapolation prohibited")
    _require(temperatures[upper] - temperatures[upper - 1] <= max_gap, "Anchor interpolation bracket too wide")
    return float(np.interp(anchor, temperatures, values))


def extract_features(curve, registry, policy):
    """Target-independent curve summaries. Unknown/unsupported data remain explicit."""
    validate_policy(policy)
    validate_curve(curve, registry)
    result = {"curve_id": curve["curve_id"], "quantity": curve["quantity"], "unit": curve["unit"],
              "policy_sha256": sha256(policy), "status": "insufficient_data", "features": {}, "reasons": [],
              "raw_point_count": len(curve["points"]), "statistical_sample_count": 1,
              "source_sha256": registry[curve["source_id"]]["sha256"], "curve_content_sha256": sha256(curve)}
    if curve["normal_state_status"] != "verified_normal":
        result["reasons"].append("Normal state was not verified")
    if not _text(curve["unit"]):
        result["reasons"].append("Original response unit is unknown")
    normalization = curve.get("normalization", {"kind": "none"})
    if (not isinstance(normalization, dict) or normalization.get("kind") not in {"none", "fixed_reference_temperature", "published_constant_scale"}
            or _quantity_forbidden(json.dumps(normalization)) or re.search(r'(?i)(?<![a-z])tc(?![a-z])', json.dumps(normalization))):
        result["reasons"].append("Outcome-derived or unspecified normalization")
    elif normalization.get("kind") == "fixed_reference_temperature" and not (
            _number(normalization.get("reference_temperature_k")) and policy["window_k"][0] <= normalization["reference_temperature_k"] <= policy["window_k"][1]):
        result["reasons"].append("Normalization reference is outside frozen normal window")
    if curve["quantity"] not in TRANSPORT | SECONDARY:
        result["reasons"].append("Observable has no frozen extractor")
    effective = copy.deepcopy(curve["fixed_coordinates"])
    any_overrides = any(bool(p.get("coordinates")) for p in curve["points"])
    if any_overrides:
        measured_coordinates = [point_coordinates(curve, p) for p in curve["points"]]
        for axis in FIXED_COORDINATES:
            values = {c[axis] for c in measured_coordinates}
            if len(values) > 1:
                result["reasons"].append("Non-temperature coordinate varies or is partially unknown: " + axis)
            elif len(values) == 1:
                effective[axis] = next(iter(values))
        result["effective_fixed_coordinates"] = effective
    normal_range = curve.get("normal_state_evidence", {}).get("verified_range_k", [float("inf"), -float("inf")])
    selected_indices = [i for i, p in enumerate(curve["points"]) if policy["window_k"][0] <= p["temperature_k"] <= policy["window_k"][1]
                        and normal_range[0] <= p["temperature_k"] <= normal_range[1] and p["value"] is not None]
    selected = [curve["points"][i] for i in selected_indices]
    result["used_point_indices"] = selected_indices
    if curve["quantity"] in TRANSPORT and any(p["value"] <= 0 for p in selected):
        result["reasons"].append("Nonpositive transport points cannot be normal-state features")
    if result["reasons"]:
        return result
    buckets = {}
    for point in selected:
        buckets.setdefault(float(point["temperature_k"]), []).append(float(point["value"]))
    result["window_point_count"], result["unique_temperature_count"] = len(selected), len(buckets)
    if len(buckets) < policy["minimum_unique_temperatures"]:
        result["reasons"].append("Too few distinct temperatures in frozen window")
        return result
    t = np.array(sorted(buckets))
    y = np.array([np.mean(buckets[value]) for value in t])
    try:
        low, high = policy["transport_anchors_k"]
        middle = policy["curvature_midpoint_k"]
        normal_range = curve["normal_state_evidence"]["verified_range_k"]
        _require(normal_range[0] <= low and normal_range[1] >= high,
                 "Normal-state verification does not cover fixed anchors")
        vlow, vmid, vhigh = [_interpolate(t, y, anchor, policy["maximum_interpolation_bracket_k"]) for anchor in (low, middle, high)]
        if curve["quantity"] in TRANSPORT:
            mean = (vlow + vhigh) / 2
            features = {"log_ratio_250_200": float(np.log(vhigh / vlow)),
                        "normalized_secant_per_k": float((vhigh - vlow) / ((high - low) * mean)),
                        "normalized_curvature_per_k2": float((vlow - 2 * vmid + vhigh) / ((middle - low) ** 2 * mean))}
        else:
            features = {"value_200": vlow, "value_250": vhigh,
                        "secant_per_k": (vhigh - vlow) / (high - low),
                        "curvature_per_k2": (vlow - 2 * vmid + vhigh) / (middle - low) ** 2}
        _require(all(_number(v) for v in features.values()), "Non-finite extracted features")
        result.update(status="ready", features=features, anchor_values={"200": vlow, "225": vmid, "250": vhigh},
                      feature_units="dimensionless shape / K powers" if curve["quantity"] in TRANSPORT else curve["unit"] + " with declared K powers",
                      replicate_temperatures=int(sum(len(v) > 1 for v in buckets.values())))
    except ValueError as error:
        result["reasons"].append(str(error))
    return result


def _link_reasons(normal, target, link):
    reasons = []
    if not isinstance(link, dict) or link.get("same_physical_specimen") is not True or link.get("assertion_status") != "source_checked" or not _text(link.get("source_locator")):
        return ["Inspected explicit same-physical-specimen link required"]
    if link.get("specimen_id") != normal.get("specimen_id") or link.get("curve_id") != normal.get("curve_id"):
        reasons.append("Link does not name this physical specimen and curve")
    reference = target.get("reference", {})
    if target.get("observation_type") != "sample_superconductivity" or target.get("assertion_status") != "source_checked" or reference.get("source_kind") != "primary_experiment" or reference.get("inspection_status") != "full_text_inspected" or not _text(reference.get("locator")):
        reasons.append("Link target requires inspected primary sample evidence")
    scope = link.get("scope", "same_specimen_condition_matched")
    if scope not in BASE_POLICY["matching_scopes"]:
        reasons.append("Unknown matching scope")
    same_run = scope == "same_run_measured_tc"
    if same_run:
        if link.get("same_raw_trace") is not True:
            reasons.append("Same-run scope requires inspected same_raw_trace assertion")
        for key in ("measurement_run_id", "trace_id", "raw_source_sha256"):
            actual = normal.get(key)
            if not _text(actual) or target.get(key) != actual or link.get(key) != actual:
                reasons.append("Same-run binding mismatch: " + key)
        if target.get("derived_from_curve_id") != normal.get("curve_id"):
            reasons.append("Target is not derived from this exact curve")
        axes = normal.get("varied_axes")
        if not isinstance(axes, list) or not axes or len(set(axes)) != len(axes) or any(a not in F.COORDINATES for a in axes) or "temperature_k" not in axes:
            reasons.append("Same-run scope needs explicit measured varied_axes")
        else:
            if target.get("varied_axes") != axes or link.get("varied_axes") != axes:
                reasons.append("Same-run varied-axis declarations disagree")
            for axis in axes:
                if axis != "temperature_k" and (normal["coordinates"].get(axis) is None or target["conditions"].get(axis if axis not in {"pressure_gpa", "magnetic_field_t"} else {"pressure_gpa": "pressure_GPa", "magnetic_field_t": "field_T"}[axis]) is None):
                    reasons.append("Unknown controlled axis: " + axis)
    left, right = normal["conditions"], target["conditions"]
    for key in ("pressure_GPa", "field_T"):
        if not _number(left.get(key)) or not _number(right.get(key)):
            if not same_run:
                reasons.append("Unknown essential " + key)
        elif abs(left[key] - right[key]) > BASE_POLICY["condition_tolerance"]:
            reasons.append("Different " + key)
    for key in ("formula", "sample_form"):
        if not _text(left.get(key)) or not _text(right.get(key)):
            reasons.append("Unknown " + key)
        elif key == "formula":
            if F.ND.composition(left[key]) != F.ND.composition(right[key]):
                reasons.append("Different explicit formula")
        elif left[key] != right[key]:
            reasons.append("Different " + key)
    for axis in ("doping_fraction", "strain"):
        a, b = normal["coordinates"].get(axis), right.get(axis)
        if a is not None and b is not None and abs(a - b) > BASE_POLICY["condition_tolerance"]:
            reasons.append("Different " + axis)
    if left.get("phase") is not None and right.get("phase") is not None and left["phase"] != right["phase"]:
        reasons.append("Different declared phase")
    if link.get("target_sample_id") != right.get("sample_id") or link.get("curve_sample_id") != left.get("sample_id"):
        reasons.append("Explicit source sample identifiers disagree")
    if not _text(left.get("sample_id")) or not _text(right.get("sample_id")):
        reasons.append("Physical source sample identifiers are unknown")
    return reasons


def historical_observations(events, *, as_of):
    """Filter event availability before resolving corrections, never afterwards."""
    F.verify_events(events)
    cutoff = _time(as_of)
    visible = [event for event in events if _time(event["recorded_at"]) <= cutoff]
    replaced = {event["supersedes"] for event in visible if event["supersedes"] is not None}
    return {event["hash"]: event for event in visible
            if event["event_type"] == "observation" and event["hash"] not in replaced}


def target_available_by(payload, cutoff):
    if _time(payload["observed_at"]) > cutoff:
        return False
    published = payload["reference"].get("publication_date")
    if published is None:
        return False
    if len(published) == 10:
        return date.fromisoformat(published) <= cutoff.date()
    return _time(published) <= cutoff


def scoped_precursor_export(events, *, policy, as_of, same_specimen_links):
    """Versioned narrow export. Never changes strict feature_eligible or GP policy."""
    validate_policy(policy)
    cutoff = _time(as_of)
    policy_hash = sha256(policy)
    active = historical_observations(events, as_of=as_of)
    accepted, excluded = [], []
    for event in active.values():
        payload = event["payload"]
        if payload["observation_type"] != "normal_state_measurement":
            continue
        reasons = F._feature_reasons(payload, as_of=as_of)
        if _time(event["recorded_at"]) > cutoff:
            reasons.append("Measurement was not frozen by cutoff")
        if payload.get("normal_state_policy_sha256") != policy_hash:
            reasons.append("Measurement is not bound to this frozen extraction policy")
        if payload["quantity"] in TRANSPORT and _number(payload["value"]) and payload["value"] <= 0:
            reasons.append("Nonpositive normalized/absolute transport is outcome evidence, not a precursor")
        if _time(policy["defined_at"]) > cutoff:
            reasons.append("Scoped policy was not frozen by cutoff")
        links = [link for link in same_specimen_links if link.get("curve_id") == payload.get("curve_id")]
        valid_links = []
        for link in links:
            target_event = active.get(link.get("target_observation_hash"))
            if target_event and target_available_by(target_event["payload"], cutoff) and target_event["payload"]["observation_type"] == "sample_superconductivity" and not _link_reasons(payload, target_event["payload"], link):
                valid_links.append(link)
        coordinates = payload["coordinates"]
        # Only these exact exclusions are reconsidered. Essential P/B and every
        # other source/window/timing criterion remain inherited from feedback.
        allowed_missing = {"strain"}
        if valid_links:
            allowed_missing.add("doping_fraction")
        if any(link.get("scope") == "same_run_measured_tc" for link in valid_links):
            allowed_missing.update({"pressure_gpa", "magnetic_field_t"})
        if {k for k in F.COORDINATES if coordinates[k] is None} <= allowed_missing:
            reasons = [r for r in reasons if r != "one or more parameter coordinates are unknown"]
        if any(link.get("scope") == "same_run_measured_tc" for link in valid_links):
            reasons = [r for r in reasons if r not in {"unknown pressure_GPa", "unknown field_T"}]
        if payload["conditions"].get("phase") is None and valid_links:
            reasons = [r for r in reasons if r != "unknown phase"]
        if reasons:
            excluded.append({"observation_hash": event["hash"], "reasons": sorted(set(reasons))})
        else:
            accepted.append({"observation_hash": event["hash"], "payload": copy.deepcopy(payload),
                             "scoped_policy_sha256": policy_hash, "strict_feature_eligible": not F._feature_reasons(payload),
                             "unknown_nuisance": [k for k in ("strain", "doping_fraction") if coordinates[k] is None],
                             "missing_condition_flags": {k: coordinates[k] is None for k in FIXED_COORDINATES},
                             "phase_unknown": payload["conditions"].get("phase") is None,
                             "doping_axis_learning_allowed": coordinates["doping_fraction"] is not None})
    return {"accepted": accepted, "excluded": excluded, "policy_sha256": policy_hash, "default_feedback_policy_unchanged": True}


def join_measured_targets(events, *, curves, features, links, registry, policy, as_of):
    """Return linked records, not fit-ready zero-filled labels or an automatic join."""
    validate_policy(policy)
    cutoff = _time(as_of)
    targets = {key: event["payload"] for key, event in historical_observations(events, as_of=as_of).items()
               if target_available_by(event["payload"], cutoff)}
    exported = scoped_precursor_export(events, policy=policy, as_of=as_of, same_specimen_links=links)
    eligible_points = {}
    for point in exported["accepted"]:
        payload = point["payload"]
        eligible_points.setdefault(payload["curve_id"], []).append(payload)
    curve_index, feature_index = {c["curve_id"]: c for c in curves}, {f["curve_id"]: f for f in features}
    _require(len(curve_index) == len(curves) and len(feature_index) == len(features), "Duplicate curve/feature IDs require adjudication")
    accepted, excluded = [], []
    for link in links:
        curve, target = curve_index.get(link.get("curve_id")), targets.get(link.get("target_observation_hash"))
        reasons = []
        if curve is None or target is None:
            excluded.append({"link": link, "reasons": ["Curve or active target observation missing"]})
            continue
        normal = curve_observations(curve, registry, policy, point_indices=[0])[0]
        reasons.extend(_link_reasons(normal, target, link))
        if target["observation_type"] != "sample_superconductivity" or target["assertion_status"] != "source_checked":
            reasons.append("Inspected measured sample outcome required")
        if target["outcome"] is not True or not _number(target.get("tc_K")) or target.get("tc_K", 0) <= 0:
            reasons.append("No uncensored positive measured Tc; null observations are not Tc=0")
        if not _text(target.get("tc_criterion")):
            reasons.append("Measured Tc criterion unresolved")
        if _number(target.get("tc_K")) and any(target["conditions"].get(k) is not None and (
                target["tc_K"] < target["conditions"][k] if k == "t_min_K" else target["tc_K"] > target["conditions"][k]) for k in ("t_min_K", "t_max_K")):
            reasons.append("Measured Tc lies outside its declared measurement interval")
        feature = feature_index.get(curve["curve_id"], {})
        if feature.get("status") != "ready" or feature.get("policy_sha256") != sha256(policy):
            reasons.append("Frozen target-independent curve features unavailable")
        if feature.get("curve_content_sha256") != sha256(curve) or feature.get("source_sha256") != registry[curve["source_id"]]["sha256"]:
            reasons.append("Feature source/curve content binding mismatch")
        recomputed = extract_features(curve, registry, policy)
        if feature != recomputed:
            reasons.append("Extracted summaries differ from frozen source-only extractor")
        matched_indices = set()
        source = registry[curve["source_id"]]
        curve_hash = sha256(curve)
        for point in eligible_points.get(curve["curve_id"], []):
            provenance = point.get("point_provenance", {})
            index = provenance.get("point_index")
            if type(index) is not int or not 0 <= index < len(curve["points"]):
                continue
            actual = curve["points"][index]
            if (point.get("curve_content_sha256") == curve_hash and point.get("raw_source_sha256") == source["sha256"]
                    and point.get("quantity") == curve["quantity"] and point.get("unit") == curve["unit"]
                    and point.get("specimen_id") == curve["specimen_id"]
                    and point.get("conditions") == point_conditions(curve, actual, point_coordinates(curve, actual))
                    and point.get("coordinates") == point_coordinates(curve, actual)
                    and point.get("value") == actual["value"] and point.get("reference") == source["reference"]
                    and provenance.get("source_id") == curve["source_id"] and provenance.get("locator") == actual["source_locator"]):
                matched_indices.add(index)
        if not set(feature.get("used_point_indices", [])) <= matched_indices or not feature.get("used_point_indices"):
            reasons.append("Feature points are not eligible recorded ledger observations at cutoff")
        if reasons:
            excluded.append({"link": link, "reasons": sorted(set(reasons))})
            continue
        comp = F.ND.composition(curve["conditions"]["formula"])
        effective = feature.get("effective_fixed_coordinates", curve["fixed_coordinates"])
        effective_conditions = copy.deepcopy(curve["conditions"])
        effective_conditions.update(pressure_GPa=effective["pressure_gpa"], field_T=effective["magnetic_field_t"])
        composition_quality = "unknown"
        if _text(link.get("composition_quality")) and _text(link.get("composition_source_locator")):
            composition_quality = link["composition_quality"]
        declared_quality = curve.get("composition_quality")
        if declared_quality is not None and composition_quality != "unknown" and declared_quality != composition_quality:
            composition_quality = "conflicting_composition_quality"
        accepted.append({"curve_id": curve["curve_id"], "material_id": curve["material_id"], "specimen_id": curve["specimen_id"],
                         "series_id": curve.get("series_id"), "source_identity": _source_identity(registry[curve["source_id"]]["reference"]),
                         "chemical_system": "-".join(sorted(comp)), "quantity": curve["quantity"], "unit": curve["unit"],
                         "conditions": effective_conditions, "fixed_coordinates": copy.deepcopy(effective),
                         "composition_quality": composition_quality, "composition_source_locator": link.get("composition_source_locator"),
                         "tc_K": target["tc_K"], "tc_criterion": target["tc_criterion"], "target_observation_hash": link["target_observation_hash"],
                         "features": copy.deepcopy(feature["features"]), "policy_sha256": sha256(policy),
                         "matching_scope": link.get("scope", "same_specimen_condition_matched"),
                         "missing_condition_flags": {k: effective[k] is None for k in FIXED_COORDINATES},
                         "axis_learning_allowed": {k: effective[k] is not None and target["conditions"].get({"pressure_gpa": "pressure_GPa", "magnetic_field_t": "field_T"}.get(k, k)) is not None for k in FIXED_COORDINATES},
                         "same_specimen_link": copy.deepcopy(link), "statistical_unit": "specimen-condition", "doping_axis_learning_allowed": curve["fixed_coordinates"]["doping_fraction"] is not None})
    return {"accepted": accepted, "excluded": excluded, "target": F.SAMPLE_TARGET, "not_dft_or_parent_labels": True}


def independent_components(records):
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(records):
        keys = [("system", row["chemical_system"]), ("source", row["source_identity"]), ("specimen", row["specimen_id"])]
        if _text(row.get("series_id")):
            keys.append(("series", row["source_identity"] + "::" + row["series_id"]))
        for key in keys:
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    components = {}
    for i, row in enumerate(records):
        components.setdefault(find(i), []).append(row["curve_id"])
    ordered = sorted((sorted(v) for v in components.values()), key=lambda v: tuple(v))
    return [{"component_id": sha256(v)[:16], "curve_ids": v} for v in ordered]


def cohort_audit(records, policy):
    validate_policy(policy)
    components = independent_components(records)
    def unit(row):
        return sha256({"specimen_id": row["specimen_id"], "conditions": {k: row["conditions"].get(k) for k in ("pressure_GPa", "field_T", "phase")}, "coordinates": row["fixed_coordinates"]})
    units = {unit(r) for r in records}
    feasibility = []
    for component in components:
        held = set(component["curve_ids"])
        training = [r for r in records if r["curve_id"] not in held]
        training_n = len({unit(r) for r in training})
        feasibility.append({"held_component": component["component_id"], "training_components": len(components) - 1,
                            "training_specimen_conditions": training_n,
                            "minimum_training_requirements_met": len(components) - 1 >= policy["minimum_training_components"] and training_n >= policy["minimum_training_samples"]})
    eligible = len(components) >= policy["minimum_independent_components"] and all(r["minimum_training_requirements_met"] for r in feasibility)
    return {"status": "pending_split_and_criterion_freeze" if eligible else "insufficient_data",
            "linked_curve_records": len(records), "unique_specimens": len({r["specimen_id"] for r in records}),
            "unique_specimen_conditions": len(units), "independent_components": len(components), "components": components,
            "minimum_independent_components": policy["minimum_independent_components"],
            "minimum_training_components": policy["minimum_training_components"], "minimum_training_samples": policy["minimum_training_samples"],
            "single_component_holdout_feasibility_not_a_frozen_split": feasibility,
            "tc_criteria": {c: sum(r["tc_criterion"] == c for r in records) for c in sorted({r["tc_criterion"] for r in records})},
            "temperature_points_are_not_independent_samples": True, "models_fitted": 0, "adopted": False,
            "limitations": ["Rows sharing a specimen/condition need modality or replicate adjudication before model fitting",
                            "A dataset's raw curve count is not its number of independent chemical systems or sources",
                            "No prospective claim follows from newly ingested historical literature"]}


def resolve_links_at_cutoff(events, links, *, as_of):
    cutoff = _time(as_of)
    active_targets = {}
    for event in historical_observations(events, as_of=as_of).values():
        if target_available_by(event["payload"], cutoff):
            target_id = event["payload"].get("normal_collection_target_id")
            if target_id is not None:
                active_targets.setdefault(target_id, []).append(event["hash"])
    resolved, unresolved = [], []
    for original in links:
        link = copy.deepcopy(original)
        if "target_observation_hash" not in link:
            choices = active_targets.get(link.get("target_id"), [])
            if len(choices) != 1:
                unresolved.append({"link": link, "reason": "Target ID unresolved or ambiguous in recorded historical ledger"})
                continue
            link["target_observation_hash"] = choices[0]
        resolved.append(link)
    return resolved, unresolved


def ingest_collection(collection, *, registry, policy, ledger_path, output_dir, append=False, as_of=None):
    """Record actual measurements even when no labels/valid holdout are available."""
    validate_policy(policy)
    _require(isinstance(collection, dict) and isinstance(collection.get("curves"), list), "Collection needs curves[]")
    corrections = collection.get("observation_corrections", [])
    _require(isinstance(corrections, list), "observation_corrections must be an explicit list")
    correction_map, previous_hashes = {}, set()
    for correction in corrections:
        _require(isinstance(correction, dict) and set(correction) == {"curve_id", "point_index", "supersedes", "reason"},
                 "Point correction needs only curve_id, point_index, supersedes and reason; targets cannot be corrected here")
        _require(_text(correction["curve_id"]), "Correction curve_id required")
        _require(type(correction["point_index"]) is int and correction["point_index"] >= 0,
                 "Correction point_index must be a nonnegative integer")
        previous = correction["supersedes"]
        _require(isinstance(previous, str) and re.fullmatch("[0-9a-f]{64}", previous), "Correction supersedes must be a SHA256 hash")
        _require(_text(correction["reason"]), "Correction reason required")
        key = (correction["curve_id"], correction["point_index"])
        _require(key not in correction_map, "Duplicate correction curve/point mapping")
        _require(previous not in previous_hashes, "Duplicate correction supersedes hash")
        correction_map[key] = correction
        previous_hashes.add(previous)
    curves, features, payloads, invalid = [], [], [], []
    seen, used_corrections, supersedes = set(), set(), []
    for curve in collection["curves"]:
        _require(curve.get("curve_id") not in seen, "Duplicate curve ID in collection")
        seen.add(curve.get("curve_id"))
        try:
            observations = curve_observations(curve, registry, policy)
            feature = extract_features(curve, registry, policy)
        except (ValueError, F.FeedbackValidationError) as error:
            invalid.append({"curve_id": curve.get("curve_id"), "reason": str(error)})
            continue
        curves.append(curve)
        features.append(feature)
        for index, payload in enumerate(observations):
            key = (curve["curve_id"], index)
            correction = correction_map.get(key)
            if correction is not None:
                payload["correction_reason"] = correction["reason"]
                used_corrections.add(key)
            payloads.append(payload)
            supersedes.append(correction["supersedes"] if correction is not None else None)
    _require(used_corrections == set(correction_map), "Unused correction mapping: missing or invalid curve/point")
    target_ids = set()
    for target in collection.get("targets", []):
        _require(isinstance(target, dict) and _text(target.get("target_id")), "Target needs explicit target_id")
        _require(target["target_id"] not in target_ids, "Duplicate target ID")
        target_ids.add(target["target_id"])
        payload = copy.deepcopy(target["payload"])
        F.validate_observation(payload)
        _require(payload["observation_type"] == "sample_superconductivity", "This collection route is measured-sample only")
        payload["normal_collection_target_id"] = target["target_id"]
        payloads.append(payload)
        supersedes.append(None)
    ledger = F.FeedbackLedger(ledger_path)
    # Only the count is needed below. Do not retain a second decoded copy of a
    # large ledger while the atomic writer validates and appends its new view.
    before_count = len(ledger.read()) if Path(ledger_path).exists() else 0
    if append:
        if correction_map:
            ledger.append_observations(payloads, supersedes=supersedes)
        else:
            ledger.append_observations(payloads)
    events = ledger.read() if Path(ledger_path).exists() else []
    cutoff = as_of or datetime.now(timezone.utc).isoformat()
    links, unresolved = resolve_links_at_cutoff(events, collection.get("links", []), as_of=cutoff)
    linked = join_measured_targets(events, curves=curves, features=features, links=links, registry=registry, policy=policy, as_of=cutoff)
    audit = cohort_audit(linked["accepted"], policy)
    result = {"version": VERSION, "policy_sha256": sha256(policy), "as_of": cutoff,
              "append_requested": bool(append), "observations_prepared": len(payloads),
              "ledger_events_before": before_count, "ledger_events_after": len(events),
              "ledger_events_added": len(events) - before_count, "ledger_head": F.verify_events(events)["head"],
              "curves_schema_valid": len(curves), "invalid_curves": invalid,
              "normal_feature_ready_curves": sum(f["status"] == "ready" for f in features),
              "feature_failures": [{"curve_id": f["curve_id"], "reasons": f["reasons"]} for f in features if f["status"] != "ready"],
              "unresolved_links": unresolved, "linked_measured_tc_records": len(linked["accepted"]),
              "excluded_links": linked["excluded"], "cohort": audit, "models_fitted": 0,
              "public_redistribution_authorized_by_module": False,
              "limitations": ["Raw file hashes and checked locators bind curation; software cannot authenticate a paper's scientific statements",
                              "Normal observations are recorded even if missing modalities, conditions or labels prevent training",
                              "No fit before independent-component, target-criterion and split gating; no Tc=0 for censored outcomes"]}
    if correction_map:
        result["normal_point_corrections_prepared"] = len(correction_map)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("normal-state-preflight.json", result), ("normal-state-features.json", features),
                        ("normal-state-linked-records.json", linked), ("normal-state-source-registry.json", {"sources": list(registry.values())})):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def freeze_training_protocol(output_dir, policy):
    validate_policy(policy)
    document = dict(copy.deepcopy(TRAINING_PROTOCOL), extraction_policy_sha256=sha256(policy))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "normal-state-training-protocol.json"
    if path.exists():
        _require(json.loads(path.read_text(encoding="utf-8")) == document, "Refusing to replace a frozen training protocol")
    path.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "normal-state-training-protocol.sha256").write_text(sha256(document) + "\n", encoding="utf-8")
    return document


def _pilot_unit(row):
    return sha256({"specimen_id": row["specimen_id"], "conditions": row["fixed_coordinates"],
                   "phase": row["conditions"].get("phase"), "criterion": "resistive_midpoint"})


def primary_pilot_cohort(records, *, expected_policy_sha256=None):
    accepted, excluded = [], []
    for row in records:
        reasons = []
        if expected_policy_sha256 is not None and row.get("policy_sha256") != expected_policy_sha256:
            reasons.append("Record belongs to a different or unbound extraction policy")
        if row.get("quantity") not in TRANSPORT:
            reasons.append("Secondary modality is not a primary model input")
        if CRITERION_ALIASES.get(row.get("tc_criterion")) != "resistive_midpoint":
            reasons.append("Tc criterion is outside the explicit midpoint alias mapping")
        try:
            F.ND.composition(row["conditions"].get("formula"))
        except (ValueError, KeyError, TypeError):
            reasons.append("Exact reported sample formula is unavailable")
        if row.get("composition_quality") not in {"reported_sample_formula", "same_sample_reported", "nominal_sample_formula"}:
            reasons.append("Composition is unknown or only a replica/proxy measurement")
        if not _number(row.get("tc_K")) or row.get("tc_K", 0) <= 0:
            reasons.append("An uncensored positive measured Tc is required")
        if not all(_number(row.get("features", {}).get(k)) for k in BASE_POLICY["transport_features"]):
            reasons.append("Frozen normal-state shape features missing")
        if row.get("matching_scope") not in BASE_POLICY["matching_scopes"]:
            reasons.append("No validated matching scope")
        if reasons:
            excluded.append({"curve_id": row.get("curve_id"), "reasons": reasons})
        else:
            accepted.append(row)
    counts = {}
    for row in accepted:
        counts[_pilot_unit(row)] = counts.get(_pilot_unit(row), 0) + 1
    unique = []
    for row in accepted:
        if counts[_pilot_unit(row)] > 1:
            excluded.append({"curve_id": row["curve_id"], "reasons": ["Duplicate specimen-condition requires explicit adjudication"]})
        else:
            unique.append(row)
    return unique, excluded


def pilot_matrix(records):
    from pymatgen.core.periodic_table import Element
    baseline, shape = [], []
    for row in records:
        comp = F.ND.composition(row["conditions"]["formula"])
        total = sum(comp.values())
        weights = np.array([n / total for n in comp.values()])
        elements = [Element(name) for name in comp]
        z, mass = np.array([e.Z for e in elements]), np.array([float(e.atomic_mass) for e in elements])
        electronegativity = np.array([e.X if e.X is not None else np.nan for e in elements], float)
        physical = [float(weights @ z), float(weights @ mass),
                    float(weights @ electronegativity) if np.isfinite(electronegativity).all() else np.nan, float(len(comp))]
        allowed = row.get("axis_learning_allowed", {})
        controls = [row["fixed_coordinates"].get(k) if allowed.get(k) is True else np.nan for k in PILOT_CONDITIONS]
        numeric = np.array([*physical, *[v if _number(v) else np.nan for v in controls]], float)
        flags = (~np.isfinite(numeric)).astype(float)
        quantity = np.array([float(row["quantity"] == q) for q in sorted(TRANSPORT)])
        baseline.append(np.concatenate([numeric, flags, quantity]))
        shape.append([row["features"][k] for k in BASE_POLICY["transport_features"]])
    names = [*COMPOSITION_FEATURES, *PILOT_CONDITIONS]
    names += ["missing_" + k for k in names] + ["quantity_" + q for q in sorted(TRANSPORT)]
    return np.asarray(baseline, float), np.asarray(shape, float), names


class PilotScale:
    def fit(self, matrix):
        matrix = np.asarray(matrix, float)
        self.mean = np.array([float(c[np.isfinite(c)].mean()) if np.isfinite(c).any() else 0. for c in matrix.T])
        self.std = np.array([float(c[np.isfinite(c)].std()) if np.isfinite(c).any() else 0. for c in matrix.T])
        self.keep = self.std > 1e-12
        return self

    def transform(self, matrix):
        matrix = np.asarray(matrix, float)
        return np.where(np.isfinite(matrix[:, self.keep]),
                        (matrix[:, self.keep] - self.mean[self.keep]) / self.std[self.keep], 0.)


def verified_pilot_records(evidence, *, policy):
    """Rebuild evidence in this process. Hashes bind bytes, not scientific truth."""
    _require(isinstance(evidence, dict) and all(k in evidence for k in ("registry_document", "source_root", "collection", "ledger_path", "as_of")),
             "Real fitting requires original registry, sources, collection and historical ledger inputs")
    registry = source_registry(evidence["registry_document"], source_root=evidence["source_root"])
    collection = evidence["collection"]
    events = F.read_events(evidence["ledger_path"])
    curves = collection["curves"]
    features = [extract_features(curve, registry, policy) for curve in curves]
    links, unresolved = resolve_links_at_cutoff(events, collection.get("links", []), as_of=evidence["as_of"])
    linked = join_measured_targets(events, curves=curves, features=features, links=links,
                                   registry=registry, policy=policy, as_of=evidence["as_of"])
    cutoff = _time(evidence["as_of"])
    visible = [event for event in events if _time(event["recorded_at"]) <= cutoff]
    binding = {"as_of": evidence["as_of"], "historical_ledger_head": visible[-1]["hash"] if visible else F.GENESIS,
               "current_ledger_head": events[-1]["hash"] if events else F.GENESIS,
               "registry_sha256": sha256(evidence["registry_document"]), "collection_sha256": sha256(collection),
               "policy_sha256": sha256(policy), "linked_records_sha256": sha256(linked["accepted"]),
               "unresolved_links": unresolved, "excluded_links": linked["excluded"],
               "source_claims_not_cryptographically_authenticated": True}
    return linked["accepted"], binding


def fit_measured_pilot(records=None, *, policy, output_dir, allow_fit=False, synthetic=False, evidence=None):
    """Explicit opt-in only; a failed data gate fits zero models and retains evidence."""
    protocol = freeze_training_protocol(output_dir, policy)  # Before cohort/label access.
    output = Path(output_dir)
    binding = None
    if evidence is not None:
        _require(records is None and not synthetic, "Do not mix detached rows or synthetic data with verified evidence")
        records, binding = verified_pilot_records(evidence, policy=policy)
    elif allow_fit and not synthetic:
        raise ValueError("Real detached fitting is disabled; supply original source-bound evidence inputs")
    _require(isinstance(records, list), "Pilot records or source-bound evidence required")
    rows, exclusions = primary_pilot_cohort(records, expected_policy_sha256=sha256(policy))
    audit = cohort_audit(rows, policy)
    report = {"model_name": "Storm-normal-state-pilot", "training_protocol_sha256": sha256(protocol),
              "extraction_policy_sha256": sha256(policy), "synthetic": bool(synthetic), "adopted": False,
              "status": "insufficient_data", "models_fitted": 0, "cohort": audit, "excluded": exclusions,
              "retrospective_replay": True, "existing_storm_dft_model_unchanged": True}
    report["verified_evidence_binding"] = binding
    report["gate_only_detached_records_unverified"] = binding is None and not synthetic
    report.update(run_at=datetime.now(timezone.utc).isoformat(), input_records_sha256=sha256(records),
                  implementation_sha256_lf=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest())
    if audit["status"] == "insufficient_data" or not allow_fit:
        if audit["status"] != "insufficient_data":
            report["status"] = ("gate_only_detached_records_unverified" if binding is None and not synthetic
                                else "awaiting_explicit_fit_authorization_after_source_audit")
        (output / "normal-state-pilot-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return report
    from sklearn.linear_model import Ridge
    baseline, shape, names = pilot_matrix(rows)
    target = np.log1p([r["tc_K"] for r in rows])
    design_matrices = {"baseline": baseline, "with_normal": np.column_stack([baseline, shape])}
    predictions = {d: np.full(len(rows), np.nan) for d in design_matrices}
    folds = []
    for component in audit["components"]:
        test = np.array([r["curve_id"] in component["curve_ids"] for r in rows])
        train = ~test
        fold = {"held_component": component["component_id"], "train_curve_ids": [r["curve_id"] for r, k in zip(rows, train) if k],
                "test_curve_ids": [r["curve_id"] for r, k in zip(rows, test) if k], "designs": {}}
        for design, matrix in design_matrices.items():
            scale = PilotScale().fit(matrix[train])
            A, B = scale.transform(matrix[train]), scale.transform(matrix[test])
            if A.shape[1]:
                head = Ridge(alpha=1., solver="svd", fit_intercept=True).fit(A, target[train])
                predicted = head.predict(B)
                coefficients, intercept = head.coef_.tolist(), float(head.intercept_)
            else:
                predicted = np.full(test.sum(), target[train].mean())
                coefficients, intercept = [], float(target[train].mean())
            p = np.clip(np.expm1(predicted), 0, None)
            _require(np.isfinite(p).all(), "Non-finite pilot prediction")
            predictions[design][test] = p
            report["models_fitted"] += 1
            fold["designs"][design] = {"train_mean": scale.mean.tolist(), "train_std": scale.std.tolist(),
                                        "keep": scale.keep.tolist(), "coefficients": coefficients, "intercept": intercept,
                                        "mae_k": float(np.abs(np.expm1(target[test]) - p).mean())}
        folds.append(fold)
    metrics = {}
    y = np.expm1(target)
    for design, pred in predictions.items():
        metrics[design] = {"component_macro_mae_k": float(np.mean([f["designs"][design]["mae_k"] for f in folds])),
                           "row_mae_k": float(np.abs(y - pred).mean()), "row_rmse_k": float(np.sqrt(np.mean((y - pred) ** 2)))}
    deltas = np.array([f["designs"]["with_normal"]["mae_k"] - f["designs"]["baseline"]["mae_k"] for f in folds])
    rng = np.random.default_rng(7)
    bootstrap = deltas[rng.integers(0, len(deltas), size=(1000, len(deltas)))].mean(axis=1)
    report.update(status="completed_exploratory", metrics=metrics, folds=folds,
                  input_names={"baseline": names, "with_normal": names + BASE_POLICY["transport_features"]},
                  paired_bootstrap={"delta_macro_mae_k_augmented_minus_baseline": float(deltas.mean()),
                                    "percentile95_k": np.quantile(bootstrap, [.025, .975]).tolist(), "resamples": 1000,
                                    "few_group_interval_not_confirmatory": True},
                  predictions=[{"curve_id": r["curve_id"], "target_tc_k": r["tc_K"], **{d: float(p[i]) for d, p in predictions.items()}} for i, r in enumerate(rows)])
    (output / "normal-state-pilot-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", action="store_true")
    parser.add_argument("--training-protocol", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Gate/evaluate the separate measured-sample pilot; defaults to no fit")
    parser.add_argument("--linked-records", type=Path)
    parser.add_argument("--allow-fit", action="store_true", help="Explicitly opt in after source audit; data minima still cannot be bypassed")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--defined-at")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--sources-root", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--as-of")
    parser.add_argument("--append", action="store_true", help="Append inspected measured observations, including feature-ineligible evidence; never fit a model")
    args = parser.parse_args()
    if args.protocol:
        document = freeze_policy(args.output_dir, defined_at=args.defined_at)
        print(json.dumps({"policy_sha256": sha256(document), "models_fitted": 0}))
    elif args.training_protocol:
        if args.policy is None:
            parser.error("--training-protocol requires --policy")
        document = freeze_training_protocol(args.output_dir, json.loads(args.policy.read_text(encoding="utf-8")))
        print(json.dumps({"training_protocol_sha256": sha256(document), "models_fitted": 0}))
    elif args.pilot:
        if args.policy is None:
            parser.error("--pilot requires --policy")
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        freeze_training_protocol(args.output_dir, policy)
        if args.linked_records is not None:
            if args.allow_fit:
                parser.error("Detached --linked-records can only gate; real fit needs original --registry --collection --sources-root --ledger")
            data = json.loads(args.linked_records.read_text(encoding="utf-8"))
            records = data["accepted"] if isinstance(data, dict) else data
            report = fit_measured_pilot(records, policy=policy, output_dir=args.output_dir)
        else:
            if any(value is None for value in (args.registry, args.collection, args.sources_root, args.ledger)):
                parser.error("Evidence-bound --pilot needs --registry --collection --sources-root --ledger")
            evidence = {"registry_document": json.loads(args.registry.read_text(encoding="utf-8")),
                        "source_root": args.sources_root, "collection": json.loads(args.collection.read_text(encoding="utf-8")),
                        "ledger_path": args.ledger, "as_of": args.as_of or datetime.now(timezone.utc).isoformat()}
            report = fit_measured_pilot(policy=policy, output_dir=args.output_dir, evidence=evidence, allow_fit=args.allow_fit)
        print(json.dumps({k: report[k] for k in ("status", "models_fitted", "adopted")}))
    else:
        if any(value is None for value in (args.registry, args.collection, args.sources_root, args.ledger, args.policy)):
            parser.error("Ingestion needs --registry --collection --sources-root --ledger --policy")
        registry = source_registry(json.loads(args.registry.read_text(encoding="utf-8")), source_root=args.sources_root)
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        result = ingest_collection(json.loads(args.collection.read_text(encoding="utf-8")), registry=registry, policy=policy,
                                   ledger_path=args.ledger, output_dir=args.output_dir, append=args.append, as_of=args.as_of)
        print(json.dumps({k: result[k] for k in ("ledger_events_added", "curves_schema_valid", "normal_feature_ready_curves", "linked_measured_tc_records", "models_fitted")}))


if __name__ == "__main__":
    main()
