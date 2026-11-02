"""E5 -- what privacy, exhaustiveness and the optimisations cost, end to end (Section 5.3.2, Figure 8).

(a) every pair at the defaults: end-to-end time of PRIV_EXPL, OPT_PRIV_EXPL, B1, B2, B3;
(b) identity: OPT_PRIV_EXPL releases exactly what PRIV_EXPL releases with the same randomness;
(c) B2 against the size of its candidate pool (end to end: statistics + enumeration);
(d) the statistics routes on PRIV_EXPL: original (Section 4.2), O1 alone, O1 + O3.

Every timed run has the time limit ``defaults.timeout_s``.
Raw data in ``results/e5/raw/*.csv``; ``pqde plot e5`` rebuilds the figures.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .. import plotting, timeouts
from ..algorithm import explain
from ..baselines import b2_candidates, exhaustive_best
from ..pairs import resolve_pair
from ..runner import METHODS, ORIGINAL_ROUTE, OPT_ROUTE, run_method, time_methods
from ..stats import build_cache
from .common import (make_params, out_dir, pairs_by_dataset, read_raw, run_metadata, to_markdown, write_csv,
                     write_json, write_raw)

EXP = "e5"
ROUTE_NAMES = {"direct/general/lazy": "original (Sec. 4.2)", "grouped/general/eager": "O1",
               "grouped/general/lazy": "O1 + O3 (OPT_PRIV_EXPL)"}


def plot(cfg: dict, base=None) -> None:
    od = out_dir(EXP, base)
    dp = read_raw(EXP, "default_point", base)
    syn = {r.dataset: bool(r.synthetic) for r in dp.itertuples()}
    per_pair = dp.groupby(["dataset", "pair", "method"], as_index=False, sort=False).agg(
        total_s=("total_s", "median"), build_s=("build_s", "median"), mech_s=("mech_s", "median"),
        timeout=("timeout", "max"))
    write_csv(per_pair, od / "default_point_per_pair.csv")
    wide = per_pair.pivot_table(index=["dataset", "pair"], columns="method", values="total_s", sort=False).reset_index()
    wide = wide[["dataset", "pair"] + [m for m in METHODS if m in wide.columns]]
    if "PRIV_EXPL" in wide and "OPT_PRIV_EXPL" in wide:
        wide["speedup OPT"] = wide["PRIV_EXPL"] / wide["OPT_PRIV_EXPL"]
    (od / "default_point_per_pair.md").write_text(to_markdown(wide, floatfmt="{:.4g}"))
    plotting.plot_method_bars(per_pair, od / "fig8a_methods", "End-to-end time at the defaults (mean over pairs)", syn)
    for name, fn in (("b2_growth", lambda g: plotting.plot_b2_growth(g, od / "fig8b_b2_growth", syn)),
                     ("routes", None), ("identity", None)):
        try:
            df = read_raw(EXP, name, base)
        except FileNotFoundError:
            continue
        if name == "b2_growth":
            fn(df)
        elif name == "routes":
            rr = df.groupby(["dataset", "pair", "route"], as_index=False, sort=False).agg(
                total_s=("total_s", "median"), build_s=("build_s", "median"))
            rr["route"] = rr.route.map(lambda r: ROUTE_NAMES.get(r, r))
            write_csv(rr, od / "routes_per_pair.csv")
            piv = rr.groupby(["dataset", "route"], as_index=False, sort=False).total_s.mean().pivot(
                index="dataset", columns="route", values="total_s").reset_index()
            (od / "routes.md").write_text(to_markdown(piv, floatfmt="{:.4g}"))
            plotting.plot_routes(rr, od / "routes", syn)
        else:
            (od / "identity.md").write_text(to_markdown(df, floatfmt="{:.3g}"))


def _identical(ds, q1, q2, params, seed: int, runs: int = 5) -> dict:
    a = build_cache(ds, q1, q2, **ORIGINAL_ROUTE)
    b = build_cache(ds, q1, q2, **OPT_ROUTE)
    same = 0
    for r in range(runs):
        ra = explain(a.fresh_copy(), params, np.random.default_rng([seed, r]))
        rb = explain(b.fresh_copy(), params, np.random.default_rng([seed, r]))
        ok = ra.retained.tolist() == rb.retained.tolist() and ra.selections == rb.selections and all(
            np.array_equal(x.noisy_h1, y.noisy_h1) and np.array_equal(x.noisy_h2, y.noisy_h2)
            for x, y in zip(ra.explanations, rb.explanations))
        same += int(ok)
    return {"runs": runs, "identical_runs": same,
            "max_abs_use_diff": float(np.max(np.abs(a.use - b.use)))}


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    d = cfg["defaults"]
    e = cfg[EXP]
    seed = int(d["seed"])
    timeout_s = float(d["timeout_s"])
    repeats = 1 if quick else int(e["repeats"])
    timeout_reps = int(d.get("timeout_repeats", 3))
    pairs = pairs or cfg.get("runtime_pairs", cfg["pairs"])
    by_ds = pairs_by_dataset(pairs, cfg.get("datasets"))
    dp_rows, g_rows, r_rows, id_rows = [], [], [], []
    for ds_name, pids in by_ds.items():
        for pid in pids:
            pair = resolve_pair(pid)
            syn = bool(pair.dataset.meta.get("synthetic", False))
            ds, q1, q2 = pair.dataset, pair.q1, pair.q2
            from ..views import enumerate_views

            params = make_params(d, len(enumerate_views(ds)), len(ds.explain_attrs))
            # (a) every method end to end at the defaults, every method in every repeat
            # (a method that hits the time limit: timeout_repeats runs)
            n_to: dict = {}
            for r in range(repeats):
                methods = tuple(m for m in METHODS if n_to.get(m, 0) < timeout_reps)
                for out in time_methods(ds, q1, q2, params, methods=methods, seed=seed, repeat=r,
                                        gamma_eval=float(d["gamma_eval"]), timeout_s=timeout_s):
                    n_to[out.method] = n_to.get(out.method, 0) + int(out.timeout)
                    dp_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "method": out.method, "repeat": r,
                                    "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s,
                                    "timeout": out.timeout})
            # (b) identical releases
            id_rows.append({"dataset": ds_name, "pair": pid,
                            **_identical(ds, q1, q2, params, seed, 2 if quick else int(e.get("identity_runs", 10)))})
            priv = float(np.median([x["total_s"] for x in dp_rows if x["pair"] == pid and x["method"] == "PRIV_EXPL"]))
            # (c) B2 against its candidate pool, end to end (original route)
            for size in (e["b2_pool_sizes"] if not quick else e["b2_pool_sizes"][:2]):
                n_to_g = 0
                for r in range(1 if quick else int(e.get("b2_growth_repeats", 10))):
                    if n_to_g >= timeout_reps:
                        break
                    t0 = time.perf_counter()
                    try:
                        with timeouts.deadline(timeout_s):
                            cache = build_cache(ds, q1, q2, **ORIGINAL_ROUTE)
                            cands, scores, aidx = b2_candidates(cache, params, float(d["gamma_eval"]))
                            if size > len(scores):
                                break
                            keep = np.sort(np.argsort(-scores, kind="stable")[:size])
                            _, _, n_sub, _ = exhaustive_best(scores[keep], aidx[keep], params.k, params.lam)
                        total, to = time.perf_counter() - t0, False
                    except timeouts.RunTimeout:
                        total, to, n_sub = timeout_s, True, None
                        n_to_g += 1
                    g_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "pool_size": size, "repeat": r,
                                   "subsets": n_sub, "b2_total_s": total, "timeout": to, "priv_total_s": priv})
            # (d) statistics routes, PRIV_EXPL end to end
            for rt in e["routes"]:
                name = f"{rt['mode']}/{rt['rep']}/{rt['hist']}"
                for r in range(1 if quick else int(e.get("route_repeats", 10))):
                    out = run_method("PRIV_EXPL", ds, q1, q2, params, rng=np.random.default_rng([seed, r]), route=rt,
                                     timeout_s=timeout_s)
                    r_rows.append({"dataset": ds_name, "synthetic": syn, "pair": pid, "route": name, "repeat": r,
                                   "build_s": out.build_s, "mech_s": out.mech_s, "total_s": out.total_s,
                                   "timeout": out.timeout})
            print(f"  E5 {pid}: " + "  ".join(
                f"{m} {np.median([x['total_s'] for x in dp_rows if x['pair'] == pid and x['method'] == m]):.3f}s"
                for m in METHODS) + f"  identical {id_rows[-1]['identical_runs']}/{id_rows[-1]['runs']}", flush=True)
            for name, rows in (("default_point", dp_rows), ("b2_growth", g_rows), ("routes", r_rows),
                               ("identity", id_rows)):
                write_raw(pd.DataFrame(rows), EXP, name, base)
    write_json(run_metadata(cfg, experiment=EXP, repeats=repeats, timeout_s=timeout_s), out_dir(EXP, base) / "metadata.json")
    plot(cfg, base)
    return {}
