"""Storm 6: frozen, CPU-only, report-only electron-phonon/geometry ablations.

The target is Alexandria's recomputed, simplified Allen-Dynes DFT Tc, not
experimental Tc. Predicted lambda/omega_log are the *only* component inputs to
the forecasting route. True test components are used solely in the separately
labelled algebraic oracle check and evaluation. No model is released here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import mechanism_features as MF
import pipeline as P

DESIGNS = {
    "R0": {"features": "D", "route": "direct", "name": "Storm1 fixed CPU direct Tc"},
    "R1": {"features": "D", "route": "components", "name": "Predicted lambda/omega_log to Allen-Dynes"},
    "R2": {"features": "D+geometry", "route": "direct", "name": "Geometry plus direct Tc"},
    "R3": {"features": "D+geometry", "route": "components", "name": "Geometry plus component route"},
    "R4": {"features": "D+PCA8(geometry)", "route": "components", "name": "Train-only geometry PCA8 plus component route"},
}
REFERENCE_SHA256 = {
    "storm_round4.json": "a735915e2818b48db8f2d92ff2d661ac3dbddd374dae57197cf16419de2809b4",
    "storm_round4_predictions.csv": "87d91d7fd6c887511e22c7f995a82cc249a5a60b488d3e05b7592baec3e45915",
    "storm_round5.json": "0e5a07abf25210dad18ad97cc8b1712db5a26facebf4954d5fd7f971cd957847",
    "storm_round5_ranges.csv": "d6836ebba0a533c075f5a92b7c861ae0639c00bc7ec2965a5bed4f76d07a33f1",
    "gnn_round2_final_predictions.csv": "b1de122cc4565b252745997522a1b2ed2228de1e1b69fb02a9427d84ff3b3296",
}
PARAMS = dict(P.STORM1_PARAMS)
SEED = 7
ALPHA = .10
CALIBRATION_FRACTION = .20
PCA_COMPONENTS = 8
BOOTSTRAPS = 1000
DATA_URL = "https://ndownloader.figshare.com/files/55551155"
SMOKE_PARAMS = dict(PARAMS, max_iter=12, max_leaf_nodes=7, min_samples_leaf=3)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _status(path, value):
    """Optional operational progress must not change a scientific fit/result."""
    try:
        _json(path, value)
    except OSError as error:
        warnings.warn(f"Storm6 optional progress write failed: {error}", RuntimeWarning)


def freeze_protocol(output_dir, *, smoke=False):
    """Persist the complete design before loading targets or fitting anything."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sources = {str(p.relative_to(P.ROOT)): _sha(p) for p in (
        Path(__file__), Path(P.__file__), Path(MF.__file__), P.EXPERIMENTS,
    ) if p.exists()}
    protocol = {
        "version": "storm6-frozen-cpu-ablation-v1", "adopted": False, "report_only": True,
        "smoke": bool(smoke), "source_sha256": sources, "reference_sha256": REFERENCE_SHA256,
        "expected_cohort": {"materials": 7582, "chemical_systems": 4288, "outer_folds": 5},
        "dataset": "alex_supercon; pipeline.to_frame/clean; original order, no extra filtering",
        "data_source": {"url": DATA_URL, "filename": "alex_supercon.json", "paper_doi": "10.1002/adfm.202404043",
                        "historical_structure_hash_unavailable": True},
        "target": "Recomputed simplified Allen-Dynes Tc (K), f1=f2=1, not measured Tc",
        "mu_star": .10, "omega_log_unit": "K", "lambda_unit": "dimensionless",
        "input_columns": {"D": "Unchanged Storm1 featurize + physics_features; no lambda/wlog/Tc inputs",
                          "geometry": list(MF.FEATURE_NAMES)},
        "geometry_version": MF.FEATURE_VERSION, "geometry_config": MF.GeometryConfig().__dict__,
        "designs": DESIGNS, "params": dict(SMOKE_PARAMS if smoke else PARAMS),
        "hyperparameter_selection": "None: all five fixed designs reported, no winner selected",
        "direct_target_transform": "log1p(Tc); expm1 and nonnegative clip",
        "component_target_transform": "Untransformed lambda and omega_log, as Storm1; lambda clip>=0, omega_log clip>=1K",
        "invalid_ad_denominator": "Existing pipeline.allen_dynes returns Tc=0 for denominator<=0; count explicitly",
        "outer_split": "Original sklearn GroupKFold(5), chemical system, no shuffled rows",
        "inner_split": {"kind": "GroupShuffleSplit(1)", "calibration_fraction": CALIBRATION_FRACTION,
                        "seed": "7 + outer zero-based index", "unit": "chemical system"},
        "preprocessing": "Fit separately on full outer train for point forecasts, and proper train for split intervals; never calibration/test. Drop columns entirely missing in the respective train subset; retain other NaNs for native HGB missing routing.",
        "geometry_pca": {"n_components": PCA_COMPONENTS, "imputation": "train median, all-missing=0",
                         "scaling": "train StandardScaler", "missingness": "19 indicators appended; PCA fitted only to imputed geometry"},
        "interval": {"level": .90, "score": "max absolute log1p residual per calibration chemical system",
                     "quantile": "ceil((G+1)*.9)-th group score; infinity if rank>G",
                     "center": "Separate proper-train-only head; never substituted with refitted full-outer forecast",
                     "coverage": "Report both material coverage and fraction of whole test systems simultaneously covered",
                     "limitation": "Group exchangeability is an assumption, not established by this fixed materials cohort"},
        "ood": {"features": "D only, shared across all designs", "imputation": "train median, all-missing=0",
                "scaling": "train StandardScaler", "distance": "Euclidean nearest training row; training reference distances exclude every row in the query's own chemical system",
                "threshold": "95th percentile of training nearest-different-chemical-system distances",
                "scope": "Point OOD uses outer train; interval OOD uses proper train; descriptive, not a probability"},
        "bootstrap": {"unit": "chemical system cluster", "repetitions": BOOTSTRAPS, "seed": SEED,
                      "quantity": "material-weighted delta MAE (new minus reference), percentile 95% interval"},
        "measured_diagnostics": "No map refit. Report uncalibrated matched-3DSC and graded-anchor errors separately; composition match is not phase/pressure match",
        "historical_limitations": ["These outer folds have already selected previous Storm/GNN models and are not a new blind test",
                                   "Saved GNN references used their validation folds for epoch selection",
                                   "Historical Storm5 widths use other-fold OOF residuals; no independent split-conformal guarantee is inferred",
                                   "The unchanged D reference contains n_sites, a/b/c/c_over_a and 27-cell nearest distances; although the new 19 geometry features pass equivalent-cell tests, complete R2/R3/R4 models are not guaranteed cell/basis invariant",
                                   "Geometry associations do not establish a superconducting mechanism"],
        "feedback": {"experimental_training_records": 0, "measured_negative_training_records": 0,
                     "policy": "No feedback or normal-state records alter the DFT targets"},
        "failures": "Reject altered/misaligned historical artifacts or cohort; retain failed designs explicitly; never fall back to GNN/MACE training",
        "seed": SEED,
    }
    encoded = (json.dumps(protocol, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if not smoke and (out / "protocol.json").exists() and (out / "protocol.json").read_bytes() != encoded:
        raise ValueError("Refusing to overwrite a different real-run frozen protocol")
    (out / "protocol.json").write_bytes(encoded)
    (out / "protocol.sha256").write_text(digest + "\n", encoding="utf-8")
    return protocol, digest


def run_identity():
    now = dt.datetime.now(dt.timezone.utc)
    identifier = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + str(time.time_ns())
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=P.ROOT, capture_output=True,
                                text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {"run_at": now.isoformat(), "run_id": identifier, "source_commit": commit,
            "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}


def _finite_or_nan(x):
    x = np.asarray(x, float).copy()
    x[~np.isfinite(x)] = np.nan
    return x


class TrainScale:
    """Train-fitted median/scale; a missing value is never inferred from test data."""
    def fit(self, X):
        from sklearn.preprocessing import StandardScaler
        X = _finite_or_nan(X)
        self.median = np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0. for c in X.T])
        self.scaler = StandardScaler().fit(np.where(np.isfinite(X), X, self.median))
        return self

    def transform(self, X):
        X = _finite_or_nan(X)
        return self.scaler.transform(np.where(np.isfinite(X), X, self.median))


class FeatureMap:
    def __init__(self, design):
        self.design = design

    def fit(self, D, geometry):
        if self.design == "R4":
            from sklearn.decomposition import PCA
            self.scale = TrainScale().fit(geometry)
            if min(geometry.shape) < PCA_COMPONENTS:
                raise ValueError("R4 requires at least 8 training rows and geometry columns")
            self.pca = PCA(n_components=PCA_COMPONENTS, svd_solver="full").fit(self.scale.transform(geometry))
        self.keep = np.isfinite(self._unfiltered(D, geometry)).any(axis=0)
        if not self.keep.any():
            raise ValueError("No observed training feature columns")
        return self

    def _unfiltered(self, D, geometry):
        D, geometry = _finite_or_nan(D), _finite_or_nan(geometry)
        if self.design in ("R0", "R1"):
            return D
        if self.design == "R4":
            return np.column_stack([D, self.pca.transform(self.scale.transform(geometry)), ~np.isfinite(geometry)])
        return np.column_stack([D, geometry])

    def transform(self, D, geometry):
        return self._unfiltered(D, geometry)[:, self.keep]


def forecast(design, Dtr, Gtr, targets_tr, Dte, Gte, *, seed, params):
    """The fit/predict boundary receives training targets only, never test answers."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    fmap = FeatureMap(design).fit(Dtr, Gtr)
    Xtr, Xte = fmap.transform(Dtr, Gtr), fmap.transform(Dte, Gte)
    result = {}
    if DESIGNS[design]["route"] == "direct":
        m = HistGradientBoostingRegressor(random_state=seed, **params)
        result["tc"] = np.clip(np.expm1(m.fit(Xtr, np.log1p(targets_tr["tc"])).predict(Xte)), 0, None)
    else:
        for name, lower in (("lambda", 0.), ("wlog", 1.)):
            m = HistGradientBoostingRegressor(random_state=seed, **params)
            result[name] = np.clip(m.fit(Xtr, targets_tr[name]).predict(Xte), lower, None)
        result["tc"] = P.allen_dynes(result["lambda"], result["wlog"], mu=.10)
    if any(not np.isfinite(a).all() for a in result.values()):
        raise ValueError("Non-finite model forecast")
    return result


def calibration_indices(train, groups, fold):
    from sklearn.model_selection import GroupShuffleSplit
    train = np.asarray(train, int)
    a, b = next(GroupShuffleSplit(n_splits=1, test_size=CALIBRATION_FRACTION,
                                random_state=SEED + fold).split(train, groups=groups[train]))
    fit, cal = train[a], train[b]
    if set(groups[fit]) & set(groups[cal]):
        raise AssertionError("Calibration chemical systems overlap proper train")
    return fit, cal


def group_quantile(scores, groups, *, alpha=ALPHA):
    scores, groups = np.asarray(scores, float), np.asarray(groups)
    if not len(scores) or not np.isfinite(scores).all():
        raise ValueError("Finite, nonempty calibration residuals required")
    maxima = np.array([scores[groups == g].max() for g in np.unique(groups)])
    rank = int(np.ceil((len(maxima) + 1) * (1 - alpha)))
    return float(np.sort(maxima)[rank - 1]) if rank <= len(maxima) else float("inf")


def split_ranges(ycal, pcal, groups_cal, center):
    q = group_quantile(np.abs(np.log1p(ycal) - np.log1p(pcal)), groups_cal)
    if not np.isfinite(q):
        # Infinity is mathematically required with too few groups, not a finite interval success.
        return np.zeros(len(center)), np.full(len(center), np.inf), None
    z = np.log1p(center)
    return np.clip(np.expm1(z - q), 0, None), np.expm1(z + q), q


def ood_distance(Dtr, Dte, groups_tr):
    from sklearn.neighbors import NearestNeighbors
    groups_tr = np.asarray(groups_tr)
    if len(Dtr) != len(groups_tr) or len(np.unique(groups_tr)) < 2:
        raise ValueError("OOD requires aligned rows and at least two training chemical systems")
    scale = TrainScale().fit(Dtr)
    A, B = scale.transform(Dtr), scale.transform(Dte)
    nn = NearestNeighbors(algorithm="brute", n_jobs=2).fit(A)
    # Usually k=8 suffices. Expand only unresolved queries; same-system
    # polymorphs and self neighbors must not set the reference threshold.
    nearest_other = np.full(len(A), np.inf)
    unresolved = np.arange(len(A))
    k = min(8, len(A))
    while len(unresolved):
        distances, indices = nn.kneighbors(A[unresolved], n_neighbors=k, return_distance=True)
        other = groups_tr[indices] != groups_tr[unresolved, None]
        found = other.any(axis=1)
        nearest_other[unresolved[found]] = distances[found, other[found].argmax(axis=1)]
        unresolved = unresolved[~found]
        if not len(unresolved):
            break
        if k == len(A):
            raise ValueError("No different-system neighbor for OOD reference")
        k = min(2 * k, len(A))
    threshold = float(np.quantile(nearest_other, .95))
    distance = nn.kneighbors(B, n_neighbors=1, return_distance=True)[0][:, 0]
    return distance, distance > threshold, threshold


def evaluate_fold(D, geometry, targets, groups, train, test, design, fold, *, params):
    """Fit all point/interval preprocessing within its own appropriate training subset."""
    train, test = np.asarray(train, int), np.asarray(test, int)
    if set(groups[train]) & set(groups[test]):
        raise ValueError("Outer test chemical systems overlap training")
    proper, cal = calibration_indices(train, groups, fold)
    subset = lambda indices: {k: np.asarray(v)[indices] for k, v in targets.items()}
    point = forecast(design, D[train], geometry[train], subset(train), D[test], geometry[test],
                     seed=SEED + fold, params=params)
    both = np.concatenate([cal, test])
    split = forecast(design, D[proper], geometry[proper], subset(proper), D[both], geometry[both],
                     seed=SEED + fold, params=params)
    lo, hi, q = split_ranges(targets["tc"][cal], split["tc"][:len(cal)], groups[cal], split["tc"][len(cal):])
    return {"point": point, "interval_center": split["tc"][len(cal):], "lo": lo, "hi": hi, "q": q,
            "proper": proper, "calibration": cal}


def point_metrics(y, pred, groups, fold_of, *, tail_mask, ood=None):
    from sklearn.metrics import r2_score
    error = np.abs(y - pred)
    out = {"n": len(y), "mae_k": float(error.mean()), "rmse_k": float(np.sqrt(np.mean((y - pred) ** 2))),
           "r2": float(r2_score(y, pred)), "median_absolute_error_k": float(np.median(error)),
           "within_1k_fraction": float(np.mean(error <= 1)), "within_2k_fraction": float(np.mean(error <= 2)),
           "fold_mae_k": [float(error[fold_of == k].mean()) for k in np.unique(fold_of)],
           "tail_n": int(tail_mask.sum()), "tail_mae_k": float(error[tail_mask].mean()) if tail_mask.any() else None,
           "chemical_systems": int(len(np.unique(groups)))}
    if ood is not None:
        for name, mask in (("ood", ood), ("within_training_distance", ~ood)):
            out[name] = {"n": int(mask.sum()), "mae_k": float(error[mask].mean()) if mask.any() else None}
    return out


def interval_metrics(y, lo, hi, groups, tail_mask, ood):
    inside = (y >= lo) & (y <= hi)
    finite = np.isfinite(lo) & np.isfinite(hi)
    result = {"row_coverage": float(inside.mean()),
              "group_simultaneous_coverage": float(np.mean([inside[groups == g].all() for g in np.unique(groups)])),
              "tail_coverage": float(inside[tail_mask].mean()) if tail_mask.any() else None,
              "finite_interval_rows": int(finite.sum()), "unbounded_interval_rows": int((~finite).sum()),
              "mean_width_k": None, "median_width_k": None, "interval_score_k": None}
    if finite.all():
        width = hi - lo
        score = width + 2 / ALPHA * (np.clip(lo - y, 0, None) + np.clip(y - hi, 0, None))
        result.update(mean_width_k=float(width.mean()), median_width_k=float(np.median(width)), interval_score_k=float(score.mean()))
    for name, mask in (("ood", ood), ("within_training_distance", ~ood)):
        result[name] = {"n": int(mask.sum()), "row_coverage": float(inside[mask].mean()) if mask.any() else None}
    return result


def paired_bootstrap(y, pred, reference, groups, *, repetitions=BOOTSTRAPS):
    """Cluster resampling preserves every row of a sampled chemical system."""
    _, inverse = np.unique(groups, return_inverse=True)
    counts = np.bincount(inverse)
    sums = np.bincount(inverse, weights=np.abs(y - pred) - np.abs(y - reference))
    rng = np.random.default_rng(SEED)
    samples = rng.integers(0, len(counts), (repetitions, len(counts)))
    values = sums[samples].sum(axis=1) / counts[samples].sum(axis=1)
    return {"delta_mae_k_new_minus_reference": float(sums.sum() / counts.sum()),
            "percentile_95_interval_k": np.quantile(values, [.025, .975]).tolist(),
            "repetitions": repetitions, "unit": "chemical-system cluster", "selection_adjusted": False}


def load_references(train, fold_of, directory=None):
    """Historical references are immutable; do not silently retrain a network."""
    directory = Path(directory or P.RESULTS)
    for name, expected in REFERENCE_SHA256.items():
        path = directory / name
        if not path.is_file() or _sha(path) != expected:
            raise ValueError(f"Historical reference missing or changed: {name}")
    r4 = json.loads((directory / "storm_round4.json").read_text(encoding="utf-8"))
    r5 = json.loads((directory / "storm_round5.json").read_text(encoding="utf-8"))
    if not (r4["adopted"] and r4["best"] == "S3" and r5["adopted"] and r5["best"] == "U2"):
        raise ValueError("Historical Storm4/5 reference design differs from frozen protocol")
    ids = train["id"].astype(str).tolist()
    aligned = {}
    for key, name in (("storm4", "storm_round4_predictions.csv"), ("storm5", "storm_round5_ranges.csv"),
                      ("gnn", "gnn_round2_final_predictions.csv")):
        frame = pd.read_csv(directory / name, dtype={"id": str})
        if frame["id"].duplicated().any() or set(frame["id"]) != set(ids) or len(frame) != len(ids):
            raise ValueError(f"Historical {key} IDs are not the exact cohort")
        frame = frame.set_index("id").loc[ids].reset_index()
        if not np.array_equal(frame["chemsys"].to_numpy(), train["chemsys"].to_numpy()):
            raise ValueError(f"Historical {key} chemical systems differ")
        if "fold" in frame and not np.array_equal(frame["fold"].to_numpy(), fold_of):
            raise ValueError(f"Historical {key} folds differ")
        if not np.allclose(frame["tc"].to_numpy(), train["tc"].to_numpy(), atol=6e-6, rtol=0):
            raise ValueError(f"Historical {key} target labels differ")
        numeric = frame.select_dtypes(include=[np.number]).to_numpy()
        if not np.isfinite(numeric).all():
            raise ValueError(f"Historical {key} contains non-finite values")
        aligned[key] = frame
    if not np.allclose(aligned["storm4"]["tc_pred_best"], aligned["storm5"]["tc_pred"], atol=1.1e-5, rtol=0):
        raise ValueError("Storm5 point center differs from Storm4")
    return aligned, {"storm4": r4, "storm5": r5}


def geometry_features(train, cache_dir):
    values, diagnostics = [], []
    for k, (identifier, atoms) in enumerate(zip(train["id"], train["atoms"])):
        row = MF.extract_features(atoms, cache_dir=cache_dir)
        if row["names"] != list(MF.FEATURE_NAMES):
            raise ValueError("Geometry feature order differs from frozen protocol")
        values.append(row["values"])
        diagnostics.append({"id": str(identifier), **row["diagnostics"]})
        if (k + 1) % 250 == 0:
            P.log(f"Storm6 geometry {k + 1}/{len(train)} (label-free, no MACE)")
    return _finite_or_nan(values), diagnostics


def synthetic_data():
    rng = np.random.default_rng(SEED)
    groups = np.repeat([f"synthetic-system-{k:03}" for k in range(100)], 2)
    D = rng.normal(size=(len(groups), 8))
    lam = .5 + .12 * np.tanh(D[:, 0])
    wlog = 180 + 25 * D[:, 1]
    atoms = [{"lattice_mat": (np.eye(3) * (2.8 + .2 * np.tanh(x))).tolist(),
              "coords": [[0., 0., 0.]], "elements": ["Cu"], "cartesian": False} for x in D[:, 2]]
    frame = pd.DataFrame({"id": [f"synthetic-{i}" for i in range(len(groups))], "chemsys": groups,
                          "lambda": lam, "wlog": wlog, "tc": P.allen_dynes(lam, wlog), "atoms": atoms})
    geometry, diagnostics = geometry_features(frame, None)
    return frame, D, geometry, diagnostics, None


def prepare_real():
    from jarvis.db.figshare import get_db_info
    if get_db_info()["alex_supercon"][0] != DATA_URL:
        raise ValueError("Alexandria registry URL differs from frozen data source")
    raw = P.load_dataset("alex_supercon")  # No JARVIS locked test is opened.
    frame, fields = P.to_frame(raw, "alexandria")
    frame, counts = P.clean(frame)
    if len(frame) != 7582 or frame["id"].duplicated().any() or frame["chemsys"].nunique() != 4288:
        raise ValueError("Alexandria cohort differs from frozen 7582 IDs / 4288 systems")
    table = P.element_table(sorted({e for els in frame["elements"] for e in els}))
    base = P.featurize(frame, table)
    phys = P.physics_features(frame, base)
    D = np.column_stack([base.to_numpy(float), phys.to_numpy(float)])
    geometry, diagnostics = geometry_features(frame, P.CACHE / "storm6-geometry")
    manifest = {"fields": fields, "clean_counts": counts, "D_columns": list(base) + list(phys),
                "id_order_sha256": hashlib.sha256("\n".join(frame["id"].astype(str)).encode()).hexdigest(),
                "all_missing_D_columns": [n for n, c in zip(list(base) + list(phys), D.T) if not np.isfinite(c).any()],
                "structure_target_sha256": hashlib.sha256(frame[["id", "atoms", "lambda", "wlog", "tc"]].to_json(orient="records", double_precision=15).encode()).hexdigest()}
    return frame, D, geometry, diagnostics, (phys, manifest)


def measured_diagnostics(frame, phys, predictions):
    """Descriptive composition matches only. No fitted experimental map or gate."""
    import storm3 as S3
    out = {"used_for_selection": False, "map_refitted": False,
           "limitations": ["Composition matching pools polymorphs and does not verify phase, pressure, field or sample form",
                           "Existing folds/literature have already been examined; this is not prospective validation"],
           "graded_anchors": P.experimental_check(frame, predictions, list(predictions)), "matched_3dsc": {}}
    if out["graded_anchors"]:
        out["graded_anchors"]["summary"]["rule"] = "Descriptive only; not an adoption criterion in Storm6"
    for design, pred in predictions.items():
        # Dummy components are unused for this uncalibrated Tc diagnostic. Never pass true DFT components as model inputs.
        matched = S3.matched_set(frame, phys, pred, np.zeros(len(frame)), np.ones(len(frame)))
        out["matched_3dsc"][design] = {"n": len(matched), "n_sc": int((matched["tc_exp"] > 0).sum()),
                                            "uncalibrated_mae_k": float(np.mean(np.abs(matched["tc_exp"] - matched["storm"]))) if len(matched) else None,
                                            "dft_label_mae_k": float(np.mean(np.abs(matched["tc_exp"] - matched["dft_tc"]))) if len(matched) else None}
    return out


def run(smoke=False, output_dir=None):
    import sklearn
    from sklearn.model_selection import GroupKFold
    started = time.time()
    identity = run_identity()
    out = Path(output_dir) if output_dir is not None else P.RESULTS / "storm6" / identity["run_id"]
    protocol, digest = freeze_protocol(out, smoke=smoke)
    _json(out / "run.json", {**identity, "protocol_sha256": digest, "output_dir": str(out)})
    frame, D, geometry, diagnostics, extra = synthetic_data() if smoke else prepare_real()
    groups = frame["chemsys"].to_numpy()
    targets = {k: frame[k].to_numpy(float) for k in ("tc", "lambda", "wlog")}
    y = targets["tc"]
    splits = list(GroupKFold(n_splits=5).split(D, y, groups))
    fold_of = np.zeros(len(frame), int)
    for fold, (_, test) in enumerate(splits):
        fold_of[test] = fold + 1
    references, historical = ({}, {}) if smoke else load_references(frame, fold_of)
    _json(out / "geometry-diagnostics.json", diagnostics)
    _json(out / "input-manifest.json", {"n": len(frame), "chemical_systems": len(np.unique(groups)),
                                         "geometry_missing_fraction": np.mean(~np.isfinite(geometry), axis=0).tolist(),
                                         "details": extra[1] if extra else {"synthetic": True}})
    tail = y >= np.quantile(y, .9)
    point_ood, split_ood = np.zeros(len(y), bool), np.zeros(len(y), bool)
    point_distance, split_distance = np.zeros(len(y)), np.zeros(len(y))
    fold_manifest = []
    for fold, (train, test) in enumerate(splits):
        proper, cal = calibration_indices(train, groups, fold)
        point_distance[test], point_ood[test], q1 = ood_distance(D[train], D[test], groups[train])
        split_distance[test], split_ood[test], q2 = ood_distance(D[proper], D[test], groups[proper])
        fold_manifest.append({"fold": fold + 1, "outer_train_systems": sorted(set(groups[train])),
                              "proper_train_systems": sorted(set(groups[proper])), "calibration_systems": sorted(set(groups[cal])),
                              "test_systems": sorted(set(groups[test])), "ood_threshold_full_train": q1,
                              "ood_threshold_proper_train": q2, "n_train": len(train), "n_proper": len(proper),
                              "n_calibration": len(cal), "n_test": len(test)})
    _json(out / "folds.json", fold_manifest)
    report = {**identity, "output_dir": str(out), "version": protocol["version"], "protocol_sha256": digest, "adopted": False, "report_only": True,
              "smoke": bool(smoke), "status": "running", "target": protocol["target"],
              "cohort": {"n": len(frame), "chemical_systems": len(np.unique(groups)), "tail_threshold_k": float(np.quantile(y, .9))},
              "oracle_formula_check": {"forecast": False, "inputs": "true test lambda/omega_log; algebraic consistency only",
                                       "max_absolute_error_k": float(np.max(np.abs(P.allen_dynes(targets["lambda"], targets["wlog"], mu=.10) - y)))},
              "designs": {d: {"status": "pending", "name": c["name"]} for d, c in DESIGNS.items()},
              "references": {}, "historical_measured": {}, "limitations": protocol["historical_limitations"],
              "feedback_training_records": 0, "measured_negative_training_records": 0,
              "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__}}
    if references:
        for name, col in (("Storm1_saved", "tc_pred_storm1"), ("Storm4_saved", "tc_pred_best")):
            report["references"][name] = point_metrics(y, references["storm4"][col].to_numpy(), groups, fold_of, tail_mask=tail, ood=point_ood)
        r = references["storm5"]
        report["references"]["Storm5_saved_intervals"] = interval_metrics(y, r["tc_lo"].to_numpy(), r["tc_hi"].to_numpy(), groups, tail, point_ood)
        report["historical_measured"] = {"matched_3dsc_calibration": historical["storm4"]["calibration"],
                                         "graded_anchor_summary": historical["storm4"]["experiments"]["summary"],
                                         "different_denominators_do_not_pool": True,
                                         "new_calibration_fitted": False}
    rows, all_predictions = [], {}
    params = SMOKE_PARAMS if smoke else PARAMS
    _json(out / "report.json", report)
    for design in DESIGNS:
        predictions = {k: np.full(len(y), np.nan) for k in ("tc", "lambda", "wlog", "center", "lo", "hi")}
        entry = {"status": "running", "name": DESIGNS[design]["name"], "folds": []}
        report["designs"][design] = entry
        try:
            for fold, (train, test) in enumerate(splits):
                result = evaluate_fold(D, geometry, targets, groups, train, test, design, fold, params=params)
                for key, values in result["point"].items():
                    predictions[key][test] = values
                for key, source in (("center", "interval_center"), ("lo", "lo"), ("hi", "hi")):
                    predictions[key][test] = result[source]
                entry["folds"].append({"fold": fold + 1, "calibration_log_groupmax_quantile": result["q"],
                                       "interval_status": "finite" if result["q"] is not None else "unbounded_too_few_calibration_systems"})
                P.log(f"Storm6 {design} fold {fold + 1}/5 complete ({time.time() - started:.1f}s)")
                _status(out / "status.json", {"design": design, "fold": fold + 1, "status": "running", "protocol_sha256": digest})
            entry.update(status="completed", point=point_metrics(y, predictions["tc"], groups, fold_of, tail_mask=tail, ood=point_ood),
                         split_center=point_metrics(y, predictions["center"], groups, fold_of, tail_mask=tail, ood=split_ood),
                         intervals=interval_metrics(y, predictions["lo"], predictions["hi"], groups, tail, split_ood))
            if DESIGNS[design]["route"] == "components":
                entry["components"] = {key: {"mae": float(np.mean(np.abs(targets[key] - predictions[key]))),
                                             "rmse": float(np.sqrt(np.mean((targets[key] - predictions[key]) ** 2))),
                                             "unit": "K" if key == "wlog" else "dimensionless"} for key in ("lambda", "wlog")}
                denominator = predictions["lambda"] - .10 * (1 + .62 * predictions["lambda"])
                entry["ad_nonpositive_denominator_rows"] = int(np.sum(denominator <= 0))
                entry["ad_zero_tc_rows"] = int(np.sum(predictions["tc"] == 0))
            if references:
                for ref, col in (("Storm1_saved", "tc_pred_storm1"), ("Storm4_saved", "tc_pred_best")):
                    entry.setdefault("paired_bootstrap", {})[ref] = paired_bootstrap(y, predictions["tc"], references["storm4"][col].to_numpy(), groups)
            all_predictions[design] = predictions["tc"]
            for i in range(len(y)):
                rows.append({"id": str(frame["id"].iloc[i]), "chemsys": str(groups[i]), "fold": int(fold_of[i]), "design": design,
                             "tc_target_dft_k": float(y[i]), "lambda_target": float(targets["lambda"][i]), "wlog_target_k": float(targets["wlog"][i]),
                             "tc_pred_full_outer_k": float(predictions["tc"][i]),
                             "lambda_pred": float(predictions["lambda"][i]) if np.isfinite(predictions["lambda"][i]) else None,
                             "wlog_pred_k": float(predictions["wlog"][i]) if np.isfinite(predictions["wlog"][i]) else None,
                             "tc_interval_center_proper_train_k": float(predictions["center"][i]), "tc_lo_k": float(predictions["lo"][i]),
                             "tc_hi_k": float(predictions["hi"][i]) if np.isfinite(predictions["hi"][i]) else None,
                             "interval_unbounded": bool(not np.isfinite(predictions["hi"][i])),
                             "ood_full_outer": bool(point_ood[i]), "distance_full_outer": float(point_distance[i]),
                             "ood_proper_train": bool(split_ood[i]), "distance_proper_train": float(split_distance[i])})
        except (ValueError, RuntimeError, FloatingPointError) as error:
            entry.update(status="failed", reason=f"{type(error).__name__}: {error}")
        _json(out / "report.json", report)
        pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False)
    if not smoke and all_predictions:
        if references:
            all_predictions["Storm4_saved"] = references["storm4"]["tc_pred_best"].to_numpy()
        try:
            report["measured_diagnostics"] = measured_diagnostics(frame, extra[0], all_predictions)
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            report["measured_diagnostics"] = {"status": "unavailable", "reason": f"{type(error).__name__}: {error}", "map_refitted": False}
    report["status"] = "completed" if all(e["status"] == "completed" for e in report["designs"].values()) else "incomplete"
    report["seconds"] = round(time.time() - started, 3)
    _json(out / "report.json", report)
    _status(out / "status.json", {"status": report["status"], "protocol_sha256": digest})
    if report["status"] != "completed":
        raise RuntimeError(f"Storm6 incomplete: see {out / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Synthetic, offline protocol/interface check; not a scientific result")
    parser.add_argument("--protocol", action="store_true", help="Freeze design and source hashes only; do not load targets or train")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.protocol:
        out = args.output_dir or P.RESULTS / "storm6" / run_identity()["run_id"]
        _, digest = freeze_protocol(out, smoke=args.smoke)
        P.log(f"Storm6 protocol frozen: {digest}")
    else:
        result = run(smoke=args.smoke, output_dir=args.output_dir)
        P.log(f"Storm6 {result['status']}; report only, adopted=false: {result['output_dir']}")


if __name__ == "__main__":
    main()
