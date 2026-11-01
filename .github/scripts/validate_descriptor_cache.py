"""Keep completed descriptor batches reusable after an interrupted training step.

Only known MACE descriptor files and H6 descriptor manifests below the explicitly
named cache directory may be removed. Model weights, datasets and results are
untouched. This checks file integrity, not scientific provenance; H6 checks its
structure, package, aggregation and checkpoint identities when loading a batch.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import zipfile
import zlib
from pathlib import Path

import numpy as np


def validate_cache(cache_dir: Path) -> dict:
    cache_dir = Path(cache_dir)
    if cache_dir.is_symlink():
        raise ValueError("cache root must not be a symbolic link")
    root = cache_dir.resolve()
    manifest_dir = root / "hurricane6_descriptor_manifests"
    if manifest_dir.is_symlink():
        raise ValueError("descriptor manifest directory must not be a symbolic link")
    paths = list(root.glob("mace_mp0_*.npz")) + list(manifest_dir.glob("*.json"))
    # Validate every path before deleting anything. Do not follow cache symlinks.
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("descriptor cache contains a symbolic link or external path")
    checked, discarded = 0, []
    for path in paths:
        try:
            if not path.is_file():
                raise ValueError("expected a regular cache file")
            if path.suffix == ".npz":
                # Own the outer file handle too, including np.load failures.
                with path.open("rb") as stream, np.load(stream, allow_pickle=True) as stored:
                    ids, values = stored["ids"], stored["X"]
                    if (ids.ndim != 1 or values.ndim != 2 or len(ids) != len(values)
                            or not len(ids) or not values.shape[1] or not np.isfinite(values).all()):
                        raise ValueError("incomplete or nonfinite descriptor matrix")
            else:
                saved = json.loads(path.read_text(encoding="utf-8"))
                checkpoint = saved.get("checkpoint", {})
                if (not isinstance(saved.get("generation"), dict)
                        or not isinstance(checkpoint.get("checkpoint_url"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", checkpoint.get("checkpoint_sha256", ""))):
                    raise ValueError("incomplete descriptor manifest")
        except (OSError, ValueError, KeyError, TypeError, AttributeError, EOFError,
                zipfile.BadZipFile, pickle.UnpicklingError, zlib.error) as error:
            # An interrupted np.savez/write_text must not poison the next run.
            # Directories and unrelated files are never deleted by this helper.
            if not path.is_file():
                raise ValueError(f"not a regular descriptor cache file: {path.name}") from error
            path.unlink()
            discarded.append(str(path.relative_to(root)))
            print(f"Discarded incomplete descriptor cache: {path.name} ({type(error).__name__})")
        checked += 1
    return {"checked": checked, "retained": checked - len(discarded), "discarded": discarded}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate_cache(args.cache_dir), sort_keys=True))


if __name__ == "__main__":
    main()

