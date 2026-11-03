"""Hurricane 9 data module: the MDR SuperCon Datasheet as a reviewed, censoring-aware training source.

    python ml/hurricane9_data.py --audit [--cache DIR] [--output PATH]   # count-only audit of the real file (no fit)
    python ml/hurricane9_data.py --smoke                                 # synthetic rows through every rule (no download)

Source: MDR SuperCon Datasheet Ver.220808, National Institute for Materials Science, DOI 10.48505/nims.3837,
licence CC BY 4.0. Attribution: "This study used the MDR SuperCon Datasheet (https://doi.org/10.48505/nims.3837),
a numerical data sheet for superconducting materials, which is made public by the National Institute for Materials
Science (NIMS)." The data table and every interpretation file are pinned by SHA-256 (SOURCES). The three header lines
of the table are validated by their field symbols and long names, never by column positions.

Every rule of coordination/claude-R-009-hurricane9-design.md v0.2 is a function here with a unit test:
observations keep their conditions (section 2.1); the ambient/bulk domain policy and the quarantine reasons (2.2);
per-family event thresholds with censoring-aware labels (2.3); canonical units and aggregation (2.4); canonical
composition, the integer-rounded parent rule and the deterministic family rule with statuses (2.6); the provenance
graph, connected components, fold manifest and anchor purge (3); the date-first temporal split (5.2).

Nothing here fits a model. A measurement floor is censored evidence, never a negative for a higher event; films,
multiphase samples, pressure studies, hydrides and quarantined extremes are statuses, never negatives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

VERSION = "hurricane9-data-v0.2"
MDR_DOI = "https://doi.org/10.48505/nims.3837"
MDR_README_DOI = "https://doi.org/10.48505/nims.3740"
ATTRIBUTION = ("This study used the MDR SuperCon Datasheet (https://doi.org/10.48505/nims.3837), a numerical data sheet "
               "for superconducting materials, which is made public by the National Institute for Materials Science (NIMS).")
LICENCE = "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
MDR_FILES = "https://mdr.nims.go.jp/filesets/"
# Every file read for interpretation is pinned (design note section 1); the data table is the only one parsed for rows.
SOURCES = {
    "220808_MDR_OAndM.txt": {"url": MDR_FILES + "871b1990-c5b5-4905-a4f0-8afb55e5d789/download", "bytes": 18227757,
                             "sha256": "a874ab2472c960ace275b2f97e6b97fae8fae2420513fc94d919d0037f202ff7",
                             "role": "oxide and metallic data table (parsed)"},
    "primary.tsv": {"url": MDR_FILES + "ae72944c-bb97-4c6a-b2e4-6b96b31c66a8/download", "bytes": 1968352,
                    "sha256": "66cb67af1d1914f8f28e4aae5a0377992755c6cc166bc3f0a160f8c59cc77320",
                    "role": "readme preview of num, name, element, str3, utc, tc, journal (cross-check only)"},
    "SuperCon_ReadMe_en.pdf": {"url": MDR_FILES + "dd00e931-e7b7-4bc5-bde2-ba0ff1e9adaf/download", "bytes": 668934,
                               "sha256": "89096c1f006a5d5c256d14394880b31684ad2ce0b4f7ea0d37175256ea6a029d",
                               "role": "field and code tables used for interpretation"},
    "SuperCon_ReadMe.pdf": {"url": MDR_FILES + "567ca63b-01ba-43cc-95d6-34376a01096e/download", "bytes": 787656,
                            "sha256": "ccabe6162135c6dbab4a00f63af5f7945b143c57e6eaa50069c7f3dbefd756bd", "role": "readme (Japanese)"},
    "ReadmeTbl.xlsx": {"url": MDR_FILES + "28e52e3f-8f92-4656-abb6-354e4cef11a1/download", "bytes": 25748,
                       "sha256": "f0e84613aeed5faa8e248a2505b99d3c6df3c22b01bc4f6ab3d26451afd2c0e4", "role": "code tables"},
    "220808_supercon-mdr-schema.yml": {"url": MDR_FILES + "a937a66f-b7a2-4ce8-99f5-f5d9102f639e/download", "bytes": 1798,
                                       "sha256": "b484be5962a552f0a3fd757ecf90182226a5ea72533d3430c3003622592f12c1",
                                       "role": "dataset record metadata (licence, DOI)"},
    "supercon-rm-mdr-schema.yml": {"url": MDR_FILES + "1836f005-6878-4d2d-abd0-98d1b1315324/download", "bytes": 1718,
                                   "sha256": "9040b4cf7282a7ebb1ea668d425bdc2b763b321e75db96324c68642b4d287967",
                                   "role": "readme record metadata"},
    "220808organic_MDR_Organic.txt": {"url": MDR_FILES + "d3ec0c3b-5a64-44e9-8bf0-295865f18bfb/download", "bytes": 216943,
                                      "sha256": "5e73705c82b850096fac1cc8c8ffbef5144692e51084a650f81391f57942fae1",
                                      "role": "organic table (not used)"},
}
DATA_FILE = "220808_MDR_OAndM.txt"

# Code tables from SuperCon_ReadMe_en.pdf (pinned above). Blank codes mean "unspecified".
SHAPE = {"1": "single-phase bulk", "2": "multi-phase bulk", "3": "single crystal", "4": "film", "5": "film (single)"}
TC_METHOD = {"1": "magnetization", "2": "ac susceptibility", "3": "resistivity", "4": "heat capacity", "5": "tunneling",
             "6": "infrared spectroscopy", "7": "thermal conductivity", "8": "Raman spectroscopy", "9": "NMR",
             "10": "surface impedance", "11": "neutron diffraction", "12": "photoemission", "13": "microwave transmission",
             "14": "others"}
SYMMETRY = {"1": "cubic", "2": "tetragonal", "3": "orthorhombic", "4": "monoclinic", "5": "triclinic", "6": "trigonal",
            "7": "hexagonal"}
# Header validation: symbol -> long name as the readme labels it (prefix match on the long-name row, case-insensitive).
REQUIRED_FIELDS = {
    "num": "data number", "refno": "reference number", "name": "common formula of materials", "element": "chemical formula",
    "ma1": "element name of materials", "ma2": "composition of MA1", "mb1": "element name of materials",
    "mb2": "composition of MA2", "mc1": "element name of materials", "mc2": "composition of MA3",
    "md1": "element name of materials", "md2": "composition of MA4", "me1": "element name of materials",
    "me2": "composition of MA5", "mf1": "element name of materials", "mf2": "composition of MA6",
    "mg1": "element name of materials", "mg2": "composition of MA7", "mh1": "element name of materials",
    "mh2": "composition of MA8", "mi1": "element name of materials", "mi2": "composition of MA9",
    "mj1": "element name of materials", "mj2": "composition of MA10", "mo1": "oxygen", "mo2": "common formula of oxygen",
    "oz": "measured value of Oxygen content", "shape": "shape", "year": "publication year of reference",
    "str1": "\"*crystal structure, symmetry\"", "str3": "common name of structure", "spaceg": "space group",
    "tblno": "international table number", "ulat": "unit of lattice constant", "lata": "lattice constant a",
    "latb": "lattice constant b", "latc": "lattice constant c", "utc": "unit of Tc", "t1": "transition temperature (R = 0)",
    "t2": "transition temperature (mid point)", "t3": "transition temperature (R = 100%)",
    "tcsus": "Tc from susceptibility measurement", "tcn": "lowest temperature for measurement (not",
    "tcwidth": "transition width for resistive transition", "tc": "Tc (of this sample) recommended",
    "tcmeth": "tc measurement method", "dtcdp": "slope at P = 0 in Tc vs P plot", "pmax": "maximum pressure applied",
}
ELEMENT_PAIRS = [("ma1", "ma2"), ("mb1", "mb2"), ("mc1", "mc2"), ("md1", "md2"), ("me1", "me2"), ("mf1", "mf2"),
                 ("mg1", "mg2"), ("mh1", "mh2"), ("mi1", "mi2"), ("mj1", "mj2")]
ELEMENTS = set(P.ELEMENT_SYMBOLS) if hasattr(P, "ELEMENT_SYMBOLS") else {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc",
    "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr", "Nb",
    "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm",
    "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl",
    "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md",
    "No", "Lr", "D"}

# ---------------------------------------------------------------- frozen policies (design note v0.2)
EVENT_K = {"cuprate": 4.2, "iron-nickel": 4.2, "other-oxide": 4.2, "heavy-fermion": 1.0}   # section 2.3
HIGH_TC_K = 30.0                                                                           # named endpoint
# Ambient-bulk ceilings from replicated ambient records (quarantine above, never deletion): section 2.2
CEILING_K = {"cuprate": 140.0, "iron-nickel": 60.0, "heavy-fermion": 20.0, "other-oxide": 40.0, "other": 45.0}
CRITERION_CONFLICT = (0.20, 5.0)   # relative and absolute disagreement between tc and t1/t2/t3/tcsus that quarantines
EXCLUDED_SHAPES = {"2", "4", "5"}  # multi-phase bulk, film, film (single): excluded domains, never negatives
HEAVY_FERMION_ELEMENTS = {"Ce", "U", "Yb", "Pu", "Np", "Pr", "Sm"}
PNICTOGEN_CHALCOGEN = {"As", "P", "Sb", "Se", "Te", "S"}
OTHER_OXIDE_METALS = {"Bi", "Ru", "Co", "Ni", "Ti", "Nb", "W", "Re"}
# Structure-name tables (str3), precedence over composition (section 2.6). Names are matched after lower-casing.
STRUCTURE_FAMILY = {
    "cuprate": {"y123", "y124", "y247", "bi2201", "bi2212", "bi2223", "tl1201", "tl1212", "tl1223", "tl2201", "tl2212",
                "tl2223", "hg1201", "hg1212", "hg1223", "hg1234", "t", "t'", "t*", "m1212", "cu1212", "cu1223", "ru1212",
                "ru1222", "pb1212", "pb2213", "pb3212", "infinite layer", "infinite-layer", "0212", "1212", "1223", "2212",
                "2223", "2201", "1201", "214", "123", "124", "247"},
    "iron-nickel": {"oxypnictide", "1111", "122 (fe)", "111 (fe)", "11 (fe)", "pbfcl", "anti-pbo", "fese", "zrcusias",
                    "lafeaso", "bafe2as2", "lifeas", "nafeas"},
    "heavy-fermion": {"hocoga5", "cecoin5", "cein3", "ceru2si2", "upt3", "ube13", "pucoga5", "ucoge", "urhge", "cu3au",
                      "aucu3", "ni3sn"},
    "other-oxide": {"bkbo", "bismuthate", "ruthenate", "cobaltate", "nickelate", "spinel", "pyrochlore", "perovskite"},
}
OXYGEN = re.compile(r"^(\d*\.?\d*)\s*([-+]?)\s*([A-Za-z]*)$")
FORMULA = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


# ---------------------------------------------------------------- download and parse
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(name: str, cache_dir, *, get=None, offline=False) -> bytes:
    """One pinned MDR file from the cache or the network, verified by size and SHA-256 before use."""
    spec = SOURCES[name]
    path = Path(cache_dir) / name
    if path.is_file():
        data = path.read_bytes()
    elif offline:
        raise ValueError(f"offline and {name} is not cached")
    else:
        if get is None:
            req = urllib.request.Request(spec["url"], headers={"User-Agent": "supercon-ml (github.com/diracmagic/supercon-ml)"})
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
        else:
            data = get(spec["url"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if len(data) != spec["bytes"] or sha256_bytes(data) != spec["sha256"]:
        raise ValueError(f"{name}: size or SHA-256 differs from the pinned Ver.220808 file; refusing to parse")
    return data


def parse_table(text: str) -> pd.DataFrame:
    """The oxide-and-metallic table: three header lines (column numbers, long names, symbols), then rows.
    Columns are located by symbol; each required symbol's long name must match the readme label."""
    lines = text.split("\n")
    if len(lines) < 4:
        raise ValueError("MDR table: fewer than four lines")
    numbers, long_names, symbols = (lines[i].rstrip("\r").split("\t") for i in range(3))
    if not all(n.strip().isdigit() for n in numbers if n.strip()):
        raise ValueError("MDR table: the first header line must hold column numbers")
    if len(long_names) != len(symbols):
        raise ValueError("MDR table: long-name and symbol header lines differ in length")
    position = {}
    for i, s in enumerate(symbols):
        s = s.strip()
        if s in position:
            raise ValueError(f"MDR table: duplicate symbol {s!r}")
        position[s] = i
    for symbol, label in REQUIRED_FIELDS.items():
        if symbol not in position:
            raise ValueError(f"MDR table: required field {symbol!r} missing from the symbol header")
        found = long_names[position[symbol]].strip().lower()
        if not found.startswith(label.lower()):
            raise ValueError(f"MDR table: field {symbol!r} is labelled {found!r}, expected {label!r}")
    rows = []
    for k, line in enumerate(lines[3:], start=4):
        if not line.strip():
            continue
        cells = line.rstrip("\r").split("\t")
        if len(cells) < len(symbols):
            cells += [""] * (len(symbols) - len(cells))
        rows.append({s: cells[i].strip() for s, i in position.items()} | {"line": k})
    df = pd.DataFrame(rows)
    if df.empty or df["num"].duplicated().any():
        raise ValueError("MDR table: empty or duplicate data numbers")
    return df


def number(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ---------------------------------------------------------------- composition, parent, family
def composition(row) -> tuple[dict, dict]:
    """Composition from the structured element fields plus the oxygen fields (design 2.6, 2.1).
    Returns (comp, oxygen) where oxygen = {"nominal": float|None, "status": fixed|variable|unknown|measured|none,
    "expression": str}. The free-text 'element' string is only a cross-check (returned under 'element_matches')."""
    comp = {}
    for a, b in ELEMENT_PAIRS:
        el, x = str(row.get(a, "")).strip(), number(row.get(b, ""))
        if not el:
            continue
        if el not in ELEMENTS or x is None or x <= 0:
            raise ValueError(f"row {row.get('num')}: bad element field {el!r} {row.get(b)!r}")
        comp[el] = comp.get(el, 0.0) + x
    oxygen = {"nominal": None, "status": "none", "expression": str(row.get("mo2", "")).strip()}
    if str(row.get("mo1", "")).strip():
        if str(row.get("mo1", "")).strip() != "O":
            raise ValueError(f"row {row.get('num')}: mo1 is {row.get('mo1')!r}, expected 'O'")
        m = OXYGEN.match(oxygen["expression"])
        if not m:
            raise ValueError(f"row {row.get('num')}: cannot read the oxygen expression {oxygen['expression']!r}")
        value, sign, letters = m.groups()
        if value:
            oxygen["nominal"] = float(value)
            oxygen["status"] = "variable" if (sign or letters) else "fixed"
        else:
            oxygen["status"] = "unknown"
        measured = number(row.get("oz", ""))
        if measured is not None and measured > 0:
            oxygen["nominal"], oxygen["status"] = measured, "measured"
        if oxygen["nominal"] is not None:
            comp["O"] = comp.get("O", 0.0) + oxygen["nominal"]
    if not comp:
        raise ValueError(f"row {row.get('num')}: no element fields")
    return comp, oxygen


def parse_formula(s: str) -> dict:
    """Free-text formula to a composition ('Y1Ba2Cu3O7-X' -> O nominal 7); used only to cross-check the fields."""
    s = re.sub(r"(O\d*\.?\d*)[-+]?[A-Za-z]*$", r"\1", str(s).strip())
    out, pos = {}, 0
    for m in FORMULA.finditer(s):
        if m.start() != pos:
            break
        el, n = m.group(1), m.group(2)
        out[el] = out.get(el, 0.0) + (float(n) if n else 1.0)
        pos = m.end()
    if pos != len(s) or not out:
        raise ValueError(f"cannot parse formula {s!r}")
    return out


def canonical(comp: dict) -> str:
    """Coefficients scaled so that the largest non-oxygen metal coefficient is 1, rounded to 1e-3, sorted symbols."""
    scale = max((v for k, v in comp.items() if k != "O"), default=max(comp.values()))
    return " ".join(f"{el}{round(comp[el] / scale, 3):g}" for el in sorted(comp))


SITE_GROUP = re.compile(r"\(([A-Za-z,\s]+)\)(\d*\.?\d*)")


def _format(parts: dict) -> str:
    return "".join(f"{el}{parts[el] if parts[el] != 1 else ''}" for el in sorted(parts))


def parent_from_name(name: str, comp: dict):
    """Parent from the datasheet's common formula, which marks shared sites: '(La,Sr)2CuO4' -> La2CuO4 (the host of a
    site is the member with the larger coefficient), 'NaFe1-xCoxAs' -> NaFeAs, 'YBa2(Cu,Zn)4O8' -> YBa2Cu4O8,
    'LaFeAsO1-xFx' -> LaFeAsO. Returns None when the name is blank or cannot be read against the composition."""
    text = str(name or "").strip().strip('"').replace(" ", "")
    if not text:
        return None
    parts, pos = {}, 0
    for m in SITE_GROUP.finditer(text):
        text = text[:m.start()] + ("~" * (m.end() - m.start())) + text[m.end():]   # mask groups, keep offsets
        members = [e for e in m.group(1).split(",") if e]
        if any(e not in comp for e in members):
            return None
        host = max(members, key=lambda e: (comp[e], -members.index(e)))
        count = m.group(2)
        n = float(count) if count else 1.0
        parts[host] = parts.get(host, 0.0) + n
    plain = text.replace("~", "")
    while pos < len(plain):
        if not plain[pos].isupper():
            return None
        el = plain[pos]
        if pos + 1 < len(plain) and plain[pos + 1].islower() and (el + plain[pos + 1]) in comp:
            el += plain[pos + 1]          # two-letter symbols only when the composition has them (Fx is F + dopant x)
        if el not in comp:
            return None
        pos += len(el)
        m = re.match(r"(\d*\.?\d*)([-+](?:\d+\.?\d*|[a-z]))?", plain[pos:])
        num, rest = m.group(1), m.group(2) or ""
        pos += m.end()
        if not num and not rest and pos < len(plain) and plain[pos].islower():
            pos += 1                       # a bare x, y, z or d: a dopant without a host count
            continue
        parts[el] = parts.get(el, 0.0) + (float(num) if num else 1.0)
    if not parts or all(k == "O" for k in parts):
        return None
    rounded = {k: int(math.floor(v + 0.5)) for k, v in parts.items()}
    if any(n <= 0 for n in rounded.values()):
        return None
    return _format(rounded)


ANIONS = {"O", "F", "Cl", "Br", "I", "S", "Se", "Te", "N", "P", "As", "Sb"}


def parent_from_coefficients(comp: dict, *, dopant_below=0.5, tolerance=0.25, max_multiplier=8) -> str:
    """Fallback parent (design 2.6) when the datasheet gives no readable common formula. Elements with a coefficient
    below `dopant_below` are dopants: an anion dopant is returned to the oxygen count, a cation dopant to the kept
    cation with the largest deficit below the next integer (the depleted host). The kept coefficients are then scaled by
    the largest cation; among the multipliers up to `max_multiplier` that bring all of them within `tolerance` of
    integers, the one with the smallest total rounding error wins (ties to the smaller multiplier); oxygen rounds half
    up at that multiplier. 'unresolved' when no multiplier fits. A vacancy compound without a readable common formula
    (K0.8Fe2Se2) keeps its own parent; the element-set edge of the provenance graph still joins it to KFe2Se2."""
    cations = {k: v for k, v in comp.items() if k != "O"}
    if not cations:
        return "unresolved"
    kept = {k: v for k, v in cations.items() if v >= dopant_below}
    oxygen = comp.get("O")
    if not kept:
        return "unresolved"
    for el in sorted(cations):
        if el in kept:
            continue
        if el in ANIONS and oxygen is not None:
            oxygen += cations[el]
            continue
        host = max(sorted(kept), key=lambda k: (math.ceil(kept[k] - 1e-9) - kept[k], -sorted(kept).index(k)))
        kept[host] += cations[el]
    base = max(kept.values())
    best = None
    for mult in range(1, max_multiplier + 1):   # the multiplier with the smallest total rounding error, ties to the smaller
        scaled = {k: v / base * mult for k, v in kept.items()}
        rounded = {k: int(math.floor(x + 0.5)) for k, x in scaled.items()}
        if all(n > 0 and abs(scaled[k] - n) <= tolerance for k, n in rounded.items()):
            error = sum(abs(scaled[k] - n) for k, n in rounded.items())
            if best is None or error < best[0] - 1e-9:
                best = (error, mult, rounded)
    if best is None:
        return "unresolved"
    error, mult, rounded = best
    if oxygen is not None:
        o = int(math.floor(oxygen / base * mult + 0.5))
        if o <= 0:
            return "unresolved"
        rounded["O"] = o
    return _format(rounded)


def parent(comp: dict, name: str = "") -> str:
    """The parent compound used as the isolation and search unit: the common-formula route when the datasheet gives
    one, else the coefficient route."""
    return parent_from_name(name, comp) or parent_from_coefficients(comp)


def family(comp: dict, structure_name: str = "") -> tuple[str, str]:
    """Deterministic family with status (design 2.6): structure name first, then the composition fallback."""
    els = set(comp)
    name = str(structure_name or "").strip().lower()
    by_structure = [fam for fam, names in STRUCTURE_FAMILY.items() if name and name in names]
    cu_o = {"Cu", "O"} <= els
    fe_sheet = bool(({"Fe", "Ni"} & els) and (PNICTOGEN_CHALCOGEN & els))
    if by_structure:
        fam = by_structure[0]
        if fam == "iron-nickel" and not fe_sheet:
            return "mixed", "structure name says iron/nickel but no Fe/Ni pnictogen-chalcogen composition"
        if fam == "cuprate" and not cu_o:
            if {"Ni", "O"} <= els and not fe_sheet:
                return "other-oxide", "by-structure (nickelate analogue of a cuprate structure type)"
            return "mixed", "structure name says cuprate but no Cu-O composition"
        return fam, "by-structure"
    guesses = []
    if cu_o and not fe_sheet:
        guesses.append("cuprate")
    if fe_sheet and not cu_o:
        guesses.append("iron-nickel")
    if (els & HEAVY_FERMION_ELEMENTS) and not cu_o:
        guesses.append("heavy-fermion")
    if "O" in els and (els & OTHER_OXIDE_METALS) and not cu_o and not fe_sheet:
        guesses.append("other-oxide")
    if cu_o and fe_sheet:
        return "mixed", "Cu-O and Fe/Ni pnictogen-chalcogen composition"
    if len(guesses) == 1:
        return guesses[0], "by-composition (uncertain)"
    if guesses == ["iron-nickel", "heavy-fermion"] or guesses == ["heavy-fermion", "other-oxide"]:
        return guesses[0], "by-composition (uncertain; precedence)"
    if len(guesses) > 1:
        return "mixed", "two composition rules fire: " + ", ".join(guesses)
    return "other", "unknown"


# ---------------------------------------------------------------- observations: domain, labels
def observation(row) -> dict:
    """One data row with its conditions and a domain status (design 2.1, 2.2). Never deletes; never labels a negative
    from absence, form, pressure or extremes."""
    comp, oxygen = composition(row)
    fam, fam_status = family(comp, row.get("str3", ""))
    tc, tcn = number(row.get("tc")), number(row.get("tcn"))
    obs = {"num": str(row["num"]), "refno": str(row.get("refno", "")), "year": number(row.get("year")),
           "composition": comp, "canonical": canonical(comp), "parent": parent(comp, row.get("name", "")), "oxygen": oxygen,
           "family": fam, "family_status": fam_status, "structure_name": str(row.get("str3", "")).strip(),
           "symmetry": SYMMETRY.get(str(row.get("str1", "")).strip()), "space_group": str(row.get("spaceg", "")).strip(),
           "lattice": {k: number(row.get(k)) for k in ("lata", "latb", "latc")}, "lattice_unit": str(row.get("ulat", "")).strip(),
           "shape": str(row.get("shape", "")).strip(), "form": SHAPE.get(str(row.get("shape", "")).strip(), "unspecified"),
           "tc": tc, "tc_fields": {k: number(row.get(k)) for k in ("t1", "t2", "t3", "tcsus")}, "tc_width": number(row.get("tcwidth")),
           "tc_method": TC_METHOD.get(str(row.get("tcmeth", "")).strip().split(",")[0].strip('" '), None),
           "floor": tcn, "pressure": {"pmax": number(row.get("pmax")), "dtcdp": str(row.get("dtcdp", "")).strip()},
           "unit": str(row.get("utc", "")).strip() or "K", "line": row.get("line")}
    obs["status"], obs["reason"] = domain_status(obs)
    return obs


def domain_status(obs: dict) -> tuple[str, str]:
    """admitted | excluded | quarantined, with the reason code (design 2.2)."""
    if obs["unit"].upper() != "K":
        return "excluded", "temperature unit not K"
    if "H" in obs["composition"] or "D" in obs["composition"]:
        return "excluded", "hydrogen-containing compound (project rule)"
    if (obs["pressure"]["pmax"] or 0) > 0 or obs["pressure"]["dtcdp"]:
        return "excluded", "pressure study"
    if obs["shape"] in EXCLUDED_SHAPES:
        return "excluded", f"sample form {SHAPE[obs['shape']]}"
    if obs["family"] in ("mixed",):
        return "excluded", "family mixed: " + obs["family_status"]
    tc, floor = obs["tc"], obs["floor"]
    if tc is not None and tc < 0:
        return "excluded", "negative tc value"
    if tc is not None and floor is not None:
        return "quarantined", "contradictory evidence within one observation (tc and tcn both present)"
    if tc is not None and tc > CEILING_K.get(obs["family"], CEILING_K["other"]):
        return "quarantined", f"tc above the frozen ambient-bulk ceiling of {CEILING_K.get(obs['family'], CEILING_K['other'])} K"
    if tc is not None:
        rel, absolute = CRITERION_CONFLICT
        for k, v in obs["tc_fields"].items():
            if v is not None and v > 0 and abs(v - tc) > max(rel * tc, absolute):
                return "quarantined", f"criterion conflict: {k}={v} against tc={tc}"
    if tc is None and floor is None:
        return "excluded", "no transition and no floor recorded"
    return "admitted", ""


def event_label(obs: dict, threshold: float):
    """1 / 0 / 'censored' for the event Tc >= threshold (design 2.3). A floor labels 0 only when it is at or below the
    threshold; a positive labels by its value."""
    if obs["status"] != "admitted":
        return "censored"
    if obs["tc"] is not None and obs["tc"] > 0:
        return 1 if obs["tc"] >= threshold else 0
    if obs["tc"] is not None and obs["tc"] == 0:
        return "censored"   # a recorded zero without a floor is not a supported negative
    if obs["floor"] is not None:
        return 0 if obs["floor"] <= threshold else "censored"
    return "censored"


def unit_key(obs: dict) -> tuple:
    form_class = "single crystal" if obs["shape"] == "3" else "bulk-specified" if obs["shape"] == "1" else "unspecified"
    return (obs["canonical"], obs["oxygen"]["status"], obs["structure_name"] or "none", form_class)


def canonical_units(observations: list, *, thresholds=EVENT_K) -> list:
    """Aggregate admitted observations into canonical units (design 2.4) with per-family event labels, the Tc median
    of positives, the spread, the floor, conflict flags and the earliest year."""
    groups = defaultdict(list)
    for o in observations:
        if o["status"] == "admitted":
            groups[unit_key(o)].append(o)
    units = []
    for key, members in sorted(groups.items()):
        fam = members[0]["family"]
        threshold = thresholds.get(fam)
        positives = [o["tc"] for o in members if o["tc"] is not None and o["tc"] > 0]
        floors = [o["floor"] for o in members if o["tc"] is None and o["floor"] is not None]
        labels = [event_label(o, threshold) for o in members] if threshold is not None else []
        if threshold is None:
            label = "censored"
        elif 1 in labels:
            label = 1
        elif 0 in labels:
            label = 0
        else:
            label = "censored"
        conflict = "sample-dependent" if (positives and floors) else ""
        years = [o["year"] for o in members if o["year"] is not None]
        units.append({"key": key, "canonical": key[0], "oxygen_status": key[1], "structure_name": key[2], "form_class": key[3],
                      "family": fam, "family_status": members[0]["family_status"], "parent": members[0]["parent"],
                      "elements": sorted(members[0]["composition"]), "members": [o["num"] for o in members],
                      "n_observations": len(members), "event_threshold_k": threshold, "event": label,
                      "high_tc_event": (1 if max(positives) >= HIGH_TC_K else 0) if positives else "censored",
                      "tc_k": float(np.median(positives)) if positives else None,
                      "tc_spread_k": [min(positives), max(positives), len(positives)] if positives else None,
                      "floor_k": max(floors) if floors else None, "conflict": conflict,
                      "earliest_year": int(min(years)) if years else None, "latest_year": int(max(years)) if years else None})
    return units


# ---------------------------------------------------------------- provenance graph, components, folds
class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def components(units: list, *, extra_nodes=()) -> dict:
    """Connected components over MDR units and extra nodes (3DSC rows, MP ids, background compounds, anchors), with
    edges for equal canonical composition, equal resolved parent, explicit links and equal element set within a family
    (design 3). extra_nodes: dicts with id, kind, canonical, parent, elements, family, links (ids). Target-blind."""
    uf, nodes = UnionFind(), {}
    for u in units:
        nodes[("unit", u["canonical"], u["oxygen_status"], u["structure_name"], u["form_class"])] = u
    for n in extra_nodes:
        key = (n["kind"], n["id"])
        if key in nodes:
            raise ValueError(f"duplicate provenance node {key}")
        nodes[key] = n
    by_canonical, by_parent, by_elements = defaultdict(list), defaultdict(list), defaultdict(list)
    for key, n in nodes.items():
        uf.find(key)
        if n.get("canonical"):
            by_canonical[n["canonical"]].append(key)
        if n.get("parent") and n["parent"] != "unresolved":
            by_parent[n["parent"]].append(key)
        if n.get("elements") and n.get("family") not in (None, "other", "mixed"):
            by_elements[(n["family"], tuple(sorted(n["elements"])))].append(key)
    for index in (by_canonical, by_parent, by_elements):
        for keys in index.values():
            for k in keys[1:]:
                uf.union(keys[0], k)
    for key, n in nodes.items():
        for link in n.get("links", []):   # explicit links are (kind, id) pairs of other nodes
            target = tuple(link)
            if target not in nodes:
                raise ValueError(f"provenance link to an unknown node {target}")
            uf.union(key, target)
    members = defaultdict(list)
    for key in nodes:
        members[uf.find(key)].append(key)
    out = {}
    for i, (root, keys) in enumerate(sorted(members.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))):
        anchors = [k for k in keys if nodes[k].get("kind") in ("anchor", "prior-claim")]
        fams = Counter(nodes[k].get("family") for k in keys)
        out[f"C{i:05d}"] = {"members": [list(k) for k in keys], "size": len(keys), "families": dict(fams),
                            "purged": bool(anchors), "purge_reason": "anchor or prior-claim member" if anchors else ""}
    return out


def assign_folds(comps: dict, *, k=5, seed=7) -> dict:
    """Greedy balance of non-purged components over k folds, largest first, by family-weighted size; deterministic."""
    folds = {f: Counter() for f in range(1, k + 1)}
    order = sorted((c for c, v in comps.items() if not v["purged"]), key=lambda c: (-comps[c]["size"], c))
    assignment = {}
    for c in order:
        fams = comps[c]["families"]
        best = min(folds, key=lambda f: (sum(folds[f][fam] * n for fam, n in fams.items()), sum(folds[f].values()), f))
        assignment[c] = best
        folds[best].update(fams)
    return assignment


def manifest(units: list, comps: dict, assignment: dict) -> dict:
    """Immutable fold manifest: every unit with its component, fold, family, event label and purge status."""
    unit_component = {}
    for cid, c in comps.items():
        for m in c["members"]:
            if m[0] == "unit":
                unit_component[tuple(m[1:])] = cid
    rows = []
    for u in units:
        cid = unit_component[(u["canonical"], u["oxygen_status"], u["structure_name"], u["form_class"])]
        rows.append({"canonical": u["canonical"], "oxygen_status": u["oxygen_status"], "structure_name": u["structure_name"],
                     "form_class": u["form_class"], "family": u["family"], "parent": u["parent"], "component": cid,
                     "fold": assignment.get(cid), "purged": comps[cid]["purged"], "event_threshold_k": u["event_threshold_k"],
                     "event": u["event"], "high_tc_event": u["high_tc_event"], "tc_k": u["tc_k"], "earliest_year": u["earliest_year"]})
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {"rows": rows, "sha256": sha256_bytes(text.encode())}


def support(manifest_rows: list) -> dict:
    """Minimum support per family and fold: positives, usable negatives, components (design 3)."""
    out = defaultdict(lambda: defaultdict(lambda: {"positives": 0, "negatives": 0, "censored": 0, "components": set()}))
    for r in manifest_rows:
        if r["purged"] or r["fold"] is None:
            continue
        cell = out[r["family"]][r["fold"]]
        cell["components"].add(r["component"])
        if r["event"] == 1:
            cell["positives"] += 1
        elif r["event"] == 0:
            cell["negatives"] += 1
        else:
            cell["censored"] += 1
    return {fam: {f: {k: (len(v) if isinstance(v, set) else v) for k, v in cell.items()} for f, cell in folds.items()}
            for fam, folds in out.items()}


# ---------------------------------------------------------------- temporal split
def temporal_split(observations: list, *, cutoff=2017, thresholds=EVENT_K) -> dict:
    """Date-first split (design 5.2): training units from reports with year <= cutoff only; test = units whose earliest
    admitted report in any source is > cutoff (new materials); later reports about pre-cutoff units are 'repeat'."""
    dated = [o for o in observations if o["status"] == "admitted" and o["year"] is not None]
    undated = [o for o in observations if o["status"] == "admitted" and o["year"] is None]
    before = canonical_units([o for o in dated if o["year"] <= cutoff], thresholds=thresholds)
    known = {u["key"] for u in before}
    after_units = canonical_units([o for o in dated if o["year"] > cutoff], thresholds=thresholds)
    new = [u for u in after_units if u["key"] not in known]
    repeat = [u for u in after_units if u["key"] in known]
    known_parents = {u["parent"] for u in before if u["parent"] != "unresolved"}
    new_parent = [u for u in new if u["parent"] not in known_parents]
    return {"cutoff": cutoff, "train_units": before, "test_new_units": new, "test_new_parent_units": new_parent,
            "repeat_report_units": repeat, "undated_excluded": len(undated)}


# ---------------------------------------------------------------- audit (count-only) and smoke
def audit(observations: list, *, primary_tsv: str | None = None, dsc_canonicals: set | None = None) -> dict:
    """Counts and examples for every rule; no model is fitted (design 7, step 3)."""
    out = {"version": VERSION, "rows": len(observations), "status": Counter(o["status"] for o in observations),
           "reasons": Counter(o["reason"] for o in observations if o["reason"]),
           "family": Counter(o["family"] for o in observations), "family_status": Counter(o["family_status"] for o in observations),
           "oxygen_status": Counter(o["oxygen"]["status"] for o in observations), "form": Counter(o["form"] for o in observations),
           "with_tc": sum(o["tc"] is not None for o in observations), "with_floor": sum(o["floor"] is not None for o in observations),
           "with_structure_name": sum(bool(o["structure_name"]) for o in observations),
           "with_year": sum(o["year"] is not None for o in observations), "unresolved_parent": sum(o["parent"] == "unresolved" for o in observations)}
    admitted = [o for o in observations if o["status"] == "admitted"]
    out["admitted_by_family"] = Counter(o["family"] for o in admitted)
    out["event_labels"] = {fam: Counter(str(event_label(o, t)) for o in admitted if o["family"] == fam) for fam, t in EVENT_K.items()}
    units = canonical_units(observations)
    out["units"] = {"n": len(units), "by_family": Counter(u["family"] for u in units),
                    "events": {fam: Counter(str(u["event"]) for u in units if u["family"] == fam) for fam in EVENT_K},
                    "conflicts": sum(bool(u["conflict"]) for u in units),
                    "multi_observation": sum(u["n_observations"] > 1 for u in units)}
    quarantined = [o for o in observations if o["status"] == "quarantined"]
    out["quarantine_examples"] = [{"num": o["num"], "canonical": o["canonical"], "tc": o["tc"], "year": o["year"], "reason": o["reason"]}
                                  for o in sorted(quarantined, key=lambda o: -(o["tc"] or 0))[:10]]
    if primary_tsv is not None:
        out["primary_tsv_crosscheck"] = crosscheck_primary(observations, primary_tsv)
    if dsc_canonicals is not None:
        out["overlap_with_3dsc_canonicals"] = sum(o["canonical"] in dsc_canonicals for o in admitted)
    modelled = [u for u in units if u["family"] in EVENT_K]
    comps = components(modelled)
    assignment = assign_folds(comps)
    man = manifest(modelled, comps, assignment)
    out["components"] = {"n": len(comps), "largest": max((c["size"] for c in comps.values()), default=0),
                         "purged": sum(c["purged"] for c in comps.values())}
    out["support"] = support(man["rows"])
    out["manifest_sha256"] = man["sha256"]
    split = temporal_split(observations)
    out["temporal"] = {"cutoff": split["cutoff"], "train_units": len(split["train_units"]), "test_new_units": len(split["test_new_units"]),
                       "test_new_parent_units": len(split["test_new_parent_units"]), "repeat_report_units": len(split["repeat_report_units"]),
                       "undated_excluded": split["undated_excluded"],
                       "test_new_by_family": Counter(u["family"] for u in split["test_new_units"])}
    return json.loads(json.dumps(out, default=lambda v: dict(v) if isinstance(v, Counter) else list(v) if isinstance(v, set) else str(v)))


def crosscheck_primary(observations: list, primary_tsv: str) -> dict:
    """primary.tsv is a preview of the same rows: every num must agree on element, str3 and tc (design 1)."""
    lines = primary_tsv.split("\n")
    symbols = lines[2].rstrip("\r").split("\t")
    pos = {s.strip(): i for i, s in enumerate(symbols)}
    preview = {}
    for line in lines[3:]:
        if line.strip():
            cells = line.rstrip("\r").split("\t")
            preview[cells[pos["num"]].strip()] = {k: cells[pos[k]].strip() for k in ("element", "str3", "tc") if k in pos and pos[k] < len(cells)}
    by_num = {o["num"]: o for o in observations}
    mismatches = []
    for num, p in preview.items():
        o = by_num.get(num)
        if o is None:
            mismatches.append({"num": num, "problem": "preview row absent from the table"})
            continue
        if p.get("str3", "") != o["structure_name"] or (number(p.get("tc")) != o["tc"]):
            mismatches.append({"num": num, "problem": "str3 or tc differ", "preview": p, "table": {"str3": o["structure_name"], "tc": o["tc"]}})
    return {"preview_rows": len(preview), "mismatches": len(mismatches), "examples": mismatches[:10]}


def synthetic_table() -> str:
    """A tiny table in the real layout for --smoke and the tests (no real rows)."""
    symbols = list(REQUIRED_FIELDS)
    numbers = "\t".join(str(i + 1) for i in range(len(symbols)))
    longs = "\t".join(REQUIRED_FIELDS[s] for s in symbols)
    syms = "\t".join(symbols)
    blank = {s: "" for s in symbols}
    rows = [
        {**blank, "num": "1", "refno": "AAA0010001", "name": "(La,Sr)2CuO4", "element": "La1.85Sr0.15Cu1O4-Y", "ma1": "La", "ma2": "1.85",
         "mb1": "Sr", "mb2": "0.15", "mc1": "Cu", "mc2": "1", "mo1": "O", "mo2": "4-Y", "shape": "1", "year": "1987", "str1": "2",
         "str3": "T", "lata": "3.78", "latc": "13.2", "ulat": "A", "utc": "K", "t2": "38", "tc": "38", "tcmeth": "3"},
        {**blank, "num": "2", "refno": "AAA0010002", "name": "La2CuO4", "element": "La2Cu1O4", "ma1": "La", "ma2": "2", "mb1": "Cu",
         "mb2": "1", "mo1": "O", "mo2": "4", "shape": "1", "year": "1988", "str3": "T", "utc": "K", "tcn": "4.2"},
        {**blank, "num": "3", "refno": "BBB0020003", "name": "LaFeAsO1-xFx", "element": "La1Fe1As1O0.9F0.1", "ma1": "La", "ma2": "1",
         "mb1": "Fe", "mb2": "1", "mc1": "As", "mc2": "1", "md1": "F", "md2": "0.1", "mo1": "O", "mo2": "0.9", "shape": "1",
         "year": "2008", "str3": "oxypnictide", "utc": "K", "tc": "26"},
        {**blank, "num": "4", "refno": "CCC0030004", "name": "CeCoIn5", "element": "Ce1Co1In5", "ma1": "Ce", "ma2": "1", "mb1": "Co",
         "mb2": "1", "mc1": "In", "mc2": "5", "shape": "3", "year": "2001", "str3": "HoCoGa5", "utc": "K", "tc": "2.3"},
        {**blank, "num": "5", "refno": "CCC0030005", "name": "CeRhIn5", "element": "Ce1Rh1In5", "ma1": "Ce", "ma2": "1", "mb1": "Rh",
         "mb2": "1", "mc1": "In", "mc2": "5", "shape": "", "year": "2019", "str3": "HoCoGa5", "utc": "K", "tcn": "0.35"},
        {**blank, "num": "6", "refno": "DDD0040006", "name": "YBa2Cu3O7 film", "element": "Y1Ba2Cu3O7-X", "ma1": "Y", "ma2": "1",
         "mb1": "Ba", "mb2": "2", "mc1": "Cu", "mc2": "3", "mo1": "O", "mo2": "7-X", "shape": "4", "year": "1990", "str3": "Y123",
         "utc": "K", "tc": "90"},
        {**blank, "num": "7", "refno": "EEE0050007", "name": "H3S", "element": "H3S1", "ma1": "H", "ma2": "3", "mb1": "S", "mb2": "1",
         "shape": "", "year": "2015", "utc": "K", "tc": "203"},
        {**blank, "num": "8", "refno": "FFF0060008", "name": "Ba(Fe,Co)2As2", "element": "Ba1Fe1.8Co0.2As2", "ma1": "Ba", "ma2": "1",
         "mb1": "Fe", "mb2": "1.8", "mc1": "Co", "mc2": "0.2", "md1": "As", "md2": "2", "shape": "3", "year": "2020",
         "str3": "ThCr2Si2", "utc": "K", "tc": "22", "t2": "21.5"},
        {**blank, "num": "9", "refno": "GGG0070009", "name": "Er123 wrong", "element": "Er1Ba2Cu3O7-X", "ma1": "Er", "ma2": "1",
         "mb1": "Ba", "mb2": "2", "mc1": "Cu", "mc2": "3", "mo1": "O", "mo2": "7-X", "shape": "", "year": "1987", "str3": "Y123",
         "utc": "K", "tc": "275"},
        {**blank, "num": "10", "refno": "HHH0080010", "name": "Nd0.85Sr0.15NiO2", "element": "Nd0.85Sr0.15Ni1O2", "ma1": "Nd",
         "ma2": "0.85", "mb1": "Sr", "mb2": "0.15", "mc1": "Ni", "mc2": "1", "mo1": "O", "mo2": "2", "shape": "4", "year": "2019",
         "str3": "infinite layer", "utc": "K", "tc": "15"},
    ]
    body = "\n".join("\t".join(r[s] for s in symbols) for r in rows)
    return f"{numbers}\n{longs}\n{syms}\n{body}\n"


def load_observations(text: str) -> tuple[list, list]:
    """Parse and build observations; rows whose fields cannot be read are reported, not dropped silently."""
    table = parse_table(text)
    observations, unreadable = [], []
    for _, row in table.iterrows():
        try:
            observations.append(observation(row))
        except ValueError as err:
            unreadable.append({"num": str(row.get("num")), "line": int(row.get("line")), "error": str(err)})
    return observations, unreadable


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="count-only audit of the pinned real table (no fit)")
    parser.add_argument("--smoke", action="store_true", help="synthetic rows through every rule")
    parser.add_argument("--cache", type=Path, default=P.CACHE / "mdr-supercon-220808")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    started = time.time()
    if args.smoke:
        observations, unreadable = load_observations(synthetic_table())
        report = {"smoke": True, "note": "synthetic rows; not a data result", **audit(observations), "unreadable": unreadable}
    elif args.audit:
        data = fetch(DATA_FILE, args.cache, offline=args.offline)
        primary = fetch("primary.tsv", args.cache, offline=args.offline)
        hashes = {name: fetch(name, args.cache, offline=args.offline) and SOURCES[name]["sha256"] for name in SOURCES}
        observations, unreadable = load_observations(data.decode("utf-8", errors="strict"))
        report = {"smoke": False, "sources_verified": hashes, "licence": LICENCE, "attribution": ATTRIBUTION,
                  **audit(observations, primary_tsv=primary.decode("utf-8")), "unreadable": unreadable[:50],
                  "unreadable_count": len(unreadable)}
    else:
        parser.error("choose --audit or --smoke")
    report["seconds"] = round(time.time() - started, 3)
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
