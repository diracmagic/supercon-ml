"""Preserve a real transport trace without inventing its exact composition."""
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import xlrd
ROOT=Path(__file__).parent
path=ROOT/'nbc/source.xls'
digest=hashlib.sha256(path.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--observed-at", help="Reuse a documented frozen inspection timestamp when reproducing this curation")
args=parser.parse_args()
now=args.observed_at or datetime.now(timezone.utc).isoformat()
ref=dict(doi='10.1038/s41467-020-16987-y',url='https://pmc.ncbi.nlm.nih.gov/articles/PMC7335109/',
    publication_date='2020-07-03',inspection_status='full_text_inspected',source_kind='primary_experiment',
    locator='Methods: Sample fabrication; Superconducting properties; Figure 7a,b; Source Data Figure 7 columns B,C')
source=dict(source_id='dobrovolskiy2020-nbc',raw_path='nbc/source.xls',sha256=digest,reference=ref,license='CC-BY-4.0',
    download_url='https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-020-16987-y/MediaObjects/41467_2020_16987_MOESM3_ESM.xls',
    attribution='Dobrovolskiy et al., Nature Communications 11,3291 (2020). Source numerical values preserved.')
s=xlrd.open_workbook(path).sheet_by_name('Figure 7')
points=[]
for i in range(3,s.nrows):
    t,y=s.cell_value(i,1),s.cell_value(i,2)
    if isinstance(t,(int,float)) and isinstance(y,(int,float)) and t>0 and math.isfinite(t) and math.isfinite(y):
        points.append(dict(temperature_k=t,value=y,source_locator=f"Source Data 'Figure 7'!B{i+1}:C{i+1}"))
conditions=dict(sample_id='dobrovolskiy2020:typical-microstrip',formula=None,sample_form='thin_film',
    phase='fcc Nb-C nanocrystalline microstrip with Ga/N impurities and insulating cap',pressure_GPa=None,
    field_T=None,t_min_K=min(p['temperature_k'] for p in points),t_max_K=max(p['temperature_k'] for p in points),method='resistivity')
curve=dict(curve_id='dobrovolskiy2020:Fig7ab',source_id=source['source_id'],material_id='Nb-C-FIBID-microstrip',
    specimen_id=conditions['sample_id'],series_id='dobrovolskiy2020:Fig7',observed_at=now,quantity='resistivity',unit='microohm cm',
    conditions=conditions,fixed_coordinates=dict(pressure_gpa=None,doping_fraction=None,strain=None,magnetic_field_t=None),
    normal_state_status='verified_normal',normal_state_evidence=dict(locator='Methods: Superconducting properties, Fig7a,b',
    statement='Published normal-state resistivity trace; only fixed 150–300 K region designated normal.',verified_range_k=[150.,300.]),
    points=points,measurement_run_id='dobrovolskiy2020:Fig7ab',trace_id="Source Data 'Figure 7' columns B:C",varied_axes=['temperature_k'],
    composition_proxy=dict(atomic_fractions={'C':.43,'Nb':.29,'Ga':.15,'N':.13},basis='EDS on thicker replica, not the measured microstrip',
                           eligible_as_exact_specimen_formula=False),
    primary_training_exclusion='Exact measured-specimen composition unknown; do not substitute pure NbC or replica EDS.')
payload=dict(material_id=curve['material_id'],observed_at=now,statement='Reported same trace measured Tc using 50% resistance drop; composition of measured microstrip unresolved.',
    observation_type='sample_superconductivity',assertion_status='source_checked',outcome=True,evidence_kind='measured_transition',tc_K=5.6,
    tc_criterion='resistive_midpoint',conditions=conditions,reference=ref,derived_from_curve_id=curve['curve_id'],
    measurement_run_id=curve['measurement_run_id'],trace_id=curve['trace_id'],raw_source_sha256=digest,varied_axes=['temperature_k'])
(ROOT/'nbc-registry.json').write_text(json.dumps({'sources':[source]},indent=2),encoding='utf-8')
(ROOT/'nbc-collection.json').write_text(json.dumps({'curves':[curve],'targets':[dict(target_id='dobrovolskiy2020:Tcmid',payload=payload)],
    'links':[], 'primary_training_exclusion':curve['primary_training_exclusion']},indent=2),encoding='utf-8')
print(json.dumps(dict(points=len(points),Tmin=conditions['t_min_K'],Tmax=conditions['t_max_K'],exact_composition_known=False)))
