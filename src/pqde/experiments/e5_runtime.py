"""E5 -- what privacy and exhaustiveness cost, end to end (Section 5.3.2, Figure 8).

(a) every pair at the defaults: end-to-end time of PRIV_EXPL, B1, B2, B3;
(b) B2 against the size of its candidate pool (end to end: statistics + enumeration);
(c) the statistics routes: PRIV_EXPL end to end with the direct route of
    Section 4.2 and with the optimisations O1-O3.

Raw data in ``results/e5/raw/{default_point,b2_growth,routes}.csv``; ``pqde plot e5``.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..baselines import b2_candidates, exhaustive_best
from ..pairs import resolve_pair
from ..runner import METHODS, run_method
from ..stats import build_cache
from .common import (make_params, out_dir, pairs_by_dataset, read_raw, run_metadata, stats_route, to_markdown,
                     write_csv, write_json, write_raw)

EXP = "e5"


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    dp = read_raw(EXP, "default_point", base)
    syn = {r.dataset: bool(r.synthetic) for r in dp.itertuples()}
    per_pair = dp.groupby(["dataset", "pair", "method"], as_index=False, sort=False).agg(
        total_s=("total_s", "median"), build_s=("build_s", "median"), mech_s=("mech_s", "median"),
        estimated=("estimated", "max"))
    write_csv(per_pair, od / "default_point_per_pair.csv")
    wide = per_pair.pivot_table(index=["dataset", "pair"], columns="method", values="total_s", sort=False).reset_index()
    (od / "default_point_per_pair.md").write_text(to_markdown(wide, floatfmt="{:.4g}"))
    plotting.plot_method_bars(per_pair, od / "fig8a_methods", "End-to-end time at the defaults (mean over pairs)", syn)
    try:
        g = read_raw(EXP, "b2_growth", base)
        plotting.plot_b2_growth(g, od / "fig8b_b2_growth", syn)
    except FileNotFoundError:
        pass
    try:
        r = read_raw(EXP, "routes", base)
        rr = r.groupby(["dataset", "pair", "route"], as_index=False, sort=False).agg(total_s=("total_s", "median"),
                                                                                    build_s=("build_s", "median"))
        write_csv(rr, od / "routes_per_pair.csv")
        piv = rr.groupby(["dataset", "route"], as_index=False, sort=False).total_s.mean().pivot(
            index="dataset", columns="route", values="total_s").reset_index()
        (od / "routes.md").write_text(to_markdown(piv, floatfmt="{:.4g}"))
        plotting.plot_routes(rr, od / "routes", syn)
    except FileNotFoundError:
        pass


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    d = cfg["defaults"]
    e = cfg[EXP]
    seed = int(d["seed"])
    route = stats_route(d)
    repeats = 1 if quick else int(e["repeats"])
    pairs = pairs or cfg["pairs"]
    by_ds = pairs_by_dataset(pairs, cfg.get("datasets"))
    dp_rows, g_rows, r_rows = [], [], []
    for ds_name, pids in by_ds.items():
        for pid in pids:
            pair = resolve_pair(pid)
            syn = bool(pair.dataset.meta.get("synthetic", False))
            ds, q1, q2 = pair.dataset, pair.q1, pair.q2
            c0 = build_cache(ds, q1, q2, **route)
            params = make_params(d, c0.n_views, len(ds.explain_attrs))
            # (a) every method end to end at the defaults
            for method in METHODS:
                for r in range(1 if method == "B2" else repeats):
                    out = run_method(method, ds, q1, q2, params, rng=np.random.default_rng([seed, r]), stats=route,
                                     gamma_eval=float(d["gamma_eval"]), b2_max_subsets=int(d["b2_max_subsets"]))
                    dp_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "method": method, "repeat": r,
                                    "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s,
                                    "estimated": out.estimated})
            priv = float(np.median([x["total_s"] for x in dp_rows if x["pair"] == pid and x["method"] == "PRIV_EXPL"]))
            # (b) B2 against its candidate pool, end to end
            sizes = e["b2_pool_sizes"] if not quick else e["b2_pool_sizes"][:2]
            for size in sizes:
                t0 = time.perf_counter()
                cache = build_cache(ds, q1, q2, **route)
                cands, scores, aidx = b2_candidates(cache, params, float(d["gamma_eval"]))
                if size > len(scores):
                    continue
                keep = np.sort(np.argsort(-scores, kind="stable")[:size])
                _, _, n_sub, info = exhaustive_best(scores[keep], aidx[keep], params.k, params.lam)
                g_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "pool_size": size, "subsets": n_sub,
                               "b2_total_s": time.perf_counter() - t0, "priv_total_s": priv})
            # (c) statistics routes, PRIV_EXPL end to end
            for rt in e["routes"]:
                name = f"{rt['mode']}/{rt['rep']}/{rt['hist']}"
                for r in range(1 if quick else max(1, repeats // 2 + 1)):
                    out = run_method("PRIV_EXPL", ds, q1, q2, params, rng=np.random.default_rng([seed, r]), stats=rt)
                    r_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "route": name, "repeat": r,
                                   "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s})
            print(f"  E5 {pid}: " + "  ".join(
                f"{m} {np.median([x['total_s'] for x in dp_rows if x['pair'] == pid and x['method'] == m]):.3f}s"
                for m in METHODS), flush=True)
            write_raw(pd.DataFrame(dp_rows), EXP, "default_point", base)
            write_raw(pd.DataFrame(g_rows), EXP, "b2_growth", base)
            write_raw(pd.DataFrame(r_rows), EXP, "routes", base)
    write_json(run_metadata(cfg, experiment=EXP, repeats=repeats, route=route), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
