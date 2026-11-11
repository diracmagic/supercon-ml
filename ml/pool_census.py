"""Pool census (count-only): which open crystal-structure databases could widen Hurricane's screening pool.

Step 1 (--probe). For each candidate database the JARVIS-tools copy is downloaded and read as a stream, and the report
gives its size, every field with how often it is filled and of which types, a few short example values of the scalar
fields, the fields that look like an experimental or database cross-reference, and simple counts on the structures:
atoms per cell, number of elements, hydrogen and carbon, and the distinct compositions (exact reduced formulas), with
their overlaps between the databases, for all records and for the pool-like ones (no hydrogen, at least two elements,
at most 100 atoms in the cell, ordered). No model is loaded or fitted, nothing is written into results/ or progress/,
and no structure is printed. The report goes into the job log between markers, in lines of at most 2,000 characters.

Licences of the underlying data, as found on 2026-11-11: JARVIS-DFT, NIST (already used for the pool); Alexandria,
CC BY 4.0 (alexandria.icams.rub.de/about.html); Crystallography Open Database, placed in the public domain by its
contributors (crystallography.net/cod); Materials Project, CC BY 4.0 for its own data, with the GNoME structures under
CC BY-NC (to be confirmed on the Materials Project terms page before any use). OQMD is counted only: no data licence was
found for it, and it is not to be used until one is. This step only counts.
"""
import argparse
import collections
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

DATASETS = ["dft_3d", "alex_pbe_hull", "cod", "mp_3d_2020", "megnet2", "oqmd_3d_no_cfid"]
UNCONFIRMED = {"oqmd_3d_no_cfid": "no data licence found on oqmd.org on 2026-11-11; counted only, not to be used until its licence is confirmed"}
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
    out = collections.Counter(str(e) for e in elements)
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


def census(name: str, info: list, store: Path, keep: bool) -> tuple[dict, set]:
    url, member = info[0], info[1]
    zpath = store / (member + ".zip")
    size, digest, secs = download(url, zpath)
    rep = {"dataset": name, "url": url, "file": member, "zip_bytes": size, "zip_sha256": digest, "download_s": round(secs, 1),
           "note": info[2], "reference": info[3] if len(info) > 3 else None}
    t0 = time.time()
    n, fields, types, ex = 0, collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(list)
    atoms_key, n_atoms, n_el, with_h, with_c, no_structure = None, collections.Counter(), collections.Counter(), 0, 0, 0
    struct_keys, overlap = collections.Counter(), collections.Counter()
    comps, top_elements, pool_like, pool_comps, samples = set(), collections.Counter(), 0, set(), []
    for rec in records(zpath, member):
        n += 1
        if not isinstance(rec, dict):
            types["(record)"][kind(rec)] += 1
            continue
        for k, v in rec.items():
            types[k][kind(v)] += 1
            if filled(v):
                fields[k] += 1
                if len(ex[k]) < EXAMPLES and not isinstance(v, (dict, list)):
                    ex[k].append(example(v))
                elif len(ex[k]) < 1:
                    ex[k].append(example(v))
        key, els = find_elements(rec)
        if els is None:
            no_structure += 1
            continue
        atoms_key = atoms_key or key
        disordered = None
        if isinstance(rec.get(key), dict):
            struct_keys.update(rec[key].keys())
            disordered = overlapping_sites(rec[key])
            overlap[{True: "yes", False: "no", None: "not checked"}[disordered]] += 1
        c = counts_of(els)
        if len(samples) < 3:
            samples.append(sorted(c)[:8])
        if disordered is False and "H" not in c and len(c) >= 2 and len(els) <= 100:
            pool_like += 1
            pool_comps.add(formula_key(c))
        n_atoms[bucket(len(els))] += 1
        n_el[bucket(len(c), (1, 2, 3, 4, 5, 6, 8))] += 1
        with_h += "H" in c
        with_c += "C" in c
        top_elements.update(c.keys())
        comps.add(formula_key(c))
    rep.update({
        "records": n, "read_s": round(time.time() - t0, 1),
        "fields": {k: {"filled": fields[k], "types": dict(types[k]), "examples": ex[k]} for k in sorted(types)},
        "cross_reference_fields": sorted(k for k in types if CROSS_REF.search(str(k))),
        "structure_field": atoms_key, "structure_keys": dict(struct_keys.most_common(20)), "no_structure": no_structure,
        "atoms_per_cell": dict(sorted(n_atoms.items())), "elements_per_compound": dict(sorted(n_el.items())),
        "with_hydrogen": with_h, "with_carbon": with_c, "distinct_compositions": len(comps),
        "overlapping_sites": dict(overlap), "licence_note": UNCONFIRMED.get(name), "element_samples": samples,
        "pool_like": {"rule": POOL_LIKE, "records": pool_like, "distinct_compositions": len(pool_comps)},
        "elements_seen": len(top_elements)})
    if not keep:
        zpath.unlink()
    return rep, (comps, pool_comps)


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
        if name not in cat:
            out["missing"].append(name)
            continue
        try:
            rep, comps = census(name, cat[name], store, keep)
        except Exception as exc:   # one database that cannot be read does not stop the others
            out["datasets"].append({"dataset": name, "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            continue
        out["datasets"].append(rep)
        comp_sets[name] = comps
        print(f"[census] {name}: {rep['records']:,} records, {rep['distinct_compositions']:,} distinct compositions, "
              f"read in {rep['read_s']} s", flush=True)
    keys = sorted(comp_sets)
    for label, part in (("all", 0), ("pool_like", 1)):
        sets = {k: comp_sets[k][part] for k in keys}
        out[label] = {"overlaps": {f"{a} & {b}": len(sets[a] & sets[b]) for i, a in enumerate(keys) for b in keys[i + 1:]},
                      "union_distinct_compositions": len(set().union(*sets.values())) if sets else 0,
                      "only_in": {k: len(sets[k] - set().union(*(sets[j] for j in keys if j != k))) for k in keys}}
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
