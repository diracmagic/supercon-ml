"""Live paper feed for the app: new superconductivity papers from arXiv and from Nature, Science,
Physical Review Letters and Physical Review X.

Run from the repository root:  python feed/papers.py
It writes progress/papers.json, which the app reads. Only the standard library is used.
Sources:
  - arXiv API, category cond-mat.supr-con (primary and cross-listed). arXiv metadata, including
    abstracts, is offered under CC0.
  - Crossref REST API, filtered by journal ISSN and publication date; titles are matched for
    superconductivity. Abstracts are shown only when the publisher deposited one with Crossref.
Topic and type tags are assigned automatically from keywords, so they are a rough guide.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "progress" / "papers.json"
UA = "supercon-ml paper feed (https://github.com/diracmagic/supercon-ml)"
ARXIV_MAX = 80
JOURNAL_DAYS = 150
JOURNAL_MAX = 30
JOURNALS = [
    ("Nature", "Nature", ["0028-0836", "1476-4687"]),
    ("Science", "Science", ["0036-8075", "1095-9203"]),
    ("PRL", "Phys. Rev. Lett.", ["0031-9007", "1079-7114"]),
    ("PRX", "Phys. Rev. X", ["2160-3308"]),
]
ABSTRACT_MAX = 1400

TOPICS = [
    ("Cuprates", r"cuprate|CuO[_]?2|YBa[_]?2Cu|YBCO|Bi[_]?2Sr[_]?2|Bi-?22[01]2|La[_]?2-?x?Sr|LSCO|Hg-?12[0-9]{2}|HgBa|Nd[_]?2-?x?Ce|copper oxide"),
    ("Nickelates", r"nickelate|La[_]?3Ni[_]?2O|La[_]?4Ni[_]?3O|Ni[_]?2O[_]?7|NdNiO|PrNiO|infinite-layer"),
    ("Iron-based", r"iron-based|iron pnictide|iron chalcogenide|pnictide|FeSe|FeTe|FeAs|BaFe[_]?2|LiFeAs|Fe-based"),
    ("Hydrides", r"hydride|H[_]?3S\b|LaH[_]?10|superhydride|hydrogen-rich|CeH[_]?9|YH[_]?[69]|LaBeH|LaSc[_]?2H|ternary hydride"),
    ("Moiré and 2D", r"twisted|moir[eé]|graphene|WSe[_]?2|MoTe[_]?2|rhombohedral|van der Waals|monolayer|two-dimensional"),
    ("Kagome", r"kagome|CsV[_]?3Sb[_]?5|KV[_]?3Sb[_]?5|RbV[_]?3Sb[_]?5|AV[_]?3Sb[_]?5"),
    ("Heavy fermions", r"heavy[- ]fermion|Kondo|CeCoIn|CeRh[_]?2As|UTe[_]?2|UPt[_]?3|URhGe|UCoGe|CeCu[_]?2Si"),
    ("Triplet and ruthenates", r"Sr[_]?2RuO[_]?4|ruthenate|spin-triplet|triplet pairing|odd-parity"),
    ("Topological", r"topolog|Majorana|Kitaev"),
    ("Electron–phonon", r"electron-phonon|electron–phonon|phonon-mediated|Eliashberg|MgB[_]?2|Nb[_]?3Sn|NbTi|conventional superconduct|McMillan|Allen-Dynes"),
    ("Vortices and junctions", r"Josephson|SQUID|diode effect|vortex|vortices|Meissner|flux quant|Abrikosov"),
    ("AI and data", r"machine learning|machine-learning|deep learning|neural network|data-driven|high-throughput|large language model|generative model"),
]
KINDS = {
    "theory": r"\btheor|\bmodel(s|ed|ing)?\b|Hubbard|t-J\b|mean-field|field theory|we propose|we predict|we argue|analytic|phenomenolog|effective (model|theory)",
    "computation": r"first-principles|first principles|ab initio|density functional|\bDFT\b|machine learning|neural network|Monte Carlo|DMRG|tensor network|numerical|simulation|high-throughput",
    "experiment": r"we report|we measure|measurement|we observe|observation|ARPES|photoemission|STM\b|scanning tunnel|neutron|muon|\bμSR|\bNMR\b|resistivity|specific heat|magnetization|susceptibility|thin film|single crystal|synthes|diamond anvil|spectroscop|microscop|transport|we grow|grown",
}
EXCLUDE = r"qubit|transmon|fluxonium|quantum processor|quantum computer|quantum computing|error[- ]correct|quantum memory|single-photon detector|nanowire single-photon|SNSPD|resonator|readout|circuit QED|parametric amplifier|kinetic inductance detector"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as err:  # network hiccups: retry, then give up on this source
            log(f"fetch failed ({attempt + 1}/3): {err}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}")


SUB = dict(zip("0123456789+-=()xδ", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₓδ"))
SUP = dict(zip("0123456789+-=()n*", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ*"))
TEX = {"alpha": "α", "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε",
       "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "Theta": "Θ", "kappa": "κ", "lambda": "λ",
       "Lambda": "Λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ", "tau": "τ",
       "phi": "φ", "varphi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ", "omega": "ω", "Omega": "Ω",
       "pm": "±", "mp": "∓", "times": "×", "sim": "∼", "approx": "≈", "simeq": "≃", "leq": "≤", "geq": "≥",
       "le": "≤", "ge": "≥", "lesssim": "≲", "gtrsim": "≳", "infty": "∞", "circ": "°", "prime": "′",
       "uparrow": "↑", "downarrow": "↓", "rightarrow": "→", "to": "→", "hbar": "ħ", "AA": "Å", "cdot": "·",
       "langle": "⟨", "rangle": "⟩", "parallel": "∥", "perp": "⊥", "propto": "∝", "sqrt": "√", "ell": "ℓ"}


def _script(body: str, table: dict) -> str:
    return "".join(table.get(ch, ch) for ch in body)


def tex_lite(s: str) -> str:
    """Turn the LaTeX that arXiv titles and abstracts use for formulas into plain Unicode."""
    def math(m):
        t = m.group(1)
        t = re.sub(r"\\(?:mathrm|mathbf|mathit|mathcal|text|textrm|textit|rm|bf|it|operatorname)\s*\{([^{}]*)\}", r"\1", t)
        t = re.sub(r"\\([A-Za-z]+)\s?", lambda g: TEX.get(g.group(1), g.group(1)), t)
        t = re.sub(r"_\{([^{}]*)\}|_(\S)", lambda g: _script(g.group(1) or g.group(2), SUB), t)
        t = re.sub(r"\^\{([^{}]*)\}|\^(\S)", lambda g: _script(g.group(1) or g.group(2), SUP), t)
        return t.replace("{", "").replace("}", "").replace("\\", "").replace("~", " ")
    s = re.sub(r"\$\$?([^$]*)\$?\$", math, s)
    s = re.sub(r"\\(?:emph|textit|textbf|textrm)\{([^{}]*)\}", r"\1", s)
    return s.replace("\\%", "%").replace("\\&", "&").replace("--", "–").replace("``", "“").replace("''", "”")


def html_lite(s: str) -> str:
    """Strip the HTML and JATS markup in Crossref titles and abstracts, keeping sub- and superscripts."""
    s = re.sub(r"<(?:\w+:)?sub>(.*?)</(?:\w+:)?sub>", lambda m: _script(re.sub(r"<[^>]+>", "", m.group(1)), SUB), s, flags=re.S)
    s = re.sub(r"<(?:\w+:)?sup>(.*?)</(?:\w+:)?sup>", lambda m: _script(re.sub(r"<[^>]+>", "", m.group(1)), SUP), s, flags=re.S)
    s = re.sub(r"</?(?:\w+:)?(?:p|title|sec|list|list-item|br)\b[^>]*>", " ", s)
    return re.sub(r"<[^>]+>", "", s)


def clean_text(s: str) -> str:
    s = tex_lite(html.unescape(html_lite(s or "")))
    return re.sub(r"\s+", " ", s).strip()


def tags_for(text: str) -> tuple[list, str]:
    topics = [name for name, pat in TOPICS if re.search(pat, text, re.I)][:3]
    scores = {k: len(re.findall(p, text, re.I)) for k, p in KINDS.items()}
    kind = max(scores, key=scores.get) if max(scores.values()) > 0 else ""
    return topics, kind


def short_authors(names: list) -> list:
    return names[:3] + (["et al."] if len(names) > 3 else [])


def fetch_arxiv() -> list:
    q = urllib.parse.urlencode({"search_query": "cat:cond-mat.supr-con", "sortBy": "submittedDate",
                                "sortOrder": "descending", "start": 0, "max_results": ARXIV_MAX})
    root = ET.fromstring(get("https://export.arxiv.org/api/query?" + q))
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    items = []
    for e in root.findall("a:entry", ns):
        abs_url = (e.findtext("a:id", "", ns) or "").strip()
        m = re.search(r"abs/(.+?)(v\d+)?$", abs_url)
        if not m:
            continue
        aid = m.group(1)
        title = clean_text(e.findtext("a:title", "", ns))
        abstract = clean_text(e.findtext("a:summary", "", ns))
        authors = [clean_text(a.findtext("a:name", "", ns)) for a in e.findall("a:author", ns)]
        prim = e.find("x:primary_category", ns)
        cats = [c.get("term") for c in e.findall("a:category", ns) if c.get("term")]
        topics, kind = tags_for(title + " " + abstract)
        items.append({
            "id": aid,
            "source": "arXiv",
            "title": title,
            "authors": short_authors(authors),
            "n_authors": len(authors),
            "date": (e.findtext("a:published", "", ns) or "")[:10],
            "updated": (e.findtext("a:updated", "", ns) or "")[:10],
            "category": prim.get("term") if prim is not None else "",
            "cross_list": bool(prim is not None and prim.get("term") != "cond-mat.supr-con"),
            "abstract": abstract[:ABSTRACT_MAX],
            "url": f"https://arxiv.org/abs/{aid}",
            "pdf": f"https://arxiv.org/pdf/{aid}",
            "journal_ref": clean_text(e.findtext("x:journal_ref", "", ns)),
            "doi": clean_text(e.findtext("x:doi", "", ns)),
            "topics": topics,
            "kind": kind,
            "categories": cats[:6],
        })
    log(f"arXiv: {len(items)} entries")
    return items


def crossref_date(w: dict) -> str:
    for key in ("published-online", "published-print", "published", "issued", "created"):
        parts = (w.get(key) or {}).get("date-parts") or [[]]
        p = parts[0]
        if p and p[0]:
            return "-".join(f"{x:02d}" if i else str(x) for i, x in enumerate(p + [1, 1][len(p) - 1:]))[:10]
    return ""


def fetch_journal(short: str, name: str, issns: list) -> list:
    since = (dt.date.today() - dt.timedelta(days=JOURNAL_DAYS)).isoformat()
    filt = ",".join([f"issn:{i}" for i in issns] + [f"from-pub-date:{since}", "type:journal-article"])
    q = urllib.parse.urlencode({
        "query.bibliographic": "superconductivity superconducting superconductor superconductors",
        "filter": filt, "sort": "published", "order": "desc", "rows": 100,
        "select": "DOI,title,author,container-title,published,published-online,published-print,issued,created,abstract,URL,type",
    })
    data = json.loads(get("https://api.crossref.org/works?" + q))
    items = []
    for w in data.get("message", {}).get("items", []):
        title = clean_text(" ".join(w.get("title") or []))
        if not re.search(r"supercond", title, re.I) or re.search(EXCLUDE, title, re.I):
            continue
        abstract = clean_text(w.get("abstract", ""))
        abstract = re.sub(r"^(Abstract|Summary)\s+", "", abstract)
        names = [clean_text(" ".join(x for x in (a.get("given"), a.get("family")) if x)) or clean_text(a.get("name", ""))
                 for a in (w.get("author") or [])]
        names = [n for n in names if n]
        topics, kind = tags_for(title + " " + abstract)
        doi = w.get("DOI", "")
        items.append({
            "id": doi,
            "source": short,
            "journal": name,
            "title": title,
            "authors": short_authors(names),
            "n_authors": len(names),
            "date": crossref_date(w),
            "abstract": abstract[:ABSTRACT_MAX],
            "url": f"https://doi.org/{doi}",
            "doi": doi,
            "topics": topics,
            "kind": kind,
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    log(f"{short}: {len(items)} superconductivity articles since {since}")
    return items[:JOURNAL_MAX]


def main() -> int:
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    feed = {"arxiv": old.get("arxiv", []), "journals": old.get("journals", [])}
    ok = []
    try:
        feed["arxiv"] = fetch_arxiv() or feed["arxiv"]
        ok.append("arXiv")
    except Exception as err:
        log(f"arXiv skipped: {err}")
    journals, kept = [], {x.get("source"): [] for x in feed["journals"]}
    for x in feed["journals"]:
        kept[x.get("source")].append(x)
    for short, name, issns in JOURNALS:
        time.sleep(1)
        try:
            journals += fetch_journal(short, name, issns)
            ok.append(short)
        except Exception as err:
            log(f"{short} skipped: {err}")
            journals += kept.get(short, [])
    seen, unique = set(), []
    for x in sorted(journals, key=lambda x: x["date"], reverse=True):
        if x["id"] not in seen:
            seen.add(x["id"])
            unique.append(x)
    feed["journals"] = unique
    if not ok:
        log("no source could be fetched; leaving the feed unchanged")
        return 0
    same = old.get("arxiv") == feed["arxiv"] and old.get("journals") == feed["journals"]
    if same:
        log("no change")
        return 0
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    out = {
        "schema": 1,
        "updated": now,
        "about": ("New superconductivity papers from arXiv (cond-mat.supr-con, including cross-lists) and from "
                  "Nature, Science, Physical Review Letters and Physical Review X, refreshed every three hours. "
                  "Topic and type tags are assigned automatically from keywords."),
        "sources_ok": ok,
        "arxiv": feed["arxiv"],
        "journals": feed["journals"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {OUT.relative_to(ROOT)}: {len(out['arxiv'])} arXiv and {len(out['journals'])} journal papers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
