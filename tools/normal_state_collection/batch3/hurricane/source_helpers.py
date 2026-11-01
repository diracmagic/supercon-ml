"""Small, read-only source-table helpers; no ML or ledger dependency."""
from pathlib import Path
import hashlib
import json
import math


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_provenance(root, relative):
    """Prefer the local retrieval log; bundle copies contain metadata only."""
    local = Path(root) / relative
    path = local if local.exists() else Path(__file__).resolve().parent / "input-metadata" / relative
    return json.loads(path.read_text(encoding="utf-8"))


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2,
                                      allow_nan=False) + "\n").encode("utf-8"))


def compact_curve(curve):
    """Only metadata, a count and a digest leave the private source directory."""
    points = curve["data"]
    result = {key: value for key, value in curve.items() if key != "data"}
    result["point_records"] = len(points)
    result["data_sha256_canonical_json"] = canonical_sha(points)
    return result
