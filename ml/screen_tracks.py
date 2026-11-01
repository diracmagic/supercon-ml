"""Directed Storm lists drawn from its existing metallic screening pool.

These lists do not create a new model or override the pool's exclusions. Pass the
ranked rows produced from ``storm_pool`` and the original structures, before
truncating to the main top-50 list. A borocarbide can occur in both lists.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd


def in_training_domain(row: Mapping) -> bool:
    """Unknown distance is exploratory, never silently treated as in-domain."""
    if row.get("outside") is True:
        return False
    value = row.get("novelty")
    try:
        return math.isfinite(float(value)) and float(value) <= 1.0
    except (TypeError, ValueError):
        return False


def directed_tracks(ranked: pd.DataFrame, structures_by_id: Mapping, *, limit: int = 50) -> dict:
    """Return separate B/C lists, with in-domain and exploration groups.

    ``ranked`` must come from Storm's already filtered metallic pool. If it also
    carries a numeric ``gap`` column, require gap <= 0.1 eV as an extra safeguard.
    Within each group order by predicted DFT Tc, descending; an unknown distance
    always enters exploration. ``limit`` is applied separately to each group.
    """
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    groups = {"borides": {"in_domain": [], "exploration": []},
              "carbides": {"in_domain": [], "exploration": []}}
    id_col = "jid" if "jid" in ranked else "id"
    if id_col not in ranked:
        return {"source": "Storm metallic screening pool", "tracks": groups}
    score_col = "storm_tc" if "storm_tc" in ranked else "tc"
    rows = ranked.copy()
    if "model" in rows:
        rows = rows[rows["model"] == "Storm"]
    if "gap" in rows:
        rows = rows[pd.to_numeric(rows["gap"], errors="coerce") <= 0.1]
    rows = rows.drop_duplicates(id_col)
    if score_col in rows:
        rows = rows.assign(_track_score=pd.to_numeric(rows[score_col], errors="coerce"))
        rows = rows.sort_values(["_track_score", id_col], ascending=[False, True], na_position="last")
    for row in rows.to_dict("records"):
        atoms = structures_by_id.get(str(row[id_col]))
        if atoms is None:
            atoms = structures_by_id.get(row[id_col])
        if not atoms:
            continue
        elements = set(atoms.get("elements", []))
        group = "in_domain" if in_training_domain(row) else "exploration"
        clean = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                 for k, v in row.items() if k != "_track_score"}
        clean["domain_group"] = group
        for key, element in (("borides", "B"), ("carbides", "C")):
            if element in elements and len(groups[key][group]) < limit:
                groups[key][group].append(dict(clean))
    return {"source": "Storm metallic screening pool", "ranking": "predicted DFT Tc within each domain group",
            "domain_rule": "finite novelty <= 1; missing distance is exploration", "tracks": groups}
