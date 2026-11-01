"""Compact source/provenance index; original restricted numeric data stay local."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def file_record(path, url=None, **extra):
    data = path.read_bytes()
    result = {'path': path.relative_to(SOURCE_ROOT).as_posix(), 'bytes': len(data),
              'sha256': hashlib.sha256(data).hexdigest(), 'md5': hashlib.md5(data).hexdigest(), **extra}
    if url:
        result['source_url'] = url
    audit_path = path.with_name(path.name + '.provenance.json')
    if audit_path.exists():
        audit = load(audit_path)
        result.update({k: audit[k] for k in ('requested_url', 'final_url', 'retrieved_at_utc', 'expected_repository_md5') if k in audit})
    else:
        result['retrieved_on'] = '2026-11-01'
        result['timestamp_precision'] = 'collection day; exact HTTP retrieval timestamp was not logged for this initial root/caller download'
    return result


def clean_provenance():
    allowed = {'content-type', 'content-length', 'content-disposition', 'date', 'etag', 'last-modified', 'location'}
    for path in (ROOT / 'raw').rglob('*.provenance.json'):
        item = load(path)
        if 'headers' in item:
            item['headers'] = {k: v for k, v in item['headers'].items() if k.lower() in allowed}
        body = path.with_name(path.name.removesuffix('.provenance.json'))
        if body.suffix == '.pdf' and body.exists():
            item['expected_format_matches'] = body.read_bytes().startswith(b'%PDF-')
            if not item['expected_format_matches']:
                item['status'] = 'response_received_but_not_pdf'
        path.write_text(json.dumps(item, indent=2) + '\n', encoding='utf-8')


clean_provenance()
registry = load(ROOT / 'heat-registry.json')
audits = load(ROOT / 'verification/collection-audit.json')
datasets = []
DOWNLOAD_URLS = {
    'nbse2-2025-raw-moment': 'https://zenodo.org/records/15627723/files/Magnetization%20data.zip?download=1',
    'nbse2-2025-source-xlsx': 'https://zenodo.org/records/15627723/files/Source%20data.xlsx?download=1',
    'mgb2-2020-bulk': 'https://ora.ox.ac.uk/objects/uuid:b8aa6e71-8960-47bc-a186-aec73338efb2/files/r0r967440t',
    'mgb2-2022-composite': 'https://ora.ox.ac.uk/objects/uuid:2acd535d-ce42-462d-9b19-43f5b0443eca/files/d9p290963p',
    'ta16te-2024-source-xlsx': 'https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-45952-2/MediaObjects/41467_2024_45952_MOESM6_ESM.xlsx',
    'hea-2022-raw': 'https://zenodo.org/api/records/6673464/files/Evidence%20for%20Isotropic%20s-Wave%20Superconductivity%20in%20High-Entropy%20Alloys%20Raw%20Data.zip/content',
}
for source in registry['sources']:
    raw_path = SOURCE_ROOT / source['raw_path']
    source_item = dict(source)
    source_item['original_file'] = file_record(raw_path, DOWNLOAD_URLS[source['source_id']])
    source_item['normal_state_feature_status'] = 'not_admitted_unknown_normal_and_no150-300Kcoverage'
    datasets.append(source_item)

derived = [file_record(path, kind='exact numeric source extraction; local only')
           for path in sorted((ROOT / 'derived').rglob('*.csv'))]
access_failures = []
for path in sorted((ROOT / 'raw').rglob('*.provenance.json')):
    item = load(path)
    if item.get('status') not in {'downloaded'}:
        access_failures.append({k: v for k, v in item.items() if k not in {'headers'}})
access_failures.append({'requested_url': 'https://data.4tu.nl/file/8178b0dc-c6b7-4f0c-af82-abdbc73e8927/b2309c1c-da5a-4156-90bd-cc16d09ee52c',
                        'client': 'PowerShell Invoke-WebRequest with normal TLS; authorized retry after initial urllib timeout',
                        'attempt_observed_on': '2026-11-01', 'exact_attempt_time_not_logged': True,
                        'status': 'failed', 'bytes': 0, 'reason': 'TCP connection timeout data.4tu.nl:443; stopped retrying'})

manifest = {
    'schema_version': 1, 'collection': 'Primary heat capacity and magnetic-response source collection',
    'scope': 'Current batch of author-deposited data only; literature/source search is not exhaustive.',
    'counts': {'source_datasets_raw_files': len(datasets), 'primary_studies': 5,
               'material_families': 4, 'curve_count': 35,
               'numeric_observations': 33323, 'missing_response_observations': 1,
               'total_point_records': 33324, 'specific_heat_points': 382,
               'four_pi_chi_points': 196, 'explicit_moment_emu_points': 31945,
               'unknown_unit_author_M_points': 800,
               'verified_normal_curves': 0, 'feature_ready_curves': 0, 'measured_Tc_targets': 0,
               'exact_specimen_Tc_links': 0, 'ledger_writes_by_this_collector': 0, 'models_fitted': 0},
    'scientific_boundary': [
        'Temperature points and field sweeps are not independent material/sample counts.',
        'The fixed150-300Knormal window is not covered; no collected curve was labeled verified_normal.',
        'C/T converted only through T=sqrt(T2),C=(C/T)*T; electronic-background-subtracted/normalized model curves excluded.',
        'Magnetic dipole moment(emu),4pi*chi and unknown-unitM remain distinct observables.',
        'All31,445 instrument-field points retain explicit magnitude conversion and signedoriginal field/direction; not measured internalB.',
        'Pressure/doping/strain not reported remain null; fabrication pressure or Mg additivewtpercent are not measurementpressure or dopingfraction.',
        'Ta1.6Te heat/magnetic fragments and unresolved NbSe2 crystals are not falsely joined as one measured specimen.',
        'These data provide observation/provenance coverage, not independent evidence of a universal pairing mechanism or a validated highTc predictor.',
    ],
    'sources': datasets,
    'source_data_integrity': {'repository_md5_checked': ['nbse2_2025/Magnetization data.zip', 'nbse2_2025/Source data.xlsx', 'hea_2022/raw-data.zip'],
                              'all_original_raw_files_sha256_bound_by_normal_state_registry': True,
                              'all_retained_points_roundtripped_to_raw_cells_or_lines': True,
                              'raw_file_modifications': 0, 'author_analysis_code_executed': False},
    'collection_files': {'registry': file_record(ROOT / 'heat-registry.json'),
                         'collection_numeric_local_only': file_record(ROOT / 'heat-collection.json'),
                         'roundtrip_audit': file_record(ROOT / 'verification/collection-audit.json'),
                         'derived_csvs_local_only': derived},
    'access_failures': access_failures,
    'pending_sources': [
        {'material': 'NbS2', 'status': 'public_dataset_identified_download_failed',
         'paper_doi': '10.1038/s41467-021-23976-2', 'dataset_doi': '10.4121/14623011.v1',
         'url': 'https://data.4tu.nl/articles/_/14623011/1',
         'published_file': {'name': 'Data.zip', 'bytes': 648831, 'repository_md5': '05cc74a3a444c98febcb2635429ae3fc'},
         'reported_modalities': ['specific heat', 'magnetic torque', 'linear thermal expansion'],
         'license': 'CC-BY-SA-4.0 per primary repository landing',
         'limitations': ['No data bytes obtained; no C units or numerical measurements imported.', 'Torque is not magnetic susceptibility.']},
        {'material': 'V,Nb', 'status': 'needs_full_text_original_tables',
         'paper_doi': '10.1515/zna-1960-0808', 'reported_temperature_range_k': [10,273],
         'title': 'Die Atom- und Elektronenwarme des Vanadins und Niobs zwischen10und273K',
         'publisher_url': 'https://www.degruyterbrill.com/document/doi/10.1515/zna-1960-0808/pdf',
         'archive_doi': '10.17617/3.GRUJYR', 'archive_license': 'CC-BY-ND-3.0 per official archive API metadata',
         'limitations': ['Publisher returned WAF challenge/noPDF; archival individual URL redirected to HTMLchallenge.',
                         'Official public archiveAPI inspected: entire Reihe_A.zip50,086,033,062bytes, not downloaded.',
                         'No secondary JANAF/fitted curve or invented digitization substituted.']},
        {'material': 'MgB2 calorimetry', 'status': 'paper_found_no_original_numeric_curve_dataset_in_this_search',
         'paper_doi': '10.1103/PhysRevLett.87.167003',
         'primary_pdf_url': 'https://ir.lib.nycu.edu.tw/bitstream/11536/29338/1/bd6f816bad10b74262fcc428d2b38f00.pdf',
         'inspection_scope': 'primary search-indexed text only; not admitted as numeric data',
         'limitations': ['Synthesis3GPa is not measurement pressure.', 'No curve digitized or modeled from article figure.']},
        {'material': 'Nb3Sn,V3Si', 'status': 'no_original_machine_readable_heat_curve_found_in_this_search',
         'limitations': ['Not a claim that raw data do not exist or measurements were never performed.', 'Handbook fits/secondary compilations excluded.']},
        {'material': 'Nb laser-processed', 'status': 'next_batch_source_downloaded_by_root_not_part_of_current_collection',
         'dataset_doi': '10.5281/zenodo.19254033', 'paper_doi': '10.1016/j.jallcom.2026.188695',
         'author_preprint': 'https://arxiv.org/abs/2604.15981',
         'root_reported_file': {'path': 'nb-laser/source.zip', 'bytes': 59412788,
                                'md5': 'd60e285d7e8455d7ae881de92998346a',
                                'sha256': '803793c1250a12921de369ddb993740ea91ef9249c0864930f3b2b38ef08624f'},
         'limitations': ['Collector has not re-curated this archive. Excluded from current counts/hashes/admission.',
                         'ProcessingNpressure is not measurementP/dopingfraction.']},
    ],
    'search_log': [
        {'query': 'NbS2 heat capacity raw data dataset', 'source_urls': ['https://data.4tu.nl/articles/_/14623011/1'], 'result': 'primary repository identified; fetch timeout'},
        {'query': 'NbSe2 orbital FFLO source data magnetization Zenodo', 'source_urls': ['https://zenodo.org/records/15627723', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC12356947/'], 'result': 'author original ZIP/XLSX downloaded and inspected'},
        {'query': 'Improving the connectivity of MgB2 dataset zip', 'source_urls': ['https://ora.ox.ac.uk/objects/uuid:2acd535d-ce42-462d-9b19-43f5b0443eca'], 'result': 'primary original ZIP downloaded with repository terms'},
        {'query': 'Effect of sintering temperature MgB2 raw magnetisation dataset', 'source_urls': ['https://ora.ox.ac.uk/objects/uuid:b8aa6e71-8960-47bc-a186-aec73338efb2'], 'result': 'primary original ZIP downloaded; sharedFast58 duplicate found'},
        {'query': 'Evidence for isotropic s-wave superconductivity high-entropy alloys raw data', 'source_urls': ['https://zenodo.org/records/6673464','https://archive-ouverte.unige.ch/unige:166708'], 'result': 'original ZIP and publishedPDF inspected; field/unit ambiguity retained'},
        {'query': 'specific heat superconductor csv raw data Nb3Sn V3Si MgB2', 'source_urls': ['https://doi.org/10.1103/PhysRevLett.87.167003'], 'result': 'no additional original numericCcurve admitted'},
        {'query': 'Die Atom- und Elektronenwarme des Vanadins und Niobs', 'source_urls': ['https://doi.org/10.1515/zna-1960-0808','https://edmond.mpg.de/api/datasets/:persistentId/?persistentId=doi:10.17617/3.GRUJYR'], 'result': 'bibliographic original source and public archive metadata; no paper tablebytes'},
    ],
    'public_upload_allowlist': ['heat-registry.json','build_normal_collection.py','extract_nbse2.py','extract_additional.py','verify_collection.py','build_manifest.py','manifest.json','verification/collection-audit.json'],
    'never_upload_as_part_of_this_harvest': ['heat-collection.json','raw/','derived/','verification/hea-published-figure1.png'],
    'public_redistribution_authorized_by_software': False,
}
(ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'manifest_bytes': (ROOT / 'manifest.json').stat().st_size,
                  'sources': len(datasets), 'curves': 35, 'point_records': 33324,
                  'manifest_sha256': hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest()}, indent=2))
