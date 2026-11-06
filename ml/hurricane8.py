"""Exploratory, train-only unsupervised prototypes for Hurricane P/U ranking.

Unlabeled parents are not measured negatives. A catalog ranking is not p(SC).
No held-family features, labels, or chemical systems enter representation fitting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

import hurricane7 as H7
import unsupervised as UP

DESIGNS = ("U0", "U1")
SNAPSHOT_SHA256 = "5932496e18c8a12dcd184191139b29d1afcaa8f42e241af3e178d2eece304530"
PROTOCOL = {
    "version": "hurricane8-train-only-unsupervised-prototypes-v1",
    "adopted": False, "report_only": True,
    "target": H7.PROTOCOL["target"],
    "label_semantics": H7.PROTOCOL["label_semantics"],
    "cohort": H7.PROTOCOL["cohort"],
    "mixed_family_exclusions": H7.MIXED_FAMILIES,
    "families": H7.PROTOCOL["families"],
    "designs": {"U0": "Exact H7 R0 main-effect pairwise Ridge baseline",
                "U1": "Same main effects and Ridge head plus16 train-only KMeans RBF prototype similarities"},
    "inputs": list(H7.MF.FEATURE_NAMES) + list(H7.EXTRA_NAMES),
    "representation": {"input": "Unlabeled physical X of corresponding training parents only, restricted to the identical main-effect columns eligible in H7 R0; not P/U labels",
        "k": 16, "seed": 7, "n_init": 10,
        "preprocessing": "Training median imputation, training mean/std, remove all-missing/constant columns, z clip at5; no missing indicators",
        "feature": "exp(-squared Euclidean distance / (2 sigma^2)) to each train-only prototype",
        "sigma": "Median strictly positive training distance to nearest prototype;1 scaled-unit fallback if all distances zero",
        "degenerate": "Only distinct informative training vectors fit active prototypes; pad to16 with explicit inactive zero columns; all-constant or all-missing yields no active prototype",
        "background": "None: no held-family, test, calibration, auxiliary JARVIS or external foundation-model rows",
        "interpretation": "Unsupervised material similarity; cluster membership does not establish mechanism or superconductivity"},
    "outer": H7.PROTOCOL["outer"],
    "inner_system_folds": H7.PROTOCOL["inner_system_folds"],
    "alpha_grid": H7.PROTOCOL["alpha_grid"],
    "alpha_tie_auc_tolerance": H7.PROTOCOL["alpha_tie_auc_tolerance"],
    "inner_objective": H7.PROTOCOL["inner_objective"],
    "head": "H7 R0 Ridge with the identical pair generation, family/system weights, normalization, alpha grid and seed",
    "pairs": H7.PROTOCOL["pairs"],
    "main_preprocessing": H7.PROTOCOL["preprocessing"],
    "prototype_head_scale": "H7 train-only linear TermBasis scale applied to baseline main-effect columns and prototype similarities; no interaction terms",
    "metrics": ["Equal-family observed-P/U AUC", "Equal-family recall at20% ranking budget with fractional ties"],
    "cross_family_score_pooling": False,
    "paired_bootstrap": {"repetitions": 1000, "seed": 7, "unit": "chemical-system clusters across all held families",
        "quantities": ["macro observed-P/U AUC U1-U0", "macro recall at20% budget U1-U0"],
        "conditioning": "Fixed exploratory predictions; does not undo previous inspection or model selection"},
    "optional_snapshot": {"source": "H7 CI66 input-parents.csv, same frozen615-parent cohort",
        "sha256": SNAPSHOT_SHA256, "hash_rule": "Exact original bytes; no parsing before checksum validation"},
    "source_data_sha256": H7.PROTOCOL["source_sha256"],
    "failure_semantics": "Any failed fold remains explicit; incomplete designs have null macro and unavailable paired comparison",
    "publication": "All designs reported; no automatic winner selection or model release. Families were inspected previously; not a new blind test.",
    "feedback_records": 0, "precursor_training_records": 0,
    "seed": 7,
}


def code_manifest():
    files = [Path(__file__), Path(UP.__file__), Path(H7.__file__)]
    previous = H7.code_manifest()["source_sha256"]
    for p in files:
        previous[p.relative_to(H7.P.ROOT).as_posix()] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return previous


def freeze_protocol(output_dir):
    declaration = {**PROTOCOL, "source_code_sha256": code_manifest(),
                   "inherited_h7_protocol_sha256": H7.digest(H7.protocol())}
    encoded = (json.dumps(declaration, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "protocol.json"
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("Refusing to overwrite a different frozen H8 protocol")
    path.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    (out / "protocol.sha256").write_text(digest + "\n", encoding="utf-8")
    return declaration, digest


def load_snapshot(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SNAPSHOT_SHA256:
        raise ValueError("Not the frozen H7 feature/parent snapshot")
    frame = pd.read_csv(path, float_precision="round_trip")
    parents = frame[["material_id", "family", "system", "n_entries"]].copy()
    parents["tc"] = frame["observed_positive"].map({True: 1., False: 0.})
    parents["full_family_membership"] = frame["full_family_membership"].map(json.loads)
    return {"parents": parents, "geometry": frame[list(H7.MF.FEATURE_NAMES)].to_numpy(float),
            "extras": frame[list(H7.EXTRA_NAMES)].to_numpy(float),
            "provenance": {"source_sha256": PROTOCOL["source_data_sha256"],
                "snapshot_input_sha256": SNAPSHOT_SHA256, "snapshot_origin": "H7 CI66 original per-parent physical input",
                "auxiliary_background_rows": 0, "background_used_as_negative": False}}


class PrototypeFeatures:
    def fit(self, geometry, extras):
        self.main = H7.FeatureBasis("R0").fit(geometry, extras)
        # Labels and family identities are deliberately absent from this API.
        self.prototype_columns = self.main.scale.keep.copy()
        self.prototype = UP.TrainOnlyPrototypes(n_clusters=16, seed=7).fit(
            np.column_stack([geometry, extras])[:, self.prototype_columns])
        self.names = self.main.names + [f"material_prototype_RBF{i+1}" for i in range(16)]
        self.training_rows = len(geometry)
        return self

    def transform(self, geometry, extras):
        return np.column_stack([self.main.transform(geometry, extras),
                                self.prototype.transform(np.column_stack([geometry, extras])[:, self.prototype_columns])])


class PrototypeRanker:
    def __init__(self, alpha, seed):
        self.alpha, self.seed = alpha, seed

    def fit(self, geometry, extras, positive, families, systems):
        self.features = PrototypeFeatures().fit(geometry, extras)
        base = self.features.transform(geometry, extras)
        self.terms = H7.TermBasis().fit(base, self.features.names, nonlinear=False)
        matrix = self.terms.transform(base)
        self.coefficient, self.fit_info = H7.fit_head(matrix, positive, families, systems,
            design="R0", alpha=self.alpha, seed=self.seed)
        self.training_systems = sorted(set(map(str, systems)))
        return self

    def predict(self, geometry, extras):
        return self.terms.transform(self.features.transform(geometry, extras)) @ self.coefficient

    def identity(self):
        return {"design": "U1", "alpha": self.alpha, **self.fit_info,
            "training_systems": self.training_systems, "main_features": self.features.main.names,
            "main_scale": H7.scale_identity(self.features.main.scale),
            "prototype_input_columns_in_original_matrix": np.flatnonzero(self.features.prototype_columns).tolist(),
            "prototype": self.features.prototype.identity(),
            "head_scale": H7.scale_identity(self.terms.scale),
            "head_features": self.terms.names, "coefficients": self.coefficient.tolist()}


def fit_split(data, design, alpha, train, held_systems, *, seed):
    parents = data["parents"]
    systems = parents.iloc[train]["system"].astype(str).to_numpy()
    if set(systems) & set(held_systems):
        raise ValueError("Held chemical system reached representation/head fitting")
    if design not in DESIGNS:
        raise ValueError("Unknown frozen design")
    fitted = H7.Ranker("R0", alpha, seed) if design == "U0" else PrototypeRanker(alpha, seed)
    return fitted.fit(data["geometry"][train], data["extras"][train],
        parents.iloc[train]["tc"].to_numpy(float) > 0,
        parents.iloc[train]["family"].to_numpy(), systems)


def select_alpha(data, design, train, outer_held):
    from sklearn.model_selection import GroupKFold
    parents, records = data["parents"], []
    groups = parents.iloc[train]["system"].to_numpy()
    expected = sorted(set(parents.iloc[train]["family"]))
    # Representation fitting is independent of alpha and labels; reuse it only
    # for identical training rows via fresh complete fits for clarity/audit.
    for alpha in PROTOCOL["alpha_grid"]:
        folds = []
        for fold, (a, b) in enumerate(GroupKFold(PROTOCOL["inner_system_folds"]).split(train, groups=groups)):
            tr, val = train[a], train[b]
            held = set(outer_held) | set(parents.iloc[val]["system"])
            fitted = fit_split(data, design, alpha, tr, held, seed=PROTOCOL["seed"] + fold)
            scores = fitted.predict(data["geometry"][val], data["extras"][val])
            folds.append({"fold": fold, "training_ids": parents.iloc[tr]["material_id"].astype(str).tolist(),
                "validation_ids": parents.iloc[val]["material_id"].astype(str).tolist(),
                "training_systems": fitted.training_systems, "validation_systems": sorted(set(parents.iloc[val]["system"])),
                "representation_fit_rows": len(tr), "auxiliary_rows": 0,
                "family_metrics": H7.validation_family_metrics(parents.iloc[val], scores, expected),
                "status": fitted.fit_info["status"],
                "prototype_identity": fitted.features.prototype.identity() if design == "U1" else None})
        objective = H7.inner_objective(folds, expected)
        records.append({"alpha": alpha, "mean_observed_pu_auc": objective["macro"],
            "family_mean_fold_auc": objective["families"], "objective_status": objective["status"], "folds": folds})
    valid = [r for r in records if r["mean_observed_pu_auc"] is not None and all(f["status"] != "not_converged" for f in r["folds"])]
    if not valid:
        raise ValueError("No valid inner ranking comparison; no held-family selection allowed")
    best = max(r["mean_observed_pu_auc"] for r in valid)
    chosen = max(r["alpha"] for r in valid if r["mean_observed_pu_auc"] >= best - PROTOCOL["alpha_tie_auc_tolerance"])
    return chosen, records


def paired_intervals(parents, predictions, *, resamples):
    # Reuse the frozen H7 system-cluster resampling and per-family metrics.
    # Alias names only at the evaluator boundary; no historical state changes.
    mapped = {r: predictions[u] for r, u in [("R0", "U0"), ("R1", "U1")] if u in predictions}
    return {"U1-U0": H7.paired_intervals(parents, mapped, resamples=resamples)["R1-R0"]}


def run(*, smoke=False, output_dir=None, input_csv=None):
    started = time.perf_counter()
    identity = H7.run_identity()
    out = Path(output_dir) if output_dir else H7.P.RESULTS / "hurricane8" / identity["run_id"]
    if (out / "report.json").exists():
        raise ValueError("H8 run directory is non-overwriting; use a new directory")
    protocol, fingerprint = freeze_protocol(out)  # Before loading labels or fitting.
    report = {**identity, "version": PROTOCOL["version"], "adopted": False, "report_only": True,
        "smoke": smoke, "protocol_sha256": fingerprint, "protocol": protocol,
        "status": "preparing", "designs": {}, "failures": [], "actual_precursor_training_records": 0,
        "actual_feedback_training_records": 0}
    H7._write_json(out / "report.json", report)
    try:
        if smoke and input_csv:
            raise ValueError("Synthetic smoke cannot load a real input snapshot")
        data = H7.prepare_smoke() if smoke else load_snapshot(input_csv) if input_csv else H7.prepare_real()
        parents, geometry, extras = H7.validate_data(data, smoke=smoke)
        data.update(geometry=geometry, extras=extras)
    except Exception as error:
        report.update(status="failed_preparation", failures=[{"reason": f"{type(error).__name__}: {error}"}])
        H7._write_json(out / "report.json", report)
        raise
    metadata = [{"material_id": str(r["material_id"]), "family": str(r["family"]), "system": str(r["system"]),
        "observed_positive": bool(r["tc"] > 0), "n_entries": int(r["n_entries"]),
        "full_family_membership": r["full_family_membership"]} for _, r in parents.iterrows()]
    input_frame = pd.concat([pd.DataFrame(metadata), pd.DataFrame(np.column_stack([geometry, extras]),
        columns=PROTOCOL["inputs"])], axis=1)
    input_frame.to_csv(out / "input-parents.csv", index=False, float_format="%.17g")
    H7._write_json(out / "input-manifest.json", {"source_sha256": PROTOCOL["source_data_sha256"],
        "input_csv_sha256": hashlib.sha256((out / "input-parents.csv").read_bytes()).hexdigest(),
        "provenance": data["provenance"], "auxiliary_rows": 0})
    report["cohort"] = {"parents": len(parents), "positive": int((parents.tc > 0).sum()), "unlabeled": int((parents.tc == 0).sum())}
    predictions = {design: np.full(len(parents), np.nan) for design in DESIGNS}
    lofo, fits, folds = {d: [] for d in DESIGNS}, [], []
    report["status"] = "running"
    for family in PROTOCOL["families"]:
        train, test, held = H7.outer_split(parents, family)
        folds.append({"family": family, "held_systems": sorted(held),
            "training_ids": parents.iloc[train]["material_id"].astype(str).tolist(),
            "test_ids": parents.iloc[test]["material_id"].astype(str).tolist(),
            "training_systems": sorted(set(parents.iloc[train]["system"])),
            "held_family_training_memberships": sum(family in m for m in parents.iloc[train]["full_family_membership"])})
        H7._write_json(out / "folds.json", folds)
        for design in DESIGNS:
            H7.P.log(f"H8 {design}: held family={family}, train={len(train)}, test={len(test)}")
            try:
                alpha, inner = select_alpha(data, design, train, held)
                fitted = fit_split(data, design, alpha, train, held, seed=PROTOCOL["seed"])
                if fitted.fit_info["status"] == "not_converged":
                    raise RuntimeError("Outer ranking head did not converge")
                scores = fitted.predict(geometry[test], extras[test])
                if not np.isfinite(scores).all():
                    raise ValueError("Nonfinite outer score")
                predictions[design][test] = scores
                lofo[design].append({"family": family, "status": "completed", **H7.metrics(parents.iloc[test].tc.to_numpy() > 0, scores)})
                fits.append({"design": design, "held_family": family, "model": fitted.identity(), "inner_selection": inner})
            except (ValueError, RuntimeError, FloatingPointError) as error:
                failure = {"design": design, "family": family, "status": "failed", "reason": f"{type(error).__name__}: {error}"}
                report["failures"].append(failure)
                lofo[design].append(failure)
            report.update(lofo=lofo, fits=fits)
            H7._write_json(out / "report.json", report)
    complete = {}
    macro = {}
    for design in DESIGNS:
        valid = np.isfinite(predictions[design]).all()
        report["designs"][design] = {"status": "completed" if valid else "incomplete"}
        macro[design] = {key: float(np.mean([r[key] for r in lofo[design]])) if valid else None
                        for key in ("observed_pu_auc", "recall_at_budget")}
        if valid:
            complete[design] = predictions[design]
    rows = []
    for design, scores in predictions.items():
        for i, r in parents.iterrows():
            rows.append({"design": design, "material_id": str(r.material_id), "family": str(r.family), "chemsys": str(r.system),
                "observed_positive": bool(r.tc > 0), "unlabeled": bool(r.tc == 0), "n_entries": int(r.n_entries),
                "catalog_rank_score": float(scores[i]) if np.isfinite(scores[i]) else None,
                "prediction_status": "available" if np.isfinite(scores[i]) else "failed"})
    pd.DataFrame(rows).to_csv(out / "parents.csv", index=False)
    report.update(status="completed" if len(complete) == len(DESIGNS) else "incomplete", macro=macro,
        paired_intervals=paired_intervals(parents, complete, resamples=20 if smoke else 1000),
        selection_effort_diagnostic_not_model_input={d: H7.stratum_metrics(parents, score, parents.n_entries.to_numpy() == 1)
            for d, score in complete.items()}, seconds=round(time.perf_counter() - started, 3))
    H7._write_json(out / "report.json", report)
    if report["status"] != "completed":
        raise RuntimeError("H8 incomplete: failures retained; no design released")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--protocol", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--input-csv", type=Path)
    args = parser.parse_args()
    if args.protocol:
        if args.output_dir is None:
            parser.error("--protocol requires --output-dir")
        _, digest = freeze_protocol(args.output_dir)
        H7.P.log(f"H8 frozen protocol {digest}")
    else:
        result = run(smoke=args.smoke, output_dir=args.output_dir, input_csv=args.input_csv)
        H7.P.log(f"H8 {result['status']}, report-only adopted=false")


if __name__ == "__main__":
    main()
