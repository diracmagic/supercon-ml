"""Retain signed field-sweep response tables; do not call them normal R(T).

SC boundaries/calculations are indexed separately. Author sample assignments
are preserved as source claims; a repeated-trace label conflict is not resolved
by choosing the convenient Tc. No targets or ledger records are produced.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import zipfile
from source_helpers import sha, write, compact_curve

STUDY = "nickelate-2026"
DOI = "10.1038/s41467-026-75922-9"


def tables(archive, name):
    return [line.split("\t") for line in archive.read(name).decode("cp1252").splitlines()]


def points(rows, start, col):
    result = []
    for index, row in enumerate(rows[start:], start + 1):
        if len(row) <= col + 1 or not row[col].strip() or not row[col+1].strip():
            continue
        x = float(row[col])
        y = None if row[col+1].strip() == "--" else float(row[col+1])
        assert math.isfinite(x) and (y is None or math.isfinite(y))
        result.append([x, y, index])
    return result


def main(root):
    data = root / STUDY
    path = data / "source.zip"
    expected = "md5:631e84b5d1cfdf6ec9c9ea509cdbd5c5"  # Zenodo20636178 v1 repository metadata
    assert expected == "md5:" + hashlib.md5(path.read_bytes()).hexdigest()
    source = {"source_id": STUDY + ":Raw_Data_File", "source_doi": DOI,
              "raw_path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path),
              "url": "https://zenodo.org/records/20636178/files/Raw_Data_File.zip?download=1",
              "repository_checksum": expected, "repository_checksum_verified": True,
              "dataset_version": "Zenodo20636178 v1 published11June2026", "dataset_license": "CC-BY-4.0",
              "license_url": "https://creativecommons.org/licenses/by/4.0/",
              "article_license": "CC-BY-NC-ND-4.0; distinct from dataset license",
              "citation": "Yip et al., High-field-stabilized reentrant superconductivity in infinite-layer nickelate thin films, Nature Communications(2026)"}
    archive = zipfile.ZipFile(path)
    curves, index = [], []
    specs = [("A", "S1", None, 0, "temperature"), ("B", "S2", None, 0, "temperature"),
             ("C", "S1", 1.5, None, "angle"), ("D", "S2", 1.8, None, "angle"),
             ("E", "S1", 1.5, None, "angle"), ("F", "S2", .35, 0, "single"),
             ("G", "S2", 1.8, None, "angle"), ("3B", None, None, 0, "sample")]
    for fig, sample, fixed_t, fixed_angle, mode in specs:
        member = f"Raw_Data_File/Fig.1/Fig1{fig}.dat" if fig != "3B" else "Raw_Data_File/Fig.3/Fig3B.dat"
        rows = tables(archive, member)
        start = 2 if mode == "single" else 3
        # E has two trailing empty columns. They are not missing measurements.
        ncol = max(len(row) for row in rows)
        for col in range(0, ncol - 1, 2):
            values = points(rows, start, col)
            if not values:
                continue
            label = rows[2][col+1] if mode != "single" else None
            s = label if mode == "sample" else sample
            temp = float(re.search(r"[\d.]+", label).group()) if mode == "temperature" else fixed_t
            angle = float(re.search(r"[\d.]+", label).group()) if mode == "angle" else fixed_angle
            if mode == "sample":
                temp = {"S2": .35, "S3": .6, "S4": .6, "S5": 1.5}[s]
            normalized = rows[0][col+1].strip().lower() == "r/rn"
            curve = {"curve_id": f"{STUDY}:Fig{fig}:pair{col//2+1}", "source_id": source["source_id"],
                     "source_doi": DOI, "source_archive_member": member, "source_column_pair_1based": [col+1, col+2],
                     "source_header_label": label, "family": "nickelate",
                     "chemical_system": ["Ca", "Eu", "Ni", "O", "Sm", "Sr"] if s == "S4" else ["Ca", "Eu", "Ni", "O", "Sm"],
                     "study_group_id": "doi:" + DOI, "source_group_id": "doi:" + DOI,
                     "series_group_id": STUDY + ":five-film-series", "author_sample_label": s,
                     "specimen_id": STUDY + ":" + s,
                     "sample_assignment_status": "author figure/header claim; no model target link created",
                     "sample_form": "infinite-layer nickelate epitaxial film",
                     "quantity": "resistance_normalized_to_normal_state" if normalized else "longitudinal_resistivity",
                     "unit": "dimensionless" if normalized else "milliohm cm",
                     "source_unit_plain_text": rows[1][col+1],
                     "unit_evidence": "PublishedPDFp2 Figure1E-G axes show milliohm cm; source Origin escape m\\g(W) cm means milli-ohm cm" if not normalized else "Source header R/Rn",
                     "independent_axis": "signed_applied_field_t", "data_columns": ["signed_applied_field_t", "value", "source_row"],
                     "data": values, "fixed_conditions": {"temperature_k": temp, "angle_degrees_field_from_c_axis": angle,
                        "pressure_gpa": None, "magnetic_field_t": None, "doping_fraction": None, "strain": None},
                     "field_min_t": min(p[0] for p in values), "field_max_t": max(p[0] for p in values),
                     "explicit_missing_responses": sum(p[1] is None for p in values),
                     "normal_state_review": {"status": "unknown; sweep contains superconducting/reentrant transitions, not an admitted normal-state curve"},
                     "representation_overlap": "Fig1C/E and Fig1D/G include normalized and absolute views at overlapping conditions; not additional physical specimens",
                     "tc_K": None, "tc_criterion": None}
            if fig == "3B" and s == "S4":
                curve["specimen_id"] = None
                curve["sample_assignment_status"] = "unresolved: author header S4 conflicts with strong repeated-trace evidence against Fig1F labelled S2; no sample/Tc reassignment"
            # Every prepared numeric value must roundtrip to its exact original field.
            for x, y, row in values:
                assert float(rows[row-1][col]) == x
                assert rows[row-1][col+1] == "--" if y is None else float(rows[row-1][col+1]) == y
            curves.append(curve)
    for member in archive.namelist():
        if member.endswith(".dat"):
            content = archive.read(member)
            kind = "author_calculation" if "Calculation" in member else "experimental_SC_boundary_outcome" if "Fig.2/" in member or "Fig3A" in member else "field_sweep_response"
            index.append({"archive_member": member, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                          "scope": kind, "prospective_normal_feature_admitted": False})
    f = next(c for c in curves if c["curve_id"] == STUDY + ":FigF:pair1")
    g = next(c for c in curves if c["curve_id"] == STUDY + ":Fig3B:pair2")
    a, b = ({x: y for x, y, _ in c["data"]} for c in (f, g))
    common = sorted(set(a) & set(b))
    scale = sum(a[k]*b[k] for k in common) / sum(b[k]**2 for k in common)
    conflict = {"status": "unresolved_source_sample_label_conflict", "absolute_source": f["curve_id"],
                "normalized_source": g["curve_id"], "author_labels": ["S2", "S4"],
                "common_unique_field_values": len(common), "least_squares_representation_scale": scale,
                "common_values_residual_below_1e_12": sum(abs(a[k]-scale*b[k]) < 1e-12 for k in common),
                "maximum_absolute_residual": max(abs(a[k]-scale*b[k]) for k in common),
                "limitation": "Repeated field keys use the last source row for this diagnostic. Strong shared-trace evidence is not an author-confirmed correction; original labels and bytes retained, no numeric Tc linked"}
    claims = []
    for label, tc, formula, thickness in [("S1",9.6,"Sm0.58Eu0.35Ca0.07NiO2",6.5),
            ("S2",11.7,"Sm0.53Eu0.4Ca0.07NiO2",4.5), ("S3",16.8,"Sm0.53Eu0.4Ca0.07NiO2",6.5),
            ("S4",22.1,"Sm0.79Eu0.12Ca0.04Sr0.05NiO2",4.5), ("S5",31.7,"Sm0.73Eu0.2Ca0.07NiO2",4.5)]:
        claims.append({"claim_id": STUDY + ":Table1:" + label, "author_sample_label": label,
                       "specimen_id": STUDY + ":" + label, "tc_K": tc,
                       "tc_criterion": "midpoint halfway between zero and saturated normal-state resistance",
                       "formula": formula, "film_thickness_nm": thickness, "thickness_uncertainty_nm": .5,
                       "source_locator": "PublishedPDFp2 Table1 and Results paragraph defining Tc/Hc midpoints",
                       "pressure_gpa": None, "magnetic_field_t": None, "model_target_link_created": False})
    audit = {"status": "source_roundtrip_pass_with_unresolved_source_label_conflict", "curves_prepared": len(curves),
             "point_records": sum(len(c["data"]) for c in curves), "source_cell_roundtrip_checked": True,
             "explicit_missing_responses": sum(c["explicit_missing_responses"] for c in curves),
             "author_sample_labels": 5, "independent_papers": 1, "independent_families": 1,
             "broad_temperature_longitudinal_curves": 0, "reported_numeric_midpoint_claims": 5,
             "model_target_links": 0, "label_conflict": conflict,
             "paper_curve_omitted_from_source": "Fig1B published caption/axis has1.8K, but sourceFig1B header has no1.8K pair; no row fabricated",
             "signed_fields_retained": True, "models_fitted": 0, "ledger_files_read_or_written": 0, "policy_frozen": False}
    write(data / "source-registry.json", {"sources": [source], "archive_members": index})
    write(data / "curves.json", {"schema_version": "hurricane-source-curation-v1-not-training-policy", "sources": [source],
          "curves": curves, "reported_tc_claims": claims, "model_target_links": [], "automatic_training": False})
    write(data / "curves-index.json", {"curves": [compact_curve(c) for c in curves]})
    write(data / "curation-audit.json", audit)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parent)
    main(parser.parse_args().data_root.resolve())
