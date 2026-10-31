"""Live paper and news feed for the app: new superconductivity papers from arXiv and from Nature,
Nature Physics, Nature Materials, Nature Communications, npj Quantum Materials, Science, Physical Review
Letters and Physical Review X, plus superconductivity news from Nature and science-news sites.

Run from the repository root:  python feed/papers.py
It writes progress/papers.json, which the app reads. Only the standard library is used.
Sources:
  - arXiv API, category cond-mat.supr-con (primary and cross-listed). arXiv metadata, including
    abstracts, is offered under CC0.
  - Crossref REST API, filtered by journal ISSN and publication date; titles are matched for
    superconductivity. Abstracts are shown only when the publisher deposited one with Crossref.
  - News: the RSS feeds of Nature (news and comment only), ScienceDaily, Phys.org, Physics World,
    APS Physics and Quanta Magazine, keeping items that mention superconductivity. Only the headline,
    a short snippet and the link are kept.
  - AI for superconductivity: a second arXiv query across all categories for papers that mention
    superconductivity together with machine learning, neural networks, language models, generative
    models, active learning or autonomous labs; matching journal papers and news are added too.
Topic and type tags are assigned automatically from keywords, so they are a rough guide.
"""
from __future__ import annotations

import datetime as dt
import email.utils
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
UA = "Mozilla/5.0 (compatible; supercon-ml-feed/1.0; +https://github.com/diracmagic/supercon-ml)"
ARXIV_MAX = 80
JOURNAL_DAYS = 150
JOURNAL_MAX = 30
JOURNALS = [
    ("Nature", "Nature", ["0028-0836", "1476-4687"]),
    ("Science", "Science", ["0036-8075", "1095-9203"]),
    ("PRL", "Phys. Rev. Lett.", ["0031-9007", "1079-7114"]),
    ("PRX", "Phys. Rev. X", ["2160-3308"]),
    ("Nat. Phys.", "Nature Physics", ["1745-2473", "1745-2481"]),
    ("Nat. Mater.", "Nature Materials", ["1476-1122", "1476-4660"]),
    ("Nat. Commun.", "Nature Communications", ["2041-1723"]),
    ("npj Quantum Mater.", "npj Quantum Materials", ["2397-4648"]),
]
ABSTRACT_MAX = 1400
NEWS_FEEDS = [
    ("Nature News", "https://www.nature.com/nature.rss"),   # RSS 1.0; research papers there come from Crossref instead
    ("ScienceDaily", "https://www.sciencedaily.com/rss/matter_energy/superconductors.xml"),
    ("Phys.org", "https://phys.org/rss-feed/physics-news/superconductivity/"),
    ("Physics World", "https://physicsworld.com/feed/"),
    ("APS Physics", "https://feeds.aps.org/rss/recent/physics.xml"),
    ("Quanta Magazine", "https://www.quantamagazine.org/feed/"),
]
AI_ARXIV_MAX = 60
AI_MAX = 80
# AI-for-superconductivity items: a paper or story qualifies when it mentions superconductivity and one of these
AI_PATTERN = (r"machine[- ]learn|deep[- ]learn|neural[- ]network|graph neural|neural (?:quantum state|operator|tensor)|"
              r"language model|generative (?:model|AI|design)|diffusion model|active learning|Bayesian optimi[sz]|"
              r"autonomous (?:lab|laborator|experiment|discovery|agent)|self-driving lab|foundation model|"
              r"artificial intelligence")
AI_CAPS = r"\bAI\b|\bLLMs?\b|\bAI-(?:driven|guided|designed|assisted|based)"   # matched case-sensitively
# quantum-computing and superconducting-electronics papers that mention machine learning are not about materials
AI_DEVICE = (r"qubit|transmon|fluxonium|quantum (?:processor|computer|computing|circuit|device|error|state discrimination|"
             r"memory|router|neural network|generative)|circuit QED|readout|superconducting (?:logic|circuit|electronics|"
             r"detector|nanowire|resonator|cavit|digital|qubit|perceptron|neural)|SNSPD|single-photon|"
             r"cryogenic (?:computing|electronics)|neuromorphic|perceptron|spiking")
AI_TITLE = AI_PATTERN + r"|\bneural\b|\blearning\b|transformer|data-driven|\bagents?\b"
SC_TITLE = r"supercond|electron-phonon|electron–phonon|\bpairing\b|Cooper|Eliashberg"
AI_CATS = ("cond-mat", "physics.comp-ph", "physics.chem-ph", "physics.app-ph", "cs.LG", "cs.AI", "cs.CL", "cs.IR",
           "stat.ML", "hep-th")
AI_QUERY = ('(ti:superconductor OR ti:superconductors OR ti:superconductivity OR ti:superconducting OR '
            'abs:superconductor OR abs:superconductors OR abs:superconductivity OR abs:superconducting) AND '
            '(abs:"machine learning" OR abs:"deep learning" OR abs:"neural network" OR abs:"neural networks" OR '
            'abs:"language model" OR abs:"language models" OR abs:"generative model" OR abs:"active learning" OR '
            'abs:"graph neural" OR abs:"foundation model" OR abs:"autonomous" OR abs:"artificial intelligence" OR '
            'abs:"Bayesian optimization" OR abs:"machine-learned")')
NEWS_DAYS = 180
NEWS_MAX = 40
SNIPPET_MAX = 280

TOPICS = [
    ("Cuprates", r"cuprate|CuO[_]?2|YBa[_]?2Cu|YBCO|Bi[_]?2Sr[_]?2|Bi-?22[01]2|La[_]?2-?x?Sr|LSCO|Hg-?12[0-9]{2}|HgBa|Nd[_]?2-?x?Ce|copper oxide"),
    ("Nickelates", r"nickelate|La[_]?3Ni[_]?2O|La[_]?4Ni[_]?3O|Ni[_]?2O[_]?7|NdNiO|PrNiO|infinite-layer"),
    ("Iron-based", r"iron-based|iron pnictide|iron chalcogenide|pnictide|FeSe|FeTe|FeAs|BaFe[_]?2|LiFeAs|Fe-based"),
    ("Hydrides", r"hydride|H[_]?3S\b|LaH[_]?10|superhydride|hydrogen-rich|CeH[_]?9|YH[_]?[69]|LaBeH|LaSc[_]?2H|ternary hydride"),
    ("Moiré and 2D", r"twisted|moir[eé]|graphene|WSe[_]?2|MoTe[_]?2|rhombohedral|van der Waals|monolayer|two-dimensional"),
    ("Kagome", r"kagome|CsV[_]?3Sb[_]?5|KV[_]?3Sb[_]?5|RbV[_]?3Sb[_]?5|AV[_]?3Sb[_]?5"),
    ("Heavy fermions", r"heavy[- ]fermion|Kondo|CeCoIn|CeRh[_]?2As|UTe[_]?2|uranium ditelluride|UPt[_]?3|URhGe|UCoGe|CeCu[_]?2Si"),
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
# News stories are kept but tagged "Quantum devices" when the headline is about devices or the text names one; a materials
# story that only says it "could help build quantum computers" is not a device story.
DEVICE_TITLE = EXCLUDE + r"|superconducting circuit|quantum information|quantum technolog"
DEVICE_TEXT = r"qubit|transmon|fluxonium|quantum processor|quantum memory|circuit QED|single-photon detector|SNSPD|parametric amplifier|kinetic inductance detector"
# Titles from news feeds and Crossref often carry Unicode sub- and superscripts (La₃Ni₂O₇, UTe₂); match them like plain digits.
PLAIN_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹₊₋⁺⁻", "01234567890123456789+-+-")


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
    text = text.translate(PLAIN_DIGITS)
    topics = [name for name, pat in TOPICS if re.search(pat, text, re.I)][:3]
    scores = {k: len(re.findall(p, text, re.I)) for k, p in KINDS.items()}
    kind = max(scores, key=scores.get) if max(scores.values()) > 0 else ""
    return topics, kind


def short_authors(names: list) -> list:
    return names[:3] + (["et al."] if len(names) > 3 else [])


def is_ai(x: dict) -> bool:
    """True for a paper or story about AI or machine learning for superconductivity: it names an AI method, is not
    about quantum devices, and has superconductivity in the title, or in the text with AI or pairing in the title."""
    title = x.get("title", "")
    text = title + " " + x.get("abstract", x.get("summary", ""))
    if not (re.search(AI_PATTERN, text, re.I) or re.search(AI_CAPS, text)):
        return False
    if re.search(AI_DEVICE, text, re.I) or re.search(EXCLUDE, title, re.I):
        return False
    cat = x.get("category", "")
    if x.get("source") == "arXiv" and cat and not cat.startswith(AI_CATS):
        return False
    if re.search(r"supercond", title, re.I):
        return True
    if not (re.search(r"superconductors?\b|superconductivity|critical temperatures?", text, re.I) or re.search(r"\bT_?c\b", text)):
        return False
    return bool(re.search(AI_TITLE, title, re.I) or re.search(AI_CAPS, title) or re.search(SC_TITLE, title, re.I))


def fetch_arxiv(query: str = "cat:cond-mat.supr-con", max_results: int = ARXIV_MAX) -> list:
    q = urllib.parse.urlencode({"search_query": query, "sortBy": "submittedDate",
                                "sortOrder": "descending", "start": 0, "max_results": max_results})
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
    log(f"arXiv ({query[:40]}): {len(items)} entries")
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


def parse_date(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError, IndexError):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        return m.group(1) if m else ""


RSS1 = "{http://purl.org/rss/1.0/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def fetch_news(name: str, url: str) -> list:
    root = ET.fromstring(get(url))
    atom = "{http://www.w3.org/2005/Atom}"
    entries = root.findall(".//item") or root.findall(f".//{RSS1}item") or root.findall(f".//{atom}entry")
    since = (dt.date.today() - dt.timedelta(days=NEWS_DAYS)).isoformat()
    items = []
    for e in entries:
        def text(tag):
            for t in (tag, RSS1 + tag, atom + tag):
                el = e.find(t)
                if el is not None and el.text:
                    return el.text
            return ""
        title = clean_text(text("title"))
        desc = clean_text(text("description") or text("summary") or text(CONTENT + "encoded") or text("content"))
        # Nature's feed starts each item with "Nature, Published online: <date>; doi:<doi>"
        desc = re.sub(r"^Nature, Published online:[^;]*;\s*doi:\S+\s*", "", desc)
        link = text("link").strip()
        if not link:
            el = e.find(atom + "link")
            link = el.get("href", "") if el is not None else ""
        date = parse_date(text("pubDate") or text("published") or text("updated") or text(DC + "date"))
        if not title or not link.startswith("http") or not re.search(r"supercond", title + " " + desc, re.I):
            continue
        if name == "Nature News" and "/d41586-" not in link:   # keep news and comment, not research papers
            continue
        if date and date < since:
            continue
        snippet = desc if len(desc) <= SNIPPET_MAX else desc[:SNIPPET_MAX].rsplit(" ", 1)[0] + "…"
        topics, _ = tags_for(title + " " + desc)
        if re.search(DEVICE_TITLE, title, re.I) or re.search(DEVICE_TEXT, desc, re.I):
            topics = (topics + ["Quantum devices"])[:3]
        items.append({"id": link, "source": name, "title": title, "date": date, "summary": snippet, "url": link, "topics": topics})
    log(f"news, {name}: {len(items)} superconductivity items")
    return items


def main() -> int:
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    feed = {"arxiv": old.get("arxiv", []), "journals": old.get("journals", []), "news": old.get("news", []),
            "ai": old.get("ai", [])}
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
    news, kept_news = [], {}
    for x in feed["news"]:
        kept_news.setdefault(x.get("source"), []).append(x)
    for name, url in NEWS_FEEDS:
        time.sleep(1)
        try:
            news += fetch_news(name, url)
            ok.append(name)
        except Exception as err:
            log(f"news, {name} skipped: {err}")
            news += kept_news.get(name, [])
    seen_n, uniq_n = set(), []
    for x in sorted(news, key=lambda x: x.get("date", ""), reverse=True):
        key = re.sub(r"\W+", " ", x["title"].lower()).strip()
        if x["url"] not in seen_n and key not in seen_n:
            seen_n.update([x["url"], key])
            uniq_n.append(x)
    feed["news"] = uniq_n[:NEWS_MAX]
    # AI for superconductivity: its own arXiv query across categories, plus matching items from the other lists
    ai_arxiv = None
    try:
        time.sleep(3)   # arXiv asks for a pause between API calls
        ai_arxiv = fetch_arxiv(AI_QUERY, AI_ARXIV_MAX)
        ok.append("arXiv AI")
    except Exception as err:
        log(f"arXiv AI query skipped: {err}")
    pool = [dict(x, kind_of="paper") for x in (ai_arxiv if ai_arxiv is not None else
                                               [y for y in feed["ai"] if y.get("source") == "arXiv"])]
    pool += [dict(x, kind_of="paper") for x in feed["arxiv"] + feed["journals"]]
    pool += [dict(x, kind_of="news") for x in feed["news"]]
    seen_ai, ai = set(), []
    for x in sorted(pool, key=lambda x: x.get("date", ""), reverse=True):
        key = x.get("doi") or x.get("id") or x.get("url")
        if key in seen_ai or not is_ai(x):
            continue
        seen_ai.add(key)
        ai.append(x)
    feed["ai"] = ai[:AI_MAX]
    log(f"AI for superconductivity: {len(feed['ai'])} items")
    if not ok:
        log("no source could be fetched; leaving the feed unchanged")
        return 0
    same = all(old.get(k) == feed[k] for k in ("arxiv", "journals", "news", "ai"))
    if same:
        log("no change")
        return 0
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    out = {
        "schema": 1,
        "updated": now,
        "about": ("New superconductivity papers from arXiv (cond-mat.supr-con, including cross-lists) and from "
                  "Nature, Nature Physics, Nature Materials, Nature Communications, npj Quantum Materials, Science, "
                  "Physical Review Letters and Physical Review X, and superconductivity news from Nature and "
                  "science-news sites, refreshed every three hours. Topic and type tags are assigned automatically."),
        "sources": {"journals": [[s, n] for s, n, _ in JOURNALS], "news": [n for n, _ in NEWS_FEEDS]},
        "sources_ok": ok,
        "arxiv": feed["arxiv"],
        "journals": feed["journals"],
        "news": feed["news"],
        "ai": feed["ai"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"wrote {OUT.relative_to(ROOT)}: {len(out['arxiv'])} arXiv and {len(out['journals'])} journal papers, "
        f"{len(out['news'])} news items, {len(out['ai'])} AI-for-superconductivity items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
