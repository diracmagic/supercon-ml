"""Retain two author DC resistivity tables; do not infer a Tc criterion or fit.

The repository tables include zero-temperature/zero-response rows whose
instrumental provenance is unspecified. They are retained, flagged, and never
automatically admitted as observations to an experimental ledger.
"""
from pathlib import Path
import argparse
import json
import openpyxl
from source_helpers import sha, canonical_sha, number, write, compact_curve, read_provenance

DOI = "10.1038/s41567-026-03266-8"
STUDY = "fete-fese-planckian-2026"


def main(root):
    data = root / STUDY
    provenance = read_provenance(root, STUDY + "/download-provenance.json")
    sources = []
    for item in provenance:
        path = root / item["path"]
        assert sha(path) == item["sha256"]
        sources.append({"source_id": STUDY + ":" + path.stem, "source_doi": DOI,
                        "raw_path": item["path"], "url": item["url"],
                        "bytes": path.stat().st_size, "sha256": sha(path),
                        "repository_checksum": item["repository_checksum"],
                        "repository_checksum_verified": item["checksum_verified"],
                        "retrieved_utc": item["retrieved_utc"], "dataset_version": "Zenodo18662533 v1",
                        "dataset_license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "citation": "Romero III et al., Planckian scattering and parallel conduction channels in an iron chalcogenide superconductor, Nature Physics22,851-855(2026)",
                        "rights_scope": "Dataset license is separate from publisher article/preprint rights"})
    path = data / "original/ExDat1.xlsx"
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    curves, claims = [], []
    for x, tc in ((.45, 13.2), (.35, 11.8)):
        sheet = wb[f"Se = {x:.2f}"]
        rows = list(sheet.values)
        assert rows[1][0] == "T(K)" and rows[1][1] == "Rho (mOhm mm)" and rows[1][2] == "Fit"
        points = [[row[0], row[1], index] for index, row in enumerate(rows, 1)
                  if number(row[0]) and number(row[1])]
        assert len(points) == len(rows) - 2
        for t, rho, row in points:
            assert sheet.cell(row, 1).value == t and sheet.cell(row, 2).value == rho
        specimen = f"{STUDY}:film:x{x:.2f}"
        cid = specimen + ":DC-resistivity"
        zeros = [row for t, rho, row in points if t <= 9 and float(t).is_integer() and rho == 0]
        curves.append({"curve_id": cid, "source_id": STUDY + ":ExDat1", "source_doi": DOI,
                       "family": "iron_chalcogenide", "chemical_system": ["Fe", "Se", "Te"],
                       "study_group_id": "doi:" + DOI, "source_group_id": "doi:" + DOI,
                       "series_group_id": STUDY + ":two-film-composition-series", "specimen_id": specimen,
                       "author_unique_specimen_id": None,
                       "identity_scope": "Source sheet x matches the two films explicitly described on author-preprintPDFp1; not a unique instrument sample identifier",
                       "reported_material": "FeTe1-xSex", "reported_composition_x": x,
                       "sample_form": "100nm epitaxial film on CaF2(100), 100nm Se cap",
                       "quantity": "dc_longitudinal_resistivity", "response_component": "longitudinal",
                       "unit": "milliohm mm", "source_unit_plain_text": rows[1][1],
                       "unit_conversion_not_applied": "1milliohm mm = 100microohm cm; original values retained",
                       "independent_axis": "temperature_k", "data_columns": ["temperature_k", "value", "source_row"],
                       "data": points, "source_locator_template": f"ExDat1.xlsx:'{sheet.title}'!A{{source_row}}:B{{source_row}}",
                       "fixed_conditions": {"pressure_gpa": None, "magnetic_field_t": None, "doping_fraction": None, "strain": None},
                       "normal_state_review": {"status": "candidate normal portion only, not admitted to a frozen training policy",
                                               "review_window_k": [150, 290],
                                               "basis": "Both films have reported DC transitions below14K; no raw lowT point is automatically labelled normal"},
                       "temperature_min_k": min(p[0] for p in points), "temperature_max_k": max(p[0] for p in points),
                       "author_table_zero_tail_rows": zeros,
                       "zero_tail_provenance": "AtintegerT0..9K the author table has exactlyzero rho. Source does not identify these as individual instrument measurements; no replacement, interpolation or ledger admission performed",
                       "negative_response_rows": sum(p[1] < 0 for p in points),
                       "author_fit_column_excluded": "ColumnC Fit is author-derived, not an independent observation",
                       "tc_K": None, "tc_criterion": None})
        claims.append({"claim_id": specimen + ":reported-Tc", "specimen_id": specimen,
                       "tc_K": tc, "tc_criterion": None, "criterion_status": "not specified in inspected author v1 manuscript",
                       "source_url": "https://arxiv.org/abs/2505.00623", "source_version": "arXiv2505.00623v1,1May2025; text dated2May2025",
                       "source_locator": "AuthorpreprintPDFp1 paragraph starting TDTS was performed; ExtendedDataFig1p8",
                       "matched_numeric_table": cid, "model_target_link_created": False,
                       "limitation": "Numeric Tc is a primary author v1 claim, not a verified published-version midpoint definition"})
    index = []
    for source in sources:
        workbook = openpyxl.load_workbook(root / source["raw_path"], read_only=True, data_only=True)
        index.append({"source_id": source["source_id"], "sheets": [{"sheet": s.title, "rows": s.max_row,
                      "columns": s.max_column} for s in workbook]})
    result = {"schema_version": "hurricane-source-curation-v1-not-training-policy", "sources": sources,
              "curves": curves, "reported_tc_claims": claims, "model_target_links": [],
              "workbook_index": index, "automatic_training": False,
              "exclusions": ["All fit/Drude/model columns, opticalSCcondensate and literaturecomparison compilations remain separate from raw DCinputs",
                             "Other workbook copies/refits of these DCdata are not additional samples or independent curves"]}
    audit = {"status": "source_cell_roundtrip_pass_no_training_admission", "curves_prepared": len(curves),
             "point_records": sum(len(c["data"]) for c in curves), "source_cell_roundtrip_checked": True,
             "distinct_physical_films": 2, "independent_papers": 1, "independent_families": 1, "chemical_systems": 1,
             "longitudinal_cover_200_225_250K": [c["curve_id"] for c in curves if c["temperature_max_k"] >= 250],
             "same_sample_numeric_Tc_claims": 2, "same_sample_explicit_midpoint_targets": 0, "model_target_links": 0,
             "source_table_rows_not_asserted_all_instrument_raw": True,
             "author_table_zero_tail_rows": sum(len(c["author_table_zero_tail_rows"]) for c in curves),
             "curves_index": [compact_curve(c) for c in curves], "models_fitted": 0, "ledger_files_read_or_written": 0,
             "published_fulltext_access": "publisher preview read; fulltext inspected is arXivv1, not asserted identical to final published article",
             "policy_frozen": False}
    write(data / "source-registry.json", {"sources": sources})
    write(data / "curves.json", result)
    write(data / "curation-audit.json", audit)
    print(json.dumps({key: value for key, value in audit.items() if key != "curves_index"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parent)
    main(parser.parse_args().data_root.resolve())
