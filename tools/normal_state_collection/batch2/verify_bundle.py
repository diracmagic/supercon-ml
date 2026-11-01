"""Read-only metadata, original-byte and optional replay checks; no model or ledger."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent
ALLOWED_SUFFIXES = {".py", ".json", ".md"}
DRIVE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)")
LOCAL_UNIX = re.compile(r"^/(?:Users|home|mnt|tmp|var|private)(?:/|$)")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def walk(value, location="$", *, in_public=True):
    if isinstance(value, dict):
        if in_public:
            require(not isinstance(value.get("points"), list), "Curve points embedded: " + location)
            require(not isinstance(value.get("data"), list), "Original numeric array embedded: " + location)
            require("used_point_indices" not in value, "Full point-index list embedded: " + location)
            require("event_type" not in value, "Ledger event embedded: " + location)
        for key, child in value.items():
            walk(child, location + "." + key, in_public=in_public)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            walk(child, location + f"[{i}]", in_public=in_public)
    elif isinstance(value, str):
        require(not DRIVE.search(value) and not LOCAL_UNIX.search(value), "Local absolute path: " + location)
        if value.startswith(("http://", "https://")):
            url = urlsplit(value)
            require(url.username is None and url.password is None, "URL credentials: " + location)
            for key, _ in parse_qsl(url.query):
                require(not any(word in key.lower() for word in ("signature", "credential", "token", "password", "api_key", "access_key")),
                        "Authenticated download URL: " + location)


def below(root, relative):
    path = Path(relative)
    require(not path.is_absolute(), "Expected relative input path")
    resolved = (root / path).resolve(strict=True)
    require(root in resolved.parents and resolved.is_file(), "Input escaped declared root")
    require(resolved.suffix.lower() != ".jsonl", "A ledger cannot be a replay input")
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="Optional private batch2 originals; hash checks only")
    parser.add_argument("--replay-root", type=Path, help="Optional generated replay directory; compare captured outputs")
    args = parser.parse_args()
    documents, scripts = {}, []
    files = sorted(p for p in ROOT.rglob("*") if p.is_file())
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        require(path.suffix in ALLOWED_SUFFIXES, "Binary/raw/ledger file in public bundle: " + name)
        require(not name.endswith("collection.json"), "Complete collection in public bundle: " + name)
        require(path.stat().st_size <= 70_000, "Public metadata/source file exceeds 70KB: " + name)
        raw = path.read_bytes()
        require(b"\r" not in raw, "Expected LF text: " + name)
        text = raw.decode("utf-8")
        require(not DRIVE.search(text), "Local absolute path in source: " + name)
        if path.suffix == ".py":
            compile(ast.parse(text, filename=name), name, "exec")
            scripts.append(name)
        elif path.suffix == ".json":
            documents[name] = json.loads(text)
            walk(documents[name], name)
    provenance = documents["bundle-provenance.json"]
    for item in provenance["scripts"] + provenance["metadata"] + provenance.get("helper_files", []):
        require(sha(below(ROOT, item["path"])) == item["bundled_sha256"], "Bundled checksum changed: " + item["path"])
    for item in provenance["metadata"]:
        for omitted in item["omitted_index_arrays"]:
            require(omitted["count"] >= 0 and re.fullmatch("[0-9a-f]{64}", omitted["canonical_sha256"]),
                    "Missing compact point-index provenance")
    policy_path = ROOT.parent / "protocol" / "normal-state-policy.json"
    require(hashlib.sha256(canonical(load(policy_path))).hexdigest() == provenance["extraction_policy_canonical_sha256"],
            "Frozen extraction policy changed")
    original_files = 0
    if args.data_root is not None:
        private = args.data_root.resolve(strict=True)
        for record in documents["source-inputs.json"]["files"]:
            require(sha(below(private, record["raw_path"])) == record["sha256"], "Original SHA256 changed: " + record["raw_path"])
            original_files += 1
    replay_checks = 0
    if args.replay_root is not None:
        private = args.replay_root.resolve(strict=True)
        for record in documents["replay-validation.json"]["collections"]:
            path = below(private, record["path"])
            require(sha(path) == record["original_bytes_sha256"], "Default replay differs: " + record["path"])
            doc = load(path)
            require(len(doc["curves"]) == record["curves"] and sum(len(c["points"]) for c in doc["curves"]) == record["point_records"],
                    "Replayed curve/point counts differ")
            require(len(doc["targets"]) == record["targets"] and len(doc["links"]) == record["links"],
                    "Replayed target/link decisions differ")
            replay_checks += 1
        aggregate = documents["replay-validation.json"]["aggregate"]
        registry = load(below(private, "combined/registry.json"))
        collection = load(below(private, "combined/collection.json"))
        subset = {k: collection[k] for k in ("curves", "targets", "links")}
        require(hashlib.sha256(canonical(registry)).hexdigest() == aggregate["registry_canonical_sha256"], "Rebased registry differs")
        require(hashlib.sha256(canonical(subset)).hexdigest() == aggregate["scientific_arrays_canonical_sha256"],
                "Aggregate scientific arrays differ")
        replay_checks += 2
    print(json.dumps({"status": "pass", "public_files": len(files), "python_sources_compiled_only": len(scripts),
                      "json_documents_checked": len(documents), "original_files_sha256_checked": original_files,
                      "replay_checks": replay_checks, "raw_curve_fulltext_or_ledger_files_bundled": 0,
                      "extractors_executed": 0, "ledger_files_read_or_written": 0, "models_fitted": 0}, indent=2))


if __name__ == "__main__":
    main()
