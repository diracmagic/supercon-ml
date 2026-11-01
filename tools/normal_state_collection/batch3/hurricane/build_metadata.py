"""Build public metadata from locally curated original-source adaptations.

No numerical response arrays, PDFs, registry authentication material or ledger
records are copied. Existing source files are read; only --output-root is written.
"""
from pathlib import Path
import argparse
import hashlib
import json
from source_helpers import sha, canonical_sha, compact_curve, read_provenance


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def compact(curve):
    row = compact_curve(curve)
    # Original row-index arrays are not needed in the public metadata package.
    for name in ("author_table_zero_tail_rows",):
        if name in row:
            values = row.pop(name)
            row[name + "_count"] = len(values)
            row[name + "_sha256"] = canonical_sha(values)
    return row


def main(root, out):
    root, out = root.resolve(), out.resolve()
    if root == out or root in out.parents:
        raise ValueError("Use an output directory outside the private source root")
    studies = ["lsco-2017", "fete-fese-planckian-2026", "nickelate-2026"]
    results = {name: read(root / name / ("lsco-curves.json" if name == "lsco-2017" else "curves.json")) for name in studies}
    audits = {name: read(root / name / ("lsco-curation-audit.json" if name == "lsco-2017" else "curation-audit.json")) for name in studies}
    sources = []
    logitems = []
    for relative in ("initial-download-log.json", "attachment-download-log.json", "further-download-log.json", "fallback-download-log.json",
                     "fete-fese-planckian-2026/download-provenance.json", "fete-fese-planckian-2026/preprint-download-log.json"):
        value = read_provenance(root, relative)
        items = value if isinstance(value, list) else [value]
        if relative.endswith("preprint-download-log.json"):
            items = [dict(item, path="fete-fese-planckian-2026/" + item["path"]) for item in items]
        logitems.extend(items)
    by_path = {item["path"]: item for item in logitems}
    for name, result in results.items():
        for source in result["sources"]:
            row = dict(source)
            assert sha(root / row["raw_path"]) == row["sha256"]
            info = by_path.get(row["raw_path"], {})
            row["retrieved_utc"] = info.get("retrieved_utc")
            sources.append(row)
    evidence = []
    evidence_paths = ["lsco-2017/author-paper.pdf", "fes-fese-fete-2022/author-paper.pdf",
                      "fes-fese-fete-2022/original/41563_2022_1291_MOESM1_ESM.pdf",
                      "nickelate-2026/paper.pdf", "fete-fese-planckian-2026/author-preprint.pdf"]
    for relative in evidence_paths:
        path = root / relative
        info = by_path[relative]
        assert sha(path) == info["sha256"]
        evidence.append({"raw_path": relative, "url": info["url"], "bytes": path.stat().st_size,
                         "sha256": sha(path), "retrieved_utc": info["retrieved_utc"],
                         "distribution": "Not included in the public package; inspect publisher/repository rights separately"})
    registry = {"schema_version": 1, "numeric_source_containers": len(sources), "sources": sources, "primary_evidence_artifacts": evidence,
                "verification_scope": "SHA/checksum verifies bytes, not the truth of paper claims, sample identity, calibration or an SC transition",
                "raw_or_derived_numerical_arrays_bundled": False}
    write(out / "source-registry.json", registry)
    for name, result in results.items():
        audit = dict(audits[name])
        audit.pop("curves_index", None)
        audit["curated_private_output_sha256_canonical_json"] = canonical_sha(result)
        write(out / name / "curation-audit.json", audit)
        claims = {"reported_tc_claims": result["reported_tc_claims"], "model_target_links": result["model_target_links"],
                  "limitation": "Primary source claims, not ledger labels or admissions under a training policy"}
        write(out / name / "reported-tc-claims.json", claims)
        groups = {}
        for curve in result["curves"]:
            key = curve["curve_id"].split(":")[1] if name == "nickelate-2026" else "curves"
            groups.setdefault(key, []).append(compact(curve))
        for key, values in groups.items():
            write(out / name / (key.lower() + "-index.json"), {"curves": values})
    allcurves = [c for result in results.values() for c in result["curves"]]
    broad = [c for name in studies[:2] for c in results[name]["curves"] if c["response_component"] == "longitudinal"]
    summary = {"schema_version": 1, "status": "source_collection_only_no_effect_test", "scope": "This batch3Hurricane curation only; not a census of every legacy Hmaterial lead",
               "numeric_source_primary_papers": 3, "numeric_source_families": ["cuprate", "iron_chalcogenide", "nickelate"],
               "primary_papers_fulltext_inspected": 4, "additional_paper_without_numeric_response_source": "10.1038/s41563-022-01291-5",
               "curves_or_trace_representations_prepared": len(allcurves), "point_records": sum(len(c["data"]) for c in allcurves),
               "finite_response_records": sum(p[1] is not None for c in allcurves for p in c["data"]),
               "explicit_source_missing_responses": sum(p[1] is None for c in allcurves for p in c["data"]),
               "independent_sample_warning": "Trace count is not sampleN; normalized/absolute views and temperature/angle sweeps repeat the same physical film",
               "broad_longitudinal": {"curves": len(broad), "point_records": sum(len(c["data"]) for c in broad),
                    "distinct_physical_films": 5, "independent_papers": 2, "chemical_systems": 2, "families": 2,
                    "cover_200_225_250K": len([c for c in broad if c["temperature_min_k"] <= 200 and c["temperature_max_k"] >= 250]),
                    "reported_same_sample_numeric_Tc_claims_criterion_unspecified": 2,
                    "explicit_same_sample_midpoint_Tc_targets": 0,
                    "figure1_LSCO_exact_numeric_Tc_missing": 3,
                    "limitations": ["FeTeSe fulltext inspected is authorv1; final publisher criterion not verified", "Twenty author-table lowT zero-tail rows are not asserted all instrumental measurements", "Numeric pressure/field conditions remain null when not explicitly stated"]},
               "nickelate": {"author_sample_labels_in_paper": 5, "broad_temperature_curves": 0, "reported_midpoint_Tc_claims": 5,
                    "normal_state_sweep_designations": 0, "unresolved_source_sample_label_conflicts": 1,
                    "chemical_element_sets_in_author_sample_claims": 2,
                    "source_sc_boundary_and_calculation_tables_excluded_from_features": True},
               "LOFO_readiness": {"multiple_families_with_broad_raw_rho": True, "numeric_family_count_is_not_a_validated_effect_test": True,
                    "paired_midpoint_broad_rho_families": 0, "models_fitted": 0, "LOFO_runs": 0,
                    "reason": "Same-specimen numeric targets with a verified common criterion are incomplete. This batch alone cannot substantiate an improvement or a cross-family law. No new eligibility threshold was frozen."},
               "model_target_links": 0, "ledger_files_read_or_written": 0, "automatic_training": False, "new_policy_frozen": False,
               "grouping": "Use paper/source and family, keeping all dopings/angles/fields and repeated representations from one study in the same group; three LSCO dopings are one cuprate family, not three families"}
    write(out / "hurricane-readiness.json", summary)
    print(json.dumps({"numeric_sources": len(sources), "curves": len(allcurves), "points": summary["point_records"],
                      "broad_curves": len(broad), "paired_midpoint_targets": 0, "models_fitted": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    main(args.data_root, args.output_root)
