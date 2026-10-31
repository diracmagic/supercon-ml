"""Storm, search round 4: Storm 1.0's trees and the crystal-graph network together.

Storm 1.0 learns from hand-made and physics features; the graph network (ml/gnn.py, ml/gnn2.py) learns from the atoms
and their neighbours. Their errors are only partly correlated: in graph-network round 1, the average of the two was
better than Storm 1.0 in all five folds. Round 4 turns this into candidate Storms.

Base candidates (DFT Allen-Dynes Tc on Alexandria, the same 5-fold GroupKFold by chemical system as every Storm round):
    S0  Storm 1.0 (reference)
    S1  the average of Storm 1.0 and the graph network
    S2  the same average taken on log(1 + Tc)
    S3  Storm 1.0, the graph network and the network's Allen-Dynes route (from its λ and ω_log), averaged
The graph network is retrained here with two seeds in the design that graph-network round 2 released (the round-1
design if none was), so every prediction is out of fold. The weights are fixed, not fitted.

The lowest-error base that beats Storm 1.0 on average and in at least 4 of the 5 folds, and is not more than 0.5 K
worse on the graded measured Tc (data/experiments.json), is then calibrated to measured Tc with round 3's maps on the
same matched 3DSC materials and folds, side by side with Storm 1.0 (that is, Storm 3.0). It is released as Storm 4.0
if, calibrated, it is also closer to measured Tc than Storm 3.0.

Run from the repository root:  python ml/pipeline.py storm4   (GNN_SMOKE=1 for a quick check on a small subset)
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

import gnn as G1
import gnn2 as G2
import hurricane as H
import pipeline as P
import storm3 as S3

ROUND = 4
VERSION = "4.0"
SMOKE = os.environ.get("GNN_SMOKE") == "1"
SEEDS = int(os.environ.get("STORM4_SEEDS", 1 if SMOKE else 2))


def _mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def gnn_design() -> tuple[dict, str]:
    """The graph-network design to use: the one round 2 released, else the round-1 design."""
    path = P.RESULTS / "gnn_round2.json"
    if path.exists():
        r = json.loads(path.read_text())
        if r.get("adopted"):
            best = next(x for x in r["leaderboard"] if x["id"] == r["best"])
            cfg = dict(best["config"], id=best["id"], name=best["name"])
            return cfg, f"graph network {r.get('version')} ({best['name'].lstrip('+ ')})"
    return dict(G2.BASE, id="G0", name="Round-1 design"), "graph network 1.0 (round-1 design)"


def calibrate(m: pd.DataFrame) -> dict:
    """Round 3's calibration maps on a matched set: out-of-fold measured-Tc predictions and scores."""
    from sklearn.model_selection import GroupKFold
    k = min(P.N_FOLDS, m["chemsys"].nunique())
    folds = list(GroupKFold(n_splits=k).split(m, m["tc_exp"], m["chemsys"]))
    y = m["tc_exp"].to_numpy()
    board, oof = [], {}
    for c in S3.CANDIDATES:
        p = np.zeros(len(m))
        try:
            for tr, te in folds:
                p[te] = c["pred"](c["fit"](m.iloc[tr]), m.iloc[te])
        except (TypeError, ValueError) as err:
            P.log(f"{c['id']} skipped: {err}")
            continue
        oof[c["id"]] = p
        board.append({"id": c["id"], "name": c["name"], "mae": _mae(p, y), "fold_mae": [_mae(p[te], y[te]) for _, te in folds]})
    ref = next(r for r in board if r["id"] == "K0")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_mae"], ref["fold_mae"])))
    eligible = [r for r in board if r["id"] != "K0" and r["mae"] < ref["mae"] and r["folds_better"] >= min(P.ADOPT_FOLDS, k - 1)]
    best = min(eligible or board, key=lambda r: r["mae"])
    return {"board": board, "best": best, "oof": oof, "folds": folds, "k": k, "reference": ref,
            "dft_mae": _mae(m["dft_tc"], y), "n": int(len(m)), "n_sc": int((y > 0).sum())}


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    _, frames = P.load_clean()
    train = frames["alexandria"]
    if SMOKE:
        train = train.sample(n=min(500, len(train)), random_state=P.SEED).reset_index(drop=True)
    table = P.element_table(sorted({e for els in train["elements"] for e in els}))
    base = P.featurize(train, table)
    phys = P.physics_features(train, base)
    D = np.hstack([base.to_numpy(float), phys.to_numpy(float)])
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(D, y_tc, groups))
    folds = [te for _, te in splits]
    s_tc = np.clip(P.cv_predict_stage(D, y_tc, splits, P.STORM1_PARAMS), 0, None)
    s_lam = P.cv_predict_stage(D, y_lam, splits, P.STORM1_PARAMS, log_target=False)
    s_wlog = P.cv_predict_stage(D, y_wlog, splits, P.STORM1_PARAMS, log_target=False)
    P.log(f"Storm 1.0 out of fold: Tc MAE {_mae(s_tc, y_tc):.3f} K ({time.time() - t_start:.0f} s)")
    cfg, design = gnn_design()
    g = G1.build_graphs(train, table)
    glob = G2.descriptors(train, table)[0] if cfg.get("hybrid") else None
    Ttrans = np.column_stack([np.log1p(y_tc), np.log(y_lam), np.log(y_wlog)]).astype(np.float32)
    outs = []
    for s in range(SEEDS):
        o, rec = G2.train_all(g, Ttrans, y_tc, groups, splits, cfg, glob, seed=s + 1)
        outs.append(o)
        P.log(f"graph network seed {s + 1}: Tc MAE {_mae(o['tc'], y_tc):.3f} K ({rec['seconds']} s)")
    gn = {k: np.mean([o[k] for o in outs], axis=0) for k in ("tc", "lambda", "wlog")}
    gn_ad = P.allen_dynes(np.clip(gn["lambda"], 0, None), np.clip(gn["wlog"], 0, None))
    lam_mix, wlog_mix = 0.5 * (s_lam + gn["lambda"]), 0.5 * (s_wlog + gn["wlog"])
    cands = [
        {"id": "S0", "name": "Storm 1.0 (reference)", "tc": s_tc, "lam": s_lam, "wlog": s_wlog},
        {"id": "S1", "name": "Storm 1.0 and the graph network, averaged", "tc": 0.5 * (s_tc + gn["tc"]),
         "lam": lam_mix, "wlog": wlog_mix},
        {"id": "S2", "name": "Storm 1.0 and the graph network, averaged on log(1 + Tc)",
         "tc": np.expm1(0.5 * (np.log1p(s_tc) + np.log1p(np.clip(gn["tc"], 0, None)))), "lam": lam_mix, "wlog": wlog_mix},
        {"id": "S3", "name": "Storm 1.0, the graph network and its Allen–Dynes route, averaged",
         "tc": (s_tc + gn["tc"] + gn_ad) / 3.0, "lam": lam_mix, "wlog": wlog_mix},
    ]
    tail = float(np.quantile(y_tc, 0.9))
    board = []
    for c in cands:
        m = P.metrics(y_tc, c["tc"], tail=tail)
        board.append({"id": c["id"], "name": c["name"], "tc_mae": m["mae"], "tc_tail_mae": m["tail_mae"],
                      "fold_mae": G1.fold_maes(y_tc, c["tc"], folds), "lambda_mae": _mae(c["lam"], y_lam),
                      "wlog_mae": _mae(c["wlog"], y_wlog)})
    ref = board[0]
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_mae"], ref["fold_mae"])))
    exp = P.experimental_check(train, {c["id"]: c["tc"] for c in cands}, [c["id"] for c in cands])
    es = exp.get("summary", {})
    guard_on = bool(es) and es.get("n_scored", 0) >= P.EXP_MIN_N

    def exp_ok(r):
        return not guard_on or es["mae"][r["id"]] <= es["mae"]["S0"] + P.EXP_TOLERANCE
    for r in board:
        r["measured_mae"] = es.get("mae", {}).get(r["id"])
        P.log(f"{r['id']} {r['name']}: Tc MAE {r['tc_mae']:.3f} K (folds " + ", ".join(f"{x:.3f}" for x in r["fold_mae"]) +
              f"), better than Storm 1.0 in {r['folds_better']}/{P.N_FOLDS}; graded measured Tc {r['measured_mae']} K")
    eligible = [r for r in board if r["id"] != "S0" and r["tc_mae"] < ref["tc_mae"] and r["folds_better"] >= P.ADOPT_FOLDS and exp_ok(r)]
    best = min(eligible or board[1:], key=lambda r: r["tc_mae"])
    cb = next(c for c in cands if c["id"] == best["id"])
    feats = phys.assign(n_elements=base["n_elements"])
    cal_ref = cal_best = None
    m0 = S3.matched_set(train, feats, s_tc, s_lam, s_wlog)
    mb = S3.matched_set(train, feats, cb["tc"], cb["lam"], cb["wlog"])
    if len(m0) >= 10 and len(mb) >= 10:
        cal_ref, cal_best = calibrate(m0), calibrate(mb)
        P.log(f"calibrated to measured Tc on {cal_ref['n']} matched materials: Storm 1.0 + {cal_ref['best']['name']} "
              f"{cal_ref['best']['mae']:.2f} K (Storm 3.0), {best['id']} + {cal_best['best']['name']} "
              f"{cal_best['best']['mae']:.2f} K; uncalibrated {cal_ref['reference']['mae']:.2f} K and "
              f"{cal_best['reference']['mae']:.2f} K; DFT labels {cal_ref['dft_mae']:.2f} K")
    else:
        P.log("too few matched materials for the measured-Tc calibration")
    cal_ok = bool(cal_best) and cal_best["best"]["mae"] < cal_ref["best"]["mae"]
    adopted = bool(eligible) and best in eligible and cal_ok
    cal_folds_better = (int(sum(a < b for a, b in zip(cal_best["best"]["fold_mae"], cal_ref["best"]["fold_mae"])))
                        if cal_best else None)
    stamp = P.now_iso()
    out = {
        "run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": P.MODEL_NAME,
        "version": VERSION,
        "designer": ("AI agent (Claude) proposed combining Storm 1.0's trees with the crystal-graph network: a plain "
                     "average, an average on log(1 + Tc) and a three-way average with the network's Allen-Dynes route"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by chemical system on Alexandria ({len(y_tc):,} materials), the "
                      f"same folds as every Storm round; graph network retrained with {SEEDS} seed(s), out of fold"),
        "rule": (f"the base must beat Storm 1.0 on average and in at least {P.ADOPT_FOLDS} of {P.N_FOLDS} folds and not be "
                 f"more than {P.EXP_TOLERANCE} K worse on the graded measured Tc; calibrated with round 3's maps on the "
                 "same matched materials and folds, it must also be closer to measured Tc than Storm 3.0"),
        "caveat": "picking the best of several candidates on the same folds makes its score slightly optimistic",
        "gnn": {"design": design, "config": {k: v for k, v in cfg.items() if k not in ("id", "name")}, "seeds": SEEDS,
                "tc_mae": _mae(gn["tc"], y_tc), "lambda_mae": _mae(gn["lambda"], y_lam), "wlog_mae": _mae(gn["wlog"], y_wlog)},
        "leaderboard": sorted(board, key=lambda r: r["tc_mae"]), "best": best["id"], "adopted": adopted,
        "experiments": {"summary": es} if es else None, "scikit_learn": sklearn.__version__,
        "calibration": None if not cal_best else {
            "n_matched": cal_best["n"], "n_sc": cal_best["n_sc"], "dft_mae": cal_best["dft_mae"],
            "storm3": {"id": cal_ref["best"]["id"], "name": cal_ref["best"]["name"], "mae": cal_ref["best"]["mae"],
                       "folds": cal_ref["best"]["fold_mae"]},
            "best": {"id": cal_best["best"]["id"], "name": cal_best["best"]["name"], "mae": cal_best["best"]["mae"],
                     "folds": cal_best["best"]["fold_mae"], "folds_better_storm3": cal_folds_better},
            "uncalibrated_mae": cal_best["reference"]["mae"],
            "leaderboard": [{"id": r["id"], "name": r["name"], "mae": r["mae"], "folds_better": r["folds_better"]}
                            for r in sorted(cal_best["board"], key=lambda r: r["mae"])]},
        "minutes": round((time.time() - t_start) / 60, 1),
    }
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="storm4-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    results.mkdir(parents=True, exist_ok=True)
    (results / "storm_round4.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"id": train["id"], "chemsys": groups, "tc": y_tc, "tc_pred_storm1": s_tc, "tc_pred_gnn": gn["tc"],
                  "tc_pred_gnn_allen_dynes": gn_ad, "tc_pred_best": cb["tc"]}).round(5).to_csv(
        results / "storm_round4_predictions.csv", index=False)
    update_progress(out, best, progress)
    if SMOKE:
        P.log(f"storm4 smoke test passed; outputs in {results.parent}")


def update_progress(out: dict, best: dict, progress: Path) -> None:
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = out["run_at"]
    cal = out.get("calibration")
    r3 = lambda v: round(float(v), 3) if v is not None else None   # noqa: E731
    ref = next(r for r in out["leaderboard"] if r["id"] == "S0")
    entry = {
        "round": ROUND, "version": VERSION, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"] + (", calibrated to measured Tc" if cal else ""),
        "gnn": {"design": out["gnn"]["design"], "seeds": out["gnn"]["seeds"], "tc_mae": r3(out["gnn"]["tc_mae"])},
        "scores": {"tc_mae": r3(best["tc_mae"]), "reference_mae": r3(ref["tc_mae"]), "reference": "Storm 1.0",
                   "folds": [r3(x) for x in best["fold_mae"]], "reference_folds": [r3(x) for x in ref["fold_mae"]],
                   "folds_better": best["folds_better"], "lambda_mae": r3(best["lambda_mae"]), "wlog_mae": round(best["wlog_mae"], 1),
                   "measured_check_mae": best.get("measured_mae"), "measured_check_reference": ref.get("measured_mae")},
        "leaderboard": [{"id": r["id"], "name": r["name"], "tc_mae": r3(r["tc_mae"]), "folds_better": r["folds_better"]}
                        for r in out["leaderboard"]],
        "rule": out["rule"], "caveat": out["caveat"],
    }
    if cal:
        entry["calibration"] = {"method": cal["best"]["name"], "mae": round(cal["best"]["mae"], 2),
                                "mae_storm3": round(cal["storm3"]["mae"], 2), "mae_raw": round(cal["uncalibrated_mae"], 2),
                                "dft_mae": round(cal["dft_mae"], 2), "folds": [round(x, 2) for x in cal["best"]["folds"]],
                                "folds_storm3": [round(x, 2) for x in cal["storm3"]["folds"]],
                                "folds_better_storm3": cal["best"]["folds_better_storm3"], "n_matched": cal["n_matched"]}
    am = prog.setdefault("ai_model", {})
    am["ensemble"] = entry   # read by app versions that know Storm 4.0; older ones keep showing Storm 3.0
    if out["adopted"]:
        P.add_history(prog, {"at": stamp, "model": f"Storm {VERSION} (AI-designed)", "target": "Tc", "split": "val",
                             "mae": r3(best["tc_mae"])})
    msg = (f"Storm round 4 ({len(out['leaderboard']) - 1} combinations of Storm 1.0 and the {out['gnn']['design']}): best "
           f"{best['name']}, DFT Tc MAE {best['tc_mae']:.3f} K against {ref['tc_mae']:.3f} K for Storm 1.0, better in "
           f"{best['folds_better']} of {P.N_FOLDS} folds")
    if cal:
        msg += (f"; calibrated to measured Tc {cal['best']['mae']:.2f} K against {cal['storm3']['mae']:.2f} K for "
                f"Storm 3.0")
    msg += "; " + (f"adopted as Storm {VERSION}" if out["adopted"] else "not adopted, so Storm 3.0 stays in use")
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)
