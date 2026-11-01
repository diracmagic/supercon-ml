"""Merge reviewed private inputs; do not append a ledger or fit a model."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import sys
sys.dont_write_bytecode = True

from bundle_common import BUNDLE


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="Private batch2 originals directory")
    parser.add_argument("--previous-root", type=Path, required=True,
                        help="Previous private collection and original-source directory")
    parser.add_argument("--collections-root", type=Path,
                        help="Replayed batch2 JSON directory; defaults to --data-root")
    parser.add_argument("--source-root", type=Path,
                        help="Common parent containing both original-source directories")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve(strict=True)
    previous = args.previous_root.resolve(strict=True)
    collections = (args.collections_root or args.data_root).resolve(strict=True)
    work = (args.source_root or data_root.parent).resolve(strict=True)
    require(work in previous.parents and work in data_root.parents,
            "--source-root must contain both original-source directories")
    output = args.output_dir.resolve()
    require(output != BUNDLE and BUNDLE not in output.parents,
            "Generated curve arrays must stay outside the public bundle")
    parts = [
        (previous, previous, "combined-registry.json", "combined-collection.json", "previous-root"),
        (collections, data_root, "transport/transport-registry.json", "transport/transport-collection.json", "collections-root"),
        (collections, data_root, "thermo/nitral-2024/nitral-registry.json", "thermo/nitral-2024/nitral-collection.json", "collections-root"),
        (collections / "validation", data_root / "validation", "YRu3B2-registry.json", "YRu3B2-collection.json", "collections-root/validation"),
    ]
    registry = {"sources": []}
    collection = {"curves": [], "targets": [], "links": [], "batch_notes": []}
    new = {"curves": [], "targets": [], "links": []}
    manifest = []
    seen = {key: set() for key in ("sources", "curves", "targets")}
    for index, (json_base, source_base, registry_name, collection_name, role) in enumerate(parts):
        rpath, cpath = json_base / registry_name, json_base / collection_name
        r, c = read(rpath), read(cpath)
        for source in r["sources"]:
            source = copy.deepcopy(source)
            relative = Path(source["raw_path"])
            require(not relative.is_absolute(), "Original paths must be relative")
            absolute = (source_base / relative).resolve(strict=True)
            require(source_base.resolve() in absolute.parents and work in absolute.parents,
                    "Original source escaped its declared private source directory")
            require(absolute.suffix.lower() != ".jsonl", "A ledger is not an original source")
            require(hashlib.sha256(absolute.read_bytes()).hexdigest() == source["sha256"],
                    "Original source SHA256 changed: " + relative.as_posix())
            source["raw_path"] = absolute.relative_to(work).as_posix()
            require(source["source_id"] not in seen["sources"], "Duplicate source ID")
            seen["sources"].add(source["source_id"])
            registry["sources"].append(source)
        for key, identifier in (("curves", "curve_id"), ("targets", "target_id")):
            for row in c.get(key, []):
                require(row[identifier] not in seen[key], "Duplicate " + identifier)
                seen[key].add(row[identifier])
                collection[key].append(row)
                if index:
                    new[key].append(row)
        collection["links"].extend(c.get("links", []))
        if index:
            new["links"].extend(c.get("links", []))
        notes = {key: value for key, value in c.items() if key not in ("curves", "targets", "links")}
        # Input-role references remain meaningful after moving a private workspace.
        collection["batch_notes"].append({"collection": role + "/" + collection_name, "notes": notes})
        manifest.append({
            "input_root_role": role, "registry": registry_name, "collection": collection_name,
            "registry_sha256": hashlib.sha256(rpath.read_bytes()).hexdigest(),
            "collection_sha256": hashlib.sha256(cpath.read_bytes()).hexdigest(),
            "curves": len(c["curves"]), "point_records": sum(len(x["points"]) for x in c["curves"]),
            "targets": len(c.get("targets", [])), "links": len(c.get("links", [])),
        })
    corrections = data_root / "observation-corrections.json"
    correction_count = 0
    if corrections.exists():
        # These ledger-specific identities are an explicit private input, never
        # inferred from a formula, a renamed curve or a similar numeric value.
        records = read(corrections)
        require(isinstance(records, list), "Correction map must be an explicit list")
        curves = {row["curve_id"]: row for row in collection["curves"]}
        used_points, used_old_hashes = set(), set()
        for row in records:
            require(isinstance(row, dict) and set(row) == {"curve_id", "point_index", "supersedes", "reason"},
                    "Correction entries need curve_id, point_index, supersedes and reason")
            cid, i, old = row["curve_id"], row["point_index"], row["supersedes"]
            require(isinstance(cid, str) and bool(cid) and cid in curves and type(i) is int and 0 <= i < len(curves[cid]["points"]),
                    "Correction does not identify a current source point")
            require(isinstance(old, str) and re.fullmatch("[0-9a-f]{64}", old), "Invalid superseded observation hash")
            require(isinstance(row["reason"], str) and bool(row["reason"].strip()), "Correction reason required")
            require((cid, i) not in used_points and old not in used_old_hashes, "Duplicate explicit correction")
            used_points.add((cid, i))
            used_old_hashes.add(old)
        collection["observation_corrections"] = records
        new["observation_corrections"] = copy.deepcopy(records)
        correction_count = len(records)
        manifest.append({"input_root_role": "data-root", "observation_corrections": corrections.name,
                         "sha256": hashlib.sha256(corrections.read_bytes()).hexdigest(), "count": correction_count,
                         "ledger_read_or_applied_by_aggregate": False})
    output.mkdir(parents=True, exist_ok=True)
    for name, content in (("registry.json", registry), ("collection.json", collection),
                          ("new-collection.json", new), ("input-manifest.json", manifest)):
        (output / name).write_text(json.dumps(content, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n",
                                  encoding="utf-8")
    print(json.dumps({"sources": len(registry["sources"]), "curves": len(collection["curves"]),
                      "points": sum(len(x["points"]) for x in collection["curves"]),
                      "targets": len(collection["targets"]), "links": len(collection["links"]),
                      "new_points": sum(len(x["points"]) for x in new["curves"]),
                      "explicit_observation_corrections": correction_count,
                      "ledger_files_read_or_written": 0, "models_fitted": 0}))


if __name__ == "__main__":
    main()
