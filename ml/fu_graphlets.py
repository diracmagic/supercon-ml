"""Frozen, label-free crystal graphlets for the Fu lattice research pilot.

This mapping uses actual periodic atom coordinates, not D/geometry summaries.
Every atom is a center; all choices tied at the third-neighbor distance receive
equal weight.  A missing center makes the material descriptor unknown rather
than silently changing its atom population.  Species do not set model hopping,
onsite energies, filling, or interactions.  The resulting uniform-hopping,
fixed-U Hubbard clusters are structural surrogates, not material Hamiltonians.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations, permutations
import math
from collections.abc import Mapping

from ase import Atoms
from ase.data import atomic_numbers
from ase.neighborlist import neighbor_list
import numpy as np


MAPPING_VERSION = "fu-lattice-graphlets-v1"
RADIUS_ANGSTROM = 8.0
TIE_TOLERANCE_ANGSTROM = 1e-8
MAX_TIE_COMBINATIONS = 256
NEIGHBOR_EDGE_FACTOR = 1.15
EDGE_ORDER = tuple(combinations(range(4), 2))
_EDGE_INDEX = {edge: i for i, edge in enumerate(EDGE_ORDER)}
_PERMUTATIONS = tuple(permutations(range(4)))
COVERAGE_NAMES = ("structure_mapped", "center_coverage_fraction")
ENERGY_FEATURE_NAMES = tuple(
    f"fu_u{u}_{name}"
    for u in (4, 8)
    for name in (
        "energy_n2_per_site", "energy_n3_per_site", "energy_n4_per_site",
        "correlation_n2_per_site", "correlation_n3_per_site",
        "correlation_n4_per_site", "curvature_per_site",
    )
)


def canonical_mask(mask: int) -> int:
    """Minimum six-edge bitmask over all 24 vertex permutations.

    Bit order is (01,02,03,12,13,23), shared with the independent solver bank.
    Disconnected graphs remain in the registry even though a forced central
    star means the crystal mapping itself produces only four graph classes.
    """
    if isinstance(mask, (bool, np.bool_)) or not isinstance(mask, (int, np.integer)) or not 0 <= mask < 64:
        raise ValueError("a four-site simple graph mask must be an integer in [0,63]")
    edges = [edge for bit, edge in enumerate(EDGE_ORDER) if (int(mask) >> bit) & 1]
    return min(
        sum(1 << _EDGE_INDEX[tuple(sorted((perm[i], perm[j])))] for i, j in edges)
        for perm in _PERMUTATIONS
    )


GRAPH_MASKS = tuple(sorted({canonical_mask(mask) for mask in range(64)}))
_GRAPH_INDEX = {mask: index for index, mask in enumerate(GRAPH_MASKS)}
GRAPH_FEATURE_NAMES = tuple(f"fu_graph_mask_{mask:02d}_frequency" for mask in GRAPH_MASKS)


def _to_ase(atoms) -> Atoms:
    """Accept ASE Atoms, a JARVIS Atoms object, or its original atoms dict."""
    if isinstance(atoms, Atoms):
        crystal = atoms.copy()
        if not np.asarray(crystal.pbc, bool).all():
            raise ValueError("the frozen mapping requires three periodic directions")
        # ASE's CIF reader can retain fractional occupancy in info while putting
        # only the dominant species into Atoms.  Do not silently accept that
        # dominant-species projection as an ordered original structure.
        occupancy = crystal.info.get("occupancy", {})
        if not isinstance(occupancy, Mapping) or any(
            not isinstance(site, Mapping) or len(site) != 1
            or any(not math.isfinite(float(value)) or float(value) != 1 for value in site.values())
            for site in occupancy.values()
        ):
            raise ValueError("partial/disordered CIF site occupancies")
    else:
        if not isinstance(atoms, Mapping) and callable(getattr(atoms, "to_dict", None)):
            atoms = atoms.to_dict()
        if not isinstance(atoms, Mapping):
            raise ValueError("actual ASE/JARVIS structure coordinates are required")
        if atoms.get("is_ordered") is False:
            raise ValueError("partially occupied/disordered sites cannot be arbitrarily ordered")
        elements = list(atoms.get("elements", []))
        coords = np.asarray(atoms.get("coords", []), dtype=float)
        cell = np.asarray(atoms.get("lattice_mat", []), dtype=float)
        if coords.shape != (len(elements), 3) or cell.shape != (3, 3):
            raise ValueError("expected lattice_mat[3,3], coords[N,3], elements[N]")
        if any(not isinstance(e, str) or e not in atomic_numbers or atomic_numbers[e] == 0 for e in elements):
            raise ValueError("unknown/dummy species in the original structure")
        if "occupancies" in atoms:
            occupancy = np.asarray(atoms["occupancies"], float)
            if occupancy.shape != (len(elements),) or not np.isfinite(occupancy).all() or not np.all(occupancy == 1):
                raise ValueError("partial or malformed site occupancies")
        cartesian = atoms.get("cartesian", False)
        if not isinstance(cartesian, (bool, np.bool_)):
            raise ValueError("cartesian must be a boolean")
        crystal = Atoms(symbols=elements, cell=cell, pbc=True,
                        **({"positions": coords} if cartesian else {"scaled_positions": coords}))
    if not len(crystal):
        raise ValueError("empty structures have no mapped centers")
    cell = np.asarray(crystal.cell, float)
    if not np.isfinite(cell).all() or not np.isfinite(crystal.positions).all():
        raise ValueError("nonfinite cell or atom coordinates")
    if cell.shape != (3, 3) or abs(float(np.linalg.det(cell))) <= np.finfo(float).tiny:
        raise ValueError("singular periodic cell")
    if not np.isfinite(np.linalg.cond(cell)) or np.linalg.cond(cell) > 1 / np.finfo(float).eps:
        raise ValueError("numerically singular periodic cell")
    if (crystal.numbers <= 0).any():
        raise ValueError("dummy species are not actual atom sites")
    # Wrapping changes image labels but not physical sites.  Do not round source
    # coordinates or substitute a template structure.
    crystal.set_scaled_positions(crystal.get_scaled_positions(wrap=True))
    return crystal


def _slack(length: float) -> float:
    """Floating roundoff allowance, not an additional geometric tie cutoff."""
    return 64 * np.finfo(float).eps * max(1.0, abs(float(length)))


def _center_graphlets(site_indices, shifts, vectors, distances, center):
    """Map one center, retaining (site index, integer image shift) identities."""
    diagnostic = {"center_index": int(center), "mapped": False,
                  "neighbors_in_radius": int(len(distances))}
    if len(distances) < 3:
        diagnostic.update(status="insufficient_neighbors", reason="fewer than three periodic neighbors within 8 Angstrom")
        return None, diagnostic
    if np.any(distances <= _slack(RADIUS_ANGSTROM)):
        diagnostic.update(status="coincident_sites", reason="distinct periodic sites have numerically zero separation")
        return None, diagnostic
    # Each site image is a separate orbital.  A repeated species/site index is
    # not a reason to discard its nonzero lattice translations.
    identities = [(int(j), tuple(int(x) for x in shift)) for j, shift in zip(site_indices, shifts)]
    if len(identities) != len(set(identities)):
        diagnostic.update(status="duplicate_image_identity", reason="neighbor list repeated an identical site image")
        return None, diagnostic
    third = float(np.partition(distances, 2)[2])
    strict = np.flatnonzero(distances < third - TIE_TOLERANCE_ANGSTROM)
    boundary = np.flatnonzero(np.abs(distances - third) <= TIE_TOLERANCE_ANGSTROM)
    needed = 3 - len(strict)
    count = math.comb(len(boundary), needed)
    diagnostic.update(third_neighbor_distance_angstrom=third,
                      strict_neighbors=int(len(strict)), tied_boundary_neighbors=int(len(boundary)),
                      tie_combination_count=int(count))
    if count > MAX_TIE_COMBINATIONS:
        diagnostic.update(status="tie_budget_exceeded", reason="all-tie average exceeds 256 combinations for this center")
        return None, diagnostic
    support = list(strict) + list(boundary)
    diagnostic["shell_image_identities"] = [
        {"site_index": identities[i][0], "shift": list(identities[i][1]),
         "distance_angstrom": float(distances[i])} for i in support
    ]
    histogram = Counter()
    for tied_choice in combinations(boundary.tolist(), needed):
        chosen = list(strict) + list(tied_choice)
        points = vectors[chosen]
        threshold = NEIGHBOR_EDGE_FACTOR * float(np.max(distances[chosen]))
        mask = 0b000111  # Center 0 is connected to vertices 1, 2 and 3.
        for i, j in combinations(range(3), 2):
            if np.linalg.norm(points[i] - points[j]) <= threshold + _slack(threshold):
                mask |= 1 << _EDGE_INDEX[(i + 1, j + 1)]
        histogram[canonical_mask(mask)] += 1
    frequency = np.zeros(len(GRAPH_MASKS), dtype=float)
    for mask, multiplicity in histogram.items():
        frequency[_GRAPH_INDEX[mask]] = multiplicity / count
    diagnostic.update(status="ok", mapped=True,
                      motif_counts={str(mask): int(n) for mask, n in sorted(histogram.items())})
    return frequency, diagnostic


def extract_graphlets(atoms) -> tuple[np.ndarray, dict]:
    """Return frequencies in GRAPH_MASKS order and complete mapping diagnostics.

    Fully mapped frequencies sum to one and average every center equally.
    Invalid or partially mapped structures return eleven NaNs.  Coverage flags
    distinguish missing structure/centers from physical zero motif frequency.
    """
    diagnostics = {"mapping_version": MAPPING_VERSION, "status": "invalid",
                   "structure_mapped": False, "n_sites": 0, "mapped_centers": 0,
                   "center_coverage_fraction": 0.0, "motif_masks": list(GRAPH_MASKS),
                   "radius_angstrom": RADIUS_ANGSTROM,
                   "tie_tolerance_angstrom": TIE_TOLERANCE_ANGSTROM,
                   "max_tie_combinations_per_center": MAX_TIE_COMBINATIONS,
                   "neighbor_edge_factor": NEIGHBOR_EDGE_FACTOR, "centers": []}
    missing = np.full(len(GRAPH_MASKS), np.nan)
    try:
        crystal = _to_ase(atoms)
        diagnostics["n_sites"] = len(crystal)
        first, second, shifts, vectors, distances = neighbor_list(
            "ijSDd", crystal, RADIUS_ANGSTROM + _slack(RADIUS_ANGSTROM),
            self_interaction=False,
        )
        within = distances <= RADIUS_ANGSTROM + _slack(RADIUS_ANGSTROM)
        first, second, shifts, vectors, distances = (
            array[within] for array in (first, second, shifts, vectors, distances)
        )
        rows = []
        for center in range(len(crystal)):
            selected = first == center
            row, detail = _center_graphlets(second[selected], shifts[selected],
                                            vectors[selected], distances[selected], center)
            diagnostics["centers"].append(detail)
            if row is not None:
                rows.append(row)
        diagnostics["mapped_centers"] = len(rows)
        diagnostics["center_coverage_fraction"] = len(rows) / len(crystal)
        diagnostics["structure_mapped"] = len(rows) == len(crystal)
        diagnostics["status"] = "ok" if diagnostics["structure_mapped"] else "unmapped_centers"
        if diagnostics["structure_mapped"]:
            return np.mean(rows, axis=0), diagnostics
        return missing, diagnostics
    except (ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as error:
        diagnostics.update(status="invalid", reason=str(error))
        return missing, diagnostics


def coverage_features(diagnostics: Mapping) -> np.ndarray:
    """Shared, explicit mapping flags; never an inferred electronic property."""
    return np.asarray([float(bool(diagnostics["structure_mapped"])),
                       float(diagnostics["center_coverage_fraction"])], dtype=float)


def aggregate_features(frequencies, bank_lookup) -> np.ndarray:
    """Frequency-weighted 14-feature solver lookup, without ED substitution.

    bank_lookup is an array of shape (11,14) in GRAPH_MASKS order, or a mapping
    from integer/string canonical masks to length-14 vectors.  The runner must
    separately require the neural bank's global QC pass before using it.
    """
    frequency = np.asarray(frequencies, dtype=float)
    if frequency.shape != (len(GRAPH_MASKS),):
        raise ValueError("expected eleven canonical graph frequencies")
    if np.isnan(frequency).any():
        return np.full(len(ENERGY_FEATURE_NAMES), np.nan)
    if not np.isfinite(frequency).all() or (frequency < 0).any() or not np.isclose(frequency.sum(), 1, atol=1e-12, rtol=0):
        raise ValueError("mapped graph frequencies must be finite, nonnegative and sum to one")
    if isinstance(bank_lookup, Mapping):
        rows = [bank_lookup[mask] if mask in bank_lookup else bank_lookup[str(mask)] for mask in GRAPH_MASKS]
        bank = np.asarray(rows, dtype=float)
    else:
        bank = np.asarray(bank_lookup, dtype=float)
    if bank.shape != (len(GRAPH_MASKS), len(ENERGY_FEATURE_NAMES)) or not np.isfinite(bank).all():
        raise ValueError("a complete finite 11x14 solver bank is required; no failed-entry fallback")
    return frequency @ bank
