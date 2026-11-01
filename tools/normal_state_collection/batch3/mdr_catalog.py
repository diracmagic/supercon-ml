"""Inventory the pinned NIMS secondary database without creating training labels.

Raw cell strings, units, table locations, literature citations and archive-member
hashes are retained. A database row is not an independently verified specimen;
neither an attached graph nor a composition match establishes a same-sample join.
This program does not write the experimental feedback ledger or fit any model.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile

DATASET_DOI = "10.48505/nims.4487"
GUIDE_DOI = "10.48505/nims.4488"
FILES = {
    "20240322_MDR_OAndM.txt": ("f599ef0040c18521e386f758ee826fe269f67ef369c1a007656035d03ccdfdf6", "2347b413-9c15-43b7-90e6-41fe9243b1a5"),
    "240322_MDR_Organic.txt": ("d116848a90d01e48356ed6cf0bb69035fa863a3a559deac1ef188025bdb3b423", "1a18e447-8ec2-4316-be12-b4acdc885fb8"),
    "data.zip": ("e6f01f5631343a077762bfaf7f8f17898abb47d224a4edf72f8df0c5ad698dc5", "35342c71-7902-41bb-a5b8-ea74438dcb58"),
    "schema.json": ("e1c9da5febe039af30f94bb1d57b2c46a579464cef1e179efc9b75193ae00cd9", "8b1fca32-37bb-43f4-8ede-b8915233e355"),
    "ReadmeTbl.xlsx": ("6b6c8311f9968fb5e726bf444141391ee2e11eba62423554ca7e5040f3a04b97", "fa5208b6-b199-494c-aac3-edf07093935b"),
    "SuperCon_ReadMe_en.pdf": ("1f3490ee3f415707cdfd4e7aade936d97f4202cdda7244ad8b2e0caf62ad6531", "4f1fcd20-92ea-4b53-8c2d-29281d2ca642"),
}
PROPERTY_FIELDS = (
    "resrt", "abresrt", "cresrt", "res77", "abres77", "cres77",
    "resn", "abresn", "cresn", "nort", "kaizero", "curiec", "moment",
    "gamma", "debyet", "rh300", "rh300n", "rh300p", "rhn", "carrier",
    "thc300", "thc300n", "thc300p", "tp300", "tp300n", "tp300p",
)
OUTCOME_FIELDS = ("t1", "t2", "t3", "tcsus", "tc", "tcn", "tcmax", "pcrit")
FIGURE_FIELDS = ("svfig", "model", "tcfig", "hirfig", "figjc", "spheat", "thcfig", "tpfig", "hallfig", "fig1", "fig2", "f1_filename", "f2_filename")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def parse_table(raw, filename):
    """Use the actual two header rows, reject ragged/duplicate-ID records."""
    stream = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), delimiter="\t")
    descriptions, symbols = next(stream), next(stream)
    require(len(descriptions) == len(symbols), "Header widths differ")
    require(len(set(symbols)) == len(symbols) and "num" in symbols and "refno" in symbols, "Ambiguous table symbols")
    rows, seen, empty_rows = [], set(), []
    for logical_row, values in enumerate(stream, 3):
        require(len(values) == len(symbols), f"Ragged row {logical_row} in {filename}")
        if not any(values):
            empty_rows.append(logical_row)
            continue
        fields = dict(zip(symbols, values))
        require(fields["num"] and fields["num"] not in seen, "Missing or duplicate data number")
        seen.add(fields["num"])
        rows.append({
            "record_id": f"mdr240322:{filename}:{fields['num']}",
            "table": filename, "logical_row": logical_row,
            "evidence_domain": "secondary_literature_database",
            "training_eligible": False, "primary_source_checked": False,
            "sample_identity_verified": False, "phase_state": "unclassified",
            "raw_fields": fields,
            "citation": {"dataset_doi": DATASET_DOI, "reference_number": fields["refno"],
                         **{key: fields.get(key, "") for key in ("title", "author", "journal", "year")}},
        })
    return {"symbols": symbols, "descriptions": descriptions, "rows": rows, "empty_logical_rows": empty_rows}


def text_inventory(raw, suffix):
    """Describe numeric text; do not interpret axes or merge distinct series."""
    try:
        text = raw.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp932")
            encoding = "cp932"
        except UnicodeDecodeError:
            return {"encoding": "unresolved", "parse_status": "unparsed", "numeric_xy_rows": None}
    def numeric_pair(cells):
        if len(cells) < 2:
            return False
        try:
            return all(math.isfinite(float(v)) for v in cells[:2])
        except ValueError:
            return False

    # Some .dat members are actually CSV (including an index column). Index
    # availability only; do not mistake the first numeric column for temperature.
    trials = {sep: list(csv.reader(io.StringIO(text, newline=""), delimiter=sep)) for sep in ("\t", ",")}
    scores = {sep: sum(numeric_pair(row) for row in rows) for sep, rows in trials.items()}
    preferred = "\t" if suffix == ".dat" else ","
    delimiter = max(trials, key=lambda sep: (scores[sep], sep == preferred))
    rows = trials[delimiter]
    metadata_values, numeric, series, sections = {}, 0, collections.Counter(), []
    section = None
    first_numeric = None
    for row_number, cells in enumerate(rows, 1):
        if not cells:
            continue
        for key in ("FIGNO", "XPROP", "XUNIT", "YPROP", "YUNIT", "PPROP", "PUNIT"):
            if cells[0].startswith(key + ":"):
                value = cells[0].split(":", 1)[1]
                values = metadata_values.setdefault(key, [])
                if value not in values:
                    values.append(value)
                if section is None or key == "FIGNO" or key in section["metadata_raw"]:
                    section = {"first_logical_row": row_number, "metadata_raw": {}}
                    sections.append(section)
                section["metadata_raw"][key] = value
        # Count only finite pairs; retain the complete immutable file separately.
        if numeric_pair(cells):
            numeric += 1
            first_numeric = first_numeric or row_number
            if len(cells) >= 3 and cells[2].strip():
                series[cells[2]] += 1
    conflicts = {key: values for key, values in metadata_values.items() if len(values) > 1}
    # This is only a filename/header availability index, not a normal-state decision.
    return {"encoding": encoding, "parse_status": "text_indexed",
            "header_lines": text.splitlines()[:max(0, min(12, (first_numeric or 13) - 1))],
            "delimiter": "tab" if delimiter == "\t" else "comma",
            "delimiter_numeric_pair_counts": {"tab" if k == "\t" else "comma": v for k, v in scores.items()},
            "delimiter_changed_from_extension_default": delimiter != preferred,
            "axis_metadata_raw": {key: values[0] for key, values in metadata_values.items() if len(values) == 1},
            "axis_metadata_conflicts": conflicts, "metadata_sections": sections,
            "physical_axes_resolved": False,
            "numeric_xy_rows": numeric, "numeric_pair_semantics": "First two finite numeric columns only; an index column is possible, not assumed physical X/Y",
            "third_column_raw_values": dict(sorted(series.items())),
            "plot_digitizer_marker": "plot digitizer" in text[:2000].lower(),
            "numeric_pairs_are_not_independent_samples": True}


def archive_inventory(raw):
    records = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate archive names")
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            require(not name.is_absolute() and ".." not in name.parts and "\\" not in item.filename,
                    "Unsafe archive path")
            if item.is_dir():
                continue
            require(item.file_size < 20_000_000, "Unexpected oversized member")
            contents = archive.read(item)
            suffix = name.suffix.lower()
            entry = {"archive_member": item.filename, "bytes": len(contents), "sha256": digest(contents),
                     "evidence_domain": "secondary_literature_attachment", "training_eligible": False,
                     "primary_source_checked": False, "sample_identity_verified": False,
                     "phase_state": "unclassified", "contains_multiple_series_possible": True}
            if suffix in {".dat", ".csv"}:
                entry.update(text_inventory(contents, suffix))
            else:
                entry.update(parse_status="non_numeric_attachment", numeric_xy_rows=None)
            records.append(entry)
    return records


def build(data_root, output):
    source_bytes, sources = {}, []
    root = Path(data_root).resolve(strict=True)
    for filename, (expected, fileset) in FILES.items():
        path = (root / filename).resolve(strict=True)
        require(root in path.parents, "Source escaped declared data root")
        raw = path.read_bytes()
        require(digest(raw) == expected, "Pinned source bytes changed: " + filename)
        source_bytes[filename] = raw
        sources.append({"filename": filename, "sha256": expected, "bytes": len(raw),
                        "url": f"https://mdr.nims.go.jp/filesets/{fileset}/download"})
    schema = json.loads(source_bytes["schema.json"])
    require(schema["doi"] == "https://doi.org/" + DATASET_DOI, "Wrong dataset version")
    tables = {name: parse_table(raw, name) for name, raw in source_bytes.items() if name.endswith(".txt")}
    members = archive_inventory(source_bytes["data.zip"])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / "secondary-records.jsonl"
    with rows_path.open("w", encoding="utf-8", newline="\n") as file:
        for table in tables.values():
            for row in table["rows"]:
                file.write(canonical(row).decode() + "\n")
    members_path = output / "attachment-index.json"
    members_path.write_bytes(canonical(members) + b"\n")
    stats = {}
    for name, table in tables.items():
        rows = [r["raw_fields"] for r in table["rows"]]
        stats[name] = {
            "records": len(rows), "columns": len(table["symbols"]),
            "empty_logical_rows_excluded": table["empty_logical_rows"],
            "nonempty_reference_numbers": len({r["refno"] for r in rows if r["refno"]}),
            "missing_reference_number_records": sum(not r["refno"] for r in rows),
            "populated_fields": {key: sum(bool(r.get(key)) for r in rows) for key in PROPERTY_FIELDS + OUTCOME_FIELDS + FIGURE_FIELDS},
            "midpoint_and_any_property_cells": sum(bool(r.get("t2")) and any(r.get(key) for key in PROPERTY_FIELDS) for r in rows),
            "midpoint_and_property_is_not_verified_pair": True,
        }
    summary = {
        "version": "mdr240322-secondary-acquisition-v1", "dataset_doi": DATASET_DOI, "guide_doi": GUIDE_DOI,
        "citation": "Center for Basic Research on Materials, NIMS. MDR SuperCon Datasheet Ver.240322. https://doi.org/10.48505/nims.4487",
        "license": "CC-BY-4.0", "sources": sources, "tables": stats,
        "headers": {name: {"symbols": t["symbols"], "descriptions": t["descriptions"]} for name, t in tables.items()},
        "attachments": {"files": len(members),
                        "extensions": dict(sorted(collections.Counter(PurePosixPath(m["archive_member"]).suffix.lower() for m in members).items())),
                        "numeric_xy_rows": sum(m.get("numeric_xy_rows") or 0 for m in members),
                        "files_with_numeric_pairs": sum(bool(m.get("numeric_xy_rows")) for m in members),
                        "plot_digitizer_marked_files": sum(bool(m.get("plot_digitizer_marker")) for m in members),
                        "files_with_metadata_conflicts": sum(bool(m.get("axis_metadata_conflicts")) for m in members),
                        "files_with_delimiter_override": sum(bool(m.get("delimiter_changed_from_extension_default")) for m in members),
                        "unresolved_encoding_files": sum(m.get("encoding") == "unresolved" for m in members)},
        "outputs": [{"filename": p.name, "sha256": digest(p.read_bytes()), "bytes": p.stat().st_size} for p in (rows_path, members_path)],
        "training_rows_exported": 0, "ledger_events_added": 0, "models_fitted": 0, "adopted": False,
        "limitations": [
            "Database rows and graph points are not independent specimens. Repeated literature and samples are retained.",
            "Original field strings/units/criteria are preserved; absent values stay absent, not zero or negative labels.",
            "Room temperature resrt is not asserted to mean exactly 300 K. Raw temperature, direction and units require review.",
            "Gamma/Debye derivations require primary-text checks; superconducting jumps/gaps/critical fields are not precursor inputs.",
            "Archive headers and third columns may describe multiple series; no automatic temperature/property/unit or specimen binding.",
            "Composition or graph-name equality is only a retrieval hint, not evidence of the same measured sample or candidate structure.",
            "Records include secondary literature values and digitized graphs, not a newly verified primary-measurement cohort.",
        ],
    }
    (output / "summary.json").write_bytes(canonical(summary) + b"\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.data_root, args.output)
    print(json.dumps({"tables": result["tables"], "attachments": result["attachments"], "training_rows_exported": 0}, indent=2))
