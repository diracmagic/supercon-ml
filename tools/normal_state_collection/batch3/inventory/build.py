"""Create this compact public inventory from the separately stored audited work files.

No downloads, fitting, curve extraction, ledger access, or source-file mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_PRIVATE_MANIFEST_SHA256 = "4654712cd80084b4329d06bea47eddfd0cda88d7d4c65ad9c5a420de9db26fee"
LIMIT_BYTES = 68000


def sha(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8"))


def compact_prediction(row):
    p = row["prediction"]
    fields = ({"tc_dft_pred_k": "tc", "tc_dft_interval_lo_k": "lo", "tc_dft_interval_hi_k": "hi",
               "tc_empirical_corrected_pred_k": "tc_cal", "p_sc_model_score": "p_sc",
               "lambda_model_pred": "lambda", "wlog_model_pred_as_reported": "wlog",
               "conventional_model_score": "p_conventional"} if row["track"] == "Storm" else
              {"tc_model_output_k": "tc", "tc_given_sc_model_output_k": "tc_sc",
               "tc_model_interval_lo_k": "lo", "tc_model_interval_hi_k": "hi",
               "p_sc_model_score": "p_sc", "p_model_disagreement_lo": "p_lo",
               "p_model_disagreement_hi": "p_hi", "unconventional_model_score": "p_unconventional",
               "routing_family": "family", "routing_types": "types"})
    return {"model": p["model"], "screen_round": p["screen_round"],
            "source_pointer": p["source_pointer"],
            "outputs": {new: p[old] for new, old in fields.items() if old in p},
            "observed_label": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="Directory containing the private inventory JSON and its audit reports")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Destination for compact metadata JSON; existing source files are never edited")
    args = parser.parse_args()
    data, out = args.data_root.resolve(), args.output_dir.resolve()
    source_path = data / "candidate-acquisition-manifest.json"
    assert sha(source_path.read_bytes()) == EXPECTED_PRIVATE_MANIFEST_SHA256, "Unexpected private inventory version"
    source = read(source_path)
    crosswalk = read(data / "mdr-candidate-review-crosswalk.json")
    assert len(source["candidates"]) == 152 and len(source["retired_candidates"]) == 5
    assert crosswalk["summary"]["exact_matching_mdr_records"] == 0
    source_map, candidates, retired = {}, [], []

    def audit_summary(row):
        audit = row["prior_audit"]
        ids = []
        for item in audit["sources"]:
            # Scope and access failures remain attached; references are never label claims.
            selected = {key: item[key] for key in (
                "url", "accessed_url", "cite", "doi", "doi_normalized_from_explicit_field_or_doi_url",
                "kind", "locator", "evidence_scope", "supports", "identity_warning", "prior_access_claim",
                "evidence_domain", "candidate_experimental_specimen_link_verified") if key in item}
            sid = "source-" + canonical(selected)[:20]
            source_map[sid] = {"source_id": sid, **selected}
            ids.append(sid)
        return {"status": audit["status"], "superconductivity_outcome_as_recorded": audit["superconductivity_outcome_as_recorded"],
                "original_audit_pointer": audit["source_pointer"].replace("work/supercon-ml/", ""),
                "audit_record_sha256_canonical_json": audit["audit_record_sha256_canonical_json"],
                "prior_search_log_count": audit["prior_search_log_count"],
                "prior_search_log_sha256_canonical_json": audit["prior_search_log_sha256_canonical_json"],
                "conditions_as_recorded": audit["conditions_as_recorded"],
                "literature_source_ids": ids, "training_label_created": False}

    mdr_by_id = {row["material_id"]: row for row in crosswalk["candidates"]}
    for row in source["candidates"]:
        structure = row["structure_identity"]
        mdr = mdr_by_id[row["material_id"]]
        candidates.append({
            "material_id": row["material_id"], "formula": row["formula"], "track": row["track"],
            "current": True, "rank": row["rank"], "subtracks": row["subtracks"],
            "prediction_summary": compact_prediction(row),
            "structure_reference": {key: structure[key] for key in (
                "database_id", "database_url", "space_group_as_reported", "n_sites",
                "structure_sha256_canonical_json", "source_pointer", "experimental_phase_or_specimen_match")},
            "model_domain": row["model_domain"], "prior_audit": audit_summary(row),
            "acquisition": {"requested_modalities": ["rho_or_R", "chi_or_M", "C"],
                            "sample_condition_target_join": "not_verified", "training_eligible": False,
                            "raw_dataset_lead_ids": row["acquisition"]["raw_dataset_lead_ids"],
                            "track_dependency": None},
            "mdr_review": {"dataset_version": "240322", "exact_composition_matches": 0,
                           "same_system_different_composition_links": mdr["same_element_system_nonmatching_composition_review_links"],
                           "same_system_unresolved_composition_links": mdr["same_declared_element_system_unresolved_composition_review_links"],
                           "sample_or_structure_join": False},
        })
    for row in source["retired_candidates"]:
        retired.append({"material_id": row["material_id"], "formula": row["formula"], "track": row["track"],
                        "current": False, "reason": row["reason"], "prior_audit": audit_summary(row)})
    out.mkdir(parents=True, exist_ok=True)
    written = []

    def save(name, value, purpose, count=None):
        raw = encode(value)
        assert len(raw) < LIMIT_BYTES, (name, len(raw))
        (out / name).write_bytes(raw)
        item = {"path": name, "bytes": len(raw), "sha256_raw_bytes": sha(raw), "purpose": purpose}
        if count is not None:
            item["records"] = count
        written.append(item)

    def split_records(prefix, key, records, purpose):
        batches, batch = [], []
        for row in records:
            tentative = batch + [row]
            if len(encode({"schema_version": 1, key: tentative})) >= LIMIT_BYTES:
                assert batch, "A record exceeds compact-file size limit"
                batches.append(batch)
                batch = [row]
            else:
                batch = tentative
        if batch:
            batches.append(batch)
        for number, part in enumerate(batches, 1):
            save(f"{prefix}-{number:02d}.json", {"schema_version": 1, key: part}, purpose, len(part))

    split_records("candidates-part", "candidates", candidates, "Current candidate metadata; prediction is explicitly separate from observations")
    split_records("literature-part", "sources", list(source_map.values()), "Scoped source citations, inherited access checks and failures; no label transfer")
    save("retired-candidates.json", {"schema_version": 1, "retired_candidates": retired}, "Five historical IDs, excluded from the current count/ranking", len(retired))
    for name in ("primary-data-leads.json", "mdr-ingestion-risk-audit.json"):
        save(name, read(data / name), "Primary availability review" if name.startswith("primary") else "Secondary MDR ingestion boundaries")
    save("mdr-review-crosswalk-summary.json", {
        "schema_version": 1, "source_private_crosswalk_sha256": sha((data / "mdr-candidate-review-crosswalk.json").read_bytes()),
        "dataset_doi": crosswalk["dataset_doi"], "readme_doi": crosswalk["readme_doi"],
        "rules": crosswalk["rules"], "summary": crosswalk["summary"], "mdr_sources": crosswalk["mdr_sources"],
        "metadata_correction": crosswalk.get("metadata_correction"),
        "related_system_records": crosswalk["related_system_records"],
        "limitations": crosswalk["limitations"],
        "unresolved_full_metadata_private": crosswalk["unresolved_metadata_file"],
    }, "Zero exact matches; all 20 related-system records retain source num/refno/line and no sample join")
    for name in ("build.py", "validate.py", "README.md"):
        raw = (Path(__file__).resolve().parent / name).read_bytes()
        assert len(raw) < LIMIT_BYTES
        (out / name).write_bytes(raw)
        written.append({"path": name, "bytes": len(raw), "sha256_raw_bytes": sha(raw),
                        "purpose": "Reproducible metadata build/validation" if name.endswith(".py") else "Scope and replay instructions"})
    manifest = {
        "schema_version": 1, "created_on": source["created_on"], "current_candidate_count": 152,
        "retired_candidate_count": 5, "models": source["authority"]["models"],
        "authority": source["authority"], "source_inputs": source["inputs"],
        "source_private_manifest": {"filename": source_path.name, "bytes": source_path.stat().st_size,
                                    "sha256_raw_bytes": EXPECTED_PRIVATE_MANIFEST_SHA256},
        "summary": source["summary"], "files": written,
        "prediction_semantics": {"Storm": "S5 predicts DFT Allen–Dynes Tc; its empirical correction and model scores are predictions, not measured candidate feedback. S6 exploratory results do not replace this ranking.",
                                 "Hurricane": "Released H4 outputs only; p min/max express fitted-model disagreement, not confidence intervals. H6/H7 exploratory results do not replace this ranking.",
                                 "family": "H4 family/type fields are model routing outputs, not an observed pairing mechanism."},
        "structure_hash_rule": "Canonical sorted compact UTF-8 JSON of original stored lattice/elements/frac. Representation-sensitive; no symmetry-equivalence or experimental-phase identity claim.",
        "audit_hash_rule": "Canonical sorted compact UTF-8 JSON of original entire audit material record. Original source-file raw and CRLF-to-LF hashes are both retained; index hashes match LF only.",
        "common_acquisition_requirements": source["acquisition_requirements"],
        "package_boundaries": ["metadata and source references only", "no atoms or raw curve point arrays",
                               "no PDFs, ZIPs, source XLSX or ledger", "all current and retired candidate source checks preserved by reference",
                               "unknown is not a negative label", "no formula-only sample/structure/target join"],
        "models_fitted": 0, "ledger_writes": 0, "new_training_labels": 0,
        "track_dependency_order": [], "files_max_bytes": LIMIT_BYTES,
    }
    # The manifest does not list its own digest, avoiding self-referential hashing.
    (out / "manifest.json").write_bytes(encode(manifest))
    print(json.dumps({"files": [item["path"] for item in written] + ["manifest.json"],
                      "manifest_sha256": sha((out / "manifest.json").read_bytes()),
                      "current": len(candidates), "retired": len(retired), "literature_sources": len(source_map)}, indent=2))


if __name__ == "__main__":
    main()
