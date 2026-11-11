"""Hurricane 9.0: the release run of the design that the declared time-window test supported.

    python ml/hurricane9_release.py --protocol                 # the frozen release protocol and its SHA-256
    python ml/hurricane9_release.py --smoke [--output-dir DIR] # invented rows through every step; not a result
    python ml/pipeline.py hurricane9                           # the release run: writes results/ and progress/

The model is the "data" design of ml/hurricane9.py, unchanged: the recipe of Hurricane 4.0 without its Materials
Project structure block, trained on every usable unit of the four modelled families in the MDR SuperCon Datasheet.
It answers in two parts, the chance of the family's event and the Tc if the compound superconducts. Around it stands
the guard of Hurricane 4.0 with the same three numbers: compounds with no superconductivity record that lie inside
the training data join the classifier as weak negatives, and a compound outside the training data gets "not known"
instead of a chance.

Everything that decides the release is in PROTOCOL. The run refuses to read any data unless the hash of PROTOCOL is
written in results/validation/hurricane9-release-declaration-v1.md. The evidence for the Tc part is the declared run
of hurricane9-protocol-v1, repeated here unchanged; the guard is checked here for the first time, on background
compounds that the classifier did not learn from.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
import warnings
from functools import reduce
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane as HU  # noqa: E402
import hurricane2 as H2  # noqa: E402
import hurricane9 as F  # noqa: E402
import hurricane9_data as D  # noqa: E402

P = HU.P
VERSION = "hurricane9-release-v1"
ROUND, MODEL_VERSION, DESIGN = 9, "9.0", "data"
WEIGHT, RADIUS, ABSTAIN = 0.3, 1.0, 1.0      # the guard of Hurricane 4.0, unchanged
FALSE_ALARM_LIMIT = 0.05                     # its limit, unchanged
ALPHA, N_REPEATS = 0.10, 3
DECLARATION = P.ROOT / "results" / "validation" / "hurricane9-release-declaration-v1.md"
APP_FAMILY = {"cuprate": "cuprate", "iron-nickel": "iron-based", "heavy-fermion": "heavy-fermion", "other-oxide": "other oxide"}
KONNO = {"cite": "T. Konno et al., Phys. Rev. B 103, 014509 (2021)", "doi": "10.1103/PhysRevB.103.014509"}
RULE = ("release the design if, in this run, claim C1 of hurricane9-protocol-v1 is met (it ranks the units of new cuprate "
        "parents by Tc better than the previous recipe on the previous model's data, with the interval of the pooled "
        f"difference above zero) and its guard gives at least an even chance to at most {FALSE_ALARM_LIMIT:.0%} of the "
        "held-out compounds with no superconductivity record that Radar sends to Hurricane")
PROTOCOL = {
    "name": "hurricane9-release-protocol-v1", "release_module": VERSION, "fit_protocol": F.PROTOCOL["name"],
    "fit_protocol_sha256": F.protocol_sha256(), "round": ROUND, "version": MODEL_VERSION,
    "model": {"design": DESIGN, "blocks": F.DESIGNS[DESIGN]["blocks"], "regressor": F.REGRESSOR, "classifier": F.CLASSIFIER, "seed": F.SEED,
              "rows": "every unit of the four modelled families built from every admitted report of the datasheet, all years; units "
                      "whose oxygen content no source field instantiates and the flagged unit take no part",
              "regressor_rows": "the rows with a Tc value, target log(1 + Tc)",
              "classifier_rows": "the rows with a family event of 0 or 1, and the background compounds of the guard",
              "answer": "the chance of the family event, the Tc if the compound superconducts, and their product"},
    "guard": {"weight": WEIGHT, "radius": RADIUS, "abstain": ABSTAIN,
              "distance": "screen.novelty on the model's own inputs: the distance to the nearest training row over the distance "
                          "that 95% of the training rows keep from the nearest row of another parent cluster",
              "background": "Hurricane's screening pool built as screen.run builds it from JARVIS-DFT with the element counts of "
                            "these training rows (hurricane3.background), without the compounds whose composition the datasheet "
                            "lists; those within the radius join the classifier as event 0 at the weight",
              "cross_fit": "five folds by a hash of the chemical system (hurricane3.bg_fold): the chance of a background compound "
                           "comes from a classifier that learned from no background compound of its fold",
              "false_alarm": "a held-out background compound that Radar sends to Hurricane, lies inside the training data and gets "
                             "a chance of at least one half"},
    "evidence": "hurricane9.evaluate, the declared run repeated unchanged; its claims are recomputed and reported, C1 decides",
    "rule": RULE, "limits": {"false_alarms": FALSE_ALARM_LIMIT},
    "reported_without_a_limit": [
        "what the released behaviour (the guard included, refitted inside every window with the background compounds near that "
        "window's training rows) answers for the new-parent units of the declared windows: the shares answered, found, called "
        "unlikely and not known; the background compounds carry no date",
        f"the width of a {1 - ALPHA:.0%} range on log(1 + Tc) from the errors on the new-parent units with a Tc value of the declared "
        "family windows (split-conformal quantile)",
        f"permutation importance of the regressor on the same units ({N_REPEATS} shuffles, seed {F.SEED}), summed by input name",
        "the graded anchors of data/hurricane_anchors.json: an anchor whose composition the training rows hold is shown and not scored"],
    "adopted_when": "the rule is met; otherwise the entry is written as experimental and the version in use does not change",
}


def protocol_text() -> str:
    return json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":"))


def protocol_sha256() -> str:
    return hashlib.sha256(protocol_text().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- model
class Design9:
    """The released design: a regressor for Tc on the rows with a Tc value and a classifier for the family event, which
    also learns from background compounds as weak negatives when it is given any."""

    def __init__(self, seed: int = F.SEED):
        self.seed, self.reg, self.clf = seed, None, None

    def fit_regressor(self, X, tc):
        has = np.isfinite(tc)
        if has.sum() >= F.MIN_TRAIN:
            self.reg = HU._fit(X[has], np.log1p(tc[has]), F.REGRESSOR, self.seed)
        return self

    def fit_classifier(self, X, event, Xb=None, weight: float = WEIGHT):
        from sklearn.ensemble import HistGradientBoostingClassifier
        keep = event >= 0
        if min(int((event == 0).sum()), int((event == 1).sum())) < F.MIN_CLASS:
            return self
        Xc, label, w = X[keep], event[keep], None
        if Xb is not None and len(Xb):
            Xc, label = np.vstack([Xc, Xb]), np.concatenate([label, np.zeros(len(Xb), int)])
            w = np.concatenate([np.ones(int(keep.sum())), np.full(len(Xb), float(weight))])
        Xc = Xc.copy()
        Xc[:, ~np.isfinite(Xc).any(axis=0)] = 0.0   # as hurricane._fit: a feature with no value in this training set
        self.clf = HistGradientBoostingClassifier(random_state=self.seed, **F.CLASSIFIER).fit(Xc, label, sample_weight=w)
        return self

    def tc(self, X) -> np.ndarray:
        return np.clip(np.expm1(HU._predict(self.reg, X)), 0, None) if self.reg is not None and len(X) else np.full(len(X), np.nan)

    def chance(self, X) -> np.ndarray:
        return self.clf.predict_proba(X)[:, 1] if self.clf is not None and len(X) else np.full(len(X), np.nan)


def pseudo_rows(keys, comps) -> list:
    """Rows for compounds that are not datasheet units (background, pool, anchors): a composition and a name."""
    return [{"unit": {"exact": "compound:" + str(k), "structure_name": "none", "oxygen_status": "none", "family": "other",
                      "parents": [], "tc_k": None, "event": "censored"}, "comp": {e: float(v) for e, v in c.items() if float(v) > 0},
             "a": None, "c": None, "oz": None} for k, c in zip(keys, comps)]


def inputs(train: list, others: list, table, cache: dict):
    """The training matrix and one matrix for each list of other rows, all in the columns the training rows decide."""
    X, cols, out = None, [], []
    for rows in others or [[]]:
        X, Xq, cols = F.matrices(F.DESIGNS[DESIGN], train, rows, table, cache)
        out.append(Xq)
    return X, out, cols


def targets(rows: list):
    tc = np.array([r["unit"]["tc_k"] if r["unit"]["tc_k"] is not None else np.nan for r in rows], float)
    return tc, F.event_labels(rows), F.clusters(rows)


def ratio(X, groups, Xq) -> np.ndarray:
    """Each query row's distance to the nearest training row over the 95% cross-parent distance (screen.novelty)."""
    if not len(Xq):
        return np.zeros(0)
    import screen as SC
    with warnings.catch_warnings():   # an input with no value in the training rows is all-NaN: novelty zeroes it
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.asarray(SC.novelty(X, groups, Xq)["ratio"], float)


def share(mask, of=None):
    mask = np.asarray(mask, bool)
    of = np.ones(len(mask), bool) if of is None else np.asarray(of, bool)
    return float(mask[of].mean()) if of.any() else None


def conformal(residual, alpha: float = ALPHA) -> float:
    """The split-conformal quantile: the ceil((n + 1)(1 - alpha))-th smallest residual."""
    r = np.sort(np.asarray(residual, float))
    return float(r[min(len(r), math.ceil((len(r) + 1) * (1 - alpha))) - 1]) if len(r) else float("nan")


def final_rows(observations: list) -> list:
    units = [u for u in D.canonical_units(observations, lift=True) if F.usable(u) and u["family"] in D.EVENT_K]
    return F.unit_rows(units, observations)


# ---------------------------------------------------------------- guard
def guard(X, event, groups, Xb, fold_b, sent, seed: int = F.SEED) -> dict:
    """The guard, cross-fitted: every background compound gets its chance from a classifier that learned from no background
    compound of its fold. Returns the per-compound answers and the summary the rule reads."""
    fold_b, sent = np.asarray(fold_b, int), np.asarray(sent, bool)
    r = ratio(X, groups, Xb)
    near, unknown = r <= RADIUS, r > ABSTAIN
    p = np.full(len(Xb), np.nan)
    for k in range(P.N_FOLDS):
        held = fold_b == k
        if held.any():
            p[held] = Design9(seed + 1 + k).fit_classifier(X, event, Xb[near & ~held]).chance(Xb[held])
    bare = Design9(seed).fit_classifier(X, event).chance(Xb)          # no background compounds and no "not known"
    alarm = (p >= 0.5) & ~unknown
    summary = {"n": int(len(Xb)), "n_sent": int(sent.sum()), "n_used": int(near.sum()), "weight": WEIGHT, "radius": RADIUS, "abstain": ABSTAIN,
               "false_alarms": share(alarm, sent), "false_alarms_all": share(alarm),
               "false_alarms_inside": share(p >= 0.5, sent & ~unknown),
               "false_alarms_without_guard": share(bare >= 0.5, sent), "false_alarms_all_without_guard": share(bare >= 0.5),
               "unknown_sent": share(unknown, sent), "unknown_all": share(unknown),
               "folds": [share(alarm, sent & (fold_b == k)) for k in range(P.N_FOLDS)],
               "limit": FALSE_ALARM_LIMIT}
    summary["passed"] = bool(summary["false_alarms"] is not None and summary["false_alarms"] <= FALSE_ALARM_LIMIT)
    return {"p": p, "bare": bare, "ratio": r, "unknown": unknown, "near": near, "summary": summary}


# ---------------------------------------------------------------- the declared windows, with the guard
def window_answers(observations: list, supported: set, table, cache: dict, bg_rows: list) -> dict:
    """What the released behaviour answers for the new-parent units of the declared windows, and the importance of the
    regressor's inputs on the units with a Tc value of the family windows."""
    cells, gain, base_error, n_total = {}, {}, 0.0, 0
    rng = np.random.default_rng(F.SEED)
    for t in F.cutoffs():
        fams = [f for f, ts in F.WINDOWS.items() if t in ts]
        new = [f for f, c in F.NEW_FAMILY if c == t]
        w = F.checked_window(observations, t, supported)
        train = F.design_rows(DESIGN, w["train"])
        test = [r for r in w["test"] if r["unit"]["family"] in fams + new]
        if not train or not test:
            continue
        X, (Xt, Xb), cols = inputs(train, [test, bg_rows], table, cache)
        tc, event, groups = targets(train)
        d = Design9().fit_regressor(X, tc).fit_classifier(X, event, Xb[ratio(X, groups, Xb) <= RADIUS] if len(Xb) else None)
        p, pred, unknown = d.chance(Xt), d.tc(Xt), ratio(X, groups, Xt) > ABSTAIN
        y, ev = targets(test)[:2]
        fam = np.array([r["unit"]["family"] for r in test])
        for f in fams + new:
            m = fam == f
            likely, pos, neg = (p >= 0.5) & ~unknown, m & (ev == 1), m & (ev == 0)
            cells[f"{f}:{t}"] = {"family": f, "cutoff": t, "years": [t + 1, t + F.WIDTH], "new_family": f in new, "units": int(m.sum()),
                                 "superconductors": int(pos.sum()), "measured_negatives": int(neg.sum()),
                                 "not_known": share(unknown, m), "found": share(likely, pos), "unlikely": share(~likely & ~unknown, pos),
                                 "not_known_superconductors": share(unknown, pos), "alarms_on_negatives": share(likely, neg),
                                 "max_pred": float(np.nanmax(pred[m])) if m.any() and np.isfinite(pred[m]).any() else None,
                                 "max_tc": float(np.nanmax(y[m])) if np.isfinite(y[m]).any() else None}
        use = np.isin(fam, fams) & np.isfinite(y) & np.isfinite(pred)      # importance: the family windows only
        if d.reg is None or not use.any():
            continue
        Xu, yu = Xt[use], y[use]
        error = float(np.abs(pred[use] - yu).sum())
        base_error, n_total = base_error + error, n_total + int(use.sum())
        for j, name in enumerate(cols):
            inc = 0.0
            for _ in range(N_REPEATS):
                Xp = Xu.copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                inc += float(np.abs(d.tc(Xp) - yu).sum()) - error
            gain[name] = gain.get(name, 0.0) + inc / N_REPEATS
        print(f"window {t}: answers and importance on {int(use.sum())} units", file=sys.stderr, flush=True)
    order = sorted(gain, key=lambda n: (-gain[n], n))[:15]
    return {"cells": cells, "importance": [{"name": n, "gain": round(gain[n] / n_total, 3)} for n in order] if n_total else [],
            "importance_units": n_total, "error_k": base_error / n_total if n_total else None}


def pooled_answers(cells: dict, new_family: bool) -> dict:
    """The shares of the windows' cells pooled by units (family windows, or the two new-family windows)."""
    part = [c for c in cells.values() if c["new_family"] == new_family]
    total = lambda key, weight: (sum(c[key] * c[weight] for c in part if c[key] is not None) / sum(c[weight] for c in part if c[key] is not None)   # noqa: E731
                                 if any(c[key] is not None and c[weight] for c in part) else None)
    return {"units": sum(c["units"] for c in part), "superconductors": sum(c["superconductors"] for c in part),
            "coverage": None if total("not_known", "units") is None else 1.0 - total("not_known", "units"),
            "found": total("found", "superconductors"), "dismissed": total("unlikely", "superconductors"),
            "unknown": total("not_known_superconductors", "superconductors"),
            "alarms_on_negatives": total("alarms_on_negatives", "measured_negatives")}


# ---------------------------------------------------------------- evidence from the declared evaluation
def evidence(report: dict, saved: list) -> dict:
    """The numbers of the declared evaluation that the release shows: per family, per window and over all family windows."""
    names = ["previous", DESIGN, "names", "measured", "R1"]
    fams, folds = {}, []
    for f in F.WINDOWS:
        block = report["families"][f]
        pa, pp = block["pooled_all"], block["pooled_product"]["mae_k"]
        fams[f] = {"windows": pa["windows"], "units": pa["units"], "parents": pa["parents"],
                   "spearman": {n: pa["spearman"][n] for n in names},
                   "difference": {k: pa["difference"][k] for k in (f"{DESIGN}-previous", f"{DESIGN}-R1")},
                   "error_k": pa["mae_k"]["values"], "error_units": pa["mae_k"]["units"],
                   "released_measure_k": pp["values"], "released_measure_units": pp["units"]}
        for t in F.WINDOWS[f]:
            w = block["windows"].get(str(t))
            if w:
                folds.append({"family": f, "cutoff": t, "units_with_tc": w["units_with_tc"], "product_units": w["product"]["units"],
                              "spearman": {n: w["spearman"].get(n) for n in names}, "error_k": {n: w["mae_k"].get(n) for n in names + ["R0"]},
                              "released_measure_k": {n: w["product"]["mae_k"].get(n) for n in ("previous", DESIGN)}})
    rows = [r for r in saved if r["tc_k"] is not None and r["cutoff"] in F.WINDOWS.get(r["family"], []) and np.isfinite(r[DESIGN])]
    y, pred = np.array([r["tc_k"] for r in rows], float), np.array([r[DESIGN] for r in rows], float)
    residual = np.abs(np.log1p(y) - np.log1p(pred))
    width = conformal(residual)
    high = y >= HU.HIGH_TC

    def weighted(key, units, name):
        """The unit-weighted mean over the families that define the value, or None when none does."""
        have = [f for f in fams if fams[f][key].get(name) is not None and fams[f][units]]
        return sum(fams[f][key][name] * fams[f][units] for f in have) / sum(fams[f][units] for f in have) if have else None

    return {"families": fams, "folds": folds, "claims": report["claims"], "new_family": report["new_family"],
            "overall": {"units_with_tc": int(len(y)), "error_k": weighted("error_k", "error_units", DESIGN),
                        "error_previous_k": weighted("error_k", "error_units", "previous"),
                        "released_measure_k": weighted("released_measure_k", "released_measure_units", DESIGN),
                        "released_measure_previous_k": weighted("released_measure_k", "released_measure_units", "previous"),
                        "high_tc_error_k": float(np.abs(pred[high] - y[high]).mean()) if high.any() else None,
                        "r2_log": float(1 - np.sum((np.log1p(y) - np.log1p(pred)) ** 2) / np.sum((np.log1p(y) - np.log1p(y).mean()) ** 2)) if len(y) > 1 else None},
            "range": {"level": 1 - ALPHA, "width_log": width, "n": int(len(y)), "coverage": float(np.mean(residual <= width)) if len(y) else None,
                      "from": "the new-parent units with a Tc value of the declared family windows"}}


# ---------------------------------------------------------------- anchors and background
def anchor_table(final: Design9, X, groups, train: list, Xa, anchors: list) -> dict:
    """The graded anchors as the released model answers them; an anchor the training rows hold is shown, not scored."""
    import screen as SC
    known = SC.Known("training rows")
    for r in train:
        known.add(r["comp"], r["unit"]["exact"])
    elements = {e for r in train for e in r["comp"]}
    p, tc, rr = final.chance(Xa), final.tc(Xa), ratio(X, groups, Xa)
    table, scored = [], []
    for i, e in enumerate(anchors):
        comp = {k: float(v) for k, v in e["composition"].items()}
        row = {"name": e["name"], "tc_exp": e.get("tc_exp"), "status": e["status"], "use": e["use"], "family": e.get("family"),
               "source": e.get("source"), "note": e.get("note", "")}
        if any(el not in elements for el in comp):
            table.append(dict(row, pred=None, why="element outside the training data"))
            continue
        held = known.match(comp) is not None
        row.update(pred=round(float(p[i] * tc[i]), 2) if np.isfinite(p[i]) else round(float(tc[i]), 2), p_sc=round(float(p[i]), 3) if np.isfinite(p[i]) else None,
                   tc_sc=round(float(tc[i]), 2), ratio=round(float(rr[i]), 3), unknown=bool(rr[i] > ABSTAIN), in_training=held,
                   types=[k for k, v in H2.structure_types(comp).items() if v > 0])
        if held and row["use"] == "score":
            row["use"], row["note"] = "show", (row["note"] + " The datasheet the model learned from lists this composition, so it is not scored.").strip()
        table.append(row)
        if row["use"] == "score" and row["tc_exp"] is not None:
            scored.append(row)
    n = len(scored)
    return {"n_scored": n, "n_listed": len(table), "mae": round(float(np.mean([abs(r["pred"] - r["tc_exp"]) for r in scored])), 2) if n else None,
            "scored_as_check": n >= HU.ANCHOR_MIN_N,
            "rule": f"reported as a score only with at least {HU.ANCHOR_MIN_N} scored measurements; an anchor whose composition the "
                    "training rows hold is shown and not scored; never used for training or for choosing the design",
            "table": table}


def formula_of(comp: dict) -> str:
    counts = {e: int(round(v)) for e, v in comp.items()}
    g = reduce(math.gcd, counts.values()) if all(abs(v - round(v)) < 1e-9 for v in comp.values()) and counts else 1
    return "".join(f"{e}{'' if (counts[e] // g if g else comp[e]) == 1 else (counts[e] // g if g else comp[e])}" for e in sorted(comp))


def jarvis_background(observations: list, train: list) -> dict:
    """Hurricane's screening pool as the background (hurricane3.background with these training rows' element counts), without
    the compounds whose composition the datasheet lists, and Radar's routing of each."""
    import hurricane3 as H3
    import pandas as pd
    import screen as SC
    pool, info = H3.background(SC.load_rows(), pd.DataFrame({"comp": [r["comp"] for r in train]}))
    listed = SC.Known("datasheet")
    for o in observations:
        if o["oxygen"]["status"] != "unknown":
            listed.add(o["composition"], "datasheet")
    keep = np.array([listed.match(c) is None for c in pool["comp"]], bool)
    info["in_the_datasheet"] = int((~keep).sum())
    pool = pool[keep].reset_index(drop=True)
    p_unc, radar = SC.radar_scores(pool)
    systems = [H3.chemsys_of(c) for c in pool["comp"]]
    return {"key": [str(x) for x in pool["id"]], "comp": list(pool["comp"]), "chemsys": systems, "fold": [H3.bg_fold(s) for s in systems],
            "p_unconventional": np.asarray(p_unc, float), "sent": np.asarray(p_unc, float) >= 0.5, "info": info, "radar": radar,
            "source": "JARVIS-DFT 3D compounds of Hurricane's screening pool with no superconductivity record in the checked sources"}


def synthetic_background(train: list, n: int = 80, seed: int = F.SEED) -> dict:
    """Invented compounds for --smoke and the tests: no JARVIS, no Radar."""
    import hurricane3 as H3
    rng = np.random.default_rng(seed)
    elements = sorted({e for r in train for e in r["comp"]})
    comps = [{str(e): float(rng.integers(1, 5)) for e in rng.choice(elements, size=int(rng.integers(2, 4)), replace=False)} for _ in range(n)]
    systems = [H3.chemsys_of(c) for c in comps]
    return {"key": [f"X-{i}" for i in range(n)], "comp": comps, "chemsys": systems, "fold": [H3.bg_fold(s) for s in systems],
            "p_unconventional": rng.random(n), "sent": rng.random(n) < 0.5, "info": {"synthetic": True}, "radar": {"synthetic": True},
            "source": "invented compounds; not a result"}


# ---------------------------------------------------------------- the run
def build(observations: list, supported: set, bg: dict, anchors: list, table=None) -> tuple[dict, list, list]:
    """Every number of the release from the loaded tables. Returns the result, the prediction rows of the declared
    evaluation and one row per background compound."""
    train = final_rows(observations)
    bg_rows = pseudo_rows(bg["key"], bg["comp"])
    anchor_rows = pseudo_rows([f"anchor-{i}" for i in range(len(anchors))], [a["composition"] for a in anchors])
    if table is None:
        table = F.element_table(sorted({e for o in observations for e in o["composition"]} | {e for r in bg_rows + anchor_rows for e in r["comp"]}))
    cache = {}
    report, saved = F.evaluate(observations, supported, table)
    ev = evidence(report, saved)
    answers = window_answers(observations, supported, table, cache, bg_rows)
    X, (Xb, Xa), cols = inputs(train, [bg_rows, anchor_rows], table, cache)
    tc, event, groups = targets(train)
    g = guard(X, event, groups, Xb, bg["fold"], bg["sent"])
    final = Design9().fit_regressor(X, tc).fit_classifier(X, event, Xb[g["near"]] if len(Xb) else None)
    claims = {c["id"]: c for c in ev["claims"]}
    adopted = bool(claims["C1"]["met"] and g["summary"]["passed"])
    fam = np.array([r["unit"]["family"] for r in train])
    years = [r["unit"]["earliest_year"] for r in train if r["unit"].get("earliest_year") is not None]
    blocks = F.DESIGNS[DESIGN]["blocks"]
    n_cols = {"A": len(cache["names"]["A"]), "C": len(cache["names"]["C"]), "E": len(cache["names"]["T"]),
              "D": len(cols) - len(cache["names"]["A"]) - len(cache["names"]["C"]) - len(cache["names"]["T"])}
    data = {"kind": "datasheet", "source": "MDR SuperCon Datasheet Ver.220808 (NIMS), oxide and metallic table", "cite": D.ATTRIBUTION,
            "doi": D.MDR_DOI.replace("https://doi.org/", ""), "licence": "CC BY 4.0", "n": len(train), "n_sc": int(np.isfinite(tc).sum()),
            "n_event": int((event == 1).sum()), "n_negative": int((event == 0).sum()), "n_groups": int(groups.max() + 1) if len(groups) else 0,
            "years": [int(min(years)), int(max(years))] if years else None,
            "families": {APP_FAMILY[f]: {"label": HU.FAMILY_LABEL[APP_FAMILY[f]], "n": int((fam == f).sum()),
                                         "n_sc": int((np.isfinite(tc) & (fam == f)).sum()),
                                         "max_tc": round(float(np.nanmax(tc[fam == f])), 1) if np.isfinite(tc[fam == f]).any() else 0.0}
                         for f in F.WINDOWS}}
    out = {"round": ROUND, "model": HU.MODEL, "version": MODEL_VERSION, "release_module": VERSION, "adopted": adopted, "rule": RULE,
           "protocol": {"name": PROTOCOL["name"], "sha256": protocol_sha256(), "fit_protocol_sha256": F.protocol_sha256()},
           "best": {"id": "H90", "name": "The recipe of Hurricane 4.0 on the NIMS datasheet", "settings": "composition only; the guard of Hurricane 4.0",
                    "X": "ACDE", "blocks": blocks, "params": F.REGRESSOR, "two_part": "mean", "background": WEIGHT, "radius": RADIUS, "abstain": ABSTAIN,
                    "rows": "datasheet", "n_features": len(cols), "n_cols": n_cols},
           "data": data, "evidence": ev, "answers": {"cells": answers["cells"], "family_windows": pooled_answers(answers["cells"], False),
                                                     "new_family_windows": pooled_answers(answers["cells"], True)},
           "importance": answers["importance"], "importance_units": answers["importance_units"],
           "guard": dict(g["summary"], source=bg["source"], info=bg["info"], radar=bg["radar"], cite=KONNO["cite"], doi=KONNO["doi"]),
           "anchors": anchor_table(final, X, groups, train, Xa, anchors), "features": cols}
    background = [{"jid": k, "formula": formula_of(c), "chemsys": s, "fold": int(f), "p_unconventional": round(float(pu), 4), "sent": bool(st),
                   "ratio": round(float(r), 3), "p_sc": None if not np.isfinite(pp) else round(float(pp), 4),
                   "p_sc_without_guard": None if not np.isfinite(pb) else round(float(pb), 4), "not_known": bool(u)}
                  for k, c, s, f, pu, st, r, pp, pb, u in zip(bg["key"], bg["comp"], bg["chemsys"], bg["fold"], bg["p_unconventional"], bg["sent"],
                                                              g["ratio"], g["p"], g["bare"], g["unknown"])]
    return out, saved, background


def write_csv(path: Path, rows: list) -> str:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}) if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(out: dict, stamp: str) -> dict:
    """Round 9's entry in the "hurricane" block of progress.json: the fields earlier rounds wrote, read from the time
    windows, and a "temporal" block with what only this round has."""
    ev, g, data = out["evidence"], out["guard"], out["data"]
    r2, r3 = (lambda v: None if v is None else round(float(v), 2)), (lambda v: None if v is None else round(float(v), 3))
    folds = ev["folds"]
    better = sum(1 for w in folds if w["released_measure_k"][DESIGN] is not None and w["released_measure_k"]["previous"] is not None
                 and w["released_measure_k"][DESIGN] < w["released_measure_k"]["previous"])
    spec = H2.model_spec({"X": "ACDE", "params": out["best"]["params"], "two_part": "mean"}, out["best"]["n_cols"])
    spec["learner"]["two_part"] = ("a gradient-boosting classifier gives the chance that the compound superconducts at or above 4.2 K "
                                   "(1 K for a heavy-fermion compound); the regressor, trained on every unit with a measured Tc, gives "
                                   "its Tc; the prediction is their product")
    spec["learner"]["background"] = (f"{g['n_used']:,} JARVIS-DFT compounds with no superconductivity record join the classifier as "
                                     f"non-superconducting at weight {WEIGHT:g}; the Tc regressor never sees them")
    spec["cv"] = "time windows: trained on reports up to a year, asked about the parents first reported in the next five"
    nf, cells = ev["new_family"], out["answers"]["cells"]
    lofo = []
    for f, t in F.NEW_FAMILY:
        block, cell = nf.get(f"{f}:{t}"), cells.get(f"{f}:{t}")
        if not block or not cell:
            continue
        inside = block["inside_the_family"]
        lofo.append({"family": APP_FAMILY[f], "n": inside["units"], "n_sc": cell["superconductors"], "mae": r2(inside["mae_k"].get(DESIGN)),
                     "mae_median": r2(inside["mae_k"].get("R0")), "max_pred": r2(cell["max_pred"]), "max_tc": r2(cell["max_tc"]),
                     "found": r3(cell["found"]), "unknown": r3(cell["not_known_superconductors"]), "dismissed": r3(cell["unlikely"]),
                     "trained_up_to": t, "years": cell["years"], "spearman": r3(inside["spearman"].get(DESIGN)),
                     "auc_30k": {n: {k: r3(block["thirty_kelvin_auc"][n].get(k)) for k in ("auc", "lower95", "upper95")}
                                 for n in ("transfer", DESIGN, "R1") if n in block["thirty_kelvin_auc"]}})
    fw, nw = out["answers"]["family_windows"], out["answers"]["new_family_windows"]
    interval = lambda d: {k: r3(d.get(k)) for k in ("estimate", "lower95", "upper95")}   # noqa: E731
    return {
        "version": out["version"], "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental", "data": data,
        "summary": f"{out['best']['name']}, {out['best']['settings']}", "changes": out["changes"], "spec": spec, "rule": RULE,
        "scores": {"kind": "time-windows", "tc_mae": r2(ev["overall"]["released_measure_k"]), "reference_mae": r2(ev["overall"]["released_measure_previous_k"]),
                   "reference": "The previous recipe on the previous model's data",
                   "folds": [r2(w["released_measure_k"][DESIGN]) for w in folds], "reference_folds": [r2(w["released_measure_k"]["previous"]) for w in folds],
                   "fold_labels": [f"{APP_FAMILY[w['family']]} {w['cutoff'] + 1}-{w['cutoff'] + F.WIDTH}" for w in folds],
                   "folds_better": better, "sc_mae": r2(ev["overall"]["error_k"]), "high_tc_mae": r2(ev["overall"]["high_tc_error_k"]),
                   "high_tc": HU.HIGH_TC, "r2_log": r3(ev["overall"]["r2_log"]),
                   "by_family": {APP_FAMILY[f]: {"n": v["released_measure_units"], "mae": r2(v["released_measure_k"].get(DESIGN)),
                                                 "mae_ref": r2(v["released_measure_k"].get("previous"))} for f, v in ev["families"].items()}},
        "previous": {"version": "4.0", "stand_in": True, "tc_mae": r2(ev["overall"]["released_measure_previous_k"]),
                     "folds": [r2(w["released_measure_k"]["previous"]) for w in folds], "folds_better": better,
                     "sc_mae": r2(ev["overall"]["error_previous_k"]), "high_tc_mae": None},
        "lofo": lofo, "importance": out["importance"],
        "search": {"candidates": 4, "reference_id": "previous", "previous_id": None,
                   "leaderboard": [{"id": n, "name": label, "settings": note,
                                    "spearman": r3(ev["families"]["cuprate"]["spearman"][n]["estimate"]),
                                    "sc_mae": r2(ev["families"]["cuprate"]["error_k"].get(n)),
                                    "tc_mae": r2(ev["families"]["cuprate"]["released_measure_k"].get(n)), "passed": n == DESIGN and out["adopted"]}
                                   for n, label, note in (("previous", "The previous recipe on the previous model's data", "stands in for Hurricane 4.0"),
                                                          (DESIGN, "The same recipe on every datasheet unit", "released as Hurricane 9.0" if out["adopted"] else "not released"),
                                                          ("names", "With the datasheet's structure names", "no gain"),
                                                          ("measured", "With lattice lengths and the oxygen column", "no gain"))]},
        "reliability": {"about": "false alarms: the share of the held-out compounds with no superconductivity record that Radar sends to "
                                 "Hurricane which lie inside its training data and get at least an even chance; cross-fitted over five "
                                 "folds of chemical systems",
                        "rule": RULE, "caveat": "The background compounds have no superconductivity record, which is not a measurement of zero.",
                        "background": {"n": g["n"], "n_sent": g["n_sent"], "n_used": g["n_used"], "source": g["source"], "cite": g["cite"], "doi": g["doi"],
                                       "weight": WEIGHT, "radius": RADIUS},
                        "abstain": ABSTAIN, "false_alarms": r3(g["false_alarms"]), "false_alarms_without_guard": r3(g["false_alarms_without_guard"]),
                        "false_alarms_all": r3(g["false_alarms_all"]), "folds": [r3(x) for x in g["folds"]],
                        "unknown_sent": r3(g["unknown_sent"]), "unknown_all": r3(g["unknown_all"]), "coverage": r3(fw["coverage"]),
                        "found_new_parents": r3(fw["found"]), "dismissed_new_parents": r3(fw["dismissed"]),
                        "dismissed": r3(nw["dismissed"]), "found": r3(nw["found"]), "unknown_lofo": r3(nw["unknown"]),
                        "unknown_about": "not known: further from every training unit, in the model's standardized inputs, than 95% of the "
                                         "training units lie from the nearest unit of another parent",
                        "dismissed_about": "trained only on reports dated before a family was found (cuprates: up to 1985; iron-based: up to "
                                           "2005) and asked about that family's first five years"},
        "anchors": out["anchors"],
        "temporal": {"protocol": out["protocol"], "width": F.WIDTH, "claims": [{k: (r3(v) if isinstance(v, float) else v) for k, v in c.items()} for c in ev["claims"]],
                     "families": {APP_FAMILY[f]: {"windows": v["windows"], "units": v["units"], "parents": v["parents"],
                                                  "spearman": {n: interval(v["spearman"][n]) for n in v["spearman"]},
                                                  "difference": {k: dict(interval(d), met=d.get("met")) for k, d in v["difference"].items()},
                                                  "error_k": {n: r2(x) for n, x in v["error_k"].items()}} for f, v in ev["families"].items()},
                     "windows": [{"family": APP_FAMILY[w["family"]], "years": [w["cutoff"] + 1, w["cutoff"] + F.WIDTH], "units": w["units_with_tc"],
                                  "spearman": {n: r3(x) for n, x in w["spearman"].items()}, "error_k": {n: r2(x) for n, x in w["error_k"].items()}} for w in folds],
                     "answers": {"family_windows": {k: r3(v) if isinstance(v, float) else v for k, v in fw.items()},
                                 "new_family_windows": {k: r3(v) if isinstance(v, float) else v for k, v in nw.items()}},
                     "range": {k: (r3(v) if isinstance(v, float) else v) for k, v in ev["range"].items()}},
    }


def update_progress(out: dict, progress: Path) -> None:
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    e = entry(out, stamp)
    reg = prog.get("hurricane") or {}
    versions = sorted([v for v in reg.get("versions", []) if v.get("round") != ROUND] + [e], key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    cur = released[-1] if released else None
    block = dict(reg)
    block.update({"name": HU.MODEL, "current": cur["version"] if cur else None, "data": cur.get("data", reg.get("data", {})) if cur else {},
                  "versions": versions})
    ev, g, data = out["evidence"], out["guard"], out["data"]
    cu = ev["families"]["cuprate"]
    if out["adopted"]:
        block["about"] = ("Hurricane is the project's AI-designed Tc model for unconventional superconductors: cuprates, iron- and nickel-based "
                          "pnictides and chalcogenides, heavy-fermion compounds and other oxides. No first-principles theory gives their Tc, so "
                          "it learns from measured Tc: since Hurricane 9.0 from the NIMS SuperCon datasheet, including compounds measured not "
                          "to superconduct. An AI agent (Claude) proposes each design, and a version is released only if it passes a rule "
                          "fixed before its run.")
        note = (f"parents first reported in the five years after the training data end, {len(ev['folds'])} family windows; "
                f"{data['n']:,} datasheet units, {data['n_sc']:,} with a measured Tc, plus {g['n_used']:,} compounds with no "
                "superconductivity record for the classifier")
        prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
            {"tag": "hurricane", "model": f"{HU.MODEL} {out['version']} (AI-designed)", "target": "Tc_exp", "mae": round(ev["overall"]["released_measure_k"], 2),
             "unit": "K", "note": note},
            {"tag": "hurricane", "model": "The previous recipe on the previous model's data", "target": "Tc_exp",
             "mae": round(ev["overall"]["released_measure_previous_k"], 2), "unit": "K", "note": "Same windows"}]
        text = (f"Learns from {data['n']:,} measured units in the NIMS SuperCon datasheet (cuprates, iron-based, heavy-fermion and other oxides), "
                f"{data['n_sc']:,} with a measured Tc and {data['n_negative']:,} measured not to superconduct, and from {g['n_used']:,} compounds with "
                "no superconductivity record, counted as probably not superconducting. It reads the composition only. Asked about cuprate parent "
                "compounds first reported in the five years after its training data end, it ranks them by Tc with a rank correlation of "
                f"{cu['spearman'][DESIGN]['estimate']:.2f}, against {cu['spearman']['previous']['estimate']:.2f} for the previous recipe on the previous "
                f"data and {cu['spearman']['R1']['estimate']:.2f} for the Tc of the nearest known compound, which it does not clearly beat. It gives a "
                f"chance only to compounds near its training data and answers \"not known\" further away: of the held-out compounds with no "
                f"record, it gives {g['false_alarms']:.0%} at least an even chance. Our AI agent designed it.")
        fam = [m for m in prog.get("model_family", []) if m.get("id") != "hurricane"]
        fam.append({"id": "hurricane", "status": f"{HU.MODEL} {out['version']} in use", "active": True, "text": text})
        prog["model_family"] = fam
    prog["hurricane"] = block
    HU.ai_stage(prog)
    P.tidy(prog)
    prefix = f"{HU.MODEL}, round {ROUND} ("
    prog["log"] = [x for x in prog.get("log", []) if not str(x.get("event", "")).startswith(prefix)]   # a re-run replaces it
    P.add_log(prog, stamp, f"{HU.MODEL}, round {ROUND} (the recipe of Hurricane 4.0 on the NIMS datasheet): new cuprate parents ranked with "
                           f"{cu['spearman'][DESIGN]['estimate']:.2f} against {cu['spearman']['previous']['estimate']:.2f} for the previous data and "
                           f"{cu['spearman']['R1']['estimate']:.2f} for the nearest known compound; false alarms {g['false_alarms']:.0%}; "
                           + ("released as " + HU.MODEL + " " + out["version"] if out["adopted"] else "not released"))
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


CHANGES = [
    "Learns from the NIMS SuperCon datasheet instead of 3DSC: every unit of the four families, about six times the measurements",
    "Counts a compound as not superconducting only where a measurement reached down to 4.2 K (1 K for heavy-fermion compounds) and found nothing",
    "Reads the composition only: no datasheet row carries the Materials Project structure that Hurricane 4.0 read",
    "Keeps the physics features, the element shares and the structure types read from the stoichiometry",
    "Is checked on parent compounds first reported in the five years after its training data end, not on folds",
    "Keeps Hurricane 4.0's guard: compounds with no superconductivity record near the training data as weak negatives, and no chance outside it",
]


def run(smoke: bool = False, output_dir: Path | None = None) -> dict:
    import scipy
    import sklearn
    started, digest = time.time(), protocol_sha256()
    if smoke:
        observations, _ = D.load_observations(F.synthetic_table())
        supported = {u["canonical"] for i, u in enumerate(D.canonical_units(observations, lift=True)) if i % 2 == 0}
        bg, anchors = synthetic_background(final_rows(observations)), HU.load_anchors().get("materials", [])[:3]
        results = Path(output_dir or P.ROOT / "results" / "hurricane9-smoke")
        results.mkdir(parents=True, exist_ok=True)
        progress = results / "progress.json"
        progress.write_text(P.PROGRESS.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        declared = DECLARATION.read_text(encoding="utf-8") if DECLARATION.exists() else ""
        if digest not in declared:
            raise SystemExit(f"release protocol sha256 {digest} is not in {DECLARATION.name}; refusing to read any data")
        cache = P.CACHE / "mdr-supercon-220808"
        observations, _ = D.load_observations(D.fetch(D.DATA_FILE, cache).decode("utf-8", errors="replace"))
        supported, _ = F.supported_bins(D.fetch_dsc(cache).decode("utf-8", errors="replace"))
        bg, anchors = jarvis_background(observations, final_rows(observations)), HU.load_anchors().get("materials", [])
        results, progress = Path(output_dir) if output_dir else P.RESULTS, P.PROGRESS
        results.mkdir(parents=True, exist_ok=True)
    out, saved, background = build(observations, supported, bg, anchors)
    out.update(smoke=smoke, changes=CHANGES, run_at=P.now_iso(), commit=os.environ.get("GITHUB_SHA", "local"),
               designer="AI agent (Claude)", licence=D.LICENCE, attribution=D.ATTRIBUTION,
               libraries={"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
               files={"predictions_sha256": write_csv(results / f"hurricane_round{ROUND}_predictions.csv", saved),
                      "background_sha256": write_csv(results / f"hurricane_round{ROUND}_background.csv", background)},
               minutes=round((time.time() - started) / 60, 1))
    out = F.clean(out)
    (results / f"hurricane_round{ROUND}.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    update_progress(out, progress)
    show = {"version": out["version"], "adopted": out["adopted"], "protocol": out["protocol"], "claims": out["evidence"]["claims"],
            "guard": {k: v for k, v in out["guard"].items() if k not in ("info", "radar")}, "answers": out["answers"],
            "overall": out["evidence"]["overall"], "range": out["evidence"]["range"], "data": out["data"], "importance": out["importance"],
            "anchors": out["anchors"], "files": out["files"], "minutes": out["minutes"], "smoke": smoke}
    text = json.dumps(F.clean(show), sort_keys=True, separators=(",", ":"), allow_nan=False)
    print("=== hurricane9-release begin")
    for i in range(0, len(text), 2000):
        print(f"h9r|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== hurricane9-release end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", action="store_true", help="print the frozen release protocol and its SHA-256")
    parser.add_argument("--smoke", action="store_true", help="invented rows through every step; not a result")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.protocol:
        print(json.dumps(PROTOCOL, indent=1, sort_keys=True))
        print("protocol sha256 " + protocol_sha256())
    elif args.smoke:
        run(smoke=True, output_dir=args.output_dir)
    else:
        parser.error("choose --protocol or --smoke; the release run is python ml/pipeline.py hurricane9")


if __name__ == "__main__":
    main()
