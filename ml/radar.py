"""Radar, round 1: which of our two models should a material go to?

Radar reads a material's composition and crystal structure and gives the probability that it belongs to an
unconventional family (cuprates, iron- and nickel-based compounds, heavy-fermion compounds and other oxides:
Hurricane's domain) rather than to the conventional, phonon-mediated superconductors that Storm covers. The labels
are the SuperCon classes in 3DSC: Cuprate, Ferrite, Heavy_fermion and Oxide for unconventional, Other, Chevrel and
Carbon for conventional; mixed classes are left out. A material is sent to Hurricane when the probability is at
least one half.

Scoring: 5-fold cross-validation grouped by parent compound, as for Hurricane. The main score is the log loss
(how much probability Radar gives to the right answer); balanced accuracy, ROC AUC, the Brier score and the
calibration error are reported alongside. A harder test leaves out one family at a time: trained without any
cuprate, how many cuprates does Radar still send to Hurricane? An AI agent (Claude) proposed the candidates; a
design is released as a new version only if it beats the composition-only baseline on average and in at least
4 of the 5 folds. The graded anchors are predicted for information and never used for training or selection.

Run from the repository root:  python ml/pipeline.py radar
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd

import hurricane as H
import pipeline as P

MODEL = "Radar"
ROUND = 1
UNCONV = set(H.FAMILY_OF_CLASS)                  # Cuprate, Ferrite, Heavy_fermion, OxideHeavy_fermion, Oxide
CONV = {"Other", "Chevrel", "Carbon"}
PARAMS = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=10, l2_regularization=1.0)
CONV_LABEL = {"Other": "Other conventional", "Chevrel": "Chevrel phases", "Carbon": "Carbon-based"}
EXPERIMENTS = P.ROOT / "data" / "experiments.json"


# ---------------------------------------------------------------- models


def _fit(X, y, params, seed, weights=None, n_bags=1):
    from sklearn.ensemble import HistGradientBoostingClassifier
    empty = ~np.isfinite(X).any(axis=0)
    if empty.any():
        X = X.copy()
        X[:, empty] = 0.0
    models = []
    for b in range(n_bags):
        m = HistGradientBoostingClassifier(random_state=seed + 1000 * b, **params)
        m.fit(X, y, sample_weight=weights)
        models.append(m)
    return models


def _proba(models, X) -> np.ndarray:
    return np.mean([m.predict_proba(X)[:, 1] for m in models], axis=0)


def _balanced(y) -> np.ndarray:
    w = np.ones(len(y))
    for c in (0, 1):
        n = (y == c).sum()
        if n:
            w[y == c] = len(y) / (2.0 * n)
    return w


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class _Platt:
    """Logistic map from Radar's log-odds to calibrated probabilities (Platt scaling)."""

    def __init__(self, oof, y):
        from sklearn.linear_model import LogisticRegression
        self.lr = LogisticRegression(C=1.0).fit(_logit(oof)[:, None], y)

    def predict(self, p):
        return self.lr.predict_proba(_logit(p)[:, None])[:, 1]


def _calibrator(X, y, groups, params, seed):
    """Platt scaling learned from out-of-fold probabilities inside the training fold."""
    from sklearn.model_selection import GroupKFold
    k = min(3, len(np.unique(groups)))
    oof = np.zeros(len(y))
    for i, (a, b) in enumerate(GroupKFold(n_splits=k).split(X, y, groups)):
        oof[b] = _proba(_fit(X[a], y[a], params, seed + 50 + i), X[b])
    return _Platt(oof, y)


def fit_design(c: dict, X, y, groups, seed):
    w = _balanced(y) if c.get("balanced") else None
    models = _fit(X, y, c["params"], seed, weights=w, n_bags=c.get("bags", 1))
    cal = _calibrator(X, y, groups, c["params"], seed) if c.get("calibrate") else None
    return models, cal


def predict_design(fitted, X) -> np.ndarray:
    models, cal = fitted
    p = _proba(models, X)
    return np.clip(cal.predict(p), 0.0, 1.0) if cal is not None else p


def run_candidate(c: dict, mats: dict, y, groups, splits) -> np.ndarray:
    X = mats[c["X"]]
    p = np.zeros(len(y))
    for k, (tr, te) in enumerate(splits):
        p[te] = predict_design(fit_design(c, X[tr], y[tr], groups[tr], P.SEED + k), X[te])
    return p


def scores(y, p, folds, labels) -> dict:
    from sklearn.metrics import roc_auc_score
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    ll = -(y * np.log(pc) + (1 - y) * np.log(1 - pc))
    hat = (p >= 0.5).astype(int)
    tpr, tnr = float(np.mean(hat[y == 1] == 1)), float(np.mean(hat[y == 0] == 0))
    bins = np.minimum((p * 10).astype(int), 9)
    ece = float(sum(np.sum(bins == b) / len(p) * abs(p[bins == b].mean() - y[bins == b].mean())
                    for b in range(10) if np.any(bins == b)))
    out = {"log_loss": float(ll.mean()), "balanced_accuracy": (tpr + tnr) / 2, "to_hurricane": tpr, "to_storm": tnr,
           "accuracy": float(np.mean(hat == y)), "auc": float(roc_auc_score(y, p)),
           "brier": float(np.mean((p - y) ** 2)), "ece": ece,
           "fold_log_loss": [float(ll[te].mean()) for te in folds],
           "fold_balanced_accuracy": [float((np.mean(hat[te][y[te] == 1] == 1) + np.mean(hat[te][y[te] == 0] == 0)) / 2)
                                      for te in folds]}
    out["by_class"] = {}
    for lab in sorted(set(labels)):
        m = labels == lab
        right = hat[m] == y[m]
        out["by_class"][lab] = {"n": int(m.sum()), "right": float(right.mean()), "mean_p": float(p[m].mean()),
                                "model": "Hurricane" if y[m][0] == 1 else "Storm"}
    return out


def lofo(c: dict, mats: dict, y, labels, groups) -> list:
    """Leave one family out (each unconventional family, and the Chevrel and carbon-based classes): train on the
    rest, then ask how much of the held-out family goes to the right model."""
    X = mats[c["X"]]
    out = []
    for lab in list(H.FAMILY_LABEL) + ["Chevrel", "Carbon"]:
        te = np.where(labels == lab)[0]
        tr = np.where(labels != lab)[0]
        if len(te) < 10:
            continue
        p = predict_design(fit_design(c, X[tr], y[tr], groups[tr], P.SEED + 300), X[te])
        to_h = float(np.mean(p >= 0.5))
        want_h = bool(y[te][0] == 1)
        out.append({"family": lab, "label": H.FAMILY_LABEL.get(lab, CONV_LABEL.get(lab, lab)), "n": int(len(te)),
                    "model": "Hurricane" if want_h else "Storm", "right": to_h if want_h else 1 - to_h,
                    "mean_p": float(p.mean())})
    return out


def permutation_importance(c: dict, mats: dict, y, groups, splits, names, n_repeats=2) -> list:
    """Mean increase of the out-of-fold log loss when one input is shuffled within each test fold."""
    rng = np.random.default_rng(P.SEED)
    X = mats[c["X"]]
    gain = np.zeros(X.shape[1])

    def ll(p, t):
        pc = np.clip(p, 1e-6, 1 - 1e-6)
        return float(np.mean(-(t * np.log(pc) + (1 - t) * np.log(1 - pc))))
    for k, (tr, te) in enumerate(splits):
        fitted = fit_design(dict(c, calibrate=False), X[tr], y[tr], groups[tr], P.SEED + k)
        base = ll(predict_design(fitted, X[te]), y[te])
        for j in range(X.shape[1]):
            inc = 0.0
            for _ in range(n_repeats):
                Xp = X[te].copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                inc += ll(predict_design(fitted, Xp), y[te]) - base
            gain[j] += inc / n_repeats * len(te) / len(y)
    order = np.argsort(-gain)
    return [{"name": names[j], "gain": round(float(gain[j]), 4)} for j in order[:12]]


# ---------------------------------------------------------------- checks on known materials


def known_materials(final, c: dict, table, elements: list) -> list:
    """Radar's call for the graded anchors (Hurricane) and the graded conventional superconductors (Storm)."""
    rows = []
    sets = [(H.load_anchors().get("materials", []), True)]
    if EXPERIMENTS.exists():
        sets.append((json.loads(EXPERIMENTS.read_text(encoding="utf-8")).get("materials", []), False))
    for mats, is_anchor in sets:
        for e in mats:
            if e.get("status") in ("refuted", "retracted"):
                continue
            comp = {k: float(v) for k, v in e["composition"].items()}
            if any(el not in table.index for el in comp):
                continue
            st = H.anchor_structure(e["structure"]) if e.get("structure") else {}
            blocks = {"A": pd.DataFrame([H.composition_row(comp, table)]), "C": pd.DataFrame([H.physics_row(comp)]),
                      "B": pd.DataFrame([H.structure_row(st, comp, table)]), "D": H.element_fractions([comp], elements)}
            X = np.hstack([blocks[b].to_numpy(float) for b in c["X"]])
            p = float(predict_design(final, X)[0])
            fam = e.get("family") or ("hydride" if "H" in comp else "conventional")
            rows.append({"name": e["name"], "family": fam, "p_unconventional": round(p, 3),
                         "model": "Hurricane" if p >= 0.5 else "Storm", "structure": bool(st), "list": "anchors" if is_anchor else "experiments"})
    return rows


# ---------------------------------------------------------------- spec and progress


def model_spec(c: dict, n: dict) -> dict:
    spec = H.model_spec(dict(c, params=dict(c["params"], loss=None)), n)
    spec["learner"]["kind"] = "gradient-boosting classifier"
    spec["learner"]["loss"] = "log loss"
    spec["learner"]["weights"] = "balanced classes" if c.get("balanced") else None
    spec["learner"]["calibration"] = "Platt scaling, from out-of-fold probabilities inside each training fold" if c.get("calibrate") else None
    spec["target"] = "probability that the material belongs to an unconventional family"
    spec["rule"] = "send to Hurricane if the probability is at least 0.5, otherwise to Storm"
    return spec


def update_progress(out: dict) -> None:
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, ref, ver, data = out["best"], out["baseline"], out["version"], out["data"]
    sc, rs = best["scores"], ref["scores"]
    r3 = lambda v: round(float(v), 3)   # noqa: E731
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"] + ("" if best["settings"] == "default" else f", {best['settings']}"),
        "changes": out["changes"], "spec": out["spec"],
        "scores": {"log_loss": r3(sc["log_loss"]), "reference_log_loss": r3(rs["log_loss"]), "reference": ref["name"],
                   "folds": [r3(x) for x in sc["fold_log_loss"]], "reference_folds": [r3(x) for x in rs["fold_log_loss"]],
                   "folds_better": best["folds_better"], "balanced_accuracy": r3(sc["balanced_accuracy"]),
                   "reference_balanced_accuracy": r3(rs["balanced_accuracy"]), "to_hurricane": r3(sc["to_hurricane"]),
                   "to_storm": r3(sc["to_storm"]), "auc": r3(sc["auc"]), "brier": r3(sc["brier"]), "ece": r3(sc["ece"]),
                   "by_class": {k: {"n": v["n"], "right": r3(v["right"]), "mean_p": r3(v["mean_p"]), "model": v["model"]}
                                for k, v in sc["by_class"].items()}},
        "lofo": [{k: (r3(v) if isinstance(v, float) else v) for k, v in r.items()} for r in out["lofo"]],
        "importance": out["importance"],
        "known": out["known"],
        "search": {"candidates": len(out["leaderboard"]), "reference_id": ref["id"],
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"],
                                    "log_loss": r3(r["scores"]["log_loss"]),
                                    "balanced_accuracy": r3(r["scores"]["balanced_accuracy"]),
                                    "folds_better": r["folds_better"]} for r in out["leaderboard"]]},
    }
    reg = prog.get("radar") or {}
    versions = [v for v in reg.get("versions", []) if v.get("round") != ROUND] + [entry]
    versions.sort(key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    prog["radar"] = {
        "name": MODEL,
        "about": ("Radar is the project's router. From a material's composition and crystal structure it gives the "
                  "probability that the material belongs to an unconventional family (cuprates, iron- and nickel-based, "
                  "heavy-fermion and other oxides), and sends it to Hurricane if so and to Storm otherwise. It learns "
                  "from the SuperCon classes in 3DSC. An AI agent (Claude) proposes each design; candidates are scored "
                  "with cross-validation grouped by parent compound, and a version is released only if it beats the "
                  "composition-only baseline on average and in at least 4 of 5 folds."),
        "current": released[-1]["version"] if released else None,
        "data": data,
        "versions": versions,
    }
    lof = {r["family"]: r for r in out["lofo"]}
    text = (f"Reads a material’s composition and crystal structure and gives the probability that it belongs to an "
            f"unconventional family, then sends it to Hurricane or Storm. It learns from {data['n']:,} SuperCon entries "
            f"in 3DSC ({data['n_unconventional']:,} unconventional, {data['n_conventional']:,} conventional). For parent "
            f"compounds it never saw it picks the right model {sc['balanced_accuracy']:.0%} of the time (balanced "
            f"accuracy), against {rs['balanced_accuracy']:.0%} for a composition-only baseline.")
    cup = lof.get("cuprate")
    if cup:
        text += (f" Trained without any cuprate, it still sends {cup['right']:.0%} of cuprates to Hurricane.")
    text += " Our AI agent designed it."
    fam = [m for m in prog.get("model_family", []) if m.get("id") != "radar"]
    fam.append({"id": "radar", "status": f"{MODEL} {ver} in use" if out["adopted"] else f"{MODEL} {ver}, experimental",
                "active": bool(out["adopted"]), "text": text})
    prog["model_family"] = fam
    H.ai_stage(prog)
    P.add_log(prog, stamp, f"{MODEL} {ver}, the AI-designed router between Storm and Hurricane (round {ROUND}, "
                           f"{len(out['leaderboard'])} candidates): log loss {sc['log_loss']:.3f} against "
                           f"{rs['log_loss']:.3f} for the composition-only baseline, better in {best['folds_better']} of "
                           f"{P.N_FOLDS} folds; balanced accuracy {sc['balanced_accuracy']:.1%}; " +
                           ("adopted" if out["adopted"] else "not adopted, so it stays experimental"))
    P.tidy(prog)
    prog["updated"] = stamp
    P.PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {MODEL} {ver} ({entry['status']})")


# ---------------------------------------------------------------- run


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    P.RESULTS.mkdir(exist_ok=True)
    dsc = H.load_3dsc()
    unc = H.build_frame(dsc, UNCONV)
    con = H.build_frame(dsc, CONV)
    df = pd.concat([unc.assign(y=1, label=unc["family"]), con.assign(y=0, label=con["sc_class"])], ignore_index=True)
    df = df.drop_duplicates(subset="formula_sc", keep=False).reset_index(drop=True)   # a formula in two classes is ambiguous
    y = df["y"].to_numpy(int)
    labels = df["label"].to_numpy()
    groups = df["group"].to_numpy()
    symbols = sorted({e for c in df["comp"] for e in c})
    extra = {e for a in H.load_anchors().get("materials", []) for e in a["composition"]}
    if EXPERIMENTS.exists():
        extra |= {e for a in json.loads(EXPERIMENTS.read_text(encoding="utf-8")).get("materials", []) for e in a["composition"]}
    table = P.element_table(sorted(set(symbols) | extra))
    P.log(f"Radar data: {len(df)} entries ({int(y.sum())} unconventional, {int((y == 0).sum())} conventional) in "
          f"{len(set(groups))} parent groups; " + ", ".join(f"{k} {int((labels == k).sum())}" for k in sorted(set(labels))))
    blocks = H.feature_blocks(df, table, [H.dsc_structure(r) for _, r in df.iterrows()])
    counts = {}
    for c in df["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = H.element_fractions(df["comp"], elements)
    names = {b: list(blocks[b].columns) for b in blocks}
    n_cols = {b: len(names[b]) for b in names}
    mats = {key: np.hstack([blocks[b].to_numpy(float) for b in key]) for key in ("A", "AC", "AB", "ABC", "ABCD")}
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats["A"], y, groups))
    folds = [te for _, te in splits]
    cands = [
        {"id": "R0", "name": "Composition only (baseline)", "settings": "default", "X": "A", "params": PARAMS},
        {"id": "R1", "name": "Composition + physics features", "settings": "default", "X": "AC", "params": PARAMS},
        {"id": "R2", "name": "Composition + measurable structure", "settings": "default", "X": "AB", "params": PARAMS},
        {"id": "R3", "name": "Composition + structure + physics", "settings": "default", "X": "ABC", "params": PARAMS},
        {"id": "R4", "name": "Composition + structure + physics + element fractions", "settings": "default", "X": "ABCD",
         "params": PARAMS},
        {"id": "R5", "name": "Composition + structure + physics, balanced classes", "settings": "default", "X": "ABC",
         "params": PARAMS, "balanced": True},
        {"id": "R6", "name": "Composition + structure + physics", "settings": "average of 5 seeds", "X": "ABC",
         "params": dict(PARAMS, max_features=0.8), "bags": 5},
        {"id": "R7", "name": "Composition + structure + physics, calibrated probabilities", "settings": "default",
         "X": "ABC", "params": PARAMS, "calibrate": True},
    ]
    board, preds = [], {}
    for c in cands:
        t0 = time.time()
        try:
            p = run_candidate(c, mats, y, groups, splits)
        except (TypeError, ValueError) as err:   # e.g. an option this scikit-learn version lacks
            P.log(f"{c['id']} skipped: {err}")
            continue
        s = scores(y, p, folds, labels)
        row = dict(c, scores=s, n_features=int(mats[c["X"]].shape[1]), seconds=round(time.time() - t0))
        row["params"] = dict(c["params"])
        board.append(row)
        preds[c["id"]] = p
        P.log(f"{c['id']} {c['name']} [{c['settings']}]: log loss {s['log_loss']:.4f}, balanced accuracy "
              f"{s['balanced_accuracy']:.3f} (to Hurricane {s['to_hurricane']:.3f}, to Storm {s['to_storm']:.3f}), AUC "
              f"{s['auc']:.4f}, Brier {s['brier']:.4f}, calibration error {s['ece']:.4f}, {row['seconds']} s")
    ref = next(r for r in board if r["id"] == "R0")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["scores"]["fold_log_loss"], ref["scores"]["fold_log_loss"])))
    eligible = [r for r in board if r["id"] != "R0" and r["scores"]["log_loss"] < ref["scores"]["log_loss"]
                and r["folds_better"] >= P.ADOPT_FOLDS]
    adopted = bool(eligible)
    best = min(eligible or [r for r in board if r["id"] != "R0"], key=lambda r: r["scores"]["log_loss"])
    cb = next(c for c in cands if c["id"] == best["id"])
    feat_names = [n for b in cb["X"] for n in names[b]]
    importance = permutation_importance(cb, mats, y, groups, splits, feat_names)
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.4f})" for i in importance[:8]))
    lofo_rows = lofo(cb, mats, y, labels, groups)
    lofo_ref = {r["family"]: r for r in lofo(cands[0], mats, y, labels, groups)}
    for r in lofo_rows:
        r["right_baseline"] = lofo_ref[r["family"]]["right"] if r["family"] in lofo_ref else None
        P.log(f"leave one family out, {r['family']}: {r['right']:.1%} sent to {r['model']} (baseline design "
              f"{r['right_baseline']:.1%}), mean probability of unconventional {r['mean_p']:.3f}")
    final = fit_design(cb, mats[cb["X"]], y, groups, P.SEED + 500)
    known = known_materials(final, cb, table, elements)
    P.log("known materials: " + "; ".join(f"{k['name']} {k['p_unconventional']:.2f} -> {k['model']}" for k in known))
    version = f"{ROUND}.0"
    data = {"source": "3DSC_MP (SuperCon classes, with Materials Project structures)", "cite": H.DSC_CITE,
            "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": H.DSC_COMMIT[:7],
            "n": int(len(y)), "n_unconventional": int(y.sum()), "n_conventional": int((y == 0).sum()),
            "n_groups": int(len(set(groups))), "classes": {k: int((labels == k).sum()) for k in sorted(set(labels))}}
    P.log(f"{MODEL} {version} = {best['id']} {best['name']} [{best['settings']}]: log loss {best['scores']['log_loss']:.4f} "
          f"(baseline {ref['scores']['log_loss']:.4f}, better in {best['folds_better']}/{P.N_FOLDS} folds; adopted: {adopted})")
    leader = sorted(board, key=lambda r: r["scores"]["log_loss"])
    changes = H.spec_changes(dict(cb, params=dict(cb["params"], loss=None), noise=False, aux=False), cands[0])
    changes = [x for x in changes if x != "Same structure as the baseline"]
    if cb.get("balanced"):
        changes.append("Weights both classes equally")
    if cb.get("calibrate"):
        changes.append("Calibrates the probabilities with a logistic (Platt) map learned inside each training fold")
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed the candidates: Hurricane's physics features, measurable structure, "
                     "element fractions, balanced classes, a seed bag and calibrated probabilities"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by parent compound on {len(y):,} 3DSC entries; leave-one-family-out "
                      "reported separately; graded materials never used for training or selection"),
        "rule": (f"release the design with the lowest log loss that beats the composition-only baseline on average and "
                 f"in at least {P.ADOPT_FOLDS} of {P.N_FOLDS} folds; otherwise the best design stays experimental"),
        "caveat": ("the labels are SuperCon's chemical classes, a proxy for the pairing mechanism rather than a measurement "
                   "of it, and picking the best of several designs on the same folds makes its score slightly optimistic"),
        "scikit_learn": sklearn.__version__, "data": data,
        "baseline": {"id": ref["id"], "name": ref["name"], "scores": ref["scores"]},
        "leaderboard": leader, "best": best, "adopted": adopted, "spec": model_spec(cb, n_cols),
        "changes": changes or ["Same structure as the baseline"], "importance": importance, "lofo": lofo_rows,
        "known": known,
    }
    (P.RESULTS / "radar_round1.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"formula": df["formula_sc"], "class": labels, "group": groups, "unconventional": y,
                  "p_best": preds[best["id"]], "p_baseline": preds["R0"]}).round(4).to_csv(
        P.RESULTS / "radar_round1_predictions.csv", index=False)
    update_progress(out)


if __name__ == "__main__":
    run()
