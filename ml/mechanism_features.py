"""Small, label-free periodic geometry descriptors, not pairing mechanisms.

Input is the ordered original-CIF/JARVIS atoms dictionary used by H6/screen:
``lattice_mat`` contains lattice row vectors (Angstrom), ``coords`` contains
fractional coordinates unless ``cartesian=True``, and ``elements`` lists sites.
No Tc, family, oxidation-state guess, space-group label or element-specific
structural template is read. Covalent-radius contacts are only a geometric proxy;
ionic/metallic bonding and interactions beyond the chosen shell need not follow it.

ASE supplies periodic images, including nonzero-image self edges. A quotient
graph's integer cycle translations determine its periodic connectivity dimension;
cell aspect ratios and a minimum-image-only graph cannot do this reliably.
See https://docs.ase-lib.org/ase/neighborlist.html for ASE's shift-vector convention.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import ase
from ase import Atoms
from ase.data import atomic_numbers, covalent_radii
from ase.neighborlist import neighbor_list
import numpy as np

FEATURE_VERSION = 'periodic-local-geometry-v1'
FEATURE_RATIONALE = {
    'coordination_mean': 'Mean geometric-contact count per site, including distinct periodic images.',
    'coordination_std': 'Population spread of geometric-contact counts across sites.',
    'metal_ligand_coordination_mean': 'Mean nonmetal/metalloid-neighbor count over broadly classified metal centers; not a valence.',
    'metal_ligand_coordination_std': 'Population spread of the above counts; no metal centers means unknown.',
    'bond_length_mean_angstrom': 'Mean geometric-contact length in Angstrom; directed pairs have equal multiplicity.',
    'bond_length_cv': 'Global population standard deviation divided by mean contact length.',
    'local_planarity_mean': 'Mean (middle-smallest)/largest eigenvalue of the center-origin unit-bond second moment; CN>=3.',
    'local_planarity_std': 'Population spread of local planarity; linear coordination is not classified as planar.',
    'local_linearity_mean': 'Mean (largest-middle)/largest eigenvalue of the unit-bond second moment; CN>=2.',
    'local_linearity_std': 'Population spread of local linearity.',
    'tetrahedral_order_mean': 'Mean 1-(3/8)*sum((cos(angle)+1/3)^2) over all six neighbor pairs at exactly-four-contact sites.',
    'tetrahedral_order_std': 'Population spread of tetrahedral order; negative distorted values are not clipped.',
    'local_bond_length_cv_mean': 'Mean within-site contact-length CV over sites with at least two contacts.',
    'radius_normalized_length_mean': 'Mean d/(r_cov_i+r_cov_j), with the same tabulated radii on every dataset.',
    'radius_normalized_abs_deviation_mean': 'Mean absolute deviation of the above ratio from one; not measured strain.',
    'connectivity_0d_site_fraction': 'Site fraction in contact components with no periodic winding (including isolated sites).',
    'connectivity_1d_site_fraction': 'Site fraction in components with one independent integer winding direction.',
    'connectivity_2d_site_fraction': 'Site fraction in components with two independent integer winding directions; layered-contact proxy.',
    'connectivity_3d_site_fraction': 'Site fraction in components with three independent integer winding directions.',
}
FEATURE_NAMES = tuple(FEATURE_RATIONALE)
# A fixed, broad chemical partition, never a Cu/Fe/family template or oxidation
# assignment. Metalloids count as possible ligand sites; noble gases do not.
LIGAND_ELEMENTS = frozenset('H B C N O F Si P S Cl Ge As Se Br Sb Te I At Ts'.split())
NONMETAL_ELEMENTS = LIGAND_ELEMENTS | frozenset('He Ne Ar Kr Xe Rn Og'.split())
DISCLAIMER = ('Geometric proxies only: contacts, coordination shapes and winding dimension do not establish '
              'bond order, oxidation state, orbital energies, exchange interactions or a superconducting mechanism.')


@dataclass(frozen=True)
class GeometryConfig:
    cutoff_scale: float = 1.25
    sensitivity_fraction: float = 0.05
    max_atoms: int = 2048
    max_neighbor_edges: int = 500_000
    min_separation_angstrom: float = 1e-4

    def __post_init__(self):
        if not (math.isfinite(self.cutoff_scale) and self.cutoff_scale > 0):
            raise ValueError('cutoff_scale must be finite and positive')
        if not (0 < self.sensitivity_fraction < 0.5):
            raise ValueError('sensitivity_fraction must lie between zero and one half')
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
               for value in (self.max_atoms, self.max_neighbor_edges)):
            raise ValueError('geometry budgets must be positive integers')
        if not (math.isfinite(self.min_separation_angstrom) and self.min_separation_angstrom > 0):
            raise ValueError('geometry budgets and minimum separation must be positive')


class _StructureIssue(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _result(values, diagnostics):
    values = [float(value) for value in values]
    diagnostics.update(finite_features=sum(math.isfinite(value) for value in values),
                       missing_features=[name for name, value in zip(FEATURE_NAMES, values) if not math.isfinite(value)],
                       proxy_disclaimer=DISCLAIMER,
                       unavailable_properties={'oxidation_states': 'not inferred', 'orbital_energies': 'not measured or inferred'})
    return {'version': FEATURE_VERSION, 'names': list(FEATURE_NAMES), 'values': values,
            'features': dict(zip(FEATURE_NAMES, values)), 'diagnostics': diagnostics}


def _validated(atoms, config):
    if not isinstance(atoms, dict):
        raise _StructureIssue('invalid', 'atoms must be an ordered structure dictionary')
    try:
        cell = np.asarray(atoms['lattice_mat'], dtype=float)
        coords = np.asarray(atoms['coords'], dtype=float)
        elements = list(atoms['elements'])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise _StructureIssue('invalid', 'missing or malformed lattice, coordinates or elements') from error
    n = len(elements)
    if not n or cell.shape != (3, 3) or coords.shape != (n, 3):
        raise _StructureIssue('invalid', 'expected nonempty N sites, a 3x3 cell and Nx3 coordinates')
    if n > config.max_atoms:
        raise _StructureIssue('budget_exceeded', f'{n} sites exceeds max_atoms={config.max_atoms}')
    if not np.isfinite(cell).all() or not np.isfinite(coords).all():
        raise _StructureIssue('invalid', 'nonfinite lattice or coordinates')
    try:
        with np.errstate(over='ignore', invalid='ignore'):
            volume, condition = abs(float(np.linalg.det(cell))), float(np.linalg.cond(cell))
    except np.linalg.LinAlgError as error:
        raise _StructureIssue('invalid', 'periodic cell decomposition failed') from error
    if not math.isfinite(volume) or not math.isfinite(condition) or volume < 1e-8 or condition > 1e8:
        raise _StructureIssue('invalid', 'singular or numerically degenerate periodic cell')
    if any(not isinstance(e, str) or e not in atomic_numbers or atomic_numbers[e] == 0 for e in elements):
        raise _StructureIssue('invalid', 'unknown or dummy element; no species/radius substitution allowed')
    numbers = np.asarray([atomic_numbers[e] for e in elements])
    # ASE fills unreported radii beyond Cm with a common placeholder. Do not use
    # that placeholder as a measurement. H6 already rejects these elements.
    if (numbers > 96).any():
        raise _StructureIssue('unsupported', 'ASE covalent radii beyond Z=96 are placeholders, not supported measurements')
    if atoms.get('is_ordered') is False:
        raise _StructureIssue('invalid', 'disordered/partially occupied structure is not an ordered geometry')
    if 'occupancies' in atoms:
        try:
            occupancy = np.asarray(atoms['occupancies'], float)
            ordered = occupancy.shape == (n,) and np.isfinite(occupancy).all() and np.allclose(occupancy, 1, atol=1e-10, rtol=0)
        except (TypeError, ValueError, OverflowError):
            ordered = False
        if not ordered:
            raise _StructureIssue('invalid', 'partial or malformed occupancy; no arbitrary ordering allowed')
    cartesian = atoms.get('cartesian', False)
    if not isinstance(cartesian, (bool, np.bool_)):
        raise _StructureIssue('invalid', 'cartesian must be a boolean when present')
    fractional = coords @ np.linalg.inv(cell) if cartesian else coords
    if not np.isfinite(fractional).all():
        raise _StructureIssue('invalid', 'coordinate conversion overflowed the periodic cell')
    fractional = fractional % 1.0
    radii = np.asarray(covalent_radii[numbers], float)
    if not np.isfinite(radii).all() or (radii <= 0).any():
        raise _StructureIssue('unsupported', 'missing tabulated covalent radius')
    return Atoms(symbols=elements, scaled_positions=fractional, cell=cell, pbc=True), radii


def _integer_rank(vectors):
    """Rank of 3-D integer vectors, without floating tolerances or integer overflow."""
    basis = []
    cross = lambda a, b: (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    for vector in vectors:
        v = tuple(int(x) for x in vector)
        if not any(v):
            continue
        if not basis:
            basis.append(v)
        elif len(basis) == 1:
            if any(cross(basis[0], v)):
                basis.append(v)
        elif sum(x*y for x, y in zip(cross(*basis), v)):
            return 3
    return len(basis)


def _dimensions(n, first, second, shifts):
    graph = [[] for _ in range(n)]
    for i, j, shift in zip(first, second, shifts):
        graph[int(i)].append((int(j), tuple(int(x) for x in shift)))
    positions, dimensions, components = {}, np.zeros(n, int), []
    for start in range(n):
        if start in positions:
            continue
        positions[start] = (0, 0, 0)
        queue, sites, cycles = deque([start]), [], []
        while queue:
            i = queue.popleft()
            sites.append(i)
            for j, shift in graph[i]:
                proposed = tuple(a+b for a, b in zip(positions[i], shift))
                if j not in positions:
                    positions[j] = proposed
                    queue.append(j)
                else:
                    cycles.append(tuple(a-b for a, b in zip(proposed, positions[j])))
        dimension = _integer_rank(cycles)
        dimensions[sites] = dimension
        components.append({'sites': len(sites), 'periodic_dimension': dimension})
    return np.bincount(dimensions, minlength=4) / n, components


def _mean(values):
    return float(np.mean(values)) if len(values) else math.nan


def _std(values):
    return float(np.std(values)) if len(values) else math.nan


def _orders(vectors):
    """Center-origin unit-bond moments, not centered neighbor-endpoint PCA."""
    n = len(vectors)
    unit = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    eigenvalues = np.maximum(np.linalg.eigvalsh(unit.T @ unit / n), 0)
    small, middle, large = eigenvalues
    planarity = float((middle-small) / large) if n >= 3 else math.nan
    linearity = float((large-middle) / large) if n >= 2 else math.nan
    tetrahedral = math.nan
    if n == 4:
        cosines = (unit @ unit.T)[np.triu_indices(4, 1)]
        tetrahedral = float(1 - 3/8 * np.sum((np.clip(cosines, -1, 1) + 1/3)**2))
    return planarity, linearity, tetrahedral


def _calculate(crystal, radii, config):
    n = len(crystal)
    upper = config.cutoff_scale * (1 + config.sensitivity_fraction)
    radius = upper * float(radii.max()) * 2
    estimate = n*n / crystal.get_volume() * 4*math.pi*radius**3/3
    if estimate > 8*config.max_neighbor_edges:
        raise _StructureIssue('budget_exceeded', 'density/cutoff predicts an excessive periodic neighbor allocation')
    i, j, shifts, vectors, distances = neighbor_list('ijSDd', crystal, upper*radii,
                                                    self_interaction=False, max_nbins=200_000)
    if len(i) > config.max_neighbor_edges:
        raise _StructureIssue('budget_exceeded', 'periodic neighbor edge budget exceeded; no truncated shell returned')
    if len(i) and float(distances.min()) < config.min_separation_angstrom:
        raise _StructureIssue('invalid', 'overlapping or near-coincident sites/images')
    ratios = distances / (radii[i] + radii[j])
    keep = ratios <= config.cutoff_scale
    first, second, shift, vector, distance = i[keep], j[keep], shifts[keep], vectors[keep], distances[keep]
    degree = np.bincount(first, minlength=n)
    symbols = crystal.get_chemical_symbols()
    metals = np.asarray([e not in NONMETAL_ELEMENTS for e in symbols])
    ligand = np.asarray([e in LIGAND_ELEMENTS for e in symbols])
    ligand_degree = np.bincount(first[ligand[second]], minlength=n)[metals]
    planar, linear, tetra, radial = [], [], [], []
    ends = np.searchsorted(first, np.arange(n+1))  # ASE sorts by center index.
    for site in range(n):
        a, b = ends[site], ends[site+1]
        if a == b:
            continue
        p, l, t = _orders(vector[a:b])
        if math.isfinite(p):
            planar.append(p)
        if math.isfinite(l):
            linear.append(l)
            radial.append(float(np.std(distance[a:b]) / np.mean(distance[a:b])))
        if math.isfinite(t):
            tetra.append(t)
    fractions, components = _dimensions(n, first, second, shift)
    norm = ratios[keep]
    values = [_mean(degree), _std(degree), _mean(ligand_degree), _std(ligand_degree),
              _mean(distance), float(np.std(distance)/np.mean(distance)) if len(distance) else math.nan,
              _mean(planar), _std(planar), _mean(linear), _std(linear), _mean(tetra), _std(tetra),
              _mean(radial), _mean(norm), _mean(np.abs(norm-1)), *fractions]
    sensitivity = []
    for scale in [config.cutoff_scale*(1-config.sensitivity_fraction), config.cutoff_scale, upper]:
        chosen = ratios <= scale
        dimensions, _ = _dimensions(n, i[chosen], j[chosen], shifts[chosen])
        sensitivity.append({'cutoff_scale': scale, 'directed_edges': int(chosen.sum()),
                            'coordination_mean': float(chosen.sum()/n), 'dimension_site_fractions': dimensions.tolist()})
    near = np.abs(ratios-config.cutoff_scale) <= config.cutoff_scale*config.sensitivity_fraction
    return _result(values, {'status': 'ok', 'structure_valid': True, 'cached': False, 'n_sites': n,
                           'directed_contact_edges': len(first), 'isolated_sites': int((degree == 0).sum()),
                           'coverage': {'planarity_sites': len(planar), 'linearity_sites': len(linear),
                                        'four_contact_sites': len(tetra), 'metal_centers': int(metals.sum()),
                                        'ligand_sites': int(ligand.sum())},
                           'components': components, 'cutoff_sensitivity': sensitivity,
                           'dimensionality_changes_with_cutoff': any(not np.allclose(item['dimension_site_fractions'], fractions, atol=1e-12, rtol=0) for item in sensitivity),
                           'near_cutoff_fraction_of_searched_edges': float(near.mean()) if len(near) else 0.0})


def extract_features(atoms: dict, *, config: GeometryConfig | None = None, cache_dir: Path | str | None = None) -> dict:
    """Fixed 19-name vector plus coverage; NaN denotes unavailable, never imputed zero.

    Invalid/unsupported/budget-limited structures return all-NaN vectors and an
    explicit diagnostic status. Valid isolated sites remain 0D with unknown local
    shapes. Optional JSON caches use null for missing values and bind the complete
    geometry, feature version, parameters, ASE version and radii-table fingerprint.
    Equivalent cells may miss the cache, but must yield equivalent descriptors.
    """
    config = config or GeometryConfig()
    try:
        crystal, radii = _validated(atoms, config)
        generation = {'version': FEATURE_VERSION, 'settings': asdict(config), 'ase': ase.__version__,
                      'radii_sha256': _digest(np.asarray(covalent_radii).tolist())}
        key = _digest({'generation': generation, 'cell': crystal.cell.array.tolist(),
                       'fractional': crystal.get_scaled_positions().tolist(), 'elements': crystal.get_chemical_symbols()})
        cache = Path(cache_dir) / (key+'.json') if cache_dir is not None else None
        if cache is not None and cache.is_file():
            try:
                saved = json.loads(cache.read_text(encoding='utf-8'))
                values = saved['values']
                if saved['cache_key'] != key or saved['generation'] != generation or saved['names'] != list(FEATURE_NAMES) or len(values) != len(FEATURE_NAMES):
                    raise ValueError('cache identity/columns mismatch')
                if any(v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)) for v in values):
                    raise ValueError('invalid cached feature values')
                diagnostics = dict(saved['diagnostics'], cached=True, cache_key=key, generation=generation)
                return _result([math.nan if v is None else v for v in values], diagnostics)
            except (KeyError, TypeError, ValueError, OSError):
                pass  # A damaged/stale cache never supplies training features.
        result = _calculate(crystal, radii, config)
        result['diagnostics'].update(cache_key=key, generation=generation)
        if cache is not None:
            temporary = None
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                payload = {'cache_key': key, 'generation': generation, 'names': result['names'],
                           'values': [v if math.isfinite(v) else None for v in result['values']], 'diagnostics': result['diagnostics']}
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=cache.parent, prefix='.geometry-', suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(payload, handle, allow_nan=False)
                os.replace(temporary, cache)
            except OSError as error:
                result['diagnostics']['cache_warning'] = str(error)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return result
    except _StructureIssue as error:
        return _result([math.nan]*len(FEATURE_NAMES), {'status': error.status, 'structure_valid': False, 'reason': str(error), 'cached': False})
