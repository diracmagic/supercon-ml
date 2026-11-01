"""Reproduce sample-A transport from retained author I-V/T bytes; never fit a Tc model.

The broad trace and the two transition traces remain distinct. An archive,
cooldown and contact match does not establish identical reported P/B conditions.
Only the already published 1.25 K midpoint is transcribed; no collector Tc is fit.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle_common as B
OUTPUT = None
ARCHIVE_SHA256 = "33cc65d8822eeef1b9a51984b04d90f7a4c2ee64bf6b06e1563e7be1ff052b20"
PAPER_SHA256 = "f01ba9514e2d5b349d938d7a2da236bfb2eebd5f527376d2641056fbfaf1b1af"
PREFIX = "datset_superconducting_nitridized-aluminum_thin_films/run2/CD45/routines_0r2v3_/"
FILES = [
    ("nitral-2024-0r2v3-CD45-broad-C1", "AlN_0r2v3_continuous_during_CD_C1_Still.txt", True),
    ("nitral-2024-0r2v3-CD45-transition-C1", "AlN_0r2v3_Tc_measurement_C1.txt", False),
    ("nitral-2024-0r2v3-CD45-transition2-C1", "AlN_0r2v3_Tc_measurement_2_C1.txt", False),
]
SPECIMEN = "nitral-2024:0r2v3:CD45:C1"
OBSERVED_AT = "2026-11-01T13:59:19+00:00"  # curation/inspection time, not measurement date


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(name, value):
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def parse_author_table(raw, *, temperature=False):
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[0].split("\t")[-1] == "A", "Current axis is not source-reported amperes"
    assert lines[1].split("\t")[-1] == ("K" if temperature else "V"), "Response unit mismatch"
    assert lines[2].startswith("Parameter #1") and "Repetitions" in lines[2]
    assert lines[4] == "First row is x-data, the following rows are y-data"
    repetitions = np.fromstring(lines[3], sep="\t")
    values = np.loadtxt(io.StringIO("\n".join(lines[5:])), delimiter="\t")
    assert values.ndim == 2 and values.shape[0] == len(repetitions) + 1
    assert np.isfinite(values).all(), "Do not silently drop missing original I-V/T values"
    assert np.array_equal(repetitions, np.arange(1, len(repetitions) + 1))
    return repetitions, values[0], values[1:]


def extract_trace(archive, basename):
    member = PREFIX + basename
    temp_member = member[:-4] + "_temperatures.txt"
    vb, tb = archive.read(member), archive.read(temp_member)
    repetitions, current, voltage = parse_author_table(vb)
    trep, tcurrent, temperatures = parse_author_table(tb, temperature=True)
    assert np.array_equal(repetitions, trep) and np.array_equal(current, tcurrent)
    assert voltage.shape == temperatures.shape
    centered = current - current.mean()
    denom = np.dot(centered, centered)
    assert denom > 0
    # Explicit free intercept removes the voltage offset; no zero intercept,
    # absolute-value clipping, smoothing or superconducting-background removal.
    resistance = voltage @ centered / denom
    intercept = voltage.mean(axis=1) - resistance * current.mean()
    predicted = intercept[:, None] + resistance[:, None] * current
    residual_sum = np.square(voltage - predicted).sum(axis=1)
    total_sum = np.square(voltage - voltage.mean(axis=1)[:, None]).sum(axis=1)
    r_squared = np.where(total_sum > 0, 1 - residual_sum / total_sum, np.nan)
    mean_t = temperatures.mean(axis=1)
    assert np.isfinite(resistance).all() and np.isfinite(mean_t).all() and (mean_t > 0).all()
    # Independent linear algebra identity check, not a second scientific fit.
    coefficients = np.linalg.lstsq(np.column_stack((current, np.ones_like(current))), voltage.T, rcond=None)[0]
    assert np.allclose(resistance, coefficients[0], rtol=1e-11, atol=1e-12)
    points = []
    for i, (temperature, value) in enumerate(zip(mean_t, resistance)):
        points.append({
            "temperature_k": float(temperature), "value": float(value),
            "source_locator": f"source.zip:{member}:line {i + 7} voltage(V), line 6 current(A); {temp_member}:line {i + 7} temperature(K); repetition {int(repetitions[i])}",
            "source_repetition": int(repetitions[i]),
            "derivation": {"kind": "ordinary_least_squares_IV_with_free_intercept", "current_points": len(current),
                           "current_min_a": float(current.min()), "current_max_a": float(current.max()),
                           "voltage_intercept_v": float(intercept[i]),
                           "r_squared": float(r_squared[i]) if np.isfinite(r_squared[i]) else None,
                           "temperature_min_k": float(temperatures[i].min()), "temperature_max_k": float(temperatures[i].max()),
                           "temperature_reduction": "Arithmetic mean of the matching thermometer samples for this I-V repetition; original range retained"},
        })
    window = (mean_t >= 150.) & (mean_t <= 300.)
    return points, {
        "iv_member": member, "iv_member_sha256": digest(vb), "temperature_member": temp_member,
        "temperature_member_sha256": digest(tb), "repetitions": len(repetitions), "iv_points_per_repetition": len(current),
        "temperature_min_k": float(mean_t.min()), "temperature_max_k": float(mean_t.max()),
        "normal_window_records": int(window.sum()), "normal_window_unique_mean_temperatures": len(set(mean_t[window])),
        "r_squared_min": float(np.nanmin(r_squared)), "r_squared_median": float(np.nanmedian(r_squared)),
        "window_r_squared_min": float(np.nanmin(r_squared[window])) if window.any() else None,
        "maximum_temperature_change_within_IV_k": float(np.ptp(temperatures, axis=1).max()),
    }


def main():
    global OUTPUT
    args = B.arguments(__doc__, observed_at=OBSERVED_AT)
    DATA, SOURCE_ROOT = args.data_root / "thermo/nitral-2024", args.data_root
    OUTPUT = args.output_dir / "thermo/nitral-2024"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.project_root))
    from ml import normal_state as M, feedback as F
    raw = (DATA / "source.zip").read_bytes()
    assert digest(raw) == ARCHIVE_SHA256
    assert digest((DATA / "paper.pdf").read_bytes()) == PAPER_SHA256
    policy_path = args.policy
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    M.validate_policy(policy)
    reference = {
        "doi": "10.1088/1361-6668/ad20fc", "url": "https://publikationen.bibliothek.kit.edu/1000168884/152381183",
        "publication_date": "2024-02-14", "source_kind": "primary_experiment", "inspection_status": "full_text_inspected",
        "locator": "Paper PDF pp.4-7 (printed pp.3-6), Sec.2 and Sec.3.2, Figs.2-3, Table2; author Readme_NitrAl.md and run2/CD45/routines_0r2v3_/C1 IV/T pairs",
        "dataset_doi": "10.5281/zenodo.10194875", "citation": "Torras-Coloma et al. Superconducting nitridized-aluminum thin films. Supercond. Sci. Technol.37,035017 (2024).",
        "paper_sha256": PAPER_SHA256,
    }
    source = {
        "source_id": "torrascoloma2024-nitral-author-archive", "raw_path": "thermo/nitral-2024/source.zip",
        "sha256": ARCHIVE_SHA256, "reference": reference, "license": "CC-BY-4.0",
        "download_url": "https://zenodo.org/records/10194875/files/datset_superconducting_nitridized-aluminum_thin_films.zip?download=1",
        "preprocessing_note": "Instrument I-V/T arrays retained in archive. Each derived four-terminal resistance is an OLS voltage/current slope with free intercept, in ohms. Not sheet resistance, not intrinsic resistivity, not author-processed R(T).",
    }
    registry_doc = {"sources": [source]}
    registry = M.source_registry(registry_doc, source_root=SOURCE_ROOT)
    curves, trace_audit = [], []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for cid, filename, broad in FILES:
            points, audit = extract_trace(archive, filename)
            audit["curve_id"] = cid
            trace_audit.append(audit)
            conditions = {"sample_id": SPECIMEN, "formula": "Al", "sample_form": "thin film", "phase": None,
                          "pressure_GPa": None, "field_T": None, "t_min_K": audit["temperature_min_k"],
                          "t_max_K": audit["temperature_max_k"], "method": "four-terminal current-voltage resistance"}
            curve = {
                "curve_id": cid, "source_id": source["source_id"], "material_id": "Al", "specimen_id": SPECIMEN,
                "series_id": "nitral-2024:0r2v3", "observed_at": args.observed_at,
                "quantity": "resistance", "unit": "ohm", "conditions": conditions,
                "fixed_coordinates": {"pressure_gpa": None, "doping_fraction": None, "strain": None, "magnetic_field_t": None},
                "normal_state_status": "verified_normal" if broad else "unknown", "normalization": {"kind": "none"},
                "points": points, "measurement_run_id": "nitral-2024:run2:CD45:C1",
                "trace_id": audit["iv_member"] + "::" + audit["temperature_member"], "varied_axes": ["temperature_k"],
                "sample_label": None, "candidate_paper_label": "A (exact physicalpiece mapping unverified)", "source_sample_id": "0r2v3", "fabrication_run": 2, "cooldown": "CD45", "contacts": "C1",
                "nominal_thickness_nm": 100., "fabrication_nitrogen_to_argon_flow_percent": 0.,
                "sample_notes": ["Table2 identifies A as the pure-Al reference, nitrogen/argon flow0%, run2, nominal100nm. The rawcode0r2v3 identifies the0%/run2 archive specimen, but Table2 does not name v3/CD45/C1; exact TableA-to-rawpiece identity remains unverified. Gas-flow fraction is a process parameter, never substituted for an atomic doping fraction.",
                                 "The author directory and all three IV/T basenames uniquely identify 0r2v3, CD45, C1; broad and transition files remain distinct traces.",
                                 "Methods specify magnetic shielding, not a numeric residual/applied field. Measurement pressure and field remain null; sputtering pressures are not measurement pressure.",
                                 "No specimen-resolved C(T) or chi(T) is in this author's archive. No multimodal join is constructed.",
                                 "Finite negative fitted resistances in the low-T noise/transition region are retained; no clipping or fake zero."]
            }
            if broad:
                curve["normal_state_evidence"] = {
                    "locator": "Paper Sec.3.1, Fig.2: metallic normal transport of0%N2/run2 pureAl reference; matching author rawcode0r2v3 IV/T at150-300K",
                    "statement": "The fixed150-300K portion is measured metallic normal transport of the0%N2/run2 pure-Al archive specimen. No Table2Tc value or low-T transition is used in the feature calculation or assigned to this specific physicalpiece.",
                    "verified_range_k": [150., 300.],
                }
            M.validate_curve(curve, registry)
            M.curve_observations(curve, registry, policy)  # payload validation only, no ledger
            curves.append(curve)
    target_ref = copy.deepcopy(reference)
    target_ref["locator"] = "Paper PDF p.6 (printed p.5) Sec.3.2 explicit50%relative-onset criterion; PDF p.7 (printed p.6), Table2 rowA:0%Al reference,run2,100nm,Tc1.25+-0.01K; source.zip run2/CD45/routines_0r2v3_/AlN_0r2v3_Tc_measurement[_2]_C1 pairedIV/T files"
    table_specimen = "nitral-2024:paper-Table2-A:run2-0pct:physical-piece-unresolved"
    payload = {
        "material_id": "Al", "observed_at": args.observed_at, "statement": "Author-reported resistive-midpoint Tc of Table2 sampleA, the pure-Al reference. Exact assignment to archive specimen0r2v3/CD45/C1 remains unverified; numeric measurementP/B unreported.",
        "observation_type": "sample_superconductivity", "assertion_status": "source_checked", "outcome": True,
        "evidence_kind": "measured_transition", "tc_K": 1.25, "tc_uncertainty_K": .01, "tc_is_approximate": False,
        "tc_criterion": "resistive_midpoint", "conditions": copy.deepcopy(curves[1]["conditions"]), "reference": target_ref,
        "measurement_run_id": None, "trace_id": None,
        "raw_source_sha256": None,
        "curation_note": "1.25+-0.01K is a published Table2 value, not a collector threshold derived from noisy I-V arrays. The paper does not identify0r2v3/CD45/C1 or explain v3; matching0%/run2 and numerical proximity do not establish the same physical piece. No Tc is assigned to the rawtraces."
    }
    payload["conditions"]["sample_id"] = table_specimen
    payload["conditions"]["t_min_K"] = None
    payload["conditions"]["t_max_K"] = None
    payload["conditions"]["method"] = "resistivity"
    F.validate_observation(payload)
    link = {
        "curve_id": curves[0]["curve_id"], "target_id": "nitral-2024:sample-A:Tcmid",
        "same_physical_specimen": None, "assertion_status": "needs_review", "specimen_id": SPECIMEN,
        "curve_sample_id": SPECIMEN, "target_sample_id": table_specimen,
        "source_locator": "Table2 rowA maps0%/run2 to pureAl but does not identify0r2v3/CD45/C1. Source.zip run2/CD45/routines_0r2v3_ directory and C1 basenames bind the3rawtraces to each other only. AuthorREADME defines runs/cooldowns/sample_id/contact configurations; v3 meaning unreported.",
        "scope": "same_specimen_condition_matched", "same_raw_trace": False,
        "same_cooldown": None, "same_contact_configuration": None, "same_author_specimen_code": None,
        "within_raw_trace_set_only": {"same_cooldown": "CD45", "same_contacts": "C1", "same_sample_code": "0r2v3"},
        "measurement_run_id": None, "unresolved_conditions": ["pressure_gpa", "magnetic_field_t", "Table2A_to_0r2v3_physical_identity"],
        "primary_join_eligible": False,
    }
    feature = M.extract_features(curves[0], registry, policy)
    normal = M.curve_observations(curves[0], registry, policy, point_indices=[0])[0]
    reasons = M._link_reasons(normal, payload, link)
    assert reasons == ["Inspected explicit same-physical-specimen link required"]
    collection = {"curves": curves, "targets": [{"target_id": link["target_id"], "payload": payload}],
                  "links": [], "unverified_candidate_links": [link], "primary_training_exclusion": "Table2A-to-raw0r2v3 physicalpiece unverified; measurement pressure and magnetic field also unreported. No Tc target is linked to the rawtraces, no main-cohort admission.",
                  "automatic_training": False}
    audit = {
        "status": "pass_with_explicit_training_exclusion", "source_archive_sha256": ARCHIVE_SHA256,
        "paper_sha256": PAPER_SHA256, "frozen_policy_sha256": M.sha256(policy), "curation_inspected_at": args.observed_at,
        "curves": len(curves), "point_records": sum(len(c["points"]) for c in curves), "physical_specimens": 1,
        "material_groups": 1, "published_midpoint_targets": 1, "strict_primary_cohort_added": 0,
        "sample": {"paper_label": None, "candidate_paper_label": "A, exact physicalpiece mapping unverified", "formula": "Al", "source_code": "0r2v3", "run": 2, "cooldown": "CD45", "contacts": "C1", "nominal_thickness_nm": 100.},
        "tc": {"value_k": 1.25, "uncertainty_k": .01, "criterion": "50% resistance drop relative to onset", "source": "Table2 rowA; Sec.3.2", "collector_computed_tc": False},
        "trace_diagnostics": trace_audit, "frozen_transport_extraction": feature,
        "strict_link_exclusion_reasons": reasons,
        "same_specimen_evidence": copy.deepcopy(link),
        "unresolved": ["Table2 does not identify0r2v3/CD45/C1 or explain v3; 0%/run2 metadata and similarTc do not prove an exact physicalpiece/cooldown/contact match to the published1.25K value.",
                       "No numeric measurementP/B; magnetic shielding does not establish0T.",
                       "Separate highT and transition raw files; shared archive/cooldown/C1 is not identical rawtrace.",
                       "R is collector-derived OLS slope of rawIV, not a source-deposited processedR table. IV noise and within-ramp temperature drift are retained diagnostics.",
                       "Paper labels NitrAl's other samples by process gas flow; atomicN content is explicitly unreported, so do not manufacture formulas or concentration-axis labels.",
                       "Reported Table2 values do not identify which of the two nearTc repetitions contributed to their average; both are preserved and no per-fileTc is assigned."],
        "zero_model_fits": True, "zero_ledger_reads_or_writes": True, "original_bytes_unchanged": True,
    }
    write_json("nitral-registry.json", registry_doc)
    write_json("nitral-collection.json", collection)
    write_json("nitral-curation-audit.json", audit)
    print(json.dumps({k: audit[k] for k in ("status", "curves", "point_records", "physical_specimens", "published_midpoint_targets", "strict_primary_cohort_added", "strict_link_exclusion_reasons")}, indent=2))


if __name__ == "__main__":
    main()
