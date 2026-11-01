"""Independent H7 artifact checker; no project/scientific-model module imports.

Input directories are read-only. Requires numpy/pandas/sklearn. This audits
observed-positive-versus-unlabeled ranking, never true SC probabilities, H4
accuracy, causal mechanisms, or an independent prospective study.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

DESIGNS = ("R0", "R1", "R2")
FLAGS = ("is_metal", "small_gap", "is_magnetic")
EXTRAS = ("volume_per_atom_angstrom3", *FLAGS)


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def array_equal(actual, expected, name, atol=1e-9):
    a, b = np.asarray(actual), np.asarray(expected)
    require(a.shape == b.shape, f"{name}: array shape differs")
    if a.dtype.kind in "biuf" and b.dtype.kind in "biuf":
        require(np.allclose(a, b, atol=atol, rtol=1e-8, equal_nan=True), f"{name}: array values differ")
    else:
        require(np.array_equal(a, b), f"{name}: array values differ")


def compare(actual, expected, name, deltas):
    if isinstance(actual, dict):
        require(set(actual) <= set(expected), f"{name}: missing report fields")
        for key, value in actual.items():
            compare(value, expected[key], f"{name}.{key}", deltas)
    elif isinstance(actual, (list, tuple)):
        require(len(actual) == len(expected), f"{name}: array length differs")
        for index, (a, b) in enumerate(zip(actual, expected)):
            compare(a, b, f"{name}[{index}]", deltas)
    elif actual is None or isinstance(actual, (str, bool)):
        require(actual == expected, f"{name}: value differs")
    else:
        error = abs(float(actual)-float(expected))
        require(error <= 1e-10, f"{name}: number differs")
        deltas.append(error)


def parse_bool(column):
    values = column.map(lambda value: value if type(value) in (bool, np.bool_) else
                        True if value == "True" else False if value == "False" else None)
    require(not values.isna().any(), "invalid explicit boolean column")
    return values.to_numpy(bool)


def parse_membership(value):
    # input-parents.csv historically emits Python-list text; parents.csv emits
    # JSON-list text. Decode either safely, without eval or importing H7.
    try:
        result = json.loads(value)
    except json.JSONDecodeError:
        result = ast.literal_eval(value)
    require(isinstance(result, list) and all(isinstance(x, str) for x in result), "invalid family membership")
    return result


def rank_metrics(positive, score, budget_fraction=.2):
    """Mann-Whitney AUC with average tied ranks; explicit fractional budget ties."""
    positive, score = np.asarray(positive, bool), np.asarray(score, float)
    require(len(positive) == len(score) and np.isfinite(score).all(), "unaligned/nonfinite ranking")
    n, p = len(score), int(positive.sum())
    u = n-p
    order = np.argsort(score, kind="stable")
    sorted_score = score[order]
    boundaries = np.r_[0, np.flatnonzero(sorted_score[1:] != sorted_score[:-1])+1, n]
    ranks = np.empty(n, float)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        ranks[order[left:right]] = (left+1+right)/2
    auc = float((ranks[positive].sum()-p*(p+1)/2)/(p*u)) if p and u else None
    budget = math.ceil(budget_fraction*n)
    if budget and p:
        boundary = np.partition(score, n-budget)[n-budget]
        above, tied = score > boundary, score == boundary
        allocation = (budget-int(above.sum()))/int(tied.sum())
        recalled = float(positive[above].sum()+allocation*positive[tied].sum())
        recall = recalled/p
    else:
        recalled = recall = None
    return dict(n=n, n_positive=p, n_unlabeled=u, observed_pu_auc=auc,
                recall_at_budget=recall, budget=budget, expected_recorded_positives_at_budget=recalled)


def cluster_intervals(positive, families, systems, predictions, family_names, comparisons, repetitions, seed):
    """Resample whole systems jointly across held families; equal-family macro."""
    unique = sorted(set(systems))
    blocks = [np.flatnonzero(systems == value) for value in unique]
    rng = np.random.default_rng(seed)
    values = {f"{a}-{b}": {"observed_pu_auc": [], "recall_at_budget": []} for a, b in comparisons}
    for _ in range(repetitions):
        selected = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        aggregates = {}
        valid = True
        for design, score in predictions.items():
            rows = [rank_metrics(positive[selected[families[selected] == family]], score[selected[families[selected] == family]])
                    for family in family_names]
            if any(row["observed_pu_auc"] is None for row in rows):
                valid = False
                break
            aggregates[design] = {key: float(np.mean([row[key] for row in rows]))
                                  for key in ("observed_pu_auc", "recall_at_budget")}
        if valid:
            for a, b in comparisons:
                for key in values[f"{a}-{b}"]:
                    values[f"{a}-{b}"][key].append(aggregates[a][key]-aggregates[b][key])
    original = {design: {key: float(np.mean([rank_metrics(positive[families == f], score[families == f])[key]
                                                   for f in family_names]))
                           for key in ("observed_pu_auc", "recall_at_budget")} for design, score in predictions.items()}
    result = {}
    for a, b in comparisons:
        name = f"{a}-{b}"
        result[name] = {"status": "completed", "quantities": {}}
        for key, samples in values[name].items():
            result[name]["quantities"][key] = dict(delta_new_minus_reference=original[a][key]-original[b][key],
                                                    lower95=float(np.quantile(samples, .025)) if samples else None,
                                                    upper95=float(np.quantile(samples, .975)) if samples else None,
                                                    valid_resamples=len(samples), requested_resamples=repetitions)
    return result


def refit_scale(matrix, preprocessing):
    matrix = np.asarray(matrix, float)
    keep = np.isfinite(matrix).mean(axis=0) >= preprocessing["minimum_training_finite_fraction"]
    chosen = matrix[:, keep]
    median = np.nanmedian(np.where(np.isfinite(chosen), chosen, np.nan), axis=0) if chosen.shape[1] else np.zeros(0)
    filled = np.where(np.isfinite(chosen), chosen, median)
    mean, std = filled.mean(axis=0), filled.std(axis=0)
    variable = std > preprocessing["constant_tolerance"]
    selected = np.flatnonzero(keep)[variable]
    keep[:] = False
    keep[selected] = True
    return {"keep": keep.tolist(), "median": median[variable].tolist(), "mean": mean[variable].tolist(), "std": std[variable].tolist()}


def check_scale(matrix, exported, protocol, name):
    expected = refit_scale(matrix, protocol["preprocessing"])
    require(set(exported) == {"keep", "median", "mean", "std"}, f"{name}: unexpected scale fields")
    for key, value in expected.items():
        array_equal(exported[key], value, f"{name}.{key}")


def transform_scale(matrix, scale, protocol):
    selected = np.asarray(matrix, float)[:, np.asarray(scale["keep"], bool)]
    filled = np.where(np.isfinite(selected), selected, np.asarray(scale["median"]))
    return np.clip((filled-np.asarray(scale["mean"]))/np.asarray(scale["std"]),
                   -protocol["preprocessing"]["z_clip"], protocol["preprocessing"]["z_clip"])


def check_outer_basis(model, train, test, geometry, extras, protocol):
    basis, design = model["feature_basis"], model["design"]
    require(basis["training_rows"] == len(train), "outer basis fitted row count differs")
    require(model["pca_auxiliary_rows"] == 0, "external PCA rows present")
    pca_eigen_residual = None
    if design == "R2":
        check_scale(geometry[train], basis["geometry_scale"], protocol, "geometry_scale")
        scaled = transform_scale(geometry, basis["geometry_scale"], protocol)
        pca = basis["pca"]
        require(pca["fit_rows"] == len(train) and pca["auxiliary_rows"] == 0, "PCA fit membership count differs")
        center = np.asarray(pca["mean"])
        components = np.asarray(pca["components"])
        explained = np.asarray(pca["explained_variance"])
        require(components.shape == (protocol["pca_components"], scaled.shape[1]), "PCA shape differs")
        array_equal(center, scaled[train].mean(axis=0), "PCA train mean")
        array_equal(components@components.T, np.eye(len(components)), "PCA orthonormal rows")
        covariance = np.cov(scaled[train], rowvar=False, ddof=1)
        array_equal(explained, np.linalg.eigvalsh(covariance)[::-1][:len(components)], "PCA train eigenvalues")
        pca_eigen_residual = float(np.max(np.abs(covariance@components.T-components.T*explained)))
        require(pca_eigen_residual < 1e-7, "PCA components do not match train-only covariance")
        raw = np.column_stack([(scaled-center)@components.T, extras])
        all_names = [f"geometry_PC{i+1}" for i in range(protocol["pca_components"])] + list(EXTRAS)
    else:
        require("pca" not in basis and "geometry_scale" not in basis, "unexpected PCA on direct geometry")
        raw = np.column_stack([geometry, extras])
        all_names = list(protocol["geometry_features"])+list(EXTRAS)
    check_scale(raw[train], basis["main_scale"], protocol, "main_scale")
    names = [name for name, keep in zip(all_names, basis["main_scale"]["keep"]) if keep]
    require(basis["main_features"] == names, "unexpected predictors or main feature order")
    main = transform_scale(raw, basis["main_scale"], protocol)
    terms = [(i, None) for i in range(len(names))]
    if design != "R0":
        terms += [(i, i) for i, name in enumerate(names) if name not in FLAGS]
        terms += [(i, j) for i in range(len(names)) for j in range(i+1, len(names))
                  if {names[i], names[j]} != {"is_metal", "small_gap"}]
    require([list(x) for x in terms] == basis["term_indices_before_train_filter"], "unexpected term expansion")
    all_terms = [names[i] if j is None else f"{names[i]} * {names[j]}" for i, j in terms]
    expanded = np.column_stack([main[:, i] if j is None else main[:, i]*main[:, j] for i, j in terms]) if terms else np.zeros((len(main), 0))
    check_scale(expanded[train], basis["term_scale"], protocol, "term_scale")
    expected_terms = [name for name, keep in zip(all_terms, basis["term_scale"]["keep"]) if keep]
    require(model["terms"] == expected_terms, "term names contain extra/leaking predictors")
    coefficients = np.asarray(model["coefficients"], float)
    require(coefficients.shape == (len(expected_terms),) and np.isfinite(coefficients).all(), "invalid coefficient vector")
    require(model["nonzero_terms"] == int(np.sum(np.abs(coefficients)>protocol["stability"]["coefficient_tolerance"])), "nonzero coefficient count differs")
    predicted = transform_scale(expanded[test], basis["term_scale"], protocol)@coefficients
    return predicted, {"main_features": names, "terms": len(expected_terms), "training_rows": len(train),
                       "pca_train_eigen_residual": pca_eigen_residual}


def check_stability(stability, model, training_families, protocol, repetitions):
    if model["design"] == "R0":
        require(stability is None, "R0 unexpectedly has nonlinear term stability")
        return None
    rules = protocol["stability"]
    require(stability["resamples"] == repetitions, "stability bootstrap count differs")
    counts = stability["bootstrap_status_counts"]
    require(sum(counts.values()) == repetitions and all(type(v) is int and v >= 0 for v in counts.values()), "invalid stability status counts")
    experts = stability["training_family_heads"]
    require(sorted(x["family"] for x in experts) == sorted(training_families), "stability expert families differ")
    converged = model["status"] != "not_converged" and counts.get("not_converged", 0) == 0 and all(x["status"] != "not_converged" for x in experts)
    require(stability["status"] == ("completed" if converged else "inconclusive_nonconvergence"), "stability conclusion ignores nonconvergence")
    require([row["term"] for row in stability["terms"]] == model["terms"], "stability term order differs")
    common = []
    for row, coefficient in zip(stability["terms"], model["coefficients"]):
        require(abs(row["coefficient"]-coefficient) <= 1e-12, "stability coefficient differs")
        sign = int(np.sign(coefficient)) if abs(coefficient) > rules["coefficient_tolerance"] else 0
        frequency, agreement = row["selection_frequency"], row["conditional_sign_agreement"]
        require(0 <= frequency <= 1 and 0 <= agreement <= 1, "invalid stability frequency/agreement")
        selected = frequency*repetitions
        require(abs(selected-round(selected)) < 1e-8 and round(selected) <= repetitions-counts.get("not_converged", 0), "stability frequency denominator differs")
        require(abs(agreement*selected-round(agreement*selected)) < 1e-8, "stability conditional agreement denominator differs")
        signs = row["training_family_signs"]
        require(len(signs) == len(training_families) and all(s in (-1, 0, 1) for s in signs), "invalid expert signs")
        supported = bool(sign) and len(signs) == rules["training_families_same_sign"] and all(s == sign for s in signs)
        expected = bool(converged and supported and frequency >= rules["selection_frequency"] and agreement >= rules["conditional_sign_agreement"])
        require(row["common_in_training"] is expected, "common-term threshold logic differs")
        if expected:
            common.append(row["term"])
    require(stability["common_terms"] == common, "common_terms list differs")
    return {"status": stability["status"], "common_terms": common, "criterion_logic_verified": True,
            "raw_bootstrap_coefficients_exported": False}


def check_inner(records, model, train, outer_held, inputs, positive, families, systems, protocol, deltas):
    require([r["alpha"] for r in records] == protocol["alpha_grid"], "inner alpha grid/order differs")
    training_families = sorted(set(families[train]))
    splits = list(GroupKFold(protocol["inner_system_folds"]).split(train, groups=systems[train]))
    for record in records:
        require(len(record["folds"]) == len(splits), "inner fold count differs")
        aucs = {family: [] for family in training_families}
        for number, ((a, b), fold) in enumerate(zip(splits, record["folds"])):
            tr, val = train[a], train[b]
            require(fold["fold"] == number and fold["pca_auxiliary_rows"] == 0, "inner fold ID/external rows differ")
            require(fold["training_ids"] == inputs.iloc[tr].material_id.tolist() and fold["validation_ids"] == inputs.iloc[val].material_id.tolist(), "inner row membership/order differs")
            require(fold["training_systems"] == sorted(set(systems[tr])) and fold["validation_systems"] == sorted(set(systems[val])), "inner system membership differs")
            require(not (set(systems[tr]) & (set(systems[val]) | outer_held)), "inner/outer chemical-system leakage")
            require(set(fold["family_metrics"]) == set(training_families), "inner family metric coverage differs")
            for family in training_families:
                ix = val[families[val] == family]
                row = fold["family_metrics"][family]
                count = int(positive[ix].sum())
                compare(dict(n=len(ix), n_positive=count, n_unlabeled=len(ix)-count), row, "inner counts", deltas)
                available = bool(count and len(ix)-count)
                require(row["status"] == ("valid" if available else "skipped"), "inner missing-family status differs")
                expected_reason = None if available else "no_validation_rows" if not len(ix) else "no_observed_positive" if not count else "no_unlabeled"
                require(row["skip_reason"] == expected_reason, "inner skipped-family reason differs")
                value = row["observed_pu_auc"]
                require((value is not None) == available, "inner unsupported AUC was filled/dropped")
                if available:
                    require(0 <= value <= 1, "inner AUC out of range")
                    aucs[family].append(value)
        family_means = {family: dict(n_valid_folds=len(values), mean_fold_auc=float(np.mean(values)) if values else None)
                        for family, values in aucs.items()}
        compare(family_means, record["family_mean_fold_auc"], "inner within-family fold means", deltas)
        valid = all(aucs.values())
        mean = float(np.mean([x["mean_fold_auc"] for x in family_means.values()])) if valid else None
        compare(mean, record["mean_observed_pu_auc"], "inner equally weighted training-family macro", deltas)
        require(record["objective_status"] == ("valid" if valid else "invalid_missing_training_family_auc"), "inner objective validity differs")
    eligible = [r for r in records if r["mean_observed_pu_auc"] is not None and all(x["status"] != "not_converged" for x in r["folds"])]
    require(bool(eligible), "outer model has no valid training-only alpha selection")
    best = max(r["mean_observed_pu_auc"] for r in eligible)
    chosen = max(r["alpha"] for r in eligible if r["mean_observed_pu_auc"] >= best-protocol["alpha_tie_auc_tolerance"])
    require(model["alpha"] == chosen, "alpha rule uses wrong metric/tie break")
    return {"selected_alpha": chosen, "inner_memberships_verified": True,
            "fold_family_AUC_to_family_mean_to_macro_verified": True,
            "raw_inner_scores_and_bases_exported": False}


def coverage(inputs, matrix, names, families, family_names):
    result = {}
    for family in ["all", *family_names]:
        keep = np.ones(len(inputs), bool) if family == "all" else families == family
        result[family] = {"n": int(keep.sum()), "features": {
            name: {"finite_rows": int(np.isfinite(matrix[keep, j]).sum()),
                   "finite_fraction": float(np.isfinite(matrix[keep, j]).mean()) if keep.any() else None}
            for j, name in enumerate(names)}}
    return result


def stratum_ranking(positive, score, keep, families, family_names):
    by_family = {family: rank_metrics(positive[keep&(families == family)], score[keep&(families == family)]) for family in family_names}
    macro = {}
    for key in ("observed_pu_auc", "recall_at_budget"):
        defined = [family for family in family_names if by_family[family][key] is not None]
        macro[key] = {"macro": float(np.mean([by_family[family][key] for family in defined])) if defined else None,
                      "n_defined_families": len(defined), "defined_families": defined}
    return {"per_family": by_family, "macro_among_defined_families": macro,
            "cross_family_score_pooling": False, "primary_metric": False}


def run(args):
    root, folder = args.repo_root.resolve(), args.run_dir.resolve()
    relative = lambda path: Path(os.path.relpath(path, root)).as_posix()
    report, protocol, manifest, folds = (read_json(folder/name) for name in ("report.json", "protocol.json", "input-manifest.json", "folds.json"))
    frozen_hash = digest(protocol)
    require(frozen_hash == args.expected_protocol_hash == report["protocol_sha256"] == (folder/"protocol.sha256").read_text().strip(), "frozen protocol digest differs")
    require(report["protocol"] == protocol and protocol["version"] == "hurricane7-exploratory-pu-ranking-v2", "wrong H7 protocol version")
    amendment = protocol["preflight_amendment"]
    require(amendment["superseded_protocol_sha256"] == "3d82c25a5a893290a6e62c50002d2065f0bf0a8812a08b197520965196c0c352"
            and amendment["no_real_fit_observed"] is True and amendment["only_synthetic_smoke_before_amendment"] is True, "preflight amendment record differs")
    require(report["report_only"] is True and report["adopted"] is False and report["status"] == "completed", "run incomplete/not report-only")
    smoke = report["mode"] == "synthetic_smoke_not_scientific"
    require(args.allow_smoke or not smoke, "synthetic smoke is not a scientific artifact")
    require(not report["failures"] and set(report["designs"]) == set(DESIGNS) and all(x["status"] == "completed" for x in report["designs"].values()), "incomplete design/failure silently included")
    require(report["actual_feedback_training_records"] == report["actual_precursor_training_records"] == 0, "unexpected feedback training rows")
    require(hashlib.sha256((folder/"input-parents.csv").read_bytes()).hexdigest() == manifest["input_csv_sha256"] and digest(manifest) == report["input_manifest_sha256"], "input/manifest digest differs")
    require(manifest["source_data_sha256"] == protocol["source_sha256"] and manifest["auxiliary_background_rows"] == 0, "input source or external cohort differs")
    inputs = pd.read_csv(folder/"input-parents.csv", dtype={"material_id": str})
    output = pd.read_csv(folder/"parents.csv", dtype={"material_id": str})
    require(not inputs.material_id.duplicated().any(), "input IDs repeated")
    ids, families, systems = inputs.material_id.to_numpy(), inputs.family.to_numpy(), inputs.system.to_numpy()
    positive = parse_bool(inputs.observed_positive)
    members = [parse_membership(value) for value in inputs.full_family_membership]
    require(all(value == [family] for value, family in zip(members, families)), "mixed full family membership reached cohort")
    require(set(families) == set(protocol["families"]), "held-family coverage differs")
    require(not (set(ids) & set(protocol["mixed_family_exclusions"])), "excluded mixed-family ID entered cohort")
    require(np.isfinite(inputs.n_entries).all() and (inputs.n_entries >= 1).all() and (inputs.n_entries == inputs.n_entries.astype(int)).all(), "invalid linked-entry count")
    metadata = [{"material_id": str(row.material_id), "family": str(row.family), "system": str(row.system),
                 "observed_positive": bool(p), "n_entries": int(row.n_entries), "full_family_membership": membership}
                for (_, row), p, membership in zip(inputs.iterrows(), positive, members)]
    require(digest(metadata) == manifest["cohort_metadata_sha256"], "cohort metadata digest differs")
    if not smoke:
        require((len(inputs), int(positive.sum()), int((~positive).sum())) == (615, 288, 327), "615/288P/327U fixed cohort differs")
        mixed = {x["material_id"]: x["memberships"] for x in manifest["provenance"]["mixed_excluded"]}
        require(mixed == protocol["mixed_family_exclusions"] and len(mixed) == 4, "four mixed-family exclusions differ")
    compare(dict(n=len(inputs), n_positive=int(positive.sum()), n_unlabeled=int((~positive).sum())), report["cohort"], "cohort", [])
    names = list(protocol["geometry_features"])+list(EXTRAS)
    require(len(protocol["geometry_features"]) == 19 and protocol["additional_features"] == list(EXTRAS), "frozen 19+4 feature allowlist differs")
    geometry, extras = inputs[names[:19]].to_numpy(float), inputs[names[19:]].to_numpy(float)
    require(not np.isinf(geometry).any() and not np.isinf(extras).any(), "invalid infinite source input")
    flag = extras[:, 1:]
    require(np.isin(flag, [0., 1.]).all(), "invalid electronic flags")
    if not smoke:
        require(not ((flag[:, 0] == 1)&(flag[:, 1] == 1)).any(), "real metal/small-gap flags overlap")
    deltas = []
    finite_coverage = coverage(inputs, np.column_stack([geometry, extras]), names, families, protocol["families"])
    compare(finite_coverage, manifest["coverage"], "input finite coverage", deltas)
    compare(finite_coverage, report["feature_coverage_by_family"], "report finite coverage", deltas)
    require(len(folds) == 4, "outer fold count differs")
    require(len(output) == len(inputs)*3 and set(output.design) == set(DESIGNS), "three-design output cohort differs")
    predictions, outer_metrics = {}, {}
    for design in DESIGNS:
        rows = output[output.design == design].reset_index(drop=True)
        require(np.array_equal(rows.material_id.to_numpy(), ids), "output ID order differs")
        require(np.array_equal(rows.family.to_numpy(), families) and np.array_equal(rows.chemsys.to_numpy(), systems), "output family/system differs")
        require(np.array_equal(parse_bool(rows.observed_positive), positive) and np.array_equal(parse_bool(rows.unlabeled), ~positive), "P/U output labels differ")
        require((rows.prediction_status == "available").all(), "missing score was presented as available")
        scores = rows.catalog_rank_score.to_numpy(float)
        require(np.isfinite(scores).all(), "nonfinite rank scores")
        predictions[design] = scores
        metrics_by_family = [dict(family=family, status="completed", **rank_metrics(positive[families == family], scores[families == family]))
                             for family in protocol["families"]]
        compare(metrics_by_family, report["lofo"][design], f"{design} outer PU metrics", deltas)
        macro = {key: float(np.mean([row[key] for row in metrics_by_family])) for key in ("observed_pu_auc", "recall_at_budget")}
        compare(macro, report["macro"][design], f"{design} outer macro", deltas)
        outer_metrics[design] = {"families": metrics_by_family, "macro": macro}
        if "n_entries" in rows:
            array_equal(rows.n_entries, inputs.n_entries, "output linked entries")
        if "full_family_membership" in rows:
            require([parse_membership(x) for x in rows.full_family_membership] == members, "output full family membership differs")
        if "geometry_finite_feature_count" in rows:
            array_equal(rows.geometry_finite_feature_count, np.isfinite(geometry).sum(axis=1), "output geometry finite counts")
    fit_records = report["fits"]
    require(len(fit_records) == 12 and len({(x["design"], x["held_family"]) for x in fit_records}) == 12, "outer model coverage differs")
    model_audits = []
    for family, fold in zip(protocol["families"], folds):
        test = np.flatnonzero(families == family)
        held = set(systems[test])
        train = np.flatnonzero((families != family)&~np.isin(systems, list(held)))
        require(fold["held_family"] == family and fold["held_systems"] == sorted(held), "outer held membership differs")
        require(fold["training_ids"] == ids[train].tolist() and fold["test_ids"] == ids[test].tolist(), "outer row membership differs")
        require(fold["training_systems"] == sorted(set(systems[train])) and not (set(systems[train])&held), "outer system leakage")
        require(fold["full_membership_held_family_training_rows"] == 0, "full-family intruders in train")
        compare(coverage(inputs.iloc[train], np.column_stack([geometry, extras])[train], names, families[train], protocol["families"]),
                fold["training_feature_coverage"], "outer training feature coverage", deltas)
        for design in DESIGNS:
            fitted = next(x for x in fit_records if x["design"] == design and x["held_family"] == family)
            model = fitted["model"]
            require(fitted["held_systems"] == sorted(held) and model["training_systems"] == sorted(set(systems[train])), "outer fit systems differ")
            require(model["design"] == design and model["status"] != "not_converged", "outer model design/convergence differs")
            computed_score, basis_info = check_outer_basis(model, train, test, geometry, extras, protocol)
            array_equal(computed_score, predictions[design][test], "held-out coefficients-to-score", atol=1e-8)
            inner = check_inner(fitted["inner_selection"], model, train, held, inputs, positive, families, systems, protocol, deltas)
            stable_repetitions = 4 if smoke else protocol["stability"]["system_bootstraps"]
            stability = check_stability(fitted["stability"], model, sorted(set(families[train])), protocol, stable_repetitions)
            model_audits.append({"design": design, "held_family": family, **basis_info, "inner": inner, "stability": stability,
                                 "maximum_reconstructed_score_error": float(np.max(np.abs(computed_score-predictions[design][test])))})
    comparisons = [tuple(x) for x in protocol["paired_comparisons"]]
    repetitions = 20 if smoke else protocol["paired_system_bootstraps"]
    paired = cluster_intervals(positive, families, systems, predictions, protocol["families"], comparisons, repetitions, protocol["seed"])
    compare(paired, report["paired_intervals"], "joint chemical-system paired bootstrap", deltas)
    effort = []
    for name, keep in (("1", inputs.n_entries.to_numpy() == 1), ("2-4", inputs.n_entries.between(2, 4).to_numpy()), ("5+", inputs.n_entries.to_numpy() >= 5)):
        effort.append({"linked_entries": name, "n": int(keep.sum()), "recorded_positive_fraction": float(positive[keep].mean()) if keep.any() else None,
                       "ranking_diagnostics": {design: stratum_ranking(positive, score, keep, families, protocol["families"])
                                               for design, score in predictions.items()}})
    compare(effort, report["selection_effort_diagnostic_not_model_input"], "n_entries ascertainment diagnostic", deltas)
    chance = [{"family": f, "n": int(np.sum(families == f)), "observed_pu_auc": .5,
               "expected_random_recall_at_ceil_20pct_budget": math.ceil(.2*int(np.sum(families == f)))/int(np.sum(families == f))}
              for f in protocol["families"]]
    source_checked = {}
    source_reference = "executed_commit"
    for name, expected in report["code_manifest"]["source_sha256"].items():
        raw = subprocess.run(["git", "show", f"{report['source_commit']}:{name}"], cwd=root,
                             capture_output=True)
        matched = raw.returncode == 0 and hashlib.sha256(raw.stdout.replace(b"\r\n", b"\n")).hexdigest() == expected
        if not matched and smoke and args.allow_working_tree_source:
            source_reference = "working_tree_synthetic_only"
            path = root/name
            matched = path.is_file() and hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected
        source_checked[name] = matched
    require(all(source_checked.values()), "executed source bytes differ")
    source_file_verified = False
    if args.source_data:
        require(hashlib.sha256(args.source_data.read_bytes()).hexdigest() == protocol["source_sha256"], "pinned raw source data digest differs")
        source_file_verified = True
    result = {"status": "passed", "mode": report["mode"], "report_only": True, "adopted": False,
              "run_id": report["run_id"], "source_commit": report["source_commit"], "protocol_sha256": frozen_hash,
              "paths": {"script": relative(Path(__file__).resolve()), "run_dir": relative(folder)},
              "integrity": {"executed_source_hashes_match": source_checked, "raw_3dsc_source_hash_verified": source_file_verified,
                            "source_reference": source_reference,
                            "fixed_cohort": {"n": len(inputs), "positive": int(positive.sum()), "unlabeled": int((~positive).sum())},
                            "outer_and_inner_system_memberships_verified": True, "outer_training_transforms_and_coefficients_to_scores_verified": True,
                            "report_numeric_comparisons": len(deltas), "maximum_report_numeric_difference": max(deltas, default=0.)},
              "ranking_chance_baselines": {"families": chance, "macro_auc": .5,
                  "macro_expected_random_recall_at_ceil_20pct_budget": float(np.mean([x["expected_random_recall_at_ceil_20pct_budget"] for x in chance]))},
              "outer_metrics": outer_metrics, "paired_system_intervals": paired, "model_audits": model_audits,
              "n_entries_diagnostic": effort,
              "limits": ["P/U means catalog-recorded positive versus not-recorded-positive. This is not true-SC ROC, probability, specificity, experimental negative accuracy, a mechanism, or an H4 p>=0.5 success-rate comparison.",
                         "Frozen v2 records a preflight-only change from pooled inner scores to fold-family AUC -> valid-fold family mean -> equal training-family macro. It is not a post-real-evaluation threshold change.",
                         "Inner memberships and reported AUC aggregation/alpha selection are independently checked, but raw inner validation scores and fitted transform/PCA identities are not exported. Inner AUC and inner train-only transforms cannot be numerically reconstructed from these artifacts.",
                         "Outer training medians/scales/column filtering, PCA eigensystem and term expansion are reconstructed from raw exported inputs; coefficients are used only to check exported held-out scores, not to refit or independently certify the optimization solution.",
                         "Common-term logic, frequencies' denominators and convergence gates are checked. Raw stability bootstrap coefficient matrices/pair draws and expert coefficient vectors are absent, so original frequency and sign estimates cannot be independently refitted.",
                         "Whole-system bootstrap intervals condition on the already inspected families, fixed exploratory predictions and selection protocol; they are not selection-adjusted or new independent validation.",
                         "Random budget recall is ceil(0.2*N)/N within each held family, then a family macro; it is not exactly 20 percent when family sizes are not multiples of five.",
                         "CIF/geometry provenance is bound in the manifest, but raw CIF structures and geometry extraction are not recomputed by this audit. No scientific model module is imported and no models are retrained."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "output": relative(args.output.resolve()), "mode": report["mode"],
                      "macro": {d: x["macro"] for d, x in outer_metrics.items()}, "paired": paired,
                      "maximum_report_numeric_difference": max(deltas, default=0.)}, allow_nan=False))
    return result


def main():
    workspace = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=workspace)
    parser.add_argument("--expected-protocol-hash", default="47b45b22ae94ca4a49f39aeabac2ea1e0b23a000aacfc5c29bb2a680f52abacf")
    parser.add_argument("--source-data", type=Path)
    parser.add_argument("--allow-smoke", action="store_true", help="Audit synthetic plumbing, explicitly not a scientific result")
    parser.add_argument("--allow-working-tree-source", action="store_true", help="Synthetic smoke only: permit matching an uncommitted source manifest")
    parser.add_argument("--output", type=Path, default=workspace/"results"/"validation"/"hurricane7-ci66.json")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
