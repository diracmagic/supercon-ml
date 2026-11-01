"""Small, explicit normal-state response maps; no experiments or SC rewards.

Only ``feedback.legal_precursor_export`` supplies observations. A fit has one
caller-selected series (or, without a series, one physical sample), phase,
quantity and exact response unit. The five coordinate names have fixed units:
K, GPa, fraction, dimensionless strain, and T. Units are never inferred/converted.

``fit_response(events, as_of=..., group=..., axes=..., bounds=...)`` returns a
ResponseFit with a JSON-compatible audit and a private in-memory GP. ``predict``
and ``suggest_next_points`` do not append evidence, execute experiments, learn
Tc, or change any released model. A group is e.g. {"sample_id": "sample-A",
"phase": "phase-A", "quantity": "resistivity", "unit": "microohm cm"}.
An explicitly recorded series_id can replace sample_id, never be inferred from
composition. Unselected coordinates must be constant, or be explicitly fixed by
the caller to select a slice. Incompatible methods are not silently combined.

    python ml/parameter_space.py --audit [--ledger ledger.jsonl] [--as-of ISO8601]

The CLI is read-only and fits no models; absent measurements are reported as zero.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF

try:
    from . import feedback as F
except ImportError:
    import feedback as F


VERSION = 'normal-response-gp-v1'
AXIS_UNITS = dict(zip(F.COORDINATES, ('K', 'GPa', 'fraction', 'dimensionless', 'T')))
LIMITATION = ('Maps normal-state responses only; without validated superconducting phase-boundary data, '
              'this does not demonstrate movement toward superconductivity. No predicted Tc or model '
              'score is a measured reward. GP uncertainty is conditional on this kernel and noise '
              'assumptions, not a calibrated confidence interval.')
NUMERICAL_JITTER = 1e-8


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _coordinate(axis, value):
    if axis not in AXIS_UNITS or not _finite(value):
        return False
    if axis == 'temperature_k':
        return value > 0
    if axis == 'doping_fraction':
        return 0 <= value <= 1
    return axis == 'strain' or value >= 0


def _sc_quantity(quantity):
    name = re.sub('[^a-z0-9]', '', quantity.lower())
    return (name in {'tc', 'tck', 'tconset', 'tczero', 'criticaltemperature', 'transitiontemperature',
                     'criticalcurrent', 'criticalfield', 'uppercriticalfield', 'lowercriticalfield',
                     'shieldingfraction', 'scfraction', 'scvolumefraction', 'superfluiddensity', 'condensatedensity'} or
            name.startswith(('criticaltemperature', 'transitiontemperature', 'tconset', 'tczero',
                             'uppercriticalfield', 'lowercriticalfield', 'criticalcurrent', 'criticalfield',
                             'shieldingfraction', 'superfluiddensity', 'condensatedensity', 'diamagneticonset')) or
            any(part in name for part in ('superconduct', 'meissner', 'zeroresistan', 'heatcapacityjump', 'tcrelative')))


def _group_of(row):
    series = row.get('series_id')
    identity = {'series_id': series} if _text(series) else {'sample_id': row['sample_id']}
    return dict(identity, phase=row['phase'], quantity=row['quantity'], unit=row['unit'])


def _group_key(group):
    return json.dumps(group, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _validated_request(group, axes, bounds, fixed):
    _require(isinstance(group, dict), 'group must be explicit')
    identities = [key for key in ('series_id', 'sample_id') if key in group]
    _require(len(identities) == 1 and set(group) == {identities[0], 'phase', 'quantity', 'unit'},
             'group needs exactly series_id OR sample_id, plus phase, quantity, unit')
    _require(all(_text(value) for value in group.values()), 'group values must be known nonempty text')
    _require(not _sc_quantity(group['quantity']), 'superconductivity criteria and Tc cannot be mapped as precursor inputs')
    _require(isinstance(axes, (list, tuple)) and 1 <= len(axes) <= len(AXIS_UNITS) and
             all(axis in AXIS_UNITS for axis in axes) and len(set(axes)) == len(axes),
             'axes must be distinct normal-state coordinate names')
    _require(isinstance(bounds, dict) and set(bounds) == set(axes), 'bounds must explicitly cover every selected axis only')
    for axis in axes:
        pair = bounds[axis]
        _require(isinstance(pair, (list, tuple)) and len(pair) == 2 and
                 all(_coordinate(axis, value) for value in pair) and pair[0] < pair[1] and math.isfinite(pair[1]-pair[0]),
                 f'invalid explicit bounds for {axis}')
    _require(isinstance(fixed, dict) and all(key in AXIS_UNITS and key not in axes and _coordinate(key, value)
                                           for key, value in fixed.items()),
             'fixed coordinates must be known, valid unselected axes')


@dataclass
class ResponseFit:
    status: str
    audit: dict
    _gp: GaussianProcessRegressor | None = field(default=None, repr=False)
    _x: np.ndarray | None = field(default=None, repr=False)
    _low: np.ndarray | None = field(default=None, repr=False)
    _span: np.ndarray | None = field(default=None, repr=False)
    _response_mean: float = field(default=0, repr=False)
    _response_scale: float = field(default=1, repr=False)
    _hull_equations: np.ndarray | None = field(default=None, repr=False)


def fit_response(events, *, as_of, group, axes, bounds, fixed_coordinates=None, max_points=512):
    """Fit one measured response; insufficient data produce no surrogate curve.

    Requires >=max(4, 2*d+1) unique points and full centered coordinate rank. An
    explicit series permits pooling its identified samples, not arbitrary samples
    sharing a formula. Replicates at identical coordinates are averaged, with
    observed replicate variance retained in the GP diagonal and in the audit.
    """
    _require(fixed_coordinates is None or isinstance(fixed_coordinates, dict), 'fixed_coordinates must be an explicit mapping')
    fixed = {} if fixed_coordinates is None else dict(fixed_coordinates)
    _validated_request(group, axes, bounds, fixed)
    _require(type(max_points) is int and max_points > 0, 'max_points must be a positive integer')
    exported = F.legal_precursor_export(events, as_of=as_of)  # verifies chain, windows, source and time
    axes = tuple(axes)
    low = np.array([bounds[axis][0] for axis in axes], float)
    span = np.array([bounds[axis][1]-bounds[axis][0] for axis in axes], float)
    audit = {'version': VERSION, 'as_of': as_of, 'group': dict(group), 'axes': list(axes),
             'axis_units': {axis: AXIS_UNITS[axis] for axis in axes},
             'bounds': {axis: list(bounds[axis]) for axis in axes},
             'eligible_normal_measurements': len(exported['accepted']), 'excluded_by_eligibility': exported['excluded'],
             'excluded_by_slice': [], 'minimum_unique_points': max(4, 2*len(axes)+1),
             'training_event_hashes': [], 'training_points': [], 'fixed_coordinates': {},
             'automatic_retraining': False, 'experiments_executed': 0, 'limitation': LIMITATION}

    def stopped(status, reason):
        audit.update(status=status, reason=reason)
        return ResponseFit(status=status, audit=audit, _low=low, _span=span)

    rows = []
    for row in exported['accepted']:
        if _group_of(row) != group:
            continue
        coordinate = row['coordinates']
        reason = None
        if any(coordinate.get(axis) is None for axis in axes):
            reason = 'selected axis value missing; never filled with zero'
        elif any(coordinate[axis] < bounds[axis][0] or coordinate[axis] > bounds[axis][1] for axis in axes):
            reason = 'observation outside explicit operator bounds'
        elif any(coordinate[key] != value for key, value in fixed.items()):
            reason = 'observation outside explicitly fixed coordinate slice'
        if reason:
            audit['excluded_by_slice'].append({'observation_hash': row['observation_hash'], 'reason': reason})
        else:
            rows.append(row)
    audit['selected_measurements'] = len(rows)
    if not rows:
        return stopped('insufficient_data', 'no eligible measured points in this exact group and slice')
    if 'sample_id' in group and len({row['material_id'] for row in rows}) != 1:
        return stopped('insufficient_data', 'sample identity maps to multiple material IDs; explicit adjudication required')
    methods = {row['conditions']['method'] for row in rows}
    if len(methods) != 1 or len({row['conditions']['sample_form'] for row in rows}) != 1:
        return stopped('insufficient_data', 'measurement methods or sample forms differ; do not silently pool')
    for axis in AXIS_UNITS:
        if axis in axes:
            continue
        values = {row['coordinates'][axis] for row in rows}
        if len(values) != 1 or None in values:
            return stopped('insufficient_data', f'unselected {axis} varies or is unknown; select this axis or fix an explicit slice')
        fixed[axis] = values.pop()
    audit.update(fixed_coordinates=fixed, method=next(iter(methods)),
                 sample_ids=sorted({row['sample_id'] for row in rows}),
                 material_ids=sorted({row['material_id'] for row in rows}))
    buckets = {}
    for row in rows:
        buckets.setdefault(tuple(float(row['coordinates'][axis]) for axis in axes), []).append(row)
    n = len(buckets)
    audit['unique_points'] = n
    if n < audit['minimum_unique_points']:
        return stopped('insufficient_data', 'too few unique measured parameter points')
    if n > max_points:
        return stopped('budget_exceeded', 'unique-point budget exceeded; no silent subsampling')
    points = sorted(buckets)
    x = (np.asarray(points)-low) / span
    singular = np.linalg.svd(x-x.mean(axis=0), compute_uv=False)
    rank = int((singular > 1e-10).sum())
    audit.update(centered_axis_rank=rank, normalized_axis_singular_values=singular.tolist(),
                 rank_tolerance_in_bound_normalized_coordinates=1e-10)
    if rank != len(axes):
        return stopped('insufficient_data', 'selected axes are rank deficient; no surface away from the measured subspace')
    responses, variances = [], []
    for point in points:
        records = buckets[point]
        values = np.array([row['value'] for row in records], float)
        with np.errstate(over='ignore', invalid='ignore'):
            mean = float(values.mean())
            variance = float(values.var(ddof=1)) if len(values) > 1 else 0.0
        if not math.isfinite(mean) or not math.isfinite(variance):
            return stopped('fit_failed', 'response aggregation overflow; no nonfinite curve returned')
        responses.append(mean)
        variances.append(variance/len(values))
        audit['training_points'].append({'coordinates': dict(zip(axes, point)), 'mean': responses[-1],
                                         'replicates': len(records), 'replicate_variance': variance,
                                         'event_hashes': [row['observation_hash'] for row in records],
                                         'sources': [row['reference'] for row in records]})
    hashes = [row['observation_hash'] for row in rows]
    audit['training_event_hashes'] = hashes
    y = np.asarray(responses)
    magnitude = float(np.abs(y).max()) or 1.0
    ymean, yscale = float((y/magnitude).mean()*magnitude), float((y/magnitude).std()*magnitude)
    constant = yscale == 0
    if constant:
        yscale = abs(ymean) or 1.0
    normalized = (y-ymean)/yscale
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        alpha = np.asarray(variances)/yscale/yscale + NUMERICAL_JITTER
    if not np.isfinite(normalized).all() or not np.isfinite(alpha).all():
        return stopped('fit_failed', 'response/noise normalization overflow; no nonfinite curve returned')
    kernel = ConstantKernel(1.0, constant_value_bounds='fixed') * RBF(np.full(len(axes), .35), length_scale_bounds='fixed')
    gp = GaussianProcessRegressor(kernel=kernel, alpha=alpha, optimizer=None, normalize_y=False)
    try:
        gp.fit(x, normalized)
    except (ValueError, np.linalg.LinAlgError) as error:
        return stopped('fit_failed', f'GP numerical fit failed: {error}')
    hull = None
    if len(axes) > 1:
        from scipy.spatial import ConvexHull, QhullError
        try:
            hull = ConvexHull(x).equations
        except QhullError:
            audit['convex_hull_warning'] = 'Numerical hull unavailable; axis-range coverage alone is incomplete.'
    audit.update(status='ok', response_normalization={'mean': ymean, 'scale': yscale, 'constant_response': constant},
                 kernel=str(gp.kernel_), observed_ranges={axis: [min(p[k] for p in points), max(p[k] for p in points)]
                                                         for k, axis in enumerate(axes)},
                 numerical_jitter_in_normalized_variance=NUMERICAL_JITTER,
                 noise_assumption='Replicate variance/n when available, plus numerical jitter; single-point measurement error is unknown.',
                 uncertainty='Latent-response posterior standard deviation, conditional on a fixed unit-scale RBF kernel; not validated coverage.')
    return ResponseFit('ok', audit, gp, x, low, span, ymean, yscale, hull)


def _query(fit, coordinates):
    axes = fit.audit['axes']
    if not isinstance(coordinates, dict) or any(key not in AXIS_UNITS for key in coordinates):
        return None, 'invalid_coordinates'
    if any(axis not in coordinates or coordinates[axis] is None for axis in axes):
        return None, 'missing_axis'
    if any(not _coordinate(key, value) for key, value in coordinates.items()):
        return None, 'invalid_coordinates'
    if any(key not in axes and value != fit.audit['fixed_coordinates'].get(key) for key, value in coordinates.items()):
        return None, 'outside_fixed_context'
    if any(not fit.audit['bounds'][axis][0] <= coordinates[axis] <= fit.audit['bounds'][axis][1] for axis in axes):
        return None, 'outside_bounds'
    return (np.array([coordinates[axis] for axis in axes])-fit._low)/fit._span, 'ok'


def predict(fit, points):
    """No value outside explicit bounds; flag axis-range and convex-hull extrapolation."""
    _require(isinstance(fit, ResponseFit), 'fit must be a ResponseFit')
    _require(isinstance(points, (list, tuple)) and len(points) <= 4096, 'provide at most 4096 query points')
    result = {'status': 'ok' if fit.status == 'ok' else 'not_fitted', 'model_status': fit.status,
              'unit': fit.audit['group']['unit'], 'as_of': fit.audit['as_of'],
              'training_event_hashes': fit.audit['training_event_hashes'], 'rows': [], 'limitation': LIMITATION}
    for coordinates in points:
        row = {'coordinates': coordinates}
        if fit.status != 'ok':
            row['status'] = 'not_fitted'
        else:
            x, status = _query(fit, coordinates)
            row['status'] = status
            if status == 'ok':
                mean, std = fit._gp.predict(x[None, :], return_std=True)
                outside_axes = [axis for axis in fit.audit['axes']
                                if not fit.audit['observed_ranges'][axis][0] <= coordinates[axis] <= fit.audit['observed_ranges'][axis][1]]
                # A rectangle can hide holes in multi-axis coverage. Report the
                # observed convex hull too; being inside still proves no physics.
                if len(fit.audit['axes']) == 1:
                    outside_hull = bool(outside_axes)
                else:
                    outside_hull = (bool(np.any(fit._hull_equations[:, :-1] @ x + fit._hull_equations[:, -1] > 1e-10))
                                    if fit._hull_equations is not None else None)
                row.update(coordinates=dict(fit.audit['fixed_coordinates'], **coordinates),
                           predicted_response=float(mean[0]*fit._response_scale+fit._response_mean),
                           posterior_std=float(std[0]*fit._response_scale), normalized_std=float(std[0]),
                           extrapolates_observed_range=bool(outside_axes), outside_observed_axes=outside_axes,
                           outside_observed_convex_hull=outside_hull,
                           coverage_distance=float(np.linalg.norm(fit._x-x, axis=1).min()/math.sqrt(len(x))))
        result['rows'].append(row)
    return result


def suggest_next_points(fit, candidates, *, budget, cost_unit, max_points=1):
    """Rank explicit feasible points by normalized uncertainty/coverage per cost.

    Costs and total budget share the caller's cost_unit. This is a transparent
    acquisition heuristic, not physical reward or an entropy/RL guarantee. No
    response-value maximization or implicit candidate grid is used.
    """
    _require(_finite(budget) and budget >= 0 and _text(cost_unit), 'known nonnegative budget and explicit cost_unit required')
    _require(type(max_points) is int and max_points >= 0, 'max_points must be a nonnegative integer')
    _require(isinstance(candidates, (list, tuple)) and len(candidates) <= 4096, 'provide at most 4096 candidates')
    report = {'status': 'ok' if fit.status == 'ok' else 'not_fitted', 'selected': [], 'excluded': [],
              'budget': budget, 'cost_unit': cost_unit, 'spent': 0.0, 'experiments_executed': 0,
              'training_event_hashes': fit.audit['training_event_hashes'], 'limitation': LIMITATION,
              'policy': 'normalized latent posterior std * (1 + nearest normalized coverage distance) / external cost'}
    if fit.status != 'ok':
        return report
    pending = {}
    for index, candidate in enumerate(candidates):
        reason = None
        if not isinstance(candidate, dict) or not _finite(candidate.get('cost')) or candidate['cost'] <= 0:
            reason = 'missing_or_invalid_external_cost'
        elif candidate.get('cost_unit', cost_unit) != cost_unit:
            reason = 'incompatible_cost_unit'
        else:
            row = predict(fit, [candidate.get('coordinates')])['rows'][0]
            if row['status'] != 'ok':
                reason = row['status']
            elif row['coverage_distance'] <= 1e-12:
                reason = 'already_observed_point'
            else:
                x, _ = _query(fit, candidate['coordinates'])
                key = tuple(float(value) for value in x)
                old = pending.get(key)
                if old is not None and old['cost'] <= candidate['cost']:
                    reason = 'duplicate_candidate'
                else:
                    if old is not None:
                        report['excluded'].append({'index': old['index'], 'reason': 'duplicate_candidate'})
                    pending[key] = dict(row, index=index, candidate_id=candidate.get('candidate_id'), cost=candidate['cost'], _x=x)
        if reason:
            report['excluded'].append({'index': index, 'reason': reason})
    covered = list(fit._x)
    while pending and len(report['selected']) < max_points:
        available = []
        for key, row in pending.items():
            if row['cost'] + report['spent'] > budget:
                continue
            coverage = min(float(np.linalg.norm(x-row['_x'])/math.sqrt(len(row['_x']))) for x in covered)
            gain = row['normalized_std']*(1+coverage)
            available.append((gain/row['cost'], -row['index'], key, gain, coverage))
        if not available:
            break
        score, _, key, gain, coverage = max(available)
        row = pending.pop(key)
        covered.append(row.pop('_x'))
        row.update(acquisition_score=score, uncertainty_coverage_proxy=gain, batch_coverage_distance=coverage, cost_unit=cost_unit)
        report['selected'].append(row)
        report['spent'] += row['cost']
    report['excluded'].extend({'index': row['index'], 'reason': 'budget_or_batch_limit'} for row in pending.values())
    return report


def audit_data(events, *, as_of):
    exported = F.legal_precursor_export(events, as_of=as_of)
    groups, excluded_quantities = {}, []
    for row in exported['accepted']:
        if _sc_quantity(row['quantity']):
            excluded_quantities.append(row['observation_hash'])
            continue
        group = _group_of(row)
        item = groups.setdefault(_group_key(group), {'group': group, 'measurements': 0})
        item['measurements'] += 1
    return {'valid': True, 'version': VERSION, 'as_of': as_of, 'ledger_events': len(events),
            'eligible_normal_measurements': sum(item['measurements'] for item in groups.values()),
            'excluded_by_eligibility': len(exported['excluded']), 'excluded_sc_criteria': excluded_quantities,
            'groups': [groups[key] for key in sorted(groups)], 'models_fitted': 0,
            'experiments_executed': 0, 'automatic_retraining': False, 'limitation': LIMITATION}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', action='store_true', required=True)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--expected-head')
    parser.add_argument('--as-of', default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args(argv)
    try:
        exists = args.ledger is not None and args.ledger.is_file()
        if args.expected_head is not None and not exists:
            raise ValueError('a pinned expected_head requires an existing ledger')
        events = F.read_events(args.ledger, expected_head=args.expected_head) if exists else []
        report = audit_data(events, as_of=args.as_of)
        report.update(exists=exists, ledger=str(args.ledger) if args.ledger is not None else None)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
