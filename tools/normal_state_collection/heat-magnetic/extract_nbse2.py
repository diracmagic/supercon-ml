"""Exact numeric extraction of author-deposited data, with duplicate checks.

This script reads, but never modifies, the original workbook/archive. It does
not select a normal-state window or generate feedback/experimental labels.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import zipfile

import openpyxl

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw' / 'nbse2_2025'
OUT = ROOT / 'derived' / 'nbse2_2025'
OUT.mkdir(parents=True, exist_ok=True)


def digest(path):
    data = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
            'md5': hashlib.md5(data).hexdigest()}


def sheet_pairs(ws, column):
    out = []
    for row in range(3, ws.max_row + 1):
        x, y = ws.cell(row, column).value, ws.cell(row, column + 1).value
        if x is None and y is None:
            continue
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
            raise ValueError(f'Non-numeric pair {ws.title} row {row}')
        out.append((float(x), float(y), row))
    return out


workbook = openpyxl.load_workbook(RAW / 'Source data.xlsx', read_only=True, data_only=True)
series, points, duplicate_checks = [], [], []
with zipfile.ZipFile(RAW / 'Magnetization data.zip') as archive:
    for field in range(1, 8):
        name = f'Ba{field}T.DAT'
        original = archive.read(name)
        lines = [(i, line) for i, line in enumerate(original.decode('utf-8-sig').splitlines(), 1)
                 if line.strip()]
        if lines[1][1] != 'Time Stamp (sec),Temperature (K),Magnetic Field (Oe),Moment (emu)':
            raise ValueError(f'Unexpected header {name}')
        data = [(line_no, *map(float, next(csv.reader([line])))) for line_no, line in lines[2:]]
        s_id = f'nbse2_2025_fig1b_{field}T'
        xlsx = sheet_pairs(workbook['Fig.1b'], 1 + 3 * (field - 1))
        exact = [(r[2], r[4]) for r in data] == [(r[0], r[1]) for r in xlsx]
        if not exact:
            raise ValueError(f'Workbook and archive disagree: {name}')
        duplicate_checks.append({'archive_member': name, 'sheet': 'Fig.1b',
                                 'xlsx_column_pair': [1 + 3 * (field - 1), 2 + 3 * (field - 1)],
                                 'temperature_moment_pairs_identical': exact,
                                 'points': len(data), 'counted_once': True})
        for order, (line_no, timestamp, temperature, actual_oe, moment) in enumerate(data):
            points.append({'series_id': s_id, 'point_order': order, 'temperature_k': temperature,
                           'magnetic_moment_emu': moment, 'reported_field_oe': actual_oe,
                           'applied_mu0h_t_from_oe': actual_oe * 1e-4,
                           'nominal_applied_mu0h_t': field, 'timestamp_instrument_sec': timestamp,
                           'source_file': 'raw/nbse2_2025/Magnetization data.zip',
                           'source_locator': f'{name}:line:{line_no}',
                           'normal_state_eligibility': 'not_assessed'})
        series.append({'series_id': s_id, 'source': name, 'source_member_sha256': hashlib.sha256(original).hexdigest(),
                       'source_sheet_duplicate': 'Fig.1b', 'quantity': 'magnetic_dipole_moment', 'unit': 'emu',
                       'nominal_applied_mu0h_t': field, 'field_orientation': 'parallel to basal plane',
                       'cooling_protocol': 'ZFC', 'points': len(data),
                       'temperature_min_k': min(r[2] for r in data),
                       'temperature_max_k': max(r[2] for r in data),
                       'acquisition_temperature_direction': 'warming' if data[-1][2] > data[0][2] else 'cooling'})

for sheet, column, field, label, phi in [
    ('Fig.1a', 1, 0.0005, 'ZFC', 0), ('Fig.1a', 4, 0.0005, 'FC', 0),
    ('Fig.1d', 4, 4., 'misaligned_1deg', 1),
    ('Fig.1e', 4, 5., 'misaligned_1deg', 1),
    ('Fig.1f', 4, 6., 'misaligned_1deg', 1),
]:
    data = sheet_pairs(workbook[sheet], column)
    s_id = f'nbse2_2025_{sheet.replace(".", "")}_{label}'
    for order, (temperature, moment, row) in enumerate(data):
        points.append({'series_id': s_id, 'point_order': order, 'temperature_k': temperature,
                       'magnetic_moment_emu': moment, 'reported_field_oe': None,
                       'applied_mu0h_t_from_oe': None, 'nominal_applied_mu0h_t': field,
                       'timestamp_instrument_sec': None,
                       'source_file': 'raw/nbse2_2025/Source data.xlsx',
                       'source_locator': f'{sheet}!{openpyxl.utils.get_column_letter(column)}{row}:'
                                         f'{openpyxl.utils.get_column_letter(column + 1)}{row}',
                       'normal_state_eligibility': 'not_assessed'})
    series.append({'series_id': s_id, 'source_sheet': sheet, 'source_columns': [column, column + 1],
                   'quantity': 'magnetic_dipole_moment', 'unit': 'emu',
                   'nominal_applied_mu0h_t': field, 'angle_from_basal_plane_deg': phi,
                   'cooling_protocol': label if label in ('ZFC', 'FC') else 'not_explicit_in_sheet',
                   'points': len(data), 'temperature_min_k': min(r[0] for r in data),
                   'temperature_max_k': max(r[0] for r in data),
                   'acquisition_temperature_direction': 'warming' if data[-1][0] > data[0][0] else 'cooling'})

for sheet, field in [('Fig.1d', 4), ('Fig.1e', 5), ('Fig.1f', 6)]:
    left = [(r[0], r[1]) for r in sheet_pairs(workbook[sheet], 1)]
    reference = [(p['temperature_k'], p['magnetic_moment_emu']) for p in points
                 if p['series_id'] == f'nbse2_2025_fig1b_{field}T']
    duplicate_checks.append({'sheet': sheet, 'columns': [1, 2],
                             'duplicate_of': f'nbse2_2025_fig1b_{field}T',
                             'temperature_moment_pairs_identical': left == reference,
                             'points': len(left), 'counted_once': True})
    if left != reference:
        raise ValueError(f'Expected duplicate differs: {sheet}')

with (OUT / 'magnetic_moment_vs_temperature.csv').open('w', newline='', encoding='utf-8') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(points[0]))
    writer.writeheader()
    writer.writerows(points)

inventory = {
    'dataset_id': 'nbse2_2025', 'formula': 'NbSe2', 'phase': '2H',
    'independent_composition_groups': 1, 'distinct_series_not_independent_samples': len(series),
    'numeric_observations': len(points),
    'source_article_reports_distinct_bulk_crystals': 2,
    'raw_series_to_individual_crystal_assignment': 'unknown; no source file contains sample identifier',
    'pressure_gpa': None, 'doping_fraction': None, 'strain': None,
    'sample_form': 'bulk single crystal',
    'normal_state_eligibility': 'not_assessed',
    'automatic_training_eligible_observations': 0,
    'quantity_warning': 'Moment in emu is neither mass/volume magnetization nor susceptibility. No conversion using an unreported mass or internal field.',
    'plotting_warning': 'Paper plot uses emu/g and visual offsets; source cells/raw DAT are Moment (emu). No display offsets or guessed normalization applied.',
    'series': series, 'duplicate_checks': duplicate_checks,
    'workbook_sheet_inventory': [{'sheet': s.title, 'rows': s.max_row, 'columns': s.max_column} for s in workbook],
    'excluded_from_moment_extraction': [
        {'sheets': ['Fig.1c'], 'reason': 'dM/dT is a processed derivative, not additional independent raw moment'},
        {'sheets': ['Fig.2a', 'Fig.2b', 'Fig.2d'], 'reason': 'magnetic torque or derivatives in arbitrary units, not chi'},
        {'sheets': ['Fig.2c'], 'reason': 'organic comparator, not NbSe2'},
        {'sheets': ['Fig.3', 'Fig.4a', 'Fig.4b', 'Supplmentary Fig.S1'], 'reason': 'phase boundaries, normalized transition/outcome data or comparison literature; not normal precursor input'},
        {'sheets': ['Fig.4c'], 'reason': 'electrical resistance in mOhm, not heat or magnetic modality; no resistivity conversion'},
        {'sheets': ['Fig.5a', 'Fig.5b'], 'reason': 'theoretical/model curves, not experiment'},
    ],
    'original_files': [digest(RAW / name) for name in ['Magnetization data.zip', 'Source data.xlsx', 'repository-metadata.json']],
    'limitations': [
        'All curves include superconducting-state signal; no whole-curve normal-state assertion.',
        'No Tc-relative input window, Tc label, fitted curve, interpolated point, or invented condition was created.',
        'Field series and measurement points must remain grouped by material/study; cannot be treated as independent composition groups.',
        'No documented pressure/doping/strain in raw files: unknown stays null, not zero.',
        'Raw headers do not document background subtraction; do not claim uncorrected instrument data beyond the deposited author description.',
    ],
}
(OUT / 'series_inventory.json').write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'series': len(series), 'points': len(points), 'duplicate_checks': len(duplicate_checks),
                  'all_duplicates_exact': all(d['temperature_moment_pairs_identical'] for d in duplicate_checks),
                  'temperature_min_k': min(p['temperature_k'] for p in points),
                  'temperature_max_k': max(p['temperature_k'] for p in points)}, indent=2))
