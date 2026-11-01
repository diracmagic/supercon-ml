"""Hurricane 7: exploratory common-association learning from positive/unlabeled parents.

Scores rank *recorded positive descendants* against unlabeled parents. They are
not superconductivity probabilities, measured-negative labels, or mechanisms.
R0, R1 and R2 are all reported; none can replace the released model.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import hurricane as H
import hurricane3 as H3
import hurricane5 as H5
import hurricane6 as H6
import mechanism_features as MF
import pipeline as P

DESIGNS = ("R0", "R1", "R2")
FLAGS = ("is_metal", "small_gap", "is_magnetic")
EXTRA_NAMES = ("volume_per_atom_angstrom3", *FLAGS)
MIXED_FAMILIES = {
    "mp-1106248": ["iron-based", "other oxide"],
    "mp-1218154": ["cuprate", "other oxide"],
    "mp-1274783": ["cuprate", "other oxide"],
    "mp-5670": ["cuprate", "other oxide"],
}
PROTOCOL = {
    "version": "hurricane7-exploratory-pu-ranking-v2",
    "preflight_amendment": {"superseded_protocol_sha256": "3d82c25a5a893290a6e62c50002d2065f0bf0a8812a08b197520965196c0c352",
                            "reason": "Uncalibrated scores from different inner-fold models cannot be pooled into a single AUC. Compute AUC only within each validation fold and family, then average valid folds within family and the three training families equally.",
                            "no_real_fit_observed": True, "only_synthetic_smoke_before_amendment": True},
    "target": H6.ND.PARENT_TARGET,
    "label_semantics": "P: an original MP parent with an observed positive SuperCon descendant; U: no positive descendant recorded in this snapshot, not measured nonsuperconducting.",
    "source_commit": H.DSC_COMMIT,
    "source_sha256": H.DSC_SHA256,
    "families": list(H.FAMILY_LABEL),
    "mixed_family_exclusions": MIXED_FAMILIES,
    "cohort": {"historical_h6": 619, "historical_h6_positive": 290,
               "h7": 615, "positive": 288, "unlabeled": 327},
    "geometry_version": MF.FEATURE_VERSION,
    "geometry_features": list(MF.FEATURE_NAMES),
    "geometry_config": {"cutoff_scale": 1.25, "sensitivity_fraction": 0.05,
                        "max_atoms": 2048, "max_neighbor_edges": 500000,
                        "min_separation_angstrom": 0.0001},
    "additional_features": list(EXTRA_NAMES),
    "electronic_flags": {"is_metal": "gap<=0.005 eV",
                         "small_gap": "0.005<gap<=1.0 eV",
                         "is_magnetic": "abs(moment/volume)>0.0001 muB/angstrom^3"},
    "excluded_predictors": ["family", "element identities/fractions", "known structure-family templates",
                            "n_entries", "Tc", "database ID", "raw gap/moment/hull/formation energy",
                            "cell volume", "MACE descriptors", "missing-value indicators"],
    "designs": {"R0": "Ridge ranking on main effects",
                "R1": "ElasticNet ranking on main effects, continuous squares and pairwise interactions",
                "R2": "Fixed secondary ablation: train-only geometry PCA8 plus the same four additional features, then the R1 head"},
    "pairs": {"unlabeled_partners_per_positive": 4,
              "within_family_only": True, "different_chemical_systems": True,
              "weights": "Equal eligible training families, then equal eligible positive chemical systems (bootstrap system multiplicities respected), then equal eligible positive rows. Uniformly sample up to four distinct eligible unlabeled systems and one row per system; bootstrap multiplicity weights the system draw."},
    "outer": "Leave each family out; remove its chemical systems from all supervised and auxiliary training.",
    "inner_system_folds": 3,
    "alpha_grid": [0.001, 0.01, 0.1, 1.0],
    "alpha_tie_auc_tolerance": 0.01,
    "l1_ratio": 0.8,
    "ridge_penalty": "The same inner alpha grid as R1/R2; sklearn Ridge alpha = number_of_pairs * selected_alpha",
    "max_iter": 5000,
    "tol": 0.0001,
    "seed": 7,
    "preprocessing": {"minimum_training_finite_fraction": 0.5,
                      "constant_tolerance": 1e-12, "z_clip": 5.0,
                      "imputation": "training median; no missingness indicator"},
    "pca_components": 8,
    "pca_background": "None. PCA8 fits only the corresponding outer/inner training parents; no JARVIS auxiliary cohort, MACE or foundation-model pretraining.",
    "inner_objective": "AUC separately in every inner validation fold x family with both P and U. Equally average valid-fold AUCs within each training family, then equally average all three training families. An alpha is invalid if any training family has no valid fold. Choose largest alpha within 0.01 AUC of best. Never compare scores across inner models; all transformations and term expansion fit inside each training fold.",
    "stability": {"system_bootstraps": 64, "selection_frequency": 0.8,
                  "conditional_sign_agreement": 0.9, "coefficient_tolerance": 1e-8,
                  "training_families_same_sign": 3,
                  "conditioning": "fixed outer-training feature basis and selected alpha; descriptive, not a false-discovery guarantee",
                  "convergence": "Any nonconverged bootstrap or family-specific head makes common-term support inconclusive; report empty common_terms, never treat unconverged coefficients as evidence"},
    "primary": "Macro observed-positive-versus-unlabeled AUC across four held families; it is not true-superconductor ROC AUC.",
    "secondary": {"recall_budget_fraction": 0.2, "ties": "fractional allocation within boundary ties"},
    "paired_comparisons": [["R1", "R0"], ["R2", "R1"]],
    "paired_system_bootstraps": 1000,
    "paired_quantities": ["macro observed-P/U AUC", "macro recall at 20% ranking budget"],
    "failure_semantics": "Pending/failed/inconclusive folds stay explicit, never zero-filled. Empty feature/rule sets may return a finite all-tied score. Any incomplete design has null macro and is excluded from paired comparisons; all requested designs remain in the report.",
    "actual_feedback_training_records": 0,
    "actual_precursor_training_records": 0,
    "feedback": "Freeze each pre-feedback score/target/snapshot first. Only verified target-compatible evidence exports may change training labels. Model predictions and MACE stability are not SC labels; undoped sample nulls are not parent-potential negatives. Previously published but newly ingested literature remains retrospective.",
    "publication": "Exploratory report only: these four families were already inspected in H6. No winner selection, mechanism/causal claim, probability calibration or model release; adopted always false.",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def protocol() -> dict:
    return json.loads(json.dumps(PROTOCOL))


def freeze_protocol(output_dir: Path) -> str:
    """Call before loading the target/cohort or fitting anything."""
    declaration = protocol()
    fingerprint = digest(declaration)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "protocol.json"
    payload = json.dumps(declaration, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise ValueError("frozen H7 protocol changed")
    if not path.exists():
        path.write_text(payload, encoding="utf-8")
    (output_dir / "protocol.sha256").write_text(fingerprint + "\n", encoding="utf-8")
    return fingerprint


def parent_cohort(source: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Use complete class memberships, before formula deduplication, to exclude ambiguity."""
    parents = H5.parent_frame(source)
    classes = source[source["sc_class"].isin(H.FAMILY_OF_CLASS)].copy()
    classes["family"] = classes["sc_class"].map(H.FAMILY_OF_CLASS)
    memberships = classes.groupby(classes["material_id_2"].astype(str))["family"].agg(lambda v: sorted(set(v)))
    mixed = {str(mid): values for mid, values in memberships.items()
             if len(values) > 1 and str(mid) in set(parents["material_id"])}
    if mixed != MIXED_FAMILIES:
        raise ValueError("mixed-family memberships differ from the frozen metadata exclusions")
    excluded = [{"material_id": mid, "memberships": values} for mid, values in sorted(mixed.items())]
    parents = parents[~parents["material_id"].isin(mixed)].reset_index(drop=True)
    parents["full_family_membership"] = [memberships.loc[str(mid)] for mid in parents["material_id"]]
    expected = PROTOCOL["cohort"]
    if (len(parents), int((parents["tc"] > 0).sum()), int((parents["tc"] == 0).sum())) != (
            expected["h7"], expected["positive"], expected["unlabeled"]):
        raise ValueError("parent cohort differs from the frozen H7 snapshot")
    return parents, excluded


def geometry_rows(frame: pd.DataFrame, cache: Path) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    values, volumes, diagnostics = [], [], []
    config = MF.GeometryConfig(**PROTOCOL["geometry_config"])
    for _, row in frame.iterrows():
        result = MF.extract_features(row["atoms"], config=config, cache_dir=cache)
        if result["version"] != PROTOCOL["geometry_version"] or result["names"] != PROTOCOL["geometry_features"]:
            raise ValueError("geometry version or column order differs from the frozen protocol")
        values.append(result["values"])
        atoms = row["atoms"]
        volumes.append(abs(float(np.linalg.det(np.asarray(atoms["lattice_mat"], float)))) / len(atoms["elements"]))
        diagnostics.append({"id": str(row["id"]), **result["diagnostics"]})
    return np.asarray(values, float), np.asarray(volumes, float), diagnostics


def parent_extras(parents, volume_per_atom):
    """Strict feature allowlist: research counts, IDs, targets and raw DFT never enter X."""
    flags = np.asarray([[r["elec"][name] for name in FLAGS] for _, r in parents.iterrows()], float)
    return np.column_stack([np.asarray(volume_per_atom, float), flags])


def prepare_real() -> dict:
    source = H.load_3dsc()
    source_path = Path(os.environ.get("HURRICANE_3DSC", P.CACHE / "3DSC_MP.csv"))
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != PROTOCOL["source_sha256"]:
        raise ValueError("H7 requires the pinned 3DSC snapshot")
    parents, mixed = parent_cohort(source)
    crystal, failures = H6.original_structures(parents)
    if len(crystal) != len(parents):
        raise ValueError("H7 fixed cohort needs every original CIF; no replacement or score-dependent exclusion: "
                         + json.dumps(failures[:5]))
    parents = parents.loc[crystal["parent_index"]].reset_index(drop=True)
    geometry, vpa, diagnostics = geometry_rows(crystal, P.CACHE / "hurricane7_geometry")
    if any(d["status"] != "ok" for d in diagnostics):
        raise ValueError("a fixed-cohort parent has unavailable original geometry")
    extras = parent_extras(parents, vpa)
    parents = parents.assign(system=[H3.chemsys_of(comp) for comp in parents["comp"]])
    return {"parents": parents, "geometry": geometry, "extras": extras,
            "provenance": {"source_sha256": PROTOCOL["source_sha256"], "mixed_excluded": mixed,
                           "original_cifs": crystal.drop(columns=["atoms", "parent_index"]).to_dict("records"),
                           "geometry": diagnostics, "auxiliary_background_rows": 0,
                           "background_used_as_negative": False}}


def prepare_smoke() -> dict:
    """Offline numerical plumbing only; not a scientific cohort or result."""
    rng, rows = np.random.default_rng(PROTOCOL["seed"]), []
    for fi, family in enumerate(PROTOCOL["families"]):
        for i in range(16):
            rows.append({"material_id": f"synthetic-{fi}-{i}", "family": family,
                         "full_family_membership": [family],
                         "system": f"system-{fi}-{i // 2}", "tc": float(i % 3 != 0), "n_entries": 1})
    parents = pd.DataFrame(rows)
    geometry = rng.normal(size=(len(parents), len(MF.FEATURE_NAMES)))
    geometry[:, 0] += (parents["tc"].to_numpy() > 0) * 0.8
    extras = np.column_stack([rng.uniform(5, 30, len(parents)), rng.integers(0, 2, (len(parents), 3))])
    return {"parents": parents, "geometry": geometry, "extras": extras,
            "provenance": {"synthetic": True, "auxiliary_background_rows": 0, "background_used_as_negative": False}}


class TrainingScale:
    """Every median, column decision and scale is fitted on supplied training rows."""
    def fit(self, matrix):
        matrix = np.asarray(matrix, float)
        fraction = np.isfinite(matrix).mean(axis=0)
        self.keep = fraction >= PROTOCOL["preprocessing"]["minimum_training_finite_fraction"]
        chosen = matrix[:, self.keep]
        if chosen.shape[1]:
            self.median = np.nanmedian(np.where(np.isfinite(chosen), chosen, np.nan), axis=0)
            filled = np.where(np.isfinite(chosen), chosen, self.median)
            self.mean, self.scale = filled.mean(axis=0), filled.std(axis=0)
            variable = self.scale > PROTOCOL["preprocessing"]["constant_tolerance"]
            indices = np.flatnonzero(self.keep)[variable]
            self.keep[:] = False
            self.keep[indices] = True
            self.median, self.mean, self.scale = self.median[variable], self.mean[variable], self.scale[variable]
        else:
            self.median = self.mean = self.scale = np.zeros(0)
        return self

    def transform(self, matrix):
        chosen = np.asarray(matrix, float)[:, self.keep]
        filled = np.where(np.isfinite(chosen), chosen, self.median)
        return np.clip((filled - self.mean) / self.scale,
                       -PROTOCOL["preprocessing"]["z_clip"], PROTOCOL["preprocessing"]["z_clip"])


class FeatureBasis:
    def __init__(self, design):
        self.design = design

    def fit(self, geometry, extras):
        if self.design == "R2":
            from sklearn.decomposition import PCA
            pool = geometry
            self.geometry_scale = TrainingScale().fit(pool)
            scaled = self.geometry_scale.transform(pool)
            n = PROTOCOL["pca_components"]
            if min(scaled.shape) < n:
                raise ValueError("R2 has insufficient training geometry for the frozen PCA8")
            self.pca = PCA(n_components=n, svd_solver="full").fit(scaled)
            raw = np.column_stack([self.pca.transform(self.geometry_scale.transform(geometry)), extras])
            names = [f"geometry_PC{i + 1}" for i in range(n)] + list(EXTRA_NAMES)
        else:
            raw = np.column_stack([geometry, extras])
            names = list(MF.FEATURE_NAMES) + list(EXTRA_NAMES)
        self.scale = TrainingScale().fit(raw)
        self.names = [name for name, keep in zip(names, self.scale.keep) if keep]
        self.training_rows = len(geometry)
        return self

    def transform(self, geometry, extras):
        if self.design == "R2":
            geometry = self.pca.transform(self.geometry_scale.transform(geometry))
        return self.scale.transform(np.column_stack([geometry, extras]))


class TermBasis:
    def fit(self, matrix, names, nonlinear):
        self.terms = [(i, None) for i in range(len(names))]
        if nonlinear:
            self.terms += [(i, i) for i, name in enumerate(names) if name not in FLAGS]
            self.terms += [(i, j) for i in range(len(names)) for j in range(i + 1, len(names))
                           if {names[i], names[j]} != {"is_metal", "small_gap"}]
        self.all_names = [names[i] if j is None else f"{names[i]} * {names[j]}" for i, j in self.terms]
        expanded = self._expand(matrix)
        self.scale = TrainingScale().fit(expanded)
        self.names = [name for name, keep in zip(self.all_names, self.scale.keep) if keep]
        return self

    def _expand(self, matrix):
        return np.column_stack([matrix[:, i] if j is None else matrix[:, i] * matrix[:, j]
                                for i, j in self.terms]) if self.terms else np.zeros((len(matrix), 0))

    def transform(self, matrix):
        return self.scale.transform(self._expand(matrix))


def scale_identity(scale):
    return {"keep": scale.keep.tolist(), "median": scale.median.tolist(),
            "mean": scale.mean.tolist(), "std": scale.scale.tolist()}


def basis_identity(fitted):
    features = fitted.features
    result = {"main_features": features.names, "main_scale": scale_identity(features.scale),
              "term_scale": scale_identity(fitted.terms.scale),
              "term_indices_before_train_filter": [list(v) for v in fitted.terms.terms],
              "training_rows": features.training_rows}
    if fitted.design == "R2":
        result["geometry_scale"] = scale_identity(features.geometry_scale)
        result["pca"] = {"components": features.pca.components_.tolist(), "mean": features.pca.mean_.tolist(),
                         "explained_variance": features.pca.explained_variance_.tolist(),
                         "fit_rows": features.training_rows, "auxiliary_rows": 0}
    return result


def pair_data(matrix, positive, families, systems, *, seed, multiplicity=None):
    """Construct observed P>U preferences; no experimental-negative labels are made."""
    positive, families, systems = np.asarray(positive, bool), np.asarray(families), np.asarray(systems)
    multiplicity = np.ones(len(matrix)) if multiplicity is None else np.asarray(multiplicity, float)
    if len(matrix) != len(positive) or not np.isfinite(matrix).all():
        raise ValueError("Pairwise training requires aligned finite transformed features")
    if multiplicity.shape != (len(matrix),) or not np.isfinite(multiplicity).all() or (multiplicity < 0).any():
        raise ValueError("Invalid chemical-system bootstrap multiplicities")
    for system in np.unique(systems):
        if len(np.unique(multiplicity[systems == system])) != 1:
            raise ValueError("Bootstrap multiplicity must be constant across every row of a chemical system")
    rng, differences, weights, used_families = np.random.default_rng(seed), [], [], []
    pair_families, pair_positive_systems = [], []
    for family in sorted(set(families)):
        p = np.flatnonzero((families == family) & positive & (multiplicity > 0))
        u = np.flatnonzero((families == family) & ~positive & (multiplicity > 0))
        if not len(p) or not len(u):
            continue
        u_groups = {system: u[systems[u] == system] for system in sorted(set(systems[u]))}
        p_groups = {system: p[systems[p] == system] for system in sorted(set(systems[p]))}
        before = len(differences)
        family_weights = []
        for index in p:
            choices = [system for system in u_groups if system != systems[index]]
            if not choices:
                continue
            probability = np.array([multiplicity[u_groups[system]].mean() for system in choices])
            number = min(PROTOCOL["pairs"]["unlabeled_partners_per_positive"], len(choices))
            selected = rng.choice(len(choices), size=number, replace=False, p=probability / probability.sum())
            for choice in selected:
                other = int(rng.choice(u_groups[choices[int(choice)]]))
                differences.append(matrix[index] - matrix[other])
                family_weights.append(float(multiplicity[index] / (len(p_groups[systems[index]]) * number)))
                pair_families.append(str(family))
                pair_positive_systems.append(str(systems[index]))
        if len(differences) > before:
            used_families.append(family)
            # Normalize eligible preferences after construction. A positive with
            # no different-system U partner cannot silently downweight a family.
            local = np.asarray(family_weights, float)
            weights.extend((local / local.sum()).tolist())
    if not differences:
        return np.zeros((0, matrix.shape[1])), np.zeros(0), {"families": [], "family_weight_fraction": {},
                                                           "positive_system_weight_fraction_within_family": {}}
    weights = np.asarray(weights, float)
    weights *= len(weights) / weights.sum()
    pair_families, pair_positive_systems = np.asarray(pair_families), np.asarray(pair_positive_systems)
    diagnostic = {"families": list(map(str, used_families)),
                  "family_weight_fraction": {str(f): float(weights[pair_families == f].sum() / weights.sum()) for f in used_families},
                  "positive_system_weight_fraction_within_family": {
                      str(f): {str(s): float(weights[(pair_families == f) & (pair_positive_systems == s)].sum()
                                             / weights[pair_families == f].sum())
                               for s in sorted(set(pair_positive_systems[pair_families == f]))} for f in used_families}}
    return np.asarray(differences), weights, diagnostic


def fit_head(matrix, positive, families, systems, *, design, alpha, seed, multiplicity=None):
    pairs, weights, diagnostic = pair_data(matrix, positive, families, systems, seed=seed, multiplicity=multiplicity)
    if not matrix.shape[1] or not len(pairs):
        return np.zeros(matrix.shape[1]), {"status": "empty", "pairs": len(pairs), **diagnostic}
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import ElasticNet, Ridge
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        if design == "R0":
            head = Ridge(alpha=len(pairs) * alpha, fit_intercept=False)
        else:
            head = ElasticNet(alpha=alpha, l1_ratio=PROTOCOL["l1_ratio"], fit_intercept=False,
                              max_iter=PROTOCOL["max_iter"], tol=PROTOCOL["tol"], selection="cyclic")
        head.fit(pairs, np.ones(len(pairs)), sample_weight=weights)
    converged = not any(issubclass(item.category, ConvergenceWarning) for item in caught)
    coef = np.asarray(head.coef_, float)
    if not np.isfinite(coef).all():
        raise ValueError("Non-finite learned ranking coefficients")
    return coef, {"status": "completed" if converged else "not_converged", "pairs": len(pairs), **diagnostic}


def metrics(positive, scores) -> dict:
    positive, scores = np.asarray(positive, bool), np.asarray(scores, float)
    if not np.isfinite(scores).all():
        raise ValueError("nonfinite ranking score")
    p, u = scores[positive], scores[~positive]
    auc = float(np.mean((p[:, None] > u) + 0.5 * (p[:, None] == u))) if len(p) and len(u) else None
    budget = int(math.ceil(PROTOCOL["secondary"]["recall_budget_fraction"] * len(scores)))
    if budget and len(p):
        boundary = np.sort(scores)[-budget]
        above, tied = scores > boundary, scores == boundary
        fraction = (budget - int(above.sum())) / int(tied.sum())
        recalled = float(positive[above].sum() + fraction * positive[tied].sum())
        recall = recalled / len(p)
    else:
        recalled = recall = None
    return {"n": len(scores), "n_positive": len(p), "n_unlabeled": len(u),
            "observed_pu_auc": auc, "recall_at_budget": recall,
            "budget": budget, "expected_recorded_positives_at_budget": recalled}


class Ranker:
    def __init__(self, design, alpha, seed):
        self.design, self.alpha, self.seed = design, alpha, seed

    def fit(self, geometry, extras, positive, families, systems):
        self.features = FeatureBasis(self.design).fit(geometry, extras)
        base = self.features.transform(geometry, extras)
        self.terms = TermBasis().fit(base, self.features.names, self.design != "R0")
        self.matrix = self.terms.transform(base)
        self.coefficient, self.fit_info = fit_head(self.matrix, positive, families, systems,
                                                  design=self.design, alpha=self.alpha, seed=self.seed)
        self.training_systems = sorted(set(map(str, systems)))
        return self

    def predict(self, geometry, extras):
        scores = self.terms.transform(self.features.transform(geometry, extras)) @ self.coefficient
        if not np.isfinite(scores).all():
            raise ValueError("Non-finite predicted PU ranking scores")
        return scores

    def identity(self):
        return {"design": self.design, "alpha": self.alpha, **self.fit_info,
                "training_systems": self.training_systems, "pca_auxiliary_rows": 0,
                "terms": self.terms.names, "coefficients": self.coefficient.tolist(),
                "feature_basis": basis_identity(self),
                "nonzero_terms": int((np.abs(self.coefficient) > PROTOCOL["stability"]["coefficient_tolerance"]).sum())}


def fit_split(data, design, alpha, train, held_systems, *, seed):
    parents = data["parents"]
    train_systems = parents.iloc[train]["system"].astype(str).to_numpy()
    if set(train_systems) & set(held_systems):
        raise ValueError("held chemical system reached supervised training")
    return Ranker(design, alpha, seed).fit(
        data["geometry"][train], data["extras"][train],
        parents.iloc[train]["tc"].to_numpy(float) > 0, parents.iloc[train]["family"].to_numpy(),
        train_systems)


def select_alpha(data, design, train, outer_held):
    from sklearn.model_selection import GroupKFold
    parents, records = data["parents"], []
    groups = parents.iloc[train]["system"].to_numpy()
    if len(set(groups)) < PROTOCOL["inner_system_folds"]:
        raise ValueError("not enough training chemical systems for frozen inner folds")
    for alpha in PROTOCOL["alpha_grid"]:
        folds = []
        for fold, (a, b) in enumerate(GroupKFold(n_splits=PROTOCOL["inner_system_folds"]).split(train, groups=groups)):
            tr, val = train[a], train[b]
            held = set(outer_held) | set(parents.iloc[val]["system"])
            fitted = fit_split(data, design, alpha, tr, held, seed=PROTOCOL["seed"] + fold)
            score = fitted.predict(data["geometry"][val], data["extras"][val])
            val_rows = parents.iloc[val]
            family_metrics = validation_family_metrics(val_rows, score, sorted(set(parents.iloc[train]["family"])))
            folds.append({"fold": fold, "validation_systems": sorted(set(val_rows["system"])),
                          "training_systems": fitted.training_systems,
                          "training_ids": parents.iloc[tr]["material_id"].astype(str).tolist(),
                          "validation_ids": parents.iloc[val]["material_id"].astype(str).tolist(),
                          "pca_auxiliary_rows": 0,
                          "family_metrics": family_metrics, "status": fitted.fit_info["status"]})
        objective = inner_objective(folds, sorted(set(parents.iloc[train]["family"])))
        records.append({"alpha": alpha, "mean_observed_pu_auc": objective["macro"],
                        "family_mean_fold_auc": objective["families"], "objective_status": objective["status"], "folds": folds})
    valid = [row for row in records if row["mean_observed_pu_auc"] is not None
             and all(f["status"] != "not_converged" for f in row["folds"])]
    if not valid:
        raise ValueError("no valid inner ranking comparison; do not use the held-out family to choose")
    best = max(row["mean_observed_pu_auc"] for row in valid)
    chosen = max(row["alpha"] for row in valid
                 if row["mean_observed_pu_auc"] >= best - PROTOCOL["alpha_tie_auc_tolerance"])
    return chosen, records


def validation_family_metrics(rows, scores, expected_families):
    result = {}
    for family in expected_families:
        mask = rows["family"].to_numpy() == family
        entry = metrics(rows.loc[mask, "tc"].to_numpy() > 0, np.asarray(scores)[mask])
        entry["status"] = "valid" if entry["observed_pu_auc"] is not None else "skipped"
        entry["skip_reason"] = (None if entry["status"] == "valid" else
                                "no_validation_rows" if entry["n"] == 0 else
                                "no_observed_positive" if entry["n_positive"] == 0 else "no_unlabeled")
        result[str(family)] = entry
    return result


def inner_objective(folds, expected_families):
    families = {}
    for family in expected_families:
        values = [fold["family_metrics"][str(family)]["observed_pu_auc"] for fold in folds
                  if fold["family_metrics"][str(family)]["observed_pu_auc"] is not None]
        families[str(family)] = {"n_valid_folds": len(values), "mean_fold_auc": float(np.mean(values)) if values else None}
    valid = all(value["n_valid_folds"] > 0 for value in families.values())
    return {"families": families, "macro": float(np.mean([v["mean_fold_auc"] for v in families.values()])) if valid else None,
            "status": "valid" if valid else "invalid_missing_training_family_auc"}


def stable_terms(fitted, positive, families, systems, *, resamples):
    """Training-only descriptive stability; never selects terms using outer outcomes."""
    tolerance = PROTOCOL["stability"]["coefficient_tolerance"]
    families, systems = np.asarray(families), np.asarray(systems)
    rng, coefficients, fit_states = np.random.default_rng(PROTOCOL["seed"]), [], []
    unique_systems = sorted(set(systems))
    for sample in range(resamples):
        multiplicity = np.zeros(len(systems))
        drawn = rng.choice(unique_systems, size=len(unique_systems), replace=True)
        for group in unique_systems:
            multiplicity[systems == group] = np.sum(drawn == group)
        coef, state = fit_head(fitted.matrix, positive, families, systems, design=fitted.design,
                           alpha=fitted.alpha, seed=PROTOCOL["seed"] + 1000 + sample, multiplicity=multiplicity)
        coefficients.append(coef)
        fit_states.append(state["status"])
    coefficients = np.asarray(coefficients)
    experts, expert_states = [], []
    for family in sorted(set(families)):
        keep = families == family
        coef, state = fit_head(fitted.matrix[keep], np.asarray(positive)[keep], families[keep], systems[keep],
                           design=fitted.design, alpha=fitted.alpha, seed=PROTOCOL["seed"])
        # A constant/undefined term cannot support a cross-family common association.
        variable = fitted.matrix[keep].std(axis=0) > PROTOCOL["preprocessing"]["constant_tolerance"]
        experts.append(np.where(variable, coef, 0.0))
        expert_states.append({"family": str(family), "status": state["status"]})
    experts = np.asarray(experts)
    rows, common = [], []
    all_converged = (fitted.fit_info["status"] != "not_converged" and "not_converged" not in fit_states
                     and all(s["status"] != "not_converged" for s in expert_states))
    for j, term in enumerate(fitted.terms.names):
        selected = (np.abs(coefficients[:, j]) > tolerance) & (np.asarray(fit_states) != "not_converged")
        sign = np.sign(fitted.coefficient[j]) if abs(fitted.coefficient[j]) > tolerance else 0.0
        frequency = float(selected.mean())
        agreement = float(np.mean(np.sign(coefficients[selected, j]) == sign)) if selected.any() and sign else 0.0
        family_signs = [int(np.sign(value)) if abs(value) > tolerance else 0 for value in experts[:, j]]
        supported = (bool(sign) and len(family_signs) == PROTOCOL["stability"]["training_families_same_sign"]
                     and all(value == sign for value in family_signs))
        row = {"term": term, "coefficient": float(fitted.coefficient[j]),
               "selection_frequency": frequency, "conditional_sign_agreement": agreement,
               "training_family_signs": family_signs,
               "common_in_training": bool(all_converged and supported and frequency >= PROTOCOL["stability"]["selection_frequency"]
                                          and agreement >= PROTOCOL["stability"]["conditional_sign_agreement"])}
        rows.append(row)
        if row["common_in_training"]:
            common.append(term)
    return {"resamples": resamples, "status": "completed" if all_converged else "inconclusive_nonconvergence",
            "bootstrap_status_counts": {s: fit_states.count(s) for s in sorted(set(fit_states))},
            "training_family_heads": expert_states, "bootstrap_unit": "chemical system across all training families",
            "basis_conditioning": PROTOCOL["stability"]["conditioning"],
            "common_terms": common, "terms": rows,
            "interpretation": "Standardized association terms, conditional on correlated features and this basis; signs with interactions are not unconditional physical effects."}


def paired_intervals(parents, predictions, *, resamples):
    rng, results = np.random.default_rng(PROTOCOL["seed"]), {}
    groups = sorted(set(parents["system"]))
    blocks = [np.flatnonzero(parents["system"].to_numpy() == group) for group in groups]
    comparisons = [(a, b) for a, b in PROTOCOL["paired_comparisons"] if a in predictions and b in predictions]
    differences = {f"{a}-{b}": {"observed_pu_auc": [], "recall_at_budget": []} for a, b in comparisons}
    for _ in range(resamples):
        selected = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), size=len(blocks))])
        families = parents.iloc[selected]["family"].to_numpy()
        scores_by_design = {}
        valid = True
        for design, scores in predictions.items():
            family_metrics = []
            for family in PROTOCOL["families"]:
                ix = selected[families == family]
                row = metrics(parents.iloc[ix]["tc"].to_numpy() > 0, scores[ix])
                if row["observed_pu_auc"] is None:
                    valid = False
                family_metrics.append(row)
            scores_by_design[design] = {key: float(np.mean([row[key] for row in family_metrics]))
                                        if valid else None for key in ("observed_pu_auc", "recall_at_budget")}
        if not valid:
            continue
        for a, b in comparisons:
            for key in differences[f"{a}-{b}"]:
                differences[f"{a}-{b}"][key].append(scores_by_design[a][key] - scores_by_design[b][key])
    for a, b in PROTOCOL["paired_comparisons"]:
        name = f"{a}-{b}"
        if name not in differences:
            results[name] = {"status": "unavailable_incomplete_design", "requested_resamples": resamples}
            continue
        results[name] = {"status": "completed", "unit": "chemical-system clusters across all held families",
                         "conditioning": "fixed exploratory out-of-family predictions, not a new independent study",
                         "quantities": {}}
        for key, values in differences[name].items():
            original = []
            for design in (a, b):
                original.append(float(np.mean([metrics(parents.loc[parents["family"] == f, "tc"].to_numpy() > 0,
                                                     predictions[design][parents["family"].to_numpy() == f])[key]
                                               for f in PROTOCOL["families"]])))
            results[name]["quantities"][key] = {
                "delta_new_minus_reference": original[0] - original[1],
                "lower95": float(np.quantile(values, .025)) if values else None,
                "upper95": float(np.quantile(values, .975)) if values else None,
                "valid_resamples": len(values), "requested_resamples": resamples}
    return results


def outer_split(parents, family):
    test = np.flatnonzero(parents["family"].to_numpy() == family)
    held = set(parents.iloc[test]["system"].astype(str))
    train = np.flatnonzero((parents["family"].to_numpy() != family)
                           & ~parents["system"].isin(held).to_numpy())
    if not len(test) or not len(train):
        raise ValueError("Empty outer family split")
    if set(parents.iloc[train]["system"]) & held:
        raise AssertionError("Outer chemical-system leakage")
    return train, test, held


def validate_data(data, *, smoke):
    parents, geometry, extras = data["parents"], np.asarray(data["geometry"], float), np.asarray(data["extras"], float)
    if geometry.shape != (len(parents), len(MF.FEATURE_NAMES)) or extras.shape != (len(parents), len(EXTRA_NAMES)):
        raise ValueError("Parent features do not match the frozen feature columns")
    if np.isinf(geometry).any() or np.isinf(extras).any():
        raise ValueError("Infinite source features are invalid; missing source features must be NaN")
    if parents["material_id"].duplicated().any() or parents["material_id"].isin(MIXED_FAMILIES).any():
        raise ValueError("Duplicate or mixed-family parent reached the fixed cohort")
    for _, row in parents.iterrows():
        if row["family"] not in PROTOCOL["families"] or row["full_family_membership"] != [row["family"]]:
            raise ValueError("Complete original family membership is not isolated")
    if set(parents["family"]) != set(PROTOCOL["families"]):
        raise ValueError("All four frozen families are required")
    tc = parents["tc"].to_numpy(float)
    if not np.isfinite(tc).all() or (tc < 0).any():
        raise ValueError("Invalid observed-positive/unlabeled targets")
    if not smoke and (len(parents), int((tc > 0).sum()), int((tc == 0).sum())) != (615, 288, 327):
        raise ValueError("Real parent counts differ from the frozen cohort")
    if (np.isfinite(extras[:, 0]) & (extras[:, 0] <= 0)).any():
        raise ValueError("Volume must be per atom and positive when observed")
    finite_flags = extras[:, 1:][np.isfinite(extras[:, 1:])]
    if not np.isin(finite_flags, [0., 1.]).all():
        raise ValueError("Safe electronic flags must be categorical 0/1 or unknown")
    return parents, geometry, extras


def feature_coverage(parents, geometry, extras):
    matrix = np.column_stack([geometry, extras])
    names = list(MF.FEATURE_NAMES) + list(EXTRA_NAMES)
    result = {}
    for family in ["all", *PROTOCOL["families"]]:
        keep = np.ones(len(parents), bool) if family == "all" else parents["family"].to_numpy() == family
        result[family] = {"n": int(keep.sum()), "features": {
            name: {"finite_rows": int(np.isfinite(matrix[keep, j]).sum()),
                   "finite_fraction": float(np.isfinite(matrix[keep, j]).mean()) if keep.any() else None}
            for j, name in enumerate(names)}}
    return result


def stratum_metrics(parents, scores, keep):
    """A held family's rank scale is comparable only within that family model."""
    keep = np.asarray(keep, bool)
    by_family = {}
    for family in PROTOCOL["families"]:
        mask = keep & (parents["family"].to_numpy() == family)
        by_family[family] = metrics(parents.loc[mask, "tc"].to_numpy() > 0, scores[mask])
    summary = {}
    for key in ("observed_pu_auc", "recall_at_budget"):
        available = [f for f, values in by_family.items() if values[key] is not None]
        summary[key] = {"macro": float(np.mean([by_family[f][key] for f in available])) if available else None,
                        "n_defined_families": len(available), "defined_families": available}
    return {"per_family": by_family, "macro_among_defined_families": summary,
            "cross_family_score_pooling": False, "primary_metric": False}


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _status(path, value):
    try:
        _write_json(path, value)
    except OSError as error:
        warnings.warn(f"H7 optional status write failed: {error}", RuntimeWarning)


def run_identity():
    now = dt.datetime.now(dt.timezone.utc)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=P.ROOT, check=True,
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {"run_at": now.isoformat(), "run_id": now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + str(time.time_ns()),
            "source_commit": commit, "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}


def code_manifest():
    files = [Path(__file__), Path(MF.__file__), Path(H.__file__), Path(H3.__file__),
             Path(H5.__file__), Path(H6.__file__), Path(P.__file__)]
    return {"hash_rule": "SHA256 of source bytes with CRLF replaced by LF only",
            "source_sha256": {str(p.relative_to(P.ROOT)).replace("\\", "/"):
                              hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in files}}


def run(*, smoke=False, output_dir: Path | None = None) -> dict:
    identity = run_identity()
    output_dir = Path(output_dir) if output_dir is not None else P.RESULTS / "hurricane7" / identity["run_id"]
    fingerprint = freeze_protocol(output_dir)
    started = time.perf_counter()
    report = {**identity, "output_dir": str(output_dir), "status": "preparing", "round": 7,
              "report_only": True, "adopted": False, "mode": "synthetic_smoke_not_scientific" if smoke else "exploratory_pu_ranking",
              "protocol_sha256": fingerprint, "protocol_hash_rule": "SHA256 of canonical sorted compact JSON, no trailing newline",
              "protocol": protocol(), "code_manifest": code_manifest(),
              "designs": {d: {"status": "pending"} for d in DESIGNS},
              "actual_feedback_training_records": 0, "actual_precursor_training_records": 0,
              "versions": {}, "failures": [],
              "limitations": ["The four families were repeatedly inspected in H6; this is exploratory, not independent confirmation.",
                              "Historical positive ascertainment is not random. P/U ranking can learn research attention rather than superconducting mechanisms.",
                              "Unlabeled parents are not measured negatives; no physical probability, Brier score, specificity or calibrated interval is claimed.",
                              "Geometry, composition-correlated radii, missingness and conditional interaction signs do not establish causal or universal pairing rules.",
                              "PCA8 is fitted only on training-parent geometry. It is a representation ablation, not auxiliary or foundation-model pretraining.",
                              "PCA directions are refitted in each split; identically named PC terms across outer folds are different bases and cannot be merged into one physical rule.",
                              "Stable terms condition on the outer training basis and chosen alpha; they are diagnostics, not a refitted stable-only predictor or a false-discovery guarantee.",
                              "Newly ingested old literature is retrospective; only timestamped pre-feedback predictions can support prospective validation."]}
    for package in ("numpy", "pandas", "scikit-learn", "ase", "pymatgen", "jarvis-tools"):
        try:
            report["versions"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["versions"][package] = None
    _write_json(output_dir / "run.json", {**identity, "protocol_sha256": fingerprint, "code_manifest": report["code_manifest"]})
    _write_json(output_dir / "report.json", report)
    try:
        data = prepare_smoke() if smoke else prepare_real()
        parents, geometry, extras = validate_data(data, smoke=smoke)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        report.update(status="failed_preparation", failures=[{"stage": "preparation", "reason": f"{type(error).__name__}: {error}"}])
        _write_json(output_dir / "report.json", report)
        raise
    coverage = feature_coverage(parents, geometry, extras)
    metadata = [{"material_id": str(r["material_id"]), "family": str(r["family"]), "system": str(r["system"]),
                 "observed_positive": bool(r["tc"] > 0), "n_entries": int(r["n_entries"]),
                 "full_family_membership": r["full_family_membership"]} for _, r in parents.iterrows()]
    inputs = pd.DataFrame(np.column_stack([geometry, extras]), columns=list(MF.FEATURE_NAMES) + list(EXTRA_NAMES))
    inputs = pd.concat([pd.DataFrame(metadata), inputs], axis=1)
    inputs.to_csv(output_dir / "input-parents.csv", index=False, float_format="%.17g")
    input_manifest = {"source_data_sha256": PROTOCOL["source_sha256"], "cohort_metadata_sha256": digest(metadata),
                      "input_csv_sha256": hashlib.sha256((output_dir / "input-parents.csv").read_bytes()).hexdigest(),
                      "input_csv_hash_rule": "SHA256 of exact emitted bytes", "coverage": coverage,
                      "provenance": data["provenance"], "auxiliary_background_rows": 0}
    _write_json(output_dir / "input-manifest.json", input_manifest)
    report["input_manifest_sha256"] = digest(input_manifest)
    report["feature_coverage_by_family"] = coverage
    report["cohort"] = {"n": len(parents), "n_positive": int((parents["tc"] > 0).sum()), "n_unlabeled": int((parents["tc"] == 0).sum()),
                         "historical_h6_denominator": 619, "historical_h6_positive": 290,
                         "mixed_exclusions": data["provenance"].get("mixed_excluded", []), "historical_h6_not_rescored": True}
    prediction = {design: np.full(len(parents), np.nan) for design in DESIGNS}
    lofo, fits = {design: [] for design in DESIGNS}, []
    fold_manifest = []
    report["status"] = "running"
    for family in PROTOCOL["families"]:
        train, test, held = outer_split(parents, family)
        fold_manifest.append({"held_family": family, "held_systems": sorted(held),
                              "training_systems": sorted(set(parents.iloc[train]["system"])),
                              "training_ids": parents.iloc[train]["material_id"].astype(str).tolist(),
                              "test_ids": parents.iloc[test]["material_id"].astype(str).tolist(),
                              "full_membership_held_family_training_rows": int(sum(family in m for m in parents.iloc[train]["full_family_membership"])),
                              "training_feature_coverage": feature_coverage(parents.iloc[train], geometry[train], extras[train])})
        _write_json(output_dir / "folds.json", fold_manifest)
        for design in DESIGNS:
            P.log(f"H7 {design}: held family={family}; training={len(train)}; test={len(test)}")
            try:
                alpha, inner = select_alpha(data, design, train, held)
                fitted = fit_split(data, design, alpha, train, held, seed=PROTOCOL["seed"])
                if fitted.fit_info["status"] == "not_converged":
                    raise RuntimeError("Outer ranking head did not converge")
                scores = fitted.predict(geometry[test], extras[test])
                stability = None if design == "R0" else stable_terms(
                    fitted, parents.iloc[train]["tc"].to_numpy() > 0,
                    parents.iloc[train]["family"].to_numpy(), parents.iloc[train]["system"].to_numpy(),
                    resamples=4 if smoke else PROTOCOL["stability"]["system_bootstraps"])
                prediction[design][test] = scores
                lofo[design].append({"family": family, "status": "completed", **metrics(parents.iloc[test]["tc"].to_numpy() > 0, scores)})
                fits.append({"design": design, "held_family": family, "held_systems": sorted(held),
                             "model": fitted.identity(), "inner_selection": inner, "stability": stability,
                             "dropped_main_features": [n for n in list(MF.FEATURE_NAMES) + list(EXTRA_NAMES) if n not in fitted.features.names]
                             if design != "R2" else [n for n, k in zip(MF.FEATURE_NAMES, fitted.features.geometry_scale.keep) if not k]})
            except (ValueError, RuntimeError, FloatingPointError) as error:
                failure = {"design": design, "family": family, "status": "failed", "reason": f"{type(error).__name__}: {error}"}
                lofo[design].append(failure)
                report["failures"].append(failure)
            report.update(lofo=lofo, fits=fits)
            _write_json(output_dir / "report.json", report)
            _status(output_dir / "status.json", {"design": design, "held_family": family, "protocol_sha256": fingerprint})
    macro, complete_predictions = {}, {}
    for design in DESIGNS:
        complete = np.isfinite(prediction[design]).all()
        report["designs"][design] = {"status": "completed" if complete else "incomplete"}
        macro[design] = {key: float(np.mean([row[key] for row in lofo[design]])) if complete else None
                         for key in ("observed_pu_auc", "recall_at_budget")}
        if complete:
            complete_predictions[design] = prediction[design]
    intervals = paired_intervals(parents, complete_predictions,
                                 resamples=20 if smoke else PROTOCOL["paired_system_bootstraps"])
    rows = []
    for design, scores in prediction.items():
        for i, parent in parents.iterrows():
            rows.append({"design": design, "material_id": str(parent["material_id"]),
                         "family": str(parent["family"]), "chemsys": str(parent["system"]),
                         "observed_positive": bool(parent["tc"] > 0), "unlabeled": bool(parent["tc"] <= 0),
                         "n_entries": int(parent["n_entries"]), "full_family_membership": json.dumps(parent["full_family_membership"]),
                         "geometry_finite_feature_count": int(np.isfinite(geometry[i]).sum()),
                         "catalog_rank_score": float(scores[i]) if np.isfinite(scores[i]) else None,
                         "prediction_status": "available" if np.isfinite(scores[i]) else "failed"})
    effort = []
    for name, keep in (("1", parents["n_entries"] == 1),
                       ("2-4", parents["n_entries"].between(2, 4)),
                       ("5+", parents["n_entries"] >= 5)):
        strata = {"linked_entries": name, "n": int(keep.sum()),
                  "recorded_positive_fraction": float((parents.loc[keep, "tc"] > 0).mean()) if keep.any() else None,
                  "ranking_diagnostics": {}}
        for design, scores in complete_predictions.items():
            strata["ranking_diagnostics"][design] = stratum_metrics(parents, scores, keep)
        effort.append(strata)
    report.update(status="completed" if len(complete_predictions) == len(DESIGNS) else "incomplete", macro=macro,
                  paired_intervals=intervals, selection_effort_diagnostic_not_model_input=effort,
                  smoke_overrides={"stability_resamples": 4, "paired_resamples": 20} if smoke else None,
                  seconds=round(time.perf_counter() - started, 3))
    _write_json(output_dir / "report.json", report)
    pd.DataFrame(rows).to_csv(output_dir / "parents.csv", index=False)
    _status(output_dir / "status.json", {"status": report["status"], "protocol_sha256": fingerprint})
    P.log(f"H7 exploratory report: {output_dir / 'report.json'}; adopted=false")
    if report["status"] != "completed":
        raise RuntimeError("H7 incomplete; explicit failures and partial forecasts retained in report.json/parents.csv")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--protocol", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.protocol:
        out = args.output_dir or P.RESULTS / "hurricane7" / run_identity()["run_id"]
        print(freeze_protocol(out))
    else:
        run(smoke=args.smoke, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
