"""Screening: candidate superconductors found by our AI models, in two lists.

Conventional: Radar keeps the metals in the JARVIS-DFT database that look like conventional (phonon-mediated)
superconductors, and Storm 5.0 (Storm 4.0 with its 90% range) predicts their DFT Tc.
Unconventional (from round 2): Radar sends the materials that look like the unconventional families (cuprates, iron-
and nickel-based, heavy-fermion compounds and other oxides) to Hurricane 2.0, which predicts the chance that each
superconducts and its measured Tc if it does, with a 90% range for that Tc.

The lists hold only our own finds. A material is left out if
    - its composition is in SuperCon or 3DSC (the 3DSC file, JARVIS's copy of the SuperCon formulas and the SuperCon
      extract on the UCI repository, as far as each can be downloaded),
    - it already has a computed Tc: it is in the Alexandria or JARVIS electron-phonon data (which our models learn from
      or are tested on), or JARVIS-DFT lists a Tc for it,
    - it is in data/prior_claims.json, the superconductors reported or predicted by others that we track,
    - or (from round 2) it has exactly the elements of a known superconductor, so that every candidate is in a chemical
      system where no superconductor has been reported.
Compositions match when they have the same elements and every share is within 2 at.%; a "system" entry in the prior
claims matches every material made of exactly those elements.

Storm's pool: JARVIS-DFT 3D (OptB88vdW), no band gap, within 50 meV/atom of the convex hull, non-magnetic (under 0.5
μB per cell, as the training data), 2 to 4 elements, no hydrogen, noble gases or short-lived radioactive elements, no
larger than the training data's cells, and only elements that at least 20 training materials contain.
Hurricane's pool: within 50 meV/atom of the hull, a band gap of at most 1 eV (doping can make such a compound metallic),
magnetic or not, 2 to 5 elements, the same elements left out, up to 40 atoms in the cell, and only elements that at
least 20 of Hurricane's training materials contain. Of several polymorphs of one composition, the most stable is kept;
each list is ranked by its model's prediction, one candidate per chemical system.

The models are the released ones, refitted on all their data: Storm 1.0's trees and the graph network in use, averaged
as round 4 chose (Storm 4.0), calibrated to measured Tc with round 4's map; Storm 5.0's range is one width on
log(1 + Tc), set from Storm 4.0's out-of-fold errors on Alexandria (90%); Radar is the released design, and a material
goes to Storm if the probability that it belongs to an unconventional family is under one half.

Hurricane is the released design (round 2's H12: the chance that a compound superconducts times its Tc if it does),
refitted on all of its 3DSC data; its range is one width on log(1 + Tc) for the Tc if it superconducts, set from its
out-of-fold errors on the superconducting entries (90%).

The top 50 of each list go into progress.json with their crystal structures, for the app's Candidates view; every
material Storm scored is in results/screen_roundN_ranked.csv, every one Hurricane scored in
results/screen_roundN_hurricane.csv, and every excluded one, with the reason, in results/screen_roundN_excluded.csv.

Run from the repository root:  python ml/pipeline.py screen
(SCREEN_SMOKE=1: a quick check on small subsets that writes into a temporary folder)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

import gnn as G1
import gnn2 as G2
import hurricane as H
import hurricane2 as H2
import pipeline as P
import radar as RD
import storm3 as S3
import storm4 as S4
import storm5 as S5

ROUND = 2
SMOKE = os.environ.get("SCREEN_SMOKE") == "1"
POOL = "dft_3d"
GAP_MAX = 0.005          # eV (OptB88vdW): metals
EHULL_MAX = 0.05         # eV/atom above the convex hull
MAGMOM_MAX = 0.5         # μB per cell, as for the training data
N_ELEMENTS = (2, 4)
HUR_GAP_MAX = 1.0        # eV: Hurricane's pool also takes narrow-gap compounds, which doping can make metallic
HUR_ELEMENTS = (2, 5)
HUR_MAX_ATOMS = 40
MAX_ATOMS = 40           # and no larger than the training data's cells (their 99th percentile)
MIN_ELEMENT = 20         # an element must occur in at least this many training materials
NEAR = 0.02              # the same elements and every share within 2 at.%: the same material
TOP_N = 50
PER_SYSTEM = 1           # one candidate per chemical system in the published list
NOBLE = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
PRIOR = P.ROOT / "data" / "prior_claims.json"
UCI_URL = "https://archive.ics.uci.edu/static/public/464/superconductivty+data.zip"
JARVIS_PAGE = "https://www.ctcms.nist.gov/~knc6/jsmol/{}.html"
# space-group number -> point group (the last number of each range), and crystal systems
POINT_GROUPS = [(1, "1"), (2, "-1"), (5, "2"), (9, "m"), (15, "2/m"), (24, "222"), (46, "mm2"), (74, "mmm"), (80, "4"),
                (82, "-4"), (88, "4/m"), (98, "422"), (110, "4mm"), (122, "-42m"), (142, "4/mmm"), (146, "3"),
                (148, "-3"), (155, "32"), (161, "3m"), (167, "-3m"), (173, "6"), (174, "-6"), (176, "6/m"),
                (182, "622"), (186, "6mm"), (190, "-6m2"), (194, "6/mmm"), (199, "23"), (206, "m-3"), (214, "432"),
                (220, "-43m"), (230, "m-3m")]
SYSTEMS = [(2, "triclinic"), (15, "monoclinic"), (74, "orthorhombic"), (142, "tetragonal"), (167, "trigonal"),
           (194, "hexagonal"), (230, "cubic")]


def _num(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return np.nan
    return x if math.isfinite(x) else np.nan


def counts_of(elements) -> dict:
    u, c = np.unique(list(elements), return_counts=True)
    return {str(e): float(n) for e, n in zip(u, c)}


class Known:
    """Compositions that others have reported, computed or predicted, grouped by element set."""

    def __init__(self, name: str):
        self.name = name
        self.by_set: dict = {}
        self.systems: dict = {}
        self.n = 0

    def add(self, comp: dict, label: str) -> None:
        comp = {e: float(v) for e, v in comp.items() if float(v) > 0}
        if not comp:
            return
        key = tuple(sorted(comp))
        tot = sum(comp.values())
        self.by_set.setdefault(key, []).append((np.array([comp[e] / tot for e in key]), label))
        self.n += 1

    def add_system(self, elements, label: str) -> None:
        self.systems[tuple(sorted(elements))] = label
        self.n += 1

    def match(self, comp: dict) -> str | None:
        key = tuple(sorted(e for e, v in comp.items() if v > 0))
        if key in self.systems:
            return self.systems[key]
        tot = sum(comp[e] for e in key)
        x = np.array([comp[e] / tot for e in key])
        for v, label in self.by_set.get(key, []):
            if float(np.max(np.abs(v - x))) <= NEAR + 1e-9:
                return label
        return None


def _formulas(K: Known, formulas, label: str, S: Known | None = None, tcs=None) -> int:
    """Add every parseable formula to K; with S, the element set of every superconductor (Tc above 0) to S as well."""
    n0 = K.n
    tcs = list(tcs) if tcs is not None else [np.nan] * len(list(formulas))
    for f, tc in zip(formulas, tcs):
        try:
            comp = H.parse_formula(str(f).strip())
        except ValueError:
            continue
        K.add(comp, label)
        if S is not None and _num(tc) > 0:
            S.add_system(sorted(comp), label)
    return K.n - n0


def supercon_known(sources: list) -> tuple[Known, Known]:
    """Compositions with a SuperCon record: 3DSC (always), JARVIS's SuperCon formulas and the UCI extract (if they load);
    and the chemical systems of the superconductors among them."""
    K, S = Known("supercon"), Known("system")
    dsc = H.load_3dsc()
    sources.append({"name": "3DSC, SuperCon matched to Materials Project structures",
                    "n": _formulas(K, dsc["formula_sc"], "3DSC", S, pd.to_numeric(dsc["tc"], errors="coerce")),
                    "doi": "10.1038/s41597-023-02721-y", "commit": H.DSC_COMMIT[:7]})
    try:
        rows = P.load_dataset("supercon_chem")
        k = P.pick(rows[0].keys(), "formula", "comp", "composition", "material", "chemical_formula")
        kt = P.pick(rows[0].keys(), "Tc", "tc", "critical_temp", "tc_k")
        if k:
            sources.append({"name": "SuperCon formulas in JARVIS (supercon_chem)",
                            "n": _formulas(K, [r.get(k) for r in rows], "SuperCon", S if kt else None, [r.get(kt) for r in rows] if kt else None)})
        else:
            P.log(f"supercon_chem not used: no formula field in {sorted(rows[0].keys())}")
    except Exception as err:   # optional source
        P.log(f"supercon_chem not used: {err}")
    if not SMOKE and os.environ.get("SCREEN_OFFLINE") != "1":
        try:
            path = P.CACHE / "uci_superconductivity.zip"
            if not path.exists():
                req = urllib.request.Request(UCI_URL, headers={"User-Agent": "supercon-ml (github.com/diracmagic/supercon-ml)"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    path.write_bytes(r.read())
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            with zipfile.ZipFile(path) as z:
                name = next(n for n in z.namelist() if n.endswith("unique_m.csv"))
                with z.open(name) as fh:
                    um = pd.read_csv(fh)
            sources.append({"name": "SuperCon extract of K. Hamidieh (2018), UCI Machine Learning Repository",
                            "n": _formulas(K, um["material"], "SuperCon", S, um["critical_temp"] if "critical_temp" in um else None),
                            "doi": "10.1016/j.commatsci.2018.07.052", "sha256": sha[:12]})
        except Exception as err:   # optional source
            P.log(f"UCI SuperCon extract not used: {err}")
    sources.append({"name": "chemical systems with a known superconductor (from the lists above)", "n": len(S.systems)})
    return K, S


def computed_known(sources: list) -> Known:
    """Compositions with a computed Tc: every entry of the Alexandria and JARVIS electron-phonon data, before cleaning."""
    K = Known("computed")
    for name, label in (("alex_supercon", "Alexandria electron-phonon data"), ("supercon_3d", "JARVIS electron-phonon data")):
        rows = P.load_dataset(name)
        ka = P.pick(rows[0].keys(), "atoms", "structure")
        n0 = K.n
        for r in rows:
            try:
                K.add(counts_of(r[ka]["elements"]), label)
            except (KeyError, TypeError):
                continue
        sources.append({"name": label + f" ({name})", "n": K.n - n0})
    return K


def prior_known(sources: list) -> Known:
    K = Known("prior")
    if PRIOR.exists():
        d = json.loads(PRIOR.read_text(encoding="utf-8"))
        for e in d.get("materials", []):
            label = e.get("ref") or "prior"
            if e.get("system"):
                K.add_system(e["system"], label)
            elif e.get("formula"):
                try:
                    K.add(H.parse_formula(e["formula"]), label)
                except ValueError:
                    P.log(f"prior claim not parsed: {e['formula']}")
        sources.append({"name": "data/prior_claims.json, reported or predicted by others", "n": K.n})
    return K


# ---------------------------------------------------------------- the pool


def point_group(n: float) -> str:
    return next((pg for top, pg in POINT_GROUPS if n <= top), "") if n == n else ""


def crystal_system(n: float) -> str:
    return next((cs for top, cs in SYSTEMS if n <= top), "") if n == n else ""


def reduced_lengths(lat: np.ndarray) -> list:
    """The three shortest non-coplanar lattice vectors (successive minima), as for the training data's cells."""
    pts = []
    for i in range(-2, 3):
        for j in range(-2, 3):
            for k in range(-2, 3):
                v = i * lat[0] + j * lat[1] + k * lat[2]
                n = float(np.linalg.norm(v))
                if n > 1e-6:
                    pts.append((n, v))
    pts.sort(key=lambda t: t[0])
    basis = []
    for n, v in pts:
        if not basis:
            basis.append((n, v))
        elif len(basis) == 1:
            if np.linalg.norm(np.cross(basis[0][1], v)) > 1e-6 * n * basis[0][0]:
                basis.append((n, v))
        elif abs(np.dot(np.cross(basis[0][1], basis[1][1]), v)) > 1e-6 * n * basis[0][0] * basis[1][0]:
            basis.append((n, v))
            break
    return [t[0] for t in basis]


def radar_structure(atoms: dict, spg_number: float, spg_symbol: str) -> dict:
    """Radar's structure description (as hurricane.dsc_structure) from a JARVIS cell and its space group."""
    lat = np.asarray(atoms["lattice_mat"], float)
    n = len(atoms["elements"])
    vol = abs(float(np.linalg.det(lat)))
    lengths = reduced_lengths(lat)
    cs = crystal_system(spg_number)
    centring = {"I": "body-centered", "F": "face-centered", "A": "base-centered", "B": "base-centered",
                "C": "base-centered"}.get(str(spg_symbol or "").strip()[:1], "primitive")
    st = {"crystal_system": cs, "centring": centring, "point_group": point_group(spg_number), "lengths": lengths,
          "vpa": vol / n if n else np.nan}
    if cs == "cubic":
        st["c_over_a"] = 1.0
    elif cs in ("tetragonal", "hexagonal") and len(lengths) == 3:
        mult = {"primitive": 1, "base-centered": 2, "body-centered": 2, "face-centered": 4}[centring]
        s = sorted(lengths)
        a = s[0] if abs(s[0] - s[1]) < 2e-3 * s[1] else (s[1] if abs(s[1] - s[2]) < 2e-3 * s[2] else None)
        if a:
            base = a * a * (1.0 if cs == "tetragonal" else math.sqrt(3) / 2)
            st["c_over_a"] = vol * mult / base / a
    return st


def frac_coords(atoms: dict) -> np.ndarray:
    lat = np.asarray(atoms["lattice_mat"], float)
    xyz = np.asarray(atoms["coords"], float)
    f = xyz @ np.linalg.inv(lat) if atoms.get("cartesian") else xyz
    f = f - np.floor(f)
    f[f > 1 - 1e-6] = 0.0
    return f


def load_rows() -> pd.DataFrame:
    rows = P.load_dataset(POOL)
    keys = rows[0].keys()
    k = {name: P.pick(keys, *cands) for name, cands in {
        "id": ("jid", "id"), "atoms": ("atoms",), "gap": ("optb88vdw_bandgap",), "hull": ("ehull", "e_above_hull"),
        "mag": ("magmom_oszicar", "magmom_outcar", "magmom"), "spg": ("spg_symbol",), "spgn": ("spg_number",),
        "icsd": ("icsd",), "tc": ("Tc_supercon",)}.items()}
    missing = [n for n in ("id", "atoms", "gap", "hull", "mag") if k[n] is None]
    if missing:
        raise SystemExit(f"{POOL}: could not find fields {missing}; available: {sorted(keys)}")
    recs = []
    for r in rows:
        a = r.get(k["atoms"])
        if not isinstance(a, dict) or not a.get("elements") or not a.get("lattice_mat"):
            continue
        icsd = r.get(k["icsd"]) if k["icsd"] else None
        recs.append({"id": str(r.get(k["id"])), "atoms": a, "gap": _num(r.get(k["gap"])), "ehull": _num(r.get(k["hull"])),
                     "magmom": _num(r.get(k["mag"])), "spg": str(r.get(k["spg"]) or "") if k["spg"] else "",
                     "spg_number": _num(r.get(k["spgn"])) if k["spgn"] else np.nan,
                     "icsd": bool(icsd) and str(icsd).strip().lower() not in ("na", "none", "nan", "[]", ""),
                     "jarvis_tc": _num(r.get(k["tc"])) if k["tc"] else np.nan})
    df = pd.DataFrame(recs)
    df = df.assign(comp=df["atoms"].map(lambda a: counts_of(a["elements"])))
    df = df.assign(elements=df["comp"].map(sorted), nat=df["atoms"].map(lambda a: len(a["elements"])))
    return df.assign(chemsys=df["elements"].map("-".join))


BAD = {"H"} | NOBLE | S5.RADIOACTIVE


def storm_pool(df: pd.DataFrame, train_counts: dict, nat_max: int) -> tuple[pd.DataFrame, list]:
    steps = [("JARVIS-DFT 3D entries", len(df))]
    df = df[df["gap"] <= GAP_MAX]
    steps.append(("metals (no OptB88vdW band gap)", len(df)))
    df = df[df["ehull"] <= EHULL_MAX]
    steps.append((f"within {int(EHULL_MAX * 1000)} meV/atom of the convex hull", len(df)))
    df = df[df["magmom"].abs() <= MAGMOM_MAX]
    steps.append((f"non-magnetic (under {MAGMOM_MAX} μB per cell)", len(df)))
    df = df[df["elements"].map(lambda e: N_ELEMENTS[0] <= len(e) <= N_ELEMENTS[1] and not (set(e) & BAD))]
    steps.append((f"{N_ELEMENTS[0]} to {N_ELEMENTS[1]} elements, no hydrogen, noble gases or short-lived radioactive elements", len(df)))
    df = df[df["nat"] <= nat_max]
    steps.append((f"up to {nat_max} atoms in the cell", len(df)))
    df = df[df["elements"].map(lambda e: all(train_counts.get(x, 0) >= MIN_ELEMENT for x in e))]
    steps.append((f"only elements in at least {MIN_ELEMENT} training materials", len(df)))
    return df.reset_index(drop=True), steps


def hurricane_pool(df: pd.DataFrame, train_counts: dict) -> tuple[pd.DataFrame, list]:
    steps = [("JARVIS-DFT 3D entries", len(df))]
    df = df[df["ehull"] <= EHULL_MAX]
    steps.append((f"within {int(EHULL_MAX * 1000)} meV/atom of the convex hull", len(df)))
    df = df[df["gap"] <= HUR_GAP_MAX]
    steps.append((f"a band gap of at most {HUR_GAP_MAX:g} eV, magnetic or not", len(df)))
    df = df[df["elements"].map(lambda e: HUR_ELEMENTS[0] <= len(e) <= HUR_ELEMENTS[1] and not (set(e) & BAD))]
    steps.append((f"{HUR_ELEMENTS[0]} to {HUR_ELEMENTS[1]} elements, no hydrogen, noble gases or short-lived radioactive elements", len(df)))
    df = df[df["nat"] <= HUR_MAX_ATOMS]
    steps.append((f"up to {HUR_MAX_ATOMS} atoms in the cell", len(df)))
    df = df[df["elements"].map(lambda e: all(train_counts.get(x, 0) >= MIN_ELEMENT for x in e))]
    steps.append((f"only elements in at least {MIN_ELEMENT} of Hurricane's training materials", len(df)))
    return df.reset_index(drop=True), steps


def one_per_composition(df: pd.DataFrame) -> pd.DataFrame:
    """Of several polymorphs of one composition, the most stable."""
    df = df.assign(key=df["comp"].map(P._composition_key)).sort_values(["key", "ehull", "id"])
    return df.drop_duplicates("key", keep="first").drop(columns="key").reset_index(drop=True)


def exclude(df: pd.DataFrame, known: list) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Leave out everything others have reported, computed or predicted; the first matching list gives the reason."""
    reason, source = [], []
    for comp, jtc in zip(df["comp"], df["jarvis_tc"]):
        r = s = None
        for K in known:
            hit = K.match(comp)
            if hit:
                r, s = K.name, hit
                break
        if r is None and jtc == jtc:
            r, s = "computed", "JARVIS-DFT lists a Tc"
        reason.append(r)
        source.append(s)
    df = df.assign(reason=reason, source=source)
    out = df[df["reason"].notna()]
    counts = {name: int((out["reason"] == name).sum()) for name in ("supercon", "computed", "prior", "system")}
    counts["total"] = int(len(out))
    return df[df["reason"].isna()].drop(columns=["reason", "source"]).reset_index(drop=True), out.reset_index(drop=True), counts


# ---------------------------------------------------------------- the models


def _released(path: Path, key: str, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(key) or default
    except (OSError, ValueError):
        return default


def storm_combination(oof: dict) -> tuple[str, str]:
    """Round 4's released combination of Storm 1.0 and the graph network (S3 unless the results say otherwise)."""
    r4 = P.RESULTS / "storm_round4.json"
    best = _released(r4, "best", "S3")
    names = {"S1": "Storm 1.0 and the graph network, averaged", "S2": "Storm 1.0 and the graph network, averaged on log(1 + Tc)",
             "S3": "Storm 1.0, the graph network and its Allen–Dynes route, averaged"}
    return (best if best in names else "S3"), names.get(best, names["S3"])


def combine(kind: str, s_tc, g_tc, g_lam, g_wlog) -> np.ndarray:
    if kind == "S1":
        return 0.5 * (s_tc + g_tc)
    if kind == "S2":
        return np.expm1(0.5 * (np.log1p(np.clip(s_tc, 0, None)) + np.log1p(np.clip(g_tc, 0, None))))
    g_ad = P.allen_dynes(np.clip(g_lam, 0, None), np.clip(g_wlog, 0, None))
    return (s_tc + g_tc + g_ad) / 3.0


def calibration_map():
    """Round 4's released map from Storm's DFT Tc to measured Tc (the gradient-boosting correction unless the results
    name another)."""
    r4 = P.RESULTS / "storm_round4.json"
    cid = ((_released(r4, "calibration", {}) or {}).get("best") or {}).get("id", "K5")
    return next((c for c in S3.CANDIDATES if c["id"] == cid), next(c for c in S3.CANDIDATES if c["id"] == "K5"))


def cal_frame(tc, lam, wlog, comps, feats: pd.DataFrame) -> pd.DataFrame:
    m = pd.DataFrame({"storm": np.clip(tc, 0, None), "lam": np.maximum(lam, 0.0), "wlog": np.maximum(wlog, 1.0)})
    m["mag3d"] = [sum(n for e, n in c.items() if e in S3.MAG3D) / sum(c.values()) for c in comps]
    for c in ("d_fraction", "p_fraction", "light_fraction", "vec", "inv_sqrt_mass"):
        m[c] = feats[c].to_numpy(float)
    m["n_elements"] = [float(len(c)) for c in comps]
    m["log_storm"] = np.log1p(m["storm"])
    m["log_ad"] = np.log1p(P.allen_dynes(m["lam"], m["wlog"]))
    return m


def radar_design() -> dict:
    best = _released(P.RESULTS / "radar_round1.json", "best", None)
    if isinstance(best, dict) and best.get("X"):
        return {"id": best.get("id"), "name": best.get("name"), "X": best["X"], "params": dict(best["params"]),
                "balanced": best.get("balanced"), "bags": best.get("bags", 1), "calibrate": best.get("calibrate")}
    return {"id": "R4", "name": "Composition + structure + physics + element fractions", "X": "ABCD", "params": RD.PARAMS}


def radar_scores(pool: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Radar, refitted on all of its 3DSC data (as radar.run builds them), applied to the pool."""
    dsc = H.load_3dsc()
    unc, con = H.build_frame(dsc, RD.UNCONV), H.build_frame(dsc, RD.CONV)
    df = pd.concat([unc.assign(y=1), con.assign(y=0)], ignore_index=True)
    df = df.drop_duplicates(subset="formula_sc", keep=False).reset_index(drop=True)
    y, groups = df["y"].to_numpy(int), df["group"].to_numpy()
    symbols = {e for c in df["comp"] for e in c} | {e for c in pool["comp"] for e in c}
    table = P.element_table(sorted(symbols))
    blocks = H.feature_blocks(df, table, [H.dsc_structure(r) for _, r in df.iterrows()])
    counts = {}
    for c in df["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = H.element_fractions(df["comp"], elements)
    c = radar_design()
    X = np.hstack([blocks[b].to_numpy(float) for b in c["X"]])
    final = RD.fit_design(c, X, y, groups, P.SEED + 500)
    sts = [radar_structure(a, n, s) for a, n, s in zip(pool["atoms"], pool["spg_number"], pool["spg"])]
    pb = H.feature_blocks(pool, table, sts)
    pb["D"] = H.element_fractions(pool["comp"], elements)
    Xp = np.hstack([pb[b].to_numpy(float) for b in c["X"]])
    return RD.predict_design(final, Xp), {"design": c.get("name"), "id": c.get("id"), "n_train": int(len(y))}


def storm_scores(train: pd.DataFrame, pool: pd.DataFrame, table: pd.DataFrame) -> dict:
    from sklearn.model_selection import GroupKFold

    t0 = time.time()
    base_t = P.featurize(train, table)
    phys_t = P.physics_features(train, base_t)
    D_t = np.hstack([base_t.to_numpy(float), phys_t.to_numpy(float)])
    base_p = P.featurize(pool, table)
    phys_p = P.physics_features(pool, base_p)
    D_p = np.hstack([base_p.to_numpy(float), phys_p.to_numpy(float)])
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    # out of fold on the same folds as every Storm round: for the 90% range and the calibration map
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(D_t, y_tc, groups))
    o_tc = np.clip(P.cv_predict_stage(D_t, y_tc, splits, P.STORM1_PARAMS), 0, None)
    o_lam = P.cv_predict_stage(D_t, y_lam, splits, P.STORM1_PARAMS, log_target=False)
    o_wlog = P.cv_predict_stage(D_t, y_wlog, splits, P.STORM1_PARAMS, log_target=False)
    fold_of = np.zeros(len(y_tc), int)
    for k, (_, te) in enumerate(splits):
        fold_of[te] = k + 1
    cfg, design, gver, saved, seeds = S4.gnn_design()
    Ttr = np.column_stack([np.log1p(y_tc), np.log(y_lam), np.log(y_wlog)]).astype(np.float32)
    go = S4.saved_gnn(saved, train, fold_of)
    if go is not None:
        gsource = f"saved out-of-fold predictions ({saved.name})"
    else:   # only if the saved predictions are missing: retrain out of fold
        g = G1.build_graphs(train, table)
        glob = G2.descriptors(train, table)[0] if cfg.get("hybrid") else None
        outs = [G2.train_all(g, Ttr, y_tc, groups, splits, cfg, glob, seed=s + 1, epochs=G1.EPOCHS)[0] for s in range(seeds)]
        go = {k: np.mean([o[k] for o in outs], axis=0) for k in ("tc", "lambda", "wlog")}
        gsource = f"retrained out of fold ({seeds} seeds)"
    kind, kind_name = storm_combination(go)
    oof = np.clip(combine(kind, o_tc, go["tc"], go["lambda"], go["wlog"]), 0, None)
    lam_oof, wlog_oof = 0.5 * (o_lam + go["lambda"]), 0.5 * (o_wlog + go["wlog"])
    P.log(f"Storm 4.0 out of fold ({kind}, graph network from {gsource}): Tc MAE {np.mean(np.abs(oof - y_tc)):.3f} K")
    # Storm 5.0's range: one width on log(1 + Tc) (U2, as released; U0 would be one width in K) from the out-of-fold errors
    unc = _released(P.RESULTS / "storm_round5.json", "best", "U2")
    on_log = unc != "U0"
    if unc not in ("U0", "U2"):
        P.log(f"Storm round 5 released {unc}; the screening uses U2, one width on log(1 + Tc)")
    fwd = np.log1p if on_log else (lambda v: np.asarray(v, float))   # noqa: E731
    back = np.expm1 if on_log else (lambda v: np.asarray(v, float))   # noqa: E731
    width = S5.cq(np.abs(fwd(y_tc) - fwd(oof)), S5.ALPHA)
    lo_o, hi_o = back(fwd(oof) - width), back(fwd(oof) + width)
    cover = float(np.mean((y_tc >= np.clip(lo_o, 0, None)) & (y_tc <= hi_o)))
    # the calibration map, fitted on the matched 3DSC materials from the out-of-fold predictions
    feats_t = phys_t.assign(n_elements=base_t["n_elements"])
    m = S3.matched_set(train, feats_t, oof, lam_oof, wlog_oof)
    cal = calibration_map()
    cal_fit = cal["fit"](m) if len(m) >= 10 else None
    P.log(f"range width {width:.4f} " + ("on log(1 + Tc)" if on_log else "K") + f", out-of-fold coverage {cover:.3f}; calibration {cal['id']} on {len(m)} "
          f"matched materials ({time.time() - t0:.0f} s)")
    # the released models, refitted on all of Alexandria, for the pool
    n_t, n_p = len(train), len(pool)
    X = np.vstack([D_t, D_p])
    split = [(np.arange(n_t), np.arange(n_t, n_t + n_p))]
    pad = lambda v: np.concatenate([v, np.zeros(n_p)])   # noqa: E731  (the pool's rows are never trained on)
    s_tc = np.clip(P.cv_predict_stage(X, pad(y_tc), split, P.STORM1_PARAMS), 0, None)[n_t:]
    s_lam = P.cv_predict_stage(X, pad(y_lam), split, P.STORM1_PARAMS, log_target=False)[n_t:]
    s_wlog = P.cv_predict_stage(X, pad(y_wlog), split, P.STORM1_PARAMS, log_target=False)[n_t:]
    both = pd.concat([train[["id", "atoms", "chemsys"]], pool[["id", "atoms", "chemsys"]]], ignore_index=True)
    g = G1.build_graphs(both, table)
    glob = G2.descriptors(both, table)[0] if cfg.get("hybrid") else None
    T = np.zeros((n_t + n_p, 3), np.float32)
    T[:n_t] = Ttr
    outs = []
    for s in range(seeds):
        o, rec = G2.train_all(g, T, pad(y_tc), both["chemsys"].to_numpy(), split, cfg, glob, seed=s + 1, epochs=G1.EPOCHS)
        outs.append({k: o[k][n_t:] for k in ("tc", "lambda", "wlog")})
        P.log(f"graph network seed {s + 1} on all of Alexandria: {rec['seconds']} s")
    gp = {k: np.mean([o[k] for o in outs], axis=0) for k in ("tc", "lambda", "wlog")}
    tc = np.clip(combine(kind, s_tc, gp["tc"], gp["lambda"], gp["wlog"]), 0, None)
    lam, wlog = 0.5 * (s_lam + gp["lambda"]), 0.5 * (s_wlog + gp["wlog"])
    lo, hi = np.clip(back(fwd(tc) - width), 0, None), back(fwd(tc) + width)
    feats_p = phys_p.assign(n_elements=base_p["n_elements"])
    tc_cal = cal["pred"](cal_fit, cal_frame(tc, lam, wlog, list(pool["comp"]), feats_p)) if cal_fit is not None else np.full(n_p, np.nan)
    return {"tc": tc, "lo": lo, "hi": hi, "tc_cal": np.asarray(tc_cal, float), "lambda": lam, "wlog": wlog,
            "storm1": s_tc, "gnn": gp["tc"], "gnn_ad": P.allen_dynes(np.clip(gp["lambda"], 0, None), np.clip(gp["wlog"], 0, None)),
            "info": {"combination": kind, "combination_name": kind_name, "gnn": design, "gnn_version": gver, "seeds": seeds,
                     "gnn_oof": gsource, "range_design": "U2" if on_log else "U0", "width_log": round(float(width), 4) if on_log else None,
                     "width_k": None if on_log else round(float(width), 3), "oof_coverage": round(cover, 3),
                     "oof_mae": round(float(np.mean(np.abs(oof - y_tc))), 3), "calibration": cal["name"],
                     "calibration_id": cal["id"], "n_matched": int(len(m)), "n_train": int(n_t)}}


H12 = {"id": "H12", "name": "Hurricane 1.0 + structure types, in two parts", "settings": "probability times Tc",
       "X": "ABCDE", "params": H.PARAMS, "two_part": "mean"}
H4 = {"id": "H4", "name": "Composition + structure + physics + element fractions", "settings": "Hurricane 1.0",
      "X": "ABCD", "params": H.PARAMS}


def hurricane_design() -> tuple[dict, str]:
    """The released Hurricane design and its version: round 2's best if it was released, else Hurricane 1.0; with no
    results file (the smoke test), Hurricane 2.0 as released (H12)."""
    try:
        d = json.loads((P.RESULTS / "hurricane_round2.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(H12), "2.0"
    best = d.get("best") or {}
    if d.get("adopted") and best.get("X"):
        keep = ("id", "name", "settings", "X", "params", "two_part", "per_family", "bags")
        c = {k: best[k] for k in keep if best.get(k) is not None}
        c["params"] = dict(c.get("params") or H.PARAMS)
        return c, str(d.get("version") or "2.0")
    return dict(H4), "1.0"


def family_guess(comp: dict) -> str:
    """The unconventional family that a material's elements point to (shown with each candidate; also picks the model of
    a per-family Hurricane design)."""
    els = set(comp)
    if {"Cu", "O"} <= els:
        return "cuprate"
    if els & {"Fe", "Ni"} and els & (H2.PNICTOGEN | H2.CHALCOGEN):
        return "iron-based"
    if els & H2.HF_F:
        return "heavy-fermion"
    if "O" in els:
        return "other oxide"
    return "other"


def hur_parts(d, X, fam) -> tuple[np.ndarray, np.ndarray]:
    """The two parts of a Hurricane prediction for each row: the chance that the compound superconducts (NaN for a
    one-part design) and its Tc if it does."""
    if d.c.get("per_family"):
        p, t = np.full(len(X), np.nan), np.zeros(len(X))
        for f in np.unique(fam):
            m = fam == f
            p[m], t[m] = hur_parts(d.parts.get(f, d.pooled), X[m], fam[m])
        return p, t
    tc = np.clip(np.expm1(H._predict(d.reg, X)), 0, None)
    if d.c.get("two_part") and d.clf is not None:
        return d.clf.predict_proba(X)[:, 1], tc
    return np.full(len(X), np.nan), tc


def hurricane_scores(pool: pd.DataFrame) -> dict:
    """The released Hurricane design, refitted on all of its 3DSC data (as hurricane2.run builds them), applied to the
    materials Radar sends it. Its range is one width on log(1 + Tc) for the Tc if a compound superconducts, from the
    out-of-fold errors on the superconducting entries (5 folds by parent compound, as in every Hurricane round)."""
    from sklearn.model_selection import GroupKFold

    t0 = time.time()
    c, version = hurricane_design()
    dsc = H.load_3dsc()
    hur = H.build_frame(dsc, set(H.FAMILY_OF_CLASS))
    y, groups, fam = hur["tc"].to_numpy(float), hur["group"].to_numpy(), hur["family"].to_numpy()
    table = P.element_table(sorted({e for cc in hur["comp"] for e in cc} | {e for cc in pool["comp"] for e in cc}))
    blocks = H.feature_blocks(hur, table, [H.dsc_structure(r) for _, r in hur.iterrows()])
    counts = {}
    for cc in hur["comp"]:
        for e in cc:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = H.element_fractions(hur["comp"], elements)
    blocks["E"] = pd.DataFrame([H2.structure_types(cc) for cc in hur["comp"]])
    X = np.hstack([blocks[b].to_numpy(float) for b in c["X"]])
    o_p, o_tc = np.full(len(y), np.nan), np.zeros(len(y))
    for k, (tr, te) in enumerate(GroupKFold(n_splits=P.N_FOLDS).split(X, y, groups)):
        d = H2.Design(c, P.SEED + k).fit(X[tr], y[tr], fam[tr])
        o_p[te], o_tc[te] = hur_parts(d, X[te], fam[te])
    sc = y > 0
    width = S5.cq(np.abs(np.log1p(y[sc]) - np.log1p(o_tc[sc])), S5.ALPHA)
    cover = float(np.mean((y[sc] >= np.clip(np.expm1(np.log1p(o_tc[sc]) - width), 0, None)) &
                          (y[sc] <= np.expm1(np.log1p(o_tc[sc]) + width))))
    likely = np.isfinite(o_p) & (o_p >= 0.5)
    check = {"n": int(len(y)), "n_sc": int(sc.sum()), "share_sc": round(float(sc.mean()), 3), "n_likely": int(likely.sum()),
             "share_sc_likely": round(float(sc[likely].mean()), 3) if likely.any() else None,
             "share_sc_unlikely": round(float(sc[np.isfinite(o_p) & ~likely].mean()), 3) if (np.isfinite(o_p) & ~likely).any() else None,
             "about": ("out of fold on the 3DSC entries: of the compounds Hurricane gave at least an even chance, the share that "
                       "superconduct, against the share among the others")}
    P.log(f"Hurricane {version} ({c['id']}) out of fold: range width {width:.4f} on log(1 + Tc), coverage {cover:.3f} on "
          f"{int(sc.sum())} superconductors; {check['share_sc_likely']} of the {check['n_likely']} entries given at least an "
          f"even chance superconduct, against {check['share_sc_unlikely']} of the others ({time.time() - t0:.0f} s)")
    final = H2.Design(c, P.SEED + 500).fit(X, y, fam)
    n_p = len(pool)
    info = {"version": version, "id": c["id"], "name": c["name"], "settings": c.get("settings"),
            "two_part": c.get("two_part"), "n_train": int(len(y)), "n_train_sc": int(sc.sum()),
            "width_log": round(float(width), 4), "oof_coverage": round(cover, 3), "check": check}
    if not n_p:
        return {"tc": np.zeros(0), "p_sc": np.zeros(0), "tc_sc": np.zeros(0), "lo": np.zeros(0), "hi": np.zeros(0),
                "family": [], "types": [], "info": info}
    sts = [radar_structure(a, n, s) for a, n, s in zip(pool["atoms"], pool["spg_number"], pool["spg"])]
    pb = H.feature_blocks(pool, table, sts)
    pb["D"] = H.element_fractions(pool["comp"], elements)
    pb["E"] = pd.DataFrame([H2.structure_types(cc) for cc in pool["comp"]], columns=list(H2.TYPE_RATIONALE))
    Xp = np.hstack([pb[b].to_numpy(float) for b in c["X"]])
    if Xp.shape[1] != X.shape[1]:
        raise SystemExit(f"Hurricane's inputs for the pool ({Xp.shape[1]}) do not match its training inputs ({X.shape[1]})")
    pf = np.array([family_guess(cc) for cc in pool["comp"]])
    tc = np.clip(final.predict(Xp, pf), 0, None)
    p_sc, tc_sc = hur_parts(final, Xp, pf)
    lo, hi = np.clip(np.expm1(np.log1p(tc_sc) - width), 0, None), np.expm1(np.log1p(tc_sc) + width)
    types = [[k for k, v in H2.structure_types(cc).items() if v > 0] for cc in pool["comp"]]
    return {"tc": tc, "p_sc": p_sc, "tc_sc": tc_sc, "lo": lo, "hi": hi, "family": list(pf), "types": types, "info": info}


# ---------------------------------------------------------------- run


def _r(v, n: int):
    """v rounded to n places, or None if it is missing."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, n) if math.isfinite(v) else None


def crystal(a: dict) -> dict:
    return {"lattice": np.round(np.asarray(a["lattice_mat"], float), 4).tolist(), "elements": list(a["elements"]),
            "frac": np.round(frac_coords(a), 5).tolist()}


def top_rows(ranked: pd.DataFrame, rows) -> list:
    """The first TOP_N of the given rows (already in order), one per chemical system."""
    top, per = [], {}
    for i in rows:
        cs = ranked.at[i, "chemsys"]
        if per.get(cs, 0) >= PER_SYSTEM:
            continue
        per[cs] = per.get(cs, 0) + 1
        top.append(i)
        if len(top) == TOP_N:
            break
    return top


def base_record(rank: int, r: pd.Series) -> dict:
    spg = f"{r['spg']} ({int(r['spg_number'])})" if r["spg"] and r["spg_number"] == r["spg_number"] else (r["spg"] or None)
    return {"rank": rank, "formula": r["formula"], "id": r["jid"],
            "url": JARVIS_PAGE.format(r["jid"]) if str(r["jid"]).startswith("JVASP-") else None, "spg": spg,
            "ehull": _r(r["ehull"], 3), "icsd": bool(r["icsd"])}


def run() -> None:
    import sklearn

    t_start = time.time()
    _, frames = P.load_clean()
    train = frames["alexandria"]
    if SMOKE:
        train = train.sample(n=min(500, len(train)), random_state=P.SEED).reset_index(drop=True)
    train_counts = {}
    for els in train["elements"]:
        for e in els:
            train_counts[e] = train_counts.get(e, 0) + 1
    nat_max = int(min(MAX_ATOMS, np.percentile(train["atoms"].map(lambda a: len(a["elements"])), 99)))
    hur_counts = {}
    for cc in H.build_frame(H.load_3dsc(), set(H.FAMILY_OF_CLASS))["comp"]:
        for e in cc:
            hur_counts[e] = hur_counts.get(e, 0) + 1
    rows = load_rows()
    spool, s_steps = storm_pool(rows, train_counts, nat_max)
    hpool, h_steps = hurricane_pool(rows, hur_counts)
    for tag, steps in (("Storm", s_steps), ("Hurricane", h_steps)):
        for name, n in steps:
            P.log(f"{tag}'s pool: {name}: {n:,}")
    sources = []
    K, S = supercon_known(sources)
    known = [K, computed_known(sources), prior_known(sources), S]
    spool, s_out, s_counts = exclude(spool, known)
    hpool, h_out, h_counts = exclude(hpool, known)
    for tag, cnt in (("Storm", s_counts), ("Hurricane", h_counts)):
        P.log(f"{tag}'s pool: left out {cnt['total']:,} materials that others have reported, computed or predicted, or "
              f"that share the elements of a known superconductor: {cnt}")
    n_s, n_h = len(spool), len(hpool)
    spool, hpool = one_per_composition(spool), one_per_composition(hpool)
    P.log(f"Storm's pool: {len(spool):,} compositions ({n_s - len(spool):,} less stable polymorphs dropped); Hurricane's: "
          f"{len(hpool):,} ({n_h - len(hpool):,} dropped)")
    if SMOKE:
        spool, hpool = spool.head(300).reset_index(drop=True), hpool.head(300).reset_index(drop=True)
    if not len(spool):
        raise SystemExit("Storm's pool is empty")
    # Radar, once for every material in either pool: under one half goes to Storm, the rest to Hurricane
    both = pd.concat([spool, hpool], ignore_index=True).drop_duplicates("id").reset_index(drop=True)
    p_all, radar_info = radar_scores(both)
    p_of = dict(zip(both["id"], np.asarray(p_all, float)))
    p_s = spool["id"].map(p_of).to_numpy(float)
    p_h = hpool["id"].map(p_of).to_numpy(float)
    to_storm = p_s < 0.5
    sent = p_h >= 0.5
    hsel = hpool[sent].reset_index(drop=True)
    P.log(f"Radar: {int(to_storm.sum()):,} of the {len(spool):,} in Storm's pool look conventional; {int(sent.sum()):,} of "
          f"the {len(hpool):,} in Hurricane's pool look unconventional")
    table = P.element_table(sorted(set(train_counts) | {e for els in spool["elements"] for e in els}))
    st = storm_scores(train, spool, table)
    hu = hurricane_scores(hsel)
    # Storm: every material in its pool is scored; the list takes those Radar sends to Storm
    ranked = pd.DataFrame({
        "jid": spool["id"], "formula": [S3.pretty(c) for c in spool["comp"]], "chemsys": spool["chemsys"], "nat": spool["nat"],
        "spg": spool["spg"], "spg_number": spool["spg_number"], "ehull": spool["ehull"], "icsd": spool["icsd"],
        "p_unconventional": p_s, "model": np.where(to_storm, "Storm", "Hurricane"), "storm_tc": st["tc"],
        "lo": st["lo"], "hi": st["hi"], "tc_calibrated": st["tc_cal"], "lambda": st["lambda"], "wlog": st["wlog"],
        "storm1_tc": st["storm1"], "gnn_tc": st["gnn"], "gnn_allen_dynes_tc": st["gnn_ad"]})
    ranked = ranked.sort_values(["model", "storm_tc"], ascending=[False, False]).reset_index(drop=True)
    by_id = dict(zip(rows["id"], rows["atoms"]))
    cands = []
    for rank, i in enumerate(top_rows(ranked, ranked.index[ranked["model"] == "Storm"]), 1):
        r = ranked.loc[i]
        c = dict(base_record(rank, r), tc=_r(r["storm_tc"], 2), lo=_r(r["lo"], 2), hi=_r(r["hi"], 2),
                 tc_cal=_r(r["tc_calibrated"], 2), **{"lambda": _r(r["lambda"], 3)}, wlog=_r(r["wlog"], 1),
                 p_conventional=_r(1 - float(r["p_unconventional"]), 3), atoms=crystal(by_id[r["jid"]]))
        cands.append({k: v for k, v in c.items() if v is not None})
    # Hurricane: the materials Radar sends it, highest predicted Tc (the chance times the Tc if it superconducts) first
    hr = pd.DataFrame({
        "jid": hsel["id"], "formula": [S3.pretty(c) for c in hsel["comp"]], "chemsys": hsel["chemsys"], "nat": hsel["nat"],
        "spg": hsel["spg"], "spg_number": hsel["spg_number"], "ehull": hsel["ehull"], "gap": hsel["gap"],
        "magmom": hsel["magmom"], "icsd": hsel["icsd"], "p_unconventional": p_h[sent], "family": hu["family"],
        "hurricane_tc": hu["tc"], "p_sc": hu["p_sc"], "tc_sc": hu["tc_sc"], "lo": hu["lo"], "hi": hu["hi"],
        "types": [";".join(t) for t in hu["types"]]})
    hr = hr.sort_values(["hurricane_tc", "tc_sc", "jid"], ascending=[False, False, True]).reset_index(drop=True)
    hcands = []
    for rank, i in enumerate(top_rows(hr, hr.index), 1):
        r = hr.loc[i]
        c = dict(base_record(rank, r), tc=_r(r["hurricane_tc"], 2), tc_sc=_r(r["tc_sc"], 2), lo=_r(r["lo"], 2),
                 hi=_r(r["hi"], 2), p_sc=_r(r["p_sc"], 3), p_unconventional=_r(r["p_unconventional"], 3),
                 family=r["family"] if r["family"] != "other" else None, gap=_r(r["gap"], 2),
                 magnetic=True if abs(float(r["magmom"])) > MAGMOM_MAX else None,
                 types=[t for t in str(r["types"]).split(";") if t] or None, atoms=crystal(by_id[r["jid"]]))
        hcands.append({k: v for k, v in c.items() if v is not None})
    stamp = P.now_iso()
    s_rule = (f"metals within {int(EHULL_MAX * 1000)} meV/atom of the convex hull, non-magnetic, {N_ELEMENTS[0]} to "
              f"{N_ELEMENTS[1]} elements, up to {nat_max} atoms in the cell, elements our training data covers; the list "
              f"holds the {int(to_storm.sum()):,} that Radar sends to Storm, one per chemical system")
    h_rule = (f"within {int(EHULL_MAX * 1000)} meV/atom of the convex hull, a band gap of at most {HUR_GAP_MAX:g} eV, magnetic "
              f"or not, {HUR_ELEMENTS[0]} to {HUR_ELEMENTS[1]} elements, up to {HUR_MAX_ATOMS} atoms in the cell, elements "
              f"Hurricane's training data covers; the list "
              f"holds the {int(sent.sum()):,} that Radar sends to Hurricane, one per chemical system")
    rv, sv, hv = radar_version(), storm_version(), hu["info"]["version"]
    out = {
        "run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND,
        "models": [f"Radar {rv}", f"Storm {sv}", f"Hurricane {hv}"],
        "pool": {"source": "JARVIS-DFT", "dataset": POOL, "steps": [{"step": s, "n": n} for s, n in s_steps],
                 "n_screened": int(len(spool)), "n_storm": int(to_storm.sum()), "n_hurricane": int((~to_storm).sum()),
                 "rule": s_rule},
        "excluded": s_counts, "sources": sources, "radar": radar_info, "storm": st["info"],
        "rule": ("only our own finds: nothing that SuperCon, 3DSC, the Alexandria or JARVIS electron-phonon data or our list "
                 "of others' claims already has, and nothing made of exactly the elements of a known superconductor"),
        "caveat": ("Storm predicts the DFT (Allen-Dynes, μ* = 0.10) Tc of a structure that DFT says is stable or nearly so; "
                   "a candidate is a prediction until a full electron-phonon calculation and then an experiment check it"),
        "hurricane": {
            "model": f"Hurricane {hv}", "design": hu["info"],
            "pool": {"source": "JARVIS-DFT", "dataset": POOL, "steps": [{"step": s, "n": n} for s, n in h_steps],
                     "n_screened": int(len(hpool)), "n_sent": int(sent.sum()), "rule": h_rule},
            "excluded": h_counts, "candidates": hcands,
            "caveat": ("Hurricane learned measured Tc from cuprates, iron-based, heavy-fermion compounds and other oxides; it "
                       "gives the chance that a compound superconducts and its Tc if it does. Many of these compounds would "
                       "need doping or pressure, and a candidate is a prediction until an experiment checks it")},
        "scikit_learn": sklearn.__version__, "minutes": round((time.time() - t_start) / 60, 1), "candidates": cands,
    }
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="screen-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"screen_round{ROUND}.json").write_text(json.dumps(out, indent=1, default=float, ensure_ascii=False) + "\n")
    ranked.round(5).to_csv(results / f"screen_round{ROUND}_ranked.csv", index=False)
    hr.round(5).to_csv(results / f"screen_round{ROUND}_hurricane.csv", index=False)
    ex = pd.concat([s_out.assign(pool="Storm"), h_out.assign(pool="Hurricane")], ignore_index=True)
    pd.DataFrame({"jid": ex["id"], "formula": [S3.pretty(c) for c in ex["comp"]], "pool": ex["pool"], "reason": ex["reason"],
                  "matched": ex["source"]}).to_csv(results / f"screen_round{ROUND}_excluded.csv", index=False)
    update_progress(out, progress)
    if SMOKE:
        P.log(f"screen smoke test passed; outputs in {results.parent}")


def radar_version() -> str:
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8")) if P.PROGRESS.exists() else {}
    return str((prog.get("radar") or {}).get("current") or "1.0")


def storm_version() -> str:
    am = (json.loads(P.PROGRESS.read_text(encoding="utf-8")) if P.PROGRESS.exists() else {}).get("ai_model") or {}
    unc, ens = am.get("uncertainty") or {}, am.get("ensemble") or {}
    if unc.get("status") == "adopted" and unc.get("version"):
        return str(unc["version"])
    return str(ens.get("version") or am.get("current") or "1.0")


def update_progress(out: dict, progress: Path) -> None:
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = out["run_at"]
    c, hu = out["candidates"], out["hurricane"]
    hc, hd = hu["candidates"], hu["design"]
    prog["screen"] = {
        "round": ROUND, "date": stamp[:10], "status": "done", "models": out["models"],
        "pool": {"source": out["pool"]["source"], "what": "metals with no superconductivity record",
                 "n_screened": out["pool"]["n_screened"], "n_listed_from": out["pool"]["n_storm"], "rule": out["pool"]["rule"]},
        "excluded": out["excluded"], "rule": out["rule"], "caveat": out["caveat"],
        "range": {"level": 0.9, "design": out["storm"]["range_design"], "width_log": out["storm"]["width_log"],
                  "width_k": out["storm"]["width_k"], "oof_coverage": out["storm"]["oof_coverage"]},
        "candidates": c,
        "hurricane": {
            "model": hu["model"], "design": hd["id"], "two_part": hd.get("two_part"),
            "pool": {"source": hu["pool"]["source"], "what": "compounds with no superconductivity record that Radar sends to Hurricane",
                     "n_screened": hu["pool"]["n_screened"], "n_sent": hu["pool"]["n_sent"], "rule": hu["pool"]["rule"]},
            "excluded": hu["excluded"],
            "range": {"level": 0.9, "design": "U2", "width_log": hd["width_log"], "oof_coverage": hd["oof_coverage"],
                      "of": "the Tc if it superconducts"},
            "check": hd["check"], "caveat": hu["caveat"], "candidates": hc},
    }
    for st in prog.get("stages", []):
        if st.get("id") == "screen":
            st.update(status="active", date=st.get("date") or stamp[:10], detail=(
                f"Round {ROUND}: {len(c)} conventional candidates (Storm) and {len(hc)} unconventional ones (Hurricane) found "
                f"by our AI models in JARVIS-DFT, none of them reported or predicted before and none made of the elements of "
                f"a known superconductor; next: full DFT checks of the top ones"))
    done = sum(1 for s in prog.get("stages", []) if s.get("status") == "done")
    current = next((s for s in prog.get("stages", []) if s.get("status") == "active"), None)
    if prog.get("stages"):
        prog["badge"] = f"{done}/{len(prog['stages'])} done · now: " + (current["short"].lower() if current else "models")
    msg = (f"Screening round {ROUND}: {out['models'][1]} scored {out['pool']['n_screened']:,} metals and {hu['model']} "
           f"{hu['pool']['n_sent']:,} compounds that {out['models'][0]} sent it, from JARVIS-DFT, after leaving out "
           f"{out['excluded']['total'] + hu['excluded']['total']:,} entries that others have reported, computed or predicted "
           f"or that share the elements of a known superconductor; {len(c)} conventional and {len(hc)} unconventional "
           f"candidates published")
    tops = []
    if c:
        tops.append(f"{c[0]['formula']} at {c[0]['tc']:.1f} K (Storm, 90% range {c[0]['lo']:.1f}–{c[0]['hi']:.1f} K)")
    if hc and hc[0].get("tc_sc") is not None:
        h0 = hc[0]
        tops.append(f"{h0['formula']} (Hurricane: {h0['tc_sc']:.1f} K if it superconducts" +
                    (f", a {100 * h0['p_sc']:.0f}% chance that it does)" if h0.get("p_sc") is not None else ")"))
    if tops:
        msg += ", led by " + " and ".join(tops)
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)


if __name__ == "__main__":
    run()
