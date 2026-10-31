"""Graph neural network, round 2: an AI-designed search over crystal-graph networks.

Round 1 (ml/gnn.py) trained one CGCNN-style network. In round 2 an AI agent (Claude) proposed changes to it, and each
candidate is trained with the same settings (one seed, the same epochs) on the same 5-fold GroupKFold by chemical
system as Storm:

    G0  the round-1 design (reference)
    G1  + weight averaging: the network is evaluated with an exponential moving average of its weights
    G2  + an Allen-Dynes head: Tc is computed inside the network from the predicted λ and ω_log, so the prediction
          obeys the formula the labels come from
    G3  + crystal descriptors: Storm 1.0's 43 composition and structure features and 11 physics features join the
          readout next to the learned crystal-graph vector
    G4  wider and deeper: 4 message-passing layers of width 96
    G5  G1 + G3 together
    G6  G1 + G2 + G3 together

A candidate is selected only if it beats G0 on average and in at least 4 of the 5 folds; the epoch is always picked on
10% of the training fold's chemical systems, never on the test fold. Each candidate is also compared with Storm 1.0 on
the same folds, alone and averaged with it.

The search trains one seed per candidate for 150 epochs, so its errors are not comparable with version 1.0, which
averages two seeds trained for 200 epochs. The final check therefore retrains the selected design exactly like version
1.0 and releases it as version 2.0 only if it then beats version 1.0 on average and in at least 4 of the 5 folds. Its
out-of-fold predictions go to results/gnn_round2_final_predictions.csv, which Storm round 4 reuses.

Run from the repository root:  python ml/pipeline.py gnn2        (the search)
                               python ml/pipeline.py gnn2final   (the final check of the selected design)
(GNN_SMOKE=1 for a quick check on a small subset)
"""
from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

import gnn as G1
import pipeline as P

ROUND = 2
NAME = "Graph neural network"
SMOKE = os.environ.get("GNN_SMOKE") == "1"
EPOCHS = int(os.environ.get("GNN_EPOCHS", 2 if SMOKE else 150))
# the final check trains like version 1.0 did (results/gnn_round1.json "training"); these override it
FINAL_EPOCHS = os.environ.get("GNN_FINAL_EPOCHS")
FINAL_SEEDS = os.environ.get("GNN_FINAL_SEEDS")
EVAL_EVERY = 2
EMA_DECAY = 0.998
BASE = dict(hidden=64, n_conv=3, head=(128, 64), lr=2e-3, wd=1e-4, ema=False, ad_head=False, hybrid=False)
CANDIDATES = [
    {"id": "G0", "name": "Round-1 design (reference)", **BASE},
    {"id": "G1", "name": "+ weight averaging", **dict(BASE, ema=True)},
    {"id": "G2", "name": "+ Allen–Dynes head", **dict(BASE, ad_head=True)},
    {"id": "G3", "name": "+ Storm 1.0's crystal descriptors in the readout", **dict(BASE, hybrid=True)},
    {"id": "G4", "name": "Wider and deeper (4 layers, width 96)", **dict(BASE, hidden=96, n_conv=4)},
    {"id": "G5", "name": "+ weight averaging + crystal descriptors", **dict(BASE, ema=True, hybrid=True)},
    {"id": "G6", "name": "+ weight averaging + Allen–Dynes head + crystal descriptors", **dict(BASE, ema=True, ad_head=True, hybrid=True)},
]


# ---------------------------------------------------------------- the network (JAX)


def network(props: np.ndarray, cfg: dict, n_glob: int):
    import jax
    import jax.numpy as jnp

    props_t = jnp.asarray(props)
    centers = jnp.linspace(0.0, G1.CUTOFF, G1.N_RBF)
    width = G1.CUTOFF / (G1.N_RBF - 1)
    tw = jnp.asarray(G1.TARGET_W, jnp.float32)
    H = cfg["hidden"]

    def init(key, n_el: int) -> dict:
        keys = iter(jax.random.split(key, 16 + 4 * cfg["n_conv"] + len(cfg["head"])))

        def dense(i, o, bias=True, scale=1.0):
            w = jax.random.normal(next(keys), (i, o), jnp.float32) * math.sqrt(scale / i)
            return {"w": w, "b": jnp.zeros(o, jnp.float32)} if bias else {"w": w}
        p = {"emb": jax.random.normal(next(keys), (n_el, H), jnp.float32) * 0.5,
             "prop": dense(props.shape[1], H), "conv": [], "head": []}
        for _ in range(cfg["n_conv"]):
            p["conv"].append({"dst": dense(H, 2 * H, bias=False), "src": dense(H, 2 * H, bias=False),
                              "edge": dense(G1.N_RBF, 2 * H), "g": jnp.ones(H, jnp.float32), "b": jnp.zeros(H, jnp.float32)})
        first = H
        if cfg["hybrid"]:
            p["glob"] = dense(n_glob, H, scale=2.0)
            first = 2 * H
        dims = (first,) + tuple(cfg["head"])
        for a, b in zip(dims[:-1], dims[1:]):
            p["head"].append(dense(a, b, scale=2.0))
        p["out"] = dense(dims[-1], 3, scale=0.1)
        return p

    def layer_norm(x, g, b):
        mu = jnp.mean(x, -1, keepdims=True)
        var = jnp.mean((x - mu) ** 2, -1, keepdims=True)
        return (x - mu) * jax.lax.rsqrt(var + 1e-5) * g + b

    def forward(p, bt):
        n_nodes, n_graphs = bt["z"].shape[0], bt["gmask"].shape[0]
        h = p["emb"][bt["z"]] + props_t[bt["z"]] @ p["prop"]["w"] + p["prop"]["b"]
        rbf = jnp.exp(-(((bt["dist"][:, None] - centers[None, :]) / width) ** 2))
        em = bt["emask"][:, None]
        deg = jax.ops.segment_sum(bt["emask"], bt["rcv"], num_segments=n_nodes)
        inv_deg = 1.0 / jnp.maximum(deg, 1.0)
        for c in p["conv"]:
            zz = (h @ c["dst"]["w"])[bt["rcv"]] + (h @ c["src"]["w"])[bt["snd"]] + rbf @ c["edge"]["w"] + c["edge"]["b"]
            gate, core = jnp.split(zz, 2, axis=-1)
            msg = jax.nn.sigmoid(gate) * jax.nn.softplus(core) * em
            agg = jax.ops.segment_sum(msg, bt["rcv"], num_segments=n_nodes) * inv_deg[:, None]
            h = layer_norm(h + agg, c["g"], c["b"])
        nm = bt["nmask"][:, None]
        cnt = jax.ops.segment_sum(bt["nmask"], bt["nodeg"], num_segments=n_graphs)
        x = jax.ops.segment_sum(h * nm, bt["nodeg"], num_segments=n_graphs) / jnp.maximum(cnt, 1.0)[:, None]
        if cfg["hybrid"]:
            x = jnp.concatenate([x, jax.nn.silu(bt["glob"] @ p["glob"]["w"] + p["glob"]["b"])], axis=-1)
        for d in p["head"]:
            x = jax.nn.silu(x @ d["w"] + d["b"])
        return x @ p["out"]["w"] + p["out"]["b"]

    def allen_dynes_std(out, mu, sd):
        """log(1 + Tc) from the predicted λ and ω_log with Allen-Dynes (μ* = 0.10), in the units of the Tc target."""
        lam = jnp.exp(out[:, 1] * sd[1] + mu[1])
        wlog = jnp.exp(out[:, 2] * sd[2] + mu[2])
        den = lam - P.MU_STAR * (1 + 0.62 * lam)
        ok = den > 1e-3
        tc = jnp.where(ok, wlog / 1.2 * jnp.exp(-1.04 * (1 + lam) / jnp.where(ok, den, 1.0)), 0.0)
        return (jnp.log1p(tc) - mu[0]) / sd[0]

    def huber(err):
        a = jnp.abs(err)
        return jnp.where(a < G1.HUBER, 0.5 * a ** 2 / G1.HUBER, a - 0.5 * G1.HUBER)

    def loss(p, bt):
        out = forward(p, bt)
        gm = bt["gmask"][:, None]
        hub = huber(out - bt["y"])
        total = jnp.sum(hub * gm * tw[None, :])
        wsum = jnp.sum(tw)
        if cfg["ad_head"]:
            t_ad = allen_dynes_std(out, bt["mu"], bt["sd"])
            total = total + jnp.sum(huber(t_ad - bt["y"][:, 0]) * bt["gmask"])
            wsum = wsum + 1.0
        return total / (jnp.maximum(jnp.sum(bt["gmask"]), 1.0) * wsum)

    return init, forward, loss, allen_dynes_std


# ---------------------------------------------------------------- training


def train_all(g: dict, Ttrans: np.ndarray, y_tc: np.ndarray, groups: np.ndarray, splits: list, cfg: dict,
              glob: np.ndarray | None, seed: int = 0, epochs: int | None = None) -> tuple[dict, dict]:
    import jax
    import jax.numpy as jnp
    import optax

    n_glob = 0 if glob is None else glob.shape[1]
    init, forward, loss, ad_std = network(g["props"], cfg, n_glob)
    new_key = getattr(jax.random, "key", None) or jax.random.PRNGKey
    n_el = len(g["elements"])
    mean_nodes = float(np.mean(g["n"]))
    packer = G1.Packer(g, G1.BATCH, mean_nodes)
    epacker = G1.Packer(g, G1.EVAL_BATCH, mean_nodes)

    def fit_val(tr, fold):
        rng = np.random.default_rng(P.SEED + 100 * fold)
        ug = np.unique(groups[tr])
        rng.shuffle(ug)
        held = set(ug[:max(1, int(round(G1.VAL_FRAC * len(ug))))])
        is_val = np.array([x in held for x in groups[tr]])
        return tr[~is_val], tr[is_val]

    E = int(epochs or EPOCHS)
    per_epoch = max(len(packer.batches(fit_val(tr, k)[0])) for k, (tr, _) in enumerate(splits))
    steps = E * per_epoch
    sched = optax.warmup_cosine_decay_schedule(init_value=cfg["lr"] * 0.05, peak_value=cfg["lr"],
                                               warmup_steps=max(1, steps // 50), decay_steps=steps,
                                               end_value=cfg["lr"] * 0.02)
    opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(sched, weight_decay=cfg["wd"]))

    @jax.jit
    def step(p, s, ema, bt):
        val, grads = jax.value_and_grad(loss)(p, bt)
        upd, s = opt.update(grads, s, p)
        p = optax.apply_updates(p, upd)
        ema = jax.tree_util.tree_map(lambda e, q: EMA_DECAY * e + (1 - EMA_DECAY) * q, ema, p)
        return p, s, ema, val

    @jax.jit
    def predict(p, bt):
        out = forward(p, bt)
        return out, ad_std(out, bt["mu"], bt["sd"])

    def collate(pk, idx, Y=None, mu=None, sd=None):
        bt = pk.collate(idx, Y)
        bt["mu"] = mu.astype(np.float32)
        bt["sd"] = sd.astype(np.float32)
        if glob is not None:
            gl = np.zeros((pk.G + 1, n_glob), np.float32)
            gl[:len(idx)] = glob[idx]
            bt["glob"] = gl
        return bt

    def predict_std(p, idx, mu, sd):
        out = np.zeros((len(idx), 3), np.float32)
        ad = np.zeros(len(idx), np.float32)
        pos = {int(i): k for k, i in enumerate(idx)}
        for b in epacker.batches(idx):
            o, a = predict(p, collate(epacker, b, mu=mu, sd=sd))
            rows = [pos[i] for i in b]
            out[rows] = np.asarray(o)[:len(b)]
            ad[rows] = np.asarray(a)[:len(b)]
        return out, ad

    n = len(y_tc)
    res = {"direct": np.zeros((n, 3)), "ad": np.zeros(n)}
    record = {"epochs": E, "seed": seed, "folds": []}
    t_start = time.time()
    for k, (tr, te) in enumerate(splits):
        fit, val = fit_val(tr, k)
        mu, sd = Ttrans[fit].mean(0), Ttrans[fit].std(0)
        Ys = ((Ttrans - mu) / sd).astype(np.float32)
        p = init(new_key(2000 * (k + 1) + 97 * seed), n_el)
        s = opt.init(p)
        ema = p
        rng = np.random.default_rng(P.SEED + 2000 * (k + 1) + 97 * seed)
        best = (np.inf, p, -1)
        t0 = time.time()
        for ep in range(E):
            for b in packer.batches(rng.permutation(fit)):
                p, s, ema, _ = step(p, s, ema, collate(packer, b, Ys, mu, sd))
            if ep % EVAL_EVERY == EVAL_EVERY - 1 or ep == E - 1:
                q = ema if cfg["ema"] else p
                pv, av = predict_std(q, val, mu, sd)
                z = av if cfg["ad_head"] else pv[:, 0]
                tc_v = np.clip(np.expm1(z * sd[0] + mu[0]), 0, None)
                mae_v = float(np.mean(np.abs(tc_v - y_tc[val])))
                if mae_v < best[0]:
                    best = (mae_v, q, ep)
        pt, at = predict_std(best[1], te, mu, sd)
        res["direct"][te] = pt * sd + mu
        res["ad"][te] = at * sd[0] + mu[0]
        record["folds"].append({"fold": k + 1, "best_epoch": best[2] + 1, "val_tc_mae": round(best[0], 4),
                                "seconds": round(time.time() - t0)})
        P.log(f"gnn2 {cfg['id']} fold {k + 1}: best epoch {best[2] + 1}, validation Tc MAE {best[0]:.3f} K, "
              f"{time.time() - t0:.0f} s")
    record["seconds"] = round(time.time() - t_start)
    record["n_params"] = int(sum(np.size(x) for x in jax.tree_util.tree_leaves(p)))
    out = {"tc_direct": np.clip(np.expm1(res["direct"][:, 0]), 0, None),
           "tc_ad_head": np.clip(np.expm1(res["ad"]), 0, None),
           "lambda": np.exp(res["direct"][:, 1]), "wlog": np.exp(res["direct"][:, 2])}
    out["tc"] = out["tc_ad_head"] if cfg["ad_head"] else out["tc_direct"]
    return out, record


# ---------------------------------------------------------------- run


def descriptors(train: pd.DataFrame, table: pd.DataFrame) -> tuple[np.ndarray, list]:
    """Storm 1.0's inputs: 43 hand-made composition and structure features and 11 physics features, standardized."""
    base = P.featurize(train, table)
    phys = P.physics_features(train, base)
    X = np.hstack([base.to_numpy(float), phys.to_numpy(float)])
    mu, sd = np.nanmean(X, 0), np.nanstd(X, 0)
    X = np.nan_to_num((X - mu) / np.where(sd > 0, sd, 1.0)).astype(np.float32)
    return np.clip(X, -6, 6), list(base.columns) + list(phys.columns)


def run() -> None:
    import jax
    import optax
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    _, frames = P.load_clean()
    train = frames["alexandria"]
    if SMOKE:
        train = train.sample(n=min(500, len(train)), random_state=P.SEED).reset_index(drop=True)
    table = P.element_table(sorted({e for els in train["elements"] for e in els}))
    g = G1.build_graphs(train, table)
    glob, glob_names = descriptors(train, table)
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    Ttrans = np.column_stack([np.log1p(y_tc), np.log(y_lam), np.log(y_wlog)]).astype(np.float32)
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(np.zeros((len(y_tc), 1)), y_tc, groups))
    folds = [te for _, te in splits]
    P.log(f"gnn2: {len(train):,} crystals, {len(glob_names)} crystal descriptors; {len(CANDIDATES)} candidates x "
          f"{EPOCHS} epochs; jax {jax.__version__}, optax {optax.__version__}")
    board, preds = [], {}
    for c in CANDIDATES:
        out, rec = train_all(g, Ttrans, y_tc, groups, splits, c, glob if c["hybrid"] else None)
        fm = G1.fold_maes(y_tc, out["tc"], folds)
        row = {"id": c["id"], "name": c["name"], "config": {k: v for k, v in c.items() if k not in ("id", "name")},
               "tc_mae": float(np.mean(np.abs(out["tc"] - y_tc))), "fold_mae": fm,
               "tc_direct_mae": float(np.mean(np.abs(out["tc_direct"] - y_tc))),
               "tc_ad_head_mae": float(np.mean(np.abs(out["tc_ad_head"] - y_tc))),
               "tc_allen_dynes_mae": float(np.mean(np.abs(P.allen_dynes(out["lambda"], out["wlog"]) - y_tc))),
               "lambda_mae": float(np.mean(np.abs(out["lambda"] - y_lam))),
               "wlog_mae": float(np.mean(np.abs(out["wlog"] - y_wlog))), "training": rec}
        board.append(row)
        preds[c["id"]] = out
        P.log(f"gnn2 {c['id']} {c['name']}: Tc MAE {row['tc_mae']:.3f} K (folds " + ", ".join(f"{x:.3f}" for x in fm) +
              f"), λ {row['lambda_mae']:.3f}, ω_log {row['wlog_mae']:.1f} K, {rec['seconds']} s")
    ref = next(r for r in board if r["id"] == "G0")
    for r in board:
        r["folds_better"] = int(sum(a < b for a, b in zip(r["fold_mae"], ref["fold_mae"])))
    eligible = [r for r in board if r["id"] != "G0" and r["tc_mae"] < ref["tc_mae"] and r["folds_better"] >= P.ADOPT_FOLDS]
    selected = bool(eligible)   # released only after the final check (final() below)
    best = min(eligible or board, key=lambda r: r["tc_mae"])
    cmp = G1.compare(train, y_tc, preds[best["id"]]["tc"], folds)
    comp, s1, blend = cmp if cmp else (None, None, None)
    if comp:
        comp["folds_better_storm1"] = int(sum(a < b for a, b in zip(best["fold_mae"], comp["storm1"]["folds"])))
        comp["blend"]["folds_better_storm1"] = int(sum(a < b for a, b in zip(comp["blend"]["folds"], comp["storm1"]["folds"])))
        for r in board:   # every candidate against Storm 1.0, alone and averaged with it
            pb = 0.5 * (preds[r["id"]]["tc"] + s1)
            r["blend_mae"] = float(np.mean(np.abs(pb - y_tc)))
            r["blend_folds_better_storm1"] = int(sum(a < b for a, b in zip(G1.fold_maes(y_tc, pb, folds), comp["storm1"]["folds"])))
    stamp = P.now_iso()
    out = {"run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": NAME,
           "designer": "AI agent (Claude) proposed the candidates: weight averaging, an Allen-Dynes head, Storm 1.0's "
                       "crystal descriptors in the readout, a wider and deeper network, and their combinations",
           "selection": (f"{P.N_FOLDS}-fold GroupKFold by chemical system on Alexandria ({len(y_tc):,} materials), the "
                         f"same folds as Storm; one seed and {EPOCHS} epochs per candidate; the epoch is picked on "
                         f"{G1.VAL_FRAC:.0%} of each training fold's chemical systems"),
           "rule": (f"select the lowest-error candidate that beats the round-1 design on average and in at least "
                    f"{P.ADOPT_FOLDS} of {P.N_FOLDS} folds; retrained like version 1.0, it is released only if it then "
                    f"beats version 1.0 the same way"),
           "caveat": "picking the best of several candidates on the same folds makes its score slightly optimistic",
           "descriptors": glob_names, "leaderboard": sorted(board, key=lambda r: r["tc_mae"]), "reference_id": "G0",
           "best": best["id"], "selected": selected, "adopted": False, "version": None, "comparison": comp,
           "versions": {"jax": jax.__version__, "optax": optax.__version__}, "minutes": round((time.time() - t_start) / 60, 1)}
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="gnn2-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        write(out, train, preds, folds, best, tmp / "results", tmp / "progress.json")
        P.log(f"gnn2 smoke test passed; outputs in {tmp}")
        return
    write(out, train, preds, folds, best, P.RESULTS, P.PROGRESS)


def _phrase(name: str) -> str:
    """A design's name as part of a sentence: "Wider and deeper" -> "wider and deeper"; names keep their capitals."""
    s = str(name).lstrip("+ ").rstrip(".")
    return s[:1].lower() + s[1:] if s[:1].isupper() and not s.startswith(("Storm", "Allen")) else s


def write(out: dict, train: pd.DataFrame, preds: dict, folds: list, best: dict, results: Path, progress: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    (results / f"gnn_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    cols = {"id": train["id"], "chemsys": train["chemsys"], "fold": np.zeros(len(train), int), "tc": train["tc"]}
    for k, te in enumerate(folds):
        cols["fold"][te] = k + 1
    for cid, pr in preds.items():
        cols[f"tc_pred_{cid}"] = pr["tc"]
        cols[f"lambda_pred_{cid}"] = pr["lambda"]
        cols[f"wlog_pred_{cid}"] = pr["wlog"]
    pd.DataFrame(cols).round(5).to_csv(results / f"gnn_round{ROUND}_predictions.csv", index=False)
    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp = out["run_at"]
    cur = prog.get("gnn") or {}
    versions = [v for v in cur.get("versions", []) if v.get("round") != ROUND]
    if not versions and cur.get("round") == 1:   # the round-1 block becomes version 1.0
        versions = [{"version": "1.0", "round": 1, "date": cur.get("date"), "status": "adopted",
                     "summary": cur.get("summary"), "tc_mae": cur.get("tc_mae"), "folds": cur.get("folds"),
                     "spec": cur.get("spec")}]
    comp = out.get("comparison")
    entry = {"version": f"{ROUND}.0", "round": ROUND, "date": stamp[:10],
             "status": "selected" if out.get("selected") else "experimental",   # "selected": waiting for the final check
             "summary": best["name"], "tc_mae": round(best["tc_mae"], 3), "folds": [round(x, 3) for x in best["fold_mae"]],
             "folds_better": best["folds_better"],
             "reference_mae": round(next(r for r in out["leaderboard"] if r["id"] == "G0")["tc_mae"], 3),
             "search": {"candidates": len(out["leaderboard"]), "reference_id": "G0",
                        "leaderboard": [{"id": r["id"], "name": r["name"], "tc_mae": round(r["tc_mae"], 3),
                                         "folds_better": r["folds_better"],
                                         "blend_mae": round(r["blend_mae"], 3) if "blend_mae" in r else None}
                                        for r in out["leaderboard"]]}}
    if comp:
        entry["storm1_mae"] = round(comp["storm1"]["tc_mae"], 3)
        entry["folds_better_storm1"] = comp["folds_better_storm1"]
        entry["blend"] = {"name": comp["blend"]["name"], "tc_mae": round(comp["blend"]["tc_mae"], 3),
                          "folds": [round(x, 3) for x in comp["blend"]["folds"]],
                          "folds_better_storm1": comp["blend"]["folds_better_storm1"]}
    versions.append(entry)
    versions.sort(key=lambda v: v["round"])
    released = [v for v in versions if v.get("status") == "adopted"]
    curv = released[-1] if released else versions[-1]
    block = dict(cur)
    block.update({"name": NAME, "status": "done", "current": curv["version"], "round": ROUND, "date": stamp[:10],
                  "tc_mae": curv["tc_mae"], "folds": curv["folds"], "versions": versions,
                  "summary": ("CGCNN-style message passing on the crystal graph, trained end to end" if curv["round"] == 1
                              else "crystal-graph network, AI-designed: " + _phrase(curv["summary"]))})
    if comp and curv is entry:
        block.update({"storm1_mae": entry["storm1_mae"], "folds_better_storm1": entry["folds_better_storm1"], "blend": entry["blend"]})
    prog["gnn"] = block
    msg = (f"{NAME}, round {ROUND} ({len(out['leaderboard'])} AI-designed candidates, one seed each): best {best['id']} "
           f"{best['name'].lstrip('+ ')}, Tc MAE {best['tc_mae']:.2f} K against {entry['reference_mae']:.2f} K for the "
           f"round-1 design trained the same way, better in {best['folds_better']} of {P.N_FOLDS} folds; " +
           ("selected for the final check with two seeds" if out.get("selected") else "not selected, so version 1.0 stays"))
    if comp:
        msg += (f"; Storm 1.0 {comp['storm1']['tc_mae']:.2f} K on the same folds, the two averaged "
                f"{comp['blend']['tc_mae']:.2f} K (better than Storm 1.0 in {comp['blend']['folds_better_storm1']} of 5)")
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)


# ---------------------------------------------------------------- final check: the selected design, trained like 1.0


def _r1_fields(r1: dict) -> dict:
    """Version 1.0's scores in the form the progress block uses, from results/gnn_round1.json."""
    sc, comp = r1.get("scores") or {}, r1.get("comparison") or {}
    f = {"tc_mae": round(sc["tc"]["mae"], 3), "folds": [round(x, 3) for x in r1["fold_mae"]]}
    if "tc_via_lambda_wlog" in sc:
        f["tc_via_allen_dynes_mae"] = round(sc["tc_via_lambda_wlog"]["mae"], 3)
    if "lambda" in sc:
        f["lambda_mae"] = round(sc["lambda"]["mae"], 3)
    if "wlog" in sc:
        f["wlog_mae"] = round(sc["wlog"]["mae"], 1)
    if comp:
        f.update({"storm1_mae": round(comp["storm1"]["tc_mae"], 3), "baseline_mae": round(comp["baseline"]["tc_mae"], 3),
                  "folds_better_storm1": comp.get("folds_better_storm1"), "folds_better_baseline": comp.get("folds_better_baseline"),
                  "blend": {"name": comp["blend"]["name"], "tc_mae": round(comp["blend"]["tc_mae"], 3),
                            "folds": [round(x, 3) for x in comp["blend"]["folds"]],
                            "folds_better_storm1": comp["blend"].get("folds_better_storm1")}})
    if r1.get("spec"):
        f["spec"] = r1["spec"]
    return f


METRIC_KEYS = ("tc_mae", "folds", "tc_via_allen_dynes_mae", "lambda_mae", "wlog_mae", "storm1_mae", "baseline_mae",
               "folds_better_storm1", "folds_better_baseline", "blend", "spec")


def final() -> None:
    """Retrain the design the round-2 search selected exactly like version 1.0 (its seeds, averaged, and its epochs) on
    the same folds, and release it as version 2.0 only if it beats version 1.0 on average and in at least 4 of 5 folds."""
    import jax
    import optax
    from sklearn.model_selection import GroupKFold

    t_start = time.time()
    spath, r1path = P.RESULTS / f"gnn_round{ROUND}.json", P.RESULTS / "gnn_round1.json"
    if not spath.exists() or not r1path.exists():
        P.log("gnn2final: the round-2 search or version 1.0's results are missing; nothing to check")
        return
    srch, r1 = json.loads(spath.read_text()), json.loads(r1path.read_text())
    if not srch.get("selected", srch.get("adopted")):   # search files written before the final check said "adopted"
        P.log("gnn2final: the round-2 search selected no design, so version 1.0 stays")
        return
    best = next(r for r in srch["leaderboard"] if r["id"] == srch["best"])
    cfg = dict(best["config"], id=best["id"], name=best["name"])
    tr1 = r1.get("training") or {}
    epochs = int(FINAL_EPOCHS or (2 if SMOKE else tr1.get("epochs") or 200))
    seeds = int(FINAL_SEEDS or (1 if SMOKE else tr1.get("seeds") or 2))
    _, frames = P.load_clean()
    train = frames["alexandria"]
    if SMOKE:
        train = train.sample(n=min(500, len(train)), random_state=P.SEED).reset_index(drop=True)
    table = P.element_table(sorted({e for els in train["elements"] for e in els}))
    g = G1.build_graphs(train, table)
    glob = descriptors(train, table)[0] if cfg["hybrid"] else None
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    Ttrans = np.column_stack([np.log1p(y_tc), np.log(y_lam), np.log(y_wlog)]).astype(np.float32)
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(np.zeros((len(y_tc), 1)), y_tc, groups))
    folds = [te for _, te in splits]
    fold_of = np.zeros(len(y_tc), int)
    for k, te in enumerate(folds):
        fold_of[te] = k + 1
    # version 1.0 on exactly these materials and folds, from its saved out-of-fold predictions
    ref_tc, same_folds = None, None
    r1pred = P.RESULTS / "gnn_round1_predictions.csv"
    if r1pred.exists() and not SMOKE:
        rp = pd.read_csv(r1pred).drop_duplicates("id").set_index("id")
        rp.index = rp.index.astype(str)
        ids = train["id"].astype(str)
        if ids.isin(rp.index).all():
            ref_tc = rp.loc[ids, "tc_pred"].to_numpy(float)
            same_folds = bool((rp.loc[ids, "fold"].to_numpy(int) == fold_of).all())
    if ref_tc is not None:
        ref_folds, ref_mae = G1.fold_maes(y_tc, ref_tc, folds), float(np.mean(np.abs(ref_tc - y_tc)))
    else:
        ref_folds, ref_mae = list(r1["fold_mae"]), float(r1["scores"]["tc"]["mae"])
    P.log(f"gnn2final: {best['id']} {best['name']}, {seeds} seed(s) x {epochs} epochs as version 1.0; version 1.0 "
          f"{ref_mae:.3f} K on these folds" + ("" if same_folds is None else f" (same folds as its run: {same_folds})") +
          f"; jax {jax.__version__}, optax {optax.__version__}")
    outs, recs = [], []
    for s in range(seeds):
        o, rec = train_all(g, Ttrans, y_tc, groups, splits, cfg, glob, seed=s + 1, epochs=epochs)
        outs.append(o)
        recs.append(rec)
        P.log(f"gnn2final seed {s + 1}: Tc MAE {float(np.mean(np.abs(o['tc'] - y_tc))):.3f} K ({rec['seconds']} s)")
    pred = {k: np.mean([o[k] for o in outs], axis=0) for k in ("tc", "lambda", "wlog")}
    tc_ad = P.allen_dynes(np.clip(pred["lambda"], 0, None), np.clip(pred["wlog"], 0, None))
    fm = G1.fold_maes(y_tc, pred["tc"], folds)
    mae = float(np.mean(np.abs(pred["tc"] - y_tc)))
    folds_better = int(sum(a < b for a, b in zip(fm, ref_folds)))
    adopted = mae < ref_mae and folds_better >= P.ADOPT_FOLDS
    cmp = G1.compare(train, y_tc, pred["tc"], folds)
    comp, _, blend = cmp if cmp else (None, None, None)
    if comp:
        comp["folds_better_storm1"] = int(sum(a < b for a, b in zip(fm, comp["storm1"]["folds"])))
        comp["folds_better_baseline"] = int(sum(a < b for a, b in zip(fm, comp["baseline"]["folds"])))
        comp["blend"]["folds_better_storm1"] = int(sum(a < b for a, b in zip(comp["blend"]["folds"], comp["storm1"]["folds"])))
    stamp = P.now_iso()
    fin = {"run_at": stamp, "commit": os.environ.get("GITHUB_SHA", "local")[:7], "round": ROUND, "model": NAME,
           "design": {"id": best["id"], "name": best["name"], "config": best["config"]},
           "training": {"seeds": seeds, "epochs": epochs, "runs": recs},
           "search": {"tc_mae": best["tc_mae"], "fold_mae": best["fold_mae"], "folds_better": best["folds_better"],
                      "epochs": (best.get("training") or {}).get("epochs", EPOCHS),
                      "reference_mae": next(r for r in srch["leaderboard"] if r["id"] == "G0")["tc_mae"]},
           "scores": {"tc": P.metrics(y_tc, pred["tc"]), "tc_via_lambda_wlog": P.metrics(y_tc, tc_ad),
                      "lambda": P.metrics(y_lam, pred["lambda"]), "wlog": P.metrics(y_wlog, pred["wlog"])},
           "fold_mae": fm, "reference": {"version": "1.0", "tc_mae": ref_mae, "fold_mae": ref_folds, "same_folds": same_folds},
           "folds_better": folds_better, "adopted": adopted, "version": f"{ROUND}.0" if adopted else None,
           "rule": (f"released as version {ROUND}.0 only if it beats version 1.0 on average and in at least "
                    f"{P.ADOPT_FOLDS} of {P.N_FOLDS} folds, trained the same way on the same folds"),
           "comparison": comp, "minutes": round((time.time() - t_start) / 60, 1)}
    results, progress = P.RESULTS, P.PROGRESS
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="gnn2final-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        results, progress = tmp / "results", tmp / "progress.json"
    write_final(fin, cfg, r1, train, fold_of, pred, tc_ad, blend, results, progress)
    if SMOKE:
        P.log(f"gnn2final smoke test passed; outputs in {results.parent}")


def final_spec(cfg: dict, r1: dict, seeds: int, epochs: int) -> dict:
    """Version 2.0's structure, as round 1's spec with the changes the selected design makes."""
    spec = dict(r1.get("spec") or {})
    spec["layers"] = (f"{cfg['n_conv']} gated message-passing layers (sigmoid gate times softplus message, averaged over "
                      f"neighbours, residual, layer norm), width {cfg['hidden']}")
    spec["readout"] = ("mean over atoms" + (", joined by Storm 1.0's 54 crystal descriptors," if cfg.get("hybrid") else ",") +
                       " then a network with " + " and ".join(str(x) for x in cfg["head"]) + " units (SiLU)")
    if cfg.get("ad_head"):
        spec["targets"] = ("log(1 + Tc), log λ and log ω_log together; Tc is computed inside the network from λ and "
                           "ω_log with the Allen-Dynes formula")
    spec["training"] = (f"AdamW, peak learning rate {cfg['lr']}, weight decay {cfg['wd']}, warm-up then cosine decay, "
                        f"{G1.BATCH} crystals per step, {epochs} epochs, Huber loss; the epoch with the lowest validation "
                        f"Tc error on 10% of the training fold's chemical systems is kept" +
                        ("; the network is evaluated with an exponential moving average of its weights" if cfg.get("ema") else ""))
    spec["ensemble"] = f"average of {seeds} seed(s) per fold"
    spec.pop("n_params", None)
    return spec


def write_final(fin: dict, cfg: dict, r1: dict, train: pd.DataFrame, fold_of: np.ndarray, pred: dict, tc_ad: np.ndarray,
                blend, results: Path, progress: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    (results / f"gnn_round{ROUND}_final.json").write_text(json.dumps(fin, indent=2, default=float) + "\n")
    cols = {"id": train["id"], "chemsys": train["chemsys"], "fold": fold_of, "tc": train["tc"], "tc_pred": pred["tc"],
            "tc_pred_allen_dynes": tc_ad, "lambda": train["lambda"], "lambda_pred": pred["lambda"],
            "wlog": train["wlog"], "wlog_pred": pred["wlog"]}
    if blend is not None:
        cols["tc_pred_blend_storm1"] = blend
    pd.DataFrame(cols).round(5).to_csv(results / f"gnn_round{ROUND}_final_predictions.csv", index=False)

    prog = json.loads(progress.read_text(encoding="utf-8"))
    stamp, sc, comp, ver = fin["run_at"], fin["scores"], fin.get("comparison"), f"{ROUND}.0"
    cur = prog.get("gnn") or {}
    old = {v.get("round"): v for v in cur.get("versions", [])}
    v1 = dict(old.get(1) or {"version": "1.0", "round": 1, "date": cur.get("date"), "status": "adopted",
                             "summary": "CGCNN-style message passing on the crystal graph, trained end to end"})
    v1.update(_r1_fields(r1))
    v2 = dict(old.get(ROUND) or {})
    fields = {"tc_mae": round(sc["tc"]["mae"], 3), "folds": [round(x, 3) for x in fin["fold_mae"]],
              "tc_via_allen_dynes_mae": round(sc["tc_via_lambda_wlog"]["mae"], 3), "lambda_mae": round(sc["lambda"]["mae"], 3),
              "wlog_mae": round(sc["wlog"]["mae"], 1),
              "spec": final_spec(cfg, r1, fin["training"]["seeds"], fin["training"]["epochs"])}
    if comp:
        fields.update({"storm1_mae": round(comp["storm1"]["tc_mae"], 3), "baseline_mae": round(comp["baseline"]["tc_mae"], 3),
                       "folds_better_storm1": comp["folds_better_storm1"], "folds_better_baseline": comp["folds_better_baseline"],
                       "blend": {"name": comp["blend"]["name"], "tc_mae": round(comp["blend"]["tc_mae"], 3),
                                 "folds": [round(x, 3) for x in comp["blend"]["folds"]],
                                 "folds_better_storm1": comp["blend"]["folds_better_storm1"]}})
    search = dict(v2.get("search") or {})
    search.update({"best": fin["design"]["id"], "tc_mae": round(fin["search"]["tc_mae"], 3),
                   "folds_better": fin["search"]["folds_better"], "reference_mae": round(fin["search"]["reference_mae"], 3),
                   "seeds": 1, "epochs": fin["search"]["epochs"]})
    v2.update({"version": ver, "round": ROUND, "date": v2.get("date") or stamp[:10], "checked": stamp[:10],
               "status": "adopted" if fin["adopted"] else "experimental", "summary": fin["design"]["name"],
               "seeds": fin["training"]["seeds"], "epochs": fin["training"]["epochs"],
               "reference_mae": round(fin["reference"]["tc_mae"], 3), "folds_better": fin["folds_better"],
               "search": search, **fields})
    versions = sorted([v for r, v in old.items() if r not in (1, ROUND)] + [v1, v2], key=lambda v: v["round"])
    curv = [v for v in versions if v.get("status") == "adopted"][-1]
    block = {k: v for k, v in cur.items() if k not in METRIC_KEYS}
    block.update({"name": NAME, "status": "done", "current": curv["version"], "round": max(v["round"] for v in versions),
                  "date": stamp[:10], "versions": versions,
                  "summary": ("CGCNN-style message passing on the crystal graph, trained end to end" if curv["round"] == 1
                              else "crystal-graph network, AI-designed: " + _phrase(curv["summary"]))})
    block.update({k: curv[k] for k in METRIC_KEYS if k in curv})
    prog["gnn"] = block
    # a search run before the final check existed recorded the selected design as released; correct that record
    model2 = f"{NAME} {ver} (AI-designed)"
    prog["history"] = [h for h in prog.get("history", []) if h.get("model") != model2]
    for e in prog.get("log", []):
        ev = e.get("event", "")
        if ev.startswith(f"{NAME}, round {ROUND} (") and f"released as version {ver}" in ev:
            e["event"] = ev.replace(f"released as version {ver}", "selected for the final check with two seeds")
    if fin["adopted"]:
        P.add_history(prog, {"at": stamp, "model": model2, "target": "Tc", "split": "val", "mae": fields["tc_mae"]})
    tr = fin["training"]
    msg = (f"{NAME}, round {ROUND} final check: {fin['design']['id']} {fin['design']['name'].lstrip('+ ')}, retrained like "
           f"version 1.0 ({tr['seeds']} seeds averaged, {tr['epochs']} epochs): Tc MAE {sc['tc']['mae']:.3f} K against "
           f"{fin['reference']['tc_mae']:.3f} K for version 1.0, better in {fin['folds_better']} of {P.N_FOLDS} folds; " +
           (f"released as version {ver}" if fin["adopted"] else "not released, so version 1.0 stays"))
    if comp:
        msg += (f"; averaged with Storm 1.0 {comp['blend']['tc_mae']:.3f} K (Storm 1.0 alone {comp['storm1']['tc_mae']:.3f} K, "
                f"better in {comp['blend']['folds_better_storm1']} of 5 folds)")
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)
