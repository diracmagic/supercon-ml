"""Hurricane 6 experiment: frozen MACE-MP-0 inputs, evaluated only by leaving families out.

    python ml/hurricane6.py                 # real structures/model, CPU; cache is reused
    python ml/hurricane6.py --smoke         # synthetic plumbing check, NOT a model result
    python ml/hurricane6.py --protocol      # print the predeclared comparison without training
    python ml/hurricane6.py --prepare-only  # original-CIF coverage audit; no MACE or fitting

H4 stays in use. This experiment never writes progress.json and never releases a
model. The target is a *parent's observed superconducting descendants*, not whether
its undoped formula superconducts. Hosono's condition-specific sample nulls are
validated separately and cannot be negatives for that parent-potential target.

Set HURRICANE_3DSC_ROOT to a local 3DSC/superconductors_3D directory to read
original CIFs offline. Otherwise individual original CIFs are downloaded from the
same pinned 3DSC commit as the tabular data. No lattice/atom positions are invented.
MACE inputs include the JARVIS weak-negative background, also cached. Neither a
test family nor a held-out background chemical system enters the model that scores it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd

import hurricane as H
import hurricane2 as H2
import hurricane3 as H3
import hurricane4 as H4
import hurricane5 as H5
import negative_data as ND
import pipeline as P
import screen as SC

ROUND = 6
DESIGNS = ("H4", "P1", "M1")
MODEL_URL = "https://github.com/ACEsuit/mace-mp/releases/download/mace_mp_0/2023-12-03-mace-128-L1_epoch-199.model"
PROTOCOL = {
    "version": "hurricane6-lofo-v1",
    "target": ND.PARENT_TARGET,
    "target_definition": "One original MP structure; label positive if any linked SuperCon entry has Tc>0; regression target is their highest observed Tc. Zero only means no superconducting entry was observed among those linked in this dataset; it does not disprove potential under all dopings or pressures.",
    "evaluation": "Four fixed leave-one-family-out tests, with identical parent test rows across designs; no grouped-CV score is used for this comparison.",
    "families": list(H.FAMILY_LABEL),
    "designs": {"H4": "Released H4 entry model, asked about parents", "P1": "H4 inputs and settings, trained on parents", "M1": "P1 plus frozen MACE-MP-0 medium invariant mean/std/max descriptors"},
    "mace_model": "medium",
    "mace_checkpoint_url": MODEL_URL,
    "3dsc_commit": H.DSC_COMMIT,
    "3dsc_sha256": H.DSC_SHA256,
    "regressor_params": dict(H.PARAMS),
    "classifier_params": dict(H2.CLF_PARAMS),
    "reference_settings": {"two_part": "mean", "background": 0.3, "radius": 1.0, "abstain": 1.0},
    "structure_min_fraction": 0.95,
    "primary": "Macro-average fraction of positive parents found (p>=0.5 and not abstained) across held-out families.",
    "promising_rule": {"macro_found_gain_over_both_references": 0.05, "extra_positive_parents_over_both_references": 10,
                       "paired_chemical_system_bootstrap_lower95_gain_over_both": 0.0,
                       "brier_tolerance_over_each_reference": 0.01, "macro_tc_mae_tolerance_K": 1.0,
                       "unknown_rate_increase_over_each_reference": 0.05, "max_background_false_alarms": 0.05},
    "threshold": 0.5,
    "bootstrap": {"resamples": 1000, "seed": P.SEED, "unit": "chemical system, sampled within each family"},
    "weak_background": "H4's JARVIS compounds without a superconductivity record, label 0 at weight 0.3; these are explicitly weak labels, not measured negatives. Keep only H4's radius in handcrafted inputs.",
    "gating": "H4 abstention/radius in handcrafted inputs, held fixed between P1 and M1 so embedding gains cannot come solely from changed abstention geometry.",
    "negative_evidence": "Hosono sample nulls are audited but not used for this parent target; no Tc=0 is imputed from a temperature-censored observation.",
    "publication": "Report-only challenger. adopted is always false; H4 current and progress.json remain untouched. Any release needs a separate preregistered independent evaluation.",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def protocol() -> dict:
    # Return a fresh copy so callers cannot mutate the declared comparison in memory.
    return json.loads(json.dumps(PROTOCOL))


def safe_cif_path(value: str) -> str:
    """Only pinned-repository-relative CIF paths; never URL/path traversal or doped structures."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("missing or unsafe original CIF path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ":" in value or path.suffix.lower() != ".cif":
        raise ValueError("unsafe original CIF path")
    if "synth_doped" in value.lower():
        raise ValueError("artificially doped CIF cannot represent an undoped parent")
    return str(path)


def cif_bytes(relative: str, *, local_root: Path | None = None, cache: Path | None = None) -> bytes:
    relative = safe_cif_path(relative)
    if local_root is not None:
        base = Path(local_root).resolve()
        path = (base / relative).resolve()
        if base not in path.parents:
            raise ValueError("original CIF escaped the configured local root")
        return path.read_bytes()
    cache = Path(cache or (P.CACHE / "hurricane6_cifs"))
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((H.DSC_COMMIT + "/" + relative).encode()).hexdigest()
    path = cache / (key + ".cif")
    if path.exists():
        return path.read_bytes()
    url = f"https://raw.githubusercontent.com/aimat-lab/3DSC/{H.DSC_COMMIT}/superconductors_3D/{urllib.parse.quote(relative, safe='/')}"
    request = urllib.request.Request(url, headers={"User-Agent": "supercon-ml hurricane6 original-structure audit"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
            break
        except urllib.error.HTTPError:
            raise  # a missing published structure is an explicit exclusion
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                raise RuntimeError(f"original-CIF download unavailable: {url}: {error}") from error
            time.sleep(attempt + 1)
    if not content or b"<html" in content[:1000].lower() or b"_cell_length_a" not in content:
        raise ValueError("download is not a CIF")
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return content


def original_structures(parents: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Original ordered MP structures only; return explicit exclusions, without approximating disorder."""
    from pymatgen.core import Structure

    rows, excluded = [], []
    local = os.environ.get("HURRICANE_3DSC_ROOT")
    for index, parent in parents.iterrows():
        source = parent["row"]
        try:
            # Cleaned intermediate CIFs named by cif_before_synthetic_doping are
            # not all published on GitHub; the original MP CIF is published and
            # has actual undoped atomic positions, rather than a reconstructed cell.
            column = "original_cif_2" if isinstance(source.get("original_cif_2"), str) else "cif_before_synthetic_doping"
            relative = safe_cif_path(source.get(column))
            raw = cif_bytes(relative, local_root=Path(local) if local else None)
            structure = Structure.from_str(raw.decode("utf-8"), fmt="cif")
            if not structure.is_ordered:
                raise ValueError("original structure has partial occupancy; no arbitrary ordering is allowed")
            wanted, actual = parent["comp"], structure.composition.get_el_amt_dict()
            nt, na = sum(wanted.values()), sum(actual.values())
            if set(wanted) != set(actual) or any(abs(wanted[e] / nt - actual[e] / na) > 1e-5 for e in wanted):
                raise ValueError("original CIF composition disagrees with the parent formula")
            content_hash = hashlib.sha256(raw).hexdigest()
            atoms = {"lattice_mat": structure.lattice.matrix.tolist(), "coords": structure.frac_coords.tolist(),
                     "elements": [site.specie.symbol for site in structure], "cartesian": False,
                     "props": ["" for _ in structure]}
            rows.append({"parent_index": index, "id": f"{parent['material_id']}:{content_hash}", "atoms": atoms,
                         "material_id": str(parent["material_id"]), "cif": relative, "cif_source_column": column,
                         "cif_sha256": content_hash})
        except (OSError, ValueError, TypeError, KeyError) as error:
            excluded.append({"material_id": str(parent["material_id"]), "reason": str(error)})
    return pd.DataFrame(rows), excluded


def descriptor_key(frame: pd.DataFrame, role: str) -> str:
    # IDs in pipeline.mace_descriptors are checked on cache load; the content hash in
    # this key additionally invalidates caches if coordinates/species/order change.
    content = [{"id": str(r["id"]), "atoms": r["atoms"]} for _, r in frame.iterrows()]
    return f"hurricane6_{role}_{digest(content)[:24]}"


def descriptor_generation() -> dict:
    versions = {}
    for name in ("mace-torch", "torch", "numpy", "jarvis-tools"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"packages": versions, "aggregation_sha256": hashlib.sha256(inspect.getsource(P.mace_descriptors).encode()).hexdigest(),
            "checkpoint_url": MODEL_URL, "model": P.MACE_MODEL}


def checkpoint_identity() -> dict:
    """Verify the explicit MP-0 alias before using the shared descriptor implementation."""
    from mace.calculators.foundations_models import download_mace_mp_checkpoint, mace_mp_urls
    if mace_mp_urls.get(P.MACE_MODEL) != MODEL_URL:
        raise ValueError("MACE's medium alias changed; declare a new checkpoint/protocol before evaluating")
    path = Path(download_mace_mp_checkpoint(P.MACE_MODEL))
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    return {"checkpoint_url": MODEL_URL, "checkpoint_sha256": sha.hexdigest()}


def embeddings(frame: pd.DataFrame, role: str) -> tuple[np.ndarray, dict]:
    if P.MACE_MODEL != PROTOCOL["mace_model"]:
        raise ValueError("H6 protocol fixes MACE_MODEL=medium; a different checkpoint requires a new protocol")
    generation = descriptor_generation()
    structure_key = descriptor_key(frame, role)
    cache_key = f"{structure_key}_{digest(generation)[:16]}"
    manifest_dir = P.CACHE / "hurricane6_descriptor_manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / f"{cache_key}.json"
    identity = None
    if manifest.exists():
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        if saved.get("generation") == generation and saved.get("checkpoint", {}).get("checkpoint_url") == MODEL_URL:
            identity = saved["checkpoint"]
    verified_now = False
    if not identity or not identity.get("checkpoint_sha256"):
        identity = checkpoint_identity()
        verified_now = True
        manifest.write_text(json.dumps({"generation": generation, "checkpoint": identity}, indent=2) + "\n", encoding="utf-8")
    # Reuse the existing aggregation, but checkpoint batches so an interrupted
    # 1,700-material background does not lose all computed descriptors.
    keys, batches = [], []
    for offset in range(0, len(frame), 128):
        chunk = frame.iloc[offset:offset + 128]
        key = f"{cache_key}_{identity['checkpoint_sha256'][:16]}_{offset}"
        keys.append(key)
        descriptor_cache = P.CACHE / f"mace_mp0_{P.MACE_MODEL}_{key}.npz"
        if not descriptor_cache.exists() and not verified_now:
            current_checkpoint = checkpoint_identity()
            if current_checkpoint != identity:
                raise ValueError("checkpoint bytes changed since these descriptors were generated; a mixed cache is forbidden")
            verified_now = True
        batches.append(np.asarray(P.mace_descriptors(chunk, key), dtype=float))
    values = np.vstack(batches) if batches else np.zeros((0, 0))
    if values.ndim != 2 or len(values) != len(frame) or not values.shape[1] or not np.isfinite(values).all():
        raise ValueError("MACE descriptors are not a finite row-aligned matrix")
    return values, {"keys": keys, "batch_size": 128, "n": len(frame), "features": values.shape[1],
                    "structure_fingerprint": digest([{ "id": str(r["id"]), "atoms": r["atoms"]} for _, r in frame.iterrows()]),
                    "model": P.MACE_MODEL, **identity, "descriptor_generation": generation}


def leave_family_masks(families, systems, held_family: str) -> tuple[np.ndarray, np.ndarray]:
    """Hold out the family AND every chemical system it uses, including mixed-label systems."""
    families, systems = np.asarray(families), np.asarray(systems)
    test = families == held_family
    held_systems = np.unique(systems[test])
    train = (~test) & ~np.isin(systems, held_systems)
    if not test.any() or not train.any():
        raise ValueError(f"empty LOFO train/test for {held_family}")
    return train, test


def background_masks(systems, held_systems, fold: int | None = None):
    systems = np.asarray(systems)
    train = ~np.isin(systems, sorted(set(held_systems)))
    if fold is not None:
        train &= np.array([H3.bg_fold(s) != fold for s in systems])
    return train


def found_mask(p, unknown, threshold=0.5):
    return (np.asarray(p) >= threshold) & ~np.asarray(unknown, bool)


def summary(y, p, tc, unknown) -> dict:
    y, p, tc, unknown = np.asarray(y), np.asarray(p), np.asarray(tc), np.asarray(unknown, bool)
    positive = y > 0
    found = found_mask(p, unknown)
    return {"n": len(y), "n_sc": int(positive.sum()), "n_found": int((found & positive).sum()),
            "found": float(found[positive].mean()) if positive.any() else None,
            "unknown_sc": float(unknown[positive].mean()) if positive.any() else None,
            "tc_mae": float(np.abs(tc - y).mean()), "brier": float(np.mean((p - positive) ** 2))}


def bootstrap_gain(y, families, systems, current_found, reference_found, *, resamples=1000, seed=P.SEED):
    """Paired chemical-system bootstrap within families; positive parents only for recall."""
    y, families, systems = np.asarray(y), np.asarray(families), np.asarray(systems)
    difference = np.asarray(current_found, float) - np.asarray(reference_found, float)
    blocks = []
    for family in H.FAMILY_LABEL:
        eligible = (families == family) & (y > 0)
        groups = np.unique(systems[eligible])
        if len(groups):
            blocks.append([np.where(eligible & (systems == group))[0] for group in groups])
    if not blocks:
        raise ValueError("no positive-parent groups for paired bootstrap")
    rng, gains = np.random.default_rng(seed), []
    for _ in range(resamples):
        means = []
        for family_blocks in blocks:
            chosen = rng.integers(0, len(family_blocks), size=len(family_blocks))
            positions = np.concatenate([family_blocks[i] for i in chosen])
            means.append(float(difference[positions].mean()))
        gains.append(float(np.mean(means)))
    return {"lower95": float(np.quantile(gains, 0.025)), "upper95": float(np.quantile(gains, 0.975)),
            "resamples": resamples, "unit": "chemical system within held-out family"}


def score_design(c: dict, Xp, Xe, Xb, gate_p, gate_e, gate_b, y, ye, fam, fame, systems, syse, sysb, *, seed=P.SEED):
    """LOFO only. Background false alarms additionally cross-fit by their own system hash."""
    pred, probability, unknown = np.zeros(len(y)), np.zeros(len(y)), np.zeros(len(y), bool)
    rows, background_rows = [], []
    entry = c.get("rows") == "entry"
    for family in H.FAMILY_LABEL:
        train_p, test = leave_family_masks(fam, systems, family)
        held = set(systems[test])
        train_e = (fame != family) & ~np.isin(syse, sorted(held))
        train_X, train_y, train_fam = (Xe[train_e], ye[train_e], fame[train_e]) if entry else (Xp[train_p], y[train_p], fam[train_p])
        gate, gate_systems = (gate_e[train_e], syse[train_e]) if entry else (gate_p[train_p], systems[train_p])
        ratio_b = H4.ratio(gate, gate_systems, gate_b)
        near = ratio_b <= c.get("radius", 1.0)
        use = background_masks(sysb, held) & near
        model = H2.Design(c, seed).fit(train_X, train_y, train_fam, Xb=Xb[use])
        tc = model.predict(Xp[test], fam[test])
        prob, _ = SC.hur_parts(model, Xp[test], fam[test])
        if not np.isfinite(prob).all():
            raise ValueError(f"{c['id']} cannot give probabilities for {family}")
        unk = H4.ratio(gate, gate_systems, gate_p[test]) > c.get("abstain", 1.0)
        pred[test], probability[test], unknown[test] = tc, prob, unk
        row = dict(family=family, **summary(y[test], prob, tc, unk), n_train=len(train_X), n_background=int(use.sum()),
                   held_systems=sorted(held), train_systems=sorted(set(gate_systems)))
        rows.append(row)
        # Five *separate* fits for background evaluation. A background compound's
        # own chemical-system fold is absent; it is never averaged with fits that saw it.
        for fold in range(P.N_FOLDS):
            test_b = np.array([H3.bg_fold(s) == fold for s in sysb])
            if not test_b.any():
                continue
            # Background systems can also occur among 3DSC's measured-zero
            # entries. Remove the held-out systems from *both* training sources,
            # including the reference set used for distances.
            held_b = set(sysb[test_b])
            keep_p = train_p & ~np.isin(systems, sorted(held_b))
            keep_e = train_e & ~np.isin(syse, sorted(held_b))
            bx, by, bfamily = (Xe[keep_e], ye[keep_e], fame[keep_e]) if entry else (Xp[keep_p], y[keep_p], fam[keep_p])
            bgate, bsystems = (gate_e[keep_e], syse[keep_e]) if entry else (gate_p[keep_p], systems[keep_p])
            ratio_fold = H4.ratio(bgate, bsystems, gate_b)
            train_b = background_masks(sysb, held | held_b, fold) & (ratio_fold <= c.get("radius", 1.0))
            model_b = H2.Design(c, seed + fold).fit(bx, by, bfamily, Xb=Xb[train_b])
            pb, _ = SC.hur_parts(model_b, Xb[test_b], np.array(["unknown"] * int(test_b.sum())))
            unk_b = ratio_fold[test_b] > c.get("abstain", 1.0)
            for index, pvalue, unknown_value in zip(np.where(test_b)[0], pb, unk_b):
                background_rows.append({"design": c["id"], "left_out_family": family, "index": int(index),
                                        "chemsys": str(sysb[index]), "background_fold": fold,
                                        "p_sc": float(pvalue), "not_known": bool(unknown_value),
                                        "training_system_overlap": bool(sysb[index] in (set(sysb[train_b]) | set(bsystems)))})
    return {"p": probability, "tc": pred, "unknown": unknown, "lofo": rows, "background": background_rows}


def compare(outputs: dict, y, families, systems, sent) -> dict:
    stats = {}
    for name, output in outputs.items():
        rows = output["lofo"]
        bg = output["background"]
        fa = [r["p_sc"] >= 0.5 and not r["not_known"] for r in bg if sent[r["index"]]]
        stats[name] = {"macro_found": float(np.mean([r["found"] for r in rows])),
                       "n_found": sum(r["n_found"] for r in rows), "n_sc": sum(r["n_sc"] for r in rows),
                       "macro_tc_mae": float(np.mean([r["tc_mae"] for r in rows])),
                       "macro_brier": float(np.mean([r["brier"] for r in rows])),
                       "macro_unknown_sc": float(np.mean([r["unknown_sc"] for r in rows])),
                       "background_false_alarms": float(np.mean(fa)) if fa else None}
    margins = PROTOCOL["promising_rule"]
    checks, candidate = {}, stats["M1"]
    for reference in ("H4", "P1"):
        ref = stats[reference]
        interval = bootstrap_gain(y, families, systems,
                                  found_mask(outputs["M1"]["p"], outputs["M1"]["unknown"]),
                                  found_mask(outputs[reference]["p"], outputs[reference]["unknown"]),
                                  resamples=PROTOCOL["bootstrap"]["resamples"])
        checks[reference] = {"macro_found": candidate["macro_found"] - ref["macro_found"] >= margins["macro_found_gain_over_both_references"],
                             "extra_parents": candidate["n_found"] - ref["n_found"] >= margins["extra_positive_parents_over_both_references"],
                             "paired_interval": interval["lower95"] > margins["paired_chemical_system_bootstrap_lower95_gain_over_both"],
                             "brier": candidate["macro_brier"] <= ref["macro_brier"] + margins["brier_tolerance_over_each_reference"],
                             "tc_mae": candidate["macro_tc_mae"] <= ref["macro_tc_mae"] + margins["macro_tc_mae_tolerance_K"],
                             "unknown": candidate["macro_unknown_sc"] <= ref["macro_unknown_sc"] + margins["unknown_rate_increase_over_each_reference"],
                             "gain_interval": interval}
    fa = candidate["background_false_alarms"]
    alarms_ok = fa is not None and fa <= margins["max_background_false_alarms"]
    promising = alarms_ok and all(all(v for k, v in r.items() if k != "gain_interval") for r in checks.values())
    return {"stats": stats, "checks": checks, "background_false_alarms_pass": alarms_ok,
            "promising": bool(promising), "adopted": False}


def negative_audit() -> dict:
    doc = ND.load()
    labels = ND.export_labels(doc, target=ND.PARENT_TARGET, threshold_K=2.0,
                             pressure_GPa=None, sample_form=None, field_T=None)
    return {**ND.validate_document(doc), "source": str(ND.DEFAULT.relative_to(P.ROOT)),
            "n_used_for_parent_training": len(labels["accepted"]), "excluded": labels["excluded"]}


def prepare_real() -> dict:
    dsc = H.load_3dsc()
    tabular = Path(os.environ.get("HURRICANE_3DSC", P.CACHE / "3DSC_MP.csv"))
    if hashlib.sha256(tabular.read_bytes()).hexdigest() != PROTOCOL["3dsc_sha256"]:
        raise ValueError("H6 real evaluation requires the pinned 3DSC file, including when using a local override")
    entries, all_parents = H.build_frame(dsc, set(H.FAMILY_OF_CLASS)), H5.parent_frame(dsc)
    crystal, excluded = original_structures(all_parents)
    if len(crystal) < PROTOCOL["structure_min_fraction"] * len(all_parents):
        raise ValueError(f"only {len(crystal)}/{len(all_parents)} parent structures are usable; at least 95% required. Exclusions: {json.dumps(excluded[:10])}")
    parents = all_parents.loc[crystal["parent_index"]].reset_index(drop=True)
    # Drop entries whose original parent has no usable structure, keeping cohort definitions aligned.
    entries = entries[entries["material_id_2"].astype(str).isin(parents["material_id"].astype(str))].reset_index(drop=True)
    rows = SC.load_rows()
    bg, bg_info = H3.background(rows, entries)
    if not len(bg):
        raise ValueError("empty weak-background pool")
    symbols = sorted({e for c in list(parents["comp"]) + list(entries["comp"]) + list(bg["comp"]) for e in c})
    table = P.element_table(symbols)
    counts = {}
    for comp in entries["comp"]:
        for element in comp:
            counts[element] = counts.get(element, 0) + 1
    elements = sorted(e for e, n in counts.items() if n >= 10)
    parent_blocks = H5.parent_blocks(parents, table, elements)
    entry_blocks = H.feature_blocks(entries, table, [H.dsc_structure(r) for _, r in entries.iterrows()])
    entry_blocks["D"] = H.element_fractions(entries["comp"], elements)
    entry_blocks["E"] = pd.DataFrame([H2.structure_types(c) for c in entries["comp"]])
    bg_blocks = H5.pool_blocks(bg, table, elements)
    current, version = SC.hurricane_design(upto=4)
    if version != "4.0" or current.get("per_family") or not current.get("two_part"):
        raise ValueError("H6 v1 requires released H4's pooled two-part design")
    if current.get("params") != PROTOCOL["regressor_params"] or any(current.get(k) != v for k, v in PROTOCOL["reference_settings"].items()):
        raise ValueError("released H4 settings differ from the H6 v1 protocol; declare a new comparison before evaluating")
    key = current["X"]
    for block in key:
        if list(parent_blocks[block]) != list(entry_blocks[block]) or list(parent_blocks[block]) != list(bg_blocks[block]):
            raise ValueError(f"feature columns differ in block {block}")
    stack = lambda blocks: np.hstack([blocks[b].to_numpy(float) for b in key])
    Xp, Xe, Xb = stack(parent_blocks), stack(entry_blocks), stack(bg_blocks)
    mp, info_p = embeddings(crystal, "parents")
    mb, info_b = embeddings(bg[["id", "atoms"]], "background")
    if mp.shape[1] != mb.shape[1]:
        raise ValueError("parent/background MACE descriptor dimensions differ")
    sent = np.asarray(SC.radar_scores(bg)[0]) >= 0.5
    return dict(parents=parents, entries=entries, bg=bg, current=current,
                Xp=Xp, Xe=Xe, Xb=Xb, mp=mp, mb=mb, sent=sent,
                provenance={"3dsc_commit": H.DSC_COMMIT, "all_parents": len(all_parents), "usable_parents": len(parents),
                            "excluded": excluded, "original_cifs": crystal.drop(columns=["atoms", "parent_index"]).to_dict("records"),
                            "embeddings": {"parents": info_p, "background": info_b}, "weak_background": bg_info})


def prepare_smoke() -> dict:
    """Offline synthetic inputs exercise actual fitting and split safeguards; no fake scientific scores."""
    rng, rows = np.random.default_rng(P.SEED), []
    for fi, family in enumerate(H.FAMILY_LABEL):
        for i in range(12):
            rows.append(dict(material_id=f"smoke-{fi}-{i}", formula_sc="synthetic", comp={"Fe": 1, "As": 1},
                             family=family, tc=float(i % 3 != 0) * (2 + fi + i / 4), system=f"synthetic-{fi}-{i // 2}"))
    parents = pd.DataFrame(rows)
    entries = parents.assign(material_id_2=parents["material_id"])
    Xp = rng.normal(size=(len(rows), 5))
    mp = rng.normal(size=(len(rows), 6))
    bg = pd.DataFrame({"id": [f"bg-{i}" for i in range(15)], "chemsys": [f"bg-system-{i}" for i in range(15)]})
    params = dict(H.PARAMS, max_iter=3, min_samples_leaf=2)
    return dict(parents=parents, entries=entries, bg=bg,
                current=dict(id="H20", params=params, two_part="mean", background=0.3, radius=1.0, abstain=1.0),
                Xp=Xp, Xe=Xp.copy(), Xb=rng.normal(size=(len(bg), 5)), mp=mp, mb=rng.normal(size=(len(bg), 6)),
                sent=np.ones(len(bg), bool), provenance={"synthetic": True, "not_a_model_result": True})


def freeze_protocol(output_dir: Path) -> str:
    declaration = protocol()
    fingerprint = digest(declaration)
    frozen = output_dir / f"protocol-{fingerprint[:16]}.json"
    payload = json.dumps(declaration, sort_keys=True, indent=2) + "\n"
    if frozen.exists() and frozen.read_text(encoding="utf-8") != payload:
        raise ValueError("stored protocol has changed")
    if not frozen.exists():
        frozen.write_text(payload, encoding="utf-8")
    return fingerprint


def prepare_only(*, output_dir: Path | None = None, parents_per_family: int = 0) -> tuple[Path, bool]:
    """Coverage gate before expensive embeddings. A sample audit is never a full-cohort pass."""
    output_dir = Path(output_dir or (P.RESULTS / "hurricane6"))
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = freeze_protocol(output_dir)
    dsc = H.load_3dsc()
    tabular = Path(os.environ.get("HURRICANE_3DSC", P.CACHE / "3DSC_MP.csv"))
    if hashlib.sha256(tabular.read_bytes()).hexdigest() != PROTOCOL["3dsc_sha256"]:
        raise ValueError("preflight requires the pinned 3DSC CSV")
    parents = H5.parent_frame(dsc)
    all_count = len(parents)
    if parents_per_family < 0:
        raise ValueError("parents_per_family must be nonnegative")
    if parents_per_family:
        parents = parents.groupby("family", sort=False).head(parents_per_family)
    crystal, excluded = original_structures(parents)
    fraction = len(crystal) / len(parents) if len(parents) else 0.0
    passed = fraction >= PROTOCOL["structure_min_fraction"]
    result = {"mode": "sample_structure_smoke" if parents_per_family else "full_structure_preflight",
              "run_at": P.now_iso(), "protocol_sha256": fingerprint, "all_parents": all_count,
              "checked_parents": len(parents), "usable_parents": len(crystal), "usable_fraction": fraction,
              "required_fraction": PROTOCOL["structure_min_fraction"], "passed": passed,
              "full_cohort_checked": not bool(parents_per_family), "ready_for_full_embedding_run": passed and not bool(parents_per_family),
              "excluded": excluded, "original_cifs": crystal.drop(columns=["atoms", "parent_index"], errors="ignore").to_dict("records"),
              "adopted": False, "negative_evidence": negative_audit()}
    path = output_dir / f"preflight-{'sample-' if parents_per_family else ''}{time.time_ns()}.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    P.log(f"H6 structure preflight: {len(crystal)}/{len(parents)} usable; report {path}")
    return path, passed


def run(*, smoke=False, output_dir: Path | None = None) -> Path:
    output_dir = Path(output_dir or (P.RESULTS / "hurricane6"))
    output_dir.mkdir(parents=True, exist_ok=True)
    declaration = protocol()
    fingerprint = freeze_protocol(output_dir)  # before any fitting/data-dependent comparison
    started = time.time()
    data = prepare_smoke() if smoke else prepare_real()
    par, ent, bg = data["parents"], data["entries"], data["bg"]
    y, ye = par["tc"].to_numpy(float), ent["tc"].to_numpy(float)
    fam, fame = par["family"].to_numpy(), ent["family"].to_numpy()
    systems = par["system"].to_numpy() if smoke else np.array([H3.chemsys_of(c) for c in par["comp"]])
    syse = ent["system"].to_numpy() if smoke else np.array([H3.chemsys_of(c) for c in ent["comp"]])
    sysb = bg["chemsys"].to_numpy()
    current = data["current"]
    if smoke:
        # Keep the synthetic plumbing check short; the protocol/full-run settings are unchanged.
        original_classifier_params = H2.CLF_PARAMS
        H2.CLF_PARAMS = dict(H2.CLF_PARAMS, max_iter=3, min_samples_leaf=2)
    outputs = {}
    try:
        for ident in DESIGNS:
            candidate = dict(current, id=ident, rows="entry" if ident == "H4" else "parent", per_family=False)
            Xp = np.hstack([data["Xp"], data["mp"]]) if ident == "M1" else data["Xp"]
            Xb = np.hstack([data["Xb"], data["mb"]]) if ident == "M1" else data["Xb"]
            outputs[ident] = score_design(candidate, Xp, data["Xe"], Xb, data["Xp"], data["Xe"], data["Xb"],
                                          y, ye, fam, fame, systems, syse, sysb)
    finally:
        if smoke:
            H2.CLF_PARAMS = original_classifier_params
    result = compare(outputs, y, fam, systems, data["sent"])
    versions = {}
    for name in ("numpy", "pandas", "scikit-learn", "mace-torch", "torch", "pymatgen", "jarvis-tools"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    stamp = P.now_iso()
    run_id = f"{'smoke-' if smoke else ''}{stamp.replace(':', '').replace('-', '').replace('+', 'p')}-{time.time_ns()}"
    base = output_dir / run_id
    report = dict(run_at=stamp, run_id=run_id, round=ROUND, version="6.0-experiment", adopted=False,
                  mode="synthetic_smoke_not_scientific" if smoke else "real_lofo_experiment",
                  protocol=declaration, protocol_sha256=fingerprint, comparison=result,
                  lofo={k: v["lofo"] for k, v in outputs.items()}, provenance=data["provenance"],
                  negative_evidence=negative_audit(), packages=versions, seconds=round(time.time() - started, 1),
                  limitations=["MPTrj pretraining may already contain held-out MP structures; this is label/family holdout, not proof of unseen-structure pretraining.",
                               "No independent Hosono parent-potential negative labels exist in the imported sample-null records.",
                               "LOFO is a diagnostic experiment; no tuning or release is authorized from this report alone."])
    if smoke:
        report["comparison"]["promising"] = False
    base.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    predictions = []
    for ident, out in outputs.items():
        for i in range(len(y)):
            predictions.append({"design": ident, "material_id": str(par.iloc[i]["material_id"]), "family": str(fam[i]),
                                "chemsys": str(systems[i]), "tc_parent_max": y[i], "p_sc": out["p"][i],
                                "tc_pred": out["tc"][i], "not_known": bool(out["unknown"][i])})
    pd.DataFrame(predictions).to_csv(base.with_name(base.name + "-parents.csv"), index=False)
    pd.DataFrame([r for out in outputs.values() for r in out["background"]]).to_csv(base.with_name(base.name + "-background.csv"), index=False)
    P.log(f"H6 report only: {base.with_suffix('.json')}; H4 remains in use")
    return base.with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", default=os.environ.get("HURRICANE6_SMOKE") == "1")
    parser.add_argument("--protocol", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--parents-per-family", type=int, default=0,
                        help="only with --prepare-only: sample this many per family; 0 audits the full cohort")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.protocol:
        print(json.dumps({"sha256": digest(protocol()), "protocol": protocol()}, indent=2))
    elif args.prepare_only:
        _, passed = prepare_only(output_dir=args.output_dir, parents_per_family=args.parents_per_family)
        if not passed:
            raise SystemExit(2)
    else:
        if args.parents_per_family:
            parser.error("--parents-per-family requires --prepare-only")
        run(smoke=args.smoke, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
