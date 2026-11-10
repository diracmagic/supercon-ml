"""Hurricane 9, first fit: an independent recomputation of the declared claims from the saved predictions.

    python ml/hurricane9_audit.py --dir fit

Reads hurricane9-predictions.csv and hurricane9-report.json from the given folder and recomputes the pooled rank
correlations and errors of the cuprate windows, the four contrasts and the two new-family AUCs with pandas, scipy and
scikit-learn only: no function of ml/hurricane9.py is used, and the parent clusters are rebuilt from the saved parent
names. It stops with an error if a number differs from the report by more than 1e-9. It also draws its own parent
bootstrap, with another generator and seed, to show that the intervals of the report do not hang on one random
stream. Statistics on saved predictions only: nothing is fitted and no claim, rule or number of the run is changed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

VERSION = "hurricane9-audit-v1"
CUTOFFS = [1990, 1995, 2000, 2005]
PREDICTORS = ["previous", "data", "names", "measured", "R1"]
CONTRASTS = {"C0": ("measured", "previous", False), "C1": ("data", "previous", False), "C2": ("measured", "names", True), "C3": ("data", "R1", False)}
NEW_FAMILY = {"C4:cuprate:1985": ("cuprate", 1985), "C4:iron-nickel:2005": ("iron-nickel", 2005)}
TOLERANCE = 1e-9
REPLICATES, SEED = 500, 20261110
MIN_ROWS, MIN_CLASS = 3, 10          # the protocol's own limits for a defined rank correlation and a defined AUC


def parent_clusters(parents) -> np.ndarray:
    """Connected components of the rows over the parent names they share (a row with no parent stands alone)."""
    names, rows, cols = {}, [], []
    for i, text in enumerate(parents):
        for name in [x for x in str(text).split(" | ") if x and x != "nan"]:
            rows.append(i)
            cols.append(names.setdefault(name, len(names)))
    n = len(parents)
    graph = coo_matrix((np.ones(len(rows)), (rows, [n + c for c in cols])), shape=(n + len(names), n + len(names)))
    return connected_components(graph, directed=False)[1][:n]


def rho(frame: pd.DataFrame, column: str) -> float:
    """Spearman rank correlation of a predictor with Tc, nan where the protocol calls it undefined."""
    x, y = frame[column].to_numpy(float), frame["tc_k"].to_numpy(float)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    if len(x) < MIN_ROWS or len(set(x)) < 2 or len(set(y)) < 2:
        return float("nan")
    return float(spearmanr(x, y).statistic)


def windows(frame: pd.DataFrame) -> list:
    """The rows of each cutoff with their parent clusters, in cutoff order."""
    return [part.assign(group=parent_clusters(part["parents"].tolist())) for _, part in sorted(frame.groupby("cutoff"), key=lambda kv: kv[0])]


def pooled(parts: list, weights: list, a: str, b: str | None = None):
    """Weighted mean over the windows that define the value (weight: parent clusters), with the clusters of those windows."""
    values = np.array([rho(p, a) - (rho(p, b) if b else 0.0) for p in parts], float)
    keep = np.isfinite(values)
    if not keep.any():
        return None, 0
    w = np.array(weights, float)[keep]
    return float(np.sum(values[keep] * w) / np.sum(w)), int(np.sum(w))


def bootstrap(parts: list, weights: list, a: str, b: str, rng) -> tuple[float, float]:
    """Percentile interval of the pooled difference when parent clusters are redrawn inside each window."""
    members = [[part.index[part["group"] == g].to_numpy() for g in sorted(part["group"].unique())] for part in parts]
    draws = []
    for _ in range(REPLICATES):
        again = [part.loc[np.concatenate([m[k] for k in rng.integers(0, len(m), len(m))])] for part, m in zip(parts, members)]
        draws.append(pooled(again, weights, a, b)[0])
    draws = [d for d in draws if d is not None]
    if len(draws) < REPLICATES // 2:
        return None, None
    low, high = np.percentile(draws, [2.5, 97.5])
    return float(low), float(high)


def audit(folder: Path) -> list:
    report = json.loads((folder / "hurricane9-report.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(folder / "hurricane9-predictions.csv", float_precision="round_trip")
    claims = {c["id"]: c for c in report["claims"]}
    rng = np.random.default_rng(SEED)
    checks = []       # (what, recomputed, reported)
    cuprate = frame[(frame["family"] == "cuprate") & frame["tc_k"].notna() & frame["cutoff"].isin(CUTOFFS)].reset_index(drop=True)
    parts = windows(cuprate)
    weights = [p["group"].nunique() for p in parts]
    table = report["families"]["cuprate"]["pooled_all"]
    checks.append(("cuprate units", len(cuprate), table["units"]))
    checks.append(("cuprate parent clusters", int(sum(weights)), table["parents"]))
    everyone = ["R0", "R1", "previous", "data", "names", "measured"]
    shared = [p for p in parts if np.isfinite(p[everyone].to_numpy(float)).all()]      # the windows in which every predictor is defined
    for n in PREDICTORS:
        checks.append((f"pooled Spearman {n}", pooled(parts, weights, n)[0], table["spearman"][n]["estimate"]))
        error = float(np.mean(np.concatenate([(p[n] - p["tc_k"]).abs().to_numpy(float) for p in shared]))) if shared else None
        checks.append((f"pooled error {n} (K)", error, table["mae_k"]["values"][n]))
    intervals = {}
    for claim, (a, b, with_c) in CONTRASTS.items():
        rows = cuprate[cuprate["c_angstrom"].notna()].reset_index(drop=True) if with_c else cuprate
        sub = windows(rows)
        w = [p["group"].nunique() for p in sub]
        difference, clusters = pooled(sub, w, a, b)
        both = [p for p in sub if np.isfinite(rho(p, a)) and np.isfinite(rho(p, b))]       # the windows that define both designs
        both_w = [p["group"].nunique() for p in both]
        checks.append((f"{claim} parent clusters", clusters, claims[claim]["parents"]))
        checks.append((f"{claim} {a}", pooled(both, both_w, a)[0], claims[claim][a]))
        checks.append((f"{claim} {b}", pooled(both, both_w, b)[0], claims[claim][b]))
        checks.append((f"{claim} difference", difference, claims[claim]["difference"]))
        intervals[claim] = (bootstrap(sub, w, a, b, rng), (claims[claim]["lower95"], claims[claim]["upper95"]), claims[claim]["met"])
    for claim, (family, cutoff) in NEW_FAMILY.items():
        rows = frame[(frame["cutoff"] == cutoff) & frame["high_tc_event"].isin([0, 1]) & frame["transfer"].notna()]
        rows = rows[~((rows["high_tc_event"] == 1) & (rows["family"] != family))]
        positives, negatives = int((rows["high_tc_event"] == 1).sum()), int((rows["high_tc_event"] == 0).sum())
        checks.append((f"{claim} units", len(rows), claims[claim]["units"]))
        checks.append((f"{claim} positives", positives, claims[claim]["positives"]))
        value = float(roc_auc_score(rows["high_tc_event"].astype(int), rows["transfer"])) if min(positives, negatives) >= MIN_CLASS else None
        checks.append((f"{claim} AUC", value, claims[claim]["auc"]))
    show = lambda v: f"{'undefined':>14s}" if v is None else f"{v:14.9f}" if isinstance(v, float) else f"{v:14d}"   # noqa: E731
    worst, failed = 0.0, []
    print(f"{'quantity':38s} {'recomputed':>14s} {'report':>14s}")
    for what, mine, theirs in checks:
        print(f"{what:38s} {show(mine)} {show(theirs)}")
        if mine is None and theirs is None:
            continue
        if mine is None or theirs is None or not abs(mine - theirs) <= TOLERANCE:
            failed.append(what)
        else:
            worst = max(worst, abs(mine - theirs))
    print(f"largest difference {worst:.3e}; tolerance {TOLERANCE:.0e}")
    for claim, (mine, theirs, met) in intervals.items():
        print(f"{claim}: interval of the report {theirs}, met {met}; this bootstrap ({REPLICATES} draws, seed {SEED}) {mine}")
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", type=Path, required=True, help="folder with hurricane9-predictions.csv and hurricane9-report.json")
    args = parser.parse_args(argv)
    print(f"=== {VERSION}")
    failed = audit(args.dir)
    if failed:
        raise SystemExit("audit: these numbers do not agree with the report: " + "; ".join(failed))
    print("=== audit: every recomputed number agrees with the report")


if __name__ == "__main__":
    main()
