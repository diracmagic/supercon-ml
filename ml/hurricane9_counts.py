"""Hurricane 9 support counts: rolling publication-year windows and coverage of the measured sample fields.

    python ml/hurricane9_counts.py --audit [--cache DIR] [--output PATH]   # counts on the pinned real table (no fit)
    python ml/hurricane9_counts.py --smoke                                 # the same counts on the synthetic rows

Two questions are answered by counting, before any design is frozen:

1. Could a rolling temporal test carry the primary claim? For each cutoff year T, the training side is every unit
   built from reports with year <= T, and the test side is the units of the next WIDTH years that no training unit
   matches. A new-parent unit claims only parents that no training unit claims. Each cell gives the units by event
   label, the units that carry a Tc value, the 30 K positives and the distinct parents, and says how many new-parent
   units have an earlier relative in the same family (same element set, same structure name).
2. Are the measured sample fields there? Per family: how many admitted reports and units carry a measured oxygen
   content, lattice constants, a measurement floor, a method, a stated form and a structure name, and how many parents
   have at least MIN_UNITS Tc-bearing units with a c-axis length that takes at least MIN_DISTINCT different values.

Every data rule comes from ml/hurricane9_data.py, unchanged: admission, the replication lift inside each window
(F-40), unit identity, parent claims (F-43), family and event labels. Nothing here fits a model, makes a prediction
or relates a Tc value to an input; Tc enters only through the unit's event label and through "has a Tc value".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hurricane9_data as H  # noqa: E402

VERSION = "hurricane9-counts-v1"
CUTOFFS = (1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020)   # T: train on reports with year <= T
WIDTH = 5                                                    # test on reports with T < year <= T + WIDTH; windows do not overlap
OPEN_CUTOFF = 2017                                           # the design note's single cutoff, open-ended (cross-check)
BIN = 5                                                      # years per bin of the first-report histogram
MIN_UNITS, MIN_DISTINCT = 5, 3                               # a parent series that could show a trend along its doping
FAMILIES = tuple(H.EVENT_K) + ("other",)
PIECE = 2000                                                 # characters of the report per printed line


def _cell(units: list) -> dict:
    """Counts for one group of units; no Tc value leaves this function."""
    return {"units": len(units),
            "positive": sum(u["event"] == 1 for u in units),
            "negative": sum(u["event"] == 0 for u in units),
            "censored": sum(u["event"] == "censored" for u in units),
            "with_tc_value": sum(u["tc_k"] is not None for u in units),
            "high_tc_positive": sum(u["high_tc_event"] == 1 for u in units),
            "parents": len({p for u in units for p in u["parents"]})}


def _by_family(units: list) -> dict:
    return {fam: _cell([u for u in units if u["family"] == fam]) for fam in FAMILIES}


def window_counts(observations: list, cutoff: int, width: int | None) -> dict:
    """Train on reports with year <= cutoff, test on the reports of the next width years (all later years when
    width is None). Admission, lift and aggregation run inside each side on its own reports, as in H.temporal_split."""
    dated = [o for o in observations if o["year"] is not None]
    last = None if width is None else cutoff + width
    before = H.canonical_units([o for o in dated if o["year"] <= cutoff], lift=True)
    after = H.canonical_units([o for o in dated if o["year"] > cutoff and (last is None or o["year"] <= last)], lift=True)
    known_keys = {u["key"] for u in before}
    known_parents = {p for u in before for p in u["parents"]}
    element_sets = {(u["family"], tuple(u["elements"])) for u in before}
    structures = {(u["family"], u["structure_name"]) for u in before if u["structure_name"] != "none"}
    new = [u for u in after if u["key"] not in known_keys]
    repeat = [u for u in after if u["key"] in known_keys]
    new_parent = [u for u in new if u["parents"] and not (set(u["parents"]) & known_parents)]
    no_parent = [u for u in new if not u["parents"]]
    out = {"cutoff": cutoff, "window": [cutoff + 1, last], "train": _by_family(before), "new_units": _by_family(new),
           "repeat_units": _by_family(repeat), "new_units_without_resolved_parent": _by_family(no_parent),
           "new_parent_units": {}}
    for fam in FAMILIES:
        members = [u for u in new_parent if u["family"] == fam]
        same_elements = [(fam, tuple(u["elements"])) in element_sets for u in members]
        same_structure = [(fam, u["structure_name"]) in structures for u in members]
        cell = _cell(members)
        cell["earlier_same_element_set"] = sum(same_elements)
        cell["earlier_same_structure_name"] = sum(same_structure)
        cell["no_earlier_relative"] = sum(not a and not b for a, b in zip(same_elements, same_structure))
        positives = [u for u, a, b in zip(members, same_elements, same_structure) if u["event"] == 1 and not a and not b]
        cell["positive_with_no_earlier_relative"] = len(positives)
        cell["parents_of_positives_with_no_earlier_relative"] = len({p for u in positives for p in u["parents"]})
        out["new_parent_units"][fam] = cell
    return out


def first_report_histogram(units: list, bin_years: int = BIN) -> dict:
    """Units and resolved parents by the year of their first admitted report (whole-cohort units)."""
    out = {}
    for fam in FAMILIES:
        members = [u for u in units if u["family"] == fam and u["earliest_year"] is not None]
        first_parent = {}
        for u in members:
            for p in u["parents"]:
                first_parent[p] = min(first_parent.get(p, u["earliest_year"]), u["earliest_year"])
        label = lambda y: f"{y // bin_years * bin_years}-{y // bin_years * bin_years + bin_years - 1}"   # noqa: E731
        out[fam] = {"units": dict(sorted(Counter(label(u["earliest_year"]) for u in members).items())),
                    "parents": dict(sorted(Counter(label(y) for y in first_parent.values()).items())),
                    "undated_units": sum(u["family"] == fam and u["earliest_year"] is None for u in units)}
    return out


def _positive(v) -> bool:
    return v is not None and v > 0


FIELDS = {
    "oxygen_measured": lambda o: o["oxygen"]["status"] == "measured",
    "oxygen_fixed": lambda o: o["oxygen"]["status"] == "fixed",
    "oxygen_variable": lambda o: o["oxygen"]["status"] == "variable",
    "oxygen_unknown": lambda o: o["oxygen"]["status"] == "unknown",
    "lattice_a": lambda o: _positive(o["lattice"]["lata"]),
    "lattice_c": lambda o: _positive(o["lattice"]["latc"]),
    "lattice_a_and_c": lambda o: _positive(o["lattice"]["lata"]) and _positive(o["lattice"]["latc"]),
    "lattice_unit_stated": lambda o: bool(o["lattice_unit"]),
    "structure_name": lambda o: bool(o["structure_name"]),
    "space_group": lambda o: bool(o["space_group"]),
    "symmetry": lambda o: o["symmetry"] is not None,
    "floor": lambda o: o["floor"] is not None,
    "tc_method": lambda o: o["tc_method"] is not None,
    "tc_width": lambda o: o["tc_width"] is not None,
    "form_stated": lambda o: bool(o["shape"]),
    "year": lambda o: o["year"] is not None,
}


def field_coverage(observations: list, units: list) -> dict:
    """How many admitted reports, units and parent series carry each measured field (counts only). The units are the
    whole-cohort units of the observations; the reports of a unit are found by the unit key after the same replication
    lift that built the units, never by the data number (the table repeats a few data numbers)."""
    admitted = [o for o in H.apply_replication_lift(observations) if o["status"] == "admitted"]
    reports_of = defaultdict(list)
    for o in admitted:
        reports_of[H.unit_key(o)].append(o)
    reports = {}
    for fam in FAMILIES:
        members = [o for o in admitted if o["family"] == fam]
        reports[fam] = {"reports": len(members), **{name: sum(bool(test(o)) for o in members) for name, test in FIELDS.items()}}
    all_rows = {}
    for fam in FAMILIES + ("mixed",):
        members = [o for o in observations if o["family"] == fam]
        all_rows[fam] = {"rows": len(members),
                         "pressure_study": sum(o["pressure"]["status"] == "pressure study" for o in members),
                         "pmax_positive": sum(_positive(o["pressure"]["pmax"]) for o in members),
                         "dtcdp_stated": sum(bool(o["pressure"]["dtcdp"]) for o in members)}
    unit_rows, series = {}, {}
    for fam in FAMILIES:
        members = [u for u in units if u["family"] == fam]
        carried = []
        for u in members:
            obs = reports_of[u["key"]]
            carried.append({"unit": u, "c": sorted({round(o["lattice"]["latc"], 3) for o in obs if _positive(o["lattice"]["latc"])}),
                            "a_and_c": any(FIELDS["lattice_a_and_c"](o) for o in obs),
                            "oxygen": any(FIELDS["oxygen_measured"](o) for o in obs)})
        tc = [c for c in carried if c["unit"]["tc_k"] is not None]
        unit_rows[fam] = {"units": len(members), "units_with_tc_value": len(tc),
                          "lattice_c": sum(bool(c["c"]) for c in carried), "lattice_a_and_c": sum(c["a_and_c"] for c in carried),
                          "oxygen_measured": sum(c["oxygen"] for c in carried),
                          "with_tc_value_and_lattice_c": sum(bool(c["c"]) for c in tc),
                          "with_tc_value_and_oxygen_measured": sum(c["oxygen"] for c in tc),
                          "with_tc_value_and_both": sum(bool(c["c"]) and c["oxygen"] for c in tc)}
        groups = defaultdict(list)
        for c in tc:
            if len(c["unit"]["parents"]) == 1:   # one resolved parent claim; ambiguous and unresolved units form no series
                groups[c["unit"]["parents"][0]].append(c)
        with_c = {p: [c for c in g if c["c"]] for p, g in groups.items()}
        with_o = {p: [c for c in g if c["oxygen"]] for p, g in groups.items()}
        varying = {p: g for p, g in with_c.items() if len(g) >= MIN_UNITS and len({v for c in g for v in c["c"]}) >= MIN_DISTINCT}
        series[fam] = {"parents_with_a_tc_bearing_unit": len(groups),
                       "parents_with_min_units": sum(len(g) >= MIN_UNITS for g in groups.values()),
                       "units_in_those": sum(len(g) for g in groups.values() if len(g) >= MIN_UNITS),
                       "parents_with_min_units_having_lattice_c": sum(len(g) >= MIN_UNITS for g in with_c.values()),
                       "parents_with_min_units_and_varying_lattice_c": len(varying),
                       "units_in_varying_lattice_c_series": sum(len(g) for g in varying.values()),
                       "parents_with_min_units_having_oxygen_measured": sum(len(g) >= MIN_UNITS for g in with_o.values()),
                       "units_in_oxygen_measured_series": sum(len(g) for g in with_o.values() if len(g) >= MIN_UNITS)}
    return {"min_units": MIN_UNITS, "min_distinct_values": MIN_DISTINCT, "admitted_reports_after_lift": len(admitted),
            "reports_matched_to_units": sum(len(reports_of[u["key"]]) for u in units), "admitted_reports": reports,
            "all_rows": all_rows, "units": unit_rows, "parent_series": series}


def report(observations: list, *, cutoffs=CUTOFFS, width=WIDTH, open_cutoff=OPEN_CUTOFF) -> dict:
    units = H.canonical_units(observations, lift=True)
    years = [o["year"] for o in observations if o["year"] is not None]
    reference = H.temporal_split(observations, cutoff=open_cutoff)
    mine = window_counts(observations, open_cutoff, None)
    agree = (_by_family(reference["train_units"]) == mine["train"] and _by_family(reference["test_new_units"]) == mine["new_units"]
             and _by_family(reference["repeat_report_units"]) == mine["repeat_units"]
             and _by_family(reference["test_new_parent_units"]) == {f: {k: c[k] for k in _cell([])} for f, c in mine["new_parent_units"].items()})
    return {"version": VERSION, "data_module": H.VERSION,
            "note": "count-only: no model is fitted, no prediction is made and no Tc value is related to an input",
            "totals": {"observations": len(observations), "status": dict(Counter(o["status"] for o in observations)),
                       "admitted_without_year": sum(o["status"] == "admitted" and o["year"] is None for o in observations),
                       "year_range": [int(min(years)), int(max(years))] if years else None,
                       "units": len(units), "units_by_family": dict(Counter(u["family"] for u in units)),
                       "modelled_units": sum(u["family"] in H.EVENT_K for u in units)},
            "first_report": first_report_histogram(units),
            "rolling": {"cutoffs": list(cutoffs), "width": width, "windows": [window_counts(observations, t, width) for t in cutoffs]},
            "open_window": mine, "open_window_agrees_with_temporal_split": bool(agree),
            "coverage": field_coverage(observations, units)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit", action="store_true", help="counts on the pinned real table (no fit)")
    parser.add_argument("--smoke", action="store_true", help="counts on the synthetic rows")
    parser.add_argument("--cache", type=Path, default=H.P.CACHE / "mdr-supercon-220808")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    started = time.time()
    if args.smoke:
        observations, unreadable = H.load_observations(H.synthetic_table())
        out = {"smoke": True, "synthetic": "synthetic rows; not a data result"}
    elif args.audit:
        data = H.fetch(H.DATA_FILE, args.cache, offline=args.offline)
        observations, unreadable = H.load_observations(data.decode("utf-8", errors="replace"))
        out = {"smoke": False, "source": {"file": H.DATA_FILE, "sha256": H.SOURCES[H.DATA_FILE]["sha256"], "doi": H.MDR_DOI},
               "licence": H.LICENCE, "attribution": H.ATTRIBUTION}
    else:
        parser.error("choose --audit or --smoke")
    out.update(report(observations), unreadable_count=len(unreadable))
    out["seconds"] = round(time.time() - started, 3)
    text = json.dumps(out, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print("=== hurricane9-counts begin")
    for i in range(0, len(text), PIECE):   # numbered pieces: a job log is easier to read back than one very long line
        print(f"h9c|{i // PIECE:03d}|{text[i:i + PIECE]}")
    print("=== hurricane9-counts end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))


if __name__ == "__main__":
    main()
