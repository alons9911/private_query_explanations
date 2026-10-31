"""E4 -- running time against k, N, eps, |P|, tau and gamma (Section 5.3.2, Figure 7).

The one-off cache build (two passes over D) is timed separately from the
per-invocation mechanism (view stage + k selection rounds + release).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..pairs import pair_cache, resolve_pair
from ..query import parse
from ..stats import build_cache
from ..views import enumerate_views
from .common import out_dir, params_from, run_metadata, write_csv, write_json


def _mech_ms(cache, params, repeats: int, seed: int = 0) -> float:
    times = []
    for r in range(repeats):
        res = explain(cache, params, np.random.default_rng([seed, r]))
        times.append(res.timings["mechanism_ms"])
    return float(np.median(times))


def _n_sweep(pair_id: str, sizes: list[int], params, repeats: int, seed: int) -> pd.DataFrame:
    pair = resolve_pair(pair_id)
    rows = []
    for n in sizes:
        ds = pair.dataset.subsample(int(n), seed=seed, replace=int(n) > pair.dataset.N)
        q1 = parse(pair.q1_sql).evaluate(ds.raw)
        q2 = parse(pair.q2_sql).evaluate(ds.raw) if not pair.q2_sql.startswith("Q_Sigma") else None
        if q2 is None:
            raise ValueError("N sweep is defined for refinement/contrast pairs")
        builds = []
        for _ in range(3):
            cache = build_cache(ds, q1, q2)
            builds.append(cache.build_seconds)
        rows.append({"pair": pair_id, "N": int(n), "build_s": float(np.median(builds)),
                     "mechanism_ms": _mech_ms(cache, params, repeats)})
    return pd.DataFrame(rows)


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    e = cfg["e4"]
    d = cfg["defaults"]
    seed = int(d["seed"])
    repeats = 3 if quick else int(e["repeats"])
    pid = (pairs or [e["pair"]])[0]
    pair = resolve_pair(pid)
    cache = pair_cache(pid)
    base_params = params_from(d)
    panels = {}
    panels["k"] = pd.DataFrame([{"k": k, "mechanism_ms": _mech_ms(cache, base_params.with_(k=int(k)), repeats)}
                                for k in e["ks"]])
    sizes = [int(round(f * pair.dataset.N)) for f in e["n_fractions"]]
    panels["N"] = _n_sweep(pid, sizes, base_params, repeats, seed)
    panels["epsilon"] = pd.DataFrame([{"epsilon": x, "mechanism_ms": _mech_ms(cache, base_params.with_(epsilon=float(x)), repeats)}
                                      for x in e["epsilons"]])
    all_views = enumerate_views(pair.dataset)
    rng = np.random.default_rng(seed)
    prow = []
    for s in e["view_pool_sizes"]:
        s = int(min(s, len(all_views)))
        idx = np.sort(rng.choice(len(all_views), size=s, replace=False))
        c = build_cache(pair.dataset, pair.q1, pair.q2, views=[all_views[i] for i in idx])
        prow.append({"P": s, "build_s": c.build_seconds, "mechanism_ms": _mech_ms(c, base_params, repeats)})
    panels["P"] = pd.DataFrame(prow)
    panels["tau"] = pd.DataFrame([
        {"tau_percent": pc, "tau": max(1, int(round(pc / 100 * cache.n_views))),
         "mechanism_ms": _mech_ms(cache, base_params.with_(tau=max(1, int(round(pc / 100 * cache.n_views)))), repeats)}
        for pc in e["tau_percent_of_P"]])
    panels["gamma"] = pd.DataFrame([
        {"gamma_percent": pc, "gamma": pc / 100 * cache.N,
         "mechanism_ms": _mech_ms(cache, base_params.with_(gamma=max(pc / 100 * cache.N, 0.0)), repeats)}
        for pc in e["gamma_percent_of_N"]])
    od = out_dir("e4", base)
    for k, df in panels.items():
        write_csv(df, od / f"time_vs_{k}.csv")
    plotting.plot_scalability(panels, od / "fig7_scalability",
                              f"Running time of the algorithm ({pid}, {pair.dataset.name})")
    out = {"panels": panels}
    tax_pair = e.get("tax_pair")
    if tax_pair and not quick and (pairs is None):
        tax = _n_sweep(tax_pair, [int(x) for x in e["tax_rows"]], base_params, repeats, seed)
        write_csv(tax, od / "time_vs_N_tax.csv")
        plotting.plot_scalability({"N": tax}, od / "scalability_tax_N",
                                  f"Running time vs N on {tax_pair} (tax rows re-sampled from the benchmark file)")
        out["tax"] = tax
    write_json(run_metadata(cfg, experiment="e4", pair=pid, repeats=repeats), od / "metadata.json")
    return out
