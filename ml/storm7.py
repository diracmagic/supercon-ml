"""Storm7: frozen exploratory direct-Tc comparison with train-only RBF prototypes.

U0 exactly uses Storm6 R2's raw feature map and HGB head. U1 appends16
label-free prototype similarities learned solely from training geometry.
Neither design replaces a released model. DFT targets are not measured Tc.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import storm6 as S
import unsupervised as U

P = S.P
DESIGNS = {"U0": "Unchanged Storm6 R2 raw D+geometry direct Tc",
           "U1": "Same raw D+geometry and direct head plus16 geometry RBF prototypes"}
PARAMS, SMOKE_PARAMS, SEED = dict(S.PARAMS), dict(S.SMOKE_PARAMS), 7


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def freeze_protocol(output_dir, *, smoke=False):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    source_paths = [Path(__file__), Path(U.__file__), Path(S.__file__), Path(P.__file__), Path(S.MF.__file__)]
    protocol = {
        "version": "storm7-frozen-rbf-prototypes-v1", "adopted": False, "report_only": True, "smoke": bool(smoke),
        "source_sha256_lf": {p.relative_to(P.ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in source_paths},
        "experimental_context": {"path": Path(P.EXPERIMENTS).relative_to(P.ROOT).as_posix(),
                                 "sha256_crlf_to_lf_only": S._reference_sha(P.EXPERIMENTS),
                                 "hash_rule": S.REFERENCE_HASH_RULE,
                                 "scope": "Provenance only; Storm7 does not load experimental anchors, fit measured diagnostics or use them as targets"},
        "data_source": {"url": S.DATA_URL, "prepare": "Unchanged storm6.prepare_real", "n": 7582, "chemical_systems": 4288},
        "reference_sha256": S.REFERENCE_SHA256, "reference_hash_rule": S.REFERENCE_HASH_RULE,
        "target": "Recomputed simplified Allen-Dynes DFT Tc(K), mu*=0.1,f1=f2=1; not measured Tc",
        "designs": DESIGNS, "head": "HistGradientBoostingRegressor on log1p(Tc); expm1 nonnegative clip",
        "params": SMOKE_PARAMS if smoke else PARAMS, "head_seed": "7+zero-based outer fold",
        "feature_baseline": "Exact Storm6 FeatureMap(R2), D+19 geometry; no target components as inputs",
        "representation_input": list(S.MF.FEATURE_NAMES),
        "representation": {"class": U.VERSION, "n_clusters": 16, "seed": 7, "n_init": 10,
                           "kmeans": "k-means++,lloyd,max_iter300,tol1e-4",
                           "preprocessing": "train medians; drop train all-missing/constant std<=1e-12; train means/std; clip using fixed +/-5; no test-fit statistics",
                           "map": "exp(-squared Euclidean distance/(2*sigma^2));16 columns appended",
                           "sigma": "median strictly positive (>1e-12) train nearest-centroid distance; if none use1 scaled unit and flag",
                           "degenerate": "fit k=min(16,distinct scaled train rows); retain occupied centroids only and log KMeans collapse/warnings; inactive columns0 explicit padding; no informative columns=>all inactive; never physical missing=0"},
        "outer": "Unchanged GroupKFold5 chemical-system splits, original row order",
        "inner": "Unchanged GroupShuffleSplit20% calibration, seed7+fold, disjoint systems",
        "preprocessing_scope": "Independent full-outer point map and proper-train interval map; no calibration or test fit; representation fit receives X only",
        "interval": "90% group split conformal; max absolute log1p residual per calibration chemical system, ceil((G+1)*.9); unbounded if insufficient groups; proper-train center",
        "ood": "Unchanged Storm6 D-only shared mask, nearest different-system training distances95th percentile; independent full/proper scopes",
        "primary_comparison": "U1 minus U0 material-weighted MAE,1000 paired chemical-system bootstrap,seed7",
        "secondary": "Shared top10% target tail and shared OOD subgroup MAE; row/group interval coverage and width; saved Storm4 context; no model selection",
        "label_access": "Targets only in supervised heads and evaluation/calibration; no Tc/lambda/wlog in representation",
        "feedback_training_records": 0, "actual_normal_state_training_records": 0,
        "limitations": ["Previously inspected folds: exploratory, not independent blind evaluation",
                        "RBF cluster similarities are not mechanisms or superconductivity probabilities",
                        "DFT labels, experimental measurements and P/U labels remain separate",
                        "No test/auxiliary structure corpus is used for representation training",
                        "Existing D features are not guaranteed cell/basis invariant; new geometry features do not repair that whole-model limitation",
                        "Nominal group coverage assumes exchangeable systems; subgroup coverage can differ"],
        "publication": "All2 designs reported; adopted=false always; no winner or release rule",
    }
    payload = (json.dumps(protocol, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path = out / "protocol.json"
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("Refusing to overwrite a different frozen Storm7 protocol")
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (out / "protocol.sha256").write_text(digest + "\n", encoding="utf-8")
    return protocol, digest


def forecast(design, Dtr, Gtr, ytr, Dte, Gte, *, seed, params):
    from sklearn.ensemble import HistGradientBoostingRegressor
    if design not in DESIGNS:
        raise ValueError("Unknown Storm7 design")
    fmap = S.FeatureMap("R2").fit(Dtr, Gtr)
    A, B = fmap.transform(Dtr, Gtr), fmap.transform(Dte, Gte)
    identity = {"raw_keep": fmap.keep.tolist(), "fit_rows": len(Dtr), "prototype": None}
    if design == "U1":
        prototype = U.TrainOnlyPrototypes(n_clusters=16, seed=SEED).fit(Gtr)
        A = np.column_stack([A, prototype.transform(Gtr)])
        B = np.column_stack([B, prototype.transform(Gte)])
        identity["prototype"] = prototype.identity()
    model = HistGradientBoostingRegressor(random_state=seed, **params)
    prediction = np.clip(np.expm1(model.fit(A, np.log1p(ytr)).predict(B)), 0, None)
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite forecast")
    return prediction, identity


def evaluate_fold(D, geometry, y, groups, train, test, design, fold, *, params):
    train, test = np.asarray(train, int), np.asarray(test, int)
    if set(groups[train]) & set(groups[test]):
        raise ValueError("Outer test system reached training")
    proper, cal = S.calibration_indices(train, groups, fold)
    point, point_fit = forecast(design, D[train], geometry[train], y[train], D[test], geometry[test], seed=SEED+fold, params=params)
    both = np.concatenate([cal, test])
    split, split_fit = forecast(design, D[proper], geometry[proper], y[proper], D[both], geometry[both], seed=SEED+fold, params=params)
    lo, hi, q = S.split_ranges(y[cal], split[:len(cal)], groups[cal], split[len(cal):])
    return {"point": point, "center": split[len(cal):], "lo": lo, "hi": hi, "q": q,
            "proper": proper, "calibration": cal, "calibration_predictions": split[:len(cal)],
            "point_fit": point_fit, "split_fit": split_fit}


def run(smoke=False, output_dir=None):
    import sklearn
    from sklearn.model_selection import GroupKFold
    started, identity = time.time(), S.run_identity()
    out = Path(output_dir) if output_dir is not None else P.RESULTS / "storm7" / identity["run_id"]
    if (out / "run.json").exists() or (out / "report.json").exists():
        raise ValueError("Storm7 run directory is non-overwriting; use a new directory")
    protocol, digest = freeze_protocol(out, smoke=smoke)  # Must precede data/targets.
    _json(out / "run.json", {**identity, "protocol_sha256": digest})
    report = {**identity, "version": protocol["version"], "protocol_sha256": digest,
              "smoke": bool(smoke), "adopted": False, "report_only": True, "status": "preparing",
              "output_dir": str(out), "target": protocol["target"],
              "cohort": None,
              "designs": {d:{"status":"pending","name":n} for d,n in DESIGNS.items()},
              "references": {}, "limitations": protocol["limitations"],
              "versions": {"sklearn":sklearn.__version__,"numpy":np.__version__,"pandas":pd.__version__}}
    _json(out / "report.json", report)
    preparation_stage = "load_data_and_construct_folds"
    try:
        frame, D, G, diagnostics, extra = S.synthetic_data() if smoke else S.prepare_real()
        groups, ids, y = frame["chemsys"].to_numpy(), frame["id"].astype(str).to_numpy(), frame["tc"].to_numpy(float)
        splits = list(GroupKFold(n_splits=5).split(D, groups=groups))
        fold_of = np.zeros(len(y), int)
        for fold, (_, test) in enumerate(splits):
            fold_of[test] = fold+1
        preparation_stage = "verify_historical_references"
        refs, _ = ({}, {}) if smoke else S.load_references(frame, fold_of)
        preparation_stage = "write_input_artifacts"
        _json(out / "input-manifest.json", {"n": len(y), "chemical_systems": len(np.unique(groups)),
                                            "details": extra[1] if extra else {"synthetic": True},
                                            "geometry_columns": list(S.MF.FEATURE_NAMES)})
        _json(out / "geometry-diagnostics.json", diagnostics)
        # Exact numeric inputs permit independently reconstructing every representation.
        np.savez_compressed(out / "feature-inputs.npz", D=D, geometry=G, ids=ids.astype(str), groups=groups.astype(str))
        tail = y >= np.quantile(y, .9)
        ood, split_ood = np.zeros(len(y), bool), np.zeros(len(y), bool)
        distances, split_distances, folds = np.zeros(len(y)), np.zeros(len(y)), []
        preparation_stage = "compute_shared_ood_and_fold_manifest"
        for fold, (train, test) in enumerate(splits):
            proper, cal = S.calibration_indices(train, groups, fold)
            distances[test], ood[test], q1 = S.ood_distance(D[train], D[test], groups[train])
            split_distances[test], split_ood[test], q2 = S.ood_distance(D[proper], D[test], groups[proper])
            record = {"fold": fold+1, "ood_threshold_full_train": q1, "ood_threshold_proper_train": q2}
            for name, ix in (("outer_train",train),("proper_train",proper),("calibration",cal),("test",test)):
                record[name+"_ids"], record[name+"_systems"] = ids[ix].tolist(), sorted(set(groups[ix]))
            folds.append(record)
        _json(out / "folds.json", folds)
        preparation_stage = "historical_context_metrics"
        if refs:
            report["references"]["Storm4_saved"] = S.point_metrics(y, refs["storm4"]["tc_pred_best"].to_numpy(),groups,fold_of,tail_mask=tail,ood=ood)
        report["cohort"] = {"n": len(y), "chemical_systems": len(np.unique(groups)), "tail_threshold_k": float(np.quantile(y,.9))}
    except Exception as error:
        report.update(status="failed_preparation", preparation_stage=preparation_stage,
                      reason=f"{type(error).__name__}: {error}", seconds=round(time.time()-started,3))
        for entry in report["designs"].values():
            entry["status"] = "not_run_preparation_failed"
        _json(out / "report.json", report)
        raise
    report["status"] = "running"
    rows, calibration_rows, predictions = [], [], {}
    _json(out / "report.json", report)
    for design in DESIGNS:
        entry = {"status":"running","name":DESIGNS[design],"folds":[]}
        report["designs"][design] = entry
        pred = {k:np.full(len(y),np.nan) for k in ("point","center","lo","hi")}
        try:
            for fold,(train,test) in enumerate(splits):
                result = evaluate_fold(D,G,y,groups,train,test,design,fold,params=SMOKE_PARAMS if smoke else PARAMS)
                for key in pred:
                    pred[key][test] = result[key]
                fit_path = f"{design}-fold{fold+1}-fits.json"
                _json(out / fit_path, {"point":result["point_fit"],"proper_train":result["split_fit"],
                                      "point_fit_ids":ids[train].tolist(),"proper_fit_ids":ids[result["proper"]].tolist()})
                cal = result["calibration"]
                residual = np.abs(np.log1p(y[cal])-np.log1p(result["calibration_predictions"]))
                maxima = {str(g):float(residual[groups[cal]==g].max()) for g in np.unique(groups[cal])}
                entry["folds"].append({"fold":fold+1,"fit_artifact":fit_path,"calibration_q":result["q"],
                                       "calibration_groups":len(maxima),"quantile_rank":int(np.ceil((len(maxima)+1)*.9)),
                                       "calibration_group_scores":maxima,
                                       "interval_status":"finite" if result["q"] is not None else "unbounded_insufficient_groups"})
                for j,i in enumerate(cal):
                    calibration_rows.append({"design":design,"fold":fold+1,"id":ids[i],"chemsys":groups[i],
                                             "target_dft_k":y[i],"proper_pred_k":result["calibration_predictions"][j],"abs_log_residual":residual[j]})
                P.log(f"Storm7 {design} fold{fold+1}/5 complete ({time.time()-started:.1f}s)")
            entry.update(status="completed",point=S.point_metrics(y,pred["point"],groups,fold_of,tail_mask=tail,ood=ood),
                         split_center=S.point_metrics(y,pred["center"],groups,fold_of,tail_mask=tail,ood=split_ood),
                         intervals=S.interval_metrics(y,pred["lo"],pred["hi"],groups,tail,split_ood))
            if refs:
                entry["paired_vs_Storm4"] = S.paired_bootstrap(y,pred["point"],refs["storm4"]["tc_pred_best"].to_numpy(),groups)
            predictions[design] = pred["point"]
            for i in range(len(y)):
                rows.append({"id":ids[i],"chemsys":groups[i],"fold":int(fold_of[i]),"design":design,
                             "tc_target_dft_k":y[i],"tc_pred_full_outer_k":pred["point"][i],
                             "tc_interval_center_proper_train_k":pred["center"][i],"tc_lo_k":pred["lo"][i],
                             "tc_hi_k":pred["hi"][i] if np.isfinite(pred["hi"][i]) else None,
                             "interval_unbounded":bool(not np.isfinite(pred["hi"][i])),
                             "ood_full_outer":bool(ood[i]),"distance_full_outer":distances[i],
                             "ood_proper_train":bool(split_ood[i]),"distance_proper_train":split_distances[i]})
        except (ValueError,RuntimeError,FloatingPointError) as error:
            entry.update(status="failed",reason=f"{type(error).__name__}: {error}")
        _json(out / "report.json",report)
        pd.DataFrame(rows).to_csv(out / "predictions.csv",index=False)
        pd.DataFrame(calibration_rows).to_csv(out / "calibration-predictions.csv",index=False)
    if set(predictions)==set(DESIGNS):
        report["paired_U1_minus_U0"] = {}
        for name,mask in (("overall",np.ones(len(y),bool)),("tail",tail),("ood",ood)):
            report["paired_U1_minus_U0"][name] = (S.paired_bootstrap(y[mask],predictions["U1"][mask],predictions["U0"][mask],groups[mask]) if mask.any() else {"status":"no_rows"})
    report["status"] = "completed" if all(v["status"]=="completed" for v in report["designs"].values()) else "incomplete"
    report["seconds"] = round(time.time()-started,3)
    _json(out / "report.json",report)
    files = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!="artifact-manifest.json"}
    _json(out / "artifact-manifest.json",{"sha256":files})
    if report["status"]!="completed":
        raise RuntimeError(f"Storm7 incomplete; see {out / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--protocol",action="store_true")
    parser.add_argument("--output-dir",type=Path)
    args = parser.parse_args()
    if args.protocol:
        freeze_protocol(args.output_dir or P.RESULTS / "storm7" / S.run_identity()["run_id"],smoke=args.smoke)
    else:
        run(smoke=args.smoke,output_dir=args.output_dir)


if __name__=="__main__":
    main()
