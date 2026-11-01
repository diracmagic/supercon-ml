"""Bounded literature evidence keyed to a candidate ID, never a training label."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "data" / "candidate_literature_audit.json"
STATUSES = {"reported-nonsuperconducting", "structure-only", "needs-full-text", "not-found-in-this-search"}


def load_audit(index: Path = INDEX) -> tuple[dict, dict]:
    """Read the inspectable evidence parts, checking coverage and content hashes."""
    doc = json.loads(index.read_text(encoding="utf-8"))
    records = {}
    for part in doc["parts"]:
        path = (index.parent / part["path"]).resolve()
        if not path.is_relative_to(index.parent.resolve()):
            raise ValueError("Literature audit part is outside its data directory")
        # Git may check out LF sources as CRLF on Windows. Hash the published LF.
        text = path.read_text(encoding="utf-8")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != part["sha256"]:
            raise ValueError(f"Literature audit hash mismatch: {part['path']}")
        rows = json.loads(text)["materials"]
        if len(rows) != part["count"]:
            raise ValueError("Literature audit part count mismatch")
        for row in rows:
            key = row["material_id"]
            if key in records or row["status"] not in STATUSES or not row.get("search_log"):
                raise ValueError(f"Invalid or duplicate literature record: {key}")
            records[key] = row
    if len(records) != doc["summary"]["candidates_audited"]:
        raise ValueError("Literature audit total count mismatch")
    return records, doc


def compact_record(row: dict) -> dict:
    """Keep a short display record; the full source log remains in data/."""
    sources = []
    for source in row.get("sources", []):
        if source.get("url"):
            sources.append({"url": source["url"],
                            "cite": (source.get("cite") or source.get("doi") or "Original source")[:180],
                            "evidence": (source.get("evidence_scope") or source.get("supports", ""))[:250]})
    result = {"status": row["status"], "searched_on": row["searched_on"],
              "sources": sources[:2], "limitations": row.get("limitations", "")[:180] if row["status"] != "not-found-in-this-search" else ""}
    if row["superconductivity_outcome"] != "unknown":
        result["conclusion"] = row["superconductivity_outcome"]
    if row.get("check_correction"):
        result["check_correction"] = copy.deepcopy(row["check_correction"])
    return result


def attach_audits(candidates: list[dict], records: dict) -> dict:
    """Annotate exact IDs only. Do not change scores, checks, ranking or labels."""
    covered = 0
    for candidate in candidates:
        record = records.get(candidate.get("id"))
        if record is not None:
            candidate["literature_audit"] = copy.deepcopy(compact_record(record))
            covered += 1
    return {"searched": covered, "listed": len(candidates), "unsearched": len(candidates) - covered,
            "about": "A bounded literature search is separate from a superconductivity test; unknown is not a negative label."}
