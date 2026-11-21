"""Hurricane round 10: the guard of Hurricane 9.0 learns from a wide, correctly selected background.

    python ml/hurricane10.py --protocol                 # the frozen protocol and its SHA-256
    python ml/hurricane10.py --smoke [--output-dir DIR] # invented rows through every step; not a result
    python ml/pipeline.py hurricane10                   # the run: results/hurricane_round10.json and a table

Why. Screening round 7 (run on a branch, not published) put Hurricane 9.0 to 118,750 compounds with no
superconductivity record from four open sources. It gave at least an even chance to 21% of the compounds it judged, and
all 100 compounds it would have listed were copper oxides: substituted variants of known cuprate superconductors, and
copper oxysalts and other copper oxides that are not layered cuprates. Hurricane reads the composition only, and the
compounds it learns from as weak negatives were the 158 of 3,881 JARVIS-DFT compounds that lie near its training rows,
and those 3,881 were selected with JARVIS-DFT's ehull field, which does not follow the convex hull.

What changes: the background of the classifier, and nothing else. The training rows, the inputs, the regressor (the Tc
if a compound superconducts), the classifier's settings and seeds and the guard's three numbers (weight, radius,
abstention) are those of ml/hurricane9_release.py. The background becomes the pool of screening round 7, assembled by
ml/hurricane9_screen7.py from JARVIS-DFT (its hull computed from the file's formation energies), the Materials Project,
Alexandria and the Crystallography Open Database, without every compound whose parent compound by the datasheet's
coefficient rule is the parent of a datasheet entry: such a compound is a variant of a compound that has been measured,
and it may well superconduct.

The test is fixed in PROTOCOL before the run, and both designs are computed in the run on the same compounds:
    A. Of the compounds of the new background that Radar sends to Hurricane and that lie inside the training data, the
       share given at least an even chance, each by a classifier that learned from no background compound of its fold,
       is at most half the share that Hurricane 9.0 gives the same compounds.
    B. In the declared time windows of hurricane9-protocol-v1 (the family windows, pooled), the share of the new-parent
       superconductors given at least an even chance inside the training data is at least Hurricane 9.0's share minus
       0.05.
The design is adopted as Hurricane 10.0 when A and B hold; otherwise it is reported and Hurricane 9.0 stays. The run
writes results only: a release and a candidate list are later steps.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane9_screen7 as S7  # noqa: E402

S6, R = S7.S6, S7.R
F, D, HU, P = R.F, R.D, R.HU, R.P
VERSION = "hurricane10-v1"
ROUND, MODEL_VERSION = 10, "10.0"
FACTOR, MARGIN = 0.5, 0.05      # test A: at most half of 9.0's share; test B: found at least 9.0's minus 0.05
TOP = 25                        # compounds shown per track, one per chemical system; not a list
DECLARATION = P.ROOT / "results" / "validation" / "hurricane10-declaration-v1.md"
RELEASED = "hurricane_round9.json"
RESULT, TABLE = f"hurricane_round{ROUND}.json", f"hurricane_round{ROUND}_pool.csv.gz"
TEST_A = (f"of the compounds of the new background that Radar sends to Hurricane and that lie inside the training data, the share "
          f"given a chance of at least one half, each by the classifier of its fold, is at most {FACTOR:g} times the share that "
          f"Hurricane {R.MODEL_VERSION} gives the same compounds")
TEST_B = (f"in the family windows of {F.PROTOCOL['name']}, pooled by units, the share of new-parent superconductors given a chance of at "
          f"least one half inside the training data is at least Hurricane {R.MODEL_VERSION}'s share minus {MARGIN:g}")
PROTOCOL = {
    "name": "hurricane10-protocol-v1", "module": VERSION, "round": ROUND, "version": MODEL_VERSION,
    "previous": {"version": R.MODEL_VERSION, "release_protocol": R.PROTOCOL["name"], "release_protocol_sha256": R.protocol_sha256(),
                 "fit_protocol": F.PROTOCOL["name"], "fit_protocol_sha256": F.protocol_sha256()},
    "unchanged": "the training rows (hurricane9_release.final_rows), the inputs, the regressor and its target, the classifier's "
                 "settings and seeds (Design9), and the guard's weight, radius and abstention (hurricane9_release.guard and "
                 "window_answers), so every Tc and every distance to the training data is Hurricane 9.0's",
    "background": {
        "pool": f"the pool of screening round 7 as ml/hurricane9_screen7.py assembles it ({S7.PROTOCOL['name']}, sha256 "
                f"{S7.protocol_sha256()}): its sources, files, tracks, rules and exclusions, the COD rows of results/{S7.COD_SNAPSHOT}, "
                "and Radar's routing (radar_route, with its check against the release)",
        "without": "every compound whose parent by hurricane9_data.parent_from_coefficients (its default arguments) is a parent of "
                   "the datasheet: a resolved parent claim of any observation, or the coefficient-route parent of any "
                   "observation's composition, whatever the observation's status; such a compound is neither background nor scored",
        "folds": "hurricane3.bg_fold of the chemical system, as the guard of Hurricane 9.0",
        "sent": "Radar's probability of an unconventional family is at least one half",
        "replaces": "the 3,881 JARVIS-DFT compounds of hurricane9_release.jarvis_background"},
    "previous_chances": "for every compound of the pool that Radar sends: the classifier of the compound's fold in the guard of "
                        "Hurricane 9.0 (hurricane9_screen7.score, which stops unless it gives the guard's chances for the released "
                        "background), and the released background table must be reproduced (hurricane9_screen.compare_with_release)",
    "tests": {"A": TEST_A, "B": TEST_B, "factor": FACTOR, "margin": MARGIN,
              "inside": "the distance ratio to the training rows is at most the guard's abstention (the same for both designs)"},
    "adopted_when": "A and B hold; otherwise the round is reported and the version in use does not change",
    "reported_without_a_limit": [
        "the family windows' share of new parents measured not to superconduct that get at least an even chance, and the "
        "new-family windows, for both designs, recomputed in this run with the same code",
        "both guards' summaries, and the share of each design's alarms by Hurricane's family rule (hurricane9_data.family)",
        f"the {TOP} compounds of each track that the new design ranks highest by the chance times the Tc, one per chemical system, "
        "with Hurricane 9.0's chance beside each; this is not a list",
        "the compounds left out as variants of datasheet parents: counts by track and source, and those Hurricane 9.0 would have "
        "given at least an even chance"],
    "written": [f"results/{RESULT}", f"results/{TABLE}"],
    "not_written": "progress/progress.json and the app: a release and a screening round are later steps",
}


def protocol_text() -> str:
    return json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":"))


def protocol_sha256() -> str:
    return hashlib.sha256(protocol_text().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- variants of datasheet compounds
def parent_key(comp: dict) -> str | None:
    """The parent compound of a composition by the datasheet's coefficient rule, or None when the rule cannot resolve one."""
    p, _ = D.parent_from_coefficients({str(e): float(v) for e, v in comp.items() if float(v) > 0})
    return None if p.startswith("unresolved") else p


def datasheet_parents(observations: list) -> set:
    """Every parent the datasheet speaks for: the resolved parent claim of each observation and the coefficient-route parent
    of each observation's composition (a common formula and the coefficients can name the same host differently)."""
    out = set()
    for o in observations:
        claim = str(o.get("parent") or "")
        if claim and not claim.startswith(("unresolved", "ambiguous")):
            out.add(claim)
        comp = o.get("composition") or {}
        if comp:
            p, _ = D.parent_from_coefficients(comp, oxygen_status=(o.get("oxygen") or {}).get("status", "none"))
            if not p.startswith("unresolved"):
                out.add(p)
    return out


def split_pool(pool: list, parents: set) -> tuple[list, list]:
    """The pool without the variants of datasheet parents, and the variants (each marked with its parent)."""
    kept, variants = [], []
    for r in pool:
        p = parent_key(r["comp"])
        if p is not None and p in parents:
            variants.append(dict(r, variant_of=p))
        else:
            kept.append(r)
    return kept, variants


def background_of(pool: list) -> dict:
    """The pool as a background in the form hurricane9_release.guard reads."""
    import hurricane3 as H3
    systems = [r["chemsys"] for r in pool]
    return {"key": [S7.tag(r) for r in pool], "comp": [r["comp"] for r in pool], "chemsys": systems,
            "fold": np.array([H3.bg_fold(s) for s in systems], int),
            "sent": np.array([r["p_unconventional"] >= 0.5 for r in pool], bool)}


# ---------------------------------------------------------------- the two designs
def share(mask, of) -> float | None:
    of = np.asarray(of, bool)
    return float(np.asarray(mask, bool)[of].mean()) if of.any() else None


def decide(a_new, a_prev, b_new, b_prev) -> dict:
    """The rule of PROTOCOL: A, at most FACTOR times 9.0's share (and 9.0's share above zero); B, found at least 9.0's minus MARGIN."""
    a = a_new is not None and a_prev is not None and a_prev > 0 and a_new <= FACTOR * a_prev
    b = b_new is not None and b_prev is not None and b_new >= b_prev - MARGIN
    return {"A": bool(a), "B": bool(b), "adopted": bool(a and b)}


def family_of(comp: dict) -> str:
    return D.family(comp)[0]


def by_family(alarm: np.ndarray, comps: list) -> dict:
    """The alarms of one design, counted by Hurricane's family rule."""
    return dict(collections.Counter(family_of(c) for c, a in zip(comps, alarm) if a).most_common())


def compare(observations: list, supported: set, bg_prev: dict, pool: list, kept: list, variants: list, anchors: list) -> dict:
    """Everything the rule and the report read, computed for both designs in one place."""
    train = R.final_rows(observations)
    new = background_of(kept)
    rows_new, rows_prev = R.pseudo_rows(new["key"], new["comp"]), R.pseudo_rows(bg_prev["key"], bg_prev["comp"])
    table = F.element_table(sorted({e for o in observations for e in o["composition"]} | {e for r in rows_new + rows_prev for e in r["comp"]}))
    cache = {}
    X, (Xn,), cols = R.inputs(train, [rows_new], table, cache)
    tc, event, groups = R.targets(train)
    g = R.guard(X, event, groups, Xn, new["fold"], new["sent"])              # the new design: every chance cross-fitted
    tc_sc = R.Design9().fit_regressor(X, tc).tc(Xn)
    # Hurricane 9.0 on every compound of the pool that Radar sends, variants included, as screening round 7 scored them
    sent_all = [r for r in pool if r["p_unconventional"] >= 0.5]
    sc = S7.score(observations, bg_prev, anchors, sent_all)
    prev = {S7.tag(r): float(p) for r, p in zip(sent_all, sc["pool"]["p"])}
    prev_tc = {S7.tag(r): float(t) for r, t in zip(sent_all, sc["pool"]["tc_sc"])}
    prev_unknown = {S7.tag(r): bool(u) for r, u in zip(sent_all, sc["pool"]["unknown"])}
    p_prev = np.array([prev.get(k, np.nan) for k in new["key"]], float)
    inside = ~np.asarray(g["unknown"], bool)
    judged = new["sent"] & inside & np.isfinite(g["p"]) & np.isfinite(p_prev)
    alarm_new, alarm_prev = judged & (g["p"] >= 0.5), judged & (p_prev >= 0.5)
    same_tc = [abs(prev_tc[k] - float(t)) for k, t, s in zip(new["key"], tc_sc, new["sent"]) if s and k in prev_tc and np.isfinite(t)]
    same_inside = sum(1 for k, u, s in zip(new["key"], g["unknown"], new["sent"]) if s and k in prev_unknown and prev_unknown[k] != bool(u))
    # the declared windows, recomputed for both designs with the same code
    ans_new = R.window_answers(observations, supported, table, cache, rows_new)
    ans_prev = R.window_answers(observations, supported, table, cache, rows_prev)
    fam_new, fam_prev = R.pooled_answers(ans_new["cells"], False), R.pooled_answers(ans_prev["cells"], False)
    a_new, a_prev = share(alarm_new, judged), share(alarm_prev, judged)
    rule = decide(a_new, a_prev, fam_new["found"], fam_prev["found"])
    # the variants: how many, and those that 9.0 would have called likely
    v_sent = [r for r in variants if r["p_unconventional"] >= 0.5]
    v_alarm = [r for r in v_sent if prev.get(S7.tag(r), 0.0) >= 0.5 and not prev_unknown.get(S7.tag(r), True)]
    return {
        "train": train, "new": new, "g": g, "tc_sc": tc_sc, "p_prev": p_prev, "judged": judged, "sc": sc, "prev": prev, "prev_unknown": prev_unknown,
        "summary": {
            "rule": rule,
            "A": {"new": a_new, "previous": a_prev, "compounds": int(judged.sum()), "alarms_new": int(alarm_new.sum()),
                  "alarms_previous": int(alarm_prev.sum()), "factor": FACTOR},
            "B": {"new": fam_new["found"], "previous": fam_prev["found"], "margin": MARGIN},
            "family_windows": {"new": fam_new, "previous": fam_prev},
            "new_family_windows": {"new": R.pooled_answers(ans_new["cells"], True), "previous": R.pooled_answers(ans_prev["cells"], True)},
            "cells": {"new": ans_new["cells"], "previous": ans_prev["cells"]},
            "guard": {"new": g["summary"], "previous": sc["summary"]},
            "alarms_by_family": {"new": by_family(alarm_new, new["comp"]), "previous": by_family(alarm_prev, new["comp"])},
            "checks": {"regressor_unchanged_largest_difference_k": max(same_tc) if same_tc else 0.0,
                       "inside_differs_for": same_inside, "classifier_difference": sc.get("classifier_difference")},
            "pool": {"compounds": len(pool), "sent": len(sent_all), "background": len(kept), "background_sent": int(new["sent"].sum()),
                     "background_near": int(np.asarray(g["near"], bool).sum()),
                     "previous_alarms_on_the_whole_pool": sum(1 for r in sent_all if prev.get(S7.tag(r), 0.0) >= 0.5 and not prev_unknown.get(S7.tag(r), True)),
                     "previous_judged_on_the_whole_pool": sum(1 for r in sent_all if not prev_unknown.get(S7.tag(r), True))},
            "variants": {"n": len(variants), "sent": len(v_sent), "previous_alarms": len(v_alarm),
                         "by_track": dict(collections.Counter(r["track"] for r in variants)),
                         "by_source": dict(collections.Counter(r["db"] for r in variants)),
                         "examples": [{"id": S7.tag(r), "formula": S7.pretty(r["comp"]), "parent": r["variant_of"], "track": r["track"],
                                       "previous_chance": round(prev[S7.tag(r)], 3)}
                                      for r in sorted(v_alarm, key=lambda r: (-prev[S7.tag(r)], S7.tag(r)))[:40]]},
        }}


def top_by_track(kept: list, c: dict) -> dict:
    """The compounds each track's would-be list would open with under the new design: judged, ordered by the chance times the
    Tc, then the Tc, then the id, one per chemical system. Shown beside Hurricane 9.0's chance; not a list."""
    g, tc_sc, p_prev, new = c["g"], c["tc_sc"], c["p_prev"], c["new"]
    out = {}
    for track in ("experimental", "computed"):
        idx = [i for i in np.flatnonzero(c["judged"]) if kept[i]["track"] == track and np.isfinite(tc_sc[i])]
        idx.sort(key=lambda i: (-float(g["p"][i] * tc_sc[i]), -float(tc_sc[i]), new["key"][i]))
        rows, seen = [], set()
        for i in idx:
            if kept[i]["chemsys"] in seen:
                continue
            seen.add(kept[i]["chemsys"])
            rows.append({"id": new["key"][i], "formula": S7.pretty(kept[i]["comp"]), "family": family_of(kept[i]["comp"]),
                         "chance": round(float(g["p"][i]), 3), "chance_9_0": round(float(p_prev[i]), 3), "tc_sc": round(float(tc_sc[i]), 1),
                         "labels": kept[i].get("labels") or []})
            if len(rows) == TOP:
                break
        out[track] = rows
    return out


def write_table(path: Path, kept: list, variants: list, c: dict) -> str:
    """One row per compound of the pool: the new design's answer for the background, Hurricane 9.0's for every compound Radar sends."""
    g, tc_sc, new = c["g"], c["tc_sc"], c["new"]
    cols = ["id", "formula", "db", "track", "chemsys", "fold", "p_unconventional", "sent", "variant_of", "ratio", "not_known", "chance",
            "chance_9_0", "tc_sc"]
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, r in enumerate(kept):
            k = new["key"][i]
            w.writerow([k, S7.pretty(r["comp"]), r["db"], r["track"], r["chemsys"], int(new["fold"][i]), round(r["p_unconventional"], 4),
                        int(new["sent"][i]), "", round(float(g["ratio"][i]), 3), int(bool(g["unknown"][i])),
                        "" if not np.isfinite(g["p"][i]) else round(float(g["p"][i]), 4),
                        "" if k not in c["prev"] else round(c["prev"][k], 4), "" if not np.isfinite(tc_sc[i]) else round(float(tc_sc[i]), 2)])
        for r in variants:
            k = S7.tag(r)
            w.writerow([k, S7.pretty(r["comp"]), r["db"], r["track"], r["chemsys"], "", round(r["p_unconventional"], 4),
                        int(r["p_unconventional"] >= 0.5), r["variant_of"], "", int(c["prev_unknown"].get(k, False)), "",
                        "" if k not in c["prev"] else round(c["prev"][k], 4), ""])
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- the run
def run(smoke: bool = False, output_dir: Path | None = None) -> dict:
    import scipy
    import sklearn
    started, digest = time.time(), protocol_sha256()
    if smoke:
        observations, _ = D.load_observations(F.synthetic_table())
        supported = {u["canonical"] for i, u in enumerate(D.canonical_units(observations, lift=True)) if i % 2 == 0}
        train = R.final_rows(observations)
        bg_prev, anchors = R.synthetic_background(train), HU.load_anchors().get("materials", [])[:3]
        calculated, cod = S7.synthetic_sources(train, bg_prev)
        counts = {e: S7.MIN_ELEMENT for r in train for e in r["comp"]}
        pool, info = S7.assemble(calculated, cod, counts, [], None)
        p_unc, radar = S7.synthetic_route(pool)
        sources, same = {"synthetic": True}, None
        results = Path(output_dir or P.ROOT / "results" / "hurricane10-smoke")
    else:
        import screen as SC
        declared = DECLARATION.read_text(encoding="utf-8") if DECLARATION.exists() else ""
        if digest not in declared:
            raise SystemExit(f"protocol sha256 {digest} is not in {DECLARATION.name}; refusing to read any data")
        released = json.loads((P.RESULTS / RELEASED).read_text(encoding="utf-8")) if (P.RESULTS / RELEASED).exists() else {}
        if not released.get("adopted") or released.get("smoke") or released.get("version") != R.MODEL_VERSION or \
                (released.get("protocol") or {}).get("sha256") != R.protocol_sha256():
            raise SystemExit("results/" + RELEASED + " is not the adopted release of Hurricane 9.0; nothing to compare with")
        if not (P.RESULTS / S7.COD_SNAPSHOT).is_file():
            raise SystemExit(f"results/{S7.COD_SNAPSHOT} is missing: the COD rows of screening round 7 are part of the pool")
        cache = P.CACHE / "mdr-supercon-220808"
        observations, _ = D.load_observations(D.fetch(D.DATA_FILE, cache).decode("utf-8", errors="replace"))
        supported, _ = F.supported_bins(D.fetch_dsc(cache).decode("utf-8", errors="replace"))
        train = R.final_rows(observations)
        bg_prev, anchors = R.jarvis_background(observations, train), HU.load_anchors().get("materials", [])
        counts = dict(collections.Counter(e for r in train for e in r["comp"]))
        can = lambda r: S7.size_ok(r) and S7.gap_ok(r) and S7.covered(r, counts)   # noqa: E731
        jar, j_info = S7.jarvis_records(SC.load_rows(), counts)
        mp, m_info = S7.read_mp(S7.source_folder(), can)
        alex, a_info = S7.read_alexandria(S7.source_folder(), can)
        cod, c_info = S7.read_cod(P.RESULTS)
        pool, info = S7.assemble(jar + mp + alex, cod, counts, SC.known_lists([]), S7.datasheet_list(observations))
        p_unc, radar = S7.radar_route(pool)
        radar = dict(radar, check=S7.routing_check(pool, p_unc, bg_prev))
        sources = {S7.JARVIS: j_info, S7.MP: m_info, S7.ALEX: a_info, S7.COD: c_info}
        same = "pending"
        results = Path(output_dir) if output_dir else P.RESULTS
    P.log(f"pool: {info['pool']:,} compounds, {info['tracks']}")
    for r, p in zip(pool, np.asarray(p_unc, float)):
        r["p_unconventional"] = float(p)
    kept, variants = split_pool(pool, datasheet_parents(observations))
    P.log(f"left out as variants of datasheet parents: {len(variants):,}; background: {len(kept):,}")
    c = compare(observations, supported, bg_prev, pool, kept, variants, anchors)
    if same == "pending":            # stops here, before anything is written, if the release is not reproduced
        same = S6.compare_with_release(bg_prev, c["sc"], P.RESULTS / S6.BACKGROUND)
    s = c["summary"]
    results.mkdir(parents=True, exist_ok=True)
    out = {"round": ROUND, "model": HU.MODEL, "version": MODEL_VERSION, "module": VERSION, "smoke": smoke,
           "adopted": s["rule"]["adopted"], "rule": {"A": TEST_A, "B": TEST_B},
           "protocol": {"name": PROTOCOL["name"], "sha256": digest, "previous_release_sha256": R.protocol_sha256(),
                        "pool_protocol_sha256": S7.protocol_sha256()},
           "result": s, "top": top_by_track(kept, c), "pool_info": info, "sources": sources, "radar": radar, "reproduces": same,
           "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local"), "designer": "AI agent (Claude)",
           "libraries": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__}}
    out["files"] = {"pool_table_sha256": write_table(results / TABLE, kept, variants, c)}
    out["minutes"] = round((time.time() - started) / 60, 1)
    out = F.clean(out)
    (results / RESULT).write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    show = {k: out[k] for k in ("round", "version", "adopted", "protocol", "result", "top", "pool_info", "radar", "reproduces", "files", "minutes", "smoke")}
    text = json.dumps(show, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    print("=== hurricane10 begin")
    for i in range(0, len(text), 2000):
        print(f"h10|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== hurricane10 end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    rule = s["rule"]
    P.log(f"Hurricane round {ROUND}: A {s['A']['previous']} -> {s['A']['new']} ({'met' if rule['A'] else 'not met'}), "
          f"B {s['B']['previous']} -> {s['B']['new']} ({'met' if rule['B'] else 'not met'}); adopted: {rule['adopted']}")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", action="store_true", help="print the frozen protocol and its SHA-256")
    parser.add_argument("--smoke", action="store_true", help="invented rows through every step; not a result")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.protocol:
        print(json.dumps(PROTOCOL, indent=1, sort_keys=True))
        print("protocol sha256 " + protocol_sha256())
    elif args.smoke:
        run(smoke=True, output_dir=args.output_dir)
    else:
        parser.error("choose --protocol or --smoke; the run is python ml/pipeline.py hurricane10")


if __name__ == "__main__":
    main()
