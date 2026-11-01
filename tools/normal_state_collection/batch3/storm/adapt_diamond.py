"""Rebuild inspected B-doped-diamond curves; no ledger, training, or Tc joins.

Original PPMS resistance columns are used, never the apparent resistivity columns
whose instrument geometry is a placeholder. All missing values/order/repeats and
signed field readings remain traceable. Run with the repository's Python venv.
"""
from pathlib import Path
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent
ARCHIVE_SHA = '21e12aa4e9d7a68aae6bafc2145ef5fb02b6dd09c841bfbf8403999bfbceade3'
PAPER_SHA = 'd9832c9ae7f78930b91308a650872ad91d5ea739311793862adce06590f55eff'
SAMPLES = {'230224B': '6k', '230224': '12k', '230224C': '18k',
           '250618': '24k', '250703': '30k', '250707': '36k'}
GAS_PPM = {'6k': 6536, '12k': 12821, '18k': 18868, '24k': 24691,
           '30k': 30303, '36k': 36421}
TC = {'12k': 2.90, '18k': 3.75, '24k': 4.03, '30k': 3.98, '36k': 3.79}
RAMAN_B_CM3 = {'12k': 2.66e21, '18k': 3.35e21, '24k': 3.56e21,
               '30k': 3.79e21, '36k': 3.46e21}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def sample_map(path):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as archive:
        strings = [''.join(e.itertext()) for e in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(archive.read('xl/worksheets/sheet1.xml')).find('s:sheetData', ns):
            values = {}
            for cell in row:
                value = cell.find('s:v', ns)
                if value is not None:
                    text = strings[int(value.text)] if cell.get('t') == 's' else value.text
                    values[re.match('[A-Z]+', cell.get('r'))[0]] = text
            rows.append(values)
    return {r['A']: r['C'] for r in rows[1:] if 'A' in r and 'C' in r}


def ppms(path):
    text = path.read_text(encoding='utf-8-sig', errors='strict')
    marker = text.index('[Data]')
    headers = list(csv.reader(io.StringIO(text[:marker])))
    body = text[marker + len('[Data]'):].strip()
    table = list(csv.reader(io.StringIO(body)))
    names = {int(r[2].strip()[6]): r[1].strip() for r in headers
             if r and r[0] == 'INFO' and re.fullmatch(r'Sample[123] Name', r[2].strip())}
    header_line = next(i for i, line in enumerate(text.splitlines(), 1) if line.startswith('Comment,Time Stamp'))
    records = [(header_line + i, r) for i, r in enumerate(table[1:], 1) if r]
    notices = [dict(line=line, original_cells=row) for line, row in records if len(row) <= 4]
    assert all(row['original_cells'][0] == 'Measurement was Aborted' for row in notices)
    return names, table[0], [(line, row) for line, row in records if len(row) > 4], notices


def main():
    global ROOT, SOURCE_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=SOURCE_ROOT,
                        help='Collection root containing storm/raw/diamond4inch-data.zip and extracted storm/raw/diamond4inch/')
    parser.add_argument('--output-dir', type=Path, help='Defaults to the source root storm directory; only normalized JSON is written.')
    parser.add_argument('--repo', type=Path, default=ROOT.parents[1] / 'supercon-ml')
    parser.add_argument('--policy', type=Path, default=ROOT.parents[1] / 'normal-state-collection/protocol/normal-state-policy.json')
    parser.add_argument('--observed-at', default='2026-11-01T15:56:20+00:00')
    args = parser.parse_args()
    SOURCE_ROOT = args.source_root.resolve()
    ROOT = SOURCE_ROOT / 'storm'
    output = args.output_dir.resolve() if args.output_dir else ROOT
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.repo.resolve()))
    from ml import normal_state as N, feedback as F
    policy = json.loads(args.policy.read_text(encoding='utf-8'))
    N.validate_policy(policy)
    archive, paper = ROOT / 'raw/diamond4inch-data.zip', ROOT / 'raw/diamond4inch-paper.pdf'
    assert digest(archive) == ARCHIVE_SHA
    assert hashlib.md5(archive.read_bytes()).hexdigest() == '2acbd68b55852b9dbd3ad347bc5c9fd0'
    assert digest(paper) == PAPER_SHA
    extracted = ROOT / 'raw/diamond4inch/open data'
    mapping_path = extracted / 'sampled id.xlsx'
    assert sample_map(mapping_path) == SAMPLES
    reference = dict(doi='10.48550/arXiv.2609.15282',
        url='https://arxiv.org/abs/2609.15282', dataset_doi='10.17035/cardiff.34715652.v1',
        citation='Mandal, S. and Williams, O. A. Growth of superconducting boron doped diamond on 4inch silicon wafers. arXiv:2609.15282v1 (14 September 2026). Author preprint, not an established journal version.',
        publication_date='2026-09-14', inspection_status='full_text_inspected', source_kind='primary_experiment',
        locator='Author preprint PDF pp.3-4 section2 (gas ratios, estimates, warming2-10K); p.6 section3 (Tc=0.5R5K); p.8 Table1/central pieces; p.12 Table2 (Raman estimates); deposited sample mapping and PPMS headers.',
        accessed_url='https://arxiv.org/pdf/2609.15282', accessed_version='arXiv v1 author preprint',
        inspected_fulltext_sha256=PAPER_SHA)
    sources, curves, targets, candidates, audits = [], [], [], [], []
    for path in sorted((extracted / 'PPMS').rglob('*.dat')):
        names, header, records, notices = ppms(path)
        assert set(names) == {1, 2, 3} and all(s in SAMPLES for s in names.values())
        raw_sha = digest(path)
        source_id = 'batch3:diamond4inch:' + raw_sha[:16]
        source = dict(source_id=source_id, raw_path=path.relative_to(SOURCE_ROOT).as_posix(),
            sha256=raw_sha, reference=copy.deepcopy(reference), license='CC-BY-4.0',
            archive_path=archive.relative_to(SOURCE_ROOT).as_posix(), archive_sha256=ARCHIVE_SHA,
            archive_md5='2acbd68b55852b9dbd3ad347bc5c9fd0',
            download_url='https://ndownloader.figshare.com/files/70393047',
            sample_mapping_path=mapping_path.relative_to(SOURCE_ROOT).as_posix(),
            sample_mapping_sha256=digest(mapping_path),
            non_numeric_instrument_notices=notices,
            source_notes=['Author-deposited PPMS instrument data. Source order, duplicate temperatures, repeats, missing readings retained.',
                'Bridge Resistance (Ohms) used. Bridge Resistivity (Ohm-m) is not trusted as intrinsic resistivity: header sets cross-section=length=1.',
                'Gas-phase B/C ppm and Raman-model B estimates are separate metadata, not a measured film chemical formula or doping_fraction.'])
        sources.append(source)
        ti, bi = header.index('Temperature (K)'), header.index('Magnetic Field (Oe)')
        mode = 'field_sweep' if path.name.startswith('RH_') else 'cooling' if path.name.startswith('cooling') else 'warming'
        for bridge, internal_id in sorted(names.items()):
            label = SAMPLES[internal_id]
            yi = header.index(f'Bridge {bridge} Resistance (Ohms)')
            ei = header.index(f'Bridge {bridge} Excitation (uA)')
            ts = [numeric(r[ti]) for _, r in records]
            fields = [numeric(r[bi]) for _, r in records]
            assert all(t is not None and t > 0 for t in ts) and all(b is not None for b in fields)
            fixed_b = abs(fields[0]) * 1e-4 if len(set(fields)) == 1 else None
            cid = f'diamond4inch-{internal_id}-bridge{bridge}-{path.stem}'
            specimen = f'diamond4inch-{internal_id}-central-piece-candidate'
            points = []
            for (line, record), temp, field in zip(records, ts, fields):
                point = dict(temperature_k=temp, value=numeric(record[yi]),
                    source_locator=f'{path.relative_to(extracted).as_posix()}:line{line}:Temperature(K),Bridge{bridge}Resistance(Ohms)',
                    source_signed_field_oe=field, source_excitation_uA=numeric(record[ei]),
                    field_orientation=dict(signed_applied_field_oe=field, axis_orientation=None),
                    source_unit_conversion='Original resistance in Ohms; applied-field magnitude coordinate = abs(source Oe)*1e-4 T; original signed reading retained.')
                if fixed_b is None:
                    point['coordinates'] = dict(magnetic_field_t=abs(field)*1e-4)
                points.append(point)
            broad = mode == 'cooling' and max(ts) >= 250
            curve = dict(curve_id=cid, source_id=source_id, material_id='boron-doped-diamond:' + label,
                specimen_id=specimen, series_id='diamond4inch-six-growth-conditions', observed_at=args.observed_at,
                quantity='resistance', unit='Ohm', conditions=dict(sample_id=specimen, formula=None,
                    sample_form='CVD boron-doped nanocrystalline diamond film on silicon', phase=None,
                    pressure_GPa=None, field_T=fixed_b, t_min_K=min(ts), t_max_K=max(ts), method='van der Pauw electrical resistance'),
                fixed_coordinates=dict(pressure_gpa=None, doping_fraction=None, strain=None, magnetic_field_t=fixed_b),
                normal_state_status='verified_normal' if broad else 'unknown', points=points,
                composition_quality='doped_host_with_unresolved_absolute_film_composition',
                normalization=dict(kind='none'), measurement_run_id=path.stem,
                trace_id=path.relative_to(extracted).as_posix()+f':Bridge{bridge}Resistance(Ohms)',
                varied_axes=['magnetic_field_t'] if mode == 'field_sweep' else ['temperature_k'],
                sample_metadata=dict(author_internal_id=internal_id, author_label=label,
                    gas_phase_B_over_C_ppm=GAS_PPM[label], gas_ratio_is_not_film_doping=True,
                    raman_bernard_estimated_B_cm3=RAMAN_B_CM3.get(label),
                    raman_value_is_model_estimate=True, sample_region='central region', sweep=mode,
                    physical_piece_across_files_uniquely_identified=False),
                sample_notes=['Same film/central-region candidate identity comes from PPMS bridge header + deposited sample-id XLSX + author p.8. Unique physical-piece cross-trace identity is not independently established.',
                    'Pressure and phase unquantified here remain null; recorded tiny residual applied field is preserved rather than replaced by zero.',
                    'Cooling/rep/warming/R(H) traces are repeated observations of six growth-condition candidates, not independent material systems.',
                    'The whole curve includes transition/field-induced response; only source-checked absolute150-300K portions of broad cooling traces are normal-state eligible.',
                    'No link to author warming Tc is admitted: not the same raw trace; exact repeat used for Table1 is not identified, and absolute film composition is unresolved.'])
            if broad:
                curve['normal_state_evidence'] = dict(locator='Preprint pp.4,6,8: transition2.9-4.03K, R5K reference; original cooling-file T/K column extends to~300K.',
                    statement='The declared absolute150-300K cooling region is above the author-reported low-temperature transitions; no transition region is used as a precursor.',
                    verified_range_k=[150., 300.])
            curves.append(curve)
            audits.append(dict(curve_id=cid, mode=mode, author_label=label, raw_points=len(points),
                missing_values=sum(p['value'] is None for p in points), temperature_range_K=[min(ts),max(ts)],
                field_range_Oe=[min(fields),max(fields)], broad_cooling_candidate=broad))
    for internal_id, label in SAMPLES.items():
        if label not in TC:
            continue  # No Tc=0 or unconditional negative from Tmin=2K censoring.
        sid = f'diamond4inch-{internal_id}-central-piece-candidate'
        target_id = f'diamond4inch-{label}:author-resistive-midpoint'
        payload = dict(material_id='boron-doped-diamond:' + label, observed_at=args.observed_at,
            statement='Historical author-reported warming resistive midpoint Tc of a central-region film piece; not a model prediction or a cross-trace admitted label.',
            observation_type='sample_superconductivity', assertion_status='source_checked', outcome=True,
            evidence_kind='measured_transition', tc_K=TC[label], tc_criterion='resistive_midpoint',
            tc_is_approximate=False, criterion_definition='Tc at R(Tc)=0.5*R(5K); author preprint p.6 section3 and p.8 Table1.',
            conditions=dict(sample_id=sid, formula=None, sample_form='CVD boron-doped nanocrystalline diamond film on silicon',
                phase=None, pressure_GPa=None, field_T=None, t_min_K=2., t_max_K=10., method='resistivity'),
            reference=copy.deepcopy(reference), raw_source_sha256=PAPER_SHA,
            source_locator='Author preprint p.8 Table1; criterion p.6; warming2-10K method p.4.',
            curation_note='Author criterion retained separately. Same-film/central-region candidate matching only; no same-raw-trace relation to broad cooling. Gas B/C is not assigned to film composition.')
        F.validate_observation(payload)
        targets.append(dict(target_id=target_id, payload=payload))
        candidates.append(dict(target_id=target_id, candidate_curve_ids=[c['curve_id'] for c in curves if c['sample_metadata']['author_internal_id']==internal_id],
            admission_status='not_admitted', same_raw_trace=False, same_physical_specimen_confirmed=False,
            reason='Only author film/internal code and central region match. Table1 uses warming, broad region is in cooling; no unique physical piece and chosen-repeat binding; film composition unresolved.'))
    registry_doc = dict(sources=sources,
        source_root=Path(os.path.relpath(SOURCE_ROOT, Path.cwd())).as_posix(), ledger_written=False)
    registry = N.source_registry(registry_doc, source_root=SOURCE_ROOT)
    features = []
    for curve in curves:
        N.validate_curve(curve, registry)
        N.curve_observations(curve, registry, policy, point_indices=[0])
        features.append(N.extract_features(curve, registry, policy))
    collection = dict(curves=curves, targets=targets, links=[], candidate_matches=candidates,
        primary_tc_criterion='resistive_midpoint', temperature_points_are_not_independent_materials=True,
        primary_pilot_admitted_groups=0, ledger_written=False,
        unresolved_censoring=[dict(author_label='6k', measured_no_transition_down_to_K=2., tc_K=None,
            no_parent_negative=True, note='Source statement retained as censoring metadata; no negative training label created.')])
    audit = dict(curves=len(curves), points=sum(len(c['points']) for c in curves),
        source_numeric_files=len(sources), author_film_codes=6, independent_new_systems_for_primary_pilot=0,
        targets=len(targets), links=0, ledger_written=False, models_fitted=0,
        frozen_policy_sha256=N.sha256(policy), per_curve=audits, feature_diagnostics=features,
        limitations=['Normal-only curves plus separate author Tc outcomes; no cross-trace primary links.',
            'Film B stoichiometry is unresolved. Gas ppm is process metadata. Raman B concentrations remain model estimates.',
            'Repeated cooling/heating sweeps and six gas conditions are not additional independent systems.'])
    for name, value in [('transport-registry.json',registry_doc), ('transport-collection.json',collection),
                        ('transport-adapter-audit.json',audit)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',', ':'),allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ['curves','points','targets','links','independent_new_systems_for_primary_pilot','ledger_written','models_fitted']}))


if __name__ == '__main__':
    main()
