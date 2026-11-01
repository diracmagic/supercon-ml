"""Reproduce author-source inspection without fitting or writing a ledger.

The high-T RRR trace and low-T transition are NOT silently joined. Shared
notebook dimensions are circumstantial specimen evidence, not an exact sample
identifier or proof of matching unreported sample pressure.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io
import json
import sys
import zipfile

import pandas as pd

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle_common as B
OUTPUT = None

EXPECTED_ZIP_SHA = 'caa5dc079b241d2e873781a20dc5a288dc383c16bbd324ed322bd07256fe82f1'
MEMBERS = {
    'YRu3B2_LT.csv': 'YRu3B2_data/Fig_1/Fig_1a/YRu3B2_resistance.csv',
    'YRu3B2_HT.csv': 'YRu3B2_data/RRR/YRu3B2_resistance_HT.csv',
    'YRu3B2_LT_author.ipynb': 'YRu3B2_data/Fig_1/Fig_1a/Fig_1a_code.ipynb',
    'YRu3B2_HT_author.ipynb': 'YRu3B2_data/RRR/RRR_calculation.ipynb',
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def dump(name, obj):
    (OUTPUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main():
    global OUTPUT
    args = B.arguments(__doc__, observed_at='2026-11-01T14:00:54.645058+00:00')
    HERE = args.data_root / 'validation'
    OUTPUT = args.output_dir / 'validation'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.project_root))
    from ml import normal_state as N
    original = HERE / 'raw' / 'YRu3B2_data.zip'
    if digest(original.read_bytes()) != EXPECTED_ZIP_SHA:
        raise ValueError('Downloaded original ZIP changed')
    manifest = []
    with zipfile.ZipFile(original) as archive:
        for name, member in MEMBERS.items():
            content = archive.read(member)
            path = HERE / 'raw' / name
            B.materialize_original_member(path, content, source_root=args.data_root)
            manifest.append({'raw_path': 'raw/' + name, 'zip_member': member, 'sha256': digest(content), 'bytes': len(content)})
    observed_at = args.observed_at
    paper = {'doi': '10.48550/arXiv.2512.09314', 'url': 'https://arxiv.org/html/2512.09314',
             'inspection_status': 'full_text_inspected', 'source_kind': 'primary_experiment',
             'publication_date': '2025-12-10', 'locator': 'Experimental Methods; Experimental Results paragraph 1; Fig. 1a caption'}
    sources = []
    for name, member in list(MEMBERS.items())[:2]:
        content = (HERE / 'raw' / name).read_bytes()
        sources.append({'source_id': 'yru3b2-' + ('LT' if '_LT' in name else 'HT'),
                        'raw_path': 'raw/' + name, 'sha256': digest(content), 'reference': paper,
                        'dataset_doi': '10.5281/zenodo.18276373', 'dataset_url': 'https://zenodo.org/records/18276373',
                        'download_url': 'https://zenodo.org/records/18276373/files/YRu3B2_data.zip?download=1',
                        'zip_sha256': EXPECTED_ZIP_SHA, 'zip_member': member, 'license': 'CC-BY-4.0'})
    ht = pd.read_csv(HERE / 'raw' / 'YRu3B2_HT.csv')
    lt = pd.read_csv(HERE / 'raw' / 'YRu3B2_LT.csv')
    # This is the author's documented RRR selection, unrelated to target Tc:
    # df_up = df_up[idxmin:]; df_up = df_up[Temperature < 299].
    start = int(ht['Temperature (K)'].idxmin())
    warm = ht.iloc[start:]
    warm = warm[warm['Temperature (K)'] < 299]
    curve_specs = [
        ('HT', warm, 'Temperature (K)', 'Bridge 2 Resistance (ohms)', 'RRR/YRu3B2_resistance_HT.csv', float(warm['Magnetic Field (Oe)'].iloc[0]) * 1e-4),
        ('LT', lt, 'ADR Temp (K)', 'Bridge 2 Resistance (ohms)', 'Fig_1/Fig_1a/YRu3B2_resistance.csv', 0.),
    ]
    curves = []
    for suffix, frame, tcol, rcol, trace, field in curve_specs:
        if not frame[tcol].notna().all():
            raise ValueError('Missing temperature encountered; explicit curation required')
        limits = [float(frame[tcol].min()), float(frame[tcol].max())]
        curve = {'curve_id': 'YRu3B2-' + suffix, 'source_id': 'yru3b2-' + suffix,
                 'material_id': 'source-YRu3B2-Gaggl',
                 'specimen_id': 'unresolved-source-specimen:YRu3B2-' + suffix,
                 'specimen_identity_status': 'source_has_no_explicit_bar_identifier; no cross-trace specimen match asserted',
                 'series_id': 'Gaggl-YRu3B2-transport', 'observed_at': observed_at,
                 'quantity': 'resistance', 'unit': 'ohm',
                 'conditions': {'sample_id': None, 'formula': 'YRu3B2', 'sample_form': 'bar cut from arc-melted polycrystal',
                                'phase': 'hexagonal CeCo3B2-type', 'pressure_GPa': None,
                                't_min_K': limits[0], 't_max_K': limits[1], 'field_T': field, 'method': 'resistivity'},
                 'fixed_coordinates': {'pressure_gpa': None, 'doping_fraction': None, 'strain': None, 'magnetic_field_t': field},
                 'measurement_run_id': 'source-trace-run:YRu3B2-' + suffix, 'trace_id': trace,
                 'varied_axes': ['temperature_k'], 'normalization': {'kind': 'none'},
                 'normal_state_status': 'verified_normal' if suffix == 'HT' else 'unknown',
                 'points': [{'temperature_k': float(row[tcol]), 'value': float(row[rcol]) if pd.notna(row[rcol]) else None,
                             'source_locator': f'{MEMBERS["YRu3B2_" + suffix + ".csv"]}; CSV logical data record {int(index) + 1}; columns {tcol}, {rcol}'}
                            for index, row in frame.iterrows()],
                 'missing_resistance_records_retained_as_null': int(frame[rcol].isna().sum())}
        if suffix == 'HT':
            curve['normal_state_evidence'] = {'locator': 'Experimental Results paragraph 1; source RRR notebook',
                                              'statement': 'Source describes conventional metallic resistivity above the sub-kelvin transition; frozen 150-300 K region is normal state.',
                                              'verified_range_k': [150., 300.]}
            curve['author_selection'] = {'notebook': MEMBERS['YRu3B2_HT_author.ipynb'], 'start_dataframe_index': start, 'temperature_max_exclusive_k': 299.,
                                         'selection_rule': 'Warming segment from minimum Temperature(K), then T<299 K, exactly as author RRR notebook; no resistance filtering or smoothing.'}
            curve['field_provenance'] = {'column': 'Magnetic Field (Oe)', 'constant_sensor_reading_oe': .014402,
                                          'conversion': 'applied field magnitude Oe*1e-4 -> T; this is not an internal induction measurement',
                                          'author_notebook_nominal_label': '0 T', 'nominal_and_sensor_reading_not_silently_equated': True}
            curve['uninterpreted_pressure_column'] = 'Pressure () has no reported unit or sample-pressure meaning; retained only in original CSV, never treated as GPa.'
        else:
            curve['field_provenance'] = {'locator': 'Fig. 1a caption', 'kind': 'source-declared external nominal zero magnetic field',
                                          'sensor_reading': None}
        curves.append(curve)
    low_source = sources[0]
    target = {'target_id': 'YRu3B2-Gaggl-resistive-midpoint', 'payload': {
        'material_id': 'source-YRu3B2-Gaggl', 'observed_at': observed_at,
        'statement': 'The primary Experimental Results explicitly reports a resistive transition midpoint of 0.78 K; its bar is not identified with the high-T RRR trace by an explicit specimen ID.',
        'observation_type': 'sample_superconductivity', 'assertion_status': 'source_checked', 'outcome': True,
        'evidence_kind': 'measured_transition', 'tc_K': .78, 'tc_criterion': 'resistive_midpoint',
        'conditions': curves[1]['conditions'], 'reference': paper, 'derived_from_curve_id': curves[1]['curve_id'],
        'measurement_run_id': curves[1]['measurement_run_id'], 'trace_id': curves[1]['trace_id'],
        'raw_source_sha256': low_source['sha256'], 'varied_axes': ['temperature_k']}}
    registry_document = {'sources': sources}
    registry = N.source_registry(registry_document, source_root=HERE)
    policy_path = args.policy
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    features = [N.extract_features(c, registry, policy) for c in curves]
    N.F.validate_observation(target['payload'])
    dump('YRu3B2-registry.json', registry_document)
    dump('YRu3B2-collection.json', {'curves': curves, 'targets': [target], 'links': []})
    dump('YRu3B2-features.json', features)
    audit = {'status': 'not_admitted_to_primary_or_sensitivity_cohort', 'models_fitted': 0, 'ledger_written': False,
             'original_zip_sha256': EXPECTED_ZIP_SHA, 'files': manifest,
             'numeric_data': {'LT_rows': len(lt), 'HT_rows_full': len(ht), 'HT_author_selected_rows': len(warm),
                              'HT_author_selected_range_k': [float(warm['Temperature (K)'].min()), float(warm['Temperature (K)'].max())],
                              'HT_window_rows_150_300': int(warm['Temperature (K)'].between(150, 300).sum()),
                              'HT_features_status': features[0]['status'], 'LT_features_status': features[1]['status']},
             'evidence': {'paper': paper, 'dataset_doi': '10.5281/zenodo.18276373', 'dataset_license': 'CC-BY-4.0',
                          'resistive_midpoint_tc_k': .78,
                          'same_bar_circumstantial': {'notebooks': [MEMBERS['YRu3B2_HT_author.ipynb'], MEMBERS['YRu3B2_LT_author.ipynb']],
                              'HT_code': 'l1=54/45; w1=18/45; d1=11/45 # Unit: mm; Bridge 2 Resistance (ohms)',
                              'LT_code': 'l=54/45; w=18/45; t=11/45 # Unit: mm; Bridge 2 Resistance (ohms)',
                              'paper_caption': 'Fig. 1a describes a bar-shaped sample in zero external field',
                              'explicit_same_specimen_identifier': None,
                              'interpretation': 'Identical unusual dimensions and instrument channel support likely same bar, but a copied geometry or another bar is not excluded. Not an inspected explicit same-physical-specimen assertion.'}},
             'exclusions': ['High-T and low-T are different measurement traces, with no explicit same-bar identifier or statement.',
                            'Sample pressure is unreported for both traces; the unrelated instrument Pressure() column is not a sample-pressure measurement in GPa.',
                            'High-T measured residual field reading is 0.014402 Oe, whereas low-T has only a nominal zero-field declaration; equivalence is not silently asserted.',
                            'A source physical sample identifier is unknown; no checked composition link is fabricated.'],
             'next_evidence_needed': ['Author or original supplementary/source metadata explicitly linking the two traces to the same physical bar.',
                                      'For original strict cross-trace primary scope, explicit matching sample pressure and field evidence; a new pre-fit sensitivity protocol may retain unknown nuisance conditions but cannot waive specimen identity.']}
    dump('YRu3B2-audit.json', audit)
    print(json.dumps({'curves': len(curves), 'target_records': 1, 'links': 0, 'features_ready': sum(f['status'] == 'ready' for f in features),
                      'models_fitted': 0, 'ledger_written': False, 'status': audit['status']}))


if __name__ == '__main__':
    main()
