"""Split the supplementary running-time run of TopTauExhaustive without pruning (EXH_TOPTAU, with PEEQ and
OPT in the same runs) into cloud shards tt-<n>: E4 sweeps k and tau, one job per (pair, sweep).

Job lengths: the candidates of the exact top-tau views of every pair (tau = 3k in the k sweep, the swept tau
at k = 5) give C(n, k) subsets at ~1.3 million per second; a run that would exceed the 30-minute limit is
extrapolated in seconds (3 runs), one that fits runs 10 times; plus 10 runs of PEEQ and OPT per point.
Writes scripts/shards/tt-<n>.jobs and results/toptau_plan.csv.

Usage: python scripts/plan_toptau_shards.py [n_shards]
"""
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "src")
from pqde.baselines import exact_top_views  # noqa: E402
from pqde.pairs import resolve_pair  # noqa: E402
from pqde.runner import ORIGINAL_ROUTE  # noqa: E402
from pqde.stats import build_cache  # noqa: E402
from pqde.views import enumerate_views  # noqa: E402

N_SHARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
RATE, LIMIT, SLOTS = 1.3e6, 1800.0, 4
cfg = yaml.safe_load(open("configs/experiments.yaml"))
ERICA = ["EA1", "EA2", "EA4", "EC1", "EC2", "EC3", "EH1", "EH2", "EH3", "EH5"]
PAIRS = list(cfg["pairs"]) + ERICA
KS = cfg["e4"]["sweeps"]["k"]
TAUS = cfg["e4"]["sweeps"]["tau"]
pre = pd.read_csv("results_preview/e5/raw/default_point.csv")
peeq = pre[pre.method.isin(["PRIV_EXPL", "OPT"])].groupby("pair").total_s.median().groupby(level=0).sum()
cache_file = Path("results/toptau_pools.json")
pools = json.loads(cache_file.read_text()) if cache_file.exists() else {}
rows = []
for pid in PAIRS:
    if pid not in pools:
        p = resolve_pair(pid)
        c = build_cache(p.dataset, p.q1, p.q2, **ORIGINAL_ROUTE)
        nv = len(enumerate_views(p.dataset))
        taus = sorted({min(3 * k, nv) for k in KS} | {nv if str(t) == "all" else min(int(t), nv) for t in TAUS})
        pools[pid] = {str(t): int(np.sum(~np.isnan(c.hd_matrix(0.0, exact_top_views(c, t))))) for t in taus}
        pools[pid]["P"] = nv
        cache_file.write_text(json.dumps(pools, indent=1))
    pl, nv = pools[pid], pools[pid]["P"]
    ref = float(peeq.get(pid, 1.0)) * 1.2

    def run_h(n, k):
        t = math.comb(n, k) / RATE
        return (10 * (t + ref) if t <= LIMIT else 3 * (ref + 5) + 7 * ref) / 3600
    hk = sum(run_h(pl[str(min(3 * k, nv))], k) for k in KS)
    ht = sum(run_h(pl[str(nv if str(t) == "all" else min(int(t), nv))], 5) for t in TAUS)
    rows += [(hk, pid, "k"), (ht, pid, "tau")]
plan = pd.DataFrame(rows, columns=["hours", "pair", "sweep"]).sort_values("hours", ascending=False)
plan.to_csv("results/toptau_plan.csv", index=False)


def makespan(js):
    slots = [0.0] * SLOTS
    for h, *_ in sorted(js, key=lambda j: -j[0]):
        heapq.heappush(slots, heapq.heappop(slots) + h)
    return max(slots)


jobs = list(plan.itertuples(index=False, name=None))
shards = [[] for _ in range(N_SHARDS)]
for j in jobs:
    best = min(range(N_SHARDS), key=lambda s: (makespan(shards[s] + [j]), len(shards[s])))
    shards[best].append(j)
for n, js in enumerate(shards, 1):
    js.sort(key=lambda j: -j[0])
    with open(f"scripts/shards/tt-{n}.jobs", "w") as f:
        f.write("# SUPPLEMENTARY run: TopTauExhaustive without pruning (EXH_TOPTAU) + PEEQ and OPT, E4 sweeps k and tau;\n"
                "# run with CONFIG=configs/experiments_toptau.yaml (user, 2026-11-28).\n"
                f"# Estimated makespan {makespan(js):.1f} h (4 jobs at a time), longest job first.\n")
        for h, pid, sw in js:
            f.write(f"e4 {pid} {sw}\n")
    print(f"tt-{n}: {len(js)} jobs, est. makespan {makespan(js):.1f} h, work {sum(j[0] for j in js):.1f} h")
print("total work", round(plan.hours.sum(), 1), "h; longest", plan.head(4).round(2).values.tolist())
