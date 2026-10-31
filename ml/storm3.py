"""Storm, search round 3: calibrating the DFT-trained model against measured Tc.

Run from the repository root:
    python ml/pipeline.py storm3

Storm learns from DFT electron-phonon data (Alexandria), and the round-2 check showed that most of its error
against experiment comes from the DFT labels themselves: isotropic Allen-Dynes with one mu* misses multi-gap
MgB2, spin fluctuations suppress Tc in V, and so on. Round 3 adds a calibration head that maps Storm's prediction
to measured Tc. Training data for the head: conventional superconductors in 3DSC (SuperCon measured Tc, including
materials measured to be non-superconducting) whose composition is also in Alexandria. Storm's inputs for each of
them are out-of-fold predictions, exactly what it would give for a new material, never the DFT labels. Polymorphs
of one composition are pooled (median).

Candidates proposed by the AI agent (Claude): a linear map on log(1 + Tc), a monotone (isotonic) map, a physics
map that rescales the predicted lambda and refits an effective mu* in the Allen-Dynes formula, the same with a
spin-fluctuation term that raises mu* with the share of magnetic 3d atoms, and a small gradient-boosting correction.
They are scored with 5-fold cross-validation grouped by chemical system on the matched set; a calibration is
released as Storm 3.0 only if it beats uncalibrated Storm 1.0 on average and in at least 4 of the 5 folds.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402
import hurricane as H  # noqa: E402  (3DSC download and formula parsing)

ROUND = 3
VERSION = "3.0"
CONVENTIONAL = {"Other", "Chevrel", "Carbon"}
MIN_MATCHES = 25   # below this the calibration is reported but not considered for release
CAL_FEATURES = ["log_storm", "lam", "wlog", "log_ad", "mag3d", "d_fraction", "p_fraction", "light_fraction", "vec",
                "inv_sqrt_mass", "n_elements"]
GBM = dict(max_iter=300, learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=15, l2_regularization=2.0,
           loss="absolute_error")
MAG3D = {"V", "Cr", "Mn", "Fe", "Co", "Ni"}


def _mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


# ---------------------------------------------------------------- calibration candidates
# each candidate: fit(train frame) -> params; predict(params, frame) -> Tc (K)


def fit_identity(df):
    return {}


def pred_identity(par, df):
    return df["storm"].to_numpy()


def fit_loglinear(df):
    b, a = np.polyfit(np.log1p(df["storm"]), np.log1p(df["tc_exp"]), 1)
    return {"a": float(a), "b": float(b)}


def pred_loglinear(par, df):
    return np.clip(np.expm1(par["a"] + par["b"] * np.log1p(df["storm"].to_numpy())), 0, None)


def fit_isotonic(df):
    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(out_of_bounds="clip", increasing=True)
    iso.fit(np.log1p(df["storm"]), np.log1p(df["tc_exp"]))
    return {"model": iso}


def pred_isotonic(par, df):
    return np.clip(np.expm1(par["model"].predict(np.log1p(df["storm"].to_numpy()))), 0, None)


ALPHAS = np.round(np.arange(0.40, 1.61, 0.02), 2)
MUS = np.round(np.arange(0.00, 0.301, 0.01), 2)
GAMMAS = np.round(np.arange(0.0, 0.61, 0.05), 2)


def _ad_grid(lam, wlog, m3d, gammas):
    """Allen-Dynes Tc for every (alpha, mu*, gamma) on the grid: array [alpha, mu, gamma, material]."""
    L = ALPHAS[:, None, None, None] * lam[None, None, None, :]
    mu = MUS[None, :, None, None] + gammas[None, None, :, None] * m3d[None, None, None, :]
    denom = L - mu * (1 + 0.62 * L)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        tc = (wlog[None, None, None, :] / 1.2) * np.exp(-1.04 * (1 + L) / denom)
    return np.where((denom > 0) & np.isfinite(tc), tc, 0.0)


def _fit_physics(df, gammas):
    lam, wlog, m3d = (df[c].to_numpy(float) for c in ("lam", "wlog", "mag3d"))
    y = np.log1p(df["tc_exp"].to_numpy(float))
    tc = _ad_grid(lam, wlog, m3d, gammas)
    loss = np.mean(np.abs(np.log1p(tc) - y[None, None, None, :]), axis=-1)
    i, j, k = np.unravel_index(np.argmin(loss), loss.shape)
    return {"alpha": float(ALPHAS[i]), "mu_star": float(MUS[j]), "gamma": float(gammas[k])}


def fit_physics(df):
    return _fit_physics(df, np.array([0.0]))


def fit_physics_sf(df):
    return _fit_physics(df, GAMMAS)


def pred_physics(par, df):
    lam = par["alpha"] * df["lam"].to_numpy(float)
    mu = par["mu_star"] + par.get("gamma", 0.0) * df["mag3d"].to_numpy(float)
    denom = lam - mu * (1 + 0.62 * lam)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        tc = (df["wlog"].to_numpy(float) / 1.2) * np.exp(-1.04 * (1 + lam) / denom)
    return np.where((denom > 0) & np.isfinite(tc), tc, 0.0)


def fit_delta(df):
    from sklearn.ensemble import HistGradientBoostingRegressor
    X = df[CAL_FEATURES].to_numpy(float)
    m = HistGradientBoostingRegressor(random_state=P.SEED, **GBM)
    m.fit(X, np.log1p(df["tc_exp"]) - df["log_storm"])
    return {"model": m}


def pred_delta(par, df):
    return np.clip(np.expm1(df["log_storm"].to_numpy() + par["model"].predict(df[CAL_FEATURES].to_numpy(float))), 0, None)


CANDIDATES = [
    {"id": "K0", "name": "Storm 1.0, uncalibrated (reference)", "fit": fit_identity, "pred": pred_identity,
     "about": "Storm's prediction of the DFT Allen-Dynes Tc, taken as the measured Tc"},
    {"id": "K1", "name": "Linear map on log(1 + Tc)", "fit": fit_loglinear, "pred": pred_loglinear,
     "about": "log(1 + Tc_measured) = a + b log(1 + Tc_Storm): corrects a systematic over- or underestimate"},
    {"id": "K2", "name": "Monotone map (isotonic regression)", "fit": fit_isotonic, "pred": pred_isotonic,
     "about": "any increasing map from Storm's Tc to measured Tc, so a higher prediction never means a lower Tc"},
    {"id": "K3", "name": "Physics map: rescaled λ and an effective μ*", "fit": fit_physics, "pred": pred_physics,
     "about": "Tc = Allen-Dynes(α λ, ω_log, μ*) with Storm's predicted λ and ω_log; α and μ* are fitted"},
    {"id": "K4", "name": "Physics map + spin-fluctuation term", "fit": fit_physics_sf, "pred": pred_physics,
     "about": "as the physics map, with μ* raised by γ times the share of magnetic 3d atoms (paramagnons)"},
    {"id": "K5", "name": "Gradient-boosting correction", "fit": fit_delta, "pred": pred_delta,
     "about": "small trees learn log(1 + Tc_measured) - log(1 + Tc_Storm) from Storm's outputs and composition"},
]


# ---------------------------------------------------------------- matching


def matched_set(train: pd.DataFrame, feats: pd.DataFrame, p_tc, p_lam, p_wlog) -> pd.DataFrame:
    """Conventional 3DSC entries whose composition is in Alexandria, one row per composition."""
    dsc = H.load_3dsc()
    df = dsc[dsc["sc_class"].isin(CONVENTIONAL)].copy()
    df = df[df["synth_doped"].map(H._flag) < 0.5] if "synth_doped" in df else df
    df["tc"] = pd.to_numeric(df["tc"], errors="coerce")
    df = df[np.isfinite(df["tc"]) & (df["tc"] >= 0)]
    index = {}
    for i, atoms in enumerate(train["atoms"]):
        u, c = np.unique(list(atoms["elements"]), return_counts=True)
        index.setdefault(P._composition_key(dict(zip(u, c))), []).append(i)
    by_key = {}
    for f, tc in zip(df["formula_sc"], df["tc"]):
        try:
            comp = H.parse_formula(f)
        except ValueError:
            continue
        key = P._composition_key(comp)
        if key in index:
            by_key.setdefault(key, {"formulas": [], "tc": [], "comp": comp})
            by_key[key]["formulas"].append(f)
            by_key[key]["tc"].append(float(tc))
    rows = []
    y_tc, y_lam, y_wlog = (train[c].to_numpy() for c in ("tc", "lambda", "wlog"))
    for key, v in by_key.items():
        idx = index[key]
        comp = v["comp"]
        tot = sum(comp.values())
        lam, wlog = float(np.median(p_lam[idx])), float(np.median(p_wlog[idx]))
        r = {"name": pretty(comp), "formula": v["formulas"][0], "n_reports": len(v["tc"]), "n_polymorphs": len(idx),
             "tc_exp": float(np.median(v["tc"])), "storm": float(np.median(p_tc[idx])), "lam": max(lam, 0.0),
             "wlog": max(wlog, 1.0), "dft_tc": float(np.median(y_tc[idx])), "dft_lambda": float(np.median(y_lam[idx])),
             "dft_wlog": float(np.median(y_wlog[idx])), "chemsys": "-".join(sorted(comp)),
             "mag3d": sum(n for e, n in comp.items() if e in MAG3D) / tot}
        for c in ("d_fraction", "p_fraction", "light_fraction", "vec", "inv_sqrt_mass"):
            r[c] = float(np.median(feats[c].to_numpy(float)[idx]))
        r["n_elements"] = float(len(comp))
        rows.append(r)
    out = pd.DataFrame(rows)
    if len(out):
        out["log_storm"] = np.log1p(out["storm"])
        out["log_ad"] = np.log1p(P.allen_dynes(out["lam"], out["wlog"]))
    return out.sort_values("name").reset_index(drop=True) if len(out) else out


def pretty(comp: dict) -> str:
    """Reduced formula with integer amounts where possible, elements in the usual order (metals first)."""
    vals = np.array(list(comp.values()), float)
    for m in range(1, 13):
        if np.all(np.abs(vals / vals.min() * m - np.round(vals / vals.min() * m)) < 1e-3):
            n = np.round(vals / vals.min() * m).astype(int)
            g = np.gcd.reduce(n)
            amounts = dict(zip(comp, (n // g).tolist()))
            break
    else:
        amounts = {e: round(v, 3) for e, v in comp.items()}
    from pymatgen.core.periodic_table import Element

    def chi(e):   # most electropositive first, as in Nb3Sn, MgB2, V3Si
        try:
            return float(Element(e).X)
        except Exception:
            return 2.0
    order = sorted(amounts, key=lambda e: (chi(e), e))
    return "".join(e + ("" if amounts[e] == 1 else str(amounts[e])) for e in order)


# ---------------------------------------------------------------- run


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    P.RESULTS.mkdir(exist_ok=True)
    _, frames = P.load_clean()
    train = frames["alexandria"]
    table = P.element_table(sorted({e for els in train["elements"] for e in els}))
    base = P.featurize(train, table)
    phys = P.physics_features(train, base)
    D = np.hstack([base.to_numpy(float), phys.to_numpy(float)])
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy() for c in ("tc", "lambda", "wlog"))
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(D, y_tc, groups))
    t0 = time.time()
    p_tc = np.clip(P.cv_predict_stage(D, y_tc, splits, P.STORM1_PARAMS), 0, None)
    p_lam = P.cv_predict_stage(D, y_lam, splits, P.STORM1_PARAMS, log_target=False)
    p_wlog = P.cv_predict_stage(D, y_wlog, splits, P.STORM1_PARAMS, log_target=False)
    P.log(f"Storm 1.0 out of fold on Alexandria: Tc MAE {_mae(p_tc, y_tc):.3f} K, lambda MAE {_mae(p_lam, y_lam):.3f}, "
          f"omega_log MAE {_mae(p_wlog, y_wlog):.1f} K ({time.time() - t0:.0f} s)")
    m = matched_set(train, phys.assign(n_elements=base["n_elements"]), p_tc, p_lam, p_wlog)
    n = len(m)
    P.log(f"matched {n} compositions between 3DSC (conventional classes, not synthetically doped) and Alexandria; "
          f"{int((m['tc_exp'] > 0).sum()) if n else 0} superconducting")
    if n < 10:
        P.log("too few matches for a calibration; nothing written")
        return
    k = min(P.N_FOLDS, m["chemsys"].nunique())
    folds = list(GroupKFold(n_splits=k).split(m, m["tc_exp"], m["chemsys"]))
    y = m["tc_exp"].to_numpy()
    board, oof = [], {}
    for c in CANDIDATES:
        p = np.zeros(n)
        try:
            for tr, te in folds:
                par = c["fit"](m.iloc[tr])
                p[te] = c["pred"](par, m.iloc[te])
        except (TypeError, ValueError) as err:
            P.log(f"{c['id']} skipped: {err}")
            continue
        oof[c["id"]] = p
        sc = y > 0
        row = {"id": c["id"], "name": c["name"], "about": c["about"], "mae": _mae(p, y),
               "mae_sc": _mae(p[sc], y[sc]) if sc.any() else None,
               "mae_log": _mae(np.log1p(p), np.log1p(y)),
               "fold_mae": [_mae(p[te], y[te]) for _, te in folds]}
        board.append(row)
    ref = next(r for r in board if r["id"] == "K0")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_mae"], ref["fold_mae"])))
        P.log(f"{r['id']} {r['name']}: measured-Tc MAE {r['mae']:.2f} K (superconductors "
              f"{r['mae_sc'] if r['mae_sc'] is None else round(r['mae_sc'], 2)} K), better than uncalibrated in "
              f"{r['folds_better']}/{k} folds")
    dft_mae = _mae(m["dft_tc"], y)
    eligible = [r for r in board if r["id"] != "K0" and r["mae"] < ref["mae"] and r["folds_better"] >= min(P.ADOPT_FOLDS, k - 1)]
    adopted = bool(eligible) and n >= MIN_MATCHES
    best = min(eligible or [r for r in board if r["id"] != "K0"], key=lambda r: r["mae"])
    cb = next(c for c in CANDIDATES if c["id"] == best["id"])
    par_all = cb["fit"](m)
    params = {kk: v for kk, v in par_all.items() if kk != "model"}
    if best["id"] == "K2":   # the monotone map itself, on log(1 + Tc)
        iso = par_all["model"]
        params = {"log_storm": [round(float(x), 4) for x in iso.X_thresholds_],
                  "log_tc": [round(float(x), 4) for x in iso.y_thresholds_]}
    physics = {}
    for cid in ("K3", "K4"):
        cc = next(c for c in CANDIDATES if c["id"] == cid)
        physics[cid] = cc["fit"](m)
    P.log(f"best calibration {best['id']} {best['name']}: {best['mae']:.2f} K vs {ref['mae']:.2f} K uncalibrated and "
          f"{dft_mae:.2f} K for the DFT labels themselves; adopted: {adopted}; fitted on all matches: {params}; physics "
          f"maps {physics}")
    cal = oof[best["id"]] if adopted else oof["K0"]
    m["storm_cal_oof"] = oof[best["id"]]
    gap = m.assign(gap=m["tc_exp"] - cal)
    shortfalls = gap[gap["tc_exp"] >= 5].sort_values("gap", ascending=False).head(12)
    overshoots = gap[gap["tc_exp"] == 0].sort_values("gap").head(8)

    def rows_of(d):
        return [{"name": r["name"], "tc_exp": round(r["tc_exp"], 2), "storm": round(r["storm"], 2),
                 "calibrated": round(float(r["storm_cal_oof"]), 2), "dft": round(r["dft_tc"], 2),
                 "dft_lambda": round(r["dft_lambda"], 3), "reports": int(r["n_reports"]),
                 "polymorphs": int(r["n_polymorphs"])} for _, r in d.iterrows()]
    leader = sorted(board, key=lambda r: r["mae"])
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND,
        "model": P.MODEL_NAME, "version": VERSION, "base": "Storm 1.0",
        "designer": ("AI agent (Claude) proposed the calibration maps: linear and monotone maps on log(1 + Tc), an "
                     "Allen-Dynes physics map with a rescaled λ and an effective μ*, a spin-fluctuation term and a "
                     "gradient-boosting correction"),
        "data": {"source": "3DSC_MP conventional classes (Other, Chevrel, Carbon), not synthetically doped, matched to "
                           "Alexandria by composition; polymorphs pooled (median)", "cite": H.DSC_CITE,
                 "n_matched": n, "n_sc": int((y > 0).sum()), "n_groups": int(m["chemsys"].nunique()),
                 "inputs": "Storm 1.0 out-of-fold predictions of Tc, λ and ω_log (never the DFT labels)"},
        "selection": f"{k}-fold GroupKFold by chemical system on the matched set",
        "rule": (f"release the lowest-error map that beats uncalibrated Storm 1.0 on average and in at least "
                 f"{min(P.ADOPT_FOLDS, k - 1)} of {k} folds, with at least {MIN_MATCHES} matched materials"),
        "caveat": ("SuperCon Tc is averaged over reports, a composition can stand for several polymorphs, and "
                   "non-superconducting entries are only as good as the lowest temperature measured"),
        "scikit_learn": sklearn.__version__,
        "leaderboard": leader, "best": best, "adopted": adopted, "params": params, "physics_fits": physics,
        "dft_mae": dft_mae, "reference_mae": ref["mae"], "reference_fold_mae": ref["fold_mae"],
        "shortfalls": rows_of(shortfalls), "overshoots": rows_of(overshoots),
    }
    (P.RESULTS / "storm_round3.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    m.drop(columns=["log_storm", "log_ad"]).round(4).to_csv(P.RESULTS / "storm_round3_matches.csv", index=False)
    update_progress(out)


def update_progress(out: dict) -> None:
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, adopted = out["best"], out["adopted"]
    d = out["data"]
    cal = {
        "round": ROUND, "version": VERSION, "date": stamp[:10], "status": "adopted" if adopted else "experimental",
        "base": out["base"], "summary": f"{out['base']} + {best['name'][0].lower() + best['name'][1:]}",
        "method": {"id": best["id"], "name": best["name"], "about": best["about"], "params": out["params"]},
        "data": {k: d[k] for k in ("n_matched", "n_sc", "n_groups", "source", "inputs")},
        "scores": {"mae": round(best["mae"], 2), "mae_raw": round(out["reference_mae"], 2),
                   "dft_mae": round(out["dft_mae"], 2), "mae_sc": round(best["mae_sc"], 2) if best["mae_sc"] is not None else None,
                   "folds": [round(x, 2) for x in best["fold_mae"]],
                   "folds_raw": [round(x, 2) for x in out["reference_fold_mae"]], "folds_better": best["folds_better"]},
        "physics": {k: v for k, v in out["physics_fits"].items()},
        "leaderboard": [{"id": r["id"], "name": r["name"], "mae": round(r["mae"], 2), "folds_better": r["folds_better"]}
                        for r in out["leaderboard"]],
        "shortfalls": out["shortfalls"][:8],
        "rule": out["rule"], "caveat": out["caveat"],
    }
    am = prog.setdefault("ai_model", {})
    am["calibration"] = cal
    note = (f"{d['n_matched']} conventional superconductors and non-superconductors from 3DSC matched to Alexandria; "
            f"grouped CV")
    prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "storm-calibration"] + [
        {"tag": "storm-calibration", "model": f"Storm {VERSION}: Storm 1.0 calibrated to measured Tc" +
         ("" if adopted else ", experimental"), "target": "Tc_exp", "mae": round(best["mae"], 2), "unit": "K", "note": note},
        {"tag": "storm-calibration", "model": "Storm 1.0, uncalibrated", "target": "Tc_exp",
         "mae": round(out["reference_mae"], 2), "unit": "K", "note": "Same materials; Storm predicts DFT Allen-Dynes Tc"},
        {"tag": "storm-calibration", "model": "DFT electron-phonon labels (Alexandria)", "target": "Tc_exp",
         "mae": round(out["dft_mae"], 2), "unit": "K", "note": "Same materials; the labels Storm learns from"},
    ]
    if adopted:
        fam = [x for x in prog.get("model_family", []) if x.get("id") != "storm"]
        fam.insert(0, {"id": "storm", "status": f"Storm {VERSION} in use", "active": True,
                       "text": ("Learns from about 7,600 materials whose electron–phonon coupling λ and phonon scale ω_log "
                                "have been computed (the Alexandria set), then a calibration learned from "
                                f"{d['n_matched']} materials with measured Tc ({d['n_sc']} superconducting) maps its "
                                f"prediction to measured Tc: off by "
                                f"{best['mae']:.1f} K on average against {out['reference_mae']:.1f} K uncalibrated and "
                                f"{out['dft_mae']:.1f} K for the DFT labels themselves. Our AI agent designed it.")})
        prog["model_family"] = fam
    H.ai_stage(prog)
    P.tidy(prog)
    P.add_log(prog, stamp, (f"Storm round 3, calibration to measured Tc ({len(out['leaderboard']) - 1} maps and the "
                            f"uncalibrated reference on {d['n_matched']} matched materials): best {best['name']}, MAE "
                            f"{best['mae']:.2f} K against "
                            f"{out['reference_mae']:.2f} K uncalibrated (DFT labels {out['dft_mae']:.2f} K), better in "
                            f"{best['folds_better']} of {len(best['fold_mae'])} folds; " +
                            (f"adopted as Storm {VERSION}" if adopted else "not adopted, so Storm 1.0 stays in use")))
    prog["updated"] = stamp
    P.PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: Storm round 3 calibration ({cal['status']})")


if __name__ == "__main__":
    run()
