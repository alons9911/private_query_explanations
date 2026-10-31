"""E4 -- end-to-end running time of PRIV_EXPL, B1, B2 and B3 (Section 5.3.2, Figure 7).

For every dataset and every one of its pairs, one parameter is varied at a time
(k, N, eps, |P|, tau, gamma) with all others at their defaults.  Each timing is
end to end: the exact statistics on the server plus the method itself, from
``(D, Q1(D), Q2(D))`` to the selected explanation set (and, for PRIV_EXPL, the
noisy histograms).  B2 beyond ``b2_max_subsets`` subsets is timed on one block
and extrapolated (marked ``estimated``).

Raw data: ``results/e4/raw/runtime.csv`` (one row per timed run).  The figure of
a dataset is one row of panels with the four methods in each (``pqde plot e4``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from ..pairs import pair_on_sample, resolve_pair
from ..runner import METHODS, run_method
from ..views import enumerate_views
from .common import (make_params, out_dir, pairs_by_dataset, read_raw, run_metadata, stats_route, write_csv,
                     write_json, write_raw)

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
                                                     mech_s=("mech_s", "median"), estimated=("estimated", "max"),
                                                     N=("N", "first"), P=("P", "first"))
    out = per_pair.groupby(["dataset", "synthetic", "sweep", "value", "method"], as_index=False).agg(
        total_s=("total_s", "mean"), build_s=("build_s", "mean"), mech_s=("mech_s", "mean"),
        estimated=("estimated", "max"), N=("N", "mean"), P=("P", "mean"), pairs=("pair", "nunique"))
    return out


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    pts = points(read_raw(EXP, "runtime", base))
    write_csv(pts, od / "points.csv")
    syn = {r.dataset: bool(r.synthetic) for r in pts.itertuples()}
    for ds in dict.fromkeys(pts.dataset):
        plotting.plot_runtime_row(pts, ds, od / f"runtime_{ds}", synthetic=syn.get(ds, False))
    plotting.plot_runtime_grid(pts, od / "runtime_all_datasets", synthetic=syn)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    d = cfg["defaults"]
    e = cfg[EXP]
    seed = int(d["seed"])
    route = stats_route(d)
    repeats = 1 if quick else int(e["repeats"])
    by_ds = pairs_by_dataset(pairs or cfg["pairs"], cfg.get("datasets"))
    rows = []
    for ds_name, pids in by_ds.items():
        sweeps = {k: list(v) for k, v in e["sweeps"].items()}
        sweeps["data_fraction"] = sorted(set(sweeps["data_fraction"]) | set(e.get("extra_data_fraction", {}).get(ds_name, [])))
        if quick:
            sweeps = {k: [v[0], v[-1]] for k, v in sweeps.items()}
        for pid in pids:
            pair = resolve_pair(pid)
            syn = bool(pair.dataset.meta.get("synthetic", False))
            print(f"  E4 {ds_name}/{pid}", flush=True)
            for sweep, values in sweeps.items():
                for val in values:
                    frac = float(val) if sweep == "data_fraction" else float(d["data_fraction"])
                    vfrac = float(val) if sweep == "view_fraction" else float(d["view_fraction"])
                    ds, q1, q2 = pair_on_sample(pair, frac, seed)
                    views = _views(ds, vfrac, seed)
                    n_views = len(views) if views is not None else len(enumerate_views(ds))
                    over = {sweep: val} if sweep in PARAM_SWEEPS else {}
                    params = make_params(d, n_views, len(ds.explain_attrs), **over)
                    for method in METHODS:
                        for r in range(1 if method == "B2" else repeats):
                            out = run_method(method, ds, q1, q2, params, views=views, rng=np.random.default_rng([seed, r]),
                                             stats=route, gamma_eval=float(d["gamma_eval"]),
                                             b2_max_subsets=int(d["b2_max_subsets"]))
                            rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "sweep": sweep, "value": val,
                                         "method": method, "repeat": r, "N": ds.N, "P": n_views, "k": params.k,
                                         "epsilon": params.epsilon, "tau": params.tau, "gamma": params.gamma,
                                         "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s,
                                         "estimated": out.estimated, "b2_subsets": out.extra.get("subsets"),
                                         "route": "/".join(route.values())})
            write_raw(pd.DataFrame(rows), EXP, "runtime", base)  # checkpoint after every pair
    write_json(run_metadata(cfg, experiment=EXP, repeats=repeats, route=route), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
