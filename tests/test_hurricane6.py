import importlib.util
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import hurricane6 as H6


class Hurricane6Tests(unittest.TestCase):
    def test_lofo_also_removes_shared_systems_from_other_families(self):
        families = np.array(["cuprate", "iron-based", "iron-based", "other oxide"])
        systems = np.array(["A-B", "A-B", "B-C", "C-D"])
        train, test = H6.leave_family_masks(families, systems, "cuprate")
        self.assertEqual(np.where(train)[0].tolist(), [2, 3])
        self.assertFalse(set(systems[train]) & set(systems[test]))

    def test_background_cross_fit_excludes_the_entire_candidate_system(self):
        systems = np.array(["In-Rh-Yb", "In-Rh-Yb", "Fe-As", "Ba-O"])
        fold = H6.H3.bg_fold("In-Rh-Yb")
        train = H6.background_masks(systems, {"Fe-As"}, fold)
        self.assertFalse(train[0])
        self.assertFalse(train[1])
        self.assertFalse(train[2])

    def test_unsafe_or_synthetic_cif_is_never_used(self):
        for value in ("../x.cif", "https://example.org/x.cif", "C:\\x.cif", "/x.cif", "data/synth_doped/x.cif", None):
            with self.assertRaises(ValueError):
                H6.safe_cif_path(value)
        self.assertEqual(H6.safe_cif_path("data/source/MP/cifs/mp-1.cif"), "data/source/MP/cifs/mp-1.cif")

    def test_local_cif_path_stays_in_root(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            root = Path(temporary)
            (root / "x.cif").write_bytes(b"example source bytes")
            self.assertEqual(H6.cif_bytes("x.cif", local_root=root), b"example source bytes")

    def test_descriptor_cache_changes_when_coordinates_change(self):
        frame = pd.DataFrame([dict(id="same-id", atoms={"coords": [[0, 0, 0]]})])
        before = H6.descriptor_key(frame, "parents")
        frame.at[0, "atoms"] = {"coords": [[0.1, 0, 0]]}
        self.assertNotEqual(before, H6.descriptor_key(frame, "parents"))

    def test_embedding_validates_row_alignment_and_values(self):
        frame = pd.DataFrame([dict(id="one", atoms={"coords": [[0, 0, 0]]})])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary, \
             patch.object(H6.P, "CACHE", Path(temporary)), \
             patch.object(H6, "descriptor_generation", return_value={"test": True}), \
             patch.object(H6, "checkpoint_identity", return_value={"checkpoint_url": H6.MODEL_URL, "checkpoint_sha256": "abc"}):
            with patch.object(H6.P, "mace_descriptors", return_value=np.ones((2, 3))):
                with self.assertRaises(ValueError):
                    H6.embeddings(frame, "parents")
            with patch.object(H6.P, "mace_descriptors", return_value=np.full((1, 3), np.nan)):
                with self.assertRaises(ValueError):
                    H6.embeddings(frame, "parents")

    def test_protocol_copy_and_hash_are_stable(self):
        original = H6.digest(H6.protocol())
        changed = H6.protocol()
        changed["promising_rule"]["max_background_false_alarms"] = 1
        self.assertEqual(original, H6.digest(H6.protocol()))
        self.assertNotEqual(original, H6.digest(changed))

    def test_descriptors_checkpoint_batches_and_report_generation_versions(self):
        frame = pd.DataFrame([dict(id=str(i), atoms={"coords": [[float(i), 0, 0]]}) for i in range(129)])
        seen = []
        generation = {"packages": {"mace-torch": "test-version"}, "checkpoint_url": H6.MODEL_URL}
        def descriptors(chunk, key, *, model_url=None):
            self.assertEqual(model_url, H6.MODEL_URL)
            cache = H6.P.mace_cache_path(key, model_url=model_url)
            if cache.exists():
                with np.load(cache) as stored:
                    return stored["X"]
            seen.append((len(chunk), key))
            values = np.ones((len(chunk), 3))
            np.savez_compressed(cache, ids=chunk["id"].astype(str).to_numpy(), X=values)
            return values
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary, \
             patch.object(H6.P, "CACHE", Path(temporary)), \
             patch.object(H6, "descriptor_generation", return_value=generation), \
             patch.object(H6, "checkpoint_identity", return_value={"checkpoint_url": H6.MODEL_URL, "checkpoint_sha256": "abc"}), \
             patch.object(H6.P, "mace_descriptors", side_effect=descriptors):
            result, info = H6.embeddings(frame, "parents")
            with patch.object(H6, "checkpoint_identity", side_effect=AssertionError("complete descriptor cache should not reload weights")):
                reused, reused_info = H6.embeddings(frame, "parents")
            np.testing.assert_array_equal(reused, result)
            self.assertEqual(reused_info, info)
        self.assertEqual([n for n, _ in seen], [128, 1])
        self.assertEqual(result.shape, (129, 3))
        self.assertEqual(info["checkpoint_sha256"], "abc")
        self.assertEqual(info["descriptor_generation"], generation)

    def test_checkpoint_identity_uses_public_explicit_url_without_private_map(self):
        calls = []
        foundations = types.ModuleType("mace.calculators.foundations_models")
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            checkpoint = Path(temporary) / "checkpoint.model"
            checkpoint.write_bytes(b"fixed-checkpoint-bytes")
            def download(url):
                calls.append(url)
                return str(checkpoint)
            foundations.download_mace_mp_checkpoint = download
            with patch.dict(sys.modules, {"mace": types.ModuleType("mace"),
                                          "mace.calculators": types.ModuleType("mace.calculators"),
                                          "mace.calculators.foundations_models": foundations}):
                result = H6.checkpoint_identity()
            self.assertEqual(calls, [H6.MODEL_URL])
            self.assertEqual(result["checkpoint_sha256"], hashlib.sha256(checkpoint.read_bytes()).hexdigest())

    def test_sample_preflight_cannot_claim_full_cohort_coverage(self):
        parents = pd.DataFrame([dict(material_id=f"p{i}", family=family) for i, family in enumerate(H6.H.FAMILY_LABEL)])
        crystal = pd.DataFrame([dict(material_id=f"p{i}", id=f"p{i}", atoms={}, parent_index=i, cif="x.cif", cif_sha256="abc") for i in range(4)])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            raw = Path(temporary) / "source.csv"
            raw.write_bytes(b"preflight-test")
            with patch.object(H6.H, "load_3dsc", return_value=pd.DataFrame()), \
                 patch.object(H6.H5, "parent_frame", return_value=parents), \
                 patch.object(H6, "original_structures", return_value=(crystal, [])), \
                 patch.dict(H6.os.environ, HURRICANE_3DSC=str(raw)), \
                 patch.dict(H6.PROTOCOL, {"3dsc_sha256": hashlib.sha256(raw.read_bytes()).hexdigest()}):
                path, passed = H6.prepare_only(output_dir=Path(temporary), parents_per_family=1)
            report = json.loads(path.read_text())
            self.assertTrue(passed)
            self.assertFalse(report["full_cohort_checked"])
            self.assertFalse(report["ready_for_full_embedding_run"])

    def test_unknown_is_not_counted_as_found(self):
        metrics = H6.summary(np.array([10, 10, 0]), np.array([0.9, 0.9, 0.1]), np.array([8, 8, 0]), [False, True, False])
        self.assertEqual(metrics["n_found"], 1)
        self.assertEqual(metrics["found"], 0.5)

    def test_bootstrap_is_paired_by_system_and_reproducible(self):
        y, family, systems = [10, 10, 0], ["cuprate"] * 3, ["A", "A", "B"]
        result = H6.bootstrap_gain(y, family, systems, [True, True, False], [False, False, False], resamples=50)
        self.assertEqual(result["lower95"], 1)
        self.assertEqual(result["upper95"], 1)
        self.assertEqual(result, H6.bootstrap_gain(y, family, systems, [True, True, False], [False, False, False], resamples=50))

    def test_background_prediction_cannot_see_its_own_training_row(self):
        data = H6.prepare_smoke()
        par, ent, bg = data["parents"], data["entries"], data["bg"]
        data["Xp"][:, 0] = np.arange(len(par))
        data["Xe"][:, 0] = np.arange(len(ent))
        data["Xb"][:, 0] = 100 + np.arange(len(bg))

        class RejectSelfTraining:
            def __init__(self, candidate, seed):
                self.c = candidate

            def fit(self, X, y, family, Xb=None):
                self.seen_background = set(Xb[:, 0]) if Xb is not None else set()
                return self

            def predict(self, X, family):
                return np.ones(len(X))

            def parts(self, X, family):
                if self.seen_background & set(X[X[:, 0] >= 100, 0]):
                    raise AssertionError("model was asked to score a background row it trained on")
                return np.full(len(X), 0.6), np.ones(len(X))

        candidate = dict(data["current"], id="P1", rows="parent")
        with patch.object(H6.H2, "Design", RejectSelfTraining), \
             patch.object(H6.H4, "ratio", side_effect=lambda train, groups, query: np.zeros(len(query))), \
             patch.object(H6.SC, "hur_parts", side_effect=lambda model, X, family: model.parts(X, family)):
            result = H6.score_design(candidate, data["Xp"], data["Xe"], data["Xb"],
                                     data["Xp"], data["Xe"], data["Xb"], par.tc.to_numpy(), ent.tc.to_numpy(),
                                     par.family.to_numpy(), ent.family.to_numpy(), par.system.to_numpy(),
                                     ent.system.to_numpy(), bg.chemsys.to_numpy())
        self.assertEqual(len(result["background"]), 4 * len(bg))
        self.assertFalse(any(r["training_system_overlap"] for r in result["background"]))

    @unittest.skipUnless(importlib.util.find_spec("sklearn"), "scikit-learn is needed for the actual-fitting smoke check")
    def test_offline_smoke_writes_only_nonrelease_report(self):
        before = H6.P.PROGRESS.read_bytes()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            with patch.dict(H6.PROTOCOL["bootstrap"], resamples=20):
                report_path = H6.run(smoke=True, output_dir=Path(temporary))
            report = json.loads(report_path.read_text())
            self.assertFalse(report["adopted"])
            self.assertFalse(report["comparison"]["promising"])
            self.assertEqual(report["mode"], "synthetic_smoke_not_scientific")
            background = pd.read_csv(report_path.with_name(report_path.stem + "-background.csv"))
            self.assertFalse(background["training_system_overlap"].any())
        self.assertEqual(H6.P.PROGRESS.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
