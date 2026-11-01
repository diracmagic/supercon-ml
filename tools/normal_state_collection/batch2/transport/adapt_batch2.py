"""Rebuild one inspected NbN source collection, never a ledger or model.

Run with --data-root PRIVATE_BATCH2 --output-dir PRIVATE_REPLAY.
Use --project-root to choose the repository and --policy for its frozen policy. Original
numeric ordering/repeated temperatures are retained. No plot digitization.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import sys
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bundle_common as B


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    args = B.arguments(__doc__, observed_at='2026-11-01T14:02:39+00:00')
    ROOT, SOURCE_ROOT = args.data_root / 'transport', args.data_root
    output = args.output_dir / 'transport'
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.project_root))
    from ml import normal_state as M, feedback as F
    policy = json.loads(args.policy.read_text(encoding='utf-8'))
    M.validate_policy(policy)
    archive = ROOT / 'raw/nbn_mo_data.zip'
    assert digest(archive) == 'd146bc914912fa4302133af35c04cc08648592e245e34b971939b13f486f24e5'
    assert hashlib.md5(archive.read_bytes()).hexdigest() == 'b9389c83ac108ab58d1ea49db24e4b90'
    paper = ROOT / 'raw/nbn_mo_paper.pdf'
    assert digest(paper) == 'fd57da3865945284e20bfc0ee1c09009ff80bba04db7d1bdad244aee673cc621'
    path = ROOT / 'raw/nbn_mo_data/Fig3/Fig3_NbN_R-R300K(Temperature).txt'
    with zipfile.ZipFile(archive) as original:
        member = 'Fig3/Fig3_NbN_R-R300K(Temperature).txt'
        B.materialize_original_member(path, original.read(member), source_root=SOURCE_ROOT)
    lines = path.read_text(encoding='utf-8').splitlines()
    assert lines[0] == 'Temperature (K)\tR/R(300K)'
    values = [(i, *map(float, line.split())) for i, line in enumerate(lines[1:], 2) if line.strip()]
    assert len(values) == 52439 and all(len(v) == 3 for v in values)
    assert min(v[1] for v in values) == 2.5 and max(v[1] for v in values) == 300
    raw_sha = digest(path)
    source_id = 'batch2:nbn-mo-2025:reference:' + raw_sha[:16]
    cid = 'nbn-mo-2025-Fig3-reference-9p6nm'
    specimen = 'nbn-mo-2025-reference-NbN-strip'
    locator = 'Author preprint arXiv:2504.18997 PDF p.5 Table1; p.6 section2B; p.7 Fig3/reference-NbN text; deposited Fig3_NbN_R-R300K(Temperature).txt'
    reference = dict(doi='10.1088/1361-6668/adeaf2', url='https://doi.org/10.6084/m9.figshare.29339720.v1',
        dataset_doi='10.6084/m9.figshare.29339720.v1', publication_date='2025-07-14',
        locator=locator, inspection_status='full_text_inspected', source_kind='primary_experiment',
        accessed_url='https://arxiv.org/pdf/2504.18997', accessed_version='Author preprint; publisher article page/data statement inspected; publisher PDF access returned HTML, not treated as full text',
        citation='Korneeva et al. Practical way to increase nonlinearity of kinetic inductance of superconductor. Superconductor Science and Technology 38,075016 (2025). DOI:10.1088/1361-6668/adeaf2',
        inspected_fulltext_sha256=digest(paper))
    source = dict(source_id=source_id, raw_path=path.relative_to(SOURCE_ROOT).as_posix(), sha256=raw_sha,
        reference=reference, license='CC-BY-4.0', archive_path=archive.relative_to(SOURCE_ROOT).as_posix(),
        archive_sha256=digest(archive), archive_md5='b9389c83ac108ab58d1ea49db24e4b90',
        download_url='https://ndownloader.figshare.com/files/55444505',
        source_notes=['Original author-deposited numerical TXT; no collector digitization, smoothing, resampling, temperature clipping or resistance conversion.',
                      'Normalized resistance R/R(300K), dimensionless; not ohm or intrinsic resistivity.',
                      'RRR<1 and increasing resistance on cooling are reported; not relabeled as a nonsuperconducting or parent-negative sample.'])
    conditions = dict(sample_id=specimen, formula='NbN', sample_form='sputtered thin-film strip', phase=None,
        pressure_GPa=None, field_T=None, t_min_K=2.5, t_max_K=300., method='two-terminal normalized resistance')
    curve = dict(curve_id=cid, source_id=source_id, material_id='NbN', specimen_id=specimen,
        series_id='nbn-mo-2025-reference-film', observed_at=args.observed_at,
        quantity='normalized_resistance', unit='1', conditions=conditions,
        composition_quality='nominal_sample_formula',
        fixed_coordinates=dict(pressure_gpa=None, doping_fraction=None, strain=None, magnetic_field_t=None),
        normal_state_status='verified_normal', normal_state_evidence=dict(locator=locator,
            statement='The author reports the reference NbN transition at8.5K and normal resistance at20K and room temperature; Fig3 inset and deposited full trace show the normal transport region150–300K. The normal-state assertion is restricted to the fixed absolute window.',
            verified_range_k=[150., 300.]),
        normalization=dict(kind='fixed_reference_temperature', reference_temperature_k=300.),
        points=[dict(temperature_k=t, value=v, source_locator=f'Fig3/Fig3_NbN_R-R300K(Temperature).txt line{line}:columns1=T(K),2=R/R(300K)') for line,t,v in values],
        measurement_run_id=cid, trace_id='research_data.zip:Fig3/Fig3_NbN_R-R300K(Temperature).txt:columns1,2',
        varied_axes=['temperature_k'], thickness_nm=9.6, width_um=4., length_mm=3., measurement_current_A=1e-5,
        sample_notes=['NbN reference without Mo (Table1); deposited NbN9.6nm thickness measured by XRR; sputtered from Nb target in Ar/N2 onto preoxidized Si. Formula NbN is author sample designation, not a measured exact N/Nb ratio.',
                      'Two-terminal R(T) can include contacts; the room-temperature four-probe characterization is a separate method and is not substituted for this normalized trace.',
                      'The authors combine broad cooling/heating and low-temperature heater-controlled measurements in one deposited Fig3 trace. They do not provide separate acquisition-run identifiers; trace-bound scope means this exact author trace, not a claimed single uninterrupted instrument sweep.',
                      'Pressure, applied magnetic field, crystal phase and strain not explicitly quantified for this trace are null; no ambient-pressure or zero-field imputation.',
                      'Duplicate temperatures, source ordering and tiny low-temperature residual values are preserved. Temperature points are not independent samples.'])
    target_id = cid + ':resistive_midpoint'
    binding = dict(measurement_run_id=curve['measurement_run_id'], trace_id=curve['trace_id'], raw_source_sha256=raw_sha, varied_axes=curve['varied_axes'])
    payload = dict(material_id='NbN', observed_at=args.observed_at,
        statement='Historical author-reported experimental Tc of the reference NbN strip; not a prediction or prospective discovery.',
        observation_type='sample_superconductivity', assertion_status='source_checked', outcome=True,
        evidence_kind='measured_transition', tc_K=8.5, tc_criterion='resistive_midpoint', tc_is_approximate=False,
        conditions=copy.deepcopy(conditions), reference=copy.deepcopy(reference), derived_from_curve_id=cid,
        criterion_definition='R(Tc)=0.5*R(20K), author section2B; use Table1/reference-Fig3 value8.5K without collector re-estimation.',
        curation_note='The author fulltrace contains both the midpoint transition and broad-T reference NbN curve; never transferred from the adjacent NbN/Mo bilayers.', **binding)
    payload['conditions']['method'] = 'resistivity'
    link = dict(curve_id=cid, target_id=target_id, same_physical_specimen=True, assertion_status='source_checked',
        specimen_id=specimen, curve_sample_id=specimen, target_sample_id=specimen,
        source_locator=locator, scope='same_run_measured_tc', same_raw_trace=True,
        composition_quality='nominal_sample_formula',
        composition_source_locator='Author preprint PDF p.4 section2A explicitly NbN film from Nb reactive sputtering; p.5 Table1 referenceNbN without Mo,9.6nm; exact N/Nb elemental analysis not reported', **binding)
    registry_doc = dict(sources=[source], source_root='work/normal-state-batch2', ledger_written=False)
    collection = dict(curves=[curve], targets=[dict(target_id=target_id, payload=payload)], links=[link],
        primary_tc_criterion='resistive_midpoint', temperature_points_are_not_independent_materials=True,
        omitted_rows=[dict(sample_id=s, reason='NbN/Mo heterogeneous bilayer, raw full-T curve retained in archive but not encoded as a homogeneous NbN/Mo chemical formula or counted as an independent elemental system') for s in ['SN5','SN6','SN7']])
    registry = M.source_registry(registry_doc, source_root=SOURCE_ROOT)
    M.validate_curve(curve, registry)
    F.validate_observation(payload)
    probe = M.curve_observations(curve, registry, policy, point_indices=[0])[0]
    assert not M._link_reasons(probe, payload, link), M._link_reasons(probe, payload, link)
    feature = M.extract_features(curve, registry, policy)
    audit = dict(curves=1, points=len(values), independent_specimens=1, independent_systems=1,
        sources=1, targets=1, links=1, frozen_policy_sha256=M.sha256(policy), feature=feature,
        link_reasons=[], ledger_written=False, models_fitted=0,
        limitations=['Author preprint full text, not publisher-paginated final PDF; page/section locators explicitly name this edition.',
                     'Nominal author formula, no independent composition analysis; unknown phase/P/B stay null.',
                     'Author-deposited combined Fig3 trace, not proof that high/low-T sweeps are one uninterrupted acquisition.'])
    for name, document in [('transport-registry.json', registry_doc), ('transport-collection.json', collection), ('transport-adapter-audit.json', audit)]:
        (output/name).write_text(json.dumps(document, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=feature['status'], reasons=feature['reasons'], points=len(values), ledger_written=False)))


if __name__ == '__main__':
    main()
