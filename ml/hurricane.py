"""Hurricane: the project's AI-designed Tc model for unconventional superconductors.

Run from the repository root:
    python ml/hurricane.py              (or: python ml/pipeline.py hurricane)

Data: the 3DSC_MP dataset (T. Sommer et al., Sci. Data 10, 816 (2023), doi:10.1038/s41597-023-02721-y,
CC BY 4.0), which matches measured Tc from the SuperCon database to Materials Project crystal structures.
The file is downloaded from a pinned commit of github.com/aimat-lab/3DSC and checked against its SHA-256.
Hurricane's domain is 3DSC's cuprates, iron- and nickel-based pnictides and chalcogenides ("Ferrite"),
heavy-fermion compounds and other oxides, including entries measured to be non-superconducting (Tc = 0).

No first-principles theory gives the Tc of these families, so Hurricane learns from measured Tc directly.
An AI agent (Claude) proposed the candidate designs: physics features for unconventional pairing (the
d-electron count of the transition-metal layer from charge balance, the cuprate hole doping and its Tc dome,
the number of CuO2 planes, heavy-metal charge reservoirs, f-electron share and f-f spacing for heavy
fermions), measurable structure descriptors, label-noise down-weighting, a seed bag and conventional
superconductors as context. Every candidate is scored with the same 5-fold cross-validation grouped by parent
compound; leave-one-family-out tests show how far the model is from predicting a family it has never seen.
A graded set of later measurements (data/hurricane_anchors.json) is predicted but never used for training.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402  (shared helpers: paths, element table, metrics, progress log)

MODEL = "Hurricane"
ROUND = 1
DSC_COMMIT = "8d69ca9c94b83d387378549225d3b7c3af85ca42"
DSC_URL = ("https://raw.githubusercontent.com/aimat-lab/3DSC/" + DSC_COMMIT +
           "/superconductors_3D/data/final/MP/3DSC_MP.csv")
DSC_SHA256 = "353b86f9c60505d11a3e25df8312da02ff88fd8e27af05b632dec4739d52eb24"
DSC_CITE = ("T. Sommer et al., 3DSC - a dataset of superconductors including crystal structures, Sci. Data 10, "
            "816 (2023), doi:10.1038/s41597-023-02721-y; data CC BY 4.0, github.com/aimat-lab/3DSC")
ANCHORS = P.ROOT / "data" / "hurricane_anchors.json"   # outside ml/, so editing it does not start a training run
ANCHOR_MIN_N = 8   # the anchor check is reported as a score only with at least this many scored measurements

FAMILY_OF_CLASS = {"Cuprate": "cuprate", "Ferrite": "iron-based", "Heavy_fermion": "heavy-fermion",
                   "OxideHeavy_fermion": "heavy-fermion", "Oxide": "other oxide"}
FAMILY_LABEL = {"cuprate": "Cuprates", "iron-based": "Iron- and nickel-based", "heavy-fermion": "Heavy-fermion",
                "other oxide": "Other oxides"}
CONVENTIONAL = {"Other", "Chevrel", "Carbon", "Heavy_fermionChevrel"}   # context data for one candidate only
PARAMS = dict(max_iter=800, learning_rate=0.04, max_leaf_nodes=31, min_samples_leaf=10, l2_regularization=1.0)
HIGH_TC = 30.0   # K: "high-Tc" error is reported for measured Tc at or above this

# ---------------------------------------------------------------- chemistry

FORMULA = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")
ANION = {"O": -2, "S": -2, "Se": -2, "Te": -2, "F": -1, "Cl": -1, "Br": -1, "I": -1, "N": -3, "P": -3, "As": -3}
FIXED = {"H": 1, "Li": 1, "Na": 1, "K": 1, "Rb": 1, "Cs": 1, "Be": 2, "Mg": 2, "Ca": 2, "Sr": 2, "Ba": 2,
         "Sc": 3, "Y": 3, "La": 3, "Pr": 3, "Nd": 3, "Pm": 3, "Sm": 3, "Gd": 3, "Tb": 3, "Dy": 3, "Ho": 3,
         "Er": 3, "Tm": 3, "Yb": 3, "Lu": 3, "Zn": 2, "Cd": 2, "Hg": 2, "B": 3, "Al": 3, "Ga": 3, "In": 3,
         "C": 4, "Si": 4, "Ge": 4, "Sn": 4, "Pb": 2, "Bi": 3, "Sb": 3, "Ag": 1, "Au": 1, "Zr": 4, "Hf": 4,
         "Th": 4, "U": 4}
ACTIVE = {"Ti": 4, "V": 5, "Cr": 6, "Mn": 7, "Fe": 8, "Co": 9, "Ni": 10, "Cu": 11, "Nb": 5, "Mo": 6, "Ru": 8,
          "Rh": 9, "Pd": 10, "Ta": 5, "W": 6, "Re": 7, "Os": 8, "Ir": 9, "Pt": 10}   # element: group number
F_ELECTRONS = {"Ce": 1, "Pr": 2, "Nd": 3, "Pm": 4, "Sm": 5, "Eu": 6, "Gd": 7, "Tb": 8, "Dy": 9, "Ho": 10,
               "Er": 11, "Tm": 12, "Yb": 13, "U": 3, "Np": 4, "Pu": 5, "Am": 6}
MAG3D = {"V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"}
HEAVY_BLOCK = {"Hg", "Tl", "Bi", "Pb"}
PNICTOGEN_CHALCOGEN = {"P", "As", "Sb", "S", "Se", "Te"}
CRYSTAL_SYSTEMS = ["cubic", "hexagonal", "trigonal", "tetragonal", "orthorhombic", "monoclinic", "triclinic"]
CENTRING = ["primitive", "base-centered", "body-centered", "face-centered"]
POINT_GROUP_ORDER = {"1": 1, "-1": 2, "2": 2, "m": 2, "2/m": 4, "222": 4, "mm2": 4, "mmm": 8, "4": 4, "-4": 4,
                     "4/m": 8, "422": 8, "4mm": 8, "-42m": 8, "-4m2": 8, "4/mmm": 16, "3": 3, "-3": 6, "32": 6,
                     "3m": 6, "-3m": 12, "6": 6, "-6": 6, "6/m": 12, "622": 12, "6mm": 12, "-6m2": 12, "-62m": 12,
                     "6/mmm": 24, "23": 12, "m-3": 24, "432": 24, "-43m": 24, "m-3m": 48}

PHYSICS_RATIONALE = {
    "tm_d": "d electrons per transition-metal atom from charge balance (Cu2+ is d9, Fe2+ d6, Ni+ d9); each family's "
            "parent compound sits at a characteristic filling and doping moves it away",
    "p_cu": "holes per Cu from charge balance (negative for electron doping); cuprate Tc rises and falls with it",
    "dome": "the empirical cuprate dome 1 - 82.6 (p - 0.16)^2 (Presland and Tallon), largest at p = 0.16",
    "cu_layers": "Cu atoms per formula unit, a proxy for the number of CuO2 planes; Tc rises from one to three planes",
    "heavy_block": "share of Hg, Tl, Bi and Pb, the heavy-metal charge reservoirs of the highest-Tc cuprates",
    "fe_based": "iron or nickel together with a pnictogen or chalcogen, the FeAs- or FeSe-type layer",
    "f_share": "share of atoms with a partly filled f shell (Ce, Yb, U, Pu and others), the local moments of "
               "heavy-fermion metals",
    "f_count": "nominal f-electron count of those atoms",
    "mag3d": "share of magnetic 3d atoms (V to Cu), a proxy for spin fluctuations",
    "nonint": "share of non-integer stoichiometry, which marks doped samples",
    "n_atoms_fu": "atoms per formula unit as written, a measure of chemical complexity",
    "oxide": "share of oxygen", "chalcogenide": "share of S, Se and Te", "pnictide": "share of P, As and Sb",
    "halide": "share of F, Cl, Br and I",
}
STRUCTURE_RATIONALE = {
    "crystal system and lattice centring": "seven crystal systems and four centring types, one-hot",
    "pg_order": "order of the point group, a single number for how symmetric the crystal is",
    "vpa": "volume per atom",
    "density": "density from the composition and the volume per atom",
    "aniso": "longest over geometric mean of the two shorter reduced-cell edges, a measure of layering",
    "c_over_a": "c/a of the conventional cell for tetragonal and hexagonal crystals (1 for cubic)",
    "f_spacing": "volume per f-electron atom to the power 1/3, a proxy for the f-f distance that decides whether "
                 "f electrons stay local (the Hill limit)",
}


def parse_formula(s: str) -> dict:
    """'Ba2Cu3O6.9Y1' -> {'Ba': 2.0, 'Cu': 3.0, 'O': 6.9, 'Y': 1.0}; raises ValueError on anything else."""
    s = str(s).strip()
    out, pos = {}, 0
    for m in FORMULA.finditer(s):
        if m.start() != pos or not m.group(0):
            break
        el, n = m.group(1), m.group(2)
        out[el] = out.get(el, 0.0) + (float(n) if n else 1.0)
        pos = m.end()
    if pos != len(s) or not out or any(v <= 0 for v in out.values()):
        raise ValueError(f"cannot parse formula {s!r}")
    return out


def charge_balance_d(comp: dict) -> float:
    """Average d-electron count of the transition-metal sublattice from nominal ionic charges, or NaN where
    charge balance is not meaningful (intermetallics, no transition metal, unknown valence)."""
    els = set(comp)
    tms = [e for e in sorted(comp) if e in ACTIVE]   # a fixed order: sums over a set would depend on string hashing
    if not tms:
        return float("nan")
    ionic = els & {"O", "F", "Cl", "Br", "I"} or (els & {"S", "Se", "Te", "P", "As"})
    if not ionic:
        return float("nan")
    q = 0.0
    for el, n in comp.items():
        if el in ACTIVE:
            continue
        if el in ANION:
            q -= ANION[el] * n
            continue
        if el == "Ce":
            v = 4 if {"Cu", "O"} <= els else 3
        elif el == "Eu":
            v = 2 if els & {"As", "P"} else 3
        elif el == "Tl":
            v = 3 if "O" in els else 1
        elif el in FIXED:
            v = FIXED[el]
        else:
            return float("nan")
        q -= v * n
    n_tm = sum(comp[e] for e in tms)
    valence = q / n_tm
    group = sum(ACTIVE[e] * comp[e] for e in tms) / n_tm
    d = group - valence
    return float(d) if -0.5 <= d <= 10.5 else float("nan")


def physics_row(comp: dict) -> dict:
    tot = sum(comp.values())
    x = {el: n / tot for el, n in comp.items()}
    els = set(comp)
    d = charge_balance_d(comp)
    tms = [e for e in sorted(comp) if e in ACTIVE]
    cu_major = "Cu" in els and "O" in els and comp["Cu"] >= 0.5 * sum(comp[e] for e in tms)
    p = 9.0 - d if cu_major and np.isfinite(d) else float("nan")
    f_atoms = {el: n for el, n in comp.items() if el in F_ELECTRONS}
    f_tot = sum(f_atoms.values())
    amounts = np.array(list(comp.values()))
    return {
        "tm_d": d,
        "p_cu": p,
        "dome": max(0.0, 1.0 - 82.6 * (p - 0.16) ** 2) if np.isfinite(p) and p >= 0 else (0.0 if np.isfinite(p) else float("nan")),
        "cu_layers": min(float(comp["Cu"]), 6.0) if cu_major else float("nan"),
        "heavy_block": sum(x.get(e, 0.0) for e in sorted(HEAVY_BLOCK)),
        "fe_based": float(bool(els & {"Fe", "Ni"}) and bool(els & PNICTOGEN_CHALCOGEN)),
        "f_share": f_tot / tot,
        "f_count": sum(F_ELECTRONS[e] * n for e, n in f_atoms.items()) / f_tot if f_tot else float("nan"),
        "mag3d": sum(x.get(e, 0.0) for e in sorted(MAG3D)),
        "nonint": float(np.sum(np.abs(amounts - np.round(amounts))) / tot),
        "n_atoms_fu": min(float(tot), 60.0),
        "oxide": x.get("O", 0.0),
        "chalcogenide": sum(x.get(e, 0.0) for e in ("S", "Se", "Te")),
        "pnictide": sum(x.get(e, 0.0) for e in ("P", "As", "Sb")),
        "halide": sum(x.get(e, 0.0) for e in ("F", "Cl", "Br", "I")),
    }


def composition_row(comp: dict, table: pd.DataFrame) -> dict:
    """Composition statistics (mean, spread, min, max of eight element properties), as in Storm."""
    els = sorted(comp)
    frac = np.array([comp[e] for e in els], float)
    frac /= frac.sum()
    props = table.loc[els, P.ELEMENT_PROPS].to_numpy(float)
    f = {"n_elements": float(len(els))}
    for j, name in enumerate(P.ELEMENT_PROPS):
        col = props[:, j]
        ok = np.isfinite(col)
        if not ok.any():
            f.update({f"{name}_{s}": np.nan for s in ("mean", "std", "min", "max")})
            continue
        w = frac[ok] / frac[ok].sum()
        mean = float(np.sum(w * col[ok]))
        f[f"{name}_mean"] = mean
        f[f"{name}_std"] = float(np.sqrt(np.sum(w * (col[ok] - mean) ** 2)))
        f[f"{name}_min"] = float(col[ok].min())
        f[f"{name}_max"] = float(col[ok].max())
    return f


def _flag(v) -> float:
    s = str(v).strip().lower()
    if s in ("true", "1", "1.0", "yes"):
        return 1.0
    if s in ("false", "0", "0.0", "no", "", "nan", "none"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def structure_row(st: dict, comp: dict, table: pd.DataFrame) -> dict:
    """Measurable structure descriptors from a cell description:
    {crystal_system, centring, point_group, lengths (three reduced-cell edges, Angstrom), vpa (Angstrom^3/atom),
    a and c of the conventional cell (optional)}."""
    out = {f"cs_{c}": float(st.get("crystal_system") == c) for c in CRYSTAL_SYSTEMS}
    out.update({f"ct_{c}": float(st.get("centring") == c) for c in CENTRING})
    out["pg_order"] = float(POINT_GROUP_ORDER.get(str(st.get("point_group", "")).replace(" ", ""), np.nan))
    vpa = float(st.get("vpa", np.nan))
    out["vpa"] = vpa
    tot = sum(comp.values())
    mass = sum(float(table.loc[e, "atomic_mass"]) * n for e, n in comp.items()) / tot
    out["density"] = mass * 1.66054 / vpa if vpa > 0 else np.nan
    lengths = sorted(float(v) for v in st.get("lengths", []) if v and np.isfinite(v))
    out["aniso"] = lengths[2] / math.sqrt(lengths[0] * lengths[1]) if len(lengths) == 3 and lengths[0] > 0 else np.nan
    out["c_over_a"] = float(st["c_over_a"]) if st.get("c_over_a") is not None else np.nan
    f_share = sum(n for e, n in comp.items() if e in F_ELECTRONS) / tot
    out["f_spacing"] = (vpa / f_share) ** (1.0 / 3.0) if f_share > 0 and vpa > 0 else np.nan
    return out


def dsc_structure(r) -> dict:
    """Structure description of a 3DSC row (Materials Project cell: reduced-cell edges, volume, sites)."""
    lengths = [_num(r.get("lata_2")), _num(r.get("latb_2")), _num(r.get("latc_2"))]
    nsites, vol = _num(r.get("nsites_2")), _num(r.get("cell_volume_2"))
    cs = str(r.get("crystal_system_2", "")).strip().lower()
    centring = next((c for c in CENTRING if _flag(r.get(c, 0)) > 0.5), "primitive")
    st = {"crystal_system": cs, "centring": centring, "point_group": r.get("point_group_2", ""),
          "lengths": lengths, "vpa": vol / nsites if nsites and nsites > 0 else np.nan}
    if cs == "cubic":
        st["c_over_a"] = 1.0
    elif cs in ("tetragonal", "hexagonal") and all(np.isfinite(lengths)):
        mult = {"primitive": 1, "base-centered": 2, "body-centered": 2, "face-centered": 4}[centring]
        s = sorted(lengths)
        a = s[0] if abs(s[0] - s[1]) < 2e-3 * s[1] else (s[1] if abs(s[1] - s[2]) < 2e-3 * s[2] else None)
        if a:
            base = a * a * (1.0 if cs == "tetragonal" else math.sqrt(3) / 2)
            st["c_over_a"] = vol * mult / base / a
    return st


def anchor_structure(st: dict) -> dict:
    """Structure description of an anchor from its conventional cell: reduced-cell edges are the three shortest
    non-coplanar lattice vectors, as in the Materials Project cells of the training data."""
    cs, a, b, c = st["crystal_system"], float(st["a"]), float(st.get("b", st["a"])), float(st["c"])
    if cs in ("hexagonal", "trigonal"):
        A = np.array([[a, 0, 0], [-a / 2, a * math.sqrt(3) / 2, 0], [0, 0, c]])
        vol = a * a * c * math.sqrt(3) / 2
    else:
        A = np.diag([a, b, c])
        vol = a * b * c
    cent = {"P": [], "I": [[0.5, 0.5, 0.5]], "F": [[0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]],
            "A": [[0, 0.5, 0.5]], "B": [[0.5, 0, 0.5]], "C": [[0.5, 0.5, 0]]}[st["centring"]]
    pts = []
    rng = range(-2, 3)
    for off in [[0, 0, 0]] + cent:
        for i in rng:
            for j in rng:
                for k in rng:
                    v = (np.array([i, j, k], float) + off) @ A
                    n = float(np.linalg.norm(v))
                    if n > 1e-6:
                        pts.append((n, v))
    pts.sort(key=lambda t: t[0])
    basis = []   # successive minima: shortest vector, shortest not parallel to it, shortest not coplanar with both
    for n, v in pts:
        if not basis:
            basis.append((n, v))
        elif len(basis) == 1:
            if np.linalg.norm(np.cross(basis[0][1], v)) > 1e-6 * n * basis[0][0]:
                basis.append((n, v))
        elif abs(np.dot(np.cross(basis[0][1], basis[1][1]), v)) > 1e-6 * n * basis[0][0] * basis[1][0]:
            basis.append((n, v))
            break
    centring = {"P": "primitive", "I": "body-centered", "F": "face-centered"}.get(st["centring"], "base-centered")
    out = {"crystal_system": cs, "centring": centring, "point_group": st["point_group"],
           "lengths": [t[0] for t in basis], "vpa": vol / float(st["atoms_per_cell"])}
    out["c_over_a"] = 1.0 if cs == "cubic" else (c / a if cs in ("tetragonal", "hexagonal") else None)
    return out


def _num(v) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------- data


def load_3dsc() -> pd.DataFrame:
    """The pinned 3DSC_MP file, downloaded once into the data cache and checked against its SHA-256.
    HURRICANE_3DSC may point to a local copy (used for tests)."""
    local = os.environ.get("HURRICANE_3DSC")
    if local:
        path = Path(local)
    else:
        path = P.CACHE / "3DSC_MP.csv"
        P.CACHE.mkdir(parents=True, exist_ok=True)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != DSC_SHA256:
            P.log(f"downloading 3DSC_MP.csv ({DSC_COMMIT[:7]})")
            req = urllib.request.Request(DSC_URL, headers={"User-Agent": "supercon-ml (github.com/diracmagic/supercon-ml)"})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        data = r.read()
                    break
                except Exception as err:   # network hiccup: retry
                    P.log(f"download failed ({attempt + 1}/3): {err}")
                    time.sleep(10 * (attempt + 1))
            else:
                raise SystemExit("could not download 3DSC_MP.csv")
            got = hashlib.sha256(data).hexdigest()
            if got != DSC_SHA256:
                raise SystemExit(f"3DSC_MP.csv checksum mismatch: {got}")
            path.write_bytes(data)
    with open(path, encoding="utf-8") as fh:
        first = fh.readline()
    df = pd.read_csv(path, skiprows=1 if first.startswith("#") else 0, low_memory=False)
    P.log(f"3DSC_MP: {len(df)} rows, {df.shape[1]} columns")
    return df


def build_frame(dsc: pd.DataFrame, classes: set) -> pd.DataFrame:
    """One row per SuperCon formula in the given 3DSC classes, with parsed composition, family and group."""
    df = dsc[dsc["sc_class"].isin(classes)].copy()
    df["tc"] = pd.to_numeric(df["tc"], errors="coerce")
    df = df[np.isfinite(df["tc"]) & (df["tc"] >= 0)]
    comps, keep = [], []
    for f in df["formula_sc"]:
        try:
            comps.append(parse_formula(f))
            keep.append(True)
        except ValueError:
            comps.append(None)
            keep.append(False)
    df["comp"] = comps
    df = df[np.array(keep)]
    df = df.drop_duplicates(subset="formula_sc", keep="first").reset_index(drop=True)
    df["family"] = df["sc_class"].map(FAMILY_OF_CLASS).fillna("conventional")
    parent = df["chemical_composition_2"].astype(str) if "chemical_composition_2" in df else pd.Series([""] * len(df))
    major = df["comp"].map(lambda c: "-".join(sorted(e for e, n in c.items() if n / sum(c.values()) >= 0.05)))
    df["group"] = [p if p and p != "nan" else m for p, m in zip(parent, major)]
    return df


def feature_blocks(df: pd.DataFrame, table: pd.DataFrame, structures: list) -> dict:
    comp = pd.DataFrame([composition_row(c, table) for c in df["comp"]])
    phys = pd.DataFrame([physics_row(c) for c in df["comp"]])
    struct = pd.DataFrame([structure_row(st, c, table) for st, c in zip(structures, df["comp"])])
    return {"A": comp, "C": phys, "B": struct}


def element_fractions(comps, elements: list) -> pd.DataFrame:
    rows = []
    for c in comps:
        tot = sum(c.values())
        rows.append({f"x_{e}": c.get(e, 0.0) / tot for e in elements})
    return pd.DataFrame(rows, columns=[f"x_{e}" for e in elements])


# ---------------------------------------------------------------- models


def _fit(X, y_log, params, seed, weights=None, n_bags=1):
    from sklearn.ensemble import HistGradientBoostingRegressor
    empty = ~np.isfinite(X).any(axis=0)   # e.g. the cuprate features when cuprates are left out: constant, never used
    if empty.any():
        X = X.copy()
        X[:, empty] = 0.0
    models = []
    for b in range(n_bags):
        m = HistGradientBoostingRegressor(random_state=seed + 1000 * b, **params)
        m.fit(X, y_log, sample_weight=weights)
        models.append(m)
    return models


def _predict(models, X):
    return np.mean([m.predict(X) for m in models], axis=0)


def noise_weights(X, y_log, groups, params, seed) -> np.ndarray:
    """Label-noise down-weighting inside a training fold: entries far from out-of-fold predictions (beyond about
    three median absolute deviations) count less, never less than 0.2. Repeated or mistyped SuperCon entries are
    the target; the weights are computed from the training fold only."""
    from sklearn.model_selection import GroupKFold
    k = min(5, len(np.unique(groups)))
    oof = np.zeros(len(y_log))
    for i, (a, b) in enumerate(GroupKFold(n_splits=k).split(X, y_log, groups)):
        oof[b] = _predict(_fit(X[a], y_log[a], params, seed + 77 + i), X[b])
    r = np.abs(oof - y_log)
    mad = float(np.median(r)) or 1e-6
    return np.clip(1.0 / (1.0 + (r / (3.0 * mad)) ** 2), 0.2, 1.0)


def run_candidate(c: dict, mats: dict, y: np.ndarray, groups: np.ndarray, splits, aux=None):
    """Out-of-fold predictions (K) of one candidate on the Hurricane rows, plus the fitted fold models."""
    X = mats[c["X"]]
    y_log = np.log1p(y)
    pred = np.zeros(len(y))
    fold_models = []
    for k, (tr, te) in enumerate(splits):
        Xtr, ytr, w = X[tr], y_log[tr], None
        if c.get("aux") and aux is not None:
            test_groups = set(groups[te])
            ok = np.array([g not in test_groups for g in aux["groups"]])
            Xtr = np.vstack([np.hstack([Xtr, np.ones((len(tr), 1))]), np.hstack([aux[c["X"]][ok], np.zeros((ok.sum(), 1))])])
            ytr = np.concatenate([ytr, np.log1p(aux["y"][ok])])
            Xte = np.hstack([X[te], np.ones((len(te), 1))])
        else:
            Xte = X[te]
        if c.get("noise"):
            gtr = groups[tr] if not (c.get("aux") and aux is not None) else np.concatenate([groups[tr], aux["groups"][ok]])
            w = noise_weights(Xtr, ytr, gtr, c["params"], P.SEED + k)
        models = _fit(Xtr, ytr, c["params"], P.SEED + k, weights=w, n_bags=c.get("bags", 1))
        pred[te] = np.clip(np.expm1(_predict(models, Xte)), 0, None)
        fold_models.append((models, Xte, te))
    return pred, fold_models


def scores(y, p, families, folds) -> dict:
    err = np.abs(p - y)
    sc = y > 0
    hi = y >= HIGH_TC
    out = {
        "tc_mae": float(err.mean()),
        "tc_rmse": float(np.sqrt(np.mean((p - y) ** 2))),
        "sc_mae": float(err[sc].mean()) if sc.any() else None,
        "high_tc_mae": float(err[hi].mean()) if hi.any() else None,
        "r2_log": float(1 - np.sum((np.log1p(p) - np.log1p(y)) ** 2) / np.sum((np.log1p(y) - np.log1p(y).mean()) ** 2)),
        "fold_mae": [float(err[te].mean()) for te in folds],
        "by_family": {f: {"n": int((families == f).sum()), "mae": float(err[families == f].mean())}
                      for f in FAMILY_LABEL if (families == f).any()},
    }
    return out


def permutation_importance(fold_models, y, names, n_repeats=3, seed=P.SEED) -> list:
    """Mean increase of the out-of-fold Tc error (K) when one input is shuffled within each test fold."""
    rng = np.random.default_rng(seed)
    gain = np.zeros(len(names))
    for models, Xte, te in fold_models:
        base = np.abs(np.clip(np.expm1(_predict(models, Xte)), 0, None) - y[te]).mean()
        for j in range(len(names)):
            inc = 0.0
            for _ in range(n_repeats):
                Xp = Xte.copy()
                Xp[:, j] = rng.permutation(Xp[:, j])
                inc += np.abs(np.clip(np.expm1(_predict(models, Xp)), 0, None) - y[te]).mean() - base
            gain[j] += inc / n_repeats * len(te) / len(y)
    order = np.argsort(-gain)
    return [{"name": names[j], "gain": round(float(gain[j]), 3)} for j in order[:15]]


def lofo(c: dict, mats: dict, y: np.ndarray, families: np.ndarray, aux=None) -> list:
    """Leave one family out: train on the other families (and the context data, if the design uses it), then
    predict the whole held-out family. Also reports the error of always predicting the training median."""
    out = []
    X = mats[c["X"]]
    y_log = np.log1p(y)
    for f in FAMILY_LABEL:
        te = np.where(families == f)[0]
        tr = np.where(families != f)[0]
        if len(te) < 10:
            continue
        Xtr, ytr, Xte = X[tr], y_log[tr], X[te]
        if c.get("aux") and aux is not None:
            Xtr = np.vstack([np.hstack([Xtr, np.ones((len(tr), 1))]), np.hstack([aux[c["X"]], np.zeros((len(aux["y"]), 1))])])
            ytr = np.concatenate([ytr, np.log1p(aux["y"])])
            Xte = np.hstack([Xte, np.ones((len(te), 1))])
        models = _fit(Xtr, ytr, c["params"], P.SEED + 300, n_bags=c.get("bags", 1))
        p = np.clip(np.expm1(_predict(models, Xte)), 0, None)
        med = float(np.median(y[tr]))
        out.append({"family": f, "label": FAMILY_LABEL[f], "n": int(len(te)), "mae": float(np.abs(p - y[te]).mean()),
                    "mae_median": float(np.abs(med - y[te]).mean()), "max_tc": float(y[te].max()),
                    "max_pred": float(p.max())})
    return out


# ---------------------------------------------------------------- spec for the app


def model_spec(c: dict, n: dict) -> dict:
    inputs = [{"group": "composition", "label": "Composition statistics", "n": n["A"],
               "detail": "mean, spread, min and max of 8 element properties, plus the number of elements"}]
    if "B" in c["X"]:
        inputs.append({"group": "structure", "label": "Measurable crystal structure", "n": n["B"],
                       "items": [{"name": k, "why": v} for k, v in STRUCTURE_RATIONALE.items()]})
    if "C" in c["X"]:
        inputs.append({"group": "physics", "label": "Physics features proposed by the AI", "n": n["C"],
                       "items": [{"name": k, "why": v} for k, v in PHYSICS_RATIONALE.items()]})
    if "D" in c["X"]:
        inputs.append({"group": "elements", "label": "Element fractions", "n": n["D"],
                       "detail": "the share of each element seen in at least ten training compounds"})
    if c.get("aux"):
        inputs.append({"group": "context", "label": "Conventional superconductors as context", "n": 1,
                       "detail": "3DSC's other classes join the training folds with a flag; they are never scored"})
    p = c["params"]
    return {
        "inputs": inputs,
        "learner": {"kind": "gradient-boosting", "trees": p["max_iter"], "leaves": p["max_leaf_nodes"],
                    "learning_rate": p["learning_rate"], "min_leaf": p["min_samples_leaf"], "l2": p["l2_regularization"],
                    "features_per_split": p.get("max_features", 1.0), "ensemble": c.get("bags", 1),
                    "loss": "absolute error" if p.get("loss") == "absolute_error" else "squared error",
                    "weights": "label-noise down-weighting" if c.get("noise") else None},
        "target": "log(1 + Tc)",
        "cv": "5-fold, grouped by parent compound (the Materials Project chemical system)",
    }


def spec_changes(c: dict, ref: dict) -> list:
    out = []
    if "B" in c["X"] and "B" not in ref["X"]:
        out.append("Adds measurable crystal structure: crystal system, centring, point-group order, volume per atom, "
                   "density, layering (anisotropy and c/a) and the f-f spacing")
    if "C" in c["X"] and "C" not in ref["X"]:
        out.append("Adds physics features proposed by the AI: the d-electron count of the transition-metal layer from "
                   "charge balance, the cuprate hole doping p and its Tc dome, the number of CuO2 planes, heavy-metal "
                   "charge reservoirs, the FeAs/FeSe-type layer, f-electron share and count, magnetic 3d share and "
                   "a doping indicator")
    if "D" in c["X"] and "D" not in ref["X"]:
        out.append("Adds the share of each common element")
    if c.get("noise"):
        out.append("Down-weights entries that disagree strongly with out-of-fold predictions, to soften label noise")
    if c.get("bags", 1) > 1:
        out.append(f"Averages {c['bags']} models trained with different seeds, each split seeing a random "
                   f"{c['params'].get('max_features', 1.0):.0%} of the inputs")
    if c.get("aux"):
        out.append("Trains with 3DSC's conventional superconductors as flagged context data")
    if c["params"].get("loss") == "absolute_error":
        out.append("Fits the median instead of the mean (absolute-error loss)")
    return out or ["Same structure as the baseline"]


# ---------------------------------------------------------------- anchors


def load_anchors() -> dict:
    if not ANCHORS.exists():
        return {}
    return json.loads(ANCHORS.read_text(encoding="utf-8"))


def anchor_check(models, c: dict, table: pd.DataFrame, elements: list, n_cols: dict) -> dict:
    ex = load_anchors()
    if not ex:
        return {}
    rows, table_out = [], []
    for e in ex["materials"]:
        comp = {k: float(v) for k, v in e["composition"].items()}
        if any(el not in table.index for el in comp):
            table_out.append({"name": e["name"], "tc_exp": e.get("tc_exp"), "status": e["status"], "use": e["use"],
                              "family": e.get("family"), "source": e.get("source"), "note": e.get("note", ""),
                              "pred": None, "why": "element outside the training data"})
            continue
        st = anchor_structure(e["structure"]) if e.get("structure") else {}
        blocks = {"A": pd.DataFrame([composition_row(comp, table)]), "C": pd.DataFrame([physics_row(comp)]),
                  "B": pd.DataFrame([structure_row(st, comp, table)]), "D": element_fractions([comp], elements)}
        X = np.hstack([blocks[b].to_numpy(float) for b in c["X"]])
        if c.get("aux"):
            X = np.hstack([X, np.ones((1, 1))])
        pred = float(np.clip(np.expm1(_predict(models, X)), 0, None)[0])
        row = {"name": e["name"], "tc_exp": e.get("tc_exp"), "status": e["status"], "use": e["use"],
               "family": e.get("family"), "source": e.get("source"), "note": e.get("note", ""), "pred": round(pred, 2)}
        table_out.append(row)
        if e["use"] == "score" and e.get("tc_exp") is not None:
            rows.append(row)
    n = len(rows)
    summary = {"n_scored": n, "n_listed": len(table_out),
               "mae": round(float(np.mean([abs(r["pred"] - r["tc_exp"]) for r in rows])), 2) if n else None,
               "scored_as_check": n >= ANCHOR_MIN_N,
               "rule": f"reported as a score only with at least {ANCHOR_MIN_N} scored measurements; never used for "
                       "training or for choosing the design",
               "about": ex.get("about", "")}
    return {"summary": summary, "table": table_out, "sources": ex.get("sources", {})}


# ---------------------------------------------------------------- progress


def ai_stage(prog: dict) -> None:
    """Keep the "AI-designed models" stage in step with the models in use (also called by Storm rounds 3 and 4 and Radar)."""
    am = prog.get("ai_model") or {}
    cal, ens, unc = am.get("calibration") or {}, am.get("ensemble") or {}, am.get("uncertainty") or {}
    cur = am.get("current", "1.0")
    if unc.get("status") == "adopted" and unc.get("version") and ens.get("status") == "adopted" and ens.get("version"):
        parts = [f"Storm {unc['version']} for conventional superconductors (Storm {ens['version']} with a 90% range for "
                 "every prediction)"]
    elif ens.get("status") == "adopted" and ens.get("version"):
        parts = [f"Storm {ens['version']} for conventional superconductors ({ens.get('summary') or 'Storm ' + cur + ' and the graph network'})"]
    elif cal.get("status") == "adopted" and cal.get("version"):
        parts = [f"Storm {cal['version']} for conventional superconductors (Storm {cur} calibrated to measured Tc)"]
    else:
        parts = [f"Storm {cur} for conventional superconductors"]
    hu = prog.get("hurricane") or {}
    if hu.get("current"):
        parts.append(f"Hurricane {hu['current']} for unconventional ones")
    rd = prog.get("radar") or {}
    if rd.get("current"):
        parts.append(f"Radar {rd['current']} to pick between them")
    detail = (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + \
        (" are" if len(parts) > 1 else " is") + " in use"
    if hu and not hu.get("current"):
        detail += "; Hurricane, for unconventional superconductors, is experimental"
    if not rd.get("current"):
        detail += "; Radar, which picks the model for each material, " + ("is experimental" if rd else "comes next")
    for st in prog.get("stages", []):
        if st.get("id") == "ai-models":
            st["detail"] = detail


def update_progress(out: dict) -> None:
    prog = json.loads(P.PROGRESS.read_text(encoding="utf-8"))
    stamp = P.now_iso()
    best, ref, ver = out["best"], out["baseline"], out["version"]
    sc = best["scores"]
    entry = {
        "version": ver, "round": ROUND, "date": stamp[:10], "status": "adopted" if out["adopted"] else "experimental",
        "summary": best["name"] + ("" if best["settings"] == "default" else f", {best['settings']}"),
        "changes": out["changes"], "spec": out["spec"],
        "scores": {"tc_mae": round(sc["tc_mae"], 2), "reference_mae": round(ref["scores"]["tc_mae"], 2),
                   "reference": ref["name"], "folds": [round(x, 2) for x in sc["fold_mae"]],
                   "reference_folds": [round(x, 2) for x in ref["scores"]["fold_mae"]],
                   "folds_better": best["folds_better"],
                   "sc_mae": round(sc["sc_mae"], 2) if sc["sc_mae"] is not None else None,
                   "high_tc_mae": round(sc["high_tc_mae"], 2) if sc["high_tc_mae"] is not None else None,
                   "high_tc": HIGH_TC, "r2_log": round(sc["r2_log"], 3),
                   "by_family": {f: {"n": v["n"], "mae": round(v["mae"], 2),
                                     "mae_ref": round(ref["scores"]["by_family"][f]["mae"], 2)}
                                 for f, v in sc["by_family"].items()}},
        "lofo": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in out["lofo"]],
        "importance": out["importance"],
        "search": {"candidates": len(out["leaderboard"]), "reference_id": "H0",
                   "leaderboard": [{"id": r["id"], "name": r["name"], "settings": r["settings"],
                                    "tc_mae": round(r["scores"]["tc_mae"], 2), "folds_better": r["folds_better"]}
                                   for r in out["leaderboard"]]},
    }
    if out.get("anchors"):
        a = out["anchors"]
        entry["anchors"] = {"n_scored": a["summary"]["n_scored"], "mae": a["summary"]["mae"],
                            "scored_as_check": a["summary"]["scored_as_check"], "rule": a["summary"]["rule"],
                            "table": [{"name": r["name"], "tc_exp": r["tc_exp"], "status": r["status"], "use": r["use"],
                                       "family": r.get("family"), "pred": r.get("pred"), "note": r.get("note", "")}
                                      for r in a["table"]]}
    data = out["data"]
    reg = prog.get("hurricane") or {}
    versions = [v for v in reg.get("versions", []) if v.get("round") != ROUND] + [entry]
    versions.sort(key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    prog["hurricane"] = {
        "name": MODEL,
        "about": ("Hurricane is the project's AI-designed Tc model for unconventional superconductors: cuprates, "
                  "iron- and nickel-based pnictides and chalcogenides, heavy-fermion compounds and other oxides. No "
                  "first-principles theory gives their Tc, so it learns from measured Tc (SuperCon, with Materials "
                  "Project structures, via the 3DSC dataset), including materials that did not superconduct. An AI "
                  "agent (Claude) proposes each design; candidates are scored with cross-validation grouped by parent "
                  "compound, and a version is released only if it beats the reference on average and in at least 4 of "
                  "5 folds."),
        "current": released[-1]["version"] if released else None,
        "data": data,
        "versions": versions,
    }
    # the headline results table: measured-Tc rows (target Tc_exp), so older app versions list them too
    note = (f"5-fold CV grouped by parent compound; {data['n']:,} cuprates, iron-based, heavy-fermion and other oxides "
            f"from 3DSC (SuperCon + Materials Project), {data['n_sc']:,} superconducting")
    prog["results"] = [r for r in prog.get("results", []) if r.get("tag") != "hurricane"] + [
        {"tag": "hurricane", "model": f"{MODEL} {ver} (AI-designed)" + ("" if out["adopted"] else ", experimental"),
         "target": "Tc_exp", "mae": round(sc["tc_mae"], 2), "unit": "K", "note": note},
        {"tag": "hurricane", "model": "Gradient boosting, composition only (measured-Tc baseline)", "target": "Tc_exp",
         "mae": round(ref["scores"]["tc_mae"], 2), "unit": "K", "note": "Same data and folds"},
    ]
    for st in prog.get("stages", []):
        if st.get("id") == "data-measured":
            st.update(status="done", date=st.get("date") or stamp[:10], detail=(
                f"{data['n']:,} measured Tc for cuprates, iron-based, heavy-fermion and other oxides ({data['n_sc']:,} "
                f"superconducting) from 3DSC, which matches SuperCon to Materials Project structures; graded anchors "
                f"for later discoveries"))
        elif st.get("id") == "baseline":
            st.update(status="done", detail=(
                "Electron-phonon baseline (gradient boosting, composition + structure) and measured-Tc baseline "
                f"(composition only, {ref['scores']['tc_mae']:.1f} K on unconventional families) done"))
    done = sum(1 for s in prog.get("stages", []) if s.get("status") == "done")
    current = next((s for s in prog.get("stages", []) if s.get("status") == "active"), None)
    if prog.get("stages"):
        prog["badge"] = f"{done}/{len(prog['stages'])} done · now: " + (current["short"].lower() if current else "models")
    # the models card in the app: Hurricane's status and one line about it
    lof = {r["family"]: r for r in out["lofo"]}
    cup = lof.get("cuprate")
    text = (f"Learns from {data['n']:,} measured Tc values (cuprates, iron-based, heavy-fermion and other oxides; "
            f"SuperCon with Materials Project structures via 3DSC), including {data['n'] - data['n_sc']:,} materials that "
            f"did not superconduct. For compounds whose parent it never saw in training it is off by {sc['tc_mae']:.1f} K "
            f"on average, against {ref['scores']['tc_mae']:.1f} K for a composition-only baseline.")
    if cup:
        text += (f" Predicting a whole family it never saw is much harder: trained without any cuprate, it misses "
                 f"cuprates by {cup['mae']:.0f} K.")
    text += " Our AI agent designed it."
    fam = [m for m in prog.get("model_family", []) if m.get("id") != "hurricane"]
    fam.append({"id": "hurricane", "status": f"{MODEL} {ver} in use" if out["adopted"] else f"{MODEL} {ver}, experimental",
                "active": bool(out["adopted"]), "text": text})
    prog["model_family"] = fam
    ai_stage(prog)
    P.tidy(prog)
    P.add_log(prog, stamp, f"{MODEL} {ver}, the AI-designed model for unconventional superconductors (round {ROUND}, "
                           f"{len(out['leaderboard'])} candidates): measured-Tc MAE {sc['tc_mae']:.2f} K against "
                           f"{ref['scores']['tc_mae']:.2f} K for the composition-only baseline, better in "
                           f"{best['folds_better']} of {P.N_FOLDS} folds; " +
                           ("adopted" if out["adopted"] else "not adopted, so it stays experimental"))
    prog["updated"] = stamp
    P.PROGRESS.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(f"progress updated: {MODEL} {ver} ({entry['status']})")


# ---------------------------------------------------------------- run


def run() -> None:
    import sklearn
    from sklearn.model_selection import GroupKFold

    P.RESULTS.mkdir(exist_ok=True)
    dsc = load_3dsc()
    hur = build_frame(dsc, set(FAMILY_OF_CLASS))
    conv = build_frame(dsc, CONVENTIONAL)
    symbols = sorted({e for c in list(hur["comp"]) + list(conv["comp"]) for e in c})
    anchors = load_anchors()
    symbols = sorted(set(symbols) | {e for a in anchors.get("materials", []) for e in a["composition"]})
    table = P.element_table(symbols)
    y = hur["tc"].to_numpy(float)
    groups = hur["group"].to_numpy()
    families = hur["family"].to_numpy()
    P.log(f"Hurricane data: {len(hur)} entries ({int((y > 0).sum())} superconducting) in {len(set(groups))} parent "
          f"groups; families " + ", ".join(f"{f} {int((families == f).sum())}" for f in FAMILY_LABEL) +
          f"; {len(conv)} conventional entries as optional context")
    blocks = feature_blocks(hur, table, [dsc_structure(r) for _, r in hur.iterrows()])
    cblocks = feature_blocks(conv, table, [dsc_structure(r) for _, r in conv.iterrows()])
    counts = {}
    for c in hur["comp"]:
        for e in c:
            counts[e] = counts.get(e, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    blocks["D"] = element_fractions(hur["comp"], elements)
    cblocks["D"] = element_fractions(conv["comp"], elements)
    names = {b: list(blocks[b].columns) for b in blocks}
    n_cols = {b: len(names[b]) for b in names}
    mats, aux = {}, {"y": conv["tc"].to_numpy(float), "groups": conv["group"].to_numpy()}
    for key in ("A", "AC", "AB", "ABC", "ABCD"):
        mats[key] = np.hstack([blocks[b].to_numpy(float) for b in key])
        aux[key] = np.hstack([cblocks[b].to_numpy(float) for b in key])
    missing = {b: round(float(np.mean(~np.isfinite(blocks[b].to_numpy(float)))), 3) for b in blocks}
    P.log(f"features: composition {n_cols['A']}, structure {n_cols['B']}, physics {n_cols['C']}, elements "
          f"{n_cols['D']}; missing share {missing}")
    p_cu = blocks["C"]["p_cu"].to_numpy(float)
    cup = families == "cuprate"
    ok = cup & np.isfinite(p_cu)
    if (ok & (y > 0)).any():
        P.log(f"cuprate hole doping from charge balance: {int(ok.sum())} of {int(cup.sum())} cuprates; median p "
              f"{np.median(p_cu[ok]):.3f}; Tc-weighted mean p of the superconducting ones "
              f"{np.average(p_cu[ok & (y > 0)], weights=y[ok & (y > 0)]):.3f}")
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(mats["A"], y, groups))
    folds = [te for _, te in splits]
    med = dict(PARAMS, loss="absolute_error")
    cands = [
        {"id": "H0", "name": "Composition only (baseline)", "settings": "default", "X": "A", "params": PARAMS},
        {"id": "H1", "name": "Composition + physics features", "settings": "default", "X": "AC", "params": PARAMS},
        {"id": "H2", "name": "Composition + measurable structure", "settings": "default", "X": "AB", "params": PARAMS},
        {"id": "H3", "name": "Composition + structure + physics", "settings": "default", "X": "ABC", "params": PARAMS},
        {"id": "H4", "name": "Composition + structure + physics + element fractions", "settings": "default", "X": "ABCD", "params": PARAMS},
        {"id": "H5", "name": "Composition + structure + physics, label-noise down-weighting", "settings": "default", "X": "ABC",
         "params": PARAMS, "noise": True},
        {"id": "H6", "name": "Composition + structure + physics", "settings": "average of 5 seeds", "X": "ABC",
         "params": dict(PARAMS, max_features=0.8), "bags": 5},
        {"id": "H7", "name": "Composition + structure + physics, with conventional superconductors as context", "settings": "default",
         "X": "ABC", "params": PARAMS, "aux": True},
        {"id": "H8", "name": "Composition + structure + physics, median objective", "settings": "default", "X": "ABC", "params": med},
    ]
    board, preds, fold_models = [], {}, {}
    for c in cands:
        t0 = time.time()
        try:
            p, fm = run_candidate(c, mats, y, groups, splits, aux=aux)
        except (TypeError, ValueError) as err:   # e.g. an option this scikit-learn version lacks
            P.log(f"{c['id']} skipped: {err}")
            continue
        s = scores(y, p, families, folds)
        row = dict(c, scores=s, n_features=int(mats[c["X"]].shape[1] + (1 if c.get("aux") else 0)),
                   seconds=round(time.time() - t0))
        row.pop("params")
        row["params"] = dict(c["params"])
        board.append(row)
        preds[c["id"]], fold_models[c["id"]] = p, fm
        P.log(f"{c['id']} {c['name']} [{c['settings']}]: MAE {s['tc_mae']:.2f} K (superconductors {s['sc_mae']:.2f} K, "
              f"Tc >= {HIGH_TC:.0f} K {s['high_tc_mae']:.2f} K), R2(log) {s['r2_log']:.3f}, {row['seconds']} s; "
              + ", ".join(f"{f} {v['mae']:.2f}" for f, v in s["by_family"].items()))
    ref = next(r for r in board if r["id"] == "H0")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["scores"]["fold_mae"], ref["scores"]["fold_mae"])))
    eligible = [r for r in board if r["id"] != "H0" and r["scores"]["tc_mae"] < ref["scores"]["tc_mae"]
                and r["folds_better"] >= P.ADOPT_FOLDS]
    adopted = bool(eligible)
    best = min(eligible or [r for r in board if r["id"] != "H0"], key=lambda r: r["scores"]["tc_mae"])
    cb = next(c for c in cands if c["id"] == best["id"])
    feat_names = [n for b in cb["X"] for n in names[b]] + (["context_flag"] if cb.get("aux") else [])
    importance = permutation_importance(fold_models[best["id"]], y, feat_names)
    P.log("most important inputs: " + ", ".join(f"{i['name']} (+{i['gain']:.2f} K)" for i in importance[:8]))
    lofo_rows = lofo(cb, mats, y, families, aux=aux)
    lofo_ref = {r["family"]: r for r in lofo(cands[0], mats, y, families)}
    for r in lofo_rows:
        r["mae_cv"] = float(np.abs(preds[best["id"]][families == r["family"]] - y[families == r["family"]]).mean())
        r["mae_baseline"] = lofo_ref[r["family"]]["mae"] if r["family"] in lofo_ref else None
        P.log(f"leave one family out, {r['family']}: MAE {r['mae']:.2f} K (baseline design {r['mae_baseline']:.2f} K, "
              f"training median {r['mae_median']:.2f} K, grouped CV {r['mae_cv']:.2f} K); highest measured "
              f"{r['max_tc']:.0f} K, highest predicted {r['max_pred']:.0f} K")
    # final model on all Hurricane data, for the anchors
    X_all = mats[cb["X"]]
    y_log = np.log1p(y)
    if cb.get("aux"):
        X_fit = np.vstack([np.hstack([X_all, np.ones((len(y), 1))]), np.hstack([aux[cb["X"]], np.zeros((len(aux["y"]), 1))])])
        y_fit = np.concatenate([y_log, np.log1p(aux["y"])])
        g_fit = np.concatenate([groups, aux["groups"]])
    else:
        X_fit, y_fit, g_fit = X_all, y_log, groups
    w = noise_weights(X_fit, y_fit, g_fit, cb["params"], P.SEED + 500) if cb.get("noise") else None
    final = _fit(X_fit, y_fit, cb["params"], P.SEED + 500, weights=w, n_bags=cb.get("bags", 1))
    anchors_out = anchor_check(final, cb, table, elements, n_cols)
    if anchors_out:
        a = anchors_out["summary"]
        P.log(f"anchors: {a['n_listed']} listed, {a['n_scored']} scored, MAE {a['mae']} K; " + "; ".join(
            f"{r['name']} {r['tc_exp']} K -> {r['pred']} K" for r in anchors_out["table"] if r.get("pred") is not None))
    version = f"{ROUND}.0"
    spec = model_spec(cb, n_cols)
    changes = spec_changes(cb, cands[0])
    fam_stats = {f: {"label": FAMILY_LABEL[f], "n": int((families == f).sum()), "n_sc": int(((families == f) & (y > 0)).sum()),
                     "max_tc": float(y[families == f].max())} for f in FAMILY_LABEL if (families == f).any()}
    data = {"source": "3DSC_MP (SuperCon measured Tc matched to Materials Project structures)", "cite": DSC_CITE,
            "doi": "10.1038/s41597-023-02721-y", "licence": "CC BY 4.0", "commit": DSC_COMMIT[:7],
            "n": int(len(y)), "n_sc": int((y > 0).sum()), "n_groups": int(len(set(groups))), "families": fam_stats,
            "context": int(len(conv))}
    P.log(f"{MODEL} {version} = {best['id']} {best['name']} [{best['settings']}]: MAE {best['scores']['tc_mae']:.2f} K "
          f"(baseline {ref['scores']['tc_mae']:.2f} K, better in {best['folds_better']}/{P.N_FOLDS} folds; adopted: {adopted})")
    leader = sorted(board, key=lambda r: r["scores"]["tc_mae"])
    out = {
        "run_at": P.now_iso(), "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": MODEL,
        "version": version,
        "designer": ("AI agent (Claude) proposed the candidates: physics features for unconventional pairing, measurable "
                     "structure, element fractions, label-noise down-weighting, a seed bag, conventional context data "
                     "and a median objective"),
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by parent compound on {len(y):,} 3DSC entries; leave-one-family-out "
                      "reported separately; anchors never used for training or selection"),
        "rule": (f"release the lowest-error design that beats the composition-only baseline on average and in at least "
                 f"{P.ADOPT_FOLDS} of {P.N_FOLDS} folds; otherwise the best design stays experimental"),
        "caveat": ("SuperCon Tc values are averages over reports of varying quality, doped entries borrow the structure "
                   "of their parent compound, and picking the best of several designs on the same folds makes its "
                   "score slightly optimistic"),
        "scikit_learn": sklearn.__version__, "data": data, "physics_features": PHYSICS_RATIONALE,
        "structure_features": STRUCTURE_RATIONALE, "missing_share": missing,
        "baseline": {"id": ref["id"], "name": ref["name"], "scores": ref["scores"]},
        "leaderboard": leader, "best": best, "adopted": adopted, "spec": spec, "changes": changes,
        "importance": importance, "lofo": lofo_rows, "anchors": anchors_out or None,
    }
    (P.RESULTS / "hurricane_round1.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    pd.DataFrame({"formula": hur["formula_sc"], "family": families, "group": groups, "tc": y,
                  "tc_pred_best": preds[best["id"]], "tc_pred_baseline": preds["H0"]}).round(3).to_csv(
        P.RESULTS / "hurricane_round1_predictions.csv", index=False)
    update_progress(out)


if __name__ == "__main__":
    run()
