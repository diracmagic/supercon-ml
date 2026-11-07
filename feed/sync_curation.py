"""Merge curated "Recent advances" from the claude/news-curation branch into progress/content.json.

A daily curation task writes candidate entries, with their references, to progress/content.json on the
branch claude/news-curation and never to main. The paper-feed workflow on main runs this script after
fetching that branch. Each new entry is checked against the app's content schema and added only when its
reference key and DOI or link are new, so main stays authoritative: entries already on main, the hide
list and every other key (contact, about, schema, found, watch, cited_by) are never changed by the branch.

Run from the repository root:
  python feed/sync_curation.py progress/content.json CURATED.json [--builtin app/dist/js/initialize/content.js]
Only the standard library is used. The script prints what it added and why it skipped anything.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

# The app's own limits (applyContent in app/dist/js/definitions/content.js).
MAX_RECENT = 120
MAX_REFS = 200
MAX_HEADLINE = 180
MAX_TEXT = 900
MAX_REF_TEXT = 220
KINDS = {"experiment", "theory", "computation", "news"}
# Theory & materials card ids (THEORIES, MECHANISMS and MATERIALS in the app) plus the two overview cards.
CARDS = {
    "london", "gl", "bcs", "eliashberg", "josephson", "dwave", "spm", "topo", "moire",
    "mott", "rvb", "zr", "spinglue", "stripes", "phase", "bipolaron", "strange",
    "magnet", "mgb2", "rebco", "hg1223", "iron", "hydride", "nickelate", "magic", "triplet", "heavy",
    "field", "ai",
}
REF_KEY = re.compile(r"^[a-z0-9_-]{2,40}$")
DOI = re.compile(r"^10\.\d{4,9}/\S+$")
MONTH = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2]))?$")
UNSAFE = re.compile(r"[\x00-\x1f<>]")
DEFAULT_BUILTIN = Path(__file__).resolve().parents[1] / "app" / "dist" / "js" / "initialize" / "content.js"


def dump_content(content: dict) -> str:
    """content.json in the repository's layout: two-space indentation with the contact object on the first line."""
    text = json.dumps(content, ensure_ascii=False, indent=2)
    if content and next(iter(content)) == "contact" and isinstance(content["contact"], dict):
        lines = text.split("\n")
        span = len(json.dumps(content["contact"], ensure_ascii=False, indent=2).split("\n"))
        head = '{ "contact": ' + json.dumps(content["contact"], ensure_ascii=False, separators=(", ", ": ")) + ","
        text = "\n".join([head] + lines[1 + span:])
    return text + "\n"


def builtin_links(path: Path) -> set:
    """DOIs and links of the references built into the app, so a curated entry cannot duplicate one of them."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {m.group(1).lower() for m in re.finditer(r"\b[du]: '((?:10\.|https://)[^']+)'", text)}


def ref_problem(key: str, ref) -> str:
    if not REF_KEY.match(key or ""):
        return "reference key must be 2-40 lowercase letters, digits, - or _"
    if not isinstance(ref, dict) or not isinstance(ref.get("t"), str) or not ref["t"].strip():
        return "reference needs a citation text t"
    if len(ref["t"]) > MAX_REF_TEXT or UNSAFE.search(ref["t"]):
        return "citation text is too long or contains control characters or angle brackets"
    doi, url = ref.get("d"), ref.get("u")
    if doi is not None and not (isinstance(doi, str) and DOI.match(doi)):
        return "d must be a DOI such as 10.1103/abcd-1234"
    if url is not None and not (isinstance(url, str) and url.startswith("https://") and not UNSAFE.search(url)):
        return "u must be an https link"
    if not doi and not url:
        return "reference needs a DOI (d) or an https link (u)"
    if set(ref) - {"t", "d", "u"}:
        return "reference has unknown fields"
    return ""


def entry_problem(entry) -> str:
    if not isinstance(entry, dict):
        return "entry must be an object"
    if set(entry) - {"d", "k", "cards", "ref", "h", "x"}:
        return "entry has unknown fields"
    if not MONTH.match(str(entry.get("d", ""))):
        return "d must be YYYY or YYYY-MM"
    if entry.get("k") not in KINDS:
        return "k must be experiment, theory, computation or news"
    cards = entry.get("cards")
    if not isinstance(cards, list) or not 1 <= len(cards) <= 5 or not all(isinstance(c, str) and c in CARDS for c in cards):
        return "cards must list 1-5 known card ids"
    if len(set(cards)) != len(cards):
        return "cards repeat"
    for field, limit in (("h", MAX_HEADLINE), ("x", MAX_TEXT)):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit or UNSAFE.search(value):
            return f"{field} must be 1-{limit} characters without control characters or angle brackets"
    if not isinstance(entry.get("ref"), str):
        return "ref must name a reference"
    return ""


def merge(main: dict, curated: dict, builtin: set | None = None, today: str | None = None) -> tuple[dict, list, list]:
    """Return (merged content, added refs, skipped (ref, reason) pairs); main itself is not modified."""
    if not isinstance(main, dict) or not isinstance(main.get("recent"), list) or not isinstance(main.get("refs"), dict):
        raise ValueError("main content.json must have a recent list and a refs object")
    merged = json.loads(json.dumps(main))
    if not isinstance(curated, dict) or not isinstance(curated.get("recent"), list):
        return merged, [], []
    curated_refs = curated.get("refs") if isinstance(curated.get("refs"), dict) else {}
    used = {r.get("ref") for r in merged["recent"] if isinstance(r, dict)}
    links = {str(v.get(f, "")).lower() for v in merged["refs"].values() if isinstance(v, dict) for f in ("d", "u")} - {""}
    links |= set(builtin or ())
    added, skipped, fresh = [], [], []
    for entry in curated["recent"]:
        key = entry.get("ref") if isinstance(entry, dict) else None
        if key in used or key in merged["refs"]:
            continue   # already on main: main stays authoritative
        problem = entry_problem(entry) or ref_problem(key, curated_refs.get(key))
        ref = curated_refs.get(key) or {}
        link = str(ref.get("d") or ref.get("u") or "").lower()
        if not problem and link in links:
            problem = "the same paper is already listed"
        if not problem and len(merged["recent"]) + len(fresh) >= MAX_RECENT:
            problem = f"the app shows at most {MAX_RECENT} entries"
        if not problem and len(merged["refs"]) >= MAX_REFS:
            problem = f"the app reads at most {MAX_REFS} references"
        if problem:
            skipped.append((str(key), problem))
            continue
        merged["refs"][key] = {f: ref[f] for f in ("t", "d", "u") if f in ref}
        fresh.append({f: entry[f] for f in ("d", "k", "cards", "ref", "h", "x")})
        used.add(key)
        links.add(link)
        added.append(key)
    if fresh:
        merged["recent"] = fresh + merged["recent"]
        merged["updated"] = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    return merged, added, skipped


def main(argv: list) -> int:
    args = [a for a in argv if not a.startswith("--")]
    builtin_path = DEFAULT_BUILTIN
    if "--builtin" in argv:
        builtin_path = Path(argv[argv.index("--builtin") + 1])
        args = [a for a in args if a != str(builtin_path)]
    if len(args) != 2:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    target, source = Path(args[0]), Path(args[1])
    main_content = json.loads(target.read_text(encoding="utf-8"))
    try:
        curated = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        print(f"curated content unreadable, nothing merged: {err}")
        return 0
    merged, added, skipped = merge(main_content, curated, builtin_links(builtin_path))
    for key, reason in skipped:
        print(f"skipped {key}: {reason}")
    if added:
        target.write_text(dump_content(merged), encoding="utf-8")
        print(f"added {len(added)} curated advance(s): {', '.join(added)}")
    else:
        print("no new curated advances")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
