"""Hurricane 9, first fit: the previous recipe against more data and new inputs, on parents nobody had reported yet.

    python ml/hurricane9.py --protocol                                    # the frozen protocol and its SHA-256
    python ml/hurricane9.py --smoke [--output-dir DIR]                    # invented rows through every step; not a result
    python ml/hurricane9.py --preflight [--cache DIR]                     # the real table through every step but the fit: counts only
    python ml/hurricane9.py --run --expect-protocol-sha256 HASH [--cache DIR] [--output-dir DIR]

For each cutoff year T, every design is trained on the units built from reports dated up to T and is then asked about
the units of the parents first reported in the next five years. The designs form a ladder in which each step changes
one thing: "previous" is the recipe of Hurricane 4.0 on the units its own data (3DSC) contains, "data" is the same
recipe on every datasheet unit, "names" adds the datasheet's structure names, "measured" adds the measured sample
variables (lattice lengths and oxygen content). "transfer" has no element identities and is asked only about the two
families that were new in their window. Two references need no learning: the family median and the nearest known
compound. Everything that decides a claim is in PROTOCOL, whose hash a run must be given before it reads any data.

Report-only: adopted is False, nothing here releases a model, writes progress.json or lists a candidate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane as HU  # noqa: E402
import hurricane2 as H2  # noqa: E402
import hurricane9_counts as C  # noqa: E402
import hurricane9_data as D  # noqa: E402

VERSION = "hurricane9-fit-v1"
SEED = 7
WIDTH = 5
WINDOWS = {"cuprate": [1990, 1995, 2000, 2005], "iron-nickel": [2010, 2015],
           "heavy-fermion": [1990, 2000, 2005, 2010], "other-oxide": [1995, 2000, 2010]}
NEW_FAMILY = [["cuprate", 1985], ["iron-nickel", 2005]]
FLAGGED = ["Ba2 Ca2.55 Fe0.3 S0.3 Y1 Oz"]
DESIGNS = {"previous": {"blocks": "ACDT", "rows": "supported"}, "data": {"blocks": "ACDT", "rows": "modelled"},
           "names": {"blocks": "ACDTS", "rows": "modelled"}, "measured": {"blocks": "ACDTSX", "rows": "modelled"},
           "transfer": {"blocks": "WX", "rows": "every"}}
LADDER = ["previous", "data", "names", "measured"]
REGRESSOR = dict(HU.PARAMS, early_stopping=False)
CLASSIFIER = dict(H2.CLF_PARAMS, early_stopping=False)
MIN_ELEMENT_UNITS, MIN_NAME_UNITS, MIN_TRAIN = 10, 20, 20
MIN_ROWS, MIN_CLASS, MIN_PARENTS, SERIES_UNITS, TOP_K, REPLICATES = 3, 10, 20, 5, 20, 1000
WHITELIST = ["X", "atomic_radius", "valence", "atomic_mass", "row", "group"]
MEASURED = ["a_angstrom", "c_angstrom", "c_over_a", "oxygen_measured", "has_c", "has_oxygen_measured", "oxygen_fixed", "oxygen_variable"]
PROTOCOL = {
    "name": "hurricane9-protocol-v1", "fit_module": VERSION, "data_module": D.VERSION, "counts_module": C.VERSION, "adopted": False,
    "source": {"file": D.DATA_FILE, "sha256": D.SOURCES[D.DATA_FILE]["sha256"], "doi": D.MDR_DOI, "3dsc_sha256": D.DSC["sha256"]},
    "question": "Trained only on reports dated up to T, how well does a design rank the units of the parents first reported in the "
                "next five years by their Tc?",
    "rows": {"train": "every unit built from reports with year <= T (admission, replication lift and aggregation inside the window)",
             "test": "new-parent units of the years T+1 to T+5: units with a resolved parent, when no training unit has the same identity "
                     "or claims one of their parents",
             "excluded": "units whose oxygen content no source field instantiates, and the units listed under flagged",
             "flagged": FLAGGED, "cohort_check": "the new-parent units per family must equal hurricane9_counts.window_counts"},
    "windows": {"width": WIDTH, "cutoffs_by_family": WINDOWS,
                "rule": "fixed from the count-only run 42873383799: at least ten new parents and twenty new-parent units with a Tc "
                        "value, in a window whose training side already holds the family",
                "new_family": NEW_FAMILY, "new_family_rule": "the first window of a family, read apart and never pooled with the others"},
    "designs": {"blocks": {"A": "composition statistics (hurricane.composition_row)", "C": "the 15 physics features (hurricane.physics_row)",
                           "D": f"fractions of the elements seen in at least {MIN_ELEMENT_UNITS} training units of the design",
                           "T": "the 19 structure types read from the stoichiometry (hurricane2.structure_types)",
                           "S": f"one indicator per datasheet structure name carried by at least {MIN_NAME_UNITS} training units",
                           "X": MEASURED, "W": {"mean and std of": WHITELIST, "also": ["n_elements", "tm_d", "nonint", "n_atoms_fu"]}},
                "specs": DESIGNS, "ladder": LADDER,
                "training_rows": {"supported": "units of the four modelled families whose composition bin (hurricane9_data.canonical: ratios "
                                               "to 1e-3) is that of a 3DSC_MP row Hurricane 4.0 was trained on (its five classes, a Tc value "
                                               "of at least zero, a readable formula)",
                                  "modelled": "every unit of the four modelled families", "every": "every unit, conventional ones included"},
                "previous": "the recipe of Hurricane 4.0 without its Materials Project structure block, background compounds and "
                            "abstention, which no datasheet row supports; a stand-in for that model, not the released file",
                "lattice_unit_rule": "a length stated in nm and below 2.5, or not stated in nm and below 1, is multiplied by ten; a "
                                     "result outside 2 to 100 angstrom is missing; a unit takes the median over its own reports",
                "transfer": "fitted only for the new-family windows"},
    "learner": {"regressor": REGRESSOR, "classifier": CLASSIFIER, "seed": SEED, "target": "log(1 + Tc) of the training rows with a Tc value",
                "classifier_rows": "training rows of the four modelled families with a family event of 0 or 1",
                "minimum": {"regressor_rows": MIN_TRAIN, "classifier_rows_per_class": MIN_CLASS}},
    "references": {"R0": "the median Tc of the family's units on the training side (of all its units when the family has none)",
                   "R1": "the Tc of the unit on the training side, of any family, nearest in element fractions (L1, first in unit order on ties)"},
    "endpoints": {"primary": "Spearman rank correlation between the predicted Tc and the unit's Tc over the test units with a Tc "
                             "value, per family and window, pooled over the family's windows with the number of parent clusters as weight",
                  "secondary": ["mean absolute error in kelvin on the same units, pooled over the windows in which every design is defined",
                                "the released model's own measure: mean absolute error of event score times predicted Tc over the units "
                                "with a Tc value or a measured negative (Tc taken as zero)", "the primary on the units with no earlier relative",
                                "the primary on the units with a c axis", f"AUC of the event score, at least {MIN_CLASS} units per class",
                                f"precision of the 30 K event among the {TOP_K} highest-ranked parents",
                                f"median rank correlation inside parents with at least {SERIES_UNITS} units"],
                  "undefined": f"a rank correlation needs {MIN_ROWS} units and two distinct values on each side",
                  "interval": {"method": "percentile bootstrap over parent clusters within each window", "replicates": REPLICATES,
                               "level": 0.95, "seed": SEED}},
    "claims": [
        {"id": "C0", "text": "the improved design ranks new cuprate parents better than the previous one", "contrast": ["measured", "previous"],
         "family": "cuprate", "cutoffs": WINDOWS["cuprate"], "rows": "all"},
        {"id": "C1", "text": "more data helps the previous recipe", "contrast": ["data", "previous"], "family": "cuprate",
         "cutoffs": WINDOWS["cuprate"], "rows": "all"},
        {"id": "C2", "text": "measured sample variables help where they exist", "contrast": ["measured", "names"], "family": "cuprate",
         "cutoffs": WINDOWS["cuprate"], "rows": "with_c"},
        {"id": "C3", "text": "the previous recipe on all data beats the nearest known compound", "contrast": ["data", "R1"],
         "family": "cuprate", "cutoffs": WINDOWS["cuprate"], "rows": "all"},
        {"id": "C4", "text": "a design without element identities ranks the 30 K event above chance in a family it never saw",
         "design": "transfer", "windows": NEW_FAMILY,
         "rows": "the new family's units that pass the 30 K event against the units of any family that do not, among the new-parent units of "
                 "the window; units of other families that pass it are left out"}],
    "decision": "a contrast is pooled over the windows that define both designs and is met when the pooled difference is positive, its "
                f"interval excludes zero and those windows hold at least {MIN_PARENTS} parent clusters; C4 is met per window when the AUC "
                "interval lies above 0.5; no correction for the five claims; everything else is descriptive",
}


def protocol_text() -> str:
    return json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":"))


def protocol_sha256() -> str:
    return hashlib.sha256(protocol_text().encode("utf-8")).hexdigest()


def element_table(symbols):
    """The project's element properties (pymatgen); a symbol it cannot describe gets missing values, never a crash."""
    import pandas as pd
    frames = []
    for s in symbols:
        try:
            frames.append(HU.P.element_table([s]))
        except Exception:
            frames.append(pd.DataFrame({p: [float("nan")] for p in HU.P.ELEMENT_PROPS}, index=[s]))
    return pd.concat(frames)


# ---------------------------------------------------------------- rows
def angstrom(value, unit):
    """A lattice length in angstrom under the protocol's unit rule, or None."""
    if value is None or value <= 0:
        return None
    nm = str(unit or "").strip().lower() == "nm"
    x = value * 10.0 if (nm and value < 2.5) or (not nm and value < 1.0) else value
    return x if 2.0 <= x <= 100.0 else None


def unit_rows(units: list, reports: list) -> list:
    """One row per unit: its composition and the measured variables of its own reports (the units' own lift)."""
    reports_of = defaultdict(list)
    for o in D.apply_replication_lift(reports):
        if o["status"] == "admitted":
            reports_of[D.unit_key(o)].append(o)
    rows = []
    for u in units:
        obs = reports_of[u["key"]]
        middle = lambda xs: float(np.median(xs)) if xs else None   # noqa: E731
        a = middle([x for x in (angstrom(o["lattice"]["lata"], o["lattice_unit"]) for o in obs) if x])
        c = middle([x for x in (angstrom(o["lattice"]["latc"], o["lattice_unit"]) for o in obs) if x])
        oz = middle([o["oxygen"]["measured"] for o in obs if o["oxygen"]["status"] == "measured" and o["oxygen"]["measured"] is not None])
        rows.append({"unit": u, "comp": obs[0]["composition"], "a": a, "c": c, "oz": oz})
    return rows


def usable(u: dict) -> bool:
    return u["oxygen_status"] != "unknown" and u["exact"] not in FLAGGED


def window_rows(observations: list, cutoff: int, supported: set) -> dict:
    """Training rows and new-parent test rows of one window, selected exactly as hurricane9_counts.window_counts counts."""
    dated = [o for o in observations if o["year"] is not None]
    before_reports = [o for o in dated if o["year"] <= cutoff]
    after_reports = [o for o in dated if cutoff < o["year"] <= cutoff + WIDTH]
    before = D.canonical_units(before_reports, lift=True)
    after = D.canonical_units(after_reports, lift=True)
    known_keys = {u["key"] for u in before}
    known_parents = {p for u in before for p in u["parents"]}
    element_sets = {(u["family"], tuple(u["elements"])) for u in before}
    structures = {(u["family"], u["structure_name"]) for u in before if u["structure_name"] != "none"}
    new_parent = [u for u in after if u["key"] not in known_keys and u["parents"] and not (set(u["parents"]) & known_parents)]
    train = unit_rows([u for u in before if usable(u)], before_reports)
    test = unit_rows([u for u in new_parent if usable(u)], after_reports)
    for r in train:
        r["supported"] = r["unit"]["canonical"] in supported
    for r in test:
        u = r["unit"]
        r["no_relative"] = (u["family"], tuple(u["elements"])) not in element_sets and (u["family"], u["structure_name"]) not in structures
    counted = Counter(u["family"] for u in new_parent)
    return {"cutoff": cutoff, "train": train, "test": test,
            "cohort": {"train_units": len(before), "train_rows": len(train), "train_rows_supported": sum(r["supported"] for r in train),
                       "new_parent_units": dict(counted), "test_rows": dict(Counter(r["unit"]["family"] for r in test))}}


# ---------------------------------------------------------------- features
def base_blocks(rows: list, table, cache: dict) -> dict:
    """Blocks A, C and T of each row as arrays; a composition is computed once (cache by its exact text)."""
    out = {"A": [], "C": [], "T": []}
    for r in rows:
        key = r["unit"]["exact"]
        if key not in cache:
            a, c, t = HU.composition_row(r["comp"], table), HU.physics_row(r["comp"]), H2.structure_types(r["comp"])
            if cache.setdefault("names", {"A": list(a), "C": list(c), "T": list(t)}) != {"A": list(a), "C": list(c), "T": list(t)}:
                raise SystemExit(f"feature names differ for {key!r}; refusing to build a misaligned matrix")
            cache[key] = (np.array(list(a.values()), float), np.array(list(c.values()), float), np.array(list(t.values()), float))
        for block, values in zip("ACT", cache[key]):
            out[block].append(values)
    width = {b: len(cache["names"][b]) for b in "ACT"} if "names" in cache else {b: 0 for b in "ACT"}
    return {b: np.array(v, float).reshape(len(rows), width[b]) for b, v in out.items()}


def measured_block(rows: list) -> np.ndarray:
    nan = float("nan")
    return np.array([[r["a"] if r["a"] else nan, r["c"] if r["c"] else nan, r["c"] / r["a"] if r["a"] and r["c"] else nan,
                      r["oz"] if r["oz"] is not None else nan, float(bool(r["c"])), float(r["oz"] is not None),
                      float(r["unit"]["oxygen_status"] == "fixed"), float(r["unit"]["oxygen_status"] == "variable")] for r in rows],
                    float).reshape(len(rows), len(MEASURED))


def matrices(spec: dict, train: list, test: list, table, cache: dict):
    """Training and test matrices of one design; every data-dependent choice (elements, names) is made on the training rows."""
    tr, te = base_blocks(train, table, cache), base_blocks(test, table, cache)
    names = cache.get("names", {"A": [], "C": [], "T": []})
    parts, cols = [], []
    for block in spec["blocks"]:
        if block in "ACT":
            parts.append((tr[block], te[block])); cols += names[block]
        elif block == "D":
            seen = Counter(e for r in train for e in r["comp"])
            elements = sorted(e for e, n in seen.items() if n >= MIN_ELEMENT_UNITS)
            share = lambda rows: np.array([[r["comp"].get(e, 0.0) / sum(r["comp"].values()) for e in elements] for r in rows], float).reshape(len(rows), len(elements))   # noqa: E731
            parts.append((share(train), share(test))); cols += [f"x_{e}" for e in elements]
        elif block == "S":
            label = lambda r: r["unit"]["structure_name"].strip().lower()   # noqa: E731
            seen = Counter(label(r) for r in train if label(r) != "none")
            kept = sorted(n for n, k in seen.items() if k >= MIN_NAME_UNITS)
            hot = lambda rows: np.array([[float(label(r) == n) for n in kept] for r in rows], float).reshape(len(rows), len(kept))   # noqa: E731
            parts.append((hot(train), hot(test))); cols += [f"structure:{n}" for n in kept]
        elif block == "X":
            parts.append((measured_block(train), measured_block(test))); cols += MEASURED
        elif block == "W":
            keep_a = [i for i, n in enumerate(names["A"]) if n == "n_elements" or any(n == f"{p}_{s}" for p in WHITELIST for s in ("mean", "std"))]
            keep_c = [i for i, n in enumerate(names["C"]) if n in ("tm_d", "nonint", "n_atoms_fu")]
            parts.append((np.hstack([tr["A"][:, keep_a], tr["C"][:, keep_c]]), np.hstack([te["A"][:, keep_a], te["C"][:, keep_c]])))
            cols += [names["A"][i] for i in keep_a] + [names["C"][i] for i in keep_c]
    return np.hstack([p[0] for p in parts]), np.hstack([p[1] for p in parts]), cols


def design_rows(name: str, train: list) -> list:
    """The training rows of a design: every unit, the four modelled families, or their units in the previous model's data."""
    rule = DESIGNS[name]["rows"]
    return [r for r in train if rule == "every" or (r["unit"]["family"] in D.EVENT_K and (rule == "modelled" or r["supported"]))]


def event_labels(rows: list) -> np.ndarray:
    """The family event of each row (1, 0), or -1 where the row has none or is outside the four modelled families."""
    return np.array([r["unit"]["event"] if r["unit"]["family"] in D.EVENT_K and r["unit"]["event"] in (0, 1) else -1 for r in rows], int)


def fit_predict(name: str, train: list, test: list, table, cache: dict) -> dict:
    """Fit one design on its training rows and predict the test rows: Tc if it superconducts, and the event score."""
    spec = DESIGNS[name]
    rows = design_rows(name, train)
    nothing = np.full(len(test), np.nan)
    out = {"train_rows": len(rows), "train_rows_with_tc": sum(r["unit"]["tc_k"] is not None for r in rows), "features": 0,
           "regressor": False, "classifier": False, "tc": nothing, "score": nothing}
    if not rows or not test:
        return out
    X, Xt, cols = matrices(spec, rows, test, table, cache)
    out["features"] = len(cols)
    y = np.array([r["unit"]["tc_k"] if r["unit"]["tc_k"] is not None else np.nan for r in rows], float)
    has = np.isfinite(y)
    if has.sum() >= MIN_TRAIN:
        models = HU._fit(X[has], np.log1p(y[has]), REGRESSOR, SEED)
        out["tc"], out["regressor"] = np.clip(np.expm1(HU._predict(models, Xt)), 0, None), True
    event = event_labels(rows)
    if name != "transfer" and min((event == 0).sum(), (event == 1).sum()) >= MIN_CLASS:
        from sklearn.ensemble import HistGradientBoostingClassifier
        Xc = X[event >= 0].copy()
        Xc[:, ~np.isfinite(Xc).any(axis=0)] = 0.0   # as hurricane._fit: a feature with no value in this training set
        model = HistGradientBoostingClassifier(random_state=SEED, **CLASSIFIER).fit(Xc, event[event >= 0])
        out["score"], out["classifier"] = model.predict_proba(Xt)[:, 1], True
    return out


def references(train: list, test: list) -> dict:
    """R0, the family median of the training side, and R1, the Tc of the nearest training unit in element fractions."""
    from sklearn.metrics import pairwise_distances_argmin_min
    known = [r for r in train if r["unit"]["tc_k"] is not None]
    if not known or not test:
        return {"R0": np.full(len(test), np.nan), "R1": np.full(len(test), np.nan)}
    y = np.array([r["unit"]["tc_k"] for r in known], float)
    family = np.array([r["unit"]["family"] for r in known])
    median = {f: float(np.median(y[family == f])) for f in set(family)}
    elements = sorted({e for r in known + test for e in r["comp"]})
    share = lambda rows: np.array([[r["comp"].get(e, 0.0) / sum(r["comp"].values()) for e in elements] for r in rows], float)   # noqa: E731
    nearest, _ = pairwise_distances_argmin_min(share(test), share(known), metric="manhattan")
    return {"R0": np.array([median.get(r["unit"]["family"], float(np.median(y))) for r in test], float), "R1": y[nearest]}


# ---------------------------------------------------------------- endpoints
def spearman(a, b):
    from scipy.stats import rankdata
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if len(a) < MIN_ROWS or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def auc(score, label):
    from scipy.stats import rankdata
    score, label = np.asarray(score, float), np.asarray(label)
    ok = np.isfinite(score)
    score, label = score[ok], label[ok]
    pos, neg = int((label == 1).sum()), int((label == 0).sum())
    if pos < MIN_CLASS or neg < MIN_CLASS:
        return None
    return float((rankdata(score)[label == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def clusters(rows: list) -> np.ndarray:
    """Parent clusters: units that share a parent claim, directly or through another unit, resample together."""
    uf = D.UnionFind()
    for i, r in enumerate(rows):
        uf.find(("u", i))
        for p in r["unit"]["parents"]:
            uf.union(("u", i), ("p", p))
    roots = [uf.find(("u", i)) for i in range(len(rows))]
    order = {root: k for k, root in enumerate(sorted(set(roots)))}
    return np.array([order[x] for x in roots], int)


def rank_values(sets: list, names: list) -> list:
    """The rank correlation of every predictor in every window (None where undefined)."""
    return [{n: spearman(s["pred"][n], s["y"]) for n in names} for s in sets]


def pooled(values: list, weights: list, a: str, b: str | None = None):
    """The weighted mean over windows of a predictor's rank correlation, or of the difference of two predictors over
    the windows that define both (weight: parent clusters of the window)."""
    pairs = [(v[a] if b is None else v[a] - v[b], w) for v, w in zip(values, weights) if v[a] is not None and (b is None or v[b] is not None)]
    return float(sum(x * w for x, w in pairs) / sum(w for _, w in pairs)) if pairs else None


def interval(values: list):
    values = [v for v in values if v is not None]
    if len(values) < REPLICATES // 2:
        return {"lower95": None, "upper95": None, "valid_replicates": len(values)}
    lo, hi = np.percentile(values, [2.5, 97.5])
    return {"lower95": float(lo), "upper95": float(hi), "valid_replicates": len(values)}


def pooled_report(sets: list, names: list, pairs: list, seed: int) -> dict:
    """Pooled rank correlations with parent-bootstrap intervals, and the paired differences of the given contrasts."""
    sets = [dict(s, members=[np.flatnonzero(s["cluster"] == k) for k in range(int(s["cluster"].max()) + 1)]) for s in sets if len(s["y"])]
    weights = [len(s["members"]) for s in sets]
    values = rank_values(sets, names)
    out = {"windows": [s["cutoff"] for s in sets], "units": int(sum(len(s["y"]) for s in sets)), "parents": int(sum(weights)),
           "spearman": {n: {"estimate": pooled(values, weights, n)} for n in names},
           "difference": {}}
    for a, b in pairs:
        both = [v[a] is not None and v[b] is not None for v in values]
        shared = [v for v, k in zip(values, both) if k], [w for w, k in zip(weights, both) if k]
        out["difference"][f"{a}-{b}"] = {"estimate": pooled(values, weights, a, b), "windows": [s["cutoff"] for s, k in zip(sets, both) if k],
                                         "parents": int(sum(shared[1])), a: pooled(*shared, a), b: pooled(*shared, b)}
    if not sets:
        return out
    rng = np.random.default_rng(seed)
    draws = {n: [] for n in names}
    diffs = {f"{a}-{b}": [] for a, b in pairs}
    for _ in range(REPLICATES):
        again = []
        for s in sets:
            index = np.concatenate([s["members"][k] for k in rng.integers(0, len(s["members"]), len(s["members"]))])
            again.append({"y": s["y"][index], "pred": {n: s["pred"][n][index] for n in names}})
        value = rank_values(again, names)
        for n in names:
            draws[n].append(pooled(value, weights, n))
        for a, b in pairs:
            diffs[f"{a}-{b}"].append(pooled(value, weights, a, b))
    for n in names:
        out["spearman"][n].update(interval(draws[n]))
    for k in diffs:
        out["difference"][k].update(interval(diffs[k]))
        low = out["difference"][k]["lower95"]
        out["difference"][k]["met"] = bool(low is not None and low > 0 and out["difference"][k]["parents"] >= MIN_PARENTS)
    return out


def outcome_rows(rows: list) -> tuple[list, np.ndarray]:
    """The rows with a Tc value or a measured negative, and their outcome with the negative taken as zero kelvin."""
    idx = [i for i, r in enumerate(rows) if r["unit"]["tc_k"] is not None or r["unit"]["event"] == 0]
    return idx, np.array([rows[i]["unit"]["tc_k"] if rows[i]["unit"]["tc_k"] is not None else 0.0 for i in idx], float)


def pooled_error(sets: list, names: list) -> dict:
    """Mean absolute error in kelvin of each predictor over the windows in which every one of them is defined."""
    shared = [s for s in sets if len(s["y"]) and all(np.isfinite(s["pred"][n]).all() for n in names)]
    units = int(sum(len(s["y"]) for s in shared))
    return {"windows": [s["cutoff"] for s in shared], "units": units,
            "values": {n: (float(sum(np.abs(s["pred"][n] - s["y"]).sum() for s in shared) / units) if units else None) for n in names}}


def window_metrics(rows: list, pred: dict, score: dict, family: str) -> dict:
    """Every per-window number of one family: counts, rank correlations, errors, event AUC, top parents, series."""
    with_tc = [i for i, r in enumerate(rows) if r["unit"]["tc_k"] is not None]
    y = np.array([rows[i]["unit"]["tc_k"] for i in with_tc], float)
    sub = lambda mask: [i for i, k in enumerate(with_tc) if mask(rows[k])]   # noqa: E731
    out = {"units": len(rows), "units_with_tc": len(with_tc), "parents": int(len(set(clusters(rows)))) if rows else 0,
           "units_no_relative": len(sub(lambda r: r["no_relative"])), "units_with_c": len(sub(lambda r: bool(r["c"]))),
           "spearman": {}, "mae_k": {}, "spearman_no_relative": {}, "spearman_with_c": {}}
    for n, p in pred.items():
        p = p[with_tc]
        out["spearman"][n] = spearman(p, y)
        out["mae_k"][n] = float(np.mean(np.abs(p - y))) if len(y) and np.isfinite(p).all() else None
        for key, mask in (("spearman_no_relative", lambda r: r["no_relative"]), ("spearman_with_c", lambda r: bool(r["c"]))):
            idx = sub(mask)
            out[key][n] = spearman(p[idx], y[idx]) if idx else None
    event = np.array([r["unit"]["event"] if r["unit"]["event"] in (0, 1) else -1 for r in rows])
    out["event"] = {"positives": int((event == 1).sum()), "negatives": int((event == 0).sum()),
                    "auc": {n: auc(s[event >= 0], event[event >= 0]) for n, s in score.items()}}
    idx, y0 = outcome_rows(rows)
    out["product"] = {"units": len(idx), "measured_negatives": int(sum(rows[i]["unit"]["tc_k"] is None for i in idx)), "mae_k": {}, "spearman": {}}
    for n, s in score.items():
        value = (s * pred[n])[idx]
        out["product"]["mae_k"][n] = float(np.mean(np.abs(value - y0))) if len(y0) and np.isfinite(value).all() else None
        out["product"]["spearman"][n] = spearman(value, y0)
    cluster = clusters([rows[i] for i in with_tc]) if with_tc else np.array([], int)
    high = np.array([rows[i]["unit"]["high_tc_event"] == 1 for i in with_tc], bool)
    groups = sorted(set(cluster))
    out["top_parents"] = {"k": TOP_K, "parents": len(groups), "share_of_30k_parents": float(np.mean([high[cluster == g].any() for g in groups])) if groups else None, "precision": {}}
    for n, p in pred.items():
        p = p[with_tc]
        if len(groups) >= 2 * TOP_K and np.isfinite(p).all():
            best = sorted(groups, key=lambda g: (-float(p[cluster == g].max()), g))[:TOP_K]
            out["top_parents"]["precision"][n] = float(np.mean([high[cluster == g].any() for g in best]))
        else:
            out["top_parents"]["precision"][n] = None
    series = defaultdict(list)
    for j, i in enumerate(with_tc):
        if len(rows[i]["unit"]["parents"]) == 1:
            series[rows[i]["unit"]["parents"][0]].append(j)
    series = [np.array(v) for v in series.values() if len(v) >= SERIES_UNITS]
    out["series"] = {"parents": len(series), "median_spearman": {}}
    for n, p in pred.items():
        inside = [v for v in (spearman(p[with_tc][s], y[s]) for s in series) if v is not None]
        out["series"]["median_spearman"][n] = float(np.median(inside)) if inside else None
    return out


def new_family_auc(rows: list, tc: np.ndarray, seed: int, family: str) -> dict:
    """AUC of the new family's units that pass the 30 K event against the units of any family that do not, among the
    new-parent units of the window, with a parent-bootstrap interval. Units of other families that pass the event are
    left out: they are not the family the claim is about."""
    label = np.array([r["unit"]["high_tc_event"] if r["unit"]["high_tc_event"] in (0, 1) else -1 for r in rows])
    other = (label == 1) & np.array([r["unit"]["family"] != family for r in rows], bool)
    keep = (label >= 0) & np.isfinite(tc) & ~other
    label, tc = label[keep], tc[keep]
    out = {"units": int(len(label)), "positives": int((label == 1).sum()), "negatives": int((label == 0).sum()),
           "positives_of_other_families_left_out": int(other.sum()), "auc": auc(tc, label)}
    if out["auc"] is None:
        return dict(out, lower95=None, upper95=None, above_chance=False)
    cluster = clusters([r for r, k in zip(rows, keep) if k])
    members = [np.flatnonzero(cluster == k) for k in range(int(cluster.max()) + 1)]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(REPLICATES):
        index = np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
        draws.append(auc(tc[index], label[index]))
    out.update(interval(draws))
    out["above_chance"] = bool(out["lower95"] is not None and out["lower95"] > 0.5)
    return out


# ---------------------------------------------------------------- run
def cutoffs() -> list:
    return sorted({t for ts in WINDOWS.values() for t in ts} | {t for _, t in NEW_FAMILY})


def checked_window(observations: list, cutoff: int, supported: set) -> dict:
    """The rows of one window, after the check that its new-parent units are the ones the count-only audit counted."""
    w = window_rows(observations, cutoff, supported)
    counted = C.window_counts(observations, cutoff, WIDTH)["new_parent_units"]
    if not all(w["cohort"]["new_parent_units"].get(f, 0) == counted[f]["units"] for f in C.FAMILIES):
        raise SystemExit(f"window {cutoff}: the new-parent units differ from hurricane9_counts; refusing to go on")
    return w


def designs_of(cutoff: int) -> list:
    return LADDER + (["transfer"] if any(c == cutoff for _, c in NEW_FAMILY) else [])


def preflight(observations: list, supported: set, table=None) -> dict:
    """Every step of a run except the fit, on the real table: the rows each design would be trained on and asked about,
    and the size of its matrices. Counts only: no model is fitted and no Tc value, prediction or score leaves here."""
    if table is None:
        table = element_table(sorted({e for o in observations for e in o["composition"]}))
    out = {"elements": len(table), "elements_without_any_property": sorted(str(e) for e in table.index[~np.isfinite(table.to_numpy(float)).any(axis=1)]),
           "windows": {}}
    cache = {}
    for t in cutoffs():
        w = checked_window(observations, t, supported)
        families = sorted({r["unit"]["family"] for r in w["train"] + w["test"]})
        count = lambda rows, test: {f: sum(1 for r in rows if r["unit"]["family"] == f and test(r)) for f in families}   # noqa: E731
        cell = {"years": [t + 1, t + WIDTH], "cohort": w["cohort"], "cohort_agrees_with_counts": True,
                "train_rows_with_tc": count(w["train"], lambda r: r["unit"]["tc_k"] is not None),
                "train_rows_supported": count(w["train"], lambda r: r["supported"]),
                "train_rows_supported_with_tc": count(w["train"], lambda r: r["supported"] and r["unit"]["tc_k"] is not None),
                "train_rows_with_c": count(w["train"], lambda r: bool(r["c"])),
                "train_rows_with_oxygen_measured": count(w["train"], lambda r: r["oz"] is not None),
                "test_rows_with_tc": count(w["test"], lambda r: r["unit"]["tc_k"] is not None),
                "test_rows_with_tc_and_c": count(w["test"], lambda r: r["unit"]["tc_k"] is not None and bool(r["c"])),
                "test_rows_with_tc_no_relative": count(w["test"], lambda r: r["unit"]["tc_k"] is not None and r["no_relative"]),
                "designs": {}}
        for name in designs_of(t):
            rows = design_rows(name, w["train"])
            event = event_labels(rows)
            d = {"train_rows": len(rows), "train_rows_with_tc": sum(r["unit"]["tc_k"] is not None for r in rows),
                 "event_positives": int((event == 1).sum()), "event_negatives": int((event == 0).sum()), "features": 0,
                 "features_without_value_in_training": 0, "test_rows_without_any_value": 0}
            if rows and w["test"]:
                X, Xt, cols = matrices(DESIGNS[name], rows, w["test"], table, cache)
                d.update(features=len(cols), features_without_value_in_training=int((~np.isfinite(X).any(axis=0)).sum()),
                         test_rows_without_any_value=int((~np.isfinite(Xt).any(axis=1)).sum()))
            d["regressor"] = bool(rows and w["test"] and d["train_rows_with_tc"] >= MIN_TRAIN)
            d["classifier"] = bool(rows and w["test"] and name != "transfer" and min(d["event_positives"], d["event_negatives"]) >= MIN_CLASS)
            cell["designs"][name] = d
        out["windows"][str(t)] = cell
        print(f"window {t}: {len(w['train'])} training rows, {len(w['test'])} test rows", file=sys.stderr, flush=True)
    out["compositions"] = len(cache) - (1 if "names" in cache else 0)
    return out


def evaluate(observations: list, supported: set, table=None) -> tuple[dict, list]:
    """Every window of the protocol: fit the designs, predict the test rows, compute the endpoints. Returns the report
    and one prediction row per test unit and window."""
    report = {"windows": {}, "families": {f: {"windows": {}} for f in WINDOWS}, "new_family": {}, "claims": []}
    saved, sets, products, cache = [], defaultdict(list), defaultdict(list), {}
    if table is None:
        table = element_table(sorted({e for o in observations for e in o["composition"]}))
    for t in cutoffs():
        w = checked_window(observations, t, supported)
        names = designs_of(t)
        fitted = {n: fit_predict(n, w["train"], w["test"], table, cache) for n in names}
        ref = references(w["train"], w["test"])
        pred = dict(ref, **{n: fitted[n]["tc"] for n in names})
        score = {n: fitted[n]["score"] for n in LADDER}
        report["windows"][str(t)] = {"years": [t + 1, t + WIDTH], "cohort": w["cohort"], "cohort_agrees_with_counts": True,
                                     "designs": {n: {k: v for k, v in fitted[n].items() if k not in ("tc", "score")} for n in names}}
        print(f"window {t}: {len(w['train'])} training rows, {len(w['test'])} test rows, {len(names)} designs fitted", file=sys.stderr, flush=True)
        cluster_all = clusters(w["test"])
        for i, r in enumerate(w["test"]):
            u = r["unit"]
            saved.append({"cutoff": t, "family": u["family"], "exact": u["exact"], "structure_name": u["structure_name"], "form_class": u["form_class"],
                          "parents": " | ".join(u["parents"]), "cluster": int(cluster_all[i]), "tc_k": u["tc_k"], "event": u["event"],
                          "high_tc_event": u["high_tc_event"], "no_relative": int(r["no_relative"]), "c_angstrom": r["c"], "oxygen_measured": r["oz"],
                          **{n: float(p[i]) for n, p in pred.items()}, **{f"{n}_score": float(s[i]) for n, s in score.items()}})
        for family, ts in WINDOWS.items():
            if t not in ts:
                continue
            idx = [i for i, r in enumerate(w["test"]) if r["unit"]["family"] == family]
            rows = [w["test"][i] for i in idx]
            fam_pred = {n: p[idx] for n, p in pred.items() if n != "transfer"}
            report["families"][family]["windows"][str(t)] = window_metrics(rows, fam_pred, {n: s[idx] for n, s in score.items()}, family)
            with_tc = [j for j, r in enumerate(rows) if r["unit"]["tc_k"] is not None]
            for key, mask in (("all", lambda r: True), ("no_relative", lambda r: r["no_relative"]), ("with_c", lambda r: bool(r["c"]))):
                pick = [j for j in with_tc if mask(rows[j])]
                picked = [rows[j] for j in pick]
                sets[(family, key)].append({"cutoff": t, "y": np.array([r["unit"]["tc_k"] for r in picked], float),
                                            "pred": {n: p[pick] for n, p in fam_pred.items()},
                                            "cluster": clusters(picked) if picked else np.array([], int)})
            pick, y0 = outcome_rows(rows)
            products[family].append({"cutoff": t, "y": y0, "pred": {n: (score[n][idx] * pred[n][idx])[pick] for n in LADDER}})
        for family, c in NEW_FAMILY:
            if c == t:
                idx = [i for i, r in enumerate(w["test"]) if r["unit"]["family"] == family]
                inside = window_metrics([w["test"][i] for i in idx], {n: p[idx] for n, p in pred.items()}, {n: s[idx] for n, s in score.items()}, family)
                report["new_family"][f"{family}:{t}"] = {"thirty_kelvin_auc": {n: new_family_auc(w["test"], pred[n], SEED, family) for n in ["transfer"] + LADDER + ["R1"]},
                                                         "inside_the_family": inside}
    names = ["R0", "R1"] + LADDER
    pairs = [("measured", "previous"), ("data", "previous"), ("names", "data"), ("measured", "names"), ("data", "R1"), ("measured", "R1")]
    for (family, key), group in sorted(sets.items()):
        report["families"][family][f"pooled_{key}"] = pooled_report(group, names, pairs, SEED)
        report["families"][family][f"pooled_{key}"]["mae_k"] = pooled_error(group, names)
    for family, group in sorted(products.items()):
        report["families"][family]["pooled_product"] = {"mae_k": pooled_error(group, LADDER)}
    for claim in PROTOCOL["claims"]:
        if "contrast" in claim:
            group = [s for s in sets[(claim["family"], claim["rows"])] if s["cutoff"] in claim["cutoffs"]]
            a, b = claim["contrast"]
            result = pooled_report(group, [a, b], [(a, b)], SEED)
            d = result["difference"][f"{a}-{b}"]
            report["claims"].append({"id": claim["id"], "text": claim["text"], "windows": d["windows"], "parents": d["parents"], a: d[a], b: d[b],
                                     "difference": d["estimate"], "lower95": d.get("lower95"), "upper95": d.get("upper95"),
                                     "met": bool(d.get("met", False))})
        else:
            for family, c in claim["windows"]:
                r = report["new_family"].get(f"{family}:{c}", {}).get("thirty_kelvin_auc", {}).get(claim["design"], {})
                report["claims"].append({"id": f"{claim['id']}:{family}:{c}", "text": claim["text"], "units": r.get("units"),
                                         "positives": r.get("positives"), "negatives": r.get("negatives"),
                                         "positives_of_other_families_left_out": r.get("positives_of_other_families_left_out"), "auc": r.get("auc"),
                                         "lower95": r.get("lower95"), "upper95": r.get("upper95"), "met": bool(r.get("above_chance", False))})
    return report, saved


def clean(node):
    """The report without a non-finite number: JSON has no NaN, and an undefined value is None here."""
    if isinstance(node, dict):
        return {str(k): clean(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [clean(v) for v in node]
    if isinstance(node, (float, np.floating)):
        return float(node) if np.isfinite(node) else None
    if isinstance(node, (np.integer, np.bool_)):
        return node.item()
    return node


def supported_bins(csv_text: str) -> tuple[set, dict]:
    """The composition bins of the 3DSC_MP rows Hurricane 4.0 was trained on (hurricane.build_frame: its five classes,
    a Tc value of at least zero, a readable formula), and the counts behind them. A unit in one of these bins is in
    the previous model's data."""
    text = csv_text.split("\n", 1)[1] if csv_text.startswith("#") else csv_text
    bins, formulas, counts = set(), set(), Counter()
    for row in csv.DictReader(io.StringIO(text)):
        counts["rows"] += 1
        if str(row.get("sc_class", "")) not in HU.FAMILY_OF_CLASS:
            continue
        counts["rows_in_the_five_classes"] += 1
        try:
            tc = float(row.get("tc", ""))
            comp = D.parse_formula(str(row.get("formula_sc", "")).strip())
        except ValueError:
            counts["rows_unreadable"] += 1
            continue
        if not np.isfinite(tc) or tc < 0:
            counts["rows_without_tc"] += 1
            continue
        formulas.add(str(row.get("formula_sc", "")).strip())
        bins.add(D.canonical(comp, "fixed" if "O" in comp else "none"))
    return bins, dict(counts, formulas=len(formulas), bins=len(bins))


def synthetic_table(seed: int = 7) -> str:
    """Invented rows in the datasheet's layout, spread over the years, for --smoke and the tests (no real row)."""
    rng = np.random.default_rng(seed)
    symbols = list(D.REQUIRED_FIELDS)
    rows = []

    def add(year, tc, name, structure, pairs, oxygen="", **extra):
        r = dict({s: "" for s in symbols}, num=str(len(rows) + 1), refno=f"S{len(rows) + 1:05d}", name=name, str3=structure, shape="1", utc="K", year=str(year))
        for (element, amount), (k1, k2) in zip(pairs, D.ELEMENT_PAIRS):
            r[k1], r[k2] = element, amount
        if oxygen:
            r["mo1"], r["mo2"] = "O", oxygen
        r.update({"tc": f"{tc + rng.normal(0, 0.3):.2f}"} if tc > 2 else {"tcn": "1.8"})
        r.update(extra)
        rows.append(r)

    for i, re in enumerate(["La", "Nd", "Pr", "Sm", "Eu", "Gd"]):
        for k, x in enumerate([0.05, 0.10, 0.15, 0.20, 0.25, 0.30]):
            add(1987 + 2 * i + k % 3, 38 * (1 - 80 * (x - 0.16) ** 2) * (0.6 + 0.08 * i), f"({re},Sr)2CuO4", "T",
                [(re, f"{2 - x:.2f}"), ("Sr", f"{x:.2f}"), ("Cu", "1")], "4", lata="3.78", latc=f"{13.1 + x:.2f}")
    for i, re in enumerate(["Y", "Er", "Dy", "Ho", "Gd", "Nd", "Sm", "Eu"]):
        for k, oz in enumerate([6.4, 6.5, 6.6, 6.7, 6.8, 6.9]):
            add(1987 + i + k % 2, 150 * (oz - 6.3) * (0.9 + 0.01 * i), f"{re}Ba2Cu3O7-x", "Y123", [(re, "1"), ("Ba", "2"), ("Cu", "3")], "7-X",
                oz=f"{oz}", lata="3.83", latc=f"{11.85 - 0.3 * (oz - 6.4):.3f}", ulat="A")
    for i, re in enumerate(["La", "Ce", "Pr", "Nd", "Sm", "Gd"]):
        for k, x in enumerate([0.05, 0.08, 0.11, 0.14, 0.17]):
            add(2008 + i // 2 + k % 2, (26 + 5 * i) * (1 - 60 * (x - 0.12) ** 2), f"{re}FeAsO1-xFx", "ZrCuSiAs",
                [(re, "1"), ("Fe", "1"), ("As", "1"), ("F", f"{x:.2f}")], f"{1 - x:.2f}", lata="4.03", latc=f"{8.74 - 0.02 * i:.2f}")
    for i, ae in enumerate(["Ba", "Sr", "Ca"]):
        for k, x in enumerate([0.04, 0.08, 0.12, 0.16, 0.20, 0.28]):
            add(2009 + i + k % 2, 22 * (1 - 40 * (x - 0.12) ** 2), f"{ae}(Fe,Co)2As2", "ThCr2Si2", [(ae, "1"), ("Fe", f"{2 - x:.2f}"), ("Co", f"{x:.2f}"), ("As", "2")])
    for year, tc, f, m, x, structure in [(1979, 0, "Ce", "Cu", "Si", "CeCu2Si2"), (1986, 0, "Ce", "Ru", "Si", "CeCu2Si2"), (1988, 0, "Ce", "Rh", "Si", "CeCu2Si2"),
                                         (1992, 0, "Ce", "Pd", "Si", "CeCu2Si2"), (1996, 0, "Ce", "Ni", "Ge", "CeCu2Si2"), (2003, 0, "Yb", "Rh", "Si", "CeCu2Si2")]:
        add(year, tc, f"{f}{m}2{x}2", structure, [(f, "1"), (m, "2"), (x, "2")])
    for year, tc, m in [(2001, 2.3, "Co"), (2002, 0, "Rh"), (2003, 0, "Ir")]:
        add(year, tc, f"Ce{m}In5", "HoCoGa5", [("Ce", "1"), (m, "1"), ("In", "5")])
    for k, x in enumerate([0.30, 0.35, 0.40, 0.45, 0.50]):
        add(1988 + k % 3, 30 - 60 * abs(x - 0.38), "(Ba,K)BiO3", "perovskite", [("Ba", f"{1 - x:.2f}"), ("K", f"{x:.2f}"), ("Bi", "1")], "3")
    for year, tc, a, x in [(1954, 18.0, "Nb", "Sn"), (1973, 23.0, "Nb", "Ge"), (1958, 18.8, "Nb", "Al"), (1961, 20.0, "Nb", "Ga"), (1953, 17.0, "V", "Si"),
                           (1956, 16.5, "V", "Ga"), (1965, 6.0, "V", "Ge"), (1960, 11.0, "Mo", "Ir"), (1962, 15.0, "Mo", "Os"), (1970, 4.5, "Ti", "Sb"),
                           (1971, 3.4, "V", "Sn"), (1974, 14.0, "Nb", "Au"), (1975, 9.0, "Nb", "Pt"), (1976, 5.0, "Ta", "Sn"), (1977, 8.0, "Cr", "Ir")]:
        for k, y in enumerate([0.95, 1.00, 1.05]):
            add(year + k, tc * (1 - 2 * abs(y - 1)), f"{a}3{x}", "A15", [(a, "3"), (x, f"{y:.2f}")])
    numbers = "\t".join(str(i + 1) for i in range(len(symbols)))
    longs = "\t".join(D.REQUIRED_FIELDS[s] for s in symbols)
    return f"{numbers}\n{longs}\n" + "\t".join(symbols) + "\n" + "\n".join("\t".join(r[s] for s in symbols) for r in rows) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", action="store_true", help="print the frozen protocol and its SHA-256")
    parser.add_argument("--smoke", action="store_true", help="invented rows through every step; not a result")
    parser.add_argument("--preflight", action="store_true", help="the real table through every step but the fit; counts only")
    parser.add_argument("--run", action="store_true", help="the real run; needs --expect-protocol-sha256")
    parser.add_argument("--expect-protocol-sha256", default="")
    parser.add_argument("--cache", type=Path, default=HU.P.CACHE / "mdr-supercon-220808")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    digest = protocol_sha256()
    if args.protocol:
        print(json.dumps(PROTOCOL, indent=1, sort_keys=True))
        print("protocol sha256 " + digest)
        return
    started = time.time()
    if args.smoke:
        observations, unreadable = D.load_observations(synthetic_table())
        supported = {u["canonical"] for i, u in enumerate(D.canonical_units(observations, lift=True)) if i % 2 == 0}
        head = {"smoke": True, "synthetic": "invented rows; not a result", "previous_model_rows": {"bins": len(supported)}}
    elif args.run or args.preflight:
        if args.run and args.expect_protocol_sha256 != digest:
            raise SystemExit(f"protocol sha256 is {digest}, not the declared {args.expect_protocol_sha256 or '(none)'}; refusing to read any data")
        observations, unreadable = D.load_observations(D.fetch(D.DATA_FILE, args.cache).decode("utf-8", errors="replace"))
        supported, counts = supported_bins(D.fetch_dsc(args.cache).decode("utf-8", errors="replace"))
        head = {"smoke": False, "licence": D.LICENCE, "attribution": D.ATTRIBUTION, "previous_model_rows": counts}
    else:
        parser.error("choose --protocol, --smoke, --preflight or --run")
    import scipy
    import sklearn
    tag = "preflight" if args.preflight else "fit"
    head = dict(head, version=VERSION, adopted=False, protocol={"name": PROTOCOL["name"], "sha256": digest},
                commit=os.environ.get("GITHUB_SHA", "local"), module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                libraries={"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
                observations=len(observations), unreadable=len(unreadable))
    if args.preflight:
        out, saved = dict(head, preflight="counts only: nothing fitted, no Tc value, prediction or score", **preflight(observations, supported)), []
    else:
        report, saved = evaluate(observations, supported)
        out = dict(head, **report)
    out["seconds"] = int(round(time.time() - started))
    text = json.dumps(clean(out), sort_keys=True, separators=(",", ":"), allow_nan=False)
    if args.output_dir and args.preflight:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "hurricane9-preflight.json").write_text(text + "\n", encoding="utf-8")
    elif args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "hurricane9-report.json").write_text(text + "\n", encoding="utf-8")
        with open(args.output_dir / "hurricane9-predictions.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=sorted({k for r in saved for k in r}))
            writer.writeheader()
            writer.writerows(saved)
        print("predictions sha256 " + hashlib.sha256((args.output_dir / "hurricane9-predictions.csv").read_bytes()).hexdigest() + " rows " + str(len(saved)))
    print(f"=== hurricane9-{tag} begin")
    for i in range(0, len(text), C.PIECE):
        print(f"h9{tag[0]}|{i // C.PIECE:03d}|{text[i:i + C.PIECE]}")
    print(f"=== hurricane9-{tag} end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))


if __name__ == "__main__":
    main()
