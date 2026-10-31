"""Storm, search round 5: how sure is Storm? A 90% range around every prediction.

Storm 4.0 gives one number per material. To choose materials for DFT or experiment, the range matters as much as the
number: a material predicted at 12 K with a range of 10-14 K is a better bet than one predicted at 15 K with a range
of 2-30 K. In round 5 the AI agent (Claude) proposed ways to put a 90% range around Storm 4.0's prediction; the
prediction itself does not change.

Every candidate is scored on the same five folds as every Storm round (GroupKFold by chemical system on Alexandria,
against the computed Allen-Dynes Tc), and every range is set by conformal prediction across folds: for the materials of
one fold, the width comes from the out-of-fold errors in the other four, so a range never uses its own fold's answers.

    U0  one width for every material (the reference)
    U1  the width scaled by how much Storm 4.0's members disagree
    U2  one width on log(1 + Tc), so that the range grows with Tc
    U3  log(1 + Tc), scaled by the members' disagreement
    U4  gradient-boosted 5% and 95% quantiles from Storm's inputs and the members' predictions, conformalised (CQR)
    U5  the same on log(1 + Tc)
    U6  one width for each range of predicted Tc (Mondrian conformal), so that each range of predictions gets 90%

Scores: the interval score at 90% (the width plus 20 times any miss, in K; lower is better; Gneiting and Raftery,
J. Am. Stat. Assoc. 102, 359 (2007)), the coverage (the share of held-out materials whose Tc falls inside the range;
90% is wanted) and the coverage for the top 10% of Tc, where screening looks.

A design is released as Storm 5.0 if its coverage is within 2 points of 90% overall, at least 80% for the top 10% of Tc,
and its interval score beats U0 on average and in at least 4 of the 5 folds.

The members' out-of-fold predictions are round 4's: Storm 1.0 is retrained on the same folds (about a minute) and the
graph network's saved predictions are reused (results/gnn_round2_final_predictions.csv); without them the round stops,
because retraining the network belongs to its own stages. Ranges against measured Tc, after round 3's calibration on
the matched 3DSC materials, are reported too but are not used to choose.

Run from the repository root:  python ml/pipeline.py storm5
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

import hurricane as H
import pipeline as P
import storm3 as S3
import storm4 as S4

ROUND = 5
VERSION = "5.0"
ALPHA = 0.10          # 90% ranges
COVER_TOL = 0.02      # the coverage must be within 2 points of 90%
TAIL_MIN = 0.80       # and at least 80% for the top 10% of Tc
QPARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0)

# id, name, kind, on log(1 + Tc)
CANDIDATES = [
    ("U0", "One width for every material", "constant", False),
    ("U1", "Width scaled by how much the members disagree", "spread", False),
    ("U2", "One width on log(1 + Tc), so the range grows with Tc", "constant", True),
    ("U3", "Log(1 + Tc), width scaled by the members' disagreement", "spread", True),
    ("U4", "Gradient-boosted 5% and 95% quantiles, conformalised", "cqr", False),
    ("U5", "Gradient-boosted quantiles on log(1 + Tc), conformalised", "cqr", True),
    ("U6", "One width for each range of predicted Tc", "mondrian", False),
]
BINS = (0.5, 0.75, 0.9, 0.97)   # U6: predicted-Tc quantiles that split the materials into five ranges
# Short-lived or man-made elements are left out of the examples: nobody would make such a superconductor, and "Tc"
# (technetium) would read as the critical temperature. Thorium and uranium, which occur in nature, stay.
RADIOACTIVE = {"Tc", "Pm", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Pa", "Np", "Pu", "Am", "Cm"}


def cq(scores, alpha: float = ALPHA) -> float:
    """The conformal quantile of a set of scores: the ceil((n + 1)(1 - alpha))-th smallest."""
    s = np.sort(np.asarray(scores, float))
    if not len(s):
        return float("inf")
    k = int(np.ceil((len(s) + 1) * (1 - alpha)))
    return float(s[min(k, len(s)) - 1])


def _fwd(x, log: bool):
    x = np.asarray(x, float)
    return np.log1p(np.clip(x, 0, None)) if log else x


def _back(lo, hi, log: bool):
    if log:
        lo, hi = np.expm1(lo), np.expm1(hi)
    return np.clip(lo, 0, None), np.maximum(hi, np.clip(lo, 0, None))


def ranges_simple(y, yhat, members, folds, kind: str, log: bool):
    """Split-conformal ranges across folds: one width (constant) or a width scaled by the members' spread."""
    z, zh = _fwd(y, log), _fwd(yhat, log)
    sd = np.column_stack([_fwd(m, log) for m in members]).std(axis=1)
    lo, hi = np.zeros(len(z)), np.zeros(len(z))
    every = np.arange(len(z))
    for te in folds:
        cal = np.setdiff1d(every, te)
        if kind == "constant":
            w = np.full(len(te), cq(np.abs(z[cal] - zh[cal])))
        else:
            beta = float(np.median(sd[cal])) + 1e-6   # keeps the width finite where the members agree exactly
            w = cq(np.abs(z[cal] - zh[cal]) / (sd[cal] + beta)) * (sd[te] + beta)
        lo[te], hi[te] = zh[te] - w, zh[te] + w
    return _back(lo, hi, log)


def ranges_mondrian(y, yhat, folds, bins=BINS):
    """Split-conformal ranges with one width per range of predicted Tc (Mondrian conformal prediction, Vovk et al.,
    Algorithmic Learning in a Random World, 2005): the ranges' edges and widths come from the other folds."""
    lo, hi = np.zeros(len(y)), np.zeros(len(y))
    every = np.arange(len(y))
    for te in folds:
        cal = np.setdiff1d(every, te)
        edges = np.quantile(yhat[cal], bins)
        bc, bt = np.searchsorted(edges, yhat[cal], side="right"), np.searchsorted(edges, yhat[te], side="right")
        every_err = np.abs(y[cal] - yhat[cal])
        for b in range(len(bins) + 1):
            err = every_err[bc == b]
            w = cq(err if len(err) >= 10 else every_err)   # a nearly empty range falls back to one width
            m = te[bt == b]
            lo[m], hi[m] = yhat[m] - w, yhat[m] + w
    return _back(lo, hi, False)


def _qfit(X, z, q: float, seed: int):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, random_state=seed, **QPARAMS).fit(X, z)


def ranges_cqr(X, y, folds, log: bool):
    """Conformalised quantile regression (Romano, Patterson and Candès, NeurIPS 2019) across folds. For a test fold, the
    5% and 95% quantile models are fitted on the other folds; the correction comes from inner rounds in which each of
    those folds is predicted by quantile models fitted on the remaining ones, so the test fold is never touched."""
    z = _fwd(y, log)
    lo, hi = np.zeros(len(z)), np.zeros(len(z))
    for k, te in enumerate(folds):
        others = [j for j in range(len(folds)) if j != k]
        scores = []
        for j in others:
            fit = np.concatenate([folds[i] for i in others if i != j])
            a = _qfit(X[fit], z[fit], ALPHA / 2, P.SEED + 10 * k + j).predict(X[folds[j]])
            b = _qfit(X[fit], z[fit], 1 - ALPHA / 2, P.SEED + 10 * k + j).predict(X[folds[j]])
            a, b = np.minimum(a, b), np.maximum(a, b)
            scores.append(np.maximum(a - z[folds[j]], z[folds[j]] - b))
        corr = cq(np.concatenate(scores))
        tr = np.concatenate([folds[i] for i in others])
        a = _qfit(X[tr], z[tr], ALPHA / 2, P.SEED + 10 * k).predict(X[te])
        b = _qfit(X[tr], z[tr], 1 - ALPHA / 2, P.SEED + 10 * k).predict(X[te])
        lo[te], hi[te] = np.minimum(a, b) - corr, np.maximum(a, b) + corr
    return _back(lo, hi, log)


def score(y, lo, hi, yhat, folds, tail: float) -> dict:
    inside = (y >= lo) & (y <= hi)
    width = hi - lo
    isc = width + (2 / ALPHA) * (np.clip(lo - y, 0, None) + np.clip(y - hi, 0, None))
    top, ptop = y >= tail, yhat >= np.quantile(yhat, 0.9)   # the tenth with the highest Tc, and with the highest predictions
    return {"coverage": float(inside.mean()), "tail_coverage": float(inside[top].mean()) if top.any() else None,
            "predicted_top_coverage": float(inside[ptop].mean()) if ptop.any() else None,
            "mean_width": float(width.mean()), "median_width": float(np.median(width)),
            "tail_median_width": float(np.median(width[top])) if top.any() else None,
            "interval_score": float(isc.mean()),
            "fold_interval_score": [float(isc[te].mean()) for te in folds],
            "fold_coverage": [float(inside[te].mean()) for te in folds]}


def storm4_members(s_tc, gn: dict) -> tuple[str, list, np.ndarray] | None:
    """Storm 4.0's members and prediction, as released in round 4 (None if round 4 released nothing)."""
    path = P.RESULTS / "storm_round4.json"
    if not path.exists():
        return None
    r4 = json.loads(path.read_text())
    if not r4.get("adopted"):
        return None
    gn_ad = P.allen_dynes(np.clip(gn["lambda"], 0, None), np.clip(gn["wlog"], 0, None))
    best = r4["best"]
    if best == "S1":
        return best, [s_tc, gn["tc"]], 0.5 * (s_tc + gn["tc"])
    if best == "S2":
        m = [s_tc, np.clip(gn["tc"], 0, None)]
        return best, m, np.expm1(0.5 * (np.log1p(m[0]) + np.log1p(m[1])))
    if best == "S3":
        return best, [s_tc, gn["tc"], gn_ad], (s_tc + gn["tc"] + gn_ad) / 3.0
    return None


def measured_ranges(train, feats, yhat, lam, wlog) -> dict | None:
    """Ranges against measured Tc: round 3's calibration of Storm 4.0 on the matched 3DSC materials, out of fold, with
    a cross-fold conformal width (one width, and one width on log(1 + Tc)). Reported, not used to choose."""
    m = S3.matched_set(train, feats, yhat, lam, wlog)
    if len(m) < 30:
        return None
    cal = S4.calibrate(m)
    p = cal["oof"][cal["best"]["id"]]
    y = m["tc_exp"].to_numpy(float)
    folds = [te for _, te in cal["folds"]]
    out = {"n": int(len(m)), "n_sc": cal["n_sc"], "method": cal["best"]["name"], "mae": round(cal["best"]["mae"], 2)}
    by_key = {}
    for f, v in zip(m["formula"], p):   # composition -> calibrated out-of-fold prediction, for the worked examples
        try:
            by_key[P._composition_key(H.parse_formula(f))] = float(v)
        except ValueError:
            pass
    out["_by_key"] = by_key
    for key, log in (("one_width", False), ("log_width", True)):
        lo, hi = ranges_simple(y, p, [p], folds, "constant", log)
        s = score(y, lo, hi, p, folds, float(np.quantile(y, 0.9)))
        out[key] = {"coverage": round(s["coverage"], 3), "median_width": round(s["median_width"], 2),
                    "interval_score": round(s["interval_score"], 2),
                    "tail_coverage": None if s["tail_coverage"] is None else round(s["tail_coverage"], 3)}
    return out


# Well-known conventional superconductors that the app's Predict Tc animation walks through, in this order
WORKED = ("Nb3Sn", "MgB2", "NbN", "V3Si", "Pb", "Nb")


def worked_examples(train, y, s_tc, gn: dict, gn_ad, yhat, lo, hi, cal_by_key: dict) -> list:
    """Each step of Storm's prediction for a few graded materials (data/experiments.json), for the app's animation:
    the trees, the graph network and its lambda, omega_log and Allen-Dynes Tc, their average (Storm 4.0), the 90% range
    and the calibrated measured-Tc estimate. Out-of-fold throughout. Where Alexandria holds several structures of the
    same composition, the one whose computed Tc is the median is shown, so that every number belongs to one structure."""
    if not P.EXPERIMENTS.exists():
        return []
    ex = {e["name"]: e for e in json.loads(P.EXPERIMENTS.read_text(encoding="utf-8"))["materials"]}
    index = {}
    for i, atoms in enumerate(train["atoms"]):
        u, c = np.unique(list(atoms["elements"]), return_counts=True)
        index.setdefault(P._composition_key(dict(zip(u, c))), []).append(i)
    out = []
    for name in WORKED:
        e = ex.get(name)
        if not e or e.get("tc_exp") is None:
            continue
        key = P._composition_key(e["composition"])
        idx = index.get(key, [])
        if not idx:
            continue
        i = sorted(idx, key=lambda j: y[j])[len(idx) // 2]
        cal = cal_by_key.get(key)
        out.append({"name": name, "tc_exp": e["tc_exp"], "status": e["status"], "n_structures": len(idx),
                    "dft_tc": round(float(y[i]), 2), "trees": round(float(s_tc[i]), 2), "gnn": round(float(gn["tc"][i]), 2),
                    "gnn_lambda": round(float(gn["lambda"][i]), 3), "gnn_wlog": round(float(gn["wlog"][i]), 1),
                    "gnn_ad": round(float(gn_ad[i]), 2), "storm4": round(float(yhat[i]), 2),
                    "lo": round(float(lo[i]), 2), "hi": round(float(hi[i]), 2),
                    "calibrated": None if cal is None else round(cal, 2), "mu_star": P.MU_STAR})
    return out


def _pct(v) -> str:
    return "n/a" if v is None else f"{v:.1%}"


def _name(atoms: dict) -> str:
    u, c = np.unique(list(atoms["elements"]), return_counts=True)
    return S3.pretty(dict(zip(u, c)))


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    _, frames = P.load_clean()
    train = frames["alexandria"]
    table = P.element_table(sorted({e for els in train["elements"] for e in els}))
    base = P.featurize(train, table)
    phys = P.physics_features(train, base)
    D = np.hstack([base.to_numpy(float), phys.to_numpy(float)])
    groups = train["chemsys"].to_numpy()
    y, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(D, y, groups))
    folds = [te for _, te in splits]
    fold_of = np.zeros(len(y), int)
    for k, te in enumerate(folds):
        fold_of[te] = k + 1
    _, design, gnn_version, saved, seeds = S4.gnn_design()
    gn = S4.saved_gnn(saved, train, fold_of)
    if gn is None:
        P.log(f"Storm round 5 needs the graph network's saved out-of-fold predictions ({saved.name}); run its stages first")
        return
    s_tc = np.clip(P.cv_predict_stage(D, y, splits, P.STORM1_PARAMS), 0, None)
    s_lam = P.cv_predict_stage(D, y_lam, splits, P.STORM1_PARAMS, log_target=False)
    s_wlog = P.cv_predict_stage(D, y_wlog, splits, P.STORM1_PARAMS, log_target=False)
    got = storm4_members(s_tc, gn)
    if got is None:
        P.log("Storm round 5 puts ranges around Storm 4.0, which round 4 has not released")
        return
    design4, members, yhat = got
    check = P.RESULTS / "storm_round4_predictions.csv"
    if check.exists():   # the same folds and models should give round 4's numbers again
        old = pd.read_csv(check).drop_duplicates("id").set_index("id")
        old.index = old.index.astype(str)
        ids = train["id"].astype(str)
        if ids.isin(old.index).all():
            P.log(f"Storm 4.0 recomputed: largest difference from round 4's saved predictions "
                  f"{float(np.max(np.abs(old.loc[ids, 'tc_pred_best'].to_numpy(float) - yhat))):.4f} K")
    P.log(f"Storm 4.0 ({design4}) out of fold: Tc MAE {float(np.mean(np.abs(yhat - y))):.3f} K on {len(y):,} materials "
          f"({time.time() - t_start:.0f} s)")

    zm = np.column_stack(members)
    X = np.hstack([D, zm, yhat[:, None], zm.std(axis=1)[:, None], np.log1p(np.clip(zm, 0, None)).std(axis=1)[:, None]])
    tail = float(np.quantile(y, 0.9))
    board, ranges = [], {}
    for cid, name, kind, log in CANDIDATES:
        t0 = time.time()
        if kind == "cqr":
            lo, hi = ranges_cqr(X, y, folds, log)
        elif kind == "mondrian":
            lo, hi = ranges_mondrian(y, yhat, folds)
        else:
            lo, hi = ranges_simple(y, yhat, members, folds, kind, log)
        ranges[cid] = (lo, hi)
        board.append({"id": cid, "name": name, "kind": kind, "log": log, **score(y, lo, hi, yhat, folds, tail),
                      "seconds": round(time.time() - t0, 1)})
    ref = board[0]
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_interval_score"], ref["fold_interval_score"])))
        P.log(f"{r['id']} {r['name']}: interval score {r['interval_score']:.2f} K, better than one width in "
              f"{r['folds_better']}/{P.N_FOLDS} folds; coverage {r['coverage']:.1%} (top 10% of Tc "
              f"{r['tail_coverage']:.1%}; top 10% of predictions {_pct(r['predicted_top_coverage'])}), median width "
              f"{r['median_width']:.2f} K, mean {r['mean_width']:.2f} K ({r['seconds']} s)")

    def honest(r):
        return abs(r["coverage"] - (1 - ALPHA)) <= COVER_TOL and (r["tail_coverage"] or 0) >= TAIL_MIN
    eligible = [r for r in board if r["id"] != "U0" and honest(r) and r["interval_score"] < ref["interval_score"]
                and r["folds_better"] >= P.ADOPT_FOLDS]
    best = min(eligible or board[1:], key=lambda r: r["interval_score"])
    adopted = bool(eligible)
    lo, hi = ranges[best["id"]]

    feats = phys.assign(n_elements=base["n_elements"])
    measured = None
    try:
        measured = measured_ranges(train, feats, yhat, 0.5 * (s_lam + gn["lambda"]), 0.5 * (s_wlog + gn["wlog"]))
    except Exception as err:   # the 3DSC download is optional for this round
        P.log(f"ranges against measured Tc skipped: {err}")
    if measured:
        P.log(f"against measured Tc ({measured['n']} matched materials, {measured['method']}, MAE {measured['mae']} K): "
              f"one width covers {measured['one_width']['coverage']:.1%} with a median width of "
              f"{measured['one_width']['median_width']} K; on log(1 + Tc) {measured['log_width']['coverage']:.1%} and "
              f"{measured['log_width']['median_width']} K")

    cal_by_key = measured.pop("_by_key", {}) if measured else {}
    gn_ad = P.allen_dynes(np.clip(gn["lambda"], 0, None), np.clip(gn["wlog"], 0, None))
    worked = worked_examples(train, y, s_tc, gn, gn_ad, yhat, lo, hi, cal_by_key)
    for w in worked:
        P.log(f"worked example {w['name']}: computed {w['dft_tc']} K; trees {w['trees']} K, network {w['gnn']} K, network "
              f"lambda {w['gnn_lambda']} and omega_log {w['gnn_wlog']} K -> Allen-Dynes {w['gnn_ad']} K; Storm 4.0 "
              f"{w['storm4']} K, 90% range {w['lo']}-{w['hi']} K; calibrated {w['calibrated']} K; measured {w['tc_exp']} K")
    examples, seen = [], set()
    for i in np.argsort(-yhat):   # the five highest predictions, one per composition, without short-lived elements
        if set(train["atoms"].iloc[i]["elements"]) & RADIOACTIVE:
            continue
        name = _name(train["atoms"].iloc[i])
        if name in seen:
            continue
        seen.add(name)
        examples.append({"name": name, "id": str(train["id"].iloc[i]), "tc": round(float(y[i]), 2),
                         "pred": round(float(yhat[i]), 2), "lo": round(float(lo[i]), 2), "hi": round(float(hi[i]), 2),
                         "inside": bool(lo[i] <= y[i] <= hi[i])})
        if len(examples) == 5:
            break
    stamp = P.now_iso()
    out = {
        "run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": P.MODEL_NAME,
        "version": VERSION, "level": 1 - ALPHA,
        "designer": ("AI agent (Claude) proposed seven ways to give Storm 4.0 a 90% range: one width for all, widths set by "
                     "how much its members disagree, widths on log(1 + Tc), conformalised gradient-boosted quantiles and "
                     "one width for each range of predicted Tc"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by chemical system on Alexandria ({len(y):,} materials), the same folds "
                      f"as every Storm round; widths set by conformal prediction from the other folds' out-of-fold errors; "
                      f"graph network: saved out-of-fold predictions of version {gnn_version} ({saved.name}), {seeds} "
                      "seeds averaged"),
        "rule": (f"coverage within {COVER_TOL * 100:.0f} points of {(1 - ALPHA) * 100:.0f}%, at least {TAIL_MIN:.0%} for "
                 f"the top 10% of Tc, and an interval score better than one width for every material on average and in at "
                 f"least {P.ADOPT_FOLDS} of {P.N_FOLDS} folds"),
        "caveat": ("a range is for the computed (DFT Allen-Dynes) Tc that Storm learns; measured Tc can lie further away, "
                   "see 'measured'"),
        "storm4": {"design": design4, "members": len(members), "tc_mae": float(np.mean(np.abs(yhat - y))), "gnn": design},
        "tail_threshold": tail, "leaderboard": sorted(board, key=lambda r: r["interval_score"]), "best": best["id"],
        "adopted": adopted, "measured": measured, "examples": examples, "worked": worked, "scikit_learn": sklearn.__version__,
        "minutes": round((time.time() - t_start) / 60, 1),
    }
    P.RESULTS.mkdir(parents=True, exist_ok=True)
    (P.RESULTS / "storm_round5.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"id": train["id"], "chemsys": groups, "fold": fold_of, "tc": y, "tc_pred": yhat, "tc_lo": lo,
                  "tc_hi": hi}).round(5).to_csv(P.RESULTS / "storm_round5_ranges.csv", index=False)
    update_progress(out, best, ref)


def update_progress(out: dict, best: dict, ref: dict) -> None:
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8"))
    stamp = out["run_at"]
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    r2 = lambda v: None if v is None else round(float(v), 2)   # noqa: E731
    entry = {
        "round": ROUND, "version": VERSION, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"], "level": out["level"],
        "scores": {"interval_score": r2(best["interval_score"]), "reference_interval_score": r2(ref["interval_score"]),
                   "reference": ref["name"], "folds": [r2(x) for x in best["fold_interval_score"]],
                   "reference_folds": [r2(x) for x in ref["fold_interval_score"]], "folds_better": best["folds_better"],
                   "coverage": r3(best["coverage"]), "tail_coverage": r3(best["tail_coverage"]),
                   "reference_coverage": r3(ref["coverage"]), "reference_tail_coverage": r3(ref["tail_coverage"]),
                   "median_width": r2(best["median_width"]), "mean_width": r2(best["mean_width"]),
                   "tail_median_width": r2(best["tail_median_width"]), "reference_median_width": r2(ref["median_width"]),
                   "fold_coverage": [r3(x) for x in best["fold_coverage"]], "tail_threshold": r2(out["tail_threshold"])},
        "leaderboard": [{"id": r["id"], "name": r["name"], "interval_score": r2(r["interval_score"]),
                         "coverage": r3(r["coverage"]), "tail_coverage": r3(r["tail_coverage"]),
                         "median_width": r2(r["median_width"]), "folds_better": r["folds_better"]}
                        for r in out["leaderboard"]],
        "measured": out["measured"], "examples": out["examples"], "worked": out["worked"], "rule": out["rule"],
        "caveat": out["caveat"],
    }
    am = prog.setdefault("ai_model", {})
    am["uncertainty"] = entry   # app versions that know Storm 5.0 read this
    sc = entry["scores"]
    if out["adopted"]:
        fam = prog.get("model_family", [])
        for m in fam:
            if m.get("id") == "storm":
                m["status"] = f"Storm {VERSION} in use"
                text = (m.get("text") or "").split(" Since Storm 5.0")[0].replace(" Our AI agent designed it.", "")
                m["text"] = (text + f" Since Storm {VERSION} it also gives a 90% range for every prediction: for materials "
                             f"it never saw, the range held the computed Tc {sc['coverage']:.0%} of the time "
                             f"({sc['tail_coverage']:.0%} for the tenth with the highest Tc), and half of the ranges are "
                             f"narrower than {sc['median_width']:.1f} K. Our AI agent designed it.")
    H.ai_stage(prog)
    msg = (f"Storm round 5 ({len(out['leaderboard']) - 1} ways to give Storm 4.0 a 90% range): best {best['name']}, "
           f"interval score {best['interval_score']:.2f} K against {ref['interval_score']:.2f} K for one width for every "
           f"material, better in {best['folds_better']} of {P.N_FOLDS} folds; for held-out materials it held the computed "
           f"Tc {best['coverage']:.1%} of the time ({best['tail_coverage']:.1%} for the tenth with the highest Tc), and "
           f"half of the ranges are narrower than {best['median_width']:.2f} K; "
           + (f"adopted as Storm {VERSION}" if out["adopted"] else "not adopted, so Storm 4.0 stays in use without a range"))
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    P.PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)
