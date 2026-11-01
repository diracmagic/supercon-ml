"""Extract authors' Bi and Ta1.6Te numerical data with source-row identities."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile
from inspect_xlsx import read_sheets

ROOT=Path(__file__).parent
INSPECTED='2026-11-01T12:57:19+00:00'
SOURCES=[]
CURVES=[]
TARGETS=[]
LINKS=[]
OMITTED=[]

def source(identifier,path,doi,url,date,locator,license,**extra):
    rec=dict(source_id=identifier,raw_path=path,sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),
             reference=dict(doi=doi,url=url,publication_date=date,locator=locator,
                            inspection_status='full_text_inspected',source_kind='primary_experiment'),
             license=license,**extra)
    SOURCES.append(rec)
    return rec

def curve(identifier,src,formula,specimen,phase,quantity,unit,pressure,field,points,locator,normal=True):
    condition=dict(sample_id=specimen,formula=formula,sample_form='bulk',phase=phase,
                   pressure_GPa=pressure,field_T=field,t_min_K=min(p['temperature_k'] for p in points),
                   t_max_K=max(p['temperature_k'] for p in points),method='resistivity' if 'resistivity' in quantity else 'magnetic_susceptibility')
    row=dict(curve_id=identifier,source_id=src['source_id'],material_id=formula,specimen_id=specimen,
             series_id=src['reference']['doi']+':transport-pressure-series' if formula=='Bi' and 'resistivity' in quantity else identifier,
             observed_at=INSPECTED,quantity=quantity,unit=unit,conditions=condition,
             fixed_coordinates=dict(pressure_gpa=pressure,doping_fraction=None,strain=None,magnetic_field_t=field),
             normal_state_status='verified_normal' if normal else 'unknown',points=points,
             measurement_run_id=identifier,trace_id=locator,varied_axes=['temperature_k'])
    if normal:
        row['normal_state_evidence']=dict(locator=locator+'; paper Results and figure caption',
            statement='Author-reported normal-state transport in the absolute 150–300 K region. Only measured points in this range are marked verified normal.',verified_range_k=[150.,300.])
    CURVES.append(row)
    return row

def target(c,src,tc,criterion,locator,approx=False):
    ident=c['curve_id']+':Tc'
    meta=dict(measurement_run_id=c['measurement_run_id'],trace_id=c['trace_id'],raw_source_sha256=src['sha256'],varied_axes=c['varied_axes'])
    payload=dict(material_id=c['material_id'],observed_at=INSPECTED,
        statement='Measured sample transition reported in the inspected primary paper; historical evidence, not a prospective model discovery.',
        observation_type='sample_superconductivity',assertion_status='source_checked',outcome=True,
        evidence_kind='measured_transition',tc_K=tc,tc_criterion=criterion,tc_is_approximate=approx,
        conditions=copy.deepcopy(c['conditions']),reference=dict(src['reference'],locator=locator),
        derived_from_curve_id=c['curve_id'],**meta)
    TARGETS.append(dict(target_id=ident,payload=payload))
    LINKS.append(dict(curve_id=c['curve_id'],target_id=ident,same_physical_specimen=True,
        assertion_status='source_checked',specimen_id=c['specimen_id'],curve_sample_id=c['conditions']['sample_id'],
        target_sample_id=c['conditions']['sample_id'],source_locator=locator,
        scope='same_run_measured_tc',same_raw_trace=True,**meta))

bi=source('brown2018-bi-source','bi_pressure/source.zip','10.1126/sciadv.aao4793',
    'https://doi.org/10.17863/CAM.18197','2018-04-13','SupportingDataForPublication.zip headers; paper Figs.1–4 and Methods',
    'CC-BY-NC-ND-4.0',distribution='Local research extraction only; do not redistribute adapted numeric data',
    preprocessing_note='Published resistivity values were scaled at 300 K to literature values; not unprocessed instrument voltage.')
with ZipFile(ROOT/bi['raw_path']) as z:
    names=[n for n in z.namelist() if n.startswith('SupportingDataForPublication/') and n.endswith('.dat')
           and (('/Fig1/' in n) or ('/Fig3/Bip' in n) or ('/Fig4/Fig4a/' in n))]
    for name in names:
        lines=z.read(name).decode().splitlines()
        header=' '.join(l for l in lines if l.startswith('#'))
        p=float(re.search(r'(?:at |# )(\d+(?:\.\d+)?) kbar',header).group(1))/10.
        b=float(re.search(r'(?:field of |field of)(\d+(?:\.\d+)?)\s*T',header).group(1)) if 'resistivity' in header.lower() else .002
        points=[]
        for number,line in enumerate(lines,1):
            if not line.strip() or line.startswith('#'): continue
            values=[float(v) for v in line.split()]
            if len(values)!=2 or not all(math.isfinite(v) for v in values) or values[0]<=0:
                OMITTED.append(dict(source_id=bi['source_id'],locator=f'{name}:line {number}',reason='nonfinite or nonpositive-temperature source row',source_text=line))
                continue
            points.append(dict(temperature_k=values[0],value=values[1],source_locator=f'{name}:line {number}; columns T,Rho' if '/Fig4/' not in name else f'{name}:line {number}; columns T,M/H'))
        ident='brown2018:'+name.split('/')[-1].replace('.dat','').replace(' ','_')
        magnetic='/Fig4/' in name
        phase='Bi-III' if ('Bi-3' in header or p>=2.6) else ('Bi-I/Bi-II temperature-dependent phase at 2.53 GPa' if p==2.53 else 'Bi-I')
        row=curve(ident,bi,'Bi','brown2018:'+('magnetic-29kbar' if magnetic else 'transport:'+str(p)+'GPa'),phase,
                  'magnetic_susceptibility' if magnetic else 'resistivity','SI M/H dimensionless' if magnetic else 'microohm cm',
                  p,b,points,name,normal=not magnetic)
        row['conditions']['method']='magnetic_susceptibility' if magnetic else 'resistivity'
        row['measurement_details']='SQUID magnetometry' if magnetic else 'four-point AC resistivity, calibrated at 300 K to published values'
        row['source_sample_identity_note']='Curator-namespaced measurement-series identity; same source across pressures, not assumed independent specimens.'
        if name.endswith('/Bip27s.dat'):
            # Fig.2 Bi0Ts is the repeated low-temperature part of Fig.1's trace.
            low=[]
            for line in z.read('SupportingDataForPublication/Fig2/Bi0Ts.dat').decode().splitlines():
                if line and not line.startswith('#'): low.append(tuple(map(float,line.split())))
            available={(pnt['temperature_k'],pnt['value']) for pnt in points}
            exact=sum(pair in available for pair in low if all(math.isfinite(v) for v in pair))
            row['duplicate_crosscheck']=dict(other_trace='Fig2/Bi0Ts.dat',exact_overlap_points=exact,
                compared_points=len(low),other_trace_sha256=hashlib.sha256(z.read('SupportingDataForPublication/Fig2/Bi0Ts.dat')).hexdigest())
            target(row,bi,7.05,'resistive_midpoint','Paper Fig.2 and Results, Fig.3 midpoint criterion; raw Fig1/Bip27s.dat contains this same transition; Fig2/Bi0Ts.dat numerical overlap audited',approx=True)

ta=source('tokumoto2024-ta16te-source','ta16te/source-publisher.xlsx','10.1038/s41467-024-45952-2',
    'https://doi.org/10.1038/s41467-024-45952-2','2024-03-01','Source Data Figure 2a,b; Electrical resistivity; Physical property measurements',
    'CC-BY-4.0',download_url='https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-024-45952-2/MediaObjects/41467_2024_45952_MOESM6_ESM.xlsx',
    attribution='Tokumoto, Hamano, Nakagawa et al. Nature Communications 15,1529 (2024). Numerical transcription of source table, original normalization retained.')
sheets=dict(read_sheets(ROOT/ta['raw_path']))
points=[]
for data in sheets['Figure 2a,b'][1:]:
    tkey=next(k for k in data if k.startswith('A'))
    rownum=tkey[1:]
    points.append(dict(temperature_k=data[tkey],value=data['B'+rownum],source_locator=f"Source Data 'Figure 2a,b'!A{rownum}:B{rownum}"))
c=curve('tokumoto2024:rho',ta,'Ta1.6Te','tokumoto2024:transport-piece','dodecagonal quasicrystal majority, minor approximant impurity',
        'normalized_resistivity','rho/rho(300 K)',None,None,points,"Source Data 'Figure 2a,b' columns A:B")
c['conditions']['method']='resistivity'
c['sample_notes']='Transport cut piece, cross section 2–3 mm × 2–3 mm, length 5–6 mm; not the 95.64 mg magnetic or 26.09 mg calorimetry specimen.'
c['normalization_reference']='300 K normal-state resistivity; not Tc or superconducting-state normalization'
target(c,ta,.98,'resistive_midpoint','Electrical resistivity text, Fig.2a,b: rho(Tc_mid)=0.5*rho(1.1 K); Source Data same Figure 2a,b A:B trace')

(ROOT/'root-registry.json').write_text(json.dumps(dict(sources=SOURCES),indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
(ROOT/'root-collection.json').write_text(json.dumps(dict(curves=CURVES,targets=TARGETS,links=LINKS,omitted_rows=OMITTED),indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
print(json.dumps(dict(curves=len(CURVES),points=sum(len(c['points']) for c in CURVES),targets=len(TARGETS),omitted=len(OMITTED),duplicates=[c.get('duplicate_crosscheck') for c in CURVES if c.get('duplicate_crosscheck')]),indent=2))
