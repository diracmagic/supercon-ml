"""Hurricane, round 3: fewer false alarms outside the training data.

Hurricane 2.0 learned from 2,123 measured Tc values, almost all from a handful of families (cuprates, iron-based and
heavy-fermion compounds, other oxides). In screening round 2, 45 of the 50 compounds at the top of its list lay outside
that data, and several still got a chance of superconducting of 70 to 90%, among them hypothetical structures that no
one has made. Its classifier had never been shown an ordinary compound: SuperCon records superconductors, and the 728
3DSC entries that did not superconduct are the few that someone reported. T. Konno et al. (Phys. Rev. B 103, 014509
(2021)) met the same problem and added crystal structures with no superconductivity record as non-superconducting.

Round 3 does the same with the compounds that Hurricane screens. The background is Hurricane's screening pool: JARVIS-DFT
compounds within 50 meV/atom of the convex hull, with a band gap of at most 1 eV, 2 to 5 elements, up to 40 atoms and
only elements that at least 20 of Hurricane's training materials contain, one per composition, leaving out everything
that SuperCon, 3DSC, the electron-phonon data, the claims we track or our anchors already have, and everything made of
exactly the elements of a known superconductor. None has a superconductivity record. Most were probably never tested and
a few may be superconductors that nobody has found, so they join the classifier (never the Tc regressor) as
non-superconducting, at a reduced weight. The AI agent (Claude) proposed three weights:

    H16  Hurricane 2.0 (H12) + the background compounds at weight 0.1
    H17  the same at weight 0.3
    H18  the same at weight 1

H0 (composition only) and H12 (Hurricane 2.0) are retrained on the same folds and seeds as rounds 1 and 2. The background
is split into five folds by chemical system, fold k paired with the 3DSC fold k: each fold's model learns from the other
four folds of both, and never from a background compound in the chemical system of a held-out 3DSC entry. Out of fold:

    false alarms    the share of background compounds that Radar sends to Hurricane and that the model gives at least
                    an even chance of superconducting (an upper bound: a few may superconduct)
    measured Tc     the error on the 3DSC entries, overall and on the superconducting ones, as in every round
    Brier score     of the chance of superconducting, on the 3DSC entries
    database swap   for 3DSC compounds that JARVIS also has, the change of the chance when the structure comes from JARVIS
                    instead of the Materials Project. A design must not learn to tell the two databases apart: that would
                    lower its false alarms for the wrong reason

A design is released as Hurricane 3.0 if, against Hurricane 2.0 on the same folds, it raises at most half as many false
alarms and fewer in at least 4 of the 5 folds, is not more than 0.3 K worse on measured Tc and 0.5 K worse on the
superconducting entries, has a Brier score at most 0.01 worse, and the database swap lowers its chance by at most 0.05
more than it lowers Hurricane 2.0's. Of those, the one with the fewest false alarms is released. The rule was fixed before
the run. Leave-one-family-out and the anchors are reported, never used to choose.

The screening (ml/screen.py) then scores each compound with a model that did not learn from its chemical system's
background fold.

Run from the repository root:  python ml/pipeline.py hurricane3
(HURRICANE3_SMOKE=1: a quick check on small data that writes into a temporary folder)
"""
from __future__ import annotations

import hashlib
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
import pipeline as P
import screen as SC

ROUND = 3
SMOKE = os.environ.get("HURRICANE3_SMOKE") == "1"
WEIGHTS = {"H16": 0.1, "H17": 0.3, "H18": 1.0}
FA_FACTOR = 0.5     # at most half of Hurricane 2.0's false alarms ...
MAE_TOL = 0.3       # K: ... not more than this much worse on measured Tc ...
SC_TOL = 0.5        # K: ... and on the superconducting entries ...
BRIER_TOL = 0.01    # ... a Brier score at most this much worse ...
SHIFT_TOL = 0.05    # ... and the database swap lowers the chance by at most this much more
TOP = 50
KONNO = {"cite": "T. Konno et al., Phys. Rev. B 103, 014509 (2021)", "doi": "10.1103/PhysRevB.103.014509"}
RULE = (f"release the design with the fewest false alarms among those that, against Hurricane 2.0 on the same folds, "
        f"raise at most {FA_FACTOR:g} times as many false alarms on the held-out background compounds that Radar sends "
        f"to Hurricane and fewer in at least {P.ADOPT_FOLDS} of {P.N_FOLDS} folds, are not more than {MAE_TOL:g} K worse "
        f"on measured Tc and {SC_TOL:g} K worse on the superconducting entries, have a Brier score at most "
        f"{BRIER_TOL:g} worse, and whose chance drops by at most {SHIFT_TOL:g} more than Hurricane 2.0's when 3DSC "
        f"compounds are described with JARVIS structures instead of their own")
FA_ABOUT = ("false alarms: the share of held-out background compounds (JARVIS-DFT compounds with no superconductivity "
            "record that Radar sends to Hurricane) given at least an even chance of superconducting; an upper bound, as "
            "a few of them may superconduct")
SHIFT_ABOUT = ("the mean change of the chance of superconducting for 3DSC compounds that JARVIS-DFT also has, when their "
               "structure comes from JARVIS instead of the Materials Project (out of fold)")
CAVEAT = ("The background compounds have no superconductivity record, which is not a measurement of zero: most were "
          "probably never tested and a few may superconduct. Counting them as non-superconducting makes Hurricane more "
          "cautious about chemistry unlike its training data, including a family that nobody has found yet.")


def bg_fold(chemsys: str) -> int:
    """The background fold of a chemical system, fixed by a hash so that it never depends on the order of the data."""
    return int(hashlib.md5(str(chemsys).encode("utf-8")).hexdigest()[:8], 16) % P.N_FOLDS


def chemsys_of(comp: dict) -> str:
    return "-".join(sorted(e for e, v in comp.items() if v > 0))


def train_mask(k: int, folds: np.ndarray, systems: np.ndarray, test_systems: set) -> np.ndarray:
    """The background compounds that fold k's model learns from: not in fold k, and not in the chemical system of a
    held-out 3DSC entry."""
    return (folds != k) & ~np.isin(systems, sorted(test_systems))


def background(rows: pd.DataFrame, hur: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Hurricane's screening pool, built as screen.run builds it: the background compounds."""
    counts = {}
    for cc in hur["comp"]:
        for e in cc:
            counts[e] = counts.get(e, 0) + 1
    pool, steps = SC.hurricane_pool(rows, counts)
    sources = []
    known = SC.known_lists(sources)
    pool, _, excluded = SC.exclude(pool, known)
    n = len(pool)
    pool = SC.one_per_composition(pool)
    return pool, {"steps": [{"step": s, "n": int(m)} for s, m in steps], "excluded": excluded,
                  "polymorphs_dropped": int(n - len(pool)), "sources": sources}


def matched(hur: pd.DataFrame, rows: pd.DataFrame) -> tuple[np.ndarray, list]:
    """The 3DSC entries whose composition JARVIS-DFT also has (the same elements, every share within 2 at.%), with the
    most stable JARVIS entry for each: their positions in hur and their rows in the JARVIS table."""
    J = SC.Known("jarvis")
    order = rows.assign(_h=rows["ehull"].fillna(np.inf)).sort_values(["_h", "id"]).index
    for i in order:
        J.add(rows.at[i, "comp"], str(i))
    pos, jr = [], []
    for i, comp in enumerate(hur["comp"]):
        hit = J.match(comp)
        if hit is not None:
            pos.append(i)
            jr.append(int(hit))
    return np.array(pos, int), jr


def run_design(c: dict, X, y, fam, splits, sys3, Xb, fam_b, fold_b, sys_b, Xm, m_pos) -> dict:
    """One design out of fold: its 3DSC predictions and their two parts, its chances for the held-out background
    compounds and for the matched 3DSC compounds described with JARVIS structures, and the fitted fold models."""
    n, nb = len(y), len(Xb)
    pred, p3, tc3 = np.zeros(n), np.full(n, np.nan), np.zeros(n)
    pb, predb, pm = np.full(nb, np.nan), np.zeros(nb), np.full(len(m_pos), np.nan)
    fitted, n_bg = [], []
    use_bg = bool(c.get("background"))
    for k, (tr, te) in enumerate(splits):
        keep = train_mask(k, fold_b, sys_b, set(sys3[te]))
        d = H2.Design(c, P.SEED + k).fit(X[tr], y[tr], fam[tr], Xb=Xb[keep] if use_bg else None)
        n_bg.append(int(keep.sum()) if use_bg else 0)
        pred[te] = d.predict(X[te], fam[te])
        p3[te], tc3[te] = SC.hur_parts(d, X[te], fam[te])
        tb = np.where(fold_b == k)[0]
        if len(tb):
            pb[tb] = SC.hur_parts(d, Xb[tb], fam_b[tb])[0]
            predb[tb] = d.predict(Xb[tb], fam_b[tb])
        mi = np.where(np.isin(m_pos, te))[0]
        if len(mi):
            pm[mi] = SC.hur_parts(d, Xm[mi], fam[m_pos[mi]])[0]
        fitted.append((d, te))
    return {"pred": pred, "p": p3, "tc_sc": tc3, "pb": pb, "predb": predb, "pm": pm, "fitted": fitted, "n_bg": n_bg}


def reliability(o: dict, y, sent, fold_b, m_pos) -> dict:
    """False alarms, Brier score, recall and the database swap of one design (None for a one-part design)."""
    p = o["p"]
    if not np.isfinite(p).all():
        return {"false_alarms": None}
    sc = (y > 0).astype(float)
    alarm = o["pb"] >= 0.5
    folds = [float(alarm[sent & (fold_b == k)].mean()) if (sent & (fold_b == k)).any() else None for k in range(P.N_FOLDS)]
    likely = p >= 0.5
    dm = o["pm"] - p[m_pos] if len(m_pos) else np.zeros(0)
    return {"false_alarms": float(alarm[sent].mean()) if sent.any() else None, "fa_folds": folds,
            "false_alarms_all": float(alarm.mean()) if len(alarm) else None,
            "p_mean_sent": float(o["pb"][sent].mean()) if sent.any() else None,
            "brier": float(np.mean((p - sc) ** 2)), "recall": float(likely[sc > 0].mean()) if (sc > 0).any() else None,
            "share_sc_likely": float(sc[likely].mean()) if likely.any() else None,
            "share_sc_unlikely": float(sc[~likely].mean()) if (~likely).any() else None,
            "shift": float(dm.mean()) if len(dm) else 0.0, "shift_abs": float(np.abs(dm).mean()) if len(dm) else 0.0,
            "n_matched": int(len(dm))}


def lofo(c: dict, X, y, fam, Xb=None) -> list:
    """Leave one family out (as hurricane2.lofo), with the background compounds if the design uses them."""
    out = []
    for f in H.FAMILY_LABEL:
        te, tr = np.where(fam == f)[0], np.where(fam != f)[0]
        if len(te) < 10:
            continue
        d = H2.Design(c, P.SEED + 300).fit(X[tr], y[tr], fam[tr], Xb=Xb if c.get("background") else None)
        p = d.predict(X[te], fam[te])
        pp = SC.hur_parts(d, X[te], fam[te])[0]
        med = float(np.median(y[tr]))
        out.append({"family": f, "label": H.FAMILY_LABEL[f], "n": int(len(te)), "mae": float(np.abs(p - y[te]).mean()),
                    "mae_median": float(np.abs(med - y[te]).mean()), "max_tc": float(y[te].max()), "max_pred": float(p.max()),
                    "recall": float((pp[y[te] > 0] >= 0.5).mean()) if np.isfinite(pp).all() and (y[te] > 0).any() else None})
    return out


def top_kept(order_pred, p_new, sent, systems, n=TOP) -> tuple[int, list]:
    """Of Hurricane 2.0's top n background compounds (sent by Radar, one per chemical system, by its predicted Tc), how
    many another design still gives at least an even chance; and their positions."""
    top, seen = [], set()
    for i in np.argsort(-order_pred, kind="stable"):
        if not sent[i] or systems[i] in seen:
            continue
        seen.add(systems[i])
        top.append(int(i))
        if len(top) == n:
            break
    return int(sum(p_new[i] >= 0.5 for i in top)), top


def spec_changes(c: dict, ref: dict, n_bg: int) -> list:
    out = H2.spec_changes(c, ref)
    if c.get("background"):
        out.append(f"Adds {n_bg:,} compounds with no superconductivity record (Hurricane's JARVIS-DFT screening pool) to the "
                   f"classifier as non-superconducting, each at weight {c['background']:g}, after Konno et al. (2021)")
    return out


def model_spec(c: dict, n_cols: dict, n_bg: int) -> dict:
    spec = H2.model_spec(c, n_cols)
    if c.get("background"):
        spec["learner"]["background"] = (f"{n_bg:,} JARVIS-DFT compounds with no superconductivity record join the "
                                         f"classifier as non-superconducting at weight {c['background']:g}; the Tc "
                                         "regressor never sees them")
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
    bg, bg_info = background(rows, hur)
    symbols = sorted({e for c in list(hur["comp"]) + list(conv["comp"]) + list(bg["comp"]) for e in c} |
                     {e for a in anchors_in.get("materials", []) for e in a["composition"]})
    table = P.element_table(symbols)
    y, groups, fam = hur["tc"].to_numpy(float), hur["group"].to_numpy(), hur["family"].to_numpy()
    sys3 = np.array([chemsys_of(c) for c in hur["comp"]])
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
    # the designs: H0, Hurricane 2.0 as released (round 2's best), and Hurricane 2.0 with the background at three weights
    prev_c, prev_ver = SC.hurricane_design(upto=2)
    if not prev_c.get("two_part"):
        raise SystemExit(f"Hurricane {prev_ver} gives no chance of superconducting; round 3 needs round 2's two-part design")
    prev_c = dict(prev_c, id=prev_c.get("id") or "H12", name=f"Hurricane {prev_ver}", settings="as released")
    cands = [{"id": "H0", "name": "Composition only (baseline)", "settings": "default", "X": "A", "params": H.PARAMS},
             prev_c]
    for cid, w in WEIGHTS.items():
        cands.append(dict(prev_c, id=cid, name=f"Hurricane {prev_ver} + background compounds as non-superconducting",
                          settings=f"weight {w:g}", background=w))
    keys = sorted({c["X"] for c in cands})
    mats = {key: np.hstack([blocks[b].to_numpy(float) for b in key]) for key in keys}
    # the background compounds, their folds and whether Radar sends them to Hurricane
    if not len(bg):
        raise SystemExit("no background compounds: Hurricane's screening pool is empty")
    bblocks = SC.hur_blocks(bg, table, elements)
    for b in bblocks:
        if list(bblocks[b].columns) != names[b]:
            raise SystemExit(f"background inputs, block {b}, do not match the training inputs")
    mats_b = {key: np.hstack([bblocks[b].to_numpy(float) for b in key]) for key in keys}
    fam_b = np.array([SC.family_guess(cc) for cc in bg["comp"]])
    sys_b = bg["chemsys"].to_numpy()
    fold_b = np.array([bg_fold(s) for s in sys_b])
    p_radar, radar_info = SC.radar_scores(bg)
    sent = np.asarray(p_radar, float) >= 0.5
    if not sent.any():
        raise SystemExit("Radar sends none of the background compounds to Hurricane: no false alarms to count")
    # the matched compounds: 3DSC entries that JARVIS also has, with the JARVIS structure in place of their own
    m_pos, m_rows = matched(hur, rows)
    if len(m_pos):
        sts = [SC.radar_structure(rows.at[j, "atoms"], rows.at[j, "spg_number"], rows.at[j, "spg"]) for j in m_rows]
        Bj = pd.DataFrame([H.structure_row(s, c, table) for s, c in zip(sts, hur["comp"].iloc[m_pos])])[names["B"]]
    else:
        Bj = blocks["B"].iloc[:0]
    mats_m = {key: np.hstack([(Bj if b == "B" else blocks[b].iloc[m_pos].reset_index(drop=True)).to_numpy(float)
                              for b in key]) for key in keys}
    P.log(f"Hurricane round 3: {len(hur)} 3DSC entries ({int((y > 0).sum())} superconducting); {len(bg):,} background "
          f"compounds, {int(sent.sum()):,} of them sent to Hurricane by Radar, in folds of " +
          ", ".join(str(int((fold_b == k).sum())) for k in range(P.N_FOLDS)) +
          f"; {len(m_pos)} 3DSC entries matched to a JARVIS structure")
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats["A"], y, groups))
    folds = [te for _, te in splits]
    board, outs = [], {}
    for c in cands:
        t0 = time.time()
        o = run_design(c, mats[c["X"]], y, fam, splits, sys3, mats_b[c["X"]], fam_b, fold_b, sys_b, mats_m[c["X"]], m_pos)
        s = H.scores(y, o["pred"], fam, folds)
        rel = reliability(o, y, sent, fold_b, m_pos)
        board.append(dict(c, scores=s, reliability=rel, n_features=int(mats[c["X"]].shape[1]), n_background=o["n_bg"],
                          seconds=round(time.time() - t0)))
        outs[c["id"]] = o
        fa = rel.get("false_alarms")
        P.log(f"{c['id']} {c['name']} [{c['settings']}]: MAE {s['tc_mae']:.2f} K (superconductors {s['sc_mae']:.2f} K)" +
              (f"; false alarms {fa:.3f} (all background {rel['false_alarms_all']:.3f}), Brier {rel['brier']:.4f}, recall "
               f"{rel['recall']:.3f}, database swap {rel['shift']:+.3f} (mean |change| {rel['shift_abs']:.3f}, "
               f"{rel['n_matched']} compounds)" if fa is not None else "") + f", {board[-1]['seconds']} s")
    base = next(r for r in board if r["id"] == "H0")
    prev = next(r for r in board if r["id"] == prev_c["id"])
    pr = prev["reliability"]
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], base["scores"]["fold_mae"])))
        r["folds_better_previous"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], prev["scores"]["fold_mae"])))
        rel = r["reliability"]
        if rel.get("false_alarms") is None or r is prev or pr.get("false_alarms") is None:
            continue
        rel["folds_fewer"] = int(sum(a is not None and b is not None and a < b for a, b in zip(rel["fa_folds"], pr["fa_folds"])))
        r["checks"] = {
            "false_alarms": rel["false_alarms"] <= FA_FACTOR * pr["false_alarms"],
            "false_alarm_folds": rel["folds_fewer"] >= P.ADOPT_FOLDS,
            "tc": r["scores"]["tc_mae"] <= prev["scores"]["tc_mae"] + MAE_TOL,
            "superconductors": r["scores"]["sc_mae"] <= prev["scores"]["sc_mae"] + SC_TOL,
            "brier": rel["brier"] <= pr["brier"] + BRIER_TOL,
            "database_swap": rel["shift"] >= pr["shift"] - SHIFT_TOL}
        r["passed"] = all(r["checks"].values())
    new = [r for r in board if r.get("background")]
    eligible = [r for r in new if r.get("passed")]
    adopted = bool(eligible)
    best = min(eligible or new, key=lambda r: (r["reliability"]["false_alarms"], r["scores"]["tc_mae"]))
    cb = next(c for c in cands if c["id"] == best["id"])
    br = best["reliability"]
    P.log(f"best {best['id']}: false alarms {br['false_alarms']:.3f} against {pr['false_alarms']:.3f} for Hurricane "
          f"{prev_ver}, fewer in {br.get('folds_fewer')}/{P.N_FOLDS} folds; checks {best.get('checks')}; adopted: {adopted}")
    # Hurricane 2.0's top 50 background compounds: how many keep at least an even chance
    kept_new, top = top_kept(outs[prev["id"]]["predb"], outs[best["id"]]["pb"], sent, sys_b)
    kept_prev = int(sum(outs[prev["id"]]["pb"][i] >= 0.5 for i in top))
    P.log(f"of Hurricane {prev_ver}'s top {len(top)} background compounds (one per chemical system), {kept_prev} had at "
          f"least an even chance under Hurricane {prev_ver} and {kept_new} under {best['id']}")
    Xc = mats[cb["X"]]
    Xb_all = mats_b[cb["X"]]
    feat_names = [n for b in cb["X"] for n in names[b]]
    imp = H2.importance(outs[best["id"]]["fitted"], Xc, y, fam, feat_names)
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.2f} K)" for i in imp[:8]))
    lofo_rows = lofo(cb, Xc, y, fam, Xb_all)
    lofo_prev = {r["family"]: r for r in lofo(prev_c, mats[prev_c["X"]], y, fam)}
    lofo_ref = {r["family"]: r for r in lofo(cands[0], mats["A"], y, fam)}
    for r in lofo_rows:
        r["mae_cv"] = float(np.abs(outs[best["id"]]["pred"][fam == r["family"]] - y[fam == r["family"]]).mean())
        r["mae_baseline"] = lofo_ref[r["family"]]["mae"] if r["family"] in lofo_ref else None
        r["mae_previous"] = lofo_prev[r["family"]]["mae"] if r["family"] in lofo_prev else None
        r["recall_previous"] = lofo_prev[r["family"]].get("recall") if r["family"] in lofo_prev else None
        share = lambda v: "n/a" if v is None else f"{v:.2f}"   # noqa: E731
        P.log(f"leave one family out, {r['family']}: MAE {r['mae']:.2f} K (Hurricane {prev_ver} {r['mae_previous']:.2f} K, "
              f"baseline design {r['mae_baseline']:.2f} K); share of its superconductors given at least an even chance "
              f"{share(r['recall'])} (Hurricane {prev_ver} {share(r['recall_previous'])})")
    final = H2.Design(cb, P.SEED + 500).fit(Xc, y, fam, Xb=Xb_all)
    final_prev = H2.Design(prev_c, P.SEED + 500).fit(mats[prev_c["X"]], y, fam)
    anchors_out = H2.anchors(final, cb, table, elements)
    anchors_prev = H2.anchors(final_prev, prev_c, table, elements)
    if anchors_out:
        before = {r["name"]: r for r in anchors_prev.get("table", [])}
        for r in anchors_out["table"]:
            b = before.get(r["name"]) or {}
            if b.get("pred") is not None:
                r["pred_previous"], r["p_sc_previous"] = b["pred"], b.get("p_sc")
        a = anchors_out["summary"]
        P.log(f"anchors: {a['n_listed']} listed, {a['n_scored']} scored, MAE {a['mae']} K; " + "; ".join(
            f"{r['name']} {r['tc_exp']} K -> {r['pred']} K (chance {r.get('p_sc')}, Hurricane {prev_ver}: "
            f"{r.get('p_sc_previous')})" for r in anchors_out["table"] if r.get("pred") is not None))
    version = f"{ROUND}.0"
    fam_stats = {f: {"label": H.FAMILY_LABEL[f], "n": int((fam == f).sum()), "n_sc": int(((fam == f) & (y > 0)).sum()),
                     "max_tc": float(y[fam == f].max())} for f in H.FAMILY_LABEL if (fam == f).any()}
    data = {"source": "3DSC_MP (SuperCon measured Tc matched to Materials Project structures)", "cite": H.DSC_CITE,
            "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": H.DSC_COMMIT[:7],
            "n": int(len(y)), "n_sc": int((y > 0).sum()), "n_groups": int(len(set(groups))), "families": fam_stats,
            "context": int(len(conv))}
    bg_out = dict(bg_info, n=int(len(bg)), n_sent=int(sent.sum()), source="JARVIS-DFT 3D (OptB88vdW)",
                  folds=[int((fold_b == k).sum()) for k in range(P.N_FOLDS)],
                  folds_sent=[int((sent & (fold_b == k)).sum()) for k in range(P.N_FOLDS)], radar=radar_info,
                  about=("Hurricane's screening pool: compounds with no superconductivity record, counted as not "
                         "superconducting; split into five folds by chemical system"), **KONNO)
    P.log(f"Hurricane {version} = {best['id']} {best['name']} [{best['settings']}]: MAE {best['scores']['tc_mae']:.2f} K "
          f"(Hurricane {prev_ver} {prev['scores']['tc_mae']:.2f} K), false alarms {br['false_alarms']:.3f} against "
          f"{pr['false_alarms']:.3f}; adopted: {adopted}")
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": H.MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed adding Hurricane's screening pool to its classifier as non-superconducting "
                     "background compounds, at three weights, after Konno et al. (2021), and the database-swap check"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by parent compound on {len(y):,} 3DSC entries, the same folds and seeds "
                      f"as rounds 1 and 2; the background in {P.N_FOLDS} folds by chemical system, fold k paired with "
                      "3DSC fold k; leave-one-family-out and anchors reported, never used to choose"),
        "rule": RULE, "caveat": CAVEAT, "false_alarms_about": FA_ABOUT, "shift_about": SHIFT_ABOUT,
        "scikit_learn": sklearn.__version__, "data": data, "background": bg_out,
        "matched": {"n": int(len(m_pos)), "about": SHIFT_ABOUT},
        "baseline": {"id": base["id"], "name": base["name"], "scores": base["scores"]},
        "previous": {"id": prev["id"], "version": prev_ver, "scores": prev["scores"], "reliability": pr},
        "leaderboard": sorted(board, key=lambda r: (r["reliability"].get("false_alarms") is None,
                                                   r["reliability"].get("false_alarms") or 0.0, r["scores"]["tc_mae"])),
        "best": best, "adopted": adopted,
        "top": {"n": len(top), "kept": kept_new, "kept_previous": kept_prev,
                "about": (f"of Hurricane {prev_ver}'s top {len(top)} background compounds (sent by Radar, one per chemical "
                          "system, by predicted Tc, out of fold), how many keep at least an even chance")},
        "spec": model_spec(cb, n_cols, len(bg)), "changes": spec_changes(cb, cands[0], len(bg)), "importance": imp,
        "lofo": lofo_rows, "anchors": anchors_out or None, "minutes": round((time.time() - t_start) / 60, 1),
    }
    for r in out["leaderboard"]:
        r["params"] = dict(r["params"])
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="hurricane3-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"hurricane_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"formula": hur["formula_sc"], "family": fam, "group": groups, "tc": y,
                  "tc_pred_best": outs[best["id"]]["pred"], "p_sc_best": outs[best["id"]]["p"],
                  "tc_pred_previous": outs[prev["id"]]["pred"], "p_sc_previous": outs[prev["id"]]["p"],
                  "tc_pred_baseline": outs["H0"]["pred"]}).round(4).to_csv(results / f"hurricane_round{ROUND}_predictions.csv", index=False)
    pd.DataFrame({"jid": bg["id"], "formula": [SC.S3.pretty(c) for c in bg["comp"]], "chemsys": sys_b, "fold": fold_b,
                  "p_unconventional": np.asarray(p_radar, float), "sent": sent, "family": fam_b,
                  "p_sc_previous": outs[prev["id"]]["pb"], "tc_pred_previous": outs[prev["id"]]["predb"],
                  "p_sc_best": outs[best["id"]]["pb"], "tc_pred_best": outs[best["id"]]["predb"]}
                 ).round(4).to_csv(results / f"hurricane_round{ROUND}_background.csv", index=False)
    update_progress(out, progress)
    if SMOKE:
        P.log(f"hurricane3 smoke test passed; outputs in {tmp}")


def update_progress(out: dict, progress: Path) -> None:
    """Round 3's entry in the "hurricane" block, in the same form as round 2 plus its reliability check."""
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, ref, prev, ver = out["best"], out["baseline"], out["previous"], out["version"]
    sc, br, pr = best["scores"], best["reliability"], prev["reliability"]
    r2 = lambda v: round(float(v), 2)   # noqa: E731
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    bg = out["background"]
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": f"{best['name']}, {best['settings']}",
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
        "search": {"candidates": len(out["leaderboard"]), "reference_id": "H0", "previous_id": prev["id"],
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"], "tc_mae": r2(r["scores"]["tc_mae"]),
                                    "sc_mae": r2(r["scores"]["sc_mae"]), "folds_better": r["folds_better"],
                                    "folds_better_previous": r["folds_better_previous"],
                                    "false_alarms": r3(r["reliability"].get("false_alarms")),
                                    "brier": r3(r["reliability"].get("brier")), "shift": r3(r["reliability"].get("shift")),
                                    "passed": r.get("passed")} for r in out["leaderboard"]]},
        "reliability": {
            "about": FA_ABOUT, "rule": out["rule"], "caveat": out["caveat"],
            "background": {"n": bg["n"], "n_sent": bg["n_sent"], "source": bg["source"], "cite": KONNO["cite"],
                           "doi": KONNO["doi"], "weight": best.get("background")},
            "false_alarms": r3(br["false_alarms"]), "false_alarms_previous": r3(pr["false_alarms"]),
            "folds": [r3(x) for x in br["fa_folds"]], "folds_previous": [r3(x) for x in pr["fa_folds"]],
            "folds_fewer": br.get("folds_fewer"),
            "false_alarms_all": r3(br["false_alarms_all"]), "false_alarms_all_previous": r3(pr["false_alarms_all"]),
            "brier": r3(br["brier"]), "brier_previous": r3(pr["brier"]),
            "recall": r3(br["recall"]), "recall_previous": r3(pr["recall"]),
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
                                                                "p_sc_previous") if k in r})
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
                f"from 3DSC (SuperCon + Materials Project), {data['n_sc']:,} superconducting, plus {bg['n']:,} compounds "
                "with no superconductivity record for the classifier")
        prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
            {"tag": "hurricane", "model": f"{H.MODEL} {ver} (AI-designed)", "target": "Tc_exp", "mae": r2(sc["tc_mae"]),
             "unit": "K", "note": note},
            {"tag": "hurricane", "model": "Gradient boosting, composition only (measured-Tc baseline)", "target": "Tc_exp",
             "mae": r2(ref["scores"]["tc_mae"]), "unit": "K", "note": "Same data and folds"}]
        lof = {r["family"]: r for r in out["lofo"]}
        text = (f"Learns from {data['n']:,} measured Tc values (cuprates, iron-based, heavy-fermion and other oxides; "
                f"SuperCon with Materials Project structures via 3DSC), including {data['n'] - data['n_sc']:,} materials "
                f"that did not superconduct, and from {bg['n']:,} compounds with no superconductivity record, counted as "
                f"probably not superconducting. For compounds whose parent it never saw in training it is off by "
                f"{sc['tc_mae']:.1f} K on average, against {prev['scores']['tc_mae']:.1f} K for Hurricane "
                f"{prev['version']} and {ref['scores']['tc_mae']:.1f} K for a composition-only baseline. Among compounds "
                f"like those it screens, it gives at least an even chance of superconducting to {br['false_alarms']:.0%}, "
                f"against {pr['false_alarms']:.0%} for Hurricane {prev['version']}.")
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
    P.add_log(prog, stamp, f"{H.MODEL}, round {ROUND} ({len(WEIGHTS)} AI-designed candidates): best {best['id']} "
                           f"{best['name']} [{best['settings']}]; among held-out compounds with no superconductivity record "
                           f"that Radar sends to Hurricane, {br['false_alarms']:.0%} got at least an even chance of "
                           f"superconducting, against {pr['false_alarms']:.0%} for Hurricane {prev['version']}; measured-Tc "
                           f"MAE {sc['tc_mae']:.2f} K against {prev['scores']['tc_mae']:.2f} K; " +
                           (f"released as {H.MODEL} {ver}" if out["adopted"] else
                            f"not released, so Hurricane {prev['version']} stays in use"))
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {H.MODEL} round {ROUND} ({entry['status']})")


if __name__ == "__main__":
    run()
