"""E4 -- end-to-end running time of PRIV_EXPL, OPT_PRIV_EXPL, B1, B2, B3 (Section 5.3.2, Figure 7).

For every dataset and every one of its pairs, one parameter is varied at a time
(k, N, eps, |P|, tau, gamma) with all others at their defaults.  Each timing is
end to end, from ``(D, Q1(D), Q2(D))`` to the selected explanations (see
:func:`pqde.runner.time_methods`).  Every run has the time limit
``defaults.timeout_s``.  Every method is timed ``e4.repeats`` times at every
point; a method that hits the limit is run ``defaults.timeout_repeats`` times at
that point and then no more.  Nothing is inferred: every recorded run was run.

Raw data: ``results/e4/raw/runtime.csv`` (one row per timed run).  The figure of
a dataset is one row of panels with the four methods in each (``pqde plot e4``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from ..pairs import pair_on_sample, resolve_pair
from ..runner import METHODS, time_methods
from ..views import enumerate_views
from .common import make_params, out_dir, pairs_by_dataset, read_raw, run_metadata, write_csv, write_json, write_raw

EXP = "e4"
PARAM_SWEEPS = ("k", "epsilon", "tau", "gamma_mult")


def _views(ds, fraction: float, seed: int):
    if fraction >= 1.0:
        return None
    allv = enumerate_views(ds)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(allv), size=max(1, int(round(fraction * len(allv)))), replace=False))
    return [allv[i] for i in idx]


def points(raw: pd.DataFrame) -> pd.DataFrame:
    """Median over repeats per (pair, point, method), then mean over the pairs of a dataset."""
    keys = ["dataset", "synthetic", "pair", "sweep", "value", "method"]
    per_pair = raw.groupby(keys, as_index=False).agg(total_s=("total_s", "median"), build_s=("build_s", "median"),
                                                     mech_s=("mech_s", "median"), timeout=("timeout", "max"),
                                                     N=("N", "first"), P=("P", "first"))
    out = per_pair.groupby(["dataset", "synthetic", "sweep", "value", "method"], as_index=False).agg(
        total_s=("total_s", "mean"), build_s=("build_s", "mean"), mech_s=("mech_s", "mean"),
        timeout=("timeout", "max"), N=("N", "mean"), P=("P", "mean"), pairs=("pair", "nunique"))
    return out


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    pts = points(read_raw(EXP, "runtime", base))
    order = {d: i for i, d in enumerate(cfg.get("datasets", []))}
    pts = pts.sort_values("dataset", key=lambda c: c.map(lambda d: order.get(d, len(order))), kind="stable")
    write_csv(pts, od / "points.csv")
    syn = {r.dataset: bool(r.synthetic) for r in pts.itertuples()}
    for ds in dict.fromkeys(pts.dataset):
        plotting.plot_runtime_row(pts, ds, od / f"runtime_{ds}", synthetic=syn.get(ds, False))
    plotting.plot_runtime_grid(pts, od / "runtime_all_datasets", synthetic=syn)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    d = cfg["defaults"]
    e = cfg[EXP]
    seed = int(d["seed"])
    timeout_s = float(d["timeout_s"])
    repeats = 1 if quick else int(e["repeats"])
    by_ds = pairs_by_dataset(pairs or e.get("pairs") or cfg.get("runtime_pairs", cfg["pairs"]), cfg.get("datasets"))
    timeout_reps = int(d.get("timeout_repeats", 3))
    rows = []
    for ds_name, pids in by_ds.items():
        sweeps = {k: list(v) for k, v in e["sweeps"].items()}
        if "data_fraction" in sweeps:
            sweeps["data_fraction"] = sorted(set(sweeps["data_fraction"])
                                             | set(e.get("extra_data_fraction", {}).get(ds_name, [])))
        if quick:
            sweeps = {k: [v[0], v[-1]] for k, v in sweeps.items()}
        for pid in pids:
            pair = resolve_pair(pid)
            syn = bool(pair.dataset.meta.get("synthetic", False))
            n_full = len(enumerate_views(pair.dataset))
            print(f"  E4 {ds_name}/{pid}", flush=True)
            for sweep, values in sweeps.items():
                if sweep == "tau":  # capped at |P|; "all" = every view
                    values = sorted({n_full if str(v) == "all" else min(int(v), n_full) for v in values})
                for val in values:
                    frac = float(val) if sweep == "data_fraction" else float(d["data_fraction"])
                    vfrac = float(val) if sweep == "view_fraction" else float(d["view_fraction"])
                    ds, q1, q2 = pair_on_sample(pair, frac, seed)
                    views = _views(ds, vfrac, seed)
                    n_views = len(views) if views is not None else len(enumerate_views(ds))
                    over = {sweep: val} if sweep in PARAM_SWEEPS else {}
                    params = make_params(d, n_views, len(ds.explain_attrs), **over)
                    # every method is timed in every repeat; a method that hits the time limit
                    # is run timeout_repeats times at this point and then no more
                    n_timeouts: dict = {}
                    for r in range(repeats):
                        methods = tuple(m for m in METHODS if n_timeouts.get(m, 0) < timeout_reps)
                        if not methods:
                            break
                        outs = time_methods(ds, q1, q2, params, methods=methods, views=views, seed=seed, repeat=r,
                                            gamma_eval=float(d["gamma_eval"]), timeout_s=timeout_s)
                        for out in outs:
                            if out.timeout:
                                n_timeouts[out.method] = n_timeouts.get(out.method, 0) + 1
                            rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "sweep": sweep, "value": val,
                                         "method": out.method, "repeat": r, "N": ds.N, "P": n_views, "k": params.k,
                                         "epsilon": params.epsilon, "tau": params.tau, "gamma": params.gamma,
                                         "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s,
                                         "timeout": out.timeout, "inferred": False,
                                         "b2_subsets": out.extra.get("subsets", out.extra.get("subsets_total")),
                                         "b2_estimated_s": out.extra.get("estimated_seconds")})
                    print(f"    {sweep}={val}: " + "  ".join(
                        f"{m} {np.median([x['total_s'] for x in rows if x['pair'] == pid and x['sweep'] == sweep and x['value'] == val and x['method'] == m]):.3g}s"
                        for m in METHODS), flush=True)
                    write_raw(pd.DataFrame(rows), EXP, "runtime", base)  # checkpoint after every point
    write_json(run_metadata(cfg, experiment=EXP, repeats=repeats, timeout_s=timeout_s), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
