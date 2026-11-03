"""Storm8: frozen exploratory direct-Tc comparison with label-free electronic inputs.

P0 uses the same raw feature map and HGB head as Storm6 R2 (Storm7 U0); bitwise equality with an earlier
run is not expected under another numerical environment. With these settings and fewer than 10,000 training
rows, HGB uses no early stopping or subsampling, so its seed has no effect.
P1 appends three DFT ground-state inputs of the same Alexandria PBE entries, fetched by ID from Alexandria's
OPTIMADE API before any target is used, and kept only where the returned structure is the dataset structure:
the density of states at the Fermi energy per atom and per cubic angstrom, and the band gap. They carry no
Tc, lambda or omega_log label. The labels are PBEsol/Quantum ESPRESSO electron-phonon results, while the
existing and new inputs describe the PBE structures: inputs and labels are cross-functional by construction.
Motivation (McMillan-Hopfield): lambda = N(E_F) <I^2> / (M <omega^2>). Neither design replaces a released
model. DFT targets are not measured Tc.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

import storm6 as S

P = S.P
VERSION = "storm8-electronic-ground-state-v1"
DESIGNS = {"P0": "Unchanged Storm6 R2 raw D+geometry direct Tc (Storm7 U0)",
           "P1": "Same plus Alexandria PBE N(E_F) per atom, N(E_F) per cubic angstrom and band gap",
           "PM": "Missingness control: P0 plus one 0/1 availability indicator per electronic column, never a value"}
RULE_DESIGNS = ("P0", "P1")  # The prespecified rule compares these two; PM is descriptive attribution evidence.
ELECTRONIC_COLUMNS = ["dos_ef_per_atom", "dos_ef_per_cubic_angstrom", "band_gap_ev"]
PARAMS, SMOKE_PARAMS, SEED = dict(S.PARAMS), dict(S.SMOKE_PARAMS), S.SEED
MIN_EFFECT_K = 0.03
COVERAGE_FLOOR = 0.90  # Fraction of cohort rows with all three electronic inputs; below it no conclusion about P1.
STORM7_U0_MAE_K = 0.9674607593639637
STORM7_INPUT_SHA256 = {"D": "ba387c1da55e6bf82904234f0ad750c2584c72288a089502ffad0564ee8fa741",
                       "geometry": "a5c514f1f4bb7b68818ebf7e74b662fa6d591f706444492bc2f99dddb910bc5f",
                       "ids": "beaf572610d75cf519ef3871890035e01a9403e3dfe1ba6c9f01f99f9b5ee3e2"}
OPTIMADE_URL = "https://alexandria.icams.rub.de/pbe/v1/structures"
EXPECTED_XC = "gga_x_pbe + gga_c_pbe"
RESPONSE_FIELDS = ["id", "nsites", "lattice_vectors", "species", "species_at_sites", "cartesian_site_positions",
                   "chemical_formula_reduced", "last_modified", "_alexandria_xc_functional", "_alexandria_dos_ef",
                   "_alexandria_band_gap", "_alexandria_magnetization"]
STRUCTURE_TOL = {"cell_metric_relative": 1e-5, "site_angstrom": 1e-3}  # Sampled PBE cells agree with the dataset to 4e-7 in volume.
REVIEWED_PROTOCOL = Path(__file__).resolve().parents[1] / "results" / "validation" / "storm8-protocol-v1" / "protocol.json"
BATCH = 25
MAX_PAGES_PER_BATCH = 5
USER_AGENT = "supercon-ml-storm8/1 (+https://github.com/diracmagic/supercon-ml)"
ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _sha_lf(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def array_sha256(X):
    """SHA-256 of C-order float64 bytes, every NaN written as the same NaN."""
    X = np.ascontiguousarray(X, dtype=np.float64)
    return hashlib.sha256(np.where(np.isnan(X), np.nan, X).tobytes()).hexdigest()


def freeze_protocol(output_dir, *, smoke=False):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__), Path(S.__file__), Path(P.__file__), Path(S.MF.__file__), P.ROOT / "ml" / "requirements.txt"]
    protocol = {
        "version": VERSION, "adopted": False, "report_only": True, "smoke": bool(smoke),
        "source_sha256_lf": {p.relative_to(P.ROOT).as_posix(): _sha_lf(p) for p in sources},
        "data_source": {"url": S.DATA_URL, "prepare": "Unchanged storm6.prepare_real", "n": 7582, "chemical_systems": 4288},
        "target": "Recomputed simplified Allen-Dynes DFT Tc(K), mu*=0.1,f1=f2=1; not measured Tc",
        "designs": DESIGNS, "head": "HistGradientBoostingRegressor on log1p(Tc); expm1 nonnegative clip",
        "params": SMOKE_PARAMS if smoke else PARAMS, "head_seed": "7+zero-based outer fold (no effect: no early stopping or subsampling below 10,000 rows)",
        "feature_baseline": "Exact Storm6 FeatureMap(R2), D+19 geometry; no target components as inputs",
        "electronic_inputs": {
            "columns": ELECTRONIC_COLUMNS,
            "definitions": {"dos_ef_per_atom": "_alexandria_dos_ef / nsites (OPTIMADE values, states/(eV atom))",
                            "dos_ef_per_cubic_angstrom": "_alexandria_dos_ef / |det(lattice_vectors)| (states/(eV A^3))",
                            "band_gap_ev": "_alexandria_band_gap (eV)"},
            "source": {"endpoint": OPTIMADE_URL, "functional": EXPECTED_XC, "response_fields": RESPONSE_FIELDS,
                       "batch_ids": BATCH, "filter": 'id="..." OR id="..."', "max_pages_per_batch": MAX_PAGES_PER_BATCH,
                       "license": "Alexandria data, CC BY 4.0 (https://alexandria.icams.rub.de/about.html); attribution kept"},
            "correspondence": ("Rows bind by Alexandria ID. The alex_supercon structures behind D/geometry equal the Alexandria PBE "
                               "entries (24/24 sampled IDs; PBEsol entries are separate relaxations). Labels are Quantum ESPRESSO "
                               "electron-phonon results listed by Alexandria under PBEsol (10.1002/adfm.202404043). Existing and new "
                               "inputs are PBE descriptors: cross-functional with the labels by construction"),
            "structure_check": {"rule": ("_alexandria_xc_functional equals the PBE value; nsites equals both site-array lengths; "
                                         "every site fully occupied by one element with a finite concentration of 1; equal species "
                                         "counts; every entry of the lattice metric L L^T agrees within cell_metric_relative times "
                                         "sqrt(G_ii G_jj) (per-axis relative lengths and angles), for some lattice-vector order; "
                                         "every site matched one-to-one to a same-element site under periodic images after at most "
                                         "one rigid origin shift, with the Cartesian residual in both cells within site_angstrom; "
                                         "invariant to rotation, lattice-vector order, site order and origin; other basis changes "
                                         "count as mismatches and their coverage cost is reported"),
                                "tolerances": STRUCTURE_TOL, "uses": "IDs and structures only, never labels"},
            "mismatch": "All three inputs NaN; the row is kept and its status names the reason",
            "acquisition_evidence": ("Every raw page is copied into the run directory as soon as it arrives, with an incremental "
                                     "request manifest (url, sha256, bytes, status completed/partial/failed) that survives failures"),
            "dos_convention": "Alexandria's published value, states/(eV calculation cell); no per-spin split documented; negative values are missing",
            "magnetization": "Recorded per row, descriptive only",
            "fetch_order": "By ID only, after the protocol is frozen and before any target is used for fitting",
            "missing": "NaN, handled natively by HGB; electronic columns missing in every training row of a fold are dropped for that fold",
            "snapshot": "Every raw OPTIMADE response is kept byte-for-byte with its SHA-256 in the artifact"},
        "outer": "Unchanged GroupKFold5 chemical-system splits, original row order",
        "ood": "Unchanged Storm6 D-only nearest different-system training distance, 95th percentile, full outer training set",
        "primary_comparison": "P1 minus P0 material-weighted MAE, 1000 paired chemical-system bootstrap, seed 7",
        "estimand": ("P1 minus P0 on all retained rows compares the pipeline with the Alexandria inputs as available (NaN where "
                     "unavailable) against the unchanged baseline. It does not by itself attribute a gain to the physical values: "
                     "PM (P0 plus the per-column availability indicators, which carry every missingness pattern P1 can see but "
                     "no value) is reported alongside as the missingness control, and a gain is attributed to the values only if "
                     "P1 also improves on PM. Coverage and mismatch reasons are reported overall, per held-out fold, in the top-10% "
                     "tail and in the OOD subgroup. The coverage floor is a policy choice"),
        "real_entry_point": ("A real run reads the reviewed frozen file results/validation/storm8-protocol-v1/protocol.json before "
                             "generating anything, refuses an alias to its own output, and refuses to load data unless the protocol "
                             "it generates equals those pre-existing reviewed bytes; CI compares it as well"),
        "shifted_forecasts": "The P0 and P1 forecasts of both 1-ulp refits are saved per row (shifted-forecasts.csv) as each completes",
        "bootstrap": ("storm6.paired_bootstrap: chemical systems resampled with replacement with all their rows; delta = sum of "
                      "row (|y-P1| - |y-P0|) over sampled rows / number of sampled rows; 1000 draws from numpy default_rng(7); "
                      "2.5 and 97.5 percentiles; not selection-adjusted"),
        "decision_rule": {"prespecified_gain_rule_met": "all three conditions below",
                          "coverage": (f"at least {COVERAGE_FLOOR:.0%} of cohort rows have all three electronic inputs; "
                                       "otherwise no conclusion about P1 is drawn"),
                          "main": (f"point delta <= -{MIN_EFFECT_K} K and upper 95% bound < 0: an observed improvement of at "
                                   f"least {MIN_EFFECT_K} K whose interval excludes no improvement; not a 95%-supported "
                                   f"improvement of {MIN_EFFECT_K} K"),
                          "robustness": ("after shifting every finite D, geometry and electronic input by +1 ulp, and separately "
                                         "by -1 ulp, and refitting both designs on the same folds, the point delta is "
                                         f"<= -{MIN_EFFECT_K} K in both refits (Storm forecasts are sensitive to 1-ulp input "
                                         "changes, and the fixed-forecast bootstrap does not include refit instability)"),
                          "otherwise": "rule not met; or no conclusion when the coverage floor is not met",
                          "adopted": "false in every case; report-only"},
        "secondary": "Top-10% target MAE and Storm6 OOD subgroup MAE (paired), electronic-input coverage by status",
        "descriptive_only": ["Spearman correlation of dos_ef_per_atom with DFT lambda and omega_log (None when undefined)",
                             "P0 MAE versus Storm7 U0 (0.9674607593639637 K) as a reproduction check",
                             "PM minus P0 and P1 minus PM paired comparisons (missingness control)",
                             "Per-design forecast and MAE changes in the +1 and -1 ulp refits (their P1-P0 deltas enter the rule)",
                             "Bitwise equality of D, geometry and ID order with the saved Storm7 inputs (storm7_input_sha256)"],
        "storm7_input_sha256": STORM7_INPUT_SHA256, "coverage_floor": COVERAGE_FLOOR, "min_effect_k": MIN_EFFECT_K,
        "package_specification": "ml/requirements.txt (lower bounds only; hash above); exact versions recorded in the run, not pinned",
        "numerics": ("numpy AVX-512 dispatch disabled and OPENBLAS_CORETYPE=Haswell: a mitigation, not validated as guaranteeing "
                     "equality across hardware; hardware and loaded libraries recorded in the artifact"),
        "label_access": "Targets only in supervised heads and evaluation; electronic inputs fetched by ID without labels",
        "feedback_training_records": 0, "actual_normal_state_training_records": 0,
        "limitations": ["Previously inspected folds: exploratory, not independent blind evaluation",
                        "N(E_F) of a new candidate needs a DFT calculation; Alexandria provides it for its entries only",
                        "N(E_F) is one factor of lambda; electron-phonon matrix elements remain unmodelled",
                        "Inputs are PBE ground-state descriptors; labels are PBEsol/Quantum ESPRESSO electron-phonon results",
                        "The chemical-system bootstrap does not include refit instability; the two 1-ulp refits probe it but do not bound it; package versions are not pinned",
                        "DFT labels and experimental measurements remain separate"],
        "publication": "All three designs reported; adopted=false always; no winner or release rule",
    }
    payload = (json.dumps(protocol, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path = out / "protocol.json"
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("Refusing to overwrite a different frozen Storm8 protocol")
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    (out / "protocol.sha256").write_text(digest + "\n", encoding="utf-8")
    return protocol, digest


def _sites_match(X1, e1, X2, e2, cells, tol):
    """One-to-one same-element site match under periodic images after at most one rigid origin shift.
    The residual of a pair is its Cartesian distance in every cell of 'cells', so strain in either cell counts."""
    from scipy.optimize import linear_sum_assignment
    rare = min(sorted(set(e1)), key=e1.count)
    first = e1.index(rare)
    for j in (k for k, e in enumerate(e2) if e == rare):
        shift, matched = X2[j] - X1[first], True
        for element in sorted(set(e1)):
            A = X1[[i for i, e in enumerate(e1) if e == element]]
            B = X2[[i for i, e in enumerate(e2) if e == element]] - shift
            delta = A[:, None, :] - B[None, :, :]
            delta -= np.round(delta)
            distance = np.max([np.linalg.norm(delta @ L, axis=-1) for L in cells], axis=0)
            rows, cols = linear_sum_assignment(distance)
            if distance[rows, cols].max() > tol:
                matched = False
                break
        if matched:
            return True
    return False


def _occupied_elements(record):
    """Element per site for a fully ordered record; raises ValueError('occupancy') for anything else."""
    species, elements = {s["name"]: s for s in record["species"]}, []
    for name in record["species_at_sites"]:
        s = species[name]
        symbols, concentration = list(s["chemical_symbols"]), [float(c) for c in s["concentration"]]
        if len(symbols) != 1 or len(concentration) != 1 or not math.isfinite(concentration[0]) \
                or abs(concentration[0] - 1) > 1e-6 or symbols[0] in ("X", "vacancy"):
            raise ValueError("occupancy")
        elements.append(str(symbols[0]))
    return elements


def same_structure(atoms, record, tol=STRUCTURE_TOL):
    """'ok' if the OPTIMADE record is the dataset structure (see the protocol), otherwise the mismatch reason."""
    if record.get("_alexandria_xc_functional") != EXPECTED_XC:
        return "mismatch_functional"
    try:
        L1, X1 = np.asarray(atoms["lattice_mat"], float), np.asarray(atoms["coords"], float)
        e1 = [str(e) for e in atoms["elements"]]
        if atoms.get("cartesian"):
            X1 = X1 @ np.linalg.inv(L1)
        L2, C2 = np.asarray(record["lattice_vectors"], float), np.asarray(record["cartesian_site_positions"], float)
        try:
            e2 = _occupied_elements(record)
        except ValueError as error:
            if str(error) == "occupancy":
                return "mismatch_occupancy"
            raise
        nsites = record["nsites"]
        if isinstance(nsites, bool) or not isinstance(nsites, (int, float)) or not math.isfinite(nsites) \
                or int(nsites) != nsites or int(nsites) != len(e2) or len(C2) != len(e2):
            return "mismatch_nsites"
        X2 = C2 @ np.linalg.inv(L2)
    except (KeyError, TypeError, ValueError, IndexError, np.linalg.LinAlgError):
        return "mismatch_unreadable"
    if L1.shape != (3, 3) or L2.shape != (3, 3) or X1.shape != (len(e1), 3) or X2.shape != (len(e2), 3) \
            or not (np.isfinite(L1).all() and np.isfinite(L2).all() and np.isfinite(X1).all() and np.isfinite(X2).all()):
        return "mismatch_unreadable"
    if Counter(e1) != Counter(e2):
        return "mismatch_species"
    G1, cell_matched = L1 @ L1.T, False
    scale = np.sqrt(np.outer(np.diag(G1), np.diag(G1)))
    for order in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
        Lp = L2[list(order)]
        if np.max(np.abs(G1 - Lp @ Lp.T) / scale) > tol["cell_metric_relative"]:
            continue
        cell_matched = True
        if _sites_match(X1, e1, X2[:, list(order)], e2, (L1, Lp), tol["site_angstrom"]):
            return "ok"
    return "mismatch_sites" if cell_matched else "mismatch_cell"


def _http_get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _batch_url(ids):
    query = " OR ".join(f'id="{i}"' for i in ids)
    return OPTIMADE_URL + "?" + urllib.parse.urlencode(
        {"filter": query, "response_fields": ",".join(RESPONSE_FIELDS), "page_limit": len(ids)})


def _get_with_retries(get, url, retries, pause):
    for attempt in range(retries + 1):
        try:
            return get(url)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries:
                raise
        time.sleep(pause * 2 ** attempt)
    raise RuntimeError("unreachable")


def _next_link(doc):
    link = (doc.get("links") or {}).get("next")
    if isinstance(link, dict):
        link = link.get("href")
    return link or None


def fetch_electronic(ids, cache_dir, *, get=None, offline=False, retries=4, pause=1.0, snapshot_dir=None, progress_path=None):
    """Fetch OPTIMADE records by ID only. Returns ({id: attributes}, manifest, [raw response bytes]).

    With snapshot_dir and progress_path, every page is copied there as soon as it arrives and a progress manifest
    (status completed / partial / failed) is rewritten after every page, so a later failure loses no evidence."""
    get = get or _http_get
    ids = [str(i) for i in ids]
    bad = [i for i in ids if not ID_PATTERN.fullmatch(i)]
    if bad:
        raise ValueError(f"unsafe material IDs for an OPTIMADE filter: {bad[:3]}")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate material IDs")
    cache = Path(cache_dir)
    raw_dir = cache / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    request = {"endpoint": OPTIMADE_URL, "response_fields": RESPONSE_FIELDS, "batch": BATCH, "ids": ids}
    request_sha = hashlib.sha256(json.dumps(request, separators=(",", ":")).encode()).hexdigest()
    manifest_path = cache / f"manifest-{request_sha[:16]}.json"
    bodies = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("request_sha256") != request_sha:
            raise ValueError("cached OPTIMADE manifest belongs to a different request")
        if snapshot_dir is not None:
            Path(snapshot_dir).mkdir(parents=True, exist_ok=True)
        verified = []

        def cached_progress(status, error=None):
            if progress_path is not None:
                _json(progress_path, {"request_sha256": request_sha, "endpoint": OPTIMADE_URL, "status": status,
                                      "reused_cache": True, "pages_expected": len(manifest["pages"]), "pages_completed": len(verified),
                                      "error": error, "pages": verified, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        cached_progress("partial")
        try:
            for entry in manifest["pages"]:
                body = (raw_dir / f"{entry['sha256']}.json").read_bytes()
                if hashlib.sha256(body).hexdigest() != entry["sha256"]:
                    raise ValueError(f"cached OPTIMADE response bytes changed: {entry['sha256']}")
                if snapshot_dir is not None:
                    (Path(snapshot_dir) / f"{entry['sha256']}.json").write_bytes(body)
                bodies.append(body)
                verified.append(entry)
                cached_progress("partial")
        except Exception as error:
            cached_progress("failed", f"{type(error).__name__}: {error}")
            raise
        manifest = dict(manifest, reused_cache=True)
        cached_progress("completed")
    else:
        if offline:
            raise ValueError("offline mode and no cached OPTIMADE responses for this request")
        pages, batches = [], list(range(0, len(ids), BATCH))
        if snapshot_dir is not None:
            Path(snapshot_dir).mkdir(parents=True, exist_ok=True)

        def progress(status, error=None):
            if progress_path is not None:
                _json(progress_path, {"request_sha256": request_sha, "endpoint": OPTIMADE_URL, "status": status,
                                      "batches_total": len(batches), "pages_completed": len(pages), "error": error,
                                      "pages": pages, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()})
        progress("partial")
        try:
            for start in batches:
                url, seen = _batch_url(ids[start:start + BATCH]), set()
                while url:
                    if url in seen or len(seen) >= MAX_PAGES_PER_BATCH:
                        raise ValueError("OPTIMADE pagination did not terminate")
                    seen.add(url)
                    body = _get_with_retries(get, url, retries, pause)
                    digest = hashlib.sha256(body).hexdigest()
                    (raw_dir / f"{digest}.json").write_bytes(body)
                    if snapshot_dir is not None:
                        (Path(snapshot_dir) / f"{digest}.json").write_bytes(body)
                    pages.append({"url": url, "sha256": digest, "bytes": len(body), "batch_start": start})
                    bodies.append(body)
                    progress("partial")
                    url = _next_link(json.loads(body))
        except Exception as error:
            progress("failed", f"{type(error).__name__}: {error}")
            raise
        manifest = {"request_sha256": request_sha, "endpoint": OPTIMADE_URL, "response_fields": RESPONSE_FIELDS,
                    "batch": BATCH, "n_ids": len(ids), "pages": pages,
                    "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat()}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        progress("completed")
        manifest = dict(manifest, reused_cache=False)
    records = {}
    for body in bodies:
        for item in json.loads(body).get("data", []):
            if item.get("id") in records:
                raise ValueError(f"OPTIMADE returned {item.get('id')} twice")
            records[item.get("id")] = dict(item.get("attributes") or {}, id=item.get("id"))
    unexpected = sorted(set(records) - set(ids))
    if unexpected:
        raise ValueError(f"OPTIMADE returned unrequested IDs: {unexpected[:3]}")
    return records, manifest, bodies


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return math.nan
    return value if math.isfinite(value) else math.nan


def electronic_inputs(ids, structures, records):
    """Three inputs per row, NaN when missing; status explains every row; magnetization is descriptive only."""
    E, status = np.full((len(ids), len(ELECTRONIC_COLUMNS)), np.nan), []
    magnetization, negative_dos = np.full(len(ids), np.nan), 0
    for k, (material, atoms) in enumerate(zip(ids, structures)):
        record = records.get(str(material))
        if record is None:
            status.append("not_returned")
            continue
        check = same_structure(atoms, record)
        if check != "ok":
            status.append(check)
            continue
        dos, n, gap = _number(record.get("_alexandria_dos_ef")), _number(record.get("nsites")), _number(record.get("_alexandria_band_gap"))
        magnetization[k] = _number(record.get("_alexandria_magnetization"))
        negative_dos += int(dos < 0)
        try:
            volume = abs(float(np.linalg.det(np.asarray(record.get("lattice_vectors"), float))))
        except (TypeError, ValueError, np.linalg.LinAlgError):
            volume = math.nan
        per_atom = dos / n if n > 0 and dos >= 0 else math.nan
        per_volume = dos / volume if volume > 1e-8 and dos >= 0 else math.nan
        E[k] = [per_atom, per_volume, gap if gap >= 0 else math.nan]
        status.append("ok" if np.isfinite(E[k]).all() else "partial")
    finite = np.isfinite(magnetization)
    diagnostics = {"negative_dos_rows": negative_dos, "magnetization_recorded_rows": int(finite.sum()),
                   "abs_magnetization_ge_0p1_muB_per_cell": int((np.abs(magnetization[finite]) >= .1).sum())}
    return E, status, diagnostics


def synthetic_electronic(D):
    """Smoke-only stand-in; one row in five missing for NaN handling. The synthetic target depends on D only, so the
    smoke head may never split on these columns and P1 can equal P0 there; the unit tests cover the P1 path."""
    noise = np.random.default_rng(SEED).normal(size=(len(D), 2))
    E = np.column_stack([np.exp(.3 * D[:, 3] + .3 * noise[:, 0]), .1 * np.exp(.3 * D[:, 3] + .3 * noise[:, 1]), np.clip(D[:, 4], 0, None)])
    E[::5] = np.nan
    return E, ["synthetic" if i % 5 else "synthetic_missing" for i in range(len(D))]


def forecast(design, Dtr, Gtr, Etr, ytr, Dte, Gte, Ete, *, fold, params):
    from sklearn.ensemble import HistGradientBoostingRegressor
    if design not in DESIGNS:
        raise ValueError("Unknown Storm8 design")
    fmap = S.FeatureMap("R2").fit(Dtr, Gtr)
    A, B = fmap.transform(Dtr, Gtr), fmap.transform(Dte, Gte)
    identity = {"raw_keep": fmap.keep.tolist(), "fit_rows": len(Dtr), "electronic_keep": None}
    Etr, Ete = S._finite_or_nan(Etr), S._finite_or_nan(Ete)
    if design == "P1":
        keep = np.isfinite(Etr).any(axis=0)
        A, B = np.column_stack([A, Etr[:, keep]]), np.column_stack([B, Ete[:, keep]])
        identity["electronic_keep"] = keep.tolist()
    elif design == "PM":  # Availability only: one 0/1 column per electronic column, never a value.
        A = np.column_stack([A, np.isfinite(Etr).astype(float)])
        B = np.column_stack([B, np.isfinite(Ete).astype(float)])
        identity["electronic_keep"] = "availability_indicators_per_column"
    model = HistGradientBoostingRegressor(random_state=SEED + fold, **params)
    prediction = np.clip(np.expm1(model.fit(A, np.log1p(ytr)).predict(B)), 0, None)
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite forecast")
    return prediction, identity


def decision(paired, *, coverage, shifted_deltas):
    """Three prespecified conditions; adopted is False whatever the outcome."""
    delta, (low, high) = paired["delta_mae_k_new_minus_reference"], paired["percentile_95_interval_k"]
    covered = bool(coverage >= COVERAGE_FLOOR)
    main = bool(delta <= -MIN_EFFECT_K and high < 0)
    robust = bool(len(shifted_deltas) == 2 and all(d <= -MIN_EFFECT_K for d in shifted_deltas.values()))
    if not covered:
        conclusion = "no conclusion about P1: electronic-input coverage below the floor"
    elif len(shifted_deltas) != 2:
        conclusion = "undetermined: the 1-ulp refits are unavailable"
    else:
        conclusion = "prespecified gain rule met" if main and robust else "prespecified gain rule not met"
    return {"prespecified_gain_rule_met": covered and main and robust, "conclusion": conclusion,
            "conditions": {"coverage_floor_met": covered, "main_rule_met": main, "robust_under_1ulp_refits": robust},
            "rule": (f"coverage >= {COVERAGE_FLOOR}; point delta <= -{MIN_EFFECT_K} K and upper 95% bound < 0 "
                     f"(not a 95%-supported {MIN_EFFECT_K} K gain); delta <= -{MIN_EFFECT_K} K in both 1-ulp-shifted refits"),
            "coverage_all_three": float(coverage), "coverage_floor": COVERAGE_FLOOR, "delta_mae_k": delta,
            "percentile_95_interval_k": [low, high], "shifted_delta_mae_k": dict(shifted_deltas), "adopted": False}


def _spearman(a, b):
    """Spearman correlation, or None when it is undefined (fewer than 3 finite pairs or a constant input)."""
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        value = pd.Series(a[mask]).rank().corr(pd.Series(b[mask]).rank())
    return float(value) if np.isfinite(value) else None


def _ulp_shift(X, direction):
    X = np.array(X, dtype=np.float64)
    finite = np.isfinite(X)
    X[finite] = np.nextafter(X[finite], direction * np.inf)
    return X


def shifted_refits(D, G, E, y, splits, reference, *, params, ids=None, fold_of=None, save_to=None):
    """P0 and P1 refit after shifting every finite input by one ulp up, then down; the P1-P0 deltas enter the rule.
    With save_to, every completed forecast vector is written to that CSV at once (aligned IDs and folds), so the
    gate can be audited without refitting."""
    out, saved = {}, {}
    for name, direction in (("plus_1ulp", 1), ("minus_1ulp", -1)):
        Ds, Gs, Es = (_ulp_shift(X, direction) for X in (D, G, E))
        entry, preds = {}, {}
        for design in RULE_DESIGNS:
            pred = np.full(len(y), np.nan)
            for fold, (train, test) in enumerate(splits):
                pred[test], _ = forecast(design, Ds[train], Gs[train], Es[train], y[train], Ds[test], Gs[test], Es[test],
                                         fold=fold, params=params)
            preds[design] = pred
            change = np.abs(pred - reference[design])
            entry[design] = {"mae_k": float(np.mean(np.abs(y - pred))),
                             "mae_change_k": float(np.mean(np.abs(y - pred)) - np.mean(np.abs(y - reference[design]))),
                             "max_abs_forecast_change_k": float(change.max()), "rows_changed": int((change > 0).sum())}
            saved[f"{design.lower()}_{name}_k"] = pred
            if save_to is not None:
                table = pd.DataFrame({"id": ids, "fold": fold_of, "tc_target_dft_k": y})
                for column in ("p0_plus_1ulp_k", "p1_plus_1ulp_k", "p0_minus_1ulp_k", "p1_minus_1ulp_k"):
                    table[column] = saved.get(column, np.full(len(y), np.nan))
                table.to_csv(save_to, index=False)
        entry["delta_mae_k_P1_minus_P0"] = float(np.mean(np.abs(y - preds["P1"])) - np.mean(np.abs(y - preds["P0"])))
        out[name] = entry
    return out


def run(smoke=False, output_dir=None, *, offline=False, reviewed_protocol=REVIEWED_PROTOCOL):
    import sklearn
    from sklearn.model_selection import GroupKFold
    started, identity = time.time(), S.run_identity()
    out = Path(output_dir) if output_dir is not None else P.RESULTS / "storm8" / identity["run_id"]
    if (out / "run.json").exists() or (out / "report.json").exists():
        raise ValueError("Storm8 run directory is non-overwriting; use a new directory")
    if not smoke:  # Every real entry point needs a pre-existing reviewed frozen protocol, read before anything is generated.
        reviewed = Path(reviewed_protocol)
        if reviewed.resolve() == (out / "protocol.json").resolve():
            raise ValueError("Real Storm8 run refused: the reviewed protocol path must not be the run's own output")
        if not reviewed.is_file():
            raise ValueError(f"Real Storm8 run refused: no reviewed frozen file at {reviewed}")
        reviewed_bytes = reviewed.read_bytes()
    protocol, digest = freeze_protocol(out, smoke=smoke)  # Must precede data, inputs and targets.
    if not smoke and reviewed_bytes != (out / "protocol.json").read_bytes():
        raise ValueError(f"Real Storm8 run refused: the generated protocol does not equal the reviewed frozen file {reviewed}")
    _json(out / "run.json", {**identity, "protocol_sha256": digest, "reviewed_protocol": None if smoke else str(reviewed_protocol)})
    report = {**identity, "version": VERSION, "protocol_sha256": digest, "smoke": bool(smoke), "adopted": False,
              "report_only": True, "status": "preparing", "output_dir": str(out), "target": protocol["target"],
              "designs": {d: {"status": "pending", "name": n} for d, n in DESIGNS.items()},
              "limitations": protocol["limitations"],
              "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__}}
    _json(out / "report.json", report)
    stage = "load_data"
    try:
        frame, D, G, _, extra = S.synthetic_data() if smoke else S.prepare_real()
        groups, ids, y = frame["chemsys"].to_numpy(), frame["id"].astype(str).to_numpy(), frame["tc"].to_numpy(float)
        stage = "electronic_inputs"
        if smoke:
            E, status = synthetic_electronic(D)
            optimade, electronic_diagnostics = {"synthetic": True}, {}
        else:
            records, optimade, _ = fetch_electronic(ids, P.CACHE / "alexandria-optimade", offline=offline,
                                                    snapshot_dir=out / "optimade", progress_path=out / "optimade-progress.json")
            E, status, electronic_diagnostics = electronic_inputs(ids, list(frame["atoms"]), records)
        _json(out / "optimade-manifest.json", optimade)
        pd.DataFrame(E, columns=ELECTRONIC_COLUMNS).assign(id=ids, status=status).to_csv(out / "electronic-inputs.csv", index=False)
        available = np.isfinite(E).all(axis=1)
        report["electronic_inputs"] = {"rows": len(ids), "status_counts": dict(Counter(status)),
                                       "coverage_all_three": float(available.mean()), **electronic_diagnostics}
        stage = "folds_and_ood"
        splits = list(GroupKFold(n_splits=5).split(D, groups=groups))
        fold_of, ood = np.zeros(len(y), int), np.zeros(len(y), bool)
        for fold, (train, test) in enumerate(splits):
            fold_of[test] = fold + 1
            _, ood[test], _ = S.ood_distance(D[train], D[test], groups[train])
        tail = y >= np.quantile(y, .9)
        status_array = np.asarray(status)
        report["electronic_inputs"]["coverage_by"] = {
            "fold": {str(f): float(available[fold_of == f].mean()) for f in range(1, 6)},
            "tail": float(available[tail].mean()), "ood": float(available[ood].mean()) if ood.any() else None,
            "status_counts_by_fold": {str(f): dict(Counter(status_array[fold_of == f].tolist())) for f in range(1, 6)}}
        _json(out / "input-manifest.json", {"n": len(y), "chemical_systems": len(np.unique(groups)),
                                            "details": extra[1] if extra else {"synthetic": True},
                                            "electronic_columns": ELECTRONIC_COLUMNS})
        np.savez_compressed(out / "feature-inputs.npz", D=D, geometry=G, electronic=E, ids=ids.astype(str), groups=groups.astype(str))
        report["cohort"] = {"n": len(y), "chemical_systems": len(np.unique(groups)), "tail_threshold_k": float(np.quantile(y, .9))}
        hashes = {"D": array_sha256(D), "geometry": array_sha256(G),
                  "ids": hashlib.sha256("\n".join(ids.astype(str)).encode()).hexdigest()}
        report["input_reproduction"] = {"sha256": hashes, "storm7_sha256": STORM7_INPUT_SHA256,
                                        "bitwise_equal_to_storm7": {k: hashes[k] == STORM7_INPUT_SHA256[k] for k in hashes}}
    except Exception as error:
        report.update(status="failed_preparation", preparation_stage=stage, reason=f"{type(error).__name__}: {error}",
                      seconds=round(time.time() - started, 3))
        _json(out / "report.json", report)
        raise
    report["status"] = "running"
    _json(out / "report.json", report)
    params, predictions, rows = SMOKE_PARAMS if smoke else PARAMS, {}, []
    for design in DESIGNS:
        entry = {"status": "running", "name": DESIGNS[design], "folds": []}
        report["designs"][design] = entry
        pred = np.full(len(y), np.nan)
        try:
            for fold, (train, test) in enumerate(splits):
                pred[test], fit = forecast(design, D[train], G[train], E[train], y[train], D[test], G[test], E[test],
                                           fold=fold, params=params)
                entry["folds"].append({"fold": fold + 1, **fit})
                P.log(f"Storm8 {design} fold{fold + 1}/5 complete ({time.time() - started:.1f}s)")
            entry.update(status="completed", point=S.point_metrics(y, pred, groups, fold_of, tail_mask=tail, ood=ood))
            predictions[design] = pred
            if design == "P0" and not smoke:
                entry["reproduction_check"] = {"p0_mae_k": entry["point"]["mae_k"], "storm7_u0_mae_k": STORM7_U0_MAE_K}
        except (ValueError, RuntimeError, FloatingPointError) as error:
            entry.update(status="failed", reason=f"{type(error).__name__}: {error}")
        _json(out / "report.json", report)
    # Primary per-row evidence is saved as soon as it exists, before any optional or secondary computation.
    for i in range(len(y)):
        rows.append({"id": ids[i], "chemsys": groups[i], "fold": int(fold_of[i]), "tc_target_dft_k": y[i],
                     **{f"{d.lower()}_pred_k": predictions[d][i] if d in predictions else math.nan for d in DESIGNS},
                     "all_electronic_inputs_available": bool(available[i]), "ood": bool(ood[i])})
    pd.DataFrame(rows).to_csv(out / "predictions.csv", index=False)
    masks = (("overall", np.ones(len(y), bool)), ("tail", tail), ("ood", ood))
    if all(d in predictions for d in RULE_DESIGNS):
        paired = {name: S.paired_bootstrap(y[mask], predictions["P1"][mask], predictions["P0"][mask], groups[mask])
                  for name, mask in masks if mask.any()}
        report["paired_P1_minus_P0"] = paired
        _json(out / "report.json", report)
        try:
            shifted = shifted_refits(D, G, E, y, splits, predictions, params=params, ids=ids, fold_of=fold_of,
                                     save_to=out / "shifted-forecasts.csv")
            report["refits_under_1ulp_shifts"] = shifted
            deltas = {k: v["delta_mae_k_P1_minus_P0"] for k, v in shifted.items()}
        except (ValueError, RuntimeError, FloatingPointError, MemoryError) as error:
            report["refits_under_1ulp_shifts"] = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
            deltas = {}
        report["decision"] = decision(paired["overall"], coverage=report["electronic_inputs"]["coverage_all_three"],
                                      shifted_deltas=deltas)
        _json(out / "report.json", report)
    if "PM" in predictions and all(d in predictions for d in RULE_DESIGNS):
        report["missingness_control"] = {
            "descriptive_only": True,
            "PM_minus_P0": S.paired_bootstrap(y, predictions["PM"], predictions["P0"], groups),
            "P1_minus_PM": S.paired_bootstrap(y, predictions["P1"], predictions["PM"], groups),
            "reading": "A gain is attributed to the electronic values only if P1 also improves on PM"}
    if "lambda" in frame:
        report["descriptive_only"] = {
            "spearman_dos_ef_per_atom_vs_lambda": _spearman(E[:, 0], frame["lambda"].to_numpy(float)),
            "spearman_dos_ef_per_atom_vs_log_omega_log": _spearman(E[:, 0], np.log(frame["wlog"].to_numpy(float)))}
    report["status"] = "completed" if all(v["status"] == "completed" for v in report["designs"].values()) else "incomplete"
    report["seconds"] = round(time.time() - started, 3)
    _json(out / "report.json", report)
    files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out.rglob("*")) if p.is_file() and p.name != "artifact-manifest.json"}
    _json(out / "artifact-manifest.json", {"sha256": files})
    if report["status"] != "completed":
        raise RuntimeError(f"Storm8 incomplete; see {out / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--protocol", action="store_true")
    parser.add_argument("--offline", action="store_true", help="use cached OPTIMADE responses only")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviewed-protocol", type=Path, default=REVIEWED_PROTOCOL,
                        help="frozen protocol a real run must reproduce byte for byte")
    args = parser.parse_args()
    if args.protocol:
        freeze_protocol(args.output_dir or P.RESULTS / "storm8" / S.run_identity()["run_id"], smoke=args.smoke)
    else:
        run(smoke=args.smoke, output_dir=args.output_dir, offline=args.offline, reviewed_protocol=args.reviewed_protocol)


if __name__ == "__main__":
    main()
