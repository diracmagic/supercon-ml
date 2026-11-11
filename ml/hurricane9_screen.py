"""Screening round 6: the candidates of Hurricane 9.0.

    python ml/hurricane9_screen.py --protocol                 # the frozen screening protocol and its SHA-256
    python ml/hurricane9_screen.py --smoke [--output-dir DIR] # invented rows through every step; not a result
    python ml/pipeline.py hurricane9screen                    # the screening run: writes results/ and progress/

The published candidates of Hurricane were screened by Hurricane 4.0 (screening round 5). This run screens the pool
with the version in use. It fits no new design and decides nothing: it repeats the released computation of
ml/hurricane9_release.py for the screening pool and writes it down as a list.

- The pool is the one the release run built for its guard: Hurricane's screening pool from JARVIS-DFT, built as
  screen.run builds it with the element counts of Hurricane 9.0's training rows and the same exclusions (nothing that
  SuperCon, 3DSC, the computed-Tc data or the list of others' claims has, and nothing made of exactly the elements of
  a known superconductor), without the compounds whose composition the datasheet lists.
- The chance of a compound is the guard's cross-fitted chance: it comes from a classifier that learned from no
  background compound of the compound's fold, so no candidate is scored by a model that was told it does not
  superconduct. These are the numbers the release run committed (results/hurricane_round9_background.csv). The run
  computes them again and stops, writing nothing, if a compound, its routing or its chance differs.
- The Tc if the compound superconducts is the released regressor's, which never sees a background compound; its 90%
  range uses the released width on log(1 + Tc).
- A compound outside the training data gets "not known": it is counted, not listed. Of the others that Radar sends to
  Hurricane, the list holds one per chemical system, ranked by the chance times the Tc, at most 50.

Storm's list and every other part of the screen block stay as screening round 5 published them. Everything that
decides the list is in PROTOCOL; the run refuses to read any data unless the hash of PROTOCOL is written in
results/validation/hurricane9-screen-declaration-v1.md.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane9_release as R  # noqa: E402

F, D, HU, H2, P = R.F, R.D, R.HU, R.H2, R.P
VERSION = "hurricane9-screen-v1"
ROUND = 6                       # screening round 5 published both lists; this round is Hurricane's list only
TOP_N, PER_SYSTEM = 50, 1       # as screen.py
TOLERANCE = 5.1e-5              # the committed table is rounded to four decimals
DECLARATION = P.ROOT / "results" / "validation" / "hurricane9-screen-declaration-v1.md"
RELEASED = "hurricane_round9.json"
BACKGROUND = "hurricane_round9_background.csv"
PROTOCOL = {
    "name": "hurricane9-screen-protocol-v1", "module": VERSION, "screening_round": ROUND,
    "model": {"name": HU.MODEL, "version": R.MODEL_VERSION, "release_protocol": R.PROTOCOL["name"],
              "release_protocol_sha256": R.protocol_sha256(),
              "status": "the version in use; this run releases, tunes and compares nothing"},
    "pool": "hurricane9_release.jarvis_background: Hurricane's screening pool built as screen.run builds it from JARVIS-DFT "
            "with the element counts of the released training rows and the exclusions of screen.known_lists, without the "
            "compounds whose composition the datasheet lists; Radar refitted on its 3DSC rows routes each compound",
    "chance": "hurricane9_release.guard, cross-fitted in five folds by a hash of the chemical system: the chance of a compound "
              "comes from a classifier that learned from no background compound of its fold",
    "must_reproduce": {"file": "results/" + BACKGROUND, "what": "the same compounds in the same order, the same Radar routing, "
                       "the same not-known answers and every chance within the tolerance", "tolerance": TOLERANCE,
                       "otherwise": "the run stops and writes nothing"},
    "tc": "hurricane9_release.Design9().fit_regressor on the released training rows (the rows with a Tc value, target "
          "log(1 + Tc)); the 90% range is the released width on log(1 + Tc), read from results/" + RELEASED,
    "listed": {"sent": "Radar's probability of an unconventional family is at least one half",
               "inside": "the distance ratio is at most the guard's abstention; a compound further away is not known and not listed",
               "order": "the chance times the Tc if it superconducts, then that Tc, then the JARVIS id",
               "per_chemical_system": PER_SYSTEM, "top": TOP_N},
    "written": ["results/screen_round6.json", "results/screen_round6_hurricane.csv",
                "progress/progress.json: screen.hurricane, screen.models, the detail of the screen stage and one log entry"],
    "unchanged": "Storm's list and every other field of the screen block, as screening round 5 published them",
}
CAVEAT = ("Hurricane learned measured Tc from cuprates, iron-based, heavy-fermion compounds and other oxides in the NIMS SuperCon "
          "datasheet; it reads the composition only and gives the chance that a compound superconducts and its Tc if it does. "
          "Many of these compounds would need doping or pressure, and a candidate is a prediction until an experiment checks it")
NOT_KNOWN = ("Hurricane gives no chance to a compound further from every training compound, in its standardized inputs, than the "
             "distance that separates 95% of the training compounds from their nearest neighbour in another parent compound; "
             "such compounds are not listed")
COLUMNS = ["jid", "formula", "chemsys", "nat", "spg", "spg_number", "ehull", "gap", "magmom", "icsd", "p_unconventional", "family",
           "hurricane_tc", "p_sc", "tc_sc", "lo", "hi", "types", "novelty", "nearest_training", "nearest_training_tc", "not_known"]


def protocol_text() -> str:
    return json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":"))


def protocol_sha256() -> str:
    return hashlib.sha256(protocol_text().encode("utf-8")).hexdigest()


def pretty(comp: dict) -> str:
    """The reduced formula as the screening rounds write it."""
    import storm3 as S3
    return S3.pretty(comp)


# ---------------------------------------------------------------- the released computation, for the pool
def score(observations: list, bg: dict, anchors: list, table=None) -> dict:
    """What the released Hurricane 9.0 answers for every compound of the pool. The steps and their order are those of
    hurricane9_release.build, so the chances are the ones its guard check recorded."""
    import screen as SC
    train = R.final_rows(observations)
    bg_rows = R.pseudo_rows(bg["key"], bg["comp"])
    anchor_rows = R.pseudo_rows([f"anchor-{i}" for i in range(len(anchors))], [a["composition"] for a in anchors])
    if table is None:
        table = F.element_table(sorted({e for o in observations for e in o["composition"]} | {e for r in bg_rows + anchor_rows for e in r["comp"]}))
    X, (Xb, _), cols = R.inputs(train, [bg_rows, anchor_rows], table, {})
    tc, event, groups = R.targets(train)
    g = R.guard(X, event, groups, Xb, bg["fold"], bg["sent"])
    reg = R.Design9().fit_regressor(X, tc)
    with np.errstate(invalid="ignore"):
        nearest = np.asarray(SC.novelty(X, groups, Xb)["nearest"], int) if len(Xb) else np.zeros(0, int)
    return {"train": train, "tc": tc, "event": event, "p": g["p"], "ratio": g["ratio"], "unknown": g["unknown"], "near": g["near"],
            "summary": g["summary"], "tc_sc": reg.tc(Xb), "nearest": nearest, "n_features": len(cols)}


def compare_with_release(bg: dict, sc: dict, path: Path) -> dict:
    """The pool and its chances against the table the release run committed. Any difference stops the run."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if [r["jid"] for r in rows] != [str(k) for k in bg["key"]]:
        ours, theirs = {str(k) for k in bg["key"]}, {r["jid"] for r in rows}
        raise SystemExit(f"the pool is not the release run's pool: {len(ours - theirs)} compounds are new, {len(theirs - ours)} are "
                         f"missing and the order {'differs' if ours == theirs else 'cannot be compared'}; nothing is written")
    worst = 0.0
    for i, r in enumerate(rows):
        if (r["sent"] == "True") != bool(bg["sent"][i]) or (r["not_known"] == "True") != bool(sc["unknown"][i]):
            raise SystemExit(f"{r['jid']}: Radar's routing or the not-known answer differs from the release run; nothing is written")
        ours = float(sc["p"][i])
        if r["p_sc"] == "" or not math.isfinite(ours):
            if (r["p_sc"] == "") != (not math.isfinite(ours)):
                raise SystemExit(f"{r['jid']}: a chance exists in only one of the two runs; nothing is written")
            continue
        worst = max(worst, abs(ours - float(r["p_sc"])))
    if worst > TOLERANCE:
        raise SystemExit(f"a chance differs from the release run's by {worst:.2e}, more than {TOLERANCE:.1e}; nothing is written")
    return {"file": "results/" + path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows),
            "largest_difference": round(worst, 7), "tolerance": TOLERANCE}


def nearest_record(row: dict) -> tuple[str, float | None]:
    """The training row nearest to a compound: its composition as the datasheet gives it, and its Tc (0 for a
    composition measured not to superconduct, nothing for one with neither a Tc value nor such a measurement)."""
    unit = row["unit"]
    tc = unit.get("tc_k")
    formula = "".join(f"{e}{float(v):g}" for e, v in sorted(row["comp"].items()))
    return formula, (float(tc) if tc is not None else 0.0 if unit.get("event") == 0 else None)


def table_rows(bg: dict, sc: dict, meta: dict, width: float) -> list:
    """One row for every compound Radar sends to Hurricane, in the published order: the judged ones first, by the chance
    times the Tc if it superconducts, then that Tc, then the JARVIS id."""
    import screen as SC
    rows = []
    for i in np.flatnonzero(np.asarray(bg["sent"], bool)):
        jid, comp, m = str(bg["key"][i]), bg["comp"][i], meta[str(bg["key"][i])]
        p, tc_sc = float(sc["p"][i]), float(sc["tc_sc"][i])
        near_formula, near_tc = nearest_record(sc["train"][int(sc["nearest"][i])])
        rows.append({"jid": jid, "formula": pretty(comp), "chemsys": bg["chemsys"][i], "nat": int(m["nat"]), "spg": m["spg"],
                     "spg_number": m["spg_number"], "ehull": m["ehull"], "gap": m["gap"], "magmom": m["magmom"], "icsd": bool(m["icsd"]),
                     "p_unconventional": float(bg["p_unconventional"][i]), "family": SC.family_guess(comp),
                     "hurricane_tc": p * tc_sc, "p_sc": p, "tc_sc": tc_sc,
                     "lo": max(math.expm1(math.log1p(tc_sc) - width), 0.0), "hi": math.expm1(math.log1p(tc_sc) + width),
                     "types": ";".join(k for k, v in H2.structure_types(comp).items() if v > 0), "novelty": float(sc["ratio"][i]),
                     "nearest_training": near_formula, "nearest_training_tc": near_tc, "not_known": bool(sc["unknown"][i])})
    down = lambda v: -v if math.isfinite(v) else math.inf   # noqa: E731  (a missing value sorts last)
    rows.sort(key=lambda r: (r["not_known"], down(r["hurricane_tc"]), down(r["tc_sc"]), r["jid"]))
    return rows


def judged(r: dict) -> bool:
    """Hurricane gives this compound a chance: it lies inside the training data and the chance exists."""
    return not r["not_known"] and math.isfinite(r["p_sc"]) and math.isfinite(r["tc_sc"])


def listed_rows(rows: list) -> list:
    """The judged compounds in order, one per chemical system, at most TOP_N."""
    out, per = [], {}
    for r in rows:
        if not judged(r) or per.get(r["chemsys"], 0) >= PER_SYSTEM:
            continue
        per[r["chemsys"]] = per.get(r["chemsys"], 0) + 1
        out.append(r)
        if len(out) == TOP_N:
            break
    return out


def published_listings(prog: dict) -> tuple[dict, dict]:
    """The first listings that the published lists carry. Screening round 5 is not in results/, so its candidates'
    dates are read from the published block: by JARVIS id and by composition."""
    by_id, by_comp = {}, {}
    screen = prog.get("screen") or {}
    for c in list(screen.get("candidates") or []) + list((screen.get("hurricane") or {}).get("candidates") or []):
        rec = c.get("listed") if isinstance(c, dict) else None
        if not isinstance(rec, dict) or len(str(rec.get("date") or "")) != 10 or not isinstance(rec.get("round"), int):
            continue
        entry = {"date": rec["date"], "at": rec["date"], "round": rec["round"], "file": rec.get("file")}
        try:
            key = P._composition_key(HU.parse_formula(str(c.get("formula", ""))))
        except ValueError:
            key = None
        for table, k in ((by_id, c.get("id")), (by_comp, key)):
            if k and (k not in table or (entry["at"], entry["round"]) < (table[k]["at"], table[k]["round"])):
                table[k] = entry
    return by_id, by_comp


def first_listings(results: Path, prog: dict) -> tuple[dict, dict]:
    """screen.first_listed over results/, with the published block's dates where they are earlier."""
    import screen as SC
    seen = SC.first_listed(results)
    for table, more in zip(seen, published_listings(prog)):
        for k, entry in more.items():
            if k not in table or (entry["at"], entry["round"]) < (table[k]["at"], table[k]["round"]):
                table[k] = entry
    return seen


def corrected_check(jid: str, check, records: dict):
    """A check with the exact-ID correction of the literature audit, as the publication of round 5 applied it."""
    correction = (records.get(jid) or {}).get("check_correction")
    if check and correction and isinstance(correction.get("check"), dict) and check.get("doi") == correction.get("replaces_doi"):
        return copy.deepcopy(correction["check"])
    return check


def candidates(rows: list, bg: dict, meta: dict, seen: tuple, now: dict, checks: tuple, records: dict) -> list:
    """The published records of the listed compounds, with the fields the earlier rounds gave a Hurricane candidate."""
    import screen as SC
    comp_of = dict(zip((str(k) for k in bg["key"]), bg["comp"]))
    out = []
    for rank, r in enumerate(listed_rows(rows), 1):
        comp = comp_of[r["jid"]]
        c = dict(SC.base_record(rank, r), tc=SC._r(r["hurricane_tc"], 2), tc_sc=SC._r(r["tc_sc"], 2), lo=SC._r(r["lo"], 2), hi=SC._r(r["hi"], 2),
                 p_sc=SC._r(r["p_sc"], 3), p_unconventional=SC._r(r["p_unconventional"], 3),
                 family=r["family"] if r["family"] != "other" else None, gap=SC._r(r["gap"], 2),
                 magnetic=True if abs(float(r["magmom"])) > SC.MAGMOM_MAX else None,
                 types=[t for t in r["types"].split(";") if t] or None, novelty=SC._r(r["novelty"], 2),
                 nearest={"formula": r["nearest_training"], "tc": SC._r(r["nearest_training_tc"], 2)},
                 listed=SC.listed_for(r["jid"], comp, seen, now), atoms=SC.crystal(meta[r["jid"]]["atoms"]),
                 check=corrected_check(r["jid"], SC.check_for(checks[0], checks[1], comp), records))
        out.append({k: v for k, v in c.items() if v is not None})
    return out


# ---------------------------------------------------------------- the pool's records
def jarvis_meta(keys) -> dict:
    """The JARVIS-DFT record of every compound of the pool: what the list shows next to a prediction."""
    import screen as SC
    rows = SC.load_rows().set_index("id")
    return {str(k): {"nat": int(rows.at[k, "nat"]), "spg": rows.at[k, "spg"], "spg_number": rows.at[k, "spg_number"], "ehull": rows.at[k, "ehull"],
                     "gap": rows.at[k, "gap"], "magmom": rows.at[k, "magmom"], "icsd": bool(rows.at[k, "icsd"]), "atoms": rows.at[k, "atoms"]}
            for k in keys}


def synthetic_meta(bg: dict) -> dict:
    """Invented records for --smoke and the tests: one atom per formula unit on a line; not a structure."""
    out = {}
    for k, comp in zip(bg["key"], bg["comp"]):
        elements = [e for e in sorted(comp) for _ in range(int(round(comp[e])))]
        n = len(elements)
        out[str(k)] = {"nat": n, "spg": "P1", "spg_number": 1.0, "ehull": 0.0, "gap": 0.0, "magmom": 0.0, "icsd": False,
                       "atoms": {"lattice_mat": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0 * n]], "elements": elements,
                                 "coords": [[0.0, 0.0, (i + 0.5) / n] for i in range(n)], "cartesian": False}}
    return out


# ---------------------------------------------------------------- the published block
def block(rows: list, cands: list, bg: dict, sc: dict, released: dict, stamp: str) -> dict:
    """screen.hurricane as the app reads it, with the fields the earlier rounds published and the round and date of this list."""
    import screen as SC
    g, info = sc["summary"], bg.get("info") or {}
    n_sent, n_unknown = len(rows), sum(1 for r in rows if r["not_known"])
    answers = (released.get("answers") or {})
    new, fam = answers.get("new_family_windows") or {}, answers.get("family_windows") or {}
    rng = (released.get("evidence") or {}).get("range") or {}
    excluded = dict(info.get("excluded") or {})
    if "in_the_datasheet" in info:
        excluded["datasheet"] = int(info["in_the_datasheet"])
    rule = (f"within {int(SC.EHULL_MAX * 1000)} meV/atom of the convex hull, a band gap of at most {SC.HUR_GAP_MAX:g} eV, magnetic or not, "
            f"{SC.HUR_ELEMENTS[0]} to {SC.HUR_ELEMENTS[1]} elements, up to {SC.HUR_MAX_ATOMS} atoms in the cell, elements Hurricane's "
            f"training data covers; the list holds the {n_sent:,} that Radar sends to Hurricane, one per chemical system, except the "
            f"{n_unknown:,} too far from Hurricane's training data for it to give a chance")
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    return {
        "model": f"{HU.MODEL} {R.MODEL_VERSION}", "design": "H90", "two_part": "mean", "round": ROUND, "date": stamp[:10],
        "pool": {"source": "JARVIS-DFT", "what": "compounds with no superconductivity record that Radar sends to Hurricane",
                 "n_screened": int(g["n"]), "n_sent": n_sent, "rule": rule},
        "excluded": excluded,
        "range": {"level": rng.get("level", 1 - R.ALPHA), "width_log": round(float(rng["width_log"]), 4), "of": "the Tc if it superconducts",
                  "from": "its errors on parent compounds first reported after its training data end"},
        "check": {"about": "of the compositions of new parent compounds in its time windows, the share given at least an even chance: of "
                           "those that superconduct, and of those measured not to superconduct",
                  "found": r3(fam.get("found")), "alarms_on_negatives": r3(fam.get("alarms_on_negatives")), "n": fam.get("units")},
        "novelty": {"level": SC.NOVEL_LEVEL, "outside": 0, "about": SC.NOVELTY_ABOUT},
        "caveat": CAVEAT, "candidates": cands,
        "background": {"n": int(g["n_used"]), "weight": R.WEIGHT, "cross_fitted": True, "radius": R.RADIUS, "pool": int(g["n"])},
        "reliability": {"false_alarms": None if g["false_alarms"] is None else round(float(g["false_alarms"]), 4),
                        "n_background": int(g["n_used"]), "abstain": R.ABSTAIN,
                        "about": "false alarms: the share of the held-out compounds with no superconductivity record that Radar sends to "
                                 "Hurricane which lie inside its training data and get at least an even chance; the compounds of this "
                                 "list are those same compounds, so a candidate with at least an even chance is one of them",
                        "cite": R.KONNO["cite"], "doi": R.KONNO["doi"], "found": r3(new.get("found")), "dismissed": r3(new.get("dismissed")),
                        "unknown_lofo": r3(new.get("unknown")),
                        "dismissed_about": "trained only on reports dated before a family was found and asked about that family's first five years"},
        "not_known": {"n": n_unknown, "of": n_sent, "abstain": R.ABSTAIN, "about": NOT_KNOWN},
    }


def stage_detail(screen: dict) -> str:
    """The screen stage's line: Storm's list as screening round 5 left it, and Hurricane's list of this round."""
    import screen as SC
    text = SC.screening_stage_detail(screen)
    h = screen.get("hurricane") or {}
    mark = "The candidate list contains model suggestions"
    note = (f"Hurricane's list is from round {h.get('round')}, screened with {h.get('model')}: {(h.get('not_known') or {}).get('n', 0):,} of "
            f"the {(h.get('pool') or {}).get('n_sent', 0):,} compounds Radar sent it are too far from its training data for a chance. ")
    return text.replace(mark, note + mark) if mark in text else text + " " + note.strip()


def update_progress(out: dict, progress: Path) -> None:
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp, b = out["run_at"], out["hurricane"]
    screen = prog.get("screen") or {}
    radar_storm = [m for m in screen.get("models") or [] if isinstance(m, str) and not m.startswith(HU.MODEL)]
    screen["models"] = radar_storm + [b["model"]]
    screen["hurricane"] = b
    prog["screen"] = screen
    for st in prog.get("stages", []):
        if st.get("id") == "screen":
            st["detail"] = stage_detail(screen)
    cands, top = b["candidates"], None
    if cands:
        top = max(cands, key=lambda c: (c["p_sc"], c["tc_sc"]))
    likely = sum(1 for c in cands if c["p_sc"] >= 0.5)
    msg = (f"Screening round {ROUND}: {b['model']} screened the {b['pool']['n_sent']:,} compounds that Radar sent it from a pool of "
           f"{b['pool']['n_screened']:,} JARVIS-DFT compounds with no superconductivity record; {b['not_known']['n']:,} are too far from its "
           f"training data for a chance and are not listed, and {len(cands)} are published, one per chemical system. "
           f"{'None' if likely == 0 else 'One' if likely == 1 else likely} of them {'has' if likely == 1 else 'have'} at least an even chance"
           + (f"; the highest is {top['formula']} at {top['p_sc']:.0%}, with {top['tc_sc']:.1f} K if it superconducts" if top else "")
           + ". These are model suggestions, not measurements; Storm's list stays as round 5 published it")
    prefix = f"Screening round {ROUND}:"
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(prefix)]   # a re-run replaces it
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)


# ---------------------------------------------------------------- the run
def write_table(path: Path, rows: list) -> str:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if r[k] is None else round(r[k], 5) if isinstance(r[k], float) else r[k]) for k in COLUMNS})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(bg: dict, sc: dict, meta: dict, released: dict, same: dict, results: Path, progress: Path, smoke: bool, started: float) -> dict:
    """Everything after the scoring: the table of the compounds Radar sent, the list, the block, the result file and the
    progress file, and the block printed into the log with its hash."""
    import scipy
    import sklearn
    import screen as SC
    from literature_audit import load_audit
    stamp = P.now_iso()
    rows = table_rows(bg, sc, meta, float(released["evidence"]["range"]["width_log"]))
    seen = ({}, {}) if smoke else first_listings(P.RESULTS, json.loads(progress.read_text(encoding="utf-8")))
    now = {"date": stamp[:10], "at": stamp, "round": ROUND, "file": f"screen_round{ROUND}.json"}
    records = load_audit()[0]
    cands = candidates(rows, bg, meta, seen, now, SC.load_checks(), records)
    b = block(rows, cands, bg, sc, released, stamp)
    info = bg.get("info") or {}
    out = {"run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local"), "round": ROUND, "smoke": smoke, "module": VERSION,
           "protocol": {"name": PROTOCOL["name"], "sha256": protocol_sha256(), "release_protocol_sha256": R.protocol_sha256()},
           "models": [b["model"]], "candidates": [], "hurricane": b, "reproduces": same, "guard": dict(sc["summary"]),
           "sources": info.get("sources"), "radar": bg.get("radar"), "pool_steps": info.get("steps"),
           "counts": {"pool": int(len(bg["key"])), "sent": len(rows), "not_known": b["not_known"]["n"], "judged": sum(1 for r in rows if judged(r)),
                      "chemical_systems_judged": len({r["chemsys"] for r in rows if judged(r)}), "listed": len(cands),
                      "at_least_an_even_chance": sum(1 for c in cands if c["p_sc"] >= 0.5),
                      "with_a_recorded_check": sum(1 for c in cands if c.get("check")),
                      "with_a_literature_record": sum(1 for c in cands if c["id"] in records),
                      "listed_before": sum(1 for c in cands if c["listed"]["round"] != ROUND)},
           "libraries": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
           "licence": D.LICENCE, "attribution": D.ATTRIBUTION}
    out["files"] = {"hurricane_table_sha256": write_table(results / f"screen_round{ROUND}_hurricane.csv", rows)}
    out["minutes"] = round((time.time() - started) / 60, 1)
    out = F.clean(out)
    (results / f"screen_round{ROUND}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    update_progress(out, progress)
    show = {k: out[k] for k in ("round", "smoke", "protocol", "reproduces", "counts", "guard", "files", "minutes")}
    show["block"] = out["hurricane"]
    text = json.dumps(F.clean(show), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    print("=== hurricane9-screen begin")
    for i in range(0, len(text), 2000):
        print(f"h9s|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== hurricane9-screen end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    return out


def run(smoke: bool = False, output_dir: Path | None = None) -> dict:
    started, digest = time.time(), protocol_sha256()
    if smoke:
        observations, _ = D.load_observations(F.synthetic_table())
        supported = {u["canonical"] for i, u in enumerate(D.canonical_units(observations, lift=True)) if i % 2 == 0}
        bg, anchors = R.synthetic_background(R.final_rows(observations)), HU.load_anchors().get("materials", [])[:3]
        results = Path(output_dir or P.ROOT / "results" / "hurricane9-screen-smoke")
        results.mkdir(parents=True, exist_ok=True)
        progress = results / "progress.json"
        progress.write_text(P.PROGRESS.read_text(encoding="utf-8"), encoding="utf-8")
        released, _, background = R.build(observations, supported, bg, anchors)      # stands in for the committed release
        R.write_csv(results / BACKGROUND, background)
        released, table, meta = F.clean(released), results / BACKGROUND, synthetic_meta(bg)
    else:
        declared = DECLARATION.read_text(encoding="utf-8") if DECLARATION.exists() else ""
        if digest not in declared:
            raise SystemExit(f"screening protocol sha256 {digest} is not in {DECLARATION.name}; refusing to read any data")
        results, progress, table = Path(output_dir) if output_dir else P.RESULTS, P.PROGRESS, P.RESULTS / BACKGROUND
        if not (P.RESULTS / RELEASED).exists() or not table.exists():
            raise SystemExit("the release run's results are not in results/; nothing to screen with")
        released = json.loads((P.RESULTS / RELEASED).read_text(encoding="utf-8"))
        if not released.get("adopted") or released.get("smoke") or released.get("version") != R.MODEL_VERSION or \
                (released.get("protocol") or {}).get("sha256") != R.protocol_sha256():
            raise SystemExit("results/" + RELEASED + " is not the adopted release of this protocol; nothing is written")
        cache = P.CACHE / "mdr-supercon-220808"
        observations, _ = D.load_observations(D.fetch(D.DATA_FILE, cache).decode("utf-8", errors="replace"))
        bg, anchors = R.jarvis_background(observations, R.final_rows(observations)), HU.load_anchors().get("materials", [])
        results.mkdir(parents=True, exist_ok=True)
        meta = None
    sc = score(observations, bg, anchors)
    same = compare_with_release(bg, sc, table)            # stops here, before anything is written, if the release is not reproduced
    if meta is None:
        meta = jarvis_meta([k for k, s in zip(bg["key"], bg["sent"]) if s])
    return publish(bg, sc, meta, released, same, results, progress, smoke, started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", action="store_true", help="print the frozen screening protocol and its SHA-256")
    parser.add_argument("--smoke", action="store_true", help="invented rows through every step; not a result")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.protocol:
        print(json.dumps(PROTOCOL, indent=1, sort_keys=True))
        print("protocol sha256 " + protocol_sha256())
    elif args.smoke:
        run(smoke=True, output_dir=args.output_dir)
    else:
        parser.error("choose --protocol or --smoke; the screening run is python ml/pipeline.py hurricane9screen")


if __name__ == "__main__":
    main()
