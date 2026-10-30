"""supercon-ml pipeline: electron-phonon data, baseline models and progress updates.

Usage (from the repository root):
    python ml/pipeline.py baseline     # composition + structure features, gradient boosting
    python ml/pipeline.py foundation   # adds frozen MACE-MP-0 descriptors and bagged heads
    python ml/pipeline.py search       # AI-designed model search; releases the Storm model, same CV

The command downloads the Alexandria and JARVIS electron-phonon datasets through
jarvis-tools, cleans them, recomputes the Allen-Dynes Tc with one mu*, trains
gradient-boosting baselines with composition-grouped cross-validation, and writes
results/ plus an updated progress/progress.json. The JARVIS set is kept aside as the
locked cross-code test set and is never used for training here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PROGRESS = ROOT / "progress" / "progress.json"
CACHE = Path(os.environ.get("SUPERCON_DATA", Path.home() / ".cache" / "supercon-data"))
MU_STAR = 0.10
SEED = 7
N_FOLDS = 5
try:  # the project log uses US Central time
    from zoneinfo import ZoneInfo
    CENTRAL = ZoneInfo("America/Chicago")
except Exception:  # pragma: no cover
    CENTRAL = dt.timezone(dt.timedelta(hours=-6))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- data


def load_dataset(name: str) -> list[dict]:
    from jarvis.db.figshare import data

    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows = data(name, store_dir=str(CACHE))
    log(f"{name}: {len(rows)} entries in {time.time() - t0:.0f}s; fields: {sorted(rows[0].keys())}")
    return rows


def pick(keys, *candidates):
    lower = {k.lower(): k for k in keys}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def allen_dynes(lam, wlog, mu=MU_STAR):
    """Allen-Dynes Tc (K) without the f1 f2 strong-coupling corrections; wlog in K."""
    lam = np.asarray(lam, float)
    wlog = np.asarray(wlog, float)
    denom = lam - mu * (1 + 0.62 * lam)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        tc = (wlog / 1.2) * np.exp(-1.04 * (1 + lam) / denom)
    return np.where((denom > 0) & np.isfinite(tc), tc, 0.0)


def to_frame(rows: list[dict], source: str) -> tuple[pd.DataFrame, dict]:
    keys = rows[0].keys()
    k_lam = pick(keys, "la", "lambda", "lam", "lamb", "el_ph_lambda")
    k_wlog = pick(keys, "wlog", "omega_log", "w_log", "omegalog", "wlog_K")
    k_tc = pick(keys, "Tc", "tc", "tc_ad", "Tc_AD")
    k_id = pick(keys, "jid", "id", "mat_id", "material_id", "alex_id")
    k_atoms = pick(keys, "atoms", "structure")
    k_mag = pick(keys, "magmom", "magmom_outcar", "magmom_oszicar", "total_magnetization")
    fields = {"lambda": k_lam, "wlog": k_wlog, "tc": k_tc, "id": k_id, "atoms": k_atoms, "magmom": k_mag}
    missing = [n for n in ("lambda", "wlog", "atoms") if fields[n] is None]
    if missing:
        raise SystemExit(f"{source}: could not find fields {missing}; available: {sorted(keys)}")
    recs = []
    for i, r in enumerate(rows):
        try:
            lam = float(r[k_lam])
            wlog = float(r[k_wlog])
        except (TypeError, ValueError):
            continue
        recs.append({
            "id": str(r.get(k_id, f"{source}-{i}")) if k_id else f"{source}-{i}",
            "source": source,
            "atoms": r[k_atoms],
            "lambda": lam,
            "wlog": wlog,
            "tc_reported": _num(r.get(k_tc)) if k_tc else np.nan,
            "magmom": _num(r.get(k_mag)) if k_mag else np.nan,
        })
    return pd.DataFrame(recs), fields


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    counts = {"raw": int(len(df))}
    df = df[np.isfinite(df["lambda"]) & np.isfinite(df["wlog"])]
    df = df[(df["lambda"] > 0) & (df["lambda"] < 10) & (df["wlog"] > 0) & (df["wlog"] < 3000)]
    counts["finite_physical"] = int(len(df))
    elems = df["atoms"].map(lambda a: sorted(set(a["elements"])))
    df = df.assign(elements=elems, chemsys=elems.map("-".join))
    df = df[~df["elements"].map(lambda e: "H" in e)]
    counts["no_hydrides"] = int(len(df))
    if df["magmom"].notna().any():
        df = df[~(df["magmom"].abs() > 0.5)]
    counts["non_magnetic"] = int(len(df))
    df = df.assign(tc=allen_dynes(df["lambda"], df["wlog"]))
    return df.reset_index(drop=True), counts


# ---------------------------------------------------------------- features

ELEMENT_PROPS = ["Z", "atomic_mass", "X", "row", "group", "atomic_radius", "mendeleev_no", "valence"]


def element_table(symbols) -> pd.DataFrame:
    from pymatgen.core.periodic_table import Element

    rows = {}
    for s in symbols:
        e = Element(s)
        def val(attr):
            try:
                v = getattr(e, attr)
                return float(v) if v is not None else np.nan
            except Exception:
                return np.nan
        try:
            valence = float(sum(n for _, n in [e.valence])) if e.valence else np.nan
        except Exception:
            valence = np.nan
        rows[s] = {
            "Z": float(e.Z),
            "atomic_mass": val("atomic_mass"),
            "X": val("X"),
            "row": val("row"),
            "group": val("group"),
            "atomic_radius": val("atomic_radius"),
            "mendeleev_no": val("mendeleev_no"),
            "valence": valence,
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def featurize(df: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    feats = []
    for atoms in df["atoms"]:
        els = list(atoms["elements"])
        uniq, counts = np.unique(els, return_counts=True)
        frac = counts / counts.sum()
        props = table.loc[uniq, ELEMENT_PROPS].to_numpy(float)
        f = {"n_elements": len(uniq), "n_sites": len(els)}
        for j, name in enumerate(ELEMENT_PROPS):
            col = props[:, j]
            ok = np.isfinite(col)
            if not ok.any():
                for stat in ("mean", "std", "min", "max"):
                    f[f"{name}_{stat}"] = np.nan
                continue
            w = frac[ok] / frac[ok].sum()
            mean = float(np.sum(w * col[ok]))
            f[f"{name}_mean"] = mean
            f[f"{name}_std"] = float(np.sqrt(np.sum(w * (col[ok] - mean) ** 2)))
            f[f"{name}_min"] = float(col[ok].min())
            f[f"{name}_max"] = float(col[ok].max())
        f.update(structure_features(atoms, table))
        feats.append(f)
    return pd.DataFrame(feats)


def structure_features(atoms: dict, table: pd.DataFrame) -> dict:
    lat = np.asarray(atoms["lattice_mat"], float)
    coords = np.asarray(atoms["coords"], float)
    if atoms.get("cartesian"):
        frac = coords @ np.linalg.inv(lat)
    else:
        frac = coords
    vol = abs(float(np.linalg.det(lat)))
    n = len(atoms["elements"])
    mass = float(table.loc[list(atoms["elements"]), "atomic_mass"].sum())
    a, b, c = np.linalg.norm(lat, axis=1)
    out = {
        "volume_per_atom": vol / n,
        "density": mass * 1.66054 / vol,  # g/cm^3
        "a": a, "b": b, "c": c,
        "c_over_a": c / a if a else np.nan,
    }
    # nearest-neighbour distances over the 27 neighbouring cells
    shifts = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], float)
    cart = frac @ lat
    images = (frac[None, :, :] + shifts[:, None, :]).reshape(-1, 3) @ lat
    d = np.linalg.norm(cart[:, None, :] - images[None, :, :], axis=-1)
    d[d < 1e-6] = np.inf
    nn = d.min(axis=1)
    out.update({"nn_min": float(nn.min()), "nn_mean": float(nn.mean()), "nn_max": float(nn.max())})
    return out


# ---------------------------------------------------------------- models


def grouped_cv(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, log_target=False):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import GroupKFold

    pred = np.zeros_like(y, dtype=float)
    for k, (tr, te) in enumerate(GroupKFold(n_splits=N_FOLDS).split(X, y, groups)):
        model = HistGradientBoostingRegressor(
            max_iter=800, learning_rate=0.04, max_leaf_nodes=31, min_samples_leaf=20,
            l2_regularization=1.0, random_state=SEED + k)
        target = np.log1p(y[tr]) if log_target else y[tr]
        model.fit(X.iloc[tr], target)
        p = model.predict(X.iloc[te])
        pred[te] = np.expm1(p) if log_target else p
    return pred


def metrics(y, p, tail=None):
    err = p - y
    out = {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "r2": float(1 - np.sum(err ** 2) / np.sum((y - y.mean()) ** 2)),
        "n": int(len(y)),
    }
    if tail is not None:
        m = y >= tail
        out["tail_threshold"] = float(tail)
        out["tail_n"] = int(m.sum())
        out["tail_mae"] = float(np.mean(np.abs(err[m]))) if m.any() else None
    return out


# ---------------------------------------------------------------- progress


def now_iso() -> str:
    return dt.datetime.now(CENTRAL).replace(microsecond=0).isoformat()


def add_log(prog: dict, stamp: str, event: str) -> None:
    """Append an activity entry unless the same event is already recorded."""
    if not any(e.get("event") == event for e in prog.get("log", [])):
        prog.setdefault("log", []).append({"at": stamp, "event": event})


def add_history(prog: dict, entry: dict) -> None:
    """Append a training-run point unless the latest point for this model has the same score."""
    hist = prog.setdefault("history", [])
    same = [h for h in hist if h.get("model") == entry["model"] and h.get("target") == entry["target"]]
    if not same or same[-1].get("mae") != entry["mae"]:
        hist.append(entry)


def tidy(prog: dict) -> None:
    """Drop repeated activity entries and repeated history points left by earlier runs."""
    seen, log = set(), []
    for e in prog.get("log", []):
        if e.get("event") not in seen:
            seen.add(e.get("event"))
            log.append(e)
    prog["log"] = log
    hist, last = [], {}
    for h in prog.get("history", []):
        key = (h.get("model"), h.get("target"))
        if last.get(key) != h.get("mae"):
            hist.append(h)
        last[key] = h.get("mae")
    prog["history"] = hist


def update_progress(summary: dict, scores: dict) -> None:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    stamp = now_iso()
    today = stamp[:10]
    alex = summary["alexandria"]["counts"]
    jar = summary["jarvis"]["counts"]
    for st in prog["stages"]:
        if st["id"] == "compute":
            st.update(status="done", date=st.get("date") or today)
        elif st["id"] == "data-eph":
            st.update(status="done", date=today, detail=(
                f"{alex['non_magnetic']:,} Alexandria entries kept for training (of {alex['raw']:,}); "
                f"{jar['non_magnetic']:,} JARVIS entries held out as the locked test set; "
                f"Tc recomputed with mu* = {MU_STAR}"))
        elif st["id"] == "baseline":
            st.update(status="active", date=today, detail=(
                "Electron-phonon baseline done (gradient boosting, composition + structure features); "
                "measured-Tc baseline next"))
    tc = scores["tc_direct"]
    prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "baseline-eph"] + [
        {"tag": "baseline-eph", "model": "Gradient boosting (composition + structure)", "target": "Tc",
         "mae": round(tc["mae"], 3), "unit": "K", "note": f"{N_FOLDS}-fold composition-grouped CV on Alexandria"},
        {"tag": "baseline-eph", "model": "Gradient boosting for lambda and omega_log, then Allen-Dynes", "target": "Tc",
         "mae": round(scores["tc_via_lambda_wlog"]["mae"], 3), "unit": "K",
         "note": f"Same CV; Tc computed from the two predicted quantities with mu* = {MU_STAR}"},
        {"tag": "baseline-eph", "model": "Gradient boosting (composition + structure)", "target": "lambda",
         "mae": round(scores["lambda"]["mae"], 3), "unit": "", "note": f"{N_FOLDS}-fold composition-grouped CV on Alexandria"},
        {"tag": "baseline-eph", "model": "Gradient boosting (composition + structure)", "target": "omega_log",
         "mae": round(scores["wlog"]["mae"], 1), "unit": "K", "note": f"{N_FOLDS}-fold composition-grouped CV on Alexandria"},
    ]
    tidy(prog)
    add_history(prog, {"at": stamp, "model": "Gradient-boosting baseline", "target": "Tc", "split": "val",
                       "mae": round(tc["mae"], 3)})
    add_log(prog, stamp, f"Downloaded {alex['raw']:,} Alexandria and {jar['raw']:,} JARVIS electron-phonon "
                         f"entries; kept {alex['non_magnetic']:,} for training")
    add_log(prog, stamp, f"Gradient-boosting baseline: Tc MAE {tc['mae']:.2f} K, lambda MAE "
                         f"{scores['lambda']['mae']:.3f}, omega_log MAE {scores['wlog']['mae']:.1f} K "
                         f"({N_FOLDS}-fold composition-grouped CV)")
    done = sum(1 for s in prog["stages"] if s["status"] == "done")
    current = next((s for s in prog["stages"] if s["status"] == "active"), None)
    prog["badge"] = f"{done}/{len(prog['stages'])} done · now: " + (current["short"].lower() if current else "baselines")
    prog["updated"] = stamp
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"progress updated: {prog['badge']}")


# ---------------------------------------------------------------- foundation-model descriptors

MACE_MODEL = os.environ.get("MACE_MODEL", "medium")
N_BAGS = 3


def mace_descriptors(df: pd.DataFrame, key: str) -> np.ndarray:
    """Mean, std and max over atoms of frozen MACE-MP-0 invariant descriptors."""
    cache = CACHE / f"mace_mp0_{MACE_MODEL}_{key}.npz"
    ids = df["id"].astype(str).to_numpy()
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        if len(z["ids"]) == len(ids) and (z["ids"] == ids).all():
            log(f"MACE descriptors loaded from cache ({z['X'].shape})")
            return z["X"]
    import torch
    from jarvis.core.atoms import Atoms
    from mace.calculators import mace_mp

    torch.set_num_threads(os.cpu_count() or 2)
    calc = mace_mp(model=MACE_MODEL, device="cpu", default_dtype="float32")
    feats = []
    t0 = time.time()
    for i, a in enumerate(df["atoms"]):
        d = calc.get_descriptors(Atoms.from_dict(a).ase_converter(), invariants_only=True)
        if isinstance(d, list):
            d = d[0]
        d = np.asarray(d, dtype=np.float32)
        feats.append(np.concatenate([d.mean(0), d.std(0), d.max(0)]))
        if (i + 1) % 1000 == 0:
            log(f"MACE descriptors: {i + 1}/{len(df)} in {time.time() - t0:.0f}s")
    X = np.vstack(feats)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, ids=ids, X=X)
    log(f"MACE descriptors: {X.shape} in {time.time() - t0:.0f}s")
    return X


def bagged_grouped_cv(X: np.ndarray, y: np.ndarray, groups: np.ndarray, log_target=False, n_bags=N_BAGS):
    """Grouped CV with a bootstrap ensemble per fold; returns the mean prediction and its spread."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import GroupKFold

    preds = np.zeros((n_bags, len(y)))
    rng = np.random.default_rng(SEED)
    for k, (tr, te) in enumerate(GroupKFold(n_splits=N_FOLDS).split(X, y, groups)):
        for b in range(n_bags):
            idx = rng.choice(tr, size=len(tr), replace=True)
            model = HistGradientBoostingRegressor(
                max_iter=1000, learning_rate=0.04, max_leaf_nodes=31, min_samples_leaf=20,
                l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
                n_iter_no_change=40, random_state=SEED + 13 * k + b)
            target = np.log1p(y[idx]) if log_target else y[idx]
            model.fit(X[idx], target)
            p = model.predict(X[te])
            preds[b, te] = np.expm1(p) if log_target else p
    return preds.mean(0), preds.std(0)


def update_progress_foundation(scores: dict, base: dict | None) -> None:
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    stamp = now_iso()
    for st in prog["stages"]:
        if st["id"] == "foundation":
            st.update(status="active", date=stamp[:10], detail=(
                f"Electron-phonon head done: frozen MACE-MP-0 ({MACE_MODEL}) descriptors with "
                f"{N_BAGS}-model bagged gradient boosting for uncertainty; measured-Tc head next"))
    tc = scores["tc_direct"]
    note = f"{N_FOLDS}-fold composition-grouped CV on Alexandria"
    prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "foundation-eph"] + [
        {"tag": "foundation-eph", "model": f"MACE-MP-0 descriptors + gradient boosting", "target": "Tc",
         "mae": round(tc["mae"], 3), "unit": "K", "note": note},
        {"tag": "foundation-eph", "model": "MACE-MP-0 descriptors, lambda and omega_log, then Allen-Dynes",
         "target": "Tc", "mae": round(scores["tc_via_lambda_wlog"]["mae"], 3), "unit": "K",
         "note": f"Same CV; mu* = {MU_STAR}"},
        {"tag": "foundation-eph", "model": "MACE-MP-0 descriptors + gradient boosting", "target": "lambda",
         "mae": round(scores["lambda"]["mae"], 3), "unit": "", "note": note},
        {"tag": "foundation-eph", "model": "MACE-MP-0 descriptors + gradient boosting", "target": "omega_log",
         "mae": round(scores["wlog"]["mae"], 1), "unit": "K", "note": note},
    ]
    tidy(prog)
    add_history(prog, {"at": stamp, "model": "MACE-MP-0 descriptors + gradient boosting", "target": "Tc",
                       "split": "val", "mae": round(tc["mae"], 3)})
    change = ""
    if base:
        change = f" (baseline {base['tc_direct']['mae']:.2f} K)"
    add_log(prog, stamp, (
        f"MACE-MP-0 descriptors + gradient boosting: Tc MAE {tc['mae']:.2f} K{change}, lambda MAE "
        f"{scores['lambda']['mae']:.3f}, omega_log MAE {scores['wlog']['mae']:.1f} K; uncertainty vs error "
        f"Spearman {scores['tc_direct'].get('uncertainty_spearman', float('nan')):.2f}"))
    done = sum(1 for s in prog["stages"] if s["status"] == "done")
    prog["badge"] = f"{done}/{len(prog['stages'])} done · now: foundation model"
    prog["updated"] = stamp
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"progress updated: {prog['badge']}")


# ---------------------------------------------------------------- AI-designed model search

BASE_PARAMS = dict(max_iter=800, learning_rate=0.04, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=1.0)
N_PCA = 32
PHYSICS_RATIONALE = {
    "vec": "valence electrons per atom; Matthias found Tc peaks near 4.7 and 6.5 in transition-metal compounds",
    "matthias_d47": "distance of the valence-electron count from the first Matthias peak (4.7)",
    "matthias_d65": "distance from the second Matthias peak (6.5)",
    "d_fraction": "share of d-block atoms, a proxy for a high density of states at the Fermi level",
    "p_fraction": "share of p-block atoms (covalent bonding, as in MgB2 and the A15 compounds)",
    "light_fraction": "share of light atoms (Z <= 9), which vibrate at high frequency",
    "inv_sqrt_mass": "composition average of M^-1/2; phonon frequencies scale like M^-1/2 (isotope effect)",
    "omega_proxy": "M^-1/2 divided by the mean nearest-neighbour distance, a crude stiffness-over-mass frequency scale",
    "mass_ratio": "heaviest over lightest atomic mass; light atoms in a heavy matrix give separate optical modes",
    "x_diff": "electronegativity difference, a proxy for ionicity and charge transfer",
    "packing_fraction": "atomic-sphere volume over volume per atom, a proxy for how compressed the lattice is",
}


def _block(z: int, group: float) -> str:
    if 58 <= z <= 71 or 90 <= z <= 103:
        return "f"
    if group in (1, 2) or z == 2:
        return "s"
    if 3 <= group <= 12:
        return "d"
    return "p"


def physics_features(df: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Physics-motivated descriptors proposed by the AI agent in search round 1 (see PHYSICS_RATIONALE)."""
    from pymatgen.core.periodic_table import Element

    info = {}

    def element(sym):
        if sym not in info:
            e = Element(sym)
            z, grp = int(e.Z), float(e.group or 0)
            blk = _block(z, grp)
            ve = 2.0 if z == 2 else grp if blk in ("s", "d") else (grp - 10 if blk == "p" else 3.0)
            r = getattr(e, "atomic_radius", None)
            x = getattr(e, "X", None)
            info[sym] = (float(e.atomic_mass), float(ve), blk, z,
                         float(r) if r is not None else np.nan, float(x) if x is not None else np.nan)
        return info[sym]

    rows = []
    for atoms, vpa, nn_mean in zip(df["atoms"], base["volume_per_atom"], base["nn_mean"]):
        uniq, counts = np.unique(list(atoms["elements"]), return_counts=True)
        x = counts / counts.sum()
        el = [element(s) for s in uniq]
        mass = np.array([e[0] for e in el])
        ve = np.array([e[1] for e in el])
        blk = np.array([e[2] for e in el])
        z = np.array([e[3] for e in el])
        rad = np.array([e[4] for e in el])
        chi = np.array([e[5] for e in el])
        vec = float(np.sum(x * ve))
        inv_sqrt_m = float(np.sum(x / np.sqrt(mass)))
        rad = np.where(np.isfinite(rad), rad, np.nanmean(rad) if np.isfinite(rad).any() else 1.5)
        rows.append({
            "vec": vec,
            "matthias_d47": abs(vec - 4.7),
            "matthias_d65": abs(vec - 6.5),
            "d_fraction": float(np.sum(x[blk == "d"])),
            "p_fraction": float(np.sum(x[blk == "p"])),
            "light_fraction": float(np.sum(x[z <= 9])),
            "inv_sqrt_mass": inv_sqrt_m,
            "omega_proxy": inv_sqrt_m / nn_mean if nn_mean > 0 else np.nan,
            "mass_ratio": float(mass.max() / mass.min()),
            "x_diff": float(np.nanmax(chi) - np.nanmin(chi)) if np.isfinite(chi).any() else np.nan,
            "packing_fraction": float(np.sum(x * 4.0 / 3.0 * np.pi * rad ** 3) / vpa) if vpa > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def cv_predict(X: np.ndarray, y: np.ndarray, groups: np.ndarray, params: dict, log_target=False, pca_from=None):
    """Grouped-CV predictions. If pca_from is set, columns from that index on are standardised and
    reduced to N_PCA principal components inside each training fold, so nothing leaks from the test fold."""
    from sklearn.decomposition import PCA
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler

    pred = np.zeros(len(y))
    for k, (tr, te) in enumerate(GroupKFold(n_splits=N_FOLDS).split(X, y, groups)):
        xtr, xte = X[tr], X[te]
        if pca_from is not None:
            rtr, rte = np.nan_to_num(xtr[:, pca_from:]), np.nan_to_num(xte[:, pca_from:])
            sc = StandardScaler().fit(rtr)
            pca = PCA(n_components=min(N_PCA, X.shape[1] - pca_from), random_state=SEED).fit(sc.transform(rtr))
            xtr = np.hstack([xtr[:, :pca_from], pca.transform(sc.transform(rtr))])
            xte = np.hstack([xte[:, :pca_from], pca.transform(sc.transform(rte))])
        model = HistGradientBoostingRegressor(random_state=SEED + k, **params)
        model.fit(xtr, np.log1p(y[tr]) if log_target else y[tr])
        p = model.predict(xte)
        pred[te] = np.expm1(p) if log_target else p
    return pred


MODEL_NAME = "Storm"
MODEL_ABOUT = ("Storm is the project's AI-designed Tc model. An AI agent (Claude) proposes each design; every "
               "candidate is trained and scored with the same composition-grouped cross-validation, and a new version "
               "is released only if it beats the current best on average and in at least 4 of the 5 folds.")
STRUCTURE_COLS = {"volume_per_atom", "density", "a", "b", "c", "c_over_a", "nn_min", "nn_mean", "nn_max"}
SEARCH_ROUND = 1
ADOPT_FOLDS = 4  # adopt a design only if it beats the reference on average and in at least 4 of the 5 folds


def model_spec(set_id: str, params: dict, base_cols: list, n_mace: int) -> dict:
    """Machine-readable structure of a design; the app animates it, so every new version explains itself."""
    n_struct = sum(1 for c in base_cols if c in STRUCTURE_COLS)
    inputs = [
        {"group": "composition", "label": "Composition statistics", "n": len(base_cols) - n_struct,
         "detail": "mean, spread, min and max of 8 element properties, plus element and site counts"},
        {"group": "structure", "label": "Crystal structure", "n": n_struct,
         "detail": "volume and density, lattice lengths, nearest-neighbour distances"},
    ]
    if set_id in ("D", "E"):
        inputs.append({"group": "physics", "label": "Physics features proposed by the AI", "n": len(PHYSICS_RATIONALE),
                       "items": [{"name": k, "why": v} for k, v in PHYSICS_RATIONALE.items()]})
    if set_id == "B":
        inputs.append({"group": "mace", "label": "MACE-MP-0 fingerprint", "n": n_mace,
                       "detail": "frozen foundation-model descriptors: mean, spread and max over atoms"})
    elif set_id in ("C", "E"):
        inputs.append({"group": "mace", "label": "MACE-MP-0 fingerprint, compressed", "n_in": n_mace, "n": N_PCA,
                       "transform": "PCA", "detail": f"{n_mace} foundation-model numbers squeezed to {N_PCA} principal "
                                                    "components, fitted inside each training fold"})
    return {
        "inputs": inputs,
        "learner": {"kind": "gradient-boosting", "trees": params["max_iter"], "leaves": params["max_leaf_nodes"],
                    "learning_rate": params["learning_rate"], "min_leaf": params["min_samples_leaf"],
                    "l2": params["l2_regularization"], "features_per_split": params.get("max_features", 1.0)},
        "target": "log(1 + Tc)",
        "cv": f"{N_FOLDS}-fold, grouped by chemical system",
    }


def spec_changes(spec: dict, ref: dict) -> list:
    """Plain-language list of what a design changes relative to the reference design."""
    out = []
    have = {i["group"]: i for i in ref["inputs"]}
    for i in spec["inputs"]:
        if i["group"] in have:
            continue
        if i["group"] == "physics":
            out.append(f"Adds {i['n']} physics features proposed by the AI: valence electrons per atom and the distance "
                       "to Matthias's two Tc peaks, d- and p-block shares, light-atom share, an M^-1/2 phonon scale, a "
                       "stiffness-over-mass proxy, mass ratio, electronegativity spread and packing fraction")
        elif i["group"] == "mace" and i.get("transform"):
            out.append(f"Adds the MACE-MP-0 foundation-model fingerprint, compressed from {i['n_in']} to {i['n']} "
                       "numbers with principal-component analysis")
        elif i["group"] == "mace":
            out.append(f"Adds the full {i['n']}-number MACE-MP-0 foundation-model fingerprint")
    a, b = spec["learner"], ref["learner"]
    if a["leaves"] != b["leaves"] or a["min_leaf"] != b["min_leaf"]:
        word = "Deeper" if a["leaves"] > b["leaves"] else "Smaller"
        out.append(f"{word} trees: up to {a['leaves']} leaves (was {b['leaves']}), at least {a['min_leaf']} materials "
                   f"per leaf (was {b['min_leaf']})")
    if a["l2"] != b["l2"]:
        out.append(f"Stronger penalty on large leaf values (L2 {a['l2']:g}, was {b['l2']:g})")
    if a["learning_rate"] != b["learning_rate"] or a["trees"] != b["trees"]:
        out.append(f"Learning rate {a['learning_rate']:g} with {a['trees']:,} trees (was {b['learning_rate']:g} "
                   f"with {b['trees']:,})")
    if a["features_per_split"] != b["features_per_split"]:
        out.append(f"Each split looks at a random {a['features_per_split']:.0%} of the features")
    return out or ["Same structure as the reference; different random seed or data"]


def update_progress_search(out: dict) -> None:
    """Record the round under "search" and the released model under "ai_model" in progress.json, plus one
    history point and one log entry. The headline "results" list is left alone, so older app versions keep
    their model panels unchanged."""
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    stamp = now_iso()
    best, ref, rnd, ver = out["best"], out["baseline"], out["round"], out["version"]
    sc = best["scores"]
    prog["search"] = {
        "round": rnd,
        "at": stamp,
        "designer": out["designer"],
        "selection": out["selection"],
        "rule": out["rule"],
        "baseline": {"name": ref["name"], "tc_mae": round(ref["tc_mae"], 3)},
        "best": {"id": best["id"], "name": best["name"], "settings": best["settings"],
                 "tc_mae": round(best["tc_mae"], 3), "folds_better": best["folds_better"]},
        "adopted": out["adopted"],
        "candidates": [{"id": r["id"], "name": r["name"], "settings": r["settings"], "n_features": r["n_features"],
                        "tc_mae": round(r["tc_mae"], 3), "folds_better": r["folds_better"]}
                       for r in out["leaderboard"]],
        "caveat": out["caveat"],
        "details": "results/model_search.json",
    }
    entry = {
        "version": ver,
        "round": rnd,
        "date": stamp[:10],
        "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"] + ("" if best["settings"] == "default" else f", {best['settings']}"),
        "changes": out["changes"],
        "spec": out["spec"],
        "scores": {"tc_mae": round(best["tc_mae"], 3), "reference_mae": round(ref["tc_mae"], 3),
                   "reference": ref["name"], "folds": [round(x, 3) for x in best["fold_mae"]],
                   "reference_folds": [round(x, 3) for x in ref["fold_mae"]], "folds_better": best["folds_better"],
                   "tail_mae": round(best["tc_tail_mae"], 3),
                   "tc_via_lambda_wlog_mae": round(sc["tc_via_lambda_wlog"]["mae"], 3),
                   "lambda_mae": round(sc["lambda"]["mae"], 3), "omega_log_mae": round(sc["wlog"]["mae"], 1)},
        "search": {"candidates": len(out["leaderboard"]),
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"],
                                    "tc_mae": round(r["tc_mae"], 3), "folds_better": r["folds_better"]}
                                   for r in out["leaderboard"]]},
    }
    reg = prog.get("ai_model") or {}
    versions = [v for v in reg.get("versions", []) if v.get("round") != rnd] + [entry]
    versions.sort(key=lambda v: v["round"])
    prog["ai_model"] = {"name": MODEL_NAME, "about": MODEL_ABOUT, "current": versions[-1]["version"], "versions": versions}
    tidy(prog)
    add_history(prog, {"at": stamp, "model": f"{MODEL_NAME} {ver} (AI-designed)", "target": "Tc", "split": "val",
                       "mae": round(best["tc_mae"], 3)})
    if out["adopted"]:
        verdict = (f"Tc MAE {best['tc_mae']:.2f} K against {ref['tc_mae']:.2f} K for the baseline, better in "
                   f"{best['folds_better']} of {N_FOLDS} folds; adopted")
    else:
        verdict = (f"Tc MAE {best['tc_mae']:.2f} K against {ref['tc_mae']:.2f} K for the baseline, better in only "
                   f"{best['folds_better']} of {N_FOLDS} folds, so it stays experimental")
    add_log(prog, stamp, f"{MODEL_NAME} {ver}, the AI-designed model from search round {rnd} "
                         f"({len(out['leaderboard'])} candidates): {verdict}")
    prog["updated"] = stamp
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"progress updated: {MODEL_NAME} {ver} ({entry['status']})")


def run_search() -> None:
    """Round 1 of the AI-designed model search. The candidates (feature sets, physics features and
    settings) were proposed by an AI agent; every candidate is scored with the same composition-grouped
    CV on Alexandria, and the locked JARVIS test set is not touched."""
    import sklearn
    from sklearn.model_selection import GroupKFold

    RESULTS.mkdir(exist_ok=True)
    _, frames = load_clean()
    train = frames["alexandria"]
    table = element_table(sorted({e for els in train["elements"] for e in els}))
    base = featurize(train, table)
    phys = physics_features(train, base)
    M = mace_descriptors(train, "alexandria")
    groups = train["chemsys"].to_numpy()
    y_lam, y_wlog, y_tc = (train[c].to_numpy() for c in ("lambda", "wlog", "tc"))
    tail = float(np.quantile(y_tc, 0.9))
    A = base.to_numpy(float)
    D = np.hstack([A, phys.to_numpy(float)])
    folds = [te for _, te in GroupKFold(n_splits=N_FOLDS).split(A, y_tc, groups)]
    log(f"search: {len(y_tc)} materials; {A.shape[1]} hand-made, {phys.shape[1]} physics and {M.shape[1]} MACE features")
    sets = {
        "A": ("Hand-made features (baseline)", A, None),
        "B": ("Hand-made + full MACE-MP-0 descriptors", np.hstack([A, M]), None),
        "C": (f"Hand-made + {N_PCA} MACE principal components", np.hstack([A, M]), A.shape[1]),
        "D": ("Hand-made + physics features", D, None),
        "E": (f"Hand-made + physics + {N_PCA} MACE components", np.hstack([D, M]), D.shape[1]),
    }
    board, preds = [], {}

    def score(cid, set_id, params, tweak="default"):
        name, X, pca_from = sets[set_id]
        t0 = time.time()
        try:
            p = np.clip(cv_predict(X, y_tc, groups, params, log_target=True, pca_from=pca_from), 0, None)
        except TypeError as err:  # e.g. an option this scikit-learn version lacks
            log(f"{cid} skipped: {err}")
            return None
        m = metrics(y_tc, p, tail=tail)
        row = {"id": cid, "set": set_id, "name": name, "settings": tweak, "params": dict(params),
               "n_features": int(X.shape[1] if pca_from is None else pca_from + N_PCA),
               "tc_mae": m["mae"], "tc_rmse": m["rmse"], "tc_r2": m["r2"], "tc_tail_mae": m["tail_mae"],
               "fold_mae": [float(np.mean(np.abs(p[te] - y_tc[te]))) for te in folds],
               "seconds": round(time.time() - t0)}
        board.append(row)
        preds[cid] = p
        log(f"{cid} {name} [{tweak}]: Tc MAE {m['mae']:.3f} K, tail {m['tail_mae']:.2f} K, {row['seconds']} s")
        return row

    for set_id in sets:
        score(set_id, set_id, BASE_PARAMS)
    lead = min(board, key=lambda r: r["tc_mae"])
    variants = (
        ("deeper trees", dict(BASE_PARAMS, max_leaf_nodes=63, min_samples_leaf=10)),
        ("stronger regularization", dict(BASE_PARAMS, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=5.0)),
        ("slower learning", dict(BASE_PARAMS, learning_rate=0.02, max_iter=1600)),
        ("half the features per split", dict(BASE_PARAMS, max_features=0.5)),
    )
    for i, (tweak, params) in enumerate(variants, 1):
        score(f"{lead['set']}{i}", lead["set"], params, tweak)
    ref = next(r for r in board if r["id"] == "A")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_mae"], ref["fold_mae"])))
    # adopt the lowest-error design among those that beat the baseline on average and in >= ADOPT_FOLDS folds
    eligible = [r for r in board if r["id"] != "A" and r["tc_mae"] < ref["tc_mae"] and r["folds_better"] >= ADOPT_FOLDS]
    adopted = bool(eligible)
    best = min(eligible or [r for r in board if r["id"] != "A"], key=lambda r: r["tc_mae"])
    _, X, pca_from = sets[best["set"]]
    p_lam = cv_predict(X, y_lam, groups, best["params"], pca_from=pca_from)
    p_wlog = cv_predict(X, y_wlog, groups, best["params"], pca_from=pca_from)
    extra = {
        "lambda": metrics(y_lam, p_lam),
        "wlog": metrics(y_wlog, p_wlog),
        "tc_via_lambda_wlog": metrics(y_tc, allen_dynes(np.clip(p_lam, 0, None), np.clip(p_wlog, 0, None)), tail=tail),
    }
    cols = list(base.columns)
    spec = model_spec(best["set"], best["params"], cols, M.shape[1])
    changes = spec_changes(spec, model_spec("A", BASE_PARAMS, cols, M.shape[1]))
    version = f"{SEARCH_ROUND}.0"
    log(f"{MODEL_NAME} {version} = {best['id']} {best['name']} [{best['settings']}]: Tc MAE {best['tc_mae']:.3f} K "
        f"(baseline {ref['tc_mae']:.3f} K, better in {best['folds_better']}/{N_FOLDS} folds, adopted: {adopted}); "
        f"via lambda/omega_log {extra['tc_via_lambda_wlog']['mae']:.3f} K")
    out = {
        "run_at": now_iso(),
        "commit": os.environ.get("GITHUB_SHA", "local")[:7],
        "round": SEARCH_ROUND,
        "model": MODEL_NAME,
        "version": version,
        "designer": "AI agent (Claude) proposed the candidate feature sets, the physics features and the settings",
        "selection": (f"{N_FOLDS}-fold GroupKFold by chemical system on Alexandria ({len(y_tc):,} materials); "
                      "the locked JARVIS test set is not used"),
        "rule": (f"release the lowest-error design among those that beat the baseline on average and in at least "
                 f"{ADOPT_FOLDS} of {N_FOLDS} folds; otherwise the best design stays experimental"),
        "caveat": ("picking the best of several candidates on the same folds makes its score slightly optimistic; "
                   "the locked JARVIS test set will check the final model once"),
        "scikit_learn": sklearn.__version__,
        "physics_features": PHYSICS_RATIONALE,
        "baseline": {k: ref[k] for k in ("id", "name", "tc_mae", "fold_mae")},
        "leaderboard": sorted(board, key=lambda r: r["tc_mae"]),
        "best": dict(best, scores=extra),
        "adopted": adopted,
        "spec": spec,
        "changes": changes,
    }
    (RESULTS / "model_search.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"id": train["id"], "chemsys": groups, "tc": y_tc, "tc_pred_storm": preds[best["id"]],
                  "tc_pred_baseline": preds["A"]}).round(5).to_csv(RESULTS / "model_search_predictions.csv", index=False)
    update_progress_search(out)


# ---------------------------------------------------------------- commands


def load_clean() -> tuple[dict, dict]:
    summary = {}
    frames = {}
    for key, name in (("alexandria", "alex_supercon"), ("jarvis", "supercon_3d")):
        rows = load_dataset(name)
        df, fields = to_frame(rows, key)
        df, counts = clean(df)
        frames[key] = df
        summary[key] = {
            "dataset": name, "fields": fields, "counts": counts,
            "lambda": df["lambda"].describe().round(4).to_dict(),
            "wlog": df["wlog"].describe().round(2).to_dict(),
            "tc_ad": df["tc"].describe().round(3).to_dict(),
        }
        if df["tc_reported"].notna().any():
            both = df[df["tc_reported"].notna()]
            summary[key]["tc_reported_vs_recomputed_mae"] = float(np.mean(np.abs(both["tc_reported"] - both["tc"])))
        log(f"{key}: {counts}")
    return summary, frames


def run_baseline() -> None:
    RESULTS.mkdir(exist_ok=True)
    summary, frames = load_clean()
    (RESULTS / "data_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")

    train = frames["alexandria"]
    table = element_table(sorted({e for els in train["elements"] for e in els}))
    t0 = time.time()
    X = featurize(train, table)
    log(f"features: {X.shape[1]} columns for {len(X)} materials in {time.time() - t0:.0f}s")
    groups = train["chemsys"].to_numpy()

    scores = {}
    y_lam = train["lambda"].to_numpy()
    y_wlog = train["wlog"].to_numpy()
    y_tc = train["tc"].to_numpy()
    p_lam = grouped_cv(X, y_lam, groups)
    p_wlog = grouped_cv(X, y_wlog, groups)
    p_tc = grouped_cv(X, y_tc, groups, log_target=True)
    tail = float(np.quantile(y_tc, 0.9))
    scores["lambda"] = metrics(y_lam, p_lam)
    scores["wlog"] = metrics(y_wlog, p_wlog)
    scores["tc_direct"] = metrics(y_tc, np.clip(p_tc, 0, None), tail=tail)
    scores["tc_via_lambda_wlog"] = metrics(y_tc, allen_dynes(np.clip(p_lam, 0, None), np.clip(p_wlog, 0, None)), tail=tail)
    for k, v in scores.items():
        log(f"{k}: " + ", ".join(f"{m}={x:.4g}" for m, x in v.items() if isinstance(x, float)))

    out = {
        "run_at": now_iso(),
        "commit": os.environ.get("GITHUB_SHA", "local")[:7],
        "model": "HistGradientBoostingRegressor",
        "features": list(X.columns),
        "cv": f"{N_FOLDS}-fold GroupKFold by chemical system",
        "mu_star": MU_STAR,
        "n_train": int(len(train)),
        "scores": scores,
    }
    (RESULTS / "baseline_eph.json").write_text(json.dumps(out, indent=2) + "\n")
    pd.DataFrame({"id": train["id"], "chemsys": groups, "tc": y_tc, "tc_pred": np.clip(p_tc, 0, None),
                  "lambda": y_lam, "lambda_pred": p_lam, "wlog": y_wlog, "wlog_pred": p_wlog}).round(5) \
        .to_csv(RESULTS / "baseline_eph_predictions.csv", index=False)
    update_progress(summary, scores)


def run_foundation() -> None:
    from scipy.stats import spearmanr

    RESULTS.mkdir(exist_ok=True)
    _, frames = load_clean()
    train = frames["alexandria"]
    table = element_table(sorted({e for els in train["elements"] for e in els}))
    base_X = featurize(train, table)
    M = mace_descriptors(train, "alexandria")
    X = np.hstack([base_X.to_numpy(float), M])
    log(f"features: {base_X.shape[1]} composition/structure + {M.shape[1]} MACE = {X.shape[1]}")
    groups = train["chemsys"].to_numpy()
    y_lam = train["lambda"].to_numpy()
    y_wlog = train["wlog"].to_numpy()
    y_tc = train["tc"].to_numpy()
    t0 = time.time()
    p_lam, s_lam = bagged_grouped_cv(X, y_lam, groups)
    p_wlog, s_wlog = bagged_grouped_cv(X, y_wlog, groups)
    p_tc, s_tc = bagged_grouped_cv(X, y_tc, groups, log_target=True)
    log(f"bagged CV done in {time.time() - t0:.0f}s")
    p_tc = np.clip(p_tc, 0, None)
    tail = float(np.quantile(y_tc, 0.9))
    scores = {
        "lambda": metrics(y_lam, p_lam),
        "wlog": metrics(y_wlog, p_wlog),
        "tc_direct": metrics(y_tc, p_tc, tail=tail),
        "tc_via_lambda_wlog": metrics(y_tc, allen_dynes(np.clip(p_lam, 0, None), np.clip(p_wlog, 0, None)), tail=tail),
    }
    scores["tc_direct"]["uncertainty_spearman"] = float(spearmanr(s_tc, np.abs(p_tc - y_tc)).correlation)
    for k, v in scores.items():
        log(f"{k}: " + ", ".join(f"{m}={x:.4g}" for m, x in v.items() if isinstance(x, float)))
    base_path = RESULTS / "baseline_eph.json"
    base = json.loads(base_path.read_text())["scores"] if base_path.exists() else None
    out = {
        "run_at": now_iso(),
        "commit": os.environ.get("GITHUB_SHA", "local")[:7],
        "descriptors": f"MACE-MP-0 {MACE_MODEL}, invariant node features, mean/std/max over atoms",
        "head": f"HistGradientBoostingRegressor, {N_BAGS}-model bootstrap ensemble per fold",
        "cv": f"{N_FOLDS}-fold GroupKFold by chemical system",
        "mu_star": MU_STAR,
        "n_train": int(len(train)),
        "n_features": int(X.shape[1]),
        "scores": scores,
    }
    (RESULTS / "foundation_eph.json").write_text(json.dumps(out, indent=2) + "\n")
    pd.DataFrame({"id": train["id"], "chemsys": groups, "tc": y_tc, "tc_pred": p_tc, "tc_std": s_tc,
                  "lambda": y_lam, "lambda_pred": p_lam, "wlog": y_wlog, "wlog_pred": p_wlog}).round(5) \
        .to_csv(RESULTS / "foundation_eph_predictions.csv", index=False)
    update_progress_foundation(scores, base)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["baseline", "foundation", "search"])
    args = ap.parse_args(argv)
    if args.command == "baseline":
        run_baseline()
    elif args.command == "foundation":
        run_foundation()
    elif args.command == "search":
        run_search()


if __name__ == "__main__":
    sys.exit(main())
