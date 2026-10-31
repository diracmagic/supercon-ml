"""Hurricane, round 2: new designs for unconventional superconductors, released only if they beat Hurricane 1.0.

Round 1 released Hurricane 1.0 (H4: composition statistics, measurable structure, physics features and element
shares, gradient boosting on log(1 + Tc)). In round 2 an AI agent (Claude) proposed:

    H9   Hurricane 1.0 + structure types: which known structure family a formula belongs to, read from its
         stoichiometry (123, 214 and electron-doped cuprates, Bi-, Tl- and Hg-based cuprates, infinite-layer cuprates;
         1111, 122, 111 and 11 iron-based compounds; 115 and 122 heavy-fermion compounds; nickelates)
    H10  Hurricane 1.0 in two parts: the probability that a compound superconducts at all, times the Tc expected if
         it does
    H11  the same two parts with the median rule: the expected Tc where superconductivity is more likely than not,
         zero elsewhere (for a target that is often exactly zero, the median is what minimises the absolute error)
    H12  structure types and two parts
    H13  structure types and two parts with the median rule
    H14  Hurricane 1.0 with one model per family (cuprates, iron- and nickel-based, heavy-fermion, other oxides)
    H15  structure types, average of five seeds

H0 (composition only) and H4 (Hurricane 1.0) are retrained on the same folds as round 1. A design is released as
Hurricane 2.0 only if it beats Hurricane 1.0 on average and in at least 4 of the 5 folds and is not more than 0.5 K
worse on the superconducting entries, so it cannot win by predicting zero where a superconductor is uncertain.

Run from the repository root:  python ml/pipeline.py hurricane2
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd

import hurricane as H
import pipeline as P

ROUND = 2
SC_TOLERANCE = 0.5   # K: a new version may not be worse than the current one on superconducting entries by more
CLF_PARAMS = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=10, l2_regularization=1.0)

RE = {"Y", "Sc", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"}
AE = {"Ca", "Sr", "Ba", "Mg"}
ALK = {"Li", "Na", "K", "Rb", "Cs"}
PNICTOGEN = {"P", "As", "Sb"}
CHALCOGEN = {"S", "Se", "Te"}
HF_F = {"Ce", "U", "Pu", "Yb", "Np", "Pr"}
TYPE_RATIONALE = {
    "123_cuprate": "RE Ba2 Cu3 O6+x stoichiometry (YBCO and its rare-earth cousins): two CuO2 planes next to CuO chains",
    "214_cuprate": "A2 CuO4 stoichiometry (La2-xSrxCuO4 and relatives): single CuO2 planes in a rock-salt stack",
    "electron_doped_cuprate": "A2 CuO4 with cerium on the A site (Nd2-xCexCuO4, T' structure): doped with electrons",
    "Bi_cuprate": "bismuth with strontium, copper and oxygen: the Bi-2201, 2212 and 2223 series",
    "Tl_cuprate": "thallium-based cuprates, among the highest Tc at ambient pressure",
    "Hg_cuprate": "mercury-based cuprates, the record-holding Hg-12(n-1)n series",
    "infinite_layer_cuprate": "A CuO2 with no other charge reservoir: infinite-layer (Sr,Ca)CuO2",
    "1111_pnictide": "RE (or alkaline earth) Fe As O/F with one of each: the LaFeAsO family, Tc up to 55 K",
    "122_pnictide": "A Fe2 As2 with an alkaline-earth or alkali A: the BaFe2As2 family",
    "111_pnictide": "A Fe As with an alkali A: LiFeAs and NaFeAs",
    "11_chalcogenide": "Fe with Se, Te or S and no other cation: FeSe and Fe(Se,Te)",
    "122_chalcogenide": "an alkali with Fe2Se2: intercalated iron selenides such as KxFe2-ySe2",
    "nickel_pnictide": "nickel instead of iron in the pnictide or chalcogenide layer: low-Tc cousins such as LaNiAsO",
    "115_heavy_fermion": "an f element, a Co, Rh or Ir atom and five In or Ga atoms: the CeCoIn5 family",
    "122_heavy_fermion": "an f element with two transition-metal and two Si or Ge atoms: the CeCu2Si2 (ThCr2Si2) family",
    "nickelate_oxide": "nickel oxides without copper: the nickelate family, in 3DSC mostly non-superconducting",
    "bismuthate_oxide": "bismuth oxides with Ba or K and no copper: Ba1-xKxBiO3 and BaPb1-xBixO3, Tc up to about 30 K",
    "ruthenate_oxide": "ruthenium oxides with strontium: Sr2RuO4, a long-debated candidate for unconventional pairing",
    "cobaltate_oxide": "cobalt oxides with sodium: NaxCoO2, superconducting when hydrated",
}


def _near(x: float, target: float, tol: float) -> bool:
    return abs(x - target) <= tol


def structure_types(comp: dict) -> dict:
    """Indicators of known structure families, read from the stoichiometry alone (1 if the formula fits)."""
    n = {e: float(v) for e, v in comp.items() if v > 0}
    g = lambda s: sum(n.get(e, 0.0) for e in sorted(s))   # noqa: E731  (sorted: a set's order depends on hashing)
    cu, o, fe, ni = n.get("Cu", 0.0), n.get("O", 0.0), n.get("Fe", 0.0), n.get("Ni", 0.0)
    re_, ae, alk, pn, ch = g(RE), g(AE), g(ALK), g(PNICTOGEN), g(CHALCOGEN)
    out = {k: 0.0 for k in TYPE_RATIONALE}
    if cu > 0 and o > 0:
        r = lambda v: v / cu   # noqa: E731
        if 0.45 <= r(n.get("Ba", 0.0)) <= 0.75 and 0.2 <= r(re_) <= 0.42 and 1.8 <= r(o) <= 2.5:
            out["123_cuprate"] = 1.0
        if 1.6 <= r(re_ + ae) <= 2.4 and 3.4 <= r(o) <= 4.6:
            out["214_cuprate"] = 1.0
            if n.get("Ce", 0.0) > 0 and g({"Nd", "Pr", "Sm", "Eu", "Gd"}) > 0:
                out["electron_doped_cuprate"] = 1.0
        if n.get("Bi", 0.0) > 0 and n.get("Sr", 0.0) > 0:
            out["Bi_cuprate"] = 1.0
        if n.get("Tl", 0.0) > 0:
            out["Tl_cuprate"] = 1.0
        if n.get("Hg", 0.0) > 0:
            out["Hg_cuprate"] = 1.0
        if 0.7 <= r(ae + re_) <= 1.3 and re_ <= 0.2 * cu and 1.6 <= r(o) <= 2.4 and g({"Bi", "Tl", "Hg", "Pb", "Ba"}) == 0:
            out["infinite_layer_cuprate"] = 1.0
    tm = fe + ni
    if tm > 0 and pn + ch > 0:
        r = lambda v: v / tm   # noqa: E731
        if pn > 0 and 0.6 <= r(re_ + ae) <= 1.4 and 0.6 <= r(pn) <= 1.4 and 0.4 <= r(o + n.get("F", 0.0) + n.get("H", 0.0)) <= 1.4:
            out["1111_pnictide"] = 1.0
        elif pn > 0 and 0.35 <= r(ae + alk + n.get("Eu", 0.0)) <= 0.65 and 0.75 <= r(pn) <= 1.25:
            out["122_pnictide"] = 1.0
        elif pn > 0 and 0.7 <= r(alk) <= 1.3 and 0.7 <= r(pn) <= 1.3:
            out["111_pnictide"] = 1.0
        if ch > 0 and pn == 0:
            if 0.7 <= r(ch) <= 1.4 and (re_ + ae + alk) <= 0.1 * tm:
                out["11_chalcogenide"] = 1.0
            elif 0.15 <= r(alk) <= 0.65 and 0.75 <= r(ch) <= 1.3:
                out["122_chalcogenide"] = 1.0
        if ni > fe:
            out["nickel_pnictide"] = 1.0
    f = g(HF_F)
    if f > 0:
        tmx = g({"Co", "Rh", "Ir"})
        inga = g({"In", "Ga"})
        if tmx > 0 and _near(tmx / f, 1.0, 0.35) and _near(inga / f, 5.0, 1.2):
            out["115_heavy_fermion"] = 1.0
        tm2 = g({"Cu", "Ni", "Pd", "Rh", "Ru", "Co", "Fe", "Pt", "Au", "Ir", "Os"})
        sige = g({"Si", "Ge"})
        if tm2 > 0 and _near(tm2 / f, 2.0, 0.5) and _near(sige / f, 2.0, 0.5):
            out["122_heavy_fermion"] = 1.0
    if o > 0 and cu == 0:
        if ni > 0 and pn + ch == 0:   # an oxypnictide such as LaNiAsO is a nickel pnictide, not a nickelate
            out["nickelate_oxide"] = 1.0
        if n.get("Bi", 0.0) > 0 and g({"Ba", "K"}) > 0:
            out["bismuthate_oxide"] = 1.0
        if n.get("Ru", 0.0) > 0 and n.get("Sr", 0.0) > 0:
            out["ruthenate_oxide"] = 1.0
        if n.get("Co", 0.0) > 0 and n.get("Na", 0.0) > 0:
            out["cobaltate_oxide"] = 1.0
    return out


# ---------------------------------------------------------------- designs


def _fit_clf(X, labels, seed):
    from sklearn.ensemble import HistGradientBoostingClassifier
    empty = ~np.isfinite(X).any(axis=0)   # as in hurricane._fit: a feature with no value in this training set
    if empty.any():
        X = X.copy()
        X[:, empty] = 0.0
    m = HistGradientBoostingClassifier(random_state=seed, **CLF_PARAMS)
    m.fit(X, labels)
    return m


class Design:
    """One candidate fitted on one training set: gradient boosting on log(1 + Tc), optionally with a classifier for
    whether the compound superconducts (two parts) and optionally one model per family."""

    def __init__(self, c: dict, seed: int):
        self.c, self.seed = c, seed

    def fit(self, X, y, fam):
        c = self.c
        if c.get("per_family"):
            base = dict(c, per_family=False)
            self.parts = {f: Design(base, self.seed).fit(X[fam == f], y[fam == f], fam[fam == f]) for f in np.unique(fam)}
            self.pooled = Design(base, self.seed).fit(X, y, fam)   # for a family with no training rows (leave one out)
            return self
        sc = y > 0
        if c.get("two_part"):
            self.clf = _fit_clf(X, sc.astype(int), self.seed) if 0 < sc.sum() < len(y) else None
            self.reg = H._fit(X[sc], np.log1p(y[sc]), c["params"], self.seed, n_bags=c.get("bags", 1))
        else:
            self.reg = H._fit(X, np.log1p(y), c["params"], self.seed, n_bags=c.get("bags", 1))
        return self

    def predict(self, X, fam):
        c = self.c
        if c.get("per_family"):
            out = np.zeros(len(X))
            for f in np.unique(fam):
                m = fam == f
                out[m] = self.parts.get(f, self.pooled).predict(X[m], fam[m])
            return out
        tc = np.clip(np.expm1(H._predict(self.reg, X)), 0, None)
        if c.get("two_part") and self.clf is not None:
            p = self.clf.predict_proba(X)[:, 1]
            return np.where(p >= 0.5, tc, 0.0) if c["two_part"] == "median" else p * tc
        return tc

    def explain(self, X, fam) -> dict:
        """The parts of one prediction (the first row of X): the probability that the compound superconducts and the
        regressor's Tc if it does (for a one-part design only the Tc). The app animates these."""
        if self.c.get("per_family"):
            return self.parts.get(fam[0], self.pooled).explain(X, fam)
        tc = float(np.clip(np.expm1(H._predict(self.reg, X[:1])), 0, None)[0])
        p = float(self.clf.predict_proba(X[:1])[:, 1][0]) if self.c.get("two_part") and self.clf is not None else None
        return {"p_sc": None if p is None else round(p, 3), "tc_sc": round(tc, 2), "rule": self.c.get("two_part")}


def run_design(c: dict, mats: dict, y, fam, splits):
    X = mats[c["X"]]
    pred, fitted = np.zeros(len(y)), []
    for k, (tr, te) in enumerate(splits):
        d = Design(c, P.SEED + k).fit(X[tr], y[tr], fam[tr])
        pred[te] = d.predict(X[te], fam[te])
        fitted.append((d, te))
    return pred, fitted


def importance(fitted, X, y, fam, names, n_repeats=3) -> list:
    """Mean increase of the out-of-fold Tc error (K) when one input is shuffled within each test fold."""
    rng = np.random.default_rng(P.SEED)
    gain = np.zeros(len(names))
    for d, te in fitted:
        Xte = X[te]
        base = np.abs(d.predict(Xte, fam[te]) - y[te]).mean()
        for j in range(len(names)):
            inc = 0.0
            for _ in range(n_repeats):
                Xp = Xte.copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                inc += np.abs(d.predict(Xp, fam[te]) - y[te]).mean() - base
            gain[j] += inc / n_repeats * len(te) / len(y)
    order = np.argsort(-gain)
    return [{"name": names[j], "gain": round(float(gain[j]), 3)} for j in order[:15]]


def lofo(c: dict, X, y, fam) -> list:
    """Leave one family out with the given design (a per-family design falls back to its pooled model)."""
    out = []
    for f in H.FAMILY_LABEL:
        te, tr = np.where(fam == f)[0], np.where(fam != f)[0]
        if len(te) < 10:
            continue
        p = Design(c, P.SEED + 300).fit(X[tr], y[tr], fam[tr]).predict(X[te], fam[te])
        med = float(np.median(y[tr]))
        out.append({"family": f, "label": H.FAMILY_LABEL[f], "n": int(len(te)), "mae": float(np.abs(p - y[te]).mean()),
                    "mae_median": float(np.abs(med - y[te]).mean()), "max_tc": float(y[te].max()), "max_pred": float(p.max())})
    return out


# physics inputs shown with each anchor in the app (the holes per Cu and its dome, CuO2 planes, the d count, ...)
EXPLAIN_PHYSICS = ("p_cu", "dome", "cu_layers", "tm_d", "heavy_block", "fe_based", "f_share", "nonint")


def report_spread(dsc: pd.DataFrame, formulas, y, preds: dict) -> dict:
    """How far repeated reports of the same formula in SuperCon (via 3DSC) disagree: for every formula listed with more
    than one Tc, each distinct value against the mean of the others. No model can be expected to beat this on those
    compounds, so it is a floor for Hurricane's error. Also: each model's error on the same formulas."""
    df = dsc[dsc["sc_class"].isin(set(H.FAMILY_OF_CLASS))].copy()
    df["tc"] = pd.to_numeric(df["tc"], errors="coerce")
    df = df[np.isfinite(df["tc"]) & (df["tc"] >= 0)]
    devs, multi = [], set()
    n_rows = df.groupby("formula_sc").size()
    for f, g in df.groupby("formula_sc"):
        vals = np.unique(np.round(g["tc"].to_numpy(float), 2))   # rows repeated for several matched structures count once
        if len(vals) < 2:
            continue
        multi.add(f)
        for i in range(len(vals)):
            devs.append(abs(vals[i] - np.delete(vals, i).mean()))
    m = np.array([f in multi for f in formulas])
    out = {"n_formulas": int(len(n_rows)), "n_with_rows": int((n_rows > 1).sum()), "n_with_reports": int(len(multi)),
           "spread_mae": round(float(np.mean(devs)), 2) if devs else None,
           "spread_median": round(float(np.median(devs)), 2) if devs else None,
           "model_mae": {k: round(float(np.abs(v[m] - y[m]).mean()), 2) for k, v in preds.items()} if m.any() else None,
           "about": ("formulas that SuperCon lists with more than one Tc; each distinct value against the mean of the "
                     "others, which no model can beat on those compounds")}
    return out


def anchors(final: Design, c: dict, table, elements: list) -> dict:
    """Hurricane's graded anchors (later discoveries), predicted by the final design; never used for selection."""
    ex = H.load_anchors()
    if not ex:
        return {}
    rows, listed = [], []
    for e in ex["materials"]:
        comp = {k: float(v) for k, v in e["composition"].items()}
        base = {"name": e["name"], "tc_exp": e.get("tc_exp"), "status": e["status"], "use": e["use"],
                "family": e.get("family"), "source": e.get("source"), "note": e.get("note", "")}
        if any(el not in table.index for el in comp):
            listed.append(dict(base, pred=None, why="element outside the training data"))
            continue
        st = H.anchor_structure(e["structure"]) if e.get("structure") else {}
        blocks = {"A": pd.DataFrame([H.composition_row(comp, table)]), "C": pd.DataFrame([H.physics_row(comp)]),
                  "B": pd.DataFrame([H.structure_row(st, comp, table)]), "D": H.element_fractions([comp], elements),
                  "E": pd.DataFrame([structure_types(comp)])}
        X = np.hstack([blocks[b].to_numpy(float) for b in c["X"]])
        fam = np.array([e.get("family") or "unknown"])
        row = dict(base, pred=round(float(final.predict(X, fam)[0]), 2), **final.explain(X, fam))
        ph = blocks["C"].iloc[0]
        row["physics"] = {k: round(float(ph[k]), 3) for k in EXPLAIN_PHYSICS if k in ph and np.isfinite(ph[k])}
        row["types"] = [k for k, v in structure_types(comp).items() if v > 0]
        listed.append(row)
        if e["use"] == "score" and e.get("tc_exp") is not None:
            rows.append(row)
    n = len(rows)
    return {"summary": {"n_scored": n, "n_listed": len(listed),
                        "mae": round(float(np.mean([abs(r["pred"] - r["tc_exp"]) for r in rows])), 2) if n else None,
                        "scored_as_check": n >= H.ANCHOR_MIN_N,
                        "rule": f"reported as a score only with at least {H.ANCHOR_MIN_N} scored measurements; never used "
                                "for training or for choosing the design", "about": ex.get("about", "")},
            "table": listed, "sources": ex.get("sources", {})}


# ---------------------------------------------------------------- spec


def model_spec(c: dict, n_cols: dict) -> dict:
    spec = H.model_spec(dict(c, X=c["X"].replace("E", "")), n_cols)
    if "E" in c["X"]:
        spec["inputs"].append({"group": "types", "label": "Structure types proposed by the AI", "n": n_cols["E"],
                               "items": [{"name": k, "why": v} for k, v in TYPE_RATIONALE.items()]})
    if c.get("two_part"):
        spec["learner"]["two_part"] = ("a gradient-boosting classifier gives the probability that the compound "
                                       "superconducts; the regressor, trained on superconductors only, gives its Tc; " +
                                       ("the prediction is that Tc where the probability is at least one half, else zero"
                                        if c["two_part"] == "median" else "the prediction is their product"))
    if c.get("per_family"):
        spec["learner"]["per_family"] = "one model per family, trained on that family only"
    return spec


def spec_changes(c: dict, ref: dict) -> list:
    out = [x for x in H.spec_changes(dict(c, X=c["X"].replace("E", "")), ref) if x != "Same structure as the baseline"]
    if "E" in c["X"]:
        out.append("Adds structure types proposed by the AI, read from the stoichiometry: 123, 214, electron-doped, Bi-, "
                   "Tl-, Hg-based and infinite-layer cuprates; 1111, 122, 111 and 11 iron-based compounds; 115 and 122 "
                   "heavy-fermion compounds; nickel pnictides; nickelate, bismuthate, ruthenate and cobaltate oxides")
    if c.get("two_part"):
        out.append("Splits the prediction in two: whether the compound superconducts, and its Tc if it does" +
                   (", predicting zero where superconductivity is less likely than not" if c["two_part"] == "median" else ""))
    if c.get("per_family"):
        out.append("Trains one model per family")
    return out or ["Same structure as the baseline"]


# ---------------------------------------------------------------- run


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    P.RESULTS.mkdir(exist_ok=True)
    dsc = H.load_3dsc()
    hur = H.build_frame(dsc, set(H.FAMILY_OF_CLASS))
    conv = H.build_frame(dsc, H.CONVENTIONAL)
    anchors_in = H.load_anchors()
    symbols = sorted({e for c in list(hur["comp"]) + list(conv["comp"]) for e in c} |
                     {e for a in anchors_in.get("materials", []) for e in a["composition"]})
    table = P.element_table(symbols)
    y = hur["tc"].to_numpy(float)
    groups = hur["group"].to_numpy()
    fam = hur["family"].to_numpy()
    blocks = H.feature_blocks(hur, table, [H.dsc_structure(r) for _, r in hur.iterrows()])
    counts = {}
    for c in hur["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = H.element_fractions(hur["comp"], elements)
    blocks["E"] = pd.DataFrame([structure_types(c) for c in hur["comp"]])
    names = {b: list(blocks[b].columns) for b in blocks}
    n_cols = {b: len(names[b]) for b in names}
    mats = {key: np.hstack([blocks[b].to_numpy(float) for b in key]) for key in ("A", "ABCD", "ABCDE")}
    hits = {k: int(blocks["E"][k].sum()) for k in TYPE_RATIONALE}
    P.log(f"Hurricane round 2: {len(hur)} entries ({int((y > 0).sum())} superconducting) in {len(set(groups))} parent "
          f"groups; structure types found: " + ", ".join(f"{k} {v}" for k, v in hits.items()))
    for k in TYPE_RATIONALE:   # which family each type lands in, as a sanity check of the stoichiometry rules
        m = blocks["E"][k].to_numpy(float) > 0
        if m.any():
            P.log(f"  {k}: " + ", ".join(f"{f} {int((fam[m] == f).sum())}" for f in H.FAMILY_LABEL if (fam[m] == f).any()) +
                  f"; mean Tc {y[m].mean():.1f} K")
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats["A"], y, groups))
    folds = [te for _, te in splits]
    PR = H.PARAMS
    cands = [
        {"id": "H0", "name": "Composition only (baseline)", "settings": "default", "X": "A", "params": PR},
        {"id": "H4", "name": "Composition + structure + physics + element fractions", "settings": "Hurricane 1.0", "X": "ABCD", "params": PR},
        {"id": "H9", "name": "Hurricane 1.0 + structure types", "settings": "default", "X": "ABCDE", "params": PR},
        {"id": "H10", "name": "Hurricane 1.0 in two parts", "settings": "probability times Tc", "X": "ABCD", "params": PR, "two_part": "mean"},
        {"id": "H11", "name": "Hurricane 1.0 in two parts", "settings": "median rule", "X": "ABCD", "params": PR, "two_part": "median"},
        {"id": "H12", "name": "Hurricane 1.0 + structure types, in two parts", "settings": "probability times Tc", "X": "ABCDE", "params": PR, "two_part": "mean"},
        {"id": "H13", "name": "Hurricane 1.0 + structure types, in two parts", "settings": "median rule", "X": "ABCDE", "params": PR, "two_part": "median"},
        {"id": "H14", "name": "Hurricane 1.0, one model per family", "settings": "default", "X": "ABCD", "params": PR, "per_family": True},
        {"id": "H15", "name": "Hurricane 1.0 + structure types", "settings": "average of 5 seeds", "X": "ABCDE",
         "params": dict(PR, max_features=0.8), "bags": 5},
    ]
    board, preds, fits = [], {}, {}
    for c in cands:
        t0 = time.time()
        try:
            p, fitted = run_design(c, mats, y, fam, splits)
        except (TypeError, ValueError) as err:   # e.g. an option this scikit-learn version lacks
            P.log(f"{c['id']} skipped: {err}")
            continue
        s = H.scores(y, p, fam, folds)
        board.append(dict(c, scores=s, n_features=int(mats[c["X"]].shape[1]), seconds=round(time.time() - t0)))
        preds[c["id"]], fits[c["id"]] = p, fitted
        P.log(f"{c['id']} {c['name']} [{c['settings']}]: MAE {s['tc_mae']:.2f} K (superconductors {s['sc_mae']:.2f} K, "
              f"Tc >= {H.HIGH_TC:.0f} K {s['high_tc_mae']:.2f} K), {board[-1]['seconds']} s; " +
              ", ".join(f"{f} {v['mae']:.2f}" for f, v in s["by_family"].items()))
    base = next(r for r in board if r["id"] == "H0")
    prev = next(r for r in board if r["id"] == "H4")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], base["scores"]["fold_mae"])))
        r["folds_better_previous"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], prev["scores"]["fold_mae"])))
    new = [r for r in board if r["id"] not in ("H0", "H4")]
    eligible = [r for r in new if r["scores"]["tc_mae"] < prev["scores"]["tc_mae"] and r["folds_better_previous"] >= P.ADOPT_FOLDS
                and r["scores"]["sc_mae"] <= prev["scores"]["sc_mae"] + SC_TOLERANCE]
    adopted = bool(eligible)
    best = min(eligible or new, key=lambda r: r["scores"]["tc_mae"])
    cb = next(c for c in cands if c["id"] == best["id"])
    feat_names = [n for b in cb["X"] for n in names[b]]
    imp = importance(fits[best["id"]], mats[cb["X"]], y, fam, feat_names)
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.2f} K)" for i in imp[:8]))
    lofo_rows = lofo(cb, mats[cb["X"]], y, fam)
    lofo_ref = {r["family"]: r for r in lofo(cands[0], mats["A"], y, fam)}
    for r in lofo_rows:
        r["mae_cv"] = float(np.abs(preds[best["id"]][fam == r["family"]] - y[fam == r["family"]]).mean())
        r["mae_baseline"] = lofo_ref[r["family"]]["mae"] if r["family"] in lofo_ref else None
        P.log(f"leave one family out, {r['family']}: MAE {r['mae']:.2f} K (baseline design {r['mae_baseline']:.2f} K, "
              f"training median {r['mae_median']:.2f} K)")
    floor = report_spread(dsc, hur["formula_sc"].tolist(), y, {"best": preds[best["id"]], "previous": preds["H4"]})
    if floor["spread_mae"] is not None:
        P.log(f"repeated reports: {floor['n_with_reports']} of {floor['n_formulas']} formulas have more than one Tc; they "
              f"differ from the mean of the others by {floor['spread_mae']:.2f} K on average (median "
              f"{floor['spread_median']:.2f} K); on those formulas {best['id']} is off by {floor['model_mae']['best']:.2f} K "
              f"and Hurricane 1.0 by {floor['model_mae']['previous']:.2f} K")
    else:
        P.log(f"repeated reports: none of the {floor['n_formulas']} formulas has more than one distinct Tc in 3DSC "
              f"({floor['n_with_rows']} appear in several rows with the same Tc)")
    final = Design(cb, P.SEED + 500).fit(mats[cb["X"]], y, fam)
    anchors_out = anchors(final, cb, table, elements)
    if anchors_out:
        a = anchors_out["summary"]
        P.log(f"anchors: {a['n_listed']} listed, {a['n_scored']} scored, MAE {a['mae']} K; " + "; ".join(
            f"{r['name']} {r['tc_exp']} K -> {r['pred']} K" for r in anchors_out["table"] if r.get("pred") is not None))
    version = f"{ROUND}.0"
    fam_stats = {f: {"label": H.FAMILY_LABEL[f], "n": int((fam == f).sum()), "n_sc": int(((fam == f) & (y > 0)).sum()),
                     "max_tc": float(y[fam == f].max())} for f in H.FAMILY_LABEL if (fam == f).any()}
    data = {"source": "3DSC_MP (SuperCon measured Tc matched to Materials Project structures)", "cite": H.DSC_CITE,
            "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": H.DSC_COMMIT[:7],
            "n": int(len(y)), "n_sc": int((y > 0).sum()), "n_groups": int(len(set(groups))), "families": fam_stats,
            "context": int(len(conv))}
    P.log(f"Hurricane {version} = {best['id']} {best['name']} [{best['settings']}]: MAE {best['scores']['tc_mae']:.2f} K "
          f"(Hurricane 1.0 {prev['scores']['tc_mae']:.2f} K, better in {best['folds_better_previous']}/{P.N_FOLDS} folds; "
          f"superconductors {best['scores']['sc_mae']:.2f} K against {prev['scores']['sc_mae']:.2f} K; adopted: {adopted})")
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": H.MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed the candidates: structure types read from the stoichiometry, a two-part "
                     "model (does it superconduct, and at what Tc) with a mean and a median rule, one model per family "
                     "and a seed bag"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by parent compound on {len(y):,} 3DSC entries, the same folds as round 1; "
                      "leave-one-family-out reported separately; anchors never used for training or selection"),
        "rule": (f"release the lowest-error design that beats Hurricane 1.0 on average and in at least {P.ADOPT_FOLDS} of "
                 f"{P.N_FOLDS} folds and is not more than {SC_TOLERANCE} K worse on the superconducting entries"),
        "caveat": ("SuperCon Tc values are averages over reports of varying quality, doped entries borrow the structure of "
                   "their parent compound, and picking the best of several designs on the same folds makes its score "
                   "slightly optimistic"),
        "scikit_learn": sklearn.__version__, "data": data, "structure_types": TYPE_RATIONALE, "type_counts": hits,
        "baseline": {"id": base["id"], "name": base["name"], "scores": base["scores"]},
        "previous": {"id": prev["id"], "version": "1.0", "scores": prev["scores"]},
        "leaderboard": sorted(board, key=lambda r: r["scores"]["tc_mae"]), "best": best, "adopted": adopted,
        "spec": model_spec(cb, n_cols), "changes": spec_changes(cb, cands[0]), "importance": imp, "lofo": lofo_rows,
        "anchors": anchors_out or None, "floor": floor, "minutes": round((time.time() - t_start) / 60, 1),
    }
    for r in out["leaderboard"]:
        r["params"] = dict(r["params"])
    (P.RESULTS / f"hurricane_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"formula": hur["formula_sc"], "family": fam, "group": groups, "tc": y,
                  "tc_pred_best": preds[best["id"]], "tc_pred_hurricane1": preds["H4"], "tc_pred_baseline": preds["H0"]}
                 ).round(3).to_csv(P.RESULTS / f"hurricane_round{ROUND}_predictions.csv", index=False)
    update_progress(out)


def update_progress(out: dict) -> None:
    """Round 2's entry in the "hurricane" block, in the same form as round 1 (scores against the composition-only
    baseline, which the app compares with), plus the comparison with Hurricane 1.0 that decides the release."""
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, ref, prev, ver = out["best"], out["baseline"], out["previous"], out["version"]
    sc, r2 = best["scores"], lambda v: round(float(v), 2)   # noqa: E731
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"] + ("" if best["settings"] in ("default", "Hurricane 1.0") else f", {best['settings']}"),
        "changes": out["changes"], "spec": out["spec"], "rule": out["rule"],
        "scores": {"tc_mae": r2(sc["tc_mae"]), "reference_mae": r2(ref["scores"]["tc_mae"]), "reference": ref["name"],
                   "folds": [r2(x) for x in sc["fold_mae"]], "reference_folds": [r2(x) for x in ref["scores"]["fold_mae"]],
                   "folds_better": best["folds_better"],
                   "sc_mae": r2(sc["sc_mae"]) if sc["sc_mae"] is not None else None,
                   "high_tc_mae": r2(sc["high_tc_mae"]) if sc["high_tc_mae"] is not None else None,
                   "high_tc": H.HIGH_TC, "r2_log": round(sc["r2_log"], 3),
                   "by_family": {f: {"n": v["n"], "mae": r2(v["mae"]), "mae_ref": r2(ref["scores"]["by_family"][f]["mae"])}
                                 for f, v in sc["by_family"].items()}},
        "previous": {"version": prev["version"], "tc_mae": r2(prev["scores"]["tc_mae"]),
                     "folds": [r2(x) for x in prev["scores"]["fold_mae"]], "folds_better": best["folds_better_previous"],
                     "sc_mae": r2(prev["scores"]["sc_mae"]), "high_tc_mae": r2(prev["scores"]["high_tc_mae"])},
        "lofo": [{k: (r2(v) if isinstance(v, float) else v) for k, v in r.items()} for r in out["lofo"]],
        "importance": out["importance"],
        "search": {"candidates": len(out["leaderboard"]), "reference_id": "H0", "previous_id": "H4",
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"], "tc_mae": r2(r["scores"]["tc_mae"]),
                                    "sc_mae": r2(r["scores"]["sc_mae"]), "folds_better": r["folds_better"],
                                    "folds_better_previous": r["folds_better_previous"]} for r in out["leaderboard"]]},
    }
    if out.get("anchors"):
        a = out["anchors"]
        entry["anchors"] = {"n_scored": a["summary"]["n_scored"], "mae": a["summary"]["mae"],
                            "scored_as_check": a["summary"]["scored_as_check"], "rule": a["summary"]["rule"],
                            "table": [dict({"name": r["name"], "tc_exp": r["tc_exp"], "status": r["status"], "use": r["use"],
                                            "family": r.get("family"), "pred": r.get("pred"), "note": r.get("note", "")},
                                           **{k: r[k] for k in ("p_sc", "tc_sc", "rule", "physics", "types") if k in r})
                                      for r in a["table"]]}
    if out.get("floor"):
        entry["floor"] = out["floor"]
    reg = prog.get("hurricane") or {}
    versions = sorted([v for v in reg.get("versions", []) if v.get("round") != ROUND] + [entry], key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    cur = released[-1] if released else None
    block = dict(reg)
    block.update({"name": H.MODEL, "current": cur["version"] if cur else None, "data": out["data"], "versions": versions})
    prog["hurricane"] = block
    if out["adopted"]:
        data = out["data"]
        note = (f"5-fold CV grouped by parent compound; {data['n']:,} cuprates, iron-based, heavy-fermion and other oxides "
                f"from 3DSC (SuperCon + Materials Project), {data['n_sc']:,} superconducting")
        prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
            {"tag": "hurricane", "model": f"{H.MODEL} {ver} (AI-designed)", "target": "Tc_exp", "mae": r2(sc["tc_mae"]),
             "unit": "K", "note": note},
            {"tag": "hurricane", "model": "Gradient boosting, composition only (measured-Tc baseline)", "target": "Tc_exp",
             "mae": r2(ref["scores"]["tc_mae"]), "unit": "K", "note": "Same data and folds"}]
        lof = {r["family"]: r for r in out["lofo"]}
        text = (f"Learns from {data['n']:,} measured Tc values (cuprates, iron-based, heavy-fermion and other oxides; "
                f"SuperCon with Materials Project structures via 3DSC), including {data['n'] - data['n_sc']:,} materials "
                f"that did not superconduct. For compounds whose parent it never saw in training it is off by "
                f"{sc['tc_mae']:.1f} K on average, against {prev['scores']['tc_mae']:.1f} K for Hurricane 1.0 and "
                f"{ref['scores']['tc_mae']:.1f} K for a composition-only baseline.")
        if lof.get("cuprate"):
            text += (f" Predicting a whole family it never saw is much harder: trained without any cuprate, it misses "
                     f"cuprates by {lof['cuprate']['mae']:.0f} K.")
        text += " Our AI agent designed it."
        fam = [m for m in prog.get("model_family", []) if m.get("id") != "hurricane"]
        fam.append({"id": "hurricane", "status": f"{H.MODEL} {ver} in use", "active": True, "text": text})
        prog["model_family"] = fam
    H.ai_stage(prog)
    P.tidy(prog)
    prefix = f"{H.MODEL}, round {ROUND} ("
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(prefix)]   # a re-run replaces it
    P.add_log(prog, stamp, f"{H.MODEL}, round {ROUND} ({len(out['leaderboard']) - 2} AI-designed candidates): best "
                           f"{best['id']} {best['name']} [{best['settings']}], measured-Tc MAE {sc['tc_mae']:.2f} K against "
                           f"{prev['scores']['tc_mae']:.2f} K for Hurricane 1.0, better in {best['folds_better_previous']} of "
                           f"{P.N_FOLDS} folds (superconductors {sc['sc_mae']:.2f} K against {prev['scores']['sc_mae']:.2f} K); " +
                           (f"released as {H.MODEL} {ver}" if out["adopted"] else "not released, so Hurricane 1.0 stays in use"))
    prog["updated"] = stamp
    P.PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {H.MODEL} round {ROUND} ({entry['status']})")


if __name__ == "__main__":
    run()
