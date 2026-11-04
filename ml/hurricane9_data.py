"""Hurricane 9 data module: the MDR SuperCon Datasheet as a reviewed, censoring-aware training source.

    python ml/hurricane9_data.py --audit [--cache DIR] [--output PATH]   # count-only audit of the real file (no fit)
    python ml/hurricane9_data.py --smoke                                 # synthetic rows through every rule (no download)

Source: MDR SuperCon Datasheet Ver.220808, National Institute for Materials Science, DOI 10.48505/nims.3837,
licence CC BY 4.0. Attribution: "This study used the MDR SuperCon Datasheet (https://doi.org/10.48505/nims.3837),
a numerical data sheet for superconducting materials, which is made public by the National Institute for Materials
Science (NIMS)." The data table and every interpretation file are pinned by SHA-256 (SOURCES). The three header lines
of the table are validated by their field symbols and long names, never by column positions.

Every data rule of coordination/claude-R-009-hurricane9-design.md v0.3 is a function here with a unit test:
observations keep their conditions and the research assumptions in force (section 2.1, 2.2); the ambient/bulk
domain policy, the extreme-value review ceilings with replication lift and the criterion policy (2.2, 2.3); the
Tc-channel decision table and per-family event thresholds with censoring-aware labels (2.3); lossless unit identity,
the representative-target unit event and its flags (2.4); exact and approximate composition, the two parent routes
with statuses and the deterministic family rule (2.6); the provenance graph, connected components, fold manifest and
anchor purge (3); the date-first temporal split (5.2).

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
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402

VERSION = "hurricane9-data-v0.3"
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

# ---------------------------------------------------------------- frozen policies (design note v0.3)
EVENT_K = {"cuprate": 4.2, "iron-nickel": 4.2, "other-oxide": 4.2, "heavy-fermion": 1.0}   # section 2.3
HIGH_TC_K = 30.0                                                                           # named endpoint
# Research assumptions (section 2.2): stated, counted and separable; none is a datasheet convention.
ASSUMPTIONS = {
    "A1": "a blank temperature unit (utc) is read as kelvin; explicit-K rows are a separable cohort",
    "A2": "blank pressure fields (pmax, dtcdp) are read as an ambient-pressure report; no field states ambient, so no "
          "result is pressure-validated",
    "A3": "a blank sample form (shape) is read as unspecified bulk; rows with a stated form are a separable cohort",
}
# Extreme-value review ceilings (section 2.2, F-38): the highest replicated ambient-pressure bulk Tc of each family in the
# public literature plus headroom, cited here and read from no project file; values above are quarantined "extreme
# value, unverified" unless replicated within the unit by two references (lift below). Never a deletion.
CEILING_K = {
    "cuprate": 140.0,        # HgBa2Ca2Cu3O8+d, 133 K at ambient pressure: Schilling et al., Nature 363, 56 (1993)
    "iron-nickel": 60.0,     # SmFeAsO1-xFx, 55 K: Ren et al., Chin. Phys. Lett. 25, 2215 (2008)
    "heavy-fermion": 20.0,   # PuCoGa5, 18.5 K: Sarrao et al., Nature 420, 297 (2002)
    "other-oxide": 40.0,     # Ba0.6K0.4BiO3, about 30 K: Cava et al., Nature 332, 814 (1988)
}
REPLICATION = (2, 0.10)      # an extreme value is lifted when >= 2 references in the unit agree within 10%
# Criterion policy for positives (section 2.3, F-26): the recommended tc is the label; the other channels are checks.
CRITERION = {
    "ordering_slack_k": 0.5,          # t1 <= t2 <= t3 up to this slack, else "resistive criterion ordering"
    "window_rel": 0.10, "window_abs_k": 1.0,   # tc must lie in [t1 - tol, t3 + tol], tol = max(rel * tc, abs)
    "midpoint_rel": 0.20, "midpoint_abs_k": 2.0,  # with only t2: |tc - t2| <= max(rel * tc, abs)
    "sus_rel": 0.20, "sus_abs_k": 2.0,  # tcsus <= t3 + tol, or <= tc * (1 + rel) + abs when t3 is absent
    "weak_diamagnetic_ratio": 0.5,      # tcsus < ratio * tc: flagged, never quarantined
}
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
    position, duplicates = {}, {}
    for i, s in enumerate(symbols):
        s = s.strip()
        if s in position:   # Ver.220808 writes 'year' twice (material block and reference block), with one long name
            if long_names[i].strip().lower() != long_names[position[s]].strip().lower():
                raise ValueError(f"MDR table: duplicate symbol {s!r} with two different long names")
            duplicates.setdefault(s, []).append(i)
            continue
        position[s] = i
    for symbol, label in REQUIRED_FIELDS.items():
        if symbol not in position:
            raise ValueError(f"MDR table: required field {symbol!r} missing from the symbol header")
        found = long_names[position[symbol]].strip().lower()
        if not found.startswith(label.lower()):
            raise ValueError(f"MDR table: field {symbol!r} is labelled {found!r}, expected {label!r}")
    extra = {f"{s}__{k + 2}": i for s, idx in duplicates.items() for k, i in enumerate(idx)}   # later occurrences, for the audit
    rows = []
    for k, line in enumerate(lines[3:], start=4):
        if not line.strip():
            continue
        cells = line.rstrip("\r").split("\t")
        if len(cells) < len(symbols):
            cells += [""] * (len(symbols) - len(cells))
        rows.append({s: cells[i].strip() for s, i in position.items()} | {s: cells[i].strip() for s, i in extra.items()} | {"line": k})
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("MDR table: no data rows")
    df.attrs["duplicate_symbols"] = {s: [position[s]] + idx for s, idx in duplicates.items()}
    df.attrs["duplicate_num_rows"] = int(df["num"].duplicated().sum())
    return df


def number(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


# ---------------------------------------------------------------- composition, parent, family
def _decimal_text(s: str) -> str:
    """The source coefficient at its own precision, in a canonical spelling ('0.60' -> '0.6', '1.0' -> '1')."""
    d = Decimal(str(s).strip()).normalize()
    return format(d, "f") if d != d.to_integral() else str(int(d))


def composition(row) -> tuple[dict, dict]:
    """Composition from the structured element fields plus the oxygen fields (design 2.1, 2.6, F-32).
    Returns (comp, oxygen). comp holds the cations as floats and an 'O' entry only when a numeric oxygen value is
    instantiated by a source field: the measured content (oz) or the number written in the oxygen expression
    (mo2 '4' is fixed, '7-X' is a nominal count with a variable deficit). oxygen = {"expression", "status":
    fixed|variable|unknown|measured|none, "nominal", "measured", "numeric", "numeric_source", "charge_identified",
    "exact"}: 'unknown' (Oz, OX) instantiates no number, so the composition carries no oxygen coefficient and the
    identity keeps the expression; 'exact' is the lossless identity text of the whole composition at source
    precision. The free-text 'element' string is only a cross-check."""
    comp, exact = {}, {}
    for a, b in ELEMENT_PAIRS:
        el, raw = str(row.get(a, "")).strip(), str(row.get(b, "")).strip()
        if not el:
            continue
        x = number(raw)
        if el not in ELEMENTS or x is None or x <= 0:
            raise ValueError(f"row {row.get('num')}: bad element field {el!r} {raw!r}")
        comp[el] = comp.get(el, 0.0) + x
        exact[el] = exact.get(el, []) + [_decimal_text(raw)]
    oxygen = {"expression": str(row.get("mo2", "")).strip(), "status": "none", "nominal": None, "measured": None,
              "numeric": None, "numeric_source": "none", "charge_identified": False}
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
            oxygen["measured"], oxygen["status"] = measured, "measured"
            oxygen["numeric"], oxygen["numeric_source"] = measured, "measured (oz)"
        elif oxygen["nominal"] is not None:
            oxygen["numeric"] = oxygen["nominal"]
            oxygen["numeric_source"] = "fixed count" if oxygen["status"] == "fixed" else "nominal count of a variable expression"
        oxygen["charge_identified"] = oxygen["status"] in ("fixed", "measured")
        if oxygen["numeric"] is not None:
            comp["O"] = comp.get("O", 0.0) + oxygen["numeric"]
    if not comp:
        raise ValueError(f"row {row.get('num')}: no element fields")
    parts = [f"{el}{'+'.join(exact[el])}" for el in sorted(exact)]
    if oxygen["status"] != "none":
        parts.append("O" + (oxygen["expression"] or "?") + (f"|oz{_decimal_text(str(row.get('oz')).strip())}" if oxygen["measured"] is not None else ""))
    oxygen["exact"] = " ".join(parts)
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


def canonical(comp: dict, oxygen_status: str = "none") -> str:
    """Approximate composition bin: coefficients scaled so that the largest non-oxygen coefficient is 1, rounded to
    1e-3, sorted symbols; an 'O?' token marks an oxygen content that no source field instantiates. This bin is an
    isolation edge of the provenance graph (section 3), never the identity of a unit (that is the lossless exact
    text of composition())."""
    scale = max((v for k, v in comp.items() if k != "O"), default=max(comp.values()))
    text = " ".join(f"{el}{round(comp[el] / scale, 3):g}" for el in sorted(comp))
    return text + (" O?" if oxygen_status == "unknown" else "")


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
    known = set(comp) | {"O"}             # the common formula may write a nominal oxygen count the fields do not instantiate
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
        if pos + 1 < len(plain) and plain[pos + 1].islower() and (el + plain[pos + 1]) in known:
            el += plain[pos + 1]          # two-letter symbols only when the composition has them (Fx is F + dopant x)
        if el not in known:
            return None
        pos += len(el)
        m = re.match(r"(\d*\.?\d*)([-+](?:\d+\.?\d*|[A-Za-z]))?", plain[pos:])   # a sign then a letter is a deficit/excess symbol
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


def parent_from_coefficients(comp: dict, *, oxygen_status="none", dopant_below=0.5, tolerance=0.25, max_multiplier=8) -> tuple[str, str]:
    """Coefficient route (design 2.6), used only when the datasheet gives no readable common formula. Returns
    (parent, status). Steps, in this order: (1) with an uninstantiated oxygen content ('unknown' status) the parent is
    unresolved; (2) every element other than O with a source coefficient below `dopant_below` (per formula unit as
    written) is a dopant: an anion dopant (ANIONS) is added to the oxygen count, a cation dopant to the kept cation
    with the largest deficit below its next integer (ties: alphabetical order of the kept cations); (3) the kept
    coefficients are divided by the largest of them and multiplied by m = 1..max_multiplier; m is admissible when every
    scaled coefficient rounds (half up) to a positive integer within `tolerance`; among admissible m the smallest total
    rounding error wins, ties to the smaller m; (4) oxygen rounds half up at that m; (5) no admissible m, no cation
    or a non-positive oxygen count give 'unresolved'. Integer proximity identifies a nominal host, not a verified
    structure; K0.8Fe2Se2 keeps its own parent (Fe5K2Se5) and reaches KFe2Se2 only through the element-set edge."""
    cations = {k: v for k, v in comp.items() if k != "O"}
    if not cations:
        return "unresolved", "unresolved: no cation"
    if oxygen_status == "unknown":
        return "unresolved", "unresolved: oxygen content not instantiated by any source field"
    kept = {k: v for k, v in cations.items() if v >= dopant_below}
    oxygen = comp.get("O")
    if not kept:
        return "unresolved", "unresolved: every coefficient below the dopant threshold"
    for el in sorted(cations):
        if el in kept:
            continue
        if el in ANIONS and oxygen is not None:
            oxygen += cations[el]
            continue
        order = sorted(kept)
        host = max(order, key=lambda k: (math.ceil(kept[k] - 1e-9) - kept[k], -order.index(k)))
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
        return "unresolved", f"unresolved: no multiplier up to {max_multiplier} within {tolerance} of integers"
    error, mult, rounded = best
    if oxygen is not None:
        o = int(math.floor(oxygen / base * mult + 0.5))
        if o <= 0:
            return "unresolved", "unresolved: oxygen rounds to zero"
        rounded["O"] = o
    return _format(rounded), f"coefficients (multiplier {mult})"


def parent(comp: dict, name: str = "", oxygen_status: str = "none") -> tuple[str, str]:
    """The parent compound used as the isolation and search unit, with the route that produced it: the datasheet's
    common formula when it is readable against the fields (source-backed site notation), else the coefficient route.
    'unresolved' parents never create an equal-parent edge."""
    named = parent_from_name(name, comp)
    if named:
        return named, "common formula"
    return parent_from_coefficients(comp, oxygen_status=oxygen_status)


def family(comp: dict, structure_name: str = "", oxygen: bool | None = None) -> tuple[str, str]:
    """Deterministic family with status (design 2.6): structure name first, then the composition fallback. Oxygen
    counts as present when the oxygen field is set even if its content is not instantiated (YBa2Cu3Oz)."""
    els = set(comp) | ({"O"} if oxygen else set())
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


# ---------------------------------------------------------------- observations: evidence, domain, labels
def tc_evidence(row) -> dict:
    """Frozen precedence over the Tc channels of one row (design 2.3 decision table, F-25). Channels: tc (the
    recommended value, the only label channel), tcn (the lowest measured temperature without a transition: a floor),
    t1/t2/t3/tcsus (zero-resistance, midpoint, onset and susceptibility values: checks, never labels). Kinds:
    positive (tc > 0, no floor); negative (floor > 0, no tc > 0, no other positive channel); contradictory (tc > 0 and
    a floor: quarantined); mixed (floor with another positive channel and no tc: quarantined, never a negative);
    zero-without-floor (tc recorded as 0 and no floor: censored); alternate-only (no tc, no floor, another channel
    positive: excluded, no fallback criterion is adopted); negative-value (tc < 0: excluded); none."""
    tc, tcn = number(row.get("tc")), number(row.get("tcn"))
    channels = {k: number(row.get(k)) for k in ("t1", "t2", "t3", "tcsus")}
    alternate = {k: v for k, v in channels.items() if v is not None and v > 0}
    floor = tcn if (tcn is not None and tcn > 0) else None
    if tc is not None and tc < 0:
        kind = "negative-value"
    elif tc is not None and tc > 0:
        kind = "contradictory" if floor is not None else "positive"
    elif floor is not None:
        kind = "mixed" if alternate else "negative"
    elif tc is not None:
        kind = "zero-without-floor"
    elif alternate:
        kind = "alternate-only"
    else:
        kind = "none"
    return {"kind": kind, "tc": tc if kind in ("positive", "contradictory") else None, "floor": floor,
            "channels": channels, "alternate": alternate}


def criterion_check(tc: float, channels: dict) -> tuple[str, list]:
    """Criterion-specific discrepancy policy for a positive (design 2.3, F-26). Only channels > 0 take part; the
    relative denominator is the recommended tc; checks combine by logical OR (any failure quarantines). Returns
    (quarantine reason or "", flags). Ordering: t1 <= t2 <= t3 up to the slack. Window: tc within [t1 - tol, t3 + tol]
    using the resistive channels present, tol = max(window_rel * tc, window_abs_k); with only t2, |tc - t2| within
    max(midpoint_rel * tc, midpoint_abs_k). Susceptibility: tcsus at most t3 + tol, or tc * (1 + sus_rel) + sus_abs_k
    when t3 is absent; a susceptibility value below weak_diamagnetic_ratio * tc is flagged, not quarantined (bulk
    fraction and percolation differ legitimately)."""
    c = CRITERION
    t1, t2, t3, sus = (channels.get(k) if (channels.get(k) or 0) > 0 else None for k in ("t1", "t2", "t3", "tcsus"))
    slack = c["ordering_slack_k"]
    for a, b, label in ((t1, t2, "t1 > t2"), (t2, t3, "t2 > t3"), (t1, t3, "t1 > t3")):
        if a is not None and b is not None and a > b + slack:
            return f"resistive criterion ordering ({label})", []
    tol = max(c["window_rel"] * tc, c["window_abs_k"])
    if t1 is not None and tc < t1 - tol:
        return f"recommended tc {tc:g} below the zero-resistance temperature t1={t1:g}", []
    if t3 is not None and tc > t3 + tol:
        return f"recommended tc {tc:g} above the resistive onset t3={t3:g}", []
    if t2 is not None and t1 is None and t3 is None and abs(tc - t2) > max(c["midpoint_rel"] * tc, c["midpoint_abs_k"]):
        return f"recommended tc {tc:g} far from the midpoint t2={t2:g}", []
    flags = []
    if sus is not None:
        cap = (t3 + tol) if t3 is not None else tc * (1 + c["sus_rel"]) + c["sus_abs_k"]
        if sus > cap:
            return f"susceptibility value tcsus={sus:g} above the resistive onset", []
        if sus < c["weak_diamagnetic_ratio"] * tc:
            flags.append("weak diamagnetic onset")
    return "", flags


def observation(row) -> dict:
    """One data row with its conditions, its evidence kind and a domain status (design 2.1 to 2.3). Never deletes;
    never labels a negative from absence, form, pressure or extremes; every research assumption used is listed."""
    comp, oxygen = composition(row)
    fam, fam_status = family(comp, row.get("str3", ""), oxygen["status"] != "none")
    evidence = tc_evidence(row)
    unit = str(row.get("utc", "")).strip()
    shape = str(row.get("shape", "")).strip()
    pmax, dtcdp = number(row.get("pmax")), str(row.get("dtcdp", "")).strip()
    par, route = parent(comp, row.get("name", ""), oxygen["status"])
    assumptions = ([] if unit else ["A1"]) + ([] if (pmax or 0) > 0 or dtcdp else ["A2"]) + ([] if shape else ["A3"])
    obs = {"num": str(row["num"]), "refno": str(row.get("refno", "")), "year": number(row.get("year")),
           "composition": comp, "elements": sorted(set(comp) | ({"O"} if oxygen["status"] != "none" else set())),
           "exact": oxygen["exact"], "canonical": canonical(comp, oxygen["status"]),
           "parent": par, "parent_route": route, "oxygen": oxygen,
           "family": fam, "family_status": fam_status, "structure_name": str(row.get("str3", "")).strip(),
           "symmetry": SYMMETRY.get(str(row.get("str1", "")).strip()), "space_group": str(row.get("spaceg", "")).strip(),
           "lattice": {k: number(row.get(k)) for k in ("lata", "latb", "latc")}, "lattice_unit": str(row.get("ulat", "")).strip(),
           "shape": shape, "form": SHAPE.get(shape, "unspecified"),
           "evidence": evidence["kind"], "tc": evidence["tc"], "tc_fields": evidence["channels"], "tc_width": number(row.get("tcwidth")),
           "tc_method": TC_METHOD.get(str(row.get("tcmeth", "")).strip().split(",")[0].strip('" '), None),
           "floor": evidence["floor"], "pressure": {"pmax": pmax, "dtcdp": dtcdp,
                                                    "status": "pressure study" if ((pmax or 0) > 0 or dtcdp) else "unknown, assumed ambient (A2)"},
           "unit": unit or "K", "unit_status": "explicit K" if unit.upper() == "K" else "blank, assumed K (A1)" if not unit else f"other ({unit})",
           "assumptions": assumptions, "flags": [], "line": row.get("line")}
    obs["status"], obs["reason"] = domain_status(obs)
    return obs


def domain_status(obs: dict) -> tuple[str, str]:
    """admitted | excluded | quarantined, with the reason code (design 2.2, 2.3). Exclusions are domains, quarantines
    are kept records under review; neither is a negative label."""
    if obs["unit"].upper() != "K":
        return "excluded", "temperature unit not K"
    if "H" in obs["composition"] or "D" in obs["composition"]:
        return "excluded", "hydrogen-containing compound (project rule)"
    if obs["pressure"]["status"] == "pressure study":
        return "excluded", "pressure study"
    if obs["shape"] in EXCLUDED_SHAPES:
        return "excluded", f"sample form {SHAPE[obs['shape']]}"
    if obs["family"] in ("mixed",):
        return "excluded", "family mixed: " + obs["family_status"]
    kind = obs["evidence"]
    if kind == "negative-value":
        return "excluded", "negative tc value"
    if kind == "contradictory":
        return "quarantined", "contradictory evidence within one observation (tc and tcn both present)"
    if kind == "mixed":
        return "quarantined", "floor with another positive Tc channel and no recommended tc"
    if kind == "zero-without-floor":
        return "excluded", "tc recorded as zero without a floor (censored, not a negative)"
    if kind == "alternate-only":
        return "excluded", "no recommended tc; only another Tc channel is positive (no fallback criterion adopted)"
    if kind == "none":
        return "excluded", "no transition and no floor recorded"
    if kind == "positive":
        ceiling = CEILING_K.get(obs["family"])
        if ceiling is not None and obs["tc"] > ceiling:
            return "quarantined", f"extreme value, unverified: tc above the review ceiling of {ceiling:g} K"
        reason, flags = criterion_check(obs["tc"], obs["tc_fields"])
        obs["flags"].extend(flags)
        if reason:
            return "quarantined", "criterion conflict: " + reason
    return "admitted", ""


def lift_replicated_extremes(observations: list) -> int:
    """Section 2.2 (F-38): an extreme value is admitted when at least REPLICATION[0] references with distinct refno in
    the same unit agree within REPLICATION[1] of their largest value; the records keep the flag 'replicated extreme'.
    Returns the number of lifted observations. Reads no project anchor or prior-claim file."""
    n_refs, rel = REPLICATION
    groups = defaultdict(list)
    for o in observations:
        if o["status"] == "quarantined" and o["reason"].startswith("extreme value"):
            groups[unit_key(o)].append(o)
    lifted = 0
    for members in groups.values():
        top = max(o["tc"] for o in members)
        agreeing = [o for o in members if o["tc"] >= (1 - rel) * top]
        if len({o["refno"] for o in agreeing}) >= n_refs:
            for o in agreeing:
                o["status"], o["reason"] = "admitted", ""
                o["flags"].append("replicated extreme")
                lifted += 1
    return lifted


def event_label(obs: dict, threshold: float):
    """1 / 0 / 'censored' for the event Tc >= threshold (design 2.3) at observation level. A floor labels 0 only when
    it is at or below the threshold; a positive labels by its value; everything else is censored."""
    if obs["status"] != "admitted":
        return "censored"
    if obs["tc"] is not None and obs["tc"] > 0:
        return 1 if obs["tc"] >= threshold else 0
    if obs["floor"] is not None:
        return 0 if obs["floor"] <= threshold else "censored"
    return "censored"


def form_class(shape: str) -> str:
    return "single crystal" if shape == "3" else "bulk-specified" if shape == "1" else "unspecified"


def unit_key(obs: dict) -> tuple:
    """Lossless unit identity (design 2.4, F-27): the exact composition text at source precision (oxygen expression
    included), the structure name and the sample-form class. Approximate bins never merge units."""
    return (obs["exact"], obs["structure_name"] or "none", form_class(obs["shape"]))


def unit_event(tc_k, floor_k, threshold):
    """Unit event from the representative target (design 2.4, F-25): with positives, E = [median Tc >= T*]; with
    floors only, E = 0 when the largest floor is at or below T*, else censored."""
    if threshold is None:
        return "censored"
    if tc_k is not None:
        return 1 if tc_k >= threshold else 0
    if floor_k is not None:
        return 0 if floor_k <= threshold else "censored"
    return "censored"


def canonical_units(observations: list, *, thresholds=EVENT_K) -> list:
    """Aggregate admitted observations into units (design 2.4): a unit is a group of compatible reports (same lossless
    composition text, structure name and form class), not a specimen. Stored target: the median tc of the positive
    reports; the unit event is the threshold of that stored target (unit_event); the spread, every floor, the
    'straddle' flag (positive reports on both sides of T*), the 'sample-dependent' flag (positives and floors in one
    unit) and the research assumptions in force are kept for the sensitivity tables, never erased."""
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
        tc_k = float(np.median(positives)) if positives else None
        floor_k = max(floors) if floors else None
        label = unit_event(tc_k, floor_k, threshold)
        flags = []
        if positives and floors:
            flags.append("sample-dependent")
        if threshold is not None and positives and min(positives) < threshold <= max(positives):
            flags.append("straddle")
        if threshold is not None and label == 0 and floors and floor_k > threshold:
            flags.append("floor above threshold ignored by positives")
        years = [o["year"] for o in members if o["year"] is not None]
        units.append({"key": key, "exact": key[0], "structure_name": key[1], "form_class": key[2],
                      "canonical": members[0]["canonical"], "oxygen_status": members[0]["oxygen"]["status"],
                      "family": fam, "family_status": members[0]["family_status"], "parent": members[0]["parent"],
                      "parent_route": members[0]["parent_route"], "elements": members[0]["elements"],
                      "members": [o["num"] for o in members], "references": len({o["refno"] for o in members}),
                      "n_observations": len(members), "event_threshold_k": threshold, "event": label,
                      "high_tc_event": (1 if tc_k >= HIGH_TC_K else 0) if tc_k is not None else "censored",
                      "tc_k": tc_k, "tc_spread_k": [min(positives), max(positives), len(positives)] if positives else None,
                      "floor_k": floor_k, "floors_k": sorted(floors), "flags": flags,
                      "assumptions": sorted({a for o in members for a in o["assumptions"]}),
                      "observation_flags": sorted({f for o in members for f in o["flags"]}),
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
    edges for equal approximate composition bin (canonical), equal resolved parent, explicit links and equal element
    set within a family (design 3). Edges group records for isolation only; they never merge label observations.
    extra_nodes: dicts with id, kind, canonical, parent, elements, family, links ((kind, id) pairs). Target-blind."""
    uf, nodes = UnionFind(), {}
    for u in units:
        nodes[("unit",) + tuple(u["key"])] = u
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
        if n.get("parent") and not str(n["parent"]).startswith("unresolved"):   # an unresolved sentinel makes no edge
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
        cid = unit_component[tuple(u["key"])]
        rows.append({"exact": u["exact"], "canonical": u["canonical"], "oxygen_status": u["oxygen_status"],
                     "structure_name": u["structure_name"], "form_class": u["form_class"], "family": u["family"],
                     "parent": u["parent"], "component": cid, "fold": assignment.get(cid), "purged": comps[cid]["purged"],
                     "event_threshold_k": u["event_threshold_k"], "event": u["event"], "high_tc_event": u["high_tc_event"],
                     "tc_k": u["tc_k"], "flags": u["flags"], "assumptions": u["assumptions"], "earliest_year": u["earliest_year"]})
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
    known_parents = {u["parent"] for u in before if not u["parent"].startswith("unresolved")}
    new_parent = [u for u in new if not u["parent"].startswith("unresolved") and u["parent"] not in known_parents]
    return {"cutoff": cutoff, "train_units": before, "test_new_units": new, "test_new_parent_units": new_parent,
            "repeat_report_units": repeat, "undated_excluded": len(undated)}


# ---------------------------------------------------------------- audit (count-only) and smoke
def audit(observations: list, *, primary_tsv: str | None = None, dsc_canonicals: set | None = None) -> dict:
    """Counts and examples for every rule; no model is fitted and no model effect is computed (design 7, step 3).
    Provisional statuses (quarantines, unresolved mappings, assumptions) are reported next to the admitted units,
    never folded into them."""
    out = {"version": VERSION, "rows": len(observations), "status": Counter(o["status"] for o in observations),
           "reasons": Counter(o["reason"] for o in observations if o["reason"]),
           "evidence_kinds": Counter(o["evidence"] for o in observations),
           "family": Counter(o["family"] for o in observations), "family_status": Counter(o["family_status"] for o in observations),
           "oxygen_status": Counter(o["oxygen"]["status"] for o in observations),
           "oxygen_numeric_source": Counter(o["oxygen"]["numeric_source"] for o in observations),
           "form": Counter(o["form"] for o in observations), "unit_status": Counter(o["unit_status"] for o in observations),
           "pressure_status": Counter(o["pressure"]["status"] for o in observations),
           "assumptions": {k: sum(k in o["assumptions"] for o in observations) for k in ASSUMPTIONS},
           "observation_flags": Counter(f for o in observations for f in o["flags"]),
           "with_tc": sum(o["tc"] is not None for o in observations), "with_floor": sum(o["floor"] is not None for o in observations),
           "with_structure_name": sum(bool(o["structure_name"]) for o in observations),
           "with_year": sum(o["year"] is not None for o in observations),
           "parent_routes": Counter(o["parent_route"] for o in observations),
           "unresolved_parent": sum(o["parent"].startswith("unresolved") for o in observations)}
    admitted = [o for o in observations if o["status"] == "admitted"]
    out["admitted_by_family"] = Counter(o["family"] for o in admitted)
    out["admitted_explicit_unit_by_family"] = Counter(o["family"] for o in admitted if "A1" not in o["assumptions"])
    out["event_labels"] = {fam: Counter(str(event_label(o, t)) for o in admitted if o["family"] == fam) for fam, t in EVENT_K.items()}
    units = canonical_units(observations)
    bins = Counter(u["canonical"] for u in units)
    out["units"] = {"n": len(units), "by_family": Counter(u["family"] for u in units),
                    "events": {fam: Counter(str(u["event"]) for u in units if u["family"] == fam) for fam in EVENT_K},
                    "flags": Counter(f for u in units for f in u["flags"]),
                    "multi_observation": sum(u["n_observations"] > 1 for u in units),
                    "approximate_bins_holding_several_units": sum(n > 1 for n in bins.values()),
                    "under_assumption": {k: sum(k in u["assumptions"] for u in units) for k in ASSUMPTIONS}}
    quarantined = [o for o in observations if o["status"] == "quarantined"]
    out["quarantine_examples"] = [{"num": o["num"], "canonical": o["canonical"], "tc": o["tc"], "year": o["year"], "reason": o["reason"]}
                                  for o in sorted(quarantined, key=lambda o: -(o["tc"] or 0))[:10]]
    out["replicated_extremes"] = sum("replicated extreme" in o["flags"] for o in observations)
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
        {**blank, "num": "11", "refno": "III0090011", "name": "", "element": "Y1Ba2Cu3Oz", "ma1": "Y", "ma2": "1", "mb1": "Ba",
         "mb2": "2", "mc1": "Cu", "mc2": "3", "mo1": "O", "mo2": "z", "shape": "", "year": "1988", "str3": "Y123", "utc": "",
         "tc": "91"},                                                                   # unknown oxygen, blank unit (A1)
        {**blank, "num": "12", "refno": "JJJ0100012", "name": "La2CuO4", "element": "La2Cu1O4", "ma1": "La", "ma2": "2", "mb1": "Cu",
         "mb2": "1", "mo1": "O", "mo2": "4", "shape": "1", "year": "1989", "str3": "T", "utc": "K", "tcn": "4.2", "t2": "10"},   # mixed
    ]
    body = "\n".join("\t".join(r[s] for s in symbols) for r in rows)
    return f"{numbers}\n{longs}\n{syms}\n{body}\n"


def load_observations(text: str, notes: dict | None = None) -> tuple[list, list]:
    """Parse and build observations; rows whose fields cannot be read are reported, not dropped silently. The
    replication lift of extreme values (section 2.2) runs once over the whole table. `notes`, when given, receives
    the table's header notes (duplicate symbols, duplicate data numbers)."""
    table = parse_table(text)
    observations, unreadable = [], []
    for _, row in table.iterrows():
        try:
            obs = observation(row)
        except ValueError as err:
            unreadable.append({"num": str(row.get("num")), "line": int(row.get("line")), "error": str(err)})
            continue
        if "year__2" in row:   # the reference block's own year column, kept for the agreement count only
            obs["year_reference_block"] = number(row.get("year__2"))
        observations.append(obs)
    lift_replicated_extremes(observations)
    if notes is not None:
        notes.update(table.attrs)
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
        text = data.decode("utf-8", errors="replace")   # the pinned bytes are hashed above; undecodable bytes are counted
        notes = {}
        observations, unreadable = load_observations(text, notes)
        report = {"smoke": False, "sources_verified": hashes, "licence": LICENCE, "attribution": ATTRIBUTION,
                  "utf8_replacement_characters": text.count("\ufffd"), "table_notes": notes,
                  "year_columns_agree": sum(o.get("year_reference_block") == o["year"] for o in observations),
                  "year_columns_differ": sum(o.get("year_reference_block") not in (None, o["year"]) for o in observations),
                  **audit(observations, primary_tsv=primary.decode("utf-8", errors="replace")), "unreadable": unreadable[:50],
                  "unreadable_count": len(unreadable),
                  "unreadable_reasons": dict(Counter(re.sub(r"row \S+: ", "", u["error"]).split(" '")[0] for u in unreadable))}
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
