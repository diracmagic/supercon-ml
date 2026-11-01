"""Verify the published acquisition snapshot; never extract data or train."""
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    manifest = json.loads((ROOT / "bundle-provenance.json").read_text(encoding="utf-8"))
    expected = {item["path"]: item for item in manifest["files"]}
    require(len(expected) == len(manifest["files"]), "Duplicate public file")
    actual = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob("*")
              if p.is_file() and "__pycache__" not in p.relative_to(ROOT).parts
              and p != ROOT / "bundle-provenance.json"}
    require(actual.keys() == expected.keys(), "Public acquisition snapshot file set changed")
    for name, path in actual.items():
        raw = path.read_bytes()
        require(path.suffix in {".json", ".py", ".md"}, "Unexpected raw/binary file")
        require(len(raw) <= 70_000 and b"\r" not in raw, "Expected compact LF source/metadata")
        require(sha(raw) == expected[name]["sha256"], "Changed snapshot bytes: " + name)
    policy = json.loads((ROOT.parent / "protocol/normal-state-policy.json").read_text(encoding="utf-8"))
    canonical = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    require(sha(canonical) == manifest["frozen_extraction_policy_sha256"], "Frozen extraction policy changed")
    mdr = json.loads((ROOT / "mdr-summary.json").read_text(encoding="utf-8"))
    require(mdr["dataset_doi"] == "10.48505/nims.4487", "MDR version changed")
    require(all(mdr[key] == 0 for key in ("models_fitted", "training_rows_exported", "ledger_events_added")),
            "Secondary catalog must not emit model/experimental evidence")
    require(manifest["models_fitted"] == 0 and manifest["adopted"] is False,
            "Acquisition snapshot cannot claim a model result")
    print(json.dumps({"status": "pass", "public_files_checked": len(actual),
                      "frozen_policy_unchanged": True, "extractors_executed": 0,
                      "models_fitted": 0, "ledger_files_read_or_written": 0}))


if __name__ == "__main__":
    main()
