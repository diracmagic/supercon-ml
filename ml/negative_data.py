"""Validate condition-specific experimental null observations, never invented Tc=0 labels.

    python ml/negative_data.py --validate data/hosono2015_negatives.json

An observation of no transition above Tmin is censored at Tmin. It says nothing
about lower temperatures, other pressures, other dopings, or all descendants of a
parent. Records with missing conditions remain useful evidence but are excluded
from training exports. This module deliberately has no pandas/ML dependency.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data" / "hosono2015_negatives.json"
SAMPLE_TARGET = "exact_sample_transition_above_threshold"
PARENT_TARGET = "parent_has_superconducting_doped_descendant"
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split())


def composition(formula: str) -> dict[str, float]:
    """Only explicit, expanded formulas; ranges, variables and parentheses need curation."""
    if not isinstance(formula, str) or not formula:
        raise ValueError("an explicit formula is required")
    out, pos = {}, 0
    for match in re.finditer(r"([A-Z][a-z]?)(\d*\.?\d*)", formula):
        if match.start() != pos or match.group(1) not in ELEMENTS:
            raise ValueError(f"not an explicit elemental formula: {formula!r}")
        value = float(match.group(2) or 1)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("stoichiometric coefficients must be finite and positive")
        out[match.group(1)] = out.get(match.group(1), 0) + value
        pos = match.end()
    if pos != len(formula) or not out:
        raise ValueError(f"not an explicit elemental formula: {formula!r}")
    return out


def _positive(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _nonnegative(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def validate_record(record: dict, sources: dict) -> list[str]:
    """Schema/evidence errors. Unknown conditions are allowed, never filled by inference."""
    errors = []
    if not isinstance(record, dict):
        return ["record must be an object"]
    for key in ("id", "formula", "source_id", "source_locator", "observation", "synthesis_status", "scope"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"missing {key}")
    try:
        comp = composition(record.get("formula"))
        explicit = record.get("composition")
        if explicit is not None and (set(explicit) != set(comp) or any(abs(float(explicit[e]) - comp[e]) > 1e-8 for e in comp)):
            errors.append("composition disagrees with expanded formula")
    except (ValueError, TypeError, KeyError):
        errors.append("formula/composition is not explicit and consistent")
    if record.get("source_id") not in sources:
        errors.append("source_id is not in sources")
    source = sources.get(record.get("source_id"), {})
    if not source.get("url") or not source.get("doi"):
        errors.append("source needs a URL and DOI")
    if record.get("scope") != "exact_sample":
        errors.append("null observations must have exact_sample scope")
    if record.get("observation") != "not_detected_above_tmin":
        errors.append("only explicit measured null observations are supported")
    if record.get("synthesis_status") != "synthesized":
        errors.append("failed or unknown synthesis is not a measured negative")
    verification = record.get("verification", {})
    if not isinstance(verification, dict) or verification.get("status") != "source_checked":
        errors.append("record has not been checked against its source")
    measure = record.get("measurement", {})
    if not isinstance(measure, dict):
        return errors + ["measurement must be an object"]
    if not _positive(measure.get("t_min_K")):
        errors.append("a positive measured t_min_K is required")
    if measure.get("t_max_K") is not None and (not _positive(measure["t_max_K"]) or (_positive(measure.get("t_min_K")) and measure["t_max_K"] < measure["t_min_K"])):
        errors.append("invalid measurement temperature range")
    pressure = measure.get("pressure_GPa")
    for field in ("pressure_GPa", "field_T"):
        if measure.get(field) is not None and not _nonnegative(measure[field]):
            errors.append(f"{field} must be finite, non-negative numeric or null")
    if pressure is None and not measure.get("pressure_status"):
        errors.append("missing pressure requires explicit pressure_status")
    if "tc_K" in record or "tc" in record or record.get("unconditional_negative"):
        errors.append("a censored null observation must not be encoded as an unconditional Tc label")
    return errors


def eligibility(record: dict, *, target: str, threshold_K: float,
                pressure_GPa: float | None, sample_form: str | None,
                field_T: float | None) -> list[str]:
    """Reasons not to export label 0 for this *specific*, condition-matched binary target.

    Validation must precede this call. A caller must state its target/conditions;
    this API has no default that silently turns observations into parent labels.
    """
    reasons = []
    if target != SAMPLE_TARGET:
        reasons.append("sample null observations cannot label parent doping potential")
    m = record.get("measurement", {})
    if not _positive(threshold_K) or not _positive(m.get("t_min_K")) or m["t_min_K"] > threshold_K:
        reasons.append("measurement does not reach the target threshold")
    if not _positive(threshold_K) or not _positive(m.get("t_max_K")) or m["t_max_K"] < threshold_K:
        reasons.append("upper measurement temperature is unknown or below the threshold")
    for key, wanted in (("pressure_GPa", pressure_GPa), ("field_T", field_T)):
        observed = m.get(key)
        if observed is None or wanted is None:
            reasons.append(f"unknown {key}")
        elif not _nonnegative(observed) or not _nonnegative(wanted):
            reasons.append(f"invalid {key}")
        elif abs(float(observed) - float(wanted)) > 1e-8:
            reasons.append(f"different {key}")
    if not sample_form or record.get("sample_form") in (None, "unknown"):
        reasons.append("unknown sample_form")
    elif record["sample_form"] != sample_form:
        reasons.append("different sample_form")
    if not m.get("method") or m["method"] == "unknown":
        reasons.append("unknown measurement method")
    return reasons


def validate_document(document: dict) -> dict:
    sources, records = document.get("sources", {}), document.get("records", [])
    errors, ids, checked = {}, set(), 0
    for index, rec in enumerate(records):
        ident = rec.get("id", f"row-{index}") if isinstance(rec, dict) else f"row-{index}"
        problems = validate_record(rec, sources)
        if ident in ids:
            problems.append("duplicate record id")
        ids.add(ident)
        if problems:
            errors[ident] = problems
        else:
            checked += 1
    return {"records": len(records), "validated_observations": checked, "errors": errors,
            "parent_training_labels": 0,
            "policy": "Censored exact-sample observations; never unconditional Tc=0 or parent-potential negatives."}


def load(path: Path = DEFAULT) -> dict:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    report = validate_document(document)
    if report["errors"]:
        raise ValueError(json.dumps(report["errors"], sort_keys=True))
    return document


def export_labels(document: dict, *, target: str, threshold_K: float,
                  pressure_GPa: float | None, sample_form: str | None,
                  field_T: float | None) -> dict:
    report = validate_document(document)
    if report["errors"]:
        raise ValueError(json.dumps(report["errors"], sort_keys=True))
    accepted, excluded = [], []
    for record in document["records"]:
        reasons = eligibility(record, target=target, threshold_K=threshold_K, pressure_GPa=pressure_GPa,
                              sample_form=sample_form, field_T=field_T)
        if reasons:
            excluded.append({"id": record["id"], "reasons": reasons})
        else:
            accepted.append({"id": record["id"], "formula": record["formula"], "label": 0,
                             "target": target, "threshold_K": threshold_K,
                             "target_window_K": [threshold_K, record["measurement"]["t_max_K"]],
                             "measurement": record["measurement"], "source_id": record["source_id"],
                             "source_locator": record["source_locator"]})
    return {"target": target, "threshold_K": threshold_K, "accepted": accepted, "excluded": excluded}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path, default=DEFAULT)
    args = parser.parse_args()
    doc = json.loads(args.validate.read_text(encoding="utf-8"))
    report = validate_document(doc)
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
