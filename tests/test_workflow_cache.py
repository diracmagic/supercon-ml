"""Failure-recovery tests for the actual helper used by Train's always-save step."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workflow_cache", ROOT / ".github/scripts/validate_descriptor_cache.py")
cache_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache_helper)


class WorkflowCacheTests(unittest.TestCase):
    def test_partial_batch_does_not_discard_completed_batches_or_source_data(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            cache = Path(temporary)
            good = cache / "mace_mp0_completed.npz"
            np.savez_compressed(good, ids=np.array(["p1", "p2"], dtype=object), X=np.ones((2, 3)))
            original = good.read_bytes()
            (cache / "mace_mp0_interrupted.npz").write_bytes(b"PK\x03\x04truncated zip")
            np.savez_compressed(cache / "mace_mp0_wrong_rows.npz", ids=["p1"], X=np.ones((2, 3)))
            np.savez_compressed(cache / "mace_mp0_nonfinite.npz", ids=["p1"], X=[[np.nan]])
            source = cache / "3DSC_MP.csv"
            source.write_text("source dataset must survive", encoding="utf-8")
            unrelated = cache / "unrelated.npz"
            unrelated.write_bytes(b"not a descriptor cache")
            manifest_dir = cache / "hurricane6_descriptor_manifests"
            manifest_dir.mkdir()
            manifest = manifest_dir / "completed.json"
            manifest.write_text(json.dumps({"generation": {"packages": {}}, "checkpoint": {
                "checkpoint_url": "https://example.org/checkpoint", "checkpoint_sha256": "a" * 64}}), encoding="utf-8")
            original_manifest = manifest.read_bytes()
            (manifest_dir / "interrupted.json").write_text('{"generation":', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = cache_helper.validate_cache(cache)
            self.assertEqual(result["retained"], 2)
            self.assertEqual(len(result["discarded"]), 4)
            self.assertEqual(good.read_bytes(), original)
            self.assertEqual(manifest.read_bytes(), original_manifest)
            self.assertEqual(source.read_text(encoding="utf-8"), "source dataset must survive")
            self.assertEqual(unrelated.read_bytes(), b"not a descriptor cache")
            self.assertEqual(cache_helper.validate_cache(cache)["discarded"], [])

    def test_missing_cache_is_a_safe_noop(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            missing = Path(temporary) / "not-created"
            self.assertEqual(cache_helper.validate_cache(missing), {"checked": 0, "retained": 0, "discarded": []})
            self.assertFalse(missing.exists())

    def test_symbolic_link_cannot_remove_or_archive_an_external_target(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            target = root / "outside-cache.npz"
            target.write_bytes(b"external source")
            try:
                (cache / "mace_mp0_link.npz").symlink_to(target)
            except OSError:
                self.skipTest("creating symlinks is unavailable on this host")
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                cache_helper.validate_cache(cache)
            self.assertEqual(target.read_bytes(), b"external source")


if __name__ == "__main__":
    unittest.main()
