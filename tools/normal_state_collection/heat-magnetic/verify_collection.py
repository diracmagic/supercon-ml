"""Verify exact-source extraction and read-only normal_state integration.

No network, ledger writes, model fitting, or generated scientific observations.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import math
import sys
import zipfile

import openpyxl

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=SOURCE_ROOT.parent / 'supercon-ml')
args = parser.parse_args()
REPOSITORY = args.repo.resolve()
sys.path.insert(0, str(REPOSITORY))
from ml import normal_state as N


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    data = path.read_bytes()
    return {'path': path.relative_to(SOURCE_ROOT).as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(), 'md5': hashlib.md5(data).hexdigest()}


def run():
    registry_document = load(ROOT / 'heat-registry.json')
    registry = N.source_registry(registry_document, source_root=SOURCE_ROOT)
    collection = load(ROOT / 'heat-collection.json')
    policy = load(SOURCE_ROOT / 'protocol/normal-state-policy.json')
    N.validate_policy(policy)
    counts, tests = Counter(), []
    raw_zips, members, workbook_cache = {}, {}, {}
    negative_signed_fields = 0
    for curve in collection['curves']:
        N.validate_curve(curve, registry)
        raw_path = SOURCE_ROOT / registry[curve['source_id']]['raw_path']
        if raw_path.suffix == '.zip' and raw_path not in raw_zips:
            raw_zips[raw_path] = zipfile.ZipFile(raw_path)
        observations = N.curve_observations(curve, registry, policy)
        curve_hash = N.sha256(curve)
        assert len(observations) == len(curve['points'])
        feature = N.extract_features(curve, registry, policy)
        assert feature['status'] == 'insufficient_data' and feature['features'] == {}
        for point, payload in zip(curve['points'], observations):
            counts['point_records'] += 1
            counts['finite_pairs'] += point['value'] is not None
            assert payload['normal_state_status'] == 'unknown' and payload['outcome'] is None
            locator = point['source_locator']
            if curve['source_id'] in {'nbse2-2025-raw-moment', 'mgb2-2020-bulk', 'mgb2-2022-composite', 'hea-2022-raw'}:
                member_name, line = locator.rsplit(':line:', 1)
                cache_key = (raw_path, member_name)
                if cache_key not in members:
                    text = raw_zips[raw_path].read(member_name).decode('utf-8-sig' if curve['source_id'] != 'mgb2-2020-bulk' and curve['source_id'] != 'mgb2-2022-composite' else 'cp1252')
                    members[cache_key] = text.splitlines()
                raw_line = members[cache_key][int(line) - 1]
                values = next(csv.reader([raw_line]))
                if curve['source_id'] == 'nbse2-2025-raw-moment':
                    raw_t, raw_h, raw_y = map(float, values[1:4])
                elif curve['source_id'] in {'mgb2-2020-bulk', 'mgb2-2022-composite'}:
                    raw_t, raw_h, raw_y = map(float, values[2:5])
                else:
                    raw_t, raw_h = float(values[0]), None
                    raw_y = float(values[1]) if values[1] else None
                assert point['temperature_k'] == raw_t and point['value'] == raw_y
                if raw_h is not None:
                    assert point['coordinates']['magnetic_field_t'] == abs(raw_h) * 1e-4
                    assert payload['coordinates']['magnetic_field_t'] == abs(raw_h) * 1e-4
                    assert payload['conditions']['field_T'] == abs(raw_h) * 1e-4
                    assert payload['field_orientation']['signed_field_oe'] == raw_h
                    assert payload['coordinate_provenance'] == point['coordinate_provenance']
                    assert payload['source_unit_conversion'] == point['source_unit_conversion']
                    negative_signed_fields += raw_h < 0
                    counts['point_field_coordinates_verified'] += 1
            else:
                if raw_path not in workbook_cache:
                    workbook_cache[raw_path] = openpyxl.load_workbook(raw_path, read_only=True, data_only=True)
                sheet, cells = locator.rsplit('!', 1)
                a, b = cells.split(':')
                raw_x = workbook_cache[raw_path][sheet][a].value
                raw_y = workbook_cache[raw_path][sheet][b].value
                if curve['curve_id'] == 'ta16te_2024_heat':
                    assert point['temperature_k'] == math.sqrt(raw_x)
                    assert point['value'] == raw_y * math.sqrt(raw_x)
                    assert point['original_reported_pair'] == {'temperature_squared_k2': raw_x, 'C_over_T_mj_g_k2': raw_y}
                else:
                    assert point['temperature_k'] == raw_x and point['value'] == raw_y
            assert payload['point_provenance']['locator'] == locator
            assert payload['raw_source_sha256'] == registry[curve['source_id']]['sha256']
            assert payload['curve_content_sha256'] == curve_hash
        counts['curves_valid'] += 1
    for archive in raw_zips.values():
        archive.close()
    assert counts['curves_valid'] == 35 and counts['point_records'] == 33324 and counts['finite_pairs'] == 33323
    assert counts['point_field_coordinates_verified'] == 31445
    assert not collection['targets'] and not collection['links']
    assert not (ROOT / 'no-ledger-written.jsonl').exists()
    tests.extend([
        'Every source SHA256 verified within explicit collection root',
        'Every retained point exactly matches its original source line/cell; heat uses only stated algebra',
        'No missing value replaced by zero; one HEA M-missing row remains null',
        '31445 raw sensor fields reproduced in main feedback coordinates and conditions, with original signed field preserved',
        'Negative applied-field component is retained alongside explicitly converted nonnegative applied-field magnitude; not internal B',
        'All35 curves schema-valid; all normal-state statuses unknown and no feature-ready curves',
        'No target, link, Tc-relative normalization, ledger write, or model fit',
    ])
    nb = load(ROOT / 'derived/nbse2_2025/series_inventory.json')
    assert all(d['temperature_moment_pairs_identical'] for d in nb['duplicate_checks'])
    mg = load(ROOT / 'derived/mgb2_2022/series_inventory.json')
    assert len(mg['exact_byte_duplicates_counted_once']) == 1
    tests.append('NbSe2 ten duplicate comparisons and MgB2 sharedFast58 exactbyte duplicate counted once')
    report = {'schema_version': 1, 'status': 'pass', 'counts': dict(counts),
              'negative_signed_raw_field_points_preserved': negative_signed_fields,
              'independent_material_families': 4,
              'policy_sha256': N.sha256(policy), 'normal_state_version': N.VERSION,
              'normal_state_module_sha256': hashlib.sha256((REPOSITORY / 'ml/normal_state.py').read_bytes()).hexdigest(),
              'models_fitted': 0, 'ledger_writes': 0, 'normal_feature_ready_curves': 0,
              'target_records': 0, 'curve_collection': digest(ROOT / 'heat-collection.json'),
              'source_registry': digest(ROOT / 'heat-registry.json'), 'checks': tests,
              'limitations': ['Counts are observed rows and acquisition curves, not independent samples for fitting.',
                              'No150-300Kcoverage, no verifiednormal labels, and no measuredTc joins.',
                              'Oxford source/derived numericdata remain local under repository-use restrictions.',
                              'HEA units and fieldscript/caption mismatch remain unresolved; no chi conversion.']}
    (ROOT / 'verification').mkdir(exist_ok=True)
    (ROOT / 'verification/collection-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'counts', 'negative_signed_raw_field_points_preserved', 'normal_feature_ready_curves', 'models_fitted')}, indent=2))


if __name__ == '__main__':
    run()
