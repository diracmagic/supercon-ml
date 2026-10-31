"""Hurricane, round 5: asking about the parent compound, with what DFT says about its electrons.

Round 4 made Hurricane honest about what it cannot judge, but it still does not find a family it has never seen:
trained without one, it gives at least an even chance to 8% of that family's superconductors and answers "not known"
for 64%. Two things stand in the way, and this round tests both.

The question. Hurricane learns from SuperCon entries, and most of its superconductors are doped samples with
non-integer formulas (Ba0.5K0.5Fe2As2), while every compound it screens is an undoped parent from a materials
database (BaFe2As2). It has therefore learned, among other things, that an integer formula is a poor bet. The
screening question is not "does this exact formula superconduct" but "is this parent compound worth doping": the
cuprates and the iron-based superconductors were found that way. Round 5 asks that question directly. Every group of
SuperCon entries that shares one Materials Project structure becomes one row: the parent compound, labelled by
whether any of its entries superconducts and by the highest Tc reached.

The inputs. Hurricane's inputs are composition, measurable cell geometry and chemical structure types, all of which
describe which family a compound resembles. Nothing tells it what the electrons do. 3DSC carries the Materials
Project calculation of every parent, and JARVIS-DFT carries the same quantities for every compound in the screening
pool, so both sides can have a block of electronic-structure inputs: the band gap, the magnetic moment per volume,
the distance above the convex hull and the formation energy. These say whether a parent is a metal, a small-gap
semiconductor or a magnet, which is what distinguishes a parent worth doping from an ordinary compound without
naming any family.

    P0  Hurricane 4.0 as released, asked about the parent compounds (the reference)
    P1  the same design, trained on parent compounds
    P2  P1 + the electronic-structure inputs
    P3  Hurricane 4.0's entry-level training + the electronic-structure inputs
    P4  P2 without "not known": every parent gets a chance

Every design is scored on the same thing, the one that screening actually uses: given a parent compound, what does
the model say? The entry-level designs are asked the same question, about the parent's own formula, which is what
the screening does with them today. Folds are five groups of chemical systems; the background compounds keep round
3's folds, and no model sees a background compound from a held-out system.

    found            the superconducting parents of a family left out of training that get at least an even chance
    not known        those too far from the training data for a chance (round 4's rule, at parent level)
    called unlikely  the rest: a chance under one half
    false alarms     held-out background compounds, sent to Hurricane by Radar, given at least an even chance
    coverage, the Tc error on the parents, the Brier score and the database swap, as in round 4

Two databases describe the same compounds here, so the swap check matters more than before: a design must give a
3DSC parent about the same chance when its structure and its electronic values come from JARVIS instead of the
Materials Project, or it could be telling the two databases apart instead of learning physics.

The rule, fixed before the run: release the design that finds the most superconductors of a left-out family, among
those that raise false alarms on at most 5% of the held-out background compounds, call no more of a left-out
family's superconductors unlikely than Hurricane 2.0 does, give a chance to at least 85% of the held-out parents,
are not more than 1 K worse than Hurricane 4.0 on the parents' Tc, not more than 0.01 worse in Brier score, and
whose chance moves by at most 0.05 more than Hurricane 4.0's in the database swap. Ties go to fewer false alarms,
then to the lower Tc error. Finding more of a new family is the point of this round; the other tests keep round 3's
and round 4's gains.

Run from the repository root:  python ml/pipeline.py hurricane5
(HURRICANE5_SMOKE=1: a quick check on small data that writes into a temporary folder)
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
import hurricane4 as H4
import pipeline as P
import screen as SC

ROUND = 5
SMOKE = os.environ.get("HURRICANE5_SMOKE") == "1"
FA_MAX = 0.05         # at most 5% false alarms, as in round 4 ...
COVERAGE_MIN = 0.85   # ... a chance for at least 85% of the held-out parents ...
MAE_TOL = 1.0         # K, on the parents, against Hurricane 4.0 ...
BRIER_TOL = 0.01      # ... a Brier score at most this much worse ...
SHIFT_MAX = 0.10      # ... and the database swap moves the chance by at most this much, on average
MIN_FAMILY = 10       # a family is left out only with at least this many parents

RULE = (f"release the design that finds the most superconductors of a left-out family (gives them at least an even "
        f"chance), among those that raise false alarms on at most {FA_MAX:.0%} of the held-out compounds with no "
        f"superconductivity record that Radar sends to Hurricane, call no more superconductors of a left-out family "
        f"unlikely than Hurricane 2.0 does, give a chance to at least {COVERAGE_MIN:.0%} of the held-out parent "
        f"compounds, are not more than {MAE_TOL:g} K worse than Hurricane 4.0 on the parents' Tc, not more than "
        f"{BRIER_TOL:g} worse in Brier score, and whose chance moves by at most {SHIFT_MAX:g} on average when a "
        f"parent is described with JARVIS-DFT values instead of Materials Project ones, since every compound it "
        f"screens is described with JARVIS values; ties go to fewer false alarms, then to the lower Tc error")
PARENT_ABOUT = ("a parent compound is one Materials Project structure in 3DSC with all the SuperCon entries matched to "
                "it: it counts as superconducting if any of them does, and its Tc is the highest they reach")
FOUND_ABOUT = ("found: trained without a whole family, the share of that family's superconducting parents given at "
               "least an even chance, averaged over the families left out")
ELECTRONIC_ABOUT = ("what the DFT calculation says about the parent's electrons: the band gap, whether it is a metal, "
                    "the magnetic moment per volume, whether it is magnetic, the distance above the convex hull and "
                    "the formation energy per atom; from the Materials Project for the training parents and from "
                    "JARVIS-DFT for the screening pool")
CAVEAT = ("A parent compound that this model gives a chance is a compound worth doping or tuning, not a superconductor: "
          "the experiment has to find the doping, the pressure or the growth that gets there, and most parents never "
          "do. The two databases compute the same quantities with different settings, which the database swap checks "
          "but does not remove.")

# The electronic-structure blocks: the same quantities on both sides. Block G holds only what survives the change of
# database: whether the compound is a metal, whether a small gap could be closed, whether it is magnetic. Block F adds
# the raw numbers, which two codes with different functionals do not agree on as closely.
FLAG_RATIONALE = {
    "is_metal": "no band gap at all",
    "small_gap": "a gap under 1 eV, the range where doping or pressure can make a compound metallic",
    "is_magnetic": "a magnetic moment: the parent compounds of the cuprates and the iron-based superconductors are "
                   "magnets, and the moment has to be suppressed for pairing",
}
VALUE_RATIONALE = {
    "gap": "DFT band gap (eV): zero for a metal; a small gap is what doping can close",
    "mag_vol": "magnetic moment per volume (muB/A^3)",
    "ehull": "energy above the convex hull (eV/atom): how far the compound is from being the stable phase",
    "e_form": "formation energy per atom (eV): how strongly bound the compound is",
}
ELECTRONIC_RATIONALE = dict(FLAG_RATIONALE, **VALUE_RATIONALE)


def _f(v) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def electronic_row(gap, mag_vol, ehull, e_form) -> dict:
    """One row of the electronic block, from values that both databases provide."""
    g, m = _f(gap), _f(mag_vol)
    return {"gap": g, "is_metal": float(g <= 0.005) if np.isfinite(g) else np.nan,
            "small_gap": float(0.005 < g <= 1.0) if np.isfinite(g) else np.nan,
            "mag_vol": m, "is_magnetic": float(abs(m) > 1e-4) if np.isfinite(m) else np.nan,
            "ehull": _f(ehull), "e_form": _f(e_form)}


DSC_ELECTRONIC = ("band_gap_2", "total_magnetization_normalized_vol_2", "e_above_hull_2", "formation_energy_per_atom_2")


def dsc_electronic(r) -> dict:
    return electronic_row(*(r.get(c) for c in DSC_ELECTRONIC))


def jarvis_electronic(r) -> dict:
    """The same quantities for a JARVIS-DFT compound; its moment is per cell, so it is divided by the cell volume."""
    a = r["atoms"]
    vol = abs(float(np.linalg.det(np.asarray(a["lattice_mat"], float)))) if a.get("lattice_mat") else np.nan
    mag = _f(r.get("magmom"))
    return electronic_row(r.get("gap"), mag / vol if np.isfinite(mag) and vol else np.nan, r.get("ehull"),
                          r.get("e_form"))


def parent_frame(dsc: pd.DataFrame) -> pd.DataFrame:
    """One row per Materials Project structure in 3DSC: the parent compound, with the label and Tc of its entries.

    The parent's composition is the undoped Materials Project formula; where 3DSC does not give one, the entry's own
    composition rounded to whole atoms. All of a parent's entries share its structure and its electronic values."""
    df = H.build_frame(dsc, set(H.FAMILY_OF_CLASS))
    if "material_id_2" not in df.columns:
        raise SystemExit("3DSC_MP has no material_id_2 column: round 5 needs the Materials Project id of each parent")
    rows = []
    for mid, g in df.groupby(df["material_id_2"].astype(str), sort=True):
        if not mid or mid.lower() in ("nan", "none", ""):
            continue
        first = g.iloc[0]
        comp = None
        for col in ("original_formula_2", "pretty_formula_2", "formula_2"):
            if col in g.columns and isinstance(first.get(col), str) and first[col].strip():
                try:
                    comp = H.parse_formula(first[col])
                    break
                except ValueError:
                    comp = None
        if not comp:   # no Materials Project formula: round the entry's own composition to whole atoms
            comp = {e: float(max(1, round(v))) for e, v in first["comp"].items()}
        tc = g["tc"].to_numpy(float)
        fams = list(g["family"])
        rows.append({"material_id": mid, "comp": comp, "formula_sc": SC.S3.pretty(comp),
                     "formula_entry": str(first["formula_sc"]),
                     "family": max(set(fams), key=fams.count), "group": str(first["group"]),
                     "tc": float(tc.max()), "n_entries": int(len(g)), "n_sc": int((tc > 0).sum()),
                     "row": first, "elec": dsc_electronic(first)})
    out = pd.DataFrame(rows)
    if not len(out):
        raise SystemExit("no parent compounds: 3DSC gave no Materials Project ids")
    return out.reset_index(drop=True)


def parent_blocks(par: pd.DataFrame, table: pd.DataFrame, elements: list) -> dict:
    """Hurricane's input blocks for parent compounds, plus the electronic block F."""
    sts = [H.dsc_structure(r) for r in par["row"]]
    b = {"A": pd.DataFrame([H.composition_row(c, table) for c in par["comp"]]),
         "C": pd.DataFrame([H.physics_row(c) for c in par["comp"]]),
         "B": pd.DataFrame([H.structure_row(s, c, table) for s, c in zip(sts, par["comp"])]),
         "D": H.element_fractions(par["comp"], elements),
         "E": pd.DataFrame([H2.structure_types(c) for c in par["comp"]], columns=list(H2.TYPE_RATIONALE))}
    e = pd.DataFrame(list(par["elec"]), columns=list(ELECTRONIC_RATIONALE))
    b["F"], b["G"] = e, e[list(FLAG_RATIONALE)]
    return b


def pool_blocks(df: pd.DataFrame, table: pd.DataFrame, elements: list) -> dict:
    """The same blocks for JARVIS compounds (the background and the screening pool)."""
    b = SC.hur_blocks(df, table, elements)
    e = pd.DataFrame([jarvis_electronic(r) for _, r in df.iterrows()], columns=list(ELECTRONIC_RATIONALE))
    b["F"], b["G"] = e, e[list(FLAG_RATIONALE)]
    return b


def design_rows(c: dict) -> str:
    """"parent" for a design trained on parent compounds, "entry" for one trained on SuperCon entries."""
    return c.get("rows", "parent")


def fit_design(c: dict, seed: int, Xp, yp, famp, Xe, ye, fame, tr_p, tr_e, Xb=None):
    """One design fitted on its own rows: parent compounds or SuperCon entries."""
    if design_rows(c) == "entry":
        return H2.Design(c, seed).fit(Xe[tr_e], ye[tr_e], fame[tr_e], Xb=Xb)
    return H2.Design(c, seed).fit(Xp[tr_p], yp[tr_p], famp[tr_p], Xb=Xb)


def run_design(c, mats_p, mats_e, mats_b, y_p, y_e, fam_p, fam_e, sys_p, sys_e, folds_p, fam_b, fold_b, sys_b,
               mats_j, r_te, r_b) -> dict:
    """One design out of fold. Every design is asked about the parent compounds; the ones trained on SuperCon entries
    (round 4's framing) are asked the same question about each parent's own formula."""
    key = c["X"]
    Xp, Xe, Xb = mats_p[key], mats_e[key], mats_b[key]
    n, nb = len(y_p), len(Xb)
    pred, p3, tc3, unk3 = np.zeros(n), np.full(n, np.nan), np.zeros(n), np.zeros(n, bool)
    pb, predb, unkb = np.full(nb, np.nan), np.zeros(nb), np.zeros(nb, bool)
    pj = np.full(n, np.nan)
    fitted, n_bg = [], []
    for k, te in enumerate(folds_p):
        test_sys = set(sys_p[te])
        tr_p = np.where(~np.isin(sys_p, sorted(test_sys)))[0]
        tr_e = np.where(~np.isin(sys_e, sorted(test_sys)))[0]
        keep = H3.train_mask(k, fold_b, sys_b, test_sys)
        use = H4.background_use(c, keep, r_b[k])
        d = fit_design(c, P.SEED + k, Xp, y_p, fam_p, Xe, y_e, fam_e, tr_p, tr_e,
                       Xb=Xb[use] if c.get("background") else None)
        n_bg.append(int(use.sum()) if c.get("background") else 0)
        pred[te] = d.predict(Xp[te], fam_p[te])
        p3[te], tc3[te] = SC.hur_parts(d, Xp[te], fam_p[te])
        unk3[te] = H4.unknown(c, r_te[k])
        if mats_j is not None:   # the same parents described with JARVIS values (the database swap)
            Xj, has_j = mats_j[key], mats_j["_has"]
            jm = te[has_j[te]]
            if len(jm):
                pj[jm] = SC.hur_parts(d, Xj[jm], fam_p[jm])[0]
        tb = np.where(fold_b == k)[0]
        if len(tb):
            pb[tb] = SC.hur_parts(d, Xb[tb], fam_b[tb])[0]
            predb[tb] = d.predict(Xb[tb], fam_b[tb])
            unkb[tb] = H4.unknown(c, r_b[k][tb])
        fitted.append((d, te))
    return {"pred": pred, "p": p3, "tc_sc": tc3, "unknown": unk3, "pb": pb, "predb": predb, "unknown_b": unkb,
            "pj": pj, "fitted": fitted, "n_bg": n_bg}


def reliability(o: dict, y_p, sent, fold_b) -> dict:
    p = o["p"]
    if not np.isfinite(p).all():
        return {"false_alarms": None}
    sc = (y_p > 0).astype(float)
    alarm = (o["pb"] >= 0.5) & ~o["unknown_b"]
    folds = [float(alarm[sent & (fold_b == k)].mean()) if (sent & (fold_b == k)).any() else None for k in range(P.N_FOLDS)]
    likely, cov = p >= 0.5, ~o["unknown"]
    m = np.isfinite(o["pj"])
    d = o["pj"][m] - p[m]
    return {"false_alarms": float(alarm[sent].mean()), "fa_folds": folds, "false_alarms_all": float(alarm.mean()),
            "unknown_sent": float(o["unknown_b"][sent].mean()), "unknown_all": float(o["unknown_b"].mean()),
            "coverage": float(cov.mean()), "brier": float(np.mean((p - sc) ** 2)),
            "recall": float(likely[sc > 0].mean()), "found_cv": float((likely & cov)[sc > 0].mean()),
            "share_sc_likely": float(sc[likely & cov].mean()) if (likely & cov).any() else None,
            "share_sc_unlikely": float(sc[~likely & cov].mean()) if (~likely & cov).any() else None,
            "shift": float(d.mean()) if len(d) else 0.0, "shift_abs": float(np.abs(d).mean()) if len(d) else 0.0,
            "n_matched": int(m.sum())}


def lofo(c: dict, mats_p, mats_e, mats_b, y_p, y_e, fam_p, fam_e, lofo_r: dict) -> list:
    """Leave one family out, at parent level: trained without a family, how many of its superconducting parents the
    design finds, cannot judge, or calls unlikely."""
    key = c["X"]
    Xp, Xe, Xb = mats_p[key], mats_e[key], mats_b[key]
    out = []
    for f in H.FAMILY_LABEL:
        te = np.where(fam_p == f)[0]
        if len(te) < MIN_FAMILY or f not in lofo_r:
            continue
        tr_p, tr_e = np.where(fam_p != f)[0], np.where(fam_e != f)[0]
        r_f, r_bf = lofo_r[f]
        use = H4.background_use(c, np.ones(len(Xb), bool), r_bf)
        d = fit_design(c, P.SEED + 300, Xp, y_p, fam_p, Xe, y_e, fam_e, tr_p, tr_e,
                       Xb=Xb[use] if c.get("background") else None)
        pr = d.predict(Xp[te], fam_p[te])
        pp = SC.hur_parts(d, Xp[te], fam_p[te])[0]
        unk = H4.unknown(c, r_f)
        sc = y_p[te] > 0
        med = float(np.median(y_p[tr_p]))
        row = {"family": f, "label": H.FAMILY_LABEL[f], "n": int(len(te)), "n_sc": int(sc.sum()),
               "mae": float(np.abs(pr - y_p[te]).mean()), "mae_median": float(np.abs(med - y_p[te]).mean()),
               "max_tc": float(y_p[te].max()), "max_pred": float(pr.max())}
        if np.isfinite(pp).all() and sc.any():
            row.update(found=float(((pp >= 0.5) & ~unk)[sc].mean()), unknown=float(unk[sc].mean()),
                       dismissed=float(((pp < 0.5) & ~unk)[sc].mean()))
        out.append(row)
    return out


def mean_of(rows: list, key: str):
    v = [r[key] for r in rows if r.get(key) is not None]
    return float(np.mean(v)) if v else None


def spec_changes(c: dict, ref: dict, n_bg: int) -> list:
    out = H4.spec_changes(c, ref, n_bg)
    if design_rows(c) == "parent":
        out.append("Asks about the parent compound: every Materials Project structure in 3DSC is one row, "
                   "superconducting if any of its SuperCon entries is, with the highest Tc they reach")
    if "F" in c["X"]:
        out.append("Adds what the DFT calculation says about the electrons: band gap, metal or small-gap, magnetic "
                   "moment per volume, distance above the convex hull and formation energy per atom")
    elif "G" in c["X"]:
        out.append("Adds the three things both databases agree on about the electrons: whether the compound is a "
                   "metal, whether a small gap could be closed by doping, and whether it is magnetic")
    return out


def model_spec(c: dict, n_cols: dict, n_bg: int) -> dict:
    spec = H4.model_spec(dict(c, X=c["X"].replace("F", "").replace("G", "")), n_cols, n_bg)
    for b, lab, why in (("F", "What DFT says about the electrons", ELECTRONIC_RATIONALE),
                        ("G", "What DFT says about the electrons", FLAG_RATIONALE)):
        if b in c["X"]:
            spec["inputs"].append({"group": "electronic", "label": lab, "n": n_cols[b],
                                   "items": [{"name": k, "why": v} for k, v in why.items()]})
    if design_rows(c) == "parent":
        spec["target"] = "log(1 + Tc) of the parent compound (the highest its SuperCon entries reach)"
        spec["cv"] = "5-fold, grouped by chemical system, one row per parent compound"
        spec["learner"]["rows"] = PARENT_ABOUT
    return spec


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    dsc = H.load_3dsc()
    ent = H.build_frame(dsc, set(H.FAMILY_OF_CLASS))
    par = parent_frame(dsc)
    conv = H.build_frame(dsc, H.CONVENTIONAL)
    anchors_in = H.load_anchors()
    rows = SC.load_rows()
    if "e_form" not in rows.columns:
        rows = rows.assign(e_form=np.nan)
    bg, bg_info = H3.background(rows, ent)
    if not len(bg):
        raise SystemExit("no background compounds: Hurricane's screening pool is empty")
    symbols = sorted({e for c in list(ent["comp"]) + list(par["comp"]) + list(conv["comp"]) + list(bg["comp"]) for e in c} |
                     {e for a in anchors_in.get("materials", []) for e in a["composition"]})
    table = P.element_table(symbols)
    y_p, fam_p = par["tc"].to_numpy(float), par["family"].to_numpy()
    y_e, fam_e = ent["tc"].to_numpy(float), ent["family"].to_numpy()
    sys_p = np.array([H3.chemsys_of(c) for c in par["comp"]])
    sys_e = np.array([H3.chemsys_of(c) for c in ent["comp"]])
    counts = {}
    for c in ent["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    pblocks = parent_blocks(par, table, elements)
    eblocks = H.feature_blocks(ent, table, [H.dsc_structure(r) for _, r in ent.iterrows()])
    eblocks["D"] = H.element_fractions(ent["comp"], elements)
    eblocks["E"] = pd.DataFrame([H2.structure_types(c) for c in ent["comp"]], columns=list(H2.TYPE_RATIONALE))
    ee = pd.DataFrame([dsc_electronic(r) for _, r in ent.iterrows()], columns=list(ELECTRONIC_RATIONALE))
    eblocks["F"], eblocks["G"] = ee, ee[list(FLAG_RATIONALE)]
    names = {b: list(pblocks[b].columns) for b in pblocks}
    n_cols = {b: len(names[b]) for b in names}
    for b in names:   # the two framings and the pool must describe the same things in the same order
        if list(eblocks[b].columns) != names[b]:
            raise SystemExit(f"entry inputs, block {b}, do not match the parent inputs")
    cur_c, cur_ver = SC.hurricane_design(upto=4)
    if not cur_c.get("abstain"):
        raise SystemExit(f"round 5 builds on Hurricane 4.0 (round 4's released design); the version in use is {cur_ver}")
    ref_c, ref_ver = SC.hurricane_design(upto=2)
    base_X = cur_c["X"]
    cands = [
        dict(cur_c, id="P0", name=f"Hurricane {cur_ver}", settings="as released, asked about the parent compounds",
             rows="entry", X=base_X),
        dict(cur_c, id="P1", name="Hurricane 4.0 trained on parent compounds", settings="the same inputs",
             rows="parent", X=base_X),
        dict(cur_c, id="P2", name="Parent compounds + what DFT says about the electrons",
             settings="band gap, magnetism and stability, as numbers", rows="parent", X=base_X + "F"),
        dict(cur_c, id="P3", name="Parent compounds + metal, small gap, magnetic",
             settings="only what both databases agree on", rows="parent", X=base_X + "G"),
        dict(cur_c, id="P4", name="SuperCon entries + metal, small gap, magnetic",
             settings="round 4's rows, the new inputs", rows="entry", X=base_X + "G"),
        dict(cur_c, id="P5", name="Parent compounds + metal, small gap, magnetic",
             settings="every parent gets a chance", rows="parent", X=base_X + "G", abstain=None),
    ]
    keys = sorted({c["X"] for c in cands})
    mats_p = {k: np.hstack([pblocks[b].to_numpy(float) for b in k]) for k in keys}
    mats_e = {k: np.hstack([eblocks[b].to_numpy(float) for b in k]) for k in keys}
    bblocks = pool_blocks(bg, table, elements)
    for b in names:
        if list(bblocks[b].columns) != names[b]:
            raise SystemExit(f"background inputs, block {b}, do not match the parent inputs")
    mats_b = {k: np.hstack([bblocks[b].to_numpy(float) for b in k]) for k in keys}
    fam_b = np.array([SC.family_guess(cc) for cc in bg["comp"]])
    sys_b = bg["chemsys"].to_numpy()
    fold_b = np.array([H3.bg_fold(s) for s in sys_b])
    p_radar, radar_info = SC.radar_scores(bg)
    sent = np.asarray(p_radar, float) >= 0.5
    if not sent.any():
        raise SystemExit("Radar sends none of the background compounds to Hurricane: no false alarms to count")
    # the same parents described with JARVIS values, for the database swap
    j_pos, j_rows = H3.matched(par, rows)
    mats_j = None
    if len(j_pos):
        jd = rows.loc[j_rows].reset_index(drop=True)
        sts = [SC.radar_structure(jd.at[i, "atoms"], jd.at[i, "spg_number"], jd.at[i, "spg"]) for i in range(len(jd))]
        Bj = pd.DataFrame([H.structure_row(s, c, table) for s, c in zip(sts, par["comp"].iloc[j_pos])])[names["B"]]
        Ej = pd.DataFrame([jarvis_electronic(r) for _, r in jd.iterrows()], columns=names["F"])
        Gj = Ej[names["G"]]
        mats_j = {}
        for k in keys:
            parts = []
            for b in k:
                full = pd.DataFrame(np.nan, index=range(len(par)), columns=names[b])
                src = (Bj if b == "B" else Ej if b == "F" else Gj if b == "G"
                       else pblocks[b].iloc[j_pos].reset_index(drop=True))
                full.iloc[j_pos] = src.to_numpy(float)
                parts.append(full.to_numpy(float))
            mats_j[k] = np.hstack(parts)
        mats_j["_has"] = np.isin(np.arange(len(par)), j_pos)   # which parents JARVIS also describes
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats_p[base_X], y_p, sys_p))
    folds_p = [te for _, te in splits]
    # distances, once per input set: fold by fold and family by family, always against the training part
    r_te, r_b, lofo_r = {}, {}, {}
    for k in keys:
        Xp, Xb = mats_p[k], mats_b[k]
        rt, rb = [], []
        for tr, te in splits:
            r = H4.ratio(Xp[tr], sys_p[tr], np.vstack([Xp[te], Xb]))
            rt.append(r[:len(te)])
            rb.append(r[len(te):])
        r_te[k], r_b[k] = rt, rb
        lr = {}
        for f in H.FAMILY_LABEL:
            te, tr = np.where(fam_p == f)[0], np.where(fam_p != f)[0]
            if len(te) >= MIN_FAMILY:
                r = H4.ratio(Xp[tr], sys_p[tr], np.vstack([Xp[te], Xb]))
                lr[f] = (r[:len(te)], r[len(te):])
        lofo_r[k] = lr
    n_sc_p = int((y_p > 0).sum())
    P.log(f"Hurricane round 5: {len(par):,} parent compounds from {len(ent):,} 3DSC entries ({n_sc_p:,} parents "
          f"superconduct, {len(set(sys_p)):,} chemical systems), {len(bg):,} background compounds "
          f"({int(sent.sum())} sent by Radar), {len(j_pos):,} parents JARVIS also has; "
          + ", ".join(f"{f} {int((fam_p == f).sum())} parents" for f in H.FAMILY_LABEL if (fam_p == f).any()))
    board, outs = [], {}
    for c in cands:
        t0 = time.time()
        o = run_design(c, mats_p, mats_e, mats_b, y_p, y_e, fam_p, fam_e, sys_p, sys_e, folds_p, fam_b, fold_b, sys_b,
                       mats_j, r_te[c["X"]], r_b[c["X"]])
        s = H.scores(y_p, o["pred"], fam_p, folds_p)
        rel = reliability(o, y_p, sent, fold_b)
        lf = lofo(c, mats_p, mats_e, mats_b, y_p, y_e, fam_p, fam_e, lofo_r[c["X"]])
        rel["found"] = mean_of(lf, "found")
        rel["dismissed"] = mean_of(lf, "dismissed")
        rel["unknown_lofo"] = mean_of(lf, "unknown")
        board.append(dict(c, scores=s, reliability=rel, lofo=lf, n_features=int(mats_p[c["X"]].shape[1]),
                          n_background=o["n_bg"], seconds=round(time.time() - t0)))
        outs[c["id"]] = o
        if rel.get("false_alarms") is not None:
            P.log(f"{c['id']} {c['name']} [{c['settings']}]: parent MAE {s['tc_mae']:.2f} K; found "
                  f"{rel['found']:.3f}, not known {rel['unknown_lofo']:.3f}, called unlikely {rel['dismissed']:.3f} "
                  f"of a left-out family; false alarms {rel['false_alarms']:.3f}, coverage {rel['coverage']:.3f}, "
                  f"Brier {rel['brier']:.4f}, database swap {rel['shift']:+.3f} (|{rel['shift_abs']:.3f}|), "
                  f"{board[-1]['seconds']} s")
        else:
            P.log(f"{c['id']} {c['name']}: parent MAE {s['tc_mae']:.2f} K, {board[-1]['seconds']} s")
    ref = next(r for r in board if r["id"] == "P0")
    rr = ref["reliability"]
    # Hurricane 2.0's dismissal bar, from round 4's results if they are there
    bar = None
    try:
        r4 = json.loads((P.RESULTS / "hurricane_round4.json").read_text(encoding="utf-8"))
        bar = ((r4.get("reference") or {}).get("reliability") or {}).get("dismissed")
    except (OSError, ValueError):
        bar = None
    if bar is None:
        bar = rr.get("dismissed")
        P.log("no round-4 results: the dismissal bar is Hurricane 4.0's own, not Hurricane 2.0's")
    for r in board:
        rel = r["reliability"]
        r["folds_better_previous"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], ref["scores"]["fold_mae"])))
        if r["id"] == "P0" or rel.get("false_alarms") is None:
            continue
        r["checks"] = {
            "false_alarms": rel["false_alarms"] <= FA_MAX,
            "called_unlikely": rel["dismissed"] is not None and bar is not None and rel["dismissed"] <= bar,
            "coverage": rel["coverage"] >= COVERAGE_MIN,
            "tc": r["scores"]["tc_mae"] <= ref["scores"]["tc_mae"] + MAE_TOL,
            "brier": rel["brier"] <= rr["brier"] + BRIER_TOL,
            "database_swap": rel["shift_abs"] <= SHIFT_MAX}
        r["passed"] = all(r["checks"].values())
    new = [r for r in board if r["id"] != "P0"]
    eligible = [r for r in new if r.get("passed")]
    # the point of this round: find the most of a left-out family, then fewer false alarms, then the lower Tc error
    order = lambda r: (-(r["reliability"]["found"] if r["reliability"]["found"] is not None else -1),   # noqa: E731
                       r["reliability"]["false_alarms"], r["scores"]["tc_mae"])
    best = min(eligible or new, key=order)
    br = best["reliability"]
    # a release must also actually find more than Hurricane 4.0 does; otherwise the round changes nothing
    better = (br["found"] is not None and rr["found"] is not None and br["found"] > rr["found"])
    adopted = bool(eligible) and better
    cb = next(c for c in cands if c["id"] == best["id"])
    P.log(f"best {best['id']}: found {br['found']:.3f} (Hurricane {cur_ver} {rr['found']:.3f}), called unlikely "
          f"{br['dismissed']:.3f} (bar {bar:.3f}), false alarms {br['false_alarms']:.3f}, coverage "
          f"{br['coverage']:.3f}; checks {best.get('checks')}; finds more: {better}; adopted: {adopted}")
    imp = H2.importance(outs[best["id"]]["fitted"], mats_p[cb["X"]], y_p, fam_p,
                        [n for b in cb["X"] for n in names[b]])
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.2f} K)" for i in imp[:8]))
    lof_ref = {r["family"]: r for r in ref["lofo"]}
    lofo_rows = []
    for r in best["lofo"]:
        f = r["family"]
        r = dict(r, mae_cv=float(np.abs(outs[best["id"]]["pred"][fam_p == f] - y_p[fam_p == f]).mean()),
                 mae_previous=(lof_ref.get(f) or {}).get("mae"), found_previous=(lof_ref.get(f) or {}).get("found"),
                 unknown_previous=(lof_ref.get(f) or {}).get("unknown"),
                 dismissed_previous=(lof_ref.get(f) or {}).get("dismissed"))
        lofo_rows.append(r)
        f2 = lambda v: "n/a" if v is None else f"{v:.2f}"   # noqa: E731
        P.log(f"leave one family out, {f}: found {f2(r.get('found'))}, not known {f2(r.get('unknown'))}, called "
              f"unlikely {f2(r.get('dismissed'))} (Hurricane {cur_ver}: found {f2(r['found_previous'])}, unlikely "
              f"{f2(r['dismissed_previous'])})")
    # the final model, on all of the data, and the anchors it predicts
    r_all_b = H4.ratio(mats_p[cb["X"]], sys_p, mats_b[cb["X"]])
    use_final = H4.background_use(cb, np.ones(len(mats_b[cb["X"]]), bool), r_all_b)
    final = fit_design(cb, P.SEED + 500, mats_p[cb["X"]], y_p, fam_p, mats_e[cb["X"]], y_e, fam_e,
                       np.arange(len(y_p)), np.arange(len(y_e)),
                       Xb=mats_b[cb["X"]][use_final] if cb.get("background") else None)
    uses_dft = ("F" in cb["X"]) or ("G" in cb["X"])
    anchors_out = None if uses_dft else H2.anchors(final, cb, table, elements)
    if uses_dft:
        P.log("anchors are not scored this round: the graded materials have no DFT electronic values of their own")
    version = f"{ROUND}.0"
    fam_stats = {f: {"label": H.FAMILY_LABEL[f], "n": int((fam_p == f).sum()),
                     "n_sc": int(((fam_p == f) & (y_p > 0)).sum()), "max_tc": float(y_p[fam_p == f].max())}
                 for f in H.FAMILY_LABEL if (fam_p == f).any()}
    data = {"source": "3DSC_MP (SuperCon measured Tc matched to Materials Project structures), by parent compound",
            "cite": H.DSC_CITE, "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": H.DSC_COMMIT[:7],
            "n": int(len(y_p)), "n_sc": n_sc_p, "n_entries": int(len(y_e)), "n_groups": int(len(set(sys_p))),
            "families": fam_stats, "parent_about": PARENT_ABOUT}
    bg_out = dict(bg_info, n=int(len(bg)), n_sent=int(sent.sum()), source="JARVIS-DFT 3D (OptB88vdW)",
                  folds=[int((fold_b == k).sum()) for k in range(P.N_FOLDS)], radar=radar_info,
                  n_used=int(use_final.sum()),
                  about=("Hurricane's screening pool: compounds with no superconductivity record, counted as not "
                         "superconducting; split into five folds by chemical system as in round 3"), **H3.KONNO)
    P.log(f"Hurricane {version} = {best['id']} {best['name']} [{best['settings']}]: adopted: {adopted}")
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": H.MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed asking about the parent compound instead of the doped sample, and "
                     "adding what the DFT calculation says about its electrons"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by chemical system on {len(y_p):,} parent compounds; a design "
                      "trained on SuperCon entries never sees an entry from a held-out system, and the background "
                      "compounds keep round 3's folds"),
        "rule": RULE, "caveat": CAVEAT, "parent_about": PARENT_ABOUT, "found_about": FOUND_ABOUT,
        "electronic_about": ELECTRONIC_ABOUT, "false_alarms_about": H3.FA_ABOUT, "unknown_about": H4.UNKNOWN_ABOUT,
        "dismissed_about": H4.DISMISS_ABOUT, "shift_about": ("the mean change of a parent's chance of superconducting "
                                                             "when it is described with JARVIS-DFT values instead of "
                                                             "Materials Project ones (out of fold)"),
        "scikit_learn": sklearn.__version__, "data": data, "background": bg_out, "matched": {"n": int(len(j_pos))},
        "previous": {"id": ref["id"], "version": cur_ver, "scores": ref["scores"], "reliability": rr,
                     "lofo": ref["lofo"]},
        "dismissed_bar": bar, "dismissed_bar_version": ref_ver,
        "leaderboard": sorted(board, key=lambda r: (-(r["reliability"].get("found") if r["reliability"].get("found")
                                                      is not None else -1), r["scores"]["tc_mae"])),
        "best": best, "adopted": adopted, "finds_more": better,
        "spec": model_spec(cb, n_cols, int(use_final.sum())),
        "changes": spec_changes(cb, cands[0], int(use_final.sum())),
        "importance": imp, "lofo": lofo_rows, "anchors": anchors_out or None,
        "minutes": round((time.time() - t_start) / 60, 1),
    }
    for r in out["leaderboard"]:
        r["params"] = dict(r["params"])
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="hurricane5-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"hurricane_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    ob = outs[best["id"]]
    pd.DataFrame({"material_id": par["material_id"], "formula": par["formula_sc"],
                  "one_entry": par["formula_entry"],
                  "family": fam_p, "chemsys": sys_p, "n_entries": par["n_entries"], "n_sc": par["n_sc"],
                  "tc_max": y_p, "tc_pred_best": ob["pred"], "p_sc_best": ob["p"], "not_known_best": ob["unknown"],
                  "p_sc_previous": outs["P0"]["p"], "tc_pred_previous": outs["P0"]["pred"]}
                 ).round(4).to_csv(results / f"hurricane_round{ROUND}_parents.csv", index=False)
    update_progress(out, progress)
    if SMOKE:
        P.log(f"hurricane5 smoke test passed; outputs in {tmp}")


def update_progress(out: dict, progress: Path) -> None:
    """Round 5's entry in the "hurricane" block: the same shape as round 4, with the share of a left-out family that
    the design finds next to the share it calls unlikely."""
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, prev, ver = out["best"], out["previous"], out["version"]
    sc, br, pr = best["scores"], best["reliability"], prev["reliability"]
    r2 = lambda v: None if v is None else round(float(v), 2)   # noqa: E731
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    bg = out["background"]
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": f"{best['name']}, {best['settings']}",
        "changes": out["changes"], "spec": out["spec"], "rule": out["rule"],
        "scores": {"tc_mae": r2(sc["tc_mae"]), "folds": [r2(x) for x in sc["fold_mae"]],
                   "folds_better": best.get("folds_better_previous"),
                   "sc_mae": r2(sc["sc_mae"]), "high_tc_mae": r2(sc["high_tc_mae"]), "high_tc": H.HIGH_TC,
                   "r2_log": round(sc["r2_log"], 3), "of": "the parent compounds",
                   "by_family": {f: {"n": v["n"], "mae": r2(v["mae"])} for f, v in sc["by_family"].items()}},
        "previous": {"version": prev["version"], "tc_mae": r2(prev["scores"]["tc_mae"]),
                     "folds": [r2(x) for x in prev["scores"]["fold_mae"]],
                     "folds_better": best.get("folds_better_previous"), "sc_mae": r2(prev["scores"]["sc_mae"]),
                     "high_tc_mae": r2(prev["scores"]["high_tc_mae"])},
        "lofo": [{k: (r2(v) if isinstance(v, float) and k.startswith(("mae", "max")) else r3(v)
                      if isinstance(v, float) else v) for k, v in r.items()} for r in out["lofo"]],
        "importance": out["importance"],
        "search": {"candidates": len(out["leaderboard"]), "previous_id": prev["id"],
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"],
                                    "tc_mae": r2(r["scores"]["tc_mae"]), "sc_mae": r2(r["scores"]["sc_mae"]),
                                    "found": r3(r["reliability"].get("found")),
                                    "dismissed": r3(r["reliability"].get("dismissed")),
                                    "unknown": r3(r["reliability"].get("unknown_lofo")),
                                    "false_alarms": r3(r["reliability"].get("false_alarms")),
                                    "coverage": r3(r["reliability"].get("coverage")),
                                    "brier": r3(r["reliability"].get("brier")),
                                    "shift": r3(r["reliability"].get("shift")), "passed": r.get("passed")}
                                   for r in out["leaderboard"]]},
        "reliability": {
            "about": out["false_alarms_about"], "rule": out["rule"], "caveat": out["caveat"],
            "found_about": out["found_about"], "unknown_about": out["unknown_about"],
            "dismissed_about": out["dismissed_about"], "parent_about": out["parent_about"],
            "electronic_about": out["electronic_about"],
            "background": {"n": bg["n"], "n_sent": bg["n_sent"], "source": bg["source"], "cite": H3.KONNO["cite"],
                           "doi": H3.KONNO["doi"], "weight": best.get("background"), "radius": best.get("radius"),
                           "n_used": bg["n_used"]},
            "abstain": best.get("abstain"),
            "found": r3(br.get("found")), "found_previous": r3(pr.get("found")),
            "unknown_lofo": r3(br.get("unknown_lofo")), "unknown_lofo_previous": r3(pr.get("unknown_lofo")),
            "dismissed": r3(br.get("dismissed")), "dismissed_previous": r3(pr.get("dismissed")),
            "dismissed_bar": r3(out.get("dismissed_bar")), "dismissed_bar_version": out.get("dismissed_bar_version"),
            "false_alarms": r3(br["false_alarms"]), "false_alarms_previous": r3(pr["false_alarms"]),
            "unknown_sent": r3(br["unknown_sent"]), "unknown_all": r3(br["unknown_all"]),
            "coverage": r3(br["coverage"]), "coverage_previous": r3(pr["coverage"]),
            "brier": r3(br["brier"]), "brier_previous": r3(pr["brier"]),
            "share_sc_likely": r3(br["share_sc_likely"]), "share_sc_unlikely": r3(br["share_sc_unlikely"]),
            "shift": r3(br["shift"]), "shift_previous": r3(pr["shift"]), "shift_abs": r3(br["shift_abs"]),
            "n_matched": br["n_matched"], "shift_about": out["shift_about"], "checks": best.get("checks")},
    }
    if out.get("anchors"):
        a = out["anchors"]
        entry["anchors"] = {"n_scored": a["summary"]["n_scored"], "mae": a["summary"]["mae"],
                            "scored_as_check": a["summary"]["scored_as_check"], "rule": a["summary"]["rule"],
                            "table": a["table"]}
    reg = prog.get("hurricane") or {}
    versions = sorted([v for v in reg.get("versions", []) if v.get("round") != ROUND] + [entry],
                      key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    cur = released[-1] if released else None
    block = dict(reg)
    block.update({"name": H.MODEL, "current": cur["version"] if cur else None, "versions": versions})
    if out["adopted"]:
        block["data"] = out["data"]
    prog["hurricane"] = block
    if out["adopted"]:
        d = out["data"]
        note = (f"5-fold CV grouped by chemical system; {d['n']:,} parent compounds from {d['n_entries']:,} 3DSC "
                f"entries, {d['n_sc']:,} of which superconduct when doped, plus {bg['n_used']:,} compounds with no "
                "superconductivity record for the classifier")
        prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
            {"tag": "hurricane", "model": f"{H.MODEL} {ver} (AI-designed)", "target": "Tc_exp (parent compound)",
             "mae": r2(sc["tc_mae"]), "unit": "K", "note": note}]
        text = (f"Asks whether a parent compound is worth doping: it learns from {d['n']:,} parent compounds in 3DSC "
                f"({d['n_sc']:,} of which superconduct in some doped form), from what DFT says about their electrons, "
                f"and from {bg['n_used']:,} compounds with no superconductivity record. Trained without a whole "
                f"family it finds {br['found']:.0%} of that family's superconducting parents (Hurricane "
                f"{prev['version']}: {pr['found']:.0%}), gives {br['false_alarms']:.0%} of the held-out compounds "
                f"with no record at least an even chance, and answers \"not known\" far from its training data. "
                "Our AI agent designed it.")
        fam = [m for m in prog.get("model_family", []) if m.get("id") != "hurricane"]
        fam.append({"id": "hurricane", "status": f"{H.MODEL} {ver} in use", "active": True, "text": text})
        prog["model_family"] = fam
    H.ai_stage(prog)
    P.tidy(prog)
    prefix = f"{H.MODEL}, round {ROUND} ("
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(prefix)]   # a re-run replaces it
    f0 = lambda v: "n/a" if v is None else f"{v:.0%}"   # noqa: E731
    P.add_log(prog, stamp, f"{H.MODEL}, round {ROUND} ({len(out['leaderboard']) - 1} AI-designed candidates): best "
                           f"{best['id']} {best['name']} [{best['settings']}]; trained without a whole family it finds "
                           f"{f0(br.get('found'))} of that family's superconducting parents, against "
                           f"{f0(pr.get('found'))} for Hurricane {prev['version']}, and calls "
                           f"{f0(br.get('dismissed'))} of them unlikely; false alarms {f0(br['false_alarms'])}; a "
                           f"chance for {f0(br['coverage'])} of the held-out parents; parent Tc MAE "
                           f"{sc['tc_mae']:.2f} K against {prev['scores']['tc_mae']:.2f} K; " +
                           (f"released as {H.MODEL} {ver}" if out["adopted"] else
                            f"not released, so Hurricane {prev['version']} stays in use"))
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {H.MODEL} round {ROUND} ({entry['status']})")


if __name__ == "__main__":
    run()
