"""Adapt inspected numeric originals to ml.normal_state, without writing a ledger.

source_root is this directory's parent (work/normal-state-collection). Original
files and all curves are retained. A schema-valid curve is not automatically a
fit-ready feature or a valid Tc join; the unchanged public extractor decides.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, copy, hashlib, json, sys
import normalize_sources as N

ROOT=N.ROOT
SOURCE_ROOT=ROOT.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",type=Path,default=SOURCE_ROOT.parent/"supercon-ml")
    parser.add_argument("--observed-at", help="Reuse a documented frozen inspection timestamp when reproducing this curation")
    args=parser.parse_args()
    sys.path.insert(0,str(args.repo.resolve()))
    from ml import normal_state as M, feedback as F
    policy=json.loads((SOURCE_ROOT/"protocol/normal-state-policy.json").read_text())
    M.validate_policy(policy)
    manifest=json.loads((ROOT/"scientific-manifest.json").read_text(encoding="utf-8"))
    source_index={s["source_id"]:s for s in manifest["sources"]}
    timestamp=args.observed_at or datetime.now(timezone.utc).isoformat()
    sources,curves,targets,links,omitted=[],[],[],[],[]
    registry_by_path={}

    def registry_for(path,source,locator):
        relative=path.relative_to(SOURCE_ROOT).as_posix()
        if relative in registry_by_path:return registry_by_path[relative]
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        sid="transport:"+source["source_id"]+":"+digest[:16]
        reference=dict(doi=source["paper_doi"],url="https://doi.org/"+source["dataset_doi"],
                       publication_date=source["publication_date"],locator=locator,
                       inspection_status="full_text_inspected",source_kind="primary_experiment",
                       accessed_url=source["accessed_url"],dataset_doi=source["dataset_doi"],
                       citation=source["citation"])
        sources.append(dict(source_id=sid,raw_path=relative,sha256=digest,reference=reference,
                            license=source["dataset_license"],distribution="Preserve dataset-specific license; no blanket redistribution authorization",
                            source_notes=source["notes"]))
        registry_by_path[relative]=sid
        return sid

    # Start from the audited normalized index. The conflicting MgB2 workbook is
    # deliberately not given a schema-valid normal-state assertion.
    for summary in manifest["curves"]:
        c=json.loads((ROOT/summary["normalized_path"]).read_text(encoding="utf-8"))
        if c["value_status"]!="verified_source_values":
            omitted.append(dict(curve_id=c["curve_id"],reason=c["value_status"],
                                retained_audit_path=(ROOT/summary["normalized_path"]).relative_to(SOURCE_ROOT).as_posix()))
            continue
        source=source_index[c["source_id"]]
        path=ROOT/c["original_path"]
        # The checksum-verified original XLSX binds NTU, with equality below to
        # Dataverse's ingested TSV numeric data. Do not use the TSV's different MD5.
        if c["curve_id"]=="nbtin-2024-Fig1d":
            path=ROOT/"ntu-nbtin-2024/original/Fig. 1d.xlsx"
            sheets=N.xlsx(path)
            raw_rows=next(iter(sheets.values()))
            assert N.pairs(raw_rows,0,1)==c["data"],"NTU original/ingested values differ"
        sid=registry_for(path,source,c["source_locator"])
        quantity=c["quantity"]
        normalization={"kind":"none"}
        if quantity.startswith("resistance_ratio"):
            quantity="normalized_resistance"
            normalization={"kind":"fixed_reference_temperature","reference_temperature_k":c["normalization_temperature_k"]}
        quantity={"device_resistance":"resistance","sheet_resistance":"resistance",
                  "volume_magnetic_susceptibility":"magnetic_susceptibility","magnetic_moment":"magnetization"}.get(quantity,quantity)
        formula=None if c["source_id"]=="hea-2022" else c["formula"]
        material="TaNbZrHfTi" if formula is None else formula
        conditions=dict(sample_id=c["sample_id"],formula=formula,sample_form="single crystal"if c["source_id"]=="nbse2-2020"else"thin film",
                        phase=c["phase"],pressure_GPa=c["pressure_gpa"],field_T=c["magnetic_field_t"],
                        t_min_K=c["temperature_min_k"],t_max_K=c["temperature_max_k"],method=quantity)
        # Every response value remains unchanged. Individual indices identify
        # paired numeric entries under an explicit original file/column locator.
        points=[dict(temperature_k=t,value=v,source_locator=f"{path.name}: {c['source_locator']}; finite numeric pair index {i}")for i,(t,v)in enumerate(c["data"])]
        if c["curve_id"] in {"sn-run1-broad-2p5","sn-glycerol-broad-9"}:
            sheet="4a inset"if c["curve_id"]=="sn-run1-broad-2p5"else"6a"
            offset=2 if sheet=="4a inset"else 3
            for i,point in enumerate(points):point["source_locator"]=f"{path.name} sheet '{sheet}' row {i+offset}, columns A=T(K), B=R(Ohm)"
        verified=quantity in M.TRANSPORT and c["temperature_max_k"]>=150
        row=dict(curve_id=c["curve_id"],source_id=sid,material_id=material,specimen_id=c["sample_id"],
                 series_id=c["source_id"]+":"+c["sample_id"],observed_at=timestamp,quantity=quantity,unit=c["unit"],
                 conditions=conditions,fixed_coordinates=dict(pressure_gpa=c["pressure_gpa"],doping_fraction=None,strain=None,magnetic_field_t=c["magnetic_field_t"]),
                 normal_state_status="verified_normal"if verified else"unknown",normalization=normalization,
                 points=points,measurement_run_id=c["curve_id"],trace_id=c["original_path"]+"::"+c["source_locator"],
                 varied_axes=["temperature_k"],sample_notes=c["notes"],source_curve_id=c["curve_id"])
        if verified:
            row["normal_state_evidence"]=dict(locator=c["source_locator"],
                 statement="Inspected primary transport text/figure places superconducting transitions below 50 K and reports the higher-temperature curve as normal transport; verification applies only to the fixed absolute window, not the whole trace.",
                 verified_range_k=[150.,300.])
        curves.append(row)

    # The PtSb deposit is explicitly author-extracted figure-source numerical
    # data, not a digitization performed by this collector.
    pt_source=dict(source_id="ptsb-2026",paper_doi="10.1103/zjt7-88m9",dataset_doi="10.5281/zenodo.20154939",
                   citation="Müller et al. Superconductivity in epitaxial PtSb(0001) thin films. Physical Review Materials 10,094801 (2026).",
                   publication_date="2026-09-04",accessed_url="https://journals.aps.org/prmaterials/pdf/10.1103/zjt7-88m9",
                   dataset_license="CC-BY-4.0",notes=["Author-extracted figure-source values, not instrument-native data; no collector digitization.",
                   "Pairing mechanism is not inferred from type-II behavior. This is measured-sample transport, not a DFT electron-phonon truth label."])
    path=ROOT/"zenodo-20154939/extracted/datafiles/Figure2a.txt"
    raw=[]
    for i,line in enumerate(path.read_text().splitlines(),1):
        if line.startswith("#"):continue
        parts=line.split()
        if len(parts)==2 and all(N.numeric(v)is not None for v in parts):raw.append((i,float(parts[0]),float(parts[1])))
    cid="ptsb-2026-Fig2a-30nm";specimen="ptsb-2026-Fig2a-30nm-device"
    sid=registry_for(path,pt_source,"Fig.2a; p.094801-3 III.B; original Figure2a.txt headers")
    conditions=dict(sample_id=specimen,formula="PtSb",sample_form="epitaxial thin film",phase="NiAs-type P63/mmc PtSb(0001)",
                    pressure_GPa=None,field_T=0.,t_min_K=min(x[1]for x in raw),t_max_K=max(x[1]for x in raw),method="four-probe resistivity")
    pt_curve=dict(curve_id=cid,source_id=sid,material_id="PtSb",specimen_id=specimen,series_id="ptsb-2026-thickness-series",observed_at=timestamp,
        quantity="resistivity",unit="microohm cm",conditions=conditions,
        fixed_coordinates=dict(pressure_gpa=None,doping_fraction=None,strain=None,magnetic_field_t=0.),
        normal_state_status="verified_normal",normal_state_evidence=dict(locator="Paper p.094801-3 III.B, Fig.2a and dataset column header",
         statement="Paper explicitly calls rho(2 K)=10.1 microohm cm normal-state and gives RRR=rho(300 K)/rho(2 K) approximately3; the 150–300 K part is normal transport.",verified_range_k=[150.,300.]),
        points=[dict(temperature_k=t,value=v,source_locator=f"Figure2a.txt:line {i}; temperature K / rho microohm cm")for i,t,v in raw],
        measurement_run_id=cid,trace_id="Figure2a.txt:columns1,2",varied_axes=["temperature_k"],normalization={"kind":"none"},
        sample_notes=["30 nm PtSb on SrF2(111), four-probe Hall-bar device.","Original source contains small negative SC-region instrumental values; retained, not clipped. They lie outside frozen precursor window.",
                      "Text Fig2a gives1.72K midpoint; TableI rounds 30nm value to1.71K. Use the explicitly linked Fig2a text value and retain discrepancy."],thickness_nm=30)
    curves.append(pt_curve)
    nb_source=dict(source_id="nbse2-hebs-2024",paper_doi="10.1021/acs.nanolett.3c04493",dataset_doi="10.5281/zenodo.10613828",
        citation="Shein et al. Fundamental Limits of Few-Layer NbSe2 Microbolometers at Terahertz Frequencies. Nano Letters24,2282–2288 (2024).",
        publication_date="2024-02-12",accessed_url="https://www.hse.ru/data/2026/04/01/230362828/%E2%84%962.pdf",
        dataset_license="CC-BY-4.0",notes=["Author-deposited data.zip Fig1 R_T, two-terminal device resistance with approximately27ohm contact residual.",
        "Institutional author proof read, not publisher-paginated final. No precise midpoint definition found; no primary target constructed."])
    path=ROOT/"zenodo-10613828/extracted/data/Fig 1/R_T.txt"
    values=N.pairs(N.tabular(path,"\t"),0,1)
    nb_cid="nbse2-hebs-2024-Fig1c";specimen="nbse2-hebs-2024-Fig1c-device"
    sid=registry_for(path,nb_source,"Fig.1c full R(T), Methods/results p.B lines98–118; data.zip Fig1/R_T.txt and info.txt")
    conditions=dict(sample_id=specimen,formula="NbSe2",sample_form="few-layer microwire",phase=None,pressure_GPa=None,field_T=None,
        t_min_K=min(t for t,v in values),t_max_K=max(t for t,v in values),method="two-terminal resistance")
    curves.append(dict(curve_id=nb_cid,source_id=sid,material_id="NbSe2",specimen_id=specimen,series_id="nbse2-hebs-2024-device-series",
        observed_at=timestamp,quantity="resistance",unit="ohm",conditions=conditions,
        fixed_coordinates=dict(pressure_gpa=None,doping_fraction=None,strain=None,magnetic_field_t=None),
        normal_state_status="verified_normal",normal_state_evidence=dict(locator="Author-proof p.B lines98–118, Fig1c bottom inset",
         statement="Paper explicitly reports standard metallic resistance-temperature behavior in the broad normal-state inset; the observed superconducting transition is approximately6.5K, far below fixed150–300K region.",verified_range_k=[150.,300.]),
        points=[dict(temperature_k=t,value=v,source_locator=f"data.zip:Fig 1/R_T.txt line{i+2}, columns T(K)/R(Ohm)")for i,(t,v)in enumerate(values)],
        measurement_run_id=nb_cid,trace_id="data.zip:Fig 1/R_T.txt:columns1,2",varied_axes=["temperature_k"],normalization={"kind":"none"},
        sample_notes=["Raw two-terminal device R includes contacts; no contact subtraction or conversion to intrinsic resistivity.",
        "Four devices mentioned in paper, but deposited Fig1 R_T is only one identified full curve. It is one sample, not four.",
        "Tc approximately6.5K and middle-transition R approximately50ohm mentioned; exact50%normal-state or baseline-corrected criterion unspecified, so no resistive_midpoint label."]))
    index={c["curve_id"]:c for c in curves}

    def add_target(cid,tc,criterion,locator,*,scope="same_run_measured_tc",approximate=False,note=None,key=None):
        c=index[cid];s=next(s for s in sources if s["source_id"]==c["source_id"])
        tid=key or cid+":"+criterion
        payload=dict(material_id=c["material_id"],observed_at=timestamp,statement="Inspected historical experimental sample Tc; not a model prediction or prospective discovery.",
                     observation_type="sample_superconductivity",assertion_status="source_checked",outcome=True,evidence_kind="measured_transition",
                     tc_K=tc,tc_criterion=criterion,tc_is_approximate=approximate,conditions=copy.deepcopy(c["conditions"]),reference=copy.deepcopy(s["reference"]))
        payload["reference"]["locator"]=locator
        # Preserve the response quantity/unit separately; the feedback schema's
        # established method vocabulary calls electrical SC evidence resistivity.
        payload["conditions"]["method"]="resistivity"
        if note:payload["curation_note"]=note
        link=dict(curve_id=cid,target_id=tid,same_physical_specimen=True,assertion_status="source_checked",specimen_id=c["specimen_id"],
                  curve_sample_id=c["conditions"]["sample_id"],target_sample_id=c["conditions"]["sample_id"],source_locator=locator,scope=scope)
        if scope=="same_run_measured_tc":
            binding=dict(measurement_run_id=c["measurement_run_id"],trace_id=c["trace_id"],raw_source_sha256=s["sha256"],varied_axes=c["varied_axes"])
            payload.update(binding,derived_from_curve_id=cid)
            link.update(binding,same_raw_trace=True)
        targets.append(dict(target_id=tid,payload=payload))
        links.append(link)

    add_target(cid,1.72,"resistive_midpoint","Published paper p.094801-3 III.B, Fig.2a:50%rho_n(2K) for this30nm device; same full Figure2a.txt trace contains transition and broad-T curve",
               note="TableI lists1.71K for30nm; retained source discrepancy, not silently substituted.")
    add_target("nbs2-No28-dev4-broad",2.6,"resistive_midpoint","Primary paper Fig.3b/Different Phases: R(Tc)=0.5R_N; same2H10nm No28_dev4 CSVpair1 contains both transition and high-T points")
    # The high-T inset and low-T field scan have different sampling grids. P and
    # B are known, so use genuine specimen/condition matching, not a false claim
    # that their data rows are the identical raw trace.
    add_target("sn-run1-broad-2p5",3.851,"resistive_midpoint","Fig.4a inset and Fig.4c: run1 beta-Sn2.5GPa/B0; fig4.xlsx sheet4c C3=3.851K. Main/inset trace grids differ; same film and declared conditions, no exact-trace assertion.",
               scope="same_specimen_condition_matched",key="sn-run1-broad-2p5:midpoint")
    add_target("sn-run1-broad-2p5",4.059,"resistive_onset","Fig.4c fig4.xlsx sheet4c A3=4.059K; separate onset target, excluded from midpoint primary cohort",
               scope="same_specimen_condition_matched",key="sn-run1-broad-2p5:onset")
    targets[-1]["primary_midpoint_target_eligible"]=False
    audit_only_links=[links.pop()]
    omitted.extend([dict(source_id="mgb2-2025",reason="No precise Tc criterion in inspected text; not joined to a criterion-specific target"),
                    dict(source_id="nbtin-2024",reason="Sparse high-T trace; preserve half-of-maximum and fit Tc in scientific-manifest, do not relabel as a frozen midpoint target"),
                    dict(source_id="nbse2-2020",reason="Sample identity/pressure grid conflicts prevent strict source-backed Tc link"),
                    dict(source_id="hea-2022",reason="Low-T magnetization only, unknown exact per-element fractions and Tc criterion; no precursor/target join"),
                    dict(source_id="nbs2-2021:3R",reason="No observed transition above1.4K is censored, never Tc=0 or parent-negative")])
    omitted.extend([dict(source_id="sn-2025:glycerol9GPa",reason="Fig6a/6b and Fig7 report onset-related phase features; no explicit same-sample midpoint value/criterion. Two transitions under pressure and unreportedB forbid importing Sn2.5 or10.5GPa midpoint.",
                         locator="Paper p.104513-4/5 III.D, Fig6a/b and fig7.xlsx multiple9GPa onset entries"),
                    dict(source_id="nbse2-hebs-2024",reason="Full broad curve retained; Tc around6.5K has no unambiguous midpoint criterion in inspected text, so no primary target link.",
                         locator="Author-proof p.B lines106–118, Fig1c")])
    registry_document=dict(sources=sources,source_root="work/normal-state-collection",purpose="Local source-backed experimental collection; dataset-specific redistribution restrictions retained")
    collection=dict(curves=curves,targets=targets,links=links,audit_only_target_links=audit_only_links,omitted_rows=omitted,
                    primary_tc_criterion="resistive_midpoint",temperature_points_are_not_independent_materials=True)
    registry=M.source_registry(registry_document,source_root=SOURCE_ROOT)
    audit=[]
    for c in curves:
        M.validate_curve(c,registry)
        # One point suffices for payload schema audit; no ledger is created.
        M.curve_observations(c,registry,policy,point_indices=[0])
        feature=M.extract_features(c,registry,policy)
        audit.append(dict(curve_id=c["curve_id"],status=feature["status"],reasons=feature["reasons"],raw_point_count=len(c["points"])))
    for t in targets:F.validate_observation(t["payload"])
    for link in links:
        c=index[link["curve_id"]];t=next(t for t in targets if t["target_id"]==link["target_id"])
        probe=M.curve_observations(c,registry,policy,point_indices=[0])[0]
        assert not M._link_reasons(probe,t["payload"],link),(link,M._link_reasons(probe,t["payload"],link))
    for name,document in [("transport-registry.json",registry_document),("transport-collection.json",collection),("transport-adapter-audit.json",dict(curves_schema_valid=len(curves),targets_schema_valid=len(targets),curve_features=audit,ledger_written=False,models_fitted=0))]:
        (ROOT/name).write_text(json.dumps(document,ensure_ascii=False,separators=(",", ":"),allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(dict(curves=len(curves),points=sum(len(c["points"])for c in curves),sources=len(sources),targets=len(targets),links=len(links),
                         features_ready=sum(x["status"]=="ready"for x in audit),ledger_written=False)))
    print(json.dumps([x for x in audit if x["status"]=="ready"],ensure_ascii=False))


if __name__=="__main__":main()
