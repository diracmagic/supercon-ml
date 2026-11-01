"""Portable stdlib extraction of downloaded source values; never fits or labels a model.

Run after fetch_sources.py. No smoothing, interpolation, digitization, clipping,
averaging, duplicate removal, or inferred unknown pressure/field. Original order is
preserved. Curves include superconducting outcomes and are NOT all precursors.
"""
from pathlib import Path
import csv, hashlib, json, math, re, statistics, xml.etree.ElementTree as ET, zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "normalized"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CURVES, TARGETS, SOURCES = [], [], {}


def source(key, doi, dataset_doi, title, url, license, date, notes):
    SOURCES[key] = dict(source_id=key, paper_doi=doi, dataset_doi=dataset_doi,
                        citation=title, accessed_url=url, inspection_status="full_text_inspected",
                        dataset_license=license, publication_date=date, notes=notes)


def numeric(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def tabular(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.reader(stream, delimiter=delimiter))


def xlsx(path):
    """Returns workbook sheet name -> sparse rows, resolving relationships correctly."""
    answer = {}
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(e.itertext()) for e in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        rels = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.find("s:sheets", NS):
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rel]
            member = target.lstrip("/") if target.startswith("/") else "xl/"+target
            rows = []
            with archive.open(member) as stream:
                for _, row in ET.iterparse(stream, events=["end"]):
                    if row.tag != "{"+NS["s"]+"}row":
                        continue
                    values = {}
                    for cell in row:
                        raw = cell.find("s:v", NS)
                        value = raw.text if raw is not None else "".join(cell.itertext())
                        if cell.attrib.get("t") == "s":
                            value = strings[int(value)]
                        letters = re.match("[A-Z]+", cell.attrib["r"])[0]
                        col = 0
                        for letter in letters:
                            col = 26*col + ord(letter)-64
                        values[col-1] = value
                    rows.append(values)
                    row.clear()
            answer[sheet.attrib["name"]] = rows
    return answer


def pairs(rows, x, y, start=1):
    values = []
    for row in rows[start:]:
        a = numeric(row.get(x) if isinstance(row, dict) else row[x] if x < len(row) else None)
        b = numeric(row.get(y) if isinstance(row, dict) else row[y] if y < len(row) else None)
        if a is not None and b is not None:
            values.append([a, b])
    return values


def curve(key, source_id, sample_id, formula, phase, path, locator, values, quantity, unit,
          *, pressure=None, field=None, notes=None, quality="verified_source_values", extra=None):
    assert values and all(len(x)==2 and all(math.isfinite(v) for v in x) for x in values)
    OUT.mkdir(exist_ok=True)
    file = OUT/(key+".json")
    payload = dict(curve_id=key, source_id=source_id, sample_id=sample_id, formula=formula,
                   phase=phase, quantity=quantity, unit=unit, temperature_unit="K",
                   pressure_gpa=pressure, magnetic_field_t=field, doping_fraction=None, strain=None,
                   source_locator=locator, original_path=path.relative_to(ROOT).as_posix(),
                   original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   value_status=quality, notes=notes or [],
                   data_columns=["temperature_k", "value"], data=values,
                   point_count=len(values), temperature_min_k=min(v[0] for v in values),
                   temperature_max_k=max(v[0] for v in values),
                   precursor_policy="full_curve_is_not_a_precursor; define absolute normal-state window before fitting",
                   training_eligible=False, training_eligibility_reason="pending scoped training policy and condition/target matching")
    if extra:payload.update(extra)
    file.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n", encoding="utf-8")
    summary = {k:v for k,v in payload.items() if k != "data"}
    summary["normalized_path"] = file.relative_to(ROOT).as_posix()
    summary["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    CURVES.append(summary)


def target(key, source_id, sample_id, formula, phase, tc, criterion, locator,
           *, pressure=None, field=None, uncertainty=None, notes=None, curve_ids=None):
    TARGETS.append(dict(target_id=key, source_id=source_id, sample_id=sample_id, formula=formula, phase=phase,
                        tc_K=tc, tc_criterion=criterion, source_locator=locator,
                        pressure_gpa=pressure, magnetic_field_t=field, tc_uncertainty_K=uncertainty,
                        curve_ids=curve_ids or [], notes=notes or [],
                        origin="paper_or_deposited_extracted_value", not_a_parent_potential_label=True))


def main():
    source("nbs2-2021", "10.1021/acsnano.1c07956", "10.5281/zenodo.5645160",
           "Wang et al. Superconducting 2D NbS2 Grown Epitaxially by Chemical Vapor Deposition. ACS Nano 15,18403–18410 (2021).",
           "https://pmc.ncbi.nlm.nih.gov/articles/PMC8614232/", "CC-BY-4.0", "2021-11-10",
           ["CSV data license differs from the paper's CC-BY-NC-ND license.", "Nominal NbS2; sulfur defects are reported, no exact per-device stoichiometry inferred."])
    folder = ROOT/"zenodo-5645160/original"
    for segment, filename, norm in [("broad", "Figure 3b-Long range R-T-2H-2H+3R-3R.csv", 200),
                                     ("transition", "Figure 3b inset-Short range R-T-2H-2H+3R-3R.csv", 10)]:
        path=folder/filename; rows=tabular(path)
        for i,(sample,phase,thick) in enumerate([("No28-dev4", "2H", 10), ("No18-dev3", "2H+3R",4), ("No18-dev2", "3R",3)]):
            curve("nbs2-"+sample+"-"+segment, "nbs2-2021", "nbs2-2021-"+sample, "NbS2", phase,
                  path, "Fig.3b"+(" inset" if norm==10 else "")+f" CSV column pair {i+1}", pairs(rows,2*i,2*i+1),
                  f"resistance_ratio_R_over_R{norm}K", "1", field=0,
                  notes=["Four-probe longitudinal resistance; normalized values are not ohm or intrinsic resistivity.", "Zero-field cooling; AC current 0.1 microampere. Measurement pressure not numerically stated."],
                  extra={"thickness_nm":thick,"normalization_temperature_k":norm})
    target("nbs2-No28-dev4-midpoint", "nbs2-2021", "nbs2-2021-No28-dev4", "NbS2", "2H",2.6,
           "resistive_midpoint_0.5_R_normal", "Results / Different Phases of NbS2, Fig.3b discussion",field=0,
           curve_ids=["nbs2-No28-dev4-broad","nbs2-No28-dev4-transition"])
    TARGETS.append(dict(target_id="nbs2-No18-dev2-no-transition",source_id="nbs2-2021",sample_id="nbs2-2021-No18-dev2",formula="NbS2",phase="3R",
                        tc_K=None,tc_criterion="no_transition_observed_above_Tmin",Tmin_K=1.4,pressure_gpa=None,magnetic_field_t=0,
                        source_locator="Results / Different Phases of NbS2, Fig.3b discussion",
                        notes=["Censored sample-specific observation; not Tc=0 and never a parent-potential negative."],not_a_parent_potential_label=True))

    source("mgb2-2025","10.1038/s44310-025-00084-3","10.5281/zenodo.15172735",
           "Sidorova et al. Quantum light detection in high-temperature superconducting nanowires. npj Nanophotonics 2,38 (2025).",
           "https://www.nature.com/articles/s44310-025-00084-3","CC-BY-4.0","2025-10-01",
           ["Device includes a 100 nm-wide nanowire and series 1 micrometre-wide inductor; total device resistance is not material resistivity.","Two segments of one device, not two materials; preserve overlap without counting as independent specimens."])
    path=ROOT/"zenodo-15172735/original/transition_temperature_data.csv";rows=tabular(path)
    for i in range(2):
        curve(f"mgb2-2025-device-segment{i+1}","mgb2-2025","mgb2-2025-device","MgB2","c-axis-oriented film",path,
              f"Supplementary Fig.1a; dataset README + transition_temperature_data.csv columns {2*i+1},{2*i+2}; Methods / Nanowire detector characteristics",pairs(rows,2*i,2*i+1),
              "device_resistance","ohm",notes=["Pressure and measurement field are not numerically reported; no zero is imputed.","8 nm film; nanowire and inductor transition temperatures differ."],extra={"thickness_nm":8})
    target("mgb2-2025-nanowire-transition","mgb2-2025","mgb2-2025-device","MgB2","c-axis-oriented film",35,
           None,"Methods / Nanowire detector characteristics; Supplementary Fig.1a: nanowire transition approximately 35 K",
           notes=["Approximate value; explicit onset/midpoint/zero-resistance criterion not found in inspected main text. Do not use for a criterion-specific target without clarification."])

    source("mgb2-2024","10.1038/s41467-024-47353-x","10.5281/zenodo.10514254",
           "Charaev et al. Single-photon detection using large-scale high-temperature MgB2 sensors at 20 K. Nature Communications 15 (2024).",
           "https://www.nature.com/articles/s41467-024-47353-x","CC-BY-4.0","2024-05-10",
           ["Raw Fig.1b workbook headers R,T contradict plotted axis/ranges; quarantine until column interpretation is explicitly accepted."])
    path=ROOT/"zenodo-10514254/original/Fig.1b.xlsx";rows=xlsx(path)["Sheet1"]
    curve("mgb2-2024-device-header-conflict","mgb2-2024","mgb2-2024-Fig1b-device","MgB2","film",path,
          "Fig.1b workbook A,B; first row declares R,T but numerical ranges/figure support T,R",pairs(rows,0,1),
          "device_resistance","ohm",quality="quarantined_conflicting_original_column_headers",
          notes=["Candidate interpretation A=temperature K, B=resistance ohm; original headers say A=R, B=T. Not certified for training.",
                 "Two-terminal 5 micrometre-wide meander device; contacts included. No interpolation, smoothing, or outlier clipping."],extra={"width_um":5})
    target("mgb2-2024-device-derivative","mgb2-2024","mgb2-2024-Fig1b-device","MgB2","film",37.6,
           "maximum_dR_dT","Results / Design and characterization, Fig.1b discussion",uncertainty=.3,
           notes=["Device value; parent film's 38.7 K is a separate specimen. Raw curve header conflict remains quarantined."],curve_ids=["mgb2-2024-device-header-conflict"])

    source("nbtin-2024","10.1038/s41598-024-81776-2","10.21979/N9/VH0WLV",
           "Dong et al. Establishing an end-to-end workflow for SNSPD fabrication and characterization. Scientific Reports 14,30891 (2024).",
           "https://pmc.ncbi.nlm.nih.gov/articles/PMC11680598/","CC-BY-NC-4.0","2024-12-28",
           ["Original XLSX repository MD5 verified. Ingested TSV is an additional repository transformation.","Measurement pressure/field unreported; deposition 2.5 mTorr is not measurement pressure."])
    path=ROOT/"ntu-nbtin-2024/ingested-tab/Fig. 1d.tab";rows=tabular(path,"\t")
    curve("nbtin-2024-Fig1d","nbtin-2024","nbtin-2024-Fig1d-film","Nb0.62Ti0.38N","fcc NbTiN film",path,
          "Fig.1d, first x1/y1(data) pair; fit columns deliberately excluded",pairs(rows,0,1),"sheet_resistance","ohm/square",
          notes=["Nominal metal composition set by deposition-rate balance; not a per-device chemical assay.",
                 "Only one room-temperature endpoint at 296 K beyond the dense low-T section. This is not a broad dense 150–300 K curve."],
          extra={"thickness_nm":7,"deposition_pressure_mTorr":2.5,"N2_flow_sccm":3.5})
    for tc,criterion in [(8.66,"half_of_maximum_resistance"),(8.51,"2D_fluctuation_conductivity_fit")]:
        target("nbtin-2024-"+str(tc),"nbtin-2024","nbtin-2024-Fig1d-film","Nb0.62Ti0.38N","fcc NbTiN film",tc,criterion,
               "Optimization of deposition parameters, Fig.1d discussion",curve_ids=["nbtin-2024-Fig1d"])

    source("sn-2025","10.1103/PhysRevB.111.104513","10.5281/zenodo.14759622",
           "Sasaki et al. Enhancement of superconductivity in thin films of Sn under high pressure. Physical Review B 111,104513 (2025).",
           "https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevB.111.104513/fulltext#page=1","CC-BY-4.0","2025-03-27",
           ["Resistance rather than resistivity; compression/decompression and pressure medium remain distinct conditions.","Possible 11 K anomaly discussed separately; not promoted to a confirmed Tc."])
    folder=ROOT/"zenodo-14759622/original"
    sn4=xlsx(folder/"fig4.xlsx");sn6=xlsx(folder/"fig6.xlsx")
    for name,rows,filename,p,phase,medium,loc in [
        ("sn-run1-broad-2p5",sn4["4a inset"],"fig4.xlsx",2.5,"beta-Sn","MgO-epoxy/nonhydrostatic","Fig.4a inset; p.104513-4 caption; columns A/B"),
        ("sn-glycerol-broad-9",sn6["6a"],"fig6.xlsx",9,"beta/gamma phase coexistence discussed","glycerol/quasihydrostatic","Fig.6a; p.104513-5; columns A/B")]:
        curve(name,"sn-2025","sn-2025-"+("run1"if p==2.5 else"glycerol"),"Sn",phase,folder/filename,loc,pairs(rows,0,1,1 if name.startswith("sn-run1") else 2),
              "resistance","ohm",pressure=p,field=0 if p==2.5 else None,
              notes=["Four-terminal transport. Pressure measured at room temperature; low-T pressure not separately inferred.","One pressure state is not a new independent material."],extra={"pressure_medium":medium,"pressure_path":"compression"})
    for sheet,p,history in [("4a",2.5,"compression"),("4b",10.5,"decompression_after_20_GPa")]:
        rows=sn4[sheet]
        for col in sorted(rows[0]):
            label=str(rows[0].get(col,""));match=re.fullmatch(r"([\d.]+) T",label)
            if not match:continue
            field=float(match[1]);name=f"sn-run1-{sheet}-{field:g}T"
            curve(name,"sn-2025","sn-2025-run1","Sn","beta-Sn"if p==2.5 else"gamma-Sn",folder/"fig4.xlsx",
                  "Fig."+sheet+f" {label}, workbook column pair starting {col+1}",pairs(rows,col,col+1,2),"resistance","ohm",pressure=p,field=field,
                  extra={"pressure_medium":"MgO-epoxy/nonhydrostatic","pressure_path":history})
    # Experimental extracted Tc values are the first four pairs. The following pairs are theory curves.
    rows=sn4["4c"]
    for col,p,criterion in [(0,2.5,"resistive_onset"),(2,2.5,"resistive_midpoint"),(4,10.5,"resistive_onset"),(6,10.5,"resistive_midpoint")]:
        for i,(tc,b) in enumerate(pairs(rows,col,col+1,2)):
            target(f"sn-run1-{p}-{criterion}-{i}","sn-2025","sn-2025-run1","Sn","beta-Sn"if p==2.5 else"gamma-Sn",tc,criterion,
                   f"Fig.4c, fig4.xlsx sheet4c columns {col+1}/{col+2}, source numeric row {i+3}",pressure=p,field=b,
                   notes=["Onset and midpoint are distinct target definitions; keep pressure history. Experimental extracted point, not WHH fitted grid."])

    # Source data present but deliberately outside present broad-T training handoff.
    source("hea-2022","10.1038/s41598-022-16355-4","10.5281/zenodo.6673464",
           "Leung et al. Evidence for isotropic s-wave superconductivity in high-entropy alloys. Scientific Reports 12,12773 (2022).",
           "https://access.archive-ouverte.unige.ch/access/metadata/ba192a83-71ef-4339-b7b6-1f53fd8e57c0/download","CC-BY-4.0","2022-07-27",
           ["Two measured alloy groups x=.35/.71, nominal file names .4/.75; not many independent materials.","ZFC/FC are low-T magnetization, no broad-T normal resistance curves in this package."])
    for nominal,actual,tc in [("0p4",.35,6.7),("0p75",.71,4.3)]:
        path=ROOT/f"zenodo-6673464/extracted/archive/Fig 1ab/ZFCFC/ZFCFC13102021x{nominal}.csv";rows=tabular(path)
        values=pairs(rows,0,1)
        for mode,start,stop,field in [("ZFC",0,200,.0005),("FC",200,400,.005)]:
            curve(f"hea-x{actual}-{mode}","hea-2022",f"hea-2022-x{actual}",f"(TaNb){{{1-actual:g}}}(ZrHfTi){{{actual:g}}}","single-phase bcc HEA",path,
                  f"Fig.1a/b; CSV rows {start+2}–{stop+1}; author fig1ab.m separates rows1:200/201:400",values[start:stop],
                  "magnetic_moment","emu",field=field,
                  notes=["Raw M preserved; no volume-normalized susceptibility synthesized. Field from Fig.1 caption, applied in-plane."])
        target(f"hea-x{actual}-Tc","hea-2022",f"hea-2022-x{actual}","TaNbZrHfTi","bcc",tc,None,
               "p.2 Results, Fig.1a/b; extracted susceptibility transition; exact onset/midpoint threshold unspecified",uncertainty=.1,
               notes=["Do not silently merge a susceptibility transition with resistive midpoint targets."])

    source("nbse2-2020","10.1103/PhysRevResearch.2.043392","10.5523/bris.3i7a3mzyfbrrp2j871ykh846v0",
           "Moulding et al. Absence of superconducting dome at the charge-density-wave quantum phase transition in 2H-NbSe2. Physical Review Research 2,043392 (2020).",
           "https://orca.cardiff.ac.uk/id/eprint/138618/1/PhysRevResearch.2.043392.pdf",
           "Non-Commercial Government Licence for public sector information (repository landing); not paper's CC-BY", "2020-12-18",
           ["Deposited Hall/volume susceptibility and extracted transitions; no original longitudinal rho(T) curve in deposit.",
            "Sample numbering differs between deposited README and paper figure captions. No strict cross-quantity sample join is certified."])
    folder=ROOT/"bristol-nbse2-2020/extracted"
    for path in sorted((folder/"Fig1a").glob("RH_vs_T_*.dat")):
        p=float(re.search(r"T_([\d.]+)GPa",path.name)[1])
        curve(f"nbse2-Hall-{p:g}GPa","nbse2-2020","nbse2-2020-Fig1a-sample1","NbSe2","2H single crystal",path,
              "Fig.1a; original two-column header and README, fixed10T; Methods II.A–C",pairs(tabular(path,"\t"),0,1,2),
              "hall_coefficient","mm^3/C",pressure=p,field=10,
              notes=["10% systematic thickness-related Hall uncertainty reported; not converted into extra materials.","Glycerol pressure medium; nominal pressure measured at room temperature."],
              extra={"field_orientation":"crystallographic c axis","current_A":.001,"pressure_medium":"glycerol"})
    pressures=[0,1,1.6,2.5,3.1,3.4,3.6,4,4.4,4.9,5.6,6.2,6.4]
    for letter,p in zip("abcdefghijklm",pressures):
        path=folder/f"Fig3a/ChiT_{letter}.dat"
        curve(f"nbse2-chi-{p:g}GPa","nbse2-2020","nbse2-2020-Fig3a-caption-sample2","NbSe2","2H single crystal",path,
              "Fig.3a caption p.043392-4; README pressure-to-letter map",pairs(tabular(path,"\t"),0,1),
              "volume_magnetic_susceptibility","1",pressure=p,field=.0005,
              notes=["Measured on warming after zero-field cooling. Paper Fig3a caption calls this sample2; deposited Tc table README calls its sample1. Keep separate.",
                     "Pressure-letter map does not equal the deposited Tc pressure grid; do not nearest-match Tc across samples."],
              extra={"pressure_medium":"argon","measurement_path":"warming_after_zero_field_cooling"})
    path=folder/"Fig2b/Tc_chi.dat"; rows=tabular(path,"\t")
    for i,row in enumerate(rows[2:]):
        p,tc=numeric(row[0]),numeric(row[2])
        if p is None or tc is None:continue
        target(f"nbse2-extracted-Tc-{i}","nbse2-2020","nbse2-2020-Tc-table-sample-identity-unresolved","NbSe2","2H",tc,
               "susceptibility_10_percent_normalized_step_near_onset",
               f"Fig.2b / Tc_chi.dat numeric row{i+3}; Methods II.D p.043392-2 defines10%step",pressure=p,field=.0005,
               uncertainty=numeric(row[3]),notes=["Sample identity unresolved: repository README and paper captions disagree. Do not attach automatically to Hall or Fig3a curve.",
                                                  "Fig3b is a duplicate of Fig2b; included once. RPA theory file excluded."])
        TARGETS[-1]["pressure_uncertainty_gpa"]=numeric(row[1])
        TARGETS[-1]["strict_sample_match_eligible"]=False
    manifest=dict(schema_version=1,purpose="Original-curve handoff for scientific review; not model training or feedback events",
                  retrieved_on="2026-11-01",normalization="finite numeric paired cells only; original order and all values preserved; no smoothing or digitization",
                  independence="Group by sample_id and paper; temperature/field/pressure points are not independent materials",
                  sources=list(SOURCES.values()),curves=CURVES,targets=TARGETS,
                  exclusions=[{"dataset_doi":"10.5281/zenodo.16274340","reason":"NbN 2 K THz conductivity vs frequency/B, plus theory: not broad-T normal-state R(T)"},
                              {"dataset_doi":"10.5281/zenodo.10125758","reason":"NbTiN deposition summary table; primary-paper link not resolved, not admitted"},
                              {"dataset_doi":"10.5281/zenodo.20154939","reason":"PtSb raw figure-source retained; mechanism/scope and detailed target conditions not certified in this handoff"}])
    (ROOT/"scientific-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (ROOT/"tc-targets.json").write_text(json.dumps(TARGETS,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"curves":len(CURVES),"points":sum(c["point_count"]for c in CURVES),"targets":len(TARGETS),
                      "sources":len(SOURCES),"training_records_created":0}))
    for c in CURVES:print(c["curve_id"],c["point_count"],c["temperature_min_k"],c["temperature_max_k"])


if __name__ == "__main__":main()
