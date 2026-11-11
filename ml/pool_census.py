"""Pool census (count-only): which open crystal-structure databases could widen Hurricane's screening pool.

Step 1 (--probe). For each candidate database a copy is downloaded (through JARVIS-tools, or from the database's own
server) and read as a stream, and the report
gives its size, every field with how often it is filled and of which types, a few short example values of the scalar
fields, the fields that look like an experimental or database cross-reference, and simple counts on the structures:
atoms per cell, number of elements, hydrogen and carbon, and the distinct compositions (exact reduced formulas), with
their overlaps between the databases, for all records and for the pool-like ones (no hydrogen, at least two elements,
at most 100 atoms in the cell, ordered). No model is loaded or fitted, nothing is written into results/ or progress/,
and no structure is printed. The report goes into the job log between markers, in lines of at most 2,000 characters.

Hurricane-like counts (part of the same pass). Each record is also held against the size and element rules of
Hurricane's pool (2 to 5 elements; no hydrogen, noble gases or short-lived radioactive elements; at most 40 atoms in the
cell; ordered) and, where the database gives them, against its band-gap and hull rules (at most 1 eV, at most
50 meV/atom). A record without a band gap or a hull distance is counted apart, never silently passed or dropped. The
count also says how many records carry a link to an experimental structure (an ICSD number in JARVIS-DFT or the
Materials Project; every COD entry is an experimental structure). Hurricane's rule on the training elements and the
exclusions of known superconductors are not applied here: these are upper bounds on what a pool could gain.

Licences of the underlying data, as found on 2026-11-11: JARVIS-DFT, NIST (already used for the pool); Alexandria,
CC BY 4.0 (alexandria.icams.rub.de/about.html); Crystallography Open Database, placed in the public domain by its
contributors (crystallography.net/cod); Materials Project, CC BY 4.0 for its own data. GNoME (Google DeepMind, read from
its public bucket) is under CC BY-NC 4.0 (github.com/google-deepmind/materials_discovery): this project is
non-commercial, so counting it is allowed, but nothing derived from it may enter results/ (CC BY 4.0) or a candidate list
without a separate decision and its own licence notice. OQMD is counted only: no data licence was found for it, and it is
not to be used until one is. This module only counts.
"""
import argparse
import bz2
import collections
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import zipfile
from functools import reduce
from pathlib import Path

DATASETS = ["dft_3d", "mp_3d_2020", "mp_aws", "alexandria_hull_2025", "alex_pbe_hull", "cod", "gnome_2024"]
# the Materials Project's own builds on AWS Open Data: public, no account and no key (registry.opendata.aws/materials-project)
MP_S3 = "https://materialsproject-build.s3.amazonaws.com"
S3NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
MP_AWS_MAX_BYTES = 8 * 1024 ** 3
MP_AWS_NOTE = ("Materials Project summary collection from its AWS Open Data build bucket, newest version listed; Materials "
               "Project terms of use (CC BY 4.0 for its own data); entries marked BY-NC are counted apart and nowhere else")
# databases read from their own servers rather than through JARVIS-tools: URL, format, note, reference
DIRECT = {"alexandria_hull_2025": ["https://alexandria.icams.rub.de/data/pbe/2025.07.02/convex_hull.json.bz2", "bz2",
                                   "Alexandria PBE convex hull, release 2025.07.02, from alexandria.icams.rub.de (CC BY 4.0)",
                                   "https://doi.org/10.1088/2515-7639/ae6620"],
          "gnome_2024": ["https://storage.googleapis.com/gdm_materials_discovery/gnome_data/stable_materials_summary.csv", "csv",
                         "GNoME stable materials summary (Google DeepMind), public bucket gdm_materials_discovery (CC BY-NC 4.0)",
                         "https://doi.org/10.1038/s41586-023-06735-9"]}
LICENCE_FILES = {"gnome_2024": "https://storage.googleapis.com/gdm_materials_discovery/LICENSE"}
UNCONFIRMED = {"oqmd_3d_no_cfid": "no data licence found on oqmd.org on 2026-11-11; counted only, not to be used until its licence is confirmed",
               "gnome_2024": "CC BY-NC 4.0: counted only; nothing derived from it enters results/ or a candidate list without a separate decision"}
# where each database keeps the band gap (eV) and the distance to the convex hull (eV/atom); "a.b" is field b inside a;
# "max0:" takes the value but not below zero (Alexandria leaves e_above_hull empty on part of its hull entries; its
# e_phase_separation, the distance to the hull of the other entries, is negative for a stable compound)
GAP = {"dft_3d": ["optb88vdw_bandgap"], "mp_3d_2020": ["band_gap"], "mp_aws": ["band_gap"], "gnome_2024": ["Bandgap"],
       "alexandria_hull_2025": ["data.band_gap_ind"]}
HULL = {"dft_3d": ["ehull"], "mp_3d_2020": ["e_above_hull"], "mp_aws": ["energy_above_hull"],
        "gnome_2024": ["Decomposition Energy Per Atom All", "Decomposition Energy Per Atom"],
        "alexandria_hull_2025": ["data.e_above_hull", "max0:data.e_phase_separation"]}
# a link to an experimental structure: "all" (every entry is one), fields of which any filled one counts, or "mp"
# (the Materials Project's own flag: not theoretical, or an ICSD number among its database IDs)
EXPERIMENTAL = {"dft_3d": ["icsd"], "mp_3d_2020": ["icsd_ids"], "mp_aws": "mp", "cod": "all"}
NOBLE = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
RADIOACTIVE = {"Tc", "Pm", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Pa", "Np", "Pu", "Am", "Cm"}    # as in ml/storm5.py
BAD = {"H"} | NOBLE | RADIOACTIVE
HUR_ELEMENTS, HUR_MAX_ATOMS, HUR_GAP_MAX, EHULL_MAX = (2, 5), 40, 1.0, 0.05                     # as in ml/screen.py
HURRICANE_LIKE = ("2 to 5 elements, no hydrogen, noble gases or short-lived radioactive elements, at most 40 atoms in the "
                  "cell, ordered; band gap at most 1 eV and at most 50 meV/atom above the hull where the database gives them")
FORMULA = re.compile(r"([A-Z][a-z]?)\s*(\d+(?:\.\d+)?)?")
EXAMPLES = 3
TEXT_MAX = 100
CROSS_REF = re.compile(r"icsd|theor|exp|cod|source|database|origin|ref|entry|mp_id|material_id|prov|tag|^id$|_id$", re.I)
NULLS = {None, "", "na", "NA", "nan", "None", "none", "[]"}
TOKEN = re.compile(rb"(?<=[\[,:\s])-?(?:NaN|Infinity)(?=[\s,\]\}])")
POOL_LIKE = "no hydrogen, at least two elements, at most 100 atoms in the cell, no two sites at the same place"


class Finite(io.RawIOBase):
    """The JSON byte stream with its bare NaN and Infinity tokens (which some of these files contain, and which strict
    JSON readers refuse) written as null. A token is replaced only between delimiters, so a formula such as "NaN3" in a
    string is left alone (text inside a string that itself reads ", NaN," would be changed; no field these counts use
    holds such text), and the stream is cut only after a delimiter, so no token is split."""

    def __init__(self, fh, chunk: int = 1 << 22):
        self.fh, self.chunk, self.buf, self.eof, self.prev = fh, chunk, b"", False, b" "
        self.out, self.pos = memoryview(b""), 0

    def readable(self) -> bool:
        return True

    def _fill(self) -> None:
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
            self.out, self.pos = memoryview(TOKEN.sub(b"null", self.prev + head)[len(self.prev):]), 0
            self.prev = head[-1:] or self.prev

    def readinto(self, b) -> int:
        self._fill()
        n = min(len(b), len(self.out) - self.pos)
        b[:n] = self.out[self.pos:self.pos + n]
        self.pos += n
        return n


def catalogue():
    """URL, file name, note and reference of every dataset, from the installed JARVIS-tools."""
    from jarvis.db.figshare import get_db_info
    return get_db_info()


def download(url: str, path: Path) -> tuple[int, str, float]:
    import requests
    t0, h = time.time(), hashlib.sha256()
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
                h.update(chunk)
    return path.stat().st_size, h.hexdigest(), time.time() - t0


def records_bz2(path: Path, report: dict):
    """The records of a bz2-compressed JSON file: a list of objects, an object holding such a list, or an object of
    objects. The first characters of the file are kept in the report, to show its layout."""
    import ijson
    with bz2.open(path, "rb") as fh:
        head = fh.read(600)
    report["head"] = head.decode("utf-8", errors="replace")[:300]
    first = head.lstrip()[:1]
    with bz2.open(path, "rb") as raw:
        fh = io.BufferedReader(Finite(raw), buffer_size=1 << 20)
        if first == b"[":
            yield from ijson.items(fh, "item", use_float=True)
            return
        prefix = None
        for pre, event, value in ijson.parse(fh, use_float=True):
            if event == "start_array" and pre.count(".") == 0 and pre:
                prefix = pre
                break
        report["list_at"] = prefix
    if prefix:
        with bz2.open(path, "rb") as raw:
            yield from ijson.items(io.BufferedReader(Finite(raw), buffer_size=1 << 20), prefix + ".item", use_float=True)
    else:
        with bz2.open(path, "rb") as raw:
            for _, v in ijson.kvitems(io.BufferedReader(Finite(raw), buffer_size=1 << 20), "", use_float=True):
                yield v


def records_csv(path: Path, report: dict):
    """The rows of a CSV file with a header line, as dictionaries of text."""
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        report["head"] = fh.read(300)
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def number(v):
    """A finite float from a number or a numeric text, else None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.strip())
        except ValueError:
            return None
        return x if math.isfinite(x) else None
    return None


def value(rec: dict, paths: list):
    """The first finite number found at one of the paths ("a.b" is field b inside field a)."""
    for p in paths:
        clip, p = p.startswith("max0:"), p.removeprefix("max0:")
        cur = rec
        for part in p.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        x = number(cur)
        if x is not None:
            return max(x, 0.0) if clip else x
    return None


def parse_formula(text: str):
    """Element counts of a written formula such as "Ag1 Bi1 O3", "AgBiO3" or "Ag4Bi4O12"; None if it has fractions."""
    out = collections.Counter()
    for el, amount in FORMULA.findall(str(text)):
        out[el] += float(amount) if amount else 1.0
    if not out or any(abs(v - round(v)) > 1e-6 or v <= 0 for v in out.values()):
        return None
    return {k: int(round(v)) for k, v in out.items()}


def from_formula(rec: dict):
    """Field used, element counts and atoms in the cell, for a record that has a formula instead of a structure."""
    for k in ("Composition", "composition", "Reduced Formula", "formula", "pretty_formula"):
        v = rec.get(k)
        if isinstance(v, str) and v.strip():
            c = parse_formula(v)
            if c:
                nat = number(rec.get("NSites", rec.get("nsites")))
                if nat is None and k in ("Composition", "composition"):
                    nat = sum(c.values())
                return k, c, (int(nat) if nat is not None else None)
    return None, None, None


def experimental(rec: dict, name: str):
    """True when the record links to an experimental structure, False when it does not, None when the database
    has no such link."""
    spec = EXPERIMENTAL.get(name)
    if spec == "all":
        return True
    if spec == "mp":
        if rec.get("theoretical") is False:
            return True
        ids = rec.get("database_IDs")
        return bool(isinstance(ids, dict) and filled(ids.get("icsd")))
    if not spec:
        return None
    return any(filled(rec.get(k)) for k in spec)


def s3_list(prefix: str, delimiter: str | None = None) -> tuple[list, list]:
    """Sub-folders and files (key, bytes) under a prefix of the public bucket, without signing (ListObjectsV2)."""
    import requests
    import xml.etree.ElementTree as ET
    folders, files, token = [], [], None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        if token:
            params["continuation-token"] = token
        r = requests.get(MP_S3 + "/", params=params, timeout=120)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        folders += [e.findtext(S3NS + "Prefix") for e in root.findall(S3NS + "CommonPrefixes")]
        files += [(e.findtext(S3NS + "Key"), int(e.findtext(S3NS + "Size") or 0)) for e in root.findall(S3NS + "Contents")]
        if root.findtext(S3NS + "IsTruncated") != "true":
            return folders, files
        token = root.findtext(S3NS + "NextContinuationToken")


def mp_aws_listing() -> tuple[dict, list]:
    """The build versions in the bucket and, for the newest, its collections and the files of its summary collection."""
    rep = {"bucket": MP_S3}
    try:
        folders, _ = s3_list("collections/", "/")
        versions = sorted(f.rstrip("/").split("/")[-1] for f in folders)
        rep["versions"] = versions
        dated = [v for v in versions if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)]
        if not dated:
            return rep, []
        latest = rep["latest"] = dated[-1]
        folders, files = s3_list(f"collections/{latest}/", "/")
        rep["collections"] = [f.rstrip("/").split("/")[-1] for f in folders]
        rep["loose_files"] = [[k, s] for k, s in files[:20]]
        keys = []
        if "summary" in rep["collections"]:
            _, keys = s3_list(f"collections/{latest}/summary/")
        keys += [(k, s) for k, s in files if k.split("/")[-1].startswith("summary")]
        rep["summary_files"] = {"count": len(keys), "bytes": sum(s for _, s in keys), "first": [[k, s] for k, s in keys[:5]]}
        return rep, keys
    except Exception as exc:
        rep["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return rep, []


def records_s3(keys: list, store: Path, report: dict):
    """The documents of gzip-compressed JSON-lines (or JSON array) files in the bucket, one file on disk at a time."""
    import gzip
    total, h, skipped = 0, hashlib.sha256(), []
    for i, (key, _) in enumerate(keys):
        if not key.endswith((".jsonl.gz", ".json.gz", ".jsonl", ".json")):
            skipped.append(key)
            continue
        path = store / f"mp_aws_{i:05d}_{key.split('/')[-1]}"
        b, d, _ = download(MP_S3 + "/" + key, path)
        total += b
        h.update(d.encode())
        opener = gzip.open if key.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as fh:
            first = fh.read(1)
            while first and first.isspace():
                first = fh.read(1)
            if first == "[":
                yield from json.loads(first + fh.read())
            else:
                rest = fh.readline()
                if (first + rest).strip():
                    yield json.loads(first + rest)
                for line in fh:
                    if line.strip():
                        yield json.loads(line)
        path.unlink()
    report.update({"zip_bytes": total, "zip_sha256": "sha256 of the files' sha256s: " + h.hexdigest(), "skipped_keys": skipped[:20]})


def licence_head(url: str) -> dict:
    import requests
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    text = r.text
    return {"url": url, "sha256": hashlib.sha256(r.content).hexdigest(), "chars": len(text),
            "head": " ".join(text.split())[:240]}


def records(zpath: Path, member: str):
    """The records of the JSON file inside the zip, one at a time (a list of objects, or an object of objects)."""
    zf = zipfile.ZipFile(zpath)
    names = zf.namelist()
    name = member if member in names else next((n for n in names if n.endswith(".json")), names[0])
    with zf.open(name) as fh:
        head = fh.read(4096).lstrip()
    top = head[:1]
    try:
        import ijson
    except ImportError:            # local tests on small files: the whole file at once
        data = json.loads(zf.read(name))
        yield from (data if isinstance(data, list) else data.values())
        return
    with zf.open(name) as raw:
        fh = io.BufferedReader(Finite(raw), buffer_size=1 << 20)
        if top == b"[":
            yield from ijson.items(fh, "item", use_float=True)
        else:
            for _, v in ijson.kvitems(fh, "", use_float=True):
                yield v


def kind(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "text"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "list"
    return type(v).__name__


def filled(v) -> bool:
    if isinstance(v, str):
        return v.strip() not in NULLS
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return v is not None


def example(v) -> str:
    if isinstance(v, dict):
        return "{object with keys " + ", ".join(sorted(map(str, v))[:12]) + "}"
    if isinstance(v, list):
        return f"[list of {len(v)}" + (f", first a {kind(v[0])}]" if v else "]")
    s = repr(v)
    return s if len(s) <= TEXT_MAX else s[:TEXT_MAX] + "..."


def counts_of(elements) -> dict:
    out = collections.Counter(str(e).strip() for e in elements)
    return dict(out)


def formula_key(counts: dict) -> str:
    """The exact reduced formula, elements in alphabetical order (no tolerance)."""
    if not counts:
        return ""
    g = reduce(math.gcd, [int(n) for n in counts.values()])
    return "".join(f"{e}{int(n) // g}" for e, n in sorted(counts.items()))


def bucket(n: int, edges=(1, 4, 8, 20, 40, 100, 200)) -> str:
    for e in edges:
        if n <= e:
            return f"<= {e}"
    return f"> {edges[-1]}"


def find_elements(rec: dict):
    """The element list of a record's structure, from the JARVIS atoms object or a pymatgen-like structure."""
    for key in ("atoms", "structure", "final_structure"):
        a = rec.get(key)
        if isinstance(a, dict):
            if isinstance(a.get("elements"), list):
                return key, a["elements"]
            if isinstance(a.get("sites"), list):
                els = []
                for s in a["sites"]:
                    sp = s.get("species") or []
                    els.append(sp[0].get("element") if sp and isinstance(sp[0], dict) else s.get("label"))
                return key, els
    return None, None


def overlapping_sites(a: dict, limit: int = 400) -> bool | None:
    """Two sites at the same place in the cell: how a disordered (partly occupied) structure looks once it is written
    out as a list of atoms. None when it cannot be checked (no coordinates, or a cell larger than the limit)."""
    import numpy as np
    if isinstance(a.get("sites"), list):          # a pymatgen structure: partial occupancy is written out on each site
        try:
            return any(len(s.get("species") or []) > 1 or any(float(sp.get("occu", 1.0)) < 1 - 1e-6 for sp in s["species"])
                       for s in a["sites"])
        except (TypeError, ValueError, KeyError, AttributeError):
            return None
    coords, lat = a.get("coords"), a.get("lattice_mat")
    if not isinstance(coords, list) or not coords or len(coords) > limit or not isinstance(lat, list):
        return None
    try:
        x = np.asarray(coords, float)
        if a.get("cartesian"):
            x = x @ np.linalg.inv(np.asarray(lat, float))
        x = np.round(np.mod(x, 1.0), 3) % 1.0
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return None
    return len({tuple(r) for r in x.tolist()}) < len(x)


def census(name: str, info: list, store: Path, keep: bool) -> tuple[dict, dict]:
    url, member = info[0], info[1]
    fmt = member if member in ("bz2", "csv", "s3") else "zip"
    if fmt == "s3":                 # url is the list of (key, bytes) of the files; they are fetched while reading
        zpath = None
        rep = {"dataset": name, "url": MP_S3, "file": f"{len(url)} files", "download_s": None, "note": info[2],
               "reference": info[3] if len(info) > 3 else None}
    else:
        zpath = store / {"bz2": name + ".json.bz2", "csv": name + ".csv", "zip": member + ".zip"}[fmt]
        size, digest, secs = download(url, zpath)
        rep = {"dataset": name, "url": url, "file": zpath.name if fmt != "zip" else member, "zip_bytes": size,
               "zip_sha256": digest, "download_s": round(secs, 1), "note": info[2],
               "reference": info[3] if len(info) > 3 else None}
    if name in LICENCE_FILES:
        rep["licence_file"] = licence_head(LICENCE_FILES[name])
    reader = {"bz2": lambda: records_bz2(zpath, rep), "csv": lambda: records_csv(zpath, rep),
              "zip": lambda: records(zpath, member), "s3": lambda: records_s3(url, store, rep)}[fmt]
    hl = {"base": set(), "loose": set(), "strict": set(), "experimental": set()}
    hl_records, hl_status, hl_exp_records, hl_exp_unknown = collections.Counter(), collections.Counter(), 0, 0
    licences, set_apart = collections.Counter(), collections.Counter()
    nested, nested_types, nested_ex = collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(list)
    t0 = time.time()
    n, fields, types, ex = 0, collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(list)
    atoms_key, n_atoms, n_el, with_h, with_c, no_structure = None, collections.Counter(), collections.Counter(), 0, 0, 0
    struct_keys, overlap = collections.Counter(), collections.Counter()
    comps, top_elements, pool_like, pool_comps, samples = set(), collections.Counter(), 0, set(), []
    for rec in reader():
        n += 1
        if not isinstance(rec, dict):
            types["(record)"][kind(rec)] += 1
            continue
        meta = rec.get("builder_meta")
        lic = meta.get("license") if isinstance(meta, dict) else None
        if lic is not None or name == "mp_aws":
            licences[str(lic)] += 1
        # entries under a non-commercial licence, and withdrawn ones, are counted apart and nowhere else
        if lic == "BY-NC" or rec.get("deprecated") is True:
            set_apart["BY-NC" if lic == "BY-NC" else "deprecated"] += 1
            continue
        for k, v in rec.items():
            types[k][kind(v)] += 1
            if filled(v):
                fields[k] += 1
                if len(ex[k]) < EXAMPLES and not isinstance(v, (dict, list)):
                    ex[k].append(example(v))
                elif len(ex[k]) < 1:
                    ex[k].append(example(v))
        for sub in ("data", "parameters"):
            d = rec.get(sub)
            if isinstance(d, dict):
                for k, v in d.items():
                    nested_types[f"{sub}.{k}"][kind(v)] += 1
                    if filled(v):
                        nested[f"{sub}.{k}"] += 1
                        if len(nested_ex[f"{sub}.{k}"]) < 2:
                            nested_ex[f"{sub}.{k}"].append(example(v))
        key, els = find_elements(rec)
        if els is not None:
            atoms_key = atoms_key or key
            disordered = None
            if isinstance(rec.get(key), dict):
                struct_keys.update(rec[key].keys())
                disordered = overlapping_sites(rec[key])
                overlap[{True: "yes", False: "no", None: "not checked"}[disordered]] += 1
            c, nat = counts_of(els), len(els)
        else:
            fkey, c, nat = from_formula(rec)
            if c is None:
                no_structure += 1
                continue
            atoms_key = atoms_key or "formula: " + fkey
            # a summary row of a DFT calculation stands for one ordered cell; elsewhere order cannot be checked
            disordered = False if fmt == "csv" else None
            overlap[{False: "no (one DFT cell per row)", None: "not checked"}[disordered]] += 1
        if len(samples) < 3:
            samples.append(sorted(c)[:8])
        fk = formula_key(c)
        if disordered is False and "H" not in c and len(c) >= 2 and nat is not None and nat <= 100:
            pool_like += 1
            pool_comps.add(fk)
        if (disordered is False and HUR_ELEMENTS[0] <= len(c) <= HUR_ELEMENTS[1] and not (set(c) & BAD)
                and nat is not None and nat <= HUR_MAX_ATOMS):
            hl["base"].add(fk)
            hl_records["base"] += 1
            g, h = value(rec, GAP.get(name, [])), value(rec, HULL.get(name, []))
            gs = "no gap given" if g is None else ("gap <= 1 eV" if g <= HUR_GAP_MAX else "gap > 1 eV")
            hs = "no hull given" if h is None else ("hull <= 50 meV" if h <= EHULL_MAX else "hull > 50 meV")
            hl_status[f"{gs}; {hs}"] += 1
            if gs != "gap > 1 eV" and hs != "hull > 50 meV":
                hl["loose"].add(fk)
                hl_records["loose"] += 1
                if gs == "gap <= 1 eV" and hs == "hull <= 50 meV":
                    hl["strict"].add(fk)
                    hl_records["strict"] += 1
                x = experimental(rec, name)
                if x:
                    hl["experimental"].add(fk)
                    hl_exp_records += 1
                elif x is None:
                    hl_exp_unknown += 1
        n_atoms[bucket(nat) if nat is not None else "unknown"] += 1
        n_el[bucket(len(c), (1, 2, 3, 4, 5, 6, 8))] += 1
        with_h += "H" in c
        with_c += "C" in c
        top_elements.update(c.keys())
        comps.add(fk)
    rep.update({
        "records": n, "read_s": round(time.time() - t0, 1),
        "fields": {k: {"filled": fields[k], "types": dict(types[k]), "examples": ex[k]} for k in sorted(types)},
        "nested_fields": {k: {"filled": nested[k], "types": dict(nested_types[k]), "examples": nested_ex[k]} for k in sorted(nested_types)},
        "cross_reference_fields": sorted(k for k in types if CROSS_REF.search(str(k))),
        "structure_field": atoms_key, "structure_keys": dict(struct_keys.most_common(20)), "no_structure": no_structure,
        "atoms_per_cell": dict(sorted(n_atoms.items())), "elements_per_compound": dict(sorted(n_el.items())),
        "with_hydrogen": with_h, "with_carbon": with_c, "distinct_compositions": len(comps),
        "overlapping_sites": dict(overlap), "licence_note": UNCONFIRMED.get(name), "element_samples": samples,
        "pool_like": {"rule": POOL_LIKE, "records": pool_like, "distinct_compositions": len(pool_comps)},
        "hurricane_like": {"rule": HURRICANE_LIKE, "gap_fields": GAP.get(name, []), "hull_fields": HULL.get(name, []),
                           "experimental_link": EXPERIMENTAL.get(name), "records": dict(hl_records),
                           "status": dict(sorted(hl_status.items())),
                           "distinct_compositions": {k: len(v) for k, v in hl.items()},
                           "experimental_records": hl_exp_records, "experimental_unknown_records": hl_exp_unknown},
        "licences": dict(licences), "set_apart": dict(set_apart),
        "elements_seen": len(top_elements)})
    if not keep and zpath is not None:
        zpath.unlink()
    sets = {"all": comps, "pool_like": pool_comps}
    sets.update({f"hurricane_{k}": v for k, v in hl.items()})
    return rep, sets


def emit(report: dict, tag: str) -> None:
    text = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    print(f"=== {tag} begin")
    for i in range(0, len(text), 2000):
        print(f"pc|{i // 2000:03d}|{text[i:i + 2000]}")
    print(f"=== {tag} end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))


def probe(store: Path, names: list, keep: bool = False) -> dict:
    store.mkdir(parents=True, exist_ok=True)
    cat = catalogue()
    out, comp_sets = {"step": "probe", "datasets": [], "missing": []}, {}
    try:
        import jarvis
        out["jarvis_tools"] = getattr(jarvis, "__version__", "unknown")
    except ImportError:
        out["jarvis_tools"] = None
    for name in names:
        info = DIRECT.get(name) or cat.get(name)
        if name == "mp_aws":
            listing, keys = mp_aws_listing()
            out["mp_aws_listing"] = listing
            size = sum(s for _, s in keys)
            if not keys or size > MP_AWS_MAX_BYTES:
                out["missing"].append(f"mp_aws: {len(keys)} summary files, {size:,} bytes (limit {MP_AWS_MAX_BYTES:,})")
                continue
            info = [keys, "s3", MP_AWS_NOTE + f" (version {listing.get('latest')})", "https://doi.org/10.1063/1.4812323"]
        if info is None:
            out["missing"].append(name)
            continue
        try:
            rep, comps = census(name, info, store, keep)
        except Exception as exc:   # one database that cannot be read does not stop the others
            out["datasets"].append({"dataset": name, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            continue
        out["datasets"].append(rep)
        comp_sets[name] = comps
        print(f"[census] {name}: {rep['records']:,} records, {rep['distinct_compositions']:,} distinct compositions, "
              f"read in {rep['read_s']} s", flush=True)
    keys = sorted(comp_sets)
    # the databases whose data could be used under their licence as found (JARVIS-DFT, Materials Project, Alexandria, COD)
    open_keys = [k for k in keys if k not in UNCONFIRMED]
    labels = ["all", "pool_like", "hurricane_base", "hurricane_loose", "hurricane_strict", "hurricane_experimental"]
    for label in labels:
        sets = {k: comp_sets[k][label] for k in keys}
        open_union = set().union(*(sets[k] for k in open_keys)) if open_keys else set()
        out[label] = {"overlaps": {f"{a} & {b}": len(sets[a] & sets[b]) for i, a in enumerate(keys) for b in keys[i + 1:]},
                      "union_distinct_compositions": len(set().union(*sets.values())) if sets else 0,
                      "open_union_distinct_compositions": len(open_union),
                      "only_in": {k: len(sets[k] - set().union(*(sets[j] for j in keys if j != k))) for k in keys},
                      "beyond_open_union": {k: len(sets[k] - open_union) for k in keys if k in UNCONFIRMED}}
    # what each database adds to the round-6 source (JARVIS-DFT) and to the experimental structures of the open ones
    if "dft_3d" in comp_sets:
        base = comp_sets["dft_3d"]["hurricane_loose"]
        out["beyond_dft_3d"] = {k: len(comp_sets[k]["hurricane_loose"] - base) for k in keys if k != "dft_3d"}
        exp_open = set().union(*(comp_sets[k]["hurricane_experimental"] for k in open_keys)) if open_keys else set()
        out["experimental_open_union"] = len(exp_open)
        out["experimental_open_union_beyond_dft_3d"] = len(exp_open - base)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--probe", action="store_true", help="step 1: sizes, fields and simple counts of each database")
    parser.add_argument("--store", type=Path, default=Path("/tmp/pool-census"), help="where the downloads go (deleted after reading)")
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args(argv)
    if not args.probe:
        parser.error("only --probe exists so far")
    emit(probe(args.store, args.datasets), "pool-census")


if __name__ == "__main__":
    main()
