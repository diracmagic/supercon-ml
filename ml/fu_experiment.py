"""Isolated, report-only Fu-inspired lattice descriptor comparison.

The frozen protocol is checked and copied before loading targets. A failed neural
bank blocks every arm. No released model, feedback label or historical result is
changed. Synthetic smoke output is never scientific evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROTOCOL_SHA256 = "c4e40277a96a0af5dd69a765db8cf487beabd7b7421550fa74a3e4a8cc4f423d"
PROTOCOL_V2_SHA256 = "fa46fbc0cce710e7dad454fa4f0c27bfa5477cc36d39b1a451cc1e99b6f88d60"
KNOWN_PROTOCOLS = {PROTOCOL_SHA256: "fu-lattice-pilot-v1",
                   PROTOCOL_V2_SHA256: "fu-lattice-pilot-v2-solver-convergence"}
ARMS = ("Q0", "QG", "QE", "QN")
CONTRASTS = (("QN", "Q0"), ("QG", "Q0"), ("QE", "Q0"),
             ("QN", "QG"), ("QE", "QG"), ("QN", "QE"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(plain(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def freeze_protocol(protocol_path, output_dir):
    raw = Path(protocol_path).read_bytes()
    fingerprint = hashlib.sha256(raw).hexdigest()
    if fingerprint not in KNOWN_PROTOCOLS:
        raise ValueError("Protocol bytes differ from the frozen Fu pilot")
    protocol = json.loads(raw)
    out = Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output directory must be empty; experiments never overwrite evidence")
    out.mkdir(parents=True, exist_ok=True)
    (out / "protocol.json").write_bytes(raw)
    (out / "protocol.sha256").write_text(fingerprint + "\n", encoding="ascii")
    return protocol, fingerprint


def runtime_record():
    import contextlib
    import io
    import subprocess
    import sklearn
    result = {"python": sys.version, "platform": platform.platform(),
              "machine": platform.machine(), "processor": platform.processor(),
              "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__}
    import os
    result["environment"] = {k: os.environ.get(k) for k in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NPY_DISABLE_CPU_FEATURES",
        "OPENBLAS_CORETYPE", "MKL_CBWR", "PYTHONHASHSEED")}
    # Hardware probes run in child processes; NumPy/BLAS inventory below is
    # captured in this very process, after loading the numerical packages.
    probe = None
    if shutil.which("lscpu"):
        probe = ["lscpu"]
    elif sys.platform == "win32" and shutil.which("powershell.exe"):
        probe = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "(Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name) -join '; '"]
    elif sys.platform == "darwin" and shutil.which("sysctl"):
        probe = ["sysctl", "-n", "machdep.cpu.brand_string"]
    result["cpu_model"] = platform.processor() or "unavailable"
    if probe:
        try:
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            completed = subprocess.run(probe, capture_output=True, text=True, timeout=10, check=False, **options)
            result["cpu_probe"] = {"command": probe[0], "exit_code": completed.returncode,
                                   "stdout": completed.stdout[:24000], "stderr": completed.stderr[:2000]}
            if completed.returncode == 0 and completed.stdout.strip():
                if probe[0] == "lscpu":
                    for line in completed.stdout.splitlines():
                        if line.strip().lower().startswith("model name:"):
                            result["cpu_model"] = line.split(":", 1)[1].strip()
                else:
                    result["cpu_model"] = completed.stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            result["cpu_probe"] = {"command": probe[0], "unavailable": str(error)}
    try:
        import scipy.linalg  # Load the libraries in this process before inspection.
        from threadpoolctl import threadpool_info
        result["threadpools"] = threadpool_info()
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            np.show_runtime()
        result["numpy_runtime_same_process"] = stream.getvalue()
    except ImportError as error:
        result["threadpool_unavailable"] = str(error)
    return result


def manifest(out):
    files = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*"))
             if p.is_file() and p.name != "artifact-manifest.json"}
    write_json(out / "artifact-manifest.json", {"sha256": files})


def validate_bank(bank, fingerprint, *, smoke=False):
    import fu_graphlets as FG
    if fingerprint not in KNOWN_PROTOCOLS:
        raise ValueError("Unknown unfrozen protocol")
    if bank.get("protocol_sha256") != fingerprint:
        raise ValueError("Neural bank belongs to a different protocol")
    if bank.get("synthetic", False) and not smoke:
        raise ValueError("Synthetic adapter bank cannot enter a real comparison")
    if bank.get("qc_passed") is not True or bank.get("status") != "passed":
        raise ValueError("Neural bank failed or is incomplete; no downstream comparison permitted")
    if list(bank.get("motif_masks", [])) != list(FG.GRAPH_MASKS):
        raise ValueError("Neural bank and material graph class order differ")
    exact = np.asarray(bank["exact_features"], float)
    neural = np.asarray(bank["neural_features"], float)
    names = bank.get("feature_names", [])
    if exact.shape != (11, 14) or neural.shape != (11, 14) or len(names) != 14:
        raise ValueError("Incomplete frozen 11-by-14 neural/exact lookup")
    if not np.isfinite(exact).all() or not np.isfinite(neural).all():
        raise ValueError("Nonfinite solver lookup; exact values never replace neural failures")
    return exact, neural, names


def load_bank(bank_dir, protocol_path, out, *, smoke):
    fingerprint = sha(protocol_path)
    if fingerprint not in KNOWN_PROTOCOLS:
        raise ValueError("Unknown unfrozen bank protocol")
    if bank_dir is None:
        if not smoke:
            raise ValueError("Real comparisons require --bank-dir from the separate QC-gated solver job")
        import fu_graphlets as FG
        # Deterministic adapter fixture, deliberately neither an ED result nor a
        # trained neural state. It exists only to exercise synthetic CV plumbing.
        fixture = np.arange(11 * 14, dtype=float).reshape(11, 14) / 154.
        bank = {"status": "passed", "qc_passed": True, "synthetic": True,
                "scientific_evidence": False, "protocol_sha256": fingerprint,
                "motif_masks": list(FG.GRAPH_MASKS), "exact_features": fixture.tolist(),
                "neural_features": (fixture * .9).tolist(),
                "feature_names": [f"synthetic_fixture_{i}" for i in range(14)]}
        (out / "bank").mkdir()
        write_json(out / "bank" / "bank.json", bank)
        return bank
    source = Path(bank_dir).resolve()
    if source == out.resolve() or out.resolve() in source.parents or source in out.resolve().parents:
        raise ValueError("External bank and experiment directories must be disjoint")
    # Copy the complete bank, not only its lookup table: retain H, weights and QC.
    shutil.copytree(source, out / "bank")
    if not smoke:
        from fu_wavefunction import check_bank
        verification = check_bank(out / "bank", protocol_path)
        write_json(out / "bank-verification.json", verification)
        if not verification["passed"]:
            raise ValueError("Saved neural states/Hamiltonians failed independent bank verification: "
                             + json.dumps(verification["errors"]))
    return json.loads((out / "bank" / "bank.json").read_text(encoding="utf-8"))


def _structure_rows(out, ids, atoms, provenance):
    source = out / "source"
    source.mkdir(exist_ok=True)
    with (source / "structures.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for identifier, crystal in zip(ids, atoms):
            # JSON round trips Python's exact binary floats; no decimal truncation.
            stream.write(json.dumps({"id": str(identifier), "atoms": crystal}, allow_nan=False) + "\n")
    write_json(source / "provenance.json", provenance)


def load_data(model, out, *, smoke):
    import storm6 as S
    import hurricane7 as H
    if model == "storm":
        frame, D, G, diagnostics, extra = S.synthetic_data() if smoke else S.prepare_real()
        ids = np.asarray(frame.id, dtype=str)
        groups = np.asarray(frame.chemsys, dtype=str)
        atoms = frame.atoms.tolist()
        provenance = {"source": "synthetic" if smoke else S.DATA_URL,
                      "source_details": extra[1] if extra else {"synthetic": True},
                      "structure_encoding": "exact parsed source atoms, JSON round-trip floats"}
        if not smoke:
            archive = S.P.CACHE / "alex_supercon.json.zip"
            if not archive.is_file():
                raise ValueError("Loaded Alexandria cache archive is missing; exact raw input evidence required")
            destination = out / "source" / archive.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(archive, destination)
            provenance["raw_source_archive"] = {"file": archive.name, "sha256": sha(destination)}
            provenance["provider_terms"] = {"licence": "CC BY 4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                "provider": "Alexandria electron-phonon data via JARVIS alex_supercon",
                "provider_url": "https://alexandria.icams.rub.de/", "download_url": S.DATA_URL,
                "citation_dois": ["10.1002/adma.202307085", "10.1088/2515-7639/ae6620"],
                "scope": "Provider data retain provider terms; generated descriptors do not relicense inputs"}
        _structure_rows(out, ids, atoms, provenance)
        write_json(out / "geometry-diagnostics.json", diagnostics)
        np.savez_compressed(out / "baseline-inputs.npz", ids=ids, groups=groups, D=D,
                            geometry=G, target=frame.tc.to_numpy(float))
        return {"frame": frame, "ids": ids, "groups": groups, "D": D,
                "geometry": G, "target": frame.tc.to_numpy(float), "atoms": atoms}
    if model != "hurricane":
        raise ValueError("Unknown model")
    data = H.prepare_smoke() if smoke else H.prepare_real()
    parents, geometry, extras = H.validate_data(data, smoke=smoke)
    ids = np.asarray(parents.material_id, dtype=str)
    groups = np.asarray(parents.system, dtype=str)
    if smoke:
        atoms = [{"lattice_mat": (np.eye(3) * (3.2 + .01 * i)).tolist(),
                  "coords": [[0., 0., 0.]], "elements": ["Cu"], "cartesian": False}
                 for i in range(len(parents))]
        provenance = {"synthetic": True, "not_scientific_evidence": True}
    else:
        import hurricane6 as H6
        crystal, failures = H6.original_structures(parents)
        if len(crystal) != len(parents) or failures:
            raise ValueError("Every original parent CIF is required; no replacement or row dropping")
        by_id = crystal.set_index("material_id")
        if by_id.index.duplicated().any() or set(by_id.index.astype(str)) != set(ids):
            raise ValueError("Original CIF IDs differ from the fixed parent cohort")
        atoms, saved = [], []
        source = out / "source" / "cifs"
        source.mkdir(parents=True, exist_ok=True)
        expected = {str(r["material_id"]): r["cif_sha256"]
                    for r in data["provenance"]["original_cifs"]}
        import os
        local = os.environ.get("HURRICANE_3DSC_ROOT")
        for identifier in ids:
            row = by_id.loc[identifier]
            raw = H6.cif_bytes(row["cif"], local_root=Path(local) if local else None)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != expected[identifier] or digest != row["cif_sha256"]:
                raise ValueError("CIF changed between baseline and graph mapping")
            filename = digest + ".cif"
            (source / filename).write_bytes(raw)
            atoms.append(row["atoms"])
            saved.append({"id": identifier, "sha256": digest, "file": "cifs/" + filename,
                          "pinned_source_path": row["cif"]})
        metadata_source = Path(os.environ.get("HURRICANE_3DSC", H.P.CACHE / "3DSC_MP.csv"))
        if sha(metadata_source) != H.PROTOCOL["source_sha256"]:
            raise ValueError("Pinned metadata changed between cohort preparation and source archival")
        shutil.copyfile(metadata_source, out / "source" / "3DSC_MP.csv")
        provenance = {**data["provenance"], "saved_cifs": saved,
            "metadata_snapshot": {"file": "3DSC_MP.csv", "sha256": sha(metadata_source),
                                  "url": H.H.DSC_URL, "commit": H.H.DSC_COMMIT},
            "provider_terms": {"licence": "CC BY 4.0", "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                "provider": "3DSC original Materials Project CIFs and SuperCon-linked metadata",
                "provider_url": "https://github.com/aimat-lab/3DSC", "citation": H.H.DSC_CITE,
                "materials_project_doi": "10.1063/1.4812323",
                "scope": "Provider data retain provider terms; generated descriptors do not relicense inputs"}}
    _structure_rows(out, ids, atoms, provenance)
    metadata = parents.drop(columns=[c for c in ("row", "comp", "elec") if c in parents]).copy()
    metadata.to_json(out / "parent-metadata.json", orient="records", indent=2)
    np.savez_compressed(out / "baseline-inputs.npz", ids=ids, groups=groups,
                        geometry=geometry, extras=extras, observed_positive=parents.tc.to_numpy() > 0)
    return {"parents": parents, "ids": ids, "groups": groups,
            "geometry": geometry, "extras": extras, "atoms": atoms}


def map_structures(data, bank, out, *, fingerprint, smoke=False):
    import fu_graphlets as FG
    exact, neural, names = validate_bank(bank, fingerprint, smoke=smoke)
    frequencies, flags, diagnostics = [], [], []
    for identifier, atoms in zip(data["ids"], data["atoms"]):
        frequency, diagnostic = FG.extract_graphlets(atoms)
        frequency = np.asarray(frequency, float)
        coverage = np.asarray(FG.coverage_features(diagnostic), float)
        if frequency.shape != (11,) or coverage.shape != (len(FG.COVERAGE_NAMES),):
            raise ValueError("Graph mapper changed frozen feature dimensions")
        finite = np.isfinite(frequency).all()
        if finite != bool(diagnostic["structure_mapped"]):
            raise ValueError("Graph mapper coverage flag contradicts available frequencies")
        if finite and ((frequency < 0).any() or not np.isclose(frequency.sum(), 1., atol=1e-12)):
            raise ValueError("Invalid motif-frequency probability vector")
        frequencies.append(frequency)
        flags.append(coverage)
        diagnostics.append({"id": str(identifier), **diagnostic})
    F, C = np.asarray(frequencies), np.asarray(flags)
    mapped = np.isfinite(F).all(axis=1)
    coverage = float(mapped.mean())
    np.savez_compressed(out / "motif-inputs.npz", ids=data["ids"], groups=data["groups"],
                        motif_masks=np.asarray(FG.GRAPH_MASKS), frequencies=F, coverage_flags=C)
    write_json(out / "mapping-diagnostics.json", {"coverage": coverage, "mapped": int(mapped.sum()),
               "rows": len(mapped), "coverage_names": FG.COVERAGE_NAMES, "rows_diagnostics": diagnostics})
    added = {"Q0": np.empty((len(F), 0)), "QG": np.column_stack([F, C]),
             "QE": np.column_stack([F @ exact, C]), "QN": np.column_stack([F @ neural, C])}
    feature_names = {"Q0": [], "QG": [f"graph_mask_{m}" for m in FG.GRAPH_MASKS] + list(FG.COVERAGE_NAMES),
                     "QE": ["exact_" + n for n in names] + list(FG.COVERAGE_NAMES),
                     "QN": ["neural_" + n for n in names] + list(FG.COVERAGE_NAMES)}
    np.savez_compressed(out / "added-features.npz", **added)
    write_json(out / "added-feature-names.json", feature_names)
    if coverage < .95:
        raise ValueError(f"Structural mapping coverage {coverage:.4f} is below frozen 95%; no rows dropped")
    return added, feature_names


def storm_forecast(D, G, A, y, train, query, *, seed, params):
    import storm6 as S
    from sklearn.ensemble import HistGradientBoostingRegressor
    fmap = S.FeatureMap("R2").fit(D[train], G[train])
    base_train, base_query = fmap.transform(D[train], G[train]), fmap.transform(D[query], G[query])
    # The unchanged baseline remains exactly the Storm7 map. Added columns have
    # an independent training-only all-missing decision, with native NaN routing.
    keep = np.isfinite(A[train]).any(axis=0)
    X = np.column_stack([base_train, A[train][:, keep]])
    Z = np.column_stack([base_query, A[query][:, keep]])
    model = HistGradientBoostingRegressor(random_state=seed, **params)
    pred = np.clip(np.expm1(model.fit(X, np.log1p(y[train])).predict(Z)), 0., None)
    if not np.isfinite(pred).all():
        raise ValueError("Nonfinite Storm prediction")
    return pred, {"baseline_keep": fmap.keep.tolist(), "added_keep": keep.tolist(), "fit_rows": len(train)}


def _summary(point, values, repetitions):
    values = np.asarray(values, float)
    finite = values[np.isfinite(values)]
    return {"delta_new_minus_reference": float(point), "lower95": float(np.quantile(finite, .025)) if len(finite) else None,
            "upper95": float(np.quantile(finite, .975)) if len(finite) else None,
            "valid_resamples": len(finite), "requested_resamples": repetitions,
            "conditioning": "fixed exploratory held-out predictions; no selection adjustment"}


def cluster_draws(groups, repetitions, out):
    # Pandas string columns can arrive as object arrays; store names as Unicode
    # so every NPZ member remains readable without enabling pickle.
    unique, inverse = np.unique(np.asarray(groups, dtype=str), return_inverse=True)
    draws = np.random.default_rng(7).integers(0, len(unique), size=(repetitions, len(unique)))
    np.savez_compressed(out / "bootstrap-draws.npz", systems=unique, draws=draws)
    return unique, inverse, draws


def storm_contrasts(y, predictions, groups, masks, *, repetitions, out):
    unique, inverse, draws = cluster_draws(groups, repetitions, out)
    result = {}
    for first, second in CONTRASTS:
        name = first + "-" + second
        result[name] = {}
        if first not in predictions or second not in predictions:
            result[name] = {"status": "unavailable_incomplete_arm"}
            continue
        difference = abs(y - predictions[first]) - abs(y - predictions[second])
        for label, mask in masks.items():
            counts = np.bincount(inverse[mask], minlength=len(unique))
            if not mask.any():
                result[name][label] = {"status": "no_rows"}
                continue
            sums = np.bincount(inverse[mask], weights=difference[mask], minlength=len(unique))
            denominator = counts[draws].sum(axis=1)
            values = np.divide(sums[draws].sum(axis=1), denominator,
                               out=np.full(repetitions, np.nan), where=denominator > 0)
            result[name][label] = _summary(difference[mask].mean(), values, repetitions)
    return result


def run_storm(data, added, out, report, *, smoke):
    import storm6 as S
    from sklearn.model_selection import GroupKFold
    D, G, y, groups, ids = (data[k] for k in ("D", "geometry", "target", "groups", "ids"))
    splits = list(GroupKFold(5).split(D, groups=groups))
    fold_of = np.zeros(len(y), int)
    tail = y >= np.quantile(y, .9)
    ood, split_ood = np.zeros(len(y), bool), np.zeros(len(y), bool)
    distances, split_distances = np.zeros(len(y)), np.zeros(len(y))
    folds = []
    for fold, (train, test) in enumerate(splits):
        proper, cal = S.calibration_indices(train, groups, fold)
        fold_of[test] = fold + 1
        distances[test], ood[test], threshold = S.ood_distance(D[train], D[test], groups[train])
        split_distances[test], split_ood[test], split_threshold = S.ood_distance(D[proper], D[test], groups[proper])
        entry = {"fold": fold + 1, "ood_threshold": threshold, "proper_ood_threshold": split_threshold}
        for name, ix in (("train", train), ("test", test), ("proper_train", proper), ("calibration", cal)):
            entry[name + "_ids"] = ids[ix].tolist()
            entry[name + "_systems"] = sorted(set(groups[ix]))
        folds.append(entry)
    write_json(out / "folds.json", folds)
    predictions, rows, cal_rows = {}, [], []
    for arm in ARMS:
        entry = report["arms"][arm]
        entry.update(status="running", folds=[])
        pred = {key: np.full(len(y), np.nan) for key in ("point", "center", "lo", "hi")}
        try:
            for fold, (train, test) in enumerate(splits):
                proper, cal = S.calibration_indices(train, groups, fold)
                point, fit = storm_forecast(D, G, added[arm], y, train, test, seed=7 + fold,
                                             params=S.SMOKE_PARAMS if smoke else S.PARAMS)
                query = np.concatenate([cal, test])
                split, proper_fit = storm_forecast(D, G, added[arm], y, proper, query, seed=7 + fold,
                                                    params=S.SMOKE_PARAMS if smoke else S.PARAMS)
                center = split[len(cal):]
                lo, hi, q = S.split_ranges(y[cal], split[:len(cal)], groups[cal], center)
                for key, values in (("point", point), ("center", center), ("lo", lo), ("hi", hi)):
                    pred[key][test] = values
                scores = abs(np.log1p(y[cal]) - np.log1p(split[:len(cal)]))
                maxima = {str(g): float(scores[groups[cal] == g].max()) for g in np.unique(groups[cal])}
                filename = f"{arm}-fold{fold + 1}-fits.json"
                write_json(out / filename, {"point": fit, "proper_train": proper_fit,
                    "point_fit_ids": ids[train].tolist(), "proper_fit_ids": ids[proper].tolist()})
                entry["folds"].append({"fold": fold + 1, "fit_artifact": filename,
                    "calibration_group_scores": maxima, "q": q,
                    "interval_status": "finite" if q is not None else "unbounded_insufficient_groups"})
                for j, i in enumerate(cal):
                    cal_rows.append({"arm": arm, "fold": fold + 1, "id": ids[i], "system": groups[i],
                                     "target": y[i], "proper_prediction": split[j], "abs_log_residual": scores[j]})
                write_json(out / "report.json", report)
            entry.update(status="completed", point=S.point_metrics(y, pred["point"], groups, fold_of, tail_mask=tail, ood=ood),
                         split_center=S.point_metrics(y, pred["center"], groups, fold_of, tail_mask=tail, ood=split_ood),
                         intervals=S.interval_metrics(y, pred["lo"], pred["hi"], groups, tail, split_ood))
            predictions[arm] = pred["point"]
        except (ValueError, RuntimeError, FloatingPointError) as error:
            entry.update(status="failed", reason=f"{type(error).__name__}: {error}")
        for i in range(len(y)):
            rows.append({"arm": arm, "id": ids[i], "system": groups[i], "fold": fold_of[i], "target_dft_k": y[i],
                         "prediction_k": pred["point"][i], "proper_center_k": pred["center"][i], "lo_k": pred["lo"][i],
                         "hi_k": pred["hi"][i] if np.isfinite(pred["hi"][i]) else None,
                         "interval_unbounded": bool(np.isinf(pred["hi"][i])), "ood": bool(ood[i]),
                         "distance": distances[i], "proper_ood": bool(split_ood[i]), "proper_distance": split_distances[i],
                         "prediction_status": "available" if np.isfinite(pred["point"][i]) else "failed"})
        pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False, float_format="%.17g")
        pd.DataFrame(cal_rows).to_csv(out / "calibration-predictions.csv", index=False, float_format="%.17g")
        write_json(out / "report.json", report)
    report["contrasts"] = storm_contrasts(y, predictions, groups,
        {"overall": np.ones(len(y), bool), "target_top10pct": tail, "ood": ood},
        repetitions=20 if smoke else 1000, out=out)


class AddedRanker:
    """H7 R0 baseline and train-only additions, using the unchanged pair head."""
    def __init__(self, alpha, seed):
        self.alpha, self.seed = alpha, seed

    def fit(self, geometry, extras, additions, positive, families, systems):
        import hurricane7 as H
        self.base = H.FeatureBasis("R0").fit(geometry, extras)
        self.extra_scale = H.TrainingScale().fit(additions)
        main = np.column_stack([self.base.transform(geometry, extras), self.extra_scale.transform(additions)])
        names = self.base.names + [f"addition_{i}" for i in np.flatnonzero(self.extra_scale.keep)]
        self.terms = H.TermBasis().fit(main, names, nonlinear=False)
        matrix = self.terms.transform(main)
        self.coef, self.fit_info = H.fit_head(matrix, positive, families, systems,
                                             design="R0", alpha=self.alpha, seed=self.seed)
        if self.fit_info["status"] == "not_converged":
            raise RuntimeError("Ridge head did not converge")
        self.training_systems = sorted(set(map(str, systems)))
        self.identity = {"alpha": self.alpha, "baseline_scale": H.scale_identity(self.base.scale),
                         "addition_scale": H.scale_identity(self.extra_scale), "head_scale": H.scale_identity(self.terms.scale),
                         "coefficients": self.coef.tolist(), "training_systems": self.training_systems,
                         "head_features": self.terms.names, "fit_info": self.fit_info}
        return self

    def predict(self, geometry, extras, additions):
        main = np.column_stack([self.base.transform(geometry, extras), self.extra_scale.transform(additions)])
        values = self.terms.transform(main) @ self.coef
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite P/U score")
        return values


def fit_ranker(data, additions, train, held, alpha, seed):
    parents = data["parents"]
    systems = parents.iloc[train].system.astype(str).to_numpy()
    if set(systems) & set(held):
        raise ValueError("Held chemical systems reached ranker fitting")
    return AddedRanker(alpha, seed).fit(data["geometry"][train], data["extras"][train], additions[train],
        parents.iloc[train].tc.to_numpy() > 0, parents.iloc[train].family.to_numpy(), systems)


def select_alpha(data, additions, train, outer_held):
    import hurricane7 as H
    from sklearn.model_selection import GroupKFold
    parents = data["parents"]
    groups = parents.iloc[train].system.to_numpy()
    expected = sorted(set(parents.iloc[train].family))
    records = []
    for alpha in H.PROTOCOL["alpha_grid"]:
        folds = []
        for fold, (a, b) in enumerate(GroupKFold(H.PROTOCOL["inner_system_folds"]).split(train, groups=groups)):
            tr, val = train[a], train[b]
            held = set(outer_held) | set(parents.iloc[val].system)
            fitted = fit_ranker(data, additions, tr, held, alpha, 7 + fold)
            scores = fitted.predict(data["geometry"][val], data["extras"][val], additions[val])
            folds.append({"fold": fold, "training_ids": parents.iloc[tr].material_id.astype(str).tolist(),
                          "validation_ids": parents.iloc[val].material_id.astype(str).tolist(),
                          "training_systems": fitted.training_systems,
                          "validation_systems": sorted(set(parents.iloc[val].system)),
                          "status": fitted.fit_info["status"],
                          "family_metrics": H.validation_family_metrics(parents.iloc[val], scores, expected)})
        objective = H.inner_objective(folds, expected)
        records.append({"alpha": alpha, "objective": objective, "folds": folds})
    valid = [r for r in records if r["objective"]["macro"] is not None]
    if not valid:
        raise ValueError("No valid training-only inner-family ranking comparison")
    best = max(r["objective"]["macro"] for r in valid)
    chosen = max(r["alpha"] for r in valid if r["objective"]["macro"] >= best - H.PROTOCOL["alpha_tie_auc_tolerance"])
    return chosen, records


def hurricane_contrasts(parents, predictions, *, repetitions, out):
    import hurricane7 as H
    groups = parents.system.astype(str).to_numpy()
    unique, inverse, draws = cluster_draws(groups, repetitions, out)
    blocks = [np.flatnonzero(inverse == i) for i in range(len(unique))]
    keys = ("observed_pu_auc", "recall_at_budget")
    def macro(index, scores):
        local = parents.iloc[index]
        metrics = [H.metrics(local.loc[local.family == family].tc.to_numpy() > 0,
                            scores[index][local.family.to_numpy() == family]) for family in H.PROTOCOL["families"]]
        return {key: float(np.mean([row[key] for row in metrics]))
                if all(row[key] is not None for row in metrics) else np.nan for key in keys}
    samples = {arm: {key: [] for key in keys} for arm in predictions}
    for draw in draws:
        selected = np.concatenate([blocks[i] for i in draw])
        for arm, scores in predictions.items():
            values = macro(selected, scores)
            for key in keys:
                samples[arm][key].append(values[key])
    original = {arm: macro(np.arange(len(parents)), scores) for arm, scores in predictions.items()}
    result = {}
    for first, second in CONTRASTS:
        name = first + "-" + second
        if first not in predictions or second not in predictions:
            result[name] = {"status": "unavailable_incomplete_arm"}
        else:
            result[name] = {key: _summary(original[first][key] - original[second][key],
                np.asarray(samples[first][key]) - np.asarray(samples[second][key]), repetitions) for key in keys}
    return result


def run_hurricane(data, added, out, report, *, smoke):
    import hurricane7 as H
    parents = data["parents"]
    splits = []
    for family in H.PROTOCOL["families"]:
        train, test, held = H.outer_split(parents, family)
        splits.append((family, train, test, held))
    write_json(out / "folds.json", [{"family": family, "training_ids": parents.iloc[train].material_id.astype(str).tolist(),
        "test_ids": parents.iloc[test].material_id.astype(str).tolist(), "training_systems": sorted(set(parents.iloc[train].system)),
        "held_systems": sorted(held), "held_family_training_memberships": sum(family in v for v in parents.iloc[train].full_family_membership)}
        for family, train, test, held in splits])
    predictions, rows = {}, []
    for arm in ARMS:
        scores = np.full(len(parents), np.nan)
        entry = report["arms"][arm]
        entry.update(status="running", families=[])
        for family, train, test, held in splits:
            try:
                alpha, inner = select_alpha(data, added[arm], train, held)
                fitted = fit_ranker(data, added[arm], train, held, alpha, 7)
                scores[test] = fitted.predict(data["geometry"][test], data["extras"][test], added[arm][test])
                filename = f"{arm}-{family}-fit.json"
                write_json(out / filename, {"model": fitted.identity, "inner_selection": inner,
                                           "training_ids": parents.iloc[train].material_id.astype(str).tolist()})
                entry["families"].append({"family": family, "status": "completed", "fit_artifact": filename,
                    **H.metrics(parents.iloc[test].tc.to_numpy() > 0, scores[test])})
            except (ValueError, RuntimeError, FloatingPointError) as error:
                entry["families"].append({"family": family, "status": "failed", "reason": f"{type(error).__name__}: {error}"})
            write_json(out / "report.json", report)
        complete = np.isfinite(scores).all()
        entry["status"] = "completed" if complete else "incomplete"
        entry["macro"] = {key: float(np.mean([r[key] for r in entry["families"]])) if complete else None
                          for key in ("observed_pu_auc", "recall_at_budget")}
        if complete:
            predictions[arm] = scores
        for i, row in parents.iterrows():
            rows.append({"arm": arm, "id": str(row.material_id), "family": row.family, "system": row.system,
                         "observed_positive": bool(row.tc > 0), "catalog_rank_score": scores[i],
                         "prediction_status": "available" if np.isfinite(scores[i]) else "failed"})
        pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False, float_format="%.17g")
    report["contrasts"] = hurricane_contrasts(parents, predictions, repetitions=20 if smoke else 1000, out=out)


def run(*, model, protocol_path, output_dir, bank_dir=None, smoke=False):
    started = time.perf_counter()
    out = Path(output_dir)
    protocol, fingerprint = freeze_protocol(protocol_path, out)  # First persistent operation, before targets.
    report = {"model": model, "protocol_sha256": fingerprint, "report_only": True, "adopted": False,
              "smoke": bool(smoke), "scientific_evidence": not smoke, "status": "preparing_bank",
              "arms": {arm: {"status": "not_run"} for arm in ARMS},
              "contrasts": {a + "-" + b: {"status": "not_run"} for a, b in CONTRASTS}, "failures": []}
    report["solver_selection"] = {"authoritative_numeric_seeds": protocol["solver"]["initialization_seeds"],
        "steps": protocol["solver"]["steps"], "criterion": "lowest finite variational energy among all declared numeric seeds",
        "v2_prose_erratum": ("The v2 selection prose says two seeds; the frozen numeric list of four is authoritative."
                              if fingerprint == PROTOCOL_V2_SHA256 else None)}
    write_json(out / "report.json", report)
    stage = "bank"
    try:
        write_json(out / "runtime.json", runtime_record())
        source_files = list(Path(__file__).parent.glob("*.py"))
        write_json(out / "source-manifest.json", {"sha256_lf": {p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                                                               for p in sorted(source_files)}})
        bank = load_bank(bank_dir, out / "protocol.json", out, smoke=smoke)
        validate_bank(bank, fingerprint, smoke=smoke)
        report["bank"] = {"status": bank["status"], "qc_passed": True, "artifact": "bank/bank.json",
                          "synthetic_adapter_fixture": bool(bank.get("synthetic", False))}
        stage = "data"
        report["status"] = "preparing_data"
        write_json(out / "report.json", report)
        data = load_data(model, out, smoke=smoke)
        report["cohort"] = {"rows": len(data["ids"]), "systems": len(set(data["groups"]))}
        stage = "mapping"
        added, _ = map_structures(data, bank, out, fingerprint=fingerprint, smoke=smoke)
        stage = "models"
        report["status"] = "running"
        write_json(out / "report.json", report)
        (run_storm if model == "storm" else run_hurricane)(data, added, out, report, smoke=smoke)
        report["status"] = "completed" if all(v["status"] == "completed" for v in report["arms"].values()) else "incomplete"
    except Exception as error:
        report["status"] = "blocked_bank_qc" if stage == "bank" else "failed_" + stage
        report["failures"].append({"stage": stage, "reason": f"{type(error).__name__}: {error}"})
        if stage == "bank" and (out / "bank" / "bank.json").is_file():
            try:
                saved_bank = json.loads((out / "bank" / "bank.json").read_text(encoding="utf-8"))
                report["bank"] = {"status": saved_bank.get("status"), "qc_passed": saved_bank.get("qc_passed"),
                    "entries": len(saved_bank.get("entries", [])), "failures": len(saved_bank.get("failures", [])),
                    "artifact": "bank/bank.json", "exact_solver_fallback": False}
            except (OSError, ValueError, TypeError):
                report["bank"] = {"status": "unreadable", "qc_passed": False, "exact_solver_fallback": False}
        for entry in report["arms"].values():
            if entry["status"] == "not_run":
                entry["reason"] = report["failures"][-1]["reason"]
    report["seconds"] = round(time.perf_counter() - started, 3)
    write_json(out / "report.json", report)
    manifest(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, choices=("storm", "hurricane"))
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--bank-dir", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    result = run(model=args.model, protocol_path=args.protocol, output_dir=args.output_dir,
                 bank_dir=args.bank_dir, smoke=args.smoke)
    print(json.dumps({"status": result["status"], "smoke": result["smoke"], "adopted": False}))
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
