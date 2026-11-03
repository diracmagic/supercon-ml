"""Frozen, CPU-only lattice Fermi Sets variational pilot.

Adaptation of Fu, arXiv:2601.02508v2, Eqs. (19), (21): a lattice
Jordan--Wigner signature times a signed permutation-invariant attention
coefficient. This is not a continuum VMC reproduction or a material Hamiltonian.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

FROZEN_PROTOCOL_SHA256 = "c4e40277a96a0af5dd69a765db8cf487beabd7b7421550fa74a3e4a8cc4f423d"
FROZEN_V2_PROTOCOL_SHA256 = "fa46fbc0cce710e7dad454fa4f0c27bfa5477cc36d39b1a451cc1e99b6f88d60"
KNOWN_PROTOCOL_SHA256 = {FROZEN_PROTOCOL_SHA256, FROZEN_V2_PROTOCOL_SHA256}
EDGE_ORDER = tuple(itertools.combinations(range(4), 2))
SECTORS = ((1, 1), (2, 1), (2, 2))
U_VALUES = (0.0, 4.0, 8.0)
FEATURE_NAMES = [
    name
    for u in (4, 8)
    for name in (
        *(f"fu_u{u}_energy_n{n}_per_site" for n in (2, 3, 4)),
        *(f"fu_u{u}_correlation_n{n}_per_site" for n in (2, 3, 4)),
        f"fu_u{u}_curvature_per_site",
    )
]
_BACKEND = None
_STEP_CACHE = {}


def canonical_mask(mask: int) -> int:
    if not isinstance(mask, (int, np.integer)) or not 0 <= mask < 64:
        raise ValueError("A four-site graph mask must be an integer in [0, 63].")
    edges = [edge for k, edge in enumerate(EDGE_ORDER) if mask & (1 << k)]
    edge_indices = {edge: k for k, edge in enumerate(EDGE_ORDER)}
    return min(
        sum(1 << edge_indices[tuple(sorted((p[a], p[b])))] for a, b in edges)
        for p in itertools.permutations(range(4))
    )


def canonical_graphs() -> list[int]:
    return sorted({canonical_mask(mask) for mask in range(64)})


def build_hamiltonian(mask: int, U: float, nup: int, ndown: int):
    """Return the complete Hubbard matrix and ascending integer Fock bitmasks.

    Modes are site-major: 0up,0down,1up,1down,... . Hopping is -1 along
    every graph edge in both directions; the diagonal is U times doublons.
    """
    if not 0 <= int(mask) < 64 or not 0 <= nup <= 4 or not 0 <= ndown <= 4:
        raise ValueError("Invalid graph or particle sector.")
    states = sorted(
        sum(1 << (2 * i) for i in up) + sum(1 << (2 * i + 1) for i in down)
        for up in itertools.combinations(range(4), nup)
        for down in itertools.combinations(range(4), ndown)
    )
    basis = np.asarray(states, dtype=np.int64)
    index = {state: k for k, state in enumerate(states)}
    H = np.zeros((len(states), len(states)), dtype=np.float64)
    for column, state in enumerate(states):
        H[column, column] = float(U) * sum(
            bool(state & (1 << (2 * site))) and bool(state & (1 << (2 * site + 1)))
            for site in range(4)
        )
        for edge_index, (a, b) in enumerate(EDGE_ORDER):
            if not int(mask) & (1 << edge_index):
                continue
            for spin in (0, 1):
                for dest, source in ((2 * a + spin, 2 * b + spin),
                                     (2 * b + spin, 2 * a + spin)):
                    if not state & (1 << source) or state & (1 << dest):
                        continue
                    sign = -1 if (state & ((1 << source) - 1)).bit_count() % 2 else 1
                    intermediate = state ^ (1 << source)
                    if (intermediate & ((1 << dest) - 1)).bit_count() % 2:
                        sign = -sign
                    target = intermediate | (1 << dest)
                    H[index[target], column] -= sign
    if not np.array_equal(H, H.T):
        raise AssertionError("Constructed Hamiltonian is not symmetric.")
    return H, basis


def configurations(basis: np.ndarray) -> np.ndarray:
    return np.asarray([[mode for mode in range(8) if int(state) & (1 << mode)]
                       for state in basis], dtype=np.int64)


def jw_signature(orbitals: np.ndarray) -> np.ndarray:
    """Permutation parity; coincident identical spin-orbitals have zero amplitude."""
    x = np.asarray(orbitals, dtype=np.int64)
    if x.ndim == 1:
        x = x[None, :]
    if x.ndim != 2 or np.any((x < 0) | (x >= 8)):
        raise ValueError("Expected spin-orbital labels in [0,7].")
    signature = np.ones(len(x), dtype=np.float64)
    for i in range(x.shape[1]):
        for j in range(i + 1, x.shape[1]):
            signature *= np.sign(x[:, j] - x[:, i])
    return signature


def _backend():
    global _BACKEND
    if _BACKEND is None:
        os.environ.setdefault("JAX_PLATFORMS", "cpu")
        import jax
        import jax.numpy as jnp
        import optax
        jax.config.update("jax_enable_x64", True)
        if jax.default_backend() != "cpu":
            raise RuntimeError("The frozen protocol requires the CPU backend.")
        _BACKEND = (jax, jnp, optax)
    return _BACKEND


def initialize_parameters(seed: int):
    jax, jnp, _ = _backend()
    keys = iter(jax.random.split(jax.random.PRNGKey(seed), 7))
    def weight(n_in, n_out):
        return jax.random.normal(next(keys), (n_in, n_out), dtype=jnp.float64) / math.sqrt(n_in)
    return {
        "embedding": weight(8, 16), "embedding_bias": jnp.zeros(16, dtype=jnp.float64),
        "query": weight(16, 16), "key": weight(16, 16), "value": weight(16, 16),
        "projection": weight(16, 16), "projection_bias": jnp.zeros(16, dtype=jnp.float64),
        "head": weight(16, 1)[:, 0], "head_bias": jnp.asarray(0.0, dtype=jnp.float64),
    }


def _symmetric_coefficient(params, tokens):
    """One attention layer, width 16/two heads, residual tanh, sum pooling."""
    jax, jnp, _ = _backend()
    h = jnp.tanh(tokens @ params["embedding"] + params["embedding_bias"])
    shape = (*h.shape[:-1], 2, 8)
    q = (h @ params["query"]).reshape(shape)
    k = (h @ params["key"]).reshape(shape)
    v = (h @ params["value"]).reshape(shape)
    score = jnp.einsum("bihd,bjhd->bhij", q, k) / math.sqrt(8)
    attention = jax.nn.softmax(score, axis=-1)
    mixed = jnp.einsum("bhij,bjhd->bihd", attention, v).reshape(h.shape)
    h = jnp.tanh(h + mixed @ params["projection"] + params["projection_bias"])
    return h.sum(axis=1) @ params["head"] + params["head_bias"]


def wavefunction(params, orbitals):
    """Full first-quantized function, including exchange parity and Pauli zeros."""
    _, jnp, _ = _backend()
    x = np.asarray(orbitals, dtype=np.int64)
    scalar = x.ndim == 1
    if scalar:
        x = x[None, :]
    parity = jw_signature(x)
    tokens = jnp.asarray(np.eye(8, dtype=np.float64)[x])
    result = _symmetric_coefficient(params, tokens) * jnp.asarray(parity)
    return result[0] if scalar else result


def rayleigh_quotient(psi, H) -> float:
    psi = np.asarray(psi, dtype=np.float64)
    norm2 = float(psi @ psi)
    if not np.isfinite(norm2) or norm2 <= 0:
        raise ValueError("Wavefunction has zero or nonfinite norm.")
    return float(psi @ H @ psi / norm2)


def exact_solution(H):
    eigenvalues, eigenvectors = np.linalg.eigh(H)
    tolerance = 1e-9 * max(1.0, abs(float(eigenvalues[0])))
    ground = eigenvectors[:, eigenvalues <= eigenvalues[0] + tolerance]
    return eigenvalues, ground @ ground.T


def quality_metrics(H, psi, *, eigenvalues=None, projector=None, gates=None):
    gates = gates or {"energy_per_site_error_max": .0025,
                      "normalized_residual_max": .05,
                      "ground_subspace_fidelity_min": .95,
                      "variational_lower_bound_tolerance": 1e-8}
    if eigenvalues is None or projector is None:
        eigenvalues, projector = exact_solution(H)
    psi = np.asarray(psi, dtype=np.float64)
    norm = float(np.linalg.norm(psi))
    if not np.isfinite(norm) or norm == 0 or not np.isfinite(psi).all():
        return {"passed": False, "reason": "nonfinite_or_zero_wavefunction"}
    psi = psi / norm
    energy = float(psi @ H @ psi)
    error = energy - float(eigenvalues[0])
    residual = float(np.linalg.norm(H @ psi - energy * psi))
    fidelity = float(psi @ projector @ psi)
    checks = {"variational_bound": error >= -gates["variational_lower_bound_tolerance"],
              "energy_per_site": error / 4 <= gates["energy_per_site_error_max"],
              "normalized_residual": residual <= gates["normalized_residual_max"],
              "ground_subspace_fidelity": fidelity >= gates["ground_subspace_fidelity_min"]}
    return {"passed": bool(all(checks.values())), "energy": energy,
            "exact_energy": float(eigenvalues[0]), "energy_error": error,
            "energy_per_site_error": error / 4, "normalized_residual": residual,
            "residual_definition": "norm(H psi-E psi)/norm(psi), in t units",
            "ground_subspace_fidelity": fidelity,
            "ground_space_dimension": int(round(float(np.trace(projector)))),
            "checks": checks}


def feature_lookup(energies):
    """Input axes graph,U=(0,4,8),sector=(N2,N3,N4); output graph,14."""
    e = np.asarray(energies, dtype=np.float64)
    if e.ndim != 3 or e.shape[1:] != (3, 3):
        raise ValueError("Expected energies with shape (graphs,3,3).")
    parts = []
    for u_index in (1, 2):
        eu = e[:, u_index, :]
        parts.extend((eu / 4, (eu - e[:, 0, :]) / 4,
                      ((eu[:, 2] + eu[:, 0] - 2 * eu[:, 1]) / 4)[:, None]))
    return np.concatenate(parts, axis=1)


def _optimizer_spec(solver=None):
    """Both byte-frozen protocols remain reproducible; no outcome-driven choices."""
    if solver is None:
        return 300, "constant"
    optimizer = solver["optimizer"]
    if optimizer == "Adam learning_rate0.01":
        return int(solver["steps"]), "constant"
    if optimizer == "Adam with cosine learning-rate schedule .01 to .00001 over2000steps":
        return int(solver["steps"]), "cosine"
    raise ValueError(f"Optimizer is not recognized in a frozen protocol: {optimizer}")


def learning_rate_at_step(step, solver=None):
    steps, kind = _optimizer_spec(solver)
    if kind == "constant":
        return .01
    fraction = min(max(float(step), 0), steps - 1) / max(steps - 1, 1)
    return .00001 + (.01 - .00001) * .5 * (1 + math.cos(math.pi * fraction))


def _step_functions(n_particles, solver=None):
    steps, schedule_kind = _optimizer_spec(solver)
    cache_key = (n_particles, steps, schedule_kind)
    if cache_key not in _STEP_CACHE:
        jax, jnp, optax = _backend()
        learning_rate = (.01 if schedule_kind == "constant" else
            optax.cosine_decay_schedule(init_value=.01, decay_steps=max(steps - 1, 1), alpha=.001))
        optimizer = optax.adam(learning_rate)
        def loss(params, tokens, H):
            psi = _symmetric_coefficient(params, tokens)
            norm2 = jnp.dot(psi, psi)
            return jnp.dot(psi, H @ psi) / jnp.maximum(norm2, 1e-300)
        def step(params, state, tokens, H):
            value, gradient = jax.value_and_grad(loss)(params, tokens, H)
            updates, state = optimizer.update(gradient, state, params)
            return optax.apply_updates(params, updates), state, value
        _STEP_CACHE[cache_key] = (optimizer, jax.jit(step), jax.jit(loss),
                                    jax.jit(_symmetric_coefficient))
    return _STEP_CACHE[cache_key]


def _tokens(basis):
    _, jnp, _ = _backend()
    return jnp.asarray(np.eye(8, dtype=np.float64)[configurations(basis)])


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _hardware_record():
    jax, _, optax = _backend()
    import contextlib
    import io
    import importlib.metadata
    record = {"python": sys.version, "platform": platform.platform(),
              "machine": platform.machine(), "processor": platform.processor(),
              "cpu_count": os.cpu_count(), "numpy": np.__version__, "jax": jax.__version__,
              "jaxlib": importlib.metadata.version("jaxlib"), "optax": optax.__version__,
              "jax_devices": [str(device) for device in jax.devices()],
              "jax_enable_x64": bool(jax.config.jax_enable_x64),
              "environment": {key: os.environ.get(key) for key in
                  ("NPY_DISABLE_CPU_FEATURES", "OPENBLAS_CORETYPE", "MKL_CBWR", "OMP_NUM_THREADS",
                   "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "JAX_PLATFORMS")}}
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        np.show_runtime()
    record["numpy_runtime"] = stream.getvalue()
    try:
        import threadpoolctl
        record["threadpools"] = threadpoolctl.threadpool_info()
    except ImportError:
        record["threadpools"] = "threadpoolctl unavailable"
    if os.name == "nt":
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10, check=False)
            record["cpu_inventory"] = result.stdout.strip() or result.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["cpu_inventory_error"] = str(exc)
    return record


def _timing_pilot(solver):
    """Compile once, then time 20 largest-case steps; shared compilation is amortized."""
    jax, jnp, _ = _backend()
    H, basis = build_hamiltonian(63, 8, 2, 2)
    tokens = _tokens(basis)
    H_device = jnp.asarray(H)
    seed = solver["initialization_seeds"][0]
    params = initialize_parameters(seed)
    optimizer, step, _, _ = _step_functions(4, solver)
    state = optimizer.init(params)
    start = time.perf_counter()
    compiled = step.lower(params, state, tokens, H_device).compile()
    compile_seconds = time.perf_counter() - start
    step_start = time.perf_counter()
    for _ in range(20):
        params, state, value = compiled(params, state, tokens, H_device)
    jax.block_until_ready(value)
    execution_seconds = time.perf_counter() - step_start
    total_steps = (len(canonical_graphs()) * len(U_VALUES) * len(SECTORS)
                   * len(solver["initialization_seeds"]) * solver["steps"])
    projected = len(SECTORS) * compile_seconds + execution_seconds / 20 * total_steps + 20
    return {"compile_seconds": compile_seconds, "twenty_steps_seconds": execution_seconds,
            "pilot_total_seconds": time.perf_counter() - start,
            "projected_bank_seconds": projected,
            "projected_optimizer_steps": total_steps,
            "projection": f"{len(SECTORS)} sector compilations + measured step rate*{total_steps} steps +20s overhead reserve",
            "states": 36, "seed": seed, "steps": 20,
            "pilot_weights_used_in_bank": False}


def run_bank(output_dir, protocol_path, *, smoke=False):
    start = time.perf_counter()
    output_dir, protocol_path = Path(output_dir), Path(protocol_path)
    raw = protocol_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in KNOWN_PROTOCOL_SHA256:
        raise ValueError(f"Frozen protocol SHA mismatch: {digest}")
    protocol = json.loads(raw)
    solver = protocol["solver"]
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir(exist_ok=True)
    report = {"status": "running", "qc_passed": False, "protocol_sha256": digest,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "motif_masks": canonical_graphs(), "feature_names": FEATURE_NAMES,
              "exact_features": None, "neural_features": None, "entries": [], "failures": [],
              "architecture_details": "8-way spin-orbital onehot; tanh embedding16; one2-head attention(dhead8); tanh residual projection; sum pooling; signed scalar head; JW parity",
              "protocol_version": protocol["version"],
              "solver_settings": solver,
              "learning_rate_initial": learning_rate_at_step(0, solver),
              "learning_rate_final_update": learning_rate_at_step(solver["steps"] - 1, solver),
              "selection": f"lowest finite final energy among fixed seeds {solver['initialization_seeds']} after exactly {solver['steps']} Adam steps",
              "protocol_wording_note": ("solver.selection retains stale 'two fixed seeds' wording; the explicit initialization_seeds list and root instruction specify four, all four are used" if len(solver["initialization_seeds"]) == 4 else None)}
    try:
        report["hardware"] = _hardware_record()
        report["timing"] = _timing_pilot(solver)
        if report["timing"]["projected_bank_seconds"] > protocol["solver"]["hard_seconds"]:
            report["status"] = "timing_gate_failed"
            report["failures"].append("20-step pilot projects beyond the frozen1200second bank budget")
            return report
        if smoke:
            report["status"] = "pilot_only"
            return report
        jax, jnp, _ = _backend()
        exact_energies = np.full((11, 3, 3), np.nan)
        neural_energies = np.full_like(exact_energies, np.nan)
        gates = protocol["solver"]["quality_gate"]
        for graph_index, mask in enumerate(report["motif_masks"]):
            for u_index, U in enumerate(U_VALUES):
                for sector_index, (nup, ndown) in enumerate(SECTORS):
                    if time.perf_counter() - start > protocol["solver"]["hard_seconds"]:
                        raise TimeoutError("Frozen total solver budget exceeded")
                    H, basis = build_hamiltonian(mask, U, nup, ndown)
                    eigenvalues, projector = exact_solution(H)
                    exact_energies[graph_index, u_index, sector_index] = eigenvalues[0]
                    tokens, H_device = _tokens(basis), jnp.asarray(H)
                    optimizer, step, loss, coefficient = _step_functions(nup + ndown, solver)
                    candidates, seed_records = [], []
                    for seed in protocol["solver"]["initialization_seeds"]:
                        fit_start = time.perf_counter()
                        params = initialize_parameters(seed)
                        optimizer_state = optimizer.init(params)
                        trace = [float(loss(params, tokens, H_device))]
                        for iteration in range(protocol["solver"]["steps"]):
                            params, optimizer_state, _ = step(params, optimizer_state, tokens, H_device)
                            if (iteration + 1) % 10 == 0:
                                trace.append(float(loss(params, tokens, H_device)))
                                if time.perf_counter() - fit_start > protocol["solver"]["single_fit_hard_seconds"]:
                                    raise TimeoutError(f"Single-fit60second budget exceeded: graph{mask},U{U},sector{nup}{ndown},seed{seed}")
                                if time.perf_counter() - start > protocol["solver"]["hard_seconds"]:
                                    raise TimeoutError("Frozen total solver1200second budget exceeded")
                        psi = np.asarray(coefficient(params, tokens), dtype=np.float64)
                        metrics = quality_metrics(H, psi, eigenvalues=eigenvalues, projector=projector, gates=gates)
                        seconds = time.perf_counter() - fit_start
                        case_name = f"g{mask:02d}_u{int(U)}_n{nup}{ndown}_seed{seed}.npz"
                        arrays = {f"parameter_{name}": np.asarray(value) for name, value in params.items()}
                        arrays.update(H=H, basis=basis, eigenvalues=eigenvalues,
                                      ground_projector=projector, psi=psi,
                                      energy_trace=np.asarray(trace, dtype=np.float64),
                                      trace_steps=np.arange(0, solver["steps"] + 1, 10), protocol_sha256=np.asarray(digest))
                        np.savez_compressed(cases_dir / case_name, **arrays)
                        seed_records.append({"seed": seed, "seconds": seconds,
                                             "artifact": f"cases/{case_name}", "qc": metrics})
                        if "energy" in metrics and np.isfinite(metrics["energy"]):
                            candidates.append((metrics["energy"], seed, metrics, case_name))
                    entry = {"graph_mask": mask, "U": U, "nup": nup, "ndown": ndown,
                             "basis_size": len(basis), "seeds": seed_records}
                    if candidates:
                        energy, selected_seed, metrics, case_name = min(candidates, key=lambda item: item[0])
                        neural_energies[graph_index, u_index, sector_index] = energy
                        entry.update(selected_seed=selected_seed, qc=metrics, artifact=f"cases/{case_name}")
                        if not metrics["passed"]:
                            report["failures"].append({"graph_mask": mask, "U": U,
                                "sector": [nup, ndown], "reason": "selected_neural_state_failed_frozen_qc", "qc": metrics})
                    else:
                        report["failures"].append({"graph_mask": mask, "U": U,
                            "sector": [nup, ndown], "reason": "no_finite_seed"})
                    report["entries"].append(entry)
                    print(f"bank {len(report['entries'])}/99 graph={mask} U={U:g} sector={nup},{ndown} qc={entry.get('qc', {}).get('passed', False)}", flush=True)
                    _write_json(output_dir / "report.json", report)
        np.savez_compressed(output_dir / "energies.npz", exact=exact_energies, neural=neural_energies,
                            motif_masks=np.asarray(report["motif_masks"]), U=np.asarray(U_VALUES), sectors=np.asarray(SECTORS))
        report["exact_features"] = feature_lookup(exact_energies).tolist()
        report["neural_features"] = feature_lookup(neural_energies).tolist() if np.isfinite(neural_energies).all() else None
        report["qc_passed"] = not report["failures"] and len(report["entries"]) == 99
        report["status"] = "passed" if report["qc_passed"] else "quality_gate_failed"
    except TimeoutError as exc:
        report["status"] = "runtime_budget_failed"
        report["failures"].append(str(exc))
    finally:
        report["elapsed_seconds"] = time.perf_counter() - start
        _write_json(output_dir / "report.json", report)
        _write_json(output_dir / "bank.json", report)
    return report


def _validate_state_archive(saved, H, basis, digest, gates):
    """Bind saved weights, amplitudes and complete eigenspace to the same H."""
    errors = []
    shapes = {"embedding": (8, 16), "embedding_bias": (16,), "query": (16, 16),
              "key": (16, 16), "value": (16, 16), "projection": (16, 16),
              "projection_bias": (16,), "head": (16,), "head_bias": ()}
    expected = {f"parameter_{name}" for name in shapes}
    actual = {name for name in saved if name.startswith("parameter_")}
    if actual != expected:
        errors.append("saved parameter keys are missing or unknown")
    params = {}
    for name, shape in shapes.items():
        key = f"parameter_{name}"
        if key not in saved:
            continue
        value = np.asarray(saved[key])
        if value.shape != shape or not np.issubdtype(value.dtype, np.floating) or not np.isfinite(value).all():
            errors.append(f"saved parameter shape/dtype/value invalid: {name}")
        else:
            params[name] = value
    if not np.array_equal(H, saved["H"]) or not np.array_equal(basis, saved["basis"]):
        errors.append("Hamiltonian or basis differs")
    if str(saved["protocol_sha256"]) != digest:
        errors.append("state protocol SHA mismatch")
    eigenvalues, projector = exact_solution(H)
    if np.shape(saved["eigenvalues"]) != eigenvalues.shape or not np.allclose(saved["eigenvalues"], eigenvalues, rtol=0, atol=1e-10):
        errors.append("saved complete eigenvalues differ")
    if np.shape(saved["ground_projector"]) != projector.shape or not np.allclose(saved["ground_projector"], projector, rtol=0, atol=1e-9):
        errors.append("saved ground-space projector differs")
    psi = np.asarray(saved["psi"], dtype=np.float64)
    if psi.shape != (len(basis),):
        errors.append("saved wavefunction shape differs")
        return None, float(eigenvalues[0]), errors
    qc = quality_metrics(H, psi, eigenvalues=eigenvalues, projector=projector, gates=gates)
    if not errors:
        regenerated = np.asarray(wavefunction(params, configurations(basis)), dtype=np.float64)
        old_norm, new_norm = np.linalg.norm(psi), np.linalg.norm(regenerated)
        if old_norm == 0 or new_norm == 0 or not np.isfinite(regenerated).all():
            errors.append("saved parameters reconstruct a zero or nonfinite state")
        elif not np.allclose(psi / old_norm, regenerated / new_norm, rtol=1e-9, atol=1e-10):
            errors.append("saved parameters do not reconstruct normalized saved psi")
    return qc, float(eigenvalues[0]), errors


def _energy_binding_errors(neural_energy, exact_energy, qc, exact_ground_energy):
    errors = []
    if qc is None or "energy" not in qc or not math.isclose(float(neural_energy), qc["energy"], abs_tol=1e-10, rel_tol=0):
        errors.append("neural energy bank differs from recomputed selected psi")
    if not math.isclose(float(exact_energy), exact_ground_energy, abs_tol=1e-10, rel_tol=0):
        errors.append("exact energy bank differs from recomputed ED ground energy")
    return errors


def _selection_errors(expected_seeds, validated, selected_seed, selected_artifact, selected_energy):
    errors = []
    observed = [record["seed"] for record in validated]
    if len(observed) != len(expected_seeds) or set(observed) != set(expected_seeds):
        errors.append("seed artifacts do not match the exact frozen seed set")
    finite = [record for record in validated if np.isfinite(record["energy"])]
    chosen = [record for record in finite if record["seed"] == selected_seed]
    if len(chosen) != 1:
        errors.append("selected seed does not identify one validated finite artifact")
        return errors
    chosen = chosen[0]
    if chosen["artifact"] != selected_artifact:
        errors.append("selected artifact differs from the selected seed artifact")
    if not math.isclose(chosen["energy"], selected_energy, abs_tol=1e-10, rel_tol=0):
        errors.append("selected entry energy differs from its seed state")
    # This tolerance only covers verification roundoff, never the physical QC gates.
    if not finite or chosen["energy"] > min(record["energy"] for record in finite) + 1e-10:
        errors.append("selected seed is not the minimum finite-energy seed")
    return errors


def check_bank(output_dir, protocol_path):
    """Check the protocol, every fixed seed, selected states and complete lookup."""
    output_dir, protocol_path = Path(output_dir), Path(protocol_path)
    errors = []
    digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if digest not in KNOWN_PROTOCOL_SHA256:
        errors.append("protocol bytes differ from frozen protocol")
    try:
        report = json.loads((output_dir / "bank.json").read_text(encoding="utf-8"))
        protocol = json.loads(protocol_path.read_bytes())
        if report.get("protocol_sha256") != digest:
            errors.append("bank protocol SHA mismatch")
        if report.get("status") != "passed" or not report.get("qc_passed") or report.get("failures"):
            errors.append("bank did not pass all frozen quality gates")
        if report.get("motif_masks") != canonical_graphs() or len(report.get("entries", [])) != 99:
            errors.append("bank does not contain all99 expected Hamiltonians")
        if report.get("feature_names") != FEATURE_NAMES:
            errors.append("bank feature names differ from the frozen fourteen observables")
        energies_valid = False
        with np.load(output_dir / "energies.npz", allow_pickle=False) as saved:
            exact = saved["exact"]
            neural = saved["neural"]
            if exact.shape != (11, 3, 3) or neural.shape != (11, 3, 3):
                errors.append("invalid energy array shape")
            elif not np.isfinite(exact).all() or not np.isfinite(neural).all():
                errors.append("nonfinite bank energies")
            else:
                energies_valid = True
                if not np.array_equal(saved["motif_masks"], canonical_graphs()) or not np.array_equal(saved["U"], U_VALUES) or not np.array_equal(saved["sectors"], SECTORS):
                    errors.append("energy array axes differ from the canonical Hamiltonian registry")
                if not np.allclose(feature_lookup(exact), report["exact_features"], rtol=0, atol=1e-12):
                    errors.append("exact feature lookup differs from energy bank")
                if not np.allclose(feature_lookup(neural), report["neural_features"], rtol=0, atol=1e-12):
                    errors.append("neural feature lookup differs from its own energy bank")
        observed_keys = set()
        for entry in report.get("entries", []):
            key = (entry["graph_mask"], entry["U"], entry["nup"], entry["ndown"])
            observed_keys.add(key)
            H, basis = build_hamiltonian(entry["graph_mask"], entry["U"], entry["nup"], entry["ndown"])
            validated = []
            for record in entry["seeds"]:
                relative = Path(record["artifact"])
                expected_name = f"g{entry['graph_mask']:02d}_u{int(entry['U'])}_n{entry['nup']}{entry['ndown']}_seed{record['seed']}.npz"
                if relative.is_absolute() or ".." in relative.parts or relative.parts != ("cases", expected_name):
                    errors.append(f"unsafe or seed-inconsistent artifact path: {relative}")
                    continue
                with np.load(output_dir / relative, allow_pickle=False) as saved:
                    qc, exact_ground, state_errors = _validate_state_archive(saved, H, basis, digest, protocol["solver"]["quality_gate"])
                    errors.extend(f"{error}: {key},seed{record['seed']}" for error in state_errors)
                    if qc is None or "energy" not in qc:
                        errors.append(f"seed state has no verifiable finite energy: {key},seed{record['seed']}")
                        continue
                    if not math.isclose(qc["energy"], record["qc"]["energy"], abs_tol=1e-10, rel_tol=0):
                        errors.append(f"seed record energy differs from reconstructed state: {key},seed{record['seed']}")
                    if record["qc"].get("passed") != qc["passed"]:
                        errors.append(f"seed record QC flag differs: {key},seed{record['seed']}")
                    trace_steps = np.arange(0, protocol["solver"]["steps"] + 1, 10)
                    trace = np.asarray(saved["energy_trace"])
                    if not np.array_equal(saved["trace_steps"], trace_steps) or trace.shape != trace_steps.shape or not np.isfinite(trace).all():
                        errors.append(f"seed training trace is incomplete or nonfinite: {key},seed{record['seed']}")
                    elif not math.isclose(float(trace[-1]), qc["energy"], abs_tol=1e-10, rel_tol=0):
                        errors.append(f"final trace energy differs from saved state: {key},seed{record['seed']}")
                    validated.append({"seed": record["seed"], "energy": qc["energy"], "qc": qc,
                                      "artifact": record["artifact"], "exact_ground": exact_ground})
            errors.extend(f"{error}: {key}" for error in _selection_errors(
                protocol["solver"]["initialization_seeds"], validated,
                entry["selected_seed"], entry["artifact"], entry["qc"]["energy"]))
            selected = [record for record in validated if record["seed"] == entry["selected_seed"]]
            if len(selected) == 1:
                qc = selected[0]["qc"]
                if not qc["passed"]:
                    errors.append(f"recomputed selected QC failed: {key}")
                if energies_valid:
                    index = (canonical_graphs().index(entry["graph_mask"]), U_VALUES.index(entry["U"]), SECTORS.index((entry["nup"], entry["ndown"])))
                    errors.extend(f"{error}: {key}" for error in _energy_binding_errors(neural[index], exact[index], qc, selected[0]["exact_ground"]))
        expected = {(mask, U, *sector) for mask in canonical_graphs() for U in U_VALUES for sector in SECTORS}
        if observed_keys != expected:
            errors.append("missing or unexpected Hamiltonian keys")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"bank verification error: {exc}")
    return {"passed": not errors, "protocol_sha256": digest, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bank", action="store_true", help="Run the complete frozen bank (default).")
    parser.add_argument("--check-bank", type=Path, help="Verify an existing complete bank without fitting.")
    parser.add_argument("--pilot-only", action="store_true")
    args = parser.parse_args()
    if args.check_bank is not None:
        checked = check_bank(args.check_bank, args.protocol)
        print(json.dumps(checked, indent=2))
        return 0 if checked["passed"] else 1
    if args.output_dir is None:
        parser.error("--output-dir is required when running the solver")
    report = run_bank(args.output_dir, args.protocol, smoke=args.pilot_only)
    print(json.dumps({key: report[key] for key in ("status", "qc_passed", "elapsed_seconds", "failures")}, indent=2))
    return 0 if report["qc_passed"] or report["status"] == "pilot_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
