"""Candidate ensembles which never learn a query's artificial background label.

Background folds are chemical-system folds. For a query in fold k, all ensemble
members exclude background fold k; the labelled training folds vary within it.
The member min/max describe sensitivity to fitted models, not confidence limits.
"""
from __future__ import annotations

import numpy as np


def candidate_predictions(splits, n_pool, fit_model, predict_model, *,
                          pool_folds=None, background_folds=None,
                          pool_systems=None, background_systems=None):
    """Fit/query through callbacks, returning Tc, chance and conditional Tc members.

``fit_model(tr, background_keep, background_fold, training_fold)`` must use only those training
rows. ``predict_model(model, query_indices)`` returns three 1-D arrays in order:
expected Tc, probability, and Tc conditional on superconductivity. Without a
background each training fold supplies one member, as an ordinary fold ensemble.
"""
    splits = list(splits)
    if not splits:
        raise ValueError("an ensemble needs at least one training fold")
    has_background = background_folds is not None
    if has_background:
        pf = np.asarray(pool_folds, int)
        bf = np.asarray(background_folds, int)
        ps, bs = np.asarray(pool_systems), np.asarray(background_systems)
        if len(pf) != n_pool or len(ps) != n_pool or len(bs) != len(bf):
            raise ValueError("background/query fold and system arrays must align")
        if np.any((pf < 0) | (pf >= len(splits))):
            raise ValueError("a query has no held-out background fold")
        n_members = len(splits)
    else:
        n_members = len(splits)
    values = {key: np.full((n_members, n_pool), np.nan) for key in ("tc", "p_sc", "tc_sc")}
    assigned = np.zeros(n_pool, int)
    audit = []
    for k, (tr, _) in enumerate(splits):
        query = np.flatnonzero(pf == k) if has_background else np.arange(n_pool)
        keep = bf != k if has_background else None
        if has_background and np.intersect1d(bs[keep], ps[query]).size:
            raise ValueError("a candidate chemical system occurs in its training background")
        if not len(query):
            continue
        for training_fold in range(len(splits)) if has_background else [k]:
            member_tr = splits[training_fold][0]
            model = fit_model(member_tr, keep, k, training_fold)
            predictions = predict_model(model, query)
            slot = training_fold
            for key, prediction in zip(values, predictions, strict=True):
                prediction = np.asarray(prediction, float)
                if prediction.shape != (len(query),):
                    raise ValueError("candidate prediction shape does not match its query rows")
                values[key][slot, query] = prediction
            assigned[query] += 1
        audit.append({"excluded_background_fold": k if has_background else None,
                      "n_queries": int(len(query)), "members_per_query": n_members,
                      "n_training_background": int(keep.sum()) if has_background else 0})
    if np.any(assigned != n_members):
        raise ValueError("some candidates were not scored by exactly their legal ensemble")
    values["audit"] = audit
    values["members_per_query"] = n_members
    values["method"] = "same-background-fold-training-fold-ensemble" if has_background else "training-fold-ensemble"
    return values
