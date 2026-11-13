"""A correction to the pools of screening rounds 1 to 6: how far above the convex hull each published candidate lies.

Screening rounds 1 to 6 took their pools from JARVIS-DFT 3D and kept an entry only if the file's `ehull` field was at
most 0.05 eV/atom; the published records and the app call that "within 50 meV/atom of the convex hull". The field does
not follow the convex hull of the file's own formation energies, so the two published lists, Storm's of screening
round 5 and Hurricane's of round 6, were not restricted to compounds near the hull. The record is
results/validation/screening-pools-hull-correction.md.

This step computes the distance of every JARVIS-DFT entry to the convex hull of the file's `formation_energy_peratom`,
with the elements at zero, checks it against pymatgen's phase diagram, and writes the distance of each published
candidate next to the lists: `screen.hull` in progress/progress.json and results/screen_hull_correction.json. It
changes no list, no rank, no score and no text of the published lists, runs no model and fits nothing. The file is
bound by the digest that the runs of 11 and 12 November 2026 printed for it; if jarvis-tools serves another file, the
step stops and writes nothing.

    python ml/pipeline.py screenhull       # the step, on the real file
    python ml/screen_hull.py --smoke       # invented rows through every part; not a result
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import math
import os
import tempfile
import time
from pathlib import Path

import numpy as np

import pipeline as P

VERSION = "screen-hull-v1"
NEAR = 0.05            # eV/atom: the distance the pools of rounds 1 to 6 meant to keep within (screen.EHULL_MAX)
FAR = 0.2              # eV/atom: also counted, as a compound this far above the hull is unlikely to be made
DECIMALS = 4           # the published distances, in eV/atom
AGREE = 1e-4           # eV/atom: the linear programme and pymatgen's phase diagram must agree this closely
SAMPLE = 300           # entries of the file checked against pymatgen besides every published candidate
RECORD = "results/validation/screening-pools-hull-correction.md"
RESULT = "screen_hull_correction.json"
LOG_PREFIX = "Correction to the screening pools:"
# JARVIS-DFT 3D (dft_3d) as jarvis-tools served it on 11 and 12 November 2026: the SHA-256 of one line per row of
# screen.load_rows, "id|formation energy|band gap|atoms in the cell|ICSD link" (file_digest below). The runs on the branch
# claude/screen-round7 printed it (runs 43123563097, 43125373652, 43126793006 and 43358591536), and the distances of
# the record were computed from this file.
ROWS_SHA256 = "465925380733c02fe03da2c76adeda63d352649881dfcc2184cddfa4428c7761"
ABOUT = ("The pools of screening rounds 1 to 6 kept a JARVIS-DFT entry if the file's ehull field was at most 0.05 eV/atom. That field "
         "does not follow the convex hull of the file's own formation energies, so the lists were not restricted to compounds near the "
         "hull. For each candidate of the two published lists this record gives the distance to the hull computed from those formation "
         "energies, with the elements at zero, in eV/atom. No list, rank or score is changed")


def num(v):
    """A finite float, or None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def entry(row) -> dict:
    """What this step reads of one row of screen.load_rows."""
    return {"id": str(row["id"]), "comp": {str(e): float(v) for e, v in dict(row["comp"]).items() if float(v) > 0}, "e_form": num(row.get("e_form")),
            "gap": num(row.get("gap")), "nat": num(row.get("nat")), "icsd": bool(row.get("icsd")), "field": num(row.get("ehull"))}


def file_digest(entries: list) -> str:
    """The digest that binds the file: one line per row, in the order of the file."""
    return hashlib.sha256("".join(f"{r['id']}|{r['e_form']!r}|{r['gap']!r}|{r['nat']!r}|{int(r['icsd'])}\n" for r in entries).encode()).hexdigest()


def same_file(digest: str) -> str:
    """Stops unless the file is the one the record describes."""
    if digest != ROWS_SHA256:
        raise SystemExit(f"JARVIS-DFT 3D as jarvis-tools serves it has the digest {digest}, not {ROWS_SHA256} of the record; nothing is written")
    return digest


# ---------------------------------------------------------------- the hull of the file's own formation energies
def hull_energies(entries: list, targets: list) -> np.ndarray:
    """For each target composition, the lowest formation energy per atom that a mixture of the entries can have at that
    overall composition (eV/atom). entries: (composition, formation energy per atom); the elements count as entries at
    zero, so a mixture always exists. One linear programme per target, over the entries of the target's chemical system
    and its subsystems, each composition once at its lowest energy."""
    from scipy.optimize import linprog
    best = {}
    for comp, f in entries:
        if f is None or not f < 0:              # an entry at or above the elements is never part of the lowest mixture
            continue
        tot = float(sum(comp.values()))
        key = tuple(sorted((e, round(v / tot, 6)) for e, v in comp.items()))
        if key not in best or f < best[key][1]:
            best[key] = ({e: v / tot for e, v in comp.items()}, float(f))
    by_system = collections.defaultdict(list)
    for shares, f in best.values():
        by_system[frozenset(shares)].append((shares, f))
    cache, out = {}, np.zeros(len(targets))
    for i, comp in enumerate(targets):
        tot = float(sum(comp.values()))
        els = sorted(comp)
        system = frozenset(els)
        if system not in cache:           # the entries of the chemical system and of every subsystem
            cache[system] = [m for k in range(1, len(els) + 1) for sub in itertools.combinations(els, k) for m in by_system.get(frozenset(sub), [])]
        members = cache[system]
        if not members:
            continue
        # unknowns: the share of each entry and of each element (at zero energy); the shares of every element must add up
        a_eq = np.array([[m[0].get(e, 0.0) for m in members] + [1.0 if e == x else 0.0 for x in els] for e in els])
        cost = np.array([m[1] for m in members] + [0.0] * len(els))
        res = linprog(cost, A_eq=a_eq, b_eq=np.array([comp[e] / tot for e in els]), bounds=(0, None), method="highs")
        if not res.success:
            raise SystemExit(f"the hull programme failed for {dict(comp)} ({res.message}); nothing is written")
        out[i] = min(float(res.fun), 0.0)
    return out


def distances(entries: list) -> dict:
    """id -> distance to the hull (eV/atom, not below zero) for every entry with a formation energy."""
    have = [r for r in entries if r["e_form"] is not None]
    hull = hull_energies([(r["comp"], r["e_form"]) for r in have], [r["comp"] for r in have])
    return {r["id"]: max(r["e_form"] - float(e), 0.0) for r, e in zip(have, hull)}


def pymatgen_check(entries: list, dist: dict, must: list, sample: int = SAMPLE, seed: int = P.SEED) -> dict:
    """The linear programme against pymatgen's phase diagram: for every entry named in `must` (the published
    candidates) and a seeded sample of the other entries of at most five elements, the two distances must agree."""
    try:
        from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram
        from pymatgen.core import Composition
    except ImportError:
        return {"skipped": "pymatgen is not installed"}
    by_system, by_id = collections.defaultdict(list), {r["id"]: r for r in entries}
    for r in entries:
        if r["e_form"] is not None and r["e_form"] < 0:
            by_system[frozenset(r["comp"])].append(r)
    named = set(must)
    small = [r["id"] for r in entries if r["id"] in dist and len(r["comp"]) <= 5 and r["id"] not in named]
    rng = np.random.default_rng(seed)
    pick = [small[j] for j in sorted(rng.choice(len(small), size=min(sample, len(small)), replace=False).tolist())] if small else []
    worst, where, t0 = 0.0, None, time.time()
    for key in list(must) + pick:
        r = by_id[key]
        system = frozenset(r["comp"])
        pd_entries = [PDEntry(Composition(x["comp"]), x["e_form"] * sum(x["comp"].values())) for s, members in by_system.items() if s <= system for x in members]
        pd_entries += [PDEntry(Composition({e: 1}), 0.0) for e in system]
        e = min(float(PhaseDiagram(pd_entries).get_hull_energy_per_atom(Composition(r["comp"]))), 0.0)
        diff = abs(max(r["e_form"] - e, 0.0) - dist[key])
        if diff > worst:
            worst, where = diff, key
    if worst > AGREE:
        raise SystemExit(f"the hull distance of this step differs from pymatgen's by {worst:.2e} eV/atom for {where}; nothing is written")
    return {"published_candidates_compared": len(must), "other_entries_compared": len(pick), "largest_difference_eV_per_atom": round(worst, 9),
            "seconds": round(time.time() - t0, 1)}


def file_counts(entries: list, dist: dict) -> dict:
    """The field against the computed distance, over the entries of the file that have a formation energy."""
    have = [r for r in entries if r["id"] in dist]
    field = {r["id"] for r in have if r["field"] is not None and r["field"] <= NEAR}
    computed = {r["id"] for r in have if dist[r["id"]] <= NEAR}
    values = sorted(r["field"] for r in have if r["field"] is not None)
    return {"entries": len(entries), "with_a_formation_energy": len(have), "field_is_a_number": len(values),
            "field_exactly_zero": sum(1 for v in values if v == 0), "field_median": round(float(np.median(values)), 4) if values else None,
            "computed_median": round(float(np.median([dist[r["id"]] for r in have])), 4) if have else None,
            "field_within_50_meV": len(field), "computed_within_50_meV": len(computed), "both_within": len(field & computed),
            "field_within_computed_beyond": len(field - computed), "computed_within_field_beyond": len(computed - field),
            "neither_within": len(have) - len(field | computed)}


# ---------------------------------------------------------------- the published lists
def published(name: str, block: dict, candidates: list, dist: dict, by_id: dict) -> tuple[dict, list]:
    """One published list against the computed hull: the record for the app, and one row per candidate. Every candidate
    must be an entry of the file with a formation energy; the step stops otherwise."""
    rows, table = {}, []
    for c in candidates:
        key = str(c.get("id"))
        if key not in dist:
            raise SystemExit(f"{name}: {key} ({c.get('formula')}) is not an entry of the file with a formation energy; nothing is written")
        d = round(float(dist[key]), DECIMALS)
        rows[key] = d
        table.append({"list": name, "rank": c.get("rank"), "id": key, "formula": c.get("formula"), "ehull_field": by_id[key]["field"],
                      "published_ehull": c.get("ehull"), "distance_eV_per_atom": d, "icsd": bool(by_id[key]["icsd"])})
    if len(rows) != len(candidates):
        raise SystemExit(f"{name}: an entry is listed twice; nothing is written")
    d = list(rows.values())
    record = {"round": block.get("round"), "date": block.get("date"), "listed": len(candidates), "found": len(rows),
              "within_50_meV": sum(1 for v in d if v <= NEAR), "beyond_50_meV": sum(1 for v in d if v > NEAR), "beyond_200_meV": sum(1 for v in d if v > FAR),
              "median_eV_per_atom": round(float(np.median(d)), DECIMALS) if d else None, "with_an_icsd_number": sum(1 for t in table if t["icsd"]),
              "distance_eV_per_atom": rows}
    return record, table


def lists_of(prog: dict) -> dict:
    """The two published lists as progress.json holds them: Storm's in the screen block, Hurricane's in its own."""
    screen = prog.get("screen") or {}
    hur = screen.get("hurricane") or {}
    return {"storm": (screen, list(screen.get("candidates") or [])), "hurricane": (hur, list(hur.get("candidates") or []))}


def build(entries: list, prog: dict, stamp: str, check=None) -> tuple[dict, list, dict]:
    """The record written to screen.hull, the table of candidates, and the counts of the file."""
    dist = distances(entries)
    by_id = {r["id"]: r for r in entries}
    record, table = {"about": ABOUT, "record": RECORD, "date": stamp[:10]}, []
    for name, (block, candidates) in lists_of(prog).items():
        record[name], rows = published(name, block, candidates, dist, by_id)
        table += rows
    counts = file_counts(entries, dist)
    record["file"] = {"source": "JARVIS-DFT 3D (dft_3d), as jarvis-tools serves it", **{k: counts[k] for k in (
        "entries", "field_within_50_meV", "computed_within_50_meV", "both_within", "field_within_computed_beyond", "computed_within_field_beyond")}}
    extra = {"counts": counts, "check": check(entries, dist, [t["id"] for t in table]) if check else None}
    return record, table, extra


def message(record: dict) -> str:
    s, h = record["storm"], record["hurricane"]
    return (f"{LOG_PREFIX} the pools of screening rounds 1 to 6 kept a JARVIS-DFT entry if the file's ehull field was at most 50 meV/atom, and that "
            f"field does not follow the convex hull of the file's own formation energies. Against the hull computed from those energies, "
            f"{s['beyond_50_meV']} of the {s['listed']} candidates on Storm's list (screening round {s['round']}) lie more than 50 meV/atom above it and "
            f"{s['beyond_200_meV']} more than 200 meV/atom; of the {h['listed']} on Hurricane's list (round {h['round']}), {h['beyond_50_meV']} and "
            f"{h['beyond_200_meV']}. Every candidate now shows its computed distance. No list, rank or score is changed, and both lists still stand as "
            f"published until a screening on a corrected pool replaces them")


def update_progress(record: dict, stamp: str, progress: Path) -> None:
    """Adds screen.hull and one log entry; a second run replaces both. Nothing else of the screen block is touched."""
    prog = json.loads(progress.read_text(encoding="utf-8"))
    prog["screen"]["hull"] = record
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(LOG_PREFIX)]
    P.add_log(prog, stamp, message(record))
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the run
def synthetic(prog: dict, seed: int = P.SEED) -> list:
    """Invented entries for --smoke and the tests: every published candidate with an invented formation energy, two
    invented compounds of the same elements in other proportions that compete with it, and one entry without a
    formation energy. Not data."""
    rng = np.random.default_rng(seed)
    out, n = [], 0
    for _, (_, candidates) in lists_of(prog).items():
        for c in candidates:
            comp = collections.Counter((c.get("atoms") or {}).get("elements") or [])
            if not comp:
                continue
            f = -float(rng.uniform(0.05, 1.0))
            out.append({"id": str(c["id"]), "comp": {e: float(v) for e, v in comp.items()}, "e_form": f, "gap": 0.0, "nat": float(sum(comp.values())),
                        "icsd": bool(c.get("icsd")), "field": num(c.get("ehull"))})
            for e in (sorted(comp)[0], sorted(comp)[-1]):      # the same elements with one of them doubled, sometimes lower in energy
                other = {x: float(v) * (2.0 if x == e else 1.0) for x, v in comp.items()}
                n += 1
                out.append({"id": f"SYN-{n}", "comp": other, "e_form": f * float(rng.uniform(0.2, 1.8)), "gap": 0.0, "nat": float(sum(other.values())),
                            "icsd": False, "field": float(rng.uniform(0, 3))})
    out.append({"id": "SYN-none", "comp": {"Na": 1.0, "Cl": 1.0}, "e_form": None, "gap": 5.0, "nat": 2.0, "icsd": True, "field": None})
    return out


def run(smoke: bool = False, output_dir: Path | None = None) -> dict:
    started, stamp = time.time(), P.now_iso()
    if smoke:
        results = Path(output_dir or Path(tempfile.gettempdir()) / "screen-hull-smoke")
        results.mkdir(parents=True, exist_ok=True)
        progress = results / "progress.json"
        progress.write_text(P.PROGRESS.read_text(encoding="utf-8"), encoding="utf-8")
        prog = json.loads(progress.read_text(encoding="utf-8"))
        entries, digest = synthetic(prog), None
    else:
        import screen as SC
        results, progress = Path(output_dir) if output_dir else P.RESULTS, P.PROGRESS
        prog = json.loads(progress.read_text(encoding="utf-8"))
        entries = [entry(r) for _, r in SC.load_rows().iterrows()]
        digest = same_file(file_digest(entries))
    record, table, extra = build(entries, prog, stamp, pymatgen_check)
    if not smoke and "skipped" in (extra["check"] or {"skipped": True}):
        raise SystemExit("the check against pymatgen's phase diagram did not run; nothing is written")
    out = {"run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local"), "module": VERSION, "smoke": smoke,
           "file": dict(extra["counts"], rows_sha256=digest, field_sha256=hashlib.sha256("".join(f"{r['id']}|{r['field']!r}\n" for r in entries).encode()).hexdigest()),
           "against_pymatgen": extra["check"], "screen": {"hull": record}, "candidates": table,
           "libraries": {"numpy": np.__version__, "scipy": __import__("scipy").__version__}}
    out["minutes"] = round((time.time() - started) / 60, 1)
    results.mkdir(parents=True, exist_ok=True)
    (results / RESULT).write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    update_progress(record, stamp, progress)
    P.log(message(record))
    text = json.dumps({k: out[k] for k in ("module", "smoke", "file", "against_pymatgen", "screen", "minutes")}, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)
    print("=== screen-hull begin")
    for i in range(0, len(text), 2000):
        print(f"shc|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== screen-hull end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="invented rows through every part; not a result")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.smoke:
        run(smoke=True, output_dir=args.output_dir)
    else:
        parser.error("choose --smoke; the step on the real file is python ml/pipeline.py screenhull")


if __name__ == "__main__":
    main()
