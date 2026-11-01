"""Retain author LSCO tables with observable/identity boundaries; no fit or ledger.

This is a curation schema, not an admission to ml.normal_state or a new policy.
Nominal Sr x is not inferred from the reported mobile hole density p. The
transverse even-in-field response is not silently relabelled as rho_xx or Hall.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import re
import zipfile
import xml.etree.ElementTree as ET
import argparse

import openpyxl
from source_helpers import read_provenance

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parent,
                    help="Local hurricane source root; original data are not bundled")
ROOT = parser.parse_args().data_root.resolve()
DATA = ROOT / "lsco-2017"
DOI = "10.1038/nature23290"
GROUP = "doi:" + DOI
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (DATA / name).write_bytes((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def workbook(number_):
    path = DATA / "original" / f"41586_2017_BFnature23290_MOESM{number_}_ESM.xlsx"
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return path, list(wb["Sheet1"].values)


def symbol_microohm_proof(path):
    """Plain Excel readers see 'mW'; the author's Symbol font means micro-ohm."""
    with zipfile.ZipFile(path) as archive:
        strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    proof = []
    for index, si in enumerate(strings):
        for run in si.findall("s:r", NS):
            font = run.find("s:rPr/s:rFont", NS)
            value = run.find("s:t", NS)
            if font is not None and font.get("val") == "Symbol" and value is not None and value.text == "mW":
                proof.append({"shared_string_index": index, "font": "Symbol", "encoded_text": "mW",
                              "decoded_meaning": "microohm", "numeric_scale_changed": False})
    assert proof, "Do not guess the unit from plain-text mW"
    return proof


def table_points(rows, first_row, xcol, ycol):
    points, omitted, explicit_missing = [], [], []
    for line, row in enumerate(rows, 1):
        if line < first_row or not number(row[xcol]):
            continue
        value = row[ycol]
        if value is None:
            omitted.append(line)  # No measurement for this series; do not pad with zero.
            continue
        if not number(value):
            if value == "--":
                points.append([row[xcol], None, line])
                explicit_missing.append(line)
                continue
            raise ValueError(f"Unreviewed response {value!r} on row {line}")
        points.append([row[xcol], value, line])
    assert points
    return points, omitted, explicit_missing


def main():
    logs = read_provenance(ROOT, "attachment-download-log.json")
    urls = {r["path"]: r["url"] for r in logs if r.get("status") == "downloaded"}
    expected_hashes = {r["path"]: r["sha256"] for r in logs if r.get("status") == "downloaded"}
    sources = []
    for path in sorted((DATA / "original").glob("*.xlsx")):
        relative = path.relative_to(ROOT).as_posix()
        assert sha(path) == expected_hashes[relative], "Original source bytes differ from retrieval provenance"
        sources.append({"source_id": "lsco-2017:" + path.stem, "raw_path": relative, "sha256": sha(path),
                        "bytes": path.stat().st_size, "url": urls[relative], "paper_doi": DOI,
                        "source_kind": "author_deposited_figure_source_data", "inspection_status": "full_text_and_data_inspected",
                        "license": None, "rights_note": "No separate open-data licence identified in the publisher attachment. Nature2017 article is subscription content; author manuscript has a US-government-use notice. Public availability is not a blanket redistribution licence.",
                        "distribution": "Retain numeric source/adaptation locally; publish citation/index/hashes only unless rights separately established"})
    by_path = {s["raw_path"]: s for s in sources}
    curves, omissions = [], []
    path, rows = workbook(5)
    proof = symbol_microohm_proof(path)
    assert rows[0][0].startswith("This is the Source Data for Figure 1b")
    assert "impractical" in rows[1][0] and "three dopings" in rows[2][0]
    sid = by_path[path.relative_to(ROOT).as_posix()]["source_id"]
    for p, phi, j, panel in [(.10, 40., 1, "b"), (.16, 320., 3, "c"), (.18, 180., 5, "d")]:
        specimen = f"lsco-2017:Fig1{panel}:p{p:.2f}:phi{phi:g}"
        assert f"p={p:.2f}" in rows[4][j]
        for component, column in [("longitudinal", j), ("transverse_even_in_field", j + 1)]:
            points, missing, explicit = table_points(rows, 7, 0, column)
            curve = {
                "curve_id": f"lsco-2017:Fig1{panel}:{component}", "source_id": sid,
                "source_doi": DOI, "family": "cuprate", "chemical_system": ["Cu", "La", "O", "Sr"],
                "study_group_id": GROUP, "source_group_id": GROUP, "series_group_id": "lsco-2017:ALL-MBE-doping-series",
                "specimen_id": specimen, "author_unique_specimen_id": None,
                "identity_scope": "Source Figure1 panel and doping/angle; paired longitudinal/transverse traces explicitly from the same sample (author manuscript PDFp5). No mapping to other figures solely by matchingp.",
                "reported_material": "La2-xSrxCuO4", "exact_sample_formula": None,
                "composition": {"nominal_Sr_x": None, "reported_mobile_hole_density_p_per_formula_unit": p,
                                "note": "MethodsA explicitly distinguishes nominalSr x and mobilehole p because of oxygen defects; no x=p substitution"},
                "sample_form": "epitaxial single-crystal thin film", "substrate": "LaSrAlO4 (LSAO)",
                "thickness_nm": 26., "thickness_unit_cells": 20,
                "phase": "epitaxially constrained tetragonal LSCO; sourceMethodsA",
                "quantity": "longitudinal_resistivity" if component == "longitudinal" else "in_plane_transverse_resistivity_even_in_field",
                "response_component": component, "unit": "microohm cm", "source_unit_plain_text": rows[5][column],
                "unit_evidence": {"symbol_font_decoding": proof, "paper_locator": "Author manuscript PDFpp11-12 Fig1/2 axes; source XLSX sharedStrings SymbolmW means microohm"},
                "independent_axis": "temperature_k", "data_columns": ["temperature_k", "value", "source_row"], "data": points,
                "source_locator_template": f"{path.name}:Sheet1!A{{source_row}}:{openpyxl.utils.get_column_letter(column+1)}{{source_row}}",
                "fixed_conditions": {"pressure_gpa": None, "magnetic_field_t": None, "current_a": 2e-6,
                                     "current_angle_from_100_degrees": phi, "doping_fraction": None, "strain": None},
                "condition_notes": ["Source describes spontaneous zero-external-field transverse transport, but no numeric residualfield or pressure accompanies Figure1; numericP/B leftnull.",
                                    "Crystalstrain is imposed by substrate; no numericstrain assigned to this specifictrace.",
                                    "Source averages three transverse contact voltages, then divides by current and multiplies by thickness; no additional collectorprocessing."],
                "normal_state_review": {"verified_range_k": [150., 290.], "evidence_locator": "Primary text describes normal-state transport above SCtransition; Figure1 and MethodsG. The retained trace also includes the transition region, which is not automatically normal.",
                                        "below_verified_range": "unknown_or_superconducting_region; do not use as prospective normalstate features"},
                "normalization": {"kind": "none"}, "tc_K": None, "tc_criterion": None,
                "superconductivity_claim": {"outcome": True, "scope": "Figure1sample shows a resistive transition; no numeric midpoint assigned by this curator", "source_locator": "Author manuscript PDFp5, Fig1"},
                "temperature_min_k": min(x[0] for x in points), "temperature_max_k": max(x[0] for x in points),
                "missing_cells_not_padded": len(missing), "explicit_missing_measurements": len(explicit),
                "not_hall_coefficient": component != "longitudinal",
            }
            curves.append(curve)
            omissions.append({"curve_id": curve["curve_id"], "empty_response_rows_not_added": missing})
    # These are actual pickup voltages, not an inferred susceptibility in emu/mole.
    path, rows = workbook(9)
    assert "mutual inductance" in rows[1][0]
    for column, component in [(1, "in_phase"), (2, "out_of_phase")]:
        points, missing, explicit = table_points(rows, 4, 0, column)
        curves.append({"curve_id": f"lsco-2017:ED2:pickup_{component}",
                       "source_id": by_path[path.relative_to(ROOT).as_posix()]["source_id"],
                       "source_doi": DOI, "family": "cuprate", "chemical_system": ["Cu", "La", "O", "Sr"],
                       "study_group_id": GROUP, "source_group_id": GROUP, "series_group_id": "lsco-2017:ALL-MBE-doping-series",
                       "specimen_id": "lsco-2017:ED2:optimally-doped-film", "author_unique_specimen_id": None,
                       "identity_scope": "ExtendedData2film; identity with Figure1p0.16film remains unverified, so not an additional independentfilm count",
                       "reported_material": "La2-xSrxCuO4", "exact_sample_formula": None,
                       "composition": {"reported_mobile_hole_density_p_per_formula_unit": .16, "nominal_Sr_x": None},
                       "sample_form": "epitaxial thin film", "quantity": "mutual_inductance_pickup_voltage", "response_component": component,
                       "unit": "millivolt", "source_unit_plain_text": rows[2][column],
                       "independent_axis": "temperature_k", "data_columns": ["temperature_k", "value", "source_row"], "data": points,
                       "source_locator_template": f"{path.name}:Sheet1!A{{source_row}}:{openpyxl.utils.get_column_letter(column+1)}{{source_row}}",
                       "fixed_conditions": {"pressure_gpa": None, "magnetic_field_t": None, "doping_fraction": None, "strain": None},
                       "normal_state_review": {"status": "unknown; rawpickupvoltage not a calibrated chi(T) channel"},
                       "tc_K": None, "tc_criterion": None,
                       "temperature_min_k": min(x[0] for x in points), "temperature_max_k": max(x[0] for x in points),
                       "missing_cells_not_padded": len(missing), "explicit_missing_measurements": len(explicit)})
    path, rows = workbook(15)
    assert "temperature-dependence" in rows[2][0] and "330" in rows[2][0]
    points, missing, explicit = table_points(rows, 5, 0, 1)
    curves.append({"curve_id": "lsco-2017:ED8a:transverse", "source_id": by_path[path.relative_to(ROOT).as_posix()]["source_id"],
                   "source_doi": DOI, "family": "cuprate", "chemical_system": ["Cu", "La", "O", "Sr"],
                   "study_group_id": GROUP, "source_group_id": GROUP, "series_group_id": "lsco-2017:ALL-MBE-doping-series",
                   "specimen_id": "lsco-2017:ED8:p0.16:phi330", "author_unique_specimen_id": None,
                   "identity_scope": "SourceED8a. Identity with Figure1p0.16film remains unresolved; do not count a new independentfilm",
                   "reported_material": "La2-xSrxCuO4", "exact_sample_formula": None,
                   "composition": {"reported_mobile_hole_density_p_per_formula_unit": .16, "nominal_Sr_x": None},
                   "quantity": "in_plane_transverse_resistivity_even_in_field", "response_component": "transverse_even_in_field", "unit": "microohm cm",
                   "source_unit_plain_text": rows[3][1], "independent_axis": "temperature_k",
                   "data_columns": ["temperature_k", "value", "source_row"], "data": points,
                   "source_locator_template": f"{path.name}:Sheet1!A{{source_row}}:B{{source_row}}",
                   "fixed_conditions": {"pressure_gpa": None, "magnetic_field_t": None, "doping_fraction": None, "strain": None, "current_angle_from_100_degrees": 330.},
                   "normal_state_review": {"status": "unknown; mostly SCfluctuation/transitionrange; no automatic normaldesignation"},
                   "tc_K": None, "tc_criterion": None,
                   "temperature_min_k": min(x[0] for x in points), "temperature_max_k": max(x[0] for x in points),
                   "missing_cells_not_padded": len(missing), "explicit_missing_measurements": len(explicit)})
    claims = [{"claim_id": "lsco-2017:ED2:screening-onset-and-resistive-zero", "specimen_id": "lsco-2017:ED2:optimally-doped-film",
               "tc_K": 40.8, "tc_criterion": "Meissner_screening_onset_coincident_with_resistive_zero", "outcome": True,
               "source_doi": DOI, "source_locator": "Author manuscript PDFp15, MethodsA; ExtendedData2 and sourceMOESM9",
               "linked_curve_ids": ["lsco-2017:ED2:pickup_in_phase", "lsco-2017:ED2:pickup_out_of_phase"],
               "excluded_link_to_fig1": "Samep0.16does not establish samephysicalfilm; no link to Figure1 transport inferred",
               "pressure_gpa": None, "magnetic_field_t": None}]
    # Cell-level roundtrip for every prepared numeric source pair.
    for c in curves:
        source = next(s for s in sources if s["source_id"] == c["source_id"])
        path = ROOT / source["raw_path"]
        cols = re.search(r"!([A-Z]+)\{source_row\}:([A-Z]+)\{source_row\}", c["source_locator_template"]).groups()
        sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)["Sheet1"]
        source_rows = list(sheet.values)
        xcol, ycol = [openpyxl.utils.column_index_from_string(x) - 1 for x in cols]
        for x, y, row in c["data"]:
            assert source_rows[row-1][xcol] == x
            assert source_rows[row-1][ycol] == y or (y is None and source_rows[row-1][ycol] == "--")
    workbook_index = []
    for source in sources:
        wb = openpyxl.load_workbook(ROOT / source["raw_path"], read_only=True, data_only=True)
        metadata = []
        for s in wb:
            if s.max_row == s.max_column == 1 and s.cell(1,1).value is None:
                continue
            metadata.append({"sheet": s.title, "rows": s.max_row, "columns": s.max_column,
                             "header_rows": [list(row) for row in list(s.values)[:6]]})
        workbook_index.append({"source_id": source["source_id"], "sheets": metadata})
    result = {"schema_version": "hurricane-source-curation-v1-not-training-policy", "sources": sources, "curves": curves,
              "reported_tc_claims": claims, "model_target_links": [],
              "other_author_tables_retained_as_originals": workbook_index,
              "feature_exclusions": ["Sourceangularrows atT=Tc/Tc+-0.5K are outcome-relative; never prospective normalstatefeatures.",
                                     "Nematicity, fittedamplitudes/phaseoffset and SCboundaryquantities remain separate author-derivedobservables, not rawrho_xx.",
                                     "The two mutualinductancevoltages cannot be relabelled calibratedchi without calibration and driveconditions."],
              "automatic_training": False}
    longitudinal = [c for c in curves if c["response_component"] == "longitudinal"]
    audit = {"status": "source_roundtrip_pass_no_training_admission", "curves_prepared": len(curves),
             "point_records": sum(len(c["data"]) for c in curves), "finite_responses": sum(y is not None for c in curves for _,y,_ in c["data"]),
             "longitudinal_curves": len(longitudinal), "longitudinal_point_records": sum(len(c["data"]) for c in longitudinal),
             "longitudinal_cover_200_225_250K": [c["curve_id"] for c in longitudinal if c["temperature_min_k"] <= 200 and c["temperature_max_k"] >= 250],
             "minimum_distinct_physical_films_fromFig1": 3, "additional_trace_identity_unresolved": ["ED2", "ED8a"],
             "independent_families": 1, "independent_primary_papers": 1, "chemical_systems": 1,
             "reported_numeric_Tc_claims": 1, "longitudinal_curves_with_exact_same_physical_numeric_Tc": 0,
             "model_target_links": 0, "unit_Symbol_font_evidence": proof,
             "source_cell_roundtrip_checked": True, "complete_thousand_device_dataset_claimed": False,
             "all_original_source_hashes": {s["source_id"]: s["sha256"] for s in sources},
             "models_fitted": 0, "ledger_files_read_or_written": 0, "policy_frozen": False}
    write("lsco-source-registry.json", {"sources": sources})
    write("lsco-curves.json", result)
    write("lsco-curation-audit.json", audit)
    write("empty-source-cells-not-padded.json", omissions)
    print(json.dumps({k:v for k,v in audit.items() if k not in {"all_original_source_hashes", "unit_Symbol_font_evidence"}}, indent=2))


if __name__ == "__main__":
    main()
