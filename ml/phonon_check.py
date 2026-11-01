"""Optional, bounded MACE-MP-0 finite-displacement checks for a few Storm picks.

This is a fixed-cell potential-model triage check, NOT a DFT calculation, a
converged full-Brillouin-zone stability result, or evidence of superconductivity.
The default checks Gamma and the eight q points of a 2x2x2 Gamma-centred mesh
using a 2x2x2 force-constant supercell. Neither atoms nor cell are relaxed.

ASE reference: https://docs.ase-lib.org/_modules/ase/phonons.html
MACE reference: https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html

Heavy dependencies are loaded only inside a timeout-controlled child process.
``run_checks`` is never called by importing this module.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from screen_tracks import in_training_domain

SCHEMA_VERSION = 1
SCOPE = ("Fixed-cell MACE-MP-0 finite-displacement triage on the reported q mesh; no structural relaxation, "
         "supercell convergence, full-Brillouin-zone guarantee, DFT verification, or superconductivity test.")
REUSABLE = {"completed", "inconclusive", "unsupported"}
MODEL_URLS = {
    "small": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-10-mace-128-L0_energy_epoch-249.model",
    "medium": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model",
    "large": "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/MACE_MPtrj_2022.9.model",
}


@dataclasses.dataclass(frozen=True)
class PhononConfig:
    max_candidates: int = 3
    max_total_seconds: float = 180.0
    max_material_seconds: float = 60.0
    max_primitive_atoms: int = 12
    max_supercell_atoms: int = 96
    max_force_evaluations: int = 74
    model: str = "small"  # explicitly the original MACE-MP-0; do not use mace_mp's changing default
    supercell: tuple[int, int, int] = (2, 2, 2)
    q_mesh: tuple[int, int, int] = (2, 2, 2)
    displacement_angstrom: float = 0.01
    imaginary_tolerance_mev: float = 1.0
    max_residual_force_ev_angstrom: float = 0.1
    cpu_threads: int = 2

    def validate(self):
        if self.model not in {"small", "medium", "large"}:
            raise ValueError("model must explicitly select an original MACE-MP-0 small/medium/large checkpoint")
        for key in ("supercell", "q_mesh"):
            value = getattr(self, key)
            if len(value) != 3 or any(int(v) != v or v < 1 for v in value):
                raise ValueError(f"{key} must contain three positive integers")
        if any(q > s or s % q for q, s in zip(self.q_mesh, self.supercell)):
            raise ValueError("q_mesh must be commensurate with and no denser than the finite supercell")
        for key in ("max_total_seconds", "max_material_seconds", "displacement_angstrom",
                    "imaginary_tolerance_mev", "max_residual_force_ev_angstrom"):
            if not math.isfinite(float(getattr(self, key))) or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive and finite")
        for key in ("max_candidates", "max_primitive_atoms", "max_supercell_atoms", "max_force_evaluations", "cpu_threads"):
            if int(getattr(self, key)) != getattr(self, key) or getattr(self, key) < (0 if key == "max_candidates" else 1):
                raise ValueError(f"invalid {key}")


def _stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _write(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def canonical_structure(raw: Mapping) -> dict:
    elements = list(raw.get("elements", []))
    cell, coords = np.asarray(raw.get("lattice_mat"), float), np.asarray(raw.get("coords"), float)
    if not elements or any(not isinstance(e, str) or not e for e in elements):
        raise ValueError("structure needs element symbols")
    if cell.shape != (3, 3) or coords.shape != (len(elements), 3):
        raise ValueError("invalid cell or coordinates shape")
    if not np.isfinite(cell).all() or not np.isfinite(coords).all() or abs(np.linalg.det(cell)) < 1e-8:
        raise ValueError("structure must have finite coordinates and a nonsingular 3D cell")
    pbc = np.asarray(raw.get("pbc", True), bool)
    if not pbc.all():
        raise ValueError("only fully periodic bulk structures are supported")
    return {"elements": elements, "lattice_mat": cell.tolist(), "coords": coords.tolist(),
            "cartesian": bool(raw.get("cartesian", False)), "pbc": [True, True, True]}


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _versions() -> dict:
    versions = {}
    for package in ("mace-torch", "ase", "torch", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def calculation_key(structure: dict, config: PhononConfig) -> str:
    settings = dataclasses.asdict(config)
    for key in ("max_candidates", "max_total_seconds", "max_material_seconds"):
        settings.pop(key)
    return _sha({"schema": SCHEMA_VERSION, "structure": structure, "settings": settings, "versions": _versions(),
                 "model_url": MODEL_URLS[config.model]})


def q_points(mesh) -> np.ndarray:
    """Gamma-centred fractional reciprocal coordinates, including Gamma."""
    points = np.indices(tuple(mesh)).reshape(3, -1).T / np.asarray(mesh)
    return np.where(points >= 0.5, points - 1.0, points)


def summarize_modes(energies_ev, qpts, config: PhononConfig, residual_force: float) -> dict:
    energies = np.asarray(energies_ev, float)
    qpts = np.asarray(qpts, float)
    if energies.ndim != 2 or len(energies) != len(qpts) or energies.shape[1] == 0 or not np.isfinite(energies).all():
        raise ValueError("phonon calculation returned missing or nonfinite modes")
    if not math.isfinite(residual_force):
        raise ValueError("equilibrium forces are nonfinite")
    mev = energies * 1000
    bad = mev < -config.imaginary_tolerance_mev
    minimum = np.unravel_index(int(np.argmin(mev)), mev.shape)
    equilibrated = residual_force <= config.max_residual_force_ev_angstrom
    return {"status": "completed" if equilibrated else "inconclusive",
            "verdict": ("imaginary_modes_sampled" if bad.any() else "no_significant_imaginary_modes_sampled")
                       if equilibrated else "not_assessed_non_equilibrium",
            "min_signed_mode_energy_mev": float(mev[minimum]), "min_mode_q_fractional": qpts[minimum[0]].tolist(),
            "significant_imaginary_modes": int(bad.sum()), "sampled_q_points": qpts.tolist(),
            "modes_per_q": int(mev.shape[1]), "imaginary_tolerance_mev": config.imaginary_tolerance_mev,
            "max_residual_force_ev_angstrom": float(residual_force),
            "equilibrium_force_tolerance_ev_angstrom": config.max_residual_force_ev_angstrom}


def _provenance(structure: dict, config: PhononConfig) -> dict:
    return {"schema_version": SCHEMA_VERSION, "created_at": _stamp(), "structure_sha256": _sha(structure),
            "calculation_sha256": calculation_key(structure, config), "model": "MACE-MP-0", "model_size": config.model,
            "model_release": "mace_mp_0", "model_url": MODEL_URLS[config.model], "versions": _versions(),
            "device": "cpu", "dtype": "float64", "scope": SCOPE, "settings": dataclasses.asdict(config),
            "finite_displacement": {"scheme": "central differences, all primitive-cell atoms and Cartesian directions",
                                    "displacement_angstrom": config.displacement_angstrom,
                                    "supercell": list(config.supercell), "q_mesh": list(config.q_mesh),
                                    "acoustic_sum_rule": True, "force_constant_symmetrization_iterations": 3,
                                    "relaxed": False}}


def _weights_hash(calc) -> str:
    digest = hashlib.sha256()
    for index, model in enumerate(calc.models):
        for name, tensor in sorted(model.state_dict().items()):
            digest.update(f"{index}:{name}:{tensor.dtype}:{tuple(tensor.shape)}".encode())
            digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _calculate(structure: dict, config: PhononConfig, force_cache: Path) -> dict:
    """Child-process implementation. All absence/failure states remain explicit."""
    provenance = _provenance(structure, config)
    try:
        import torch
        from ase import Atoms
        from ase.phonons import Phonons
        from mace.calculators import mace_mp
    except ImportError as err:
        return dict(provenance, status="unavailable", verdict="not_assessed", reason=f"optional dependency missing: {err}")
    torch.set_num_threads(config.cpu_threads)
    try:
        # An explicit release URL also prevents a future alias change from
        # silently substituting a different potential for a cached calculation.
        calc = mace_mp(model=MODEL_URLS[config.model], device="cpu", default_dtype="float64", dispersion=False)
    except Exception as err:
        return dict(provenance, status="unavailable", verdict="not_assessed", reason=f"MACE checkpoint could not load: {err}")
    provenance["model_weights_sha256"] = _weights_hash(calc)
    atoms = Atoms(symbols=structure["elements"], cell=structure["lattice_mat"], pbc=True,
                  **({"positions": structure["coords"]} if structure["cartesian"] else {"scaled_positions": structure["coords"]}))
    supported = set(int(z) for z in calc.z_table.zs)
    missing = sorted({s for s, z in zip(atoms.get_chemical_symbols(), atoms.numbers) if int(z) not in supported})
    if missing:
        return dict(provenance, status="unsupported", verdict="not_assessed", reason="checkpoint does not cover these elements",
                    unsupported_elements=missing)
    atoms.calc = calc
    forces = atoms.get_forces()
    if not np.isfinite(forces).all():
        return dict(provenance, status="failed", verdict="not_assessed", reason="MACE equilibrium forces are nonfinite")
    max_force = float(np.linalg.norm(forces, axis=1).max())
    if max_force > config.max_residual_force_ev_angstrom:
        return dict(provenance, status="inconclusive", verdict="not_assessed_non_equilibrium",
                    reason="input geometry is not stationary under MACE; finite displacements were not run",
                    max_residual_force_ev_angstrom=max_force,
                    equilibrium_force_tolerance_ev_angstrom=config.max_residual_force_ev_angstrom)
    force_cache.mkdir(parents=True, exist_ok=True)
    # A hard timeout can leave an empty ASE lock/cache entry. Only remove empty
    # displacement files in this calculation's own content-addressed directory.
    for path in force_cache.glob("cache.*.json"):
        if path.stat().st_size == 0:
            path.unlink()
    import inspect
    kwargs = {}
    if "use_mean_minimum_images" in inspect.signature(Phonons).parameters:
        kwargs["use_mean_minimum_images"] = True
    provenance["finite_displacement"]["mean_minimum_images"] = bool(kwargs)
    ph = Phonons(atoms, calc, supercell=tuple(config.supercell), delta=config.displacement_angstrom,
                 name=str(force_cache), **kwargs)
    ph.run()
    ph.read(acoustic=True, symmetrize=3)
    points = q_points(config.q_mesh)
    energies = ph.band_structure(points, verbose=False)
    return dict(provenance, **summarize_modes(energies, points, config, max_force))


def _subprocess_check(request: Path, response: Path, timeout: float, threads: int):
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads))
    return subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(request), str(response)],
                          timeout=timeout, capture_output=True, text=True, env=env, check=False)


def run_checks(candidates, structures_by_id: Mapping, output_dir, *, config: PhononConfig | None = None) -> dict:
    """Check at most N in-domain Storm candidates; never classify skipped work as success.

    Candidates may be records or a pandas DataFrame. Only records with a known,
    finite training distance <= 1 enter the bounded queue. The worker's timeout
    includes imports, checkpoint download/loading, force evaluations and analysis.
    """
    config = config or PhononConfig()
    config.validate()
    records = candidates.to_dict("records") if hasattr(candidates, "to_dict") else list(candidates)
    records = [r for r in records if r.get("model", "Storm") == "Storm" and in_training_domain(r)]
    def score(row):
        try:
            value = float(row.get("storm_tc", row.get("tc", 0)))
            return value if math.isfinite(value) else -math.inf
        except (ValueError, TypeError):
            return -math.inf
    records.sort(key=score, reverse=True)
    unique, seen = [], set()
    for row in records:
        mid = str(row.get("jid", row.get("id", "")))
        if mid and mid not in seen:
            unique.append((mid, row))
            seen.add(mid)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    results = []
    for mid, row in unique[:config.max_candidates]:
        base = {"material_id": mid, "formula": row.get("formula", mid), "cached": False, "scope": SCOPE}
        raw = structures_by_id.get(mid)
        if raw is None:
            results.append(dict(base, status="invalid_structure", verdict="not_assessed", reason="structure missing"))
            continue
        try:
            structure = canonical_structure(raw)
        except (ValueError, TypeError) as err:
            results.append(dict(base, status="invalid_structure", verdict="not_assessed", reason=str(err)))
            continue
        n = len(structure["elements"])
        estimates = {"primitive_atoms": n, "supercell_atoms": n * math.prod(config.supercell), "force_evaluations": 6 * n + 2}
        result = dict(_provenance(structure, config), **base, estimates=estimates)
        cache_dir = output_dir / result["calculation_sha256"]
        result_file = cache_dir / "result.json"
        if result_file.exists():
            try:
                old = json.loads(result_file.read_text(encoding="utf-8"))
                if old.get("calculation_sha256") == result["calculation_sha256"] and old.get("status") in REUSABLE:
                    results.append(dict(old, material_id=mid, formula=base["formula"], cached=True))
                    continue
            except (OSError, ValueError):
                pass
        if (n > config.max_primitive_atoms or estimates["supercell_atoms"] > config.max_supercell_atoms
                or estimates["force_evaluations"] > config.max_force_evaluations):
            result.update(status="budget_exceeded", verdict="not_assessed", reason="structure exceeds atom/force-evaluation budget")
        else:
            remaining = config.max_total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                result.update(status="budget_exceeded", verdict="not_assessed", reason="total wall-clock budget exhausted")
            else:
                request, response = cache_dir / "request.json", cache_dir / "worker-result.json"
                _write(request, {"structure": structure, "config": dataclasses.asdict(config), "force_cache": str(cache_dir / "forces")})
                try:
                    proc = _subprocess_check(request, response, min(config.max_material_seconds, remaining), config.cpu_threads)
                    if proc.returncode != 0 or not response.exists():
                        result.update(status="failed", verdict="not_assessed", reason=(proc.stderr or "worker returned no result")[-1200:])
                    else:
                        worker = json.loads(response.read_text(encoding="utf-8"))
                        if worker.get("calculation_sha256") != result["calculation_sha256"]:
                            raise ValueError("worker response does not match requested structure/settings")
                        result.update(worker)
                except subprocess.TimeoutExpired:
                    result.update(status="timeout", verdict="not_assessed", reason="hard wall-clock budget reached; calculation incomplete")
                except (OSError, ValueError) as err:
                    result.update(status="failed", verdict="not_assessed", reason=str(err))
        result["result_file"] = str(result_file)
        _write(result_file, result)
        results.append(result)
    out = {"enabled": True, "schema_version": SCHEMA_VERSION, "scope": SCOPE, "selection": "top predicted Tc, in-domain Storm only",
           "eligible": len(unique), "selected": len(results), "not_selected": max(0, len(unique) - config.max_candidates),
           "elapsed_seconds": round(time.monotonic() - started, 3), "config": dataclasses.asdict(config), "materials": results}
    _write(output_dir / "summary.json", out)
    return out


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("REQUEST", "RESPONSE"))
    args = parser.parse_args()
    if not args.worker:
        parser.error("this optional module is called by screening; --worker is an internal entry point")
    request, response = map(Path, args.worker)
    payload = json.loads(request.read_text(encoding="utf-8"))
    cfg = PhononConfig(**payload["config"])
    cfg.validate()
    try:
        out = _calculate(payload["structure"], cfg, Path(payload["force_cache"]))
    except Exception as err:
        out = dict(_provenance(payload["structure"], cfg), status="failed", verdict="not_assessed", reason=f"{type(err).__name__}: {err}")
    _write(response, out)


if __name__ == "__main__":
    _main()
