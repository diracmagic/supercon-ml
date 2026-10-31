"""Graph neural network for electron-phonon superconductors, round 1.

A crystal-graph convolutional network in the style of CGCNN (Xie & Grossman, Phys. Rev. Lett. 120, 145301, 2018),
trained end to end on the Alexandria electron-phonon set. Atoms are the nodes; each atom is joined to its 12 nearest
neighbours within 8 Å, periodic images included, and each edge carries its length in a Gaussian basis. Three gated
message-passing layers are followed by a mean over the atoms and a small network that predicts log(1 + Tc), log λ
and log ω_log together. Tc is also computed from the predicted λ and ω_log with the Allen-Dynes formula.

It is scored with the same 5-fold GroupKFold by chemical system as Storm, so its error compares directly with
Storm 1.0 and the gradient-boosting baseline (results/model_search_round2_predictions.csv). Inside each training fold,
10% of the chemical systems are held back to pick the best epoch; the test fold is never seen during training.
The locked JARVIS test set is not used. Runs on CPU with JAX.

Run from the repository root:
    python ml/pipeline.py gnn
Environment: GNN_EPOCHS, GNN_SEEDS and GNN_BUDGET_MIN (minutes) set the training length; GNN_SMOKE=1 runs a quick
check on a small subset and writes to a temporary folder instead of results/ and progress/.
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

import pipeline as P

ROUND = 1
NAME = "Graph neural network"
CUTOFF = 8.0          # Å
MAX_NB = 12           # nearest neighbours per atom
N_RBF = 40            # Gaussians for the edge length, 0 to CUTOFF
HIDDEN = 64
N_CONV = 3
HEAD = (128, 64)
LR = 2e-3
WEIGHT_DECAY = 1e-4
BATCH = 64            # crystals per training step
EVAL_BATCH = 256
VAL_FRAC = 0.10       # share of a training fold's chemical systems kept back to pick the epoch
TARGET_W = (1.0, 0.5, 0.5)   # loss weights for log(1 + Tc), log λ, log ω_log
HUBER = 0.05          # in units of each target's standard deviation
SMOKE = os.environ.get("GNN_SMOKE") == "1"
EPOCHS = int(os.environ.get("GNN_EPOCHS", 2 if SMOKE else 200))
SEEDS = int(os.environ.get("GNN_SEEDS", 1 if SMOKE else 2))
BUDGET_MIN = float(os.environ.get("GNN_BUDGET_MIN", 110))
MIN_EPOCHS = 60
ROUND2_PRED = P.RESULTS / "model_search_round2_predictions.csv"


# ---------------------------------------------------------------- crystal graphs


def crystal_graph(atoms: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Edges (receiver, sender, length in Å) from every atom to its MAX_NB nearest neighbours within CUTOFF."""
    lat = np.asarray(atoms["lattice_mat"], float)
    xyz = np.asarray(atoms["coords"], float)
    frac = xyz @ np.linalg.inv(lat) if atoms.get("cartesian") else xyz
    frac = frac - np.floor(frac)
    cart = frac @ lat
    n = len(cart)
    vol = abs(float(np.linalg.det(lat)))
    normals = np.cross(lat[[1, 2, 0]], lat[[2, 0, 1]])
    heights = vol / np.linalg.norm(normals, axis=1)          # spacing of the lattice planes
    reps = np.ceil(CUTOFF / heights).astype(int) + 1
    grid = np.stack(np.meshgrid(*[np.arange(-r, r + 1) for r in reps], indexing="ij"), -1).reshape(-1, 3)
    images = ((grid @ lat)[:, None, :] + cart[None, :, :]).reshape(-1, 3)   # image s of atom j at s * n + j
    d = np.linalg.norm(cart[:, None, :] - images[None, :, :], axis=-1)
    s0 = int(np.flatnonzero((grid == 0).all(1))[0])
    d[np.arange(n), s0 * n + np.arange(n)] = np.inf             # an atom is not its own neighbour
    k = min(MAX_NB, d.shape[1] - 1)
    idx = np.argpartition(d, k - 1, axis=1)[:, :k]
    dk = np.take_along_axis(d, idx, axis=1)
    keep = dk <= CUTOFF
    rcv = np.repeat(np.arange(n)[:, None], k, axis=1)[keep]
    snd = (idx % n)[keep]
    return rcv.astype(np.int32), snd.astype(np.int32), dk[keep].astype(np.float32)


def build_graphs(train: pd.DataFrame, table: pd.DataFrame) -> dict:
    elements = sorted({e for a in train["atoms"] for e in a["elements"]})
    index = {e: i for i, e in enumerate(elements)}
    props = table.loc[elements, P.ELEMENT_PROPS].to_numpy(float)
    mu, sd = np.nanmean(props, 0), np.nanstd(props, 0)
    props = np.nan_to_num((props - mu) / np.where(sd > 0, sd, 1.0)).astype(np.float32)
    g = {"z": [], "rcv": [], "snd": [], "dist": [], "elements": elements, "props": props}
    for a in train["atoms"]:
        r, s, d = crystal_graph(a)
        g["z"].append(np.array([index[e] for e in a["elements"]], np.int32))
        g["rcv"].append(r)
        g["snd"].append(s)
        g["dist"].append(d)
    g["n"] = np.array([len(z) for z in g["z"]])
    g["e"] = np.array([len(r) for r in g["rcv"]])
    return g


class Packer:
    """Packs crystals into batches of fixed size (padded), so the network compiles once."""

    def __init__(self, g: dict, max_graphs: int, mean_nodes: float):
        self.g = g
        self.G = max_graphs
        self.N = int(max(math.ceil(max_graphs * mean_nodes * 1.25), g["n"].max()))
        self.E = self.N * MAX_NB

    def batches(self, order) -> list:
        out, cur, nn = [], [], 0
        for i in order:
            ni = int(self.g["n"][i])
            if cur and (len(cur) == self.G or nn + ni > self.N):
                out.append(cur)
                cur, nn = [], 0
            cur.append(int(i))
            nn += ni
        if cur:
            out.append(cur)
        return out

    def collate(self, idx, Y=None) -> dict:
        G, N, E = self.G + 1, self.N + 1, self.E      # the last graph and the last node are padding
        z = np.zeros(N, np.int32)
        nodeg = np.full(N, G - 1, np.int32)
        nmask = np.zeros(N, np.float32)
        rcv = np.full(E, N - 1, np.int32)
        snd = np.full(E, N - 1, np.int32)
        dist = np.full(E, CUTOFF, np.float32)
        emask = np.zeros(E, np.float32)
        y = np.zeros((G, 3), np.float32)
        gmask = np.zeros(G, np.float32)
        no = eo = 0
        for k, i in enumerate(idx):
            ni, ei = int(self.g["n"][i]), int(self.g["e"][i])
            z[no:no + ni] = self.g["z"][i]
            nodeg[no:no + ni] = k
            nmask[no:no + ni] = 1
            rcv[eo:eo + ei] = self.g["rcv"][i] + no
            snd[eo:eo + ei] = self.g["snd"][i] + no
            dist[eo:eo + ei] = self.g["dist"][i]
            emask[eo:eo + ei] = 1
            if Y is not None:
                y[k] = Y[i]
            gmask[k] = 1
            no += ni
            eo += ei
        return {"z": z, "nodeg": nodeg, "nmask": nmask, "rcv": rcv, "snd": snd, "dist": dist, "emask": emask,
                "y": y, "gmask": gmask}


# ---------------------------------------------------------------- the network (JAX)


def network(props: np.ndarray):
    """Returns init, forward and loss functions of the crystal-graph network."""
    import jax
    import jax.numpy as jnp

    props_t = jnp.asarray(props)
    centers = jnp.linspace(0.0, CUTOFF, N_RBF)
    width = CUTOFF / (N_RBF - 1)
    tw = jnp.asarray(TARGET_W, jnp.float32)

    def init(key, n_el: int) -> dict:
        keys = iter(jax.random.split(key, 8 + 4 * N_CONV + len(HEAD)))

        def dense(i, o, bias=True, scale=1.0):
            w = jax.random.normal(next(keys), (i, o), jnp.float32) * math.sqrt(scale / i)
            return {"w": w, "b": jnp.zeros(o, jnp.float32)} if bias else {"w": w}
        p = {"emb": jax.random.normal(next(keys), (n_el, HIDDEN), jnp.float32) * 0.5,
             "prop": dense(props.shape[1], HIDDEN), "conv": [], "head": []}
        for _ in range(N_CONV):
            p["conv"].append({"dst": dense(HIDDEN, 2 * HIDDEN, bias=False), "src": dense(HIDDEN, 2 * HIDDEN, bias=False),
                              "edge": dense(N_RBF, 2 * HIDDEN), "g": jnp.ones(HIDDEN, jnp.float32),
                              "b": jnp.zeros(HIDDEN, jnp.float32)})
        dims = (HIDDEN,) + HEAD
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
        for d in p["head"]:
            x = jax.nn.silu(x @ d["w"] + d["b"])
        return x @ p["out"]["w"] + p["out"]["b"]

    def loss(p, bt):
        err = jnp.abs(forward(p, bt) - bt["y"])
        hub = jnp.where(err < HUBER, 0.5 * err ** 2 / HUBER, err - 0.5 * HUBER)
        w = bt["gmask"][:, None] * tw[None, :]
        return jnp.sum(hub * w) / (jnp.maximum(jnp.sum(bt["gmask"]), 1.0) * jnp.sum(tw))

    return init, forward, loss


def n_params(p) -> int:
    import jax
    return int(sum(np.size(x) for x in jax.tree_util.tree_leaves(p)))


# ---------------------------------------------------------------- training


def train_all(g: dict, Ttrans: np.ndarray, y_tc: np.ndarray, groups: np.ndarray, splits: list) -> tuple[np.ndarray, dict]:
    """Out-of-fold predictions (n, 3) in physical units (Tc, λ, ω_log) and a record of the training."""
    import jax
    import optax

    init, forward, loss = network(g["props"])
    new_key = getattr(jax.random, "key", None) or jax.random.PRNGKey
    n_el = len(g["elements"])
    mean_nodes = float(np.mean(g["n"]))
    packer = Packer(g, BATCH, mean_nodes)
    epacker = Packer(g, EVAL_BATCH, mean_nodes)
    predict = jax.jit(forward)

    def make_opt(epochs: int):
        per_epoch = max(len(packer.batches(fit_val(tr, k)[0])) for k, (tr, _) in enumerate(splits))
        steps = epochs * per_epoch
        warm = max(1, steps // 50)
        sched = optax.warmup_cosine_decay_schedule(init_value=LR * 0.05, peak_value=LR, warmup_steps=warm,
                                                   decay_steps=steps, end_value=LR * 0.02)
        opt = optax.chain(optax.clip_by_global_norm(1.0), optax.adamw(sched, weight_decay=WEIGHT_DECAY))

        @jax.jit
        def step(p, s, bt):
            val, grads = jax.value_and_grad(loss)(p, bt)
            upd, s = opt.update(grads, s, p)
            return optax.apply_updates(p, upd), s, val
        return opt, step

    def fit_val(tr: np.ndarray, fold: int) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(P.SEED + 100 * fold)
        ug = np.unique(groups[tr])
        rng.shuffle(ug)
        held = set(ug[:max(1, int(round(VAL_FRAC * len(ug))))])
        is_val = np.array([x in held for x in groups[tr]])
        return tr[~is_val], tr[is_val]

    def predict_std(p, idx: np.ndarray) -> np.ndarray:
        out = np.zeros((len(idx), 3), np.float32)
        pos = {int(i): k for k, i in enumerate(idx)}
        for b in epacker.batches(idx):
            o = np.asarray(predict(p, epacker.collate(b)))[:len(b)]
            out[[pos[i] for i in b]] = o
        return out

    # time two epochs to fit the run into the budget (GNN_BUDGET_MIN)
    epochs, seeds = EPOCHS, SEEDS
    fit0, _ = fit_val(splits[0][0], 0)
    mu0, sd0 = Ttrans[fit0].mean(0), Ttrans[fit0].std(0)
    opt, step = make_opt(3)
    p = init(new_key(0), n_el)
    s = opt.init(p)
    rng = np.random.default_rng(P.SEED)
    Y0 = ((Ttrans - mu0) / sd0).astype(np.float32)
    times = []
    for ep in range(3):
        t0 = time.time()
        for b in packer.batches(rng.permutation(fit0)):
            p, s, _ = step(p, s, packer.collate(b, Y0))
        jax.block_until_ready(p)
        times.append(time.time() - t0)
    t_epoch = float(np.mean(times[1:]))
    t_eval = time.time()
    predict_std(p, fit0[: max(1, len(fit0) // 10)])
    t_eval = time.time() - t_eval
    per_epoch = t_epoch + t_eval
    budget = BUDGET_MIN * 60
    projected = per_epoch * epochs * seeds * len(splits)
    if projected > budget and seeds > 1:
        seeds = 1
        projected = per_epoch * epochs * seeds * len(splits)
    if projected > budget:
        epochs = max(MIN_EPOCHS, int(budget / (per_epoch * seeds * len(splits))))
    P.log(f"gnn: {len(packer.batches(fit0))} steps per epoch, {t_epoch:.1f} s per epoch (+{t_eval:.1f} s to validate; "
          f"first epoch with compilation {times[0]:.0f} s); running {epochs} epochs x {seeds} seed(s) x {len(splits)} folds, "
          f"about {per_epoch * epochs * seeds * len(splits) / 60:.0f} min")

    opt, step = make_opt(epochs)
    n = len(y_tc)
    pred_std = np.zeros((n, 3), np.float32)
    record = {"epochs": epochs, "seeds": seeds, "seconds_per_epoch": round(t_epoch, 2), "folds": []}
    for k, (tr, te) in enumerate(splits):
        fit, val = fit_val(tr, k)
        mu, sd = Ttrans[fit].mean(0), Ttrans[fit].std(0)
        Ys = ((Ttrans - mu) / sd).astype(np.float32)
        acc = np.zeros((len(te), 3), np.float32)
        frec = {"fold": k + 1, "n_fit": int(len(fit)), "n_val": int(len(val)), "n_test": int(len(te)), "seeds": []}
        for sd_i in range(seeds):
            t0 = time.time()
            p = init(new_key(1000 * (k + 1) + sd_i), n_el)
            s = opt.init(p)
            rng = np.random.default_rng(P.SEED + 1000 * (k + 1) + sd_i)
            best = (np.inf, p, -1)
            curve = []
            for ep in range(epochs):
                losses = []
                bs = packer.batches(rng.permutation(fit))
                for b in bs:
                    p, s, lv = step(p, s, packer.collate(b, Ys))
                    losses.append(lv)
                tot = float(np.sum(np.asarray(jax.device_get(losses), float)))
                pv = predict_std(p, val)
                tc_v = np.clip(np.expm1(pv[:, 0] * sd[0] + mu[0]), 0, None)
                mae_v = float(np.mean(np.abs(tc_v - y_tc[val])))
                curve.append(round(mae_v, 4))
                if mae_v < best[0]:
                    best = (mae_v, p, ep)
                if ep % 25 == 0 or ep == epochs - 1:
                    P.log(f"gnn fold {k + 1} seed {sd_i + 1} epoch {ep + 1}/{epochs}: loss {tot / len(bs):.4f}, "
                          f"validation Tc MAE {mae_v:.3f} K (best {best[0]:.3f} K at epoch {best[2] + 1})")
            acc += predict_std(best[1], te) / seeds
            frec["seeds"].append({"best_epoch": best[2] + 1, "val_tc_mae": round(best[0], 4), "seconds": round(time.time() - t0),
                                  "curve": curve[::5]})
        pred_std[te] = acc * sd + mu
        mae_te = float(np.mean(np.abs(np.clip(np.expm1(pred_std[te, 0]), 0, None) - y_tc[te])))
        frec["test_tc_mae"] = round(mae_te, 4)
        record["folds"].append(frec)
        P.log(f"gnn fold {k + 1}: test Tc MAE {mae_te:.3f} K")
    record["n_params"] = n_params(p)
    out = np.column_stack([np.clip(np.expm1(pred_std[:, 0]), 0, None), np.exp(pred_std[:, 1]), np.exp(pred_std[:, 2])])
    return out, record


# ---------------------------------------------------------------- scores and progress


def spec(record: dict, n_el: int) -> dict:
    return {
        "architecture": "CGCNN-style crystal-graph network",
        "graph": f"atoms as nodes; edges to the {MAX_NB} nearest neighbours within {CUTOFF:g} Å, periodic images included",
        "node_inputs": f"a learned vector for each of {n_el} elements plus 8 element properties ({', '.join(P.ELEMENT_PROPS)})",
        "edge_inputs": f"bond length in {N_RBF} Gaussians from 0 to {CUTOFF:g} Å",
        "layers": f"{N_CONV} gated message-passing layers (sigmoid gate times softplus message, averaged over neighbours, "
                  f"residual, layer norm), width {HIDDEN}",
        "readout": f"mean over atoms, then a network with {HEAD[0]} and {HEAD[1]} units (SiLU)",
        "targets": "log(1 + Tc), log λ and log ω_log together (loss weights 1, 0.5, 0.5); Tc also via Allen-Dynes from λ and ω_log",
        "training": (f"AdamW, peak learning rate {LR:g}, weight decay {WEIGHT_DECAY:g}, warm-up then cosine decay, "
                     f"{BATCH} crystals per step, {record['epochs']} epochs, Huber loss; the epoch with the lowest "
                     f"validation Tc error on {VAL_FRAC:.0%} of the training fold's chemical systems is kept"),
        "ensemble": f"average of {record['seeds']} seed(s) per fold",
        "n_params": record.get("n_params"),
    }


def fold_maes(y: np.ndarray, p: np.ndarray, folds: list) -> list:
    return [float(np.mean(np.abs(p[te] - y[te]))) for te in folds]


def compare(train: pd.DataFrame, y_tc: np.ndarray, tc_pred: np.ndarray, folds: list) -> dict | None:
    """Storm 1.0 and the baseline on the same materials and folds, from the round-2 predictions."""
    if not ROUND2_PRED.exists():
        return None
    ref = pd.read_csv(ROUND2_PRED)
    if not {"id", "tc_pred_storm1", "tc_pred_baseline"} <= set(ref.columns):
        return None
    ref = ref.drop_duplicates("id").set_index("id")
    ids = train["id"].astype(str)
    if not ids.isin(ref.index.astype(str)).all():
        P.log("gnn: round-2 predictions do not cover every material; no comparison")
        return None
    ref.index = ref.index.astype(str)
    s1 = ref.loc[ids, "tc_pred_storm1"].to_numpy(float)
    base = ref.loc[ids, "tc_pred_baseline"].to_numpy(float)
    blend = 0.5 * (tc_pred + s1)
    out = {"storm1": {"tc_mae": float(np.mean(np.abs(s1 - y_tc))), "folds": fold_maes(y_tc, s1, folds)},
           "baseline": {"tc_mae": float(np.mean(np.abs(base - y_tc))), "folds": fold_maes(y_tc, base, folds)},
           "blend": {"name": "average of the graph network and Storm 1.0", "weights": [0.5, 0.5],
                     "tc_mae": float(np.mean(np.abs(blend - y_tc))), "folds": fold_maes(y_tc, blend, folds)}}
    return out, s1, blend


def report(train: pd.DataFrame, pred: np.ndarray, folds: list, record: dict, n_el: int, results: Path, progress: Path,
           versions: dict) -> dict:
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    tc_pred, lam_pred, wlog_pred = pred[:, 0], pred[:, 1], pred[:, 2]
    tc_ad = P.allen_dynes(lam_pred, wlog_pred)
    tail = float(np.quantile(y_tc, 0.9))
    scores = {"tc": P.metrics(y_tc, tc_pred, tail=tail), "tc_via_lambda_wlog": P.metrics(y_tc, tc_ad, tail=tail),
              "lambda": P.metrics(y_lam, lam_pred), "wlog": P.metrics(y_wlog, wlog_pred)}
    fm = fold_maes(y_tc, tc_pred, folds)
    cmp = compare(train, y_tc, tc_pred, folds)
    comp, s1, blend = cmp if cmp else (None, None, None)
    if comp:
        comp["folds_better_storm1"] = int(sum(a < b for a, b in zip(fm, comp["storm1"]["folds"])))
        comp["folds_better_baseline"] = int(sum(a < b for a, b in zip(fm, comp["baseline"]["folds"])))
        comp["blend"]["folds_better_storm1"] = int(sum(a < b for a, b in zip(comp["blend"]["folds"], comp["storm1"]["folds"])))
    stamp = P.now_iso()
    out = {
        "run_at": stamp,
        "commit": os.environ.get("GITHUB_SHA", "local")[:7],
        "round": ROUND,
        "model": NAME,
        "selection": (f"{P.N_FOLDS}-fold GroupKFold by chemical system on Alexandria ({len(y_tc):,} materials), the same "
                      "folds as Storm; the locked JARVIS test set is not used"),
        "spec": spec(record, n_el),
        "scores": scores,
        "fold_mae": fm,
        "comparison": comp,
        "training": record,
        "versions": versions,
    }
    results.mkdir(parents=True, exist_ok=True)
    (results / f"gnn_round{ROUND}.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    cols = {"id": train["id"], "chemsys": train["chemsys"], "fold": np.zeros(len(y_tc), int),
            "tc": y_tc, "tc_pred": tc_pred, "tc_pred_allen_dynes": tc_ad,
            "lambda": y_lam, "lambda_pred": lam_pred, "wlog": y_wlog, "wlog_pred": wlog_pred}
    for k, te in enumerate(folds):
        cols["fold"][te] = k + 1
    if blend is not None:
        cols["tc_pred_blend_storm1"] = blend
    pd.DataFrame(cols).round(5).to_csv(results / f"gnn_round{ROUND}_predictions.csv", index=False)
    update_progress(out, progress, stamp)
    return out


def update_progress(out: dict, progress: Path, stamp: str) -> None:
    prog = json.loads(progress.read_text(encoding="utf-8"))
    sc, comp = out["scores"], out.get("comparison")
    mae = sc["tc"]["mae"]
    block = {
        "name": NAME,
        "round": ROUND,
        "date": stamp[:10],
        "status": "done",
        "summary": "CGCNN-style message passing on the crystal graph, trained end to end",
        "tc_mae": round(mae, 3),
        "tc_via_allen_dynes_mae": round(sc["tc_via_lambda_wlog"]["mae"], 3),
        "lambda_mae": round(sc["lambda"]["mae"], 3),
        "wlog_mae": round(sc["wlog"]["mae"], 1),
        "folds": [round(x, 3) for x in out["fold_mae"]],
        "spec": out["spec"],
        "about": ("A crystal-graph network learns Tc, λ and ω_log straight from the atoms and their neighbours, with no "
                  "hand-made features. It is scored on the same five folds as Storm, grouped by chemical system."),
    }
    if comp:
        block.update({
            "storm1_mae": round(comp["storm1"]["tc_mae"], 3),
            "baseline_mae": round(comp["baseline"]["tc_mae"], 3),
            "folds_better_storm1": comp["folds_better_storm1"],
            "folds_better_baseline": comp["folds_better_baseline"],
            "blend": {"name": comp["blend"]["name"], "tc_mae": round(comp["blend"]["tc_mae"], 3),
                      "folds": [round(x, 3) for x in comp["blend"]["folds"]],
                      "folds_better_storm1": comp["blend"]["folds_better_storm1"]},
        })
    prog["gnn"] = block
    P.add_history(prog, {"at": stamp, "model": f"{NAME} (crystal graph)", "target": "Tc", "split": "val", "mae": round(mae, 3)})
    msg = (f"{NAME}, round {ROUND} (CGCNN-style, {out['spec']['n_params']:,} parameters): Tc MAE {mae:.2f} K on the "
           f"same 5 folds as Storm")
    if comp:
        msg += (f" (Storm 1.0 {comp['storm1']['tc_mae']:.2f} K, gradient boosting {comp['baseline']['tc_mae']:.2f} K; "
                f"better than Storm 1.0 in {comp['folds_better_storm1']} of 5 folds); averaged with Storm 1.0: "
                f"{comp['blend']['tc_mae']:.2f} K, better in {comp['blend']['folds_better_storm1']} of 5 folds")
    msg += f"; via λ and ω_log with Allen-Dynes: {sc['tc_via_lambda_wlog']['mae']:.2f} K"
    P.add_log(prog, stamp, msg)
    P.tidy(prog)
    prog["updated"] = stamp
    progress.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    P.log(msg)


# ---------------------------------------------------------------- command


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
    t0 = time.time()
    g = build_graphs(train, table)
    P.log(f"gnn: {len(train):,} crystal graphs ({int(g['n'].sum()):,} atoms, {int(g['e'].sum()):,} edges, "
          f"{g['n'].mean():.1f} atoms per cell on average, largest {g['n'].max()}) in {time.time() - t0:.0f} s; "
          f"jax {jax.__version__}, optax {optax.__version__}, {jax.device_count()} device(s): {jax.devices()[0].platform}")
    groups = train["chemsys"].to_numpy()
    y_tc, y_lam, y_wlog = (train[c].to_numpy(float) for c in ("tc", "lambda", "wlog"))
    Ttrans = np.column_stack([np.log1p(y_tc), np.log(y_lam), np.log(y_wlog)]).astype(np.float32)
    A = np.zeros((len(train), 1))
    splits = list(GroupKFold(n_splits=P.N_FOLDS).split(A, y_tc, groups))
    folds = [te for _, te in splits]
    pred, record = train_all(g, Ttrans, y_tc, groups, splits)
    record["minutes"] = round((time.time() - t_start) / 60, 1)
    versions = {"jax": jax.__version__, "optax": optax.__version__}
    if SMOKE:
        tmp = Path(tempfile.mkdtemp(prefix="gnn-smoke-"))
        shutil.copy(P.PROGRESS, tmp / "progress.json")
        out = report(train, pred, folds, record, len(g["elements"]), tmp / "results", tmp / "progress.json", versions)
        P.log(f"gnn smoke test passed: Tc MAE {out['scores']['tc']['mae']:.3f} K on {len(train)} materials; outputs in {tmp}")
        return
    report(train, pred, folds, record, len(g["elements"]), P.RESULTS, P.PROGRESS, versions)
