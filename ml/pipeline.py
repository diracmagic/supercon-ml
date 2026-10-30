"""supercon-ml pipeline: electron-phonon data, baseline models and progress updates.

Usage (from the repository root):
    python ml/pipeline.py baseline

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
    prog.setdefault("history", []).append({
        "at": stamp, "model": "Gradient-boosting baseline", "target": "Tc", "split": "val",
        "mae": round(tc["mae"], 3)})
    prog["log"] += [
        {"at": stamp, "event": (f"Downloaded {alex['raw']:,} Alexandria and {jar['raw']:,} JARVIS electron-phonon "
                                f"entries; kept {alex['non_magnetic']:,} for training")},
        {"at": stamp, "event": (f"Gradient-boosting baseline: Tc MAE {tc['mae']:.2f} K, lambda MAE "
                                f"{scores['lambda']['mae']:.3f}, omega_log MAE {scores['wlog']['mae']:.1f} K "
                                f"({N_FOLDS}-fold composition-grouped CV)")},
    ]
    done = sum(1 for s in prog["stages"] if s["status"] == "done")
    prog["badge"] = f"{done}/{len(prog['stages'])} done · now: baselines"
    prog["updated"] = stamp
    PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"progress updated: {prog['badge']}")


# ---------------------------------------------------------------- commands


def run_baseline() -> None:
    RESULTS.mkdir(exist_ok=True)
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


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["baseline"])
    args = ap.parse_args(argv)
    if args.command == "baseline":
        run_baseline()


if __name__ == "__main__":
    sys.exit(main())
