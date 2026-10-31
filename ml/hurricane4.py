"""Hurricane, round 4: "not known" instead of "unlikely" outside the training data.

Hurricane 3.0 learned from 1,714 compounds with no superconductivity record, counted as probably not superconducting,
and no longer calls ordinary compounds likely superconductors: of the held-out compounds of that kind that Radar sends
it, it gives none at least an even chance (Hurricane 2.0: 39%). The price showed in the leave-one-family-out test:
trained without a whole family, it calls almost all of that family's superconductors unlikely (99% of the cuprates and
of the heavy-fermion compounds), so it would dismiss a family that nobody has found yet. Far from everything it learned
from, a model has no basis to call a compound likely or unlikely; round 4 makes Hurricane say so.

In round 4 the AI agent (Claude) proposed four designs built on Hurricane 3.0 (H17). Each gives a chance only to
compounds near its training data, measured as for the app's "outside the training data" flag: the distance to the
nearest training compound in the model's standardized inputs, divided by the distance that separates 95% of the
training compounds from their nearest neighbour in another parent compound. Beyond a ratio of 1 a compound is outside
the training data, and there the design answers "not known".

    H19  Hurricane 3.0 as it is, no chance beyond a ratio of 1
    H20  background compounds only inside the training data (ratio up to 1), no chance beyond 1
    H21  background compounds up to a ratio of 2, no chance beyond 1
    H22  background compounds up to a ratio of 1.5, no chance beyond 1.5

H0, Hurricane 2.0 (H12) and Hurricane 3.0 (H17) are retrained on the same folds and seeds as before, the background
folds are round 3's, and every distance is measured against the training part of each fold only. Out of fold:

    false alarms     held-out compounds with no superconductivity record, sent to Hurricane by Radar, given at least
                     an even chance
    called unlikely  the superconductors of a family left out of training that get a chance under one half, averaged
                     over the four families; "not known" is not a dismissal
    coverage         the held-out 3DSC entries that get a chance at all
    measured Tc, the Brier score and the database swap, as in round 3

The rule, fixed before the run: release the design that calls the fewest superconductors of a left-out family unlikely,
among those that raise false alarms on at most 5% of the held-out compounds with no record, call no more of them
unlikely than Hurricane 2.0 does, give a chance to at least 85% of the held-out 3DSC entries, are not more than 0.3 K
worse than Hurricane 3.0 on measured Tc and 0.5 K on the superconducting entries, not more than 0.01 worse in Brier
score, and whose chance drops by at most 0.05 more than Hurricane 3.0's in the database swap. Ties go to fewer false
alarms, then to the lower Tc error.

The screening (ml/screen.py) then lists only the compounds the released design gives a chance; the others are counted
as not known.

Run from the repository root:  python ml/pipeline.py hurricane4
(HURRICANE4_SMOKE=1: a quick check on small data that writes into a temporary folder)
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

import hurricane as H
import hurricane2 as H2
import hurricane3 as H3
import pipeline as P
import screen as SC

ROUND = 4
SMOKE = os.environ.get("HURRICANE4_SMOKE") == "1"
# id: (background compounds up to this distance ratio, or None for all; no chance beyond this ratio)
DESIGNS = {"H19": (None, 1.0), "H20": (1.0, 1.0), "H21": (2.0, 1.0), "H22": (1.5, 1.5)}
SETTINGS = {"H19": "all background compounds", "H20": "background compounds inside the training data only",
            "H21": "background compounds up to twice as far", "H22": "no chance beyond 1.5 times as far, background as far"}
FA_MAX = 0.05        # at most 5% false alarms ...
COVERAGE_MIN = 0.85  # ... a chance for at least 85% of the held-out 3DSC entries ...
MAE_TOL = 0.3        # K, against Hurricane 3.0 ...
SC_TOL = 0.5         # K ...
BRIER_TOL = 0.01
SHIFT_TOL = 0.05
RULE = (f"release the design that calls the fewest superconductors of a left-out family unlikely, among those that raise "
        f"false alarms on at most {FA_MAX:.0%} of the held-out compounds with no superconductivity record that Radar "
        f"sends to Hurricane, call no more superconductors of a left-out family unlikely than Hurricane 2.0 does, give a "
        f"chance to at least {COVERAGE_MIN:.0%} of the held-out 3DSC entries, are not more than {MAE_TOL:g} K worse than "
        f"Hurricane 3.0 on measured Tc and {SC_TOL:g} K on the superconducting entries, not more than {BRIER_TOL:g} worse "
        f"in Brier score, and whose chance drops by at most {SHIFT_TOL:g} more than Hurricane 3.0's when 3DSC compounds "
        f"are described with JARVIS structures; ties go to fewer false alarms, then to the lower Tc error")
UNKNOWN_ABOUT = ("not known: a compound further from every training compound, in the model's standardized inputs, than "
                 "the given multiple of the distance that separates 95% of the training compounds from their nearest "
                 "neighbour in another parent compound gets no chance")
DISMISS_ABOUT = ("called unlikely: trained without a whole family, the share of that family's superconductors given a "
                 "chance under one half, averaged over the four families; a compound that gets no chance (not known) is "
                 "not counted as called unlikely")
CAVEAT = ("A chance far from the training data was never worth much; Hurricane now says so instead of giving one. Not "
          "known is not a hint that a compound superconducts: it means the model cannot tell. The background compounds "
          "have no superconductivity record, which is not a measurement of zero.")


def ratio(X_train, groups, X_query) -> np.ndarray:
    """Each query compound's distance to the nearest training compound over the 95% cross-group distance (screen.novelty)."""
    import warnings
    if not len(X_query):
        return np.zeros(0)
    with warnings.catch_warnings():   # an input with no value in this training part is all-NaN: screen.novelty zeroes it
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.asarray(SC.novelty(X_train, groups, X_query)["ratio"], float)


def background_use(c: dict, keep: np.ndarray, rb: np.ndarray) -> np.ndarray:
    """The background compounds a design learns from: those `keep` allows, within its radius if it has one."""
    use = keep.copy()
    if c.get("radius"):
        use &= rb <= c["radius"]
    return use


def unknown(c: dict, r: np.ndarray) -> np.ndarray:
    return r > c["abstain"] if c.get("abstain") else np.zeros(len(r), bool)


def run_design(c, X, y, fam, splits, sys3, Xb, fam_b, fold_b, sys_b, Xm, m_pos, r_te, r_b) -> dict:
    """One design out of fold, as hurricane3.run_design, with the "not known" answers: r_te[k] and r_b[k] are the
    distance ratios of fold k's held-out 3DSC entries and of every background compound to fold k's training part."""
    n, nb = len(y), len(Xb)
    pred, p3, tc3, unk3 = np.zeros(n), np.full(n, np.nan), np.zeros(n), np.zeros(n, bool)
    pb, predb, unkb = np.full(nb, np.nan), np.zeros(nb), np.zeros(nb, bool)
    pm = np.full(len(m_pos), np.nan)
    fitted, n_bg = [], []
    for k, (tr, te) in enumerate(splits):
        keep = H3.train_mask(k, fold_b, sys_b, set(sys3[te]))
        use = background_use(c, keep, r_b[k])
        d = H2.Design(c, P.SEED + k).fit(X[tr], y[tr], fam[tr], Xb=Xb[use] if c.get("background") else None)
        n_bg.append(int(use.sum()) if c.get("background") else 0)
        pred[te] = d.predict(X[te], fam[te])
        p3[te], tc3[te] = SC.hur_parts(d, X[te], fam[te])
        unk3[te] = unknown(c, r_te[k])
        tb = np.where(fold_b == k)[0]
        if len(tb):
            pb[tb] = SC.hur_parts(d, Xb[tb], fam_b[tb])[0]
            predb[tb] = d.predict(Xb[tb], fam_b[tb])
            unkb[tb] = unknown(c, r_b[k][tb])
        mi = np.where(np.isin(m_pos, te))[0]
        if len(mi):
            pm[mi] = SC.hur_parts(d, Xm[mi], fam[m_pos[mi]])[0]
        fitted.append((d, te))
    return {"pred": pred, "p": p3, "tc_sc": tc3, "unknown": unk3, "pb": pb, "predb": predb, "unknown_b": unkb, "pm": pm,
            "fitted": fitted, "n_bg": n_bg}


def reliability(o: dict, y, sent, fold_b, m_pos) -> dict:
    p = o["p"]
    if not np.isfinite(p).all():
        return {"false_alarms": None}
    sc = (y > 0).astype(float)
    alarm = (o["pb"] >= 0.5) & ~o["unknown_b"]
    folds = [float(alarm[sent & (fold_b == k)].mean()) if (sent & (fold_b == k)).any() else None for k in range(P.N_FOLDS)]
    likely = p >= 0.5
    cov = ~o["unknown"]
    dm = o["pm"] - p[m_pos] if len(m_pos) else np.zeros(0)
    return {"false_alarms": float(alarm[sent].mean()), "fa_folds": folds, "false_alarms_all": float(alarm.mean()),
            "unknown_sent": float(o["unknown_b"][sent].mean()), "unknown_all": float(o["unknown_b"].mean()),
            "coverage": float(cov.mean()), "brier": float(np.mean((p - sc) ** 2)),
            "recall": float(likely[sc > 0].mean()),
            "recall_covered": float(likely[(sc > 0) & cov].mean()) if ((sc > 0) & cov).any() else None,
            "share_sc_likely": float(sc[likely & cov].mean()) if (likely & cov).any() else None,
            "share_sc_unlikely": float(sc[~likely & cov].mean()) if (~likely & cov).any() else None,
            "shift": float(dm.mean()) if len(dm) else 0.0, "shift_abs": float(np.abs(dm).mean()) if len(dm) else 0.0,
            "n_matched": int(len(dm))}


def lofo(c: dict, X, y, fam, groups, Xb, lofo_r: dict) -> list:
    """Leave one family out: trained without a family (and with the background compounds the design allows, measured
    against the training families), how many of the family's superconductors it finds, cannot judge or calls unlikely."""
    out = []
    for f in H.FAMILY_LABEL:
        te, tr = np.where(fam == f)[0], np.where(fam != f)[0]
        if len(te) < 10:
            continue
        r_f, r_bf = lofo_r[f]
        use = background_use(c, np.ones(len(Xb), bool), r_bf)
        d = H2.Design(c, P.SEED + 300).fit(X[tr], y[tr], fam[tr], Xb=Xb[use] if c.get("background") else None)
        pr = d.predict(X[te], fam[te])
        pp = SC.hur_parts(d, X[te], fam[te])[0]
        unk = unknown(c, r_f)
        sc = y[te] > 0
        med = float(np.median(y[tr]))
        row = {"family": f, "label": H.FAMILY_LABEL[f], "n": int(len(te)), "n_sc": int(sc.sum()),
               "mae": float(np.abs(pr - y[te]).mean()), "mae_median": float(np.abs(med - y[te]).mean()),
               "max_tc": float(y[te].max()), "max_pred": float(pr.max())}
        if np.isfinite(pp).all() and sc.any():
            row.update(found=float(((pp >= 0.5) & ~unk)[sc].mean()), unknown=float(unk[sc].mean()),
                       dismissed=float(((pp < 0.5) & ~unk)[sc].mean()))
        out.append(row)
    return out


def mean_dismissed(rows: list):
    v = [r["dismissed"] for r in rows if r.get("dismissed") is not None]
    return float(np.mean(v)) if v else None


def anchor_ratios(c: dict, table, elements, X, groups) -> dict:
    """Each anchor's distance ratio to all of Hurricane's 3DSC entries, built as hurricane2.anchors builds its inputs."""
    ex = H.load_anchors()
    names, rows = [], []
    for e in ex.get("materials", []):
        comp = {k: float(v) for k, v in e["composition"].items()}
        if any(el not in table.index for el in comp):
            continue
        st = H.anchor_structure(e["structure"]) if e.get("structure") else {}
        blocks = {"A": pd.DataFrame([H.composition_row(comp, table)]), "C": pd.DataFrame([H.physics_row(comp)]),
                  "B": pd.DataFrame([H.structure_row(st, comp, table)]), "D": H.element_fractions([comp], elements),
                  "E": pd.DataFrame([H2.structure_types(comp)])}
        names.append(e["name"])
        rows.append(np.hstack([blocks[b].to_numpy(float) for b in c["X"]])[0])
    if not rows:
        return {}
    return dict(zip(names, ratio(X, groups, np.vstack(rows))))


def spec_changes(c: dict, ref: dict, n_bg: int) -> list:
    out = H3.spec_changes(dict(c, background=c.get("background")), ref, n_bg)
    if c.get("radius"):
        out[-1] = (f"Adds the compounds with no superconductivity record (Hurricane's JARVIS-DFT screening pool) that lie "
                   f"within {c['radius']:g} times the training data's spread, to the classifier as non-superconducting at "
                   f"weight {c['background']:g}, after Konno et al. (2021)")
    if c.get("abstain"):
        out.append("Gives no chance to a compound outside the training data" if c["abstain"] == 1 else
                   f"Gives no chance to a compound more than {c['abstain']:g} times as far from the training data as "
                   "the training compounds are from each other")
    return out


def model_spec(c: dict, n_cols: dict, n_bg: int) -> dict:
    spec = H3.model_spec(c, n_cols, n_bg)
    if c.get("radius"):
        spec["learner"]["background"] = (f"{n_bg:,} JARVIS-DFT compounds with no superconductivity record, within "
                                         f"{c['radius']:g} times the training data's spread, join the classifier as "
                                         f"non-superconducting at weight {c['background']:g}; the Tc regressor never sees them")
    if c.get("abstain"):
        spec["learner"]["not_known"] = ("no chance (not known) for a compound further from every training compound than "
                                        f"{c['abstain']:g} times the distance that separates 95% of the training compounds "
                                        "from their nearest neighbour in another parent compound")
    return spec


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    dsc = H.load_3dsc()
    hur = H.build_frame(dsc, set(H.FAMILY_OF_CLASS))
    conv = H.build_frame(dsc, H.CONVENTIONAL)
    anchors_in = H.load_anchors()
    rows = SC.load_rows()
    bg, bg_info = H3.background(rows, hur)
    if not len(bg):
        raise SystemExit("no background compounds: Hurricane's screening pool is empty")
    symbols = sorted({e for c in list(hur["comp"]) + list(conv["comp"]) + list(bg["comp"]) for e in c} |
                     {e for a in anchors_in.get("materials", []) for e in a["composition"]})
    table = P.element_table(symbols)
    y, groups, fam = hur["tc"].to_numpy(float), hur["group"].to_numpy(), hur["family"].to_numpy()
    sys3 = np.array([H3.chemsys_of(c) for c in hur["comp"]])
    blocks = H.feature_blocks(hur, table, [H.dsc_structure(r) for _, r in hur.iterrows()])
    counts = {}
    for c in hur["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = H.element_fractions(hur["comp"], elements)
    blocks["E"] = pd.DataFrame([H2.structure_types(c) for c in hur["comp"]], columns=list(H2.TYPE_RATIONALE))
    names = {b: list(blocks[b].columns) for b in blocks}
    n_cols = {b: len(names[b]) for b in names}
    # the designs: H0, Hurricane 2.0 and Hurricane 3.0 as released, and the four designs of this round
    ref_c, ref_ver = SC.hurricane_design(upto=2)
    cur_c, cur_ver = SC.hurricane_design(upto=3)
    if not cur_c.get("background") or not ref_c.get("two_part"):
        raise SystemExit(f"round 4 builds on Hurricane 3.0 (round 3's released design); the version in use is {cur_ver}")
    ref_c = dict(ref_c, id=ref_c.get("id") or "H12", name=f"Hurricane {ref_ver}", settings="as released")
    cur_c = dict(cur_c, id=cur_c.get("id") or "H17", name=f"Hurricane {cur_ver}", settings="as released")
    cands = [{"id": "H0", "name": "Composition only (baseline)", "settings": "default", "X": "A", "params": H.PARAMS},
             ref_c, cur_c]
    for cid, (radius, abstain) in DESIGNS.items():
        cands.append(dict(cur_c, id=cid, name=f"Hurricane {cur_ver} + not known outside the training data",
                          settings=SETTINGS[cid], radius=radius, abstain=abstain))
    keys = sorted({c["X"] for c in cands})
    if len({c["X"] for c in cands if c["id"] != "H0"}) != 1:
        raise SystemExit("the designs of round 4 must share their inputs")
    key = cur_c["X"]
    mats = {k: np.hstack([blocks[b].to_numpy(float) for b in k]) for k in keys}
    bblocks = SC.hur_blocks(bg, table, elements)
    for b in bblocks:
        if list(bblocks[b].columns) != names[b]:
            raise SystemExit(f"background inputs, block {b}, do not match the training inputs")
    mats_b = {k: np.hstack([bblocks[b].to_numpy(float) for b in k]) for k in keys}
    fam_b = np.array([SC.family_guess(cc) for cc in bg["comp"]])
    sys_b = bg["chemsys"].to_numpy()
    fold_b = np.array([H3.bg_fold(s) for s in sys_b])
    p_radar, radar_info = SC.radar_scores(bg)
    sent = np.asarray(p_radar, float) >= 0.5
    if not sent.any():
        raise SystemExit("Radar sends none of the background compounds to Hurricane: no false alarms to count")
    m_pos, m_rows = H3.matched(hur, rows)
    if len(m_pos):
        sts = [SC.radar_structure(rows.at[j, "atoms"], rows.at[j, "spg_number"], rows.at[j, "spg"]) for j in m_rows]
        Bj = pd.DataFrame([H.structure_row(s, c, table) for s, c in zip(sts, hur["comp"].iloc[m_pos])])[names["B"]]
    else:
        Bj = blocks["B"].iloc[:0]
    mats_m = {k: np.hstack([(Bj if b == "B" else blocks[b].iloc[m_pos].reset_index(drop=True)).to_numpy(float)
                            for b in k]) for k in keys}
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats["A"], y, groups))
    folds = [te for _, te in splits]
    # distances, once for all designs (they share their inputs): fold by fold, and family by family
    X, Xb = mats[key], mats_b[key]
    r_te, r_b = [], []
    for tr, te in splits:
        r = ratio(X[tr], groups[tr], np.vstack([X[te], Xb]))
        r_te.append(r[:len(te)])
        r_b.append(r[len(te):])
    lofo_r = {}
    for f in H.FAMILY_LABEL:
        te, tr = np.where(fam == f)[0], np.where(fam != f)[0]
        if len(te) >= 10:
            r = ratio(X[tr], groups[tr], np.vstack([X[te], Xb]))
            lofo_r[f] = (r[:len(te)], r[len(te):])
    r_all_b = ratio(X, groups, Xb)
    P.log(f"Hurricane round 4: {len(hur)} 3DSC entries, {len(bg):,} background compounds ({int(sent.sum())} sent by Radar); "
          f"held-out 3DSC entries outside the training data: {np.mean(np.concatenate(r_te) > 1):.3f}; background "
          f"compounds within a ratio of 1, 1.5 and 2 of all 3DSC entries: {int((r_all_b <= 1).sum())}, "
          f"{int((r_all_b <= 1.5).sum())}, {int((r_all_b <= 2).sum())}; " +
          ", ".join(f"{f} outside when left out {np.mean(v[0] > 1):.2f}" for f, v in lofo_r.items()))
    board, outs = [], {}
    for c in cands:
        t0 = time.time()
        Xc = mats[c["X"]]
        o = run_design(c, Xc, y, fam, splits, sys3, mats_b[c["X"]], fam_b, fold_b, sys_b, mats_m[c["X"]], m_pos,
                       r_te if c["X"] == key else [np.zeros(len(te)) for te in folds],
                       r_b if c["X"] == key else [np.zeros(len(Xb)) for _ in folds])
        s = H.scores(y, o["pred"], fam, folds)
        rel = reliability(o, y, sent, fold_b, m_pos)
        lf = lofo(c, Xc, y, fam, groups, mats_b[c["X"]], lofo_r) if c["X"] == key else []
        rel["dismissed"] = mean_dismissed(lf)
        board.append(dict(c, scores=s, reliability=rel, lofo=lf, n_features=int(Xc.shape[1]), n_background=o["n_bg"],
                          seconds=round(time.time() - t0)))
        outs[c["id"]] = o
        if rel.get("false_alarms") is not None:
            P.log(f"{c['id']} {c['name']} [{c['settings']}]: MAE {s['tc_mae']:.2f} K (superconductors {s['sc_mae']:.2f} K); "
                  f"false alarms {rel['false_alarms']:.3f}, not known {rel['unknown_sent']:.3f} of the sent background, "
                  f"coverage {rel['coverage']:.3f}, Brier {rel['brier']:.4f}, database swap {rel['shift']:+.3f}; called "
                  f"unlikely {rel['dismissed']:.3f} (" + ", ".join(f"{r['family']} found {r.get('found', 0):.2f} not known "
                  f"{r.get('unknown', 0):.2f} unlikely {r.get('dismissed', 0):.2f}" for r in lf) + f"), {board[-1]['seconds']} s")
        else:
            P.log(f"{c['id']} {c['name']}: MAE {s['tc_mae']:.2f} K, {board[-1]['seconds']} s")
    base = next(r for r in board if r["id"] == "H0")
    ref = next(r for r in board if r["id"] == ref_c["id"])
    cur = next(r for r in board if r["id"] == cur_c["id"])
    rr, cr = ref["reliability"], cur["reliability"]
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], base["scores"]["fold_mae"])))
        r["folds_better_previous"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], cur["scores"]["fold_mae"])))
        rel = r["reliability"]
        if r["id"] not in DESIGNS or rel.get("false_alarms") is None:
            continue
        r["checks"] = {
            "false_alarms": rel["false_alarms"] <= FA_MAX,
            "called_unlikely": rel["dismissed"] is not None and rr["dismissed"] is not None and rel["dismissed"] <= rr["dismissed"],
            "coverage": rel["coverage"] >= COVERAGE_MIN,
            "tc": r["scores"]["tc_mae"] <= cur["scores"]["tc_mae"] + MAE_TOL,
            "superconductors": r["scores"]["sc_mae"] <= cur["scores"]["sc_mae"] + SC_TOL,
            "brier": rel["brier"] <= cr["brier"] + BRIER_TOL,
            "database_swap": rel["shift"] >= cr["shift"] - SHIFT_TOL}
        r["passed"] = all(r["checks"].values())
    new = [r for r in board if r["id"] in DESIGNS]
    eligible = [r for r in new if r.get("passed")]
    adopted = bool(eligible)
    order = lambda r: (r["reliability"]["dismissed"] if r["reliability"]["dismissed"] is not None else 9,   # noqa: E731
                       r["reliability"]["false_alarms"], r["scores"]["tc_mae"])
    best = min(eligible or new, key=order)
    cb = next(c for c in cands if c["id"] == best["id"])
    br = best["reliability"]
    P.log(f"best {best['id']}: called unlikely {br['dismissed']:.3f} (Hurricane {ref_ver} {rr['dismissed']:.3f}, Hurricane "
          f"{cur_ver} {cr['dismissed']:.3f}), false alarms {br['false_alarms']:.3f}, coverage {br['coverage']:.3f}; checks "
          f"{best.get('checks')}; adopted: {adopted}")
    kept, top = H3.top_kept(outs[ref["id"]]["predb"], outs[best["id"]]["pb"], sent, sys_b)
    kept = int(sum((outs[best["id"]]["pb"][i] >= 0.5) and not outs[best["id"]]["unknown_b"][i] for i in top))
    kept_cur = int(sum(outs[cur["id"]]["pb"][i] >= 0.5 for i in top))
    kept_ref = int(sum(outs[ref["id"]]["pb"][i] >= 0.5 for i in top))
    unk_top = int(sum(outs[best["id"]]["unknown_b"][i] for i in top))
    imp = H2.importance(outs[best["id"]]["fitted"], mats[cb["X"]], y, fam, [n for b in cb["X"] for n in names[b]])
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.2f} K)" for i in imp[:8]))
    # leave one family out, the best design next to Hurricane 3.0, Hurricane 2.0 and the baseline
    lof_cur = {r["family"]: r for r in cur["lofo"]}
    lof_ref = {r["family"]: r for r in ref["lofo"]}
    lof_base = {r["family"]: r for r in H2.lofo(cands[0], mats["A"], y, fam)}
    lofo_rows = []
    for r in best["lofo"]:
        f = r["family"]
        r = dict(r, mae_cv=float(np.abs(outs[best["id"]]["pred"][fam == f] - y[fam == f]).mean()),
                 mae_baseline=lof_base[f]["mae"] if f in lof_base else None, mae_previous=lof_cur[f]["mae"] if f in lof_cur else None,
                 found_previous=(lof_cur.get(f) or {}).get("found"), dismissed_previous=(lof_cur.get(f) or {}).get("dismissed"),
                 found_reference=(lof_ref.get(f) or {}).get("found"), dismissed_reference=(lof_ref.get(f) or {}).get("dismissed"))
        lofo_rows.append(r)
        f2 = lambda v: "n/a" if v is None else f"{v:.2f}"   # noqa: E731
        P.log(f"leave one family out, {f}: found {f2(r.get('found'))}, not known {f2(r.get('unknown'))}, called unlikely "
              f"{f2(r.get('dismissed'))} (Hurricane {cur_ver} {f2(r['dismissed_previous'])}, Hurricane {ref_ver} "
              f"{f2(r['dismissed_reference'])})")
    use_final = background_use(cb, np.ones(len(Xb), bool), r_all_b)
    final = H2.Design(cb, P.SEED + 500).fit(mats[cb["X"]], y, fam, Xb=mats_b[cb["X"]][use_final])
    final_cur = H2.Design(cur_c, P.SEED + 500).fit(mats[cur_c["X"]], y, fam, Xb=mats_b[cur_c["X"]])
    anchors_out = H2.anchors(final, cb, table, elements)
    anchors_cur = H2.anchors(final_cur, cur_c, table, elements)
    if anchors_out:
        ar = anchor_ratios(cb, table, elements, mats[cb["X"]], groups)
        before = {r["name"]: r for r in anchors_cur.get("table", [])}
        for r in anchors_out["table"]:
            b = before.get(r["name"]) or {}
            if b.get("pred") is not None:
                r["pred_previous"], r["p_sc_previous"] = b["pred"], b.get("p_sc")
            if r["name"] in ar:
                r["ratio"] = round(float(ar[r["name"]]), 2)
                if cb.get("abstain") and ar[r["name"]] > cb["abstain"]:
                    r["unknown"] = True
        P.log("anchors: " + "; ".join(f"{r['name']} {r['tc_exp']} K -> " + ("not known" if r.get("unknown") else
                                      f"chance {r.get('p_sc')}") + f" (ratio {r.get('ratio')}, Hurricane {cur_ver}: chance "
                                      f"{r.get('p_sc_previous')})" for r in anchors_out["table"] if r.get("pred") is not None))
    version = f"{ROUND}.0"
    fam_stats = {f: {"label": H.FAMILY_LABEL[f], "n": int((fam == f).sum()), "n_sc": int(((fam == f) & (y > 0)).sum()),
                     "max_tc": float(y[fam == f].max())} for f in H.FAMILY_LABEL if (fam == f).any()}
    data = {"source": "3DSC_MP (SuperCon measured Tc matched to Materials Project structures)", "cite": H.DSC_CITE,
            "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": H.DSC_COMMIT[:7],
            "n": int(len(y)), "n_sc": int((y > 0).sum()), "n_groups": int(len(set(groups))), "families": fam_stats,
            "context": int(len(conv))}
    bg_out = dict(bg_info, n=int(len(bg)), n_sent=int(sent.sum()), source="JARVIS-DFT 3D (OptB88vdW)",
                  folds=[int((fold_b == k).sum()) for k in range(P.N_FOLDS)], radar=radar_info,
                  within=({str(x): int((r_all_b <= x).sum()) for x in (1.0, 1.5, 2.0)}), n_used=int(use_final.sum()),
                  about=("Hurricane's screening pool: compounds with no superconductivity record, counted as not "
                         "superconducting; split into five folds by chemical system as in round 3"), **H3.KONNO)
    P.log(f"Hurricane {version} = {best['id']} {best['name']} [{best['settings']}]: adopted: {adopted}")
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": H.MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed four designs on Hurricane 3.0 that answer \"not known\" outside the "
                     "training data, with the background compounds limited by distance in three of them"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by parent compound on {len(y):,} 3DSC entries, the same folds and seeds "
                      "as rounds 1 to 3, round 3's background folds; every distance measured against the training part of "
                      "each fold or, leaving a family out, against the other families"),
        "rule": RULE, "caveat": CAVEAT, "false_alarms_about": H3.FA_ABOUT, "unknown_about": UNKNOWN_ABOUT,
        "dismissed_about": DISMISS_ABOUT, "shift_about": H3.SHIFT_ABOUT,
        "scikit_learn": sklearn.__version__, "data": data, "background": bg_out, "matched": {"n": int(len(m_pos))},
        "baseline": {"id": base["id"], "name": base["name"], "scores": base["scores"]},
        "reference": {"id": ref["id"], "version": ref_ver, "scores": ref["scores"], "reliability": rr, "lofo": ref["lofo"]},
        "previous": {"id": cur["id"], "version": cur_ver, "scores": cur["scores"], "reliability": cr, "lofo": cur["lofo"]},
        "leaderboard": sorted(board, key=lambda r: (r["reliability"].get("dismissed") is None,
                                                   r["reliability"].get("dismissed") or 0.0, r["scores"]["tc_mae"])),
        "best": best, "adopted": adopted,
        "top": {"n": len(top), "kept": kept, "kept_previous": kept_cur, "kept_reference": kept_ref, "unknown": unk_top,
                "about": (f"of Hurricane {ref_ver}'s top {len(top)} background compounds (sent by Radar, one per chemical "
                          "system, by predicted Tc, out of fold): how many keep at least an even chance, and how many "
                          "get no chance")},
        "spec": model_spec(cb, n_cols, int(use_final.sum())), "changes": spec_changes(cb, cands[0], int(use_final.sum())),
        "importance": imp, "lofo": lofo_rows, "anchors": anchors_out or None,
        "minutes": round((time.time() - t_start) / 60, 1),
    }
    for r in out["leaderboard"]:
        r["params"] = dict(r["params"])
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="hurricane4-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"hurricane_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    ob = outs[best["id"]]
    pd.DataFrame({"formula": hur["formula_sc"], "family": fam, "group": groups, "tc": y, "tc_pred_best": ob["pred"],
                  "p_sc_best": ob["p"], "not_known_best": ob["unknown"], "tc_pred_previous": outs[cur["id"]]["pred"],
                  "p_sc_previous": outs[cur["id"]]["p"], "tc_pred_baseline": outs["H0"]["pred"]}
                 ).round(4).to_csv(results / f"hurricane_round{ROUND}_predictions.csv", index=False)
    pd.DataFrame({"jid": bg["id"], "formula": [SC.S3.pretty(c) for c in bg["comp"]], "chemsys": sys_b, "fold": fold_b,
                  "p_unconventional": np.asarray(p_radar, float), "sent": sent, "family": fam_b,
                  "ratio_all": np.round(r_all_b, 3), "p_sc_previous": outs[cur["id"]]["pb"], "p_sc_best": ob["pb"],
                  "not_known_best": ob["unknown_b"], "tc_pred_best": ob["predb"]}
                 ).round(4).to_csv(results / f"hurricane_round{ROUND}_background.csv", index=False)
    update_progress(out, progress)
    if SMOKE:
        P.log(f"hurricane4 smoke test passed; outputs in {tmp}")


def update_progress(out: dict, progress: Path) -> None:
    """Round 4's entry in the "hurricane" block, in the same form as round 3, with the "not known" answers and how many
    superconductors of a left-out family each version calls unlikely."""
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, ref, prev, base, ver = out["best"], out["reference"], out["previous"], out["baseline"], out["version"]
    sc, br, pr, rr = best["scores"], best["reliability"], prev["reliability"], ref["reliability"]
    r2 = lambda v: round(float(v), 2)   # noqa: E731
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    bg = out["background"]
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": f"{best['name']}, {best['settings']}",
        "changes": out["changes"], "spec": out["spec"], "rule": out["rule"],
        "scores": {"tc_mae": r2(sc["tc_mae"]), "reference_mae": r2(base["scores"]["tc_mae"]), "reference": base["name"],
                   "folds": [r2(x) for x in sc["fold_mae"]], "reference_folds": [r2(x) for x in base["scores"]["fold_mae"]],
                   "folds_better": best["folds_better"],
                   "sc_mae": r2(sc["sc_mae"]) if sc["sc_mae"] is not None else None,
                   "high_tc_mae": r2(sc["high_tc_mae"]) if sc["high_tc_mae"] is not None else None,
                   "high_tc": H.HIGH_TC, "r2_log": round(sc["r2_log"], 3),
                   "by_family": {f: {"n": v["n"], "mae": r2(v["mae"]), "mae_ref": r2(base["scores"]["by_family"][f]["mae"])}
                                 for f, v in sc["by_family"].items()}},
        "previous": {"version": prev["version"], "tc_mae": r2(prev["scores"]["tc_mae"]),
                     "folds": [r2(x) for x in prev["scores"]["fold_mae"]], "folds_better": best["folds_better_previous"],
                     "sc_mae": r2(prev["scores"]["sc_mae"]), "high_tc_mae": r2(prev["scores"]["high_tc_mae"])},
        # leave one family out: found, not known and called unlikely (not "recall", so that an app that knows only
        # round 3 shows the plain table)
        "lofo": [{k: (r2(v) if isinstance(v, float) and k.startswith(("mae", "max")) else r3(v) if isinstance(v, float) else v)
                  for k, v in r.items()} for r in out["lofo"]],
        "importance": out["importance"],
        "search": {"candidates": len(out["leaderboard"]), "reference_id": "H0", "previous_id": prev["id"],
                   "version_reference_id": ref["id"],
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"], "tc_mae": r2(r["scores"]["tc_mae"]),
                                    "sc_mae": r2(r["scores"]["sc_mae"]), "folds_better": r["folds_better"],
                                    "folds_better_previous": r["folds_better_previous"],
                                    "false_alarms": r3(r["reliability"].get("false_alarms")),
                                    "dismissed": r3(r["reliability"].get("dismissed")),
                                    "coverage": r3(r["reliability"].get("coverage")),
                                    "brier": r3(r["reliability"].get("brier")), "shift": r3(r["reliability"].get("shift")),
                                    "passed": r.get("passed")} for r in out["leaderboard"]]},
        "reliability": {
            "about": out["false_alarms_about"], "rule": out["rule"], "caveat": out["caveat"],
            "unknown_about": out["unknown_about"], "dismissed_about": out["dismissed_about"],
            "background": {"n": bg["n"], "n_sent": bg["n_sent"], "source": bg["source"], "cite": H3.KONNO["cite"],
                           "doi": H3.KONNO["doi"], "weight": best.get("background"), "radius": best.get("radius"),
                           "n_used": bg["n_used"]},
            "abstain": best.get("abstain"),
            "false_alarms": r3(br["false_alarms"]), "false_alarms_previous": r3(pr["false_alarms"]),
            "false_alarms_reference": r3(rr["false_alarms"]),
            "folds": [r3(x) for x in br["fa_folds"]], "folds_previous": [r3(x) for x in pr["fa_folds"]],
            "folds_fewer": None,   # round 4 is not chosen by fewer false alarms
            "false_alarms_all": r3(br["false_alarms_all"]), "false_alarms_all_previous": r3(pr["false_alarms_all"]),
            "unknown_sent": r3(br["unknown_sent"]), "unknown_all": r3(br["unknown_all"]),
            "coverage": r3(br["coverage"]), "coverage_previous": r3(pr["coverage"]),
            "dismissed": r3(br["dismissed"]), "dismissed_previous": r3(pr["dismissed"]), "dismissed_reference": r3(rr["dismissed"]),
            "reference_version": ref["version"],
            "brier": r3(br["brier"]), "brier_previous": r3(pr["brier"]),
            "recall": r3(br["recall"]), "recall_previous": r3(pr["recall"]), "recall_covered": r3(br["recall_covered"]),
            "share_sc_likely": r3(br["share_sc_likely"]), "share_sc_likely_previous": r3(pr["share_sc_likely"]),
            "shift": r3(br["shift"]), "shift_previous": r3(pr["shift"]), "n_matched": br["n_matched"],
            "shift_about": out["shift_about"], "top": out["top"], "checks": best.get("checks")},
    }
    if out.get("anchors"):
        a = out["anchors"]
        entry["anchors"] = {"n_scored": a["summary"]["n_scored"], "mae": a["summary"]["mae"],
                            "scored_as_check": a["summary"]["scored_as_check"], "rule": a["summary"]["rule"],
                            "table": [dict({"name": r["name"], "tc_exp": r["tc_exp"], "status": r["status"], "use": r["use"],
                                            "family": r.get("family"), "pred": r.get("pred"), "note": r.get("note", "")},
                                           **{k: r[k] for k in ("p_sc", "tc_sc", "rule", "physics", "types", "pred_previous",
                                                                "p_sc_previous", "ratio", "unknown") if k in r})
                                      for r in a["table"]]}
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
                f"from 3DSC (SuperCon + Materials Project), {data['n_sc']:,} superconducting, plus {bg['n_used']:,} compounds "
                "with no superconductivity record for the classifier")
        prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
            {"tag": "hurricane", "model": f"{H.MODEL} {ver} (AI-designed)", "target": "Tc_exp", "mae": r2(sc["tc_mae"]),
             "unit": "K", "note": note},
            {"tag": "hurricane", "model": "Gradient boosting, composition only (measured-Tc baseline)", "target": "Tc_exp",
             "mae": r2(base["scores"]["tc_mae"]), "unit": "K", "note": "Same data and folds"}]
        text = (f"Learns from {data['n']:,} measured Tc values (cuprates, iron-based, heavy-fermion and other oxides; "
                f"SuperCon with Materials Project structures via 3DSC), including {data['n'] - data['n_sc']:,} materials "
                f"that did not superconduct, and from {bg['n_used']:,} compounds with no superconductivity record, counted "
                f"as probably not superconducting. For compounds whose parent it never saw in training it is off by "
                f"{sc['tc_mae']:.1f} K on average. It gives a chance only to compounds near its training data and answers "
                f"\"not known\" further away: of the held-out compounds with no record, it gives {br['false_alarms']:.0%} at "
                f"least an even chance (Hurricane {ref['version']}: {rr['false_alarms']:.0%}), and trained without a whole "
                f"family it calls {br['dismissed']:.0%} of that family's superconductors unlikely (Hurricane "
                f"{prev['version']}: {pr['dismissed']:.0%}). Our AI agent designed it.")
        fam = [m for m in prog.get("model_family", []) if m.get("id") != "hurricane"]
        fam.append({"id": "hurricane", "status": f"{H.MODEL} {ver} in use", "active": True, "text": text})
        prog["model_family"] = fam
    H.ai_stage(prog)
    P.tidy(prog)
    prefix = f"{H.MODEL}, round {ROUND} ("
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(prefix)]   # a re-run replaces it
    P.add_log(prog, stamp, f"{H.MODEL}, round {ROUND} ({len(DESIGNS)} AI-designed candidates): best {best['id']} "
                           f"{best['name']} [{best['settings']}]; trained without a whole family it calls "
                           f"{br['dismissed']:.0%} of that family's superconductors unlikely, against {pr['dismissed']:.0%} for "
                           f"Hurricane {prev['version']} and {rr['dismissed']:.0%} for Hurricane {ref['version']}; false "
                           f"alarms {br['false_alarms']:.0%}; a chance for {br['coverage']:.0%} of the held-out 3DSC entries; "
                           f"measured-Tc MAE {sc['tc_mae']:.2f} K against {prev['scores']['tc_mae']:.2f} K; " +
                           (f"released as {H.MODEL} {ver}" if out["adopted"] else
                            f"not released, so Hurricane {prev['version']} stays in use"))
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {H.MODEL} round {ROUND} ({entry['status']})")


if __name__ == "__main__":
    run()
