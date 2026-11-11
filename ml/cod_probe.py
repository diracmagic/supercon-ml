"""COD access probe (count-only): how the Crystallography Open Database's own table can be read.

The JARVIS-tools copy of the COD (2021, 431,778 entries) holds the cells and the atoms only: no formula as published, no
space group, no mark for disorder, duplicates, retracted or calculated entries, and a site that is partly occupied counts
there as a whole atom. The COD's own `data` table has all of these. This probe asks the COD's public interfaces what
they return, so that a pool can read the table itself:

- the REST interface (https://www.crystallography.net/cod/result): a count, and the columns of a small CSV result;
- the public read-only database (user cod_reader, no password, as the COD documents it): the columns of the table and
  how its entries divide by method, status and flags, and how many have 2 to 5 elements and no hydrogen.

Nothing is stored and no model is involved. The COD's data are in the public domain (crystallography.net/cod); cite
Grazulis et al., J. Appl. Cryst. 42, 726 (2009) and Nucleic Acids Res. 40, D420 (2012). The report goes into the job log
between markers.
"""
import collections
import csv
import hashlib
import io
import json
import sys
import time

REST = "https://www.crystallography.net/cod/result"
HOSTS = ["www.crystallography.net", "sql.crystallography.net"]
KEY = ["file", "formula", "calcformula", "cellformula", "Z", "Zprime", "vol", "a", "b", "c", "alpha", "beta", "gamma", "nel", "sg",
       "sgHall", "sgNumber", "method", "flags", "status", "duplicateof", "optimal", "onhold", "year", "date", "mineral",
       "compoundsource", "celltemp", "diffrtemp", "cellpressure", "diffrpressure", "doi", "journal"]


def rest(params: dict, timeout: int = 300) -> tuple[int, str, float, str]:
    import requests
    t0 = time.time()
    r = requests.get(REST, params=params, timeout=timeout, headers={"User-Agent": "supercon-ml pool census (count-only probe)"})
    return r.status_code, r.text, round(time.time() - t0, 1), r.url


def table(text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return {"rows": 0, "head": text[:300]}
    cols = list(rows[0].keys())
    out = {"rows": len(rows), "columns": cols, "filled": {c: sum(1 for r in rows if str(r.get(c) or "").strip() not in ("", "NULL")) for c in cols}}
    out["examples"] = {c: [str(r.get(c))[:80] for r in rows[:3]] for c in cols if c in KEY}
    for c in ("method", "flags", "status", "sg"):
        if c in cols:
            out["values: " + c] = dict(collections.Counter(str(r.get(c)) for r in rows).most_common(12))
    return out


def probe_rest() -> dict:
    out = {}
    for name, params in [
        ("count: Hg-Ba-Cu-O, no H", {"format": "count", "el1": "Hg", "el2": "Ba", "el3": "Cu", "el4": "O", "nel1": "H"}),
        ("count: 2 to 5 elements, no H", {"format": "count", "nel1": "H", "strictmin": "2", "strictmax": "5"}),
        ("count: 2 to 5 elements, no H, no C", {"format": "count", "nel1": "H", "nel2": "C", "strictmin": "2", "strictmax": "5"}),
        ("count: everything", {"format": "count"}),
    ]:
        try:
            code, text, secs, url = rest(params)
            out[name] = {"status": code, "seconds": secs, "url": url, "answer": text.strip()[:200]}
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    for name, params in [
        ("csv: Hg-Ba-Cu-O, no H", {"format": "csv", "el1": "Hg", "el2": "Ba", "el3": "Cu", "el4": "O", "nel1": "H"}),
        ("csv: exactly 2 elements with Nb, no H", {"format": "csv", "el1": "Nb", "nel1": "H", "strictmin": "2", "strictmax": "2"}),
    ]:
        try:
            code, text, secs, url = rest(params)
            out[name] = {"status": code, "seconds": secs, "url": url, "bytes": len(text.encode("utf-8")), **table(text)}
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    # the size and time of one large export: every entry with exactly three elements and no hydrogen
    try:
        code, text, secs, url = rest({"format": "csv", "nel1": "H", "strictmin": "3", "strictmax": "3"}, timeout=900)
        rows = text.count("\n")
        out["csv: exactly 3 elements, no H (size only)"] = {"status": code, "seconds": secs, "url": url, "bytes": len(text.encode("utf-8")),
                                                            "lines": rows, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    except Exception as exc:
        out["csv: exactly 3 elements, no H (size only)"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return out


def probe_sql() -> dict:
    out = {}
    try:
        import pymysql
    except ImportError as exc:
        return {"error": f"{exc}"}
    for host in HOSTS:
        t0 = time.time()
        try:
            con = pymysql.connect(host=host, user="cod_reader", password="", database="cod", connect_timeout=30, read_timeout=600)
        except Exception as exc:
            out[host] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            continue
        rep = {"connected_s": round(time.time() - t0, 1)}
        try:
            with con.cursor() as cur:
                def q(sql):
                    cur.execute(sql)
                    return [[(v.decode("utf-8", "replace") if isinstance(v, bytes) else v) for v in row] for row in cur.fetchall()]
                rep["entries"] = q("SELECT COUNT(*) FROM data")[0][0]
                rep["columns"] = [[r[0], str(r[1])] for r in q("SHOW COLUMNS FROM data")]
                rep["newest"] = [str(v) for v in q("SELECT MAX(date), MAX(file) FROM data")[0]]
                for col in ("method", "status", "flags", "onhold IS NOT NULL", "duplicateof IS NOT NULL", "optimal IS NOT NULL"):
                    rep["by " + col] = [[str(a), int(b)] for a, b in q(f"SELECT {col}, COUNT(*) FROM data GROUP BY 1 ORDER BY 2 DESC LIMIT 20")]
                no_h = "formula NOT REGEXP ' H[0-9. ]' AND formula NOT REGEXP ' D[0-9. ]'"
                rep["2 to 5 elements, no H"] = q(f"SELECT COUNT(*) FROM data WHERE nel BETWEEN 2 AND 5 AND {no_h}")[0][0]
                rep["2 to 5 elements, no H, by nel"] = q(f"SELECT nel, COUNT(*) FROM data WHERE nel BETWEEN 2 AND 6 AND {no_h} GROUP BY nel")
                rep["2 to 5 elements, no H, with disorder"] = q(f"SELECT COUNT(*) FROM data WHERE nel BETWEEN 2 AND 5 AND {no_h} AND FIND_IN_SET('has disorder', flags)")[0][0]
                rep["2 to 5 elements, no H, usable"] = q(f"SELECT COUNT(*) FROM data WHERE nel BETWEEN 2 AND 5 AND {no_h} AND status IS NULL "
                                                         "AND duplicateof IS NULL AND onhold IS NULL AND (method IS NULL OR method <> 'theoretical')")[0][0]
                rep["sample"] = [dict(zip(["file", "formula", "calcformula", "cellformula", "Z", "vol", "sg", "sgHall", "method", "flags", "status", "year"],
                                          [str(v)[:60] for v in row]))
                                 for row in q("SELECT file, formula, calcformula, cellformula, Z, vol, sg, sgHall, method, flags, status, year FROM data "
                                              "WHERE formula LIKE '%Cu%' AND formula LIKE '%Ba%' AND formula LIKE '%Hg%' AND nel = 4 LIMIT 5")]
        except Exception as exc:
            rep["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        finally:
            con.close()
        rep["seconds"] = round(time.time() - t0, 1)
        out[host] = rep
        if "error" not in rep:
            break
    return out


def emit(report: dict, tag: str) -> None:
    text = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    print(f"=== {tag} begin")
    for i in range(0, len(text), 2000):
        print(f"cp|{i // 2000:03d}|{text[i:i + 2000]}")
    print(f"=== {tag} end sha256 " + hashlib.sha256(text.encode("utf-8")).hexdigest() + " chars " + str(len(text)))


def main():
    emit({"step": "cod-probe", "rest": probe_rest(), "sql": probe_sql()}, "cod-probe")


if __name__ == "__main__":
    main()
