"""JARVIS-DFT hull check (count-only): what the `ehull` field of the JARVIS-DFT 3D file holds.

The pool census found that the file's `ehull` field puts 89% of the entries with an ICSD number more than 50 meV/atom
above the hull (median of all entries 1.7 eV/atom), while the Materials Project and Alexandria put most of the same
compositions on or near theirs. Every screening pool of this project so far kept a JARVIS-DFT entry only if this field
was at most 0.05. This check asks the file itself what the field is:

- how `ehull` relates to the file's own formation energy per atom;
- what the distance to the convex hull is when it is computed here from those formation energies (pymatgen's phase
  diagram, the elements at zero), for a seeded sample of chemical systems, and how that compares with the field;
- the same for every chemical system of up to five elements (--all): how many entries the pools' rules would keep with
  the computed distance, and what it is for the candidates this project has published (progress/progress.json).

No model is loaded or fitted and nothing is written into results/ or progress/. The report goes into the job log
between markers.
"""
import collections
import hashlib
import itertools
import json
import math
import random
import sys
import time
from pathlib import Path

SEED = 20261111
SYSTEMS = 4000          # chemical systems in the sample (2 to 4 elements)
LIMIT = 0.05            # eV/atom, the pools' rule
NOBLE = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
RADIOACTIVE = {"Tc", "Pm", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Pa", "Np", "Pu", "Am", "Cm"}    # as in ml/storm5.py
BAD = {"H"} | NOBLE | RADIOACTIVE
PROGRESS = Path(__file__).resolve().parent.parent / "progress" / "progress.json"


def hull_distances(recs: list, by_system: dict, systems: list) -> tuple[dict, int]:
    """The distance to the convex hull of the file's own formation energies for every entry of the given chemical
    systems: entry index -> eV/atom. The hull of a system is built from the entries of the system and of all its
    subsystems, with the elements at zero."""
    from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram
    from pymatgen.core import Composition
    out, failed = {}, 0
    for s in systems:
        idx = []
        for k in range(1, len(s) + 1):
            for sub in itertools.combinations(s, k):
                idx += by_system.get(sub, [])
        entries = [PDEntry(Composition(recs[i]["c"]), recs[i]["f"] * recs[i]["n"]) for i in idx]
        entries += [PDEntry(Composition({e: 1}), 0.0) for e in s]          # the elements, at zero formation energy
        try:
            pd_ = PhaseDiagram(entries)
            for i in by_system[s]:
                out[i] = float(pd_.get_e_above_hull(PDEntry(Composition(recs[i]["c"]), recs[i]["f"] * recs[i]["n"])))
        except Exception:
            failed += 1
    return out, failed


def everything(recs: list, by_system: dict) -> dict:
    """The computed distance for every entry of a system of one to five elements, the pools' rules with it, and the
    published candidates."""
    import numpy as np
    t0 = time.time()
    systems = sorted(s for s in by_system if len(s) <= 5)
    dist, failed = hull_distances(recs, by_system, systems)
    for i in (i for s in by_system if len(s) == 1 for i in by_system[s]):      # an element: above the lowest entry of that element
        dist[i] = recs[i]["f"] - min(min(recs[j]["f"] for j in by_system[tuple(recs[i]["c"])]), 0.0)
    idx = sorted(dist)
    mine, field = np.array([dist[i] for i in idx]), np.array([recs[i]["h"] for i in idx])
    icsd = np.array([recs[i]["icsd"] for i in idx], bool)
    gap = np.array([recs[i]["gap"] if recs[i]["gap"] is not None else np.nan for i in idx])
    rules = np.array([2 <= len(recs[i]["c"]) <= 5 and recs[i]["n"] <= 40 and not (set(recs[i]["c"]) & BAD) for i in idx], bool)
    tab = lambda a, b: {"computed within; field within": int((a & b).sum()), "computed within; field beyond": int((a & ~b).sum()),      # noqa: E731
                        "computed beyond; field within": int((~a & b).sum()), "computed beyond; field beyond": int((~a & ~b).sum())}
    near, fnear = mine <= LIMIT, field <= LIMIT
    out = {"systems": len(systems), "systems_failed": failed, "entries": len(idx), "seconds": round(time.time() - t0, 1),
           "computed_quantiles": quantiles(mine), "all_entries": tab(near, fnear),
           "with_icsd": tab(near[icsd], fnear[icsd]), "without_icsd": tab(near[~icsd], fnear[~icsd]),
           "hurricane_rules (2 to 5 elements, at most 40 atoms, no H, noble or radioactive, gap at most 1 eV)": tab(near[rules & (gap <= 1.0)], fnear[rules & (gap <= 1.0)]),
           "metals (the same size and element rules, no band gap)": tab(near[rules & (gap <= 0.0)], fnear[rules & (gap <= 0.0)])}
    comps = lambda m: len({tuple(sorted((e, round(v / recs[i]["n"], 4)) for e, v in recs[i]["c"].items())) for i, k in zip(idx, m) if k})   # noqa: E731
    out["hurricane_rules_distinct_compositions"] = {"computed within": comps(near & rules & (gap <= 1.0)), "field within": comps(fnear & rules & (gap <= 1.0)),
                                                    "with an ICSD number, any distance": comps(icsd & rules & (gap <= 1.0))}
    # the candidates this project has published
    by_id = {recs[i]["id"]: i for i in idx}
    try:
        screen = json.loads(PROGRESS.read_text(encoding="utf-8")).get("screen") or {}
    except (OSError, ValueError):
        screen = {}
    for name, cands in (("storm", screen.get("candidates") or []), ("hurricane", (screen.get("hurricane") or {}).get("candidates") or [])):
        rows = []
        for c in cands:
            i = by_id.get(str(c.get("id")))
            rows.append({"rank": c.get("rank"), "formula": c.get("formula"), "id": c.get("id"), "published_ehull": c.get("ehull"),
                         "field": None if i is None else round(recs[i]["h"], 4), "computed": None if i is None else round(dist[i], 4),
                         "icsd": None if i is None else bool(recs[i]["icsd"])})
        found = [r for r in rows if r["computed"] is not None]
        out["published_" + name] = {"listed": len(rows), "found": len(found), "computed_within": sum(r["computed"] <= LIMIT for r in found),
                                    "computed_beyond": sum(r["computed"] > LIMIT for r in found),
                                    "computed_beyond_200_meV": sum(r["computed"] > 0.2 for r in found),
                                    "with_icsd": sum(bool(r["icsd"]) for r in found),
                                    "computed_quantiles": quantiles([r["computed"] for r in found], (10, 25, 50, 75, 90)),
                                    "rows": [[r["rank"], r["formula"], r["id"], r["field"], r["computed"], r["icsd"]] for r in rows]}
    return out


def number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def filled(v) -> bool:
    return v is not None and str(v).strip().lower() not in ("", "na", "nan", "none", "[]")


def quantiles(values, qs=(1, 5, 10, 25, 50, 75, 90, 95, 99)) -> dict:
    import numpy as np
    v = np.asarray(values, float)
    return {str(q): round(float(x), 4) for q, x in zip(qs, np.percentile(v, qs))} if len(v) else {}


def main():
    import numpy as np
    from jarvis.db.figshare import data
    t0 = time.time()
    rows = data("dft_3d")
    out = {"step": "jarvis-hull-check", "records": len(rows), "load_s": round(time.time() - t0, 1)}
    recs = []
    for r in rows:
        a = r.get("atoms") or {}
        els = [str(e).strip() for e in a.get("elements") or []]
        h, f = number(r.get("ehull")), number(r.get("formation_energy_peratom"))
        if not els or h is None or f is None:
            continue
        recs.append({"id": str(r.get("jid")), "c": dict(collections.Counter(els)), "n": len(els), "h": h, "f": f, "icsd": filled(r.get("icsd")),
                     "gap": number(r.get("optb88vdw_bandgap"))})
    out["with_both_values"] = len(recs)
    h = np.array([r["h"] for r in recs])
    f = np.array([r["f"] for r in recs])
    icsd = np.array([r["icsd"] for r in recs], bool)
    out["field"] = {"ehull_quantiles": quantiles(h), "formation_energy_quantiles": quantiles(f),
                    "pearson_ehull_vs_minus_formation_energy": round(float(np.corrcoef(h, -f)[0, 1]), 4),
                    "share_ehull_equals_minus_formation_energy_within_0.02": round(float((np.abs(h + f) <= 0.02).mean()), 4),
                    "share_ehull_equals_formation_energy_within_0.02": round(float((np.abs(h - f) <= 0.02).mean()), 4),
                    "ehull_plus_formation_energy_quantiles": quantiles(h + f),
                    "negative_ehull": int((h < 0).sum()), "ehull_exactly_zero": int((h == 0).sum()),
                    "formation_energy_of_entries_within": quantiles(f[h <= LIMIT]), "formation_energy_of_entries_beyond": quantiles(f[h > LIMIT]),
                    "table": {"formation energy < 0; field within": int(((f < 0) & (h <= LIMIT)).sum()),
                              "formation energy < 0; field beyond": int(((f < 0) & (h > LIMIT)).sum()),
                              "formation energy >= 0; field within": int(((f >= 0) & (h <= LIMIT)).sum()),
                              "formation energy >= 0; field beyond": int(((f >= 0) & (h > LIMIT)).sum())},
                    "with_icsd": {"n": int(icsd.sum()), "field_within": int((icsd & (h <= LIMIT)).sum()),
                                  "formation_energy_quantiles": quantiles(f[icsd])}}
    # the hull, computed here from the file's formation energies, for a seeded sample of chemical systems
    by_system = collections.defaultdict(list)
    for i, r in enumerate(recs):
        by_system[tuple(sorted(r["c"]))].append(i)
    candidates = sorted(s for s in by_system if 2 <= len(s) <= 4)
    random.Random(SEED).shuffle(candidates)
    sample = candidates[:SYSTEMS]
    t1 = time.time()
    dist, failed = hull_distances(recs, by_system, sample)
    order = sorted(dist)
    mine, field, is_icsd = np.array([dist[i] for i in order]), np.array([recs[i]["h"] for i in order]), np.array([recs[i]["icsd"] for i in order], bool)
    tab = collections.Counter(f"computed here {'within' if a <= LIMIT else 'beyond'}; field {'within' if b <= LIMIT else 'beyond'}" for a, b in zip(mine, field))
    out["recomputed"] = {"seed": SEED, "systems_in_the_file_with_2_to_4_elements": len(candidates), "systems_sampled": len(sample),
                         "systems_failed": failed, "entries": int(len(mine)), "seconds": round(time.time() - t1, 1),
                         "computed_here_quantiles": quantiles(mine), "field_quantiles_same_entries": quantiles(field),
                         "table": dict(sorted(tab.items())),
                         "pearson": round(float(np.corrcoef(mine, field)[0, 1]), 4) if len(mine) > 2 else None,
                         "with_icsd": {"n": int(is_icsd.sum()), "computed_here_within": int((is_icsd & (mine <= LIMIT)).sum()),
                                       "field_within": int((is_icsd & (field <= LIMIT)).sum())},
                         "without_icsd": {"n": int((~is_icsd).sum()), "computed_here_within": int((~is_icsd & (mine <= LIMIT)).sum()),
                                          "field_within": int((~is_icsd & (field <= LIMIT)).sum())}}
    if "--all" in sys.argv:
        out["every_system"] = everything(recs, by_system)
    try:
        import jarvis
        import pymatgen.core as pc
        out["libraries"] = {"jarvis_tools": getattr(jarvis, "__version__", "unknown"), "pymatgen": getattr(pc, "__version__", "unknown")}
    except Exception:
        pass
    text = json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    print("=== jarvis-hull-check begin")
    for i in range(0, len(text), 2000):
        print(f"jh|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== jarvis-hull-check end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))


if __name__ == "__main__":
    main()
