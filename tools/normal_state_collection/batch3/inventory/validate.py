"""Validate compact inventory bytes/counts and optionally check the private source replay."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--data-root", type=Path, help="Optional private source inventory directory")
    args = parser.parse_args()
    root = args.bundle_root.resolve()
    manifest = load(root / "manifest.json")
    candidates, sources, retired = [], {}, []
    forbidden_keys = {"atoms", "lattice", "frac", "coordinates", "points", "observations"}

    def inspect(value):
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys), set(value) & forbidden_keys
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            assert not re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", value), "Local absolute path"

    for item in manifest["files"]:
        path = root / item["path"]
        assert path.parent == root and path.is_file()
        assert digest(path) == item["sha256_raw_bytes"]
        assert path.stat().st_size == item["bytes"] < 70000
        if path.suffix != ".json":
            continue
        value = load(path)
        inspect(value)
        if item["path"].startswith("candidates-part-"):
            candidates += value["candidates"]
        elif item["path"].startswith("literature-part-"):
            for source in value["sources"]:
                assert source["source_id"] not in sources
                sources[source["source_id"]] = source
        elif item["path"] == "retired-candidates.json":
            retired = value["retired_candidates"]
        elif item["path"] == "mdr-review-crosswalk-summary.json":
            stats = value["summary"]["file_stats"]
            assert stats["20240322_MDR_OAndM.txt"]["total_records"] == 33458
            assert stats["240322_MDR_Organic.txt"]["total_records"] == 568
            assert stats["240322_MDR_Organic.txt"]["empty_logical_rows_excluded"] == [571]
            for table in stats.values():
                assert table["strictly_parsed_records"] + table["unresolved_records"] == table["total_records"]
            assert value["summary"]["exact_matching_mdr_records"] == 0
            assert value["metadata_correction"]["candidate_match_results_changed"] is False
    inspect(manifest)
    assert len(candidates) == len({row["material_id"] for row in candidates}) == 152
    assert collections.Counter(row["track"] for row in candidates) == {"Storm": 102, "Hurricane": 50}
    assert len(retired) == 5 and not ({row["material_id"] for row in candidates} & {row["material_id"] for row in retired})
    for row in candidates + retired:
        for sid in row["prior_audit"]["literature_source_ids"]:
            assert sid in sources
        assert row["prior_audit"]["training_label_created"] is False
        if row["current"]:
            assert row["prediction_summary"]["observed_label"] is False
            assert row["acquisition"]["track_dependency"] is None
            assert row["acquisition"]["training_eligible"] is False
            assert row["mdr_review"]["exact_composition_matches"] == 0
    assert manifest["models_fitted"] == manifest["ledger_writes"] == manifest["new_training_labels"] == 0
    assert manifest["track_dependency_order"] == []
    replay = "not_requested"
    if args.data_root:
        file = args.data_root / manifest["source_private_manifest"]["filename"]
        assert digest(file) == manifest["source_private_manifest"]["sha256_raw_bytes"]
        original = {row["material_id"]: row for row in load(file)["candidates"]}
        for row in candidates:
            old = original[row["material_id"]]
            assert row["formula"] == old["formula"] and row["rank"] == old["rank"]
            assert row["track"] == old["track"] and row["subtracks"] == old["subtracks"]
            assert row["structure_reference"]["structure_sha256_canonical_json"] == old["structure_identity"]["structure_sha256_canonical_json"]
            assert row["prior_audit"]["audit_record_sha256_canonical_json"] == old["prior_audit"]["audit_record_sha256_canonical_json"]
            assert row["prior_audit"]["status"] == old["prior_audit"]["status"]
            p = old["prediction"]
            output = row["prediction_summary"]["outputs"]
            assert output["p_sc_model_score"] == p["p_sc"]
            if row["track"] == "Storm":
                assert output["tc_dft_pred_k"] == p["tc"]
                assert output["tc_empirical_corrected_pred_k"] == p["tc_cal"]
                assert output["tc_dft_interval_lo_k"] == p["lo"] and output["tc_dft_interval_hi_k"] == p["hi"]
                assert output["lambda_model_pred"] == p["lambda"] and output["wlog_model_pred_as_reported"] == p["wlog"]
            else:
                assert output["tc_model_output_k"] == p["tc"] and output["tc_given_sc_model_output_k"] == p["tc_sc"]
                assert output["tc_model_interval_lo_k"] == p["lo"] and output["tc_model_interval_hi_k"] == p["hi"]
                assert output["p_model_disagreement_lo"] == p["p_lo"] and output["p_model_disagreement_hi"] == p["p_hi"]
                for destination, original_key in (("routing_family", "family"), ("routing_types", "types")):
                    if original_key in p:
                        assert output[destination] == p[original_key]
                    else:
                        assert destination not in output
        replay = "passed_152_rows_against_private_source"
    print(json.dumps({"status": "passed", "current": len(candidates), "retired": len(retired),
                      "literature_sources": len(sources), "hashed_files": len(manifest["files"]),
                      "manifest_sha256": digest(root / "manifest.json"), "private_source_replay": replay,
                      "models_fitted": 0, "ledger_writes": 0}, indent=2))


if __name__ == "__main__":
    main()
