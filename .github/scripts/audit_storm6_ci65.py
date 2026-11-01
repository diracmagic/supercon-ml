"""Independent, read-only Storm6 artifact audit; no model/pipeline imports.

Requires numpy/pandas/sklearn. Run from any directory; all inputs/outputs can be
overridden. Output paths are relative to --repo-root, never runner/local absolutes.
No training, data downloads, source edits, or release decisions are performed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

RUN = "20261101T042028909465Z-1793506828909486216"
DESIGNS = ["R0", "R1", "R2", "R3", "R4"]


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha(path, normalize=False):
    raw = Path(path).read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n") if normalize else raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def csv(path):
    return pd.read_csv(path, dtype={"id": str})


def formula(lam, omega):
    lam, omega = np.asarray(lam), np.asarray(omega)
    denominator = lam - .1 * (1 + .62 * lam)
    value = np.zeros_like(lam, dtype=float)
    good = denominator > 0
    value[good] = omega[good] / 1.2 * np.exp(-1.04 * (1 + lam[good]) / denominator[good])
    return value


def point(y, pred, groups, folds, tail, ood):
    e = y - pred
    a = np.abs(e)
    return dict(n=len(y), mae_k=float(a.mean()), rmse_k=float(np.sqrt(np.mean(e**2))),
                r2=float(1 - np.sum(e**2) / np.sum((y-y.mean())**2)),
                median_absolute_error_k=float(np.median(a)),
                within_1k_fraction=float(np.mean(a <= 1)), within_2k_fraction=float(np.mean(a <= 2)),
                fold_mae_k=[float(a[folds == f].mean()) for f in np.unique(folds)],
                tail_n=int(tail.sum()), tail_mae_k=float(a[tail].mean()),
                chemical_systems=len(np.unique(groups)),
                ood=dict(n=int(ood.sum()), mae_k=float(a[ood].mean())),
                within_training_distance=dict(n=int((~ood).sum()), mae_k=float(a[~ood].mean())))


def intervals(y, lo, hi, groups, tail, ood):
    inside = (y >= lo) & (y <= hi)
    width = hi-lo
    finite = np.isfinite(lo) & np.isfinite(hi)
    score = width + 20 * (np.maximum(lo-y, 0) + np.maximum(y-hi, 0))
    return dict(row_coverage=float(inside.mean()),
                group_simultaneous_coverage=float(np.mean([inside[groups == g].all() for g in np.unique(groups)])),
                tail_coverage=float(inside[tail].mean()), finite_interval_rows=int(finite.sum()),
                unbounded_interval_rows=int((~finite).sum()), mean_width_k=float(width.mean()),
                median_width_k=float(np.median(width)), interval_score_k=float(score.mean()),
                ood=dict(n=int(ood.sum()), row_coverage=float(inside[ood].mean())),
                within_training_distance=dict(n=int((~ood).sum()), row_coverage=float(inside[~ood].mean())))


def subset_intervals(y, lo, hi, groups, mask):
    y, lo, hi, g = y[mask], lo[mask], hi[mask], groups[mask]
    inside = (lo <= y) & (y <= hi)
    width = hi-lo
    return dict(n=len(y), chemical_systems=len(np.unique(g)), row_coverage=float(inside.mean()),
                group_simultaneous_coverage=float(np.mean([inside[g == k].all() for k in np.unique(g)])),
                mean_width_k=float(width.mean()), median_width_k=float(np.median(width)))


def bootstrap(y, new, reference, groups, mask=None):
    if mask is not None:
        y, new, reference, groups = y[mask], new[mask], reference[mask], groups[mask]
    _, membership = np.unique(groups, return_inverse=True)
    size = np.bincount(membership)
    delta = np.bincount(membership, weights=np.abs(new-y)-np.abs(reference-y))
    # Resample chemical systems, retain all selected-subset rows of each draw;
    # ratio of error sums to row counts is the material-weighted paired effect.
    draws = np.random.default_rng(7).integers(0, len(size), (1000, len(size)))
    effects = delta[draws].sum(axis=1) / size[draws].sum(axis=1)
    return dict(delta_mae_k_new_minus_reference=float(delta.sum()/size.sum()),
                percentile_95_interval_k=np.quantile(effects, [.025, .975]).tolist(),
                repetitions=1000, unit="chemical-system cluster", selection_adjusted=False,
                n=len(y), chemical_systems=len(size))


def compare(actual, expected, where, differences, *, atol=1e-10):
    if isinstance(actual, dict):
        require(set(actual) <= set(expected), f"missing report fields at {where}")
        for k in actual:
            compare(actual[k], expected[k], f"{where}.{k}", differences, atol=atol)
    elif isinstance(actual, (list, tuple)):
        require(len(actual) == len(expected), f"array length differs at {where}")
        for k, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, f"{where}[{k}]", differences, atol=atol)
    elif isinstance(actual, (int, float, np.number)) and not isinstance(actual, bool):
        delta = abs(float(actual)-float(expected))
        differences.append(delta)
        require(delta <= atol, f"metric differs at {where}: {actual} vs {expected}")
    else:
        require(actual == expected, f"value differs at {where}")


def run(args):
    repo, artifact, out = args.repo_root.resolve(), args.artifact_dir.resolve(), args.output.resolve()
    relative = lambda p: Path(os.path.relpath(p, repo)).as_posix()
    directory = artifact / "results" / "storm6" / args.run_id
    report, protocol, folds = (load(directory / name) for name in ("report.json", "protocol.json", "folds.json"))
    manifest = load(directory / "input-manifest.json")
    frame = csv(directory / "predictions.csv")
    require(report["status"] == "completed" and report["report_only"] and not report["adopted"] and not report["smoke"], "run status/flags differ")
    protocol_hash = sha(directory / "protocol.json")
    require(protocol_hash == report["protocol_sha256"] == (directory/"protocol.sha256").read_text().strip(), "protocol digest differs")
    require(protocol["report_only"] and not protocol["adopted"] and set(protocol["designs"]) == set(DESIGNS), "protocol designs/flags differ")
    source_hashes = {}
    for name, expected in protocol["source_sha256"].items():
        # Audit the executed commit, not a later working tree.
        raw = subprocess.run(["git", "show", f"{report['source_commit']}:{name}"], cwd=repo,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        actual = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        source_hashes[name] = actual == expected
    require(all(source_hashes.values()), "executed source digest differs")
    reference_hashes = {name: sha(artifact/"results"/name, normalize=True) == expected
                        for name, expected in protocol["reference_sha256"].items()}
    require(all(reference_hashes.values()), "frozen reference file hashes differ")
    require(len(frame) == 5*7582 and set(frame.design) == set(DESIGNS), "five-design cohort differs")
    base = frame[frame.design == "R0"].reset_index(drop=True)
    ids = base.id.to_numpy()
    groups = base.chemsys.to_numpy()
    fold_of = base.fold.to_numpy()
    require(len(np.unique(ids)) == 7582 and len(np.unique(groups)) == 4288, "cohort size/ID uniqueness differs")
    require(hashlib.sha256("\n".join(ids).encode()).hexdigest() == manifest["details"]["id_order_sha256"], "ID order digest differs")
    y = base.tc_target_dft_k.to_numpy()
    tail_threshold = float(np.quantile(y, .9))
    tail = y >= tail_threshold
    truth = ["chemsys", "fold", "tc_target_dft_k", "lambda_target", "wlog_target_k",
             "ood_full_outer", "distance_full_outer", "ood_proper_train", "distance_proper_train"]
    designs = {}
    for design in DESIGNS:
        d = frame[frame.design == design].reset_index(drop=True)
        require(np.array_equal(d.id.to_numpy(), ids) and not d.id.duplicated().any(), f"{design} IDs/order differ")
        require(d[truth].equals(base[truth]), f"{design} labels/folds/OOD differ")
        required = ["tc_target_dft_k", "lambda_target", "wlog_target_k", "tc_pred_full_outer_k", "tc_interval_center_proper_train_k", "tc_lo_k", "tc_hi_k"]
        require(np.isfinite(d[required].to_numpy()).all(), f"{design} non-finite predictions")
        require(not d.interval_unbounded.any() and (d.tc_lo_k <= d.tc_hi_k).all(), f"{design} invalid interval bounds")
        designs[design] = d
    split_checks = []
    reconstructed = np.zeros(len(y), int)
    for index, ((train, test), saved) in enumerate(zip(GroupKFold(5).split(np.zeros((len(y), 1)), y, groups), folds)):
        reconstructed[test] = index+1
        fit, cal = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=7+index).split(train, groups=groups[train]))
        proper, calibration = train[fit], train[cal]
        sets = {"outer_train_systems": set(groups[train]), "test_systems": set(groups[test]),
                "proper_train_systems": set(groups[proper]), "calibration_systems": set(groups[calibration])}
        require(all(v == set(saved[k]) for k, v in sets.items()), f"fold {index+1} membership differs")
        require(all(len(v) == len(saved[k]) for k, v in sets.items()), f"fold {index+1} duplicate system manifest entries")
        require(not (sets["outer_train_systems"] & sets["test_systems"]), "outer overlap")
        require(not (sets["proper_train_systems"] & sets["calibration_systems"]), "proper/calibration overlap")
        require(sets["proper_train_systems"] | sets["calibration_systems"] == sets["outer_train_systems"], "proper/calibration partition differs")
        for key, n in (("n_train", len(train)), ("n_test", len(test)), ("n_proper", len(proper)), ("n_calibration", len(calibration))):
            require(saved[key] == n, f"fold {index+1} {key} differs")
        for flag, distance, threshold in (("ood_full_outer", "distance_full_outer", "ood_threshold_full_train"),
                                          ("ood_proper_train", "distance_proper_train", "ood_threshold_proper_train")):
            require(np.array_equal(base[flag].to_numpy()[test], base[distance].to_numpy()[test] > saved[threshold]), "OOD threshold application differs")
        split_checks.append(dict(fold=index+1, n_train=len(train), n_proper=len(proper), n_calibration=len(calibration), n_test=len(test),
                                 calibration_systems=len(sets["calibration_systems"]),
                                 quantile_rank=math.ceil((len(sets["calibration_systems"])+1)*.9), no_system_overlap=True))
    require(np.array_equal(reconstructed, fold_of), "recomputed outer folds differ")
    references = {}
    maximum_label_errors = {}
    maximum_component_label_errors = {}
    for key, name in (("storm4", "storm_round4_predictions.csv"), ("storm5", "storm_round5_ranges.csv"), ("gnn", "gnn_round2_final_predictions.csv")):
        d = csv(artifact/"results"/name)
        require(not d.id.duplicated().any() and set(d.id) == set(ids), f"reference {key} IDs differ")
        d = d.set_index("id").loc[ids].reset_index()
        require(np.array_equal(d.chemsys, groups), f"reference {key} chemical systems differ")
        if "fold" in d:
            require(np.array_equal(d.fold, fold_of), f"reference {key} folds differ")
        maximum_label_errors[key] = float(np.max(np.abs(d.tc.to_numpy()-y)))
        require(maximum_label_errors[key] <= 6e-6, f"reference {key} labels differ beyond saved rounding")
        for source, target in (("lambda", "lambda_target"), ("wlog", "wlog_target_k")):
            if source in d:
                error = float(np.max(np.abs(d[source].to_numpy()-base[target].to_numpy())))
                maximum_component_label_errors[f"{key}.{source}"] = error
                require(error <= 6e-6, f"reference {key} {source} labels differ beyond saved rounding")
        references[key] = d
    compare(tail_threshold, report["cohort"]["tail_threshold_k"], "tail_threshold", [], atol=1e-12)
    require(np.max(np.abs(formula(base.lambda_target.to_numpy(), base.wlog_target_k.to_numpy())-y)) < 1e-12, "target algebra differs")
    discrepancies, metrics = [], {}
    full_ood, proper_ood = base.ood_full_outer.to_numpy(), base.ood_proper_train.to_numpy()
    saved_s4 = references["storm4"].tc_pred_best.to_numpy()
    saved_s1 = references["storm4"].tc_pred_storm1.to_numpy()
    for design, d in designs.items():
        entry = report["designs"][design]
        require(entry["status"] == "completed", f"{design} not completed")
        p = d.tc_pred_full_outer_k.to_numpy()
        center, lo, hi = (d[k].to_numpy() for k in ("tc_interval_center_proper_train_k", "tc_lo_k", "tc_hi_k"))
        computed = dict(point=point(y, p, groups, fold_of, tail, full_ood),
                        split_center=point(y, center, groups, fold_of, tail, proper_ood),
                        intervals=intervals(y, lo, hi, groups, tail, proper_ood))
        compare(computed, entry, design, discrepancies)
        intervals_max_error = 0.
        for fold in range(1, 6):
            mask = fold_of == fold
            q = entry["folds"][fold-1]["calibration_log_groupmax_quantile"]
            require(q is not None and math.isfinite(q) and q >= 0, "nonfinite/negative calibration quantile")
            lower = np.maximum(np.expm1(np.log1p(center[mask])-q), 0)
            upper = np.expm1(np.log1p(center[mask])+q)
            intervals_max_error = max(intervals_max_error, float(np.max(np.abs(lo[mask]-lower))), float(np.max(np.abs(hi[mask]-upper))))
        require(intervals_max_error < 1e-10, f"{design} interval formula differs")
        components = None
        if design in {"R1", "R3", "R4"}:
            components = {}
            for name, target, pred, unit in (("lambda", "lambda_target", "lambda_pred", "dimensionless"), ("wlog", "wlog_target_k", "wlog_pred_k", "K")):
                error = d[target].to_numpy()-d[pred].to_numpy()
                components[name] = dict(mae=float(np.abs(error).mean()), rmse=float(np.sqrt(np.mean(error**2))), unit=unit)
            compare(components, entry["components"], f"{design}.components", discrepancies)
            formula_error = float(np.max(np.abs(formula(d.lambda_pred.to_numpy(), d.wlog_pred_k.to_numpy())-p)))
            require(formula_error < 1e-12, f"{design} component formula differs")
            require((d.lambda_pred >= 0).all() and (d.wlog_pred_k >= 1).all(), "component clipping differs")
            denominator = d.lambda_pred.to_numpy()-.1*(1+.62*d.lambda_pred.to_numpy())
            require(int(np.sum(denominator <= 0)) == entry["ad_nonpositive_denominator_rows"], "denominator count differs")
            require(int(np.sum(p == 0)) == entry["ad_zero_tc_rows"], "zero Tc count differs")
        else:
            require(d.lambda_pred.isna().all() and d.wlog_pred_k.isna().all(), "direct route includes components")
        b4, b1 = bootstrap(y, p, saved_s4, groups), bootstrap(y, p, saved_s1, groups)
        for name, b in (("Storm4_saved", b4), ("Storm1_saved", b1)):
            compare({k: v for k, v in b.items() if k not in {"n", "chemical_systems"}}, entry["paired_bootstrap"][name], f"{design}.bootstrap.{name}", discrepancies)
        metrics[design] = {**computed, "components": components, "paired_bootstrap_vs_Storm4": b4,
                           "maximum_interval_formula_error_K": intervals_max_error}
    ref4 = point(y, saved_s4, groups, fold_of, tail, full_ood)
    compare(ref4, report["references"]["Storm4_saved"], "reference.Storm4", discrepancies)
    compare(point(y, saved_s1, groups, fold_of, tail, full_ood), report["references"]["Storm1_saved"], "reference.Storm1", discrepancies)
    ref5 = references["storm5"]
    require(np.allclose(ref5.tc_pred.to_numpy(), saved_s4, atol=1.1e-5, rtol=0), "Storm5 point forecasts differ from Storm4")
    ref_intervals = intervals(y, ref5.tc_lo.to_numpy(), ref5.tc_hi.to_numpy(), groups, tail, full_ood)
    compare(ref_intervals, report["references"]["Storm5_saved_intervals"], "reference.Storm5", discrepancies)
    posthoc = {
        "tail_R3_minus_Storm4": bootstrap(y, designs["R3"].tc_pred_full_outer_k.to_numpy(), saved_s4, groups, tail),
        "full_train_OOD_R2_minus_Storm4": bootstrap(y, designs["R2"].tc_pred_full_outer_k.to_numpy(), saved_s4, groups, full_ood),
        "geometry_R3_minus_R1": bootstrap(y, designs["R3"].tc_pred_full_outer_k.to_numpy(), designs["R1"].tc_pred_full_outer_k.to_numpy(), groups),
        "geometry_R2_minus_R0": bootstrap(y, designs["R2"].tc_pred_full_outer_k.to_numpy(), designs["R0"].tc_pred_full_outer_k.to_numpy(), groups),
    }
    for key, b in posthoc.items():
        b["status"] = "post_hoc_descriptive_not_frozen_release_criterion"
    common_intervals = {design: subset_intervals(y, d.tc_lo_k.to_numpy(), d.tc_hi_k.to_numpy(), groups, proper_ood) for design, d in designs.items()}
    common_intervals["Storm5_saved"] = subset_intervals(y, ref5.tc_lo.to_numpy(), ref5.tc_hi.to_numpy(), groups, proper_ood)
    anchors = report["measured_diagnostics"]["graded_anchors"]
    scored = [r for r in anchors["table"] if r["use"] == "score" and r["n_matches"] > 0 and r["tc_exp"] is not None]
    anchor_recomputed = dict(n_scored=len(scored), n_listed=len(anchors["table"]),
                             dft_mae=round(float(np.mean([abs(r["dft_tc"]-r["tc_exp"]) for r in scored])), 2),
                             mae={d: round(float(np.mean([abs(r["pred"][d]-r["tc_exp"]) for r in scored])), 2)
                                  for d in DESIGNS + ["Storm4_saved"]})
    compare(anchor_recomputed, anchors["summary"], "anchors.rounded_saved_table_arithmetic", discrepancies)
    matched = csv(artifact/"results"/"storm_round3_matches.csv")
    matched_summary = report["measured_diagnostics"]["matched_3dsc"]
    require(len(matched) == 298 and int((matched.tc_exp > 0).sum()) == 168, "historical matched pool sizes differ")
    require(all(r["n"] == 298 and r["n_sc"] == 168 for r in matched_summary.values()), "measured diagnostic denominators differ")
    result = dict(status="passed", run_id=args.run_id, github_run_id=report["github_run_id"], source_commit=report["source_commit"],
                  target=report["target"], report_only=True, adopted=False,
                  paths=dict(script=relative(Path(__file__).resolve()), artifact_dir=relative(artifact), predictions=relative(directory/"predictions.csv"),
                             report=relative(directory/"report.json"), protocol=relative(directory/"protocol.json"), folds=relative(directory/"folds.json")),
                  integrity=dict(protocol_sha256=protocol_hash, executed_source_hashes_match=source_hashes, reference_hashes_match=reference_hashes,
                                 exact_all_design_ID_order_and_fold_labels=True, reference_label_max_rounding_error_K=maximum_label_errors,
                                 reference_component_label_max_rounding_error=maximum_component_label_errors,
                                 n_prediction_rows=len(frame), n_unique_ids=7582, n_chemical_systems=4288,
                                 recomputed_outer_and_inner_folds_match=True, split_checks=split_checks,
                                 numeric_report_values_compared=len(discrepancies), maximum_report_numeric_difference=float(max(discrepancies))),
                  cohort=dict(n=7582, chemical_systems=4288, tail_n=int(tail.sum()), tail_threshold_k=tail_threshold,
                              full_train_ood_n=int(full_ood.sum()), proper_train_ood_n=int(proper_ood.sum())),
                  reference_Storm4_point=ref4, reference_Storm5_intervals_full_ood365=ref_intervals, designs=metrics,
                  R0_vs_saved_Storm1_max_absolute_prediction_difference_K=float(np.max(np.abs(designs["R0"].tc_pred_full_outer_k.to_numpy()-saved_s1))),
                  post_hoc_paired_bootstrap=posthoc,
                  common_proper_train_OOD343_interval_comparison=dict(mask="R0/R1/R2/R3/R4 shared proper-train OOD, 343 rows; applied identically to saved Storm5",
                                                                     designs=common_intervals),
                  experimental_diagnostics=dict(graded_anchor_saved_table_arithmetic=anchor_recomputed,
                                                matched_3dsc_report_values=matched_summary,
                                                historical_matched_pool_size_verified=298, historical_matched_pool_positive_tc_verified=168,
                                                independent_composition_mapping_rebuilt=False),
                  limits=["No models were refitted. Artifact source digests and split membership were checked, but train-only PCA/scaling and OOD distances cannot be numerically reconstructed without feature matrices.",
                          "Calibration predictions/residuals are absent: interval bound algebra, rank feasibility and held-out empirical coverage were verified; the saved calibration q order statistics cannot independently be reconstructed.",
                          "Historical reference Tc labels and forecasts were saved at limited decimal precision; label equality is within 6e-6 K, not bytewise equality.",
                          "7582-material target is simplified Allen-Dynes DFT Tc (mu*=0.1, f1=f2=1), not measured superconductivity; oracle components are algebraic checks only.",
                          "All historical folds have been reused for model selection; chemical-system bootstrap intervals are descriptive and not selection-adjusted or a blind external validation.",
                          "18 graded anchors and 298 composition-matched 3DSC entries (168 positive Tc, 130 zero-coded records) are different denominators and curation standards. Neither establishes phase/pressure/sample matches, prospective validation, or verified experimental negatives.",
                          "Anchor MAE was independently recomputed from the rounded saved table, not fresh primary-paper measurement verification. Atom/composition-to-ID mapping for the current 298 predictions is absent and was not reverse-engineered from Tc.",
                          "Nominal 90% group-conformal coverage relies on exchangeable chemical systems; fixed-cohort empirical coverage and especially OOD/tail subgroup coverage can differ.",
                          "Post-hoc tail/OOD/geometry contrasts are diagnostics requested after reading results, not frozen release criteria; all interval comparisons use the explicit common 343-row mask."])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(dict(status=result["status"], output=relative(out), maximum_report_numeric_difference=max(discrepancies),
                          post_hoc_paired_bootstrap=posthoc), allow_nan=False))
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--artifact-dir", type=Path, default=root.parent/"research-results-65")
    parser.add_argument("--run-id", default=RUN)
    parser.add_argument("--output", type=Path, default=root/"results"/"validation"/"storm6-ci65.json")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
