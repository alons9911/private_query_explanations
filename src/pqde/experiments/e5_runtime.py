"""E5 -- what privacy costs in running time (Section 5.3.2, Figure 8).

Per pair: one-off cache build, per-invocation time of the private algorithm,
B1 and B3, the B2 exhaustive search, and the end-to-end time (cache build +
one private invocation) -- the numbers the paper lists as TODO for the CQA and
StackOverflow pairs.  Also B2's growth with the candidate pool size.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .. import plotting
from ..algorithm import explain
from ..baselines import b1, b2_candidates, b3, exhaustive_best
from ..pairs import resolve_pair
from .common import out_dir, params_from, run_metadata, write_csv, write_json


def _median_ms(fn, repeats: int) -> float:
    ts = []
    for r in range(repeats):
        t0 = time.perf_counter()
        fn(r)
        ts.append(1e3 * (time.perf_counter() - t0))
    return float(np.median(ts))


def run(cfg: dict, pairs: list[str] | None = None, base=None, quick: bool = False) -> dict:
    e = cfg["e5"]
    d = cfg["defaults"]
    repeats = 3 if quick else int(e["repeats"])
    pairs = pairs or e["pairs"]
    params = params_from(d)
    rows = []
    for pid in pairs:
        pair = resolve_pair(pid)
        cache = pair.cache()  # fresh build so the build time is measured here
        builds = [cache.build_seconds] + [pair.cache().build_seconds for _ in range(2)]
        priv = _median_ms(lambda r: explain(cache, params, np.random.default_rng(r)), repeats)
        t_b1 = _median_ms(lambda r: b1(cache, params), repeats)
        t_b3 = _median_ms(lambda r: b3(cache, params), repeats)
        t0 = time.perf_counter()
        cands, scores, aidx = b2_candidates(cache, params)
        exhaustive_best(scores, aidx, params.k, params.lam)
        t_b2 = 1e3 * (time.perf_counter() - t0)
        build_s = float(np.median(builds))
        rows.append({"pair": pid, "dataset": pair.dataset.name, "synthetic": bool(pair.dataset.meta.get("synthetic")),
                     "N": pair.dataset.N, "|P|": cache.n_views, "cache_build_s": build_s, "private_ms": priv,
                     "B1_ms": t_b1, "B3_ms": t_b3, "B2_ms": t_b2, "B2_pool": len(cands),
                     "end_to_end_s": build_s + priv / 1e3})
        print(f"  E5 {pid}: build {build_s:.3f}s  private {priv:.2f}ms  B1 {t_b1:.2f}ms  B3 {t_b3:.2f}ms  "
              f"B2 {t_b2:.0f}ms (pool {len(cands)})")
    per_pair = pd.DataFrame(rows)
    methods = pd.DataFrame({"method": ["private", "B1", "B3", "B2"],
                            "ms": [per_pair.private_ms.median(), per_pair.B1_ms.median(), per_pair.B3_ms.median(),
                                   per_pair.B2_ms.median()]})
    # B2 growth with the candidate pool
    pid = e["b2_pair"] if e["b2_pair"] in pairs or pairs == e["pairs"] else pairs[0]
    pair = resolve_pair(pid)
    cache = pair.cache()
    cands, scores, aidx = b2_candidates(cache, params)
    priv_s = _median_ms(lambda r: explain(cache, params, np.random.default_rng(r)), repeats) / 1e3
    grow = []
    order = np.argsort(-scores, kind="stable")
    for size in e["b2_pool_sizes"]:
        if size > len(scores):
            continue
        keep = np.sort(order[:size])  # keeps the (attribute, score desc) order
        t0 = time.perf_counter()
        best, _, n_sub = exhaustive_best(scores[keep], aidx[keep], params.k, params.lam)
        grow.append({"pair": pid, "pool_size": size, "subsets": n_sub, "seconds": time.perf_counter() - t0,
                     "private_s": priv_s})
    grow = pd.DataFrame(grow)
    od = out_dir("e5", base)
    write_csv(per_pair, od / "runtime_per_pair.csv")
    write_csv(methods, od / "runtime_methods.csv")
    write_csv(grow, od / "b2_growth.csv")
    write_json(run_metadata(cfg, experiment="e5", pairs=pairs, repeats=repeats), od / "metadata.json")
    plotting.plot_runtime(methods, grow, od / "fig8_runtime")
    return {"per_pair": per_pair, "methods": methods, "b2_growth": grow}
