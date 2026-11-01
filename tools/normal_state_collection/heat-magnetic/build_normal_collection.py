"""Curate genuine low-T data into normal_state's observation-only interface.

Reads original data/exact-extraction CSVs; writes no ledger and fits no model.
All source-backed numeric curves are intentionally normal_state_status=unknown.
"""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent
INSPECTED_AT = '2026-11-01T13:03:00Z'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def registry_source(identifier, raw_relative, doi, url, date, cite, locator, license_id,
                    redistribution, scientific_limitations, full_text=True):
    path = SOURCE_ROOT / raw_relative
    return {'source_id': identifier, 'raw_path': raw_relative,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size,
            'reference': {'doi': doi, 'url': url, 'publication_date': date, 'cite': cite,
                          'source_kind': 'primary_experiment',
                          'inspection_status': 'full_text_inspected' if full_text else 'data_inspected',
                          'inspected_at': INSPECTED_AT, 'locator': locator},
            'license': license_id, 'public_redistribution': redistribution,
            'raw_data_remain_local': True, 'limitations': scientific_limitations}


def base_curve(identifier, source_id, material, specimen, formula, phase, form, method,
               quantity, unit, points, *, field=None, varied_axes=None, metadata=None):
    temperatures = [p['temperature_k'] for p in points]
    return {'curve_id': identifier, 'source_id': source_id, 'material_id': material,
            'specimen_id': specimen, 'series_id': f'{source_id}:{material}',
            'measurement_run_id': identifier, 'trace_id': identifier,
            'varied_axes': varied_axes or ['temperature_k'],
            'observed_at': INSPECTED_AT,
            'observed_at_basis': 'Source inspected/curated availability timestamp; not an inferred original experiment date.',
            'quantity': quantity, 'unit': unit,
            'conditions': {'sample_id': specimen, 'formula': formula, 'phase': phase,
                           'sample_form': form, 'method': method,
                           'pressure_GPa': None, 'field_T': field,
                           't_min_K': min(temperatures), 't_max_K': max(temperatures)},
            'fixed_coordinates': {'pressure_gpa': None, 'magnetic_field_t': field,
                                  'doping_fraction': None, 'strain': None},
            'normal_state_status': 'unknown', 'normalization': {'kind': 'none'},
            'no_target_join_requested': True, 'metadata': metadata or {}, 'points': points}


def field_point(signed_oe, locator):
    # Canonical feedback coordinate is an applied-field magnitude, not an internal B.
    # Preserve the signed measured component so this explicit conversion loses no source sign.
    conversion = 'applied field magnitude abs(H[Oe])*1e-4 T; signed component retained separately; not measured internal B'
    return {'coordinates': {'magnetic_field_t': abs(signed_oe) * 1e-4},
            'coordinate_provenance': {'magnetic_field_t': {'source_unit': 'Oe', 'canonical_unit': 'T',
                                                         'conversion': conversion, 'source_locator': locator}},
            'field_orientation': {'signed_field_oe': signed_oe,
                                  'sign_along_instrument_axis': 1 if signed_oe > 0 else -1 if signed_oe < 0 else 0,
                                  'crystal_orientation': None},
            'source_unit_conversion': conversion}


sources = [
    registry_source('nbse2-2025-raw-moment', 'heat-magnetic/raw/nbse2_2025/Magnetization data.zip',
                    '10.1038/s41467-025-62223-w', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC12356947/', '2025-08-15',
                    'Cho et al., Evidence for orbital Fulde-Ferrell-Larkin-Ovchinnikov state in the bulk limit of 2H-NbSe2, Nat Commun16,7599(2025).',
                    'Methods: sample information/DC magnetization; Fig1b. Raw headers Time Stamp,Temperature(K),Magnetic Field(Oe),Moment(emu).',
                    'CC-BY-4.0 (Zenodo dataset metadata; article separately CC-BY-NC-ND-4.0)', 'dataset_CC_BY_4.0',
                    ['Low-T mixed superconducting/normal response; exact specimen assignment among two crystals not supplied in raw files.']),
    registry_source('nbse2-2025-source-xlsx', 'heat-magnetic/raw/nbse2_2025/Source data.xlsx',
                    '10.1038/s41467-025-62223-w', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC12356947/', '2025-08-15',
                    'Cho et al., Nat Commun16,7599(2025); author dataset Zenodo10.5281/zenodo.15627723.',
                    'Fig1a,d,e,f source sheets. Source cells Moment(emu), distinct from plotted emu/g and offsets.',
                    'CC-BY-4.0 (Zenodo dataset metadata)', 'dataset_CC_BY_4.0',
                    ['No mass normalization/chi conversion or plotted display offset applied.']),
    registry_source('mgb2-2020-bulk', 'heat-magnetic/raw/mgb2_2022/MgB2.zip',
                    '10.1088/1361-6668/ab7c53', 'https://ora.ox.ac.uk/objects/uuid:b8aa6e71-8960-47bc-a186-aec73338efb2', '2020-03-19',
                    'Matthews et al., Effect of the sintering temperature on the microstructure and superconducting properties of MgB2 bulks manufactured by the field assisted sintering technique, Supercond Sci Technol33,054003(2020). Dataset10.5287/bodleian:ZO6MREoYX deposited2022.',
                    'Experimental section; QuantumDesign VSM DAT headers, sample labels; processing900/1000/1100/1200C.',
                    'Oxford repository terms of use; no dataset CC license stated', 'not_authorized_for_public_redistribution',
                    ['Private noncommercial research terms. Source/data/derived numeric curves remain local.',
                     'Porous multiphase processing specimens; no pure-cell or measurement-pressure/doping inference.']),
    registry_source('mgb2-2022-composite', 'heat-magnetic/raw/mgb2_2022/Mg-MgB2.zip',
                    '10.1088/1361-6668/ac5164', 'https://ora.ox.ac.uk/objects/uuid:2acd535d-ce42-462d-9b19-43f5b0443eca', '2022-04-26',
                    'Matthews et al., Improving the connectivity of MgB2 bulk superconductors by a novel liquid phase sintering process, Supercond Sci Technol35,065005(2022). Dataset10.5287/bodleian:xr11rwggY.',
                    'Experimental section,Table1; original VSM DAT files by1/3/6/10wtpercentMg-addition preparation groups.',
                    'Oxford repository terms of use; no dataset CC license stated', 'not_authorized_for_public_redistribution',
                    ['Mg wtpercent precursor addition is not substitutional doping fraction.',
                     'No volume/mass conversion from blank sample mass metadata or unrelated instrument channels.']),
    registry_source('ta16te-2024-source-xlsx', 'ta16te/source-publisher.xlsx',
                    '10.1038/s41467-024-45952-2', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC10907369/', '2024-03-01',
                    'Tokumoto et al., Superconductivity in a van der Waals layered quasicrystal, Nat Commun15,1529(2024).',
                    'Physical property measurements; source sheetsFigure3a,b andFigure3c; two separately weighed fragments.',
                    'CC-BY-4.0 (article/source data)', 'CC_BY_4.0',
                    ['Heat26.09mg and susceptibility95.64mg are distinct pieces, not one physical specimen.',
                     'Source4pi*chi not demagnetization corrected; no independent measured lambda label.']),
    registry_source('hea-2022-raw', 'heat-magnetic/raw/hea_2022/raw-data.zip',
                    '10.1038/s41598-022-16355-4', 'https://archive-ouverte.unige.ch/unige:166708', '2022-07-27',
                    'Leung et al., Evidence for isotropic s-wave superconductivity in high-entropy alloys, Sci Rep12,12773(2022). Dataset10.5281/zenodo.6673464(version1),concept6673463.',
                    'Published Fig1caption and Experiment; author Fig1ab/ZFCFC CSV and fig1ab.m inspected as text, no author code executed.',
                    'CC-BY-4.0 (Zenodo metadata)', 'dataset_CC_BY_4.0',
                    ['CSV M unit not explicit. PublishedcaptionZFC5Oe/FC50Oe differs from author plotting script common divisor5or5.187; retain unresolved input units/field.',
                     'Nominal x0.4/0.75 filenames correspond to EDX actualx0.35/0.71.'])]

curves = []
grouped = defaultdict(list)
for row in csv.DictReader((ROOT / 'derived/nbse2_2025/magnetic_moment_vs_temperature.csv').open(encoding='utf-8', newline='')):
    grouped[row['series_id']].append(row)
for identifier, rows in grouped.items():
    archive = rows[0]['source_file'].endswith('.zip')
    points = [{'temperature_k': float(r['temperature_k']), 'value': float(r['magnetic_moment_emu']),
               'source_locator': r['source_locator'],
               'reported_coordinates': {'field_oe': float(r['reported_field_oe']) if r['reported_field_oe'] else None},
               'instrument_timestamp_sec': float(r['timestamp_instrument_sec']) if r['timestamp_instrument_sec'] else None}
              for r in rows]
    if archive:
        for point in points:
            point.update(field_point(point['reported_coordinates']['field_oe'],
                                     point['source_locator'] + ':Magnetic Field (Oe)'))
    curves.append(base_curve(identifier, 'nbse2-2025-raw-moment' if archive else 'nbse2-2025-source-xlsx',
                             'source:nbse2-2025:2H-NbSe2', 'unresolved:nbse2-2025:individual-crystal',
                             'NbSe2', '2H', 'bulk single crystal', 'VSM-SQUID DC magnetic moment',
                             'magnetic_moment', 'emu', points,
                             field=None if archive else float(rows[0]['nominal_applied_mu0h_t']),
                             varied_axes=['temperature_k', 'magnetic_field_t'] if archive else ['temperature_k'],
                             metadata={'specimen_assignment_verified': False, 'no_specimen_target_link': True,
                                       'nominal_applied_mu0h_t': float(rows[0]['nominal_applied_mu0h_t']),
                                       'field_kind': 'nominal externally applied mu0H; exact sensor field per point when raw DAT available'}))

mgb2_inventory = {s['series_id']: s for s in load(ROOT / 'derived/mgb2_2022/series_inventory.json')['series']}
grouped = defaultdict(list)
for row in csv.DictReader((ROOT / 'derived/mgb2_2022/magnetic_moment_vs_temperature.csv').open(encoding='utf-8', newline='')):
    grouped[row['series_id']].append(row)
for identifier, rows in grouped.items():
    meta = mgb2_inventory[identifier]
    points = [{'temperature_k': float(r['temperature_k']), 'value': float(r['magnetic_moment_emu']),
               'source_locator': f"{r['source_member']}:line:{r['source_line']}",
               'reported_coordinates': {'signed_magnetic_field_oe': float(r['applied_field_oe']),
                                        'signed_applied_mu0h_t': float(r['applied_mu0h_t_from_oe'])},
               'standard_error_emu': float(r['moment_standard_error_emu']) if r['moment_standard_error_emu'] else None,
               'instrument_timestamp_sec': float(r['instrument_timestamp_sec']) if r['instrument_timestamp_sec'] else None,
               'measure_status_code': r['measure_status_code']}
              for r in rows]
    for point in points:
        point.update(field_point(point['reported_coordinates']['signed_magnetic_field_oe'],
                                 point['source_locator'] + ':Magnetic Field (Oe)'))
    curves.append(base_curve(identifier, 'mgb2-2020-bulk' if rows[0]['source_archive'].endswith('/MgB2.zip') else 'mgb2-2022-composite',
                             'source:oxford:MgB2-processing-series', f"oxford-MgB2:{rows[0]['sample_id']}",
                             'MgB2', 'MgB2 plus MgO/MgB4/residualMg, specimen-dependent',
                             'reaction/field-assisted-sintered porous bulk', 'QuantumDesign PPMS VSM magnetic moment',
                             'magnetic_moment', 'emu', points, varied_axes=['temperature_k', 'magnetic_field_t'],
                             metadata={'sample_header': meta['sample_header'], 'preparation_group': meta['source_sample_group'],
                                       'filename_protocol': meta['filename_protocol'], 'field_ramp_retained': True,
                                       'field_status': 'actual signed field retained per point; no single exact constant field asserted',
                                       'license_local_only': True}))

heat_rows = list(csv.DictReader((ROOT / 'derived/ta16te_2024/specific_heat_vs_temperature.csv').open(encoding='utf-8', newline='')))
curves.append(base_curve('ta16te_2024_heat', 'ta16te-2024-source-xlsx', 'source:ta16te-2024:Ta1.6Te',
                         'ta16te-2024:heat-fragment26.09mg', 'Ta1.6Te', 'dodecagonal quasicrystal',
                         'fragment of reaction-sintered pellet', 'PPMS thermal relaxation', 'specific_heat', 'mJ g^-1 K^-1',
                         [{'temperature_k': float(r['temperature_k']), 'value': float(r['specific_heat_mj_g_k']),
                           'source_locator': r['source_locator'],
                           'original_reported_pair': {'temperature_squared_k2': float(r['source_temperature_squared_k2']),
                                                      'C_over_T_mj_g_k2': float(r['source_c_over_t_mj_g_k2'])}}
                          for r in heat_rows],
                         metadata={'mass_mg': 26.09, 'transformation': 'T=sqrt(T2), C=(C/T)*T; exact algebra only',
                                   'background_subtraction': 'No lattice/electronic subtraction; Figure3d excluded',
                                   'heat_measurement_field_not_reported': True}))
grouped = defaultdict(list)
for row in csv.DictReader((ROOT / 'derived/ta16te_2024/four_pi_chi_vs_temperature.csv').open(encoding='utf-8', newline='')):
    grouped[row['series_id']].append(row)
for identifier, rows in grouped.items():
    curves.append(base_curve(identifier, 'ta16te-2024-source-xlsx', 'source:ta16te-2024:Ta1.6Te',
                             'ta16te-2024:chi-fragment95.64mg', 'Ta1.6Te', 'dodecagonal quasicrystal',
                             'separate fragment of reaction-sintered pellet', 'MPMS3 with3He refrigerator',
                             'four_pi_magnetic_susceptibility', '4pi*chi; source header emu Oe^-1 cm^-3',
                             [{'temperature_k': float(r['temperature_k']), 'value': float(r['reported_four_pi_chi']),
                               'source_locator': r['source_locator']} for r in rows], field=0.005,
                             metadata={'mass_mg': 95.64, 'cooling_protocol': rows[0]['cooling_protocol'],
                                       'demagnetization_correction': 'not applied by authors to source curve; no new correction here',
                                       'density_normalization': 'authors assume10.6g/cm3 approximant density',
                                       'distinct_from_heat_specimen': True}))

grouped = defaultdict(list)
for row in csv.DictReader((ROOT / 'derived/hea_2022/author_M_channel_vs_temperature.csv').open(encoding='utf-8', newline='')):
    grouped[row['series_id']].append(row)
for identifier, rows in grouped.items():
    measured_x = float(rows[0]['measured_composition_x'])
    points = [{'temperature_k': float(r['temperature_k']), 'value': float(r['source_M_value']),
               'source_locator': f"{r['source_member']}:line:{r['source_line']}"} for r in rows]
    # Preserve the author's extra incomplete row: unknown is not silently discarded or filled.
    if measured_x == .35 and identifier.endswith('_fc'):
        points.append({'temperature_k': 1.7990586, 'value': None,
                       'source_locator': f"{rows[0]['source_member']}:line:402",
                       'status': 'source_M_missing; additional row outside author plotted1:400 selection'})
    curves.append(base_curve(identifier, 'hea-2022-raw', f'source:hea-2022:actual-x{measured_x}',
                             f'hea-2022:film-actual-x{measured_x}', None,
                             'body-centered cubic disordered alloy', 'approximately1micrometer sputtered film onSiN',
                             'MPMS3 VSM-SQUID original M channel', 'author_M_channel', None, points,
                             metadata={'reported_formula_shorthand': f'(TaNb)_(1-x)(ZrHfTi)_x; x={measured_x}',
                                       'expanded_elemental_formula': 'not inferred from shorthand group ratios',
                                       'nominal_x_in_file': float(rows[0]['nominal_composition_x']),
                                       'measured_x': measured_x, 'protocol': rows[0]['cooling_protocol'],
                                       'unit_missing_in_original_header': True,
                                       'published_caption_field_oe': 5 if identifier.endswith('_zfc') else 50,
                                       'author_plotting_common_divisor': 5.187 if measured_x == .35 else 5,
                                       'field_and_unit_resolution': 'unresolved; do not convert to chi or assign a fixed field',
                                       'no_substrate_background_correction_created': True}))

registry = {'schema_version': 1, 'source_root': 'work/normal-state-collection', 'sources': sources,
            'collection_scope': 'Low-temperature genuine heat/magnetic curves. No claim of normal-state precursor eligibility.'}
collection = {'schema_version': 1, 'curated_at': INSPECTED_AT, 'curves': curves, 'targets': [], 'links': [],
              'automatic_training': False, 'models_fitted': 0,
              'curation_summary': {'curve_count': len(curves),
                                   'point_records': sum(len(c['points']) for c in curves),
                                   'finite_numeric_pairs': sum(p['value'] is not None for c in curves for p in c['points']),
                                   'normal_verified_curves': 0, 'independent_material_families': 4,
                                   'temperature_points_are_not_independent_samples': True},
              'limitations': ['All curves normal_state_status=unknown and below the frozen150-300Kwindow.',
                              'No measuredTc target or exactspecimen target join supplied.',
                              'Unknown P/doping/strain remain null. No DFT-structure/formula joins.',
                              'Noncommercial/private-research Oxford numericdata remain local. Publicupload onlysourceindex/hash/curationscript/audit.',
                              'Observation timestamp is current inspection availability, not an invented original measurement time.',
                              'Perpoint actualfield coordinates retain explicit abs(Oe)*1e-4 appliedmagnitude conversion plusoriginalsignedcomponent/direction. Mixedfieldcurves havefixedBnull andcannot become fixedfieldtemperaturefeatures.']}
save(ROOT / 'heat-registry.json', registry)
save(ROOT / 'heat-collection.json', collection)
print(json.dumps(collection['curation_summary'], indent=2))
