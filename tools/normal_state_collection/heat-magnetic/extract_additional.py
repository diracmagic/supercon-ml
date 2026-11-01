"""Read-only extraction of additional original author data, never training labels."""
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import re
import zipfile

import openpyxl

ROOT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def csv_out(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def finite(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def extract_mgb2():
    out = ROOT / 'derived' / 'mgb2_2022'
    points, inventory, duplicates, excluded, seen = [], [], [], [], {}
    sample_ids = set()
    for filename in ('MgB2.zip', 'Mg-MgB2.zip'):
        source = ROOT / 'raw' / 'mgb2_2022' / filename
        with zipfile.ZipFile(source) as archive:
            for member in archive.namelist():
                if member.startswith('__MACOSX') or not member.upper().endswith('.DAT'):
                    continue
                data = archive.read(member)
                if not re.search(r'_(ZFC|FC|FCW)50\.DAT$', member, re.I):
                    excluded.append({'archive': filename, 'member': member,
                                     'reason': 'M(H) field sweep or sample-dimensions note; retained in original ZIP, outside T-series extraction'})
                    continue
                digest = sha(data)
                if digest in seen:
                    duplicates.append({'archive': filename, 'member': member,
                                       'sha256': digest, 'duplicate_of': seen[digest]})
                    continue
                text_lines = [(i, line) for i, line in enumerate(data.decode('cp1252').splitlines(), 1)
                              if line.strip()]
                data_index = next(i for i, (_, line) in enumerate(text_lines) if line == '[Data]')
                headers = next(csv.reader([text_lines[data_index + 1][1]]))
                required = ('Temperature (K)', 'Magnetic Field (Oe)', 'Moment (emu)')
                if not all(name in headers for name in required):
                    raise ValueError(f'Unexpected VSM header {member}')
                sample_text = next((line for _, line in text_lines[:data_index]
                                    if line.endswith(',SAMPLE_MATERIAL')), None)
                sample_label = next(csv.reader([sample_text]))[1] if sample_text else None
                sample_id = re.sub(r'[^a-z0-9]+', '_', (sample_label or member.split('/')[-2]).lower()).strip('_')
                sample_ids.add(sample_id)
                s_id = f'mgb2_{sample_id}_{Path(member).stem.lower()}'
                seen[digest] = s_id
                collected, skipped = [], []
                for order, (line_no, line) in enumerate(text_lines[data_index + 2:]):
                    values = next(csv.reader([line]))
                    row = dict(zip(headers, values))
                    temperature, field, moment = [finite(row.get(key)) for key in required]
                    if None in (temperature, field, moment):
                        skipped.append({'line': line_no, 'reason': 'missing/nonfinite temperature, field or moment'})
                        continue
                    item = {'series_id': s_id, 'sample_id': sample_id, 'point_order': order,
                            'temperature_k': temperature, 'magnetic_moment_emu': moment,
                            'moment_standard_error_emu': finite(row.get('M. Std. Err. (emu)')),
                            'applied_field_oe': field, 'applied_mu0h_t_from_oe': field * 1e-4,
                            'instrument_timestamp_sec': finite(row.get('Time Stamp (sec)')),
                            'measure_status_code': row.get('Measure Status (code)'),
                            'source_archive': f'raw/mgb2_2022/{filename}',
                            'source_member': member, 'source_line': line_no,
                            'normal_state_eligibility': 'not_assessed'}
                    points.append(item)
                    collected.append(item)
                inventory.append({'series_id': s_id, 'sample_id': sample_id,
                                  'sample_header': sample_text, 'source_archive': filename,
                                  'source_member': member, 'source_sha256': digest,
                                  'points': len(collected), 'skipped_rows': skipped,
                                  'filename_protocol': re.search(r'_(ZFC|FC|FCW)50\.DAT$', member, re.I).group(1).upper(),
                                  'temperature_min_k': min(r['temperature_k'] for r in collected),
                                  'temperature_max_k': max(r['temperature_k'] for r in collected),
                                  'field_min_oe': min(r['applied_field_oe'] for r in collected),
                                  'field_max_oe': max(r['applied_field_oe'] for r in collected),
                                  'initial_field_ramp_retained': True,
                                  'source_sample_group': member.split('/')[-2]})
    csv_out(out / 'magnetic_moment_vs_temperature.csv', points)
    result = {'dataset_id': 'mgb2_2022', 'nominal_superconducting_component': 'MgB2',
              'independent_material_families': 1, 'distinct_source_sample_headers': sorted(sample_ids),
              'source_specimen_headers_count': len(sample_ids),
              'unique_temperature_acquisition_files': len(inventory), 'numeric_observations': len(points),
              'series': inventory, 'exact_byte_duplicates_counted_once': duplicates,
              'not_extracted_dat_members': excluded,
              'automatic_training_eligible_observations': 0,
              'limitations': [
                  'The Mg additions are 1/3/6/10 wt.% precursor mixture additions, not a measured substitutional doping fraction.',
                  'Specimens have MgB2 plus MgO/MgB4/residual Mg and differing porosity/processing; not pure equivalent MgB2 cells.',
                  'Different sintering temperatures are preparation history, not measurement temperature or pressure.',
                  'Pressure (Torr) is an instrument channel; not used as material hydrostatic pressure. Material pressure remains unknown.',
                  'Moment (emu) is not susceptibility or mass/volume magnetization. SAMPLE_MASS/SAMPLE_VOLUME metadata are blank; the numeric Mass (grams) channel is not assumed to be specimen mass.',
                  'Field-ramping/setpoint rows are preserved. Filenames containing 50 do not justify assigning every point a constant 50 Oe.',
                  'Normal and superconducting regions are mixed. No normal eligibility labels or Tc-relative windows created.',
                  'Oxford dataset item licenses refer to repository terms, allowing private non-commercial research; no blanket CC license or redistribution/training permission is inferred from open-access paper license.',
              ]}
    dump(out / 'series_inventory.json', result)
    return {key: result[key] for key in ('source_specimen_headers_count', 'unique_temperature_acquisition_files', 'numeric_observations')}


def extract_ta16te():
    # Canonical original remains in root collector's directory; no raw bytes changed.
    source = ROOT.parent / 'ta16te' / 'source-publisher.xlsx'
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    out = ROOT / 'derived' / 'ta16te_2024'
    heat, magnetic = [], []
    for row_num, values in enumerate(workbook['Figure 3c'].iter_rows(values_only=True), 1):
        if row_num == 1:
            assert values == ('T2 (K2)', 'C/T (mJ g-1 K-2)')
            continue
        t2, cot = map(finite, values)
        if t2 is None and cot is None:
            continue
        if t2 is None or cot is None or t2 <= 0:
            raise ValueError(f'Invalid heat pair row {row_num}')
        t = math.sqrt(t2)
        heat.append({'series_id': 'ta16te_2024_heat', 'sample_id': 'ta16te_2024_C_26p09mg',
                     'source_temperature_squared_k2': t2, 'source_c_over_t_mj_g_k2': cot,
                     'temperature_k': t, 'specific_heat_mj_g_k': cot * t,
                     'source_locator': f'Figure 3c!A{row_num}:B{row_num}',
                     'transformation': 'T=sqrt(T2); C=(C/T)*T; no fit/interpolation/background subtraction',
                     'normal_state_eligibility': 'not_assessed'})
    sheet = workbook['Figure 3a,b']
    for protocol, tc, yc in [('ZFC', 2, 3), ('FC', 5, 6)]:
        for row in range(2, sheet.max_row + 1):
            t, y = map(finite, [sheet.cell(row, tc).value, sheet.cell(row, yc).value])
            if t is None and y is None:
                continue
            if t is None or y is None:
                raise ValueError(f'Missing magnetic pair row {row}')
            magnetic.append({'series_id': f'ta16te_2024_four_pi_chi_{protocol.lower()}',
                             'sample_id': 'ta16te_2024_chi_95p64mg', 'temperature_k': t,
                             'reported_four_pi_chi': y,
                             'reported_unit': 'emu Oe-1 cm-3 (header labels 4pi*chi)',
                             'nominal_applied_field_oe': 50., 'nominal_applied_mu0h_t': 0.005,
                             'cooling_protocol': protocol,
                             'source_locator': f'Figure 3a,b!{openpyxl.utils.get_column_letter(tc)}{row}:'
                                               f'{openpyxl.utils.get_column_letter(yc)}{row}',
                             'normal_state_eligibility': 'not_assessed'})
    csv_out(out / 'specific_heat_vs_temperature.csv', heat)
    csv_out(out / 'four_pi_chi_vs_temperature.csv', magnetic)
    inventory = {'dataset_id': 'ta16te_2024', 'formula': 'Ta1.6Te', 'phase': 'dodecagonal quasicrystal',
                 'source_workbook': '../ta16te/source-publisher.xlsx', 'source_sha256': sha(source.read_bytes()),
                 'independent_composition_groups': 1, 'separate_specimens': True,
                 'samples': [
                     {'sample_id': 'ta16te_2024_C_26p09mg', 'mass_mg': 26.09,
                      'form': 'fragment cut/polished from crushed reaction-sintered pellet',
                      'quantity': 'mass_specific_heat', 'source_quantity': 'C/T', 'source_unit': 'mJ g-1 K-2',
                      'export_unit': 'mJ g-1 K-1', 'measurement': 'PPMS thermal relaxation',
                      'pressure_gpa': None, 'magnetic_field_t': None, 'doping_fraction': None, 'strain': None,
                      'points': len(heat), 'temperature_min_k': min(p['temperature_k'] for p in heat),
                      'temperature_max_k': max(p['temperature_k'] for p in heat)},
                     {'sample_id': 'ta16te_2024_chi_95p64mg', 'mass_mg': 95.64,
                      'form': 'separate fragment of crushed reaction-sintered pellet',
                      'quantity': 'four_pi_volume_susceptibility_as_reported',
                      'measurement': 'MPMS3 with 3He refrigerator',
                      'pressure_gpa': None, 'nominal_applied_mu0h_t': 0.005,
                      'doping_fraction': None, 'strain': None, 'series': 2, 'points': len(magnetic),
                      'temperature_min_k': min(p['temperature_k'] for p in magnetic),
                      'temperature_max_k': max(p['temperature_k'] for p in magnetic),
                      'density_used_by_authors_g_cm3': 10.6, 'density_basis': 'crystalline approximant density, assumed approximately QC density',
                      'author_estimated_volume_mm3': 9.02, 'author_approx_demagnetization_factor': 0.25},
                 ], 'automatic_training_eligible_observations': 0,
                 'excluded_sheets': {'Figure 3d': 'background-subtracted electronic specific heat normalized by gamma*T',
                                     'Figure 4': 'normalized/reused literature/theoretical comparisons, not new raw observations'},
                 'limitations': [
                     'Heat and susceptibility are different physical specimens; no exact-specimen multimodal join.',
                     'Only exact algebraic T2,C/T conversion applied; source values and row/cell references retained.',
                     '4pi*chi is kept as reported and is not renamed chi; no new demagnetization correction or SI conversion applied.',
                     'Heat field is not explicitly reported; pressure/doping/strain remain unknown, not zero.',
                     'Low-temperature curves include superconducting regions and do not cover a 150-300 K precursor window.',
                     'Authors estimate electron-phonon lambda via McMillan and measured Tc; that is outcome-derived, not an independent precursor feature or mechanism proof.',
                 ]}
    dump(out / 'series_inventory.json', inventory)
    return {'heat_points': len(heat), 'magnetic_points': len(magnetic)}


def extract_hea():
    source = ROOT / 'raw' / 'hea_2022' / 'raw-data.zip'
    out = ROOT / 'derived' / 'hea_2022'
    points, series = [], []
    with zipfile.ZipFile(source) as archive:
        for member in archive.namelist():
            if member.startswith('__MACOSX') or '/ZFCFC/' not in member or not member.endswith('.csv'):
                continue
            data = archive.read(member)
            rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
            assert set(rows[0]) == {'T', 'M'}
            nominal_x, measured_x = (0.4, 0.35) if 'x0p4.csv' in member else (0.75, 0.71)
            sample_id = f'hea_2022_measured_x{str(measured_x).replace(".", "p")}'
            missing, retained = [], []
            for order, row in enumerate(rows):
                t, value = finite(row['T']), finite(row['M'])
                if t is None or value is None:
                    missing.append({'source_line': order + 2, 'source_values': row,
                                    'reason': 'missing/nonfinite T or M; no imputation'})
                    continue
                if order >= 400:
                    raise ValueError(f'Unexpected extra finite HEA pair {member} row {order+2}')
                retained.append(row)
                points.append({'series_id': f'{sample_id}_{"zfc" if order < 200 else "fc"}',
                               'sample_id': sample_id, 'temperature_k': t,
                               'source_M_value': value, 'source_M_unit': 'not_explicit_in_csv',
                               'source_header': 'T,M', 'source_line': order + 2,
                               'cooling_protocol': 'ZFC' if order < 200 else 'FC',
                               'nominal_composition_x': nominal_x, 'measured_composition_x': measured_x,
                               'source_member': member, 'normal_state_eligibility': 'not_assessed'})
            series.append({'member': member, 'member_sha256': sha(data), 'source_rows': len(rows),
                           'retained_finite_pairs': len(retained), 'missing_pairs': missing,
                           'nominal_x_in_filename': nominal_x, 'actual_x_reported_by_paper': measured_x,
                           'sample_id': sample_id, 'protocol_split_source': 'author fig1ab.m: rows1:200 ZFC and201:400 FC',
                           'temperature_min_k': min(float(row['T']) for row in retained),
                           'temperature_max_k': max(float(row['T']) for row in retained)})
    csv_out(out / 'author_M_channel_vs_temperature.csv', points)
    result = {'dataset_id': 'hea_2022', 'alloy_series': '(TaNb)_(1-x)(ZrHfTi)_x',
              'independent_material_families': 1, 'actual_compositions_reported': [0.35, 0.71],
              'separate_films': 2, 'series_count': 4, 'observations': len(points),
              'sample_form': 'approximately 1 micrometer sputtered film on SiN wafer',
              'phase': 'single phase body-centered cubic per XRD/EDX',
              'series': series, 'automatic_training_eligible_observations': 0,
              'source_code_inspection_only': 'Author MATLAB/notebook files were read as text, never executed.',
              'limitations': [
                  'CSV header M does not state a unit; the author conversion divides by sample volume and approximately5Oe then multiplies4pi to plot4pi*chi. We do not silently assign chi or an unverified input unit.',
                  'Author script uses5.187 for nominalx0.4 and5 for nominalx0.75; do not assign an identical exactfield to both.',
                  'Paper reports actualx0.35/0.71; raw filenames use nominalx0.4/0.75, and both labels are retained.',
                  'One alloy series with two films does not establish two independent material families.',
                  'These low-temperature superconducting-response curves are not verified normal-state precursor inputs; no whole-curve normal label.',
                  'Pressure/strain unknown; actualelement-by-elementfractions not assumed equal from shorthandgroups.',
                  'Hc1,Hc2,penetration-depth,BCSfit/normalized-superfluid-density outputs excluded from input extraction as outcome-derived.',
              ]}
    dump(out / 'series_inventory.json', result)
    return {'points': len(points), 'films': 2, 'series': 4}


if __name__ == '__main__':
    print(json.dumps({'mgb2': extract_mgb2(), 'ta16te': extract_ta16te(), 'hea': extract_hea()}, indent=2))
