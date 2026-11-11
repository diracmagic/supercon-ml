"""Screening round 7: Hurricane 9.0 on a wider pool.

    python ml/hurricane9_screen7.py --protocol                 # the frozen screening protocol and its SHA-256
    python ml/hurricane9_screen7.py --smoke [--output-dir DIR] # invented rows through every step; not a result
    python ml/hurricane9_screen7.py --counts                   # the sizes of the pool; no Radar, no model, nothing written
    python ml/hurricane9_screen7.py --snapshot                 # read the COD once and store its usable rows in results/
    python ml/pipeline.py hurricane9screen7                    # the screening run: writes results/ and progress/

Why this round exists. Screening rounds 1 to 6 took their pool from one file, JARVIS-DFT 3D, and kept an entry only if
the file's ehull field was at most 0.05 eV/atom. That field does not follow the convex hull of the file's own
formation energies (results/validation/pool-census.md): the rule kept about a tenth of the file, unrelated to
stability, and left out nine in ten of its entries with an ICSD number. This round builds the pool again:

- Four open sources: JARVIS-DFT 3D, the Materials Project (a dated build, its entries under CC BY only), the Alexandria
  convex hull (a dated release) and the Crystallography Open Database (its own table, with the compositions as
  measured). SOURCES gives each one's licence and reference.
- One calculation speaks for each composition (Hurricane reads the composition and nothing else): of the calculated
  entries of that composition, one marked experimental before any other, then one near its source's convex hull. Its
  band gap must be at most 1 eV, so a hypothetical metallic structure does not bring in a compound that is an
  insulator as it was made.
- Two tracks. A compound with an experimental structure in one of the sources is kept whatever a calculation says about
  its stability. A compound known from calculation only is kept if its source puts that calculation within
  50 meV/atom of its convex hull; for JARVIS-DFT the distance is computed here from the file's formation energies, and
  the ehull field is not read. A measured COD composition takes the gap of the calculation of the same material; if
  there is none it stays, marked "no calculated band gap".
- Nothing about the model changes. The chance of a compound comes from the five classifiers of the release's guard:
  the classifier of a compound's fold (a hash of its chemical system) learned from no background compound of that
  system. For the compounds of the released background these are the chances the release run committed; the run
  computes them again and stops, writing nothing, if they differ. The Tc if a compound superconducts is the released
  regressor's. A compound outside the training data gets "not known" and is not listed.

Storm's list and every other part of the screen block stay as screening round 5 published them. Everything that
decides the lists is in PROTOCOL; the run refuses to read any data unless the hash of PROTOCOL is written in
results/validation/hurricane9-screen7-declaration-v1.md.
"""
from __future__ import annotations

import argparse
import bz2
import collections
import copy
import csv
import functools
import gzip
import hashlib
import io
import itertools
import json
import math
import os
import platform
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane9_screen as S6  # noqa: E402

R = S6.R
F, D, HU, H2, P = R.F, R.D, R.HU, R.H2, R.P
VERSION = "hurricane9-screen7-v1"
ROUND = 7
TOP_N, PER_SYSTEM = 50, 1       # per track, as screen.py
TOLERANCE = S6.TOLERANCE        # the committed table is rounded to four decimals
ELEMENTS = (2, 6)               # round 6: 2 to 5
MAX_ATOMS = 100                 # atoms in the primitive cell; round 6: 40. Hurricane reads the composition only
GAP_MAX = 1.0                   # eV, as round 6
EHULL_MAX = 0.05                # eV/atom, as round 6
MIN_ELEMENT = 20                # an element must occur in at least this many training materials, as round 6
NEAR = 0.02                     # the same elements and every share within 2 at.%: the same material (screen.NEAR)
PRESSURE_MAX = 1.0e5            # kPa (0.1 GPa): a COD structure determined above it is left out
MP_VERSION = "2025-09-25"
MP_BUCKET = "https://materialsproject-build.s3.amazonaws.com"
ALEXANDRIA_RELEASE = "2025.07.02"
ALEXANDRIA_URL = f"https://alexandria.icams.rub.de/data/pbe/{ALEXANDRIA_RELEASE}/convex_hull.json.bz2"
COD_HOST, COD_USER, COD_DB = "www.crystallography.net", "cod_reader", "cod"      # the COD's public read-only database
# What the count-only run of 2026-11-11 read. A run that reads anything else stops and writes nothing.
JARVIS_ROWS_SHA256 = None
MP_FILES_SHA256 = "c4464ec53f0c2d27395bc622bc43faa18985d1d0bb53ace5f0d0f6b6f74ffd45"       # of the SHA-256 of the build's 21 summary files, in order
ALEXANDRIA_SHA256 = "8e3206c2f3623c0931ce5b0c3aa62ba83905b4838e4660fd6f2067c55c5bbb8e"
DECLARATION = P.ROOT / "results" / "validation" / "hurricane9-screen7-declaration-v1.md"
RELEASED, BACKGROUND = S6.RELEASED, S6.BACKGROUND
COD_SNAPSHOT = "screen_round7_cod.csv.gz"
COD_NOTE = "screen_round7_cod.json"
POOL_FILE = "screen_round7_pool.csv.gz"
JARVIS, MP, ALEX, COD = "JARVIS-DFT", "Materials Project", "Alexandria", "COD"
ORDER = [JARVIS, MP, ALEX, COD]     # which record stands for a composition that several sources hold
SOURCES = {
    JARVIS: {"what": "JARVIS-DFT 3D (dft_3d), as jarvis-tools serves it", "licence": "public data of NIST",
             "cite": "K. Choudhary et al., The joint automated repository for various integrated simulations (JARVIS) for data-driven "
                     "materials design, npj Comput. Mater. 6, 173 (2020)", "doi": "10.1038/s41524-020-00440-1",
             "experimental": "the entry has an ICSD number", "gap": "optb88vdw_bandgap",
             "sha256": JARVIS_ROWS_SHA256, "sha256_of": "one line for each row in the file's order: identifier, formation energy per atom, "
                                                        "band gap, atoms per cell, whether it has an ICSD number",
             "hull": "computed in the run from the file's formation energies; the file's ehull field is not read"},
    MP: {"what": f"Materials Project, build {MP_VERSION}, summary collection from its AWS Open Data bucket", "licence": "CC BY 4.0",
         "cite": "A. Jain et al., Commentary: The Materials Project: A materials genome approach to accelerating materials innovation, "
                 "APL Mater. 1, 011002 (2013)", "doi": "10.1063/1.4812323", "url": MP_BUCKET + f"/collections/{MP_VERSION}/summary/",
         "left_out": "entries not marked BY-C (those marked BY-NC come from GNoME) and deprecated entries",
         "experimental": "theoretical is false", "gap": "band_gap", "hull": "energy_above_hull",
         "sha256": MP_FILES_SHA256, "sha256_of": "the SHA-256 of each summary file of the build, in order, written one after the other"},
    ALEX: {"what": f"Alexandria PBE convex hull, release {ALEXANDRIA_RELEASE}", "licence": "CC BY 4.0", "url": ALEXANDRIA_URL,
           "cite": "J. Schmidt et al., Machine-learning-assisted determination of the global zero-temperature phase diagram of materials, "
                   "Adv. Mater. 35, 2210788 (2023)", "doi": "10.1002/adma.202210788",
           "experimental": "none: the release does not say which entries are experimental", "gap": "band_gap_ind",
           "hull": "e_above_hull, or e_phase_separation (not below zero) where that is empty", "sha256": ALEXANDRIA_SHA256,
           "sha256_of": "the file convex_hull.json.bz2"},
    COD: {"what": "Crystallography Open Database, its own table, read once from its public read-only database; the usable rows are "
                  "stored in results/" + COD_SNAPSHOT + " and every run screens the stored rows", "licence": "public domain",
          "cite": "S. Grazulis et al., Crystallography Open Database - an open-access collection of crystal structures, J. Appl. Cryst. 42, "
                  "726 (2009); S. Grazulis et al., Nucleic Acids Res. 40, D420 (2012)", "doi": "10.1107/S0021889809016690",
          "url": "https://www.crystallography.net/cod/",
          "experimental": "every entry, except those marked theoretical, retracted, with errors or warnings, on hold or as a duplicate, "
                          "those without coordinates and those determined above 0.1 GPa",
          "gap": "none of its own: the gap of the reference calculation of the same material",
          "hull": "none; not needed for an experimental structure"},
}
PROTOCOL = {
    "name": "hurricane9-screen7-protocol-v1", "module": VERSION, "screening_round": ROUND,
    "model": {"name": HU.MODEL, "version": R.MODEL_VERSION, "release_protocol": R.PROTOCOL["name"],
              "release_protocol_sha256": R.protocol_sha256(),
              "status": "the version in use; this run releases, tunes and compares nothing"},
    "sources": SOURCES,
    "pool": {
        "unit": "a composition (shares to four decimals); Hurricane reads nothing else, so each composition is judged once",
        "same_material": f"the same elements and every share within {NEAR * 100:g} at.% (screen.NEAR)",
        "reference": "the calculated entry that speaks for a composition: among the entries of that composition in JARVIS-DFT, the "
                     "Materials Project and Alexandria that have a band gap, one marked experimental before any other, then one that "
                     f"its source puts at most {EHULL_MAX * 1000:g} meV/atom above its convex hull before one further away, then by "
                     "source in the order " + ", ".join(ORDER[:3]) + ", then the one closest to its source's hull, then the "
                     "identifier. Distances to a hull are compared as numbers within one source only",
        "size": f"{ELEMENTS[0]} to {ELEMENTS[1]} elements; no hydrogen, noble gas or short-lived radioactive element; at most {MAX_ATOMS} "
                f"atoms in the primitive cell of the entry that stands for the compound; every element in at least {MIN_ELEMENT} of the "
                "released training rows",
        "gap": f"the reference calculation has a band gap of at most {GAP_MAX:g} eV. A COD entry takes the reference calculation of the "
               "same material (of several, the first in the order above): it is left out if that gap is wider, and stays, marked, if "
               "no calculated entry of the same material has a gap",
        "experimental": "a compound for which a source holds an experimental structure of the same material (an entry marked "
                        "experimental in JARVIS-DFT or the Materials Project, or a usable COD entry); no rule on the distance to a "
                        "convex hull. The structure named is one with the space group of the reference calculation if there is one",
        "computed": f"any other compound, if its reference calculation lies at most {EHULL_MAX * 1000:g} meV/atom above the convex hull "
                    "of its source",
        "jarvis_hull": "the lowest energy that a mixture of JARVIS-DFT entries of the same overall composition can have, from the "
                       "file's formation energies with the elements at zero (a linear programme); an entry's distance is its "
                       "formation energy minus that",
        "left_out": "as round 6: every material that SuperCon, 3DSC, the computed-Tc data or the list of others' claims has, every "
                    "compound made of exactly the elements of a known superconductor (screen.known_lists), every composition for "
                    "which JARVIS-DFT gives a computed Tc, and every compound whose composition the datasheet lists",
        "one_per_composition": "the reference calculation, with its cell and atoms, stands for its composition; a measured COD "
                               "composition that no calculated entry has stands for itself (of several COD entries, the lowest number)"},
    "routing": "Radar refitted on its 3DSC rows, as screen.radar_scores, with each entry's cell, atoms per cell and space group; a "
               "compound is sent to Hurricane when the probability of an unconventional family is at least one half",
    "chance": "the classifiers of hurricane9_release.guard, one for each of five folds by a hash of the chemical system "
              "(hurricane3.bg_fold): a compound's chance comes from the classifier of its fold, which learned from no background "
              "compound of that fold",
    "must_reproduce": {"file": "results/" + BACKGROUND, "what": "for the released background: the same compounds in the same order, the "
                       "same Radar routing, the same not-known answers and every chance within the tolerance; and the classifiers "
                       "that score the pool give those chances exactly", "tolerance": TOLERANCE, "otherwise": "the run stops and writes nothing"},
    "tc": "hurricane9_release.Design9().fit_regressor on the released training rows; the 90% range is the released width on "
          "log(1 + Tc), read from results/" + RELEASED,
    "listed": {"sent": "Radar's probability of an unconventional family is at least one half",
               "inside": "the distance ratio is at most the guard's abstention; a compound further away is not known and not listed",
               "order": "the chance times the Tc if it superconducts, then that Tc, then the source and identifier",
               "tracks": ["experimental", "computed"], "per_chemical_system": PER_SYSTEM, "top_per_track": TOP_N},
    "written": [f"results/screen_round{ROUND}.json", f"results/screen_round{ROUND}_hurricane.csv (the compounds Hurricane gives a chance)",
                "results/" + POOL_FILE + " (every compound of the pool)", "results/" + COD_SNAPSHOT + " and results/" + COD_NOTE
                + " (if they are not there yet)",
                "progress/progress.json: screen.hurricane, screen.models, the detail of the screen stage and one log entry"],
    "unchanged": "Storm's list and every other field of the screen block, as screening round 5 published them",
}
CAVEAT = S6.CAVEAT
NOT_KNOWN = S6.NOT_KNOWN
NO_GAP = "no calculated band gap"
COLUMNS = ["id", "source", "formula", "chemsys", "track", "experimental", "labels", "nat", "spg", "spg_number", "ehull", "gap", "gap_from",
           "magmom", "p_unconventional", "family", "hurricane_tc", "p_sc", "tc_sc", "lo", "hi", "types", "novelty", "nearest_training",
           "nearest_training_tc", "not_known"]
COD_COLUMNS = ["file", "a", "b", "c", "alpha", "beta", "gamma", "vol", "nel", "sg", "sgNumber", "formula", "calcformula", "cellformula", "Z",
               "cellpressure", "diffrpressure", "year", "doi", "method", "flags", "status", "duplicateof", "onhold"]
TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?$")


def protocol_text() -> str:
    return json.dumps(PROTOCOL, sort_keys=True, separators=(",", ":"))


def protocol_sha256() -> str:
    return hashlib.sha256(protocol_text().encode("utf-8")).hexdigest()


def pretty(comp: dict) -> str:
    return S6.pretty(comp)


def num(v):
    """A finite float, or None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ---------------------------------------------------------------- the sources, as records of one form
def record(db: str, ident, comp: dict, nat, gap, hull, magmom, experimental: bool, lattice, spg_number, spg, elements=None, frac=None,
           **more) -> dict:
    """One entry of a source. comp: element -> amount; nat: atoms in the primitive cell; lattice: its three vectors."""
    return dict({"db": db, "id": str(ident), "comp": {str(e): float(v) for e, v in comp.items() if float(v) > 0}, "nat": num(nat),
                 "gap": num(gap), "hull": num(hull), "magmom": num(magmom), "experimental": bool(experimental),
                 "lattice": None if lattice is None else np.asarray(lattice, float),
                 "spg_number": None if num(spg_number) is None else int(num(spg_number)), "spg": str(spg or "").replace(" ", "") or None,
                 "elements": None if elements is None else tuple(elements),
                 "frac": None if frac is None else np.asarray(frac, np.float32)}, **more)


def slim(r: dict) -> dict:
    """A record without its cell and atoms: all that an entry which cannot enter the pool still has to say (its
    composition, its gap, whether it is experimental)."""
    r["lattice"] = r["elements"] = r["frac"] = None
    return r


def ordered_sites(structure: dict):
    """Elements and fractional coordinates of a pymatgen structure dictionary, or None if a site is shared or partly empty."""
    elements, frac = [], []
    for s in structure.get("sites") or []:
        sp = s.get("species") or []
        if len(sp) != 1 or abs(float(sp[0].get("occu", 1.0)) - 1.0) > 1e-6:
            return None
        m = re.match(r"[A-Z][a-z]?", str(sp[0].get("element", "")))
        if not m or s.get("abc") is None:
            return None
        elements.append(m.group(0))
        frac.append([round(float(x) % 1.0, 5) for x in s["abc"]])
    return (elements, frac) if elements else None


def mp_record(doc: dict):
    """A Materials Project summary document as a record; None for one that is not used (not marked BY-C, deprecated,
    without a structure, or with a shared or partly empty site)."""
    if (doc.get("builder_meta") or {}).get("license") != "BY-C" or doc.get("deprecated") is not False:
        return None
    st = doc.get("structure") or {}
    sites = ordered_sites(st)
    if sites is None or not isinstance((st.get("lattice") or {}).get("matrix"), list):
        return None
    sym = doc.get("symmetry") or {}
    return record(MP, doc.get("material_id"), collections.Counter(sites[0]), len(sites[0]), doc.get("band_gap"), doc.get("energy_above_hull"),
                  doc.get("total_magnetization"), doc.get("theoretical") is False, st["lattice"]["matrix"], sym.get("number"), sym.get("symbol"),
                  sites[0], sites[1])


def alexandria_record(entry: dict):
    """An entry of the Alexandria convex-hull file as a record."""
    st, data = entry.get("structure") or {}, entry.get("data") or {}
    sites = ordered_sites(st)
    if sites is None or not isinstance((st.get("lattice") or {}).get("matrix"), list):
        return None
    hull = num(data.get("e_above_hull"))
    if hull is None and num(data.get("e_phase_separation")) is not None:
        hull = max(num(data.get("e_phase_separation")), 0.0)
    n = num(data.get("spg"))
    return record(ALEX, data.get("mat_id"), collections.Counter(sites[0]), len(sites[0]), data.get("band_gap_ind"), hull, data.get("total_mag"),
                  False, st["lattice"]["matrix"], n, spg_symbol(n), sites[0], sites[1])


def jarvis_record(row, hull=None):
    """A row of screen.load_rows as a record; the hull distance is the one computed here, never the file's field."""
    import screen as SC
    a = row["atoms"]
    return record(JARVIS, row["id"], row["comp"], row["nat"], row["gap"], hull, row["magmom"], bool(row["icsd"]), a["lattice_mat"],
                  row["spg_number"], row["spg"], list(a["elements"]), np.round(SC.frac_coords(a), 5).tolist(),
                  jarvis_tc=num(row.get("jarvis_tc")), e_form=num(row.get("e_form")))


def cod_formula(text) -> dict | None:
    """The amounts of a COD formula such as "- Ba2 Cu1.16 Hg0.84 O4.19 -"; None if a token is not an element with an amount."""
    out = collections.Counter()
    for token in str(text or "").replace("-", " ").split():
        m = TOKEN.match(token)
        if not m:
            return None
        out[m.group(1)] += float(m.group(2)) if m.group(2) else 1.0
    return dict(out) if out and all(v > 0 for v in out.values()) else None


def cell_matrix(a, b, c, alpha, beta, gamma) -> np.ndarray:
    """The three cell vectors from the lengths and angles (degrees)."""
    al, be, ga = (math.radians(x) for x in (alpha, beta, gamma))
    cx = c * math.cos(be)
    cy = c * (math.cos(al) - math.cos(be) * math.cos(ga)) / math.sin(ga)
    return np.array([[a, 0.0, 0.0], [b * math.cos(ga), b * math.sin(ga), 0.0], [cx, cy, math.sqrt(max(c * c - cx * cx - cy * cy, 0.0))]])


CENTRING = {"P": (np.eye(3), 1),
            "I": (np.array([[-0.5, 0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5]]), 2),
            "F": (np.array([[0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]), 4),
            "A": (np.array([[1.0, 0.0, 0.0], [0.0, 0.5, -0.5], [0.0, 0.5, 0.5]]), 2),
            "B": (np.array([[0.5, 0.0, -0.5], [0.0, 1.0, 0.0], [0.5, 0.0, 0.5]]), 2),
            "C": (np.array([[0.5, -0.5, 0.0], [0.5, 0.5, 0.0], [0.0, 0.0, 1.0]]), 2),
            "R": (np.array([[2 / 3, 1 / 3, 1 / 3], [-1 / 3, 1 / 3, 1 / 3], [-1 / 3, -2 / 3, 1 / 3]]), 3)}


def primitive(lattice: np.ndarray, symbol: str, angles) -> tuple[np.ndarray, int]:
    """The primitive cell of a conventional cell with the centring its space-group symbol names, and how many primitive
    cells the conventional one holds. An R cell on rhombohedral axes is primitive already."""
    letter = str(symbol or "P").strip()[:1].upper()
    if letter == "R":
        hexagonal = ":H" in symbol.upper() or (":R" not in symbol.upper() and abs(angles[0] - 90) < 1 and abs(angles[1] - 90) < 1
                                               and abs(angles[2] - 120) < 1)
        if not hexagonal:
            return lattice, 1
    t, mult = CENTRING.get(letter, CENTRING["P"])
    return t @ lattice, mult


def cod_record(row: dict, reasons: collections.Counter | None = None):
    """A row of the COD's table as a record, or None with the reason counted. The composition is the one computed from
    the atoms of the entry with their occupancies (calcformula)."""
    def no(reason):
        if reasons is not None:
            reasons[reason] += 1
        return None
    blank = lambda v: v is None or str(v).strip() in ("", "NULL", "None")   # noqa: E731
    if str(row.get("method") or "") == "theoretical":
        return no("marked theoretical")
    if not blank(row.get("status")) or not blank(row.get("onhold")):
        return no("retracted, with errors or warnings, or on hold")
    if not blank(row.get("duplicateof")):
        return no("marked as a duplicate")
    if "has coordinates" not in str(row.get("flags") or ""):
        return no("no coordinates")
    comp = cod_formula(row.get("calcformula"))
    if comp is None:
        return no("no readable composition")
    if set(comp) & {"H", "D", "T"}:
        return no("hydrogen")
    if max(num(row.get("cellpressure")) or 0.0, num(row.get("diffrpressure")) or 0.0) > PRESSURE_MAX:
        return no("determined above 0.1 GPa")
    cell = [num(row.get(k)) for k in ("a", "b", "c", "alpha", "beta", "gamma")]
    number = num(row.get("sgNumber"))
    if any(v is None or v <= 0 for v in cell) or not 0 < cell[5] < 180 or number is None or not 1 <= number <= 230:
        return no("no cell or space-group number")
    symbol = str(row.get("sg") or "")
    lat, mult = primitive(cell_matrix(*cell), symbol, cell[3:])
    in_cell = cod_formula(row.get("cellformula"))
    n_cell = sum(in_cell.values()) if in_cell else (num(row.get("Z")) or 0.0) * sum(comp.values())
    if n_cell <= 0 or abs(float(np.linalg.det(lat))) < 1e-6:
        return no("no atoms per cell")
    return record(COD, int(float(row["file"])), comp, n_cell / mult, None, None, None, True, lat, number, symbol.split(":")[0],
                  published=str(row.get("formula") or "").strip("- ").strip() or None, year=None if num(row.get("year")) is None else int(num(row.get("year"))),
                  doi=str(row.get("doi") or "").strip() or None)


@functools.lru_cache(maxsize=None)
def spg_symbol(number) -> str | None:
    """The international symbol of a space-group number (Radar reads only its first letter, the centring)."""
    try:
        from pymatgen.symmetry.groups import sg_symbol_from_int_number
        return str(sg_symbol_from_int_number(int(number)))
    except Exception:
        return None


# ---------------------------------------------------------------- reading the sources
def source_folder() -> Path:
    """Where a run keeps the files it downloads from the Materials Project and Alexandria: a temporary folder, not the
    data cache that the workflow saves after every run (the two dated sources are 0.6 GB together)."""
    return Path(os.environ.get("SUPERCON_POOL_SOURCES") or Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "supercon-pool-sources")


def fetch(url: str, path: Path) -> Path:
    """A file from the folder, or from the network into it."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "supercon-ml (github.com/diracmagic/supercon-ml)"})
        tmp = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(req, timeout=600) as r, open(tmp, "wb") as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        tmp.replace(path)
    return path


def same_source(name: str, got: str, want) -> None:
    """Stop unless a source is, hash for hash, the one the protocol names."""
    if want is not None and got != want:
        raise SystemExit(f"{name} is not what this protocol names (SHA-256 {got}, not {want}); nothing is written")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mp_keys() -> list:
    """The files of the build's summary collection in the public bucket: (key, bytes), in order."""
    ns, keys, token = "{http://s3.amazonaws.com/doc/2006-03-01/}", [], None
    while True:
        q = {"list-type": "2", "prefix": f"collections/{MP_VERSION}/summary/"}
        if token:
            q["continuation-token"] = token
        with urllib.request.urlopen(MP_BUCKET + "/?" + urllib.parse.urlencode(q), timeout=120) as r:
            root = ET.fromstring(r.read())
        keys += [(e.findtext(ns + "Key"), int(e.findtext(ns + "Size") or 0)) for e in root.findall(ns + "Contents")]
        if root.findtext(ns + "IsTruncated") != "true":
            return sorted(k for k in keys if k[0].endswith(".jsonl.gz"))
        token = root.findtext(ns + "NextContinuationToken")


def read_mp(cache: Path, keep=None) -> tuple[list, dict]:
    """Every used record of the Materials Project build; keep(record) says whose cell and atoms are kept."""
    keys = mp_keys()
    if not keys:
        raise SystemExit(f"the Materials Project bucket lists no summary file for build {MP_VERSION}; nothing is written")
    paths = [fetch(MP_BUCKET + "/" + key, cache / "mp" / MP_VERSION / key.split("/")[-1]) for key, _ in keys]
    digest = hashlib.sha256("".join(sha256_file(path) for path in paths).encode()).hexdigest()
    same_source(f"the Materials Project build {MP_VERSION}", digest, MP_FILES_SHA256)
    out, n = [], 0
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    n += 1
                    rec = mp_record(json.loads(line))
                    if rec is not None:
                        out.append(rec if keep is None or keep(rec) else slim(rec))
    return out, {"build": MP_VERSION, "files": len(keys), "bytes": sum(s for _, s in keys), "documents": n, "used": len(out),
                 "sha256_of_the_files_sha256": digest}


class Finite(io.RawIOBase):
    """A JSON byte stream with its bare NaN and Infinity tokens written as null (strict readers refuse them)."""
    token = re.compile(rb"(?<=[\[,:\s])-?(?:NaN|Infinity)(?=[\s,\]\}])")

    def __init__(self, fh, chunk: int = 1 << 22):
        self.fh, self.chunk, self.buf, self.eof, self.prev = fh, chunk, b"", False, b" "
        self.out, self.pos = memoryview(b""), 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while self.pos >= len(self.out) and not (self.eof and not self.buf):
            data = self.fh.read(self.chunk)
            if data:
                self.buf += data
            else:
                self.eof = True
            cut = len(self.buf) if self.eof else max(self.buf.rfind(b","), self.buf.rfind(b"]"), self.buf.rfind(b"}")) + 1
            if cut <= 0:
                continue
            head, self.buf = self.buf[:cut], self.buf[cut:]
            self.out, self.pos = memoryview(self.token.sub(b"null", self.prev + head)[len(self.prev):]), 0
            self.prev = head[-1:] or self.prev
        n = min(len(b), len(self.out) - self.pos)
        b[:n] = self.out[self.pos:self.pos + n]
        self.pos += n
        return n


def read_alexandria(cache: Path, keep=None) -> tuple[list, dict]:
    """Every record of the Alexandria convex-hull file, read as a stream; keep(record) says whose cell and atoms are kept."""
    import ijson
    path = fetch(ALEXANDRIA_URL, cache / "alexandria" / ALEXANDRIA_RELEASE / "convex_hull.json.bz2")
    digest = sha256_file(path)
    same_source(f"the Alexandria release {ALEXANDRIA_RELEASE}", digest, ALEXANDRIA_SHA256)
    out, n = [], 0
    with bz2.open(path, "rb") as raw:
        for entry in ijson.items(io.BufferedReader(Finite(raw), buffer_size=1 << 20), "entries.item", use_float=True):
            n += 1
            rec = alexandria_record(entry)
            if rec is not None:
                out.append(rec if keep is None or keep(rec) else slim(rec))
    return out, {"release": ALEXANDRIA_RELEASE, "bytes": path.stat().st_size, "sha256": digest, "entries": n, "used": len(out)}


def query_cod() -> list:
    """The rows of the COD's table that can enter the pool by their number of elements, read from its public database."""
    import pymysql
    no_h = "formula NOT REGEXP ' [HDT][0-9. ]'"
    sql = (f"SELECT {', '.join(COD_COLUMNS)} FROM data WHERE CAST(nel AS UNSIGNED) BETWEEN {ELEMENTS[0]} AND {ELEMENTS[1]} AND {no_h} "
           "ORDER BY file")
    last = None
    for attempt in range(3):
        try:
            con = pymysql.connect(host=COD_HOST, user=COD_USER, password="", database=COD_DB, connect_timeout=60, read_timeout=1800)
            try:
                with con.cursor() as cur:
                    cur.execute(sql)
                    return [{k: (v.decode("utf-8", "replace") if isinstance(v, bytes) else v) for k, v in zip(COD_COLUMNS, row)} for row in cur.fetchall()]
            finally:
                con.close()
        except Exception as exc:        # the public server is busy at times
            last = exc
            time.sleep(30 * (attempt + 1))
    raise SystemExit(f"the COD's public database could not be read ({type(last).__name__}: {str(last)[:200]}); nothing is written")


def cod_snapshot(folder: Path) -> dict:
    """Read the COD's public database once and store the usable rows (COD_SNAPSHOT) with a note of the reading
    (COD_NOTE) in the folder. Every run screens the stored rows, so a later run screens what an earlier one did."""
    rows = query_cod()
    reasons = collections.Counter()
    used = {r["id"] for r in (cod_record(row, reasons) for row in rows) if r is not None}
    keep = [row for row in rows if str(int(float(row["file"]))) in used]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COD_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in keep:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in COD_COLUMNS})
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / COD_SNAPSHOT, "wb") as fh, gzip.GzipFile(filename="", fileobj=fh, mode="wb", mtime=0) as gz:      # no name and no time inside the file
        gz.write(buf.getvalue().encode("utf-8"))
    note = {"read_at": P.now_iso(), "from": f"the COD's public read-only database ({COD_HOST}, database {COD_DB})",
            "rows_read": len(rows), "what": f"entries with {ELEMENTS[0]} to {ELEMENTS[1]} elements and no hydrogen", "left_out": dict(sorted(reasons.items())),
            "rows_stored": len(keep), "file": "results/" + COD_SNAPSHOT, "sha256": sha256_file(folder / COD_SNAPSHOT),
            "licence": SOURCES[COD]["licence"], "cite": SOURCES[COD]["cite"]}
    (folder / COD_NOTE).write_text(json.dumps(note, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return note


def read_cod(folder: Path) -> tuple[list, dict]:
    """The usable COD records, from the stored rows."""
    path = folder / COD_SNAPSHOT
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    recs = [r for r in (cod_record(row) for row in rows) if r is not None]
    note = json.loads((folder / COD_NOTE).read_text(encoding="utf-8")) if (folder / COD_NOTE).is_file() else {}
    digest = sha256_file(path)
    if note.get("sha256") not in (None, digest):
        raise SystemExit(f"results/{COD_SNAPSHOT} is not the file its note describes; nothing is written")
    return recs, {"read_at": note.get("read_at"), "rows_read": note.get("rows_read"), "left_out": note.get("left_out"), "rows_stored": len(rows),
                  "used": len(recs), "sha256": digest}


# ---------------------------------------------------------------- the hull of JARVIS-DFT's own formation energies
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


def jarvis_records(rows, counts: dict) -> tuple[list, dict]:
    """Every JARVIS-DFT row as a record, with its distance to the hull of the file's own formation energies; the file's
    ehull field is not read. The rows that cannot enter the pool by size, gap or elements lose their cell and atoms."""
    recs = [jarvis_record(r) for _, r in rows.iterrows()]
    digest = hashlib.sha256("".join(f"{r['id']}|{r['e_form']!r}|{r['gap']!r}|{r['nat']!r}|{int(r['experimental'])}\n" for r in recs).encode()).hexdigest()
    same_source("JARVIS-DFT 3D as jarvis-tools serves it", digest, JARVIS_ROWS_SHA256)
    can = [size_ok(r) and gap_ok(r) and covered(r, counts) for r in recs]
    need = [i for i, r in enumerate(recs) if r["e_form"] is not None]
    entries = [(r["comp"], r["e_form"]) for r in recs if r["e_form"] is not None]
    t0 = time.time()
    hull = hull_energies(entries, [recs[i]["comp"] for i in need])
    for i, e in zip(need, hull):
        recs[i]["hull"] = max(recs[i]["e_form"] - float(e), 0.0)
    within = sum(1 for i in need if recs[i]["hull"] <= EHULL_MAX)
    info = {"rows": len(recs), "rows_sha256": digest, "with_a_formation_energy": len(entries), "hull_distance_computed_for": len(need),
            "of_them_within_50_meV": within, "seconds": round(time.time() - t0, 1), "against_pymatgen": hull_check(recs, need)}
    for r, ok in zip(recs, can):
        if not ok:
            slim(r)
    return recs, info


def hull_check(recs: list, need: list, sample: int = 300, seed: int = F.SEED) -> dict:
    """The linear programme against pymatgen's phase diagram, for a seeded sample of the entries: the two must agree."""
    try:
        from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram
        from pymatgen.core import Composition
    except ImportError:
        return {"skipped": "pymatgen is not installed"}
    by_system = collections.defaultdict(list)
    for r in recs:
        if r["e_form"] is not None and r["e_form"] < 0:
            by_system[frozenset(r["comp"])].append(r)
    rng = np.random.default_rng(seed)
    pick = sorted(rng.choice(len(need), size=min(sample, len(need)), replace=False).tolist()) if need else []
    worst = 0.0
    for j in pick:
        r = recs[need[j]]
        system = frozenset(r["comp"])
        entries = [PDEntry(Composition(x["comp"]), x["e_form"] * sum(x["comp"].values())) for s, members in by_system.items() if s <= system for x in members]
        entries += [PDEntry(Composition({e: 1}), 0.0) for e in system]
        e = min(float(PhaseDiagram(entries).get_hull_energy_per_atom(Composition(r["comp"]))), 0.0)
        worst = max(worst, abs(max(r["e_form"] - e, 0.0) - r["hull"]))
    if worst > 1e-4:
        raise SystemExit(f"the hull distance of this module differs from pymatgen's by {worst:.2e} eV/atom; nothing is written")
    return {"entries_compared": len(pick), "largest_difference_eV_per_atom": round(worst, 9)}


# ---------------------------------------------------------------- the pool
def size_ok(r: dict) -> bool:
    import screen as SC
    return (ELEMENTS[0] <= len(r["comp"]) <= ELEMENTS[1] and not (set(r["comp"]) & SC.BAD) and r["nat"] is not None
            and r["nat"] <= MAX_ATOMS + 1e-9)


def gap_ok(r: dict) -> bool:
    return r["gap"] is not None and r["gap"] <= GAP_MAX


def covered(r: dict, counts: dict) -> bool:
    return all(counts.get(e, 0) >= MIN_ELEMENT for e in r["comp"])


def tag(r: dict) -> str:
    return f"{r['db']} {r['id']}"


class Materials:
    """Entries grouped by their set of elements, to find those of the same material: the same elements and every share
    within NEAR (the rule of screen.Known)."""

    def __init__(self):
        self.by_set = {}

    def add(self, comp: dict, item) -> None:
        key = tuple(sorted(comp))
        tot = float(sum(comp.values()))
        bucket = self.by_set.setdefault(key, [[], [], None])
        bucket[0].append([comp[e] / tot for e in key])
        bucket[1].append(item)
        bucket[2] = None

    def near(self, comp: dict) -> list:
        key = tuple(sorted(comp))
        bucket = self.by_set.get(key)
        if bucket is None:
            return []
        if bucket[2] is None:
            bucket[2] = np.asarray(bucket[0], float)
        tot = float(sum(comp.values()))
        hit = np.flatnonzero(np.max(np.abs(bucket[2] - np.array([comp[e] / tot for e in key])), axis=1) <= NEAR + 1e-9)
        return [bucket[1][int(i)] for i in hit]


def by_id(r: dict) -> tuple:
    return (len(r["id"]), r["id"])          # numbers in their order


def reference_order(r: dict) -> tuple:
    """Which calculated entry speaks for a material: one marked experimental before any other, then one that its source
    puts within EHULL_MAX of its convex hull before one further away, then by source in the order of ORDER, then the one
    closest to its source's hull. Distances are compared as numbers within one source only."""
    hull = math.inf if r["hull"] is None else r["hull"]
    return (not r["experimental"], not hull <= EHULL_MAX, ORDER.index(r["db"]), hull, by_id(r))


def experimental_structure(near: list, ref: dict):
    """Of the experimental structures of a material, the one to name next to its reference calculation: one with the
    reference's space group first, then by source, then the identifier."""
    if not near:
        return None
    return min(near, key=lambda e: (e["spg_number"] is None or e["spg_number"] != ref["spg_number"], ORDER.index(e["db"]), by_id(e)))


def assemble(calculated: list, cod: list, counts: dict, known: list, datasheet=None) -> tuple[list, dict]:
    """The pool: one record per composition, each with its track ("experimental" or "computed"), the experimental
    structure that puts it on the first track, and its marks. calculated: every record of the three calculated sources
    (those that cannot enter still say which materials have an experimental structure, and a wide gap of the entry that
    speaks for a material keeps that material out); cod: the usable COD records."""
    made = Materials()                       # the experimental structures
    for r in calculated:
        if r["experimental"]:
            made.add(r["comp"], r)
    for r in cod:
        made.add(r["comp"], r)
    steps = {db: collections.Counter() for db in ORDER}
    groups, with_tc = collections.defaultdict(list), set()
    for r in calculated:
        steps[r["db"]]["entries"] += 1
        key = P._composition_key(r["comp"])
        if r.get("jarvis_tc") is not None:
            with_tc.add(key)
        if r["gap"] is not None:
            groups[key].append(r)
    refs, cands, other_group = Materials(), [], 0
    for key, members in groups.items():      # the reference calculation of each composition decides for it
        ref = min(members, key=reference_order)
        refs.add(ref["comp"], ref)
        st = steps[ref["db"]]
        st["reference calculations, one per composition"] += 1
        if not size_ok(ref):
            continue
        st["size and elements"] += 1
        if not gap_ok(ref):
            continue
        st["band gap at most 1 eV"] += 1
        if not covered(ref, counts):
            continue
        st["elements the training data cover"] += 1
        evidence = ref if ref["experimental"] else experimental_structure(made.near(ref["comp"]), ref)
        if evidence is None and not (ref["hull"] is not None and ref["hull"] <= EHULL_MAX):
            continue
        st["an experimental structure, or within 50 meV/atom of the hull"] += 1
        same = None if evidence is None or evidence is ref else bool(evidence["spg_number"] is not None and evidence["spg_number"] == ref["spg_number"])
        cands.append(dict(ref, key=key, track="experimental" if evidence else "computed", evidence=tag(evidence) if evidence else None,
                          same_space_group=same, gap_from=None, labels=[]))
    for r in cod:                            # a measured composition takes the gap of the reference calculation of the same material
        st = steps[COD]
        st["entries"] += 1
        if not size_ok(r):
            continue
        st["size and elements"] += 1
        if not covered(r, counts):
            continue
        st["elements the training data cover"] += 1
        near = refs.near(r["comp"])
        ref = min(near, key=reference_order) if near else None
        if ref is not None and not gap_ok(ref):
            continue
        st["band gap of the reference calculation at most 1 eV, or no calculation"] += 1
        cands.append(dict(r, key=P._composition_key(r["comp"]), gap=None if ref is None else ref["gap"], track="experimental", evidence=tag(r),
                          same_space_group=None, gap_from=tag(ref) if ref else None, labels=[] if ref else [NO_GAP]))
    excluded, kept = collections.Counter(), []
    for r in cands:
        reason = next((k.name for k in known if k.match(r["comp"])), None)
        if reason is None and r["key"] in with_tc:
            reason = "computed"
        if reason is None and datasheet is not None and datasheet.match(r["comp"]) is not None:
            reason = "datasheet"
        if reason:
            excluded[reason] += 1
            continue
        steps[r["db"]]["no superconductivity record"] += 1
        kept.append(r)
    groups = collections.defaultdict(list)
    for r in kept:
        groups[r.pop("key")].append(r)
    pool = []
    for members in groups.values():          # the reference calculation, with its cell and atoms, before a COD entry of that composition
        members.sort(key=lambda r: (r["db"] == COD, ORDER.index(r["db"]), by_id(r)))
        first = dict(members[0])
        first["track"] = "experimental" if any(m["track"] == "experimental" for m in members) else "computed"
        first["evidence"] = next((m["evidence"] for m in members if m["evidence"]), None)
        first["also"] = [tag(m) for m in members[1:]][:5]
        first["chemsys"] = "-".join(sorted(first["comp"]))
        pool.append(first)
        steps[first["db"]]["one per composition"] += 1
        other_group += first["same_space_group"] is False
    pool.sort(key=lambda r: (ORDER.index(r["db"]), by_id(r)))
    info = {"steps": {db: dict(steps[db]) for db in ORDER}, "excluded": dict(excluded) | {"total": int(sum(excluded.values()))},
            "pool": len(pool), "tracks": dict(collections.Counter(r["track"] for r in pool)),
            "chemical_systems": len({r["chemsys"] for r in pool}),
            "by_source": {t: dict(collections.Counter(r["db"] for r in pool if r["track"] == t)) for t in PROTOCOL["listed"]["tracks"]},
            "no_calculated_gap": sum(1 for r in pool if NO_GAP in r["labels"]),
            "experimental_structure_in_another_space_group": int(other_group)}
    return pool, info


# ---------------------------------------------------------------- Radar's routing
def structure_of(r: dict) -> dict:
    """Radar's structure description of a record (screen.radar_structure) from its primitive cell, its atoms per cell,
    which need not be whole for a measured composition, and its space group."""
    import screen as SC
    st = SC.radar_structure({"lattice_mat": r["lattice"], "elements": [None]}, float("nan") if r["spg_number"] is None else float(r["spg_number"]),
                            r["spg"] or "")
    st["vpa"] = st["vpa"] / r["nat"] if r["nat"] else float("nan")
    return st


def radar_route(pool: list) -> tuple[np.ndarray, dict]:
    """screen.radar_scores for records of any source: Radar refitted on all of its 3DSC rows, applied to the pool."""
    import pandas as pd
    import screen as SC
    H, RD = SC.H, SC.RD
    dsc = H.load_3dsc()
    unc, con = H.build_frame(dsc, RD.UNCONV), H.build_frame(dsc, RD.CONV)
    df = pd.concat([unc.assign(y=1), con.assign(y=0)], ignore_index=True)
    df = df.drop_duplicates(subset="formula_sc", keep=False).reset_index(drop=True)
    y, groups = df["y"].to_numpy(int), df["group"].to_numpy()
    frame = pd.DataFrame({"comp": [r["comp"] for r in pool]})
    table = P.element_table(sorted({e for c in df["comp"] for e in c} | {e for c in frame["comp"] for e in c}))
    blocks = H.feature_blocks(df, table, [H.dsc_structure(r) for _, r in df.iterrows()])
    seen = collections.Counter(e for c in df["comp"] for e in c)
    elements = sorted(e for e, n in seen.items() if n >= 10)
    blocks["D"] = H.element_fractions(df["comp"], elements)
    c = SC.radar_design()
    final = RD.fit_design(c, np.hstack([blocks[b].to_numpy(float) for b in c["X"]]), y, groups, P.SEED + 500)
    pb = H.feature_blocks(frame, table, [structure_of(r) for r in pool])
    pb["D"] = H.element_fractions(frame["comp"], elements)
    return RD.predict_design(final, np.hstack([pb[b].to_numpy(float) for b in c["X"]])), {"design": c.get("name"), "id": c.get("id"), "n_train": int(len(y))}


def synthetic_route(pool: list, seed: int = F.SEED) -> tuple[np.ndarray, dict]:
    """Invented routing for --smoke and the tests: no 3DSC, no Radar."""
    rng = np.random.default_rng(seed + 7)
    return rng.random(len(pool)), {"synthetic": True}


# ---------------------------------------------------------------- the released computation, for the pool
def score(observations: list, bg: dict, anchors: list, sent: list, table=None) -> dict:
    """What the released Hurricane 9.0 answers for the released background (as hurricane9_screen.score) and for the
    compounds of the pool that Radar sends. The pool's chances come from the guard's own classifiers, fitted here a
    second time with the same rows and seeds; the run stops if they do not give the guard's chances for the background."""
    import hurricane3 as H3
    import screen as SC
    train = R.final_rows(observations)
    bg_rows = R.pseudo_rows(bg["key"], bg["comp"])
    anchor_rows = R.pseudo_rows([f"anchor-{i}" for i in range(len(anchors))], [a["composition"] for a in anchors])
    new_rows = R.pseudo_rows([tag(r) for r in sent], [r["comp"] for r in sent])
    if table is None:
        table = F.element_table(sorted({e for o in observations for e in o["composition"]} | {e for r in bg_rows + anchor_rows + new_rows for e in r["comp"]}))
    X, (Xb, _, Xn), cols = R.inputs(train, [bg_rows, anchor_rows, new_rows], table, {})
    tc, event, groups = R.targets(train)
    g = R.guard(X, event, groups, Xb, bg["fold"], bg["sent"])
    reg = R.Design9().fit_regressor(X, tc)
    fold_b, fold_n = np.asarray(bg["fold"], int), np.array([H3.bg_fold(r["chemsys"]) for r in sent], int)
    again, p = np.full(len(Xb), np.nan), np.full(len(Xn), np.nan)
    for k in range(P.N_FOLDS):
        held_b, held_n = fold_b == k, fold_n == k
        if not (held_b.any() or held_n.any()):
            continue
        d = R.Design9(F.SEED + 1 + k).fit_classifier(X, event, Xb[g["near"] & ~held_b])
        if held_b.any():
            again[held_b] = d.chance(Xb[held_b])
        if held_n.any():
            p[held_n] = d.chance(Xn[held_n])
    both = np.isfinite(again) & np.isfinite(g["p"])
    gap = float(np.max(np.abs(again[both] - g["p"][both]))) if both.any() else 0.0
    if (np.isfinite(again) != np.isfinite(g["p"])).any() or gap > 1e-12:
        raise SystemExit(f"the classifiers that score the pool differ from the guard's by {gap:.2e} on the background; nothing is written")
    with np.errstate(invalid="ignore"), warnings.catch_warnings():      # as hurricane9_release.ratio: an input with no value is zeroed
        warnings.simplefilter("ignore", RuntimeWarning)
        near_b = np.asarray(SC.novelty(X, groups, Xb)["nearest"], int) if len(Xb) else np.zeros(0, int)
        nov = SC.novelty(X, groups, Xn) if len(Xn) else {"nearest": [], "ratio": []}
    ratio = np.asarray(nov["ratio"], float)
    return {"train": train, "tc": tc, "event": event, "p": g["p"], "ratio": g["ratio"], "unknown": g["unknown"], "near": g["near"],
            "summary": g["summary"], "tc_sc": reg.tc(Xb), "nearest": near_b, "n_features": len(cols), "classifier_difference": gap,
            "pool": {"p": p, "tc_sc": reg.tc(Xn), "ratio": ratio, "unknown": ratio > R.ABSTAIN, "nearest": np.asarray(nov["nearest"], int),
                     "fold": fold_n}}


SOURCE_PAGE = {JARVIS: "https://www.ctcms.nist.gov/~knc6/jsmol/{}.html", MP: "https://next-gen.materialsproject.org/materials/{}",
               COD: "https://www.crystallography.net/cod/{}.html"}


def page(label: str | None) -> dict | None:
    """A source and identifier such as "COD 1001764" as a small record with the entry's page, where the source has one."""
    if not label:
        return None
    db = next((d for d in ORDER if label.startswith(d + " ")), None)
    if db is None:
        return None
    ident = label[len(db) + 1:]
    out = {"source": db, "id": ident}
    if db in SOURCE_PAGE:
        out["url"] = SOURCE_PAGE[db].format(ident)
    return out


def table_rows(sent: list, p_unc: np.ndarray, sc: dict, width: float) -> list:
    """One row for every compound of the pool that Radar sends to Hurricane, in the published order: the judged ones
    first, by the chance times the Tc if it superconducts, then that Tc, then the source and identifier."""
    import screen as SC
    new, rows = sc["pool"], []
    for i, r in enumerate(sent):
        p, tc_sc = float(new["p"][i]), float(new["tc_sc"][i])
        near_formula, near_tc = S6.nearest_record(sc["train"][int(new["nearest"][i])])
        spg = r["spg"] or ""
        rows.append({"id": r["id"], "source": r["db"], "formula": pretty(r["comp"]), "chemsys": r["chemsys"], "track": r["track"],
                     "experimental": r["evidence"] or "", "labels": ";".join(r["labels"]), "nat": round(float(r["nat"]), 3), "spg": spg,
                     "spg_number": r["spg_number"], "ehull": r["hull"], "gap": r["gap"], "gap_from": r["gap_from"] or "", "magmom": r["magmom"],
                     "p_unconventional": float(p_unc[i]), "family": SC.family_guess(r["comp"]), "hurricane_tc": p * tc_sc, "p_sc": p, "tc_sc": tc_sc,
                     "lo": max(math.expm1(math.log1p(tc_sc) - width), 0.0), "hi": math.expm1(math.log1p(tc_sc) + width),
                     "types": ";".join(k for k, v in H2.structure_types(r["comp"]).items() if v > 0), "novelty": float(new["ratio"][i]),
                     "nearest_training": near_formula, "nearest_training_tc": near_tc, "not_known": bool(new["unknown"][i]), "_record": r})
    down = lambda v: -v if math.isfinite(v) else math.inf   # noqa: E731  (a missing value sorts last)
    rows.sort(key=lambda r: (r["not_known"], down(r["hurricane_tc"]), down(r["tc_sc"]), ORDER.index(r["source"]), r["id"]))
    return rows


def judged(r: dict) -> bool:
    return S6.judged(r)


def listed_rows(rows: list, track: str) -> list:
    """The judged compounds of one track in order, one per chemical system, at most TOP_N."""
    out, per = [], {}
    for r in rows:
        if r["track"] != track or not judged(r) or per.get(r["chemsys"], 0) >= PER_SYSTEM:
            continue
        per[r["chemsys"]] = per.get(r["chemsys"], 0) + 1
        out.append(r)
        if len(out) == TOP_N:
            break
    return out


def corrected_check(r: dict, check, records: dict):
    """A recorded check with the correction of the literature audit (hurricane9_screen.corrected_check). The audit keyed
    its two corrections by JARVIS-DFT entry; a check is matched by composition, so here the correction follows it to an
    entry of the same composition in another source."""
    fixed = S6.corrected_check(r["id"], check, records)
    if not check or fixed is not check:
        return fixed
    key = P._composition_key(r["comp"])
    for row in records.values():
        c = row.get("check_correction")
        if c and isinstance(c.get("check"), dict) and check.get("doi") == c.get("replaces_doi") and isinstance(row.get("composition"), dict) \
                and P._composition_key(row["composition"]) == key:
            return copy.deepcopy(c["check"])
    return check


def candidates(rows: list, track: str, seen: tuple, now: dict, checks: tuple, records: dict) -> list:
    """The published records of one track's list, with the fields the earlier rounds gave a Hurricane candidate and,
    new in this round, the source of the entry, the experimental structure and the marks."""
    import screen as SC
    out = []
    for rank, row in enumerate(listed_rows(rows, track), 1):
        r = row["_record"]
        spg = f"{r['spg']} ({r['spg_number']})" if r["spg"] and r["spg_number"] else (r["spg"] or None)
        src = page(tag(r))
        exp = page(r["evidence"])
        if exp and r.get("same_space_group") is not None:
            exp["same_space_group"] = bool(r["same_space_group"])      # of the named experimental structure and the calculated entry shown
        c = {"rank": rank, "formula": row["formula"], "id": r["id"], "url": src.get("url"), "spg": spg, "ehull": SC._r(r["hull"], 3) if r["hull"] is not None else None,
             "icsd": bool(exp and exp["source"] in (JARVIS, MP)), "track": track, "source": src, "experimental": exp,
             "labels": list(r["labels"]) or None, "tc": SC._r(row["hurricane_tc"], 2), "tc_sc": SC._r(row["tc_sc"], 2), "lo": SC._r(row["lo"], 2),
             "hi": SC._r(row["hi"], 2), "p_sc": SC._r(row["p_sc"], 3), "p_unconventional": SC._r(row["p_unconventional"], 3),
             "family": row["family"] if row["family"] != "other" else None, "gap": SC._r(r["gap"], 2) if r["gap"] is not None else None,
             "gap_from": page(r["gap_from"]),
             "magnetic": True if r["magmom"] is not None and abs(r["magmom"]) > SC.MAGMOM_MAX else None,
             "types": [t for t in row["types"].split(";") if t] or None, "novelty": SC._r(row["novelty"], 2),
             "nearest": {"formula": row["nearest_training"], "tc": SC._r(row["nearest_training_tc"], 2)},
             "listed": SC.listed_for(r["id"], r["comp"], seen, now),
             "atoms": {"lattice": np.round(np.asarray(r["lattice"], float), 4).tolist(), "elements": list(r["elements"]),
                       "frac": np.round(np.asarray(r["frac"], float), 5).tolist()}
             if r.get("elements") is not None and r.get("frac") is not None else None,
             "published": r.get("published"), "year": r.get("year"), "doi": r.get("doi"),
             "check": corrected_check(r, SC.check_for(checks[0], checks[1], r["comp"]), records)}
        out.append({k: v for k, v in c.items() if v is not None})
    return out


# ---------------------------------------------------------------- the published block
def first_listings(results: Path, prog: dict) -> tuple[dict, dict]:
    """hurricane9_screen.first_listings, reading the dates of both lists of a published block of this round."""
    prog = copy.deepcopy(prog)
    h = (prog.get("screen") or {}).get("hurricane") or {}
    if h.get("candidates_computed"):
        h["candidates"] = list(h.get("candidates") or []) + list(h["candidates_computed"])
    return S6.first_listings(results, prog)


def track_counts(rows: list, pool: list, lists: dict) -> dict:
    out = {}
    for t in PROTOCOL["listed"]["tracks"]:
        mine = [r for r in rows if r["track"] == t]
        out[t] = {"pool": sum(1 for r in pool if r["track"] == t), "sent": len(mine), "not_known": sum(1 for r in mine if r["not_known"]),
                  "judged": sum(1 for r in mine if judged(r)), "chemical_systems_judged": len({r["chemsys"] for r in mine if judged(r)}),
                  "listed": len(lists[t]), "at_least_an_even_chance": sum(1 for c in lists[t] if c["p_sc"] >= 0.5),
                  "judged_at_least_an_even_chance": sum(1 for r in mine if judged(r) and r["p_sc"] >= 0.5)}
    return out


TRACK_ABOUT = {
    "experimental": "compounds for which one of the sources holds an experimental structure; kept whatever a calculation says about "
                    "their stability",
    "computed": f"compounds with no experimental structure in any of the sources, whose calculated entry lies at most "
                f"{int(EHULL_MAX * 1000)} meV/atom above the convex hull of its source",
}


def block(rows: list, lists: dict, pool: list, info: dict, bg: dict, sc: dict, released: dict, stamp: str) -> dict:
    """screen.hurricane as the app reads it: the fields the earlier rounds published, with the experimental track as
    the list ("candidates") and, new in this round, the second list, the tracks and the sources."""
    import screen as SC
    g = sc["summary"]
    n_sent, n_unknown = len(rows), sum(1 for r in rows if r["not_known"])
    answers = (released.get("answers") or {})
    new, fam = answers.get("new_family_windows") or {}, answers.get("family_windows") or {}
    rng = (released.get("evidence") or {}).get("range") or {}
    counts = track_counts(rows, pool, lists)
    rule = (f"{ELEMENTS[0]} to {ELEMENTS[1]} elements, up to {MAX_ATOMS} atoms in the primitive cell, a band gap of at most {GAP_MAX:g} eV, magnetic "
            f"or not, elements Hurricane's training data covers; a compound with an experimental structure in one of the sources is kept "
            f"whatever a calculation says about its stability, any other compound only within {int(EHULL_MAX * 1000)} meV/atom of the convex "
            f"hull of its source; the list holds the {n_sent:,} that Radar sends to Hurricane, one per chemical system on each track, except "
            f"the {n_unknown:,} too far from Hurricane's training data for it to give a chance")
    r3 = lambda v: None if v is None else round(float(v), 3)   # noqa: E731
    return {
        "model": f"{HU.MODEL} {R.MODEL_VERSION}", "design": "H90", "two_part": "mean", "round": ROUND, "date": stamp[:10],
        "pool": {"source": ", ".join(ORDER), "what": "compounds with no superconductivity record that Radar sends to Hurricane",
                 "n_screened": len(pool), "n_sent": n_sent, "rule": rule, "chemical_systems": info.get("chemical_systems"),
                 "no_calculated_gap": info.get("no_calculated_gap"),
                 "experimental_structure_in_another_space_group": info.get("experimental_structure_in_another_space_group"),
                 "about": "each compound is a composition, judged once. The calculated entry that speaks for it is one marked "
                          "experimental before any other, then one near its source's convex hull; a measured COD composition takes the "
                          "band gap of the calculation of the same material and is marked if there is none. The experimental structure "
                          "named with a compound can have another space group than the calculated structure shown"},
        "excluded": dict(info.get("excluded") or {}),
        "range": {"level": rng.get("level", 1 - R.ALPHA), "width_log": round(float(rng["width_log"]), 4), "of": "the Tc if it superconducts",
                  "from": "its errors on parent compounds first reported after its training data end"},
        "check": {"about": "of the compositions of new parent compounds in its time windows, the share given at least an even chance: of "
                           "those that superconduct, and of those measured not to superconduct",
                  "found": r3(fam.get("found")), "alarms_on_negatives": r3(fam.get("alarms_on_negatives")), "n": fam.get("units")},
        "novelty": {"level": SC.NOVEL_LEVEL, "outside": 0, "about": SC.NOVELTY_ABOUT},
        "caveat": CAVEAT, "candidates": lists["experimental"], "candidates_computed": lists["computed"],
        "tracks": [dict({"id": t, "about": TRACK_ABOUT[t]}, **counts[t]) for t in PROTOCOL["listed"]["tracks"]],
        "sources": [{"name": db, "what": SOURCES[db]["what"], "licence": SOURCES[db]["licence"], "cite": SOURCES[db]["cite"], "doi": SOURCES[db]["doi"],
                     "url": SOURCES[db].get("url"), "in_the_pool": sum(1 for r in pool if r["db"] == db)} for db in ORDER],
        "hull": {"about": "JARVIS-DFT's distance to the convex hull is computed in the run from the file's own formation energies; the "
                          "file's ehull field, which the pools of rounds 1 to 6 used, does not follow that hull",
                 "record": "results/validation/pool-census.md"},
        "background": {"n": int(g["n_used"]), "weight": R.WEIGHT, "cross_fitted": "fold", "radius": R.RADIUS, "pool": int(g["n"])},
        "reliability": {"false_alarms": None if g["false_alarms"] is None else round(float(g["false_alarms"]), 4),
                        "n_background": int(g["n_used"]), "abstain": R.ABSTAIN,
                        "about": "false alarms: the share of the held-out compounds of the released background (JARVIS-DFT compounds with "
                                 "no superconductivity record) that Radar sends to Hurricane which lie inside its training data and get at "
                                 "least an even chance. The pool of this round is wider than that background; for its other compounds, "
                                 "above all the measured compositions of the COD, this share has not been measured",
                        "cite": R.KONNO["cite"], "doi": R.KONNO["doi"], "found": r3(new.get("found")), "dismissed": r3(new.get("dismissed")),
                        "unknown_lofo": r3(new.get("unknown")),
                        "dismissed_about": "trained only on reports dated before a family was found and asked about that family's first five years"},
        "not_known": {"n": n_unknown, "of": n_sent, "abstain": R.ABSTAIN, "about": NOT_KNOWN},
    }


def stage_detail(screen: dict) -> str:
    """The screen stage's line: Storm's list as screening round 5 left it, and Hurricane's lists of this round."""
    import screen as SC
    text = SC.screening_stage_detail(screen)
    h, storm = screen.get("hurricane") or {}, screen.get("candidates") or []
    pool = h.get("pool") or {}
    text = text.replace(f"{len(storm)} Storm candidates and {len(h.get('candidates') or [])} Hurricane candidates retained from JARVIS-DFT.",
                        f"{len(storm)} Storm candidates retained from JARVIS-DFT; {len(h.get('candidates') or [])} Hurricane candidates with an "
                        f"experimental structure and {len(h.get('candidates_computed') or [])} known from calculation only, from {pool.get('source')}.")
    mark = "The candidate list contains model suggestions"
    note = (f"Hurricane's lists are from round {h.get('round')}, screened with {h.get('model')} on {pool.get('n_screened', 0):,} compounds: "
            f"{(h.get('not_known') or {}).get('n', 0):,} of the {pool.get('n_sent', 0):,} that Radar sent it are too far from its training "
            f"data for a chance. ")
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
    t = {x["id"]: x for x in b["tracks"]}
    both = b["candidates"] + b["candidates_computed"]
    top = max(both, key=lambda c: (c["p_sc"], c["tc_sc"])) if both else None
    likely = sum(1 for c in both if c["p_sc"] >= 0.5)
    msg = (f"Screening round {ROUND}: {b['model']} screened a wider pool, {b['pool']['n_screened']:,} compounds with no superconductivity "
           f"record from {b['pool']['source']} ({t['experimental']['pool']:,} with an experimental structure, {t['computed']['pool']:,} known "
           f"from calculation only). Radar sent it {b['pool']['n_sent']:,}; {b['not_known']['n']:,} are too far from its training data for a "
           f"chance and are not listed. Published, one per chemical system: {len(b['candidates'])} with an experimental structure and "
           f"{len(b['candidates_computed'])} known from calculation only. "
           f"{'None' if likely == 0 else 'One' if likely == 1 else likely} of them {'has' if likely == 1 else 'have'} at least an even chance"
           + (f"; the highest is {top['formula']} at {top['p_sc']:.0%}, with {top['tc_sc']:.1f} K if it superconducts" if top else "")
           + ". The pools of rounds 1 to 6 used a JARVIS-DFT field that does not follow the convex hull; this round computes that distance "
             "itself. These are model suggestions, not measurements; Storm's list stays as round 5 published it")
    prefix = f"Screening round {ROUND}:"
    prog["log"] = [e for e in prog.get("log", []) if not str(e.get("event", "")).startswith(prefix)]   # a re-run replaces it
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)


# ---------------------------------------------------------------- the run
def write_table(path: Path, rows: list) -> str:
    """The compounds Hurricane gives a chance (sent by Radar and inside the training data), in the published order."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            if judged(r):
                writer.writerow({k: ("" if r[k] is None else round(r[k], 5) if isinstance(r[k], float) else r[k]) for k in COLUMNS})
    return hashlib.sha256(path.read_bytes()).hexdigest()


POOL_COLUMNS = ["id", "source", "formula", "chemsys", "track", "experimental", "labels", "gap", "gap_from", "ehull", "p_unconventional", "sent",
                "not_known"]


def write_pool(path: Path, pool: list, rows: list) -> str:
    """Every compound of the pool: where it comes from, its track, the gap and hull distance that let it in, Radar's
    routing and, if it was sent, whether Hurricane knows it. The same pool gives the same file (no time stamp inside)."""
    known = {(r["source"], r["id"]): r["not_known"] for r in rows}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(POOL_COLUMNS)
    for r in pool:
        sent = r["p_unconventional"] >= 0.5
        writer.writerow([r["id"], r["db"], pretty(r["comp"]), r["chemsys"], r["track"], r["evidence"] or "", ";".join(r["labels"]),
                         "" if r["gap"] is None else round(r["gap"], 4), r["gap_from"] or "", "" if r["hull"] is None else round(r["hull"], 4),
                         round(float(r["p_unconventional"]), 4), sent, known.get((r["db"], r["id"]), "") if sent else ""])
    with open(path, "wb") as fh, gzip.GzipFile(filename="", fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(pool: list, info: dict, sent: list, p_unc, bg: dict, sc: dict, released: dict, same: dict, extra: dict, results: Path, progress: Path,
            smoke: bool, started: float) -> dict:
    """Everything after the scoring: the table of the compounds Radar sent, the two lists, the block, the result file
    and the progress file, and the block printed into the log with its hash."""
    import scipy
    import sklearn
    import screen as SC
    from literature_audit import load_audit
    stamp = P.now_iso()
    rows = table_rows(sent, p_unc, sc, float(released["evidence"]["range"]["width_log"]))
    seen = ({}, {}) if smoke else first_listings(P.RESULTS, json.loads(progress.read_text(encoding="utf-8")))
    now = {"date": stamp[:10], "at": stamp, "round": ROUND, "file": f"screen_round{ROUND}.json"}
    records, checks = load_audit()[0], SC.load_checks()
    lists = {t: candidates(rows, t, seen, now, checks, records) for t in PROTOCOL["listed"]["tracks"]}
    b = block(rows, lists, pool, info, bg, sc, released, stamp)
    both = lists["experimental"] + lists["computed"]
    out = {"run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local"), "round": ROUND, "smoke": smoke, "module": VERSION,
           "protocol": {"name": PROTOCOL["name"], "sha256": protocol_sha256(), "release_protocol_sha256": R.protocol_sha256()},
           "models": [b["model"]], "candidates": [], "hurricane": b, "reproduces": same, "guard": dict(sc["summary"]),
           "classifier_difference": sc["classifier_difference"], "sources": extra.get("sources"), "known_sources": extra.get("known_sources"),
           "radar": extra.get("radar"), "pool_steps": info.get("steps"),
           "counts": {"pool": len(pool), "tracks": {x["id"]: {k: v for k, v in x.items() if k not in ("id", "about")} for x in b["tracks"]},
                      "by_source": info.get("by_source"), "no_calculated_gap": info.get("no_calculated_gap"), "sent": len(rows),
                      "not_known": b["not_known"]["n"], "judged": sum(1 for r in rows if judged(r)), "listed": len(both),
                      "at_least_an_even_chance": sum(1 for c in both if c["p_sc"] >= 0.5),
                      "with_a_recorded_check": sum(1 for c in both if c.get("check")),
                      "with_a_literature_record": sum(1 for c in both if c["id"] in records),
                      "listed_before": sum(1 for c in both if c["listed"]["round"] != ROUND)},
           "libraries": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
           "licence": D.LICENCE, "attribution": D.ATTRIBUTION}
    out["files"] = {"hurricane_table_sha256": write_table(results / f"screen_round{ROUND}_hurricane.csv", rows),
                    "pool_sha256": write_pool(results / POOL_FILE, pool, rows)}
    out["minutes"] = round((time.time() - started) / 60, 1)
    out = F.clean(out)
    (results / f"screen_round{ROUND}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    update_progress(out, progress)
    show = {k: out[k] for k in ("round", "smoke", "protocol", "reproduces", "classifier_difference", "counts", "pool_steps", "sources", "radar",
                                "guard", "files", "minutes")}
    show["block"] = out["hurricane"]
    text = json.dumps(F.clean(show), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    print("=== hurricane9-screen7 begin")
    for i in range(0, len(text), 2000):
        print(f"h9w|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== hurricane9-screen7 end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    return out


def synthetic_sources(train: list, bg: dict, seed: int = F.SEED) -> tuple[list, list]:
    """Invented records for --smoke and the tests, in the form of the four sources: some with the compositions of the
    synthetic background, some new, some that each rule must leave out. Not structures, not a result."""
    rng = np.random.default_rng(seed + 11)
    elements = sorted({e for r in train for e in r["comp"]})
    cell = lambda n: [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0 * max(n, 1.0) / 2]]     # noqa: E731

    def sites(comp):
        els = [e for e in sorted(comp) for _ in range(int(round(comp[e])))]
        return els, [[0.0, 0.0, round((i + 0.5) / len(els), 5)] for i in range(len(els))]

    def new_comp():
        return {str(e): float(rng.integers(1, 5)) for e in rng.choice(elements, size=int(rng.integers(2, 4)), replace=False)}

    calc = []
    for i, (key, comp) in enumerate(zip(bg["key"], bg["comp"])):          # JARVIS-like: the background compounds themselves
        els, frac = sites(comp)
        calc.append(record(JARVIS, key, comp, len(els), 0.0, [0.0, 0.02, 0.3][i % 3], 0.0, i % 4 == 0, cell(len(els)), 123, "P4/mmm", els, frac,
                           jarvis_tc=None, e_form=-0.5))
    for i in range(60):                                                    # Materials-Project-like
        comp = new_comp()
        els, frac = sites(comp)
        calc.append(record(MP, f"mp-{i}", comp, len(els), [0.0, 0.4, 2.5][i % 3], [0.0, 0.03, 0.2][i % 3 if i % 2 else 0], 1.0, i % 2 == 0,
                           cell(len(els)), 139, "I4/mmm", els, frac))
    for i in range(60):                                                    # Alexandria-like: calculation only
        comp = new_comp()
        els, frac = sites(comp)
        calc.append(record(ALEX, f"agm{i:06d}", comp, len(els), 0.0, [0.0, 0.01, 0.2][i % 3], 0.0, False, cell(len(els)), 225, "Fm-3m", els, frac))
    cod = []
    for i in range(60):                                                    # COD-like: measured compositions, no gap of their own
        comp = new_comp()
        first = sorted(comp)[0]
        comp[first] = round(comp[first] - 0.15, 2)                         # a partly empty site
        n = sum(comp.values())
        cod.append(record(COD, 1000000 + i, comp, n, None, None, None, True, cell(n), 123, "P4/mmm", published=None, year=1990 + i % 30, doi=None))
    # one of each kind that a rule must leave out
    calc.append(record(MP, "mp-hydride", {elements[0]: 1.0, "H": 2.0}, 3, 0.0, 0.0, 0.0, True, cell(3), 1, "P1", [elements[0], "H", "H"], sites({elements[0]: 1, "H": 2})[1]))
    calc.append(record(MP, "mp-large", {elements[0]: 60.0, elements[1]: 60.0}, 120, 0.0, 0.0, 0.0, True, cell(120), 1, "P1"))
    calc.append(record(ALEX, "agm-unstable", {elements[0]: 1.0, elements[1]: 3.0}, 4, 0.0, 0.4, 0.0, False, cell(4), 1, "P1"))
    return calc, cod


def datasheet_list(observations: list):
    """The compositions the datasheet lists, as hurricane9_release.jarvis_background builds them."""
    import screen as SC
    listed = SC.Known("datasheet")
    for o in observations:
        if o["oxygen"]["status"] != "unknown":
            listed.add(o["composition"], "datasheet")
    return listed


def routing_check(pool: list, p_unc, bg: dict) -> dict:
    """This module's routing against screen.radar_scores: the compounds of the pool that are entries of the released
    background must get the probability the release path gives them."""
    ref = {str(k): float(p) for k, p in zip(bg["key"], bg["p_unconventional"])}
    diffs = [abs(float(p) - ref[r["id"]]) for r, p in zip(pool, p_unc) if r["db"] == JARVIS and r["id"] in ref]
    worst = max(diffs) if diffs else 0.0
    if worst > 1e-9:
        raise SystemExit(f"this module's routing differs from screen.radar_scores by {worst:.2e} on the released background; nothing is written")
    return {"compounds_compared": len(diffs), "largest_difference": worst}


# Well-known compounds, to see in the count-only report what the pool's rules do with them: insulators that must stay
# out, and metals, narrow-gap compounds and correlated oxides that the gap rule is meant to let through.
PROBES = ("K2SO4 NaCl KCl MgO CaO Al2O3 SiO2 TiO2 CaF2 BaF2 LiF CaCO3 BaSO4 MgAl2O4 Y2O3 La2O3 CeO2 BaTiO3 CaTiO3 LaAlO3 Y3Al5O12 ZnO ZnS GaN AlN "
          "BN SiC Si3N4 NiO CoO MnO CuO Cu2O Fe2O3 Fe3O4 LaNiO3 La2NiO4 LaCuO3 La2CuO4 CaRuO3 FeSi CoSi PbTe Bi2Te3 CrN TiN LaFeO3 LaMnO3 LaCoO3 "
          "Sr2IrO4 Na2IrO3 RuCl3 Ca2RuO4 LaTiO3 YTiO3 V2O3 VO2 NbO2 Ti2O3 CrO2 Fe2P Mn3Si Ce3Al Cu3N").split()


def probe_report(calculated: list, pool: list, known: list, datasheet) -> list:
    """For each probe: the calculated entry that speaks for it (source and identifier, gap, hull distance, whether it is
    marked experimental), and whether the composition is in the pool."""
    import screen as SC
    comps = {f: SC.H.parse_formula(f) for f in PROBES}
    keys = {P._composition_key(c): f for f, c in comps.items()}
    groups = collections.defaultdict(list)
    for r in calculated:
        f = keys.get(P._composition_key(r["comp"]))
        if f is not None and r["gap"] is not None:
            groups[f].append(r)
    in_pool = {P._composition_key(r["comp"]): r for r in pool}
    out = []
    for f, comp in comps.items():
        ref = min(groups[f], key=reference_order) if groups.get(f) else None
        mine = in_pool.get(P._composition_key(comp))
        reason = next((k.name for k in known if k.match(comp)), None) or ("datasheet" if datasheet.match(comp) is not None else None)
        out.append([f, None if ref is None else tag(ref), None if ref is None else ref["gap"],
                    None if ref is None or ref["hull"] is None else round(ref["hull"], 4), None if ref is None else ref["experimental"],
                    f"in the pool, {mine['track']}" if mine else f"left out: {reason}" if reason else "left out by the rules"])
    return out


def dry_counts() -> dict:
    """The sizes of the pool from the real sources, and nothing else: no Radar, no model, no list, nothing written. The
    COD is read from the stored rows if they are there, else from its database without storing them."""
    import screen as SC
    started = time.time()
    observations, _ = D.load_observations(D.fetch(D.DATA_FILE, P.CACHE / "mdr-supercon-220808").decode("utf-8", errors="replace"))
    train = R.final_rows(observations)
    counts = dict(collections.Counter(e for r in train for e in r["comp"]))
    can = lambda r: size_ok(r) and gap_ok(r) and covered(r, counts)   # noqa: E731
    jar, j_info = jarvis_records(SC.load_rows(), counts)
    P.log(f"JARVIS-DFT: {j_info}")
    mp, m_info = read_mp(source_folder(), can)
    P.log(f"Materials Project: {m_info}")
    alex, a_info = read_alexandria(source_folder(), can)
    P.log(f"Alexandria: {a_info}")
    if (P.RESULTS / COD_SNAPSHOT).is_file():
        cod, c_info = read_cod(P.RESULTS)
    else:
        rows, reasons = query_cod(), collections.Counter()
        cod = [r for r in (cod_record(row, reasons) for row in rows) if r is not None]
        c_info = {"rows_read": len(rows), "used": len(cod), "left_out": dict(sorted(reasons.items())), "stored": False}
    P.log(f"COD: {c_info}")
    known_sources = []
    known, sheet = SC.known_lists(known_sources), datasheet_list(observations)
    pool, info = assemble(jar + mp + alex, cod, counts, known, sheet)
    with open(P.RESULTS / BACKGROUND, newline="", encoding="utf-8") as fh:
        released = {r["jid"] for r in csv.DictReader(fh)}
    jarvis_hull = {r["id"]: r["hull"] for r in jar if r["id"] in released}
    in_pool = {r["id"] for r in pool if r["db"] == JARVIS} & released
    keys = {P._composition_key(r["comp"]) for r in pool}
    back = [r for r in jar if r["id"] in released]
    out = {"step": "counts", "module": VERSION, "protocol_sha256": protocol_sha256(), "training_rows": len(train), "elements_covered": sum(1 for n in counts.values() if n >= MIN_ELEMENT),
           "sources": {JARVIS: j_info, MP: m_info, ALEX: a_info, COD: c_info}, "known_sources": known_sources, "pool": info,
           "pool_by_elements": dict(sorted(collections.Counter(len(r["comp"]) for r in pool).items())),
           "pool_by_atoms": dict(collections.Counter("at most 40" if r["nat"] <= 40 else "41 to 100" for r in pool)),
           "pool_by_family": {t: dict(collections.Counter(SC.family_guess(r["comp"]) for r in pool if r["track"] == t)) for t in PROTOCOL["listed"]["tracks"]},
           "released_background": {"compounds": len(released), "found_in_jarvis": len(back), "themselves_in_the_pool": len(in_pool),
                                   "composition_in_the_pool": sum(1 for r in back if P._composition_key(r["comp"]) in keys),
                                   "experimental": sum(1 for r in back if r["experimental"]),
                                   "hull_distance_within_50_meV": sum(1 for v in jarvis_hull.values() if v is not None and v <= EHULL_MAX),
                                   "hull_distance_beyond": sum(1 for v in jarvis_hull.values() if v is not None and v > EHULL_MAX),
                                   "no_hull_distance": sum(1 for v in jarvis_hull.values() if v is None)},
           "minutes": round((time.time() - started) / 60, 1)}
    kinds = (("fluoride", {"F"}), ("chloride, bromide or iodide", {"Cl", "Br", "I"}), ("oxide", {"O"}), ("sulfide, selenide or telluride", {"S", "Se", "Te"}),
             ("nitride, phosphide, arsenide or antimonide", {"N", "P", "As", "Sb"}), ("boride, carbide, silicide or germanide", {"B", "C", "Si", "Ge"}))
    kind = lambda r: next((name for name, els in kinds if els & set(r["comp"])), "none of these (intermetallic)")   # noqa: E731
    out["pool_by_kind"] = {t: dict(collections.Counter(kind(r) for r in pool if r["track"] == t)) for t in PROTOCOL["listed"]["tracks"]}
    out["no_calculated_gap_by_kind"] = dict(collections.Counter(kind(r) for r in pool if NO_GAP in r["labels"]))
    out["cod_entries_with_a_reference_gap"] = sum(1 for r in pool if r["db"] == COD and r["gap_from"])
    out["probes (formula, what speaks for it, gap, hull distance, marked experimental, result)"] = probe_report(jar + mp + alex, pool, known, sheet)
    out["experimental_named_by"] = dict(collections.Counter((r["evidence"] or "").rsplit(" ", 1)[0] for r in pool if r["track"] == "experimental"))
    examples = collections.defaultdict(list)             # a seeded sample of each source and track, to see that they were read as meant
    order = np.random.default_rng(F.SEED).permutation(len(pool))
    for r in (pool[int(i)] for i in order):
        mine = examples[f"{r['db']}, {r['track']}" + (", " + NO_GAP if NO_GAP in r["labels"] else "")]
        if len(mine) < 8:
            mine.append([r["id"], pretty(r["comp"]), round(r["nat"], 2), r["gap"], None if r["hull"] is None else round(r["hull"], 4), r["spg"],
                         r["evidence"], r["same_space_group"], r["gap_from"], ";".join(r["labels"])])
    out["examples (id, formula, atoms per cell, gap, hull distance, space group, experimental structure, same space group, gap from, marks)"] = dict(examples)
    try:
        import resource
        out["peak_memory_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    except Exception:
        pass
    text = json.dumps(F.clean(out), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    print("=== hurricane9-screen7-counts begin")
    for i in range(0, len(text), 2000):
        print(f"h9c|{i // 2000:03d}|{text[i:i + 2000]}")
    print("=== hurricane9-screen7-counts end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))
    return out


def run(smoke: bool = False, output_dir: Path | None = None) -> dict:
    started, digest = time.time(), protocol_sha256()
    extra = {}
    if smoke:
        observations, _ = D.load_observations(F.synthetic_table())
        supported = {u["canonical"] for i, u in enumerate(D.canonical_units(observations, lift=True)) if i % 2 == 0}
        train = R.final_rows(observations)
        bg, anchors = R.synthetic_background(train), HU.load_anchors().get("materials", [])[:3]
        results = Path(output_dir or P.ROOT / "results" / "hurricane9-screen7-smoke")
        results.mkdir(parents=True, exist_ok=True)
        progress = results / "progress.json"
        progress.write_text(P.PROGRESS.read_text(encoding="utf-8"), encoding="utf-8")
        released, _, background = R.build(observations, supported, bg, anchors)      # stands in for the committed release
        R.write_csv(results / BACKGROUND, background)
        released, table = F.clean(released), results / BACKGROUND
        calculated, cod = synthetic_sources(train, bg)
        counts = {e: MIN_ELEMENT for r in train for e in r["comp"]}
        pool, info = assemble(calculated, cod, counts, [], None)
        p_unc, extra["radar"] = synthetic_route(pool)
        extra["sources"] = {"synthetic": True}
    else:
        import screen as SC
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
        train = R.final_rows(observations)
        bg, anchors = R.jarvis_background(observations, train), HU.load_anchors().get("materials", [])
        results.mkdir(parents=True, exist_ok=True)
        counts = dict(collections.Counter(e for r in train for e in r["comp"]))
        can = lambda r: size_ok(r) and gap_ok(r) and covered(r, counts)   # noqa: E731
        jar, j_info = jarvis_records(SC.load_rows(), counts)
        P.log(f"JARVIS-DFT: {j_info}")
        mp, m_info = read_mp(source_folder(), can)
        P.log(f"Materials Project: {m_info}")
        alex, a_info = read_alexandria(source_folder(), can)
        P.log(f"Alexandria: {a_info}")
        if not (P.RESULTS / COD_SNAPSHOT).is_file():
            P.log(f"COD: stored {cod_snapshot(P.RESULTS)['rows_stored']:,} rows")
        cod, c_info = read_cod(P.RESULTS)
        P.log(f"COD: {c_info}")
        extra["known_sources"] = []
        pool, info = assemble(jar + mp + alex, cod, counts, SC.known_lists(extra["known_sources"]), datasheet_list(observations))
        P.log(f"pool: {info['pool']:,} compounds, {info['tracks']}")
        p_unc, extra["radar"] = radar_route(pool)
        extra["radar"] = dict(extra["radar"], check=routing_check(pool, p_unc, bg))
        extra["sources"] = {JARVIS: j_info, MP: m_info, ALEX: a_info, COD: c_info}
    p_unc = np.asarray(p_unc, float)
    for r, p in zip(pool, p_unc):
        r["p_unconventional"] = float(p)
    sent = [r for r in pool if r["p_unconventional"] >= 0.5]
    sc = score(observations, bg, anchors, sent)
    same = S6.compare_with_release(bg, sc, table)          # stops here, before anything is written, if the release is not reproduced
    return publish(pool, info, sent, np.array([r["p_unconventional"] for r in sent]), bg, sc, released, same, extra, results, progress, smoke, started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", action="store_true", help="print the frozen screening protocol and its SHA-256")
    parser.add_argument("--smoke", action="store_true", help="invented rows through every step; not a result")
    parser.add_argument("--counts", action="store_true", help="the sizes of the pool from the real sources; no Radar, no model, nothing written")
    parser.add_argument("--snapshot", action="store_true", help="read the COD's public database once and store the usable rows in results/")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    if args.protocol:
        print(json.dumps(PROTOCOL, indent=1, sort_keys=True))
        print("protocol sha256 " + protocol_sha256())
    elif args.smoke:
        run(smoke=True, output_dir=args.output_dir)
    elif args.counts:
        dry_counts()
    elif args.snapshot:
        declared = DECLARATION.read_text(encoding="utf-8") if DECLARATION.exists() else ""
        if protocol_sha256() not in declared:
            raise SystemExit(f"screening protocol sha256 {protocol_sha256()} is not in {DECLARATION.name}; refusing to read any data")
        if (P.RESULTS / COD_SNAPSHOT).is_file():
            raise SystemExit(f"results/{COD_SNAPSHOT} is there already; a second reading would change what the round screens")
        print(json.dumps(cod_snapshot(args.output_dir or P.RESULTS), indent=1))
    else:
        parser.error("choose --protocol, --smoke, --counts or --snapshot; the screening run is python ml/pipeline.py hurricane9screen7")


if __name__ == "__main__":
    main()
